#!/usr/bin/env python3
"""EmailCRM Autopilot entrypoint.

Usage:
  run.py                 full daily run
  run.py --dry-run       no mutations anywhere, digest to dryrun- file
  run.py --stage sync|bounce|followup|prospect|digest
  run.py --cap N         override the stage cap
  run.py --setup         one-time Gmail OAuth flow

Drafts only. This system has no gmail.send scope and cannot send email.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stage", choices=["sync", "nudge", "bounce", "followup", "prospect", "digest"])
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

        from stages import bounce_retry, digest, followups, inbox_sync, prospecting, reply_nudges

        def want(s):
            return args.stage in (None, s)

        def guarded(name, fn):
            try:
                status.check_stop()
                status.update(stage=name, detail="starting")
                fn()
            except status.Stopped:
                report.setdefault("stopped", True)
                report["fatal"].append(f"{name}: stopped from panel")
                raise
            except Exception:
                report["fatal"].append(f"{name} crashed: {traceback.format_exc(limit=3)}")

        try:
            if want("sync"):
                guarded("inbox sync", lambda: inbox_sync.run(
                    contacts, report, dry_run=args.dry_run))
            if want("nudge"):
                guarded("reply nudges", lambda: reply_nudges.run(
                    contacts, report, args.cap or config.NUDGE_DAILY_CAP, log, dry_run=args.dry_run))
            if want("bounce"):
                guarded("bounce retry", lambda: bounce_retry.run(
                    contacts, report, args.cap or config.BOUNCE_DAILY_CAP, log, dry_run=args.dry_run))
            if args.stage == "followup" or (args.stage is None and config.COLD_FOLLOWUPS_ENABLED):
                guarded("cold follow-ups", lambda: followups.run(
                    contacts, report, args.cap or config.FOLLOWUP_DAILY_CAP, log, dry_run=args.dry_run))
            if want("prospect"):
                guarded("prospecting", lambda: prospecting.run(
                    contacts, report, args.cap or config.PROSPECT_DAILY_CAP, log, dry_run=args.dry_run))
        except status.Stopped:
            pass  # fall through to digest with what we have

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
