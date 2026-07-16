Research this outreach candidate thoroughly using the exa search tools. Two UIUC students will send a short research-framed coffee chat request; your job is verification and hooks, not drafting.

## Candidate
- Name: <<NAME>>
- Claimed role: <<ROLE>>
- Company: <<COMPANY>>
- LinkedIn: <<LINKEDIN>>
- Found via: <<SOURCE>> (segment: <<SEGMENT>>)

## Verify (strict)
1. CURRENT role: confirm with a source dated within ~12 months. If you cannot confirm they are currently in this role, role_confirmed = false.
2. Email address: find a PUBLISHED address for them, or derive from a domain pattern PROVEN by another published employee address (cite it). Guessing a pattern with no evidence = basis "guess".
3. Flight volume: find concrete evidence the org flies at high frequency (daily ops, fleet size, dock programs, pilot counts).
4. Hooks: 2-3 SPECIFIC citable facts about this person or their program (a waiver they got, a program they built, a talk, a milestone). Generic titles are not hooks.

## Output
Output ONLY one JSON object:
{"role_confirmed": true, "role_source": "https://... (dated ...)", "company_signal": "one or two sentences on flight volume evidence", "email": {"address": "x@y.com", "basis": "published|pattern_with_evidence|guess", "evidence_urls": ["https://..."]}, "hooks": [{"fact": "", "url": ""}], "suggested_email_type": "startup_discovery"}
