# SAMS — Spatial Agentic Management System

> **"The Sims for managing AI agents."**
> A spatially-native platform for building, operating, and orchestrating fleets of
> autonomous AI agents inside a living, isometric visual workspace.

SAMS fuses three layers usually kept separate:

1. **An agent runtime** — spawns, schedules, and supervises LLM-backed agents.
2. **An orchestration engine** — coordinates multi-agent work via an Event Bus, task boards, and declarative `.flow` workflows.
3. **A spatial interface** — a real-time, game-like isometric workspace where agents, work, code, and infrastructure are visible objects.

It is **model-agnostic** (Claude / GPT / Gemini / local), **tool-extensible** (MCP + native adapters), and **agent-extensible** (anyone can author and register new agents with zero core changes).

This repository is a complete, runnable reference implementation built to the
[SAMS specification](./SAMS_Documentation.md). Every reference backend sits behind
an interface with a **local default**, so the whole platform runs out of the box
with **no external infrastructure and no API keys** (a deterministic `mock`
provider produces real work).

---

## Quickstart

### 1. Backend (Python 3.11+)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

sams up                      # start the platform on http://127.0.0.1:8787
#   alias: sams up --autonomous   (Development Mode: full autonomy, gates auto-approve)
```

In another shell:

```bash
sams status                  # SAMS v0.9.0 · development · 38 Agents Online · Gates: auto …
sams agent list              # the live fleet
sams flow run code-review --payload '{"pr":128}'
sams events tail --type agent
```

### 2. Spatial UI (TypeScript / React / Three.js)

```bash
cd web
npm install
npm run dev                  # http://localhost:5173 (proxies API+WS to :8787)
# or: npm run build  → the backend serves web/dist at http://127.0.0.1:8787/
```

Open the app and you'll see the isometric office: 38 robot agents at their
stations, the Vault, Whiteboard, Kanban Wall, and Security Gate — updating live
from the Event Bus over WebSocket.

> No API keys required. To use live models, set `defaultProvider: anthropic` in
> `configs/sams.yaml` and export `ANTHROPIC_API_KEY`.

---

## Architecture

Seven subsystems communicate **only** over the Event Bus — no subsystem calls
another for state changes; they publish and subscribe. The spatial UI, logs, and
audit trail are all projections of that one event stream.

```
            Spatial UI (React + Three.js, WebSocket)
                          │
          ┌───────────────┴───────────────┐
   Integrations ◄──►   EVENT BUS   ◄──► Observability
   (GitHub/MCP/        (Redis-ready          (events, logs,
    webhooks)          in-memory)             metrics, traces)
                          │
                    ORCHESTRATOR  (scheduling, workflows, gating, recovery)
                    │         │         │
              Agent Runtime · Spatial Engine · Vault (code, artifacts, memory)
```

| Package | Role |
|---|---|
| `sams/core` | Event Bus, event model, ids — the asynchronous backbone. |
| `sams/sdk` | Agent SDK: base `Agent`, manifest schema, `@capability`/`@hook`/`@tool`, registries. |
| `sams/runtime` | Agent Runtime — the execution sandbox; tool calls + lifecycle + telemetry. |
| `sams/orchestrator` | Scheduling, task assignment, `.flow` workflow engine, triggers, backpressure. |
| `sams/spatial` | Spatial Engine — rooms, primitives, scene graph, live event-driven placement. |
| `sams/vault` | Versioned storage + long-term (vector) memory. |
| `sams/kanban` | The shared task board (cards / columns), GitHub-syncable. |
| `sams/security` | Deny-by-default permissions, **Development Mode**, the Security Gate. |
| `sams/providers` | Pluggable LLM adapters (`mock` / `anthropic` / `openai` / `google` / `local`). |
| `sams/integrations` | GitHub Projects sync, MCP connector, webhooks. |
| `sams/tools` | The built-in tool namespace (spec §19.2). |
| `sams/chat` | Threads, messaging, and the context-aware AI Assistant. |
| `sams/api` | FastAPI REST + WebSocket control plane. |
| `sams/platform.py` | The kernel that wires it all together. |

---

## The agent catalog

36 built-in agents across 9 categories ship in `agents/builtin/`. Only **Hex** and
**Aegis** can approve gated changes — a deliberate separation-of-duties choice.

| Category | Agents |
|---|---|
| Core / Orchestration | Atlas, Sentinel, Concierge |
| Engineering | Opus, Pixel, Hex, Nova, Rune, Conduit, Cipher |
| Research | Scribe, Sage, Beacon |
| Design | Muse, Hermes, Palette |
| Product | Compass, Tally, Quill |
| Data | Ledger, Prism, Oracle |
| QA | Probe, Gauntlet |
| DevOps | Forge, Watchtower, Tinker |
| Security | Aegis, Warden |
| Comms / Content / Utility | Echo, Relay, Quote, Spotlight, Janitor, Courier, Linguist |

---

## Extending SAMS (zero core changes)

An agent is a declarative **manifest** plus an optional code **handler**. See the
worked example in `agents/custom/`:

```bash
sams agent validate agents/custom/seo-agent.agent.yaml
sams agent add agents/custom/seo-agent.agent.yaml      # hot — no restart
```

* **Manifest** (`seo-agent.agent.yaml`) — composes capabilities, tools, permissions, home.
* **Handler** (`seo_agent.py`) — adds a *brand-new* capability `content.seo_audit`.
* **Capability packs** (`packs/accessibility-pack/`) — install onto any agent.
* **Routing triggers** — label a card `seo` and the Orchestrator routes work automatically.

This is the mechanism that guarantees SAMS can grow indefinitely. See spec §6.

---

## Development Mode (full autonomy in dev)

In the `dev` environment SAMS defaults to **Development Mode**: every Security
Gate auto-passes, agents get full scope, and nothing prompts for confirmation —
so the build loop never stops. It is **scoped to `dev` only**; `staging`/`prod`
keep the strict deny-by-default model, approval gates, and confirmations. See
`configs/permissions.yaml` and spec §12.6.

```
Gates: auto · Permissions: all · Confirmations: off
```

Everything is still observable — auto-approvals are logged to the audit trail.

---

## Configuration

Three versioned YAML files in `configs/`:

* `sams.yaml` — spaces, event bus, vault, limits, providers, MCP.
* `agents.yaml` — the fleet roster (empty list = spawn the whole catalog).
* `permissions.yaml` — access policy + Development Mode.

---

## API

* **REST** — `/api/v1/{agents,spaces,tasks,workflows,events,gates,threads,assistant,metrics,status}` (spec §11.1).
* **WebSocket** — `/api/v1/stream?space=main.space` streams a scene snapshot then live deltas, and accepts commands (spec §11.2).

```bash
curl -X POST localhost:8787/api/v1/workflows/code-review/run -d '{"payload":{"pr":128}}'
curl -X POST localhost:8787/api/v1/assistant/ask -d '{"prompt":"Summarize the plan"}'
curl localhost:8787/api/v1/metrics
```

---

## Tests

```bash
pip install -e ".[dev]"
pytest -q                    # 13 integration + unit tests
```

---

## Tech stack

Python 3.11+ · asyncio · FastAPI · Pydantic v2 · (Redis-ready) Event Bus ·
TypeScript · React · React-Three-Fiber / Three.js · WebSocket · Zustand.

Built to `SAMS_Documentation.md` — the authoritative specification.
