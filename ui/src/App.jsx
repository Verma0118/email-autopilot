import { useState, useEffect, useRef, useCallback } from "react";
import { getQueue, getHistory, getStatus, getReport, getVersion, postRun, postStop } from "./api.js";
import Chrome from "./components/Chrome.jsx";
import RunBanner from "./components/RunBanner.jsx";
import Approvals from "./components/Approvals.jsx";
import Overview from "./components/Overview.jsx";
import Activity from "./components/Activity.jsx";
import HelpOverlay from "./components/HelpOverlay.jsx";
import Toasts from "./components/Toasts.jsx";
import { prettyStage } from "./pipeline.js";

const VALID_TABS = ["approvals", "overview", "activity"];

function getInitialTab() {
  const hash = (location.hash || "").replace("#", "");
  if (hash === "report") return "overview";
  if (VALID_TABS.includes(hash)) return hash;
  try { const t = localStorage.getItem("emailcrm-tab"); if (VALID_TABS.includes(t)) return t; } catch (_) {}
  return "approvals";
}

function buildCostHint(tokPct, briefsN, limitHit, hardPct = 60) {
  if (limitHit) {
    return { short: "Paused, wait for reset", text: "Claude session limit hit. Wait, then run Triage." };
  }
  if (tokPct >= hardPct) {
    return {
      short: `Cap ${Math.round(hardPct)}%, LLM stopped`,
      text: `Autopilot hit its ${Math.round(hardPct)}% token cap. Non-LLM work only until the window resets.`,
    };
  }
  if (tokPct >= 45) {
    return {
      short: `Meter ${Math.round(tokPct)}%, skip Scout`,
      text: `Autopilot meter at ${Math.round(tokPct)}% (cap ${Math.round(hardPct)}%). Run Organize or Triage instead of Scout.`,
    };
  }
  if (briefsN >= 2) {
    return {
      short: `${briefsN} briefs, Organize`,
      text: `${briefsN} briefs waiting. Run Organize before Scout.`,
    };
  }
  return null;
}

export default function App() {
  const [tab, setTab] = useState(getInitialTab);
  const [status, setStatus] = useState({ running: false, stage: "idle", detail: "idle", tokens: {}, events: [] });
  const [queue, setQueue] = useState([]);
  const [resolvedHistory, setResolvedHistory] = useState([]);
  const [report, setReport] = useState({ needs_you: [], needs_n: 0, briefs_waiting: [], errors: [] });
  const [buildHead, setBuildHead] = useState("…");
  const [helpOpen, setHelpOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [runMode, setRunMode] = useState("");

  const wasRunning = useRef(false);
  const toastId = useRef(0);

  const addToast = useCallback((content, timeout = 8000) => {
    const id = ++toastId.current;
    setToasts(prev => [...prev, { id, content }]);
    if (timeout) setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), timeout);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const showTab = useCallback((name) => {
    if (!VALID_TABS.includes(name)) return;
    setTab(name);
    try { localStorage.setItem("emailcrm-tab", name); } catch (_) {}
    try { window.history.replaceState(null, "", "#" + name); } catch (_) {}
  }, []);

  useEffect(() => {
    const onHash = () => {
      const h = (location.hash || "").replace("#", "");
      if (h === "report") showTab("overview");
      else if (VALID_TABS.includes(h)) setTab(h);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [showTab]);

  useEffect(() => {
    const cur = (location.hash || "").replace("#", "");
    if (cur !== tab) {
      try { window.history.replaceState(null, "", "#" + tab); } catch (_) {}
    }
  }, [tab]);

  const refreshQueue = useCallback(async () => {
    const data = await getQueue();
    setQueue(data);
  }, []);

  const refreshHistory = useCallback(async () => {
    const data = await getHistory();
    setResolvedHistory(data);
  }, []);

  const refreshReport = useCallback(async () => {
    const data = await getReport();
    setReport(data);
  }, []);

  const onRunStage = useCallback(async (stage) => {
    setRunMode(stage || "");
    const res = await postRun(stage || null);
    if (res.status === 409) { addToast("Already running"); return; }
    if (!res.ok) { addToast("Could not start run"); return; }
    const labels = {
      "": "Full", triage: "Triage", organize: "Organize", scout: "Scout",
      reply: "Reply", bounce: "Bounce", digest: "Digest",
    };
    addToast((labels[stage || ""] || "Run") + " started");
  }, [addToast]);

  const pollStatus = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus(s);
      if (!wasRunning.current && s.running) {
        showTab("activity");
      }
      if (wasRunning.current && !s.running) {
        refreshReport();
        const summary = s.detail || "Run finished";
        addToast(
          <span>
            {summary}.{" "}
            <button className="linkish" onClick={() => showTab("overview")}>
              Overview
            </button>
          </span>,
          12000
        );
        setQueue(prev => {
          showTab(prev.length > 0 ? "approvals" : "overview");
          return prev;
        });
        refreshQueue();
      }
      wasRunning.current = !!s.running;
    } catch (_) {
      setStatus(prev => ({ ...prev, detail: "panel server unreachable" }));
    }
  }, [showTab, refreshReport, refreshQueue, addToast]);

  const onStop = useCallback(async () => {
    const res = await postStop();
    if (!res.ok) { addToast("Could not stop"); return; }
    addToast("Stop requested");
    await pollStatus();
  }, [addToast, pollStatus]);

  useEffect(() => {
    (async () => {
      await Promise.all([refreshQueue(), refreshReport(), refreshHistory()]);
      await pollStatus();
      try {
        const v = await getVersion();
        if (v.head) setBuildHead(v.head);
      } catch (_) {}

      const hash = (location.hash || "").replace("#", "");
      if (!VALID_TABS.includes(hash) && hash !== "report") {
        setQueue(q => {
          setReport(r => {
            const needsN = r.needs_n != null ? r.needs_n : (r.needs_you || []).length;
            const briefsN = r.briefs_n || (r.briefs_waiting || []).length;
            if (q.length) showTab("approvals");
            else if (needsN + briefsN > 0) showTab("overview");
            return r;
          });
          return q;
        });
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const interval = status.running ? 1000 : 2000;
    const t1 = setInterval(pollStatus, interval);
    const t2 = setInterval(refreshQueue, 5000);
    const t3 = setInterval(refreshReport, 15000);
    const t4 = setInterval(refreshHistory, 20000);
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3); clearInterval(t4); };
  }, [pollStatus, refreshQueue, refreshReport, refreshHistory, status.running]);

  useEffect(() => {
    const base = "EmailCRM Autopilot";
    if (status.running) {
      document.title = `Running · ${prettyStage(status.stage)} · ${base}`;
    } else {
      document.title = base;
    }
  }, [status.running, status.stage]);

  useEffect(() => {
    const onKey = (ev) => {
      if (ev.key === "Escape") {
        if (helpOpen) { setHelpOpen(false); ev.preventDefault(); }
        return;
      }
      if (ev.target.matches("input, textarea, select, [contenteditable]") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const key = ev.key.toLowerCase();
      if (key === "?" || (ev.shiftKey && ev.key === "/")) { ev.preventDefault(); setHelpOpen(h => !h); return; }
      if (helpOpen) return;
      if (key === "/") { ev.preventDefault(); showTab("approvals"); document.getElementById("qsearch")?.focus(); return; }
      if (key === "1") { showTab("approvals"); return; }
      if (key === "2") { showTab("overview"); return; }
      if (key === "3") { showTab("activity"); return; }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [helpOpen, showTab]);

  const needsCount = report.needs_n != null ? report.needs_n : (report.needs_you || []).length;
  const briefsN = report.briefs_n != null ? report.briefs_n : (report.briefs_waiting || []).length;
  const overviewBadge = needsCount + briefsN;

  const tokens = status.tokens || {};
  const costHint = buildCostHint(
    tokens.pct || 0, briefsN, !!tokens.limit_hit, tokens.hard_pct != null ? tokens.hard_pct : 60);

  return (
    <>
      <Chrome
        tab={tab}
        onTabChange={showTab}
        status={status}
        queueBadge={queue.length}
        overviewBadge={overviewBadge}
        runMode={runMode}
        setRunMode={setRunMode}
        addToast={addToast}
        pollStatus={pollStatus}
        costHint={costHint}
      />
      <RunBanner
        status={status}
        onStop={onStop}
        onShowActivity={() => showTab("activity")}
      />
      <main className={status.running ? "is-live" : ""}>
        <div className={`panel${tab === "approvals" ? " active" : ""}`} id="panel-approvals" role="tabpanel">
          <Approvals
            queue={queue}
            history={resolvedHistory}
            needsCount={needsCount}
            onShowOverview={() => showTab("overview")}
            addToast={addToast}
            refreshQueue={refreshQueue}
            refreshHistory={refreshHistory}
            setRunMode={setRunMode}
            onRunStage={onRunStage}
          />
        </div>
        <div className={`panel${tab === "overview" ? " active" : ""}`} id="panel-overview" role="tabpanel">
          <Overview
            status={status}
            report={report}
            refreshReport={refreshReport}
            queueCount={queue.length}
            onRunStage={onRunStage}
            onShowApprovals={() => showTab("approvals")}
            onShowReport={() => window.open("/dashboard", "_blank", "noopener")}
          />
        </div>
        <div className={`panel${tab === "activity" ? " active" : ""}`} id="panel-activity" role="tabpanel">
          <Activity status={status} />
        </div>

        <footer className="links">
          <nav className="footer-nav" aria-label="Related links">
            <a href="https://verma0118.github.io/email-autopilot/" target="_blank" rel="noopener">Web dashboard</a>
            <a href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noopener">Gmail drafts</a>
            <a href="/dashboard" target="_blank" rel="noopener">Full report</a>
            <a href="/files/digest" target="_blank" rel="noopener">Digest</a>
            <a href="/files/prospects" target="_blank" rel="noopener">Briefs</a>
            <a href="/files/logs" target="_blank" rel="noopener">Logs</a>
          </nav>
          <p className="footer-meta">
            Daily run at 7:04 AM. Panel build <span id="build">{buildHead}</span>.
            Use <strong>Update</strong> to pull latest.
          </p>
        </footer>
      </main>

      <HelpOverlay open={helpOpen} onClose={() => setHelpOpen(false)} />
      <Toasts toasts={toasts} onRemove={removeToast} />
    </>
  );
}
