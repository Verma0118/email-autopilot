"""Stage 3b: reply nudges.

Contacts who REPLIED, promised future contact, then went silent past the
promised window. LLM reads the whole thread and decides + drafts; Python
gates, lints, and creates the in-thread reply draft.
"""
import re
from datetime import date, datetime, timedelta

import config
import crm
import gmail
import llm
import status
import validators

NUDGE_COOLDOWN_DAYS = 6


def _thread_text(thread_id):
    """Render the whole thread oldest-first with direction markers.
    Returns (text, last_from_us_date, subject)."""
    svc = gmail.get_service()
    t = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
    msgs = sorted(t.get("messages", []), key=lambda m: int(m.get("internalDate", 0)))
    parts, last_us_ms, subject = [], 0, None
    for m in msgs:
        h = {x["name"].lower(): x["value"] for x in m["payload"].get("headers", [])}
        if subject is None:
            subject = re.sub(r"^(Re|RE|Fwd?):\s*", "", h.get("subject", ""))
        from_us = config.ACCOUNT in h.get("from", "").lower()
        if from_us:
            last_us_ms = max(last_us_ms, int(m.get("internalDate", 0)))
        html = gmail._walk_parts(m["payload"], "text/html")
        plain = gmail._walk_parts(m["payload"], "text/plain")
        body = plain or re.sub(r"<[^>]+>", " ", html or "")
        body = re.sub(r"\s+", " ", body)[:1500]
        when = datetime.fromtimestamp(int(m.get("internalDate", 0)) / 1000).date()
        parts.append(f"[{when} {'FROM_US' if from_us else 'FROM_THEM'}] {body}")
    last_us = datetime.fromtimestamp(last_us_ms / 1000).date() if last_us_ms else None
    return "\n\n".join(parts), last_us, subject


def _lint(result, expected_subject):
    errs = []
    body = result.get("body_html", "")
    if result.get("subject") != expected_subject:
        errs.append(f'subject must be "{expected_subject}"')
    if "—" in body or "–" in body:
        errs.append("em/en dash")
    m = validators.CONTRACTIONS.search(validators._strip_html(body))
    if m:
        errs.append(f"contraction: {m.group(0)}")
    text = validators._strip_html(body)
    if ";" in text:
        errs.append("semicolon")
    for p in validators.BANNED_PHRASES:
        if p in text.lower():
            errs.append(f"banned phrase: {p}")
    wc = len(text.split())
    if not 20 <= wc <= 110:
        errs.append(f"body {wc} words, want 40-90")
    if re.search(r'href="(?!https://)', body):
        errs.append("non-https link")
    return errs


def run(contacts, report, cap, log, dry_run=False):
    r = report.setdefault("reply_nudges", {"drafted": [], "skipped": [], "we_owe": [], "errors": []})
    template = (config.PROMPT_DIR / "reply_nudge.md").read_text()
    today = date.today()

    candidates = []
    for c in contacts:
        if c.get("status") != "replied" or not c.get("gmail_thread_id"):
            continue
        nudge = c.get("autopilot", {}).get("reply_nudge") or {}
        last = nudge.get("drafted_at")
        if last and (today - datetime.fromisoformat(last).date()).days < NUDGE_COOLDOWN_DAYS:
            continue
        candidates.append(c)

    for c in candidates[:cap]:
        status.check_stop()
        status.update(detail=f"checking thread: {c['name']} ({c['company']})",
                      stream=config.STREAM_LABELS.get(c.get("email_type"), c.get("email_type")))
        try:
            thread, last_us, subject = _thread_text(c["gmail_thread_id"])
        except Exception as e:
            r["errors"].append(f"{c['name']}: thread fetch failed: {e}")
            continue
        if last_us and (today - last_us).days < 5:
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
            if not isinstance(result, dict) or "nudge_appropriate" not in result:
                return ["output must be JSON with nudge_appropriate"]
            if not result.get("nudge_appropriate"):
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

        if not result.get("nudge_appropriate"):
            if result.get("we_owe_later"):
                r["we_owe"].append(f"{c['name']} ({c['company']}): {result['we_owe_later']}")
            else:
                r["skipped"].append(f"{c['name']}: {result.get('reasoning')}")
            continue

        log({"action": "nudge_intent", "contact": c["id"], "subject": result["subject"],
             "promise": result.get("promised_date_passed")})
        preview = validators._strip_html(result["body_html"])
        if dry_run:
            r["drafted"].append(f"[DRY] {c['name']} ({c['company']}): {result.get('promised_date_passed')}\n  BODY: {preview}")
            continue
        # find last message id for In-Reply-To
        try:
            hits = gmail.search_sent_to(c["email"])
            in_thread = [m for m in hits if m["thread_id"] == c["gmail_thread_id"]]
            in_reply_to = max(in_thread, key=lambda m: m["internal_ms"])["message_id_header"] if in_thread else c.get("gmail_message_id")
            draft = gmail.create_reply_draft(
                to=c["email"], subject=result["subject"], body_html=result["body_html"],
                thread_id=c["gmail_thread_id"], in_reply_to=in_reply_to)
        except Exception as e:
            r["errors"].append(f"{c['name']}: draft create failed: {e}")
            continue
        c["autopilot"]["reply_nudge"] = {"drafted_at": today.isoformat(),
                                         "draft_id": draft["draft_id"],
                                         "promise": result.get("promised_date_passed")}
        crm.touch(c, "reply_nudge_drafted", draft["draft_id"])
        crm.save(contacts, dry_run)
        log({"action": "nudge_drafted", "contact": c["id"], "draft_id": draft["draft_id"]})
        r["drafted"].append(
            f"{c['name']} ({c['company']}): {result.get('promised_date_passed')} "
            f"link: {gmail.draft_link(draft['thread_id'])}\n  BODY: {preview}")
    return r
