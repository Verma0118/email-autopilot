"""Live run status + stop flag + token metering (rolling 5h window)."""
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta

import config

_lock = threading.Lock()

STATUS_FILE = config.STATE_DIR / "status.json"
STOP_FLAG = config.STATE_DIR / "stop.flag"
TOKENS_FILE = config.STATE_DIR / "tokens_session.json"
WINDOW_SECONDS = 5 * 60 * 60

_state = {}


class Stopped(Exception):
    pass


def _write():
    _state["last_update"] = datetime.now().isoformat(timespec="seconds")
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_state, indent=1))
    tmp.replace(STATUS_FILE)


def begin(mode):
    _state.clear()
    _state.update({
        "running": True, "pid": os.getpid(), "mode": mode,
        "started": datetime.now().isoformat(timespec="seconds"),
        "stage": "preflight", "detail": "", "stream": None,
        "rundown": "Updating…",
        "events": [], "tokens": tokens_snapshot(),
    })
    STOP_FLAG.unlink(missing_ok=True)
    _write()


def update(stage=None, detail=None, stream=None):
  with _lock:
    if stage is not None:
        _state["stage"] = stage
    if detail is not None:
        _state["detail"] = detail
    if stream is not None:
        _state["stream"] = stream
    ev = {"ts": datetime.now().strftime("%H:%M:%S"),
          "stage": _state.get("stage"), "detail": _state.get("detail"),
          "stream": _state.get("stream")}
    events = _state.setdefault("events", [])
    if not events or (events[-1]["detail"], events[-1]["stage"]) != (ev["detail"], ev["stage"]):
        events.append(ev)
    _state["events"] = events[-60:]
    _state["tokens"] = tokens_snapshot()
    _write()


def set_field(key, value):
    with _lock:
        _state[key] = value
        _write()


def end(summary):
    _state.update({"running": False, "stage": "idle", "detail": summary,
                   "tokens": tokens_snapshot()})
    _write()


def check_stop():
    if STOP_FLAG.exists():
        raise Stopped("stop requested from panel")


# ---------- token metering ----------

def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Los_Angeles")
    except Exception:
        return None


def _clear_limit(data):
    data.pop("limit_hit", None)
    data.pop("limit_reset", None)
    data.pop("limit_hit_at", None)
    data.pop("limit_reset_at", None)
    return data


def _parse_reset_at(reset_text, hit_at=None):
    """Parse '5:10pm' (optionally with tz note) into a unix timestamp."""
    m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", reset_text or "", re.I)
    if not m:
        return None
    hour, minute, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ap == "pm" and hour != 12:
        hour += 12
    if ap == "am" and hour == 12:
        hour = 0
    tz = _tz()
    now = datetime.now(tz) if tz else datetime.now()
    reset_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    hit = None
    if hit_at:
        try:
            hit = datetime.fromtimestamp(hit_at, tz) if tz else datetime.fromtimestamp(hit_at)
        except Exception:
            hit = None
    if hit and reset_dt <= hit:
        reset_dt += timedelta(days=1)
    return reset_dt.timestamp()


def _refresh_limit_state(data):
    """Drop stale Anthropic session-limit flags once the reset time has passed."""
    if not data.get("limit_hit"):
        return data, False
    changed = False
    reset_at = data.get("limit_reset_at")
    if not reset_at:
        reset_at = _parse_reset_at(data.get("limit_reset"), data.get("limit_hit_at"))
        if reset_at:
            data["limit_reset_at"] = reset_at
            changed = True
    now = time.time()
    hit_at = data.get("limit_hit_at") or data.get("window_start") or 0
    if reset_at and now >= reset_at:
        _clear_limit(data)
        return data, True
    # Fallback: don't stick LIMIT forever if we couldn't parse a reset time
    if (not reset_at) and hit_at and now - hit_at > 3 * 60 * 60:
        _clear_limit(data)
        return data, True
    return data, changed


def _load_tokens():
    if TOKENS_FILE.exists():
        try:
            data = json.loads(TOKENS_FILE.read_text())
        except Exception:
            data = None
        if data and time.time() - data.get("window_start", 0) < WINDOW_SECONDS:
            data, changed = _refresh_limit_state(data)
            if changed:
                TOKENS_FILE.write_text(json.dumps(data))
            return data
    return {"window_start": time.time(), "tokens": 0, "calls": 0, "warned": False}


def add_usage(usage):
    """usage: the 'usage' dict from a claude -p JSON envelope.

    Counts input+output only. Cache-write tokens are huge and made the meter
    look like Claude session % — they are not billed the same way, so ignore.
    """
    data = _load_tokens()
    # A successful call means the Anthropic session limit is no longer blocking us
    if data.get("limit_hit"):
        _clear_limit(data)
    data["tokens"] += (usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
    data["calls"] += 1
    budget = config.SESSION_TOKEN_BUDGET
    pct = data["tokens"] / budget if budget else 0
    if pct >= config.TOKEN_WARN_PCT and not data.get("warned"):
        data["warned"] = True
        try:
            subprocess.run(["osascript", "-e",
                            f'display notification "Autopilot used {int(pct * 100)}% of its session token budget" '
                            f'with title "EmailCRM Autopilot" sound name "Basso"'], timeout=10)
        except Exception:
            pass
    TOKENS_FILE.write_text(json.dumps(data))
    return pct


def token_hard_limit():
    """Absolute token count where autopilot LLM calls hard-stop."""
    budget = config.SESSION_TOKEN_BUDGET or 0
    hard = float(getattr(config, "TOKEN_HARD_PCT", 1.0) or 1.0)
    hard = max(0.05, min(1.0, hard))
    return int(budget * hard)


def over_budget():
    """True when autopilot has hit TOKEN_HARD_PCT of SESSION_TOKEN_BUDGET."""
    data = _load_tokens()
    limit = token_hard_limit()
    return bool(limit) and data["tokens"] >= limit


def limit_hit(reset_text):
    """Real Anthropic session limit observed (429). Snap meter to limit state."""
    data = _load_tokens()
    data["limit_hit"] = True
    data["limit_reset"] = reset_text
    data["limit_hit_at"] = time.time()
    reset_at = _parse_reset_at(reset_text, data["limit_hit_at"])
    if reset_at:
        data["limit_reset_at"] = reset_at
    TOKENS_FILE.write_text(json.dumps(data))


def tokens_snapshot():
    data = _load_tokens()
    budget = config.SESSION_TOKEN_BUDGET
    hard = token_hard_limit()
    limited = bool(data.get("limit_hit"))
    hard_pct = float(getattr(config, "TOKEN_HARD_PCT", 1.0) or 1.0) * 100.0
    used_pct = round(100 * data["tokens"] / budget, 1) if budget else 0
    # Cap displayed pct at hard stop once over (unless Anthropic limit latched)
    if not limited and hard and data["tokens"] >= hard:
        used_pct = round(hard_pct, 1)
    return {"used": data["tokens"], "budget": budget, "calls": data["calls"],
            "pct": 100.0 if limited else used_pct,
            "hard_pct": round(hard_pct, 1),
            "hard_limit": hard,
            "limit_hit": limited,
            "limit_reset": data.get("limit_reset"),
            "window_started": datetime.fromtimestamp(data["window_start"]).strftime("%H:%M")}


def budget_pct():
    """Autopilot meter 0–100 of SESSION_TOKEN_BUDGET. 100 if Anthropic limit latched."""
    return float(tokens_snapshot().get("pct") or 0)


def meter_allows(max_pct):
    """True if we still have room under max_pct (0–1), never past TOKEN_HARD_PCT."""
    snap = tokens_snapshot()
    if snap.get("limit_hit") or over_budget():
        return False
    hard = float(getattr(config, "TOKEN_HARD_PCT", 1.0) or 1.0)
    ceiling = min(float(max_pct), hard)
    return budget_pct() < (ceiling * 100.0)
