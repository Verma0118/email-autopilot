"""Localhost control panel for the autopilot.

http://localhost:8787 — Run / Stop, approval queue, live feed, dashboard.
Binds 127.0.0.1 only; never exposed to the network.
Run persistently via launchd (com.aarav.emailcrm.panel, KeepAlive).

Serves the React UI from ui/dist (build with: cd ui && npm run build).
JSON APIs stay on this process. Auto-reloads when Python code changes;
POST /update pulls main and restarts the panel.
"""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config
import queue_store
import status

HERE = Path(__file__).resolve().parent
PYTHON = config.AUTOPILOT / ".venv" / "bin" / "python"
RUN_PY = config.AUTOPILOT / "run.py"
DISMISS_FILE = config.STATE_DIR / "dismissed_needs.json"


def _repo_root():
    if (config.AUTOPILOT / ".git").exists():
        return config.AUTOPILOT
    if (HERE / ".git").exists():
        return HERE
    return config.AUTOPILOT


def _watched_paths():
    paths = [
        HERE / "panel.py", HERE / "status.py", HERE / "config.py",
        HERE / "queue_store.py", HERE / "gmail.py", HERE / "crm.py",
        HERE / "llm.py", HERE / "run.py", HERE / "publish.py",
        HERE / "ui" / "dist" / "index.html",
    ]
    stages = HERE / "stages"
    if stages.is_dir():
        paths.extend(sorted(stages.glob("*.py")))
    return [p for p in paths if p.exists()]


def _code_stamp():
    return tuple((str(p), p.stat().st_mtime_ns) for p in _watched_paths())


def _reexec_soon(delay=0.4):
    """Replace this process with a fresh panel.py (keeps the same port/terminal)."""
    def go():
        time.sleep(delay)
        print("reloading panel…", flush=True)
        os.execv(sys.executable, [sys.executable, str(HERE / "panel.py"), *sys.argv[1:]])
    threading.Thread(target=go, daemon=True).start()


def _watch_code_for_reload():
    stamp = _code_stamp()
    while True:
        time.sleep(1.5)
        try:
            now = _code_stamp()
            if now != stamp:
                print("code changed on disk — reloading panel", flush=True)
                _reexec_soon(0.25)
                return
        except Exception:
            pass


def _git_head():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_repo_root()), text=True, timeout=10,
        ).strip()
    except Exception:
        return None


def _git_pull():
    repo = _repo_root()
    proc = subprocess.run(
        ["git", "pull", "--ff-only", "origin", "main"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "ok": proc.returncode == 0,
        "changed": proc.returncode == 0 and "Already up to date" not in out,
        "message": out.strip()[-600:],
        "head": _git_head(),
    }


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



UI_DIST = HERE / "ui" / "dist"
_UI_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
    ".ico": "image/x-icon",
}


def _ui_path(url_path):
    """Resolve a URL path under ui/dist (None if missing / traversal)."""
    if not UI_DIST.is_dir():
        return None
    rel = (url_path or "/").split("?", 1)[0]
    if rel in ("", "/"):
        rel = "index.html"
    else:
        rel = rel.lstrip("/")
    try:
        candidate = (UI_DIST / rel).resolve()
        candidate.relative_to(UI_DIST.resolve())
    except Exception:
        return None
    return candidate if candidate.is_file() else None


def _ui_fallback_html():
    return """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EmailCRM panel</title>
<style>body{font:15px/1.5 "Plus Jakarta Sans",system-ui,sans-serif;max-width:36rem;
margin:48px auto;padding:0 20px;color:#15241e;background:#f7faf8}
code{background:#e8f2ee;padding:2px 6px;border-radius:6px}</style></head>
<body><h1>UI build missing</h1>
<p>The React panel is not built. From the repo root:</p>
<pre><code>cd ui && npm install && npm run build</code></pre>
<p>Then restart the panel.</p></body></html>"""



class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if "text/html" in ctype or ctype.startswith("application/json"):
            self.send_header("Cache-Control", "no-store")
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
        # React SPA + hashed assets from ui/dist
        if path == "/" or path.startswith("/assets/"):
            target = _ui_path(path)
            if target is None and path == "/":
                self._send(200, _ui_fallback_html(), "text/html; charset=utf-8")
                return
            if target is None:
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            ctype = _UI_MIME.get(target.suffix.lower(), "application/octet-stream")
            # Fingerprinted assets can be cached; index.html must not.
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if path == "/" or "text/html" in ctype:
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/version":
            self._send(200, json.dumps({"head": _git_head(), "repo": str(_repo_root())}))
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
        if self.path == "/update":
            try:
                result = _git_pull()
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)[:200]}))
                return
            if not result["ok"]:
                self._send(500, json.dumps({
                    "ok": False,
                    "error": "git pull failed",
                    "message": result.get("message") or "",
                }))
                return
            self._send(200, json.dumps(result))
            # Always reexec so handlers + ui/dist match disk (even if already latest)
            _reexec_soon(0.5)
        elif self.path == "/run":
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
                # Clear stage latches so a later run can try again after skip
                if item.get("kind") in ("bounce", "followup"):
                    try:
                        import crm
                        cid = (item.get("meta") or {}).get("contact_id")
                        contacts = crm.load()
                        for c in contacts:
                            if c.get("id") != cid:
                                continue
                            if item.get("kind") == "bounce":
                                br = (c.get("autopilot") or {}).get("bounce_retry") or {}
                                if br.get("status") == "queued":
                                    c["autopilot"]["bounce_retry"] = None
                                    crm.touch(c, "bounce_skip", item_id)
                            else:
                                if str(c.get("follow_up_draft_id") or "").startswith("queue:"):
                                    c["follow_up_draft_id"] = None
                                    c["follow_up_drafted_at"] = None
                                    crm.touch(c, "followup_skip", item_id)
                            crm.save(contacts)
                            break
                    except Exception:
                        pass
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
                meta = item.get("meta") or {}
                email_type = meta.get("email_type")
                attach_paths = []
                if item["kind"] in ("outreach", "bounce"):
                    attach_paths = list(config.attachments_for(email_type))
                warn = None
                expected_names = meta.get("attachments") or []
                if expected_names and not attach_paths:
                    warn = ("Attachment files missing under assets/ "
                            f"({', '.join(expected_names)}); draft created without them")

                if item["kind"] in ("reply", "followup") and item.get("thread_id"):
                    draft = gmail.create_reply_draft(
                        to=to_email, subject=subject, body_html=body_html,
                        thread_id=item["thread_id"], in_reply_to=item.get("in_reply_to"),
                        attachments=attach_paths)
                else:
                    draft = gmail.create_draft(
                        subject=subject, body_html=body_html, to=to_email,
                        attachments=attach_paths)
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
                        "linkedin_url": meta.get("linkedin"),
                        "company": item["company"],
                        "role": meta.get("role"),
                        "email_type": email_type,
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
                elif item["kind"] == "bounce":
                    contacts = crm.load()
                    cid = meta.get("contact_id")
                    for c in contacts:
                        if c.get("id") != cid:
                            continue
                        old = meta.get("old_email") or c.get("email")
                        c["email"] = to_email
                        ap = c.setdefault("autopilot", {})
                        ap["bounce_retry"] = {
                            "status": "retried",
                            "old_email": old,
                            "corrected_email": to_email,
                            "drafted_at": crm.now_iso(),
                            "evidence": meta.get("evidence") or [],
                        }
                        crm.set_status(c, "bounce_fixed", "bounce_approved", f"-> {to_email}")
                        c["follow_up_due"] = crm.due_plus_followup_days()
                        c["gmail_draft_id"] = draft["draft_id"]
                        crm.save(contacts)
                        contact_id = cid
                        break
                elif item["kind"] == "followup":
                    contacts = crm.load()
                    cid = meta.get("contact_id")
                    for c in contacts:
                        if c.get("id") != cid:
                            continue
                        crm.set_status(c, "followed_up", "followup_approved", draft["draft_id"])
                        c["follow_up_count"] = 1
                        c["follow_up_draft_id"] = draft["draft_id"]
                        c["follow_up_drafted_at"] = crm.now_iso()
                        crm.save(contacts)
                        contact_id = cid
                        break
                queue_store.resolve(item_id, "approved", gmail_draft_id=draft["draft_id"],
                                    draft_link=link, contact_id=contact_id)
                payload = {
                    "ok": True,
                    "draft_id": draft["draft_id"],
                    "draft_link": link,
                    "attached": draft.get("attached") or [],
                }
                if warn:
                    payload["warn"] = warn
                self._send(200, json.dumps(payload))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)[:300]}))
        else:
            self._send(404, "{}")


if __name__ == "__main__":
    threading.Thread(target=_watch_code_for_reload, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", config.PANEL_PORT), Handler)
    head = _git_head() or "?"
    print(f"panel on http://localhost:{config.PANEL_PORT} ({head}) — auto-reloads on code change")
    server.serve_forever()
