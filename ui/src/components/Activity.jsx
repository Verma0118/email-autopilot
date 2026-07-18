const PIPELINE_STAGES = [
  ["inbox", "Inbox"],
  ["reply", "Reply"],
  ["organize", "Organize"],
  ["scout", "Scout"],
  ["bounce", "Bounce"],
  ["digest", "Digest"],
];

function getPipelineHit(stageLabel) {
  const cur = String(stageLabel || "").toLowerCase();
  const order = PIPELINE_STAGES.map(([k]) => k);
  for (let i = 0; i < order.length; i++) {
    if (cur.includes(order[i])) return i;
  }
  return -1;
}

export default function Activity({ status }) {
  const running = !!status.running;
  const hit = getPipelineHit(status.stage);
  const events = (status.events || []).slice().reverse().slice(0, 40);

  return (
    <>
      <div className="section-head">
        <h2>Activity</h2>
      </div>
      <p className="section-lede">Live pipeline stages and events from the current run.</p>

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
          <li>no events yet — hit Run now</li>
        ) : (
          events.map((e, i) => (
            <li key={i}>
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
