"""The Agent Runtime implementation.

Implements :class:`~sams.sdk.agent.AgentServices`, so it is what gets injected
into every :class:`~sams.sdk.agent.Agent`. Responsibilities:

* **spawn / despawn** agents from manifests (resolving code-backed handlers),
* **call_tool** with permission enforcement + lifecycle hooks + events,
* **run_task** — drive a single task through assigned -> working -> (gate?) ->
  complete, emitting telemetry the spatial UI consumes.

It is purely event-emitting; the Spatial Engine and Observability layers are
subscribers, never called directly (spec design principle #3).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..core.events import Event
from ..core.ids import new_id
from ..sdk.agent import Agent, AgentContext
from ..security.permissions import PermissionDenied

if TYPE_CHECKING:
    from ..config.models import SamsConfig
    from ..core.event_bus import EventBus
    from ..kanban.board import KanbanBoard
    from ..providers.base import ProviderFactory
    from ..sdk.manifest import AgentManifest
    from ..sdk.registry import AgentRegistry, ToolRegistry
    from ..security.gate import SecurityGate
    from ..security.permissions import PermissionEngine
    from ..vault.store import Vault
    from .models import Task

log = logging.getLogger("sams.runtime")


# Artifact destination by capability family.
_ARTIFACT_DIR = {
    "code": "src",
    "research": "docs/research",
    "design": "boards",
    "plan": "docs/specs",
    "data": "data",
    "content": "content",
    "qa": "tests",
    "security": "security",
    "ops": "ops",
}
_ARTIFACT_EXT = {"code": "py", "design": "md", "data": "json"}


class AgentRuntime:
    def __init__(
        self,
        *,
        config: "SamsConfig",
        event_bus: "EventBus",
        vault: "Vault",
        kanban: "KanbanBoard",
        gate: "SecurityGate",
        permissions: "PermissionEngine",
        provider_factory: "ProviderFactory",
        tool_registry: "ToolRegistry",
        agent_registry: "AgentRegistry",
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self.vault = vault
        self.kanban = kanban
        self.gate = gate
        self.permissions = permissions
        self.provider_factory = provider_factory
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry
        self.workspace_root = config.workspace_root
        self._instances: dict[str, Agent] = {}

    # --- AgentServices: provider + tools ------------------------------------
    def provider_for(self, manifest: "AgentManifest") -> Any:
        return self.provider_factory.provider_for(manifest)

    async def call_tool(self, agent: Agent, tool_id: str, *args: Any, **kwargs: Any) -> Any:
        # Permission enforcement (deny-by-default; bypassed only by Dev Mode grant-all).
        try:
            self.permissions.check_tool(agent.manifest, tool_id)
        except PermissionDenied:
            await self.event_bus.emit(
                "security.permission.denied",
                {"agent": agent.id, "tool": tool_id},
                actor=agent.id,
                space=agent.ctx.space,
            )
            raise

        spec = self.tool_registry.get(tool_id)
        if spec is None:
            raise KeyError(f"tool {tool_id} is not registered")

        await agent.run_hooks("on_tool_call", agent.ctx, tool_id, kwargs)
        await self.event_bus.emit(
            "agent.tool.called",
            {"tool": tool_id, "agent": agent.id},
            actor=agent.id,
            space=agent.ctx.space,
            trace_id=agent.ctx.trace_id,
        )
        return await spec.fn(agent.ctx, *args, **kwargs)

    # --- lifecycle -----------------------------------------------------------
    def get(self, agent_id: str) -> Agent | None:
        return self._instances.get(agent_id)

    def instances(self) -> list[Agent]:
        return list(self._instances.values())

    def instantiate(self, manifest: "AgentManifest") -> Agent:
        handler_cls = self.agent_registry.resolve_handler(manifest) or Agent
        agent = handler_cls(manifest, self)
        self._instances[manifest.id] = agent
        return agent

    async def spawn(self, manifest: "AgentManifest", *, space: str) -> Agent:
        agent = self.instantiate(manifest)
        ctx = AgentContext(agent=agent, services=self, space=space, trace_id=new_id("trace"))
        agent.bind_context(ctx)

        await self.event_bus.emit(
            "agent.spawned",
            {
                "agent": agent.id,
                "name": agent.name,
                "color": agent.color,
                "home": manifest.spec.home.primitive,
                "role": manifest.spec.role,
                "state": "initializing",
            },
            actor=agent.id,
            space=space,
        )
        await agent.run_hooks("on_spawn", ctx)
        await self._set_state(agent, "idle", space)
        return agent

    async def despawn(self, agent_id: str, *, space: str) -> None:
        agent = self._instances.pop(agent_id, None)
        if agent is None:
            return
        await agent.run_hooks("on_despawn", agent.ctx)
        await self.event_bus.emit("agent.despawned", {"agent": agent_id}, actor=agent_id, space=space)

    # --- task execution ------------------------------------------------------
    async def run_task(self, agent: Agent, task: "Task") -> "Task":
        ctx = agent.ctx
        ctx.task = task
        ctx.trace_id = task.trace_id or ctx.trace_id
        try:
            task.status = "assigned"
            await self._set_state(agent, "assigned", task.space, {"current_task": task.title})
            await agent.run_hooks("on_assign", ctx, task)

            task.status = "working"
            await self._set_state(
                agent, "working", task.space,
                {"current_task": task.title, "progress": 0.1, "model": agent.manifest.spec.model.name},
            )
            await agent.run_hooks("on_start", ctx)

            # Do the work: a code-backed capability handler if present, else the
            # default think-and-produce-artifact path (works for declarative agents).
            if task.capability and agent.has_handler_for(task.capability):
                task.result = await agent.invoke_capability(task.capability, ctx, **task.inputs)
            else:
                task.result = await self._default_work(agent, task, ctx)

            # Gate the work if required (no-op under Development Mode auto-approve).
            if task.requires_gate:
                approved = await self._gate(agent, task, ctx)
                if not approved:
                    task.status = "error"
                    await self._set_state(agent, "error", task.space)
                    return task

            if task.card_id:
                await self.kanban.update(task.card_id, progress=1.0, actor=agent.id)

            task.status = "complete"
            await agent.run_hooks("on_complete", ctx)
            await self.event_bus.emit(
                "agent.task.completed",
                {"agent": agent.id, "task": task.id, "title": task.title, "result": _summary(task.result)},
                actor=agent.id, space=task.space, trace_id=ctx.trace_id,
            )
            await self._set_state(agent, "complete", task.space, {"progress": 1.0})
            await self._set_state(agent, "idle", task.space)
            return task
        except Exception as exc:  # noqa: BLE001 - recoverable; Sentinel handles reassignment
            log.exception("task %s failed on %s", task.id, agent.id)
            task.status = "error"
            await agent.run_hooks("on_error", ctx, exc)
            await self.event_bus.emit(
                "agent.error", {"agent": agent.id, "task": task.id, "error": str(exc)},
                actor=agent.id, space=task.space,
            )
            await self._set_state(agent, "error", task.space)
            return task

    async def _default_work(self, agent: Agent, task: "Task", ctx: AgentContext) -> dict[str, Any]:
        # Recall relevant long-term memory, then reason about the task.
        memories = await self.vault.memory.query(task.title, agent=agent.id, space=task.space, k=3)
        mem_context = "\n".join(f"- {m.text[:160]}" for m in memories) or None

        thought = await agent.think(
            f"Task: {task.title}\nInputs: {task.inputs}\nDeliver the work for your role.",
            context=mem_context,
        )
        await self.event_bus.emit(
            "agent.progress", {"agent": agent.id, "progress": 0.5},
            actor=agent.id, space=task.space, trace_id=ctx.trace_id,
        )

        family = (task.capability or "content").split(".", 1)[0]
        ext = _ARTIFACT_EXT.get(family, "md")
        slug = ctx.slug(task.title)[:40]
        path = f"vault://{_ARTIFACT_DIR.get(family, 'work')}/{slug}.{ext}"
        uri = await self.vault.write(path, thought.markdown, actor=agent.id)

        # Persist a memory of what was done so future tasks can recall it.
        await self.vault.memory.write(
            f"{agent.name} completed: {task.title} -> {uri}",
            agent=agent.id, scope=agent.manifest.spec.memory.scope, space=task.space,
        )

        await self._set_state(
            agent, "working", task.space,
            {
                "progress": 0.9,
                "current_file": uri,
                "tokens_in": thought.tokens_in,
                "tokens_out": thought.tokens_out,
                "context_window": {"used": thought.tokens_in + thought.tokens_out,
                                   "max": self.config.platform.limits.maxContextWindow},
            },
        )
        return {"artifact": uri, "summary": thought.text[:240]}

    async def _gate(self, agent: Agent, task: "Task", ctx: AgentContext) -> bool:
        req = await self.gate.request(
            kind="approval",
            summary=task.title,
            payload={"task": task.id, "result": _summary(task.result), "branch": f"feature/{ctx.slug(task.title)[:24]}"},
            approvers=task.gate_approvers or ["human:lead"],
            policy=task.gate_policy,
            produced_by=agent.id,
            actor=agent.id,
            trace_id=ctx.trace_id,
        )
        if req.status == "approved":  # Development Mode auto-approved instantly
            return True
        task.status = "blocked"
        await self._set_state(agent, "blocked", task.space)
        await agent.run_hooks("on_gate", ctx, req)
        status = await self.gate.wait(req.id)
        return status == "approved"

    # --- helpers -------------------------------------------------------------
    async def _set_state(self, agent: Agent, state: str, space: str,
                         telemetry: dict[str, Any] | None = None) -> None:
        await self.event_bus.emit(
            "agent.state.changed",
            {"agent": agent.id, "state": state, "telemetry": telemetry or {}},
            actor=agent.id, space=space, trace_id=agent.ctx.trace_id,
        )


def _summary(result: Any) -> Any:
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        return result[:240]
    return result
