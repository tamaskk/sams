import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import { ProjectLogs } from "./ProjectLogs";

const TABS = ["Event Log", "Agent Logs", "Problems", "Terminal"] as const;
type Tab = (typeof TABS)[number];

// The bottom console: Event Log / Agent Logs / Problems / Terminal (spec 16).
export function Console() {
  const [tab, setTab] = useState<Tab>("Agent Logs");
  const events = useStore((s) => s.events);
  const logs = useStore((s) => s.logs);
  const activeProjectPid = useStore((s) => s.activeProjectPid);
  const runningCount = useStore((s) => s.runningProjects.filter((p) => p.alive).length);
  const bodyRef = useRef<HTMLDivElement>(null);

  // Jump to the Terminal tab when a project is started.
  useEffect(() => {
    if (activeProjectPid != null) setTab("Terminal");
  }, [activeProjectPid]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [events.length, logs.length, tab]);

  const problems = events.filter((e) => e.type.includes("error") || e.type === "security.gate.rejected");

  return (
    <div className="console">
      <div className="console-tabs">
        {TABS.map((t) => (
          <button key={t} className={`console-tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t}{t === "Problems" && problems.length ? ` (${problems.length})` : ""}
            {t === "Terminal" && runningCount ? ` (${runningCount})` : ""}
          </button>
        ))}
      </div>
      <div className="console-body" ref={bodyRef}>
        {tab === "Event Log" &&
          events.slice(-200).map((e) => (
            <div key={e.id} className="log-line">
              <span className="log-time">{e.ts.slice(11, 19)}</span>{"  "}
              <span style={{ color: "var(--brand)" }}>{e.type}</span>{"  "}
              <span style={{ color: "var(--text-muted)" }}>{e.actor ?? ""}</span>
            </div>
          ))}
        {tab === "Agent Logs" &&
          logs.slice(-200).map((l, i) => (
            <div key={i} className="log-line">
              <span className="log-time">{l.ts.slice(11, 19)}</span>{"  "}
              <span style={{ color: "var(--text)" }}>{(l.actor ?? "system").padEnd(12)}</span>{" "}
              <span className={`lvl-${l.level}`}>[{l.level}]</span>{"  "}
              {l.message}
            </div>
          ))}
        {tab === "Problems" &&
          (problems.length === 0 ? (
            <div style={{ color: "var(--text-subtle)" }}>No errors detected</div>
          ) : (
            problems.slice(-100).map((e) => (
              <div key={e.id} className="log-line"><span className="lvl-ERROR">[ERROR]</span> {e.actor}: {JSON.stringify(e.payload)}</div>
            ))
          ))}
        {tab === "Terminal" && <ProjectLogs />}
      </div>
    </div>
  );
}
