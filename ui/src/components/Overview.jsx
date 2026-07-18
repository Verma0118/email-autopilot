import { postDismiss } from "../api.js";

function suggestNext({ tokPct, briefsN, needsN, queueN, running, limitHit }) {
  if (running) return null;
  if (limitHit) {
    return {
      title: "Session paused",
      body: "Claude hit a session limit. Wait for reset, then run Triage.",
      stage: "triage",
      label: "Run Triage",
    };
  }
  if (queueN > 0) {
    return {
      title: "Clear Approvals first",
      body: `${queueN} draft${queueN === 1 ? "" : "s"} waiting — review before starting another run.`,
      stage: null,
      label: null,
      goApprovals: true,
    };
  }
  if (briefsN >= 2) {
    return {
      title: "Organize waiting briefs",
      body: `${briefsN} prospect briefs are ready — cheaper than Scout.`,
      stage: "organize",
      label: "Run Organize",
    };
  }
  if (needsN > 0 || tokPct < 45) {
    return {
      title: "Clear inbox debt",
      body: "Sync inbox, draft replies, and fix bounces.",
      stage: "triage",
      label: "Run Triage",
    };
  }
  if (tokPct >= 45) {
    return {
      title: "Meter is mid-range",
      body: `Autopilot meter at ${Math.round(tokPct)}% — prefer Triage or Organize over Scout.`,
      stage: "triage",
      label: "Run Triage",
    };
  }
  return {
    title: "Ready for a Full run",
    body: "Inbox looks quiet and the meter has room.",
    stage: "",
    label: "Run Full",
  };
}

export default function Overview({
  status, report, refreshReport, queueCount = 0,
  onRunStage, onShowApprovals, onShowReport,
}) {
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

  const briefs = report.briefs_waiting || [];
  const briefsN = report.briefs_n != null ? report.briefs_n : briefs.length;
  const errors = report.errors || [];

  const suggestion = suggestNext({
    tokPct,
    briefsN,
    needsN,
    queueN: queueCount,
    running: !!status.running,
    limitHit: !!tokens.limit_hit,
  });

  async function handleDismiss(id) {
    await postDismiss(id);
    await refreshReport();
  }

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

      {suggestion && (
        <div className="next-run">
          <div>
            <p className="label">Suggested next</p>
            <p className="next-title">{suggestion.title}</p>
            <p className="sub">{suggestion.body}</p>
          </div>
          <div className="next-actions">
            {suggestion.goApprovals && (
              <button type="button" className="btn btn-primary btn-sm" onClick={onShowApprovals}>
                Open Approvals →
              </button>
            )}
            {suggestion.label && suggestion.stage !== null && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={!!status.running}
                onClick={() => onRunStage(suggestion.stage)}
              >
                {suggestion.label}
              </button>
            )}
          </div>
        </div>
      )}

      <div className="stack" style={{ marginTop: 18 }}>
        {needsN > 0 && (
          <div className="needs">
            <h3>
              Needs you{" "}
              <span className="badge" data-n={String(needsN)}>{needsN}</span>
            </h3>
            <ul>
              {normNeeds.slice(0, 10).map(it => {
                const href = it.href || "";
                const isMailto = href.startsWith("mailto:");
                const isHash = href.startsWith("/#") || href.startsWith("#");
                let linkLabel = "Open";
                if (isMailto) linkLabel = "Email them";
                else if (href.includes("mail.google")) linkLabel = "Open in Gmail";
                else if (isHash || href.includes("approvals")) linkLabel = "Open Approvals";
                return (
                  <li key={it.id}>
                    <div>{it.text}</div>
                    <div className="row-actions">
                      {href && (
                        isHash ? (
                          <button type="button" onClick={() => {
                            if (href.includes("approvals")) onShowApprovals();
                            else onShowReport();
                          }}>{linkLabel}</button>
                        ) : (
                          <a href={href} target="_blank" rel="noopener">{linkLabel}</a>
                        )
                      )}
                      <button type="button" onClick={() => handleDismiss(it.id)}>Dismiss</button>
                    </div>
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
              disabled={!!status.running}
              onClick={() => onRunStage("organize")}
            >
              Run Organize →
            </button>
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

        <p className="report-link-row">
          <a href="/dashboard" target="_blank" rel="noopener">Open full report ↗</a>
        </p>
      </div>
    </>
  );
}
