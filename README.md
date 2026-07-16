# EmailCRM Autopilot

Autonomous daily outreach loop. Runs at 7:04 AM via launchd, syncs the inbox,
handles bounces, drafts reply nudges, researches new prospects, and renders a
local dashboard. **Drafts only: the OAuth token has no send scope, so this
system is structurally incapable of sending email.**

## Stages

| Stage | What it does | LLM |
|---|---|---|
| inbox sync | reply/bounce/sent detection, Gmail thread backfill | no |
| reply nudges | people who replied, promised contact, went silent past the date | yes (no tools) |
| bounce retry | research corrected address (exa), evidence + MX gate, corrected draft | yes (exa) |
| cold follow-ups | paused by default (`COLD_FOLLOWUPS_ENABLED`), one per contact lifetime | yes (no tools) |
| prospecting | ICP candidate discovery + research briefs to `queue/prospects/`, never drafts | yes (exa) |
| digest | markdown digest + `dashboard.html` + macOS notification | no |

## Architecture

Python orchestrator owns all Gmail and filesystem mutations. LLM judgment runs
through headless `claude -p` with strict MCP config (exa only, or nothing) and
returns JSON that Python validates (style lint, confidence gates) before acting.

## Usage

```bash
.venv/bin/python run.py                # full run
.venv/bin/python run.py --dry-run      # no mutations
.venv/bin/python run.py --stage sync|nudge|bounce|followup|prospect|digest
.venv/bin/python run.py --cap N        # override stage cap
.venv/bin/python run.py --setup        # one-time Gmail OAuth
```

## Not in this repo

Tokens (`~/.config/emailcrm/`), CRM data (`../contacts.json`), run state, logs,
prospect briefs, digests, and `mcp-exa.json` (holds an API key) are gitignored.
This repo is the code only.
