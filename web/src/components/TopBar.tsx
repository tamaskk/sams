import { useStore } from "../store";

export function TopBar({ onSearch }: { onSearch: () => void }) {
  const status = useStore((s) => s.status);
  return (
    <div className="topbar">
      <div className="traffic"><span className="r" /><span className="y" /><span className="g" /></div>
      <div>
        <span className="wordmark">SAMS</span>{" "}
        <span className="subtitle">Spatial Agentic Management System</span>
      </div>
      <div className="topbar-spacer" />
      <div className="search-pill" onClick={onSearch}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>
        <span>Type a command or search…</span>
        <span className="kbd">⌘K</span>
      </div>
      <div className="topbar-spacer" />
      <div className="topbar-actions">
        <Icon path="M17 20h5v-2a4 4 0 0 0-3-3.87M9 20H4v-2a4 4 0 0 1 3-3.87m6-1.13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
        <Icon path="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" />
        <div className="avatar-chip">{status?.mode?.[0]?.toUpperCase() ?? "A"}</div>
      </div>
    </div>
  );
}

function Icon({ path }: { path: string }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d={path} /></svg>;
}
