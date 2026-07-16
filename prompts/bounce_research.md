An outreach email to this person hard-bounced (SMTP 550, address not found). Find their correct current email address using the exa search tools available to you.

## Contact
- Name: <<NAME>>
- Company: <<COMPANY>>
- Role: <<ROLE>>
- Bounced address: <<OLD_EMAIL>>
- LinkedIn: <<LINKEDIN>>

## Method
1. Determine the company's real email domain (watch for hyphenation, e.g. american-autonomy.com vs americanautonomy.com, and recent rebrands/acquisitions).
2. Find the company's verified email PATTERN from published addresses: press contacts, team pages, conference speaker listings, filings, published papers, media kits.
3. Verify the person still works there (recent sources only). If they left, say so.
4. Construct the corrected address from the verified pattern.

## Confidence rules
- "high" ONLY if: (a) you found at least one real published employee/press address on the same domain demonstrating the pattern, AND (b) the person verifiably still works there. Cite URLs.
- "medium" if pattern inferred but no published example, or employment unverified.
- "low" if guessing. Never inflate confidence: a wrong high-confidence answer creates a bad draft.

## Output
Output ONLY one JSON object:
{"corrected_email": "first.last@domain.com", "confidence": "high|medium|low", "pattern": "first.last@domain.com", "still_at_company": true, "evidence": [{"url": "https://...", "quote": "the exact text showing a published address or employment proof"}], "reasoning": "two sentences max"}
