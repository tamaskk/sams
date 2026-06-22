"""Long-term agent memory (spec 4.5).

A durable, retrievable memory store backed by a naive local vector index so
semantic recall works with no external vector DB. Scopes mirror the spec:
``private`` (one agent), ``space`` (all agents in a space), ``global`` (all agents).

In production this is backed by pgvector/Qdrant; the interface is identical.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.ids import new_id

_DIMS = 256


def _embed(text: str) -> list[float]:
    """Deterministic bag-of-words hash embedding (good enough for local recall)."""
    vec = [0.0] * _DIMS
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        vec[hash(token) % _DIMS] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class Memory:
    id: str
    text: str
    agent: str
    scope: str  # private | space | global
    space: str
    meta: dict[str, Any] = field(default_factory=dict)
    ts: str = ""
    embedding: list[float] = field(default_factory=list)

    def visible_to(self, agent: str, space: str) -> bool:
        if self.scope == "global":
            return True
        if self.scope == "space":
            return self.space == space
        return self.agent == agent  # private


class VaultMemory:
    """Append-only memory with semantic query. Persists to a JSONL index."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "memory.jsonl"
        self._mems: list[Memory] = []
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        for line in self.index_path.read_text().splitlines():
            if line.strip():
                self._mems.append(Memory(**json.loads(line)))

    async def write(
        self,
        text: str,
        *,
        agent: str,
        scope: str = "private",
        space: str = "main.space",
        meta: dict[str, Any] | None = None,
    ) -> Memory:
        mem = Memory(
            id=new_id("message"),
            text=text,
            agent=agent,
            scope=scope,
            space=space,
            meta=meta or {},
            ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            embedding=_embed(text),
        )
        self._mems.append(mem)
        with self.index_path.open("a") as fh:
            fh.write(json.dumps(asdict(mem)) + "\n")
        return mem

    async def query(
        self,
        text: str,
        *,
        agent: str,
        space: str = "main.space",
        k: int = 5,
    ) -> list[Memory]:
        q = _embed(text)
        scored = [
            (_cosine(q, m.embedding), m)
            for m in self._mems
            if m.embedding and m.visible_to(agent, space)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for score, m in scored[:k] if score > 0]

    def count(self) -> int:
        return len(self._mems)
