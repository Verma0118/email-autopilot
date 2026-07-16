"""Publish the dashboard to GitHub Pages, encrypted.

The public page is a passphrase prompt; the dashboard HTML is an AES-256-GCM
blob decrypted client-side via WebCrypto. Contact data never leaves the
machine in plaintext. Passphrase lives at ~/.config/emailcrm/dashboard_pass.
"""
import base64
import hashlib
import os
import subprocess

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import config

PASS_FILE = config.CONFIG_DIR / "dashboard_pass"
DOCS = config.AUTOPILOT / "docs"
PBKDF2_ITERS = 250_000

SHELL_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>EmailCRM Autopilot</title>
<style>
:root { --bg:#fafafa; --card:#fff; --ink:#18181b; --ink2:#71717a; --line:rgba(24,24,27,.12); --accent:#5753c6; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0e0e10; --card:#17171a; --ink:#ededef; --ink2:#9d9da6; --line:rgba(237,237,239,.12); --accent:#918fe8; }
}
* { box-sizing:border-box; margin:0; }
body { background:var(--bg); color:var(--ink); display:grid; place-items:center; min-height:100vh;
  font:15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding:24px; }
form { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:28px;
  width:100%; max-width:360px; display:flex; flex-direction:column; gap:12px; }
h1 { font-size:1.05rem; font-weight:650; letter-spacing:-.01em; }
p { color:var(--ink2); font-size:.85rem; }
label { font-size:.8rem; font-weight:600; color:var(--ink2); }
input { font:inherit; color:var(--ink); background:var(--bg); border:1px solid var(--line);
  border-radius:9px; padding:9px 12px; width:100%; }
input:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
button { font:inherit; font-weight:600; color:#fff; background:var(--accent); border:0;
  border-radius:9px; padding:10px; cursor:pointer; transition:transform 160ms cubic-bezier(.23,1,.32,1), opacity .2s; }
button:active { transform:scale(0.97); }
button:disabled { opacity:.6; }
.err { color:#c22f36; font-size:.82rem; display:none; }
</style></head>
<body>
<form id="f">
  <h1>EmailCRM Autopilot</h1>
  <p>This dashboard is encrypted. Enter the passphrase to decrypt it in your browser.</p>
  <label for="p">Passphrase</label>
  <input id="p" type="password" autocomplete="current-password" autofocus required>
  <button id="b" type="submit">Unlock</button>
  <p class="err" id="e" role="alert">Wrong passphrase. Try again.</p>
</form>
<script>
const BLOB = "__PAYLOAD__";
const ITERS = __ITERS__;
document.getElementById("f").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const btn = document.getElementById("b"), err = document.getElementById("e");
  btn.disabled = true; btn.textContent = "Decrypting…"; err.style.display = "none";
  try {
    const raw = Uint8Array.from(atob(BLOB), c => c.charCodeAt(0));
    const salt = raw.slice(0, 16), iv = raw.slice(16, 28), ct = raw.slice(28);
    const pw = new TextEncoder().encode(document.getElementById("p").value);
    const km = await crypto.subtle.importKey("raw", pw, "PBKDF2", false, ["deriveKey"]);
    const key = await crypto.subtle.deriveKey(
      { name:"PBKDF2", salt, iterations: ITERS, hash:"SHA-256" },
      km, { name:"AES-GCM", length:256 }, false, ["decrypt"]);
    const pt = await crypto.subtle.decrypt({ name:"AES-GCM", iv }, key, ct);
    document.open(); document.write(new TextDecoder().decode(pt)); document.close();
  } catch (_) {
    err.style.display = "block"; btn.disabled = false; btn.textContent = "Unlock";
  }
});
</script>
</body></html>
"""


def encrypt_dashboard(html_text, passphrase):
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, PBKDF2_ITERS, dklen=32)
    ct = AESGCM(key).encrypt(iv, html_text.encode(), None)
    payload = base64.b64encode(salt + iv + ct).decode()
    return SHELL_TEMPLATE.replace("__PAYLOAD__", payload).replace("__ITERS__", str(PBKDF2_ITERS))


def run(report, dry_run=False):
    """Encrypt dashboard.html -> docs/index.html, commit and push. Non-fatal on error."""
    r = report.setdefault("publish", {"status": None, "errors": []})
    dash = config.ROOT / "dashboard.html"
    if dry_run or not dash.exists():
        r["status"] = "skipped"
        return r
    if not PASS_FILE.exists():
        r["errors"].append("no passphrase at ~/.config/emailcrm/dashboard_pass; publish skipped")
        r["status"] = "skipped"
        return r
    passphrase = PASS_FILE.read_text().strip()
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(encrypt_dashboard(dash.read_text(), passphrase))
    try:
        env = dict(os.environ, PATH="/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", ""))
        subprocess.run(["git", "add", "docs/index.html"], cwd=config.AUTOPILOT, check=True, env=env,
                       capture_output=True, timeout=30)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=config.AUTOPILOT, env=env,
                              capture_output=True, timeout=30)
        if diff.returncode == 0:
            r["status"] = "unchanged"
            return r
        subprocess.run(["git", "commit", "-q", "-m", "publish: encrypted dashboard"],
                       cwd=config.AUTOPILOT, check=True, env=env, capture_output=True, timeout=30)
        subprocess.run(["git", "push", "-q"], cwd=config.AUTOPILOT, check=True, env=env,
                       capture_output=True, timeout=120)
        r["status"] = "published"
    except subprocess.CalledProcessError as e:
        r["errors"].append(f"git publish failed: {(e.stderr or b'').decode()[:200]}")
        r["status"] = "error"
    return r
