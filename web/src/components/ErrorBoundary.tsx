import { Component, type ReactNode } from "react";

// Isolates the WebGL canvas: if a GPU/WebGL context can't be created (e.g. a
// headless/software environment), the rest of the IDE shell keeps working.
export class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--text-subtle)", padding: 24, textAlign: "center" }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>3D view unavailable</div>
              <div style={{ fontSize: 12 }}>WebGL could not start in this environment. The Kanban, Console, and panels remain live — switch to the Kanban tab.</div>
            </div>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
