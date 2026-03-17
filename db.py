import sqlite3
from pathlib import Path

DB_PATH = Path("recruiter.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT,
                first_name   TEXT,
                last_name    TEXT,
                company      TEXT,
                role         TEXT,
                email        TEXT UNIQUE,
                linkedin_url TEXT,
                source_url   TEXT,
                bio          TEXT,
                status       TEXT DEFAULT 'discovered',
                created_at   TEXT DEFAULT (datetime('now')),
                updated_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS emails (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id),
                direction    TEXT,
                subject      TEXT,
                body         TEXT,
                gmail_id     TEXT,
                thread_id    TEXT,
                sent_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id),
                calendar_link TEXT,
                status       TEXT DEFAULT 'pending',
                created_at   TEXT DEFAULT (datetime('now'))
            );
        """)


def add_candidate(data: dict) -> int | None:
    try:
        with get_conn() as conn:
            cur = conn.execute("""
                INSERT OR IGNORE INTO candidates
                (name, first_name, last_name, company, role, email, linkedin_url, source_url, bio)
                VALUES (:name, :first_name, :last_name, :company, :role, :email, :linkedin_url, :source_url, :bio)
            """, data)
            return cur.lastrowid if cur.lastrowid else None
    except Exception as e:
        print(f"  DB error: {e}")
        return None


def get_candidates(status: str = None, company: str = None) -> list:
    with get_conn() as conn:
        if status and company:
            return conn.execute(
                "SELECT * FROM candidates WHERE status=? AND company=? ORDER BY created_at DESC",
                (status, company),
            ).fetchall()
        if status:
            return conn.execute(
                "SELECT * FROM candidates WHERE status=? ORDER BY created_at DESC", (status,)
            ).fetchall()
        if company:
            return conn.execute(
                "SELECT * FROM candidates WHERE company=? ORDER BY created_at DESC", (company,)
            ).fetchall()
        return conn.execute("SELECT * FROM candidates ORDER BY created_at DESC").fetchall()


def update_candidate(candidate_id: int, **fields):
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [candidate_id]
    with get_conn() as conn:
        conn.execute(
            f"UPDATE candidates SET {set_clause}, updated_at=datetime('now') WHERE id=?", values
        )


def save_email(candidate_id: int, direction: str, subject: str, body: str,
               gmail_id: str = None, thread_id: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO emails (candidate_id, direction, subject, body, gmail_id, thread_id) VALUES (?,?,?,?,?,?)",
            (candidate_id, direction, subject, body, gmail_id, thread_id),
        )


def get_candidate_emails(candidate_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM emails WHERE candidate_id=? ORDER BY sent_at ASC", (candidate_id,)
        ).fetchall()


def get_candidate_by_email(email: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM candidates WHERE email=?", (email,)).fetchone()
