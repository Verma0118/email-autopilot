"""Inbox Agent: sync (deterministic) + short LLM rundown of inbox state."""
import json
from datetime import date

import config
import crm
import gmail
import llm
import status
from stages import inbox_sync


def run(contacts, report, log, dry_run=False):
    status.update(stage="inbox agent", detail="syncing inbox")
    inbox_sync.run(contacts, report, dry_run=dry_run)
    sync = report.get("inbox_sync", {})

    status.update(detail="writing inbox rundown")
    open_convos = [f"{c['name']} ({c['company']}, {c['status']})"
                   for c in contacts if c["status"] in ("replied", "converted")]
    try:
        recent = []
        for m in gmail.search_messages("in:inbox -category:promotions newer_than:3d", max_results=10):
            meta = gmail.message_meta(m["id"])
            recent.append(f"{meta['from']}: {meta['subject']}")
    except Exception:
        recent = ["(inbox fetch failed)"]

    prompt = (config.PROMPT_DIR / "inbox_rundown.md").read_text()
    for token, value in {
        "<<TODAY>>": date.today().isoformat(),
        "<<REPLIES>>": "; ".join(sync.get("replies", [])) or "none",
        "<<OOO>>": "; ".join(sync.get("ooo", [])) or "none",
        "<<BOUNCES>>": "; ".join(sync.get("bounces", [])) or "none",
        "<<SENT>>": "; ".join(sync.get("sent_detected", [])) or "none",
        "<<OPEN_CONVOS>>": "; ".join(open_convos) or "none",
        "<<RECENT>>": "\n".join(recent) or "none",
    }.items():
        prompt = prompt.replace(token, value)

    r = report.setdefault("inbox_agent", {})
    try:
        out = llm.call(prompt, use_exa=False)
        r["rundown"] = out.get("rundown", "")
        r["action_items"] = out.get("action_items", [])
    except llm.LLMError as e:
        r["rundown"] = "(rundown unavailable: LLM skipped this run)"
        r["action_items"] = []
        report["inbox_sync"].setdefault("errors", []).append(f"rundown: {e}")
    status.set_field("rundown", r.get("rundown", ""))
    log({"action": "inbox_rundown", "rundown": r.get("rundown", "")[:200]})
    return r
