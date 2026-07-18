export default function HelpOverlay({ open, onClose }) {
  return (
    <div
      className={`help-overlay${open ? " is-open" : ""}`}
      aria-hidden={!open}
      onClick={(ev) => { if (ev.target === ev.currentTarget) onClose(); }}
    >
      <div className="help-card" role="dialog" aria-modal="true" aria-labelledby="help-title">
        <h2 id="help-title">Keyboard shortcuts</h2>
        <dl>
          <dt><span className="kbd">1</span>–<span className="kbd">4</span></dt>
          <dd>Approvals / Overview / Activity / Report</dd>
          <dt><span className="kbd">j</span> / <span className="kbd">k</span></dt>
          <dd>Next / previous queue item</dd>
          <dt><span className="kbd">a</span></dt>
          <dd>Approve focused (asks to confirm)</dd>
          <dt><span className="kbd">s</span></dt>
          <dd>Skip focused for 7 days</dd>
          <dt><span className="kbd">o</span></dt>
          <dd>Toggle edit body</dd>
          <dt><span className="kbd">/</span></dt>
          <dd>Focus search</dd>
          <dt><span className="kbd">?</span></dt>
          <dd>Toggle this help</dd>
          <dt><span className="kbd">Esc</span></dt>
          <dd>Close help</dd>
        </dl>
        <button
          type="button"
          className="btn btn-primary close"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </div>
  );
}
