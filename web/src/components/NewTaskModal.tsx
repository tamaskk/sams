import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { FolderPicker } from "./FolderPicker";

interface RepoLite { full_name: string; name: string; private: boolean; language: string | null }

function validateField(field: string, value: string | number): string {
  switch (field) {
    case "name":
      return String(value).trim() ? "" : "Task name is required.";
    case "desc": {
      const len = String(value).length;
      return len > 500 ? `${len - 500} characters over the 500-character limit.` : "";
    }
    case "maxAttempts": {
      const n = Number(value);
      if (!Number.isInteger(n) || isNaN(n)) return "Must be a whole number between 1 and 10.";
      if (n < 1) return "Must be at least 1.";
      if (n > 10) return "Must be 10 or fewer.";
      return "";
    }
    case "initialDelay": {
      const n = Number(value);
      if (isNaN(n)) return "Must be a number.";
      if (n < 0.1) return "Must be at least 0.1 seconds.";
      if (n > 30) return "Must be 30 seconds or less.";
      return "";
    }
    case "backoffMultiplier": {
      const n = Number(value);
      if (isNaN(n)) return "Must be a number.";
      if (n < 1) return "Must be at least 1×.";
      if (n > 5) return "Must be 5× or less.";
      return "";
    }
    default:
      return "";
  }
}

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
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxAttempts, setMaxAttempts] = useState(3);
  const [initialDelay, setInitialDelay] = useState(1.0);
  const [backoffMultiplier, setBackoffMultiplier] = useState(2.0);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const touch = (field: string) => setTouched((t) => ({ ...t, [field]: true }));

  const errors = {
    name: validateField("name", name),
    desc: validateField("desc", desc),
    maxAttempts: validateField("maxAttempts", maxAttempts),
    initialDelay: validateField("initialDelay", initialDelay),
    backoffMultiplier: validateField("backoffMultiplier", backoffMultiplier),
  };

  const fieldClass = (field: keyof typeof errors) =>
    `field${touched[field] ? (errors[field] ? " error" : " valid") : ""}`;

  const fieldFeedback = (field: keyof typeof errors) => {
    if (!touched[field]) return null;
    if (errors[field]) return <div className="field-error">{errors[field]}</div>;
    if (field === "desc" && !desc.trim()) return null;
    return <div className="field-check">✓</div>;
  };

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
    const retry_options = maxAttempts > 1
      ? { max_attempts: maxAttempts, initial_delay: initialDelay, backoff_multiplier: backoffMultiplier }
      : undefined;
    try {
      await api.createTask({
        title: name.trim(), description: desc.trim(), project, column: "To Do",
        image_data: imageData || undefined, image_name: imageName || undefined,
        retry_options,
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
          <input className={fieldClass("name")} autoFocus placeholder="What needs to be done?" value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => touch("name")}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) create(); }} />
          {fieldFeedback("name")}

          <label className="field-label">Description</label>
          <textarea className={fieldClass("desc")} rows={3} placeholder="Details, acceptance criteria, links…"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            onBlur={() => touch("desc")} />
          {fieldFeedback("desc")}

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
                {!repos && !repoErr && (
                  <div style={{ padding: "8px 10px", display: "flex", flexDirection: "column", gap: 9 }}>
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="skel" style={{ flex: 1, height: 14 }} />
                        <span className="skel" style={{ width: 36, height: 14 }} />
                        <span className="skel" style={{ width: 48, height: 14, borderRadius: 999 }} />
                      </div>
                    ))}
                  </div>
                )}
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

          <div style={{ marginTop: 10 }}>
            <button
              style={{ fontSize: 11, color: "var(--text-muted)", background: "none", border: "none", padding: 0, cursor: "pointer", display: "flex", alignItems: "center", gap: 5 }}
              onClick={() => setShowAdvanced((v) => !v)}
              type="button"
            >
              <span style={{ display: "inline-block", transition: "transform .15s", transform: showAdvanced ? "rotate(90deg)" : "none" }}>›</span>
              Advanced options
            </button>
            {showAdvanced && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 8 }}>
                <div>
                  <label className="field-label">Max retries</label>
                  <input className={fieldClass("maxAttempts")} type="number" min={1} max={10} step={1} value={maxAttempts}
                    onChange={(e) => setMaxAttempts(Number(e.target.value))}
                    onBlur={() => { touch("maxAttempts"); setMaxAttempts(Math.max(1, Math.min(10, maxAttempts))); }} />
                  {fieldFeedback("maxAttempts")}
                </div>
                <div>
                  <label className="field-label">Initial delay (s)</label>
                  <input className={fieldClass("initialDelay")} type="number" min={0.1} max={30} step={0.1} value={initialDelay}
                    onChange={(e) => setInitialDelay(Number(e.target.value))}
                    onBlur={() => { touch("initialDelay"); setInitialDelay(Math.max(0.1, initialDelay)); }} />
                  {fieldFeedback("initialDelay")}
                </div>
                <div>
                  <label className="field-label">Backoff multiplier</label>
                  <input className={fieldClass("backoffMultiplier")} type="number" min={1} max={5} step={0.1} value={backoffMultiplier}
                    onChange={(e) => setBackoffMultiplier(Number(e.target.value))}
                    onBlur={() => { touch("backoffMultiplier"); setBackoffMultiplier(Math.max(1, backoffMultiplier)); }} />
                  {fieldFeedback("backoffMultiplier")}
                </div>
              </div>
            )}
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
