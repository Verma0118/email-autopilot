"""Stage 2: bounce retry. Exa research -> deterministic gate -> corrected draft."""
import config
import crm
import gmail
import llm
import validators


def _render(contact):
    template = (config.PROMPT_DIR / "bounce_research.md").read_text()
    for token, value in {
        "<<NAME>>": contact["name"],
        "<<COMPANY>>": contact["company"],
        "<<ROLE>>": contact.get("role") or "",
        "<<OLD_EMAIL>>": contact["email"],
        "<<LINKEDIN>>": contact.get("linkedin_url") or "",
    }.items():
        template = template.replace(token, str(value))
    return template


def run(contacts, report, cap, log, dry_run=False):
    r = report.setdefault("bounce_retry", {"fixed": [], "dead": [], "errors": []})
    todo = [c for c in crm.eligible_for(contacts, "bounce_retry")
            if not (c.get("autopilot", {}).get("bounce_retry") or {}).get("status")][: cap]

    for c in todo:
        try:
            result = llm.call(_render(c), use_exa=True, max_turns=12)
        except llm.LLMError as e:
            r["errors"].append(f"{c['name']}: {e}")
            if llm.llm_down:
                break
            continue

        ok, reason = validators.bounce_gate(result, c["email"])
        ap = c.setdefault("autopilot", {})
        if not ok:
            if not dry_run:
                ap["bounce_retry"] = {"status": "dead", "reason": reason,
                                      "evidence": result.get("evidence", [])}
                crm.set_status(c, "bounce_dead", "bounce_gate_failed", reason)
                crm.save(contacts, dry_run)
            r["dead"].append(f"{c['name']} ({c['company']}): {reason}")
            continue

        corrected = result["corrected_email"].strip().lower()
        # fetch original sent body to resend verbatim
        expected = config.FIXED_SUBJECTS.get(c.get("email_type"))
        try:
            hits = [m for m in gmail.search_sent_to(c["email"])
                    if m["subject"].strip() == expected]
            if not hits:
                if not dry_run:
                    ap["bounce_retry"] = {"status": "manual", "corrected_email": corrected,
                                          "evidence": [e.get("url") for e in result.get("evidence", []) if isinstance(e, dict)]}
                    crm.touch(c, "bounce_manual", corrected)
                    crm.save(contacts, dry_run)
                r.setdefault("manual", []).append(
                    f"{c['name']} ({c['company']}): verified address {corrected}, but original "
                    f"sent email not found under fixed subject. Send manually.")
                continue
            html, plain = gmail.get_message_body(min(hits, key=lambda m: m["internal_ms"])["id"])
            body = html or (f"<html><body><p>{(plain or '').replace(chr(10), '<br>')}</p></body></html>")
        except Exception as e:
            r["errors"].append(f"{c['name']}: original fetch failed: {e}")
            continue

        log({"action": "bounce_retry_intent", "contact": c["id"],
             "old": c["email"], "corrected": corrected})
        if dry_run:
            r["fixed"].append(f"[DRY] {c['name']}: {c['email']} -> {corrected}")
            continue
        try:
            draft = gmail.create_draft(subject=expected, body_html=body, to=corrected)
        except Exception as e:
            r["errors"].append(f"{c['name']}: draft create failed: {e}")
            continue
        ap["bounce_retry"] = {
            "status": "retried", "old_email": c["email"], "corrected_email": corrected,
            "evidence": [e.get("url") for e in result.get("evidence", []) if isinstance(e, dict)],
            "drafted_at": crm.now_iso(),
        }
        c["email"] = corrected
        crm.set_status(c, "bounce_fixed", "bounce_retried", f"-> {corrected}")
        c["follow_up_due"] = crm.due_plus_followup_days()
        crm.save(contacts, dry_run)
        log({"action": "bounce_retry_drafted", "contact": c["id"], "draft_id": draft["draft_id"]})
        r["fixed"].append(f"{c['name']} ({c['company']}): {ap['bounce_retry']['old_email']} -> {corrected}")
    return r
