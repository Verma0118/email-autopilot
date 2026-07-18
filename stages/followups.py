"""Cold follow-up drafts into the Approvals queue (never straight to Gmail).

Paused by default via config.COLD_FOLLOWUPS_ENABLED. When re-enabled (or run
with --stage followup), drafts land in Approvals like replies/outreach.
"""
import re
from datetime import date

import config
import crm
import gmail
import llm
import queue_store
import status
import validators


def _load_prompt():
    return (config.PROMPT_DIR / "followup_draft.md").read_text()


CAL_URL_RE = re.compile(
    r'href="(https://(?:calendly\.com|cal\.com|calendar\.google\.com|calendar\.app\.google)[^"]*)"')


def _render(template, contact, original_body, calendar_url, original_subject):
    out = template
    for token, value in {
        "<<CALENDAR_URL>>": calendar_url or "NONE_FOUND",
        "<<NAME>>": contact["name"],
        "<<COMPANY>>": contact["company"],
        "<<ROLE>>": contact.get("role") or "",
        "<<EMAIL_TYPE>>": contact.get("email_type") or "startup_discovery",
        "<<HOOK_USED>>": contact.get("hook_used") or "",
        "<<NOTES>>": (contact.get("notes") or "")[:600],
        "<<SENT_AT>>": contact.get("sent_at") or "",
        "<<ORIGINAL_SUBJECT>>": original_subject or "",
        "<<ORIGINAL_EMAIL>>": (original_body or "")[:3000],
    }.items():
        out = out.replace(token, str(value))
    return out


def run(contacts, report, cap, log, dry_run=False):
    r = report.setdefault("followups", {"queued": [], "drafted": [], "skipped": [], "errors": []})
    candidates = crm.followup_candidates(contacts)[: cap]
    if not candidates:
        return r

    template = _load_prompt()
    configured_cal = (getattr(config, "CALENDAR_URL", None) or "").strip()

    for c in candidates:
        status.check_stop()
        if queue_store.has_pending_for(c.get("email")) or queue_store.blocked_for(c.get("email")):
            r["skipped"].append(f"{c['name']}: already in Approvals or snoozed")
            continue
        status.update(detail=f"drafting follow-up: {c['name']} ({c['company']})",
                      stream=config.STREAM_LABELS.get(c.get("email_type"), c.get("email_type")))
        original_subject = config.subject_for(c.get("email_type"), c.get("company")) or ""
        expected_subject = "Re: " + original_subject if original_subject else "Re: "

        html, plain = (None, None)
        try:
            hits = gmail.search_sent_to(c["email"])
            orig = [m for m in hits if m["thread_id"] == c["gmail_thread_id"]]
            if orig:
                html, plain = gmail.get_message_body(
                    min(orig, key=lambda m: m["internal_ms"])["id"])
        except Exception as e:
            r["errors"].append(f"{c['name']}: original fetch failed: {e}")

        cal_match = CAL_URL_RE.search(html or "")
        calendar_url = cal_match.group(1) if cal_match else (
            configured_cal if configured_cal.startswith("http") else None)
        prompt = _render(template, c, plain or html, calendar_url, original_subject)

        def validate(result):
            if not isinstance(result, dict) or "body_html" not in result:
                return ["output must be JSON with keys subject, body_html, new_angle"]
            errs = validators.lint_followup(
                result.get("subject", ""), result["body_html"], expected_subject
            )
            if calendar_url is None:
                errs = [e for e in errs if "anchor" not in e]
            elif calendar_url not in result["body_html"]:
                errs.append(f"must use the exact calendar URL {calendar_url}")
            return errs

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

        log({"action": "followup_intent", "contact": c["id"], "to": c["email"],
             "subject": result["subject"], "new_angle": result.get("new_angle")})
        if dry_run:
            r["queued"].append(f"[DRY] {c['name']} ({c['company']}): {result.get('new_angle')}")
            continue
        item = queue_store.add(
            kind="followup",
            track_label=config.STREAM_LABELS.get(c.get("email_type"), "follow-up"),
            name=c["name"], company=c.get("company"), email=c["email"],
            subject=result["subject"], body_html=result["body_html"],
            why=result.get("new_angle", "cold follow-up"),
            thread_id=c.get("gmail_thread_id"),
            in_reply_to=c.get("gmail_message_id"),
            meta={"contact_id": c["id"], "email_type": c.get("email_type")},
        )
        # Mark so we don't re-draft until approve/skip resolves lifecycle
        c["follow_up_drafted_at"] = crm.now_iso()
        c["follow_up_draft_id"] = f"queue:{item['id']}"
        crm.touch(c, "followup_queued", item["id"])
        crm.save(contacts, dry_run)
        log({"action": "followup_queued", "contact": c["id"], "item": item["id"]})
        r["queued"].append(f"{c['name']} ({c['company']}): {result.get('new_angle')}")
        # Keep drafted list for digest compatibility
        r["drafted"].append(f"{c['name']} ({c['company']}) queued for Approvals")
    return r
