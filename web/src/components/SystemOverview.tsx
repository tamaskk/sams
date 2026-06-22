import { useStore } from "../store";

// The System Overview minimap: a zoomed-out projection of all agents (spec 7.6).
export function SystemOverview() {
  const agents = useStore((s) => s.agents);
  const scene = useStore((s) => s.scene);
  const select = useStore((s) => s.select);
  const list = Object.values(agents);
  const W = scene?.room.width ?? 12;
  const D = scene?.room.depth ?? 10;

  return (
    <div className="minimap">
      <div className="minimap-count">{list.length} Agents Active</div>
      {scene?.primitives.map((p) => (
        <div key={p.id} title={p.name} style={{
          position: "absolute", left: `${(p.transform.position[0] / W) * 100}%`,
          top: `${(p.transform.position[2] / D) * 100}%`, width: 6, height: 6,
          transform: "translate(-50%,-50%)", borderRadius: 2,
          background: "var(--border-strong)", opacity: 0.7,
        }} />
      ))}
      {list.map((a) => (
        <div
          key={a.id}
          className="minimap-dot"
          title={`${a.name} · ${a.state}`}
          onClick={() => select("agent", a.id)}
          style={{
            left: `${(a.position[0] / W) * 100}%`,
            top: `${(a.position[2] / D) * 100}%`,
            background: a.color,
            boxShadow: a.state === "working" ? `0 0 8px ${a.color}` : undefined,
            cursor: "pointer",
          }}
        />
      ))}
    </div>
  );
}
