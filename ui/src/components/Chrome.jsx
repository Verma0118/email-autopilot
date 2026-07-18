import { useState, useRef, useEffect } from "react";
import { postRun } from "../api.js";
import { prettyStage } from "../pipeline.js";

const MODES = [
  { label: "Check email", stage: "triage", primary: true },
  { label: "Full run", stage: "" },
  { label: "Organize", stage: "organize" },
  { label: "Scout", stage: "scout" },
  { label: "Reply only", stage: "reply" },
  { label: "Bounce only", stage: "bounce" },
  { label: "Digest", stage: "digest" },
];

function modeLabel(stage) {
  return MODES.find(m => m.stage === stage)?.label || "Check email";
}

export default function Chrome({
  tab, onTabChange, status, queueBadge, overviewBadge,
  runMode, setRunMode, addToast, pollStatus,
}) {
  const running = !!status.running;
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef(null);
  const effectiveMode = runMode === undefined || runMode === null ? "triage" : runMode;
  const isAdvanced = effectiveMode !== "triage";

  useEffect(() => {
    if (!moreOpen) return;
    const onDoc = (ev) => {
      if (moreRef.current && !moreRef.current.contains(ev.target)) setMoreOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [moreOpen]);

  async function handleRun() {
    const stage = effectiveMode;
    const res = await postRun(stage || null);
    if (res.status === 409) { addToast("Already running"); return; }
    if (!res.ok) { addToast("Could not start run"); return; }
    addToast(modeLabel(stage) + " started");
    await pollStatus();
  }

  const runLabel = modeLabel(effectiveMode);

  return (
    <div className={`chrome${running ? " is-live" : ""}`}>
      <div className="chrome-inner">
        <div className="toprow">
          <div className="brand">
            <span className={`dot${running ? " live" : ""}`} aria-hidden="true" />
            <h1>EmailCRM</h1>
            <span
              className={`stagechip${running ? " live" : ""}`}
              title={running ? (status.detail || "") : "Ready"}
            >
              {running ? prettyStage(status.stage) : "Ready"}
            </span>
          </div>
          <div className="actions">
            {!running && (
              <div className="run-group" ref={moreRef}>
                <button
                  id="chrome-run-btn"
                  type="button"
                  className="btn btn-primary"
                  onClick={handleRun}
                >
                  {runLabel}
                </button>
                <button
                  type="button"
                  className={`btn btn-quiet btn-sm more-modes${isAdvanced ? " active" : ""}`}
                  aria-expanded={moreOpen}
                  aria-haspopup="listbox"
                  onClick={() => setMoreOpen(o => !o)}
                  title="Other run types"
                >
                  ▾
                </button>
                {moreOpen && (
                  <div className="mode-menu" role="listbox">
                    {MODES.map(m => (
                      <button
                        key={m.stage || "full"}
                        type="button"
                        role="option"
                        aria-selected={effectiveMode === m.stage}
                        className={effectiveMode === m.stage ? "active" : ""}
                        onClick={() => {
                          setRunMode(m.stage);
                          setMoreOpen(false);
                        }}
                      >
                        {m.label}
                        {m.primary && <span className="mode-hint">default</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        <nav className="tabs" role="tablist" aria-label="Panel sections">
          {[
            { id: "approvals", label: "Inbox", badge: queueBadge },
            { id: "overview", label: "Status", badge: overviewBadge },
            { id: "activity", label: "Live", badge: running ? 1 : 0 },
          ].map(t => (
            <button
              key={t.id}
              className="tab"
              role="tab"
              aria-selected={tab === t.id ? "true" : "false"}
              aria-controls={`panel-${t.id}`}
              onClick={() => onTabChange(t.id)}
            >
              {t.label}
              {t.id === "activity" && running ? (
                <span className="badge live-badge">
                  <span className="live-dot" aria-hidden="true" />
                  live
                </span>
              ) : (
                t.badge != null && (
                  <span className="badge" data-n={String(t.badge)}>
                    {t.badge}
                  </span>
                )
              )}
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
