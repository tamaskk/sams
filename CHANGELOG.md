# Changelog

All notable changes to SAMS are documented here. The platform uses semver;
agents and packs are versioned independently and pinned in `agents.yaml`.

## [0.9.0] — "Spatial Mode" (pre-1.0)

Initial reference implementation built to `SAMS_Documentation.md`.

### Added
- **Event Bus** — in-memory, replayable, ordered-per-consumer, at-least-once with
  idempotency dedupe and consumer groups (Redis-Streams-ready interface).
- **Agent SDK** — base `Agent`, the canonical manifest schema, `@capability` /
  `@hook` / `@tool` decorators, tool/capability/agent registries, hot registration.
- **Agent Runtime** — spawn/despawn, permission-checked tool calls, the full
  lifecycle (assigned → working → gate → complete), and live telemetry.
- **Orchestrator** — capability-based scheduling, `.flow` workflow engine with
  parallel steps + approval gates + variable interpolation, event-driven triggers,
  backpressure, and a task registry.
- **Spatial Engine** — rooms, the eight primitive types, the scene graph, and live
  event-driven agent placement + primitive glow.
- **Vault** — versioned filesystem storage + long-term vector memory.
- **Kanban** — cards/columns with bidirectional GitHub Projects sync.
- **Security** — deny-by-default permissions, separation of duties, the Security
  Gate (`all`/`any`/`quorum`), and **Development Mode** (dev-only full autonomy).
- **Providers** — `mock` (offline), `anthropic`, and OpenAI-compatible adapters.
- **Integrations** — GitHub sync, MCP connector, webhooks.
- **Chat** — threads, messaging, routing, and the context-aware AI Assistant.
- **API** — FastAPI REST control plane + WebSocket real-time stream.
- **CLI** — `sams up/status/agent/flow/task/events`.
- **Catalog** — 36 built-in agents across 9 categories.
- **Spatial UI** — React + Three.js isometric workspace, IDE shell, minimap,
  Kanban board, command palette, console, and the full design-token system.
- **Tests** — 13 integration + unit tests.
