"""Localhost control panel for the autopilot.

http://localhost:8787 — Run / Stop, approval queue, live feed, dashboard.
Binds 127.0.0.1 only; never exposed to the network.
Run persistently via launchd (com.aarav.emailcrm.panel, KeepAlive).
"""
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config
import queue_store
import status

PYTHON = config.AUTOPILOT / ".venv" / "bin" / "python"
RUN_PY = config.AUTOPILOT / "run.py"
DISMISS_FILE = config.STATE_DIR / "dismissed_needs.json"


def _load_dismissed():
    if DISMISS_FILE.exists():
        try:
            return set(json.loads(DISMISS_FILE.read_text()))
        except Exception:
            return set()
    return set()


def _save_dismissed(ids):
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    DISMISS_FILE.write_text(json.dumps(sorted(ids), indent=1))


def _filter_report(raw):
    """Drop dismissed Needs-you rows; prune stale dismiss ids."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        return raw if isinstance(raw, str) else json.dumps(raw)
    items = data.get("needs_you") or []
    norm = []
    for it in items:
        if isinstance(it, str):
            norm.append({"id": it, "text": it, "href": None})
        else:
            norm.append(it)
    dismissed = _load_dismissed()
    alive_ids = {it.get("id") for it in norm if it.get("id")}
    pruned = dismissed & alive_ids
    if pruned != dismissed:
        _save_dismissed(pruned)
    visible = [it for it in norm if it.get("id") not in pruned]
    data["needs_you"] = visible
    data["needs_n"] = len(visible)
    return json.dumps(data)


def _brief_html(record, filename):
    """Clean, scannable prospect brief — only what you need to decide."""
    import html as html_mod
    e = html_mod.escape
    cand = record.get("candidate") or {}
    brief = record.get("brief") or {}
    email = brief.get("email") or {}
    hooks = brief.get("hooks") or []
    if not isinstance(hooks, list):
        hooks = []

    name = str(cand.get("name") or "Prospect")
    company = str(cand.get("company") or "")
    role = str(cand.get("role") or "")
    linkedin = cand.get("linkedin_url") or ""
    why = str(cand.get("why_icp") or "").strip()
    signal = str(brief.get("company_signal") or "").strip()
    addr = str((email.get("address") or "")).strip()
    organized = bool(record.get("organized"))

    hook_items = []
    for h in hooks[:5]:
        if isinstance(h, dict):
            fact = str(h.get("fact") or "").strip()
            url = h.get("url") or ""
            if not fact:
                continue
            src = (f' <a class="src" href="{e(str(url))}" target="_blank" rel="noopener">source</a>'
                   if url else "")
            hook_items.append(f"<li>{e(fact)}{src}</li>")
        else:
            s = str(h).strip()
            if s:
                hook_items.append(f"<li>{e(s)}</li>")
    hooks_html = ("<ol class='hooks'>" + "".join(hook_items) + "</ol>") if hook_items else ""

    subtitle = " · ".join(x for x in (role, company) if x)
    status = "Ready for organize" if not organized else "Already organized"

    def section(title, body_html):
        if not body_html:
            return ""
        return f"<section><h2>{e(title)}</h2>{body_html}</section>"

    why_html = f"<p>{e(why)}</p>" if why else ""
    signal_html = f"<p>{e(signal)}</p>" if signal else ""

    actions = ['<a class="btn ghost" href="/#overview">← Panel</a>']
    if linkedin:
        actions.append(f'<a class="btn" href="{e(str(linkedin))}" target="_blank" rel="noopener">LinkedIn</a>')
    if addr:
        actions.append(f'<a class="btn primary" href="mailto:{e(addr)}">Email {e(addr)}</a>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(name)} — Brief</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap" rel="stylesheet">
<style>
html {{ color-scheme: light; }}
:root {{
  --bg:#f4f8f6; --paper:#fff; --ink:#15241e; --muted:#5c6f66; --faint:#8a9a92;
  --line:rgba(21,36,30,.09); --accent:#0c6b54;
  --font:"Plus Jakarta Sans", system-ui, sans-serif;
  --display:"Fraunces", Georgia, serif;
}}
* {{ box-sizing:border-box; margin:0; }}
body {{
  min-height:100vh; color:var(--ink); font:16px/1.55 var(--font); font-weight:450;
  letter-spacing:-.011em; -webkit-font-smoothing:antialiased;
  background:radial-gradient(800px 380px at 10% -10%, rgba(12,107,84,.10), transparent 55%), var(--bg);
}}
.wrap {{ max-width:640px; margin:0 auto; padding:28px 22px 64px; }}
.bar {{ display:flex; align-items:center; gap:12px; margin-bottom:28px; }}
.bar a {{ color:var(--accent); font-weight:600; font-size:.9rem; text-decoration:none; }}
.bar a:hover {{ text-decoration:underline; text-underline-offset:3px; }}
.bar .status {{ margin-left:auto; font-size:.78rem; font-weight:650; color:var(--accent);
  background:rgba(12,107,84,.1); padding:4px 10px; border-radius:999px; }}
header h1 {{
  font-family:var(--display); font-size:2.1rem; font-weight:550;
  letter-spacing:-.035em; line-height:1.12; margin-bottom:8px;
}}
header .sub {{ color:var(--muted); font-size:1.05rem; margin-bottom:18px; }}
.contact {{
  display:flex; flex-wrap:wrap; gap:10px; margin-bottom:28px;
}}
.btn {{
  display:inline-flex; align-items:center; min-height:40px; padding:0 14px;
  border-radius:10px; font:inherit; font-weight:600; font-size:.9rem;
  text-decoration:none; border:1px solid var(--line); background:var(--paper); color:var(--ink);
}}
.btn.primary {{ background:var(--accent); color:#fff; border-color:transparent; }}
.btn.ghost {{ background:transparent; color:var(--accent); border-color:transparent; padding-left:0; }}
.sheet {{
  background:var(--paper); border:1px solid var(--line); border-radius:16px;
  padding:8px 22px 22px; 
}}
section {{ padding:18px 0; border-top:1px solid var(--line); }}
section:first-child {{ border-top:0; }}
section h2 {{
  font-size:.72rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  color:var(--faint); margin-bottom:8px;
}}
section p {{ color:var(--ink); font-size:.98rem; line-height:1.6; max-width:58ch; }}
.hooks {{ padding-left:1.2rem; display:flex; flex-direction:column; gap:10px; }}
.hooks li {{ color:var(--ink); font-size:.95rem; line-height:1.5; padding-left:4px; }}
.hooks .src {{ color:var(--accent); font-size:.8rem; font-weight:650; margin-left:6px; text-decoration:none; }}
.hooks .src:hover {{ text-decoration:underline; }}
.empty {{ color:var(--muted); font-size:.95rem; padding:18px 0; }}
.foot {{ margin-top:18px; font-size:.78rem; color:var(--faint); }}
.foot a {{ color:var(--faint); }}
</style></head>
<body>
<div class="wrap">
  <div class="bar">
    <a href="/#overview">← Back</a>
    <span class="status">{e(status)}</span>
  </div>
  <header>
    <h1>{e(name)}</h1>
    {f'<p class="sub">{e(subtitle)}</p>' if subtitle else ''}
  </header>
  <div class="contact">{"".join(actions)}</div>
  <div class="sheet">
    {section("Why them", why_html)}
    {section("Company signal", signal_html)}
    {section("Talk about", hooks_html)}
    {"" if (why_html or signal_html or hooks_html) else '<p class="empty">No research notes in this brief yet.</p>'}
  </div>
  <p class="foot"><a href="/brief/{e(filename)}?raw=1">Raw data</a></p>
</div>
</body></html>"""


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EmailCRM Autopilot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap" rel="stylesheet">
<style>
html { color-scheme: light; }
:root {
  /* color */
  --bg0:#f7faf8; --bg1:#e9f3ee;
  --paper:#ffffff;
  --paper-soft:rgba(255,255,255,.72);
  --ink:#15241e; --ink2:#5c6f66; --ink3:#8a9a92;
  --line:rgba(21,36,30,.08); --line2:rgba(21,36,30,.14);
  --accent:#0c6b54; --accent-ink:#fff; --accent-soft:rgba(12,107,84,.10);
  --good:#0e6f42; --good-soft:rgba(14,111,66,.10);
  --warn:#8a5a00; --warn-soft:rgba(138,90,0,.10);
  --bad:#b42318; --bad-soft:rgba(180,35,24,.08);
  /* type */
  --font:"Plus Jakarta Sans", "Segoe UI", sans-serif;
  --display:"Fraunces", Georgia, serif;
  /* space / shape */
  --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-5:24px; --space-6:32px;
  --radius:14px; --radius-sm:10px; --radius-xs:8px;
  --chrome:72px;
  --shadow:0 1px 2px rgba(21,36,30,.04), 0 8px 24px rgba(21,36,30,.05);
  --ease:cubic-bezier(0.22,1,0.36,1);
  /* compat aliases used in existing markup */
  --surface:var(--paper-soft); --surface-solid:var(--paper); --surface2:rgba(255,255,255,.55);
  --good-bg:var(--good-soft); --warn-bg:var(--warn-soft); --bad-bg:var(--bad-soft);
  --frost:blur(16px) saturate(1.25);
  --shadow-sm:0 1px 2px rgba(21,36,30,.03), 0 4px 12px rgba(21,36,30,.04);
}
* { box-sizing:border-box; margin:0; }
html, body { height:100%; }
body {
  background:
    radial-gradient(900px 420px at 0% -5%, rgba(12,107,84,.11), transparent 55%),
    radial-gradient(700px 360px at 100% 0%, rgba(12,107,84,.06), transparent 50%),
    linear-gradient(180deg, var(--bg0), var(--bg1));
  color:var(--ink);
  font:15px/1.55 var(--font);
  font-weight:450;
  letter-spacing:-.01em;
  -webkit-font-smoothing:antialiased;
  min-height:100vh;
}
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; text-underline-offset:3px; }

/* —— buttons —— */
button, .tab, .chip {
  font:inherit; font-weight:600; border:0; cursor:pointer;
  transition:background .18s var(--ease), color .18s var(--ease), border-color .18s var(--ease), transform .14s var(--ease), opacity .18s;
}
button:active, .tab:active, .chip:active { transform:scale(0.98); }
button:disabled { opacity:.45; cursor:default; transform:none; }
button:focus-visible, .tab:focus-visible, .chip:focus-visible, a:focus-visible, summary:focus-visible, input:focus-visible {
  outline:2px solid var(--accent); outline-offset:2px;
}
.btn {
  display:inline-flex; align-items:center; justify-content:center; gap:6px;
  min-height:40px; padding:0 16px; border-radius:var(--radius-sm);
  font-weight:600; letter-spacing:-.01em;
}
.btn-primary { background:var(--accent); color:var(--accent-ink); }
.btn-primary:hover { background:#0a5c48; }
.btn-danger { background:var(--bad-soft); color:var(--bad); }
.btn-danger:hover { background:rgba(180,35,24,.14); }
.btn-good { background:var(--good-soft); color:var(--good); }
.btn-good:hover { background:rgba(14,111,66,.16); }
.btn-quiet {
  background:var(--paper); color:var(--ink2); border:1px solid var(--line);
}
.btn-quiet:hover { color:var(--ink); border-color:var(--line2); }
.btn-ghost { background:transparent; color:var(--ink2); min-height:36px; padding:0 12px; }
.btn-ghost:hover { color:var(--ink); background:rgba(21,36,30,.04); }
.btn-link {
  background:none; border:0; color:var(--accent); min-height:auto; padding:0;
  font-weight:600; text-decoration:underline; text-underline-offset:2px;
}
.btn-sm { min-height:32px; padding:0 12px; font-size:.82rem; border-radius:var(--radius-xs); }

/* —— chrome —— */
.chrome {
  position:sticky; top:0; z-index:20;
  backdrop-filter:var(--frost); -webkit-backdrop-filter:var(--frost);
  background:rgba(255,255,255,.78);
  border-bottom:1px solid var(--line);
}
.chrome-inner {
  max-width:880px; margin:0 auto; padding:14px 24px 0;
  display:flex; flex-direction:column; gap:14px;
}
.toprow {
  display:flex; align-items:center; gap:16px; flex-wrap:wrap;
}
.brand {
  display:flex; align-items:center; gap:10px; flex:1; min-width:180px;
}
.dot {
  width:8px; height:8px; border-radius:50%; background:var(--ink3); flex:none;
  transition:background .25s, box-shadow .25s;
}
.dot.live { background:var(--good); box-shadow:0 0 0 3px var(--good-soft); }
.brand h1 {
  font-family:var(--display); font-size:1.4rem; font-weight:550;
  letter-spacing:-.03em; line-height:1; color:var(--ink);
}
.stagechip {
  font-size:.75rem; font-weight:600; color:var(--ink2);
  background:transparent; border:0; padding:0; max-width:220px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-left:auto; }
.run-modes {
  display:inline-flex; gap:2px; padding:3px; border-radius:var(--radius-sm);
  background:rgba(21,36,30,.04); border:1px solid var(--line);
}
.run-modes .chip {
  padding:6px 10px; min-height:30px; font-size:.72rem; font-weight:600;
  border:0; background:transparent; color:var(--ink2); border-radius:calc(var(--radius-sm) - 2px);
}
.run-modes .chip:hover { color:var(--ink); }
.run-modes .chip.active { background:var(--paper); color:var(--ink); box-shadow:var(--shadow-sm); }

.tabs {
  display:flex; gap:0; overflow-x:auto; scrollbar-width:none;
  margin:0; padding:0; border-bottom:1px solid transparent;
}
.tabs::-webkit-scrollbar { display:none; }
.tab {
  background:transparent; color:var(--ink2); padding:10px 14px 12px; min-height:auto;
  border-radius:0; display:inline-flex; align-items:center; gap:8px;
  white-space:nowrap; font-weight:550; position:relative;
  border-bottom:2px solid transparent; margin-bottom:-1px;
}
.tab:hover { color:var(--ink); background:transparent; }
.tab[aria-selected="true"] {
  color:var(--accent); background:transparent; font-weight:650;
  border-bottom-color:var(--accent);
}
.badge {
  font-size:.68rem; font-weight:700; font-variant-numeric:tabular-nums;
  background:var(--accent-soft); color:var(--accent);
  border-radius:999px; min-width:1.25rem; height:1.25rem;
  display:inline-flex; align-items:center; justify-content:center; padding:0 5px;
}
.tab[aria-selected="true"] .badge { background:var(--accent); color:var(--accent-ink); }
.badge[data-n="0"] { display:none; }

/* —— layout —— */
main {
  max-width:880px; margin:0 auto; padding:28px 24px 88px;
}
.panel { display:none; animation:rise 340ms var(--ease); }
.panel.active { display:block; }
@keyframes rise {
  from { opacity:0; transform:translateY(8px); }
  to { opacity:1; transform:none; }
}
@media (prefers-reduced-motion: reduce) {
  .panel, .toast { animation:none !important; }
  button, .tab, .chip { transition:none; }
}

.section-head {
  display:flex; align-items:baseline; justify-content:space-between;
  gap:12px; margin-bottom:18px; flex-wrap:wrap;
}
.section-head h2 {
  font-family:var(--display); font-size:1.55rem; font-weight:550;
  letter-spacing:-.03em; line-height:1.15;
}
.section-lede {
  color:var(--ink2); font-size:.92rem; margin:-8px 0 18px; max-width:52ch;
}
.hint { color:var(--ink3); font-size:.8rem; font-weight:500; }
.kbd {
  font-size:.7rem; font-weight:650; color:var(--ink2);
  background:var(--paper); border:1px solid var(--line);
  border-radius:5px; padding:1px 5px; font-family:ui-monospace, monospace;
}

.stack { display:flex; flex-direction:column; gap:14px; }
.stack-lg { display:flex; flex-direction:column; gap:20px; }
.zone-label {
  font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  color:var(--ink3); margin-bottom:2px;
}

.grid { display:grid; grid-template-columns:1.25fr .75fr; gap:14px; }
@media (max-width:640px) {
  .grid { grid-template-columns:1fr; }
  .stagechip { display:none; }
  .chrome-inner, main { padding-left:16px; padding-right:16px; }
}

.block {
  background:var(--paper); border:1px solid var(--line);
  border-radius:var(--radius); padding:18px 20px;
  box-shadow:var(--shadow-sm);
}
.block .label {
  font-size:.7rem; color:var(--ink3); text-transform:uppercase;
  letter-spacing:.08em; font-weight:700; margin-bottom:8px;
}
.big { font-size:1.25rem; font-weight:650; letter-spacing:-.02em; overflow-wrap:anywhere; }
.sub { color:var(--ink2); font-size:.86rem; margin-top:4px; overflow-wrap:anywhere; line-height:1.45; }
.stream {
  display:inline-block; background:var(--accent-soft); color:var(--accent);
  font-size:.72rem; font-weight:650; border-radius:999px; padding:3px 10px; margin-top:10px;
}
meter { width:100%; height:8px; margin-top:12px; }
.tok.warn .big { color:var(--warn); }
.tok.bad .big { color:var(--bad); }
.rundown {
  font-size:.95rem; color:var(--ink); line-height:1.6;
  white-space:pre-wrap;
}

/* —— queue —— */
#queue { list-style:none; padding:0; display:flex; flex-direction:column; gap:14px; }
.q-item {
  background:var(--paper); border:1px solid var(--line);
  border-radius:var(--radius); padding:18px 20px;
  box-shadow:var(--shadow-sm);
  transition:border-color .2s, box-shadow .2s;
}
.q-item.focused {
  border-color:color-mix(in srgb, var(--accent) 40%, var(--line));
  box-shadow:0 0 0 3px var(--accent-soft);
}
.q-meta {
  display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; margin-bottom:6px;
}
.q-meta strong { font-size:1.08rem; font-weight:650; letter-spacing:-.02em; }
.q-why { color:var(--ink2); font-size:.9rem; margin:4px 0 10px; line-height:1.45; }
.q-subject { font-size:.88rem; margin-bottom:6px; }
.q-subject span { color:var(--ink2); }
.q-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; align-items:center; }
.q-actions button.approve { background:var(--good-soft); color:var(--good); padding:0 16px; min-height:40px; border-radius:var(--radius-sm); }
.q-actions button.skip { background:var(--paper); color:var(--ink2); padding:0 14px; min-height:40px; border-radius:var(--radius-sm); border:1px solid var(--line); }
.skip-menu { display:inline-flex; gap:4px; flex-wrap:wrap; }
.skip-menu button {
  font-size:.72rem; font-weight:600; padding:0 10px; min-height:32px;
  background:rgba(21,36,30,.04); color:var(--ink2); border-radius:var(--radius-xs);
}
.skip-menu button:hover { color:var(--ink); background:rgba(21,36,30,.07); }
details.preview { margin-top:8px; }
details.preview summary {
  cursor:pointer; color:var(--ink2); font-size:.84rem; font-weight:600;
  user-select:none; list-style:none;
}
details.preview summary::-webkit-details-marker { display:none; }
details.preview[open] summary { color:var(--ink); }
blockquote.body {
  border-left:3px solid color-mix(in srgb, var(--accent) 45%, var(--line));
  background:rgba(12,107,84,.04);
  border-radius:0 var(--radius-sm) var(--radius-sm) 0; padding:14px 16px; margin-top:8px;
  font-size:.92rem; line-height:1.6; max-width:68ch; color:var(--ink);
}
.empty {
  color:var(--ink2); font-size:.95rem;
  border:1px dashed var(--line2); border-radius:var(--radius);
  padding:40px 24px; text-align:center;
  background:rgba(255,255,255,.5);
}
.empty strong { display:block; font-family:var(--display); font-size:1.25rem;
  color:var(--ink); font-weight:550; margin-bottom:8px; letter-spacing:-.02em; }

/* —— feed —— */
#feed { list-style:none; padding:0; display:flex; flex-direction:column; gap:8px; }
#feed li {
  background:var(--paper); border:1px solid var(--line); border-radius:var(--radius-sm);
  padding:11px 14px; font-size:.86rem; display:flex; gap:12px; align-items:baseline;
}
#feed .t { color:var(--ink3); font-variant-numeric:tabular-nums; font-size:.74rem; flex:none; font-weight:500; }
#feed .s { color:var(--accent); font-weight:650; font-size:.74rem; flex:none; }

/* —— report —— */
.report-wrap {
  background:var(--paper); border:1px solid var(--line);
  border-radius:var(--radius); overflow:hidden;
  height:calc(100vh - var(--chrome) - 120px); min-height:480px;
  box-shadow:var(--shadow);
}
#dash { width:100%; height:100%; border:0; display:block; background:var(--paper); }

footer.links {
  margin-top:36px; color:var(--ink3); font-size:.78rem; line-height:1.85;
  border-top:1px solid var(--line); padding-top:16px;
}

/* —— queue edit —— */
.q-subject-row { display:flex; flex-direction:column; gap:4px; margin:8px 0 4px; }
.q-subject-row label, .q-fields label {
  font-size:.7rem; font-weight:700; color:var(--ink3); text-transform:uppercase; letter-spacing:.07em;
}
.body-edit {
  border-left:3px solid color-mix(in srgb, var(--accent) 45%, var(--line));
  background:var(--paper);
  border-radius:0 var(--radius-sm) var(--radius-sm) 0; padding:14px 16px; margin-top:8px;
  font-size:.92rem; line-height:1.6; max-width:68ch; color:var(--ink);
  min-height:7rem; outline:none; border-top:1px solid var(--line); border-right:1px solid var(--line); border-bottom:1px solid var(--line);
}
.body-edit:focus { border-color:color-mix(in srgb, var(--accent) 40%, var(--line)); box-shadow:0 0 0 3px var(--accent-soft); }
.edit-hint { color:var(--ink3); font-size:.76rem; margin-top:6px; }

/* —— attention zones —— */
.needs, .gmail-drafts, .errors-box {
  border-radius:var(--radius); padding:18px 20px; margin:0;
}
.needs {
  background:linear-gradient(180deg, rgba(12,107,84,.07), rgba(255,255,255,.9));
  border:1px solid color-mix(in srgb, var(--accent) 16%, var(--line));
}
.needs h3, .gmail-drafts h3, .errors-box h3 {
  font-family:var(--display); font-size:1.15rem; font-weight:550;
  letter-spacing:-.02em; margin-bottom:12px; display:flex; align-items:center; gap:8px;
}
.needs ul, .gmail-drafts ul, .errors-box ul {
  list-style:none; padding:0; display:flex; flex-direction:column; gap:8px;
}
.needs li, .gmail-drafts li {
  font-size:.9rem; background:var(--paper); border-radius:var(--radius-sm);
  padding:12px 14px; border:1px solid var(--line);
  display:flex; flex-direction:column; gap:6px;
}
.needs .row-actions, .gmail-drafts .row-actions {
  display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin-top:2px;
}
.needs .row-actions a, .needs .row-actions button,
.gmail-drafts .row-actions a {
  font-size:.8rem; font-weight:650; min-height:auto; padding:0;
  background:none; border:0; cursor:pointer; color:var(--accent);
}
.needs .row-actions button { color:var(--ink3); }
.needs .go { font-size:.84rem; font-weight:650; margin-top:10px; display:inline-block; }
.errors-box {
  background:linear-gradient(180deg, rgba(180,35,24,.06), rgba(255,255,255,.92));
  border:1px solid color-mix(in srgb, var(--bad) 18%, var(--line));
}
.errors-box h3 { color:var(--bad); }
.errors-box li { font-size:.86rem; color:var(--ink); line-height:1.45; }
.gmail-drafts {
  background:var(--paper); border:1px solid var(--line); box-shadow:var(--shadow-sm);
}
.lastrun {
  color:var(--ink2); font-size:.88rem; margin:0;
  padding:12px 16px; background:var(--paper); border:1px solid var(--line);
  border-radius:var(--radius-sm);
}
.lastrun strong { color:var(--ink); font-weight:650; }

.q-fields { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:10px 0 4px; }
@media (max-width:640px) { .q-fields { grid-template-columns:1fr; } }
.q-fields label { display:block; margin-bottom:5px; }
.subj-edit, .email-edit {
  font:inherit; font-weight:550; color:var(--ink); background:var(--paper);
  border:1px solid var(--line); border-radius:var(--radius-xs); padding:10px 12px; width:100%;
}
.subj-edit:focus-visible, .email-edit:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
.thread-link { font-size:.82rem; font-weight:650; margin:6px 0 0; display:inline-block; }

.filters {
  display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; align-items:center;
  padding:10px 12px; background:rgba(255,255,255,.55); border:1px solid var(--line);
  border-radius:var(--radius); 
}
.chip {
  font-size:.8rem; padding:0 12px; min-height:32px;
  border-radius:var(--radius-xs); background:transparent; color:var(--ink2);
  border:1px solid transparent;
}
.chip:hover { color:var(--ink); background:rgba(21,36,30,.04); }
.chip.active { background:var(--accent-soft); color:var(--accent); border-color:transparent; }
.qsplit { color:var(--ink3); font-size:.9rem; margin-left:8px; font-weight:500; font-family:var(--font); }
.qsearch {
  font:inherit; font-size:.86rem; color:var(--ink); background:var(--paper);
  border:1px solid var(--line); border-radius:var(--radius-xs); padding:0 12px; min-height:32px;
  min-width:160px; flex:1; max-width:260px; margin-left:auto;
}
.qsearch::placeholder { color:var(--ink3); }

.pipeline {
  display:flex; gap:6px; flex-wrap:wrap; margin-bottom:16px;
}
.pipeline .step {
  font-size:.72rem; font-weight:650; padding:5px 10px; border-radius:var(--radius-xs);
  background:var(--paper); color:var(--ink3); border:1px solid var(--line);
}
.pipeline .step.done { color:var(--good); background:var(--good-soft); border-color:transparent; }
.pipeline .step.live { color:var(--accent); background:var(--accent-soft); border-color:transparent; }

.help-overlay {
  position:fixed; inset:0; background:rgba(21,36,30,.32); z-index:50;
  backdrop-filter:blur(5px); -webkit-backdrop-filter:blur(5px);
  display:none; place-items:center; padding:24px;
}
.help-overlay.is-open { display:grid; }
.help-card {
  background:var(--paper); border:1px solid var(--line); border-radius:18px;
  padding:24px 26px; width:min(420px, 100%); max-height:80vh; overflow:auto;
  box-shadow:var(--shadow);
}
.help-card h2 { font-family:var(--display); font-size:1.3rem; margin-bottom:14px; font-weight:550; letter-spacing:-.02em; }
.help-card dl { display:grid; grid-template-columns:auto 1fr; gap:10px 16px; font-size:.9rem; }
.help-card dt .kbd { margin-right:2px; }
.help-card dd { color:var(--ink2); }
.help-card .close { margin-top:18px; width:100%; }

.empty .cta { margin-top:14px; }

.urgency-banner {
  background:var(--warn-soft); color:var(--warn); border-radius:var(--radius-sm);
  padding:12px 14px; margin-bottom:14px; font-size:.88rem; font-weight:550;
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  border:1px solid color-mix(in srgb, var(--warn) 18%, transparent);
}
.urgency-banner button { color:var(--accent); font-weight:650; background:none; border:0;
  cursor:pointer; min-height:auto; padding:0; text-decoration:underline; }

.context { margin:8px 0 4px; }
.context summary { cursor:pointer; color:var(--ink2); font-size:.82rem; font-weight:600; }
.context pre, .ctx-body {
  margin-top:8px; padding:12px 14px;
  background:rgba(12,107,84,.04);
  border-radius:0 var(--radius-sm) var(--radius-sm) 0;
  border-left:3px solid color-mix(in srgb, var(--accent) 40%, var(--line));
  font-size:.8rem; line-height:1.5; white-space:pre-wrap; max-height:220px; overflow:auto;
  color:var(--ink2);
}

.done-today { margin-top:28px; }
.done-today summary {
  cursor:pointer; color:var(--ink2); font-size:.9rem; font-weight:600; padding:6px 0;
}
.done-today ul { list-style:none; padding:10px 0 0; display:flex; flex-direction:column; gap:8px; }
.done-today li {
  font-size:.86rem; color:var(--ink2); padding:10px 14px;
  background:var(--paper); border:1px solid var(--line); border-radius:var(--radius-sm);
}
.done-today .ok { color:var(--good); font-weight:650; }
.done-today .skip { color:var(--ink3); }
.done-today button.linkish, .done-today a {
  color:var(--accent); font-weight:650; background:none; border:0; padding:0;
  min-height:auto; cursor:pointer; text-decoration:underline; font:inherit;
}

/* —— toast —— */
.toast-wrap {
  position:fixed; bottom:22px; left:50%; transform:translateX(-50%);
  z-index:40; display:flex; flex-direction:column; gap:8px; width:min(400px, calc(100% - 32px));
  pointer-events:none;
}
.toast {
  pointer-events:auto; background:var(--ink); color:#f4f8f6;
  border-radius:var(--radius-sm); padding:13px 15px; font-size:.88rem; font-weight:550;
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  box-shadow:var(--shadow);
  animation:rise 280ms var(--ease);
}
.toast a, .toast button.linkish {
  color:#7ddec0; font-weight:650; background:none; border:0; padding:0;
  min-height:auto; cursor:pointer; text-decoration:underline; text-underline-offset:2px;
}
.toast .dismiss { margin-left:auto; color:inherit; opacity:.65; background:none; border:0;
  min-height:auto; padding:2px 6px; cursor:pointer; font-weight:650; }

/* —— overview navigation helpers —— */
.jumpnav {
  display:flex; flex-wrap:wrap; gap:8px; margin:0 0 16px; padding:0;
  list-style:none;
}
.jumpnav a {
  font-size:.8rem; font-weight:600; color:var(--ink2); text-decoration:none;
  padding:6px 12px; border-radius:var(--radius-xs); background:var(--paper);
  border:1px solid var(--line);
}
.jumpnav a:hover { color:var(--accent); border-color:color-mix(in srgb, var(--accent) 28%, var(--line)); text-decoration:none; }

.person-row {
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  padding:14px 16px !important;
}
.person-row .who { flex:1; min-width:160px; }
.person-row .who strong { display:block; font-size:.98rem; font-weight:650; letter-spacing:-.015em; color:var(--ink); }
.person-row .who .meta { color:var(--ink2); font-size:.84rem; margin-top:2px; }
.person-row .tag {
  font-size:.7rem; font-weight:700; color:var(--accent); background:var(--accent-soft);
  padding:4px 9px; border-radius:999px; white-space:nowrap;
}
.person-row .btn { margin-left:auto; text-decoration:none; }
.person-row .btn:hover { text-decoration:none; }

.errors-box li {
  background:var(--paper); border:1px solid color-mix(in srgb, var(--bad) 14%, var(--line));
  border-radius:var(--radius-sm); padding:10px 12px; font-size:.84rem; line-height:1.45;
  color:var(--ink); overflow-wrap:anywhere;
}
.chrome-label {
  font-size:.68rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
  color:var(--ink3); margin-right:2px;
}

.status-strip {
  display:grid; grid-template-columns:1.1fr .9fr; gap:10px;
}
@media (max-width:640px) { .status-strip { grid-template-columns:1fr; } }
.block.compact { padding:14px 16px; }
.block.compact .big { font-size:1.15rem; }
.stack { gap:10px !important; }
.stack-lg { gap:14px !important; }
.section-head { margin-bottom:14px !important; }
.section-lede { display:none; }
.jumpnav { display:none !important; }
.errors-box {
  background:#fff !important;
  border:1px solid color-mix(in srgb, var(--bad) 22%, var(--line)) !important;
  padding:16px 18px !important;
}
.errors-box h3 { margin-bottom:6px !important; font-size:1.05rem !important; }
.err-lede { color:var(--ink2); font-size:.88rem; margin-bottom:10px; line-height:1.45; }
.errors-box li {
  background:rgba(180,35,24,.04) !important;
  border:0 !important; border-radius:8px !important;
  padding:8px 10px !important; font-size:.84rem !important;
}
.needs, .gmail-drafts { padding:14px 16px !important; margin:0 !important; }
.needs h3, .gmail-drafts h3 { font-size:1.05rem !important; margin-bottom:10px !important; }
.person-row { padding:12px 14px !important; }
main { padding-top:20px !important; }
.chrome-inner { gap:10px !important; padding-top:12px !important; }
.section-head h2 { font-size:1.4rem !important; }
</style></head>
<body>
<div class="chrome">
  <div class="chrome-inner">
    <div class="toprow">
      <div class="brand">
        <span class="dot" id="dot" aria-hidden="true"></span>
        <h1>EmailCRM</h1>
        <span class="stagechip" id="stagechip">idle</span>
      </div>
      <div class="actions">
        <span class="chrome-label">Mode</span>
        <div class="run-modes" id="run-modes" title="What to run" aria-label="Run mode">
          <button type="button" class="chip active" data-stage="">Full</button>
          <button type="button" class="chip" data-stage="triage">Triage</button>
          <button type="button" class="chip" data-stage="scout">Scout</button>
          <button type="button" class="chip" data-stage="organize">Organize</button>
          <button type="button" class="chip" data-stage="digest">Digest</button>
        </div>
        <button id="run" type="button" class="btn btn-primary">Run now</button>
        <button id="stop" type="button" class="btn btn-danger">Stop</button>
      </div>
    </div>
    <nav class="tabs" role="tablist" aria-label="Panel sections">
      <button class="tab" role="tab" id="tab-approvals" aria-controls="panel-approvals" aria-selected="true" data-panel="approvals">
        Approvals <span class="badge" id="qbadge" data-n="0">0</span>
      </button>
      <button class="tab" role="tab" id="tab-overview" aria-controls="panel-overview" aria-selected="false" data-panel="overview">
        Overview <span class="badge" id="overviewbadge" data-n="0">0</span>
      </button>
      <button class="tab" role="tab" id="tab-activity" aria-controls="panel-activity" aria-selected="false" data-panel="activity">Activity</button>
      <button class="tab" role="tab" id="tab-report" aria-controls="panel-report" aria-selected="false" data-panel="report">Report</button>
    </nav>
  </div>
</div>

<main>
  <section class="panel active" id="panel-approvals" role="tabpanel" aria-labelledby="tab-approvals">
    <div class="section-head">
      <h2>Approvals <span class="qsplit" id="qsplit"></span></h2>
      <p class="hint"><span class="kbd">j</span>/<span class="kbd">k</span> move · <span class="kbd">?</span> help</p>
    </div>
    <p class="section-lede">Review drafts before they go to Gmail. Edit freely, then approve.</p>
    <p class="urgency-banner" id="urgency-banner" hidden>
      <span id="urgency-text"></span>
      <button type="button" id="urgency-go">Overview →</button>
    </p>
    <div class="filters" id="qfilters">
      <button type="button" class="chip active" data-filter="all">All</button>
      <button type="button" class="chip" data-filter="reply">Replies</button>
      <button type="button" class="chip" data-filter="outreach">Outreach</button>
      <input class="qsearch" id="qsearch" type="search" placeholder="Search name, company…" autocomplete="off">
    </div>
    <ul id="queue"></ul>
    <details class="done-today" id="done-today">
      <summary>Done today (<span id="done-count">0</span>)</summary>
      <ul id="donelist"></ul>
    </details>
  </section>

  <section class="panel" id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" hidden>
    <div class="section-head">
      <h2>Overview</h2>
      <p class="hint" id="lastrun">Last run · <strong id="lastrun-text">—</strong></p>
    </div>

    <div class="status-strip">
      <div class="block compact">
        <p class="label">Activity</p>
        <p class="big" id="stage">idle</p>
        <p class="sub" id="detail">—</p>
        <span class="stream" id="stream" hidden></span>
      </div>
      <div class="block compact tok" id="tokcard">
        <p class="label">Claude usage</p>
        <p class="big" id="tokpct">0%</p>
        <p class="sub" id="tokdetail">—</p>
        <meter id="tokmeter" min="0" max="100" low="59" high="60" optimum="10" value="0"></meter>
      </div>
    </div>

    <div class="stack" id="zone-attention" style="margin-top:18px">
      <div class="needs" id="needsbox" hidden>
        <h3>Needs you <span class="badge" id="needsbadge" data-n="0">0</span></h3>
        <ul id="needslist"></ul>
        <a class="go" href="#report" id="needs-report">Full report →</a>
      </div>
      <div class="gmail-drafts" id="gmailbox" hidden>
        <h3>Review in Gmail <span class="badge" id="gmailbadge" data-n="0">0</span></h3>
        <ul id="gmaillist"></ul>
      </div>
      <div class="gmail-drafts" id="briefsbox" hidden>
        <h3>Briefs to organize <span class="badge" id="briefsbadge" data-n="0">0</span></h3>
        <ul id="briefslist"></ul>
        <button type="button" class="btn btn-primary btn-sm" id="briefs-organize" style="margin-top:12px">Run Organize →</button>
      </div>
      <div class="needs" id="actionsbox" hidden>
        <h3>Inbox action items</h3>
        <ul id="actionslist"></ul>
      </div>
      <div class="errors-box" id="errorsbox" hidden>
        <h3>What blocked the last run</h3>
        <p class="err-lede" id="errors-lede"></p>
        <ul id="errorslist"></ul>
      </div>
      <div class="block compact" id="rundown-block">
        <p class="label">Inbox rundown</p>
        <p class="rundown" id="rundown">—</p>
      </div>
    </div>
  </section>

  <section class="panel" id="panel-activity" role="tabpanel" aria-labelledby="tab-activity" hidden>
    <div class="section-head"><h2>Activity</h2></div>
    <p class="section-lede">Live pipeline stages and events from the current run.</p>
    <div class="pipeline" id="pipeline" aria-label="Pipeline stages"></div>
    <ul id="feed" aria-live="polite"><li>waiting for status…</li></ul>
  </section>

  <section class="panel" id="panel-report" role="tabpanel" aria-labelledby="tab-report" hidden>
    <div class="section-head">
      <h2>Report</h2>
      <p class="hint"><a href="/dashboard" target="_blank" rel="noopener">Open full page ↗</a></p>
    </div>
    <div class="report-wrap">
      <iframe id="dash" src="/dashboard" title="EmailCRM dashboard"></iframe>
    </div>
  </section>

  <footer class="links">
    <a href="https://verma0118.github.io/email-autopilot/">Web dashboard</a> (encrypted, away-from-Mac) ·
    <a href="https://mail.google.com/mail/u/0/#drafts">Gmail drafts</a> ·
    <a href="/files/digest" target="_blank" rel="noopener">Digest</a> ·
    <a href="/files/prospects" target="_blank" rel="noopener">Briefs</a> ·
    <a href="/files/logs" target="_blank" rel="noopener">Logs</a><br>
    Scheduled run: daily 7:04 AM · warning at 60% of the autopilot token budget
  </footer>
</main>
<div class="toast-wrap" id="toasts" aria-live="polite"></div>
<div class="help-overlay" id="help" aria-hidden="true">
  <div class="help-card" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <h2 id="help-title">Keyboard shortcuts</h2>
    <dl>
      <dt><span class="kbd">1</span>–<span class="kbd">4</span></dt><dd>Approvals / Overview / Activity / Report</dd>
      <dt><span class="kbd">j</span> / <span class="kbd">k</span></dt><dd>Next / previous queue item</dd>
      <dt><span class="kbd">a</span></dt><dd>Approve focused (asks to confirm)</dd>
      <dt><span class="kbd">s</span></dt><dd>Skip focused for 7 days</dd>
      <dt><span class="kbd">o</span></dt><dd>Toggle edit body</dd>
      <dt><span class="kbd">/</span></dt><dd>Focus search</dd>
      <dt><span class="kbd">?</span></dt><dd>Toggle this help</dd>
      <dt><span class="kbd">Esc</span></dt><dd>Close help</dd>
    </dl>
    <button type="button" class="btn btn-primary close" id="help-close">Close</button>
  </div>
</div>

<script>
const el = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
const sanitizeHtml = html => String(html ?? "")
  .replace(/<script[\\s\\S]*?<\\/script>/gi, "")
  .replace(/<iframe[\\s\\S]*?<\\/iframe>/gi, "")
  .replace(/\\son\\w+=("[^"]*"|'[^']*'|[^\\s>]+)/gi, "");

let focusId = null;
let queueAll = [];
let queueItems = [];
let queueFilter = "all";
let queueSearch = "";
let lastQueueSig = "";
let wasRunning = false;
let needsCount = 0;
let runStage = "";
const saveTimers = {};

const PIPELINE_STAGES = [
  ["inbox", "Inbox"], ["reply", "Reply"], ["bounce", "Bounce"],
  ["scout", "Scout"], ["organize", "Organize"], ["digest", "Digest"],
];

function showPanel(name) {
  document.querySelectorAll(".tab").forEach(t => {
    const on = t.dataset.panel === name;
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll(".panel").forEach(p => {
    const on = p.id === "panel-" + name;
    p.classList.toggle("active", on);
    p.hidden = !on;
  });
  if (name === "report") {
    const chrome = document.querySelector(".chrome");
    if (chrome) document.documentElement.style.setProperty("--chrome", chrome.offsetHeight + "px");
  }
  updateUrgencyBanner();
  try { localStorage.setItem("emailcrm-tab", name); } catch (_) {}
  if (location.hash !== "#" + name) {
    try { history.replaceState(null, "", "#" + name); } catch (_) {}
  }
}

document.querySelectorAll(".tab").forEach(t => {
  t.addEventListener("click", () => showPanel(t.dataset.panel));
});
el("needs-report").addEventListener("click", ev => {
  ev.preventDefault();
  showPanel("report");
});
el("urgency-go").addEventListener("click", () => showPanel("overview"));
window.addEventListener("hashchange", () => {
  const h = (location.hash || "").replace("#", "");
  if (["approvals", "overview", "activity", "report"].includes(h)) showPanel(h);
});

document.querySelectorAll("#qfilters .chip").forEach(c => {
  c.addEventListener("click", () => {
    queueFilter = c.dataset.filter;
    document.querySelectorAll("#qfilters .chip").forEach(x =>
      x.classList.toggle("active", x.dataset.filter === queueFilter));
    lastQueueSig = "";
    loadQueue();
  });
});
el("qsearch").addEventListener("input", () => {
  queueSearch = el("qsearch").value.trim().toLowerCase();
  lastQueueSig = "";
  loadQueue();
});

function helpIsOpen() {
  return el("help").classList.contains("is-open");
}
function openHelp() {
  el("help").classList.add("is-open");
  el("help").setAttribute("aria-hidden", "false");
}
function closeHelp() {
  el("help").classList.remove("is-open");
  el("help").setAttribute("aria-hidden", "true");
}
function toggleHelp() {
  if (helpIsOpen()) closeHelp(); else openHelp();
}

el("help-close").addEventListener("click", ev => {
  ev.preventDefault();
  ev.stopPropagation();
  closeHelp();
});
el("help").addEventListener("click", ev => {
  if (ev.target === el("help")) closeHelp();
});

function updateUrgencyBanner() {
  const banner = el("urgency-banner");
  const onApprovals = el("panel-approvals").classList.contains("active");
  if (needsCount > 0 && onApprovals) {
    banner.hidden = false;
    el("urgency-text").textContent = needsCount + " item" + (needsCount === 1 ? "" : "s") + " need you on Overview";
  } else {
    banner.hidden = true;
  }
}

function sortQueue(q) {
  return [...q].sort((a, b) => {
    if (a.kind === "reply" && b.kind !== "reply") return -1;
    if (a.kind !== "reply" && b.kind === "reply") return 1;
    return (a.created || "").localeCompare(b.created || "");
  });
}

function filterQueue(q) {
  let out = q;
  if (queueFilter === "reply") out = out.filter(i => i.kind === "reply");
  else if (queueFilter === "outreach") out = out.filter(i => i.kind === "outreach");
  if (queueSearch) {
    out = out.filter(i => {
      const hay = [i.name, i.company, i.email, i.subject, i.track, i.why]
        .map(x => String(x || "").toLowerCase()).join(" ");
      return hay.includes(queueSearch);
    });
  }
  return out;
}

function updatePipeline(stageLabel, running) {
  const pipe = el("pipeline");
  const cur = String(stageLabel || "").toLowerCase();
  const order = PIPELINE_STAGES.map(([k]) => k);
  let hit = -1;
  for (let i = 0; i < order.length; i++) {
    if (cur.includes(order[i])) { hit = i; break; }
  }
  pipe.innerHTML = PIPELINE_STAGES.map(([key, label], i) => {
    let cls = "step";
    if (running && hit >= 0) {
      if (i < hit) cls += " done";
      else if (i === hit) cls += " live";
    } else if (!running && hit < 0) {
      /* idle */
    }
    return '<span class="' + cls + '">' + label + '</span>';
  }).join("");
}

function contextHtml(item) {
  const m = item.meta || {};
  if (item.kind === "reply" && m.thread_preview) {
    return '<details class="context"><summary>Thread context</summary><pre>' +
      esc(m.thread_preview) + '</pre></details>';
  }
  if (item.kind === "outreach") {
    const parts = [];
    if (m.company_signal) parts.push("<strong>Signal</strong> · " + esc(m.company_signal));
    if (m.hooks) parts.push("<strong>Hooks</strong><br>" + esc(m.hooks).replace(/\\n/g, "<br>"));
    if (m.email_basis) parts.push("<strong>Email basis</strong> · " + esc(m.email_basis));
    if (m.brief_file) {
      parts.push('<a href="/brief/' + encodeURIComponent(m.brief_file) + '">Full brief</a>');
    }
    if (!parts.length) return "";
    return '<details class="context"><summary>Research context</summary><div class="ctx-body">' +
      parts.join("<br><br>") + '</div></details>';
  }
  return "";
}

function toast(html, { timeout = 8000 } = {}) {
  const wrap = el("toasts");
  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = html + '<button type="button" class="dismiss" aria-label="Dismiss">×</button>';
  const kill = () => t.remove();
  t.querySelector(".dismiss").onclick = kill;
  wrap.appendChild(t);
  if (timeout) setTimeout(kill, timeout);
  return t;
}

function focusedIndex() {
  if (!queueItems.length) return 0;
  const i = queueItems.findIndex(q => q.id === focusId);
  return i >= 0 ? i : 0;
}

function setFocus(i) {
  const items = [...document.querySelectorAll(".q-item")];
  if (!items.length) { focusId = null; return; }
  const idx = Math.max(0, Math.min(i, items.length - 1));
  focusId = items[idx].dataset.id;
  items.forEach((n, j) => n.classList.toggle("focused", j === idx));
  items[idx].scrollIntoView({ block:"nearest", behavior:"smooth" });
}

function draftPayload(id) {
  const li = document.querySelector('.q-item[data-id="' + CSS.escape(id) + '"]');
  if (!li) return { id };
  const subject = li.querySelector(".subj-edit")?.value;
  const email = li.querySelector(".email-edit")?.value;
  const body = li.querySelector(".body-edit")?.innerHTML;
  const out = { id };
  if (subject != null) out.subject = subject;
  if (email != null) out.email = email.trim();
  if (body != null) out.body_html = body;
  return out;
}

async function act(id, action, btn, { confirmApprove = false, skipUntil = 7 } = {}) {
  if (action === "approve" && confirmApprove) {
    const item = queueItems.find(q => q.id === id);
    const who = item ? (item.name || "this draft") : "this draft";
    if (!window.confirm("Approve draft for " + who + " → create Gmail draft?")) return;
  }
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  let payload;
  if (action === "approve") payload = draftPayload(id);
  else if (action === "skip") payload = { id, skip_until: skipUntil };
  else payload = { id };
  const res = await fetch("/" + action, {
    method:"POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    if (btn) { btn.textContent = "error"; btn.disabled = false; }
    toast(esc(data.error || "Something went wrong"));
    return;
  }
  if (action === "approve") {
    const link = data.draft_link
      || "https://mail.google.com/mail/u/0/#drafts";
    const t = toast('Draft created. <a href="' + esc(link) + '" target="_blank" rel="noopener">Open in Gmail</a> · <button type="button" class="linkish">Undo</button>');
    t.querySelector(".linkish")?.addEventListener("click", () => undoItem(id));
  } else if (action === "skip") {
    const label = skipUntil === "forever" ? "forever" : (skipUntil + "d");
    const t = toast('Snoozed ' + label + '. <button type="button" class="linkish">Undo</button>');
    t.querySelector(".linkish")?.addEventListener("click", () => undoItem(id));
  }
  lastQueueSig = "";
  await loadQueue();
  await loadHistory();
}

async function undoItem(id) {
  const r = await fetch("/undo", {
    method:"POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  let data = {};
  try { data = await r.json(); } catch (_) {}
  if (r.ok) {
    toast(data.undid === "approved" ? "Approval undone — draft deleted" : "Restored to queue");
    lastQueueSig = "";
    await loadQueue();
    await loadHistory();
  } else toast(esc(data.error || "Could not undo"));
}

function scheduleSave(id) {
  clearTimeout(saveTimers[id]);
  saveTimers[id] = setTimeout(() => {
    const payload = draftPayload(id);
    fetch("/save", {
      method:"POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});
  }, 600);
}

async function loadReport() {
  try {
    const r = await (await fetch("/report")).json();
    const box = el("needsbox");
    const items = Array.isArray(r.needs_you) ? r.needs_you : [];
    const norm = items.map(it => typeof it === "string"
      ? { id: it, text: it, href: null }
      : it);
    const n = r.needs_n != null ? r.needs_n : norm.length;
    needsCount = n;
    el("needsbadge").textContent = n;
    el("needsbadge").dataset.n = String(n);
    const gmailN = r.gmail_drafts_n || (r.gmail_drafts || []).length;
    const briefsN = r.briefs_n || (r.briefs_waiting || []).length;
    const ob = el("overviewbadge");
    ob.textContent = n + gmailN + briefsN;
    ob.dataset.n = String(n + gmailN + briefsN);
    updateUrgencyBanner();
    const ul = el("needslist");
    if (!n) { box.hidden = true; ul.innerHTML = ""; }
    else {
      box.hidden = false;
      ul.innerHTML = "";
      norm.slice(0, 10).forEach(it => {
        const li = document.createElement("li");
        const actions = [];
        if (it.href) {
          const label = String(it.href).startsWith("mailto:") ? "Email them" : "Open in Gmail";
          actions.push('<a href="' + esc(it.href) + '" target="_blank" rel="noopener">' + label + '</a>');
        }
        actions.push('<button type="button" data-dismiss="' + esc(it.id) + '">Dismiss</button>');
        li.innerHTML = '<div>' + esc(it.text) + '</div><div class="row-actions">' + actions.join("") + '</div>';
        ul.appendChild(li);
      });
      ul.querySelectorAll("[data-dismiss]").forEach(b => b.addEventListener("click", async () => {
        b.disabled = true;
        await fetch("/dismiss", { method:"POST", body: JSON.stringify({ id: b.dataset.dismiss }) });
        loadReport();
      }));
    }
    const gbox = el("gmailbox");
    const drafts = r.gmail_drafts || [];
    el("gmailbadge").textContent = drafts.length;
    el("gmailbadge").dataset.n = String(drafts.length);
    if (!drafts.length) { gbox.hidden = true; el("gmaillist").innerHTML = ""; }
    else {
      gbox.hidden = false;
      el("gmaillist").innerHTML = drafts.slice(0, 12).map(d => {
        const link = d.href
          ? '<a href="' + esc(d.href) + '" target="_blank" rel="noopener">Open draft</a>'
          : '<a href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noopener">Gmail drafts</a>';
        const body = d.body
          ? '<details><summary>Preview</summary><pre style="margin-top:6px;font-size:.78rem;white-space:pre-wrap">' +
            esc(d.body.slice(0, 400)) + (d.body.length > 400 ? "…" : "") + '</pre></details>'
          : "";
        return '<li><div>' + esc(d.text) + '</div><div class="row-actions">' + link + '</div>' + body + '</li>';
      }).join("");
    }
    const bbox = el("briefsbox");
    const briefs = r.briefs_waiting || [];
    el("briefsbadge").textContent = briefsN;
    el("briefsbadge").dataset.n = String(briefsN);
    if (!briefsN) {
      bbox.hidden = true; el("briefslist").innerHTML = "";
      const jb0 = el("jump-briefs"); if (jb0) jb0.hidden = true;
    } else {
      bbox.hidden = false;
      el("briefslist").innerHTML = briefs.slice(0, 12).map(b => {
        const name = esc(b.name || b.file || "Prospect");
        const company = b.company ? esc(b.company) : "";
        const track = b.track ? '<span class="tag">' + esc(b.track) + '</span>' : "";
        const link = b.file
          ? '<a class="btn btn-quiet btn-sm" href="/brief/' + encodeURIComponent(b.file) + '">Open brief</a>'
          : "";
        return '<li class="person-row"><div class="who"><strong>' + name + '</strong>' +
          (company ? '<div class="meta">' + company + '</div>' : '') + '</div>' +
          track + link + '</li>';
      }).join("");
    }
    const jn = el("jumpnav");
    if (jn) {
      jn.hidden = false;
      const jb = el("jump-briefs"); if (jb) jb.hidden = !briefsN;
      const je = el("jump-errors"); if (je) je.hidden = !(r.errors || []).length;
    }
    const abox = el("actionsbox");
    const actions = r.action_items || [];
    if (actions.length) {
      abox.hidden = false;
      el("actionslist").innerHTML = actions.map(a => "<li>" + esc(a) + "</li>").join("");
    } else {
      abox.hidden = true;
      el("actionslist").innerHTML = "";
    }
    const ebox = el("errorsbox");
    const errs = r.errors || [];
    const je = el("jump-errors"); if (je) je.hidden = !errs.length;
    if (!errs.length) {
      ebox.hidden = true; el("errorslist").innerHTML = "";
      const lede0 = el("errors-lede"); if (lede0) lede0.textContent = "";
    } else {
      ebox.hidden = false;
      const marked = [];
      const limits = [];
      const other = [];
      errs.forEach(e => {
        const s = String(e || "");
        const m = s.match(/^([^:]+):\\s*LLM marked down/i);
        if (m) marked.push(m[1].trim());
        else if (/rate\\/session limit|session limit/i.test(s)) limits.push(s);
        else other.push(s);
      });
      let lede = "";
      if (limits.length || marked.length) {
        lede = "Claude hit a session limit, so research/draft steps were skipped.";
        if (marked.length) lede += " Skipped: " + marked.slice(0, 6).join(", ")
          + (marked.length > 6 ? " +" + (marked.length - 6) + " more" : "") + ".";
        lede += " Usage usually resets on the time shown in Claude Usage — then Run again.";
      } else {
        lede = "These failed during the last run. Fix or retry as needed.";
      }
      const ledeEl = el("errors-lede"); if (ledeEl) ledeEl.textContent = lede;
      const rows = [];
      limits.slice(0, 2).forEach(s => {
        const short = s.replace(/^[^:]+:\\s*/, "").replace(/rate\\/session limit, skipping all LLM stages this run:\\s*/i, "");
        rows.push("<li><strong>Session limit</strong> — " + esc(short.slice(0, 180)) + (short.length > 180 ? "…" : "") + "</li>");
      });
      other.slice(0, 5).forEach(s => rows.push("<li>" + esc(s) + "</li>"));
      if (!rows.length && marked.length) {
        rows.push("<li>No individual stage errors beyond the session limit above.</li>");
      }
      el("errorslist").innerHTML = rows.join("");
    }
  } catch (_) {}
}

async function loadHistory() {
  try {
    const rows = await (await fetch("/history")).json();
    el("done-count").textContent = rows.length;
    const ul = el("donelist");
    if (!rows.length) { ul.innerHTML = '<li class="sub">Nothing resolved yet today.</li>'; return; }
    ul.innerHTML = rows.map(it => {
      const when = (it.resolved || "").slice(11, 16) || "—";
      const who = esc(it.name) + " · " + esc(it.company);
      const undo = ' · <button type="button" class="linkish" data-undo="' + esc(it.id) + '">Undo</button>';
      if (it.status === "approved") {
        const link = it.draft_link
          ? '<a href="' + esc(it.draft_link) + '" target="_blank" rel="noopener">Open draft</a> · '
          : "";
        return '<li><span class="ok">Approved</span> ' + who + ' · ' + when + ' · ' + link +
          '<button type="button" class="linkish" data-undo="' + esc(it.id) + '">Undo</button></li>';
      }
      const snooze = it.skip_until === "forever" ? " · forever"
        : (it.skip_until ? " · until " + esc(it.skip_until) : "");
      return '<li><span class="skip">Skipped</span> ' + who + snooze + ' · ' + when + undo + '</li>';
    }).join("");
    ul.querySelectorAll("[data-undo]").forEach(b => b.addEventListener("click", () => undoItem(b.dataset.undo)));
  } catch (_) {}
}

async function poll() {
  try {
    const s = await (await fetch("/status")).json();
    el("dot").className = "dot" + (s.running ? " live" : "");
    const stageLabel = s.running ? (s.stage || "running") : "idle";
    el("stage").textContent = stageLabel;
    el("stagechip").textContent = s.running
      ? (stageLabel + (s.detail ? " · " + s.detail : ""))
      : "idle";
    el("detail").textContent = s.detail || "—";
    if (!s.running && s.detail) {
      el("lastrun-text").textContent = s.detail;
    } else if (s.running) {
      el("lastrun-text").textContent = "running now…";
    }
    const st = el("stream");
    if (s.stream) { st.textContent = s.stream; st.hidden = false; } else st.hidden = true;
    if (s.rundown) el("rundown").textContent = s.rundown;
    const t = s.tokens || {};
    el("tokpct").textContent = t.limit_hit ? "LIMIT" : ((t.pct || 0) + "%");
    el("tokdetail").textContent = t.limit_hit
      ? "Anthropic session limit hit · resets " + (t.limit_reset || "soon")
      : (t.used || 0).toLocaleString() + " / " + (t.budget || 0).toLocaleString()
        + " tokens · " + (t.calls || 0) + " calls since " + (t.window_started || "—");
    el("tokmeter").value = Math.min(100, t.pct || 0);
    el("tokcard").className = "block compact tok" + (t.limit_hit || t.pct >= 100 ? " bad" : (t.pct >= 60 ? " warn" : ""));
    const feed = el("feed");
    feed.innerHTML = "";
    (s.events || []).slice().reverse().slice(0, 40).forEach(e => {
      const li = document.createElement("li");
      li.innerHTML = '<span class="t">' + esc(e.ts) + '</span>' +
        (e.stream ? '<span class="s">' + esc(e.stream) + '</span>' : '') +
        '<span>' + esc(e.detail || e.stage || "") + '</span>';
      feed.appendChild(li);
    });
    if (!(s.events || []).length) feed.innerHTML = "<li>no events yet — hit Run now</li>";
    el("run").disabled = !!s.running;
    el("stop").disabled = !s.running;
    updatePipeline(s.stage, !!s.running);
    if (!wasRunning && s.running) showPanel("activity");
    if (wasRunning && !s.running) {
      el("dash").src = "/dashboard?t=" + Date.now();
      await loadReport();
      const summary = s.detail || "Run finished";
      const t = toast(esc(summary) + ' · <button type="button" class="linkish">Overview</button>', { timeout: 12000 });
      t.querySelector(".linkish")?.addEventListener("click", () => showPanel("overview"));
      showPanel(queueAll.length ? "approvals" : "overview");
    }
    wasRunning = !!s.running;
  } catch (_) { el("detail").textContent = "panel server unreachable"; }
}

async function loadQueue() {
  try {
    const q = await (await fetch("/queue")).json();
    queueAll = sortQueue(q);
    const nReply = queueAll.filter(i => i.kind === "reply").length;
    const nOut = queueAll.filter(i => i.kind === "outreach").length;
    el("qsplit").textContent = queueAll.length
      ? (nReply ? nReply + " repl" + (nReply === 1 ? "y" : "ies") : "")
        + (nReply && nOut ? " · " : "")
        + (nOut ? nOut + " outreach" : "")
      : "";
    const filtered = filterQueue(queueAll);
    const sig = JSON.stringify(filtered.map(i => [i.id, i.subject, i.body_html, i.why, i.track]));
    queueItems = filtered;
    const badge = el("qbadge");
    badge.textContent = filtered.length;
    badge.dataset.n = String(filtered.length);
    if (sig === lastQueueSig) return;
    lastQueueSig = sig;

    const openIds = new Set(
      [...document.querySelectorAll(".q-item details[open]")].map(d => d.closest(".q-item")?.dataset.id)
    );
    const drafts = {};
    document.querySelectorAll(".q-item").forEach(li => {
      drafts[li.dataset.id] = {
        subject: li.querySelector(".subj-edit")?.value,
        email: li.querySelector(".email-edit")?.value,
        body: li.querySelector(".body-edit")?.innerHTML,
      };
    });

    const ul = el("queue");
    if (!filtered.length) {
      const searching = queueSearch || queueFilter !== "all";
      ul.innerHTML = searching
        ? '<li class="empty"><strong>No matches</strong>Try another filter or clear search.</li>'
        : '<li class="empty"><strong>Nothing waiting</strong>Run triage to sync inbox and draft replies.' +
          '<br><button type="button" class="btn btn-primary cta" id="empty-triage">Start Triage</button></li>';
      focusId = null;
      el("empty-triage")?.addEventListener("click", () => {
        runStage = "triage";
        document.querySelectorAll("#run-modes .chip").forEach(x =>
          x.classList.toggle("active", x.dataset.stage === "triage"));
        el("run").click();
      });
      return;
    }
    ul.innerHTML = "";
    filtered.forEach((item, idx) => {
      const draft = drafts[item.id] || {};
      const subject = draft.subject != null ? draft.subject : item.subject;
      const email = draft.email != null ? draft.email : (item.email || "");
      const body = draft.body != null ? draft.body : sanitizeHtml(item.body_html);
      const threadHref = item.thread_id
        ? ("https://mail.google.com/mail/u/0/#inbox/" + encodeURIComponent(item.thread_id))
        : "";
      const ctx = contextHtml(item);
      const li = document.createElement("li");
      li.className = "q-item";
      li.dataset.id = item.id;
      li.innerHTML =
        '<div class="q-meta">' +
          '<span class="stream" style="margin:0">' + esc(item.track) + '</span>' +
          '<strong>' + esc(item.name) + '</strong>' +
          '<span class="sub">' + esc(item.company) + (item.kind ? ' · ' + esc(item.kind) : '') + '</span>' +
        '</div>' +
        (item.why ? '<p class="q-why">' + esc(item.why) + '</p>' : '') +
        ctx +
        (threadHref ? '<a class="thread-link" href="' + esc(threadHref) + '" target="_blank" rel="noopener">Open thread in Gmail</a>' : '') +
        '<div class="q-fields">' +
          '<div><label for="email-' + esc(item.id) + '">To</label>' +
            '<input class="email-edit" id="email-' + esc(item.id) + '" type="email" value="' + esc(email) + '" autocomplete="off"></div>' +
          '<div><label for="subj-' + esc(item.id) + '">Subject</label>' +
            '<input class="subj-edit" id="subj-' + esc(item.id) + '" value="' + esc(subject) + '"></div>' +
        '</div>' +
        '<details class="preview"' + (openIds.has(item.id) ? " open" : "") + '>' +
          '<summary>Edit email body</summary>' +
          '<div class="body-edit" contenteditable="true" spellcheck="true">' + body + '</div>' +
          '<p class="edit-hint">Paste is plain text. Edits autosave; Approve creates the Gmail draft.</p></details>' +
        '<div class="q-actions">' +
          '<button type="button" class="btn btn-good approve" data-a="approve" data-id="' + esc(item.id) + '">Approve → Gmail draft</button>' +
          '<span class="skip-menu">' +
            '<button type="button" data-a="skip" data-until="3" data-id="' + esc(item.id) + '">Skip 3d</button>' +
            '<button type="button" data-a="skip" data-until="7" data-id="' + esc(item.id) + '">Skip 7d</button>' +
            '<button type="button" data-a="skip" data-until="forever" data-id="' + esc(item.id) + '">Skip ∞</button>' +
          '</span>' +
          '<button type="button" class="btn btn-quiet skip" data-copy="' + esc(item.id) + '">Copy body</button>' +
        '</div>';
      li.addEventListener("click", ev => {
        if (ev.target.closest("button, a, summary, details, input, [contenteditable]")) return;
        setFocus(idx);
      });
      ul.appendChild(li);
    });
    ul.querySelectorAll(".subj-edit, .email-edit").forEach(inp => {
      inp.addEventListener("input", () => scheduleSave(inp.closest(".q-item").dataset.id));
    });
    ul.querySelectorAll(".body-edit").forEach(ed => {
      ed.addEventListener("paste", ev => {
        ev.preventDefault();
        const text = (ev.clipboardData || window.clipboardData).getData("text/plain");
        document.execCommand("insertText", false, text);
      });
      ed.addEventListener("input", () => scheduleSave(ed.closest(".q-item").dataset.id));
    });
    ul.querySelectorAll("button[data-a]").forEach(b => b.addEventListener("click", () => {
      const until = b.dataset.until;
      act(b.dataset.id, b.dataset.a, b, until != null
        ? { skipUntil: until === "forever" ? "forever" : Number(until) }
        : {});
    }));
    ul.querySelectorAll("button[data-copy]").forEach(b => b.addEventListener("click", async () => {
      const li = b.closest(".q-item");
      const html = li.querySelector(".body-edit")?.innerHTML || "";
      const text = li.querySelector(".body-edit")?.innerText || "";
      try {
        await navigator.clipboard.write([
          new ClipboardItem({
            "text/html": new Blob([html], { type: "text/html" }),
            "text/plain": new Blob([text], { type: "text/plain" }),
          })
        ]);
      } catch (_) {
        try { await navigator.clipboard.writeText(text); } catch (__) {}
      }
      toast("Body copied");
    }));
    if (!filtered.some(i => i.id === focusId)) focusId = filtered[0]?.id || null;
    setFocus(focusedIndex());
  } catch (_) {}
}

document.addEventListener("keydown", ev => {
  if (ev.key === "Escape") {
    if (helpIsOpen()) { closeHelp(); ev.preventDefault(); return; }
    if (ev.target === el("qsearch")) { el("qsearch").blur(); return; }
  }
  if (ev.target.matches("input, textarea, select, [contenteditable]") || ev.metaKey || ev.ctrlKey || ev.altKey) {
    return;
  }
  const approvalsOn = el("panel-approvals").classList.contains("active");
  const key = ev.key.toLowerCase();
  if (key === "?" || (ev.shiftKey && key === "/")) { ev.preventDefault(); toggleHelp(); return; }
  if (helpIsOpen()) return; /* ignore other shortcuts while help is open */
  if (key === "/") { ev.preventDefault(); showPanel("approvals"); el("qsearch").focus(); return; }
  if (key === "1") { showPanel("approvals"); return; }
  if (key === "2") { showPanel("overview"); return; }
  if (key === "3") { showPanel("activity"); return; }
  if (key === "4") { showPanel("report"); return; }
  if (!approvalsOn || !queueItems.length) return;
  if (key === "j" || key === "arrowdown") { ev.preventDefault(); setFocus(focusedIndex() + 1); }
  else if (key === "k" || key === "arrowup") { ev.preventDefault(); setFocus(focusedIndex() - 1); }
  else if (key === "a") {
    ev.preventDefault();
    const id = queueItems[focusedIndex()]?.id;
    if (id) act(id, "approve", null, { confirmApprove: true });
  } else if (key === "s") {
    ev.preventDefault();
    const id = queueItems[focusedIndex()]?.id;
    if (id) act(id, "skip", null, { skipUntil: 7 });
  } else if (key === "o") {
    ev.preventDefault();
    const item = document.querySelectorAll(".q-item")[focusedIndex()];
    const d = item?.querySelector("details.preview");
    if (d) d.open = !d.open;
  }
});

el("briefs-organize")?.addEventListener("click", () => {
  runStage = "organize";
  document.querySelectorAll("#run-modes .chip").forEach(x =>
    x.classList.toggle("active", x.dataset.stage === "organize"));
  el("run").click();
});

document.querySelectorAll("#run-modes .chip").forEach(c => {
  c.addEventListener("click", () => {
    runStage = c.dataset.stage || "";
    document.querySelectorAll("#run-modes .chip").forEach(x =>
      x.classList.toggle("active", x === c));
  });
});

el("run").addEventListener("click", async () => {
  const res = await fetch("/run", {
    method:"POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stage: runStage || null }),
  });
  if (res.status === 409) toast("Already running");
  else if (!res.ok) toast("Could not start run");
  else {
    const label = runStage === "triage" ? "Triage" : (runStage || "Full");
    toast(label + " run started");
    poll();
  }
});
el("stop").addEventListener("click", async () => {
  const res = await fetch("/stop", { method:"POST" });
  if (!res.ok) toast("Could not stop");
  else { toast("Stop requested"); poll(); }
});

(async () => {
  const hash = (location.hash || "").replace("#", "");
  let tab = "approvals";
  try { tab = localStorage.getItem("emailcrm-tab") || "approvals"; } catch (_) {}
  if (["approvals", "overview", "activity", "report"].includes(hash)) tab = hash;
  await loadQueue();
  await loadReport();
  await loadHistory();
  if (!["approvals", "overview", "activity", "report"].includes(hash)) {
    if (queueAll.length) tab = "approvals";
    else if (needsCount > 0 || Number(el("overviewbadge")?.dataset.n || 0) > 0) tab = "overview";
  }
  showPanel(tab);
  poll();
  setInterval(poll, 2000);
  setInterval(loadQueue, 5000);
  setInterval(loadReport, 15000);
  setInterval(loadHistory, 20000);
})();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass

    def _dir_page(self, title, folder, pattern="*"):
        import html as html_mod
        rows = []
        is_briefs = folder == config.QUEUE_PROSPECTS
        if folder.exists():
            files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in files[:80]:
                if p.is_file():
                    rel = p.name
                    if is_briefs and p.suffix == ".json":
                        href = f"/brief/{html_mod.escape(rel, quote=True)}"
                    else:
                        href = f"/files/raw?p={html_mod.escape(str(p), quote=True)}"
                    rows.append(f'<li><a href="{href}">{html_mod.escape(rel)}</a></li>')
        body = ("<ul>" + "".join(rows) + "</ul>") if rows else "<p>No files yet.</p>"
        return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_mod.escape(title)}</title>
<style>body{{font:15px/1.55 "Plus Jakarta Sans",system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;color:#15241e;background:#f7faf8}}
a{{color:#0c6b54}} ul{{padding-left:1.2rem}} li{{margin:6px 0}}</style></head>
<body><h1>{html_mod.escape(title)}</h1>{body}
<p><a href="/#overview">← Panel</a></p></body></html>"""

    def _safe_local_file(self, path_str):
        """Only serve files under EmailCRM digest / briefs / logs dirs."""
        try:
            p = Path(path_str).expanduser().resolve()
        except Exception:
            return None
        allowed_roots = []
        for root in (config.DIGEST_DIR, config.QUEUE_PROSPECTS, config.LOG_DIR, config.ROOT):
            try:
                allowed_roots.append(root.expanduser().resolve())
            except Exception:
                allowed_roots.append(root)
        for root in allowed_roots:
            try:
                p.relative_to(root)
                return p if p.is_file() else None
            except ValueError:
                continue
        return None

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path.startswith("/dashboard"):
            dash = config.ROOT / "dashboard.html"
            if dash.exists():
                self._send(200, dash.read_text(), "text/html; charset=utf-8")
            else:
                self._send(200, """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>No dashboard yet</title>
<style>body{font:15px/1.55 "Plus Jakarta Sans",system-ui,sans-serif;padding:48px 24px;color:#15241e;
background:#f7faf8;text-align:center}strong{display:block;font-size:1.2rem;margin-bottom:8px}</style>
</head><body><strong>No dashboard yet</strong>Run the pipeline once to generate a report.</body></html>""",
                           "text/html; charset=utf-8")
        elif path == "/queue":
            self._send(200, json.dumps(queue_store.pending()))
        elif path == "/history":
            rows = [{
                "id": i["id"], "name": i["name"], "company": i["company"],
                "status": i["status"], "resolved": i.get("resolved"),
                "draft_link": i.get("draft_link"),
                "skip_until": i.get("skip_until"),
            } for i in queue_store.resolved_today()]
            self._send(200, json.dumps(rows))
        elif path.startswith("/brief/"):
            from urllib.parse import unquote, urlparse, parse_qs
            parsed = urlparse(self.path)
            name = unquote(parsed.path.split("/brief/", 1)[1])
            want_raw = "raw" in parse_qs(parsed.query)
            if ".." in name or "/" in name or not name:
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            brief = config.QUEUE_PROSPECTS / name
            if not brief.is_file():
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            raw = brief.read_text(errors="replace")
            if brief.suffix == ".json" and not want_raw:
                try:
                    data = json.loads(raw)
                except Exception:
                    data = None
                if isinstance(data, dict):
                    self._send(200, _brief_html(data, name), "text/html; charset=utf-8")
                    return
            if brief.suffix == ".json":
                try:
                    raw = json.dumps(json.loads(raw), indent=2)
                except Exception:
                    pass
                self._send(200, raw, "application/json; charset=utf-8")
            else:
                self._send(200, raw, "text/plain; charset=utf-8")
        elif path == "/status":
            if status.STATUS_FILE.exists():
                self._send(200, status.STATUS_FILE.read_text())
            else:
                self._send(200, json.dumps({"running": False, "stage": "idle",
                                            "tokens": status.tokens_snapshot()}))
        elif path == "/report":
            report = config.STATE_DIR / "last_report.json"
            if report.exists():
                self._send(200, _filter_report(report.read_text()))
            else:
                self._send(200, json.dumps({"needs_n": 0, "needs_you": [], "drafts_n": 0,
                                            "gmail_drafts": [], "gmail_drafts_n": 0,
                                            "errors_n": 0, "errors": [], "briefs_n": 0}))
        elif path == "/files/digest":
            from datetime import date
            today = config.DIGEST_DIR / f"{date.today().isoformat()}.md"
            if today.exists():
                self._send(200, today.read_text(), "text/markdown; charset=utf-8")
            else:
                self._send(200, self._dir_page("Digests", config.DIGEST_DIR, "*.md"),
                           "text/html; charset=utf-8")
        elif path == "/files/prospects":
            self._send(200, self._dir_page("Prospect briefs", config.QUEUE_PROSPECTS, "*.json"),
                       "text/html; charset=utf-8")
        elif path == "/files/logs":
            self._send(200, self._dir_page("Run logs", config.LOG_DIR, "*"),
                       "text/html; charset=utf-8")
        elif path == "/files/raw":
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            target = (qs.get("p") or [None])[0]
            safe = self._safe_local_file(target) if target else None
            if not safe:
                self._send(404, "not found", "text/plain; charset=utf-8")
            else:
                ctype = "text/markdown; charset=utf-8" if safe.suffix == ".md" else "text/plain; charset=utf-8"
                self._send(200, safe.read_text(errors="replace"), ctype)
        else:
            self._send(404, "{}")

    def do_POST(self):
        if self.path == "/run":
            if config.LOCK_FILE.exists():
                self._send(409, '{"error":"already running"}')
                return
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}") if length else {}
            stage = body.get("stage") or None
            allowed = {None, "triage", "inbox", "reply", "scout", "organize",
                       "bounce", "followup", "digest", "sync", "nudge", "prospect"}
            if stage not in allowed:
                self._send(400, '{"error":"invalid stage"}')
                return
            cmd = [str(PYTHON), str(RUN_PY)]
            if stage:
                cmd += ["--stage", stage]
            subprocess.Popen(cmd, cwd=str(config.AUTOPILOT),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._send(200, json.dumps({"ok": True, "stage": stage or "full"}))
        elif self.path == "/stop":
            status.STOP_FLAG.touch()
            try:
                if status.STATUS_FILE.exists():
                    pid = json.loads(status.STATUS_FILE.read_text()).get("pid")
                    if pid:
                        subprocess.run(["pkill", "-TERM", "-P", str(pid)], timeout=10)
                        subprocess.run(["kill", "-TERM", str(pid)], timeout=10)
                subprocess.run(["pkill", "-TERM", "-f", "autopilot/run.py"], timeout=10)
            except Exception:
                pass
            self._send(200, '{"ok":true}')
        elif self.path == "/save":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
            item = queue_store.update_pending(
                body.get("id"),
                subject=body.get("subject"),
                email=body.get("email"),
                body_html=body.get("body_html"),
            )
            if not item:
                self._send(404, '{"error":"item not found"}')
            else:
                self._send(200, '{"ok":true}')
        elif self.path == "/undo":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
            item_id = body.get("id")
            # try skip reopen first
            item = queue_store.reopen(item_id)
            if item:
                self._send(200, json.dumps({"ok": True, "undid": "skipped"}))
                return
            item, draft_id, contact_id = queue_store.unapprove(item_id)
            if not item:
                self._send(404, '{"error":"nothing to undo"}')
                return
            try:
                import crm
                import gmail
                if draft_id:
                    try:
                        gmail.delete_draft(draft_id)
                    except Exception:
                        pass
                if contact_id:
                    contacts = crm.load()
                    contacts = [c for c in contacts if c.get("id") != contact_id]
                    crm.save(contacts)
                elif item.get("kind") == "outreach" and item.get("email"):
                    # fallback: remove drafted contact matching email from today
                    contacts = crm.load()
                    email = (item.get("email") or "").lower()
                    contacts = [c for c in contacts
                                if not (c.get("status") == "drafted"
                                        and (c.get("email") or "").lower() == email
                                        and c.get("gmail_draft_id") == draft_id)]
                    crm.save(contacts)
            except Exception as e:
                self._send(200, json.dumps({"ok": True, "undid": "approved",
                                            "warn": str(e)[:200]}))
                return
            self._send(200, json.dumps({"ok": True, "undid": "approved"}))
        elif self.path == "/dismiss":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
            item_id = body.get("id")
            if not item_id:
                self._send(400, '{"error":"id required"}')
                return
            ids = _load_dismissed()
            ids.add(item_id)
            _save_dismissed(ids)
            self._send(200, '{"ok":true}')
        elif self.path in ("/approve", "/skip"):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
            item_id = body.get("id")
            items = [i for i in queue_store.pending() if i["id"] == item_id]
            if not items:
                self._send(404, '{"error":"item not found or already resolved"}')
                return
            item = items[0]
            if self.path == "/skip":
                raw = body.get("skip_until", 7)
                until = queue_store.skip_until_days(
                    "forever" if raw == "forever" else raw)
                queue_store.resolve(item_id, "skipped", skip_until=until)
                self._send(200, json.dumps({"ok": True, "skip_until": until}))
                return
            try:
                import crm
                import gmail
                subject = (body.get("subject") or item["subject"] or "").strip() or item["subject"]
                body_html = body.get("body_html") if body.get("body_html") is not None else item["body_html"]
                to_email = (body.get("email") or item.get("email") or "").strip()
                if not to_email:
                    self._send(400, '{"error":"To address is required"}')
                    return
                if item["kind"] == "reply" and item.get("thread_id"):
                    draft = gmail.create_reply_draft(
                        to=to_email, subject=subject, body_html=body_html,
                        thread_id=item["thread_id"], in_reply_to=item.get("in_reply_to"))
                else:
                    draft = gmail.create_draft(
                        subject=subject, body_html=body_html, to=to_email)
                link = gmail.draft_link(draft.get("thread_id"))
                contact_id = None
                if item["kind"] == "outreach":
                    from datetime import date, timedelta
                    contacts = crm.load()
                    crm.migrate(contacts)
                    contact_id = f"{item['name'].lower().replace(' ', '-')}-{date.today().year}"
                    contacts.append({
                        "id": contact_id,
                        "name": item["name"], "email": to_email,
                        "linkedin_url": item["meta"].get("linkedin"),
                        "company": item["company"], "role": None,
                        "email_type": item["meta"].get("email_type"),
                        "sent_at": None, "drafted_at": crm.now_iso(),
                        "status": "drafted", "gmail_draft_id": draft["draft_id"],
                        "gmail_thread_id": draft.get("thread_id"), "gmail_message_id": None,
                        "follow_up_due": (date.today() + timedelta(days=7)).isoformat(),
                        "hook_used": item.get("why"), "notes": "queued by autopilot organizer",
                        "follow_up_count": 0, "follow_up_draft_id": None,
                        "follow_up_drafted_at": None,
                        "autopilot": {"thread_backfill": None, "bounce_retry": None,
                                      "last_touched": crm.now_iso(), "history": []},
                    })
                    crm.save(contacts)
                queue_store.resolve(item_id, "approved", gmail_draft_id=draft["draft_id"],
                                    draft_link=link, contact_id=contact_id)
                self._send(200, json.dumps({
                    "ok": True,
                    "draft_id": draft["draft_id"],
                    "draft_link": link,
                }))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)[:300]}))
        else:
            self._send(404, "{}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", config.PANEL_PORT), Handler)
    print(f"panel on http://localhost:{config.PANEL_PORT}")
    server.serve_forever()
