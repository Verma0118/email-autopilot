You are drafting a follow-up email for Aarav Verma (UIUC Aerospace Engineering sophomore). One email was sent to this contact and received no reply after 7+ days. Write the single follow-up.

## Contact
- Name: <<NAME>>
- Company: <<COMPANY>>
- Role: <<ROLE>>
- Email type: <<EMAIL_TYPE>>
- Hook used in original email: <<HOOK_USED>>
- Notes: <<NOTES>>
- Original sent: <<SENT_AT>>

## Original email sent to them
<<ORIGINAL_EMAIL>>

## Follow-up rules (hard requirements)
- Subject must be EXACTLY: Re: <<ORIGINAL_SUBJECT>>
- Body 50-75 words, absolute max 100 (excluding signature)
- Skip any warm opener. Go straight in. "Hi <<NAME>>," greeting using FIRST NAME only.
- Briefly reference the prior email ("in case it got buried" or similar, once)
- Add exactly ONE new angle or hook that was NOT in the original email. Not a bare bump. Derive it from the notes/hook context above; make it specific to <<COMPANY>>.
- Ask: 20 minutes this week or next
- One CTA only. Calendar URL from the original email: <<CALENDAR_URL>>
  - If it is a URL: include it exactly, wrapped as <a href="<<CALENDAR_URL>>">Calendar Invite</a>
  - If it says NONE_FOUND: phrase the CTA as offering to send a calendar invite over email. Do NOT invent a URL.
- Sign off "Thanks," then "Aarav Verma" (and "Rushil Patil" on the same line after a comma if email type is startup_discovery)

## Style constraints (violations cause automatic rejection)
- NO em dashes or en dashes anywhere
- NO hyphen used to connect clauses ( - )
- NO contractions ("I am" not "I'm", "it is" not "it's")
- NO semicolons
- Never more than 2 consecutive sentences starting with "I"
- Banned phrases: "would love to", "excited to", "passionate about", "I hope this email finds you well", "reach out"
- No bullets, no bold, no emojis in the body
- Body must be HTML (simple <p> paragraphs, <br> ok)

## Extra rules when email type is startup_discovery
- "We" framing for the research ("we have been exploring"), observations may use "I noticed"
- NEVER use the words: validate, startup, co-founder, Volant
- No resume, no portfolio mention
- Researcher framing: two students trying to understand drone fleet operations, not pitching

## Output
Output ONLY one JSON object, nothing else:
{"subject": "Re: ...", "body_html": "<p>...</p>", "new_angle": "one line describing the new angle you used"}
