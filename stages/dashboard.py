"""Render ~/Desktop/EmailCRM/dashboard.html — self-contained status page.

Regenerated on every run. Single file, no external assets, vanilla HTML/CSS,
native <details> only. Light/dark via prefers-color-scheme.
"""
import html
import re
from datetime import date, datetime

import config
import crm

CSS = """
:root {
  --bg:#fafafa; --card:#ffffff; --card2:#f4f4f5; --ink:#18181b; --ink2:#71717a;
  --line:rgba(24,24,27,.09); --line2:rgba(24,24,27,.16);
  --accent:#5753c6; --accent-soft:rgba(87,83,198,.09);
  --good:#177245; --good-bg:rgba(23,114,69,.08); --warn:#96650b; --warn-bg:rgba(150,101,11,.09);
  --bad:#c22f36; --bad-bg:rgba(194,47,54,.08);
  --shadow:0 1px 1px rgba(24,24,27,.03), 0 2px 6px rgba(24,24,27,.04);
  --ease:cubic-bezier(0.23, 1, 0.32, 1);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#0e0e10; --card:#17171a; --card2:#1e1e22; --ink:#ededef; --ink2:#9d9da6;
    --line:rgba(237,237,239,.08); --line2:rgba(237,237,239,.16);
    --accent:#918fe8; --accent-soft:rgba(145,143,232,.12);
    --good:#41c780; --good-bg:rgba(65,199,128,.1); --warn:#d9a636; --warn-bg:rgba(217,166,54,.1);
    --bad:#f0555d; --bad-bg:rgba(240,85,93,.1);
    --shadow:none;
  }
}
* { box-sizing:border-box; margin:0; }
body { background:var(--bg); color:var(--ink);
  font:15px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
  -webkit-font-smoothing:antialiased;
  max-width:880px; margin:0 auto; padding:36px 24px 80px; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; text-underline-offset:3px; }
a:focus-visible, summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; border-radius:6px; }

section, header.top, p.meta { opacity:0; transform:translateY(6px);
  animation:rise 400ms var(--ease) forwards; }
header.top { animation-delay:0ms; } p.meta { animation-delay:30ms; }
section:nth-of-type(1) { animation-delay:60ms; } section:nth-of-type(2) { animation-delay:100ms; }
section:nth-of-type(3) { animation-delay:140ms; } section:nth-of-type(4) { animation-delay:180ms; }
section:nth-of-type(5) { animation-delay:220ms; } section:nth-of-type(6) { animation-delay:260ms; }
@keyframes rise { to { opacity:1; transform:translateY(0); } }
@media (prefers-reduced-motion: reduce) {
  section, header.top, p.meta { animation:fade 200ms ease forwards; transform:none; }
  @keyframes fade { to { opacity:1; } }
  .btn, summary::before { transition:none !important; }
}

header.top { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:4px; }
h1 { font-size:1.3rem; font-weight:650; letter-spacing:-.02em; }
.pill { display:inline-flex; align-items:center; gap:6px; font-size:.78rem; font-weight:600;
  padding:4px 11px; border-radius:999px; }
.pill svg { flex:none; }
.pill.ok { color:var(--good); background:var(--good-bg); }
.pill.err { color:var(--bad); background:var(--bad-bg); }
.meta { color:var(--ink2); font-size:.82rem; margin-bottom:28px; }

.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; }
.tile { background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:15px 17px 13px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:1px; }
.tile .n { font-size:1.75rem; font-weight:700; font-variant-numeric:tabular-nums; letter-spacing:-.03em; }
.tile .l { color:var(--ink2); font-size:.76rem; line-height:1.4; letter-spacing:.005em; }
.tile.pri { background:var(--accent-soft); border-color:transparent; }
.tile.pri .n { color:var(--accent); }

h2 { display:flex; align-items:center; gap:8px; font-size:.78rem; margin:36px 0 10px;
  color:var(--ink2); text-transform:uppercase; letter-spacing:.07em; font-weight:600; }
.count { color:var(--ink2); background:var(--card2); border-radius:999px;
  font-size:.72rem; padding:1px 8px; font-variant-numeric:tabular-nums; font-weight:600; }

ul.list { list-style:none; display:flex; flex-direction:column; gap:8px; padding:0; }
.item { background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:12px 15px; box-shadow:var(--shadow); overflow-wrap:anywhere; }
.item .head { display:flex; align-items:flex-start; gap:10px; }
.item .head svg { flex:none; margin-top:2px; width:16px; height:16px; }
.item.good .head svg { color:var(--good); }
.item.warn .head svg { color:var(--warn); }
.item.bad  .head svg { color:var(--bad); }
.item .txt { flex:1; font-size:.9rem; color:var(--ink); }

.btn { display:inline-flex; align-items:center; gap:6px; margin-top:9px; margin-right:8px;
  font-size:.82rem; font-weight:600; text-decoration:none; color:var(--ink);
  border:1px solid var(--line2); border-radius:9px; padding:6px 12px; min-height:32px;
  cursor:pointer; background:var(--card);
  transition:border-color 200ms var(--ease), background-color 200ms var(--ease), transform 160ms var(--ease); }
.btn:hover { border-color:var(--ink2); text-decoration:none; }
.btn:active { transform:scale(0.97); }
.btn svg { color:var(--ink2); }

details { margin-top:8px; }
summary { display:inline-flex; align-items:center; gap:5px; cursor:pointer; color:var(--ink2);
  font-size:.82rem; font-weight:600; padding:5px 2px; user-select:none; list-style:none;
  transition:color 200ms var(--ease); }
summary::-webkit-details-marker { display:none; }
summary::before { content:""; width:12px; height:12px; flex:none;
  background:currentColor; transition:transform 200ms var(--ease);
  -webkit-mask:url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>') center/contain no-repeat;
  mask:url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>') center/contain no-repeat; }
details[open] summary::before { transform:rotate(90deg); }
summary:hover { color:var(--ink); }
blockquote { border-left:2px solid var(--line2); background:var(--card2); border-radius:0 10px 10px 0;
  padding:10px 14px; margin-top:8px; color:var(--ink2); font-size:.88rem; line-height:1.6; max-width:66ch; }
.empty { color:var(--ink2); font-size:.88rem;
  background:transparent; border:1px dashed var(--line2); border-radius:12px; padding:11px 15px; }
footer { margin-top:44px; color:var(--ink2); font-size:.8rem;
  border-top:1px solid var(--line); padding-top:16px; line-height:1.9; }
"""

# Lucide-style inline SVG icons (stroke, 24 viewBox, sized 18)
_I = {
    "check": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
    "alert": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
    "x": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',
    "mail": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>',
    "user": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    "zap": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>',
    "search": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
    "bug": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m8 2 1.88 1.88"/><path d="M14.12 3.88 16 2"/><path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/><path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M6 13H2"/><path d="M3 21c0-2.1 1.7-3.9 3.8-4"/><path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/><path d="M22 13h-4"/><path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/></svg>',
}

DRAFT_LINK_RE = re.compile(r"link: (https://mail\.google\.com/[^\s<\"]+)")


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _card(entry, tone, icon):
    body = None
    text = entry
    if "\n  BODY: " in entry:
        text, body = entry.split("\n  BODY: ", 1)
    link = None
    m = DRAFT_LINK_RE.search(text)
    if m:
        link = m.group(1)
        text = DRAFT_LINK_RE.sub("", text).strip()
    out = [f'<li class="item {tone}"><div class="head">{_I[icon]}<p class="txt">{_esc(text)}</p></div>']
    if link:
        out.append(f'<a class="btn" href="{_esc(link)}">{_I["mail"]}Open draft in Gmail</a>')
    if body:
        out.append(f'<details><summary>Read draft body</summary><blockquote>{_esc(body)}</blockquote></details>')
    out.append("</li>")
    return "".join(out)


def _sec(title, icon, entries, tone, item_icon, empty):
    n = len(entries or [])
    rows = ("".join(_card(e, tone, item_icon) for e in entries)
            if entries else f'<p class="empty">{empty}</p>')
    body = f'<ul class="list">{rows}</ul>' if entries else rows
    return (f'<section aria-label="{_esc(title)}"><h2>{_I[icon]}{_esc(title)}'
            f'<span class="count">{n}</span></h2>{body}</section>')


def render(contacts, report, llm_calls, dry_run=False):
    sync = report.get("inbox_sync", {})
    nu = report.get("reply_nudges", {})
    fu = report.get("followups", {})
    br = report.get("bounce_retry", {})
    pr = report.get("prospecting", {})
    counts = crm.counts(contacts)
    backlog = len(crm.followup_candidates(contacts))
    briefs_queued = len(list(config.QUEUE_PROSPECTS.glob("*.md")))
    drafts_today = nu.get("drafted", []) + fu.get("drafted", [])
    errors = (sync.get("errors", []) + nu.get("errors", []) + fu.get("errors", [])
              + br.get("errors", []) + pr.get("errors", []) + report.get("fatal", []))
    needs_you = (
        [f"Reply received. Respond: {x}" for x in sync.get("replies", [])]
        + [f"You owe them contact later. Calendar it: {x}" for x in nu.get("we_owe", [])]
        + [f"Verified address found, send manually: {x}" for x in br.get("manual", [])]
        + [f"Thread ambiguous, check manually: {x}" for x in sync.get("backfill_ambiguous", [])]
    )
    bounce_rows = ([f"Fixed, corrected draft in Gmail: {x}" for x in br.get("fixed", [])]
                   + [f"No confident fix, dead: {x}" for x in br.get("dead", [])])
    now = datetime.now().strftime("%A %b %d, %I:%M %p")
    ok = not errors
    status_pill = (f'<span class="pill ok">{_I["check"]}All clear</span>' if ok
                   else f'<span class="pill err">{_I["alert"]}{len(errors)} error{"s" if len(errors) != 1 else ""}</span>')

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EmailCRM Autopilot</title><style>{CSS}</style></head>
<body>
<header class="top">
  <h1>EmailCRM Autopilot</h1>
  {status_pill}
</header>
<p class="meta">Last run {now}{' · DRY RUN' if dry_run else ''} · runs daily 7:04 AM · {llm_calls} LLM calls this run · drafts only, never sends</p>

<section aria-label="Pipeline totals" class="tiles">
  <div class="tile pri"><span class="n">{len(needs_you)}</span><span class="l">items need you</span></div>
  <div class="tile"><span class="n">{len(drafts_today)}</span><span class="l">drafts created today</span></div>
  <div class="tile"><span class="n">{counts.get('replied', 0) + counts.get('converted', 0)}</span><span class="l">open conversations</span></div>
  <div class="tile"><span class="n">{counts.get('bounced', 0)}</span><span class="l">bounces unresolved</span></div>
  <div class="tile"><span class="n">{briefs_queued}</span><span class="l">prospect briefs queued</span></div>
  <div class="tile"><span class="n">{backlog}</span><span class="l">cold backlog (paused)</span></div>
</section>

{_sec("Needs you", "user", needs_you, "warn", "alert", "Nothing needs you right now.")}
{_sec("Drafts waiting in Gmail — review, then send", "mail", drafts_today, "good", "check", "No drafts created today.")}
{_sec("Bounce handling", "zap", bounce_rows, "warn", "alert", "No bounce activity today.")}
{_sec("New prospect briefs", "search", pr.get("briefs", []), "good", "check", "No new briefs today.")}
{_sec("Errors", "bug", errors, "bad", "x", "No errors.")}

<footer>
  Status counts: {_esc(counts)}<br>
  <a href="file://{config.DIGEST_DIR}/{date.today().isoformat()}.md">Today's markdown digest</a> ·
  <a href="file://{config.QUEUE_PROSPECTS}">Prospect brief folder</a> ·
  <a href="file://{config.LOG_DIR}">Run logs</a>
</footer>
</body></html>"""

    path = config.ROOT / "dashboard.html"
    path.write_text(page)
    return path
