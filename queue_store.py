"""Approval queue: everything waiting for Aarav's yes/no lives here.

Items are pre-written emails (replies or new outreach). Approve in the panel
-> Gmail draft is created. Skip -> archived. Nothing reaches Gmail without
an explicit approval click.
"""
import json
import uuid
from datetime import datetime

import config

QUEUE_FILE = config.STATE_DIR / "approval_queue.json"


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


def add(kind, track_label, name, company, email, subject, body_html, why="",
        thread_id=None, in_reply_to=None, meta=None):
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


def resolve(item_id, new_status, gmail_draft_id=None):
    items = load()
    for i in items:
        if i["id"] == item_id and i["status"] == "pending":
            i["status"] = new_status
            i["resolved"] = datetime.now().isoformat(timespec="seconds")
            if gmail_draft_id:
                i["gmail_draft_id"] = gmail_draft_id
            save(items)
            return i
    return None
