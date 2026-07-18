"""Stage 1: pure-Python inbox sync.

a) drafted/bounce_fixed -> sent detection
b) gmail_thread_id backfill via fixed-subject matching
c) reply detection (25-address chunks)
d) bounce detection (mailer-daemon, X-Failed-Recipients)
"""
import json
import re
from datetime import date, datetime

import config
import crm
import gmail
import status


def _expected_subject(contact):
    return config.subject_for(contact.get("email_type"), contact.get("company"))


def _subject_matches(subject, contact):
    return config.subject_matches(
        subject, contact.get("email_type"), contact.get("company"))


def _ms_to_date(ms):
    return datetime.fromtimestamp(ms / 1000).date()


def run(contacts, report, dry_run=False):
    r = report.setdefault("inbox_sync", {
        "sent_detected": [], "backfilled": 0, "backfill_ambiguous": [],
        "backfill_not_found": [], "replies": [], "bounces": [], "errors": [],
    })

    # a) sent detection ------------------------------------------------
    status.update(detail="checking Sent for manually sent drafts")
    for c in crm.eligible_for(contacts, "sent_detection"):
        if not c.get("email"):
            continue
        try:
            hits = [m for m in gmail.search_sent_to(c["email"])
                    if _subject_matches(m["subject"], c)]
        except Exception as e:
            r["errors"].append(f"sent detection {c['name']}: {e}")
            continue
        if not hits:
            continue
        newest = max(hits, key=lambda m: m["internal_ms"])
        sent_date = _ms_to_date(newest["internal_ms"])
        if not dry_run:
            crm.set_status(c, "no_reply", "sent_detected", f"sent {sent_date}")
            c["sent_at"] = sent_date.isoformat()
            c["follow_up_due"] = crm.due_plus_followup_days(sent_date)
            c["gmail_thread_id"] = newest["thread_id"]
            c["gmail_message_id"] = newest["message_id_header"]
            c["autopilot"]["thread_backfill"] = "ok"
        r["sent_detected"].append(f"{c['name']} ({c['company']}) sent {sent_date}")
        crm.save(contacts, dry_run)

    # b) thread backfill (metadata only — safe for replied/converted too) ----
    for c in contacts:
        ap = c.get("autopilot", {})
        if (not c.get("sent_at") or c.get("gmail_thread_id") or not c.get("email")
                or ap.get("thread_backfill") in ("ambiguous", "not_found")):
            continue
        expected = _expected_subject(c)
        if not expected:
            continue
        try:
            hits = [m for m in gmail.search_sent_to(c["email"])
                    if _subject_matches(m["subject"], c)]
        except Exception as e:
            r["errors"].append(f"backfill {c['name']}: {e}")
            continue
        threads = {m["thread_id"] for m in hits}
        if not hits:
            if not dry_run:
                ap["thread_backfill"] = "not_found"
            r["backfill_not_found"].append(c["name"])
        elif len(threads) == 1:
            first = min(hits, key=lambda m: m["internal_ms"])
            if not dry_run:
                c["gmail_thread_id"] = first["thread_id"]
                c["gmail_message_id"] = first["message_id_header"]
                ap["thread_backfill"] = "ok"
                crm.touch(c, "thread_backfill", first["thread_id"])
            r["backfilled"] += 1
        else:
            if not dry_run:
                ap["thread_backfill"] = "ambiguous"
            r["backfill_ambiguous"].append(c["name"])
        crm.save(contacts, dry_run)

    # c) reply detection ----------------------------------------------
    status.update(detail="scanning inbox for replies")
    OOO_RE = re.compile(r"automatic reply|auto[- ]?reply|out of (the )?office|autoreply", re.IGNORECASE)
    watch = [c for c in crm.eligible_for(contacts, "reply_detection") if c.get("email")]
    email_map = {c["email"].lower(): c for c in watch}
    emails = list(email_map)
    marked = set()
    for i in range(0, len(emails), 25):
        chunk = emails[i:i + 25]
        q = "in:inbox {" + " ".join(f"from:{e}" for e in chunk) + "} newer_than:60d"
        try:
            hits = gmail.search_messages(q)
        except Exception as e:
            r["errors"].append(f"reply chunk {i // 25}: {e}")
            continue
        for m in hits:
            meta = gmail.message_meta(m["id"])
            sender = meta["from"].lower()
            for e, c in email_map.items():
                if e not in sender or c["id"] in marked or c["status"] == "replied":
                    continue
                if OOO_RE.search(meta["subject"]):
                    r.setdefault("ooo", []).append(f"{c['name']} ({c['company']}): {meta['subject']}")
                    continue
                marked.add(c["id"])
                if not dry_run:
                    crm.set_status(c, "replied", "reply_detected", meta["subject"])
                    c["notes"] = (c.get("notes") or "") + f" | REPLIED {date.today()}: {meta['subject']}"
                r["replies"].append(f"{c['name']} ({c['company']})")
                crm.save(contacts, dry_run)

    # d) bounce detection ----------------------------------------------
    status.update(detail="scanning for bounces")
    seen = set()
    if config.SEEN_BOUNCES.exists():
        seen = set(json.loads(config.SEEN_BOUNCES.read_text()))
    email_map_all = crm.by_email(contacts)
    new_seen = set(seen)
    try:
        for b in gmail.find_bounces():
            new_seen.add(b["msg_id"])
            if b["msg_id"] in seen:
                continue
            c = email_map_all.get(b["failed_email"])
            if c and c["status"] in crm.ELIGIBLE["bounce_detection"]:
                if not dry_run:
                    crm.set_status(c, "bounced", "bounce_detected", b["failed_email"])
                r["bounces"].append(f"{c['name']} ({c['company']}) {b['failed_email']}")
                crm.save(contacts, dry_run)
    except Exception as e:
        r["errors"].append(f"bounce detection: {e}")
    if not dry_run:
        config.SEEN_BOUNCES.write_text(json.dumps(sorted(new_seen)))
    return r
