"""Organizer Agent: turn passing scout briefs into send-ready outreach emails
in the approval queue, grouped by track.

On a full run this drains waiting briefs before scout (priority) and again
after scout if new briefs were written."""
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
    """Prefer config.CALENDAR_URL; else scrape a recent sent outreach email."""
    configured = (getattr(config, "CALENDAR_URL", None) or "").strip()
    if configured.startswith("http"):
        return configured
    try:
        for m in gmail.search_messages("in:sent newer_than:60d", max_results=15):
            html, _ = gmail.get_message_body(m["id"])
            match = CAL_URL_RE.search(html or "")
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def _resolve_email_type(rec, brief):
    """Track default + UIUC alum evidence → concrete email_type."""
    email_type = rec.get("email_type") or "startup_discovery"
    if email_type in ("cold_outreach", "cold_outreach_not_alum"):
        if brief.get("is_uiuc_alum") is False:
            return "cold_outreach_not_alum"
        if brief.get("suggested_email_type") == "cold_outreach_not_alum":
            return "cold_outreach_not_alum"
        return "cold_outreach"
    return email_type


def _track_rules(email_type):
    """Inject only the matching track rules (not all three) into the prompt."""
    key = email_type or "startup_discovery"
    if key == "cold_outreach_not_alum":
        key = "cold_outreach"
    path = config.PROMPT_DIR / f"outreach_rules_{key}.md"
    if path.exists():
        return path.read_text().strip()
    fallback = config.PROMPT_DIR / "outreach_rules_startup_discovery.md"
    return fallback.read_text().strip() if fallback.exists() else ""


def _brief_needs_organize(rec):
    if rec.get("organized"):
        return False
    address = (rec.get("brief", {}).get("email") or {}).get("address")
    return not queue_store.has_pending_for(address)


def waiting_count():
    """Unorganized prospect briefs that still need an outreach draft."""
    n = 0
    for path in config.QUEUE_PROSPECTS.glob("*.json"):
        try:
            rec = json.loads(path.read_text())
        except Exception:
            continue
        if _brief_needs_organize(rec):
            n += 1
    return n


def run(contacts, report, log, dry_run=False):
    r = report.setdefault("organizer", {"queued": [], "skipped": [], "errors": []})
    if not status.meter_allows(config.ORGANIZE_METER_MAX_PCT):
        r["skipped"].append(
            f"meter {status.budget_pct():.0f}% — organize deferred")
        return r
    status.update(stage="organizer", detail="collecting scout briefs")
    template = (config.PROMPT_DIR / "outreach_draft.md").read_text()
    calendar_url = _calendar_url()

    briefs = sorted(config.QUEUE_PROSPECTS.glob("*.json"))
    todo = []
    for path in briefs:
        try:
            rec = json.loads(path.read_text())
        except Exception:
            continue
        if _brief_needs_organize(rec):
            todo.append((path, rec))

    for path, rec in todo:
        status.check_stop()
        cand, brief = rec["candidate"], rec["brief"]
        email_type = _resolve_email_type(rec, brief)
        track_label = config.STREAM_LABELS.get(email_type, rec.get("track", ""))
        status.update(detail=f"writing outreach draft: {cand.get('name')} ({cand.get('company')})",
                      stream=track_label)
        subject = config.subject_for(email_type, cand.get("company"))
        if not subject:
            r["skipped"].append(f"{cand.get('name')}: no subject for {email_type}")
            continue
        hooks = "\n".join(f"- {h.get('fact')} ({h.get('url')})"
                          for h in brief.get("hooks", []) if isinstance(h, dict))
        prompt = template
        for token, value in {
            "<<NAME>>": cand.get("name"), "<<ROLE>>": cand.get("role"),
            "<<COMPANY>>": cand.get("company"), "<<TRACK>>": track_label,
            "<<EMAIL_TYPE>>": email_type, "<<WHY_ICP>>": cand.get("why_icp"),
            "<<SIGNAL>>": brief.get("company_signal"), "<<HOOKS>>": hooks,
            "<<SUBJECT>>": subject,
            "<<TRACK_RULES>>": _track_rules(email_type),
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
        attach_names = [p.name for p in config.attachments_for(email_type)]
        item = queue_store.add(
            kind="outreach", track_label=track_label,
            name=cand.get("name"), company=cand.get("company"), email=address,
            subject=result["subject"], body_html=result["body_html"],
            why=result.get("hook_used", ""),
            meta={"brief_file": path.name, "email_type": email_type,
                  "linkedin": cand.get("linkedin_url"),
                  "role": cand.get("role"),
                  "segment": cand.get("segment"),
                  "is_uiuc_alum": brief.get("is_uiuc_alum"),
                  "email_basis": (brief.get("email") or {}).get("basis"),
                  "company_signal": brief.get("company_signal"),
                  "hooks": hooks[:800] if hooks else "",
                  "attachments": attach_names},
        )
        rec["organized"] = True
        rec["email_type"] = email_type
        path.write_text(json.dumps(rec, indent=1))
        log({"action": "outreach_queued", "candidate": cand.get("name"), "item": item["id"]})
        r["queued"].append(f"[{track_label}] {cand.get('name')} ({cand.get('company')})")
    return r
