import { useState, useEffect, useRef } from "react";
import { postApprove, postSkip, postUndo, postSave, postRun } from "../api.js";

const KIND_PRIORITY = { reply: 0, bounce: 1, followup: 2, outreach: 3 };

const KIND_LABELS = {
  reply: "Reply",
  bounce: "Bounce",
  outreach: "Outreach",
  followup: "Follow-up",
};

const FILTERS = [
  { id: "all", label: "All" },
  { id: "reply", label: "Replies" },
  { id: "bounce", label: "Bounce" },
  { id: "outreach", label: "Outreach" },
  { id: "followup", label: "Follow-up" },
];

const TRACK_CHIPS = [
  { id: "startup", label: "Startup" },
  { id: "internship", label: "Internship" },
  { id: "nobe", label: "NOBE" },
];

function sanitizeHtml(html) {
  return String(html ?? "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, "")
    .replace(/\son\w+=("[^"]*"|'[^']*'|[^\s>]+)/gi, "");
}

function sortQueue(q) {
  return [...q].sort((a, b) => {
    const pa = KIND_PRIORITY[a.kind] ?? 99;
    const pb = KIND_PRIORITY[b.kind] ?? 99;
    if (pa !== pb) return pa - pb;
    return (a.created || "").localeCompare(b.created || "");
  });
}

function matchesTrack(item, trackId) {
  const t = String(item.track || "").toLowerCase();
  return t.includes(trackId);
}

function filterQueue(q, filter, trackFilter, search) {
  let out = q;
  if (filter !== "all") out = out.filter(i => i.kind === filter);
  if (trackFilter) out = out.filter(i => matchesTrack(i, trackFilter));
  if (search) {
    out = out.filter(i => {
      const hay = [i.name, i.company, i.email, i.subject, i.track, i.why]
        .map(x => String(x || "").toLowerCase()).join(" ");
      return hay.includes(search);
    });
  }
  return out;
}

function ContextBlock({ item }) {
  const m = item.meta || {};
  if (item.kind === "reply" && m.thread_preview) {
    return (
      <details className="context">
        <summary>Thread context</summary>
        <pre>{m.thread_preview}</pre>
      </details>
    );
  }
  if (item.kind === "bounce") {
    const oldEmail = m.old_email || "";
    const newEmail = m.corrected_email || item.email || "";
    if (!oldEmail && !newEmail) return null;
    return (
      <details className="context" open>
        <summary>Bounce fix</summary>
        <div className="ctx-body">
          <strong>Email</strong> {oldEmail || "?"} → {newEmail || "?"}
        </div>
      </details>
    );
  }
  if (item.kind === "outreach") {
    const parts = [];
    if (m.role) parts.push(<span key="role"><strong>Role</strong> {m.role}</span>);
    if (m.linkedin) {
      parts.push(
        <span key="li">
          <strong>LinkedIn</strong>{" "}
          <a href={m.linkedin} target="_blank" rel="noopener">Open LinkedIn</a>
        </span>
      );
    }
    if (m.attachments && m.attachments.length) {
      parts.push(
        <span key="att">
          <strong>Attachments</strong> {m.attachments.join(", ")}
          <span className="att-note"> (if file is in assets/)</span>
        </span>
      );
    }
    if (m.is_uiuc_alum != null) {
      parts.push(
        <span key="alum">
          <strong>Alum</strong> {m.is_uiuc_alum ? "UIUC alum" : "Not UIUC alum"}
        </span>
      );
    }
    if (m.company_signal) parts.push(<span key="sig"><strong>Signal</strong> {m.company_signal}</span>);
    if (m.hooks) parts.push(<span key="hooks"><strong>Hooks</strong><br />{String(m.hooks).replace(/\n/g, "; ")}</span>);
    if (m.email_basis) parts.push(<span key="basis"><strong>Email basis</strong> {m.email_basis}</span>);
    if (m.brief_file) parts.push(
      <a key="brief" href={"/brief/" + encodeURIComponent(m.brief_file)}>Full brief</a>
    );
    if (!parts.length) return null;
    return (
      <details className="context">
        <summary>Research context</summary>
        <div className="ctx-body">
          {parts.map((p, i) => <div key={i}>{p}</div>)}
        </div>
      </details>
    );
  }
  return null;
}

function QueueItem({
  item, focused, onFocus, onApproved, onSkipped,
  addToast, refreshQueue, refreshHistory, editing, onToggleEdit,
}) {
  const subjectRef = useRef(null);
  const emailRef = useRef(null);
  const bodyRef = useRef(null);
  const saveTimer = useRef(null);
  const detailsRef = useRef(null);

  const threadHref = item.thread_id
    ? ("https://mail.google.com/mail/u/0/#inbox/" + encodeURIComponent(item.thread_id))
    : "";

  useEffect(() => {
    if (detailsRef.current) detailsRef.current.open = !!editing;
  }, [editing]);

  function scheduleSave() {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      const payload = { id: item.id };
      if (subjectRef.current) payload.subject = subjectRef.current.value;
      if (emailRef.current) payload.email = emailRef.current.value.trim();
      if (bodyRef.current) payload.body_html = bodyRef.current.innerHTML;
      await postSave(payload).catch(() => {});
    }, 600);
  }

  async function handleApprove(btn, { confirm = false } = {}) {
    const who = item.name || "this draft";
    if (confirm && !window.confirm("Approve draft for " + who + " → create Gmail draft?")) return;
    if (btn) { btn.disabled = true; btn.textContent = "…"; }
    const payload = { id: item.id };
    if (subjectRef.current) payload.subject = subjectRef.current.value;
    if (emailRef.current) payload.email = emailRef.current.value.trim();
    if (bodyRef.current && editing) payload.body_html = bodyRef.current.innerHTML;
    const res = await postApprove(payload);
    if (!res.ok) {
      if (btn) { btn.textContent = "error"; btn.disabled = false; }
      addToast(res.data.error || "Something went wrong");
      return;
    }
    const link = res.data.draft_link || "https://mail.google.com/mail/u/0/#drafts";
    onApproved(item.id, link, res.data);
    await Promise.all([refreshQueue(), refreshHistory()]);
  }

  async function handleSkip(skipUntil) {
    const res = await postSkip(item.id, skipUntil);
    if (!res.ok) { addToast(res.data.error || "Something went wrong"); return; }
    const label = skipUntil === "forever" ? "forever" : (skipUntil + "d");
    onSkipped(item.id, label);
    await Promise.all([refreshQueue(), refreshHistory()]);
  }

  async function handleCopy() {
    const html = editing
      ? (bodyRef.current?.innerHTML || "")
      : sanitizeHtml(item.body_html);
    const text = editing
      ? (bodyRef.current?.innerText || "")
      : String(item.body_html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/html": new Blob([html], { type: "text/html" }),
          "text/plain": new Blob([text], { type: "text/plain" }),
        })
      ]);
    } catch (_) {
      try { await navigator.clipboard.writeText(text); } catch (__) {}
    }
    addToast("Body copied");
  }

  const previewHtml = sanitizeHtml(item.body_html);
  const kindLabel = KIND_LABELS[item.kind] || item.kind;

  return (
    <li
      className={`q-item${focused ? " focused" : ""}`}
      data-id={item.id}
      onClick={(ev) => {
        if (ev.target.closest("button, a, summary, details, input, [contenteditable]")) return;
        onFocus();
      }}
    >
      <div className="q-meta">
        {kindLabel && <span className={`kind-badge kind-${item.kind || "other"}`}>{kindLabel}</span>}
        {item.track && <span className="stream" style={{ margin: 0 }}>{item.track}</span>}
        <strong>{item.name}</strong>
        <span className="sub">{item.company}</span>
      </div>
      {item.why && <p className="q-why">{item.why}</p>}
      <ContextBlock item={item} />
      {threadHref && (
        <a className="thread-link" href={threadHref} target="_blank" rel="noopener">
          Open thread in Gmail
        </a>
      )}
      <div className="q-fields">
        <div>
          <label htmlFor={`email-${item.id}`}>To</label>
          <input
            ref={emailRef}
            className="email-edit"
            id={`email-${item.id}`}
            type="email"
            defaultValue={item.email || ""}
            autoComplete="off"
            onChange={scheduleSave}
          />
        </div>
        <div>
          <label htmlFor={`subj-${item.id}`}>Subject</label>
          <input
            ref={subjectRef}
            className="subj-edit"
            id={`subj-${item.id}`}
            defaultValue={item.subject || ""}
            onChange={scheduleSave}
          />
        </div>
      </div>

      {!editing && (
        <div
          className="body-preview"
          dangerouslySetInnerHTML={{ __html: previewHtml || "<p><em>Empty body</em></p>" }}
        />
      )}

      <details
        ref={detailsRef}
        className="preview"
        onToggle={(ev) => {
          if (ev.currentTarget.open !== editing) onToggleEdit(ev.currentTarget.open);
        }}
      >
        <summary>{editing ? "Editing body" : "Edit email body"}</summary>
        <div
          ref={bodyRef}
          className="body-edit"
          contentEditable
          suppressContentEditableWarning
          spellCheck
          dangerouslySetInnerHTML={{ __html: previewHtml }}
          onInput={scheduleSave}
          onPaste={(ev) => {
            ev.preventDefault();
            const text = (ev.clipboardData || window.clipboardData).getData("text/plain");
            document.execCommand("insertText", false, text);
          }}
        />
        <p className="edit-hint">Paste is plain text. Edits autosave; Approve creates the Gmail draft.</p>
      </details>

      <div className="q-actions">
        <button
          type="button"
          className="btn btn-good approve"
          onClick={(ev) => handleApprove(ev.currentTarget, { confirm: false })}
        >
          Approve
        </button>
        <button type="button" className="btn btn-quiet skip" onClick={() => handleSkip(7)}>
          Skip 7 days
        </button>
        <details className="more-actions">
          <summary>More</summary>
          <div className="more-actions-menu">
            <button type="button" onClick={() => handleSkip(3)}>Skip 3 days</button>
            <button type="button" onClick={() => handleSkip("forever")}>Skip forever</button>
            <button type="button" onClick={handleCopy}>Copy body</button>
          </div>
        </details>
      </div>
    </li>
  );
}

export default function Approvals({
  queue, history, needsCount, onShowOverview, addToast,
  refreshQueue, refreshHistory, setRunMode, onRunStage,
}) {
  const [filter, setFilter] = useState("all");
  const [trackFilter, setTrackFilter] = useState("");
  const [search, setSearch] = useState("");
  const [focusIdx, setFocusIdx] = useState(0);
  const [editingId, setEditingId] = useState(null);

  const sorted = sortQueue(queue);
  const filtered = filterQueue(sorted, filter, trackFilter, search);

  const nOut = sorted.filter(i => i.kind === "outreach").length;
  const hasOutreach = nOut > 0;

  function setFocus(i) {
    const idx = Math.max(0, Math.min(i, filtered.length - 1));
    setFocusIdx(idx);
    const items = document.querySelectorAll(".q-item");
    if (items[idx]) items[idx].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function advanceAfterRemove(removedId) {
    const idx = filtered.findIndex(i => i.id === removedId);
    const nextLen = Math.max(0, filtered.length - 1);
    if (nextLen === 0) {
      setFocusIdx(0);
      setEditingId(null);
      return;
    }
    const nextIdx = Math.min(Math.max(idx, 0), nextLen - 1);
    setFocusIdx(nextIdx);
    setEditingId(null);
  }

  function onApproved(id, link, data = {}) {
    const bits = ["Draft created."];
    if (data.warn) bits.push(String(data.warn));
    if (data.attached && data.attached.length) {
      bits.push("Attached: " + data.attached.join(", "));
    }
    addToast(
      <span>
        {bits.join(" ")}{" "}
        <a href={link} target="_blank" rel="noopener">Open in Gmail</a>
        {" · "}
        <button type="button" className="linkish" onClick={() => handleUndo(id)}>Undo</button>
      </span>
    );
    advanceAfterRemove(id);
  }

  function onSkipped(id, label) {
    addToast(
      <span>
        Snoozed {label}.{" "}
        <button className="linkish" onClick={() => handleUndo(id)}>Undo</button>
      </span>
    );
    advanceAfterRemove(id);
  }

  async function handleUndo(id) {
    const { ok, data } = await postUndo(id);
    if (ok) {
      addToast(data.undid === "approved" ? "Approval undone. Draft deleted." : "Restored to queue.");
      await Promise.all([refreshQueue(), refreshHistory()]);
    } else {
      addToast(data.error || "Could not undo");
    }
  }

  async function startTriage() {
    setRunMode("triage");
    if (onRunStage) {
      await onRunStage("triage");
    } else {
      const res = await postRun("triage");
      if (res.ok) addToast("Check email started");
      else addToast(res.status === 409 ? "Already running" : "Could not start run");
    }
  }

  // keyboard shortcuts scoped to approvals
  useEffect(() => {
    const onKey = (ev) => {
      const approvalsPanel = document.getElementById("panel-approvals");
      if (!approvalsPanel?.classList.contains("active")) return;
      if (ev.target.matches("input, textarea, select, [contenteditable]") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const key = ev.key.toLowerCase();
      if (!filtered.length) return;
      if (key === "j" || key === "arrowdown") { ev.preventDefault(); setFocus(focusIdx + 1); }
      else if (key === "k" || key === "arrowup") { ev.preventDefault(); setFocus(focusIdx - 1); }
      else if (key === "a") {
        ev.preventDefault();
        const item = filtered[focusIdx];
        if (item) {
          const btn = document.querySelector(`.q-item[data-id="${CSS.escape(item.id)}"] button.approve`);
          if (btn && window.confirm("Approve draft for " + (item.name || "this draft") + " → Gmail?")) {
            btn.click();
          }
        }
      } else if (key === "s") {
        ev.preventDefault();
        const item = filtered[focusIdx];
        if (item) {
          postSkip(item.id, 7).then(({ ok, data }) => {
            if (ok) { onSkipped(item.id, "7d"); refreshQueue(); refreshHistory(); }
            else addToast(data.error || "Error");
          });
        }
      } else if (key === "o") {
        ev.preventDefault();
        const item = filtered[focusIdx];
        if (item) setEditingId(editingId === item.id ? null : item.id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered, focusIdx, editingId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (focusIdx >= filtered.length && filtered.length > 0) {
      setFocusIdx(filtered.length - 1);
    }
  }, [filtered.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Focused card: keep preview readable; don't force edit open
  useEffect(() => {
    const item = filtered[focusIdx];
    if (item && editingId && editingId !== item.id) setEditingId(null);
  }, [focusIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  const searching = search || filter !== "all" || trackFilter;
  const showFilters = sorted.length >= 4 || searching;
  const showTrackChips = hasOutreach && nOut >= 3;

  return (
    <>
      <div className="section-head">
        <h2>
          Inbox
          {sorted.length > 0 && (
            <span className="qsplit">{sorted.length} to review</span>
          )}
        </h2>
        {sorted.length > 0 && (
          <p className="hint">
            <span className="kbd">j</span>/<span className="kbd">k</span> · <span className="kbd">a</span> approve · <span className="kbd">s</span> skip
          </p>
        )}
      </div>
      {sorted.length > 0 && (
        <p className="section-lede">
          Read, tweak if needed, then Approve. That creates a Gmail draft only. Nothing sends.
        </p>
      )}

      {needsCount > 0 && sorted.length === 0 && (
        <p className="urgency-banner">
          <span>{needsCount} item{needsCount === 1 ? "" : "s"} on Status need a look</span>
          <button type="button" onClick={onShowOverview}>Open Status</button>
        </p>
      )}

      {showFilters && (
      <div className="filters" id="qfilters">
        {FILTERS.map(f => (
          <button
            key={f.id}
            type="button"
            className={`chip${filter === f.id ? " active" : ""}`}
            onClick={() => { setFilter(f.id); }}
          >
            {f.label}
          </button>
        ))}
        {showTrackChips && (
          <span className="track-filters" aria-label="Track filters">
            {TRACK_CHIPS.map(t => (
              <button
                key={t.id}
                type="button"
                className={`chip track-chip${trackFilter === t.id ? " active" : ""}`}
                onClick={() => setTrackFilter(trackFilter === t.id ? "" : t.id)}
              >
                {t.label}
              </button>
            ))}
          </span>
        )}
        <input
          className="qsearch"
          id="qsearch"
          type="search"
          placeholder="Search…"
          autoComplete="off"
          value={search}
          onChange={ev => setSearch(ev.target.value.trim().toLowerCase())}
          onKeyDown={ev => { if (ev.key === "Escape") ev.currentTarget.blur(); }}
        />
      </div>
      )}

      <ul className="queue-list" id="queue">
        {filtered.length === 0 ? (
          <li className="empty calm">
            {searching ? (
              <><strong>No matches</strong>Try clearing search.</>
            ) : (
              <>
                <strong>Inbox clear</strong>
                <span className="empty-body">
                  Nothing waiting. Check email to sync inbox and draft anything new.
                </span>
                <button
                  type="button"
                  className="btn btn-primary cta"
                  onClick={startTriage}
                >
                  Check email
                </button>
              </>
            )}
          </li>
        ) : (
          filtered.map((item, idx) => (
            <QueueItem
              key={item.id}
              item={item}
              focused={focusIdx === idx}
              onFocus={() => setFocusIdx(idx)}
              onApproved={onApproved}
              onSkipped={onSkipped}
              addToast={addToast}
              refreshQueue={refreshQueue}
              refreshHistory={refreshHistory}
              editing={editingId === item.id}
              onToggleEdit={(open) => setEditingId(open ? item.id : null)}
            />
          ))
        )}
      </ul>

      <details className="done-today">
        <summary>Done today (<span>{history.length}</span>)</summary>
        <ul>
          {history.length === 0 ? (
            <li className="sub">Nothing resolved yet today.</li>
          ) : (
            history.map(it => {
              const when = (it.resolved || "").slice(11, 16) || "";
              const who = [it.name, it.company].filter(Boolean).join(", ");
              if (it.status === "approved") {
                return (
                  <li key={it.id}>
                    <span className="ok">Approved</span> {who}{when ? `, ${when}` : ""}
                    {it.draft_link && <> · <a href={it.draft_link} target="_blank" rel="noopener">Open draft</a></>}
                    {" · "}
                    <button type="button" className="linkish" onClick={() => handleUndo(it.id)}>Undo</button>
                  </li>
                );
              }
              const snooze = it.skip_until === "forever" ? ", forever"
                : (it.skip_until ? ", until " + it.skip_until : "");
              return (
                <li key={it.id}>
                  <span className="skiplabel">Skipped</span> {who}{snooze}{when ? `, ${when}` : ""}
                  {" · "}
                  <button type="button" className="linkish" onClick={() => handleUndo(it.id)}>Undo</button>
                </li>
              );
            })
          )}
        </ul>
      </details>
    </>
  );
}
