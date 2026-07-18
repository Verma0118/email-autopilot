import { useState, useEffect, useRef, useCallback } from "react";
import { getQueue, getHistory, getStatus, getReport, getVersion } from "./api.js";
import Chrome from "./components/Chrome.jsx";
import Approvals from "./components/Approvals.jsx";
import Overview from "./components/Overview.jsx";
import Activity from "./components/Activity.jsx";
import Report from "./components/Report.jsx";
import HelpOverlay from "./components/HelpOverlay.jsx";
import Toasts from "./components/Toasts.jsx";

const VALID_TABS = ["approvals", "overview", "activity", "report"];

function getInitialTab() {
  const hash = (location.hash || "").replace("#", "");
  if (VALID_TABS.includes(hash)) return hash;
  try { const t = localStorage.getItem("emailcrm-tab"); if (VALID_TABS.includes(t)) return t; } catch (_) {}
  return "approvals";
}

export default function App() {
  const [tab, setTab] = useState(getInitialTab);
  const [status, setStatus] = useState({ running: false, stage: "idle", detail: "—", tokens: {}, events: [] });
  const [queue, setQueue] = useState([]);
  const [resolvedHistory, setResolvedHistory] = useState([]);
  const [report, setReport] = useState({ needs_you: [], needs_n: 0, gmail_drafts: [], briefs_waiting: [], errors: [], action_items: [] });
  const [buildHead, setBuildHead] = useState("…");
  const [helpOpen, setHelpOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [runMode, setRunMode] = useState("");
  const [dashKey, setDashKey] = useState(0);

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

  // hash change support
  useEffect(() => {
    const onHash = () => {
      const h = (location.hash || "").replace("#", "");
      if (VALID_TABS.includes(h)) setTab(h);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // keep URL hash in sync with active tab
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

  // status poll
  const pollStatus = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus(s);
      if (!wasRunning.current && s.running) {
        showTab("activity");
      }
      if (wasRunning.current && !s.running) {
        setDashKey(k => k + 1);
        refreshReport();
        const summary = s.detail || "Run finished";
        const toastContent = (
          <span>
            {summary} ·{" "}
            <button className="linkish" onClick={() => showTab("overview")}>
              Overview
            </button>
          </span>
        );
        addToast(toastContent, 12000);
        setQueue(prev => {
          showTab(prev.length > 0 ? "approvals" : "overview");
          return prev;
        });
      }
      wasRunning.current = !!s.running;
    } catch (_) {
      setStatus(prev => ({ ...prev, detail: "panel server unreachable" }));
    }
  }, [showTab, refreshReport, addToast]);

  // initial load
  useEffect(() => {
    (async () => {
      await Promise.all([refreshQueue(), refreshReport(), refreshHistory()]);
      await pollStatus();
      try {
        const v = await getVersion();
        if (v.head) setBuildHead(v.head);
      } catch (_) {}

      // auto-select best tab if hash wasn't explicit
      const hash = (location.hash || "").replace("#", "");
      if (!VALID_TABS.includes(hash)) {
        setQueue(q => {
          setReport(r => {
            const needsN = r.needs_n != null ? r.needs_n : (r.needs_you || []).length;
            const gmailN = (r.gmail_drafts || []).length;
            const briefsN = r.briefs_n || (r.briefs_waiting || []).length;
            const overviewBadge = needsN + gmailN + briefsN;
            if (q.length) showTab("approvals");
            else if (overviewBadge > 0) showTab("overview");
            return r;
          });
          return q;
        });
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // polling intervals
  useEffect(() => {
    const t1 = setInterval(pollStatus, 2000);
    const t2 = setInterval(refreshQueue, 5000);
    const t3 = setInterval(refreshReport, 15000);
    const t4 = setInterval(refreshHistory, 20000);
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3); clearInterval(t4); };
  }, [pollStatus, refreshQueue, refreshReport, refreshHistory]);

  // keyboard shortcuts
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
      if (key === "4") { showTab("report"); return; }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [helpOpen, showTab]);

  const needsCount = report.needs_n != null ? report.needs_n : (report.needs_you || []).length;
  const gmailN = (report.gmail_drafts || []).length;
  const briefsN = report.briefs_n != null ? report.briefs_n : (report.briefs_waiting || []).length;
  const overviewBadge = needsCount + gmailN + briefsN;

  const tokens = status.tokens || {};
  const tokPct = tokens.pct || 0;
  let costHint = null;
  if (tokPct >= 45) costHint = "Scout costly";
  else if (briefsN >= 2) costHint = "Organize suggested";

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
        refreshQueue={refreshQueue}
        refreshReport={refreshReport}
        pollStatus={pollStatus}
        showTab={showTab}
        costHint={costHint}
      />
      <main>
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
          />
        </div>
        <div className={`panel${tab === "overview" ? " active" : ""}`} id="panel-overview" role="tabpanel">
          <Overview
            status={status}
            report={report}
            refreshReport={refreshReport}
            addToast={addToast}
            setRunMode={setRunMode}
            onRunOrganize={() => {
              setRunMode("organize");
              document.getElementById("chrome-run-btn")?.click();
            }}
            onShowReport={() => showTab("report")}
          />
        </div>
        <div className={`panel${tab === "activity" ? " active" : ""}`} id="panel-activity" role="tabpanel">
          <Activity status={status} />
        </div>
        <div className={`panel${tab === "report" ? " active" : ""}`} id="panel-report" role="tabpanel">
          <Report dashKey={dashKey} />
        </div>

        <footer className="links">
          <a href="https://verma0118.github.io/email-autopilot/" target="_blank" rel="noopener">Web dashboard</a> (encrypted, away-from-Mac) ·{" "}
          <a href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noopener">Gmail drafts</a> ·{" "}
          <a href="/files/digest" target="_blank" rel="noopener">Digest</a> ·{" "}
          <a href="/files/prospects" target="_blank" rel="noopener">Briefs</a> ·{" "}
          <a href="/files/logs" target="_blank" rel="noopener">Logs</a><br />
          Scheduled run: daily 7:04 AM · panel <span id="build">{buildHead}</span> · click <strong>Update</strong> for latest (auto-reloads after pull)
        </footer>
      </main>

      <HelpOverlay open={helpOpen} onClose={() => setHelpOpen(false)} />
      <Toasts toasts={toasts} onRemove={removeToast} />
    </>
  );
}
