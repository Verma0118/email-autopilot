import { useEffect, useRef } from "react";

export default function Report({ dashKey }) {
  const iframeRef = useRef(null);

  useEffect(() => {
    if (iframeRef.current) {
      iframeRef.current.src = "/dashboard?t=" + Date.now();
    }
  }, [dashKey]);

  return (
    <>
      <div className="section-head">
        <h2>Report</h2>
        <p className="hint">
          <a href="/dashboard" target="_blank" rel="noopener">Open full page ↗</a>
        </p>
      </div>
      <div className="report-wrap">
        <iframe
          ref={iframeRef}
          src="/dashboard"
          title="EmailCRM dashboard"
        />
      </div>
    </>
  );
}
