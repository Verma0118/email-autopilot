import { useEffect, useState } from "react";
import { PIPELINE_STAGES, getPipelineHit, formatElapsed, prettyStage } from "../pipeline.js";

export default function Activity({ status }) {
  const running = !!status.running;
  const hit = getPipelineHit(status.stage);
  const events = (status.events || []).slice().reverse().slice(0, 40);
  const [startedAt, setStartedAt] = useState(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (running) {
      setStartedAt((prev) => prev || Date.now());
      const t = setInterval(() => setNow(Date.now()), 1000);
      return () => clearInterval(t);
    }
    setStartedAt(null);
  }, [running]);

  const elapsed = startedAt ? formatElapsed(now - startedAt) : null;

  return (
    <>
      <div className="section-head">
        <h2>Activity</h2>
        {running && elapsed && <p className="hint">Elapsed {elapsed}</p>}
      </div>
      <p className="section-lede">
        {running
          ? "Watch the current stage and live event feed while Autopilot works."
          : "When a run starts, stages and events appear here so you can see progress."}
      </p>

      {running ? (
        <div className="live-now">
          <span className="run-pulse" aria-hidden="true" />
          <div>
            <p className="label">Now</p>
            <p className="live-now-title">{prettyStage(status.stage)}</p>
            <p className="sub">{status.detail || "Working…"}</p>
            {status.stream && <span className="stream">{status.stream}</span>}
          </div>
        </div>
      ) : (
        <div className="idle-card">
          <p className="idle-title">Idle</p>
          <p className="sub">Nothing is running. Pick a mode in the header and hit Run to start.</p>
        </div>
      )}

      <div className="pipeline" aria-label="Pipeline stages">
        {PIPELINE_STAGES.map(([key, label], i) => {
          let cls = "step";
          if (running && hit >= 0) {
            if (i < hit) cls += " done";
            else if (i === hit) cls += " live";
          }
          return <span key={key} className={cls}>{label}</span>;
        })}
      </div>

      <ul className="feed-list" aria-live="polite">
        {events.length === 0 ? (
          <li className="feed-empty">
            {running ? "Waiting for the first event…" : "No recent events."}
          </li>
        ) : (
          events.map((e, i) => (
            <li key={`${e.ts || ""}-${i}`} className={i === 0 && running ? "newest" : ""}>
              <span className="t">{e.ts}</span>
              {e.stream && <span className="s">{e.stream}</span>}
              <span>{e.detail || e.stage || ""}</span>
            </li>
          ))
        )}
      </ul>
    </>
  );
}
