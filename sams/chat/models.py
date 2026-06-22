"""Thread and Message models (spec 13.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..core.ids import new_id


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Message:
    id: str = field(default_factory=lambda: new_id("message"))
    thread_id: str = ""
    anchor: dict[str, Any] = field(default_factory=dict)
    author: dict[str, str] = field(default_factory=dict)  # {type: human|agent, id}
    ts: str = field(default_factory=_now)
    body: str = ""
    mentions: list[str] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    reactions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.id,
            "thread_id": self.thread_id,
            "anchor": self.anchor,
            "author": self.author,
            "ts": self.ts,
            "body": self.body,
            "mentions": self.mentions,
            "context_refs": self.context_refs,
            "actions": self.actions,
            "reactions": self.reactions,
        }


@dataclass
class Thread:
    id: str = field(default_factory=lambda: new_id("thread"))
    anchor: dict[str, Any] = field(default_factory=lambda: {"type": "global", "id": "global"})
    title: str = ""
    participants: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.id,
            "anchor": self.anchor,
            "title": self.title,
            "participants": self.participants,
            "message_count": len(self.messages),
            "updated_at": self.updated_at,
        }
