#!/usr/bin/env python3
"""EmailCRM Autopilot entrypoint.

Usage:
  run.py                 full daily run
  run.py --dry-run       no mutations anywhere, digest to dryrun- file
  run.py --stage triage|reply|organize|scout|bounce|followup|digest|inbox
  run.py --cap N         override the stage cap
  run.py --setup         one-time Gmail OAuth flow
  # legacy aliases: sync→inbox, nudge→reply, prospect→scout

Drafts only. This system has no gmail.send scope and cannot send email.

Pipeline (full run):
  1) Inbox sync + deterministic rundown (no LLM)
  2) Serial LLM by priority (token-efficient):
     reply → organize (drain waiting) → scout (if meter OK + few waiting)
     → organize (new briefs) → bounce → cold followups (if enabled)
  3) Digest + publish

All LLM drafts (reply, outreach, bounce, followup) go to Approvals — never
straight to Gmail. Scout covers startup / internship / NOBE tracks.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
import crm
import gmail
import llm
import status


def notify(text):
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{text}" with title "EmailCRM Autopilot"'],
                       timeout=10)
    except Exception:
        pass


def acquire_lock():
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    if config.LOCK_FILE.exists():
        try:
            data = json.loads(config.LOCK_FILE.read_text())
            if time.time() - data.get("ts", 0) < config.LOCK_STALE_SECONDS:
                print(f"another run active (pid {data.get('pid')}), exiting")
                sys.exit(0)
        except Exception:
            pass
    config.LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "ts": time.time()}))


def release_lock():
    config.LOCK_FILE.unlink(missing_ok=True)


def make_logger(dry_run):
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = config.LOG_DIR / f"run-{date.today().isoformat()}.jsonl"

    def log(record):
        record = dict(record, ts=datetime.now().isoformat(timespec="seconds"), dry=dry_run)
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")
    return log


def _skip(report, section, reason, log):
    bucket = report.setdefault(section, {})
    bucket.setdefault("skipped", []).append(reason)
    log({"action": "stage_skipped", "stage": section, "reason": reason})
    status.update(detail=reason)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stage", choices=["inbox", "reply", "scout", "organize",
                                        "bounce", "followup", "digest", "triage",
                                        "sync", "nudge", "prospect"])  # last 3 = legacy aliases
    ap.add_argument("--cap", type=int)
    ap.add_argument("--setup", action="store_true")
    args = ap.parse_args()

    if args.setup:
        gmail.setup()
        return

    # preflight: TCC canary
    try:
        contacts = crm.load()
    except Exception as e:
        notify("Autopilot blocked: cannot read contacts.json (grant disk access?)")
        print(f"preflight failed: {e}", file=sys.stderr)
        sys.exit(1)
    # preflight: token
    try:
        gmail.get_service()
    except gmail.NeedsSetup as e:
        notify("Autopilot blocked: Gmail token missing/expired. Run run.py --setup")
        print(f"preflight failed: {e}", file=sys.stderr)
        sys.exit(1)

    acquire_lock()
    report = {"fatal": []}
    log = make_logger(args.dry_run)
    log({"action": "run_start", "stage": args.stage or "all"})
    status.begin(args.stage or "all")
    try:
        if not args.dry_run:
            crm.backup()
        if crm.migrate(contacts):
            crm.save(contacts, args.dry_run)
            log({"action": "schema_migrated"})

        from stages import (bounce_retry, digest, followups, inbox_agent,
                            inbox_sync, organizer, prospecting, reply_agent)

        alias = {"sync": "inbox", "nudge": "reply", "prospect": "scout"}
        stage = alias.get(args.stage, args.stage)
        TRIAGE = frozenset({"inbox", "reply", "bounce"})

        def want(s):
            if stage is None:
                return True
            if stage == "triage":
                return s in TRIAGE
            return stage == s

        def guarded(name, fn):
            try:
                status.check_stop()
                status.update(stage=name, detail="starting")
                fn()
            except status.Stopped:
                report.setdefault("stopped", True)
                raise
            except Exception:
                report["fatal"].append(f"{name} crashed: {traceback.format_exc(limit=3)}")

        # —— Phase 1: inbox sync only (no LLM) ——
        if want("inbox"):
            status.set_field("rundown", "Updating…")
            guarded("inbox sync", lambda: inbox_sync.run(
                contacts, report, dry_run=args.dry_run))
            # Immediate deterministic rundown so Overview never stays stale
            guarded("inbox rundown", lambda: inbox_agent.write_rundown(
                contacts, report, log, dry_run=args.dry_run))

        # —— Phase 2: LLM drafts (skip cleanly when Claude is unavailable) ——
        # reply → organize → scout (gated) → organize → bounce → followups
        if not llm.available():
            snap = status.tokens_snapshot()
            why = ("Claude session limit latched"
                   if snap.get("limit_hit")
                   else "Claude / token budget unavailable")
            if want("reply"):
                _skip(report, "reply_agent",
                      f"{why}: reply drafts deferred (inbox sync already done)", log)
            if want("organize"):
                _skip(report, "organizer", f"{why}: organize deferred", log)
            if want("scout"):
                _skip(report, "prospecting", f"{why}: scout deferred", log)
            if want("bounce"):
                _skip(report, "bounce_retry", f"{why}: bounce research deferred", log)
            if stage == "followup" or (stage is None and config.COLD_FOLLOWUPS_ENABLED):
                _skip(report, "followups", f"{why}: follow-ups deferred", log)
            status.update(detail=f"{why}. Inbox sync still ran.")
        else:
            if want("reply"):
                guarded("reply agent", lambda: reply_agent.run(
                    contacts, report, args.cap or config.NUDGE_DAILY_CAP, log,
                    dry_run=args.dry_run))

            if want("organize"):
                if status.meter_allows(config.ORGANIZE_METER_MAX_PCT):
                    guarded("organizer", lambda: organizer.run(
                        contacts, report, log, dry_run=args.dry_run))
                else:
                    _skip(report, "organizer",
                          f"meter {status.budget_pct():.0f}% — organize deferred", log)

            scout_ran = False
            if want("scout"):
                waiting = organizer.waiting_count()
                skip_reason = None
                # Full-run only: prefer draining briefs over mining more
                if stage is None and waiting >= config.SCOUT_SKIP_IF_BRIEFS_WAITING:
                    skip_reason = (f"skipping scout: {waiting} briefs waiting "
                                   f"(≥{config.SCOUT_SKIP_IF_BRIEFS_WAITING})")
                elif not status.meter_allows(config.SCOUT_METER_MAX_PCT):
                    skip_reason = (f"skipping scout: meter {status.budget_pct():.0f}% "
                                   f"(gate {config.SCOUT_METER_MAX_PCT * 100:.0f}%)")
                elif not llm.available():
                    skip_reason = "skipping scout: Claude unavailable"
                if skip_reason:
                    _skip(report, "prospecting", skip_reason, log)
                else:
                    guarded("scout agent", lambda: prospecting.run(
                        contacts, report, args.cap, log, dry_run=args.dry_run))
                    scout_ran = True

            # Second organize pass after scout produced new briefs
            if scout_ran and want("organize"):
                if llm.available() and status.meter_allows(config.ORGANIZE_METER_MAX_PCT):
                    guarded("organizer", lambda: organizer.run(
                        contacts, report, log, dry_run=args.dry_run))
                else:
                    _skip(report, "organizer",
                          f"meter {status.budget_pct():.0f}% — post-scout organize deferred", log)

            if want("bounce"):
                if llm.available() and status.meter_allows(config.BOUNCE_METER_MAX_PCT):
                    guarded("bounce retry", lambda: bounce_retry.run(
                        contacts, report, args.cap or config.BOUNCE_DAILY_CAP, log,
                        dry_run=args.dry_run))
                else:
                    _skip(report, "bounce_retry",
                          f"meter {status.budget_pct():.0f}% — bounce deferred", log)

            if stage == "followup" or (stage is None and config.COLD_FOLLOWUPS_ENABLED):
                if llm.available():
                    guarded("cold follow-ups", lambda: followups.run(
                        contacts, report, args.cap or config.FOLLOWUP_DAILY_CAP, log,
                        dry_run=args.dry_run))
                else:
                    _skip(report, "followups", "Claude unavailable: follow-ups deferred", log)

        status.update(stage="digest", detail="writing digest + dashboard")
        path, summary = digest.run(contacts, report, llm.calls_made(), dry_run=args.dry_run)
        try:
            import publish
            pub = publish.run(report, dry_run=args.dry_run)
            log({"action": "publish", "status": pub["status"]})
        except Exception:
            report["fatal"].append(f"publish crashed: {traceback.format_exc(limit=2)}")
        log({"action": "run_end", "digest": str(path), "summary": summary})
        status.end(summary + (" — STOPPED EARLY" if report.get("stopped") else ""))
        print(f"digest: {path}\n{summary}")
    finally:
        release_lock()
        status.STOP_FLAG.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
