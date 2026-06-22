import { useEffect, useState } from "react";
import { TopBar } from "./TopBar";
import { IconRail } from "./IconRail";
import { Explorer } from "./Explorer";
import { SourceControl } from "./SourceControl";
import { GitHubPanel } from "./GitHubPanel";
import { SystemOverview } from "./SystemOverview";
import { PropertiesPanel } from "./PropertiesPanel";
import { Console } from "./Console";
import { StatusBar } from "./StatusBar";
import { CommandPalette } from "./CommandPalette";
import { Scene } from "./scene/Scene";
import { SpatialToolbar } from "./SpatialToolbar";
import { KanbanView } from "./KanbanView";
import { ErrorBoundary } from "./ErrorBoundary";
import { CodeView } from "./CodeView";
import { RepoView } from "./RepoView";
import { PullView } from "./PullView";
import { IdeasView } from "./IdeasView";
import { Breadcrumb } from "./Breadcrumb";
import { useStore } from "../store";
import { SKILL_MIME } from "./SkillPalette";
import { api } from "../lib/api";

type Tab = "Spatial" | "Kanban" | "Whiteboard" | "Code" | "Ideas";

export function Shell() {
  const [tab, setTab] = useState<Tab>("Spatial");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [railView, setRailView] = useState("explorer");
  const openFile = useStore((s) => s.openFile);
  const selectedRepo = useStore((s) => s.selectedRepo);
  const closeRepo = useStore((s) => s.closeRepo);
  const selectedPull = useStore((s) => s.selectedPull);
  const closePull = useStore((s) => s.closePull);
  const closeGit = () => { closeRepo(); closePull(); };

  // Opening a local file from the Explorer jumps to the Code tab (and leaves any
  // open GitHub repo/PR).
  useEffect(() => {
    if (openFile) { setTab("Code"); closeGit(); }
  }, [openFile]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "p")) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="shell">
      <TopBar onSearch={() => setPaletteOpen(true)} />
      <div className="shell-body">
        <IconRail
          active={tab === "Ideas" ? "ideas" : railView}
          onSelect={(id) => {
            if (id === "ideas") { closeGit(); setTab("Ideas"); }
            else setRailView(id);
          }}
        />
        {railView === "scm" ? <SourceControl /> : railView === "github" ? <GitHubPanel /> : <Explorer />}
        <div className="shell-center">
          <Breadcrumb
            tab={tab}
            onTabClick={(t) => { closeGit(); setTab(t as Tab); }}
            onCloseRepo={closeGit}
            onClosePull={closePull}
          />
          <div
            className="canvas-wrap"
            onDragOver={(e) => {
              if (e.dataTransfer.types.includes(SKILL_MIME)) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "copy";
                if (!dragOver) setDragOver(true);
              }
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              const ref = e.dataTransfer.getData(SKILL_MIME);
              setDragOver(false);
              if (ref) {
                e.preventDefault();
                if (tab !== "Spatial") setTab("Spatial");
                api.spawnType(ref).catch(() => {});
              }
            }}
          >
            {dragOver && tab === "Spatial" && (
              <div className="drop-hint">Drop to add this agent to the room</div>
            )}
            <div className="canvas-tabs">
              {(["Spatial", "Kanban", "Whiteboard", "Code", "Ideas"] as Tab[]).map((t) => (
                <button key={t} className={`canvas-tab ${!selectedRepo && !selectedPull && tab === t ? "active" : ""}`} onClick={() => { closeGit(); setTab(t); }}>{t}</button>
              ))}
              {selectedPull ? (
                <button className="canvas-tab active" onClick={closePull} title="Close pull request">PR #{selectedPull.number} ✕</button>
              ) : selectedRepo && (
                <button className="canvas-tab active" onClick={closeRepo} title="Close repository">{selectedRepo.name} ✕</button>
              )}
            </div>
            {selectedPull ? (
              <PullView key={`${selectedPull.repo}#${selectedPull.number}`} />
            ) : selectedRepo ? (
              <RepoView />
            ) : (
              <>
                {tab === "Spatial" && <><SpatialToolbar /><ErrorBoundary><Scene /></ErrorBoundary></>}
                {tab === "Kanban" && <KanbanView />}
                {tab === "Whiteboard" && (
                  <div className="empty-state">
                    <div className="empty-state-icon">✏</div>
                    <div className="empty-state-title">Whiteboard — coming soon</div>
                    <div className="empty-state-sub">A free-form canvas for designing, diagramming, and documenting alongside your agents.</div>
                    <button className="btn-primary" onClick={() => setTab("Kanban")}>Go to Kanban →</button>
                  </div>
                )}
                {tab === "Code" && <CodeView />}
                {tab === "Ideas" && <IdeasView />}
              </>
            )}
          </div>
          <Console />
        </div>
        <div className="panel right" style={{ display: "flex", flexDirection: "column" }}>
          <SystemOverview />
          <PropertiesPanel />
        </div>
      </div>
      <StatusBar />
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </div>
  );
}

function Placeholder({ label }: { label: string }) {
  return <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--text-subtle)" }}>{label}</div>;
}
