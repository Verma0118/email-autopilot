"""Scout Agent: scrape + research new contacts for all three tracks.

Research briefs only (JSON + markdown to queue/prospects/). Never drafts,
never touches Gmail. The Organizer turns passing briefs into approval items.
"""
import json
import re
from datetime import date

import yaml

import config
import crm
import llm
import status


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


def _fill(template, mapping):
    for k, v in mapping.items():
        template = template.replace(k, str(v or ""))
    return template


def _brief_prompt(candidate, track_key, track):
    return _fill((config.PROMPT_DIR / "prospect_brief.md").read_text(), {
        "<<NAME>>": candidate.get("name"),
        "<<ROLE>>": candidate.get("role"),
        "<<COMPANY>>": candidate.get("company"),
        "<<LINKEDIN>>": candidate.get("linkedin_url"),
        "<<SOURCE>>": candidate.get("source_url"),
        "<<SEGMENT>>": f"{track_key} / {candidate.get('segment', '')}",
        "<<TRACK_WHO>>": track.get("who"),
    })


def _passes_bar(brief):
    email = brief.get("email") or {}
    return bool(brief.get("role_confirmed")) and email.get("basis") in ("published", "pattern_with_evidence")


def _write_brief(candidate, brief, track_key, track, dry_run):
    slug = f"{date.today().isoformat()}-{track_key}-{_slug(candidate['name'])}"
    jpath = config.QUEUE_PROSPECTS / f"{slug}.json"
    mpath = config.QUEUE_PROSPECTS / f"{slug}.md"
    record = {"candidate": candidate, "brief": brief, "track": track_key,
              "email_type": track["email_type"], "date": date.today().isoformat(),
              "organized": False}
    hooks = "\n".join(f"- {h.get('fact')} ({h.get('url')})" for h in brief.get("hooks", []) if isinstance(h, dict))
    email = brief.get("email") or {}
    md = f"""# Prospect Brief [{track['label']}]: {candidate['name']} — {candidate['company']}
Generated: {date.today().isoformat()} | Segment: {candidate.get('segment')}

- **Role:** {candidate.get('role')} (confirmed: {brief.get('role_confirmed')}, source: {brief.get('role_source')})
- **LinkedIn:** {candidate.get('linkedin_url')}
- **Email type:** {track['email_type']}
- **Email:** {email.get('address')} (basis: {email.get('basis')})
- **Evidence:** {', '.join(email.get('evidence_urls', []))}

## Why ICP
{candidate.get('why_icp', '')}

## Signal
{brief.get('company_signal', '')}

## Hooks
{hooks}
"""
    if not dry_run:
        jpath.write_text(json.dumps(record, indent=1))
        mpath.write_text(md)
    return jpath


def run(contacts, report, cap_override, log, dry_run=False):
    r = report.setdefault("prospecting", {"briefs": [], "rejected": [], "errors": []})
    icp = yaml.safe_load(config.ICP_FILE.read_text())
    tracks = icp.get("tracks", {})
    ledger = _ledger()
    crm_keys = {_norm(c["name"], c.get("company", "")) for c in contacts}
    written = {k: 0 for k in tracks}

    def consider(candidate, track_key):
        track = tracks[track_key]
        cap = cap_override or track.get("daily_cap", 3)
        if written[track_key] >= cap:
            return
        key = _norm(candidate.get("name", ""), candidate.get("company", ""))
        if not key or key in crm_keys or key in ledger:
            return
        status.check_stop()
        status.update(detail=f"researching prospect: {candidate.get('name')} ({candidate.get('company')})",
                      stream=track["label"])
        try:
            brief = llm.call(_brief_prompt(candidate, track_key, track), use_exa=True, max_turns=12)
        except llm.LLMError as e:
            r["errors"].append(f"{candidate.get('name')}: {e}")
            return  # transient: retry next run
        if _passes_bar(brief):
            path = _write_brief(candidate, brief, track_key, track, dry_run)
            ledger[key] = f"brief:{path.name}"
            written[track_key] += 1
            r["briefs"].append(f"[{track['label']}] {candidate['name']} ({candidate['company']})")
        else:
            reason = ("role unconfirmed" if not brief.get("role_confirmed")
                      else f"email basis {((brief.get('email') or {}).get('basis'))!r}")
            ledger[key] = f"rejected:{reason}"
            r["rejected"].append(f"[{track['label']}] {candidate.get('name')}: {reason}")
        log({"action": "prospect_considered", "candidate": candidate.get("name"),
             "track": track_key, "outcome": ledger.get(key)})

    # seeds first (track-tagged)
    for seed in icp.get("seed_candidates", []):
        if llm.llm_down:
            break
        tk = seed.get("track", "startup_discovery")
        if tk in tracks:
            consider(seed, tk)

    # one discovery call per track per run, rotating that track's segments daily
    discovery_template = (config.PROMPT_DIR / "prospect_discovery.md").read_text()
    for track_key, track in tracks.items():
        if llm.llm_down:
            break
        cap = cap_override or track.get("daily_cap", 3)
        if written[track_key] >= cap:
            continue
        segments = track.get("segments", [])
        if not segments:
            continue
        seg = segments[date.today().toordinal() % len(segments)]
        status.update(detail=f"scraping for new contacts: {seg['name']}", stream=track["label"])
        prompt = _fill(discovery_template, {
            "<<SEGMENT_NAME>>": seg["name"], "<<SEGMENT_BRIEF>>": seg["brief"],
            "<<TRACK_WHO>>": track.get("who"), "<<TRACK_WHO_NOT>>": track.get("who_not"),
        })
        try:
            found = llm.call(prompt, use_exa=True, max_turns=15)
            for candidate in (found.get("candidates") or [])[:10]:
                candidate.setdefault("segment", seg["name"])
                consider(candidate, track_key)
        except llm.LLMError as e:
            r["errors"].append(f"discovery ({track_key}/{seg['name']}): {e}")

    _save_ledger(ledger, dry_run)
    return r
