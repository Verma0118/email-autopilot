"""EmailCRM Autopilot configuration. All paths and caps in one place."""
import re
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
ASSETS_DIR = AUTOPILOT / "assets"
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
# When re-enabled (or run via --stage followup), drafts go to Approvals.
# Open-thread replies / promise follow-ups are handled by reply_agent.
COLD_FOLLOWUPS_ENABLED = False
LLM_CALL_BUDGET = 40
LLM_TIMEOUT = 300

# Self-metered token budget for autopilot LLM calls (rolling 5h window).
# Anthropic does not expose the real Pro session percentage; this meters
# the autopilot's own consumption only against SESSION_TOKEN_BUDGET.
# Hard-stop at TOKEN_HARD_PCT so other Claude use keeps the remaining ~40%.
SESSION_TOKEN_BUDGET = 200_000
TOKEN_WARN_PCT = 0.50
TOKEN_HARD_PCT = 0.60

# —— Token-efficiency gates (Full run uses these; all ≤ TOKEN_HARD_PCT) ——
# Skip scout when autopilot meter is already this high (0–1).
SCOUT_METER_MAX_PCT = 0.45
# Skip organize LLM work when meter is this high (still ok to no-op).
ORGANIZE_METER_MAX_PCT = 0.55
# Skip bounce research when meter is this high.
BOUNCE_METER_MAX_PCT = 0.55
# If this many unorganized briefs are waiting, organize them and skip scout.
SCOUT_SKIP_IF_BRIEFS_WAITING = 2
# Cheaper scout tool loops (was 12 / 15).
SCOUT_BRIEF_MAX_TURNS = 8
SCOUT_DISCOVERY_MAX_TURNS = 10
# Run discovery for this many ICP tracks per Full/scout run (rotate by day).
# 2 keeps internship + NOBE from starving while startup still gets cycles.
SCOUT_MAX_TRACKS_PER_RUN = 2
# Don't spend a second LLM call on lint retry when meter is already this high.
RETRY_METER_MAX_PCT = 0.55
# Cap Exa amplification: research at most this many discovery hits per track.
SCOUT_MAX_CANDIDATES_PER_DISCOVERY = 3
# Bounce research turns (was hardcoded 12).
BOUNCE_MAX_TURNS = 7
# Bound reply-thread context stuffed into the LLM.
REPLY_THREAD_MAX_MSGS = 8
REPLY_THREAD_MSG_CHARS = 1000

PANEL_PORT = 8787

FOLLOW_UP_DAYS = 7

# Your scheduling link (used when recent sent mail has none). Set this.
CALENDAR_URL = ""

# Fixed subject lines per email type. Never vary except NOBE, which templates
# the company name (see subject_for). networking_warm kept for legacy CRM rows.
FIXED_SUBJECTS = {
    "startup_discovery": "UIUC Students | Coffee Chat Request | Aarav Verma, Rushil Patil",
    "networking_warm": "Coffee Chat Request | Aarav Verma, Fellow Illini",
    "cold_outreach": "Coffee Chat Request | Aarav Verma, Fellow Illini",
    "cold_outreach_not_alum": "Coffee Chat Request University of Illinois Student | Aarav Verma",
}
NOBE_SUBJECT_TEMPLATE = "{company} x NOBE | Engineering Project, Fall 2026"
_NOBE_SUBJECT_RE = re.compile(r".+ x NOBE \| Engineering Project, Fall 2026$")

# Optional file attachments added when an outreach draft is approved.
# Place files under assets/ (missing files are skipped with a warning).
ATTACHMENTS = {
    "cold_outreach": [ASSETS_DIR / "resume.pdf"],
    "cold_outreach_not_alum": [ASSETS_DIR / "resume.pdf"],
    "nobe_pd_outreach": [ASSETS_DIR / "nobe_overview.pdf"],
}


def subject_for(email_type, company=None):
    """Canonical subject for an email_type (NOBE includes company)."""
    if email_type == "nobe_pd_outreach":
        co = (company or "Company").strip() or "Company"
        return NOBE_SUBJECT_TEMPLATE.format(company=co)
    return FIXED_SUBJECTS.get(email_type)


def subject_matches(subject, email_type, company=None):
    """True if a Gmail subject matches the expected line for this type."""
    if not subject or not email_type:
        return False
    subj = subject.strip()
    if subj.lower().startswith("re:"):
        subj = subj[3:].strip()
    if email_type == "nobe_pd_outreach":
        if company:
            return subj == subject_for(email_type, company)
        return bool(_NOBE_SUBJECT_RE.match(subj))
    expected = FIXED_SUBJECTS.get(email_type)
    return bool(expected) and subj == expected


def attachments_for(email_type):
    """Existing attachment paths for this email_type (skips missing files)."""
    out = []
    for path in ATTACHMENTS.get(email_type) or []:
        p = Path(path)
        if p.is_file():
            out.append(p)
    return out


# Friendly stream names shown in the panel, keyed by email_type
STREAM_LABELS = {
    "startup_discovery": "startup discovery",
    "networking_warm": "internship outreach",
    "cold_outreach": "internship outreach",
    "cold_outreach_not_alum": "internship outreach",
    "follow_up": "internship outreach",
    "nobe_pd_outreach": "NOBE",
}

EXA_TOOLS = [
    "mcp__exa__web_search_exa",
    "mcp__exa__company_research_exa",
    "mcp__exa__people_search_exa",
]
