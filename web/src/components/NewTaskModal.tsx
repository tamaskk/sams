import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { FolderPicker } from "./FolderPicker";

interface RepoLite { full_name: string; name: string; private: boolean; language: string | null }

// Create a task: name, description, and where it's done — a local project folder
// OR a GitHub repo (the agents clone it, work, and open a PR). Starts in "To Do".
export function NewTaskModal({ onClose, onCreated, initial }: { onClose: () => void; onCreated: () => void; initial?: { title?: string; description?: string } }) {
  const [name, setName] = useState(initial?.title ?? "");
  const [desc, setDesc] = useState(initial?.description ?? "");
  const [project, setProject] = useState("");
  const [imageData, setImageData] = useState<string>("");
  const [imageName, setImageName] = useState<string>("");
  const [source, setSource] = useState<"local" | "github">("local");
  const [repos, setRepos] = useState<RepoLite[] | null>(null);
  const [repoErr, setRepoErr] = useState("");
  const [repoQ, setRepoQ] = useState("");
  const [busy, setBusy] = useState(false);

  const loadRepos = async () => {
    if (repos) return;
    try {
      const d = await api.githubRepos();
      if (!d.configured) { setRepoErr(d.hint || "GitHub is not configured."); setRepos([]); return; }
      setRepos(d.repos.map((r) => ({ full_name: r.full_name, name: r.name, private: r.private, language: r.language })));
    } catch { setRepoErr("Could not load repositories — is the backend running?"); setRepos([]); }
  };

  const pickSource = (s: "local" | "github") => {
    setSource(s);
    setProject("");
    if (s === "github") loadRepos();
  };

  const filteredRepos = useMemo(() => {
    const t = repoQ.trim().toLowerCase();
    const list = repos ?? [];
    return t ? list.filter((r) => r.full_name.toLowerCase().includes(t)) : list;
  }, [repos, repoQ]);

  const onPickImage = (e: any) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setImageData(String(reader.result)); setImageName(file.name); };
    reader.readAsDataURL(file);
  };

  const create = async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    try {
      await api.createTask({
        title: name.trim(), description: desc.trim(), project, column: "To Do",
        image_data: imageData || undefined, image_name: imageName || undefined,
      });
      onCreated();
      onClose();
    } finally {
      setBusy(false);
    }
  };

  const ghName = project.startsWith("github:") ? project.slice(7) : "";

  return (
    <div className="palette-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">New task</div>
        <div className="modal-body">
          <label className="field-label">Name</label>
          <input className="field" autoFocus placeholder="What needs to be done?" value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) create(); }} />

          <label className="field-label">Description</label>
          <textarea className="field" rows={3} placeholder="Details, acceptance criteria, links…"
            value={desc} onChange={(e) => setDesc(e.target.value)} />

          <label className="field-label">Reference image (optional)</label>
          {imageData ? (
            <div className="task-img-row">
              <img className="task-img-preview" src={imageData} alt="reference" />
              <div style={{ fontSize: 11, color: "var(--text-muted)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{imageName}</div>
              <button className="btn-ghost" style={{ padding: "3px 10px", fontSize: 11 }} onClick={() => { setImageData(""); setImageName(""); }}>Remove</button>
            </div>
          ) : (
            <label className="task-img-drop">
              <input type="file" accept="image/*" onChange={onPickImage} style={{ display: "none" }} />
              <span>📎 Attach an image (mockup, screenshot…) — it's given to the AI when the task runs.</span>
            </label>
          )}

          <label className="field-label">Project source</label>
          <div className="seg">
            <button className={source === "local" ? "on" : ""} onClick={() => pickSource("local")}>Local folder</button>
            <button className={source === "github" ? "on" : ""} onClick={() => pickSource("github")}>GitHub repo</button>
          </div>

          {source === "local" ? (
            <FolderPicker onChange={setProject} />
          ) : (
            <div className="repo-pick">
              <input className="gh-search" placeholder="Filter repositories…" value={repoQ} onChange={(e) => setRepoQ(e.target.value)} />
              <div className="repo-pick-list">
                {!repos && !repoErr && <div className="repo-msg">Loading repositories…</div>}
                {repoErr && <div className="repo-msg" style={{ color: "var(--text-muted)" }}>{repoErr}</div>}
                {repos && filteredRepos.map((r) => (
                  <button key={r.full_name}
                    className={`repo-pick-item ${project === `github:${r.full_name}` ? "on" : ""}`}
                    onClick={() => setProject(`github:${r.full_name}`)}>
                    <span className="repo-pick-name">{r.full_name}</span>
                    {r.language && <span className="repo-pick-lang">{r.language}</span>}
                    <span className={`gh-badge ${r.private ? "priv" : "pub"}`}>{r.private ? "Private" : "Public"}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
            {ghName
              ? <>Selected repo: <span className="mono">{ghName}</span> — agents clone it, work, and open a PR.</>
              : <>Selected: <span className="mono">{project || "…"}</span></>}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={!name.trim() || busy} onClick={create}>
            {busy ? "Creating…" : "Create task"}
          </button>
        </div>
      </div>
    </div>
  );
}
