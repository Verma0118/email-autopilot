export default function HelpOverlay({ open, onClose }) {
  return (
    <div
      className={`help-overlay${open ? " is-open" : ""}`}
      aria-hidden={!open}
      onClick={(ev) => { if (ev.target === ev.currentTarget) onClose(); }}
    >
      <div className="help-card" role="dialog" aria-modal="true" aria-labelledby="help-title">
        <h2 id="help-title">Shortcuts</h2>
        <dl>
          <dt><span className="kbd">1</span></dt>
          <dd>Inbox</dd>
          <dt><span className="kbd">2</span></dt>
          <dd>Status</dd>
          <dt><span className="kbd">3</span></dt>
          <dd>Live</dd>
          <dt><span className="kbd">j</span> / <span className="kbd">k</span></dt>
          <dd>Next / previous draft</dd>
          <dt><span className="kbd">a</span></dt>
          <dd>Approve focused draft</dd>
          <dt><span className="kbd">s</span></dt>
          <dd>Skip focused for 7 days</dd>
          <dt><span className="kbd">o</span></dt>
          <dd>Edit body</dd>
          <dt><span className="kbd">?</span></dt>
          <dd>This help</dd>
          <dt><span className="kbd">Esc</span></dt>
          <dd>Close</dd>
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
