"""Reply Agent: for every open conversation, decide whether Aarav owes a
reply; if so, draft it into the approval queue (never straight to Gmail).
Covers both direct replies and passed-promise nudges."""
from datetime import date

import config
import crm
import llm
import queue_store
import status
import validators
from stages.reply_nudges import _thread_text  # thread renderer with FROM_US markers


def _lint(result, expected_subject):
    errs = []
    body = result.get("body_html", "")
    text = validators._strip_html(body)
    if result.get("subject") != expected_subject:
        errs.append(f'subject must be "{expected_subject}"')
    if "—" in body or "–" in body:
        errs.append("em/en dash")
    m = validators.CONTRACTIONS.search(text)
    if m:
        errs.append(f"contraction: {m.group(0)}")
    if ";" in text:
        errs.append("semicolon")
    for p in validators.BANNED_PHRASES:
        if p in text.lower():
            errs.append(f"banned phrase: {p}")
    if not 15 <= len(text.split()) <= 220:
        errs.append(f"body {len(text.split())} words, unreasonable for a reply")
    return errs


def run(contacts, report, cap, log, dry_run=False):
    r = report.setdefault("reply_agent", {"queued": [], "we_owe": [], "skipped": [], "errors": []})
    template = (config.PROMPT_DIR / "reply_draft.md").read_text()
    today = date.today()

    candidates = [c for c in contacts
                  if c.get("status") in ("replied", "converted")
                  and c.get("gmail_thread_id")
                  and not queue_store.has_pending_for(c.get("email"))]

    for c in candidates[:cap]:
        status.check_stop()
        status.update(stage="reply agent",
                      detail=f"checking conversation: {c['name']} ({c['company']})",
                      stream=config.STREAM_LABELS.get(c.get("email_type"), "reply"))
        try:
            thread, last_us, subject = _thread_text(c["gmail_thread_id"])
        except Exception as e:
            r["errors"].append(f"{c['name']}: thread fetch failed: {e}")
            continue
        if last_us and (today - last_us).days < 3:
            r["skipped"].append(f"{c['name']}: we wrote {last_us}, too soon")
            continue
        expected_subject = f"Re: {subject}"
        prompt = (template
                  .replace("<<TODAY>>", today.isoformat())
                  .replace("<<NAME>>", c["name"])
                  .replace("<<COMPANY>>", c["company"])
                  .replace("<<ROLE>>", c.get("role") or "")
                  .replace("<<THREAD>>", thread))

        def validate(result):
            if not isinstance(result, dict) or "reply_needed" not in result:
                return ["output must be JSON with reply_needed"]
            if not result.get("reply_needed"):
                return []
            return _lint(result, expected_subject)

        try:
            result, errors = llm.call_with_retry(prompt, use_exa=False, validate=validate)
        except llm.LLMError as e:
            r["errors"].append(f"{c['name']}: {e}")
            if llm.llm_down:
                break
            continue
        if errors:
            r["skipped"].append(f"{c['name']}: lint failed twice: {errors}")
            continue
        if not result.get("reply_needed"):
            if result.get("we_owe_later"):
                r["we_owe"].append(f"{c['name']} ({c['company']}): {result['we_owe_later']}")
            else:
                r["skipped"].append(f"{c['name']}: {result.get('why')}")
            continue

        if dry_run:
            r["queued"].append(f"[DRY] {c['name']}: {result.get('why')}")
            continue
        # find in-reply-to for correct threading at approval time
        in_reply_to = c.get("gmail_message_id")
        item = queue_store.add(
            kind="reply", track_label="reply",
            name=c["name"], company=c["company"], email=c["email"],
            subject=result["subject"], body_html=result["body_html"],
            why=result.get("why", ""),
            thread_id=c["gmail_thread_id"], in_reply_to=in_reply_to,
            meta={"contact_id": c["id"],
                  "thread_preview": thread[-1200:] if len(thread) > 1200 else thread},
        )
        log({"action": "reply_queued", "contact": c["id"], "item": item["id"]})
        r["queued"].append(f"{c['name']} ({c['company']}): {result.get('why')}")
    return r
