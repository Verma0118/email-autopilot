"""Standalone Gmail API client for the autopilot.

Own OAuth app token at ~/.config/emailcrm/token.json with scopes
gmail.readonly + gmail.compose ONLY. There is no gmail.send scope anywhere
in this system: it is structurally incapable of sending email.
"""
import base64
import json
import re
from email.mime.text import MIMEText

import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

_service = None


class NeedsSetup(Exception):
    pass


def get_service():
    global _service
    if _service is not None:
        return _service
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not config.TOKEN_FILE.exists():
        raise NeedsSetup(f"no token at {config.TOKEN_FILE}; run: run.py --setup")
    creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            config.TOKEN_FILE.write_text(creds.to_json())
        else:
            raise NeedsSetup("token invalid and not refreshable; run: run.py --setup")
    _service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return _service


def setup():
    from google_auth_oauthlib.flow import InstalledAppFlow

    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not config.CLIENT_SECRET.exists():
        raise SystemExit(
            f"missing {config.CLIENT_SECRET} — copy your Google OAuth client secret there first"
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)
    config.TOKEN_FILE.write_text(creds.to_json())
    print(f"token written to {config.TOKEN_FILE}")


# ---------- read side ----------

def search_messages(q, max_results=50, label_ids=None):
    svc = get_service()
    kwargs = {"userId": "me", "q": q, "maxResults": max_results}
    if label_ids:
        kwargs["labelIds"] = label_ids
    resp = svc.users().messages().list(**kwargs).execute()
    return resp.get("messages", [])


def get_message(msg_id, fmt="metadata"):
    svc = get_service()
    return svc.users().messages().get(userId="me", id=msg_id, format=fmt).execute()


def headers_of(msg):
    return {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}


def message_meta(msg_id):
    msg = get_message(msg_id)
    h = headers_of(msg)
    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId"),
        "message_id_header": h.get("message-id"),
        "from": h.get("from", ""),
        "to": h.get("to", ""),
        "subject": h.get("subject", ""),
        "date": h.get("date", ""),
        "internal_ms": int(msg.get("internalDate", 0)),
    }


def search_sent_to(email, extra=""):
    return [message_meta(m["id"]) for m in search_messages(f"in:sent to:{email} {extra}".strip())]


def _walk_parts(payload, mime):
    if payload.get("mimeType") == mime and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        found = _walk_parts(part, mime)
        if found:
            return found
    return None


def get_message_body(msg_id):
    """Returns (html, plain); either may be None."""
    msg = get_message(msg_id, fmt="full")
    payload = msg.get("payload", {})
    return _walk_parts(payload, "text/html"), _walk_parts(payload, "text/plain")


FAILED_RE = re.compile(
    r"(?:final-recipient:.*?;\s*|<)([\w.+-]+@[\w.-]+\.[a-z]{2,})(?:>)?", re.IGNORECASE
)


def find_bounces(newer_days=30):
    """Returns [{msg_id, failed_email, internal_ms}]."""
    out = []
    hits = search_messages(f"from:(mailer-daemon OR postmaster) newer_than:{newer_days}d")
    for m in hits:
        msg = get_message(m["id"], fmt="full")
        h = headers_of(msg)
        failed = h.get("x-failed-recipients")
        if not failed:
            _, plain = _walk_parts(msg["payload"], "text/html"), _walk_parts(msg["payload"], "text/plain")
            body = plain or ""
            mm = re.search(r"(?:wasn't|was not|couldn't be|could not be)\s+(?:found|delivered)[\s\S]{0,200}?([\w.+-]+@[\w.-]+\.[a-z]{2,})", body, re.IGNORECASE)
            if not mm:
                mm = FAILED_RE.search(body)
            failed = mm.group(1) if mm else None
        if failed:
            out.append({
                "msg_id": m["id"],
                "failed_email": failed.strip().lower(),
                "internal_ms": int(msg.get("internalDate", 0)),
            })
    return out


def list_drafts_meta(max_results=100):
    svc = get_service()
    resp = svc.users().drafts().list(userId="me", maxResults=max_results).execute()
    out = []
    for d in resp.get("drafts", []):
        msg = d.get("message", {})
        full = svc.users().drafts().get(userId="me", id=d["id"], format="metadata").execute()
        h = {x["name"].lower(): x["value"] for x in full["message"]["payload"].get("headers", [])}
        out.append({"draft_id": d["id"], "to": h.get("to", ""), "subject": h.get("subject", "")})
    return out


# ---------- write side (drafts ONLY — no send scope exists) ----------

def create_draft(subject, body_html, to):
    svc = get_service()
    mime = MIMEText(body_html, "html")
    mime["To"] = to
    mime["From"] = config.ACCOUNT
    mime["Subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    draft = svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"draft_id": draft["id"], "message_id": draft["message"]["id"],
            "thread_id": draft["message"].get("threadId")}


def create_reply_draft(to, subject, body_html, thread_id, in_reply_to):
    svc = get_service()
    mime = MIMEText(body_html, "html")
    mime["To"] = to
    mime["From"] = config.ACCOUNT
    mime["Subject"] = subject
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
        mime["References"] = in_reply_to
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    body = {"message": {"raw": raw, "threadId": thread_id}}
    draft = svc.users().drafts().create(userId="me", body=body).execute()
    return {"draft_id": draft["id"], "message_id": draft["message"]["id"],
            "thread_id": draft["message"].get("threadId")}


def draft_link(thread_id):
    return f"https://mail.google.com/mail/u/0/#drafts/{thread_id}" if thread_id else None


def thread_link(thread_id):
    return f"https://mail.google.com/mail/u/0/#inbox/{thread_id}" if thread_id else None
