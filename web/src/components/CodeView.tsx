import { useStore } from "../store";

// A simple read-only file viewer for files opened from the Explorer's FILES tree.
export function CodeView() {
  const openFile = useStore((s) => s.openFile);
  if (!openFile) {
    return (
      <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--text-subtle)", paddingTop: 56 }}>
        Open a file from the Explorer (FILES) to view it here.
      </div>
    );
  }
  const name = openFile.path.split("/").pop();
  const lines = openFile.content.split("\n");
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", paddingTop: 44 }}>
      <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{name}</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-subtle)" }}>{openFile.path}</span>
      </div>
      <div style={{ overflow: "auto", flex: 1, background: "var(--bg-panel)" }}>
        <table className="mono" style={{ fontSize: 12, borderCollapse: "collapse", width: "100%" }}>
          <tbody>
            {lines.map((ln, i) => (
              <tr key={i}>
                <td style={{ textAlign: "right", padding: "0 10px", color: "var(--text-subtle)", userSelect: "none", verticalAlign: "top", width: 1, whiteSpace: "nowrap" }}>{i + 1}</td>
                <td style={{ padding: "0 12px", whiteSpace: "pre-wrap", color: "var(--text)" }}>{ln || " "}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
