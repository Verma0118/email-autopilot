# EmailCRM Autopilot

Daily outreach loop for startup discovery, internship (Collins/Raytheon + UIUC
alums), and NOBE engineered PD projects. Runs at 7:04 AM via launchd, syncs
inbox, drafts replies/outreach/bounce fixes into a local Approvals queue, and
renders a dashboard. **Drafts only: the OAuth token has no send scope.**

## Pipeline (Full run)

1. Inbox sync + deterministic rundown (no LLM)
2. Serial LLM by priority: reply → organize → scout (gated) → organize → bounce → cold followups (off by default)
3. Digest + dashboard + optional encrypted publish

All LLM drafts land in Approvals (`http://localhost:8787`). Nothing sends.

| Stage | What it does | Needs Claude? |
|---|---|---|
| inbox | reply/bounce/sent detection, thread backfill, rundown | **No** |
| Approvals / Update / dismiss | panel actions, Gmail draft create on approve | **No** |
| digest | markdown + `dashboard.html` | **No** |
| reply | open-thread drafts → Approvals (skips OOO / already-replied without LLM) | Yes |
| organize | scout briefs → outreach drafts → Approvals | Yes |
| scout | ICP discovery + research briefs (1 track/day, tight turns) | Yes (Exa) |
| bounce | corrected address research → Approvals | Yes (Exa) |
| followup | cold no-reply (paused: `COLD_FOLLOWUPS_ENABLED`) | Yes |

When Claude is session-limited or the autopilot meter is capped, Phase 1 (inbox) and digest still run. Draft stages defer cleanly instead of burning failed calls.

Autopilot LLM usage hard-stops at `TOKEN_HARD_PCT` (50%) of `SESSION_TOKEN_BUDGET`. Scout gates at 32%; reply/organize/bounce at 42%. Organize writes at most 3 drafts per run; scout researches at most 2 candidates per discovery.

## Architecture

Python owns Gmail and filesystem mutations. Judgment runs through headless
`claude -p` with strict MCP (Exa or nothing) and returns JSON that Python
validates before queueing. The control panel is a React app in `ui/` served by
`panel.py` from `ui/dist`.

## Usage

```bash
.venv/bin/python run.py                              # full run
.venv/bin/python run.py --dry-run                    # no mutations
.venv/bin/python run.py --stage triage|reply|organize|scout|bounce|digest
.venv/bin/python run.py --cap N                      # override stage cap
.venv/bin/python run.py --setup                      # one-time Gmail OAuth
.venv/bin/python panel.py                            # localhost:8787
./bin/refresh-panel                                  # pull main + restart panel
./bin/build-ui                                       # rebuild React UI → ui/dist
```

Legacy stage aliases: `sync`→inbox, `nudge`→reply, `prospect`→scout.

## Not in this repo

Tokens (`~/.config/emailcrm/`), CRM data (`../contacts.json`), run state, logs,
prospect briefs, digests, and `mcp-exa.json` (API key) are gitignored.
Optional attachments: `assets/resume.pdf`, `assets/nobe_overview.pdf`.
