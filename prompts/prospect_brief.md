Research this outreach candidate thoroughly using the exa search tools. Your job is verification and hooks, not drafting. Target profile for this track: <<TRACK_WHO>>

## Candidate
- Name: <<NAME>>
- Claimed role: <<ROLE>>
- Company: <<COMPANY>>
- LinkedIn: <<LINKEDIN>>
- Found via: <<SOURCE>> (segment: <<SEGMENT>>)
- Default email_type for this track: <<DEFAULT_EMAIL_TYPE>>

## Verify (strict)
<<VERIFY_RULES>>

## Output
Output ONLY one JSON object:
{"role_confirmed": true, "role_source": "https://... (dated ...)", "company_signal": "one or two sentences of track-relevant evidence", "email": {"address": "x@y.com", "basis": "published|pattern_with_evidence|guess", "evidence_urls": ["https://..."]}, "hooks": [{"fact": "", "url": ""}], "is_uiuc_alum": null, "suggested_email_type": "<<DEFAULT_EMAIL_TYPE>>"}
