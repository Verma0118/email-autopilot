"""Approval queue: everything waiting for Aarav's yes/no lives here.

Items are pre-written emails (replies or new outreach). Approve in the panel
-> Gmail draft is created. Skip -> archived (optionally snoozed). Nothing
reaches Gmail without an explicit approval click.
"""
import json
import threading
import uuid
from datetime import date, datetime, timedelta

import config

QUEUE_FILE = config.STATE_DIR / "approval_queue.json"
_lock = threading.Lock()


def load():
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return []


def save(items):
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, indent=1))
    tmp.replace(QUEUE_FILE)


def pending():
    return [i for i in load() if i["status"] == "pending"]


def has_pending_for(email):
    return any(i for i in pending() if i.get("email", "").lower() == (email or "").lower())


def blocked_for(email):
    """True if this address was skipped with an active snooze (or forever)."""
    email = (email or "").lower()
    if not email:
        return False
    today = date.today().isoformat()
    for i in load():
        if i.get("status") != "skipped":
            continue
        if (i.get("email") or "").lower() != email:
            continue
        until = i.get("skip_until")
        if until is None:
            continue  # plain skip — may reappear
        if until == "forever":
            return True
        if until >= today:
            return True
    return False


def add(kind, track_label, name, company, email, subject, body_html, why="",
        thread_id=None, in_reply_to=None, meta=None):
    with _lock:
        items = load()
        item = {
            "id": uuid.uuid4().hex[:10],
            "created": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,                # "reply" | "outreach"
            "track": track_label,        # startup discovery | internship outreach | NOBE | (reply)
            "name": name, "company": company, "email": email,
            "subject": subject, "body_html": body_html, "why": why,
            "thread_id": thread_id, "in_reply_to": in_reply_to,
            "meta": meta or {}, "status": "pending",
            "gmail_draft_id": None, "resolved": None,
        }
        items.append(item)
        save(items)
        return item


def update_pending(item_id, **fields):
    """Persist in-progress edits on a pending item (subject/email/body_html)."""
    allowed = {"subject", "email", "body_html"}
    with _lock:
        items = load()
        for i in items:
            if i["id"] == item_id and i["status"] == "pending":
                for k, v in fields.items():
                    if k in allowed and v is not None:
                        i[k] = v
                save(items)
                return i
        return None


def resolve(item_id, new_status, gmail_draft_id=None, draft_link=None, skip_until=None,
            contact_id=None):
    with _lock:
        items = load()
        for i in items:
            if i["id"] == item_id and i["status"] == "pending":
                i["status"] = new_status
                i["resolved"] = datetime.now().isoformat(timespec="seconds")
                if gmail_draft_id:
                    i["gmail_draft_id"] = gmail_draft_id
                if draft_link:
                    i["draft_link"] = draft_link
                if new_status == "skipped":
                    if skip_until is not None:
                        i["skip_until"] = skip_until
                if contact_id:
                    i["crm_contact_id"] = contact_id
                save(items)
                return i
        return None


def reopen(item_id):
    """Undo a skip — restore to pending so it reappears in the panel."""
    with _lock:
        items = load()
        for i in items:
            if i["id"] == item_id and i["status"] == "skipped":
                i["status"] = "pending"
                i["resolved"] = None
                i.pop("skip_until", None)
                save(items)
                return i
        return None


def unapprove(item_id):
    """Undo an approve — restore to pending; caller deletes the Gmail draft."""
    with _lock:
        items = load()
        for i in items:
            if i["id"] == item_id and i["status"] == "approved":
                draft_id = i.get("gmail_draft_id")
                contact_id = i.get("crm_contact_id")
                i["status"] = "pending"
                i["resolved"] = None
                i["gmail_draft_id"] = None
                i.pop("draft_link", None)
                i.pop("crm_contact_id", None)
                save(items)
                return i, draft_id, contact_id
        return None, None, None


def skip_until_days(days):
    """ISO date days from today, or 'forever'."""
    if days is None or days == "forever":
        return "forever"
    return (date.today() + timedelta(days=int(days))).isoformat()


def resolved_today():
    """Items approved or skipped today, newest first."""
    today = datetime.now().date().isoformat()
    out = []
    for i in load():
        if i.get("status") not in ("approved", "skipped"):
            continue
        resolved = (i.get("resolved") or "")[:10]
        if resolved == today:
            out.append(i)
    return sorted(out, key=lambda x: x.get("resolved") or "", reverse=True)
