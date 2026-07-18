"""Deterministic style lint and bounce confidence gate.

The LLM's output is never trusted. Every draft passes these checks before any
Gmail draft is created; every bounce correction passes the gate before use.
"""
import re
import subprocess

CONTRACTIONS = re.compile(
    r"\b(I'm|I've|I'll|I'd|you're|you've|you'll|you'd|we're|we've|we'll|we'd|"
    r"they're|they've|they'll|it's|that's|there's|here's|what's|who's|let's|"
    r"can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|haven't|"
    r"hasn't|hadn't|wouldn't|couldn't|shouldn't)\b",
    re.IGNORECASE,
)

BANNED_PHRASES = [
    "would love to",
    "excited to",
    "passionate about",
    "i hope this email finds you well",
    "reach out",
]


def _strip_html(html):
    html = html.replace("’", "'")  # curly apostrophe -> straight, so contraction lint holds
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def lint_followup(subject, body_html, expected_subject, max_words=100):
    """Return a list of violations. Empty list = clean."""
    errors = []
    text = _strip_html(body_html)

    if subject != expected_subject:
        errors.append(f'subject must be exactly "{expected_subject}", got "{subject}"')
    if "—" in body_html or "–" in body_html:
        errors.append("em/en dash found; rewrite the sentence")
    if re.search(r"\S\s-\s\S", text):
        errors.append("hyphen used as clause connector")
    m = CONTRACTIONS.search(text)
    if m:
        errors.append(f'contraction found: "{m.group(0)}"')
    low = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in low:
            errors.append(f'banned phrase: "{phrase}"')
    if ";" in text:
        errors.append("semicolon found (em dash substitute)")
    wc = len(text.split())
    if wc > max_words:
        errors.append(f"body is {wc} words, max {max_words}")
    if wc < 25:
        errors.append(f"body is {wc} words, suspiciously short")
    if 'href="https://' not in body_html:
        errors.append('body must contain an <a href="https://..."> anchor (calendar link)')
    if re.search(r"<(li|ul|ol|b|strong)\b", body_html, re.IGNORECASE):
        errors.append("no bullets or bold inside email body")
    sentences = re.split(r"(?<=[.!?])\s+", text)
    run = 0
    for s in sentences:
        if s.strip().startswith("I "):
            run += 1
            if run > 2:
                errors.append('more than 2 consecutive sentences start with "I"')
                break
        else:
            run = 0
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", body_html):
        errors.append("emoji found")
    return errors


OUTREACH_WORD_CAPS = {"startup_discovery": 180, "cold_outreach": 340,
                      "networking_warm": 390, "nobe_pd_outreach": 230}

# "Good Morning Andrew, Hope your week is going well!" (human warm open)
WARM_OUTREACH_OPENER = re.compile(
    r"^good\s+(morning|afternoon|evening)\s+[a-z][\w'.-]*,?\s+"
    r"hope\s+(your|the)\s+(day|week)\s+(is\s+going|has\s+been)\s+well!?",
    re.IGNORECASE,
)


def lint_outreach(subject, body_html, expected_subject, email_type):
    """First-touch outreach lint. Reuses the follow-up checks with per-type caps."""
    errors = lint_followup(subject, body_html, expected_subject,
                           max_words=OUTREACH_WORD_CAPS.get(email_type, 340))
    plain = _strip_html(body_html)
    text = plain.lower()
    if not WARM_OUTREACH_OPENER.search(plain):
        errors.append(
            'missing warm opener: start with "Good Morning/Afternoon [Name], '
            'Hope your week/day is going well!"'
        )
    if re.match(r"^(hi|hello|hey)\s+", text):
        errors.append('do not open with bare "Hi/Hello"; use Good Morning/Afternoon')
    if re.match(r"^my name is\b", text):
        errors.append('do not jump into "My name is…"; put the warm greeting first')
    if email_type == "startup_discovery":
        if "not pitching anything" not in text:
            errors.append('missing mandatory "Not pitching anything..." sentence')
        for banned in ("validate", "startup", "co-founder", "volant"):
            if banned in text:
                errors.append(f'startup_discovery may not contain "{banned}"')
    if email_type == "nobe_pd_outreach" and "12-week project from september to december" not in text:
        errors.append("missing mandatory NOBE 12-week pitch paragraph")
    # follow-up lint flags sub-25-word bodies; outreach must be substantial anyway
    return errors


def domain_has_mx(domain):
    try:
        out = subprocess.run(
            ["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=15
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


def bounce_gate(result, old_email):
    """result: parsed JSON from the bounce research call.
    Returns (ok, reason)."""
    corrected = (result.get("corrected_email") or "").strip().lower()
    if not corrected or "@" not in corrected:
        return False, "no corrected email returned"
    if corrected == old_email.lower():
        return False, "corrected address identical to bounced address"
    if result.get("confidence") != "high":
        return False, f"confidence is {result.get('confidence')!r}, need high"
    evidence = [e for e in result.get("evidence", []) if isinstance(e, dict) and e.get("url")]
    if not evidence:
        return False, "no evidence URLs"
    domain = corrected.split("@", 1)[1]
    if not domain_has_mx(domain):
        return False, f"domain {domain} has no MX records"
    return True, "ok"
