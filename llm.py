"""claude -p subprocess wrapper.

The LLM gets no Write/Edit tools and no Gmail access, ever. Exa search tools
only when explicitly allowed. Output must be a single JSON object; Python
validates it before anything is acted on.
"""
import json
import os
import re
import subprocess

import config
import status

_calls_made = 0
llm_down = False


class LLMError(Exception):
    pass


def available():
    """False when Claude should not be called (limit, hard cap, or marked down)."""
    global llm_down
    if llm_down:
        return False
    snap = status.tokens_snapshot()
    if snap.get("limit_hit"):
        llm_down = True
        return False
    if status.over_budget():
        llm_down = True
        return False
    return True


def _clean_env():
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # force Pro subscription OAuth
    env["PATH"] = f"{config.HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"
    return env


def _extract_json(text):
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise LLMError(f"no JSON object in model output: {text[:300]!r}")
    return json.loads(m.group(0))


def calls_remaining():
    return max(0, config.LLM_CALL_BUDGET - _calls_made)


def call(prompt, use_exa=False, max_turns=8):
    """Run claude -p, return parsed JSON dict. Raises LLMError."""
    global _calls_made, llm_down
    status.check_stop()
    if not available():
        snap = status.tokens_snapshot()
        if snap.get("limit_hit"):
            reset = snap.get("limit_reset") or "reset"
            raise LLMError(
                f"Claude session limit already latched (resets {reset}); "
                "inbox sync still works, drafts wait until reset")
        if status.over_budget():
            hard = int(getattr(config, "TOKEN_HARD_PCT", 0.60) * 100)
            raise LLMError(
                f"autopilot token cap ({hard}% of budget) reached, LLM stages stopped")
        raise LLMError("LLM marked down for this run")
    if _calls_made >= config.LLM_CALL_BUDGET:
        raise LLMError(f"call budget ({config.LLM_CALL_BUDGET}) exhausted")
    _calls_made += 1

    mcp_config = config.MCP_EXA if use_exa else config.MCP_EMPTY
    cmd = [
        config.CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--strict-mcp-config", "--mcp-config", str(mcp_config),
    ]
    if use_exa:
        cmd += ["--allowedTools", ",".join(config.EXA_TOOLS)]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=config.LLM_TIMEOUT, env=_clean_env(), cwd=str(config.HOME),
        )
    except subprocess.TimeoutExpired:
        raise LLMError(f"claude -p timed out after {config.LLM_TIMEOUT}s")

    # Parse stdout first: plugin SessionEnd hooks can fail and force exit 1
    # even when the model result is perfectly good.
    envelope = None
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        pass

    if envelope is None:
        err = (proc.stderr or proc.stdout or "")[:500]
        if re.search(r"auth|login|credential|API key", err, re.IGNORECASE):
            llm_down = True
            raise LLMError(f"auth failure, skipping all LLM stages this run: {err}")
        raise LLMError(f"claude exited {proc.returncode}, no JSON envelope: {err}")

    if isinstance(envelope.get("usage"), dict):
        status.add_usage(envelope["usage"])
    if envelope.get("is_error"):
        result_text = str(envelope.get("result", ""))
        if envelope.get("api_error_status") == 429 or "session limit" in result_text.lower():
            llm_down = True
            m = re.search(r"resets?\s+([^(·\n]+)", result_text)
            status.limit_hit(m.group(1).strip() if m else "unknown")
            raise LLMError(f"rate/session limit, skipping all LLM stages this run: {result_text[:200]}")
        raise LLMError(f"CLI error result: {result_text[:300]}")
    return _extract_json(envelope.get("result", ""))


def call_with_retry(prompt, use_exa=False, retry_suffix=None, validate=None):
    """One call; retry only on lint/validation failure when meter still has room.

    The second call is a short fix-only prompt (previous JSON + errors), not a
    full replay of the original prompt — that nearly doubled input tokens.
    """
    result = call(prompt, use_exa=use_exa)
    errors = validate(result) if validate else []
    if not errors:
        return result, []
    # Skip expensive second call when we're already tight on budget
    if (not status.meter_allows(config.RETRY_METER_MAX_PCT)
            or calls_remaining() < 1
            or llm_down):
        return result, errors
    header = retry_suffix or (
        "Fix the previous JSON draft. Output ONLY the corrected JSON object. "
        "Problems to fix:"
    )
    prev = json.dumps(result, ensure_ascii=False)
    if len(prev) > 4000:
        prev = prev[:4000] + "…"
    fix_prompt = (
        f"{header}\n- " + "\n- ".join(errors)
        + "\n\nPrevious output:\n" + prev
    )
    # Retries never need Exa — drafting/lint fixes are local.
    result = call(fix_prompt, use_exa=False)
    errors = validate(result) if validate else []
    return result, errors


def calls_made():
    return _calls_made
