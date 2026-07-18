import { postDismiss } from "../api.js";

export default function Overview({ status, report, refreshReport, addToast, setRunMode, onRunOrganize, onShowReport }) {
  const tokens = status.tokens || {};
  const tokPct = tokens.pct || 0;
  const tokClass = tokens.limit_hit || tokPct >= 100 ? " bad" : (tokPct >= 60 ? " warn" : "");
  const tokDisplay = tokens.limit_hit ? "PAUSED" : (tokPct + "%");
  const tokDetail = tokens.limit_hit
    ? "Claude session limit · try again after " + (tokens.limit_reset || "reset")
    : [(tokens.used || 0).toLocaleString(), " / ", (tokens.budget || 0).toLocaleString(),
       " · ", (tokens.calls || 0), " calls since ", tokens.window_started || "—"].join("");

  const stageLabel = status.running ? (status.stage || "running") : "idle";
  const lastRunText = status.running ? "running now…" : (status.detail || "—");
  const rundown = status.running && (!status.rundown || status.rundown === "Updating…")
    ? "Updating…"
    : (status.rundown || "—");

  const needsItems = Array.isArray(report.needs_you) ? report.needs_you : [];
  const normNeeds = needsItems.map(it => typeof it === "string" ? { id: it, text: it, href: null } : it);
  const needsN = report.needs_n != null ? report.needs_n : normNeeds.length;

  const gmailDrafts = report.gmail_drafts || [];
  const briefs = report.briefs_waiting || [];
  const briefsN = report.briefs_n != null ? report.briefs_n : briefs.length;
  const actionItems = report.action_items || [];
  const errors = report.errors || [];

  async function handleDismiss(id) {
    await postDismiss(id);
    await refreshReport();
  }

  // parse errors into groups
  const marked = [];
  const limits = [];
  const other = [];
  errors.forEach(e => {
    const s = String(e || "");
    const m = s.match(/^([^:]+):\s*LLM marked down/i);
    if (m) marked.push(m[1].trim());
    else if (/rate\/session limit|session limit/i.test(s)) limits.push(s);
    else other.push(s);
  });
  let errLede = "";
  if (errors.length) {
    if (limits.length || marked.length) {
      errLede = "Claude hit a session limit. Wait for reset, then hit Run again.";
      if (marked.length) errLede += " Skipped " + marked.length + " LLM step" + (marked.length === 1 ? "" : "s") + ".";
    } else {
      errLede = "Something failed last run.";
    }
  }

  return (
    <>
      <div className="section-head">
        <h2>Overview</h2>
        <p className="hint lastrun">Last run · <strong>{lastRunText}</strong></p>
      </div>

      <div className="status-strip">
        <div className="block compact">
          <p className="label">Activity</p>
          <p className="big">{stageLabel}</p>
          <p className="sub">{status.detail || "—"}</p>
          {status.stream && <span className="stream">{status.stream}</span>}
        </div>
        <div className={`block compact tok${tokClass}`}>
          <p className="label">Autopilot LLM meter</p>
          <p className="big">{tokDisplay}</p>
          <p className="sub">{tokDetail}</p>
          <meter min="0" max="100" low="59" high="60" optimum="10" value={Math.min(100, tokPct)} />
          <p className="sub" style={{ marginTop: 8 }}>Not your Claude session %. Just this app's calls this window.</p>
        </div>
      </div>

      <div className="stack" style={{ marginTop: 18 }}>
        {needsN > 0 && (
          <div className="needs">
            <h3>
              Needs you{" "}
              <span className="badge" data-n={String(needsN)}>{needsN}</span>
            </h3>
            <ul>
              {normNeeds.slice(0, 10).map(it => {
                const isMailto = String(it.href || "").startsWith("mailto:");
                const linkLabel = isMailto ? "Email them" : "Open in Gmail";
                return (
                  <li key={it.id}>
                    <div>{it.text}</div>
                    <div className="row-actions">
                      {it.href && (
                        <a href={it.href} target="_blank" rel="noopener">{linkLabel}</a>
                      )}
                      <button type="button" onClick={() => handleDismiss(it.id)}>Dismiss</button>
                    </div>
                  </li>
                );
              })}
            </ul>
            <a className="go" href="#report" onClick={ev => { ev.preventDefault(); onShowReport(); }}>
              Full report →
            </a>
          </div>
        )}

        {gmailDrafts.length > 0 && (
          <div className="gmail-drafts">
            <h3>
              Review in Gmail{" "}
              <span className="badge" data-n={String(gmailDrafts.length)}>{gmailDrafts.length}</span>
            </h3>
            <ul>
              {gmailDrafts.slice(0, 12).map((d, i) => {
                const link = d.href
                  ? <a href={d.href} target="_blank" rel="noopener">Open draft</a>
                  : <a href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noopener">Gmail drafts</a>;
                return (
                  <li key={i}>
                    <div>{d.text}</div>
                    <div className="row-actions">{link}</div>
                    {d.body && (
                      <details>
                        <summary>Preview</summary>
                        <pre style={{ marginTop: 6, fontSize: "0.78rem", whiteSpace: "pre-wrap" }}>
                          {d.body.slice(0, 400)}{d.body.length > 400 ? "…" : ""}
                        </pre>
                      </details>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {briefsN > 0 && (
          <div className="gmail-drafts">
            <h3>
              Briefs to organize{" "}
              <span className="badge" data-n={String(briefsN)}>{briefsN}</span>
            </h3>
            <ul>
              {briefs.slice(0, 12).map((b, i) => (
                <li key={i} className="person-row">
                  <div className="who">
                    <strong>{b.name || b.file || "Prospect"}</strong>
                    {b.company && <div className="meta">{b.company}</div>}
                  </div>
                  {b.track && <span className="tag">{b.track}</span>}
                  {b.file && (
                    <a
                      className="btn btn-quiet btn-sm"
                      href={"/brief/" + encodeURIComponent(b.file)}
                    >
                      Open brief
                    </a>
                  )}
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              style={{ marginTop: 12 }}
              onClick={onRunOrganize}
            >
              Run Organize →
            </button>
          </div>
        )}

        {actionItems.length > 0 && (
          <div className="needs">
            <h3>Inbox action items</h3>
            <ul>
              {actionItems.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          </div>
        )}

        {errors.length > 0 && (
          <div className="errors-box">
            <h3>Blocked</h3>
            {errLede && <p className="err-lede">{errLede}</p>}
            <ul>
              {limits.slice(0, 1).map((s, i) => {
                const short = s.replace(/^[^:]+:\s*/, "").replace(/rate\/session limit, skipping all LLM stages this run:\s*/i, "");
                return <li key={"lim" + i}>{short.slice(0, 140)}{short.length > 140 ? "…" : ""}</li>;
              })}
              {other.slice(0, 4).map((s, i) => <li key={"oth" + i}>{s}</li>)}
            </ul>
          </div>
        )}

        <div className="block compact">
          <p className="label">Inbox rundown</p>
          <p className="rundown">{rundown}</p>
        </div>
      </div>
    </>
  );
}
