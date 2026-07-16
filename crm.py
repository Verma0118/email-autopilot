"""CRM store: load/backup/save contacts.json, schema migration, state machine."""
import json
import shutil
from datetime import date, datetime, timedelta

import config

# Statuses the autopilot must never mutate.
PROTECTED = {"replied", "converted"}
# Statuses eligible per stage.
ELIGIBLE = {
    "sent_detection": {"drafted", "bounce_fixed"},
    "reply_detection": {"no_reply", "followed_up", "bounce_fixed", "drafted"},
    "bounce_detection": {"no_reply", "followed_up", "bounce_fixed"},
    "bounce_retry": {"bounced"},
    "followup": {"no_reply"},
}

AUTOPILOT_DEFAULTS = {
    "thread_backfill": None,
    "bounce_retry": None,
    "last_touched": None,
    "history": [],
}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def load():
    with open(config.CONTACTS) as f:
        contacts = json.load(f)
    assert isinstance(contacts, list) and contacts, "contacts.json empty or malformed"
    return contacts


def backup():
    dest = config.ROOT / f"contacts.backup-{date.today().isoformat()}.json"
    if not dest.exists():
        shutil.copy2(config.CONTACTS, dest)
    return dest


def save(contacts, dry_run=False):
    if dry_run:
        return
    tmp = config.CONTACTS.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(contacts, f, indent=2)
    tmp.replace(config.CONTACTS)


def migrate(contacts):
    """Add autopilot fields to every record. Idempotent."""
    changed = False
    for c in contacts:
        for field, default in (
            ("follow_up_count", 0),
            ("follow_up_draft_id", None),
            ("follow_up_drafted_at", None),
            ("gmail_message_id", None),
        ):
            if field not in c:
                c[field] = default
                changed = True
        if "autopilot" not in c:
            c["autopilot"] = dict(AUTOPILOT_DEFAULTS, history=[])
            changed = True
    return changed


def touch(contact, action, detail=""):
    ap = contact["autopilot"]
    ap["last_touched"] = now_iso()
    ap["history"].append({"ts": now_iso(), "action": action, "detail": detail})


def set_status(contact, new_status, action, detail=""):
    if contact["status"] in PROTECTED:
        raise ValueError(f"refusing to mutate protected contact {contact['name']} ({contact['status']})")
    old = contact["status"]
    contact["status"] = new_status
    touch(contact, action, f"{old} -> {new_status}. {detail}".strip())


def eligible_for(contacts, stage):
    statuses = ELIGIBLE[stage]
    return [c for c in contacts if c.get("status") in statuses and c["status"] not in PROTECTED]


def followup_candidates(contacts, today=None):
    today = today or date.today().isoformat()
    out = [
        c for c in eligible_for(contacts, "followup")
        if c.get("follow_up_count", 0) == 0
        and (c.get("follow_up_due") or "9999") <= today
        and c.get("autopilot", {}).get("thread_backfill") == "ok"
        and c.get("gmail_thread_id")
        and c.get("gmail_message_id")
    ]
    out.sort(key=lambda c: c.get("follow_up_due") or "9999")
    return out


def due_plus_followup_days(from_date=None):
    base = from_date or date.today()
    return (base + timedelta(days=config.FOLLOW_UP_DAYS)).isoformat()


def by_email(contacts):
    return {c["email"].lower(): c for c in contacts if c.get("email")}


def counts(contacts):
    out = {}
    for c in contacts:
        out[c.get("status", "unknown")] = out.get(c.get("status", "unknown"), 0) + 1
    return out
