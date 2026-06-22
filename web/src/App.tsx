import { useEffect } from "react";
import { Shell } from "./components/Shell";
import { connectStream } from "./lib/ws";
import { api } from "./lib/api";
import { useStore } from "./store";

export default function App() {
  useEffect(() => connectStream("main.space"), []);

  // Poll running projects so folder rows show ▶/✕ and the Terminal shows live logs.
  useEffect(() => {
    const tick = () => api.runningProjects().then(useStore.getState().setRunningProjects).catch(() => {});
    tick();
    const id = setInterval(tick, 2000);
    return () => clearInterval(id);
  }, []);

  return <Shell />;
}
