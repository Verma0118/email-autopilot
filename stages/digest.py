"""Digest markdown + dashboard + macOS notification. Always runs at end of pipeline."""
import subprocess
from datetime import date

import config
import crm


def _section(title, items):
    if not items:
        return ""
    lines = "\n".join(f"- {i}" for i in items)
    return f"\n## {title}\n{lines}\n"


def run(contacts, report, llm_calls, dry_run=False):
    today = date.today().isoformat()
    sync = report.get("inbox_sync", {})
    ia = report.get("inbox_agent", {})
    ra = report.get("reply_agent", {})
    org = report.get("organizer", {})
    fu = report.get("followups", {})
    br = report.get("bounce_retry", {})
    pr = report.get("prospecting", {})
    status_counts = crm.counts(contacts)
    overdue = len(crm.followup_candidates(contacts))

    all_errors = (sync.get("errors", []) + ra.get("errors", []) + org.get("errors", [])
                  + fu.get("errors", []) + br.get("errors", []) + pr.get("errors", [])
                  + report.get("fatal", []))

    we_owe = list(ra.get("we_owe", []) or [])
    approvals = (
        (ra.get("queued") or [])
        + (org.get("queued") or [])
        + (br.get("queued") or [])
        + (fu.get("queued") or [])
    )
    rundown_block = f"\n> {ia['rundown']}\n" if ia.get("rundown") else ""
    md = f"""# EmailCRM Autopilot Digest — {today}{' (DRY RUN)' if dry_run else ''}
{rundown_block}{_section("Awaiting your approval (panel: localhost:8787)", approvals)}{_section("Inbox action items", ia.get("action_items", []))}{_section("Replies detected (action: respond!)", sync.get("replies"))}{_section("Sends detected (you sent these manually)", sync.get("sent_detected"))}{_section("OOO auto-replies (not counted as replies)", sync.get("ooo"))}{_section("Bounces detected", sync.get("bounces"))}{_section("Bounces queued for Approvals", br.get("queued"))}{_section("Bounces needing manual send (verified address found)", br.get("manual"))}{_section("Bounces dead (no confident fix)", br.get("dead"))}{_section("We owe them contact later (calendar it)", we_owe)}{_section("Follow-ups queued for Approvals", fu.get("queued") or fu.get("drafted"))}{_section("Follow-ups skipped", fu.get("skipped"))}{_section("New prospect briefs (queue/prospects/)", pr.get("briefs"))}{_section("Prospects rejected by confidence bar", pr.get("rejected"))}{_section("Scout / organize skipped", (pr.get("skipped") or []) + (org.get("skipped") or []))}{_section("Backfill ambiguous (manual thread check needed)", sync.get("backfill_ambiguous"))}{_section("Errors", all_errors)}
## Pipeline
- Status counts: {status_counts}
- Follow-up backlog remaining: {overdue}
- Threads backfilled this run: {sync.get("backfilled", 0)}
- LLM calls used: {llm_calls}
"""
    path = config.DIGEST_DIR / f"{'dryrun-' if dry_run else ''}{today}.md"
    path.write_text(md)

    try:
        from stages import dashboard
        dashboard.render(contacts, report, llm_calls, dry_run=dry_run)
    except Exception as e:
        all_errors.append(f"dashboard render failed: {e}")

    n_q = len(approvals)
    n_re = len(sync.get("replies") or [])
    n_br = len(pr.get("briefs") or [])
    summary = (f"{n_q} awaiting approval, {n_re} replies, {n_br} briefs"
               + (f", {len(all_errors)} errors" if all_errors else ""))
    if not dry_run:
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{summary}" with title "EmailCRM Autopilot" '
                 f'sound name "Glass"'],
                timeout=10)
        except Exception:
            pass
    return path, summary
