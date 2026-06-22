import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface Entry { name: string; path: string; type: "dir" | "file"; }

// A compact folder navigator. Navigate into a folder to select it as the project
// directory — the currently-open folder is the chosen value.
export function FolderPicker({ onChange, initialPath }: { onChange: (path: string) => void; initialPath?: string }) {
  const [path, setPath] = useState<string | undefined>(initialPath || undefined); // undefined -> ~/Desktop
  const [data, setData] = useState<{ path: string; parent: string; entries: Entry[] } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.fs(path)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        onChange(d.path);
      })
      .catch(() => {
        if (!cancelled && data) setPath(data.path); // hit the root boundary — revert
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  const dirs = data?.entries.filter((e) => e.type === "dir") ?? [];

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", background: "var(--bg-app)", borderBottom: "1px solid var(--border)" }}>
        <button type="button" className="mini-btn" onClick={() => data && setPath(data.parent)} title="Up one level">↑</button>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {data?.path ?? "…"}
        </span>
      </div>
      <div style={{ maxHeight: 160, overflow: "auto" }}>
        {dirs.length === 0 ? (
          <div style={{ padding: 10, color: "var(--text-subtle)", fontSize: 12 }}>No sub-folders — this folder is selected.</div>
        ) : (
          dirs.map((d) => (
            <div key={d.path} className="tree-item" style={{ paddingLeft: 10 }} onClick={() => setPath(d.path)}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M3 7h6l2 2h10v9H3z" /></svg>
              <span>{d.name}</span>
              <span style={{ marginLeft: "auto", color: "var(--text-subtle)" }}>›</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
