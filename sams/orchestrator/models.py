"""Data models shared between the Orchestrator and the Agent Runtime.

Kept logic-free so both packages can import them without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.ids import new_id


@dataclass
class Task:
    """A unit of work the Orchestrator assigns to an agent."""

    id: str = field(default_factory=lambda: new_id("run"))
    title: str = ""
    capability: str | None = None
    assignee: str | None = None  # agent_id; None -> route by capability
    inputs: dict[str, Any] = field(default_factory=dict)
    space: str = "main.space"
    priority: str = "normal"
    labels: list[str] = field(default_factory=list)
    card_id: str | None = None
    requires_gate: bool = False
    gate_approvers: list[str] = field(default_factory=list)
    gate_policy: str = "all"
    produced_by: str | None = None
    status: str = "queued"  # queued | assigned | working | blocked | complete | error
    trace_id: str | None = None
    result: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "capability": self.capability,
            "assignee": self.assignee,
            "status": self.status,
            "card_id": self.card_id,
            "priority": self.priority,
            "labels": self.labels,
            "requires_gate": self.requires_gate,
        }


@dataclass
class WorkflowStep:
    id: str
    capability: str | None = None
    agent: str | None = None
    kind: str = "task"  # task | approval
    inputs: dict[str, Any] = field(default_factory=dict)
    parallel: bool = False
    requires: list[str] = field(default_factory=list)
    approvers: list[str] = field(default_factory=list)
    policy: str = "all"
    status: str = "pending"  # pending | running | complete | blocked | error
    result: Any = None


@dataclass
class WorkflowRun:
    run_id: str
    workflow: str
    trigger: dict[str, Any]
    space: str = "main.space"
    status: str = "running"  # running | awaiting_approval | complete | error
    steps: list[WorkflowStep] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "trigger": self.trigger,
            "status": self.status,
            "steps": [
                {"id": s.id, "agent": s.agent, "status": s.status, "kind": s.kind}
                for s in self.steps
            ],
            "outputs": self.outputs,
        }
