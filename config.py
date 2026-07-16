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

FOLLOW_UP_DAYS = 7

# Fixed subject lines per email type (agent-rules.md section 2). Never vary.
FIXED_SUBJECTS = {
    "startup_discovery": "UIUC Students | Coffee Chat Request | Aarav Verma, Rushil Patil",
    "networking_warm": "Coffee Chat Request | Aarav Verma, Fellow Illini",
    "cold_outreach": "Coffee Chat Request | Aarav Verma, Fellow Illini",
    "cold_outreach_not_alum": "Coffee Chat Request University of Illinois Student | Aarav Verma",
}

EXA_TOOLS = [
    "mcp__exa__web_search_exa",
    "mcp__exa__company_research_exa",
    "mcp__exa__people_search_exa",
]
