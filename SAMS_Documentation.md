# SAMS — Spatial Agentic Management System
### Complete Product & Technical Documentation

> **"The Sims for managing AI agents."**
> A spatially-native platform for building, operating, and orchestrating fleets of autonomous AI agents inside a living, visual workspace.

---

| | |
|---|---|
| **Document** | SAMS Platform — Complete Documentation |
| **Product version** | 0.9.0 (Pre-1.0, "Spatial Mode") |
| **Document version** | 1.0 |
| **Status** | Living document — designed to be extended |
| **Audience** | Engineers, platform operators, agent authors, technical product owners |
| **Scope** | Product concepts, full system architecture, the complete agent catalog, the agent extensibility model, APIs, schemas, security, deployment |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Core Concepts](#2-core-concepts)
3. [System Architecture](#3-system-architecture)
4. [The Agent System](#4-the-agent-system)
5. [The Agent Catalog](#5-the-agent-catalog)
6. [Building & Extending Agents](#6-building--extending-agents)
7. [The Interface, Design System & Messaging](#7-the-spatial-interface)
8. [Workflows & Orchestration](#8-workflows--orchestration)
9. [Integrations](#9-integrations)
10. [Configuration Reference](#10-configuration-reference)
11. [API Reference](#11-api-reference)
12. [Security & Permissions](#12-security--permissions)
13. [Data Models & Schemas](#13-data-models--schemas)
14. [Deployment & Operations](#14-deployment--operations)
15. [CLI & Command Reference](#15-cli--command-reference)
16. [Observability](#16-observability)
17. [Roadmap & Versioning](#17-roadmap--versioning)
18. [Glossary](#18-glossary)
19. [Appendix](#19-appendix)

---

# 1. Introduction

## 1.1 What is SAMS?

**SAMS (Spatial Agentic Management System)** is a platform for orchestrating large numbers of autonomous AI agents. Instead of managing agents through opaque logs, config files, and disconnected dashboards, SAMS renders the entire agent fleet as a **living spatial workspace** — an isometric "office" in which each agent is a visible, addressable character that occupies space, holds tools, performs work at stations, and collaborates with other agents.

The platform combines three layers that are usually kept separate:

1. **An agent runtime** — spawns, schedules, and supervises autonomous agents backed by large language models.
2. **An orchestration engine** — coordinates multi-agent work via an event bus, task boards, and workflows.
3. **A spatial interface** — a real-time, game-like visualization where agents, work, code, and infrastructure are all represented as objects you can see and manipulate.

SAMS is **model-agnostic** (Claude, GPT, Gemini, local models), **tool-extensible** (via MCP and custom adapters), and **agent-extensible** (anyone can author and register new agents — see [Section 6](#6-building--extending-agents)).

## 1.2 The "Sims for AI Agents" philosophy

The defining metaphor of SAMS is borrowed deliberately from life-simulation games. The design rests on four principles:

- **Agents are characters, not processes.** Every agent has an identity, a color, a home station, a state (working, idle, blocked, reviewing), and a visible activity. This makes a fleet of 50 agents legible at a glance in a way that a wall of terminal output never can.
- **Work happens in places.** Functional capabilities are bound to **spatial primitives**: the Desk is the active compute workspace, the Vault is storage and memory, the Kanban Wall is the task board, the Whiteboard is for planning, the Security Gate is the approval/source-control checkpoint. Moving work between places *is* the operation.
- **The world is observable and traceable.** Everything an agent does emits an event. The room is a real-time projection of the underlying event stream. Nothing happens "off-screen."
- **Everything is hot-swappable.** Agents, tools, workflows, and even spatial layouts can be added, replaced, or removed at runtime without tearing down the world.

## 1.3 Who SAMS is for

| Persona | Why they use SAMS |
|---|---|
| **Solo builders / indie hackers** | Run a private fleet of agents that ship code, research, and content while staying in control of every step. |
| **Engineering teams** | Coordinate coding, review, QA, and deploy agents against a real repository with human approval gates. |
| **Creative & agency studios** | Manage multiple client deliverables in parallel — each "room" or workspace is a client, each agent a specialist. |
| **Platform / DevOps teams** | Operate agents as first-class infrastructure with observability, permissions, and audit trails. |
| **Agent authors** | Build, test, and publish reusable agents and capability packs to the registry. |

## 1.4 Key features at a glance

- **Spatial agent management** — isometric, real-time visualization of the entire fleet.
- **Large built-in agent catalog** — 40+ ready-to-use agents across engineering, research, design, product, data, QA, DevOps, security, and ops (see [Section 5](#5-the-agent-catalog)).
- **First-class extensibility** — a documented Agent SDK, manifest schema, lifecycle hooks, and a registry for custom agents.
- **Workflows** — declarative, multi-agent pipelines (onboarding, code review, deploy, custom).
- **Kanban-native task system** — bidirectionally synced with GitHub Projects and internal boards.
- **Security Gate** — human-in-the-loop approvals, source-control integration, and audit logging.
- **Vault** — versioned storage for codebases, artifacts, and long-term agent memory.
- **Event Bus** — the asynchronous backbone every component publishes to and subscribes from.
- **Model-agnostic providers** — swap the underlying LLM per agent.
- **Full observability** — terminal, event log, agent logs, problems, and a system overview minimap.

## 1.5 How to read this document

This document is **designed to be extended**. New agents, integrations, and workflows are expected to be appended over time. Wherever you see a **`▶ Extension point`** callout, that is a place explicitly intended for you to add your own definitions. The most important extension surfaces are:

- [Section 5](#5-the-agent-catalog) — add new agents to the catalog.
- [Section 6](#6-building--extending-agents) — the canonical guide for authoring agents.
- [Section 8](#8-workflows--orchestration) — add new multi-agent workflows.
- [Section 9](#9-integrations) — add new tool/provider integrations.

Throughout, **the reference implementation stack** (Python/asyncio orchestrator, TypeScript/React/Three.js spatial UI, Redis event bus, Postgres + Mongo + object storage) is described concretely so the system is buildable — but the concepts are implementation-independent.

---

# 2. Core Concepts

This section defines the vocabulary used everywhere else in the document. Read it once; the rest of the documentation assumes these terms.

## 2.1 Agent

An **agent** is an autonomous worker backed by a language model, given an identity, a role, a set of capabilities, a permission scope, and access to tools. An agent perceives events, reasons, takes actions, and emits events. Agents are the primary unit of work in SAMS.

Every agent has:

- **Identity** — a unique `agent_id`, a human name (e.g. `blue-agent`, `Opus`, `Hermes`), and a display color.
- **Role** — its primary function (e.g. *Backend Engineer*, *Researcher*, *Reviewer*).
- **Capabilities** — the discrete skills it can perform (see [4.4](#44-agent-capabilities--skills)).
- **Tools** — external functions it may call (filesystem, git, HTTP, MCP servers, etc.).
- **Memory** — short-term context window plus long-term memory in the Vault.
- **Permissions** — what it is allowed to read, write, and approve.
- **State** — its current lifecycle status (see [4.3](#43-agent-states)).
- **Home** — the spatial primitive it is bound to (e.g. a Desk).

## 2.2 The Spatial Workspace

The **spatial workspace** (a "space" or "room") is the isometric environment that contains agents and primitives. It is a real-time projection of system state, not a static diagram. A workspace has dimensions (width, depth, height), a grid, and a set of placed primitives.

A SAMS instance may contain **multiple spaces** (e.g. `main.space`, `labs.space`, `meeting.space`), each of which can represent a project, a client, a team, or an environment.

## 2.3 Primitives (spatial objects)

A **primitive** is a placeable object in the workspace that **binds a spatial location to a functional capability**. Primitives are how abstract operations become physical actions. The core primitive types:

| Primitive | Binds to | Purpose |
|---|---|---|
| **Desk** | Active workspace / compute | Where an agent does focused work; bound to a working directory. |
| **Vault** | Storage & memory | Encrypted, versioned codebase, artifacts, and long-term agent memory. |
| **Whiteboard** | Ideation / diagrams | Planning canvas, diagrams, PRDs, linked notes. |
| **Kanban Wall** | Task board | Work items as cards across columns; synced with GitHub Projects. |
| **Security Gate** | Source control / approvals | Approval checkpoint; nothing merges or deploys without passing through. |
| **Lounge** | Idle pool | Where idle agents wait to be assigned work. |
| **Event Stream** | Live events | A visible feed of the event bus. |
| **Terminal** | Command surface | Shell access, logs, and command execution. |

Each primitive exposes **interaction points** (actions) and **metadata** (tags, bindings), and can be **coupled** to other primitives via channels (e.g. `Whiteboard.data → Desk /work/boards`).

## 2.4 Rooms & Spaces

A **room** is a bounded region within a space, defined by a footprint on the grid (e.g. `12.0m × 10.0m`, grid size `0.5m`). Rooms group related primitives and agents. Spaces are saved as `.spatial` assets (`architecture.spatial`, `office-layout.spatial`, `furniture.spatial`) and are versioned like code.

## 2.5 Workflow

A **workflow** is a declarative, multi-step pipeline that coordinates one or more agents to achieve an outcome. Workflows are stored as files (`onboarding.flow`, `code-review.flow`, `deploy.flow`) and have triggers, steps, agent assignments, gates, and outputs. See [Section 8](#8-workflows--orchestration).

## 2.6 Environment

An **environment** is a named runtime target (`dev.env`, `staging.env`, `prod.env`) with its own configuration, secrets, and permission posture. Workflows and deploys are environment-scoped.

## 2.7 The Event Bus

The **Event Bus** is the asynchronous messaging backbone of SAMS. Every meaningful change — an agent starting, a file changing, a card moving, a diagram updating — is published as an **event**. Components subscribe to the events they care about. The spatial UI, the logs, and the orchestrator are all just subscribers. This is what makes the system observable and loosely coupled.

A canonical event:

```json
{
  "id": "evt_8f3a9c2d",
  "type": "kanban.card.moved",
  "ts": "2026-06-21T11:02:31Z",
  "actor": "blue-agent",
  "space": "main.space",
  "payload": {
    "card_id": "SAMS-201",
    "from": "To Do",
    "to": "In Progress"
  },
  "trace_id": "trc_19af..."
}
```

## 2.8 Glossary of core terms

| Term | One-line definition |
|---|---|
| **Agent** | Autonomous LLM-backed worker with identity, role, tools, and permissions. |
| **Orchestrator** | The component that schedules agents and coordinates workflows. |
| **Primitive** | A spatial object that binds a place to a capability. |
| **Space / Room** | The isometric workspace (and bounded regions within it). |
| **Vault** | Versioned storage and long-term memory. |
| **Security Gate** | Human-in-the-loop approval and source-control checkpoint. |
| **Workflow** | Declarative multi-agent pipeline. |
| **Capability** | A discrete skill an agent can perform. |
| **Tool** | An external function an agent can call. |
| **Event** | An immutable record of something that happened, published to the bus. |
| **Manifest** | The declarative definition of an agent (see [6.2](#62-defining-a-custom-agent)). |
| **Registry** | The catalog of installable agents and capability packs. |

---

# 3. System Architecture

## 3.1 High-level architecture

SAMS is composed of seven subsystems communicating over the Event Bus. No subsystem calls another directly for state changes; they publish and subscribe.

```
                         ┌──────────────────────────────┐
                         │      Spatial UI (client)      │
                         │  React + Three.js, WebSocket  │
                         └───────────────┬──────────────┘
                                         │  (WS: events in/out)
                                         ▼
┌──────────────┐   events   ┌────────────────────────┐   events   ┌──────────────┐
│ Integrations │◄──────────►│        EVENT BUS        │◄──────────►│ Observability│
│  (GitHub,    │            │   (Redis Streams/NATS)  │            │  (logs,      │
│  MCP, LLM    │            └─────────┬──────────────┘            │  metrics)    │
│  providers)  │                      │                            └──────────────┘
└──────┬───────┘                      │
       │                              ▼
       │              ┌──────────────────────────────┐
       │              │         ORCHESTRATOR          │
       │              │  scheduling, workflows,       │
       │              │  task assignment, gates       │
       │              └───────┬───────────────┬──────┘
       │                      │               │
       ▼                      ▼               ▼
┌──────────────┐    ┌──────────────────┐   ┌──────────────────┐
│   AGENT      │    │   SPATIAL ENGINE  │   │      VAULT       │
│   RUNTIME    │    │  rooms, primitives│   │  code, artifacts,│
│  (workers,   │    │  bindings, layout │   │  long-term memory│
│  LLM calls)  │    └──────────────────┘   │  (Postgres/Mongo/│
└──────────────┘                            │   object store)  │
                                            └──────────────────┘
```

## 3.2 The Orchestrator

The **Orchestrator** is the brain of coordination. It does **not** do the agents' work; it decides *who* does *what*, *when*, and *in what order*. Responsibilities:

- **Scheduling** — decides which queued tasks are assigned to which idle agents based on role, capability, load, and priority.
- **Workflow execution** — drives multi-step `.flow` definitions, advancing steps as their preconditions are met.
- **Gating** — pauses work that requires human approval at a Security Gate.
- **Backpressure** — throttles spawning when resource limits (LLM rate limits, concurrency caps) are hit.
- **Recovery** — restarts or reassigns work from crashed or stuck agents.

Reference signature:

```python
from core.event_bus import EventBus
from core.agents.orchestrator import Orchestrator
from core.config import settings

event_bus = EventBus()
orchestrator = Orchestrator(event_bus)

async def main():
    await orchestrator.initialize()
    try:
        await orchestrator.start()
    except Exception as e:
        await event_bus.emit("system.error", {"error": str(e), "fatal": True})
        raise
```

## 3.3 The Event Bus

The Event Bus provides **publish/subscribe** with **durable streams** and **consumer groups**. Key guarantees and properties:

- **At-least-once delivery** with idempotency keys on consumers.
- **Ordered per-stream** (e.g. per-space or per-agent ordering where required).
- **Replayable** — streams are retained so the spatial UI and audit log can be reconstructed.
- **Typed topics** — `agent.*`, `kanban.*`, `vault.*`, `flow.*`, `security.*`, `system.*`, `spatial.*`.

Reference implementation: **Redis Streams** for the MVP (simple, durable, replayable); **NATS JetStream** as a scale-out option.

## 3.4 The Agent Runtime

The **Agent Runtime** is the execution sandbox where agents actually run. Each running agent is a supervised worker (a Celery task / asyncio task / container, depending on isolation level) that:

1. Pulls its assignment and context.
2. Loads its system prompt, capabilities, and tool bindings.
3. Calls its configured LLM provider (Claude / GPT / Gemini / local).
4. Executes tool calls within its permission scope.
5. Streams progress and results back to the Event Bus.

Isolation levels (configurable per agent):

| Level | Mechanism | Use case |
|---|---|---|
| **Light** | asyncio task in shared process | Trusted, read-only agents. |
| **Standard** | Celery worker process | Default; most agents. |
| **Hard** | Container (Docker/Firecracker) | Agents that execute untrusted code or shell. |

## 3.5 The Spatial Engine

The **Spatial Engine** owns the world model: rooms, grid, primitives, placements, bindings, and couplings. It translates between **functional state** (a card moved, a file changed) and **spatial representation** (an agent walking to the Kanban Wall, a glow on the Vault). It exposes:

- A **scene graph** consumed by the client renderer.
- **Spatial commands** (`agent:new`, `grid:resize`, `spatial:add`, `bind:directory`, `grid:snap`).
- **Binding resolution** — e.g. binding directory `/work` to `Desk 01` so file events render at that desk.

## 3.6 The Vault (storage & memory)

The **Vault** is the system of record. It stores three classes of data:

- **Codebase** — the working repository (files, modules), versioned. (Image reference: "5,412 files · 182 modules · 24 agents linked".)
- **Artifacts** — build outputs, generated documents, designs, datasets.
- **Long-term memory** — embeddings and structured memories that agents retrieve via RAG.

Reference storage split:

| Data | Store |
|---|---|
| Relational state (agents, tasks, workflows, runs) | PostgreSQL |
| Document/agent memory (notes, transcripts, scratchpads) | MongoDB |
| Vector memory (embeddings for retrieval) | pgvector / Qdrant |
| Binary artifacts (files, builds, media) | Object storage (S3-compatible) |

## 3.7 Integrations layer

The **Integrations layer** adapts external systems into Event Bus events and tool calls. Built-in adapters: **LLM providers**, **GitHub/version control**, **MCP servers**, and **webhooks**. See [Section 9](#9-integrations).

## 3.8 Data flow

The canonical data flow for "an agent does work":

```
Agents → Orchestrator → Event Bus → Integrations
   ▲                                      │
   │            Vault ◄── Memory ◄── Tools ┘
```

1. The Orchestrator assigns a task and emits `flow.step.started`.
2. The Agent Runtime loads context from the Vault and the task.
3. The agent calls its LLM and tools; each action emits events.
4. Results are written back to the Vault; the Security Gate may pause for approval.
5. The Spatial Engine renders every step in real time.

## 3.9 Technology stack (reference implementation)

| Layer | Technology |
|---|---|
| Orchestrator & runtime | Python 3.11+, asyncio, Celery, Redis |
| Event Bus | Redis Streams (MVP) → NATS JetStream (scale) |
| Persistence | PostgreSQL, MongoDB, pgvector/Qdrant, S3-compatible object store |
| Spatial UI | TypeScript, React, React-Three-Fiber / Three.js |
| Real-time transport | WebSocket (client ↔ server), SSE for one-way streams |
| LLM providers | Anthropic (Claude), OpenAI (GPT), Google (Gemini), local (Ollama/vLLM) |
| Tooling protocol | MCP (Model Context Protocol) + native tool adapters |
| Config | YAML (`sams.yaml`, `agents.yaml`, `permissions.yaml`) |
| Packaging | `pyproject.toml`, container images per environment |

> **Note:** SAMS is intentionally **observable, traceable, and hot-swappable** at every layer. Any component can be replaced as long as it speaks the Event Bus contract.

---

# 4. The Agent System

This section describes how a single agent is structured and behaves. [Section 5](#5-the-agent-catalog) then lists the agents that ship with SAMS, and [Section 6](#6-building--extending-agents) explains how to author your own.

## 4.1 Anatomy of an agent

```
┌─────────────────────────── AGENT ───────────────────────────┐
│  Identity        agent_id, name, color, avatar               │
│  Role            primary function + seniority                │
│  System prompt   persona, objectives, constraints            │
│  Model binding   provider, model, params (temperature, etc.) │
│  Capabilities    [capability_id, ...]                        │
│  Tools           [tool_id, ...] within permission scope      │
│  Memory          context window + Vault namespace            │
│  Permissions     read / write / approve scopes               │
│  Lifecycle hooks on_spawn, on_assign, on_complete, on_error  │
│  Home            bound primitive (e.g. Desk 01)              │
│  Telemetry       state, progress, current file, context use  │
└──────────────────────────────────────────────────────────────┘
```

## 4.2 Agent lifecycle

```
 spawn ──► initialize ──► idle ──► assigned ──► working ──► (gate?) ──► complete ──► idle
   │            │                                  │            │
   │            └── on_spawn hook                  │            └── on awaiting approval → blocked
   │                                               └── on_error hook → recover / reassign
   └── despawn (graceful drain) ◄──────────────────────────────────────────────────────
```

1. **Spawn** — the Orchestrator (or a human via `agent:new`) instantiates the agent from its manifest.
2. **Initialize** — load system prompt, capabilities, tools, memory namespace; run `on_spawn`.
3. **Idle** — the agent waits in the Lounge for assignment.
4. **Assigned** — a task is bound; `on_assign` runs; context is loaded from the Vault.
5. **Working** — the agent reasons and acts, emitting events.
6. **Gate (optional)** — if the task requires approval, the agent enters **blocked** at the Security Gate.
7. **Complete** — results are committed; `on_complete` runs; the agent returns to idle.
8. **Despawn** — graceful drain on shutdown or scale-down.

## 4.3 Agent states

| State | Meaning | Spatial cue |
|---|---|---|
| `initializing` | Loading manifest and context | Agent fading in at home |
| `idle` | Waiting for work | Standing in the Lounge |
| `assigned` | Task bound, not yet started | Walking to a station |
| `working` | Actively reasoning/acting | At Desk, animated, progress bar |
| `reviewing` | Reviewing another agent's output | At the Security Gate / Whiteboard |
| `blocked` | Awaiting approval or dependency | Paused, amber indicator |
| `error` | Failed; awaiting recovery | Red indicator |
| `complete` | Finished current task | Green check, returning to idle |
| `paused` | Manually suspended | Greyed out |

## 4.4 Agent capabilities & skills

A **capability** is a declared, discrete skill. Capabilities are how the Orchestrator matches tasks to agents and how permissions are scoped. Capabilities are namespaced:

```
code.write          code.review         code.refactor
research.web        research.summarize  research.cite
design.wireframe    design.diagram      design.critique
data.query          data.transform      data.visualize
qa.test.generate    qa.test.run         qa.bug.triage
ops.deploy          ops.monitor         ops.rollback
security.audit      security.secrets    security.approve
content.write       content.edit        content.localize
plan.spec           plan.breakdown      plan.estimate
```

Each capability has a **contract**: expected inputs, outputs, side effects, and required tools. Agents declare the capabilities they provide; capability packs can be installed to extend any agent (see [6.3](#63-capability-packs)).

## 4.5 Agent memory & context window

Agents have a two-tier memory model:

- **Short-term (context window)** — the live LLM context. Telemetry surfaces usage (e.g. "Context_Window: 48% / 200k"). The runtime manages compaction and summarization as the window fills.
- **Long-term (Vault memory)** — durable, retrievable memory stored per-agent and per-space. Backed by a vector store for semantic recall plus structured records for facts and decisions.

Memory scopes:

| Scope | Visible to | Use |
|---|---|---|
| `private` | Single agent | Scratchpad, working notes. |
| `space` | All agents in the space | Shared project knowledge. |
| `global` | All agents | Org-wide standards, conventions. |

## 4.6 Inter-agent communication

Agents do not call each other directly. They communicate through three channels, all on the Event Bus:

1. **Tasks** — the Orchestrator hands work between agents (e.g. a coder finishes → a reviewer is assigned).
2. **Shared primitives** — e.g. the Whiteboard or a Kanban card is a shared artifact multiple agents read/write.
3. **Mentions & messages** — agents can address a message to another agent or a human (`agent.message`), which the Orchestrator routes.

Example agent log (from the reference UI):

```
10:48:21  blue-agent     [INFO]     Loaded work items from Kanban Wall: WORK_ITEMS
10:48:22  green-agent    [SUCCESS]  Synced 24 cards across 4 columns
10:48:23  orange-agent   [INFO]     Review queue: 3 items waiting
10:48:24  purple-agent   [WARN]     Card #128 blocked: awaiting review
10:48:25  yellow-agent   [SUCCESS]  Column mapping validated
10:48:26  red-agent      [IDLE]     No active tasks
```

## 4.7 Agent permissions & roles

Permissions are declared per agent and enforced by the runtime and the Security Gate. The model is **deny-by-default**.

```yaml
# excerpt from an agent definition
permissions:
  read:
    - "vault://src/**"
    - "kanban://main.space/*"
  write:
    - "vault://src/feature-*/**"   # only feature branches
  approve: false                    # cannot self-approve merges
  tools:
    - git.commit
    - git.push
    - fs.read
    - fs.write
  environments:
    - dev
    - staging                       # not prod
```

Roles bundle a default permission posture (e.g. *Reviewer* can `approve`, *Junior Engineer* cannot push to `main`). See [Section 12](#12-security--permissions).

## 4.8 Agent telemetry

Every agent continuously reports telemetry consumed by the spatial UI and observability stack:

| Field | Example |
|---|---|
| `state` | `working` |
| `current_task` | `Build real-time agent activity engine` |
| `current_file` | `src/main.py (Line 87)` |
| `branch` | `feature/agent-activity-engine` |
| `progress` | `72%` |
| `context_window` | `48% / 200k` |
| `model` | `claude-opus-4` |
| `tokens_in / tokens_out` | `18,402 / 6,110` |

---

# 5. The Agent Catalog

SAMS ships with a broad catalog of ready-to-use agents so that common work is covered out of the box. This section is also the **primary extension surface**: adding a new agent means adding an entry here plus a manifest (see [Section 6](#6-building--extending-agents)).

## 5.1 How to read an agent profile

Each agent is documented with a consistent profile:

| Field | Meaning |
|---|---|
| **Codename** | The agent's name and color in the workspace. |
| **Role / Seniority** | Primary function and level (affects permissions). |
| **Capabilities** | Declared skills (see [4.4](#44-agent-capabilities--skills)). |
| **Tools** | External functions it may call. |
| **Default model** | The LLM binding (overridable per instance). |
| **Home** | The spatial primitive it lives at. |
| **Typical tasks** | Representative work it performs. |
| **Collaborates with** | Agents it commonly hands work to/from. |

### Color & naming convention

The six **core color agents** (`blue`, `green`, `orange`, `purple`, `red`, `yellow`) are the default generalist fleet seen in the reference UI. **Named agents** (e.g. `Opus`, `Hermes`, `Atlas`) are specialists. Custom agents should pick an unused color or a distinct name and a unique `agent_id`.

> **▶ Extension point:** To add an agent, copy any profile below, change the fields, and register a manifest. Keep `agent_id` globally unique and `capabilities` accurate — the Orchestrator routes tasks by capability.

---

## 5.2 Core / Orchestration agents

These agents run the system itself rather than producing deliverables.

### Atlas — Orchestrator Agent `slate`
- **Role / Seniority:** Lead Orchestrator / Principal
- **Capabilities:** `plan.breakdown`, `flow.execute`, `agent.assign`, `agent.supervise`
- **Tools:** `orchestrator.schedule`, `eventbus.emit`, `kanban.write`
- **Default model:** Claude Opus (high reasoning)
- **Home:** System (no desk; oversees the room)
- **Typical tasks:** Decompose goals into tasks, assign agents, drive workflows, handle backpressure and recovery.
- **Collaborates with:** Every agent.

### Sentinel — Supervisor Agent `graphite`
- **Role / Seniority:** Reliability Supervisor / Senior
- **Capabilities:** `agent.supervise`, `ops.monitor`, `agent.recover`
- **Tools:** `eventbus.subscribe`, `runtime.restart`, `alert.raise`
- **Default model:** Claude Sonnet (fast, cheap monitoring)
- **Home:** System Overview (minimap)
- **Typical tasks:** Detect stuck/crashed agents, restart or reassign, enforce concurrency caps.
- **Collaborates with:** Atlas, Watchtower.

### Concierge — Onboarding Agent `mint`
- **Role / Seniority:** Onboarding / Mid
- **Capabilities:** `plan.spec`, `agent.assign`, `content.write`
- **Tools:** `kanban.write`, `vault.read`, `flow.start`
- **Default model:** Claude Sonnet
- **Home:** Lounge
- **Typical tasks:** Run the `onboarding.flow` when a new project/space is created; set up boards, environments, and initial tasks.
- **Collaborates with:** Atlas, Scribe.

---

## 5.3 Engineering agents

The core software-building fleet. This maps to the `blue/green/red` agents and named specialists in the reference UI.

### Opus — Senior Backend Engineer `blue`
- **Role / Seniority:** Backend Engineer / Senior
- **Capabilities:** `code.write`, `code.refactor`, `code.review`, `plan.breakdown`
- **Tools:** `fs.read`, `fs.write`, `git.commit`, `git.push`, `shell.run`, `mcp.*`
- **Default model:** Claude Opus
- **Home:** Desk 01 (Active Compute)
- **Typical tasks:** Implement services and APIs, build the event system, refactor the orchestrator, write tests.
- **Collaborates with:** Hex (review), Probe (QA), Forge (DevOps).
- **Reference telemetry:** `Current_File: main.py (Line 87)`, `feature/audit-logging`, `Status: Awaiting Review`.

### Pixel — Frontend Engineer `green`
- **Role / Seniority:** Frontend Engineer / Mid
- **Capabilities:** `code.write`, `design.wireframe`, `code.review`
- **Tools:** `fs.read`, `fs.write`, `git.commit`, `browser.preview`
- **Default model:** Claude Sonnet
- **Home:** Desk 02
- **Typical tasks:** Build UI components, spatial grid resizing, minimap, polish.
- **Collaborates with:** Muse (design), Opus (API contracts).

### Hex — Code Reviewer `red`
- **Role / Seniority:** Reviewer / Senior
- **Capabilities:** `code.review`, `security.audit`, `qa.bug.triage`
- **Tools:** `git.diff`, `vault.read`, `gate.comment`, `gate.request_changes`
- **Default model:** Claude Opus
- **Home:** Security Gate
- **Typical tasks:** Review pull requests, request changes, enforce standards before merge.
- **Collaborates with:** Opus, Pixel, Aegis (security).
- **Permissions:** `approve: true` (one of the few agents allowed to approve).

### Nova — Full-stack Engineer `purple`
- **Role / Seniority:** Full-stack / Mid
- **Capabilities:** `code.write`, `code.refactor`, `data.query`
- **Tools:** `fs.*`, `git.*`, `db.query`
- **Default model:** Claude Sonnet
- **Home:** Desk 03
- **Typical tasks:** Cross-cutting features touching both frontend and backend; integrations glue.
- **Collaborates with:** Opus, Pixel, Conduit.

### Rune — Refactoring Specialist `orange`
- **Role / Seniority:** Refactoring / Senior
- **Capabilities:** `code.refactor`, `code.review`, `qa.test.generate`
- **Tools:** `fs.*`, `git.*`, `ast.analyze`
- **Default model:** Claude Opus
- **Home:** Desk 04
- **Typical tasks:** Large refactors (e.g. "Refactor Orchestrator"), dependency upgrades, dead-code removal.
- **Collaborates with:** Hex, Probe.

### Conduit — Integration Engineer `yellow`
- **Role / Seniority:** Integrations / Mid
- **Capabilities:** `code.write`, `ops.deploy`, `data.transform`
- **Tools:** `http.request`, `mcp.connect`, `webhook.register`, `git.*`
- **Default model:** Claude Sonnet
- **Home:** Desk 05
- **Typical tasks:** Build and maintain external integrations (GitHub, MCP servers, third-party APIs).
- **Collaborates with:** Forge, Nova.

### Cipher — Systems / Performance Engineer `indigo`
- **Role / Seniority:** Performance / Senior
- **Capabilities:** `code.refactor`, `ops.monitor`, `data.visualize`
- **Tools:** `profiler.run`, `shell.run`, `metrics.query`
- **Default model:** Claude Opus
- **Home:** Desk 06
- **Typical tasks:** Profiling, optimizing hot paths, reducing context/token costs, load testing.
- **Collaborates with:** Forge, Watchtower.

---

## 5.4 Research & Knowledge agents

### Scribe — Research Agent `teal`
- **Role / Seniority:** Researcher / Senior
- **Capabilities:** `research.web`, `research.summarize`, `research.cite`
- **Tools:** `web.search`, `web.fetch`, `vault.write`, `cite.format`
- **Default model:** Claude Opus
- **Home:** Whiteboard
- **Typical tasks:** Gather sources, produce cited briefs, feed findings into planning.
- **Collaborates with:** Sage, Quill.

### Sage — Knowledge / RAG Agent `cyan`
- **Role / Seniority:** Knowledge Engineer / Mid
- **Capabilities:** `research.summarize`, `data.query`, `plan.spec`
- **Tools:** `vault.search`, `vector.query`, `memory.write`
- **Default model:** Claude Sonnet
- **Home:** Vault
- **Typical tasks:** Maintain long-term memory, answer cross-project questions, build internal knowledge bases.
- **Collaborates with:** Scribe, every agent (as a memory service).

### Beacon — Competitive / Market Analyst `amber`
- **Role / Seniority:** Analyst / Mid
- **Capabilities:** `research.web`, `data.visualize`, `content.write`
- **Tools:** `web.search`, `web.fetch`, `chart.render`
- **Default model:** Claude Sonnet
- **Home:** Whiteboard
- **Typical tasks:** Market scans, competitor tracking, trend reports.
- **Collaborates with:** Scribe, Quill.

---

## 5.5 Design & Creative agents

### Muse — Product Designer `rose`
- **Role / Seniority:** Designer / Senior
- **Capabilities:** `design.wireframe`, `design.diagram`, `design.critique`
- **Tools:** `whiteboard.write`, `canvas.draw`, `image.generate`
- **Default model:** Claude Opus (multimodal)
- **Home:** Whiteboard
- **Typical tasks:** Wireframes, user flows (e.g. "Authentication Flow Improvements"), design critique.
- **Collaborates with:** Pixel, Hermes.

### Hermes — Creative Studio Agent `violet`
- **Role / Seniority:** Creative Lead / Senior
- **Capabilities:** `content.write`, `design.diagram`, `content.localize`
- **Tools:** `canvas.draw`, `image.generate`, `doc.write`
- **Default model:** Claude Opus
- **Home:** Whiteboard (own studio room)
- **Typical tasks:** Manage multiple client deliverables in parallel — moodboards, landing pages, content sets.
- **Collaborates with:** Muse, Quill, Pixel.
- **Note:** Seen branded in the "creative studio" reference video.

### Palette — Visual / Brand Agent `coral`
- **Role / Seniority:** Visual Designer / Mid
- **Capabilities:** `design.critique`, `design.wireframe`
- **Tools:** `image.generate`, `canvas.draw`, `color.extract`
- **Default model:** Claude Sonnet (multimodal)
- **Home:** Whiteboard
- **Typical tasks:** Brand systems, color/typography, asset generation.
- **Collaborates with:** Hermes, Muse.

---

## 5.6 Product & Planning agents

### Compass — Product Manager `sky`
- **Role / Seniority:** Product Manager / Senior
- **Capabilities:** `plan.spec`, `plan.breakdown`, `plan.estimate`
- **Tools:** `kanban.write`, `doc.write`, `whiteboard.read`
- **Default model:** Claude Opus
- **Home:** Whiteboard
- **Typical tasks:** Turn ideas into PRDs ("Convert to PRD"), break specs into Kanban tasks, prioritize.
- **Collaborates with:** Atlas, Muse, Opus.

### Tally — Estimator / Planner `lime`
- **Role / Seniority:** Delivery Planner / Mid
- **Capabilities:** `plan.estimate`, `plan.breakdown`, `data.visualize`
- **Tools:** `kanban.read`, `chart.render`
- **Default model:** Claude Sonnet
- **Home:** Kanban Wall
- **Typical tasks:** Estimate effort, build milestones (e.g. `v0.2.0`), track burndown.
- **Collaborates with:** Compass, Atlas.

### Quill — Technical Writer `fuchsia`
- **Role / Seniority:** Writer / Mid
- **Capabilities:** `content.write`, `content.edit`, `research.summarize`
- **Tools:** `doc.write`, `vault.read`, `md.render`
- **Default model:** Claude Sonnet
- **Home:** Desk (docs)
- **Typical tasks:** READMEs, API docs, changelogs, this kind of documentation.
- **Collaborates with:** Opus, Compass, Scribe.

---

## 5.7 Data & Analytics agents

### Ledger — Data Engineer `bronze`
- **Role / Seniority:** Data Engineer / Senior
- **Capabilities:** `data.query`, `data.transform`, `code.write`
- **Tools:** `db.query`, `etl.run`, `fs.*`
- **Default model:** Claude Sonnet
- **Home:** Desk (data)
- **Typical tasks:** Pipelines, schema design, data ingestion (e.g. large JSON/CSV conversions).
- **Collaborates with:** Prism, Nova.

### Prism — Analytics / Visualization Agent `aqua`
- **Role / Seniority:** Analyst / Mid
- **Capabilities:** `data.visualize`, `data.query`, `research.summarize`
- **Tools:** `chart.render`, `db.query`, `notebook.run`
- **Default model:** Claude Sonnet
- **Home:** Whiteboard
- **Typical tasks:** Dashboards, metrics, ad-hoc analysis, reports.
- **Collaborates with:** Ledger, Beacon, Compass.

### Oracle — ML / Model Agent `plum`
- **Role / Seniority:** ML Engineer / Senior
- **Capabilities:** `data.transform`, `code.write`, `ops.deploy`
- **Tools:** `notebook.run`, `model.train`, `model.eval`
- **Default model:** Claude Opus
- **Home:** `labs.space`
- **Typical tasks:** Train/evaluate models, build embeddings, run experiments.
- **Collaborates with:** Ledger, Cipher.

---

## 5.8 QA & Testing agents

### Probe — QA Engineer `seafoam`
- **Role / Seniority:** QA Engineer / Mid
- **Capabilities:** `qa.test.generate`, `qa.test.run`, `qa.bug.triage`
- **Tools:** `test.generate`, `test.run`, `shell.run`, `kanban.write`
- **Default model:** Claude Sonnet
- **Home:** Desk (QA)
- **Typical tasks:** Write and run test suites, file bugs, gate releases on coverage.
- **Collaborates with:** Opus, Hex, Forge.

### Gauntlet — Adversarial / Fuzz Agent `crimson`
- **Role / Seniority:** Test Engineer / Senior
- **Capabilities:** `qa.test.run`, `security.audit`, `qa.bug.triage`
- **Tools:** `fuzz.run`, `shell.run`, `report.write`
- **Default model:** Claude Opus
- **Home:** `labs.space`
- **Typical tasks:** Fuzzing, edge-case discovery, breaking things on purpose before users do.
- **Collaborates with:** Probe, Aegis.

---

## 5.9 DevOps & Infrastructure agents

### Forge — DevOps Engineer `steel`
- **Role / Seniority:** DevOps / Senior
- **Capabilities:** `ops.deploy`, `ops.monitor`, `ops.rollback`, `code.write`
- **Tools:** `ci.trigger`, `deploy.run`, `infra.apply`, `shell.run`
- **Default model:** Claude Sonnet
- **Home:** Security Gate (deploy side)
- **Typical tasks:** CI/CD, run `deploy.flow`, manage `dev/staging/prod` environments, rollbacks.
- **Collaborates with:** Hex, Watchtower, Conduit.

### Watchtower — SRE / Monitoring Agent `olive`
- **Role / Seniority:** SRE / Senior
- **Capabilities:** `ops.monitor`, `ops.rollback`, `data.visualize`
- **Tools:** `metrics.query`, `alert.raise`, `incident.open`
- **Default model:** Claude Sonnet
- **Home:** System Overview
- **Typical tasks:** Watch health, raise alerts, drive incident response, propose rollbacks.
- **Collaborates with:** Sentinel, Forge.

### Tinker — Build / Tooling Agent `tan`
- **Role / Seniority:** Build Engineer / Mid
- **Capabilities:** `code.write`, `ops.deploy`, `code.refactor`
- **Tools:** `build.run`, `package.publish`, `fs.*`
- **Default model:** Claude Sonnet
- **Home:** Desk (build)
- **Typical tasks:** Build scripts, packaging, developer tooling, dependency hygiene.
- **Collaborates with:** Forge, Rune.

---

## 5.10 Security & Compliance agents

### Aegis — Security Engineer `forest`
- **Role / Seniority:** Security / Senior
- **Capabilities:** `security.audit`, `security.secrets`, `security.approve`
- **Tools:** `sast.scan`, `secrets.scan`, `gate.approve`, `gate.request_changes`
- **Default model:** Claude Opus
- **Home:** Security Gate
- **Typical tasks:** Security reviews, secret-leak detection, threat modeling, audit-logging enforcement.
- **Collaborates with:** Hex, Forge, Warden.
- **Permissions:** `approve: true` for security-gated changes.

### Warden — Compliance / Audit Agent `charcoal`
- **Role / Seniority:** Compliance / Mid
- **Capabilities:** `security.audit`, `content.write`, `data.query`
- **Tools:** `audit.read`, `report.write`, `policy.check`
- **Default model:** Claude Sonnet
- **Home:** Vault (audit)
- **Typical tasks:** Maintain audit trails, produce compliance reports, enforce policy.
- **Collaborates with:** Aegis, Warden.

---

## 5.11 Communication & Operations agents

### Echo — Communications Agent `periwinkle`
- **Role / Seniority:** Comms / Mid
- **Capabilities:** `content.write`, `content.localize`, `research.summarize`
- **Tools:** `email.draft`, `chat.post`, `doc.write`
- **Default model:** Claude Sonnet
- **Home:** Lounge
- **Typical tasks:** Status updates, release notes, stakeholder summaries, notifications (drafts only — sending is human-approved).
- **Collaborates with:** Quill, Compass.

### Relay — Support / Triage Agent `apricot`
- **Role / Seniority:** Support / Mid
- **Capabilities:** `qa.bug.triage`, `content.write`, `research.summarize`
- **Tools:** `ticket.read`, `kanban.write`, `chat.post`
- **Default model:** Claude Sonnet
- **Home:** Lounge
- **Typical tasks:** Triage incoming issues, draft responses, route to the right agent.
- **Collaborates with:** Probe, Relay, Echo.

---

## 5.12 Content & Marketing agents

### Quote — Copywriter `magenta`
- **Role / Seniority:** Copywriter / Mid
- **Capabilities:** `content.write`, `content.edit`, `content.localize`
- **Tools:** `doc.write`, `image.generate`
- **Default model:** Claude Sonnet
- **Home:** Whiteboard (content)
- **Typical tasks:** Marketing copy, scripts, captions, multi-language content sets.
- **Collaborates with:** Hermes, Palette, Echo.

### Spotlight — Social / Campaign Agent `gold`
- **Role / Seniority:** Marketer / Mid
- **Capabilities:** `content.write`, `data.visualize`, `research.web`
- **Tools:** `schedule.post`, `analytics.read`, `chart.render`
- **Default model:** Claude Sonnet
- **Home:** Whiteboard (campaigns)
- **Typical tasks:** Plan campaigns, schedule content (human-approved), track performance.
- **Collaborates with:** Quote, Beacon.

---

## 5.13 Specialized / Utility agents

### Janitor — Cleanup Agent `ash`
- **Role / Seniority:** Maintenance / Junior
- **Capabilities:** `code.refactor`, `data.transform`
- **Tools:** `fs.*`, `vault.gc`, `cache.clear`
- **Default model:** Claude Haiku (cheap, high-volume)
- **Home:** moves between stations
- **Typical tasks:** Remove stale branches/artifacts, tidy the Vault, garbage-collect memory.
- **Collaborates with:** Tinker, Sage.

### Courier — File / Asset Agent `slate-blue`
- **Role / Seniority:** Utility / Junior
- **Capabilities:** `data.transform`, `data.query`
- **Tools:** `fs.*`, `object.upload`, `convert.run`
- **Default model:** Claude Haiku
- **Home:** Vault
- **Typical tasks:** Move/convert files, manage artifacts, format conversions.
- **Collaborates with:** Ledger, Courier.

### Linguist — Localization Agent `turquoise`
- **Role / Seniority:** Localization / Mid
- **Capabilities:** `content.localize`, `content.edit`
- **Tools:** `i18n.extract`, `translate.run`, `doc.write`
- **Default model:** Claude Sonnet
- **Home:** Desk (i18n)
- **Typical tasks:** Translate and localize UI/content (e.g. bilingual HU/EN), manage i18n keys.
- **Collaborates with:** Quote, Pixel.

---

## 5.14 Catalog summary

| Agent | Color | Category | Approves? | Default model |
|---|---|---|---|---|
| Atlas | slate | Core | — | Opus |
| Sentinel | graphite | Core | — | Sonnet |
| Concierge | mint | Core | — | Sonnet |
| Opus | blue | Engineering | — | Opus |
| Pixel | green | Engineering | — | Sonnet |
| Hex | red | Engineering | ✅ | Opus |
| Nova | purple | Engineering | — | Sonnet |
| Rune | orange | Engineering | — | Opus |
| Conduit | yellow | Engineering | — | Sonnet |
| Cipher | indigo | Engineering | — | Opus |
| Scribe | teal | Research | — | Opus |
| Sage | cyan | Research | — | Sonnet |
| Beacon | amber | Research | — | Sonnet |
| Muse | rose | Design | — | Opus |
| Hermes | violet | Design | — | Opus |
| Palette | coral | Design | — | Sonnet |
| Compass | sky | Product | — | Opus |
| Tally | lime | Product | — | Sonnet |
| Quill | fuchsia | Product | — | Sonnet |
| Ledger | bronze | Data | — | Sonnet |
| Prism | aqua | Data | — | Sonnet |
| Oracle | plum | Data | — | Opus |
| Probe | seafoam | QA | — | Sonnet |
| Gauntlet | crimson | QA | — | Opus |
| Forge | steel | DevOps | — | Sonnet |
| Watchtower | olive | DevOps | — | Sonnet |
| Tinker | tan | DevOps | — | Sonnet |
| Aegis | forest | Security | ✅ | Opus |
| Warden | charcoal | Security | — | Sonnet |
| Echo | periwinkle | Comms | — | Sonnet |
| Relay | apricot | Comms | — | Sonnet |
| Quote | magenta | Content | — | Sonnet |
| Spotlight | gold | Content | — | Sonnet |
| Janitor | ash | Utility | — | Haiku |
| Courier | slate-blue | Utility | — | Haiku |
| Linguist | turquoise | Utility | — | Sonnet |

**36 built-in agents across 9 categories.** Only **Hex** and **Aegis** can approve gated changes by default — a deliberate separation-of-duties choice. Extend this table when you add agents.

---

# 6. Building & Extending Agents

This is the most important section for longevity. SAMS is built so that **adding new agents is a first-class, low-friction operation** — no core changes required. An agent is defined declaratively (a **manifest**) plus optionally a small amount of code (a **handler**). Register it, and the Orchestrator can route work to it immediately.

## 6.1 The Agent SDK

The Agent SDK provides the base classes, the manifest loader, the tool registry, and the lifecycle hook interface. Reference (Python):

```python
from sams.sdk import Agent, capability, hook, tool
```

There are two ways to author an agent:

1. **Declarative-only** — a YAML manifest that composes existing capabilities and tools. No code. Good for most agents.
2. **Code-backed** — a manifest plus a handler class that overrides behavior or adds custom capabilities.

## 6.2 Defining a custom agent

### The manifest schema

Every agent is defined by a manifest. This is the **complete, canonical schema**:

```yaml
# agents/custom/seo-agent.agent.yaml
apiVersion: sams/v1
kind: Agent

metadata:
  id: seo-agent                 # REQUIRED, globally unique, kebab-case
  name: Beacon-SEO              # display name
  color: "#2BC6A4"              # display color (unique recommended)
  avatar: robot                 # avatar set key
  version: 1.0.0                # semver
  authors: ["tamas"]
  tags: ["marketing", "seo", "content"]
  description: "Audits pages and proposes SEO improvements."

spec:
  role: SEO Specialist
  seniority: mid                # junior | mid | senior | principal

  model:
    provider: anthropic         # anthropic | openai | google | local
    name: claude-sonnet-4
    params:
      temperature: 0.4
      max_tokens: 4096

  systemPrompt: |
    You are an SEO specialist agent in SAMS. You audit web pages,
    identify on-page and technical SEO issues, and propose concrete,
    prioritized fixes. You never publish changes; you produce reports
    and tasks for human approval.

  # Capabilities this agent PROVIDES (routable by the Orchestrator)
  capabilities:
    - research.web
    - content.edit
    - data.visualize

  # Tools this agent may CALL (must be within permissions)
  tools:
    - web.fetch
    - web.search
    - doc.write
    - kanban.write

  permissions:
    read:
      - "vault://content/**"
      - "kanban://*/*"
    write:
      - "vault://content/seo-reports/**"
    approve: false
    environments: ["dev", "staging"]

  memory:
    scope: space                # private | space | global
    retention: 30d

  home:
    primitive: Whiteboard       # where it lives in the workspace
    room: marketing

  # Optional: declarative routing hints
  routing:
    priority: normal            # low | normal | high
    concurrency: 2              # max parallel instances
    triggers:
      - on: "kanban.card.labeled"
        when: "payload.label == 'seo'"

  # Optional: handler for code-backed behavior
  handler: agents/custom/seo_agent.py:SeoAgent
```

### The handler (code-backed, optional)

When you need custom logic or a brand-new capability, provide a handler:

```python
# agents/custom/seo_agent.py
from sams.sdk import Agent, capability, hook, tool

class SeoAgent(Agent):
    """Custom SEO agent with a bespoke capability."""

    @hook("on_spawn")
    async def setup(self, ctx):
        # Runs once when the agent is instantiated.
        ctx.log.info("SEO agent ready")
        self.ruleset = await ctx.vault.read("vault://content/seo-rules.yaml")

    @capability("content.seo_audit")            # a NEW capability
    async def seo_audit(self, ctx, url: str) -> dict:
        """Audit a page and return prioritized findings."""
        html = await self.tools.web_fetch(url)          # calls a registered tool
        findings = await self.think(                     # calls the bound LLM
            prompt=f"Audit this page against the ruleset:\n{html}",
            context=self.ruleset,
        )
        report_path = await self.tools.doc_write(
            path=f"vault://content/seo-reports/{ctx.slug(url)}.md",
            content=findings.markdown,
        )
        # Create follow-up tasks for humans/other agents
        for fix in findings.fixes:
            await self.tools.kanban_write(
                column="To Do", title=fix.title, labels=["seo"]
            )
        await ctx.emit("content.seo_audit.completed",
                       {"url": url, "report": report_path})
        return {"report": report_path, "issues": len(findings.fixes)}

    @hook("on_error")
    async def on_error(self, ctx, error):
        ctx.log.error(f"SEO audit failed: {error}")
        await ctx.emit("agent.error", {"agent": self.id, "error": str(error)})
```

## 6.3 Capability packs

A **capability pack** is a reusable bundle of capabilities (and their tools/prompts) that can be installed onto *any* compatible agent — so you can extend existing agents without rewriting them.

```yaml
# packs/accessibility-pack/pack.yaml
apiVersion: sams/v1
kind: CapabilityPack
metadata:
  id: accessibility-pack
  version: 1.2.0
spec:
  provides:
    - id: design.a11y_audit
      tools: [browser.preview, doc.write]
      prompt: packs/accessibility-pack/a11y_prompt.md
  appliesTo:
    roles: ["Designer", "Frontend Engineer"]
```

Install onto an agent:

```bash
sams pack install accessibility-pack --agent pixel
```

## 6.4 Lifecycle hooks

Hooks let your code run at defined points. All hooks are async and receive a context object.

| Hook | Fires when | Typical use |
|---|---|---|
| `on_spawn` | Agent instantiated | Load config, warm caches. |
| `on_assign` | A task is bound | Fetch task context from Vault. |
| `on_start` | Work begins | Announce, set up scratchpad. |
| `on_tool_call` | Before a tool runs | Validate args, enforce policy. |
| `on_progress` | Progress updates | Emit telemetry. |
| `on_complete` | Task finished | Commit results, clean up. |
| `on_gate` | Entering an approval gate | Prepare the review payload. |
| `on_error` | Failure | Recover, escalate, log. |
| `on_despawn` | Agent shutting down | Flush memory, release locks. |

## 6.5 Tool integration

Tools are how agents touch the outside world. A tool is a typed function with a permission requirement. Register a custom tool:

```python
# tools/lighthouse.py
from sams.sdk import tool

@tool(
    id="seo.lighthouse",
    requires_permission="tools:seo.lighthouse",
    description="Run a Lighthouse audit and return scores.",
)
async def lighthouse(ctx, url: str) -> dict:
    result = await ctx.shell.run(f"lighthouse {url} --output=json --quiet")
    return ctx.json(result.stdout)
```

Tools can also be provided by **MCP servers** — any MCP server you connect becomes a set of callable tools (see [9.3](#93-mcp-model-context-protocol)). This is the recommended way to add large tool surfaces without writing adapters.

## 6.6 Registering an agent

Registration makes an agent known to the Orchestrator. Three options:

```bash
# 1. Local (this instance only)
sams agent add agents/custom/seo-agent.agent.yaml

# 2. Validate before adding
sams agent validate agents/custom/seo-agent.agent.yaml

# 3. From the registry
sams agent install beacon-seo@1.0.0
```

Or via the command palette in the spatial UI: **`Spawn New Agent` → select manifest**. Registration is hot — no restart required.

## 6.7 Testing an agent

The SDK ships a test harness that runs an agent against recorded events and fixture Vaults, with the LLM mocked or live.

```python
# tests/test_seo_agent.py
from sams.testing import AgentHarness

async def test_seo_audit_creates_tasks():
    harness = AgentHarness("agents/custom/seo-agent.agent.yaml", model="mock")
    harness.vault.put("vault://content/seo-rules.yaml", "...")
    result = await harness.invoke("content.seo_audit", url="https://example.com")
    assert result["issues"] >= 0
    assert harness.events.contains("content.seo_audit.completed")
    assert harness.kanban.cards_with_label("seo")
```

```bash
sams agent test agents/custom/seo-agent.agent.yaml
```

## 6.8 Publishing to the registry

Share an agent or pack so others (or other instances) can install it:

```bash
sams registry login
sams agent publish agents/custom/seo-agent.agent.yaml --visibility private
# -> beacon-seo@1.0.0 published to registry (private)
```

Published items carry their manifest, handler, prompts, version, and a checksum. Consumers install by `id@version`.

## 6.9 End-to-end example: adding a "Translator" agent in 5 steps

1. **Write the manifest** (`agents/custom/translator.agent.yaml`) declaring `content.localize` capability, `translate.run` + `doc.write` tools, and `home: Desk, room: i18n`.
2. **(Optional) Write a handler** if you need glossary enforcement or QA passes.
3. **Validate:** `sams agent validate agents/custom/translator.agent.yaml`
4. **Register:** `sams agent add agents/custom/translator.agent.yaml`
5. **Use it:** label any Kanban card `i18n` (or call `content.localize`), and the Orchestrator routes it to the new agent, which appears at its Desk in the workspace.

That is the entire lifecycle — **no core code touched.** This is the mechanism that guarantees you can keep extending SAMS with new agents indefinitely.

## 6.10 Best practices for agent authors

- **One agent, one clear role.** Narrow agents are easier to route, permission, and reason about than do-everything agents.
- **Declare capabilities accurately.** The Orchestrator routes by capability; a wrong declaration means wrong assignments.
- **Least privilege.** Grant the minimum read/write/tool/environment scope. Never give `approve: true` unless separation-of-duties demands it.
- **Make actions idempotent.** Events are at-least-once; design handlers to tolerate replays.
- **Emit events generously.** Observability and the spatial UI depend on it.
- **Never let an agent self-approve its own gated work.**
- **Prefer MCP tools** over bespoke adapters for breadth; write native tools only for hot paths.
- **Pin model and version** in the manifest for reproducibility; override per instance when needed.
- **Write at least one harness test** per custom capability.

---

# 7. The Spatial Interface

The spatial interface is what makes SAMS legible. It is a real-time, isometric rendering of the agent fleet and its work. This section documents what's on screen and how it maps to system state.

## 7.1 The isometric workspace

The main view is an isometric room containing agents and primitives. It is driven by the Spatial Engine's scene graph and updated live from the Event Bus over WebSocket. The header shows the product identity and global controls; the left panel is the **Explorer**; the right panel shows context (**Primitive Properties**, **System Overview**, or a selected item's detail); the bottom panel is the **console** (Terminal / Output / Event Log / Problems).

Status bar (bottom): branch (`main`), problem counts, spaces count, encoding (`UTF-8`), line ending (`LF`), language (`YAML`/`Python`), and connection state (`SAMS: Connected`), plus the platform version and mode (`SAMS Platform v0.9.0 · Spatial Mode · 6 Agents Online · All Systems Operational`).

## 7.2 The Explorer

The Explorer is a file-tree-like navigator over the SAMS workspace:

```
SAMS-WORKSPACE
├── agents/          blue, green, orange, purple, red, yellow   (M/U = modified/unmodified)
├── workflows/       onboarding.flow, code-review.flow, deploy.flow
├── environments/    dev.env, staging.env, prod.env
├── assets/          architecture.spatial, office-layout.spatial, furniture.spatial
├── configs/         sams.yaml, agents.yaml, permissions.yaml
├── README.md
├── CHANGELOG.md
└── LICENSE
```

## 7.3 Primitive types & bindings

| Primitive | Spatial appearance | Bound capability | Key interactions |
|---|---|---|---|
| **Desk** | A workstation with a laptop/monitors | Active compute, bound to a working dir | Bind directory, assign agent, open files |
| **Vault** | A safe/strongbox | Storage + memory | View status, browse files, inspect memory |
| **Whiteboard** | A glass board with diagrams | Ideation, PRDs, diagrams | Generate diagram, expand notes, convert to PRD |
| **Kanban Wall** | A board with columns of cards | Task management | New card, move card, filter, sync GitHub |
| **Security Gate** | A turnstile/access gate | Approvals + source control | Approve, request changes, review queue |
| **Lounge** | A seating area | Idle agent pool | Assign idle agents |
| **Event Stream** | A live feed panel | Event bus projection | Inspect events, filter |

Primitives can be **coupled** so changes propagate: e.g. `Coupled Whiteboard → Desk 01 via API channel (whiteboard.data → /work/boards)`.

## 7.4 The command palette

Pressing `⌘K` (or `⌘P` for the command variant) opens the palette: a single input for files, symbols, agents, and commands. It is the fastest way to act.

## 7.5 Spatial commands reference

| Command | ID | Effect |
|---|---|---|
| Spawn New Agent | `agent:new` | Instantiate an agent from a manifest. |
| Resize Grid | `grid:resize` | Change room dimensions. |
| Add Primitive | `spatial:add` | Place a new primitive. |
| Bind Directory to Primitive | `bind:directory` | Map a working directory to a Desk/primitive. |
| Snap to Grid | `grid:snap` | Align primitives to the grid. |
| Reset View | `view:reset` | Recenter the camera. |
| Add Interaction Point | `primitive:interaction:add` | Add an action to a primitive. |

Primitive properties (right panel) expose **Transform** (position X/Y/Z, rotation, scale), **Appearance** (material, opacity, edge glow, color), and **Metadata** (name, tags), plus links and bindings.

## 7.6 The System Overview minimap

The **System Overview** (top-right) is a zoomed-out projection of all spaces and agents — each agent a colored marker — with a live count ("6 Agents Active") and zoom control. It is the fastest way to see fleet distribution and spot a room that's overloaded or idle.

## 7.7 View modes

The Whiteboard supports three content modes:

- **Design** — freeform canvas (shapes, connectors, sticky notes).
- **Document** — structured docs with AI writing assistance.
- **Hybrid** — both at once (diagram + linked doc), as in the "Authentication Flow Improvements" board.

The AI Assistant panel offers actions on board content: **Generate Diagram**, **Expand Notes**, **Summarize**, **Convert to PRD**, **Create Tasks**, **Link to Desk**.

---

## 7.8 Design language & art direction

SAMS has a deliberate, cohesive visual identity: **a clean, light, premium developer tool fused with a friendly isometric life-sim.** It should feel calm and spacious, not busy — the complexity lives in the work, not the chrome.

Guiding visual principles:

- **Light, airy, minimal.** Near-white surfaces, generous whitespace, restrained borders. The 3D scene reads like a bright daylight studio.
- **Depth through softness, not heaviness.** Elevation comes from soft shadows, gentle ambient occlusion, and glassmorphism — never hard lines or harsh contrast.
- **Color means something.** Color is reserved for **identity** (each agent's color) and **status** (success / in-progress / error / idle). Neutral chrome everywhere else keeps those signals legible.
- **Friendly characters reduce cognitive load.** The rounded robot avatars make a fleet of agents feel approachable and instantly distinguishable — the core of the "Sims for agents" feel.
- **IDE familiarity.** The shell borrows the mental model of a modern code editor (Linear / Raycast / VS Code / Arc lineage) so developers feel at home immediately.

## 7.9 Color system

Extracted from the reference UI. The app theme tint is a very light blue (`#EEF6FF`); the brand/action color is blue.

**Surfaces & chrome**

| Token | Hex | Use |
|---|---|---|
| `--bg-app` | `#F6F8FB` | App background |
| `--bg-panel` | `#FFFFFF` | Panels, cards, modals |
| `--bg-tint` | `#EEF6FF` | Subtle blue tint / selected rows |
| `--border` | `#E2E8F0` | Default borders/dividers |
| `--border-strong` | `#CBD5E1` | Emphasized borders |

**Text**

| Token | Hex | Use |
|---|---|---|
| `--text` | `#0F172A` | Primary text |
| `--text-muted` | `#64748B` | Secondary text |
| `--text-subtle` | `#94A3B8` | Tertiary / placeholder |

**Brand & action**

| Token | Hex | Use |
|---|---|---|
| `--brand` | `#3B82F6` | Primary buttons, active state, links |
| `--brand-hover` | `#2563EB` | Hover/pressed |

**Status (semantic)**

| Token | Hex | Meaning |
|---|---|---|
| `--success` | `#22C55E` | Done / success / `[SUCCESS]` |
| `--warning` | `#F59E0B` | In progress / blocked / `[WARN]` |
| `--error` | `#EF4444` | Error / `[ERROR]` |
| `--idle` | `#94A3B8` | Idle / neutral / `[IDLE]` |
| `--info` | `#3B82F6` | Info / `[INFO]` |

**Agent identity palette** (the six core agents; extend with new hues for custom agents)

| Agent | Hex |
|---|---|
| blue | `#3B82F6` |
| green | `#22C55E` |
| orange | `#F97316` |
| purple | `#8B5CF6` |
| red | `#EF4444` |
| yellow | `#EAB308` |

**Soft accents** (Kanban label chips & Whiteboard sticky notes)

| Token | Hex |
|---|---|
| sticky/label yellow | `#FEF3C7` |
| sticky/label green | `#DCFCE7` |
| sticky/label pink | `#FCE7F3` |
| sticky/label blue | `#DBEAFE` |
| sticky/label purple | `#EDE9FE` |

**Glass / glow**

| Token | Value | Use |
|---|---|---|
| `--glass-edge` | `#7CC3FF` | Edge glow on glass primitives |
| `--glass-opacity` | `0.65` | Glass primitive opacity |

> **Dark variant:** the lo-fi product videos show a dark "night" environment, so a dark theme is in scope. Mirror every token above into a dark set (e.g. `--bg-app: #0B0F1A`, `--bg-panel: #131926`, text inverted) and switch by `data-theme`.

## 7.10 Typography

| Role | Family (reference) | Notes |
|---|---|---|
| UI / sans | `Inter`, `SF Pro Text`, `system-ui` | Humanist geometric sans; weights 400 / 500 / 600. |
| Monospace | `JetBrains Mono`, `SF Mono`, `ui-monospace` | Terminal, agent logs, code editor, IDs (e.g. `SAMS-201`, `prim_8f3a9c2d`). |

Suggested type scale:

| Token | Size / line-height | Use |
|---|---|---|
| `text-caption` | 12 / 16 | Labels, meta, status pills |
| `text-body` | 13–14 / 20 | Default UI text |
| `text-h3` | 16 / 24 | Panel/section headers |
| `text-h2` | 18 / 26 | Card titles, board titles |
| `text-h1` | 20–24 / 30 | View titles |

Keep weight contrast (500/600 for emphasis) rather than size jumps; favor whitespace over rules to separate groups.

## 7.11 Iconography & 3D art direction

**Icons** — thin **line icons**, rounded joins, consistent ~1.5px stroke on a uniform grid (Explorer rail, toolbar, command palette, primitive actions).

**Agent characters** — the signature element:

- Rounded, matte **robot avatars**, one **solid identity color** each.
- A simple, expressive **"visor" face** (two glowing eyes) — friendly, low-detail so it stays legible at small scale and in the minimap.
- A **glowing base ring** in the agent's color marks position and draws the eye to active agents.
- Personality through pose and motion, not detail (Pixar-lite, not photoreal).

**Spatial primitives** — each is a recognizable 3D object so its function is readable at a glance:

| Primitive | Material / form |
|---|---|
| Vault | Brushed-metal **safe / strongbox**, heavy dial |
| Whiteboard | **Frosted glass** panel with edge glow, faint diagrams |
| Kanban Wall | Glass board with **pastel sticky cards** in columns |
| Security Gate | **Brushed-metal turnstile** with a green access light |
| Desk | **Warm wood** desk + laptop/monitors, mug, small plant |
| Lounge | Soft seating, plant — a calm "idle" corner |

**Materials & lighting** — matte surfaces, soft contact shadows, gentle ambient occlusion, subtle **rim/edge glow** on interactive and glass objects; bright, even, **soft daylight** lighting. The overall render is clean and toy-like, never gritty.

## 7.12 Layout & shell

The shell is a three-pane IDE layout with a top command bar and a bottom console:

```
┌───────────────────────────────────────────────────────────────────────────┐
│ ●●●  SAMS — Spatial Agentic Management System   [ ⌘K  search… ]   👥 🔔 (A) │  top bar
├──────────┬────────────────────────────────────────────────┬───────────────┤
│ icon     │                                                │  System       │
│ rail +   │            CENTER CANVAS                       │  Overview      │
│ Explorer │   (3D scene / Kanban / Whiteboard / code)      │  (minimap)     │
│ tree     │                                                ├───────────────┤
│          │                                                │  Context panel │
│          │                                                │  (Properties / │
│          │                                                │   detail)      │
├──────────┴────────────────────────────────────────────────┴───────────────┤
│ TERMINAL · OUTPUT · EVENT LOG · PROBLEMS                     console        │
├───────────────────────────────────────────────────────────────────────────┤
│ ⬡ main*   ⊘ 2  ⚠ 0      Spaces: 2   UTF-8   LF   YAML   ● SAMS: Connected   │  status bar
└───────────────────────────────────────────────────────────────────────────┘
```

- **Top-left:** macOS-style traffic-light window controls, then the SAMS wordmark + subtitle.
- **Top-center:** the floating **command bar** (`⌘K` search / `⌘P` command).
- **Top-right:** collaborators, notifications, account.
- **Left:** an **icon rail** (Explorer, Search, Source Control, Spatial CAD, Extensions) plus the Explorer tree.
- **Right:** **System Overview** minimap on top, contextual **Properties / detail** below.
- **Bottom:** tabbed **console** and a thin **status bar**.

**Spacing & shape**

| Token | Value |
|---|---|
| Base spacing unit | `8px` (use multiples: 4/8/12/16/24) |
| `--radius-sm` | `8px` (chips, inputs) |
| `--radius-md` | `12px` (cards) |
| `--radius-lg` | `16px` (panels, modals, command bar) |
| `--shadow-sm` | `0 1px 2px rgba(15,23,42,.06)` |
| `--shadow-md` | `0 4px 12px rgba(15,23,42,.08)` |

## 7.13 Component styling

| Component | Styling notes |
|---|---|
| **Kanban card** | White, `--radius-md`, `--shadow-sm`; colored **label chips**; agent avatar; thin progress bar; comment count; id tag (`SAMS-201`). Column header shows a count badge. |
| **Status pill** | Tinted background + matching text color: In Progress (amber), In Review (orange), Done (green), Blocked (amber/red). |
| **Buttons** | Primary = filled `--brand`; secondary = ghost/outline; pill-shaped search field with leading icon + `⌘K` hint. |
| **Panels** | White, subtle border, section headers in `text-h3`, collapsible groups, generous padding. |
| **Command palette** | Centered floating card, `--radius-lg`, `--shadow-md`, grouped results with right-aligned shortcut hints (`agent:new`, `grid:resize`). |
| **Progress bar** | Thin, fully rounded, `--brand` fill on a light track; shows % (e.g. `72%`). |
| **Console / logs** | Monospace, color-coded levels (`[INFO]` blue, `[SUCCESS]` green, `[WARN]` amber, `[ERROR]` red, `[IDLE]` grey), agent name tinted to its identity color. |
| **Properties panel** | Grouped sections (Transform, Appearance, Metadata) with compact numeric steppers, a material dropdown, an opacity slider, and an edge-glow toggle + color swatch. |

## 7.14 Motion & feedback

Motion is subtle and purposeful (≈150–250ms, ease-out):

- Agents **walk** between stations and **idle** in the Lounge; an **active glow pulse** marks who's working.
- Kanban cards **slide** between columns on move; progress bars **animate** as work advances.
- Selected/active primitives **intensify their edge glow**; couplings show a faint animated channel between primitives.
- The **Event Stream** and console tick in real time as events arrive.
- State changes are reinforced by both color and the spatial cue (see [4.3](#43-agent-states)) — never color alone.

## 7.15 Design tokens (copy-paste)

A ready-to-use token set so the look is reproducible in the reference UI:

```css
:root {
  /* Surfaces */
  --bg-app: #F6F8FB;  --bg-panel: #FFFFFF;  --bg-tint: #EEF6FF;
  --border: #E2E8F0;  --border-strong: #CBD5E1;

  /* Text */
  --text: #0F172A;  --text-muted: #64748B;  --text-subtle: #94A3B8;

  /* Brand / action */
  --brand: #3B82F6;  --brand-hover: #2563EB;

  /* Status (semantic) */
  --success: #22C55E;  --warning: #F59E0B;  --error: #EF4444;
  --idle: #94A3B8;     --info: #3B82F6;

  /* Agent identity */
  --agent-blue: #3B82F6;  --agent-green: #22C55E;  --agent-orange: #F97316;
  --agent-purple: #8B5CF6; --agent-red: #EF4444;   --agent-yellow: #EAB308;

  /* Soft accents (labels / sticky notes) */
  --accent-yellow: #FEF3C7; --accent-green: #DCFCE7; --accent-pink: #FCE7F3;
  --accent-blue: #DBEAFE;   --accent-purple: #EDE9FE;

  /* Glass */
  --glass-edge: #7CC3FF;  --glass-opacity: 0.65;

  /* Radius / elevation / spacing */
  --radius-sm: 8px;  --radius-md: 12px;  --radius-lg: 16px;
  --shadow-sm: 0 1px 2px rgba(15,23,42,.06);
  --shadow-md: 0 4px 12px rgba(15,23,42,.08);
  --space-unit: 8px;

  /* Type */
  --font-ui: 'Inter','SF Pro Text',system-ui,-apple-system,sans-serif;
  --font-mono: 'JetBrains Mono','SF Mono',ui-monospace,monospace;
}

/* Dark variant (from the lo-fi product videos) */
[data-theme="dark"] {
  --bg-app: #0B0F1A;  --bg-panel: #131926;  --bg-tint: #0F1626;
  --border: #1E293B;  --border-strong: #334155;
  --text: #E6EDF7;    --text-muted: #94A3B8; --text-subtle: #64748B;
}
```

> **▶ Extension point:** When you add a new agent, give it a distinct identity hex (add an `--agent-*` token); when you add a new primitive, define its material/form here so the world stays visually coherent.

## 7.16 Chat, messaging & the AI Assistant

Conversation is a first-class surface in SAMS — it is how humans direct agents, how agents talk to each other, and how discussion stays anchored to the work. There is no separate "chat app"; messaging is woven into the workspace.

### Where conversation happens

| Surface | What it is |
|---|---|
| **AI Assistant panel** ("Ask AI") | A **context-aware** chat docked to the right of an artifact (board, doc, desk). It knows what's selected — e.g. *Context: IDEAS_BOARD.whiteboard · Frame 01, Doc 01 · 8 objects selected* — and can both answer and **run actions** (Generate Diagram, Create Tasks, Convert to PRD). |
| **Direct agent chat** | Open any agent (e.g. `blue-agent`) and converse with it directly; the console header's agent selector scopes the view to that agent. |
| **Command bar** (`⌘K`) | The "Type a command or search…" field doubles as a **natural-language entry point** — ask a question, issue an instruction, or run a command. |
| **Comment threads** | Comments anchored to a specific object — a Kanban card, a board frame, a doc selection, a diff line. (Seen on the board: *blue-agent · 10:42 AM · "Added adaptive risk checks based on recent insights" 👍*.) |
| **PR conversation** | The discussion thread on a Pull Request at the Security Gate (the PR's **Conversation** tab). |
| **Agent ↔ agent messages** | Agents address each other or a human via `agent.message`, routed by the Orchestrator and surfaced in the agent logs. |

### Core concepts

- **Thread** — a conversation with a `thread_id`, a set of **participants** (humans and/or agents), an **anchor** (what it's attached to: a board, card, PR, desk, agent, or `global`), and an ordered list of messages.
- **Mentions** — `@agent` or `@human` addresses and notifies a participant and influences routing (`Card #128 blocked: awaiting review` is the system-side counterpart).
- **Context attachment** — a message can carry references (selected objects, a file, a board) so the assistant or agent grounds its reply on exactly that material. This is what makes "Ask AI" answer *about this board* rather than in the abstract.
- **Actions from chat** — the assistant can **propose or execute** actions inline; a proposed action (e.g. *Create Tasks*) becomes real Kanban cards once accepted. Chat is therefore also a command surface.
- **Everything is an event** — every message emits `chat.message.posted` (and `agent.message` for agent-authored ones), so conversation is observable, replayable, and auditable like any other activity.
- **History & memory** — threads persist in the Vault (document store) and feed agent long-term memory (see [4.5](#45-agent-memory--context-window)); an agent can recall what was decided in a thread weeks later.

### Routing

When a human posts a message, the Orchestrator routes it:

1. **Addressed** (`@blue-agent`) → delivered to that agent.
2. **Anchored** (posted on a card/board) → delivered to the card's assignee or the board's related agents.
3. **Unaddressed** → routed by capability + context to the best-fit idle agent (same logic as task assignment, see [8.2](#82-task-assignment)).

### Permissions & safety

Agents only see threads within their permission scope. Messages that would leave the system on a human's behalf (an email, a Slack post) are **draft-only** and require human approval before sending (e.g. the `Echo` and `Relay` agents draft; a human sends). See [Section 12](#12-security--permissions).

## 7.17 Complete interface surface reference

So that **nothing on screen is undocumented**, every panel and rail item is accounted for here. Surfaces detailed elsewhere are cross-referenced; the rest are described inline.

| Surface | Location | Purpose |
|---|---|---|
| **Explorer** | Left tree | Navigate agents, workflows, environments, assets, configs (see [7.2](#72-the-explorer)). |
| **Search** | Left rail | Global search across files, agents, cards, docs, and events; results are typed and jump-to-able. |
| **Source Control** | Left rail | Git status for the workspace — changed files with `M`/`U` markers, branches, staging; feeds the Security Gate ([8.5](#85-the-code-review-flow-in-the-spatial-world)). |
| **Spatial CAD** | Left rail | The **layout editor** for the 3D world: place and transform primitives, define rooms and the grid, bind directories, and edit `.spatial` assets. This is the authoring counterpart to the spatial commands ([7.5](#75-spatial-commands-reference)). |
| **Extensions** | Left rail | Install and manage **agents, capability packs, integrations, MCP servers, and themes** from the registry ([Section 6](#6-building--extending-agents), [Section 9](#9-integrations)). |
| **Command bar** | Top center | Search + natural-language + commands ([7.4](#74-the-command-palette)). |
| **System Overview / Workspace Map** | Top right | Minimap of all spaces and agents ([7.6](#76-the-system-overview-minimap)). |
| **Context / Properties panel** | Right | Primitive Properties, agent detail, or selection context ([7.3](#73-primitive-types--bindings), [7.13](#713-component-styling)). |
| **Console** | Bottom | Terminal / Output / Event Log / Problems / Agent Logs ([Section 16](#16-observability)). |
| **Status bar** | Bottom edge | Branch, problem counts, spaces, encoding, language, connection state ([7.1](#71-the-isometric-workspace)). |
| **Outline** | Explorer (bottom) | Structural outline of the current view — board frames, doc headings — for quick jumping. |
| **Timeline** | Explorer (bottom) | A scrubbable chronological history of changes/events for the current space or artifact (who changed what, when). |
| **Collaboration** | Top right of artifacts | Live collaborators (avatars + presence), **Share**, **Cloud** sync, and an "Edited just now" indicator — multiple humans and agents co-present on the same board/doc. |
| **Account & notifications** | Top right | User menu and the notification bell (mentions, approvals awaiting you, blocked cards). |

### Whiteboard toolbar & content blocks

The Whiteboard ([7.7](#77-view-modes)) deserves its own breakdown, since the reference board is dense:

- **Toolbar:** Select, Frame, Text, Connector, Sticky Note, Shape, Comment, plus the **Design / Document / Hybrid** mode toggle, an **AI** toggle, **View** options, and zoom.
- **Frames:** named regions (`Frame 01`, `Frame 02`, `Frame 03`) that group related content (a flow, a decision tree, an example).
- **Doc blocks:** structured documents (`Doc 01`) with **AI writing** (inline suggestions, *Tab to accept*) and a **Sources (3)** citation tray.
- **Sticky-note clusters:** e.g. **Key Goals**, **Open Questions**, **Dependencies** — colored notes authored by humans and agents.
- **Reference Links:** linked external/internal docs (Auth Architecture Doc, Risk Scoring Model Spec, Audit Logging Standards).
- **Enrichment drop zone:** *"Drop files or paste links to enrich this board"* — ingest material that agents then ground on.
- **Related Agents & Activity:** which agents are attached to the board and a live activity feed of their edits.

> **▶ Extension point:** New rail tools, panels, or whiteboard block types are added the same way as primitives — register the surface, give it an icon and a place in the shell ([7.12](#712-layout--shell)), and wire its events onto the bus.

---

# 8. Workflows & Orchestration

A **workflow** is a declarative, multi-agent pipeline. Workflows live in the Explorer as `.flow` files and are executed by the Orchestrator.

## 8.1 Workflow definition

```yaml
# workflows/code-review.flow
apiVersion: sams/v1
kind: Workflow
metadata:
  id: code-review
  name: Code Review
spec:
  trigger:
    on: "git.pr.opened"
  steps:
    - id: assign-reviewer
      capability: code.review
      agent: hex                 # explicit, or omit to let the Orchestrator choose
      inputs:
        pr: "${trigger.payload.pr}"
    - id: security-scan
      capability: security.audit
      agent: aegis
      parallel: true             # runs alongside the review
    - id: gate
      kind: approval             # human/agent approval at the Security Gate
      requires: ["assign-reviewer", "security-scan"]
      approvers: ["hex", "aegis", "human:lead"]
      policy: all                # all | any | quorum(n)
    - id: merge
      capability: ops.deploy
      agent: forge
      requires: ["gate"]
  outputs:
    merged: "${steps.merge.result}"
  onError:
    notify: ["echo"]
```

## 8.2 Task assignment

The Orchestrator assigns a step's task to an agent by:

1. **Explicit assignment** (the step names an agent), or
2. **Capability match** — find idle agents that provide the required capability,
3. **Tie-break** by current load, priority, and historical success on similar tasks.

## 8.3 The Kanban system

The Kanban Wall is the human-and-agent-shared task surface. Columns map to status (`To Do`, `In Progress`, `In Review`, `Done`), and each card carries an id (`SAMS-201`), title, labels, assignee (an agent), progress, checklist, milestone, and priority. Cards sync **bidirectionally** with GitHub Projects (`Repository: sams/spatial-os · Project: SAMS Platform`). Moving a card emits `kanban.card.moved`, which can trigger workflows.

Example card detail:

```
SAMS-201  Build real-time agent activity engine
  Status: In Progress     Assignee: blue-agent (Opus)
  Labels: backend, performance     Milestone: v0.2.0     Priority: High
  Checklist 2/4:
    [x] WebSocket connection
    [x] Event schema design
    [ ] Agent action broadcaster
    [ ] UI event consumer
```

## 8.4 Built-in workflows

| Workflow | Trigger | Agents | Outcome |
|---|---|---|---|
| `onboarding.flow` | New space created | Concierge, Compass, Atlas | Boards, environments, and starter tasks created. |
| `code-review.flow` | PR opened | Hex, Aegis, Forge | Reviewed, security-scanned, gated, merged. |
| `deploy.flow` | Merge to `main` / manual | Forge, Watchtower | Built, deployed to target env, monitored. |

## 8.5 The code-review flow in the spatial world

The reference UI shows this flow concretely: an agent commits on a feature branch, a **Pull Request (#128 "Add audit logging and security gate integration")** is opened, reviewers (`Aria, Hex, Nova`) are requested, the diff is shown at the Security Gate, approvals land (`All required reviewers have approved. Ready to merge.`), and approved changes **automatically sync to the Vault**. The turnstile/gate is not a metaphor only — nothing passes to `main` without crossing it.

## 8.6 Custom workflows

> **▶ Extension point:** Add a `.flow` file with a trigger, steps (each a capability + optional agent), gates, and outputs. Reference new agents by capability and they slot in automatically. Validate with `sams flow validate workflows/your.flow`.

---

# 9. Integrations

Integrations adapt external systems into SAMS as **tools** (callable by agents) and **events** (published to the bus).

## 9.1 AI model providers

SAMS is model-agnostic. Each agent binds to a provider/model; the binding is overridable per instance and per environment.

| Provider | Models (examples) | Notes |
|---|---|---|
| Anthropic | Claude Opus / Sonnet / Haiku | Default; high-reasoning agents use Opus, high-volume use Haiku. |
| OpenAI | GPT family | Via the OpenAI adapter. |
| Google | Gemini family | Via the Gemini adapter. |
| Local | Ollama / vLLM | For private or cost-sensitive workloads. |

Provider config:

```yaml
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    default_model: claude-sonnet-4
  openai:
    api_key: ${OPENAI_API_KEY}
  local:
    base_url: http://localhost:11434
```

## 9.2 GitHub / version control

The GitHub integration provides repo, PR, and Projects sync. It maps:

- `git.pr.opened` / `git.pr.merged` → Event Bus events (trigger workflows).
- Kanban cards ↔ GitHub Project items (bidirectional).
- Commits/branches surfaced in agent telemetry and the Security Gate.

Tools exposed: `git.commit`, `git.push`, `git.diff`, `git.pr.create`, `git.pr.review`, `git.pr.merge`.

## 9.3 MCP (Model Context Protocol)

MCP is the recommended way to give agents large tool surfaces. Connect an MCP server and its tools become callable by permitted agents — no adapter code.

```yaml
mcp:
  servers:
    - name: filesystem
      type: stdio
      command: "mcp-server-filesystem /work"
    - name: database
      type: url
      url: "https://mcp.internal/db"
    - name: search
      type: url
      url: "https://mcp.example/search"
```

A connected server's tools appear in the tool registry as `mcp.<server>.<tool>` and are subject to the same permission checks as native tools.

## 9.4 Webhooks & events

Inbound webhooks become events; outbound webhooks fire on events.

```yaml
webhooks:
  inbound:
    - path: /hooks/tickets
      emits: "support.ticket.created"
  outbound:
    - on: "ops.deploy.completed"
      url: "https://hooks.slack.com/..."   # human notification
```

> **▶ Extension point:** Add a provider adapter or MCP server here. Prefer MCP for breadth; write native adapters for hot paths or deep integrations.

---

# 10. Configuration Reference

SAMS configuration is YAML, versioned alongside the workspace. The three core files:

## 10.1 `sams.yaml` — platform config

```yaml
apiVersion: sams/v1
kind: Platform
metadata:
  name: my-sams-instance
spec:
  version: 0.9.0
  defaultSpace: main.space
  spaces:
    - id: main.space
      file: assets/office-layout.spatial
    - id: labs.space
      file: assets/labs-layout.spatial
  eventBus:
    backend: redis-streams        # redis-streams | nats
    retention: 7d
  vault:
    relational: postgres://...
    documents: mongodb://...
    vectors: qdrant://...
    objects: s3://sams-artifacts
  limits:
    maxConcurrentAgents: 24
    maxContextWindow: 200000
  providers: { ... }              # see Section 9.1
  mcp: { ... }                    # see Section 9.3
```

## 10.2 `agents.yaml` — fleet roster

```yaml
apiVersion: sams/v1
kind: Roster
spec:
  agents:
    - ref: atlas                  # built-in
    - ref: opus
      model: { provider: anthropic, name: claude-opus-4 }
      instances: 1
    - ref: pixel
    - ref: hex
    - manifest: agents/custom/seo-agent.agent.yaml   # custom
  pools:
    engineering: [opus, pixel, nova, rune]
    review: [hex, aegis]
```

## 10.3 `permissions.yaml` — access policy

```yaml
apiVersion: sams/v1
kind: Permissions
spec:
  mode: development             # development | standard | strict (see 12.6)

  # When mode == development, every approval gate auto-passes and agents get
  # full scope, so nothing interrupts the build loop. Scoped to dev only.
  development:
    autoApprove: true           # auto-pass every Security Gate — no review prompts
    grantAllPermissions: true   # agents get full read / write / tool scope
    skipConfirmations: true     # never ask a human to confirm anything
    allowProtectedBranches: true
    appliesTo: [dev]            # do NOT widen to staging/prod

  roles:
    Junior Engineer:
      write: ["vault://src/feature-*/**"]
      approve: false
      environments: [dev]
    Reviewer:
      read: ["vault://**"]
      approve: true
      environments: [dev, staging]
    DevOps:
      approve: false
      environments: [dev, staging, prod]
  overrides:
    aegis: { approve: true }
  defaults:
    deny: true                    # deny-by-default
```

---

# 11. API Reference

SAMS exposes a REST API for control-plane operations, a WebSocket API for real-time events, and the Event Bus contract for integrations. All endpoints require authentication and are permission-checked.

## 11.1 REST API (control plane)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/agents` | List agents and states. |
| `POST` | `/api/v1/agents` | Spawn an agent from a manifest. |
| `GET` | `/api/v1/agents/{id}` | Get an agent's detail and telemetry. |
| `POST` | `/api/v1/agents/{id}/assign` | Assign a task to an agent. |
| `DELETE` | `/api/v1/agents/{id}` | Despawn an agent (graceful drain). |
| `GET` | `/api/v1/spaces` | List spaces. |
| `GET` | `/api/v1/spaces/{id}/scene` | Get the spatial scene graph. |
| `POST` | `/api/v1/spaces/{id}/primitives` | Add a primitive. |
| `GET` | `/api/v1/tasks` | List Kanban tasks. |
| `POST` | `/api/v1/tasks` | Create a task/card. |
| `PATCH` | `/api/v1/tasks/{id}` | Move/update a card. |
| `GET` | `/api/v1/workflows` | List workflows. |
| `POST` | `/api/v1/workflows/{id}/run` | Trigger a workflow. |
| `GET` | `/api/v1/events` | Query/replay events (paginated). |
| `POST` | `/api/v1/gates/{id}/approve` | Approve a gated change. |

Example:

```bash
curl -X POST https://sams.local/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"manifest": "agents/custom/seo-agent.agent.yaml", "instances": 1}'
```

## 11.2 WebSocket API (real-time)

The client subscribes to event streams and receives scene/state deltas.

```
WS /api/v1/stream?space=main.space
→ {"type":"agent.state.changed","actor":"blue-agent","payload":{"state":"working"}}
→ {"type":"kanban.card.moved","payload":{"card_id":"SAMS-201","to":"In Progress"}}
← {"type":"command","command":"agent:new","args":{"manifest":"..."}}
```

## 11.3 Event Bus contract

Topics and their core event types:

| Topic | Example events |
|---|---|
| `agent.*` | `agent.spawned`, `agent.state.changed`, `agent.message`, `agent.error` |
| `kanban.*` | `kanban.card.created`, `kanban.card.moved`, `kanban.card.labeled` |
| `vault.*` | `vault.file.changed`, `vault.memory.written` |
| `flow.*` | `flow.started`, `flow.step.started`, `flow.completed` |
| `security.*` | `security.gate.requested`, `security.gate.approved` |
| `spatial.*` | `spatial.primitive.added`, `spatial.binding.created` |
| `system.*` | `system.error`, `system.health` |

---

# 12. Security & Permissions

## 12.1 The Security Gate

The **Security Gate** is the enforced checkpoint between work and consequence. No merge to a protected branch and no deploy to a protected environment happens without passing the gate. It supports `all` / `any` / `quorum(n)` approval policies and records every decision.

## 12.2 Permission model

- **Deny-by-default.** Agents have no access unless granted.
- **Scoped resources.** Permissions use URI patterns (`vault://`, `kanban://`, `env://`).
- **Separation of duties.** Agents that produce work cannot approve their own gated changes.
- **Environment posture.** `prod` requires stricter approval and a narrower agent set.

## 12.3 Approval workflows

A gated step pauses the workflow, posts a review payload (diff, summary, risk notes) to the gate, and waits for approvers. Approvers may be agents (e.g. `hex`, `aegis`) and/or humans (`human:lead`). On approval, the workflow resumes; on rejection, it routes back with comments.

## 12.4 Audit logging

Every action is an event, and security-relevant events are written to an **append-only audit log** in the Vault (owned by `Warden`). Audit entries capture actor, action, target, decision, and trace id — enough to reconstruct exactly what happened and who approved it.

## 12.5 Secrets management

Secrets are never stored in manifests or memory. They are referenced (`${ANTHROPIC_API_KEY}`) and resolved at runtime from a secrets backend. `Aegis` runs secret-leak scans on commits and blocks gates on detection.

## 12.6 Development Mode (full autonomy / auto-approve)

For fast iteration, SAMS supports a **Development Mode** in which agents operate with **full autonomy and nothing requires manual approval**. While developing, the system **does everything automatically** — it never stops to ask "do you allow this?" Every gate is auto-passed, every permission is granted, and every confirmation is skipped, so the build loop runs uninterrupted.

This is the recommended posture for local/`dev` work. It is **scoped to the `dev` environment** (the existing strict model still applies to `staging` and `prod`, see [12.2](#122-permission-model) and [14.1](#141-environments)), so you get full speed where it's safe and full control where it matters.

### What Development Mode does

| Setting | Effect when enabled |
|---|---|
| `autoApprove: true` | Every **Security Gate auto-passes** — PRs, merges, and deploys proceed without a human/agent review prompt. Workflows run end-to-end without pausing. |
| `grantAllPermissions: true` | Agents receive **full read / write / tool scope** — no `deny-by-default`, no per-resource permission checks. Any agent can touch any file, run any tool. |
| `skipConfirmations: true` | **No confirmation prompts of any kind.** The system never asks the human to approve, confirm, or allow an action — it just performs it. |
| `allowProtectedBranches: true` | Agents may write to and merge protected branches (e.g. `main`) directly in dev. |

In short: **the human is never in the loop in dev** — agents plan, write, review, merge, and deploy autonomously, and the workspace simply shows it happening in real time.

### Enabling it

Either set the mode in `permissions.yaml` (see [10.3](#103-permissionsyaml--access-policy)):

```yaml
spec:
  mode: development
  development:
    autoApprove: true
    grantAllPermissions: true
    skipConfirmations: true
    allowProtectedBranches: true
    appliesTo: [dev]
```

…or pass it at startup:

```bash
sams up --mode development        # full autonomy, nothing prompts
# alias:
sams up --autonomous
```

You can confirm it's active in the status bar / `sams status` — Development Mode reports `Gates: auto · Permissions: all · Confirmations: off`.

### Behavior summary

- **Gates** become **no-ops** in dev: `security.gate.requested` is immediately followed by `security.gate.approved` with `approver: "auto:dev-mode"` (still logged for the audit trail).
- **Workflows** never enter the `blocked`/`awaiting_approval` state in dev — they flow straight through.
- **Agents** never wait on a human; an idle agent that has work simply does it.
- **Everything is still observable.** Auto-approvals, full-scope actions, and skipped confirmations are all recorded as events and in the audit log ([12.4](#124-audit-logging)) — so even with zero prompts you can see exactly what every agent did.

> **▶ Extension point / promotion path:** When you graduate a change from `dev` toward `staging`/`prod`, switch `mode: standard` (or `strict`) so the Security Gate, permission scopes, and confirmations re-engage. The same agents and workflows run unchanged — only the approval posture differs. Keep `appliesTo: [dev]` so Development Mode can never silently apply to a protected environment.

---

# 13. Data Models & Schemas

Canonical shapes for the core entities (reference).

## 13.1 Agent

```json
{
  "agent_id": "blue-agent",
  "name": "Opus",
  "color": "#3B82F6",
  "role": "Backend Engineer",
  "seniority": "senior",
  "model": {"provider": "anthropic", "name": "claude-opus-4"},
  "capabilities": ["code.write", "code.review", "code.refactor"],
  "tools": ["fs.read", "fs.write", "git.commit", "git.push"],
  "permissions": {"approve": false, "environments": ["dev", "staging"]},
  "state": "working",
  "home": {"primitive": "Desk 01", "room": "main"},
  "telemetry": {"progress": 0.72, "context_window": {"used": 96000, "max": 200000}}
}
```

## 13.2 Task (Kanban card)

```json
{
  "id": "SAMS-201",
  "title": "Build real-time agent activity engine",
  "status": "In Progress",
  "assignee": "blue-agent",
  "labels": ["backend", "performance"],
  "priority": "High",
  "milestone": "v0.2.0",
  "progress": 0.72,
  "checklist": [
    {"item": "WebSocket connection", "done": true},
    {"item": "Event schema design", "done": true},
    {"item": "Agent action broadcaster", "done": false},
    {"item": "UI event consumer", "done": false}
  ],
  "repo": "sams/spatial-os",
  "github_item": 128
}
```

## 13.3 Space / Primitive

```json
{
  "space_id": "main.space",
  "room": {"width": 12.0, "depth": 10.0, "height": 3.0, "grid": 0.5},
  "primitives": [
    {
      "id": "prim_8f3a9c2d",
      "type": "Whiteboard",
      "name": "Whiteboard",
      "transform": {"position": [7.5, 2.0, 0.0], "rotation": [0,0,0], "scale": [1.5,1.0,0.05]},
      "appearance": {"material": "glass", "opacity": 0.65, "edgeGlow": true, "color": "#7CC3FF"},
      "tags": ["whiteboard", "ideation", "linked"],
      "bindings": [{"channel": "whiteboard.data", "to": "/work/boards"}]
    }
  ]
}
```

## 13.4 Event

```json
{
  "id": "evt_8f3a9c2d",
  "type": "kanban.card.moved",
  "ts": "2026-06-21T11:02:31Z",
  "actor": "blue-agent",
  "space": "main.space",
  "payload": {"card_id": "SAMS-201", "from": "To Do", "to": "In Progress"},
  "trace_id": "trc_19af",
  "idempotency_key": "blue-agent:SAMS-201:moved:11:02:31"
}
```

## 13.5 Workflow run

```json
{
  "run_id": "run_4471",
  "workflow": "code-review",
  "trigger": {"type": "git.pr.opened", "pr": 128},
  "status": "awaiting_approval",
  "steps": [
    {"id": "assign-reviewer", "agent": "hex", "status": "complete"},
    {"id": "security-scan", "agent": "aegis", "status": "complete"},
    {"id": "gate", "status": "blocked", "approvers": ["hex","aegis","human:lead"]}
  ]
}
```

## 13.6 Message & thread

```json
{
  "thread_id": "thr_77c1",
  "anchor": {"type": "whiteboard", "id": "IDEAS_BOARD.whiteboard"},
  "title": "Authentication flow review",
  "participants": ["blue-agent", "purple-agent", "human:tamas"],
  "message_count": 12,
  "updated_at": "2026-06-21T10:42:00Z"
}
```

```json
{
  "message_id": "msg_9af2",
  "thread_id": "thr_77c1",
  "anchor": {"type": "whiteboard", "id": "IDEAS_BOARD.whiteboard", "object": "Frame 01"},
  "author": {"type": "agent", "id": "blue-agent"},
  "ts": "2026-06-21T10:42:00Z",
  "body": "Added adaptive risk checks based on recent insights.",
  "mentions": ["human:tamas"],
  "context_refs": ["vault://docs/risk-scoring-model-spec.md", "card:SAMS-302"],
  "actions": [{"type": "create_tasks", "status": "executed", "result": ["SAMS-310"]}],
  "reactions": [{"emoji": "👍", "by": "human:tamas"}]
}
```

---

# 14. Deployment & Operations

## 14.1 Environments

SAMS runs against named environments with isolated config, secrets, and permissions:

| Environment | Posture |
|---|---|
| `dev.env` | **Development Mode** by default: full autonomy — gates auto-approve, agents get full scope, no confirmation prompts (see [12.6](#126-development-mode-full-autonomy--auto-approve)). Cheap models; no protected-branch restrictions. |
| `staging.env` | Production-like; gated merges; full test suites. |
| `prod.env` | Strict; narrow agent set; mandatory approvals; audit on everything. |

## 14.2 Reference deployment topology

```
┌───────────────────────────── Cluster ─────────────────────────────┐
│  API/Gateway (FastAPI)   WebSocket gateway   Static UI (React)     │
│         │                      │                                   │
│  Orchestrator ── Event Bus (Redis/NATS) ── Agent Runtime (Celery)  │
│         │                                        │                 │
│  Postgres   MongoDB   Vector store   Object store (S3)             │
└────────────────────────────────────────────────────────────────────┘
```

Each layer scales independently. The Agent Runtime is the elastic tier (scale workers with demand); the Event Bus is the durability backbone; the Vault stores are stateful and backed up.

## 14.3 Scaling

- **Horizontal agents.** Add runtime workers to raise `maxConcurrentAgents`. The Orchestrator's backpressure prevents provider rate-limit overruns.
- **Event Bus.** Start on Redis Streams; migrate to NATS JetStream for high fan-out.
- **Isolation.** Promote untrusted agents to **Hard** isolation (containers) independently of the rest.

## 14.4 Backup & recovery

- **Vault** stores are backed up on a schedule; object storage is versioned.
- **Event streams** are retained per `eventBus.retention`, enabling replay/reconstruction of the spatial world and audit log.
- **Manifests, configs, and `.spatial`/`.flow` files** live in version control — the workspace is reproducible from source.

---

# 15. CLI & Command Reference

The `sams` CLI mirrors the control-plane API.

```bash
# Instance
sams init                              # scaffold a new instance
sams up                                # start the platform
sams status                            # health + agent states

# Agents
sams agent list
sams agent add <manifest>
sams agent validate <manifest>
sams agent test <manifest>
sams agent install <id@version>
sams agent publish <manifest> [--visibility private|public]
sams agent spawn <id> [--instances N]
sams agent despawn <id>

# Capability packs
sams pack install <pack> --agent <id>

# Workflows
sams flow list
sams flow validate <file>
sams flow run <id>

# Spaces & primitives
sams space list
sams primitive add --space <id> --type <Primitive>
sams bind directory <path> --to <Desk>

# Tasks
sams task list [--status <col>]
sams task create --title "..." [--label ...]
sams task move <id> --to <col>

# Observability
sams logs [--agent <id>] [--follow]
sams events tail [--type <topic>]
```

---

# 16. Observability

SAMS is observable by construction — the same event stream that drives the spatial UI feeds the operational tooling.

The bottom console exposes:

- **Terminal** — shell and command output.
- **Output** — structured run output.
- **Event Log** — the live event stream (filterable by topic/actor).
- **Agent Logs** — per-agent `[INFO]/[SUCCESS]/[WARN]/[IDLE]/[ERROR]` lines.
- **Problems** — current errors/warnings with counts.

Example agent-log stream:

```
10:42:11 [DESK 01]    Loaded architecture.md (1.2 KB)
10:42:12 [DESK 01]    Context shared → Whiteboard
10:42:14 [AGENT RED]  Linked events → orchestrator.py
10:42:15 [AGENT GREEN] Synced with Vault (24 modules)
10:42:17 [EVENT BUS]  event_bus.started
10:42:18 [AGENT BLUE] Started orchestrator.py
10:42:20 [SYSTEM]     All agents operational
10:42:22 [SYSTEM]     No errors detected
```

Recommended external sinks: metrics → Prometheus/Grafana; traces → OpenTelemetry (via `trace_id`); logs → your log stack. Every event carries a `trace_id` so a single user action can be followed across agents, tools, and gates.

---

# 17. Roadmap & Versioning

## 17.1 Versioning

- **Platform** uses semver; current `0.9.0` ("Spatial Mode", pre-1.0).
- **Agents and packs** are independently versioned (`id@semver`) and pinned in `agents.yaml`.
- **The Event Bus contract** is versioned via `apiVersion: sams/v1`; breaking changes bump the API version and run a migration window.

## 17.2 Indicative roadmap

| Milestone | Focus |
|---|---|
| `v0.9` (current) | Spatial mode, core agent catalog, Kanban + GitHub sync, Security Gate. |
| `v1.0` | Stable agent SDK + registry GA, multi-space at scale, hardened permissions. |
| `v1.1` | Multi-tenant spaces, richer collaboration (live co-presence), more providers. |
| `v1.2` | Marketplace for community agents/packs, visual workflow builder. |
| `Future` | Cross-instance federation, agent reputation/scoring, autonomous self-healing. |

> **▶ Extension point:** This roadmap is yours to edit. The architecture deliberately keeps agents, tools, workflows, and providers pluggable so the platform can grow without core rewrites.

---

# 18. Glossary

| Term | Definition |
|---|---|
| **Agent** | An autonomous, LLM-backed worker with identity, role, capabilities, tools, and permissions. |
| **Agent SDK** | The library for authoring agents (base classes, hooks, tools, manifest loader). |
| **Capability** | A declared, discrete skill an agent provides; used for routing and permissions. |
| **Capability pack** | A reusable bundle of capabilities installable onto compatible agents. |
| **Environment** | A named runtime target (`dev`/`staging`/`prod`) with its own config and posture. |
| **Event** | An immutable record of something that happened, published to the Event Bus. |
| **Event Bus** | The pub/sub backbone all components publish to and subscribe from. |
| **Gate / Security Gate** | The enforced approval + source-control checkpoint. |
| **Handler** | Optional agent code that adds custom behavior or capabilities. |
| **Home** | The spatial primitive an agent is bound to. |
| **Isolation level** | How strongly an agent is sandboxed (light/standard/hard). |
| **Manifest** | The declarative YAML definition of an agent. |
| **Orchestrator** | The component that schedules agents and drives workflows. |
| **Primitive** | A spatial object binding a place to a capability (Desk, Vault, etc.). |
| **Registry** | The catalog of installable agents and packs. |
| **Room / Space** | The isometric workspace (and bounded regions within it). |
| **Spatial Engine** | The subsystem owning the world model and scene graph. |
| **Vault** | Versioned storage for codebase, artifacts, and long-term memory. |
| **Workflow** | A declarative, multi-agent pipeline (`.flow`). |

---

# 19. Appendix

## 19.1 The complete capability namespace

```
code.write          code.review          code.refactor
research.web        research.summarize   research.cite
design.wireframe    design.diagram       design.critique
data.query          data.transform       data.visualize
qa.test.generate    qa.test.run          qa.bug.triage
ops.deploy          ops.monitor          ops.rollback
security.audit      security.secrets     security.approve
content.write       content.edit         content.localize
plan.spec           plan.breakdown       plan.estimate
agent.assign        agent.supervise      agent.recover
flow.execute
```

## 19.2 The complete tool namespace (built-in)

```
fs.read   fs.write   shell.run
git.commit  git.push  git.diff  git.pr.create  git.pr.review  git.pr.merge
web.search  web.fetch
db.query  etl.run  notebook.run
kanban.read  kanban.write
vault.read  vault.write  vault.search  vault.gc
whiteboard.read  whiteboard.write  canvas.draw  image.generate
doc.write  md.render  chart.render
gate.approve  gate.request_changes  gate.comment
test.generate  test.run  fuzz.run
sast.scan  secrets.scan
metrics.query  alert.raise  incident.open
ci.trigger  deploy.run  infra.apply  build.run  package.publish
email.draft  chat.post  schedule.post
translate.run  i18n.extract
mcp.<server>.<tool>          # any connected MCP server
```

## 19.3 Minimal "hello world" agent

The smallest valid agent (declarative-only):

```yaml
apiVersion: sams/v1
kind: Agent
metadata:
  id: greeter
  name: Greeter
  color: "#9CA3AF"
  version: 1.0.0
spec:
  role: Greeter
  seniority: junior
  model: { provider: anthropic, name: claude-haiku-4 }
  systemPrompt: "You greet new spaces and post a welcome note."
  capabilities: [content.write]
  tools: [chat.post]
  permissions: { approve: false, environments: [dev] }
  home: { primitive: Lounge, room: main }
```

```bash
sams agent add greeter.agent.yaml && sams agent spawn greeter
```

## 19.4 Design principles (summary)

1. **Agents are characters, not processes.**
2. **Work happens in places** (primitives bind capability to space).
3. **Everything emits events; the world is a projection of the stream.**
4. **Deny-by-default; separate duties; gate consequences.**
5. **Everything is hot-swappable and extensible** — agents, tools, workflows, providers, layouts.
6. **The reference stack is concrete, but the contracts are implementation-independent.**

---

*End of document. This is a living specification — extend the agent catalog ([Section 5](#5-the-agent-catalog)), the extensibility guide ([Section 6](#6-building--extending-agents)), workflows ([Section 8](#8-workflows--orchestration)), and integrations ([Section 9](#9-integrations)) as the platform grows.*
