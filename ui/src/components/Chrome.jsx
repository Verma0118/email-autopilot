import { useState, useRef, useEffect } from "react";
import { postRun, postStop, postUpdate } from "../api.js";

const PRIMARY_MODES = [
  { label: "Full", stage: "" },
  { label: "Triage", stage: "triage" },
  { label: "Organize", stage: "organize" },
  { label: "Scout", stage: "scout" },
];

const MORE_MODES = [
  { label: "Reply", stage: "reply" },
  { label: "Bounce", stage: "bounce" },
  { label: "Digest", stage: "digest" },
];

const ALL_MODES = [...PRIMARY_MODES, ...MORE_MODES];

function modeLabel(stage) {
  return ALL_MODES.find(m => m.stage === stage)?.label || "Full";
}

export default function Chrome({
  tab, onTabChange, status, queueBadge, overviewBadge,
  runMode, setRunMode, addToast, pollStatus, costHint,
}) {
  const running = !!status.running;
  const stageOnly = running ? (status.stage || "running") : "idle";
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef(null);
  const moreSelected = MORE_MODES.some(m => m.stage === runMode);

  useEffect(() => {
    if (!moreOpen) return;
    const onDoc = (ev) => {
      if (moreRef.current && !moreRef.current.contains(ev.target)) setMoreOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [moreOpen]);

  async function handleRun() {
    const res = await postRun(runMode || null);
    if (res.status === 409) { addToast("Already running"); return; }
    if (!res.ok) { addToast("Could not start run"); return; }
    addToast(modeLabel(runMode) + " run started");
    await pollStatus();
  }

  async function handleStop() {
    const res = await postStop();
    if (!res.ok) { addToast("Could not stop"); return; }
    addToast("Stop requested");
    await pollStatus();
  }

  async function handleUpdate() {
    addToast("Pulling latest from GitHub…");
    const res = await postUpdate();
    if (!res.ok || !res.data.ok) {
      addToast(res.data.error || res.data.message || "Update failed. Check git on this Mac.");
      return;
    }
    addToast(res.data.changed ? "Updated. Reloading panel…" : "Already latest. Reloading…");
    setTimeout(() => location.reload(), 1400);
  }

  return (
    <div className="chrome">
      <div className="chrome-inner">
        <div className="toprow">
          <div className="brand">
            <span className={`dot${running ? " live" : ""}`} aria-hidden="true" />
            <h1>EmailCRM</h1>
            <span
              className="stagechip"
              title={running ? (status.detail || stageOnly) : "idle"}
            >
              {stageOnly}
            </span>
          </div>
          <div className="actions">
            <span className="chrome-label">Mode</span>
            <div className="run-modes" title="What to run" aria-label="Run mode">
              {PRIMARY_MODES.map(m => (
                <button
                  key={m.stage || "full"}
                  type="button"
                  className={`chip${runMode === m.stage ? " active" : ""}`}
                  onClick={() => setRunMode(m.stage)}
                >
                  {m.label}
                </button>
              ))}
              <div className="mode-more" ref={moreRef}>
                <button
                  type="button"
                  className={`chip more-trigger${moreSelected ? " active" : ""}`}
                  aria-expanded={moreOpen}
                  aria-haspopup="listbox"
                  onClick={() => setMoreOpen(o => !o)}
                >
                  More{moreSelected ? `: ${modeLabel(runMode)}` : ""}
                </button>
                {moreOpen && (
                  <div className="mode-more-menu" role="listbox">
                    {MORE_MODES.map(m => (
                      <button
                        key={m.stage}
                        type="button"
                        role="option"
                        aria-selected={runMode === m.stage}
                        className={runMode === m.stage ? "active" : ""}
                        onClick={() => {
                          setRunMode(m.stage);
                          setMoreOpen(false);
                        }}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            {costHint?.text && (
              <span className="cost-hint" title={costHint.text}>
                {costHint.short || costHint.text}
              </span>
            )}
            <button
              id="chrome-run-btn"
              type="button"
              className="btn btn-primary"
              disabled={running}
              onClick={handleRun}
            >
              Run now
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={!running}
              onClick={handleStop}
            >
              Stop
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              title="git pull + reload panel"
              onClick={handleUpdate}
            >
              Update
            </button>
          </div>
        </div>
        <nav className="tabs" role="tablist" aria-label="Panel sections">
          {[
            { id: "approvals", label: "Approvals", badge: queueBadge },
            { id: "overview", label: "Overview", badge: overviewBadge },
            { id: "activity", label: "Activity", badge: 0 },
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
              {t.badge != null && (
                <span className="badge" data-n={String(t.badge)}>
                  {t.badge}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
