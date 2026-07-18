import { postRun, postStop, postUpdate } from "../api.js";

const MODES = [
  { label: "Full", stage: "" },
  { label: "Triage", stage: "triage" },
  { label: "Reply", stage: "reply" },
  { label: "Bounce", stage: "bounce" },
  { label: "Scout", stage: "scout" },
  { label: "Organize", stage: "organize" },
  { label: "Digest", stage: "digest" },
];

export default function Chrome({
  tab, onTabChange, status, queueBadge, overviewBadge,
  runMode, setRunMode, addToast, refreshQueue, refreshReport,
  pollStatus, showTab, costHint,
}) {
  const running = !!status.running;
  const stageLabel = running ? (status.stage || "running") : "idle";
  const stageChip = running
    ? stageLabel + (status.detail ? " · " + status.detail : "")
    : "idle";

  async function handleRun() {
    const res = await postRun(runMode || null);
    if (res.status === 409) { addToast("Already running"); return; }
    if (!res.ok) { addToast("Could not start run"); return; }
    const label = MODES.find(m => m.stage === runMode)?.label || "Full";
    addToast(label + " run started");
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
      addToast(res.data.error || res.data.message || "Update failed — check git on this Mac");
      return;
    }
    addToast(res.data.changed ? "Updated — reloading panel…" : "Already latest — reloading…");
    setTimeout(() => location.reload(), 1400);
  }

  return (
    <div className="chrome">
      <div className="chrome-inner">
        <div className="toprow">
          <div className="brand">
            <span className={`dot${running ? " live" : ""}`} aria-hidden="true" />
            <h1>EmailCRM</h1>
            <span className="stagechip">{stageChip}</span>
          </div>
          <div className="actions">
            <span className="chrome-label">Mode</span>
            <div className="run-modes" title="What to run" aria-label="Run mode">
              {MODES.map(m => (
                <button
                  key={m.stage || "full"}
                  type="button"
                  className={`chip${runMode === m.stage ? " active" : ""}`}
                  onClick={() => setRunMode(m.stage)}
                >
                  {m.label}
                </button>
              ))}
            </div>
            {costHint && <span className="cost-hint">{costHint}</span>}
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
            { id: "report", label: "Report", badge: 0 },
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
