"""Inbox Agent: sync (deterministic) + short rundown of inbox state.

Rundown is built from this run's sync signals — no LLM — so the Overview
card always refreshes and we don't burn tokens on a summary.
"""
from datetime import date
import re

import status
from stages import inbox_sync

_PERSON_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")


def _parse_person(line):
    """Turn sync lines into {name, company} and drop subject/auto-reply noise."""
    s = str(line or "").strip()
    if not s:
        return None
    # "Name (Co): Automatic reply: Subject | …" → keep name/company only
    head = s.split(":", 1)[0].strip() if ":" in s else s
    m = _PERSON_RE.match(head)
    if m:
        return {"name": m.group(1).strip(), "company": m.group(2).strip()}
    return {"name": head, "company": ""}


def _people(lines, limit=6):
    out = []
    seen = set()
    for line in lines or []:
        p = _parse_person(line)
        if not p:
            continue
        key = (p["name"].lower(), (p.get("company") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= limit:
            break
    return out


def _build_rundown_sections(contacts, sync):
    """Structured Overview sections — scannable, not a run-on paragraph."""
    sections = []

    replies = _people(sync.get("replies") or [], 6)
    sections.append({
        "id": "replies",
        "title": "New replies",
        "people": replies,
        "empty": "None this run.",
    })

    ooo = _people(sync.get("ooo") or [], 5)
    if ooo:
        sections.append({
            "id": "ooo",
            "title": "Out of office",
            "people": ooo,
            "empty": "",
        })

    bounces = _people(sync.get("bounces") or [], 5)
    if bounces:
        sections.append({
            "id": "bounces",
            "title": "Bounces",
            "people": bounces,
            "empty": "",
        })

    sent = _people(sync.get("sent_detected") or [], 5)
    if sent:
        sections.append({
            "id": "sent",
            "title": "You sent",
            "people": sent,
            "empty": "",
        })

    waiting = [c for c in contacts if c.get("status") in ("replied", "converted")]
    look = [
        {"name": c.get("name") or "?", "company": c.get("company") or ""}
        for c in waiting[:8]
    ]
    if look:
        sections.append({
            "id": "open",
            "title": "Open threads",
            "people": look,
            "empty": "",
            "more": max(0, len(waiting) - 8),
        })

    return sections


def _sections_to_text(sections):
    """Compact string for digest / logs (not shown as the Overview wall)."""
    parts = []
    for sec in sections:
        people = sec.get("people") or []
        if not people:
            if sec.get("empty"):
                parts.append(f"{sec['title']}: {sec['empty']}")
            continue
        names = ", ".join(
            f"{p['name']}" + (f" ({p['company']})" if p.get("company") else "")
            for p in people
        )
        more = sec.get("more") or 0
        extra = f" +{more} more" if more else ""
        parts.append(f"{sec['title']}: {names}{extra}.")
    return " ".join(parts) if parts else "Inbox quiet."


def _build_rundown(contacts, sync):
    """Plain-language summary from deterministic sync output."""
    return _sections_to_text(_build_rundown_sections(contacts, sync))


def _action_items(contacts, sync):
    """Short, non-duplicative inbox todos (Needs you owns deeper links)."""
    items = []
    seen = set()
    for line in (sync.get("replies") or [])[:5]:
        p = _parse_person(line)
        label = f"Handle reply: {p['name']}" if p else f"Handle reply: {line}"
        if p and p.get("company"):
            label += f" ({p['company']})"
        if label not in seen:
            items.append(label)
            seen.add(label)
    for line in (sync.get("bounces") or [])[:4]:
        p = _parse_person(line)
        label = f"Fix bounce: {p['name']}" if p else f"Fix bounce: {line}"
        if p and p.get("company"):
            label += f" ({p['company']})"
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
    sections = _build_rundown_sections(contacts, sync)
    text = _sections_to_text(sections)
    r = report.setdefault("inbox_agent", {})
    r["rundown"] = text
    r["rundown_sections"] = sections
    r["action_items"] = _action_items(contacts, sync)
    r["generated"] = date.today().isoformat()
    status.set_field("rundown", text)
    status.set_field("rundown_sections", sections)
    log({"action": "inbox_rundown", "rundown": text[:240], "llm": False})
    return r


def run(contacts, report, log, dry_run=False):
    """Full inbox stage: sync then rundown (used by --stage inbox)."""
    status.update(stage="inbox agent", detail="syncing inbox")
    status.set_field("rundown", "Updating…")
    status.set_field("rundown_sections", [])
    inbox_sync.run(contacts, report, dry_run=dry_run)
    return write_rundown(contacts, report, log, dry_run=dry_run)
