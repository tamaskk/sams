import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useStore } from "../store";

interface Repo {
  id: number; name: string; full_name: string; description: string; url: string;
  private: boolean; language: string | null; stars: number; forks: number;
  updated_at: string; default_branch: string; owner: string; fork: boolean; archived: boolean;
}
interface Pull {
  id: number; number: number; title: string; url: string; repo: string;
  state: string; draft: boolean; updated_at: string; comments: number;
}

const LANG_COLOR: Record<string, string> = {
  TypeScript: "#3178c6", JavaScript: "#f1e05a", Python: "#3572A5", Dart: "#00B4AB",
  HTML: "#e34c26", CSS: "#563d7c", Go: "#00ADD8", Rust: "#dea584", Java: "#b07219",
  "C++": "#f34b7d", C: "#555555", "C#": "#178600", Shell: "#89e051", Ruby: "#701516",
  Swift: "#F05138", Kotlin: "#A97BFF", PHP: "#4F5D95", Vue: "#41b883", Svelte: "#ff3e00",
};

function timeAgo(iso: string): string {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 2592000) return `${Math.floor(s / 86400)}d ago`;
  if (s < 31536000) return `${Math.floor(s / 2592000)}mo ago`;
  return `${Math.floor(s / 31536000)}y ago`;
}

// GitHub panel: list the repositories on the user's profile (read-only). Click a
// repo to open it on github.com. Mirrors the Source Control · ClickUp pattern.
export function GitHubPanel() {
  const [repos, setRepos] = useState<Repo[] | null>(null);
  const [user, setUser] = useState("");
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [hint, setHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [view, setView] = useState<"repos" | "pulls">("repos");
  const [pulls, setPulls] = useState<Pull[] | null>(null);
  const [prState, setPrState] = useState<"open" | "all">("open");
  const openRepo = useStore((s) => s.openRepo);
  const selectedRepo = useStore((s) => s.selectedRepo);
  const openPull = useStore((s) => s.openPull);
  const selectedPull = useStore((s) => s.selectedPull);
  const pullsVersion = useStore((s) => s.pullsVersion);

  const load = async () => {
    setLoading(true);
    try {
      const d = await api.githubRepos();
      setConfigured(d.configured);
      setHint(d.hint ?? "");
      setUser(d.user ?? "");
      setRepos(d.repos ?? []);
    } catch (e: any) {
      setConfigured(false);
      const msg = String(e?.message ?? "");
      setHint(msg.includes("404")
        ? "The running backend doesn't have the GitHub endpoint yet — restart `sams up`."
        : "Could not reach the SAMS backend.");
      setRepos([]);
    }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const loadPulls = async (state: "open" | "all" = prState) => {
    setLoading(true); setPulls(null);
    try {
      const d = await api.githubPulls(state);
      setConfigured(d.configured);
      setHint(d.hint ?? "");
      setPulls(d.pulls ?? []);
    } catch {
      setPulls([]);
    }
    setLoading(false);
  };

  const switchView = (v: "repos" | "pulls") => {
    setView(v);
    if (v === "pulls" && !pulls) loadPulls();
  };

  // Refresh the PR list after a merge/close/ready done in the PR view.
  useEffect(() => {
    if (view === "pulls") loadPulls(prState);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pullsVersion]);

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    const list = repos ?? [];
    if (!t) return list;
    return list.filter((r) =>
      r.name.toLowerCase().includes(t) ||
      (r.description || "").toLowerCase().includes(t) ||
      (r.language || "").toLowerCase().includes(t));
  }, [repos, q]);

  return (
    <div className="panel">
      <div className="panel-header" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>GitHub{user ? ` · @${user}` : ""}</span>
        <button className="mini-btn" title="Refresh" style={{ marginLeft: "auto" }} onClick={() => (view === "pulls" ? loadPulls() : load())}>⟳</button>
      </div>
      <div className="panel-scroll">
        {configured === false && (
          <div style={{ padding: "8px 10px", fontSize: 12, color: "var(--text-muted)" }}>
            <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 6 }}>Connect GitHub</div>
            {hint || "Set GITHUB_TOKEN before starting SAMS."}
            <div style={{ marginTop: 8, fontSize: 11 }}>
              GitHub → Settings → Developer settings → <span className="mono">Personal access tokens</span> (read access to repositories), then add to <span className="mono">.env</span>:
              <pre className="mono" style={{ background: "var(--bg-app)", padding: 8, borderRadius: 6, marginTop: 6, whiteSpace: "pre-wrap" }}>GITHUB_TOKEN=ghp_…</pre>
              and restart <span className="mono">sams up</span>.
            </div>
          </div>
        )}
        {configured !== false && (
          <div style={{ padding: "8px 10px 2px" }}>
            <div className="seg" style={{ width: "100%" }}>
              <button style={{ flex: 1 }} className={view === "repos" ? "on" : ""} onClick={() => switchView("repos")}>Repositories</button>
              <button style={{ flex: 1 }} className={view === "pulls" ? "on" : ""} onClick={() => switchView("pulls")}>Pull requests</button>
            </div>
          </div>
        )}

        {view === "repos" && <>
          {configured && (
            <div style={{ padding: "6px 10px 4px" }}>
              <input className="gh-search" placeholder="Filter repositories…" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
          )}
          {loading && <div style={{ padding: 10, color: "var(--text-subtle)", fontSize: 12 }}>Loading repositories…</div>}
          {configured && !loading && filtered.length === 0 && (
            <div style={{ padding: 10, color: "var(--text-subtle)", fontSize: 12 }}>No repositories{q ? " match your filter." : " found."}</div>
          )}
          {configured && filtered.map((r) => (
            <button
              key={r.id}
              className={`gh-repo ${selectedRepo?.full_name === r.full_name ? "open" : ""}`}
              onClick={() => openRepo({ full_name: r.full_name, name: r.name, default_branch: r.default_branch })}
              title={`Browse ${r.full_name}`}
            >
              <div className="gh-repo-top">
                <span className="gh-repo-name">{r.name}</span>
                <a className="gh-ext" href={r.url} target="_blank" rel="noopener" title="Open on GitHub" onClick={(e) => e.stopPropagation()}>↗</a>
                <span className={`gh-badge ${r.private ? "priv" : "pub"}`}>{r.private ? "Private" : "Public"}</span>
              </div>
              {r.description && <div className="gh-repo-desc">{r.description}</div>}
              <div className="gh-repo-meta">
                {r.language && <span className="gh-lang"><i className="gh-dot" style={{ background: LANG_COLOR[r.language] || "#94a3b8" }} />{r.language}</span>}
                {r.stars > 0 && <span>★ {r.stars}</span>}
                {r.fork && <span>⑂ fork</span>}
                {r.archived && <span className="gh-arch">archived</span>}
                <span style={{ marginLeft: "auto" }}>{timeAgo(r.updated_at)}</span>
              </div>
            </button>
          ))}
        </>}

        {view === "pulls" && <>
          <div className="gh-pr-filter">
            <button className={prState === "open" ? "on" : ""} onClick={() => { setPrState("open"); loadPulls("open"); }}>Open</button>
            <button className={prState === "all" ? "on" : ""} onClick={() => { setPrState("all"); loadPulls("all"); }}>All</button>
          </div>
          {loading && <div style={{ padding: 10, color: "var(--text-subtle)", fontSize: 12 }}>Loading pull requests…</div>}
          {!loading && pulls && pulls.length === 0 && (
            <div style={{ padding: 10, color: "var(--text-subtle)", fontSize: 12 }}>No {prState === "open" ? "open " : ""}pull requests.</div>
          )}
          {pulls && pulls.map((p) => (
            <button key={p.id}
              className={`gh-pr ${selectedPull?.repo === p.repo && selectedPull?.number === p.number ? "open" : ""}`}
              onClick={() => openPull({ repo: p.repo, number: p.number, title: p.title })}
              title={`Open ${p.repo} #${p.number}`}>
              <div className="gh-pr-top">
                <span className="gh-pr-title">{p.title}</span>
                <span className={`gh-pr-state ${p.draft && p.state === "open" ? "draft" : p.state}`}>{p.draft && p.state === "open" ? "draft" : p.state}</span>
              </div>
              <div className="gh-pr-meta">
                <span className="gh-pr-repo">{p.repo} · #{p.number}</span>
                <a className="gh-ext" href={p.url} target="_blank" rel="noopener" title="Open on GitHub" onClick={(e) => e.stopPropagation()}>↗</a>
                <span style={{ marginLeft: "auto" }}>{timeAgo(p.updated_at)}</span>
              </div>
            </button>
          ))}
        </>}
      </div>
    </div>
  );
}
