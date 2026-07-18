Draft a reply for Aarav Verma (UIUC Aerospace sophomore). Decide if he owes a reply; if yes, draft it.

Today: <<TODAY>>
Contact: <<NAME>> · <<COMPANY>> · <<ROLE>>

Thread (oldest first; FROM_US / FROM_THEM):
<<THREAD>>

reply_needed true if they asked something, proposed times, ball is in Aarav's court, or a promised date passed with silence.
reply_needed false if meeting is locked, thread concluded, we spoke last recently, or we owe them later (put that date in we_owe_later).

When drafting: subject EXACTLY "Re: " + original subject. Match their length ±20%. First-name greeting. End "Thanks,\nAarav". One job only. Reuse any calendar URL from the thread as <a href>; never invent URLs. No em dashes, contractions, semicolons, or "would love to"/"excited to"/"passionate about"/"reach out"/"I hope this email finds you well". Simple HTML <p> tags.

Output ONLY JSON:
{"reply_needed": true, "why": "one sentence", "subject": "Re: ...", "body_html": "<p>...</p>"}
or
{"reply_needed": false, "why": "one sentence", "we_owe_later": "2026-08-01: email Taras in August" or null}
