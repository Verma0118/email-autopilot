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
.actions { display:flex; gap:8px; }
#run { background:var(--accent); color:var(--accent-ink); padding:9px 18px; }
#stop { background:var(--bad-bg); color:var(--bad); padding:9px 16px; }

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
.q-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
.q-actions button.approve { background:var(--good-bg); color:var(--good); padding:9px 16px; }
.q-actions button.skip { background:var(--surface2); color:var(--ink2); padding:9px 16px; }
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
        <button id="run" type="button">Run now</button>
        <button id="stop" type="button">Stop</button>
      </div>
    </div>
    <nav class="tabs" role="tablist" aria-label="Panel sections">
      <button class="tab" role="tab" id="tab-approvals" aria-controls="panel-approvals" aria-selected="true" data-panel="approvals">
        Approvals <span class="badge" id="qbadge" data-n="0">0</span>
      </button>
      <button class="tab" role="tab" id="tab-overview" aria-controls="panel-overview" aria-selected="false" data-panel="overview">Overview</button>
      <button class="tab" role="tab" id="tab-activity" aria-controls="panel-activity" aria-selected="false" data-panel="activity">Activity</button>
      <button class="tab" role="tab" id="tab-report" aria-controls="panel-report" aria-selected="false" data-panel="report">Report</button>
    </nav>
  </div>
</div>

<main>
  <section class="panel active" id="panel-approvals" role="tabpanel" aria-labelledby="tab-approvals">
    <div class="section-head">
      <h2>Approval queue</h2>
      <p class="hint">Focus with <span class="kbd">j</span>/<span class="kbd">k</span> · <span class="kbd">a</span> approve · <span class="kbd">s</span> skip · <span class="kbd">o</span> open body</p>
    </div>
    <ul id="queue"></ul>
  </section>

  <section class="panel" id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" hidden>
    <div class="section-head"><h2>Overview</h2></div>
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
    <a href="https://mail.google.com/mail/u/0/#drafts">Gmail drafts</a><br>
    Scheduled run: daily 7:04 AM · warning at 60% of the autopilot token budget
  </footer>
</main>

<script>
const el = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
/* body_html from the model is intentionally rendered; still neutralize script/iframe. */
const sanitizeHtml = html => String(html ?? "")
  .replace(/<script[\\s\\S]*?<\\/script>/gi, "")
  .replace(/<iframe[\\s\\S]*?<\\/iframe>/gi, "")
  .replace(/\\son\\w+=("[^"]*"|'[^']*'|[^\\s>]+)/gi, "");

let focusIdx = 0;
let queueItems = [];

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
    /* ensure iframe has room after sticky chrome measured */
    const chrome = document.querySelector(".chrome");
    if (chrome) document.documentElement.style.setProperty("--chrome", chrome.offsetHeight + "px");
  }
  try { localStorage.setItem("emailcrm-tab", name); } catch (_) {}
}

document.querySelectorAll(".tab").forEach(t => {
  t.addEventListener("click", () => showPanel(t.dataset.panel));
});

function setFocus(i) {
  const items = [...document.querySelectorAll(".q-item")];
  if (!items.length) { focusIdx = 0; return; }
  focusIdx = Math.max(0, Math.min(i, items.length - 1));
  items.forEach((n, idx) => n.classList.toggle("focused", idx === focusIdx));
  items[focusIdx].scrollIntoView({ block:"nearest", behavior:"smooth" });
}

async function act(id, action, btn) {
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  const res = await fetch("/" + action, { method:"POST", body: JSON.stringify({ id }) });
  if (!res.ok) {
    if (btn) { btn.textContent = "error"; btn.disabled = false; }
    return;
  }
  await loadQueue();
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
    if (window.wasRunning && !s.running) el("dash").src = "/dashboard?t=" + Date.now();
    window.wasRunning = !!s.running;
  } catch (_) { el("detail").textContent = "panel server unreachable"; }
}

async function loadQueue() {
  try {
    const q = await (await fetch("/queue")).json();
    queueItems = q;
    const badge = el("qbadge");
    badge.textContent = q.length;
    badge.dataset.n = String(q.length);
    const ul = el("queue");
    if (!q.length) {
      ul.innerHTML = '<li class="empty"><strong>Nothing waiting</strong>Approve drafts here after a run. Until then, check Overview or Report.</li>';
      return;
    }
    ul.innerHTML = "";
    q.forEach((item, idx) => {
      const li = document.createElement("li");
      li.className = "q-item" + (idx === focusIdx ? " focused" : "");
      li.dataset.id = item.id;
      li.innerHTML =
        '<div class="q-meta">' +
          '<span class="stream" style="margin:0">' + esc(item.track) + '</span>' +
          '<strong>' + esc(item.name) + '</strong>' +
          '<span class="sub">' + esc(item.company) + ' · ' + esc(item.email || "no email") + '</span>' +
        '</div>' +
        (item.why ? '<p class="q-why">' + esc(item.why) + '</p>' : '') +
        '<p class="q-subject"><span>Subject · </span>' + esc(item.subject) + '</p>' +
        '<details class="preview"><summary>Read email</summary>' +
          '<blockquote class="body">' + sanitizeHtml(item.body_html) + '</blockquote></details>' +
        '<div class="q-actions">' +
          '<button type="button" class="approve" data-a="approve" data-id="' + esc(item.id) + '">Approve → Gmail draft</button>' +
          '<button type="button" class="skip" data-a="skip" data-id="' + esc(item.id) + '">Skip</button>' +
        '</div>';
      li.addEventListener("click", ev => {
        if (ev.target.closest("button, a, summary, details")) return;
        setFocus(idx);
      });
      ul.appendChild(li);
    });
    ul.querySelectorAll("button[data-a]").forEach(b => b.addEventListener("click", () => {
      act(b.dataset.id, b.dataset.a, b);
    }));
    if (focusIdx >= q.length) focusIdx = Math.max(0, q.length - 1);
    setFocus(focusIdx);
  } catch (_) {}
}

document.addEventListener("keydown", ev => {
  if (ev.target.matches("input, textarea, select") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const approvalsOn = el("panel-approvals").classList.contains("active");
  const key = ev.key.toLowerCase();
  if (key === "1") { showPanel("approvals"); return; }
  if (key === "2") { showPanel("overview"); return; }
  if (key === "3") { showPanel("activity"); return; }
  if (key === "4") { showPanel("report"); return; }
  if (!approvalsOn || !queueItems.length) return;
  if (key === "j" || key === "arrowdown") { ev.preventDefault(); setFocus(focusIdx + 1); }
  else if (key === "k" || key === "arrowup") { ev.preventDefault(); setFocus(focusIdx - 1); }
  else if (key === "a") {
    ev.preventDefault();
    const id = queueItems[focusIdx]?.id;
    if (id) act(id, "approve");
  } else if (key === "s") {
    ev.preventDefault();
    const id = queueItems[focusIdx]?.id;
    if (id) act(id, "skip");
  } else if (key === "o") {
    ev.preventDefault();
    const item = document.querySelectorAll(".q-item")[focusIdx];
    const d = item?.querySelector("details.preview");
    if (d) d.open = !d.open;
  }
});

el("run").addEventListener("click", () => fetch("/run", { method:"POST" }).then(poll));
el("stop").addEventListener("click", () => fetch("/stop", { method:"POST" }).then(poll));

(async () => {
  let tab = "approvals";
  try { tab = localStorage.getItem("emailcrm-tab") || "approvals"; } catch (_) {}
  await loadQueue();
  if (queueItems.length) tab = "approvals";
  showPanel(tab);
  poll();
  setInterval(poll, 2000);
  setInterval(loadQueue, 5000);
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

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif self.path.startswith("/dashboard"):
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
        elif self.path == "/queue":
            self._send(200, json.dumps(queue_store.pending()))
        elif self.path == "/status":
            if status.STATUS_FILE.exists():
                self._send(200, status.STATUS_FILE.read_text())
            else:
                self._send(200, json.dumps({"running": False, "stage": "idle",
                                            "tokens": status.tokens_snapshot()}))
        else:
            self._send(404, "{}")

    def do_POST(self):
        if self.path == "/run":
            if config.LOCK_FILE.exists():
                self._send(409, '{"error":"already running"}')
                return
            subprocess.Popen([str(PYTHON), str(RUN_PY)], cwd=str(config.AUTOPILOT),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._send(200, '{"ok":true}')
        elif self.path == "/stop":
            status.STOP_FLAG.touch()
            # graceful flag first; then kill the run process tree so in-flight
            # claude subprocesses die too instead of blocking for minutes
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
                queue_store.resolve(item_id, "skipped")
                self._send(200, '{"ok":true}')
                return
            try:
                import crm
                import gmail
                if item["kind"] == "reply" and item.get("thread_id"):
                    draft = gmail.create_reply_draft(
                        to=item["email"], subject=item["subject"], body_html=item["body_html"],
                        thread_id=item["thread_id"], in_reply_to=item.get("in_reply_to"))
                else:
                    draft = gmail.create_draft(
                        subject=item["subject"], body_html=item["body_html"], to=item["email"])
                queue_store.resolve(item_id, "approved", gmail_draft_id=draft["draft_id"])
                if item["kind"] == "outreach":
                    from datetime import date, timedelta
                    contacts = crm.load()
                    crm.migrate(contacts)
                    contacts.append({
                        "id": f"{item['name'].lower().replace(' ', '-')}-{date.today().year}",
                        "name": item["name"], "email": item["email"],
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
                self._send(200, json.dumps({"ok": True, "draft_id": draft["draft_id"]}))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)[:300]}))
        else:
            self._send(404, "{}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", config.PANEL_PORT), Handler)
    print(f"panel on http://localhost:{config.PANEL_PORT}")
    server.serve_forever()
