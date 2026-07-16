You are analyzing an email thread for Aarav Verma (UIUC student, drone fleet operations research outreach). This contact REPLIED at some point. Decide whether a polite nudge is appropriate today, and if so draft it.

Today's date: <<TODAY>>

## Contact
- Name: <<NAME>>
- Company: <<COMPANY>>
- Role: <<ROLE>>

## Full thread (oldest first, each message marked FROM_US or FROM_THEM)
<<THREAD>>

## Decision rules (strict)
Nudge is appropriate ONLY if ALL hold:
1. Their LAST substantive message promised future contact or scheduling (e.g. "week of July 13th works", "I will get back to you", "not available next week but after that") and gave no concrete locked meeting time, OR a promised/agreed timeframe has now clearly passed with silence.
2. That promised timeframe has PASSED as of today. A promise like "email me in August" means WE owe the email later: nudge_appropriate = false, note the date.
3. No meeting is already locked for a future date.
4. We were not the last to write within the past 5 days (do not double-bump).

If a meeting/call already happened or is scheduled in the future, nudge_appropriate = false.

## Draft rules (only when appropriate)
- Stay in thread. Subject EXACTLY "Re: " + the original thread subject.
- reply_to_thread style: short (40-90 words), first name greeting ("Hi John,"), match their casual/formal register, no signature block beyond "Thanks,\nAarav"
- One job: gently surface the promise and offer 2-3 concrete windows this week or a calendar link IF one appeared earlier in the thread (reuse exact URL, never invent one)
- No re-pitch, no new hooks, no guilt
- NO em dashes, NO contractions, NO semicolons, no banned phrases ("would love to", "excited to", "passionate about", "reach out", "I hope this email finds you well")
- Body as simple HTML paragraphs

## Output
Output ONLY one JSON object:
{"nudge_appropriate": true, "promised_date_passed": "what was promised and when", "we_owe_later": null, "subject": "Re: ...", "body_html": "<p>...</p>", "reasoning": "one sentence"}
If not appropriate: {"nudge_appropriate": false, "we_owe_later": "2026-08-01: Taras asked for an email in August" or null, "reasoning": "one sentence"}
