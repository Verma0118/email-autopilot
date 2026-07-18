"""Inbox Agent: sync (deterministic) + short rundown of inbox state.

Rundown is built from this run's sync signals — no LLM — so the Overview
card always refreshes and we don't burn tokens on a summary.
"""
from datetime import date

import status
from stages import inbox_sync


def _build_rundown(contacts, sync):
    """Plain-language summary from deterministic sync output."""
    parts = []
    replies = sync.get("replies") or []
    if replies:
        shown = "; ".join(replies[:5])
        extra = f" (+{len(replies) - 5} more)" if len(replies) > 5 else ""
        parts.append(f"New replies: {shown}{extra}.")
    else:
        parts.append("No new replies this run.")

    ooo = sync.get("ooo") or []
    if ooo:
        parts.append("Out of office: " + "; ".join(ooo[:4]) + ".")

    bounces = sync.get("bounces") or []
    if bounces:
        parts.append("Bounces: " + "; ".join(bounces[:4]) + ".")

    sent = sync.get("sent_detected") or []
    if sent:
        parts.append("You sent: " + "; ".join(sent[:4]) + ".")

    waiting = [c for c in contacts if c.get("status") in ("replied", "converted")]
    if waiting:
        names = ", ".join(
            f"{c['name']} ({c.get('company') or '?'})" for c in waiting[:6]
        )
        extra = f" +{len(waiting) - 6} more" if len(waiting) > 6 else ""
        parts.append(f"Open threads needing a look: {names}{extra}.")

    return " ".join(parts)


def _action_items(contacts, sync):
    """Short, non-duplicative inbox todos (Needs you owns deeper links)."""
    items = []
    seen = set()
    for line in (sync.get("replies") or [])[:5]:
        label = f"Handle reply: {line}"
        if label not in seen:
            items.append(label)
            seen.add(label)
    for line in (sync.get("bounces") or [])[:4]:
        label = f"Fix bounce: {line}"
        if label not in seen:
            items.append(label)
            seen.add(label)
    bounced = [c for c in contacts if c.get("status") == "bounced"]
    for c in bounced[:3]:
        label = f"Unresolved bounce: {c.get('name')} ({c.get('company') or '?'})"
        if label not in seen:
            items.append(label)
            seen.add(label)
    return items[:8]


def write_rundown(contacts, report, log, dry_run=False):
    """Refresh Overview rundown from the latest sync (call after inbox_sync)."""
    sync = report.get("inbox_sync") or {}
    status.update(stage="inbox agent", detail="updating inbox rundown")
    r = report.setdefault("inbox_agent", {})
    r["rundown"] = _build_rundown(contacts, sync)
    r["action_items"] = _action_items(contacts, sync)
    r["generated"] = date.today().isoformat()
    status.set_field("rundown", r["rundown"])
    log({"action": "inbox_rundown", "rundown": r["rundown"][:240], "llm": False})
    return r


def run(contacts, report, log, dry_run=False):
    """Full inbox stage: sync then rundown (used by --stage inbox)."""
    status.update(stage="inbox agent", detail="syncing inbox")
    status.set_field("rundown", "Updating…")
    inbox_sync.run(contacts, report, dry_run=dry_run)
    return write_rundown(contacts, report, log, dry_run=dry_run)
