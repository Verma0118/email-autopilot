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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@450;550;650;700&family=Fraunces:opsz,wght@9..144,550;9..144,650&display=swap" rel="stylesheet">
<style>
html { color-scheme: light; }
:root {
  --bg0:#f8fbfa; --bg1:#eef6f2;
  --surface:rgba(255,255,255,.82); --surface-solid:#ffffff;
  --ink:#132019; --ink2:#5a6b64; --ink3:#879890;
  --line:rgba(18,40,32,.1); --accent:#0d7a5f; --accent-ink:#fff;
  --bad:#b42318; --ease:cubic-bezier(0.23,1,0.32,1);
  --font:"Figtree", "Segoe UI", sans-serif;
  --display:"Fraunces", Georgia, serif;
  --frost:blur(18px) saturate(1.4);
  --shadow:0 1px 2px rgba(18,40,32,.04), 0 16px 40px rgba(18,40,32,.08);
}
* { box-sizing:border-box; margin:0; }
body {
  min-height:100vh; display:grid; place-items:center; padding:24px;
  color:var(--ink); font:15px/1.5 var(--font); font-weight:450;
  -webkit-font-smoothing:antialiased;
  background:
    radial-gradient(900px 420px at 20% 0%, rgba(13,122,95,.12), transparent 55%),
    radial-gradient(700px 360px at 100% 100%, rgba(62,207,154,.08), transparent 50%),
    linear-gradient(165deg, var(--bg0), var(--bg1));
}
form {
  background:var(--surface); border:1px solid var(--line); border-radius:20px;
  padding:28px 26px; width:100%; max-width:380px;
  display:flex; flex-direction:column; gap:12px;
  backdrop-filter:var(--frost); -webkit-backdrop-filter:var(--frost);
  box-shadow:var(--shadow);
  animation:rise 380ms var(--ease);
}
@keyframes rise {
  from { opacity:0; transform:translateY(8px); }
  to { opacity:1; transform:none; }
}
@media (prefers-reduced-motion: reduce) {
  form { animation:none; }
}
.mark {
  font-family:var(--display); font-size:.78rem; font-weight:550;
  letter-spacing:.04em; text-transform:uppercase; color:var(--accent);
}
h1 {
  font-family:var(--display); font-size:1.45rem; font-weight:550;
  letter-spacing:-.025em; line-height:1.15;
}
p { color:var(--ink2); font-size:.88rem; }
label { font-size:.78rem; font-weight:650; color:var(--ink3); }
input {
  font:inherit; color:var(--ink); background:var(--surface-solid);
  border:1px solid var(--line); border-radius:11px; padding:11px 13px; width:100%;
}
input:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
button {
  font:inherit; font-weight:650; color:var(--accent-ink); background:var(--accent);
  border:0; border-radius:10px; padding:11px; cursor:pointer; margin-top:4px;
  transition:transform 160ms var(--ease), opacity .2s;
}
button:active { transform:scale(0.97); }
button:disabled { opacity:.6; }
button:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.err { color:var(--bad); font-size:.84rem; display:none; }
</style></head>
<body>
<form id="f">
  <p class="mark">EmailCRM</p>
  <h1>Unlock dashboard</h1>
  <p>This report is encrypted on the device that generated it. Enter the passphrase to decrypt it in your browser.</p>
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
