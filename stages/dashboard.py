"""Render ~/Desktop/EmailCRM/dashboard.html — self-contained status page.

Regenerated on every run. Single file, vanilla HTML/CSS, native <details>.
Light/dark via prefers-color-scheme. Fonts load from Google when online.
"""
import hashlib
import html
import json
import re
from datetime import date, datetime

import config
import crm
import gmail
import queue_store

CSS = """
:root {
  --bg0:#f3f6f4; --bg1:#e8efeb; --surface:#fbfcfb; --surface2:#f0f4f1;
  --ink:#14201a; --ink2:#5c6b63; --ink3:#8a968f;
  --line:rgba(20,32,26,.09); --line2:rgba(20,32,26,.16);
  --accent:#0f6e56; --accent-soft:rgba(15,110,86,.1);
  --good:#177245; --good-bg:rgba(23,114,69,.1);
  --warn:#9a6700; --warn-bg:rgba(154,103,0,.1);
  --bad:#b42318; --bad-bg:rgba(180,35,24,.09);
  --ease:cubic-bezier(0.23, 1, 0.32, 1);
  --font:"Figtree", "Segoe UI", sans-serif;
  --display:"Fraunces", Georgia, serif;
  --radius:14px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg0:#0c1210; --bg1:#141c18; --surface:#151c19; --surface2:#1c2521;
    --ink:#e8eee9; --ink2:#9aaba2; --ink3:#6d7c74;
    --line:rgba(232,238,233,.08); --line2:rgba(232,238,233,.14);
    --accent:#3dba8f; --accent-soft:rgba(61,186,143,.14);
    --good:#3ecf8e; --good-bg:rgba(62,207,142,.12);
    --warn:#e8b339; --warn-bg:rgba(232,179,57,.12);
    --bad:#f07178; --bad-bg:rgba(240,113,120,.12);
  }
}
* { box-sizing:border-box; margin:0; }
body {
  background:
    radial-gradient(1100px 480px at 8% -8%, rgba(15,110,86,.09), transparent 55%),
    radial-gradient(800px 380px at 100% 0%, rgba(20,32,26,.04), transparent 50%),
    linear-gradient(180deg, var(--bg0), var(--bg1));
  color:var(--ink);
  font:15px/1.55 var(--font);
  font-weight:450;
  -webkit-font-smoothing:antialiased;
  max-width:880px; margin:0 auto; padding:36px 24px 80px;
}
@media (prefers-color-scheme: dark) {
  body {
    background:
      radial-gradient(1000px 460px at 8% -8%, rgba(61,186,143,.12), transparent 55%),
      radial-gradient(720px 360px at 100% 0%, rgba(61,186,143,.05), transparent 45%),
      linear-gradient(180deg, var(--bg0), var(--bg1));
  }
}
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; text-underline-offset:3px; }
a:focus-visible, summary:focus-visible {
  outline:2px solid var(--accent); outline-offset:2px; border-radius:6px;
}

.rise { opacity:0; transform:translateY(6px); animation:rise 400ms var(--ease) forwards; }
header.top { animation-delay:0ms; }
.meta { animation-delay:40ms; }
.priority { animation-delay:70ms; }
.tiles { animation-delay:110ms; }
section:nth-of-type(1) { animation-delay:150ms; }
section:nth-of-type(2) { animation-delay:190ms; }
section:nth-of-type(3) { animation-delay:230ms; }
section:nth-of-type(4) { animation-delay:270ms; }
section:nth-of-type(5) { animation-delay:310ms; }
@keyframes rise { to { opacity:1; transform:translateY(0); } }
@media (prefers-reduced-motion: reduce) {
  .rise { animation:fade 200ms ease forwards; transform:none; }
  @keyframes fade { to { opacity:1; } }
  .btn, summary::before { transition:none !important; }
}

header.top {
  display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:6px;
}
h1 {
  font-family:var(--display); font-size:1.55rem; font-weight:550;
  letter-spacing:-.025em; line-height:1.15;
}
.pill {
  display:inline-flex; align-items:center; gap:6px; font-size:.78rem; font-weight:650;
  padding:5px 12px; border-radius:999px;
}
.pill svg { flex:none; }
.pill.ok { color:var(--good); background:var(--good-bg); }
.pill.err { color:var(--bad); background:var(--bad-bg); }
.meta { color:var(--ink2); font-size:.84rem; margin-bottom:22px; }

.priority {
  background:var(--accent-soft); border:1px solid transparent;
  border-radius:calc(var(--radius) + 2px); padding:18px 20px; margin-bottom:16px;
}
.priority h2 {
  margin:0 0 10px; font-family:var(--display); font-size:1.15rem;
  font-weight:550; letter-spacing:-.02em; color:var(--ink);
  text-transform:none; display:flex; align-items:center; gap:8px;
}
.priority .count {
  background:var(--accent); color:#fff; font-family:var(--font);
}
@media (prefers-color-scheme: dark) {
  .priority .count { color:#062016; }
}
.priority .empty {
  border-style:dashed; border-color:color-mix(in srgb, var(--accent) 25%, var(--line2));
  background:transparent;
}

.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; margin-bottom:8px; }
.tile {
  background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
  padding:14px 15px 12px; display:flex; flex-direction:column; gap:2px;
}
.tile .n {
  font-size:1.7rem; font-weight:700; font-variant-numeric:tabular-nums; letter-spacing:-.03em;
}
.tile .l { color:var(--ink2); font-size:.76rem; line-height:1.35; }
.tile.hot .n { color:var(--accent); }

h2.sec {
  display:flex; align-items:center; gap:8px; font-size:.74rem; margin:28px 0 10px;
  color:var(--ink3); text-transform:uppercase; letter-spacing:.08em; font-weight:650;
}
.count {
  color:var(--ink2); background:var(--surface2); border-radius:999px;
  font-size:.72rem; padding:1px 8px; font-variant-numeric:tabular-nums; font-weight:650;
}

ul.list { list-style:none; display:flex; flex-direction:column; gap:8px; padding:0; }
.item {
  background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:12px 15px; overflow-wrap:anywhere;
}
.item .head { display:flex; align-items:flex-start; gap:10px; }
.item .head svg { flex:none; margin-top:2px; width:16px; height:16px; }
.item.good .head svg { color:var(--good); }
.item.warn .head svg { color:var(--warn); }
.item.bad  .head svg { color:var(--bad); }
.item .txt { flex:1; font-size:.9rem; color:var(--ink); }

.btn {
  display:inline-flex; align-items:center; gap:6px; margin-top:9px; margin-right:8px;
  font-size:.82rem; font-weight:650; text-decoration:none; color:var(--ink);
  border:1px solid var(--line2); border-radius:9px; padding:6px 12px; min-height:32px;
  cursor:pointer; background:var(--surface);
  transition:border-color 200ms var(--ease), background-color 200ms var(--ease), transform 160ms var(--ease);
}
.btn:hover { border-color:var(--ink2); text-decoration:none; background:var(--surface2); }
.btn:active { transform:scale(0.97); }
.btn svg { color:var(--ink2); }

details { margin-top:8px; }
summary {
  display:inline-flex; align-items:center; gap:5px; cursor:pointer; color:var(--ink2);
  font-size:.82rem; font-weight:650; padding:5px 2px; user-select:none; list-style:none;
  transition:color 200ms var(--ease);
}
summary::-webkit-details-marker { display:none; }
summary::before {
  content:""; width:12px; height:12px; flex:none; background:currentColor;
  transition:transform 200ms var(--ease);
  -webkit-mask:url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>') center/contain no-repeat;
  mask:url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>') center/contain no-repeat;
}
details[open] summary::before { transform:rotate(90deg); }
summary:hover { color:var(--ink); }
blockquote {
  border-left:2px solid var(--line2); background:var(--surface2); border-radius:0 10px 10px 0;
  padding:10px 14px; margin-top:8px; color:var(--ink2); font-size:.88rem; line-height:1.6; max-width:66ch;
}
.empty {
  color:var(--ink2); font-size:.88rem;
  background:transparent; border:1px dashed var(--line2); border-radius:12px; padding:14px 16px;
}
footer {
  margin-top:44px; color:var(--ink3); font-size:.8rem;
  border-top:1px solid var(--line); padding-top:16px; line-height:1.9;
}
.local-only, .panel-only { display:none; }
html.is-local .local-only { display:inline; }
html.is-panel .panel-only { display:inline; }
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
        out.append(f'<a class="btn" href="{_esc(link)}" target="_blank" rel="noopener">{_I["mail"]}Open draft in Gmail</a>')
    if body:
        out.append(f'<details><summary>Read draft body</summary><blockquote>{_esc(body)}</blockquote></details>')
    out.append("</li>")
    return "".join(out)


def _list(entries, tone, item_icon, empty):
    if not entries:
        return f'<p class="empty">{empty}</p>'
    rows = "".join(_card(e, tone, item_icon) for e in entries)
    return f'<ul class="list">{rows}</ul>'


def _parse_gmail_drafts(entries):
    """Turn digest draft rows into structured {text, href, body} for the panel."""
    items = []
    for entry in entries or []:
        body = None
        text = entry
        if "\n  BODY: " in entry:
            text, body = entry.split("\n  BODY: ", 1)
        link = None
        m = DRAFT_LINK_RE.search(text)
        if m:
            link = m.group(1)
            text = DRAFT_LINK_RE.sub("", text).strip()
        items.append({"text": text, "href": link, "body": body})
    return items


def _need_id(kind, text):
    return hashlib.sha1(f"{kind}:{text}".encode()).hexdigest()[:12]


def _contact_index(contacts):
    idx = {}
    for c in contacts or []:
        name = c.get("name") or ""
        company = c.get("company") or ""
        if name and company:
            idx[f"{name} ({company})"] = c
        if name:
            idx[name] = c
    return idx


_VERIFIED_EMAIL_RE = re.compile(r"verified address ([^\s,]+)", re.I)


def _build_needs(contacts, sync, we_owe, br, pending_emails=None):
    """Structured Needs-you rows for dashboard + panel (text, href, dismiss id)."""
    idx = _contact_index(contacts)
    pending = {e.lower() for e in (pending_emails or []) if e}
    items = []

    def add(kind, label, raw, href=None):
        text = f"{label}: {raw}"
        items.append({
            "id": _need_id(kind, text),
            "kind": kind,
            "text": text,
            "href": href,
        })

    for x in sync.get("replies", []):
        c = idx.get(x)
        email = ((c or {}).get("email") or "").lower()
        # Already queued for approval — Approvals tab owns it
        if email and email in pending:
            continue
        add("reply", "Reply received. Respond", x, gmail.thread_link((c or {}).get("gmail_thread_id")))
    for x in we_owe:
        # "Name (Company): reason" — match contact on the left of the first colon chunk
        head = x.split(":", 1)[0].strip()
        c = idx.get(head)
        add("owe", "You owe them contact later. Calendar it", x,
            gmail.thread_link((c or {}).get("gmail_thread_id")))
    for x in br.get("manual", []):
        m = _VERIFIED_EMAIL_RE.search(x)
        href = f"mailto:{m.group(1)}" if m else None
        add("manual", "Verified address found, send manually", x, href)
    for x in sync.get("backfill_ambiguous", []):
        add("ambiguous", "Thread ambiguous, check manually", x, None)
    return items


def _needs_list(items, empty):
    if not items:
        return f'<p class="empty">{empty}</p>'
    rows = []
    for it in items:
        link = ""
        if it.get("href"):
            label = "Email them" if it["href"].startswith("mailto:") else "Open in Gmail"
            link = (f'<a class="btn" href="{_esc(it["href"])}" target="_blank" rel="noopener">'
                    f'{_I["mail"]}{label}</a>')
        rows.append(
            f'<li class="item warn"><div class="head">{_I["alert"]}'
            f'<p class="txt">{_esc(it["text"])}</p></div>{link}</li>')
    return f'<ul class="list">{"".join(rows)}</ul>'


def _sec(title, icon, entries, tone, item_icon, empty):
    n = len(entries or [])
    body = _list(entries, tone, item_icon, empty)
    return (f'<section class="rise" aria-label="{_esc(title)}">'
            f'<h2 class="sec">{_I[icon]}{_esc(title)}'
            f'<span class="count">{n}</span></h2>{body}</section>')


def render(contacts, report, llm_calls, dry_run=False):
    sync = report.get("inbox_sync", {})
    ia = report.get("inbox_agent", {})
    ra = report.get("reply_agent", {})
    nu = report.get("reply_nudges", {})
    fu = report.get("followups", {})
    br = report.get("bounce_retry", {})
    pr = report.get("prospecting", {})
    counts = crm.counts(contacts)
    backlog = len(crm.followup_candidates(contacts))
    # Organizer consumes *.json briefs; count unorganized ones waiting for Organize
    brief_files = list(config.QUEUE_PROSPECTS.glob("*.json"))
    unorganized = []
    for path in brief_files:
        try:
            rec = json.loads(path.read_text())
            if not rec.get("organized"):
                cand = rec.get("candidate") or {}
                unorganized.append({
                    "file": path.name,
                    "name": cand.get("name") or path.stem,
                    "company": cand.get("company") or "",
                    "track": rec.get("track") or config.STREAM_LABELS.get(rec.get("email_type"), ""),
                })
        except Exception:
            unorganized.append({"file": path.name, "name": path.stem, "company": "", "track": ""})
    briefs_queued = len(unorganized)
    drafts_today = nu.get("drafted", []) + fu.get("drafted", [])
    linked_bounce = [x for x in br.get("fixed", []) if DRAFT_LINK_RE.search(x)]
    gmail_drafts = _parse_gmail_drafts(drafts_today + linked_bounce)
    errors = (sync.get("errors", []) + ia.get("errors", []) + ra.get("errors", [])
              + nu.get("errors", []) + fu.get("errors", [])
              + br.get("errors", []) + pr.get("errors", []) + report.get("fatal", []))
    we_owe = list(ra.get("we_owe", []) or []) + list(nu.get("we_owe", []) or [])
    pending_emails = [i.get("email") for i in queue_store.pending()]
    needs_items = _build_needs(contacts, sync, we_owe, br, pending_emails=pending_emails)
    bounce_rows = ([f"Fixed, corrected draft in Gmail: {x}" for x in br.get("fixed", [])]
                   + [f"No confident fix, dead: {x}" for x in br.get("dead", [])])
    action_items = ia.get("action_items") or []
    now = datetime.now().strftime("%A %b %d, %I:%M %p")
    ok = not errors
    status_pill = (f'<span class="pill ok">{_I["check"]}All clear</span>' if ok
                   else f'<span class="pill err">{_I["alert"]}{len(errors)} error{"s" if len(errors) != 1 else ""}</span>')
    needs_n = len(needs_items)
    needs_block = (
        f'<div class="priority rise" aria-label="Needs you">'
        f'<h2>{_I["user"]}Needs you <span class="count">{needs_n}</span></h2>'
        f'{_needs_list(needs_items, "Nothing needs you right now — you are caught up.")}'
        f'</div>'
    )

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EmailCRM Autopilot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@450;550;650;700&family=Fraunces:opsz,wght@9..144,550;9..144,650&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>
<header class="top rise">
  <h1>EmailCRM Autopilot</h1>
  {status_pill}
</header>
<p class="meta rise">Last run {now}{' · DRY RUN' if dry_run else ''} · daily 7:04 AM · {llm_calls} LLM calls · drafts only, never sends</p>

{needs_block}

<section class="tiles rise" aria-label="Pipeline totals">
  <div class="tile hot"><span class="n">{needs_n}</span><span class="l">items need you</span></div>
  <div class="tile"><span class="n">{len(gmail_drafts)}</span><span class="l">drafts to review in Gmail</span></div>
  <div class="tile"><span class="n">{counts.get('replied', 0) + counts.get('converted', 0)}</span><span class="l">open conversations</span></div>
  <div class="tile"><span class="n">{counts.get('bounced', 0)}</span><span class="l">bounces unresolved</span></div>
  <div class="tile"><span class="n">{briefs_queued}</span><span class="l">briefs awaiting organize</span></div>
  <div class="tile"><span class="n">{backlog}</span><span class="l">cold backlog (paused)</span></div>
</section>

{_sec("Drafts waiting in Gmail — review, then send", "mail", drafts_today + linked_bounce, "good", "check", "No drafts created today.")}
{_sec("Bounce handling", "zap", bounce_rows, "warn", "alert", "No bounce activity today.")}
{_sec("New prospect briefs", "search", pr.get("briefs", []), "good", "check", "No new briefs today.")}
{_sec("Errors", "bug", errors, "bad", "x", "No errors.")}

<footer class="rise">
  Status counts: {_esc(counts)}<br>
  <a href="https://mail.google.com/mail/u/0/#drafts">Gmail drafts</a>
  <span class="panel-only"> ·
  <a href="/files/digest" target="_blank" rel="noopener">Today's digest</a> ·
  <a href="/files/prospects" target="_blank" rel="noopener">Prospect briefs</a> ·
  <a href="/files/logs" target="_blank" rel="noopener">Run logs</a></span>
  <span class="local-only"> ·
  <a href="file://{config.DIGEST_DIR}/{date.today().isoformat()}.md">Today's digest</a> ·
  <a href="file://{config.QUEUE_PROSPECTS}">Prospect briefs</a> ·
  <a href="file://{config.LOG_DIR}">Run logs</a></span>
</footer>
<script>
if (location.protocol === "file:") document.documentElement.classList.add("is-local");
if (location.hostname === "127.0.0.1" || location.hostname === "localhost")
  document.documentElement.classList.add("is-panel");
</script>
</body></html>"""

    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    (config.STATE_DIR / "last_report.json").write_text(json.dumps({
        "generated": datetime.now().isoformat(timespec="seconds"),
        "needs_you": needs_items,
        "needs_n": needs_n,
        "drafts_n": len(gmail_drafts),
        "gmail_drafts": gmail_drafts,
        "gmail_drafts_n": len(gmail_drafts),
        "errors_n": len(errors),
        "errors": errors[:20],
        "briefs_n": briefs_queued,
        "briefs_waiting": unorganized[:20],
        "action_items": action_items[:12],
        "open_conversations": counts.get("replied", 0) + counts.get("converted", 0),
        "bounces": counts.get("bounced", 0),
        "summary": (
            f"{needs_n} need you · {len(gmail_drafts)} Gmail drafts · "
            f"{briefs_queued} briefs to organize · {len(errors)} errors"
        ),
    }, indent=1))

    path = config.ROOT / "dashboard.html"
    path.write_text(page)
    return path
