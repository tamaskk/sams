import { useEffect, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { api } from "../lib/api";

// Right context panel: Primitive Properties (Transform / Appearance / Metadata)
// or full selected-agent detail (spec 7.5, 7.13).
export function PropertiesPanel() {
  const selected = useStore((s) => s.selected);
  const scene = useStore((s) => s.scene);

  if (!selected || !selected.id) return <Empty />;

  if (selected.kind === "agent") return <AgentInspector id={selected.id} />;

  const prim = scene?.primitives.find((p) => p.id === selected.id);
  if (!prim) return <Empty />;
  const tr = prim.transform;
  return (
    <div style={{ overflow: "auto", flex: 1 }}>
      <div className="panel-header">Primitive Properties</div>
      <div className="prop-group">
        <h4>{prim.name} <span className="mono" style={{ color: "var(--text-subtle)", fontWeight: 400 }}>{prim.id}</span></h4>
      </div>
      <div className="prop-group">
        <h4>Transform</h4>
        <Row k="Position" v={tr.position.map((n) => n.toFixed(1)).join(", ")} />
        <Row k="Rotation" v={tr.rotation.map((n) => n.toFixed(1)).join(", ")} />
        <Row k="Scale" v={tr.scale.map((n) => n.toFixed(2)).join(", ")} />
      </div>
      <div className="prop-group">
        <h4>Appearance</h4>
        <Row k="Material" v={prim.appearance.material} />
        <Row k="Opacity" v={prim.appearance.opacity.toFixed(2)} />
        <Row k="Edge Glow" v={prim.appearance.edgeGlow ? "on" : "off"} />
        <div className="prop-row"><span className="k">Color</span><span className="v"><span className="swatch" style={{ background: prim.appearance.color }} /> {prim.appearance.color}</span></div>
      </div>
      <div className="prop-group">
        <h4>Metadata</h4>
        <Row k="Tags" v={prim.tags.join(", ")} />
        {prim.bindings.map((b, i) => <Row key={i} k="Binding" v={`${b.channel} → ${b.to}`} />)}
        <Row k="Actions" v={prim.interactions.join(", ")} />
      </div>
    </div>
  );
}

// Full agent inspector: live state + the complete, EDITABLE manifest (system
// prompt, model, capabilities, tools, permissions, memory, routing).
function AgentInspector({ id }: { id: string }) {
  const agent = useStore((s) => s.agents[id]);
  const setAgentColor = useStore((s) => s.setAgentColor);
  const [detail, setDetail] = useState<any | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<any>({});

  useEffect(() => {
    let alive = true;
    setDetail(null); setEditing(false);
    api.agent(id).then((d) => { if (alive) setDetail(d); }).catch(() => { if (alive) setDetail(false); });
    return () => { alive = false; };
  }, [id]);

  const live = agent?.telemetry ?? {};
  const spec = detail?.spec;
  const meta = detail?.metadata;
  const stage = detail?.stage; // pipeline stage prompt (planner/designer/…)
  const name = agent?.name ?? meta?.name ?? id;
  const color = agent?.color ?? meta?.color ?? "#9CA3AF";
  const state = agent?.state ?? detail?.state ?? "idle";
  const hasLive = live.current_task || live.current_file || live.model || live.progress != null || live.tokens_in != null;

  const startEdit = () => {
    setDraft({
      systemPrompt: spec?.systemPrompt ?? "",
      role: spec?.role ?? "",
      seniority: spec?.seniority ?? "mid",
      description: meta?.description ?? "",
      model_provider: spec?.model?.provider ?? "",
      model_name: spec?.model?.name ?? "",
      temperature: spec?.model?.params?.temperature != null ? String(spec.model.params.temperature) : "",
      max_tokens: spec?.model?.params?.max_tokens != null ? String(spec.model.params.max_tokens) : "",
      capabilities: (spec?.capabilities ?? []).join("\n"),
      tools: (spec?.tools ?? []).join("\n"),
      stagePrompt: stage?.prompt ?? "",
    });
    setEditing(true);
  };
  const set = (k: string) => (e: any) => setDraft((d: any) => ({ ...d, [k]: e.target.value }));
  const save = async () => {
    setSaving(true);
    const list = (s: string) => s.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean);
    const body: Record<string, any> = {
      systemPrompt: draft.systemPrompt, role: draft.role, seniority: draft.seniority, description: draft.description,
      model_provider: draft.model_provider, model_name: draft.model_name,
      temperature: String(draft.temperature).trim() === "" ? null : Number(draft.temperature),
      max_tokens: String(draft.max_tokens).trim() === "" ? null : Number(draft.max_tokens),
      capabilities: list(draft.capabilities), tools: list(draft.tools),
    };
    try {
      await api.patchAgent(id, body);
      if (stage) await api.setStagePrompt(stage.column, draft.stagePrompt);
      setDetail(await api.agent(id));
      setEditing(false);
    } catch { /* ignore */ }
    setSaving(false);
  };

  return (
    <div style={{ overflow: "auto", flex: 1 }}>
      <div className="panel-header" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>Agent</span>
        {spec && !editing && <button className="mini-btn" style={{ marginLeft: "auto" }} onClick={startEdit} title="Edit profile">✎ Edit</button>}
        {editing && (
          <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            <button className="accept-btn" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
            <button className="btn-ghost" style={{ padding: "3px 10px", fontSize: 11 }} onClick={() => setEditing(false)}>Cancel</button>
          </span>
        )}
      </div>

      <div className="prop-group">
        <h4>
          <label className="swatch swatch-btn" style={{ background: color }} title="Change agent color">
            <input
              type="color"
              className="swatch-color-input"
              value={color}
              onChange={(e) => {
                const newColor = e.target.value;
                setAgentColor(id, newColor);
                api.patchAgent(id, { color: newColor }).catch(() => {});
              }}
            />
          </label>
          {" "}{name}
        </h4>
        {!editing && spec && <div className="agent-sub">{spec.role}{spec.seniority ? ` · ${spec.seniority}` : ""}</div>}
        {!editing && meta?.description && <div className="agent-desc">{meta.description}</div>}
        <Row k="State" v={state} />
        <Row k="Home" v={agent?.home ?? spec?.home?.primitive ?? "—"} />
        <Row k="Agent id" v={id} mono />
      </div>

      {hasLive && (
        <div className="prop-group">
          <h4>Live</h4>
          {live.current_task && <Row k="Task" v={live.current_task} />}
          {live.current_file && <Row k="File" v={live.current_file} />}
          {live.model && <Row k="Model" v={live.model} />}
          {live.progress != null && <Row k="Progress" v={`${Math.round((live.progress || 0) * 100)}%`} />}
          {live.tokens_in != null && <Row k="Tokens" v={`${live.tokens_in} / ${live.tokens_out}`} />}
        </div>
      )}

      {detail === null && <div className="prop-group"><div className="agent-muted">Loading details…</div></div>}

      {/* ---- EDIT FORM ---- */}
      {spec && editing && (
        <div className="prop-group agent-edit">
          <Field label="Role"><input className="field" value={draft.role} onChange={set("role")} /></Field>
          <Field label="Seniority">
            <select className="field" value={draft.seniority} onChange={set("seniority")}>
              {["junior", "mid", "senior", "principal"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Description"><input className="field" value={draft.description} onChange={set("description")} /></Field>
          <Field label="Model provider"><input className="field" value={draft.model_provider} onChange={set("model_provider")} /></Field>
          <Field label="Model name"><input className="field" value={draft.model_name} onChange={set("model_name")} /></Field>
          <div style={{ display: "flex", gap: 8 }}>
            <Field label="Temperature"><input className="field" type="number" step="0.1" value={draft.temperature} onChange={set("temperature")} /></Field>
            <Field label="Max tokens"><input className="field" type="number" value={draft.max_tokens} onChange={set("max_tokens")} /></Field>
          </div>
          <Field label="System prompt"><textarea className="field" rows={9} value={draft.systemPrompt} onChange={set("systemPrompt")} /></Field>
          {stage && (
            <Field label={`Pipeline stage prompt · ${stage.column}`}>
              <textarea className="field" rows={8} value={draft.stagePrompt} onChange={set("stagePrompt")} />
              <button className="link-reset" type="button" onClick={() => setDraft((d: any) => ({ ...d, stagePrompt: stage.default }))}>reset to default</button>
              <span className="agent-field-hint">This is what the agent actually runs for this Kanban stage.</span>
            </Field>
          )}
          <Field label="Capabilities (one per line)"><textarea className="field mono" rows={3} value={draft.capabilities} onChange={set("capabilities")} /></Field>
          <Field label="Tools (one per line)"><textarea className="field mono" rows={3} value={draft.tools} onChange={set("tools")} /></Field>
        </div>
      )}

      {/* ---- READ-ONLY ---- */}
      {spec && !editing && <>
        <div className="prop-group">
          <h4>Model</h4>
          <Row k="Provider" v={spec.model?.provider ?? "—"} />
          <Row k="Model" v={spec.model?.name ?? "—"} mono />
          {spec.model?.params?.temperature != null && <Row k="Temperature" v={String(spec.model.params.temperature)} />}
          {spec.model?.params?.max_tokens != null && <Row k="Max tokens" v={String(spec.model.params.max_tokens)} />}
        </div>
        <div className="prop-group">
          <h4>System prompt</h4>
          <pre className="agent-prompt">{spec.systemPrompt?.trim() || "(none)"}</pre>
        </div>
        {stage && (
          <div className="prop-group">
            <h4>Pipeline stage prompt <span className="agent-muted" style={{ fontWeight: 400 }}>· {stage.column}{stage.overridden ? " · custom" : ""}</span></h4>
            <pre className="agent-prompt">{stage.prompt?.trim() || "(none)"}</pre>
          </div>
        )}
        <div className="prop-group"><h4>Capabilities</h4><Chips items={spec.capabilities} kind="cap" /></div>
        <div className="prop-group"><h4>Tools</h4><Chips items={spec.tools} kind="tool" /></div>
        <div className="prop-group">
          <h4>Permissions</h4>
          <Row k="Can approve" v={spec.permissions?.approve ? "yes" : "no"} />
          <Row k="Environments" v={(spec.permissions?.environments ?? []).join(", ") || "—"} />
          {(spec.permissions?.read ?? []).length > 0 && <Row k="Read" v={spec.permissions.read.join("  ")} mono />}
          {(spec.permissions?.write ?? []).length > 0 && <Row k="Write" v={spec.permissions.write.join("  ")} mono />}
        </div>
        <div className="prop-group">
          <h4>Memory &amp; routing</h4>
          <Row k="Memory" v={`${spec.memory?.scope ?? "—"}${spec.memory?.retention ? ` · ${spec.memory.retention}` : ""}`} />
          <Row k="Priority" v={spec.routing?.priority ?? "—"} />
          <Row k="Concurrency" v={String(spec.routing?.concurrency ?? "—")} />
        </div>
        <div className="prop-group">
          <h4>Identity</h4>
          <Row k="Version" v={meta?.version ?? "—"} />
          <Row k="Tags" v={(meta?.tags ?? []).join(", ") || "—"} />
          <Row k="Authors" v={(meta?.authors ?? []).join(", ") || "—"} />
        </div>
      </>}

      {!editing && (
        <div className="prop-group">
          <button className="btn-danger" onClick={async () => { await api.despawn(id).catch(() => {}); useStore.getState().select("agent", ""); }}>
            Delete agent
          </button>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="agent-field"><label className="agent-field-label">{label}</label>{children}</div>;
}

function Chips({ items, kind }: { items?: string[]; kind: "cap" | "tool" }) {
  if (!items?.length) return <span className="agent-muted">—</span>;
  return <div className="chips">{items.map((c) => <span key={c} className={`chip ${kind}`}>{c}</span>)}</div>;
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return <div className="prop-row"><span className="k">{k}</span><span className={`v${mono ? " mono" : ""}`}>{v}</span></div>;
}
function Empty() {
  return <div style={{ padding: 16, color: "var(--text-subtle)", fontSize: 12 }}>Select an agent or primitive to inspect it.</div>;
}
