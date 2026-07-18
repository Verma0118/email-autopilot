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
      body: `${queueN} draft${queueN === 1 ? "" : "s"} waiting. Review before starting another run.`,
      stage: null,
      label: null,
      goApprovals: true,
    };
  }
  if (briefsN >= 2) {
    return {
      title: "Organize waiting briefs",
      body: `${briefsN} prospect briefs are ready. Cheaper than Scout.`,
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
      body: `Autopilot meter at ${Math.round(tokPct)}%. Prefer Triage or Organize over Scout.`,
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

/** Fallback when status only has the old flat rundown string. */
function parseLegacyRundown(text) {
  const raw = String(text || "").trim();
  if (!raw || raw === "Updating…" || raw === "No rundown yet.") return null;
  const sections = [];
  const patterns = [
    [/No new replies this run\.?/i, "New replies", true],
    [/New replies:\s*(.+?)(?:\.(?:\s+[A-Z])|$)/i, "New replies", false],
    [/Out of office:\s*(.+?)(?:\.(?:\s+[A-Z])|$)/i, "Out of office", false],
    [/Bounces:\s*(.+?)(?:\.(?:\s+[A-Z])|$)/i, "Bounces", false],
    [/You sent:\s*(.+?)(?:\.(?:\s+[A-Z])|$)/i, "You sent", false],
    [/Open threads needing a look:\s*(.+?)\.?$/i, "Open threads", false],
  ];
  for (const [re, title, emptyOnly] of patterns) {
    const m = raw.match(re);
    if (!m) continue;
    if (emptyOnly) {
      sections.push({ id: title, title, people: [], empty: "None this run." });
      continue;
    }
    const chunk = m[1] || "";
    const people = chunk.split(/;\s*|\s*,\s+(?=[A-Z])/).map(bit => {
      const head = bit.split(":")[0].trim().replace(/\s*\+\d+\s*more$/i, "");
      const pm = head.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
      if (pm) return { name: pm[1].trim(), company: pm[2].trim() };
      if (!head || /^automatic reply/i.test(head)) return null;
      return { name: head, company: "" };
    }).filter(Boolean);
    if (people.length) sections.push({ id: title, title, people, empty: "" });
  }
  return sections.length ? sections : null;
}

function NeedRow({ item, onDismiss, onShowApprovals, onShowReport }) {
  const href = item.href || "";
  const isMailto = href.startsWith("mailto:");
  const isHash = href.startsWith("/#") || href.startsWith("#");
  let linkLabel = "Open";
  if (isMailto) linkLabel = "Email them";
  else if (href.includes("mail.google")) linkLabel = "Open in Gmail";
  else if (isHash || href.includes("approvals")) linkLabel = "Open Approvals";

  const title = item.title || String(item.text || "").split(":")[0];
  const detail = item.detail || (item.text && item.text.includes(":")
    ? item.text.slice(item.text.indexOf(":") + 1).trim()
    : "");
  const action = item.action || "";

  return (
    <li className="need-row">
      <div className="who">
        <strong>{title}</strong>
        {detail && <div className="meta">{detail}</div>}
        {action && <div className="need-action">{action}</div>}
      </div>
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
        <button type="button" onClick={() => onDismiss(item.id)}>Dismiss</button>
      </div>
    </li>
  );
}

function RundownBlock({ sections, fallbackText }) {
  if (!sections || !sections.length) {
    return (
      <div className="block compact rundown-block">
        <p className="label">Inbox rundown</p>
        <p className="sub">{fallbackText || "No rundown yet. Run Triage to refresh."}</p>
      </div>
    );
  }

  return (
    <div className="block compact rundown-block">
      <p className="label">Inbox rundown</p>
      <div className="rundown-sections">
        {sections.map(sec => {
          const people = sec.people || [];
          return (
            <div key={sec.id || sec.title} className="rundown-sec">
              <h4>
                {sec.title}
                {people.length > 0 && (
                  <span className="badge" data-n={String(people.length)}>{people.length}</span>
                )}
              </h4>
              {people.length === 0 ? (
                <p className="rundown-empty">{sec.empty || "None."}</p>
              ) : (
                <ul>
                  {people.map((p, i) => (
                    <li key={i} className="person-row tight">
                      <div className="who">
                        <strong>{p.name}</strong>
                        {p.company && <div className="meta">{p.company}</div>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {!!sec.more && (
                <p className="rundown-more">+{sec.more} more</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Overview({
  status, report, refreshReport, queueCount = 0,
  onRunStage, onShowApprovals, onShowReport,
}) {
  const tokens = status.tokens || {};
  const tokPct = tokens.pct || 0;
  const tokClass = tokens.limit_hit || tokPct >= 100 ? " bad" : (tokPct >= 60 ? " warn" : "");
  const tokDisplay = tokens.limit_hit ? "PAUSED" : (tokPct + "%");
  const hardPct = tokens.hard_pct != null ? tokens.hard_pct : 60;
  const tokDetail = tokens.limit_hit
    ? "Claude session limit. Try again after " + (tokens.limit_reset || "reset")
    : [
        (tokens.used || 0).toLocaleString(), " / ", (tokens.budget || 0).toLocaleString(),
        ", stops at ", hardPct, "%",
        ", ", (tokens.calls || 0), " calls since ", tokens.window_started || "start",
      ].join("");

  const stageLabel = status.running ? (status.stage || "running") : "idle";
  const lastRunText = status.running ? "running now…" : (status.detail || "idle");
  const rundownText = status.running && (!status.rundown || status.rundown === "Updating…")
    ? "Updating…"
    : (status.rundown || "");

  const sectionsFromStatus = Array.isArray(status.rundown_sections) ? status.rundown_sections : null;
  const sectionsFromReport = report?.inbox_agent?.rundown_sections;
  const rundownSections = (sectionsFromStatus && sectionsFromStatus.length)
    ? sectionsFromStatus
    : (Array.isArray(sectionsFromReport) && sectionsFromReport.length
      ? sectionsFromReport
      : parseLegacyRundown(rundownText));

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

  function cleanLimit(s) {
    return String(s)
      .replace(/^[^:]+:\s*/, "")
      .replace(/rate\/session limit, skipping all LLM stages this run:\s*/i, "")
      .replace(/\s*·\s*/g, ". ")
      .replace(/\s*—\s*/g, ". ");
  }

  return (
    <>
      <div className="section-head">
        <h2>Overview</h2>
        <p className="hint lastrun">Last run: <strong>{lastRunText}</strong></p>
      </div>
      {!status.running && (
        <p className="section-lede">
          What needs attention, then a clean inbox snapshot. Keep Approvals clear before another Full run.
        </p>
      )}

      {status.running ? (
        <div className="live-now">
          <span className="run-pulse" aria-hidden="true" />
          <div>
            <p className="label">Live run</p>
            <p className="live-now-title">{stageLabel}</p>
            <p className="sub">{status.detail || "Working…"}</p>
            {status.stream && <span className="stream">{status.stream}</span>}
            <p className="sub" style={{ marginTop: 10 }}>
              Meter {tokDisplay}. Open Activity for the event feed.
            </p>
          </div>
        </div>
      ) : (
        <div className="status-strip">
          <div className="block compact">
            <p className="label">Status</p>
            <p className="big">{stageLabel}</p>
            <p className="sub">{status.detail || "idle"}</p>
          </div>
          <div className={`block compact tok${tokClass}`}>
            <p className="label">LLM meter</p>
            <p className="big">{tokDisplay}</p>
            <p className="sub">{tokDetail}</p>
            <meter
              min="0"
              max="100"
              low={String(Math.max(1, hardPct - 15))}
              high={String(hardPct)}
              optimum="10"
              value={Math.min(100, tokPct)}
            />
          </div>
        </div>
      )}

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
              {normNeeds.slice(0, 10).map(it => (
                <NeedRow
                  key={it.id}
                  item={it}
                  onDismiss={handleDismiss}
                  onShowApprovals={onShowApprovals}
                  onShowReport={onShowReport}
                />
              ))}
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
                const short = cleanLimit(s);
                return <li key={"lim" + i}>{short.slice(0, 160)}{short.length > 160 ? "…" : ""}</li>;
              })}
              {other.slice(0, 4).map((s, i) => <li key={"oth" + i}>{s}</li>)}
            </ul>
          </div>
        )}

        <RundownBlock
          sections={rundownSections}
          fallbackText={rundownText || "No rundown yet. Run Triage to refresh."}
        />

        <p className="report-link-row">
          <a href="/dashboard" target="_blank" rel="noopener">Open full report ↗</a>
        </p>
      </div>
    </>
  );
}
