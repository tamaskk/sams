import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import { api } from "../lib/api";

// Live log viewer for started projects (the Terminal console tab). Shows the
// running projects, lets you switch between them and stop them, and tails the
// selected project's real stdout/stderr.
export function ProjectLogs() {
  const projects = useStore((s) => s.runningProjects);
  const active = useStore((s) => s.activeProjectPid);
  const setActive = useStore((s) => s.setActiveProject);
  const [log, setLog] = useState("");
  const bodyRef = useRef<HTMLPreElement>(null);

  // Default selection to the first project when none is chosen.
  const selected = active ?? (projects[0]?.pid ?? null);

  // Poll the selected project's log every 1.2s.
  useEffect(() => {
    if (selected == null) { setLog(""); return; }
    let stop = false;
    const tick = () =>
      api.projectLog(selected)
        .then((d) => { if (!stop) setLog(d.content || "(no output yet)"); })
        .catch(() => { if (!stop) setLog("(log unavailable — process not tracked)"); });
    tick();
    const id = setInterval(tick, 1200);
    return () => { stop = true; clearInterval(id); };
  }, [selected]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [log]);

  if (projects.length === 0) {
    return <div style={{ color: "var(--text-subtle)" }}>No projects running. Hover a folder in FILES · projects and click ▶ to start one.</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 8 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {projects.map((p) => (
          <div
            key={p.pid}
            className={`proj-chip ${p.pid === selected ? "sel" : ""}`}
            onClick={() => setActive(p.pid)}
          >
            <span className="run-dot" style={{ background: p.alive ? "var(--success)" : "var(--idle)" }} />
            <span style={{ fontWeight: 600 }}>{p.name}</span>
            <span className="mono" style={{ color: "var(--text-subtle)" }}>{p.command}</span>
            {p.alive && (
              <button
                className="start-btn stop visible"
                title={`Stop (pid ${p.pid})`}
                onClick={async (e) => {
                  e.stopPropagation();
                  await api.stopProject(p.pid).catch(() => {});
                  await api.runningProjects().then(useStore.getState().setRunningProjects).catch(() => {});
                }}
              >✕</button>
            )}
          </div>
        ))}
      </div>
      <pre ref={bodyRef} className="proj-log">{log}</pre>
    </div>
  );
}
