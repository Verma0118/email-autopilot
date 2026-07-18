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

function formatElapsed(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function prettyStage(stage) {
  const raw = String(stage || "running").trim();
  if (!raw) return "Running";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export { PIPELINE_STAGES, getPipelineHit, formatElapsed, prettyStage };
