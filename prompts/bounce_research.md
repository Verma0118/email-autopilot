An outreach email hard-bounced (SMTP 550). Find the correct current email with exa tools.

Contact: <<NAME>> · <<COMPANY>> · <<ROLE>>
Bounced: <<OLD_EMAIL>> · LinkedIn: <<LINKEDIN>>

1. Confirm company email domain (hyphenation, rebrands).
2. Find verified email PATTERN from published addresses.
3. Confirm they still work there. If not, say so.
4. Build corrected address from the verified pattern.

Confidence "high" only with a published same-domain example AND verified employment. "medium" if pattern inferred or employment soft. "low" if guessing. Never inflate.

Output ONLY JSON:
{"corrected_email": "first.last@domain.com", "confidence": "high|medium|low", "pattern": "first.last@domain.com", "still_at_company": true, "evidence": [{"url": "https://...", "quote": "short quote"}], "reasoning": "two sentences max"}
