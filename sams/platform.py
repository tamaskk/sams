"""The SAMS kernel — wires the seven subsystems together over the Event Bus.

This is the single object the API, CLI, and tests boot. It owns no business logic
of its own; it constructs each subsystem, connects them to the bus, loads the
catalog + roster, spawns the fleet, and starts the Orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .catalog.loader import load_builtin_manifests, load_custom_manifests
from .chat.service import ChatService
from .config.loader import load_config
from .config.models import SamsConfig
from .core.event_bus import EventBus, InMemoryEventBus, set_event_bus
from .integrations.github import GitHubSync
from .kanban.board import KanbanBoard
from .orchestrator.models import Task
from .orchestrator.orchestrator import Orchestrator
from .pipeline import PipelineController
from .providers.base import ProviderFactory
from .runtime.runner import AgentRuntime
from .sdk.manifest import AgentManifest
from .sdk.registry import AgentRegistry, CapabilityRegistry, ToolRegistry
from .security.gate import SecurityGate
from .security.permissions import PermissionEngine
from .spatial.engine import SpatialEngine
from .vault.store import LocalVault

log = logging.getLogger("sams.platform")


def _build_event_bus(config: SamsConfig) -> EventBus:
    backend = config.platform.eventBus.backend
    if backend in ("redis-streams", "nats"):
        try:
            from .core.redis_bus import RedisStreamsEventBus  # optional

            return RedisStreamsEventBus(config.platform.eventBus.redis_url)
        except Exception:  # noqa: BLE001
            log.warning("event-bus backend %s unavailable; using in-memory", backend)
    return InMemoryEventBus()


class SamsPlatform:
    def __init__(self, config: SamsConfig) -> None:
        self.config = config
        self.default_space = config.platform.defaultSpace

        # Import built-in tools for their registration side effects.
        import sams.tools  # noqa: F401

        # Event Bus — the backbone.
        self.event_bus: EventBus = _build_event_bus(config)
        set_event_bus(self.event_bus)

        # Storage & memory.
        vault_root = Path(config.workspace_root) / config.platform.vault.local_path
        self.vault = LocalVault(vault_root, self.event_bus, space=self.default_space)

        # Task board (persisted so cards survive restarts).
        kanban_state = Path(config.workspace_root) / ".sams" / "state" / "kanban.json"
        self.kanban = KanbanBoard(self.event_bus, space=self.default_space,
                                  repo="sams/spatial-os", storage_path=kanban_state)

        # Security.
        self.permissions = PermissionEngine(config)
        self.gate = SecurityGate(self.event_bus, self.permissions, space=self.default_space)

        # Providers, tools, agents.
        self.provider_factory = ProviderFactory(config)
        self.tool_registry = ToolRegistry.global_instance()
        self.capabilities = CapabilityRegistry()
        self.agent_registry = AgentRegistry(capabilities=self.capabilities)

        # Runtime + Orchestrator + Spatial Engine.
        self.runtime = AgentRuntime(
            config=config,
            event_bus=self.event_bus,
            vault=self.vault,
            kanban=self.kanban,
            gate=self.gate,
            permissions=self.permissions,
            provider_factory=self.provider_factory,
            tool_registry=self.tool_registry,
            agent_registry=self.agent_registry,
        )
        self.spatial = SpatialEngine(self.event_bus)
        self.orchestrator = Orchestrator(
            config=config,
            event_bus=self.event_bus,
            runtime=self.runtime,
            agent_registry=self.agent_registry,
            kanban=self.kanban,
            gate=self.gate,
            permissions=self.permissions,
            space=self.default_space,
        )
        self.github = GitHubSync(self.event_bus, self.kanban, space=self.default_space)
        self.chat = ChatService(
            self.event_bus, self.runtime, self.vault, self.capabilities, space=self.default_space
        )
        self.pipeline = PipelineController(
            self.event_bus, self.kanban, self.orchestrator, self.gate, space=self.default_space,
            storage_path=Path(config.workspace_root) / ".sams" / "state" / "pipeline_prompts.json",
        )

        self._booted = False

    # --- boot / shutdown -----------------------------------------------------
    async def boot(self, *, spawn_roster: bool = True) -> "SamsPlatform":
        if self._booted:
            return self
        await self.event_bus.start()

        # Spaces (from config) + live wiring. A `.spatial` asset overrides the
        # default office layout when present.
        for sp in self.config.platform.spaces:
            file = str(Path(self.config.workspace_root) / sp.file) if sp.file else None
            self.spatial.create_space(sp.id, file=file)
        if self.default_space not in self.spatial.spaces:
            self.spatial.create_space(self.default_space)
        # Restore persisted Kanban cards, then autosave on every board change.
        loaded = self.kanban.load()
        if loaded:
            log.info("restored %d kanban cards from disk", loaded)
        self.event_bus.subscribe("kanban.*", self._persist_kanban, name="kanban:persist")

        self.spatial.wire()
        self.github.wire()
        self.pipeline.wire()

        # Catalog + custom manifests into the registry.
        for manifest in load_builtin_manifests(self.config.workspace_root):
            self.agent_registry.add(manifest)
        for manifest in load_custom_manifests(self.config.workspace_root):
            self.agent_registry.add(manifest)

        await self.orchestrator.initialize()
        await self.orchestrator.start()

        if spawn_roster:
            await self._spawn_roster()

        # Re-arm Deployer validation gates lost on restart (Accept button) — done
        # AFTER spawning and defensively, so it can never keep agents offline.
        try:
            self.pipeline.rearm_pending()
        except Exception:  # noqa: BLE001
            log.exception("rearm_pending failed (non-fatal)")

        self._booted = True
        await self.event_bus.emit(
            "system.health",
            {"status": "All Systems Operational", "agents_online": len(self.runtime.instances()),
             "version": self.config.platform.version, "mode": self.config.permissions.mode},
            space=self.default_space,
        )
        log.info("SAMS booted: %d agents online", len(self.runtime.instances()))
        return self

    async def shutdown(self) -> None:
        await self.orchestrator.stop()
        await self.event_bus.stop()
        self._booted = False

    async def _persist_kanban(self, event=None) -> None:
        self.kanban.persist()

    async def _spawn_roster(self) -> None:
        from .sdk.manifest import load_manifest

        roster = self.config.roster.agents
        if not roster:
            # No explicit roster -> spawn the whole catalog (great for a demo).
            for agent_id in self.agent_registry.ids():
                manifest = self.agent_registry.get(agent_id)
                if manifest:
                    await self.spawn_agent(manifest)
            return

        for entry in roster:
            manifest: AgentManifest | None = None
            if entry.manifest:
                path = Path(self.config.workspace_root) / entry.manifest
                manifest = load_manifest(path)
                self.agent_registry.add(manifest)
            elif entry.ref:
                manifest = self.agent_registry.get(entry.ref)
            if manifest is None:
                log.warning("roster entry %s could not be resolved", entry.ref or entry.manifest)
                continue
            # Per-instance model override from the roster (spec 10.2).
            if entry.model:
                manifest.spec.model.provider = entry.model.get("provider", manifest.spec.model.provider)
                manifest.spec.model.name = entry.model.get("name", manifest.spec.model.name)
            await self.spawn_agent(manifest)

    # --- agent ops -----------------------------------------------------------
    async def spawn_agent(self, manifest: AgentManifest, *, space: str | None = None) -> Any:
        space = space or self.default_space
        if self.agent_registry.get(manifest.id) is None:
            self.agent_registry.add(manifest)
        agent = await self.runtime.spawn(manifest, space=space)
        self.orchestrator.register_spawned(agent.id)
        return agent

    async def spawn_type(self, ref: str, *, space: str | None = None) -> Any:
        """Spawn a (possibly additional) instance of an agent type by id.

        Used by the drag-from-palette UX: the first instance keeps the base id;
        further instances get a unique ``{ref}-N`` id and a cloned manifest, so
        multiple Developers/Testers/etc. can coexist.
        """
        base = self.agent_registry.get(ref)
        if base is None:
            raise KeyError(ref)
        if self.runtime.get(ref) is None:
            manifest = base
        else:
            n = 2
            while self.runtime.get(f"{ref}-{n}") is not None:
                n += 1
            doc = base.to_dict()
            doc["metadata"]["id"] = f"{ref}-{n}"
            doc["metadata"]["name"] = f"{base.name} {n}"
            manifest = AgentManifest.from_dict(doc, source=base.source)
        return await self.spawn_agent(manifest, space=space)

    async def despawn_agent(self, agent_id: str, *, space: str | None = None) -> None:
        await self.runtime.despawn(agent_id, space=space or self.default_space)
        self.agent_registry.capabilities.retract(agent_id)

    def list_agents(self, space: str | None = None) -> list[dict[str, Any]]:
        space = space or self.default_space
        scene = self.spatial.get_space(space)
        markers = scene.agents if scene else {}
        out = []
        for agent in self.runtime.instances():
            m = markers.get(agent.id)
            manifest = agent.manifest
            out.append({
                "agent_id": agent.id,
                "name": agent.name,
                "color": agent.color,
                "role": manifest.spec.role,
                "seniority": manifest.spec.seniority,
                "model": {"provider": manifest.spec.model.provider, "name": manifest.spec.model.name},
                "capabilities": manifest.capabilities,
                "tools": manifest.spec.tools,
                "permissions": {"approve": manifest.can_approve,
                                "environments": manifest.spec.permissions.environments},
                "state": m.state if m else "idle",
                "home": {"primitive": manifest.spec.home.primitive, "room": manifest.spec.home.room},
                "telemetry": m.telemetry if m else {},
            })
        return out

    # --- task / workflow / gate ops -----------------------------------------
    async def submit_task(self, title: str, *, capability: str | None = None, assignee: str | None = None,
                          inputs: dict[str, Any] | None = None, requires_gate: bool = False,
                          gate_approvers: list[str] | None = None, card_id: str | None = None) -> Task:
        task = Task(
            title=title, capability=capability, assignee=assignee, inputs=inputs or {},
            space=self.default_space, requires_gate=requires_gate,
            gate_approvers=gate_approvers or [], card_id=card_id,
        )
        await self.orchestrator.submit(task)
        return task

    async def run_workflow(self, workflow_id: str, payload: dict[str, Any] | None = None) -> Any:
        return await self.orchestrator.run_workflow(workflow_id, payload)

    async def approve_gate(self, gate_id: str, approver: str = "human:lead") -> Any:
        return await self.gate.approve(gate_id, approver)

    # --- status --------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        return {
            "version": self.config.platform.version,
            "mode": self.config.permissions.mode,
            "environment": self.config.environment,
            "agents_online": len(self.runtime.instances()),
            "spaces": list(self.spatial.spaces.keys()),
            "posture": self.permissions.posture(),
            "events": getattr(self.event_bus, "event_count", 0),
            "pending_gates": len(self.gate.pending()),
        }


def build_platform(workspace_root: str = ".", *, environment: str | None = None,
                   mode: str | None = None) -> SamsPlatform:
    config = load_config(workspace_root, environment=environment, mode=mode)
    return SamsPlatform(config)
