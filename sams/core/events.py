"""The canonical event model.

Every meaningful change in SAMS is published as an :class:`Event`. Events are
immutable records; consumers must treat delivery as **at-least-once** and use
``idempotency_key`` to dedupe (spec 3.3, 6.10).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .ids import new_id


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Topic(str, Enum):
    """The typed top-level topics of the Event Bus (spec 3.3 / 11.3)."""

    AGENT = "agent"
    KANBAN = "kanban"
    VAULT = "vault"
    FLOW = "flow"
    SECURITY = "security"
    SPATIAL = "spatial"
    SYSTEM = "system"
    CHAT = "chat"
    CONTENT = "content"
    OPS = "ops"
    GIT = "git"
    SUPPORT = "support"


def topic_of(event_type: str) -> str:
    """Return the top-level topic of an event type (``kanban.card.moved`` -> ``kanban``)."""
    return event_type.split(".", 1)[0]


class Event(BaseModel):
    """An immutable record of something that happened, published to the bus.

    Mirrors the canonical event in spec 2.7 / 13.4.
    """

    id: str = Field(default_factory=lambda: new_id("event"))
    type: str
    ts: str = Field(default_factory=_utcnow_iso)
    actor: str | None = None
    space: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    idempotency_key: str | None = None

    @property
    def topic(self) -> str:
        return topic_of(self.type)

    def model_dump_event(self) -> dict[str, Any]:
        """JSON-safe dict for the wire (WebSocket / REST / logs)."""
        return self.model_dump(mode="json")
