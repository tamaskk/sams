import { useStore } from "../store";

// Bottom status bar (spec 7.1): branch, problems, spaces, encoding, connection.
export function StatusBar() {
  const connected = useStore((s) => s.connected);
  const status = useStore((s) => s.status);
  const events = useStore((s) => s.events);
  const problems = events.filter((e) => e.type.includes("error")).length;

  return (
    <div className="statusbar">
      <span>⬡ main*</span>
      <span>⊘ {problems}</span>
      <span>⚠ 0</span>
      <span>Spaces: {status?.spaces.length ?? 0}</span>
      <div className="right">
        <span>UTF-8</span>
        <span>LF</span>
        <span>YAML</span>
        <span className={`conn ${connected ? "" : "off"}`}>
          <span className="dot" /> SAMS: {connected ? "Connected" : "Reconnecting…"}
        </span>
        <span>
          v{status?.version ?? "0.9.0"} · Spatial Mode · {status?.agents_online ?? 0} Agents Online ·{" "}
          {status?.posture.gates === "auto" ? "Dev Mode" : "Guarded"}
        </span>
      </div>
    </div>
  );
}
