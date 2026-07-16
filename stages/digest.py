"""Stage 5: digest markdown + macOS notification. Always runs."""
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
    nu = report.get("reply_nudges", {})
    fu = report.get("followups", {})
    br = report.get("bounce_retry", {})
    pr = report.get("prospecting", {})
    status_counts = crm.counts(contacts)
    overdue = len(crm.followup_candidates(contacts))

    all_errors = (sync.get("errors", []) + nu.get("errors", []) + fu.get("errors", [])
                  + br.get("errors", []) + pr.get("errors", []) + report.get("fatal", []))

    md = f"""# EmailCRM Autopilot Digest — {today}{' (DRY RUN)' if dry_run else ''}
{_section("Replies detected (action: respond!)", sync.get("replies"))}{_section("Sends detected (you sent these manually)", sync.get("sent_detected"))}{_section("OOO auto-replies (not counted as replies)", sync.get("ooo"))}{_section("Bounces detected", sync.get("bounces"))}{_section("Bounces fixed (corrected drafts in Gmail)", br.get("fixed"))}{_section("Bounces needing manual send (verified address found)", br.get("manual"))}{_section("Bounces dead (no confident fix)", br.get("dead"))}{_section("Reply nudges drafted (they promised, went silent — review + send)", nu.get("drafted"))}{_section("We owe them contact later (calendar it)", nu.get("we_owe"))}{_section("Nudges skipped", nu.get("skipped"))}{_section("Follow-up drafts created (review + send in Gmail Drafts)", fu.get("drafted"))}{_section("Follow-ups skipped", fu.get("skipped"))}{_section("New prospect briefs (queue/prospects/)", pr.get("briefs"))}{_section("Prospects rejected by confidence bar", pr.get("rejected"))}{_section("Backfill ambiguous (manual thread check needed)", sync.get("backfill_ambiguous"))}{_section("Errors", all_errors)}
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

    n_fu = len(fu.get("drafted", [])) + len(nu.get("drafted", []))
    n_re = len(sync.get("replies", []))
    n_br = len(pr.get("briefs", []))
    n_err = len(all_errors)
    summary = f"{n_fu} follow-ups drafted, {n_re} replies, {n_br} briefs" + (f", {n_err} errors" if n_err else "")
    if not dry_run:
        try:
            subprocess.run([
                "osascript", "-e",
                f'display notification "{summary}" with title "EmailCRM Autopilot" sound name "Glass"',
            ], timeout=10)
        except Exception:
            pass
    return path, summary
