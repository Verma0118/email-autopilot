import { useEffect, useRef, useState } from "react";
import { PIPELINE_STAGES, getPipelineHit, formatElapsed, prettyStage } from "../pipeline.js";

export default function Activity({ status }) {
  const running = !!status.running;
  const hit = getPipelineHit(status.stage);
  const events = (status.events || []).slice().reverse().slice(0, 40);
  const [startedAt, setStartedAt] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [flash, setFlash] = useState(0);
  const prevDetail = useRef("");

  useEffect(() => {
    if (running) {
      setStartedAt((prev) => prev || Date.now());
      const t = setInterval(() => setNow(Date.now()), 1000);
      return () => clearInterval(t);
    }
    setStartedAt(null);
  }, [running]);

  useEffect(() => {
    const d = status.detail || "";
    if (running && d && d !== prevDetail.current) {
      setFlash((n) => n + 1);
      prevDetail.current = d;
    }
  }, [running, status.detail]);

  const elapsed = startedAt ? formatElapsed(now - startedAt) : null;

  return (
    <>
      <div className="section-head">
        <h2>Activity</h2>
        {running && elapsed && (
          <p className="hint live-clock">
            <span className="run-pulse sm" aria-hidden="true" />
            {elapsed}
          </p>
        )}
      </div>
      <p className="section-lede">
        {running
          ? "Live stages and event feed while Autopilot works."
          : "Start a run to see stages and events update here in real time."}
      </p>

      {running ? (
        <div className="live-now" key={`now-${flash}`}>
          <span className="run-pulse" aria-hidden="true" />
          <div>
            <p className="label">Now</p>
            <p className="live-now-title">{prettyStage(status.stage)}</p>
            <p className="sub live-detail">
              {status.detail || "Working…"}
              <span className="live-caret" aria-hidden="true" />
            </p>
            {status.stream && <span className="stream">{status.stream}</span>}
          </div>
        </div>
      ) : (
        <div className="idle-card">
          <p className="idle-title">Quiet</p>
          <p className="sub">Nothing is running. Choose a mode up top and hit Run.</p>
        </div>
      )}

      <div className={`pipeline${running ? " is-live" : ""}`} aria-label="Pipeline stages">
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
          <li className={`feed-empty${running ? " waiting" : ""}`}>
            {running ? (
              <>
                Waiting for the first event
                <span className="live-caret" aria-hidden="true" />
              </>
            ) : (
              "No recent events."
            )}
          </li>
        ) : (
          events.map((e, i) => (
            <li
              key={`${e.ts || ""}-${e.detail || ""}-${i}`}
              className={i === 0 && running ? "newest" : ""}
              style={i === 0 && running ? { animationDelay: "0ms" } : undefined}
            >
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
