"""Live run status + stop flag + token metering (rolling 5h window)."""
import json
import os
import subprocess
import threading
import time
from datetime import datetime

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

def _load_tokens():
    if TOKENS_FILE.exists():
        data = json.loads(TOKENS_FILE.read_text())
        if time.time() - data.get("window_start", 0) < WINDOW_SECONDS:
            return data
    return {"window_start": time.time(), "tokens": 0, "calls": 0, "warned": False}


def add_usage(usage):
    """usage: the 'usage' dict from a claude -p JSON envelope."""
    data = _load_tokens()
    data["tokens"] += (usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                       + usage.get("cache_creation_input_tokens", 0))
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


def over_budget():
    data = _load_tokens()
    return config.SESSION_TOKEN_BUDGET and data["tokens"] >= config.SESSION_TOKEN_BUDGET


def limit_hit(reset_text):
    """Real Anthropic session limit observed (429). Snap meter to limit state."""
    data = _load_tokens()
    data["limit_hit"] = True
    data["limit_reset"] = reset_text
    TOKENS_FILE.write_text(json.dumps(data))


def tokens_snapshot():
    data = _load_tokens()
    budget = config.SESSION_TOKEN_BUDGET
    return {"used": data["tokens"], "budget": budget, "calls": data["calls"],
            "pct": 100.0 if data.get("limit_hit") else (round(100 * data["tokens"] / budget, 1) if budget else 0),
            "limit_hit": data.get("limit_hit", False),
            "limit_reset": data.get("limit_reset"),
            "window_started": datetime.fromtimestamp(data["window_start"]).strftime("%H:%M")}
