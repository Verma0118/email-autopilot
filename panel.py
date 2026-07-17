"""Localhost control panel for the autopilot.

http://localhost:8787 — Run / Stop buttons, live stage + stream feed,
token meter. Binds 127.0.0.1 only; never exposed to the network.
Run persistently via launchd (com.aarav.emailcrm.panel, KeepAlive).
"""
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config
import status

PYTHON = config.AUTOPILOT / ".venv" / "bin" / "python"
RUN_PY = config.AUTOPILOT / "run.py"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Autopilot Control</title>
<style>
:root {
  --bg:#fafafa; --card:#fff; --card2:#f4f4f5; --ink:#18181b; --ink2:#71717a;
  --line:rgba(24,24,27,.09); --line2:rgba(24,24,27,.16);
  --accent:#5753c6; --accent-soft:rgba(87,83,198,.09);
  --good:#177245; --good-bg:rgba(23,114,69,.08); --warn:#96650b; --warn-bg:rgba(150,101,11,.12);
  --bad:#c22f36; --bad-bg:rgba(194,47,54,.08);
  --ease:cubic-bezier(0.23,1,0.32,1);
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#0e0e10; --card:#17171a; --card2:#1e1e22; --ink:#ededef; --ink2:#9d9da6;
    --line:rgba(237,237,239,.08); --line2:rgba(237,237,239,.16);
    --accent:#918fe8; --accent-soft:rgba(145,143,232,.12);
    --good:#41c780; --good-bg:rgba(65,199,128,.1); --warn:#d9a636; --warn-bg:rgba(217,166,54,.14);
    --bad:#f0555d; --bad-bg:rgba(240,85,93,.1); }
}
* { box-sizing:border-box; margin:0; }
body { background:var(--bg); color:var(--ink);
  font:15px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
  -webkit-font-smoothing:antialiased; max-width:720px; margin:0 auto; padding:36px 24px 64px; }
header { display:flex; align-items:center; gap:12px; margin-bottom:22px; flex-wrap:wrap; }
h1 { font-size:1.25rem; font-weight:650; letter-spacing:-.02em; flex:1; }
.dot { width:9px; height:9px; border-radius:50%; background:var(--ink2); flex:none; }
.dot.live { background:var(--good); box-shadow:0 0 0 4px var(--good-bg); }
button { font:inherit; font-weight:600; border:0; border-radius:10px; padding:10px 20px;
  cursor:pointer; min-height:40px; transition:transform 160ms var(--ease), opacity .2s; }
button:active { transform:scale(0.97); }
button:disabled { opacity:.45; cursor:default; }
button:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
#run { background:var(--accent); color:#fff; }
#stop { background:var(--bad-bg); color:var(--bad); }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }
.card h2 { font-size:.74rem; color:var(--ink2); text-transform:uppercase; letter-spacing:.07em; font-weight:600; margin-bottom:6px; }
.big { font-size:1.15rem; font-weight:650; letter-spacing:-.01em; overflow-wrap:anywhere; }
.sub { color:var(--ink2); font-size:.84rem; margin-top:2px; overflow-wrap:anywhere; }
.stream { display:inline-block; background:var(--accent-soft); color:var(--accent);
  font-size:.76rem; font-weight:650; border-radius:999px; padding:2px 10px; margin-top:6px; }
meter { width:100%; height:10px; margin-top:8px; }
.tok.warn .big { color:var(--warn); }
.tok.bad .big { color:var(--bad); }
#feed { list-style:none; padding:0; display:flex; flex-direction:column; gap:6px; }
#feed li { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:8px 13px; font-size:.85rem; display:flex; gap:10px; align-items:baseline; }
#feed .t { color:var(--ink2); font-variant-numeric:tabular-nums; font-size:.78rem; flex:none; }
#feed .s { color:var(--accent); font-weight:600; font-size:.78rem; flex:none; }
footer { margin-top:28px; color:var(--ink2); font-size:.82rem; line-height:2; border-top:1px solid var(--line); padding-top:14px; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
</style></head>
<body>
<header>
  <span class="dot" id="dot" aria-hidden="true"></span>
  <h1>Autopilot Control</h1>
  <button id="run" type="button">Run now</button>
  <button id="stop" type="button">Stop</button>
</header>

<div class="grid">
  <div class="card"><h2>Current activity</h2>
    <p class="big" id="stage">idle</p>
    <p class="sub" id="detail">—</p>
    <span class="stream" id="stream" hidden></span>
  </div>
  <div class="card tok" id="tokcard"><h2>Token budget (5h window)</h2>
    <p class="big" id="tokpct">0%</p>
    <p class="sub" id="tokdetail">—</p>
    <meter id="tokmeter" min="0" max="100" low="59" high="60" optimum="10" value="0"></meter>
  </div>
</div>

<div class="card" style="margin-bottom:10px"><h2>Live feed</h2>
  <ul id="feed" aria-live="polite"><li>waiting for status…</li></ul>
</div>

<div class="card" style="padding:0; overflow:hidden">
  <h2 style="padding:16px 18px 0">Dashboard</h2>
  <iframe id="dash" src="/dashboard" title="EmailCRM dashboard"
    style="width:100%; height:1400px; border:0; display:block"></iframe>
</div>

<footer>
  <a href="https://verma0118.github.io/email-autopilot/">Web dashboard (encrypted, for away-from-Mac)</a> ·
  <a href="https://mail.google.com/mail/u/0/#drafts">Gmail drafts</a><br>
  Scheduled run: daily 7:04 AM · warning fires at 60% of the autopilot token budget
</footer>

<script>
const el = id => document.getElementById(id);
async function poll() {
  try {
    const s = await (await fetch("/status")).json();
    el("dot").className = "dot" + (s.running ? " live" : "");
    el("stage").textContent = s.running ? (s.stage || "running") : "idle";
    el("detail").textContent = s.detail || "—";
    const st = el("stream");
    if (s.stream) { st.textContent = s.stream; st.hidden = false; } else st.hidden = true;
    const t = s.tokens || {};
    el("tokpct").textContent = (t.pct || 0) + "%";
    el("tokdetail").textContent = (t.used || 0).toLocaleString() + " / " + (t.budget || 0).toLocaleString()
      + " tokens · " + (t.calls || 0) + " calls since " + (t.window_started || "—");
    el("tokmeter").value = Math.min(100, t.pct || 0);
    el("tokcard").className = "card tok" + (t.pct >= 100 ? " bad" : (t.pct >= 60 ? " warn" : ""));
    const feed = el("feed");
    feed.innerHTML = "";
    (s.events || []).slice().reverse().slice(0, 14).forEach(e => {
      const li = document.createElement("li");
      li.innerHTML = '<span class="t">' + e.ts + '</span>' +
        (e.stream ? '<span class="s">' + e.stream + '</span>' : '') +
        '<span>' + (e.detail || e.stage || "") + '</span>';
      feed.appendChild(li);
    });
    if (!(s.events || []).length) feed.innerHTML = "<li>no events yet — hit Run now</li>";
    el("run").disabled = !!s.running;
    el("stop").disabled = !s.running;
    if (window.wasRunning && !s.running) el("dash").src = "/dashboard?t=" + Date.now();
    window.wasRunning = !!s.running;
  } catch (_) { el("detail").textContent = "panel server unreachable"; }
}
el("run").addEventListener("click", () => fetch("/run", { method:"POST" }).then(poll));
el("stop").addEventListener("click", () => fetch("/stop", { method:"POST" }).then(poll));
poll(); setInterval(poll, 2000);
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
                self._send(200, "<p style='font-family:sans-serif'>No dashboard yet — run the pipeline once.</p>",
                           "text/html; charset=utf-8")
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
            self._send(200, '{"ok":true}')
        else:
            self._send(404, "{}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", config.PANEL_PORT), Handler)
    print(f"panel on http://localhost:{config.PANEL_PORT}")
    server.serve_forever()
