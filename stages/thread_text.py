"""Bounded Gmail thread renderer for reply LLM prompts."""
import re
from datetime import datetime

import config
import gmail


def thread_text(thread_id):
    """Render thread oldest-first with direction markers (bounded for LLM cost).

    Returns (text, last_from_us_date, subject). Keeps the newest N messages so
    long threads do not dump unbounded context into every reply call.
    """
    svc = gmail.get_service()
    t = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
    msgs = sorted(t.get("messages", []), key=lambda m: int(m.get("internalDate", 0)))
    max_msgs = max(1, int(getattr(config, "REPLY_THREAD_MAX_MSGS", 8) or 8))
    msg_chars = max(200, int(getattr(config, "REPLY_THREAD_MSG_CHARS", 1000) or 1000))
    parts, last_us_ms, subject = [], 0, None
    for m in msgs:
        h = {x["name"].lower(): x["value"] for x in m["payload"].get("headers", [])}
        if subject is None:
            subject = re.sub(r"^(Re|RE|Fwd?):\s*", "", h.get("subject", ""))
        from_us = config.ACCOUNT in h.get("from", "").lower()
        if from_us:
            last_us_ms = max(last_us_ms, int(m.get("internalDate", 0)))
    for m in msgs[-max_msgs:]:
        h = {x["name"].lower(): x["value"] for x in m["payload"].get("headers", [])}
        from_us = config.ACCOUNT in h.get("from", "").lower()
        html = gmail._walk_parts(m["payload"], "text/html")
        plain = gmail._walk_parts(m["payload"], "text/plain")
        body = plain or re.sub(r"<[^>]+>", " ", html or "")
        body = re.sub(r"\s+", " ", body)[:msg_chars]
        when = datetime.fromtimestamp(int(m.get("internalDate", 0)) / 1000).date()
        parts.append(f"[{when} {'FROM_US' if from_us else 'FROM_THEM'}] {body}")
    last_us = datetime.fromtimestamp(last_us_ms / 1000).date() if last_us_ms else None
    return "\n\n".join(parts), last_us, subject
