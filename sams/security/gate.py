"""The Security Gate — the enforced checkpoint between work and consequence.

No merge to a protected branch and no deploy to a protected environment happens
without passing the gate (spec 12.1). Supports ``all`` / ``any`` / ``quorum(n)``
policies and records every decision in the audit trail.

In Development Mode the gate becomes a **no-op**: ``security.gate.requested`` is
immediately followed by ``security.gate.approved`` with ``approver:
"auto:dev-mode"`` — still logged (12.6).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..core.ids import new_id

if TYPE_CHECKING:
    from ..core.event_bus import EventBus
    from .permissions import PermissionEngine

log = logging.getLogger("sams.gate")

_QUORUM = re.compile(r"quorum\((\d+)\)")


@dataclass
class GateRequest:
    id: str
    kind: str
    summary: str
    payload: dict[str, Any]
    approvers: list[str]
    policy: str
    produced_by: str | None
    space: str
    trace_id: str | None
    status: str = "pending"  # pending | approved | rejected
    decisions: dict[str, str] = field(default_factory=dict)  # approver -> approve|reject
    comments: list[dict[str, Any]] = field(default_factory=list)
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "summary": self.summary,
            "payload": self.payload,
            "approvers": self.approvers,
            "policy": self.policy,
            "produced_by": self.produced_by,
            "status": self.status,
            "decisions": self.decisions,
            "comments": self.comments,
        }


class SecurityGate:
    def __init__(
        self,
        event_bus: "EventBus",
        permissions: "PermissionEngine",
        *,
        space: str = "main.space",
    ) -> None:
        self.event_bus = event_bus
        self.permissions = permissions
        self.space = space
        self._gates: dict[str, GateRequest] = {}

    def get(self, gate_id: str) -> GateRequest | None:
        return self._gates.get(gate_id)

    def pending(self) -> list[GateRequest]:
        return [g for g in self._gates.values() if g.status == "pending"]

    def all(self) -> list[GateRequest]:
        return list(self._gates.values())

    async def request(
        self,
        *,
        kind: str = "approval",
        summary: str = "",
        payload: dict[str, Any] | None = None,
        approvers: list[str] | None = None,
        policy: str = "all",
        produced_by: str | None = None,
        actor: str | None = None,
        trace_id: str | None = None,
        force_manual: bool = False,
    ) -> GateRequest:
        req = GateRequest(
            id=new_id("gate"),
            kind=kind,
            summary=summary,
            payload=payload or {},
            approvers=approvers or ["human:lead"],
            policy=policy,
            produced_by=produced_by,
            space=self.space,
            trace_id=trace_id,
        )
        self._gates[req.id] = req
        await self.event_bus.emit(
            "security.gate.requested",
            {"gate_id": req.id, "kind": kind, "summary": summary, "approvers": req.approvers,
             "policy": policy, "produced_by": produced_by},
            actor=actor,
            space=self.space,
            trace_id=trace_id,
        )

        # Development Mode: gate is a no-op — auto-approve, still logged.
        # `force_manual` opts a gate out of auto-approve (e.g. the deploy
        # validation the human must accept explicitly), even in dev.
        if self.permissions.auto_approve and not force_manual:
            req.status = "approved"
            req.decisions["auto:dev-mode"] = "approve"
            req._event.set()
            await self.event_bus.emit(
                "security.gate.approved",
                {"gate_id": req.id, "approver": "auto:dev-mode", "auto": True},
                actor="auto:dev-mode",
                space=self.space,
                trace_id=trace_id,
            )
        return req

    async def approve(self, gate_id: str, approver: str) -> GateRequest:
        req = self._require(gate_id)
        if self.permissions.self_approval_blocked_for(approver, req.produced_by):
            raise PermissionError(
                f"{approver} cannot approve its own gated work (separation of duties)"
            )
        req.decisions[approver] = "approve"
        await self.event_bus.emit(
            "security.gate.vote", {"gate_id": gate_id, "approver": approver, "vote": "approve"},
            actor=approver, space=self.space, trace_id=req.trace_id,
        )
        if self._policy_met(req):
            req.status = "approved"
            req._event.set()
            await self.event_bus.emit(
                "security.gate.approved", {"gate_id": gate_id, "approver": approver},
                actor=approver, space=self.space, trace_id=req.trace_id,
            )
        return req

    async def reject(self, gate_id: str, approver: str, comment: str = "") -> GateRequest:
        req = self._require(gate_id)
        req.decisions[approver] = "reject"
        if comment:
            req.comments.append({"by": approver, "body": comment})
        req.status = "rejected"
        req._event.set()
        await self.event_bus.emit(
            "security.gate.rejected",
            {"gate_id": gate_id, "approver": approver, "comment": comment},
            actor=approver, space=self.space, trace_id=req.trace_id,
        )
        return req

    async def wait(self, gate_id: str, *, timeout: float | None = None) -> str:
        """Block until the gate resolves; returns ``approved`` / ``rejected``."""
        req = self._require(gate_id)
        if timeout:
            await asyncio.wait_for(req._event.wait(), timeout)
        else:
            await req._event.wait()
        return req.status

    # --- internals -----------------------------------------------------------
    def _require(self, gate_id: str) -> GateRequest:
        req = self._gates.get(gate_id)
        if req is None:
            raise KeyError(f"no gate {gate_id}")
        return req

    def _policy_met(self, req: GateRequest) -> bool:
        approvals = [a for a, v in req.decisions.items() if v == "approve"]
        if req.policy == "any":
            return len(approvals) >= 1
        m = _QUORUM.match(req.policy)
        if m:
            return len(approvals) >= int(m.group(1))
        # default "all": every named approver approved
        return all(req.decisions.get(a) == "approve" for a in req.approvers)
