"""SAMS — Spatial Agentic Management System.

"The Sims for managing AI agents." A spatially-native platform for building,
operating, and orchestrating fleets of autonomous AI agents inside a living,
isometric visual workspace.

The package is organized into the seven subsystems described in the spec
(Section 3), all communicating over the Event Bus:

    core          Event Bus, events, ids — the asynchronous backbone.
    sdk           Agent SDK: base Agent, manifest schema, decorators, registries.
    runtime       Agent Runtime: the execution sandbox where agents run.
    orchestrator  Scheduling, workflow execution, gating, backpressure, recovery.
    spatial       Spatial Engine: rooms, primitives, scene graph.
    vault         Versioned storage + long-term memory.
    kanban        The task board (cards / columns), GitHub-syncable.
    security      Security Gate + deny-by-default permissions + Development Mode.
    providers     Pluggable LLM provider adapters (mock / anthropic / openai / ...).
    integrations  External systems (GitHub, MCP, webhooks) as tools + events.
    tools         Built-in tool implementations.
    api           FastAPI REST + WebSocket control plane.
    catalog       The built-in agent catalog loader.

The top-level kernel that wires everything together is :class:`sams.platform.SamsPlatform`.
"""

__version__ = "0.9.0"
__all__ = ["__version__"]
