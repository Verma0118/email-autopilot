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

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EmailCRM Autopilot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@450;550;650;700&family=Fraunces:opsz,wght@9..144,550;9..144,650&display=swap" rel="stylesheet">
<style>
:root {
  --bg0:#f3f6f4; --bg1:#e8efeb; --surface:#fbfcfb; --surface2:#f0f4f1;
  --ink:#14201a; --ink2:#5c6b63; --ink3:#8a968f;
  --line:rgba(20,32,26,.09); --line2:rgba(20,32,26,.16);
  --accent:#0f6e56; --accent-ink:#fff; --accent-soft:rgba(15,110,86,.1);
  --good:#177245; --good-bg:rgba(23,114,69,.1);
  --warn:#9a6700; --warn-bg:rgba(154,103,0,.12);
  --bad:#b42318; --bad-bg:rgba(180,35,24,.09);
  --ease:cubic-bezier(0.23,1,0.32,1);
  --font:"Figtree", "Segoe UI", sans-serif;
  --display:"Fraunces", Georgia, serif;
  --radius:14px;
  --chrome:64px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg0:#0c1210; --bg1:#141c18; --surface:#151c19; --surface2:#1c2521;
    --ink:#e8eee9; --ink2:#9aaba2; --ink3:#6d7c74;
    --line:rgba(232,238,233,.08); --line2:rgba(232,238,233,.14);
    --accent:#3dba8f; --accent-ink:#062016; --accent-soft:rgba(61,186,143,.14);
    --good:#3ecf8e; --good-bg:rgba(62,207,142,.12);
    --warn:#e8b339; --warn-bg:rgba(232,179,57,.12);
    --bad:#f07178; --bad-bg:rgba(240,113,120,.12);
  }
}
* { box-sizing:border-box; margin:0; }
html, body { height:100%; }
body {
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(15,110,86,.09), transparent 55%),
    radial-gradient(900px 420px at 100% 0%, rgba(20,32,26,.05), transparent 50%),
    linear-gradient(180deg, var(--bg0), var(--bg1));
  color:var(--ink);
  font:15px/1.5 var(--font);
  font-weight:450;
  -webkit-font-smoothing:antialiased;
  min-height:100vh;
}
@media (prefers-color-scheme: dark) {
  body {
    background:
      radial-gradient(1000px 480px at 8% -8%, rgba(61,186,143,.12), transparent 55%),
      radial-gradient(800px 400px at 100% 0%, rgba(61,186,143,.05), transparent 45%),
      linear-gradient(180deg, var(--bg0), var(--bg1));
  }
}
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; text-underline-offset:3px; }
button, .tab {
  font:inherit; font-weight:650; border:0; border-radius:10px;
  cursor:pointer; min-height:40px; transition:transform 160ms var(--ease), opacity .2s, background .2s;
}
button:active, .tab:active { transform:scale(0.97); }
button:disabled { opacity:.45; cursor:default; transform:none; }
button:focus-visible, .tab:focus-visible, a:focus-visible, summary:focus-visible {
  outline:2px solid var(--accent); outline-offset:2px;
}

/* —— chrome —— */
.chrome {
  position:sticky; top:0; z-index:20;
  backdrop-filter:blur(14px) saturate(1.2);
  background:color-mix(in srgb, var(--bg0) 82%, transparent);
  border-bottom:1px solid var(--line);
}
.chrome-inner {
  max-width:920px; margin:0 auto; padding:12px 20px 0;
  display:flex; flex-direction:column; gap:10px;
}
.toprow {
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
}
.brand {
  display:flex; align-items:center; gap:10px; flex:1; min-width:160px;
}
.dot {
  width:9px; height:9px; border-radius:50%; background:var(--ink3); flex:none;
  transition:background .25s, box-shadow .25s;
}
.dot.live { background:var(--good); box-shadow:0 0 0 4px var(--good-bg); }
.brand h1 {
  font-family:var(--display); font-size:1.2rem; font-weight:650;
  letter-spacing:-.02em; line-height:1.1;
}
.stagechip {
  font-size:.78rem; font-weight:650; color:var(--ink2);
  background:var(--surface); border:1px solid var(--line);
  border-radius:999px; padding:5px 11px; max-width:280px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
#run { background:var(--accent); color:var(--accent-ink); padding:9px 18px; }
#stop { background:var(--bad-bg); color:var(--bad); padding:9px 16px; }
.run-modes { display:flex; gap:4px; }
.run-modes .chip { padding:5px 10px; min-height:30px; font-size:.72rem; }
.run-modes .chip.active { background:var(--accent); color:var(--accent-ink); border-color:transparent; }

.tabs {
  display:flex; gap:2px; overflow-x:auto; scrollbar-width:none;
  margin:0 -4px; padding:0 4px 10px;
}
.tabs::-webkit-scrollbar { display:none; }
.tab {
  background:transparent; color:var(--ink2); padding:8px 14px; min-height:36px;
  border-radius:10px; display:inline-flex; align-items:center; gap:7px;
  white-space:nowrap;
}
.tab:hover { color:var(--ink); background:color-mix(in srgb, var(--surface) 70%, transparent); }
.tab[aria-selected="true"] {
  color:var(--accent); background:var(--accent-soft);
}
.badge {
  font-size:.7rem; font-weight:700; font-variant-numeric:tabular-nums;
  background:var(--accent); color:var(--accent-ink);
  border-radius:999px; min-width:1.35rem; height:1.35rem;
  display:inline-flex; align-items:center; justify-content:center; padding:0 5px;
}
.tab[aria-selected="true"] .badge { background:var(--accent); }
.badge[data-n="0"] { display:none; }

/* —— layout —— */
main {
  max-width:920px; margin:0 auto; padding:20px 20px 72px;
}
.panel { display:none; animation:rise 320ms var(--ease); }
.panel.active { display:block; }
@keyframes rise {
  from { opacity:0; transform:translateY(6px); }
  to { opacity:1; transform:none; }
}
@media (prefers-reduced-motion: reduce) {
  .panel { animation:none; }
  button, .tab { transition:none; }
}

.section-head {
  display:flex; align-items:baseline; justify-content:space-between;
  gap:12px; margin-bottom:12px; flex-wrap:wrap;
}
.section-head h2 {
  font-family:var(--display); font-size:1.35rem; font-weight:550;
  letter-spacing:-.02em;
}
.hint { color:var(--ink3); font-size:.8rem; }
.kbd {
  font-size:.72rem; font-weight:650; color:var(--ink2);
  background:var(--surface); border:1px solid var(--line);
  border-radius:5px; padding:1px 6px; font-family:ui-monospace, monospace;
}

.grid { display:grid; grid-template-columns:1.2fr .8fr; gap:12px; }
@media (max-width:640px) {
  .grid { grid-template-columns:1fr; }
  .stagechip { display:none; }
}

.block {
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--radius); padding:16px 18px;
}
.block .label {
  font-size:.72rem; color:var(--ink3); text-transform:uppercase;
  letter-spacing:.08em; font-weight:650; margin-bottom:6px;
}
.big { font-size:1.2rem; font-weight:650; letter-spacing:-.015em; overflow-wrap:anywhere; }
.sub { color:var(--ink2); font-size:.86rem; margin-top:3px; overflow-wrap:anywhere; }
.stream {
  display:inline-block; background:var(--accent-soft); color:var(--accent);
  font-size:.74rem; font-weight:650; border-radius:999px; padding:2px 10px; margin-top:8px;
}
meter { width:100%; height:10px; margin-top:10px; }
.tok.warn .big { color:var(--warn); }
.tok.bad .big { color:var(--bad); }
.rundown {
  font-size:.95rem; color:var(--ink); line-height:1.55;
  white-space:pre-wrap;
}

/* —— queue —— */
#queue { list-style:none; padding:0; display:flex; flex-direction:column; gap:12px; }
.q-item {
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--radius); padding:16px 18px;
  transition:border-color .2s, box-shadow .2s;
}
.q-item.focused {
  border-color:color-mix(in srgb, var(--accent) 45%, var(--line));
  box-shadow:0 0 0 3px var(--accent-soft);
}
.q-meta {
  display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; margin-bottom:6px;
}
.q-meta strong { font-size:1.05rem; font-weight:650; }
.q-why { color:var(--ink2); font-size:.88rem; margin:4px 0 8px; }
.q-subject { font-size:.88rem; margin-bottom:6px; }
.q-subject span { color:var(--ink2); }
.q-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; align-items:center; }
.q-actions button.approve { background:var(--good-bg); color:var(--good); padding:9px 16px; }
.q-actions button.skip { background:var(--surface2); color:var(--ink2); padding:9px 16px; }
.skip-menu { display:inline-flex; gap:4px; flex-wrap:wrap; }
.skip-menu button {
  font-size:.72rem; font-weight:650; padding:6px 10px; min-height:30px;
  background:var(--surface2); color:var(--ink2); border-radius:8px;
}
details.preview { margin-top:8px; }
details.preview summary {
  cursor:pointer; color:var(--ink2); font-size:.84rem; font-weight:650;
  user-select:none; list-style:none;
}
details.preview summary::-webkit-details-marker { display:none; }
details.preview[open] summary { color:var(--ink); }
blockquote.body {
  border-left:2px solid var(--line2); background:var(--surface2);
  border-radius:0 10px 10px 0; padding:12px 14px; margin-top:8px;
  font-size:.9rem; line-height:1.55; max-width:70ch; color:var(--ink);
}
.empty {
  color:var(--ink2); font-size:.92rem;
  border:1px dashed var(--line2); border-radius:var(--radius);
  padding:28px 20px; text-align:center; background:color-mix(in srgb, var(--surface) 60%, transparent);
}
.empty strong { display:block; font-family:var(--display); font-size:1.15rem;
  color:var(--ink); font-weight:550; margin-bottom:6px; }

/* —— feed —— */
#feed { list-style:none; padding:0; display:flex; flex-direction:column; gap:6px; }
#feed li {
  background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:9px 13px; font-size:.86rem; display:flex; gap:10px; align-items:baseline;
}
#feed .t { color:var(--ink3); font-variant-numeric:tabular-nums; font-size:.76rem; flex:none; }
#feed .s { color:var(--accent); font-weight:650; font-size:.76rem; flex:none; }

/* —— report —— */
.report-wrap {
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--radius); overflow:hidden;
  height:calc(100vh - var(--chrome) - 100px); min-height:480px;
}
#dash { width:100%; height:100%; border:0; display:block; background:var(--surface); }

footer.links {
  margin-top:28px; color:var(--ink3); font-size:.8rem; line-height:1.9;
  border-top:1px solid var(--line); padding-top:14px;
}

/* —— queue edit —— */
.q-subject-row { display:flex; flex-direction:column; gap:4px; margin:8px 0 4px; }
.q-subject-row label { font-size:.72rem; font-weight:650; color:var(--ink3); text-transform:uppercase; letter-spacing:.06em; }
.body-edit {
  border-left:2px solid var(--line2); background:var(--surface2);
  border-radius:0 10px 10px 0; padding:12px 14px; margin-top:8px;
  font-size:.9rem; line-height:1.55; max-width:70ch; color:var(--ink);
  min-height:7rem; outline:none;
}
.body-edit:focus { box-shadow:inset 0 0 0 1px var(--accent); }
.edit-hint { color:var(--ink3); font-size:.76rem; margin-top:4px; }

/* —— needs-you strip —— */
.needs {
  background:var(--accent-soft); border:1px solid transparent;
  border-radius:var(--radius); padding:14px 16px; margin-bottom:12px;
}
.needs h3 {
  font-family:var(--display); font-size:1.05rem; font-weight:550;
  letter-spacing:-.02em; margin-bottom:8px; display:flex; align-items:center; gap:8px;
}
.needs ul { list-style:none; padding:0; display:flex; flex-direction:column; gap:6px; }
.needs li {
  font-size:.88rem; background:var(--surface); border-radius:10px;
  padding:8px 12px; border:1px solid var(--line);
  display:flex; flex-direction:column; gap:6px;
}
.needs .row-actions { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.needs .row-actions a, .needs .row-actions button {
  font-size:.78rem; font-weight:650; min-height:auto; padding:0;
  background:none; border:0; cursor:pointer; color:var(--accent);
}
.needs .row-actions button { color:var(--ink3); }
.needs .go { font-size:.8rem; font-weight:650; margin-top:8px; display:inline-block; }
.errors-box {
  background:var(--bad-bg); border:1px solid transparent;
  border-radius:var(--radius); padding:14px 16px; margin-bottom:12px;
}
.errors-box h3 {
  font-family:var(--display); font-size:1.05rem; font-weight:550;
  color:var(--bad); margin-bottom:8px;
}
.errors-box ul { list-style:none; padding:0; display:flex; flex-direction:column; gap:6px; }
.errors-box li { font-size:.86rem; color:var(--ink); }
.lastrun {
  color:var(--ink2); font-size:.84rem; margin-bottom:12px;
  padding:8px 12px; background:var(--surface); border:1px solid var(--line);
  border-radius:10px;
}
.lastrun strong { color:var(--ink); font-weight:650; }

.q-fields { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:8px 0 4px; }
@media (max-width:640px) { .q-fields { grid-template-columns:1fr; } }
.q-fields label { font-size:.72rem; font-weight:650; color:var(--ink3); text-transform:uppercase; letter-spacing:.06em; display:block; margin-bottom:4px; }
.subj-edit, .email-edit {
  font:inherit; font-weight:550; color:var(--ink); background:var(--surface2);
  border:1px solid var(--line); border-radius:9px; padding:8px 11px; width:100%;
}
.subj-edit:focus-visible, .email-edit:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
.thread-link { font-size:.8rem; font-weight:650; margin:4px 0 0; display:inline-block; }

.filters { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
.chip {
  font:inherit; font-weight:650; font-size:.78rem; padding:6px 12px; min-height:32px;
  border-radius:999px; background:var(--surface); color:var(--ink2);
  border:1px solid var(--line); cursor:pointer;
}
.chip:hover { color:var(--ink); border-color:var(--line2); }
.chip.active { background:var(--accent-soft); color:var(--accent); border-color:transparent; }
.qsplit { color:var(--ink3); font-size:.82rem; margin-left:8px; font-weight:550; }

.urgency-banner {
  background:var(--warn-bg); color:var(--warn); border-radius:10px;
  padding:10px 14px; margin-bottom:12px; font-size:.86rem; font-weight:550;
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
}
.urgency-banner button { color:var(--accent); font-weight:650; background:none; border:0;
  cursor:pointer; min-height:auto; padding:0; text-decoration:underline; }

.context { margin:8px 0 4px; }
.context summary { cursor:pointer; color:var(--ink2); font-size:.82rem; font-weight:650; }
.context pre, .ctx-body {
  margin-top:8px; padding:10px 12px; background:var(--surface2);
  border-radius:0 10px 10px 0; border-left:2px solid var(--line2);
  font-size:.78rem; line-height:1.5; white-space:pre-wrap; max-height:220px; overflow:auto;
  color:var(--ink2);
}

.gmail-drafts {
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--radius); padding:14px 16px; margin-bottom:12px;
}
.gmail-drafts h3 {
  font-family:var(--display); font-size:1.05rem; font-weight:550;
  margin-bottom:8px; display:flex; align-items:center; gap:8px;
}
.gmail-drafts ul { list-style:none; padding:0; display:flex; flex-direction:column; gap:8px; }
.gmail-drafts li {
  font-size:.88rem; padding:10px 12px; border:1px solid var(--line);
  border-radius:10px; background:var(--surface2);
}
.gmail-drafts .row-actions { margin-top:6px; }
.gmail-drafts .row-actions a { font-size:.78rem; font-weight:650; }

.done-today { margin-top:20px; }
.done-today summary {
  cursor:pointer; color:var(--ink2); font-size:.88rem; font-weight:650; padding:6px 0;
}
.done-today ul { list-style:none; padding:8px 0 0; display:flex; flex-direction:column; gap:6px; }
.done-today li {
  font-size:.84rem; color:var(--ink2); padding:8px 12px;
  background:var(--surface); border:1px solid var(--line); border-radius:10px;
}
.done-today .ok { color:var(--good); font-weight:650; }
.done-today .skip { color:var(--ink3); }
.done-today button.linkish, .done-today a {
  color:var(--accent); font-weight:650; background:none; border:0; padding:0;
  min-height:auto; cursor:pointer; text-decoration:underline; font:inherit;
}

/* —— toast —— */
.toast-wrap {
  position:fixed; bottom:20px; left:50%; transform:translateX(-50%);
  z-index:40; display:flex; flex-direction:column; gap:8px; width:min(420px, calc(100% - 32px));
  pointer-events:none;
}
.toast {
  pointer-events:auto; background:var(--ink); color:var(--surface);
  border-radius:12px; padding:12px 14px; font-size:.88rem; font-weight:550;
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  box-shadow:0 8px 28px rgba(20,32,26,.22);
  animation:rise 280ms var(--ease);
}
@media (prefers-color-scheme: dark) {
  .toast { background:var(--surface2); color:var(--ink); border:1px solid var(--line2); }
}
.toast a, .toast button.linkish {
  color:var(--accent); font-weight:650; background:none; border:0; padding:0;
  min-height:auto; cursor:pointer; text-decoration:underline; text-underline-offset:2px;
}
.toast .dismiss { margin-left:auto; color:inherit; opacity:.7; background:none; border:0;
  min-height:auto; padding:2px 6px; cursor:pointer; font-weight:650; }
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
        <div class="run-modes" id="run-modes" title="What to run">
          <button type="button" class="chip active" data-stage="">Full</button>
          <button type="button" class="chip" data-stage="triage">Triage</button>
          <button type="button" class="chip" data-stage="scout">Scout</button>
          <button type="button" class="chip" data-stage="digest">Digest</button>
        </div>
        <button id="run" type="button">Run now</button>
        <button id="stop" type="button">Stop</button>
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
      <h2>Approval queue <span class="qsplit" id="qsplit"></span></h2>
      <p class="hint">Focus <span class="kbd">j</span>/<span class="kbd">k</span> · <span class="kbd">a</span> approve (confirm) · <span class="kbd">s</span> skip · <span class="kbd">o</span> edit body</p>
    </div>
    <p class="urgency-banner" id="urgency-banner" hidden>
      <span id="urgency-text"></span>
      <button type="button" id="urgency-go">Overview →</button>
    </p>
    <div class="filters" id="qfilters">
      <button type="button" class="chip active" data-filter="all">All</button>
      <button type="button" class="chip" data-filter="reply">Replies</button>
      <button type="button" class="chip" data-filter="outreach">Outreach</button>
    </div>
    <ul id="queue"></ul>
    <details class="done-today" id="done-today">
      <summary>Done today (<span id="done-count">0</span>)</summary>
      <ul id="donelist"></ul>
    </details>
  </section>

  <section class="panel" id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" hidden>
    <div class="section-head"><h2>Overview</h2></div>
    <p class="lastrun" id="lastrun">Last run: <strong id="lastrun-text">—</strong></p>
    <div class="needs" id="needsbox" hidden>
      <h3>Needs you <span class="badge" id="needsbadge" data-n="0">0</span></h3>
      <ul id="needslist"></ul>
      <a class="go" href="#report" id="needs-report">Open full report →</a>
    </div>
    <div class="gmail-drafts" id="gmailbox" hidden>
      <h3>Review in Gmail <span class="badge" id="gmailbadge" data-n="0">0</span></h3>
      <ul id="gmaillist"></ul>
    </div>
    <div class="errors-box" id="errorsbox" hidden>
      <h3>Errors last run</h3>
      <ul id="errorslist"></ul>
    </div>
    <div class="grid">
      <div class="block">
        <p class="label">Current activity</p>
        <p class="big" id="stage">idle</p>
        <p class="sub" id="detail">—</p>
        <span class="stream" id="stream" hidden></span>
      </div>
      <div class="block tok" id="tokcard">
        <p class="label">LLM spend (5h window)</p>
        <p class="big" id="tokpct">0%</p>
        <p class="sub" id="tokdetail">—</p>
        <meter id="tokmeter" min="0" max="100" low="59" high="60" optimum="10" value="0"></meter>
        <p class="sub" style="margin-top:8px">Self-metered autopilot budget. Full Claude session usage is at claude.ai → Settings → Usage.</p>
      </div>
    </div>
    <div class="block" style="margin-top:12px">
      <p class="label">Inbox rundown</p>
      <p class="rundown" id="rundown">—</p>
    </div>
  </section>

  <section class="panel" id="panel-activity" role="tabpanel" aria-labelledby="tab-activity" hidden>
    <div class="section-head"><h2>Live feed</h2></div>
    <ul id="feed" aria-live="polite"><li>waiting for status…</li></ul>
  </section>

  <section class="panel" id="panel-report" role="tabpanel" aria-labelledby="tab-report" hidden>
    <div class="section-head">
      <h2>Last run report</h2>
      <p class="hint"><a href="/dashboard" target="_blank" rel="noopener">Open full page</a></p>
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
let lastQueueSig = "";
let wasRunning = false;
let needsCount = 0;
let runStage = "";
const saveTimers = {};

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
}

document.querySelectorAll(".tab").forEach(t => {
  t.addEventListener("click", () => showPanel(t.dataset.panel));
});
el("needs-report").addEventListener("click", ev => {
  ev.preventDefault();
  showPanel("report");
});
el("urgency-go").addEventListener("click", () => showPanel("overview"));

document.querySelectorAll("#qfilters .chip").forEach(c => {
  c.addEventListener("click", () => {
    queueFilter = c.dataset.filter;
    document.querySelectorAll("#qfilters .chip").forEach(x =>
      x.classList.toggle("active", x.dataset.filter === queueFilter));
    lastQueueSig = "";
    loadQueue();
  });
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
  if (queueFilter === "reply") return q.filter(i => i.kind === "reply");
  if (queueFilter === "outreach") return q.filter(i => i.kind === "outreach");
  return q;
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
      parts.push('<a href="/brief/' + encodeURIComponent(m.brief_file) + '" target="_blank" rel="noopener">Full brief</a>');
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
    const ob = el("overviewbadge");
    ob.textContent = n + gmailN;
    ob.dataset.n = String(n + gmailN);
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
    const ebox = el("errorsbox");
    const errs = r.errors || [];
    if (errs.length) {
      ebox.hidden = false;
      el("errorslist").innerHTML = errs.slice(0, 8).map(e => "<li>" + esc(e) + "</li>").join("");
    } else {
      ebox.hidden = true;
      el("errorslist").innerHTML = "";
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
    el("tokcard").className = "block tok" + (t.pct >= 100 ? " bad" : (t.pct >= 60 ? " warn" : ""));
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
      const msg = queueAll.length && queueFilter !== "all"
        ? "No " + queueFilter + " items in the queue."
        : "Nothing waiting — approve drafts here after a run.";
      ul.innerHTML = '<li class="empty"><strong>Nothing waiting</strong>' + esc(msg) + '</li>';
      focusId = null;
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
          '<p class="edit-hint">Paste is plain text. Edits apply when you approve.</p></details>' +
        '<div class="q-actions">' +
          '<button type="button" class="approve" data-a="approve" data-id="' + esc(item.id) + '">Approve → Gmail draft</button>' +
          '<span class="skip-menu">' +
            '<button type="button" data-a="skip" data-until="3" data-id="' + esc(item.id) + '">Skip 3d</button>' +
            '<button type="button" data-a="skip" data-until="7" data-id="' + esc(item.id) + '">Skip 7d</button>' +
            '<button type="button" data-a="skip" data-until="forever" data-id="' + esc(item.id) + '">Skip ∞</button>' +
          '</span>' +
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
    if (!filtered.some(i => i.id === focusId)) focusId = filtered[0]?.id || null;
    setFocus(focusedIndex());
  } catch (_) {}
}

document.addEventListener("keydown", ev => {
  if (ev.target.matches("input, textarea, select, [contenteditable]") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const approvalsOn = el("panel-approvals").classList.contains("active");
  const key = ev.key.toLowerCase();
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
  let tab = "approvals";
  try { tab = localStorage.getItem("emailcrm-tab") || "approvals"; } catch (_) {}
  await loadQueue();
  await loadReport();
  await loadHistory();
  if (queueAll.length) tab = "approvals";
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
        if folder.exists():
            files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            for p in files[:80]:
                if p.is_file():
                    rel = p.name
                    rows.append(
                        f'<li><a href="/files/raw?p={html_mod.escape(str(p), quote=True)}">'
                        f'{html_mod.escape(rel)}</a></li>')
        body = ("<ul>" + "".join(rows) + "</ul>") if rows else "<p>No files yet.</p>"
        return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_mod.escape(title)}</title>
<style>body{{font:15px/1.5 Figtree,system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;color:#14201a;background:#f3f6f4}}
a{{color:#0f6e56}} ul{{padding-left:1.2rem}} li{{margin:6px 0}}</style></head>
<body><h1>{html_mod.escape(title)}</h1>{body}
<p><a href="/">← Panel</a></p></body></html>"""

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
<style>body{font:15px/1.5 Figtree,system-ui,sans-serif;padding:48px 24px;color:#14201a;
background:#f3f6f4;text-align:center}strong{display:block;font-size:1.2rem;margin-bottom:8px}</style>
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
            from urllib.parse import unquote
            name = unquote(path.split("/brief/", 1)[1])
            if ".." in name or "/" in name or not name:
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            brief = config.QUEUE_PROSPECTS / name
            if brief.is_file():
                text = brief.read_text(errors="replace")
                if brief.suffix == ".json":
                    try:
                        text = json.dumps(json.loads(text), indent=2)
                    except Exception:
                        pass
                    ctype = "application/json; charset=utf-8"
                else:
                    ctype = "text/plain; charset=utf-8"
                self._send(200, text, ctype)
            else:
                self._send(404, "not found", "text/plain; charset=utf-8")
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
