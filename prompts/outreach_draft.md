Draft a first-touch outreach email for Aarav Verma using this researched brief. The email goes to an approval queue; write the final send-ready text.

## Sender identity
Aarav Verma, Sophomore, Aerospace Engineering major with Computer Science minor, University of Illinois Urbana-Champaign. Involvements available (pick per rules below, never all): Illinois Space Society (Space Shot structural engineer), GHOST Electric Motorcycles, NOBE (Project Manager).

## Target
- Name: <<NAME>>
- Role: <<ROLE>>
- Company: <<COMPANY>>
- Track: <<TRACK>> (email_type: <<EMAIL_TYPE>>)
- Why ICP: <<WHY_ICP>>
- Company signal: <<SIGNAL>>
- Citable hooks (use the strongest ONE, phrased conversationally):
<<HOOKS>>

## Subject (EXACT, do not vary)
<<SUBJECT>>

## Track rules
IF email_type == startup_discovery:
- Max 150 words. Intro: "My name is Aarav Verma, a Sophomore majoring in Aerospace Engineering at the University of Illinois Urbana-Champaign, and my classmate Rushil Patil studies Mechanical Engineering there as well."
- "We have been exploring" framing; observation "I noticed [hook]", questions shift to "we wanted to ask"
- MANDATORY sentence: "Not pitching anything, we are just trying to understand the problem before assuming we know it."
- Never say: validate, startup, co-founder, Volant. No resume, no portfolio.
- Sign "Thanks," then "Aarav Verma, Rushil Patil"

IF email_type == cold_outreach (internship track):
- 250-300 words, max 325. Opener: "Good [Morning/Afternoon] [Name]!" plus one warm line.
- Intro: name, year, school, major, 1-2 involvements MATCHED to their domain (aerospace/structures: Illinois Space Society; EV/propulsion/hardware: GHOST; eVTOL: both).
- Hook paragraph: the citable observation about THEM.
- Company paragraph: why THIS company, 2-3 specific sentences beyond the homepage.
- Ask: 20-30 minute chat. Mention: "I have attached my resume, and my portfolio is at <a href="https://verma0118.github.io">verma0118.github.io</a>." NEVER describe what the resume covers.
- Sign "Thanks," then "Aarav Verma"

IF email_type == nobe_pd_outreach:
- Max 200 words. Intro as Project Manager at NOBE, Sophomore in Aerospace Engineering at UIUC. NO GHOST, NO ISS, no resume, no portfolio.
- Hook: their specific product or gap plus a concrete CAD deliverable NOBE students could build.
- MANDATORY verbatim paragraph: "We propose a 12-week project from September to December, with an optional extension into the following semester. We only ask for coordination with you throughout the project to ensure high-quality outcomes. Our members gain invaluable experience, and you benefit from innovative ideas and dedicated student teams."
- Include: "I have also attached a brief overview of NOBE for your reference."
- Closing line: "Looking forward to hearing from you!" Signature includes "Project Manager, NOBE at UIUC".
- Champaign-area companies: mention the physical proximity.

## CTA
One CTA only. Calendar link to use (as <a href>Calendar Invite</a>): <<CALENDAR_URL>>
If it says NONE_FOUND, offer to send a calendar invite instead. Never invent a URL.

## Hard constraints (violations = automatic rejection)
NO em/en dashes. NO hyphen as clause connector. NO contractions. NO semicolons. Max 2 consecutive sentences starting with "I". No bullets or bold in the body. No emojis. Banned: "would love to", "excited to", "passionate about", "reach out", "I hope this email finds you well". Body is simple HTML paragraphs.

## Output
Output ONLY one JSON object:
{"subject": "<<SUBJECT>>", "body_html": "<p>...</p>", "hook_used": "one line: which hook you used"}
