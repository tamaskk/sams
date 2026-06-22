import { useState } from "react";
import { useStore } from "../store";
import { FileTree } from "./FileTree";
import { SkillPalette } from "./SkillPalette";

const WORKSPACE_CONTENT: Record<string, string> = {
  "onboarding.flow": `name: onboarding
version: "1.0"
description: Guide a new team member through the onboarding process

steps:
  - id: welcome
    agent: planner
    action: send_welcome_message

  - id: setup_env
    agent: developer
    action: provision_dev_environment
    depends_on: [welcome]

  - id: first_task
    agent: designer
    action: assign_starter_task
    depends_on: [setup_env]

  - id: review_onboarding
    agent: reviewer
    action: verify_completion
    depends_on: [first_task]
`,
  "code-review.flow": `name: code-review
version: "1.0"
description: Automated code review pipeline

steps:
  - id: lint
    agent: tester
    action: run_linter

  - id: static_analysis
    agent: reviewer
    action: static_code_analysis
    depends_on: [lint]

  - id: security_check
    agent: reviewer
    action: security_scan
    depends_on: [lint]

  - id: approve_or_request
    agent: reviewer
    action: submit_review
    depends_on: [static_analysis, security_check]
`,
  "deploy.flow": `name: deploy
version: "1.0"
description: Deploy the application to production

steps:
  - id: build
    agent: developer
    action: build_artifact

  - id: test
    agent: tester
    action: run_integration_tests
    depends_on: [build]

  - id: stage
    agent: deployer
    action: deploy_to_staging
    depends_on: [test]

  - id: smoke_test
    agent: tester
    action: run_smoke_tests
    depends_on: [stage]

  - id: prod
    agent: deployer
    action: deploy_to_production
    depends_on: [smoke_test]
    gate: security_approval
`,
  "architecture.spatial": `name: architecture
version: "1.0"
description: High-level system architecture spatial view

nodes:
  - id: gateway
    label: API Gateway
    position: [6, 0, 3]
    type: service
    color: "#0EA5E9"

  - id: auth
    label: Auth Service
    position: [3, 0, 6]
    type: service
    color: "#F43F5E"

  - id: core
    label: Core API
    position: [6, 0, 6]
    type: service
    color: "#3B82F6"

  - id: db
    label: Database
    position: [9, 0, 9]
    type: datastore
    color: "#64748B"

edges:
  - from: gateway
    to: auth
  - from: gateway
    to: core
  - from: core
    to: db
`,
  "office-layout.spatial": `name: office-layout
version: "1.0"
description: Virtual office floor plan for agent workspace

zones:
  - id: dev_corner
    label: Dev Corner
    bounds: [1, 1, 5, 5]
    color: "#3B82F620"

  - id: review_area
    label: Review Area
    bounds: [7, 1, 11, 5]
    color: "#EF444420"

  - id: lounge
    label: Lounge
    bounds: [1, 7, 5, 11]
    color: "#2DD4BF20"

furniture:
  - id: whiteboard
    type: whiteboard
    position: [3, 0, 8]

  - id: conf_table
    type: table
    position: [9, 0, 8]
`,
  "furniture.spatial": `name: furniture
version: "1.0"
description: Furniture and decor assets for the virtual office

items:
  - id: desk_standard
    label: Standard Desk
    model: desk
    scale: [1, 1, 1]
    variants:
      - name: oak
        color: "#8B5E3C"
      - name: white
        color: "#F8FAFC"

  - id: chair_ergonomic
    label: Ergonomic Chair
    model: chair
    scale: [0.8, 0.8, 0.8]

  - id: plant_medium
    label: Medium Plant
    model: plant
    scale: [0.6, 0.9, 0.6]

  - id: whiteboard_large
    label: Large Whiteboard
    model: whiteboard
    scale: [2, 1.5, 0.1]
`,
};

// The Explorer mirrors the SAMS workspace tree (spec 7.2) and lists live agents.
export function Explorer() {
  const agents = useStore((s) => s.agents);
  const select = useStore((s) => s.select);
  const setOpenFile = useStore((s) => s.setOpenFile);
  const list = Object.values(agents).sort((a, b) => a.name.localeCompare(b.name));

  function openWorkspace(name: string) {
    const content = WORKSPACE_CONTENT[name];
    if (content !== undefined) {
      setOpenFile({ path: `sams-workspace/${name}`, content });
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">Explorer</div>
      <div className="panel-scroll">
        <div className="tree-group">SKILLS · drag into the room</div>
        <SkillPalette />

        <div className="tree-group" style={{ marginTop: 8 }}>FILES · projects</div>
        <FileTree root="~/Desktop/Developer" rootName="Developer" />
        <FileTree root="~/Desktop/Work" rootName="Work" />
        <FileTree root="~/Desktop/Business" rootName="Business" />

        <div className="tree-group" style={{ marginTop: 8 }}>SAMS-WORKSPACE</div>

        <Group label={`agents · ${list.length}`} defaultOpen={false}>
          {list.map((a) => (
            <div key={a.id} className="tree-item" onClick={() => select("agent", a.id)}>
              <span className="dot" style={{ background: a.color }} />
              <span>{a.name.toLowerCase()}</span>
              <span className="badge">{a.state[0].toUpperCase()}</span>
            </div>
          ))}
        </Group>

        <Group label="workflows">
          {["onboarding.flow", "code-review.flow", "deploy.flow"].map((f) => (
            <Leaf key={f} name={f} icon="flow" onClick={() => openWorkspace(f)} />
          ))}
        </Group>
        <Group label="environments">
          {["dev.env", "staging.env", "prod.env"].map((f) => <Leaf key={f} name={f} icon="env" />)}
        </Group>
        <Group label="assets">
          {["architecture.spatial", "office-layout.spatial", "furniture.spatial"].map((f) => (
            <Leaf key={f} name={f} icon="asset" onClick={() => openWorkspace(f)} />
          ))}
        </Group>
        <Group label="configs">
          {["sams.yaml", "agents.yaml", "permissions.yaml"].map((f) => <Leaf key={f} name={f} icon="cfg" />)}
        </Group>
        <Leaf name="README.md" icon="doc" />
        <Leaf name="CHANGELOG.md" icon="doc" />
      </div>
    </div>
  );
}

function Group({ label, children, defaultOpen = true }: { label: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <div
        className="tree-group"
        style={{ fontSize: 11, color: "var(--text-muted)", cursor: "pointer", userSelect: "none" }}
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ display: "inline-block", width: 12 }}>{open ? "▾" : "▸"}</span>
        {label}
      </div>
      {open && <div style={{ paddingLeft: 6 }}>{children}</div>}
    </div>
  );
}

function Leaf({ name, onClick }: { name: string; icon: string; onClick?: () => void }) {
  return (
    <div className="tree-item" onClick={onClick} style={onClick ? { cursor: "pointer" } : undefined}>
      <span style={{ width: 8 }} />
      <span className="mono" style={{ fontSize: 12 }}>{name}</span>
    </div>
  );
}
