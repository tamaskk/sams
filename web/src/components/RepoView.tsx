import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { useStore } from "../store";

interface Entry { path: string; type: "dir" | "file"; size: number | null }
interface Node { name: string; path: string; type: "dir" | "file"; size?: number | null; children?: Node[] }

function buildTree(entries: Entry[]): Node[] {
  const root: Node = { name: "", path: "", type: "dir", children: [] };
  const dirs = new Map<string, Node>([["", root]]);
  const ensureDir = (path: string): Node => {
    const have = dirs.get(path);
    if (have) return have;
    const idx = path.lastIndexOf("/");
    const parent = ensureDir(idx >= 0 ? path.slice(0, idx) : "");
    const node: Node = { name: idx >= 0 ? path.slice(idx + 1) : path, path, type: "dir", children: [] };
    parent.children!.push(node);
    dirs.set(path, node);
    return node;
  };
  for (const e of entries) {
    if (e.type === "dir") { ensureDir(e.path); continue; }
    const idx = e.path.lastIndexOf("/");
    const parent = ensureDir(idx >= 0 ? e.path.slice(0, idx) : "");
    parent.children!.push({ name: idx >= 0 ? e.path.slice(idx + 1) : e.path, path: e.path, type: "file", size: e.size });
  }
  const sort = (n: Node) => {
    n.children?.sort((a, b) => (a.type !== b.type ? (a.type === "dir" ? -1 : 1) : a.name.localeCompare(b.name)));
    n.children?.forEach(sort);
  };
  sort(root);
  return root.children!;
}

export function RepoView() {
  const repo = useStore((s) => s.selectedRepo);
  const closeRepo = useStore((s) => s.closeRepo);
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [err, setErr] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [file, setFile] = useState<{ path: string; content: string; loading?: boolean } | null>(null);
  const [showWork, setShowWork] = useState(false);
  const [taskText, setTaskText] = useState("");
  const [posting, setPosting] = useState(false);
  const [workMsg, setWorkMsg] = useState("");
  const [showDeploy, setShowDeploy] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deployMsg, setDeployMsg] = useState("");
  const [deploySubdir, setDeploySubdir] = useState("");

  useEffect(() => {
    if (!repo) return;
    setEntries(null); setErr(""); setFile(null); setExpanded(new Set());
    setShowDeploy(false); setDeployMsg(""); setDeploySubdir("");
    api.githubTree(repo.full_name, repo.default_branch)
      .then((d) => { setEntries(d.entries); setTruncated(d.truncated); })
      .catch((e) => setErr(String(e?.message ?? "Failed to load repository.")));
  }, [repo?.full_name]);

  const tree = useMemo(() => (entries ? buildTree(entries) : []), [entries]);
  const dirPaths = useMemo(() => (entries ?? []).filter((e) => e.type === "dir").map((e) => e.path).sort(), [entries]);
  // Folders that actually contain a deployable app (a package.json / index.html).
  const appDirs = useMemo(() => {
    const set = new Set<string>();
    for (const e of entries ?? []) {
      if (e.type !== "file") continue;
      const base = e.path.split("/").pop();
      if (base === "package.json" || base === "index.html") {
        set.add(e.path.includes("/") ? e.path.slice(0, e.path.lastIndexOf("/")) : "");
      }
    }
    return [...set].sort();
  }, [entries]);
  const rootIsApp = appDirs.includes("");
  const subApps = appDirs.filter((d) => d !== "");
  const isSelectedApp = deploySubdir === "" ? rootIsApp : appDirs.includes(deploySubdir);

  // For a monorepo (no app at the root), default the picker to the first app.
  const defaultedRef = useRef("");
  useEffect(() => {
    if (defaultedRef.current === repo?.full_name) return;
    if (appDirs.length && !rootIsApp && subApps[0]) {
      setDeploySubdir(subApps[0]);
      defaultedRef.current = repo?.full_name ?? "";
    }
  }, [appDirs.join("|"), rootIsApp, repo?.full_name]); // eslint-disable-line react-hooks/exhaustive-deps

  const openFile = async (path: string) => {
    if (!repo) return;
    setFile({ path, content: "", loading: true });
    try {
      const d = await api.githubFile(repo.full_name, path, repo.default_branch);
      setFile({ path, content: d.content });
    } catch (e: any) {
      setFile({ path, content: `Could not load file:\n${String(e?.message ?? "")}` });
    }
  };

  const toggle = (path: string) =>
    setExpanded((s) => { const n = new Set(s); n.has(path) ? n.delete(path) : n.add(path); return n; });

  const startWork = async () => {
    if (!repo || !taskText.trim()) return;
    setPosting(true); setWorkMsg("");
    try {
      await api.githubWork(repo.full_name, taskText.trim());
      setWorkMsg(`Agent started on ${repo.name} — clone → edit → push → PR. Watch the Agent Logs below.`);
      setTaskText(""); setShowWork(false);
    } catch (e: any) {
      setWorkMsg("Could not start: " + String(e?.message ?? ""));
    }
    setPosting(false);
  };

  const deploy = async (prod: boolean) => {
    if (!repo) return;
    setDeploying(true); setDeployMsg("");
    try {
      await api.vercelDeploy(`github:${repo.full_name}`, prod, deploySubdir || undefined);
      const what = deploySubdir ? `${repo.name}/${deploySubdir}` : repo.name;
      setDeployMsg(`Deploying ${what} to Vercel (${prod ? "production" : "preview"}) — watch the Agent Logs for the URL.`);
      setShowDeploy(false);
    } catch (e: any) {
      setDeployMsg("Could not start deploy: " + String(e?.message ?? ""));
    }
    setDeploying(false);
  };

  if (!repo) return null;

  return (
    <div className="repo-view">
      <div className="repo-bar">
        <button className="repo-back" onClick={closeRepo} title="Back to spatial view">←</button>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.51 11.51 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222 0 1.606-.014 2.898-.014 3.293 0 .322.216.694.825.576C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg>
        <span className="repo-name">{repo.full_name}</span>
        <span className="repo-branch">{repo.default_branch}</span>
        <button className="repo-work-btn" onClick={() => { setShowWork((v) => !v); setShowDeploy(false); }}>✦ Work with agent</button>
        <button className="repo-deploy-btn" onClick={() => { setShowDeploy((v) => !v); setShowWork(false); }} title="Deploy to Vercel">▲ Vercel</button>
        <a className="repo-ext" href={`https://github.com/${repo.full_name}`} target="_blank" rel="noopener" title="Open on GitHub">↗</a>
      </div>
      {showDeploy && (
        <div className="repo-work">
          <div className="repo-deploy-folder">
            <label className="repo-deploy-label">Folder to deploy (monorepo)</label>
            <select className="pull-method" value={deploySubdir} onChange={(e) => setDeploySubdir(e.target.value)}>
              <option value="">(repo root){rootIsApp ? "" : " — no app here"}</option>
              {subApps.length > 0 && (
                <optgroup label="Deployable apps">
                  {subApps.map((p) => <option key={p} value={p}>{p}</option>)}
                </optgroup>
              )}
              <optgroup label="All folders">
                {dirPaths.filter((p) => !appDirs.includes(p)).map((p) => <option key={p} value={p}>{p}</option>)}
              </optgroup>
            </select>
          </div>
          {!isSelectedApp && (
            <div className="repo-deploy-warn">⚠ No <span className="mono">package.json</span> in this folder — the deploy will likely 404. Pick an app folder above{subApps[0] ? ` (e.g. ${subApps[0]})` : ""}.</div>
          )}
          <div className="repo-work-foot">
            <span className="repo-work-note">Clone &amp; deploy <b>{deploySubdir ? `${repo.full_name}/${deploySubdir}` : repo.full_name}</b> to Vercel. <b>Preview</b> = a safe unique URL; <b>Production</b> = your live site.</span>
            <button className="btn-ghost" style={{ padding: "5px 12px", fontSize: 12 }} disabled={deploying} onClick={() => deploy(false)}>Deploy preview</button>
            <button className="accept-btn" disabled={deploying} onClick={() => deploy(true)}>Deploy production</button>
          </div>
        </div>
      )}
      {deployMsg && <div className="repo-work-msg">{deployMsg}</div>}
      {showWork && (
        <div className="repo-work">
          <textarea
            className="repo-work-input" rows={3} value={taskText}
            placeholder="Describe the change for the agent… e.g. “Add a dark-mode toggle to the navbar.”"
            onChange={(e) => setTaskText(e.target.value)}
          />
          <div className="repo-work-foot">
            <span className="repo-work-note">The agent clones the repo, makes the change, pushes a new branch + opens a PR for you to review, then deletes the clone.</span>
            <button className="accept-btn" disabled={posting || !taskText.trim()} onClick={startWork}>{posting ? "Starting…" : "Start"}</button>
          </div>
        </div>
      )}
      {workMsg && <div className="repo-work-msg">{workMsg}</div>}
      <div className="repo-body">
        <div className="repo-tree">
          {!entries && !err && <div className="repo-msg">Loading files…</div>}
          {err && <div className="repo-msg" style={{ color: "var(--danger)" }}>{err}</div>}
          {entries && tree.map((n) => (
            <TreeNode key={n.path} node={n} depth={0} expanded={expanded} onToggle={toggle} onOpen={openFile} active={file?.path} />
          ))}
          {truncated && <div className="repo-msg" style={{ fontSize: 10 }}>Large repo — file list truncated by GitHub.</div>}
        </div>
        <div className="repo-content">
          {!file && <div className="repo-empty">Select a file to view its contents.</div>}
          {file && (
            <>
              <div className="repo-file-head">{file.path}</div>
              {file.loading ? (
                <div className="repo-msg">Loading…</div>
              ) : (
                <pre className="repo-code"><code>{file.content}</code></pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function TreeNode({ node, depth, expanded, onToggle, onOpen, active }: {
  node: Node; depth: number; expanded: Set<string>;
  onToggle: (p: string) => void; onOpen: (p: string) => void; active?: string;
}) {
  const isOpen = expanded.has(node.path);
  if (node.type === "dir") {
    return (
      <>
        <button className="repo-row" style={{ paddingLeft: 8 + depth * 14 }} onClick={() => onToggle(node.path)}>
          <span className="repo-caret">{isOpen ? "▾" : "▸"}</span>
          <span className="repo-ic"><FolderIcon /></span>
          <span className="repo-label">{node.name}</span>
        </button>
        {isOpen && node.children?.map((c) => (
          <TreeNode key={c.path} node={c} depth={depth + 1} expanded={expanded} onToggle={onToggle} onOpen={onOpen} active={active} />
        ))}
      </>
    );
  }
  return (
    <button className={`repo-row file ${active === node.path ? "active" : ""}`} style={{ paddingLeft: 8 + depth * 14 + 14 }} onClick={() => onOpen(node.path)}>
      <span className="repo-ic"><FileIcon /></span>
      <span className="repo-label">{node.name}</span>
    </button>
  );
}

function FolderIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"><path d="M3 7h6l2 2h10v9H3z" /></svg>;
}
function FileIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"><path d="M14 3H6v18h12V7z" /><path d="M14 3v4h4" /></svg>;
}
