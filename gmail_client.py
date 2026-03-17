"""
Gmail API wrapper — send emails, fetch unread replies.
"""
import base64
import re
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import GMAIL_CREDS_PATH, GMAIL_TOKEN_PATH, SENDER_EMAIL

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _service():
    token_path = Path(GMAIL_TOKEN_PATH)
    creds_path = Path(GMAIL_CREDS_PATH)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(exist_ok=True)
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str, thread_id: str = None) -> str:
    """Send a plain-text email. Returns Gmail message ID."""
    svc = _service()
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"]      = to
    msg["from"]    = SENDER_EMAIL
    msg["subject"] = subject

    raw     = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id

    sent = svc.users().messages().send(userId="me", body=payload).execute()
    return sent["id"]


def _decode_body(payload: dict) -> str:
    """Extract plain-text body from Gmail message payload."""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # recurse into multipart
            if "parts" in part:
                result = _decode_body(part)
                if result:
                    return result
    data = payload.get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def get_unread_replies() -> list[dict]:
    """
    Fetch unread messages from INBOX, mark them as read.
    Returns list of dicts: {gmail_id, thread_id, from_header, from_email, subject, body}
    """
    svc      = _service()
    results  = svc.users().messages().list(
        userId="me", q="is:unread in:inbox", maxResults=50
    ).execute()
    messages = results.get("messages", [])

    emails = []
    for m in messages:
        msg     = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body    = _decode_body(msg["payload"])

        from_header = headers.get("From", "")
        from_email  = _extract_email(from_header)

        emails.append({
            "gmail_id":    m["id"],
            "thread_id":   msg.get("threadId", ""),
            "from_header": from_header,
            "from_email":  from_email,
            "subject":     headers.get("Subject", ""),
            "body":        body,
        })

        # mark as read
        svc.users().messages().modify(
            userId="me", id=m["id"], body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    return emails


def _extract_email(from_header: str) -> str:
    m = re.search(r"<(.+?)>", from_header)
    return m.group(1).strip() if m else from_header.strip()
