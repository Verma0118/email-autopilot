"""Stage 4: prospecting. Research briefs ONLY — never creates drafts."""
import json
import re
from datetime import date

import yaml

import config
import crm
import llm


def _norm(name, company):
    return re.sub(r"[^a-z0-9]", "", (name + company).lower())


def _ledger():
    if config.PROSPECTS_SEEN.exists():
        return json.loads(config.PROSPECTS_SEEN.read_text())
    return {}


def _save_ledger(ledger, dry_run):
    if not dry_run:
        config.PROSPECTS_SEEN.write_text(json.dumps(ledger, indent=1))


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _brief_prompt(candidate, segment_name):
    template = (config.PROMPT_DIR / "prospect_brief.md").read_text()
    for token, value in {
        "<<NAME>>": candidate.get("name", ""),
        "<<ROLE>>": candidate.get("role", ""),
        "<<COMPANY>>": candidate.get("company", ""),
        "<<LINKEDIN>>": candidate.get("linkedin_url", ""),
        "<<SOURCE>>": candidate.get("source_url", ""),
        "<<SEGMENT>>": segment_name,
    }.items():
        template = template.replace(token, str(value))
    return template


def _passes_bar(brief):
    email = brief.get("email") or {}
    return bool(brief.get("role_confirmed")) and email.get("basis") in ("published", "pattern_with_evidence")


def _write_brief(candidate, brief, segment_name, dry_run):
    slug = f"{date.today().isoformat()}-{_slug(candidate['name'])}"
    path = config.QUEUE_PROSPECTS / f"{slug}.md"
    hooks = "\n".join(f"- {h.get('fact')} ({h.get('url')})" for h in brief.get("hooks", []) if isinstance(h, dict))
    email = brief.get("email") or {}
    body = f"""# Prospect Brief: {candidate['name']} — {candidate['company']}
Generated: {date.today().isoformat()} | Segment: {segment_name}

- **Role:** {candidate.get('role')} (confirmed: {brief.get('role_confirmed')}, source: {brief.get('role_source')})
- **LinkedIn:** {candidate.get('linkedin_url')}
- **Suggested type:** {brief.get('suggested_email_type', 'startup_discovery')}
- **Email:** {email.get('address')} (basis: {email.get('basis')})
- **Email evidence:** {', '.join(email.get('evidence_urls', []))}

## Why ICP
{candidate.get('why_icp', '')}

## Company flight-volume signal
{brief.get('company_signal', '')}

## Hooks (citable)
{hooks}

## Next step
Run /email-agent with this brief. Confidence bar already passed; still verify before send.
"""
    if not dry_run:
        path.write_text(body)
    return path


def run(contacts, report, cap, log, dry_run=False):
    r = report.setdefault("prospecting", {"briefs": [], "rejected": [], "errors": []})
    icp = yaml.safe_load(config.ICP_FILE.read_text())
    ledger = _ledger()
    crm_keys = {_norm(c["name"], c.get("company", "")) for c in contacts}
    written = 0

    def consider(candidate, segment_name):
        nonlocal written
        key = _norm(candidate.get("name", ""), candidate.get("company", ""))
        if not key or key in crm_keys or key in ledger:
            return
        try:
            brief = llm.call(_brief_prompt(candidate, segment_name), use_exa=True, max_turns=12)
        except llm.LLMError as e:
            r["errors"].append(f"{candidate.get('name')}: {e}")
            return  # transient: leave un-ledgered so next run retries
        if _passes_bar(brief):
            path = _write_brief(candidate, brief, segment_name, dry_run)
            ledger[key] = f"brief:{path.name}"
            r["briefs"].append(f"{candidate['name']} ({candidate['company']}) -> {path.name}")
            written += 1
        else:
            reason = "role unconfirmed" if not brief.get("role_confirmed") else f"email basis {((brief.get('email') or {}).get('basis'))!r}"
            ledger[key] = f"rejected:{reason}"
            r["rejected"].append(f"{candidate.get('name')} ({candidate.get('company')}): {reason}")
        log({"action": "prospect_considered", "candidate": candidate.get("name"), "outcome": ledger[key]})

    # seeds first
    for seed in icp.get("seed_candidates", []):
        if written >= cap or llm.llm_down:
            break
        consider(seed, seed.get("segment", "seed"))

    # then one discovery call on the rotating segment
    segments = icp.get("segments", [])
    if segments and written < cap and not llm.llm_down:
        seg = segments[date.today().toordinal() % len(segments)]
        template = (config.PROMPT_DIR / "prospect_discovery.md").read_text()
        prompt = template.replace("<<SEGMENT_NAME>>", seg["name"]).replace(
            "<<SEGMENT_BRIEF>>", seg["brief"])
        try:
            found = llm.call(prompt, use_exa=True, max_turns=15)
            for candidate in (found.get("candidates") or [])[:10]:
                if written >= cap or llm.llm_down:
                    break
                consider(candidate, seg["name"])
        except llm.LLMError as e:
            r["errors"].append(f"discovery ({seg['name']}): {e}")

    _save_ledger(ledger, dry_run)
    return r
