#!/usr/bin/env python3
"""
AI Recruiter Bot — CLI
Usage: python main.py --help
"""
import os
import click
from rich.console import Console
from rich.table import Table

import db
from searcher     import search_candidates
from email_finder import find_email
from outreach     import generate_outreach, generate_reply
from gmail_client import send_email, get_unread_replies
from classifier   import classify_reply
from watcher      import watch as _watch

console = Console()


# ─── helpers ──────────────────────────────────────────────────────────────────

def _load_job(job_arg: str) -> str:
    if os.path.isfile(job_arg):
        return open(job_arg).read().strip()
    return job_arg.strip()


# ─── CLI group ────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """🤖 AI Recruiter Bot — automated candidate sourcing & outreach"""
    db.init_db()


# ─── search ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--company", "-c", required=True, help="Target company, e.g. 'OpenAI'")
@click.option("--role",    "-r", required=True, help="Role keywords, e.g. 'ML Engineer'")
@click.option("--limit",   "-n", default=20,    show_default=True)
def search(company, role, limit):
    """Search Google / Google Scholar for candidates at a target company."""
    console.print(f"\n🔍 Searching [bold cyan]{role}[/] at [bold yellow]{company}[/]…\n")
    candidates = search_candidates(company, role, limit)

    added = 0
    for c in candidates:
        cid = db.add_candidate(c)
        status = "✅ added" if cid else "⚠️  dup"
        console.print(f"  {status}  [bold]{c['name']}[/]  —  {c['role'] or '(role unknown)'}")
        if cid:
            added += 1

    console.print(f"\n[green]Done. {added} new candidates saved.[/]\n")


# ─── find-emails ──────────────────────────────────────────────────────────────

@cli.command("find-emails")
@click.option("--company", "-c", default=None, help="Filter by company")
def find_emails(company):
    """Discover email addresses for candidates with status='discovered'."""
    rows = [c for c in db.get_candidates(status="discovered", company=company)
            if not c["email"]]
    console.print(f"\n📧 Finding emails for {len(rows)} candidates…\n")

    for c in rows:
        email = find_email(c["first_name"], c["last_name"], c["company"])
        if email:
            db.update_candidate(c["id"], email=email)
            console.print(f"  ✅ {c['name']}  →  [cyan]{email}[/]")
        else:
            console.print(f"  ❌ {c['name']}  —  no email found")

    console.print("\n[green]Email discovery complete.[/]\n")


# ─── send-outreach ────────────────────────────────────────────────────────────

@cli.command("send-outreach")
@click.option("--company",  "-c", required=True)
@click.option("--job",      "-j", required=True,
              help="Job description text, or path to a .txt file")
@click.option("--limit",    "-n", default=10, show_default=True)
@click.option("--dry-run",  is_flag=True, help="Preview without sending")
def send_outreach(company, job, limit, dry_run):
    """Generate and send personalized outreach emails via Gmail."""
    job_desc   = _load_job(job)
    candidates = [c for c in db.get_candidates(status="discovered", company=company)
                  if c["email"]][:limit]

    if not candidates:
        console.print("[yellow]No candidates with emails found. Run find-emails first.[/]")
        return

    console.print(f"\n✉️  {'[DRY RUN] ' if dry_run else ''}Sending outreach to "
                  f"{len(candidates)} candidates at {company}…\n")

    for c in candidates:
        console.print(f"  ✍️  Generating email for [bold]{c['name']}[/]…")
        subject, body = generate_outreach(dict(c), job_desc)

        if dry_run:
            console.rule("[dim]PREVIEW[/]")
            console.print(f"[bold]TO:[/]      {c['email']}")
            console.print(f"[bold]SUBJECT:[/] {subject}\n")
            console.print(body)
            console.rule()
            console.print()
        else:
            gmail_id = send_email(c["email"], subject, body)
            db.save_email(c["id"], "out", subject, body, gmail_id=gmail_id)
            db.update_candidate(c["id"], status="emailed")
            console.print(f"  ✅ Sent → {c['email']}")

    console.print(f"\n[green]Outreach done{'  (dry run)' if dry_run else ''}.[/]\n")


# ─── check-replies ────────────────────────────────────────────────────────────

@cli.command("check-replies")
@click.option("--auto-reply", is_flag=True,
              help="Automatically reply to interested / scheduling / question emails")
@click.option("--job", "-j", default="",
              help="Job description context for auto-replies")
def check_replies(auto_reply, job):
    """Check Gmail for candidate replies; optionally auto-respond."""
    job_desc = _load_job(job) if job else ""
    console.print("\n📬 Checking inbox for candidate replies…\n")

    inbound = get_unread_replies()
    if not inbound:
        console.print("[dim]No new replies.[/]\n")
        return

    status_map = {
        "interested":     "interested",
        "scheduling":     "interested",
        "question":       "replied",
        "not_interested": "not_interested",
        "out_of_office":  None,   # no status change
        "other":          None,
    }

    for msg in inbound:
        candidate = db.get_candidate_by_email(msg["from_email"])
        if not candidate:
            console.print(f"  ⚠️  Unknown sender: {msg['from_email']} — skipping")
            continue

        category = classify_reply(msg["body"], candidate["name"])
        label_color = {
            "interested": "green", "scheduling": "cyan",
            "question": "yellow", "not_interested": "red",
        }.get(category, "dim")

        console.print(
            f"  📨 [{label_color}]{category.upper()}[/{label_color}]  "
            f"[bold]{candidate['name']}[/]  <{msg['from_email']}>  "
            f"— \"{msg['subject'][:55]}\""
        )

        # Save incoming
        db.save_email(candidate["id"], "in", msg["subject"], msg["body"],
                      gmail_id=msg["gmail_id"], thread_id=msg["thread_id"])

        # Update status
        new_status = status_map.get(category)
        if new_status:
            db.update_candidate(candidate["id"], status=new_status)

        # Auto-reply
        if auto_reply and category in ("interested", "scheduling", "question"):
            history      = [dict(e) for e in db.get_candidate_emails(candidate["id"])]
            reply_body   = generate_reply(dict(candidate), job_desc, history, category)
            reply_subject = ("Re: " + msg["subject"]) if not msg["subject"].startswith("Re:") \
                            else msg["subject"]
            send_email(msg["from_email"], reply_subject, reply_body,
                       thread_id=msg["thread_id"])
            db.save_email(candidate["id"], "out", reply_subject, reply_body,
                          thread_id=msg["thread_id"])
            console.print(f"    ↩️  Auto-replied to [bold]{candidate['name']}[/]")

    console.print("\n[green]Done processing replies.[/]\n")


# ─── list ─────────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--status",  "-s", default=None,
              help="Filter by status: discovered|emailed|replied|interested|not_interested|scheduled")
@click.option("--company", "-c", default=None)
def list_candidates(status, company):
    """Show all candidates in the database."""
    rows = db.get_candidates(status=status, company=company)
    if not rows:
        console.print("[dim]No candidates found.[/]")
        return

    table = Table(show_lines=True, highlight=True)
    table.add_column("ID",      style="dim",     width=4)
    table.add_column("Name",    style="bold",     min_width=16)
    table.add_column("Company", style="cyan",     min_width=12)
    table.add_column("Role",    style="yellow",   max_width=28)
    table.add_column("Email",   style="green",    min_width=20)
    table.add_column("Status",  style="magenta",  width=14)

    for c in rows:
        table.add_row(str(c["id"]), c["name"] or "—", c["company"] or "—",
                      c["role"] or "—", c["email"] or "—", c["status"] or "—")
    console.print(table)


# ─── run (full pipeline) ──────────────────────────────────────────────────────

@cli.command()
@click.option("--company", "-c", required=True)
@click.option("--role",    "-r", required=True)
@click.option("--job",     "-j", required=True, help="Job description or path to .txt")
@click.option("--limit",   "-n", default=15,    show_default=True)
@click.option("--dry-run", is_flag=True)
def run(company, role, job, limit, dry_run):
    """
    Full pipeline in one command:
    search → find-emails → send-outreach
    """
    ctx = click.get_current_context()
    ctx.invoke(search,        company=company, role=role,    limit=limit)
    ctx.invoke(find_emails,   company=company)
    ctx.invoke(send_outreach, company=company, job=job,
               limit=limit, dry_run=dry_run)


# ─── watch (autonomous daemon) ────────────────────────────────────────────────

@cli.command()
@click.option("--job",      "-j", required=True, help="Job description or path to .txt")
@click.option("--interval", "-i", default=15,    show_default=True,
              help="Check interval in minutes")
@click.option("--followup-days", "-f", default=5, show_default=True,
              help="Days of silence before sending a follow-up")
def watch(job, interval, followup_days):
    """
    Autonomous mode: check replies, auto-respond, and follow up — forever.

    \b
    Example:
        python main.py watch -j job.txt -i 15 -f 5
    """
    job_desc = _load_job(job)
    try:
        _watch(job_desc, interval_minutes=interval, followup_days=followup_days)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped.[/]\n")


if __name__ == "__main__":
    cli()
