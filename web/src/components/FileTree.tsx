import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useStore } from "../store";

interface Entry { name: string; path: string; type: "dir" | "file"; size: number | null; }

// A lazy filesystem browser for the Explorer. Browses the user's home directory
// (default ~/Desktop) via the /api/v1/fs endpoint; opening a file shows it in the
// Code tab.
export function FileTree({ root, rootName = "Desktop" }: { root?: string; rootName?: string }) {
  return <DirNode path={root} name={rootName} depth={0} />;
}

function DirNode({ path, name, depth, defaultOpen = false }: { path?: string; name: string; depth: number; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const running = useStore((s) => (path ? s.runningProjects.find((p) => p.path === path && p.alive) : undefined));

  useEffect(() => {
    if (open && entries === null) {
      api.fs(path).then((d) => setEntries(d.entries)).catch(() => setError(true));
    }
  }, [open, path, entries]);

  const start = async (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    if (!path || pending) return;
    setPending(true);
    try {
      const r = await api.startProject(path);
      if (r.started && r.pid) {
        useStore.getState().setActiveProject(r.pid);
        await api.runningProjects().then(useStore.getState().setRunningProjects);
      } else if (!r.started) {
        alert(`Can't start "${name}": no recognizable start command (package.json / docker-compose / manage.py / main.py / Makefile / start.sh).`);
      }
    } catch { /* ignore */ }
    setPending(false);
  };

  const stop = async (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    if (!running || pending) return;
    setPending(true);
    try {
      await api.stopProject(running.pid);
      await api.runningProjects().then(useStore.getState().setRunningProjects);
    } catch { /* ignore */ }
    setPending(false);
  };

  const deploy = async (e: { stopPropagation: () => void }) => {
    e.stopPropagation();
    if (!path || deploying) return;
    if (!window.confirm(`Deploy "${name}" to Vercel production?`)) return;
    setDeploying(true);
    try {
      await api.vercelDeploy(path, true);
    } catch (err: any) {
      alert("Could not start the Vercel deploy: " + String(err?.message ?? "") +
        "\n\nSet VERCEL_TOKEN in .env (Vercel → Settings → Tokens) and restart `sams up`.");
    }
    setDeploying(false);
  };

  const pad = 8 + depth * 12;
  return (
    <div>
      <div className="tree-item folder-row" style={{ paddingLeft: pad }} onClick={() => setOpen((o) => !o)}>
        <span style={{ width: 12, display: "inline-block", color: "var(--text-subtle)" }}>{open ? "▾" : "▸"}</span>
        <FolderIcon />
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: running ? "var(--success)" : undefined }}>{name}</span>
        {running && <span className="run-dot" title="running" />}
        {path && (
          <>
            {running ? (
              <button className="start-btn stop visible" title={`Stop ${name} (pid ${running.pid})`}
                onClick={(e) => { stop(e); useStore.getState().setActiveProject(running.pid); }}>
                {pending ? "···" : "✕"}
              </button>
            ) : (
              <button className="start-btn" title={`Start ${name}`} onClick={start}>
                {pending ? "···" : "▶"}
              </button>
            )}
            <button className="start-btn deploy" title={`Deploy ${name} to Vercel`} onClick={deploy}>
              {deploying ? "···" : "▲"}
            </button>
          </>
        )}
      </div>
      {open && (
        error ? (
          <div className="tree-item" style={{ paddingLeft: pad + 22, color: "var(--error)" }}>can't read</div>
        ) : entries === null ? (
          <div className="tree-item" style={{ paddingLeft: pad + 22, color: "var(--text-subtle)" }}>loading…</div>
        ) : entries.length === 0 ? (
          <div className="tree-item" style={{ paddingLeft: pad + 22, color: "var(--text-subtle)" }}>empty</div>
        ) : (
          entries.map((e) =>
            e.type === "dir" ? (
              <DirNode key={e.path} path={e.path} name={e.name} depth={depth + 1} />
            ) : (
              <FileNode key={e.path} entry={e} depth={depth + 1} />
            )
          )
        )
      )}
    </div>
  );
}

function FileNode({ entry, depth }: { entry: Entry; depth: number }) {
  const setOpenFile = useStore((s) => s.setOpenFile);
  const open = async () => {
    try {
      const d = await api.fsRead(entry.path);
      setOpenFile({ path: d.path, content: d.content });
    } catch {
      setOpenFile({ path: entry.path, content: "(could not read file)" });
    }
  };
  return (
    <div className="tree-item" style={{ paddingLeft: 8 + depth * 12 + 12 }} onClick={open} title={entry.path}>
      <FileIcon />
      <span className="mono" style={{ fontSize: 12 }}>{entry.name}</span>
    </div>
  );
}

function FolderIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M3 7h6l2 2h10v9H3z" /></svg>;
}
function FileIcon() {
  return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" style={{ opacity: 0.6 }}><path d="M6 2h8l4 4v16H6z" /><path d="M14 2v4h4" /></svg>;
}
