import { useEffect, useState } from "react";
import { useStore } from "../store";
import { api } from "../lib/api";
import { NewTaskModal } from "./NewTaskModal";
import { TaskEditModal } from "./TaskEditModal";
import type { Card } from "../types";

// The board is a role pipeline: a task starts in To Do, then advances through each
// skill column in order (spec 8.3, adapted to the 6-role fleet).
const COLUMNS = ["To Do", "Planner", "Designer", "Developer", "Reviewer", "Tester", "Deployer", "Committed"];
const COLUMN_COLOR: Record<string, string> = {
  "To Do": "#94A3B8", Planner: "#0EA5E9", Designer: "#F43F5E", Developer: "#3B82F6",
  Reviewer: "#EF4444", Tester: "#2DD4BF", Deployer: "#64748B", Committed: "#16A34A",
};
const COLUMN_HINT: Record<string, string> = {
  "To Do": "New tasks land here", Planner: "Awaiting planning", Designer: "Awaiting design",
  Developer: "Ready to build", Reviewer: "Awaiting review", Tester: "Awaiting QA",
  Deployer: "Ready to ship", Committed: "Shipped tasks",
};
const CARD_MIME = "application/sams-card";
const STAGE_BADGE: Record<string, { label: string; cls: string }> = {
  working: { label: "● working…", cls: "st-working" },
  done: { label: "✓ done", cls: "st-done" },
  ready: { label: "✓ ready to commit", cls: "st-done" },
  awaiting_validation: { label: "✓ ready to commit", cls: "st-done" },
  committing: { label: "● committing…", cls: "st-working" },
  committed: { label: "✓ committed", cls: "st-done" },
  deploying: { label: "● deploying…", cls: "st-working" },
  rejected: { label: "✕ rejected", cls: "st-rejected" },
  error: { label: "✕ error", cls: "st-rejected" },
};

export function KanbanView() {
  const tasks = useStore((s) => s.tasks);
  const setTasks = useStore((s) => s.setTasks);
  const events = useStore((s) => s.events);
  const navCard = useStore((s) => s.navCard);
  const setNavCard = useStore((s) => s.setNavCard);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Card | null>(null);
  const [dragCol, setDragCol] = useState<string | null>(null);

  const refresh = () => api.tasks().then(setTasks).catch(() => {});
  useEffect(() => { refresh(); }, [events.filter((e) => e.type.startsWith("kanban.")).length]);

  // Sync editing card into store so the breadcrumb can display context.
  useEffect(() => {
    setNavCard(editing ? { id: editing.id, title: editing.title, status: editing.status } : null);
    return () => setNavCard(null);
  }, [editing]);

  // Allow breadcrumb "Kanban" click to close the modal.
  useEffect(() => {
    if (!navCard && editing) setEditing(null);
  }, [navCard]);

  // Move a card to a column with an optimistic update so the drag feels instant.
  const moveTo = (id: string, to: string) => {
    const card = tasks.find((c) => c.id === id);
    if (!card || card.status === to) return;
    setTasks(tasks.map((c) => (c.id === id ? { ...c, status: to } : c)));
    api.moveTask(id, to).catch(() => refresh());
  };
  const step = (id: string, status: string, dir: 1 | -1) => {
    const idx = COLUMNS.indexOf(status);
    const next = idx + dir;
    if (next >= 0 && next < COLUMNS.length) moveTo(id, COLUMNS[next]);
  };
  const commit = async (id: string) => {
    // Optimistically move it to Committed (committing…) the instant you click.
    setTasks(tasks.map((c) => (c.id === id ? { ...c, status: "Committed", stage_status: "committing" } : c)));
    await api.commitTask(id).catch(() => {});
    refresh();
  };

  if (tasks.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">▦</div>
        <div className="empty-state-title">No tasks yet</div>
        <div className="empty-state-sub">Create your first task to start the pipeline — agents will pick it up automatically.</div>
        <button className="btn-primary" onClick={() => setCreating(true)}>+ New task</button>
        {creating && <NewTaskModal onClose={() => setCreating(false)} onCreated={refresh} />}
      </div>
    );
  }

  return (
    <>
      <div style={{ position: "absolute", top: 14, right: 16, zIndex: 5 }}>
        <button className="btn-primary" onClick={() => setCreating(true)}>+ New task</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${COLUMNS.length}, 230px)`, gap: 10, padding: "56px 16px 16px", height: "100%", overflowX: "auto", overflowY: "auto" }}>
        {COLUMNS.map((col) => {
          const cards = tasks.filter((c) => c.status === col);
          const isTarget = dragCol === col;
          return (
            <div
              key={col}
              className={`kanban-col ${isTarget ? "drop-target" : ""}`}
              onDragOver={(e) => {
                if (e.dataTransfer.types.includes(CARD_MIME)) {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                  if (dragCol !== col) setDragCol(col);
                }
              }}
              onDrop={(e) => {
                const id = e.dataTransfer.getData(CARD_MIME);
                setDragCol(null);
                if (id) { e.preventDefault(); moveTo(id, col); }
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600, fontSize: 12, marginBottom: 2 }}>
                <span style={{ width: 8, height: 8, borderRadius: 99, background: COLUMN_COLOR[col] }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{col}</span>
                <span style={{ background: "var(--bg-tint)", borderRadius: 999, padding: "0 7px", fontSize: 11, color: "var(--text-muted)" }}>{cards.length}</span>
              </div>
              {cards.map((c) => (
                <div
                  key={c.id}
                  className="kanban-card"
                  draggable
                  onClick={() => setEditing(c)}
                  onDragStart={(e) => { e.dataTransfer.setData(CARD_MIME, c.id); e.dataTransfer.effectAllowed = "move"; }}
                  onDragEnd={() => setDragCol(null)}
                >
                  <div style={{ fontSize: 13, fontWeight: 500, marginBottom: c.description ? 4 : 6 }}>{c.title}</div>
                  {c.description && <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{c.description}</div>}
                  {c.image && <img className="kanban-card-img" src={`/api/v1/tasks/${c.id}/image`} alt="reference" loading="lazy" />}
                  {c.project && (
                    <div className="folder-chip" title={c.project.startsWith("github:") ? c.project.slice(7) : c.project}>
                      {c.project.startsWith("github:") ? (
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.3-1.8-1.3-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2 0-.3-.5-1.5.2-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17.3 5 18.3 5.3 18.3 5.3c.7 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .3" /></svg>
                      ) : (
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 7h6l2 2h10v9H3z" /></svg>
                      )}
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {c.project.startsWith("github:") ? c.project.slice(7) : c.project.split("/").pop()}
                      </span>
                    </div>
                  )}
                  {c.stage_status && c.stage_status !== "idle" && (
                    <div className="stage-row">
                      <span className={`stage-badge ${STAGE_BADGE[c.stage_status]?.cls ?? ""}`}>
                        {STAGE_BADGE[c.stage_status]?.label ?? c.stage_status}
                      </span>
                      {c.status === "Deployer" && (c.stage_status === "ready" || c.stage_status === "awaiting_validation") && (
                        <span style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
                          <button className="accept-btn" title="Commit → move to Committed" onClick={(e) => { e.stopPropagation(); commit(c.id); }}>Commit</button>
                        </span>
                      )}
                    </div>
                  )}
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: 11, color: "var(--text-subtle)" }}>
                    <span className="mono">{c.id}</span>
                    <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
                      {COLUMNS.indexOf(c.status) > 0 && <button className="mini-btn" title="Back a stage" onClick={(e) => { e.stopPropagation(); step(c.id, c.status, -1); }}>←</button>}
                      {COLUMNS.indexOf(c.status) < COLUMNS.length - 1 && c.status !== "Deployer" && <button className="mini-btn" title="Advance to next stage" onClick={(e) => { e.stopPropagation(); step(c.id, c.status, 1); }}>→</button>}
                    </div>
                  </div>
                </div>
              ))}
              {cards.length === 0 && (
                <div className="kanban-empty">{isTarget ? "Drop here" : COLUMN_HINT[col]}</div>
              )}
            </div>
          );
        })}
      </div>
      {creating && <NewTaskModal onClose={() => setCreating(false)} onCreated={refresh} />}
      {editing && <TaskEditModal card={editing} onClose={() => setEditing(null)} onSaved={refresh} />}
    </>
  );
}
