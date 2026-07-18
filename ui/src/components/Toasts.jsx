export default function Toasts({ toasts, onRemove }) {
  return (
    <div className="toast-wrap" aria-live="polite">
      {toasts.map(t => (
        <div key={t.id} className="toast">
          <span>{t.content}</span>
          <button
            type="button"
            className="dismiss"
            aria-label="Dismiss"
            onClick={() => onRemove(t.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
