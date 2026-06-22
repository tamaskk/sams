import { useState } from "react";
import { api } from "../lib/api";
import { useStore } from "../store";
import { FolderPicker } from "./FolderPicker";
import type { Card } from "../types";

const STAGES = ["To Do", "Planner", "Designer", "Developer", "Reviewer", "Tester", "Deployer"];
const PRIORITIES = ["Low", "Medium", "High"];

// Click a card -> edit everything: name, description, skill/stage (dropdown),
// priority, assignee, labels, project folder. Plus delete.
export function TaskEditModal({ card, onClose, onSaved }: { card: Card; onClose: () => void; onSaved: () => void }) {
  const agentsMap = useStore((s) => s.agents);
  const agents = Object.values(agentsMap);
  const [title, setTitle] = useState(card.title);
  const [desc, setDesc] = useState(card.description || "");
  const [stage, setStage] = useState(card.status);
  const [priority, setPriority] = useState(card.priority || "Medium");
  const [assignee, setAssignee] = useState(card.assignee || "");
  const [labels, setLabels] = useState((card.labels || []).join(", "));
  const [project, setProject] = useState(card.project || "");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.updateTask(card.id, {
        title: title.trim(),
        description: desc.trim(),
        to: stage,
        priority,
        assignee,
        labels: labels.split(",").map((l) => l.trim()).filter(Boolean),
        project,
      });
      onSaved();
      onClose();
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.deleteTask(card.id);
      onSaved();
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="palette-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>Edit task</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--text-subtle)", fontWeight: 400 }}>{card.id}</span>
        </div>
        <div className="modal-body" style={{ maxHeight: "62vh", overflow: "auto" }}>
          {card.stage_status === "awaiting_validation" && (
            <div className="validate-banner">
              <strong>Awaiting your validation</strong> — review the stage outputs below, then accept to deploy/commit.
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button className="btn-primary" disabled={busy}
                  onClick={async () => { setBusy(true); await api.acceptTask(card.id).catch(() => {}); onSaved(); onClose(); }}>
                  Validate &amp; Accept → Deploy
                </button>
                <button className="btn-danger" style={{ width: "auto", padding: "8px 14px" }} disabled={busy}
                  onClick={async () => { setBusy(true); await api.rejectTask(card.id).catch(() => {}); onSaved(); onClose(); }}>
                  Reject
                </button>
              </div>
            </div>
          )}
          {Object.keys(card.outputs || {}).length > 0 && (
            <>
              <label className="field-label">Stage outputs (what each agent produced)</label>
              <div className="stage-outputs">
                {Object.entries(card.outputs).map(([stage, out]) => (
                  <div key={stage} className="stage-output">
                    <div className="stage-output-h">{stage}</div>
                    <div className="stage-output-b">{out}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          <label className="field-label">Name</label>
          <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} />

          <label className="field-label">Description</label>
          <textarea className="field" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label className="field-label">Skill / stage</label>
              <select className="field" value={stage} onChange={(e) => setStage(e.target.value)}>
                {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label">Priority</label>
              <select className="field" value={priority} onChange={(e) => setPriority(e.target.value)}>
                {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>

          <label className="field-label">Assignee</label>
          <select className="field" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">Unassigned</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>

          <label className="field-label">Labels (comma separated)</label>
          <input className="field" placeholder="backend, urgent" value={labels} onChange={(e) => setLabels(e.target.value)} />

          <label className="field-label">Project folder</label>
          <FolderPicker initialPath={card.project || undefined} onChange={setProject} />
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
            Selected: <span className="mono">{project || "…"}</span>
          </div>
        </div>
        <div className="modal-footer" style={{ justifyContent: "space-between" }}>
          <button className="btn-danger" style={{ width: "auto", padding: "8px 14px" }} disabled={busy} onClick={remove}>Delete</button>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-primary" disabled={busy || !title.trim()} onClick={save}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
