import { useMemo, useState } from "react";
import { useStore } from "../store";
import { api } from "../lib/api";

interface Cmd { id: string; label: string; group: string; run: () => void; }

// ⌘K command palette (spec 7.4, 7.5): files, agents, and spatial commands.
export function CommandPalette({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const agents = useStore((s) => s.agents);
  const space = useStore((s) => s.space);

  const commands = useMemo<Cmd[]>(() => {
    const spatial: Cmd[] = [
      { id: "agent:new", label: "Spawn New Agent", group: "Spatial", run: () => api.spawn("greeter") },
      { id: "grid:resize", label: "Resize Grid", group: "Spatial", run: () => {} },
      { id: "spatial:add", label: "Add Primitive (Desk)", group: "Spatial", run: () => api.addPrimitive(space, "Desk") },
      { id: "bind:directory", label: "Bind Directory to Primitive", group: "Spatial", run: () => {} },
      { id: "view:reset", label: "Reset View", group: "Spatial", run: () => location.reload() },
      { id: "flow:code-review", label: "Run code-review workflow", group: "Workflows", run: () => api.runWorkflow("code-review", { pr: 128 }) },
      { id: "flow:deploy", label: "Run deploy workflow", group: "Workflows", run: () => api.runWorkflow("deploy", { pr: 128 }) },
      { id: "task:new", label: "New Kanban Card", group: "Tasks", run: () => api.createTask({ title: "New task from palette", labels: ["backend"] }) },
    ];
    const agentCmds: Cmd[] = Object.values(agents).map((a) => ({
      id: `agent:${a.id}`, label: `${a.name} — ${a.state}`, group: "Agents",
      run: () => useStore.getState().select("agent", a.id),
    }));
    return [...spatial, ...agentCmds];
  }, [agents, space]);

  const filtered = commands.filter((c) =>
    (c.label + c.id).toLowerCase().includes(q.toLowerCase())
  );

  const exec = (c: Cmd) => { c.run(); onClose(); };

  return (
    <div className="palette-overlay" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus placeholder="Type a command or search…" value={q}
          onChange={(e) => { setQ(e.target.value); setSel(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setSel((s) => Math.min(s + 1, filtered.length - 1));
            if (e.key === "ArrowUp") setSel((s) => Math.max(s - 1, 0));
            if (e.key === "Enter" && filtered[sel]) exec(filtered[sel]);
          }}
        />
        <div style={{ maxHeight: 360, overflow: "auto" }}>
          {groupBy(filtered).map(([group, items]) => (
            <div key={group}>
              <div className="palette-group">{group}</div>
              {items.map((c) => {
                const idx = filtered.indexOf(c);
                return (
                  <div key={c.id} className={`palette-item ${idx === sel ? "sel" : ""}`}
                    onMouseEnter={() => setSel(idx)} onClick={() => exec(c)}>
                    <span>{c.label}</span>
                    <span className="hint">{c.id}</span>
                  </div>
                );
              })}
            </div>
          ))}
          {filtered.length === 0 && <div className="palette-item" style={{ color: "var(--text-subtle)" }}>No matches</div>}
        </div>
      </div>
    </div>
  );
}

function groupBy(cmds: Cmd[]): [string, Cmd[]][] {
  const m = new Map<string, Cmd[]>();
  for (const c of cmds) { if (!m.has(c.group)) m.set(c.group, []); m.get(c.group)!.push(c); }
  return [...m.entries()];
}
