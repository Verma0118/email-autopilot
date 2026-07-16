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
    try:
        if not args.dry_run:
            crm.backup()
        if crm.migrate(contacts):
            crm.save(contacts, args.dry_run)
            log({"action": "schema_migrated"})

        from stages import bounce_retry, digest, followups, inbox_sync, prospecting, reply_nudges

        def want(s):
            return args.stage in (None, s)

        if want("sync"):
            try:
                inbox_sync.run(contacts, report, dry_run=args.dry_run)
            except Exception:
                report["fatal"].append(f"inbox_sync crashed: {traceback.format_exc(limit=3)}")
        if want("nudge"):
            try:
                reply_nudges.run(contacts, report, args.cap or config.NUDGE_DAILY_CAP,
                                 log, dry_run=args.dry_run)
            except Exception:
                report["fatal"].append(f"reply_nudges crashed: {traceback.format_exc(limit=3)}")
        if want("bounce"):
            try:
                bounce_retry.run(contacts, report, args.cap or config.BOUNCE_DAILY_CAP,
                                 log, dry_run=args.dry_run)
            except Exception:
                report["fatal"].append(f"bounce_retry crashed: {traceback.format_exc(limit=3)}")
        if args.stage == "followup" or (args.stage is None and config.COLD_FOLLOWUPS_ENABLED):
            try:
                followups.run(contacts, report, args.cap or config.FOLLOWUP_DAILY_CAP,
                              log, dry_run=args.dry_run)
            except Exception:
                report["fatal"].append(f"followups crashed: {traceback.format_exc(limit=3)}")
        if want("prospect"):
            try:
                prospecting.run(contacts, report, args.cap or config.PROSPECT_DAILY_CAP,
                                log, dry_run=args.dry_run)
            except Exception:
                report["fatal"].append(f"prospecting crashed: {traceback.format_exc(limit=3)}")

        path, summary = digest.run(contacts, report, llm.calls_made(), dry_run=args.dry_run)
        try:
            import publish
            pub = publish.run(report, dry_run=args.dry_run)
            log({"action": "publish", "status": pub["status"]})
        except Exception:
            report["fatal"].append(f"publish crashed: {traceback.format_exc(limit=2)}")
        log({"action": "run_end", "digest": str(path), "summary": summary})
        print(f"digest: {path}\n{summary}")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
