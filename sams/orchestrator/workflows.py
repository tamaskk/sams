"""Declarative multi-agent workflows (`.flow` files) — spec 8.1.

A workflow has a trigger, ordered steps (each a capability + optional agent, or an
approval gate), and outputs. Steps may declare ``requires`` (dependencies) and
``parallel``. Variable interpolation resolves ``${trigger.payload.pr}`` and
``${steps.<id>.result}``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.ids import new_id
from ..core.yamlutil import safe_load as yaml_safe_load
from .models import Task, WorkflowRun, WorkflowStep

if TYPE_CHECKING:
    from ..core.event_bus import EventBus
    from ..security.gate import SecurityGate
    from .orchestrator import Orchestrator

log = logging.getLogger("sams.workflows")

_VAR = re.compile(r"\$\{([^}]+)\}")


@dataclass
class WorkflowDefinition:
    id: str
    name: str
    trigger: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    on_error: dict[str, Any] = field(default_factory=dict)
    source: str | None = None

    @classmethod
    def from_dict(cls, doc: dict[str, Any], *, source: str | None = None) -> "WorkflowDefinition":
        meta = doc.get("metadata", {})
        spec = doc.get("spec", doc)
        return cls(
            id=meta.get("id") or spec.get("id", "workflow"),
            name=meta.get("name", meta.get("id", "Workflow")),
            trigger=spec.get("trigger", {}),
            steps=spec.get("steps", []),
            outputs=spec.get("outputs", {}),
            on_error=spec.get("onError", {}),
            source=source,
        )


def load_workflow(path: str | Path) -> WorkflowDefinition:
    p = Path(path)
    doc = yaml_safe_load(p.read_text())
    return WorkflowDefinition.from_dict(doc, source=str(p))


def _resolve(value: Any, ctx: dict[str, Any]) -> Any:
    """Interpolate ``${...}`` references against the run context."""
    if isinstance(value, str):
        m = _VAR.fullmatch(value.strip())
        if m:  # whole-string reference keeps native type
            return _lookup(m.group(1), ctx)
        return _VAR.sub(lambda mm: str(_lookup(mm.group(1), ctx)), value)
    if isinstance(value, dict):
        return {k: _resolve(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, ctx) for v in value]
    return value


def _lookup(path: str, ctx: dict[str, Any]) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


class WorkflowEngine:
    def __init__(
        self,
        orchestrator: "Orchestrator",
        event_bus: "EventBus",
        gate: "SecurityGate",
        *,
        space: str = "main.space",
    ) -> None:
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.gate = gate
        self.space = space

    async def run(self, defn: WorkflowDefinition, trigger_payload: dict[str, Any] | None = None) -> WorkflowRun:
        trace_id = new_id("trace")
        run = WorkflowRun(
            run_id=new_id("run"),
            workflow=defn.id,
            trigger={"type": defn.trigger.get("on"), **(trigger_payload or {})},
            space=self.space,
            trace_id=trace_id,
            steps=[
                WorkflowStep(
                    id=s["id"],
                    capability=s.get("capability"),
                    agent=s.get("agent"),
                    kind=s.get("kind", "approval" if s.get("approvers") else "task"),
                    inputs=s.get("inputs", {}),
                    parallel=s.get("parallel", False),
                    requires=s.get("requires", []),
                    approvers=s.get("approvers", []),
                    policy=s.get("policy", "all"),
                )
                for s in defn.steps
            ],
        )
        run_ctx: dict[str, Any] = {"trigger": run.trigger, "steps": {}}

        await self.event_bus.emit(
            "flow.started", {"run_id": run.run_id, "workflow": defn.id},
            space=self.space, trace_id=trace_id,
        )

        done: set[str] = set()
        remaining = {s.id: s for s in run.steps}
        try:
            while remaining:
                ready = [s for s in remaining.values() if set(s.requires) <= done]
                if not ready:
                    raise RuntimeError(f"workflow {defn.id} deadlocked; unmet requires")
                # Run all ready steps; parallel steps truly concurrently.
                import asyncio

                results = await asyncio.gather(
                    *(self._run_step(s, run, run_ctx) for s in ready)
                )
                for step, result in zip(ready, results):
                    run_ctx["steps"][step.id] = {"result": result}
                    done.add(step.id)
                    del remaining[step.id]

            run.outputs = _resolve(defn.outputs, run_ctx)
            run.status = "complete"
            await self.event_bus.emit(
                "flow.completed", {"run_id": run.run_id, "workflow": defn.id, "outputs": run.outputs},
                space=self.space, trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            run.status = "error"
            log.exception("workflow %s failed", defn.id)
            notify = defn.on_error.get("notify", [])
            await self.event_bus.emit(
                "flow.error", {"run_id": run.run_id, "workflow": defn.id, "error": str(exc), "notify": notify},
                space=self.space, trace_id=trace_id,
            )
        return run

    async def _run_step(self, step: WorkflowStep, run: WorkflowRun, run_ctx: dict[str, Any]) -> Any:
        step.status = "running"
        await self.event_bus.emit(
            "flow.step.started", {"run_id": run.run_id, "step": step.id, "agent": step.agent},
            space=self.space, trace_id=run.trace_id,
        )
        if step.kind == "approval":
            req = await self.gate.request(
                kind="approval",
                summary=f"{run.workflow} · {step.id}",
                payload={"run_id": run.run_id, "step": step.id},
                approvers=step.approvers,
                policy=step.policy,
                produced_by=None,
                trace_id=run.trace_id,
            )
            status = req.status if req.status != "pending" else await self.gate.wait(req.id)
            step.status = "complete" if status == "approved" else "error"
            step.result = {"gate": req.id, "status": status}
            if status != "approved":
                raise RuntimeError(f"gate {req.id} not approved ({status})")
        else:
            inputs = _resolve(step.inputs, run_ctx)
            task = Task(
                title=f"{run.workflow}: {step.id}",
                capability=step.capability,
                assignee=step.agent,
                inputs=inputs if isinstance(inputs, dict) else {"value": inputs},
                space=self.space,
                trace_id=run.trace_id,
            )
            completed = await self.orchestrator.assign_and_run(task)
            step.status = completed.status
            step.result = completed.result
            if completed.status == "error":
                raise RuntimeError(f"step {step.id} failed")

        await self.event_bus.emit(
            "flow.step.completed", {"run_id": run.run_id, "step": step.id, "status": step.status},
            space=self.space, trace_id=run.trace_id,
        )
        return step.result
