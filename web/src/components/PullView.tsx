import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { useStore } from "../store";

interface Detail {
  repo: string; number: number; title: string; body: string; state: string; draft: boolean; merged: boolean;
  mergeable: boolean | null; mergeable_state: string; head: string; base: string;
  additions: number; deletions: number; changed_files: number; commits: number; url: string; author: string;
}
interface FileChange { filename: string; status: string; additions: number; deletions: number; patch: string | null }

type Method = "merge" | "squash" | "rebase";

// A GitHub pull request, fully viewable + mergeable from SAMS — no need to open
// github.com. Shows the description, branches, changed files (with diffs), and
// Merge / Close actions (both behind an explicit confirm).
export function PullView() {
  const pull = useStore((s) => s.selectedPull);
  const closePull = useStore((s) => s.closePull);
  const bumpPulls = useStore((s) => s.bumpPulls);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [files, setFiles] = useState<FileChange[] | null>(null);
  const [err, setErr] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [method, setMethod] = useState<Method>("merge");
  const [confirming, setConfirming] = useState<"merge" | "close" | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const reload = () => {
    if (!pull) return;
    setErr(""); setDetail(null); setFiles(null);
    api.githubPull(pull.repo, pull.number).then(setDetail).catch((e) => setErr(String(e?.message ?? "Failed to load PR.")));
    api.githubPullFiles(pull.repo, pull.number).then((d) => setFiles(d.files)).catch(() => setFiles([]));
  };
  useEffect(() => { reload(); setExpanded(new Set()); setMsg(null); setConfirming(null); }, [pull?.repo, pull?.number]);

  if (!pull) return null;

  const merge = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.githubMergePull(pull.repo, pull.number, method);
      if (!alive.current) return;
      if (r.merged) { setMsg({ kind: "ok", text: `Merged via ${method}.` }); bumpPulls(); reload(); }
      else setMsg({ kind: "err", text: r.message || "Could not merge (conflicts or checks pending)." });
    } catch (e: any) { if (alive.current) setMsg({ kind: "err", text: String(e?.message ?? "Merge failed.") }); }
    if (alive.current) { setBusy(false); setConfirming(null); }
  };
  const close = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.githubClosePull(pull.repo, pull.number);
      if (!alive.current) return;
      if (r.closed) { setMsg({ kind: "ok", text: "Pull request closed." }); bumpPulls(); reload(); }
      else setMsg({ kind: "err", text: r.message || "Could not close the pull request." });
    } catch (e: any) { if (alive.current) setMsg({ kind: "err", text: String(e?.message ?? "Close failed.") }); }
    if (alive.current) { setBusy(false); setConfirming(null); }
  };

  const ready = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.githubReadyPull(pull.repo, pull.number);
      if (!alive.current) return;
      if (r.ok) { setMsg({ kind: "ok", text: "Marked ready for review." }); bumpPulls(); reload(); }
      else setMsg({ kind: "err", text: r.message || "Could not mark ready." });
    } catch (e: any) { if (alive.current) setMsg({ kind: "err", text: String(e?.message ?? "Failed.") }); }
    if (alive.current) setBusy(false);
  };

  const toggle = (f: string) => setExpanded((s) => { const n = new Set(s); n.has(f) ? n.delete(f) : n.add(f); return n; });
  const d = detail;
  const canAct = !!d && d.state === "open" && !d.merged;
  const isDraft = !!d?.draft && d?.state === "open";
  const ms = d?.mergeable_state;
  // GitHub returns mergeable:null while it is still computing — never treat that
  // (or a blocked/conflicting state) as safe to merge.
  const mergeStatus: { label: string; kind: "ok" | "warn" | "bad" | "checking" } | null =
    !canAct || isDraft ? null
    : d!.mergeable === null ? { label: "checking mergeability…", kind: "checking" }
    : (d!.mergeable === false || ms === "dirty") ? { label: "conflicts — resolve on GitHub", kind: "bad" }
    : ms === "blocked" ? { label: "blocked by required checks/reviews", kind: "bad" }
    : ms === "behind" ? { label: "branch is behind base", kind: "warn" }
    : ms === "unstable" ? { label: "some checks are failing", kind: "warn" }
    : { label: "no conflicts", kind: "ok" };
  const mergeReady = !!d && d.mergeable === true && ms !== "blocked" && ms !== "dirty" && !isDraft;

  return (
    <div className="repo-view">
      <div className="repo-bar">
        <button className="repo-back" onClick={closePull} title="Back">←</button>
        <span className={`gh-pr-state ${d?.merged ? "merged" : d?.state ?? "open"}`}>{d?.merged ? "merged" : d?.state ?? "…"}</span>
        <span className="repo-name">{pull.repo} <span style={{ color: "var(--text-subtle)" }}>#{pull.number}</span></span>
        <a className="repo-ext" href={d?.url ?? `https://github.com/${pull.repo}/pull/${pull.number}`} target="_blank" rel="noopener" title="Open on GitHub" style={{ marginLeft: "auto" }}>↗</a>
      </div>

      {err && <div className="repo-msg" style={{ color: "var(--danger)" }}>{err}</div>}
      {!d && !err && <div className="repo-msg">Loading pull request…</div>}

      {d && (
        <div className="pull-body">
          <div className="pull-title">{d.title}</div>
          <div className="pull-sub">
            <span className="pull-branch">{d.head}</span><span className="pull-arrow">→</span><span className="pull-branch">{d.base}</span>
            {d.author && <span className="pull-author">by {d.author}</span>}
          </div>
          <div className="pull-stat">
            <span>{d.commits} commit{d.commits === 1 ? "" : "s"}</span>
            <span>{d.changed_files} file{d.changed_files === 1 ? "" : "s"}</span>
            <span className="pull-add">+{d.additions}</span>
            <span className="pull-del">−{d.deletions}</span>
            {mergeStatus && (
              <span className={`pull-mergeable ${mergeStatus.kind}`}>
                {mergeStatus.kind === "ok" ? "✓ " : mergeStatus.kind === "checking" ? "" : "⚠ "}{mergeStatus.label}
              </span>
            )}
          </div>

          {d.body && <div className="pull-desc">{d.body}</div>}

          {/* actions */}
          {canAct ? (
            <div className="pull-actions">
              {confirming === "merge" ? (
                <>
                  <span className="pull-confirm-q">Merge #{d.number} into <b>{d.base}</b>?</span>
                  <button className="accept-btn" disabled={busy} onClick={merge}>{busy ? "Merging…" : "Confirm merge"}</button>
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setConfirming(null)}>Cancel</button>
                </>
              ) : confirming === "close" ? (
                <>
                  <span className="pull-confirm-q">Close #{d.number} without merging?</span>
                  <button className="reject-btn" disabled={busy} onClick={close}>{busy ? "Closing…" : "Confirm close"}</button>
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setConfirming(null)}>Cancel</button>
                </>
              ) : isDraft ? (
                <>
                  <span className="pull-confirm-q" style={{ color: "var(--text-muted)" }}>This PR is a draft — mark it ready to merge.</span>
                  <button className="accept-btn" disabled={busy} onClick={ready}>{busy ? "…" : "Ready for review"}</button>
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setConfirming("close")}>Close</button>
                </>
              ) : (
                <>
                  <select className="pull-method" value={method} onChange={(e) => setMethod(e.target.value as Method)}>
                    <option value="merge">Merge commit</option>
                    <option value="squash">Squash &amp; merge</option>
                    <option value="rebase">Rebase &amp; merge</option>
                  </select>
                  <button className="accept-btn" disabled={!mergeReady} title={mergeReady ? "" : (mergeStatus?.label ?? "Not mergeable yet")} onClick={() => setConfirming("merge")}>Merge</button>
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setConfirming("close")}>Close</button>
                </>
              )}
            </div>
          ) : (
            <div className="pull-actions"><span className="pull-closed-note">{d.merged ? "This pull request was merged." : "This pull request is closed."}</span></div>
          )}

          {msg && <div className={`pull-msg ${msg.kind}`}>{msg.text}</div>}

          {/* changed files + diffs */}
          <div className="pull-files">
            {!files && <div className="repo-msg">Loading files…</div>}
            {files && files.map((f) => (
              <div key={f.filename} className="pull-file">
                <button className="pull-file-head" onClick={() => toggle(f.filename)}>
                  <span className="repo-caret">{expanded.has(f.filename) ? "▾" : "▸"}</span>
                  <span className={`pull-file-status ${f.status}`}>{f.status[0].toUpperCase()}</span>
                  <span className="pull-file-name">{f.filename}</span>
                  <span className="pull-add" style={{ marginLeft: "auto" }}>+{f.additions}</span>
                  <span className="pull-del">−{f.deletions}</span>
                </button>
                {expanded.has(f.filename) && (
                  <pre className="pull-diff">{(f.patch ?? "(no preview — binary or too large)").split("\n").map((ln, i) => (
                    <div key={i} className={diffClass(ln)}>{ln || " "}</div>
                  ))}</pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function diffClass(line: string): string {
  if (line.startsWith("@@")) return "dl hunk";
  if (line.startsWith("+") && !line.startsWith("+++")) return "dl add";
  if (line.startsWith("-") && !line.startsWith("---")) return "dl del";
  return "dl";
}
