import { api } from "../lib/api";

// The six role-based agent skills. Drag a chip onto the room to spawn an agent,
// or click it to add one. The drag payload is read by the canvas drop handler.
export const SKILLS = [
  { ref: "planner", label: "Planner", color: "#0EA5E9", desc: "Specs, tasks, estimates" },
  { ref: "designer", label: "Designer", color: "#F43F5E", desc: "Wireframes & flows" },
  { ref: "developer", label: "Developer", color: "#3B82F6", desc: "Builds features, opens PRs" },
  { ref: "reviewer", label: "Reviewer", color: "#EF4444", desc: "Reviews & approves" },
  { ref: "tester", label: "Tester", color: "#2DD4BF", desc: "Tests & files bugs" },
  { ref: "deployer", label: "Deployer", color: "#64748B", desc: "CI/CD & rollbacks" },
];

export const SKILL_MIME = "application/sams-skill";

export function SkillPalette() {
  return (
    <div style={{ padding: "4px 8px 8px", display: "flex", flexDirection: "column", gap: 6 }}>
      {SKILLS.map((s) => (
        <div
          key={s.ref}
          className="skill-chip"
          draggable
          title="Drag into the room, or click to add"
          onDragStart={(e) => {
            e.dataTransfer.setData(SKILL_MIME, s.ref);
            e.dataTransfer.effectAllowed = "copy";
          }}
          onClick={() => api.spawnType(s.ref).catch(() => {})}
        >
          <span className="skill-bot" style={{ background: s.color }} />
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
            <span style={{ fontWeight: 600, fontSize: 12 }}>{s.label}</span>
            <span style={{ fontSize: 10, color: "var(--text-subtle)" }}>{s.desc}</span>
          </div>
          <svg className="skill-grip" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <circle cx="9" cy="6" r="1.4" /><circle cx="15" cy="6" r="1.4" />
            <circle cx="9" cy="12" r="1.4" /><circle cx="15" cy="12" r="1.4" />
            <circle cx="9" cy="18" r="1.4" /><circle cx="15" cy="18" r="1.4" />
          </svg>
        </div>
      ))}
    </div>
  );
}
