"""The Orchestrator — scheduling, assignment, triggers, backpressure, recovery."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.events import Event
from .models import Task, WorkflowRun
from .workflows import WorkflowDefinition, WorkflowEngine, load_workflow

if TYPE_CHECKING:
    from ..config.models import SamsConfig
    from ..core.event_bus import EventBus
    from ..kanban.board import KanbanBoard
    from ..runtime.runner import AgentRuntime
    from ..sdk.registry import AgentRegistry
    from ..security.gate import SecurityGate
    from ..security.permissions import PermissionEngine

log = logging.getLogger("sams.orchestrator")

# Supported operators for routing-trigger `when` conditions.
_COND = re.compile(r"^\s*([\w.]+)\s*(==|!=|in)\s*(.+?)\s*$")


class Orchestrator:
    def __init__(
        self,
        *,
        config: "SamsConfig",
        event_bus: "EventBus",
        runtime: "AgentRuntime",
        agent_registry: "AgentRegistry",
        kanban: "KanbanBoard",
        gate: "SecurityGate",
        permissions: "PermissionEngine",
        space: str = "main.space",
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self.runtime = runtime
        self.agent_registry = agent_registry
        self.kanban = kanban
        self.gate = gate
        self.permissions = permissions
        self.space = space

        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._sem = asyncio.Semaphore(config.platform.limits.maxConcurrentAgents)
        self._load: dict[str, int] = {}
        self._spawned: set[str] = set()
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._trigger_index: dict[str, list[WorkflowDefinition]] = {}
        self._runs: dict[str, WorkflowRun] = {}
        self._tasks: dict[str, Task] = {}
        self._engine = WorkflowEngine(self, event_bus, gate, space=space)
        self._scheduler_task: asyncio.Task | None = None
        self._running = False

    # --- lifecycle -----------------------------------------------------------
    async def initialize(self) -> None:
        self._load_workflows()
        self._wire_triggers()
        await self.event_bus.emit("system.health", {"component": "orchestrator", "status": "ready"},
                                  space=self.space)
        log.info("orchestrator initialized with %d workflows", len(self._workflows))

    async def start(self) -> None:
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(), name="orchestrator-scheduler")
        await self.event_bus.emit("system.started", {"component": "orchestrator"}, space=self.space)

    async def stop(self) -> None:
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    def register_spawned(self, agent_id: str) -> None:
        self._spawned.add(agent_id)
        self._load.setdefault(agent_id, 0)

    # --- workflows -----------------------------------------------------------
    def _load_workflows(self) -> None:
        wf_dir = Path(self.config.workspace_root) / "workflows"
        if not wf_dir.exists():
            return
        for f in sorted(wf_dir.glob("*.flow")):
            try:
                defn = load_workflow(f)
                self._workflows[defn.id] = defn
            except Exception:  # noqa: BLE001
                log.exception("failed to load workflow %s", f)

    def workflows(self) -> list[WorkflowDefinition]:
        return list(self._workflows.values())

    def runs(self) -> list[WorkflowRun]:
        return list(self._runs.values())

    async def run_workflow(self, workflow_id: str, payload: dict[str, Any] | None = None) -> WorkflowRun:
        defn = self._workflows.get(workflow_id)
        if defn is None:
            raise KeyError(f"no workflow {workflow_id}")
        run = await self._engine.run(defn, payload)
        self._runs[run.run_id] = run
        return run

    # --- triggers ------------------------------------------------------------
    def _wire_triggers(self) -> None:
        trigger_types: set[str] = set()
        for defn in self._workflows.values():
            on = defn.trigger.get("on")
            if on:
                self._trigger_index.setdefault(on, []).append(defn)
                trigger_types.add(on)
        # Agent routing triggers (manifest spec.routing.triggers).
        for manifest in self.agent_registry.all():
            for trig in manifest.spec.routing.triggers:
                trigger_types.add(trig.on)
        for t in trigger_types:
            self.event_bus.subscribe(t, self._on_trigger, name=f"orch-trigger:{t}")

    async def _on_trigger(self, event: Event) -> None:
        # Fire matching workflows.
        for defn in self._trigger_index.get(event.type, []):
            when = defn.trigger.get("when")
            if when and not self._cond(when, event):
                continue
            asyncio.create_task(self.run_workflow(defn.id, dict(event.payload)))
        # Fire matching agent routing triggers -> create a task for that agent.
        for manifest in self.agent_registry.all():
            for trig in manifest.spec.routing.triggers:
                if trig.on != event.type:
                    continue
                if trig.when and not self._cond(trig.when, event):
                    continue
                cap = manifest.capabilities[0] if manifest.capabilities else None
                await self.submit(Task(
                    title=f"{manifest.name}: {event.type}",
                    capability=cap,
                    assignee=manifest.id,
                    inputs=dict(event.payload),
                    space=event.space or self.space,
                ))

    def _cond(self, when: str, event: Event) -> bool:
        m = _COND.match(when)
        if not m:
            return False
        lhs, op, rhs = m.group(1), m.group(2), m.group(3).strip().strip("'\"")
        # lhs like "payload.label" -> resolve against the event
        value: Any = event
        for part in lhs.split("."):
            value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        if op == "==":
            return str(value) == rhs
        if op == "!=":
            return str(value) != rhs
        if op == "in":
            return rhs in (value or [])
        return False

    # --- scheduling ----------------------------------------------------------
    async def submit(self, task: Task) -> Task:
        self._tasks[task.id] = task
        await self.event_bus.emit("flow.task.queued", {"task": task.id, "title": task.title},
                                  space=task.space)
        await self._queue.put(task)
        return task

    def tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    async def _scheduler_loop(self) -> None:
        while self._running:
            try:
                task = await self._queue.get()
            except asyncio.CancelledError:
                break
            asyncio.create_task(self.assign_and_run(task))

    async def assign_and_run(self, task: Task) -> Task:
        """Assign a task to the best agent and run it to completion (with backpressure)."""
        self._tasks.setdefault(task.id, task)
        agent_id = self._pick_agent(task)
        if agent_id is None:
            task.status = "error"
            await self.event_bus.emit(
                "flow.task.unassignable",
                {"task": task.id, "capability": task.capability, "assignee": task.assignee},
                space=task.space,
            )
            return task
        agent = self.runtime.get(agent_id)
        assert agent is not None
        async with self._sem:  # backpressure: cap concurrent LLM-backed work
            self._load[agent_id] = self._load.get(agent_id, 0) + 1
            await self.event_bus.emit(
                "flow.task.assigned", {"task": task.id, "agent": agent_id, "title": task.title},
                space=task.space,
            )
            try:
                return await self.runtime.run_task(agent, task)
            finally:
                self._load[agent_id] = max(0, self._load.get(agent_id, 1) - 1)

    def _pick_agent(self, task: Task) -> str | None:
        # 1. explicit assignment
        if task.assignee and task.assignee in self._spawned:
            return task.assignee
        # 2. capability match
        candidates: list[str] = []
        if task.capability:
            providers = self.agent_registry.capabilities.providers_of(task.capability)
            candidates = [a for a in providers if a in self._spawned]
        if not candidates and not task.capability:
            candidates = list(self._spawned)
        if not candidates:
            return None
        # 3. tie-break: least loaded (idle preferred)
        return min(candidates, key=lambda a: self._load.get(a, 0))
