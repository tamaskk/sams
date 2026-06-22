import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { NewTaskModal } from "./NewTaskModal";

interface CUTask { id: string; name: string; description: string; status: string; url: string; priority: string | null; list: string; team: string; }

// Source Control panel: fetch the ClickUp tasks assigned to me, then Accept
// (create a SAMS card now), Edit (open the task modal prefilled), or Decline.
export function SourceControl() {
  const [tasks, setTasks] = useState<CUTask[] | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [hint, setHint] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<CUTask | null>(null);
  const [accepted, setAccepted] = useState<Set<string>>(new Set());

  const load = async () => {
    setLoading(true);
    try {
      const d = await api.clickupTasks();
      setConfigured(d.configured);
      setHint(d.hint ?? "");
      setTasks(d.tasks ?? []);
    } catch (e: any) {
      setConfigured(false);
      const msg = String(e?.message ?? "");
      setHint(msg.includes("404")
        ? "The running backend doesn't have the ClickUp endpoints yet — restart `sams up`."
        : "Could not reach the SAMS backend.");
      setTasks([]);
    }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const accept = async (t: CUTask) => {
    await api.createTask({ title: t.name, description: t.description, labels: t.status ? [t.status] : [] }).catch(() => {});
    setAccepted((s) => new Set(s).add(t.id));
  };
  const decline = (t: CUTask) => setTasks((ts) => (ts ?? []).filter((x) => x.id !== t.id));

  return (
    <div className="panel">
      <div className="panel-header" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>Source Control · ClickUp</span>
        <button className="mini-btn" title="Refresh" style={{ marginLeft: "auto" }} onClick={load}>⟳</button>
      </div>
      <div className="panel-scroll">
        {configured === false && (
          <div style={{ padding: "8px 10px", fontSize: 12, color: "var(--text-muted)" }}>
            <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 6 }}>Connect ClickUp</div>
            {hint || "Set CLICKUP_API_TOKEN before starting SAMS."}
            <div style={{ marginTop: 8, fontSize: 11 }}>
              ClickUp → Settings → Apps → <span className="mono">API Token</span> (pk_…), then:
              <pre className="mono" style={{ background: "var(--bg-app)", padding: 8, borderRadius: 6, marginTop: 6, whiteSpace: "pre-wrap" }}>export CLICKUP_API_TOKEN=pk_…
sams up</pre>
            </div>
          </div>
        )}
        {loading && <div style={{ padding: 10, color: "var(--text-subtle)", fontSize: 12 }}>Loading my tasks…</div>}
        {configured && tasks && tasks.length === 0 && !loading && (
          <div style={{ padding: 10, color: "var(--text-subtle)", fontSize: 12 }}>No open tasks assigned to you.</div>
        )}
        {configured && (tasks ?? []).map((t) => (
          <div key={t.id} className="cu-task">
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
              <span className="cu-status">{t.status}</span>
              {t.list && <span className="cu-list">{t.list}</span>}
            </div>
            <div style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.3 }}>{t.name}</div>
            {accepted.has(t.id) ? (
              <div style={{ marginTop: 6, fontSize: 11, color: "var(--success)", fontWeight: 600 }}>✓ added to To Do</div>
            ) : (
              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                <button className="accept-btn" onClick={() => accept(t)}>Accept</button>
                <button className="btn-ghost" style={{ padding: "3px 10px", fontSize: 11 }} onClick={() => setEditing(t)}>Edit</button>
                <button className="reject-btn" onClick={() => decline(t)} title="Decline">✕</button>
              </div>
            )}
          </div>
        ))}
      </div>
      {editing && (
        <NewTaskModal
          initial={{ title: editing.name, description: editing.description }}
          onClose={() => setEditing(null)}
          onCreated={() => { setAccepted((s) => new Set(s).add(editing.id)); setEditing(null); }}
        />
      )}
    </div>
  );
}
