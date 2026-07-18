"""EmailCRM Autopilot configuration. All paths and caps in one place."""
from pathlib import Path

HOME = Path.home()
ROOT = HOME / "Desktop" / "EmailCRM"
AUTOPILOT = ROOT / "autopilot"

CONTACTS = ROOT / "contacts.json"
DIGEST_DIR = ROOT / "digests"
QUEUE_PROSPECTS = AUTOPILOT / "queue" / "prospects"
STATE_DIR = AUTOPILOT / "state"
LOG_DIR = AUTOPILOT / "logs"
PROMPT_DIR = AUTOPILOT / "prompts"
ICP_FILE = AUTOPILOT / "icp.yaml"
MCP_EXA = AUTOPILOT / "mcp-exa.json"
MCP_EMPTY = AUTOPILOT / "mcp-empty.json"

CONFIG_DIR = HOME / ".config" / "emailcrm"
CLIENT_SECRET = CONFIG_DIR / "client_secret.json"
TOKEN_FILE = CONFIG_DIR / "token.json"

LOCK_FILE = STATE_DIR / "run.lock"
LOCK_STALE_SECONDS = 2 * 60 * 60
SEEN_BOUNCES = STATE_DIR / "seen_bounces.json"
PROSPECTS_SEEN = STATE_DIR / "prospects_seen.json"
DAILY_COUNTERS = STATE_DIR / "daily_counters.json"

ACCOUNT = "aarav.verma.eng0118@gmail.com"
CLAUDE_BIN = str(HOME / ".local" / "bin" / "claude")

FOLLOWUP_DAILY_CAP = 12
PROSPECT_DAILY_CAP = 5
BOUNCE_DAILY_CAP = 5
NUDGE_DAILY_CAP = 5

# Cold no-reply follow-ups paused 2026-07-15 (pre-pivot backlog is stale).
# Reply nudges (people who replied then went silent past a promised date) run instead.
# Re-enable with True or run manually: run.py --stage followup --cap N
COLD_FOLLOWUPS_ENABLED = False
LLM_CALL_BUDGET = 40
LLM_TIMEOUT = 300

# Self-metered token budget for autopilot LLM calls (rolling 5h window).
# Anthropic does not expose the real Pro session percentage; this meters
# the autopilot's own consumption only. Warn at 60%, hard-stop LLM at 100%.
SESSION_TOKEN_BUDGET = 200_000
TOKEN_WARN_PCT = 0.60

# —— Token-efficiency gates (Full run uses these) ——
# Skip scout when autopilot meter is already this high (0–1).
SCOUT_METER_MAX_PCT = 0.45
# Skip organize LLM work when meter is this high (still ok to no-op).
ORGANIZE_METER_MAX_PCT = 0.90
# Skip bounce research when meter is this high.
BOUNCE_METER_MAX_PCT = 0.85
# If this many unorganized briefs are waiting, organize them and skip scout.
SCOUT_SKIP_IF_BRIEFS_WAITING = 2
# Cheaper scout tool loops (was 12 / 15).
SCOUT_BRIEF_MAX_TURNS = 8
SCOUT_DISCOVERY_MAX_TURNS = 10
# Only run discovery for this many ICP tracks per Full run (rotate by day).
SCOUT_MAX_TRACKS_PER_RUN = 1
# Don't spend a second LLM call on lint retry when meter is already this high.
RETRY_METER_MAX_PCT = 0.88
# Cap Exa amplification: research at most this many discovery hits per track.
SCOUT_MAX_CANDIDATES_PER_DISCOVERY = 3
# Bounce research turns (was hardcoded 12).
BOUNCE_MAX_TURNS = 7
# Bound reply-thread context stuffed into the LLM.
REPLY_THREAD_MAX_MSGS = 8
REPLY_THREAD_MSG_CHARS = 1000

PANEL_PORT = 8787

FOLLOW_UP_DAYS = 7

# Fixed subject lines per email type (agent-rules.md section 2). Never vary.
FIXED_SUBJECTS = {
    "startup_discovery": "UIUC Students | Coffee Chat Request | Aarav Verma, Rushil Patil",
    "networking_warm": "Coffee Chat Request | Aarav Verma, Fellow Illini",
    "cold_outreach": "Coffee Chat Request | Aarav Verma, Fellow Illini",
    "cold_outreach_not_alum": "Coffee Chat Request University of Illinois Student | Aarav Verma",
}

# Friendly stream names shown in the panel, keyed by email_type
STREAM_LABELS = {
    "startup_discovery": "startup discovery",
    "networking_warm": "internship outreach",
    "cold_outreach": "internship outreach",
    "follow_up": "internship outreach",
    "nobe_pd_outreach": "NOBE",
}

EXA_TOOLS = [
    "mcp__exa__web_search_exa",
    "mcp__exa__company_research_exa",
    "mcp__exa__people_search_exa",
]
