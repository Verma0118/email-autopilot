import { useEffect, useState } from "react";
import { PIPELINE_STAGES, getPipelineHit, formatElapsed, prettyStage } from "../pipeline.js";

export default function RunBanner({ status, onStop, onShowActivity }) {
  const running = !!status.running;
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

  if (!running) return null;

  const hit = getPipelineHit(status.stage);
  const stage = prettyStage(status.stage);
  const detail = status.detail || "Working…";
  const elapsed = startedAt ? formatElapsed(now - startedAt) : "0:00";
  const progress = hit < 0 ? 8 : Math.round(((hit + 0.55) / PIPELINE_STAGES.length) * 100);

  return (
    <div className="run-banner" role="status" aria-live="polite">
      <div className="run-banner-inner">
        <div className="run-banner-main">
          <span className="run-pulse" aria-hidden="true" />
          <div className="run-banner-copy">
            <p className="run-banner-title">
              Running · {stage}
              {status.stream ? <span className="run-stream">{status.stream}</span> : null}
            </p>
            <p className="run-banner-detail">{detail}</p>
          </div>
        </div>
        <div className="run-banner-meta">
          <span className="run-elapsed" title="Elapsed">{elapsed}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onShowActivity}>
            Activity
          </button>
          <button type="button" className="btn btn-danger btn-sm" onClick={onStop}>
            Stop
          </button>
        </div>
      </div>
      <div className="run-progress" aria-hidden="true">
        <div className="run-progress-bar" style={{ width: `${Math.min(96, progress)}%` }} />
      </div>
      <div className="run-pipeline" aria-label="Pipeline stages">
        {PIPELINE_STAGES.map(([key, label], i) => {
          let cls = "step";
          if (hit >= 0) {
            if (i < hit) cls += " done";
            else if (i === hit) cls += " live";
          }
          return <span key={key} className={cls}>{label}</span>;
        })}
      </div>
    </div>
  );
}
