async function apiFetch(path, opts = {}) {
  const res = await fetch(path, opts);
  let data = {};
  try { data = await res.json(); } catch (_) {}
  return { ok: res.ok, status: res.status, data };
}

export async function getQueue() {
  const { data } = await apiFetch("/queue");
  return Array.isArray(data) ? data : [];
}

export async function getHistory() {
  const { data } = await apiFetch("/history");
  return Array.isArray(data) ? data : [];
}

export async function getStatus() {
  const { data } = await apiFetch("/status");
  return data;
}

export async function getReport() {
  const { data } = await apiFetch("/report");
  return data;
}

export async function getVersion() {
  const { data } = await apiFetch("/version");
  return data;
}

function postJSON(path, body) {
  return apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function postRun(stage) {
  return postJSON("/run", { stage: stage || null });
}

export async function postStop() {
  return apiFetch("/stop", { method: "POST" });
}

export async function postUpdate() {
  return postJSON("/update", {});
}

export async function postSave(payload) {
  return postJSON("/save", payload);
}

export async function postApprove(payload) {
  return postJSON("/approve", payload);
}

export async function postSkip(id, skipUntil) {
  return postJSON("/skip", { id, skip_until: skipUntil });
}

export async function postUndo(id) {
  return postJSON("/undo", { id });
}

export async function postDismiss(id) {
  return postJSON("/dismiss", { id });
}
