"""
Autonomous watch loop:
  - Every N minutes: check Gmail for replies → classify → auto-reply
  - Every morning:   follow up candidates emailed 5+ days ago with no reply
"""
import time
from datetime import datetime, timedelta

from rich.console import Console
from rich.table   import Table
from rich.live    import Live
from rich.panel   import Panel
from rich.columns import Columns
from rich         import box

import db
from gmail_client import get_unread_replies, send_email
from outreach     import generate_reply, generate_outreach
from classifier   import classify_reply

console = Console()

STATUS_COLORS = {
    "discovered":    "dim",
    "emailed":       "cyan",
    "replied":       "yellow",
    "interested":    "green",
    "not_interested":"red",
    "scheduled":     "bold green",
}

STATUS_MAP = {
    "interested":     "interested",
    "scheduling":     "interested",
    "question":       "replied",
    "not_interested": "not_interested",
}


# ── Pipeline stats ─────────────────────────────────────────────────────────────

def _pipeline_table() -> Table:
    all_candidates = db.get_candidates()
    counts: dict[str, int] = {}
    for c in all_candidates:
        s = c["status"] or "discovered"
        counts[s] = counts.get(s, 0) + 1

    t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    t.add_column("Status",  style="bold", min_width=14)
    t.add_column("Count",   justify="right", min_width=6)

    order = ["discovered","emailed","replied","interested","not_interested","scheduled"]
    for s in order:
        n = counts.get(s, 0)
        color = STATUS_COLORS.get(s, "white")
        t.add_row(f"[{color}]{s}[/{color}]", str(n))
    t.add_row("[bold]TOTAL[/]", str(len(all_candidates)))
    return t


def _recent_activity(n: int = 8) -> Table:
    rows = db.get_candidates()[:n]
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold", min_width=50)
    t.add_column("Name",    min_width=16)
    t.add_column("Company", min_width=12, style="cyan")
    t.add_column("Status",  min_width=13)
    t.add_column("Updated", min_width=16, style="dim")
    for c in rows:
        color = STATUS_COLORS.get(c["status"], "white")
        t.add_row(
            c["name"] or "—",
            c["company"] or "—",
            f"[{color}]{c['status']}[/{color}]",
            (c["updated_at"] or "")[:16],
        )
    return t


def _render_panel(cycle: int, next_check: datetime, job_desc: str) -> Panel:
    now_str  = datetime.now().strftime("%H:%M:%S")
    next_str = next_check.strftime("%H:%M:%S")

    pipeline = _pipeline_table()
    activity = _recent_activity()

    body = Columns([pipeline, activity], equal=False, expand=True)
    title = (
        f"🤖  AI Recruiter Bot  │  cycle #{cycle}  │  "
        f"now {now_str}  │  next check {next_str}"
    )
    return Panel(body, title=title, border_style="bright_blue")


# ── Core actions ───────────────────────────────────────────────────────────────

def process_replies(job_desc: str) -> int:
    """Check Gmail, classify, auto-reply. Returns number processed."""
    inbound = get_unread_replies()
    processed = 0

    for msg in inbound:
        candidate = db.get_candidate_by_email(msg["from_email"])
        if not candidate:
            continue

        category = classify_reply(msg["body"], candidate["name"])
        db.save_email(candidate["id"], "in", msg["subject"], msg["body"],
                      gmail_id=msg["gmail_id"], thread_id=msg["thread_id"])

        new_status = STATUS_MAP.get(category)
        if new_status:
            db.update_candidate(candidate["id"], status=new_status)

        if category in ("interested", "scheduling", "question") and job_desc:
            history    = [dict(e) for e in db.get_candidate_emails(candidate["id"])]
            reply_body = generate_reply(dict(candidate), job_desc, history, category)
            subj       = msg["subject"] if msg["subject"].startswith("Re:") \
                         else f"Re: {msg['subject']}"
            send_email(msg["from_email"], subj, reply_body, thread_id=msg["thread_id"])
            db.save_email(candidate["id"], "out", subj, reply_body,
                          thread_id=msg["thread_id"])

        processed += 1

    return processed


def send_followups(job_desc: str, days: int = 5) -> int:
    """
    Find candidates in 'emailed' status with no reply for `days` days.
    Send a gentle follow-up bump.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(sep=" ")
    sent   = 0

    with db.get_conn() as conn:
        stale = conn.execute("""
            SELECT c.*
            FROM   candidates c
            WHERE  c.status = 'emailed'
            AND    c.updated_at < ?
            AND    c.email IS NOT NULL
            AND    NOT EXISTS (
                SELECT 1 FROM emails e
                WHERE  e.candidate_id = c.id
                AND    e.direction    = 'out'
                AND    e.sent_at      > ?
            )
        """, (cutoff, cutoff)).fetchall()

    for c in stale:
        history    = [dict(e) for e in db.get_candidate_emails(c["id"])]
        followup   = generate_reply(dict(c), job_desc, history, "followup")

        # Reuse original subject from first outbound email
        first_out  = next((e for e in history if e["direction"] == "out"), None)
        subj       = f"Re: {first_out['subject']}" if first_out else "Checking in"

        # Find thread_id from last email
        last_email = history[-1] if history else None
        thread_id  = last_email["thread_id"] if last_email else None

        send_email(c["email"], subj, followup, thread_id=thread_id)
        db.save_email(c["id"], "out", subj, followup, thread_id=thread_id)
        db.update_candidate(c["id"], status="emailed")   # keep status, reset timer
        sent += 1

    return sent


# ── Main watch loop ────────────────────────────────────────────────────────────

def watch(job_desc: str, interval_minutes: int = 15, followup_days: int = 5):
    """
    Autonomous watch loop. Runs until Ctrl-C.

    interval_minutes  — how often to check Gmail for new replies
    followup_days     — days of silence before sending a follow-up bump
    """
    cycle      = 0
    log_lines: list[str] = []

    def log(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        log_lines.append(f"[dim]{ts}[/dim]  {msg}")
        if len(log_lines) > 20:
            log_lines.pop(0)

    console.print(
        f"\n[bold bright_blue]🤖 Watch mode started[/]  "
        f"│  checking every [bold]{interval_minutes}m[/]  "
        f"│  follow-up after [bold]{followup_days}d[/]  "
        f"│  Press Ctrl-C to stop\n"
    )

    with Live(console=console, refresh_per_second=1, screen=False) as live:
        while True:
            cycle += 1
            next_check = datetime.now() + timedelta(minutes=interval_minutes)

            # ── check replies ──
            try:
                n_replies = process_replies(job_desc)
                if n_replies:
                    log(f"✉️  Processed [green]{n_replies}[/] repl{'y' if n_replies==1 else 'ies'}")
                else:
                    log("📭 No new replies")
            except Exception as e:
                log(f"[red]Reply check error:[/] {e}")

            # ── follow-ups (once per cycle, cheap check) ──
            try:
                n_fu = send_followups(job_desc, days=followup_days)
                if n_fu:
                    log(f"↩️  Sent [cyan]{n_fu}[/] follow-up{'s' if n_fu>1 else ''} "
                        f"(>{followup_days}d silent)")
            except Exception as e:
                log(f"[red]Follow-up error:[/] {e}")

            # ── render panel ──
            log_panel = Panel(
                "\n".join(log_lines) or "[dim]No activity yet[/]",
                title="Activity Log", border_style="dim", padding=(0, 1),
            )
            main_panel = _render_panel(cycle, next_check, job_desc)
            live.update(Panel(
                f"{main_panel}\n{log_panel}",
                border_style="bright_blue", padding=0,
            ))

            # ── wait, updating countdown each second ──
            for _ in range(interval_minutes * 60):
                next_check = datetime.now() + timedelta(
                    seconds=(interval_minutes * 60 - _)
                )
                live.update(Panel(
                    f"{_render_panel(cycle, next_check, job_desc)}\n{log_panel}",
                    border_style="bright_blue", padding=0,
                ))
                time.sleep(1)
