"""Stage 3: follow-up drafts. LLM with NO tools; Python lints and drafts."""
import json
import re
from datetime import date

import config
import crm
import gmail
import llm
import status
import validators


def _load_prompt():
    return (config.PROMPT_DIR / "followup_draft.md").read_text()


CAL_URL_RE = re.compile(r'href="(https://(?:calendly\.com|cal\.com|calendar\.google\.com|calendar\.app\.google)[^"]*)"')


def _render(template, contact, original_body, calendar_url):
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
        "<<ORIGINAL_SUBJECT>>": config.FIXED_SUBJECTS.get(contact.get("email_type"), ""),
        "<<ORIGINAL_EMAIL>>": (original_body or "")[:3000],
    }.items():
        out = out.replace(token, str(value))
    return out


def run(contacts, report, cap, log, dry_run=False):
    r = report.setdefault("followups", {"drafted": [], "skipped": [], "errors": []})
    candidates = crm.followup_candidates(contacts)[: cap]
    if not candidates:
        return r

    try:
        existing = gmail.list_drafts_meta()
    except Exception as e:
        r["errors"].append(f"cannot list drafts, aborting stage: {e}")
        return r
    template = _load_prompt()

    for c in candidates:
        status.check_stop()
        status.update(detail=f"drafting follow-up: {c['name']} ({c['company']})",
                      stream=config.STREAM_LABELS.get(c.get("email_type"), c.get("email_type")))
        expected_subject = "Re: " + config.FIXED_SUBJECTS.get(c.get("email_type"), "")

        # crash repair: a matching reply draft already exists in Gmail
        dup = [d for d in existing
               if c["email"].lower() in d["to"].lower() and d["subject"].startswith("Re:")]
        if dup:
            if not dry_run:
                crm.set_status(c, "followed_up", "followup_repaired", dup[0]["draft_id"])
                c["follow_up_count"] = 1
                c["follow_up_draft_id"] = dup[0]["draft_id"]
                crm.save(contacts, dry_run)
            r["skipped"].append(f"{c['name']}: draft already existed (repaired)")
            continue

        html, plain = (None, None)
        try:
            hits = gmail.search_sent_to(c["email"])
            orig = [m for m in hits if m["thread_id"] == c["gmail_thread_id"]]
            if orig:
                html, plain = gmail.get_message_body(min(orig, key=lambda m: m["internal_ms"])["id"])
        except Exception as e:
            r["errors"].append(f"{c['name']}: original fetch failed: {e}")

        cal_match = CAL_URL_RE.search(html or "")
        calendar_url = cal_match.group(1) if cal_match else None
        prompt = _render(template, c, plain or html, calendar_url)

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
            r["drafted"].append(f"[DRY] {c['name']} ({c['company']}): {result.get('new_angle')}")
            continue
        try:
            draft = gmail.create_reply_draft(
                to=c["email"], subject=result["subject"], body_html=result["body_html"],
                thread_id=c["gmail_thread_id"], in_reply_to=c.get("gmail_message_id"),
            )
        except Exception as e:
            r["errors"].append(f"{c['name']}: draft create failed: {e}")
            continue
        crm.set_status(c, "followed_up", "followup_drafted", draft["draft_id"])
        c["follow_up_count"] = 1
        c["follow_up_draft_id"] = draft["draft_id"]
        c["follow_up_drafted_at"] = crm.now_iso()
        crm.save(contacts, dry_run)
        log({"action": "followup_drafted", "contact": c["id"], "draft_id": draft["draft_id"]})
        r["drafted"].append(
            f"{c['name']} ({c['company']}) angle: {result.get('new_angle')} "
            f"link: {gmail.draft_link(draft['thread_id'])}\n"
            f"  BODY: {validators._strip_html(result['body_html'])}"
        )
    return r
