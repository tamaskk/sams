// Left rail: Explorer, Search, Source Control, GitHub, Extensions (spec 7.17).
const TOOLS: { id: string; title: string; path: string; fill?: boolean }[] = [
  { id: "explorer", title: "Explorer", path: "M3 7h7l2 2h9v11H3z" },
  { id: "search", title: "Search", path: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm9 2-3.5-3.5" },
  { id: "scm", title: "Source Control · ClickUp", path: "M6 3v12m0 0a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm12-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm0 0v3a6 6 0 0 1-6 6h-3" },
  { id: "github", title: "GitHub · my repositories", fill: true, path: "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.51 11.51 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222 0 1.606-.014 2.898-.014 3.293 0 .322.216.694.825.576C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" },
  { id: "ideas", title: "AI Ideas Generator", path: "M9.663 17h4.673M12 3v1m6.364 1.636-.707.707M21 12h-1M4 12H3m3.343-5.657-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547Z" },
  { id: "ext", title: "Extensions", path: "M4 4h7v7H4zM13 13h7v7h-7zM13 4h7v7h-7zM4 13h7v7H4z" },
];

export function IconRail({ active, onSelect }: { active: string; onSelect: (id: string) => void }) {
  return (
    <div className="rail">
      {TOOLS.map((t) => (
        <button key={t.id} title={t.title} className={active === t.id ? "active" : ""} onClick={() => onSelect(t.id)}>
          <svg width="20" height="20" viewBox="0 0 24 24"
            fill={t.fill ? "currentColor" : "none"} stroke={t.fill ? "none" : "currentColor"}
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d={t.path} /></svg>
        </button>
      ))}
    </div>
  );
}
