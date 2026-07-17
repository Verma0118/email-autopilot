"""Organizer Agent: turn passing scout briefs into send-ready outreach emails
in the approval queue, grouped by track. Runs after Inbox + Scout finish."""
import json
import re

import config
import gmail
import llm
import queue_store
import status
import validators

CAL_URL_RE = re.compile(r'href="(https://(?:calendly\.com|cal\.com|calendar\.app\.google)[^"]*)"')


def _calendar_url():
    """Pull Aarav's real scheduling link from a recent sent outreach email."""
    try:
        for m in gmail.search_messages("in:sent newer_than:60d", max_results=15):
            html, _ = gmail.get_message_body(m["id"])
            match = CAL_URL_RE.search(html or "")
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def _subject_for(email_type):
    if email_type == "nobe_pd_outreach":
        return None  # templated per company below
    return config.FIXED_SUBJECTS.get(email_type)


def run(contacts, report, log, dry_run=False):
    r = report.setdefault("organizer", {"queued": [], "skipped": [], "errors": []})
    status.update(stage="organizer", detail="collecting scout briefs")
    template = (config.PROMPT_DIR / "outreach_draft.md").read_text()
    calendar_url = _calendar_url()

    briefs = sorted(config.QUEUE_PROSPECTS.glob("*.json"))
    todo = []
    for path in briefs:
        rec = json.loads(path.read_text())
        if not rec.get("organized") and not queue_store.has_pending_for(
                (rec.get("brief", {}).get("email") or {}).get("address")):
            todo.append((path, rec))

    for path, rec in todo:
        status.check_stop()
        cand, brief = rec["candidate"], rec["brief"]
        email_type = rec.get("email_type", "startup_discovery")
        track_label = config.STREAM_LABELS.get(email_type, rec.get("track", ""))
        status.update(detail=f"writing outreach draft: {cand.get('name')} ({cand.get('company')})",
                      stream=track_label)
        subject = _subject_for(email_type) or f"{cand.get('company')} x NOBE | Engineering Project, Fall 2026"
        hooks = "\n".join(f"- {h.get('fact')} ({h.get('url')})"
                          for h in brief.get("hooks", []) if isinstance(h, dict))
        prompt = template
        for token, value in {
            "<<NAME>>": cand.get("name"), "<<ROLE>>": cand.get("role"),
            "<<COMPANY>>": cand.get("company"), "<<TRACK>>": track_label,
            "<<EMAIL_TYPE>>": email_type, "<<WHY_ICP>>": cand.get("why_icp"),
            "<<SIGNAL>>": brief.get("company_signal"), "<<HOOKS>>": hooks,
            "<<SUBJECT>>": subject,
            "<<CALENDAR_URL>>": calendar_url or "NONE_FOUND",
        }.items():
            prompt = prompt.replace(token, str(value or ""))

        def validate(result):
            if not isinstance(result, dict) or "body_html" not in result:
                return ["output must be JSON with subject, body_html, hook_used"]
            errs = validators.lint_outreach(result.get("subject", ""), result["body_html"],
                                            subject, email_type)
            if calendar_url is None:
                errs = [e for e in errs if "anchor" not in e]
            return errs

        try:
            result, errors = llm.call_with_retry(prompt, use_exa=False, validate=validate)
        except llm.LLMError as e:
            r["errors"].append(f"{cand.get('name')}: {e}")
            if llm.llm_down:
                break
            continue
        if errors:
            r["skipped"].append(f"{cand.get('name')}: lint failed twice: {errors}")
            continue
        if dry_run:
            r["queued"].append(f"[DRY] [{track_label}] {cand.get('name')}")
            continue

        address = (brief.get("email") or {}).get("address")
        item = queue_store.add(
            kind="outreach", track_label=track_label,
            name=cand.get("name"), company=cand.get("company"), email=address,
            subject=result["subject"], body_html=result["body_html"],
            why=result.get("hook_used", ""),
            meta={"brief_file": path.name, "email_type": email_type,
                  "linkedin": cand.get("linkedin_url"),
                  "email_basis": (brief.get("email") or {}).get("basis")},
        )
        rec["organized"] = True
        path.write_text(json.dumps(rec, indent=1))
        log({"action": "outreach_queued", "candidate": cand.get("name"), "item": item["id"]})
        r["queued"].append(f"[{track_label}] {cand.get('name')} ({cand.get('company')})")
    return r
