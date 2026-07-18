import { useEffect, useState } from "react";
import { PIPELINE_STAGES, getPipelineHit, formatElapsed, prettyStage } from "../pipeline.js";

export default function RunBanner({ status, onStop, onShowActivity }) {
  const running = !!status.running;
  const [startedAt, setStartedAt] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (running) {
      setStartedAt((prev) => prev || Date.now());
      const t = setInterval(() => setNow(Date.now()), 1000);
      return () => clearInterval(t);
    }
    setStartedAt(null);
  }, [running]);

  useEffect(() => {
    if (!running) return;
    setTick((n) => n + 1);
  }, [running, status.stage, status.detail]);

  if (!running) return null;

  const hit = getPipelineHit(status.stage);
  const stage = prettyStage(status.stage);
  const detail = status.detail || "Working…";
  const elapsed = startedAt ? formatElapsed(now - startedAt) : "0:00";
  const progress = hit < 0 ? 12 : Math.round(((hit + 0.55) / PIPELINE_STAGES.length) * 100);

  return (
    <div className="run-banner" role="status" aria-live="polite">
      <div className="run-banner-inner">
        <div className="run-banner-main">
          <span className="run-pulse" aria-hidden="true" />
          <div className="run-banner-copy">
            <p className="run-banner-title">
              {stage}
              {status.stream ? <span className="run-stream">{status.stream}</span> : null}
            </p>
            <p className="run-banner-detail" key={`d-${tick}`}>
              {detail}
              <span className="live-caret" aria-hidden="true" />
            </p>
          </div>
        </div>
        <div className="run-banner-meta">
          <span className="run-elapsed" title="Elapsed">{elapsed}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onShowActivity}>
            Live
          </button>
          <button type="button" className="btn btn-danger btn-sm" onClick={onStop}>
            Stop
          </button>
        </div>
      </div>
      <div className="run-progress" aria-hidden="true">
        <div
          className={`run-progress-bar${hit < 0 ? " indeterminate" : ""}`}
          style={hit < 0 ? undefined : { width: `${Math.min(96, progress)}%` }}
        />
      </div>
    </div>
  );
}
