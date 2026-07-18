"""Bounce retry: Exa research → gate → Approvals queue (corrected To + original body).

Never writes straight to Gmail. Approve in the panel creates the draft and
updates the CRM email.
"""
import config
import crm
import gmail
import llm
import queue_store
import status
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
    r = report.setdefault("bounce_retry", {
        "fixed": [], "dead": [], "manual": [], "queued": [], "errors": [], "skipped": []})
    todo = [c for c in crm.eligible_for(contacts, "bounce_retry")
            if not (c.get("autopilot", {}).get("bounce_retry") or {}).get("status")][: cap]

    bounce_turns = int(getattr(config, "BOUNCE_MAX_TURNS", 7) or 7)
    for c in todo:
        status.check_stop()
        if not status.meter_allows(config.BOUNCE_METER_MAX_PCT):
            r["skipped"].append(
                f"meter {status.budget_pct():.0f}% — bounce stopped mid-run")
            break
        if queue_store.has_pending_for(c.get("email")):
            r["skipped"].append(f"{c['name']}: already in Approvals")
            continue
        status.update(detail=f"researching bounce fix: {c['name']} ({c['company']})",
                      stream=config.STREAM_LABELS.get(c.get("email_type"), c.get("email_type")))
        try:
            result = llm.call(_render(c), use_exa=True, max_turns=bounce_turns)
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
        if queue_store.has_pending_for(corrected):
            r["skipped"].append(f"{c['name']}: corrected address already queued")
            continue

        expected = config.subject_for(c.get("email_type"), c.get("company"))
        try:
            hits = [m for m in gmail.search_sent_to(c["email"])
                    if config.subject_matches(m["subject"], c.get("email_type"), c.get("company"))]
            if not hits:
                if not dry_run:
                    ap["bounce_retry"] = {
                        "status": "manual", "corrected_email": corrected,
                        "evidence": [e.get("url") for e in result.get("evidence", [])
                                     if isinstance(e, dict)]}
                    crm.touch(c, "bounce_manual", corrected)
                    crm.save(contacts, dry_run)
                r["manual"].append(
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
            r["queued"].append(f"[DRY] {c['name']}: {c['email']} -> {corrected}")
            continue

        email_type = c.get("email_type")
        attach_names = [p.name for p in config.attachments_for(email_type)]
        item = queue_store.add(
            kind="bounce",
            track_label=config.STREAM_LABELS.get(email_type, "bounce"),
            name=c["name"], company=c.get("company"), email=corrected,
            subject=expected, body_html=body,
            why=f"Bounce fix: {c['email']} → {corrected}",
            meta={
                "contact_id": c["id"],
                "old_email": c["email"],
                "corrected_email": corrected,
                "email_type": email_type,
                "attachments": attach_names,
                "evidence": [e.get("url") for e in result.get("evidence", [])
                             if isinstance(e, dict)],
            },
        )
        ap["bounce_retry"] = {
            "status": "queued", "old_email": c["email"], "corrected_email": corrected,
            "queue_id": item["id"],
            "evidence": [e.get("url") for e in result.get("evidence", []) if isinstance(e, dict)],
        }
        crm.touch(c, "bounce_queued", corrected)
        crm.save(contacts, dry_run)
        log({"action": "bounce_retry_queued", "contact": c["id"], "item": item["id"]})
        r["queued"].append(
            f"{c['name']} ({c['company']}): {c['email']} -> {corrected} (Approvals)")
        # Keep legacy "fixed" empty for Gmail-direct path; dashboard uses queued
        r.setdefault("fixed", [])
    return r
