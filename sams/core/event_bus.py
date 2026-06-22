"""The Event Bus — the asynchronous publish/subscribe backbone of SAMS.

The bus provides:

* **At-least-once delivery** with per-consumer idempotency dedupe.
* **Ordered per consumer** — each subscription processes events in publish order.
* **Replayable** — a retained history lets the spatial UI and audit log be
  reconstructed (spec 3.3, 14.4).
* **Typed topics** — ``agent.*``, ``kanban.*``, ``vault.*``, ``flow.*``,
  ``security.*``, ``spatial.*``, ``system.*``, ``chat.*``.
* **Consumer groups** — competing consumers load-balance a stream.

The reference implementation here is fully in-memory so SAMS runs with zero
external infrastructure. It is interface-compatible with a Redis Streams /
NATS JetStream backend (see :mod:`sams.core.redis_bus`); the platform selects a
backend by ``eventBus.backend`` in ``sams.yaml`` and the rest of the system is
none the wiser — "any component can be replaced as long as it speaks the Event
Bus contract" (spec 3.9).
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Awaitable, Callable

from .events import Event

log = logging.getLogger("sams.eventbus")

Handler = Callable[[Event], Awaitable[None]]


def _matches(pattern: str, event_type: str) -> bool:
    """``agent.*`` matches ``agent.spawned``; ``*`` matches everything."""
    if pattern in ("*", "**", ""):
        return True
    # Allow both "agent" (topic) and "agent.*" forms.
    if "." not in pattern and "*" not in pattern:
        return event_type.split(".", 1)[0] == pattern
    return fnmatch.fnmatch(event_type, pattern)


class Subscription:
    """A live subscription. Process events from its own ordered queue."""

    def __init__(
        self,
        bus: "EventBus",
        pattern: str,
        handler: Handler,
        *,
        name: str,
        group: str | None = None,
    ) -> None:
        self.bus = bus
        self.pattern = pattern
        self.handler = handler
        self.name = name
        self.group = group
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self._seen: deque[str] = deque(maxlen=4096)
        self._seen_set: set[str] = set()
        self._task: asyncio.Task | None = None
        self.active = True

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name=f"sub:{self.name}")

    async def _run(self) -> None:
        while self.active:
            event = await self.queue.get()
            try:
                # Idempotency: skip events we've already handled (at-least-once).
                key = event.idempotency_key
                if key is not None:
                    if key in self._seen_set:
                        continue
                    if len(self._seen) == self._seen.maxlen:
                        self._seen_set.discard(self._seen[0])
                    self._seen.append(key)
                    self._seen_set.add(key)
                await self.handler(event)
            except asyncio.CancelledError:  # pragma: no cover - shutdown
                raise
            except Exception:  # noqa: BLE001 - one bad handler must not kill the stream
                log.exception("subscriber %s failed on %s", self.name, event.type)
            finally:
                self.queue.task_done()

    async def cancel(self) -> None:
        self.active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class EventBus(ABC):
    """The contract every Event Bus backend must satisfy."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def publish(self, event: Event) -> Event: ...

    @abstractmethod
    def subscribe(
        self, pattern: str, handler: Handler, *, name: str | None = None, group: str | None = None
    ) -> Subscription: ...

    @abstractmethod
    async def history(
        self,
        *,
        topic: str | None = None,
        actor: str | None = None,
        type: str | None = None,
        limit: int = 200,
    ) -> list[Event]: ...

    async def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        actor: str | None = None,
        space: str | None = None,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Event:
        """Convenience: build and publish an :class:`Event` in one call."""
        event = Event(
            type=type,
            payload=payload or {},
            actor=actor,
            space=space,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
        )
        return await self.publish(event)


class InMemoryEventBus(EventBus):
    """Fully in-memory bus: durable-within-process, replayable, ordered.

    Good for local/dev and tests. Swap for Redis Streams to get cross-process
    durability and replay across restarts.
    """

    def __init__(self, *, retention: int = 10000) -> None:
        self._subs: list[Subscription] = []
        self._groups_rr: dict[str, int] = {}
        self._history: deque[Event] = deque(maxlen=retention)
        self._running = False
        self._n = 0

    async def start(self) -> None:
        self._running = True
        log.info("event bus started (in-memory, retention=%d)", self._history.maxlen)

    async def stop(self) -> None:
        self._running = False
        for sub in list(self._subs):
            await sub.cancel()
        self._subs.clear()

    async def publish(self, event: Event) -> Event:
        self._n += 1
        self._history.append(event)
        # Fan out to every matching subscription, preserving order. Grouped
        # subscriptions act as competing consumers (one member per event).
        delivered_groups: dict[str, list[Subscription]] = {}
        for sub in self._subs:
            if not _matches(sub.pattern, event.type):
                continue
            if sub.group:
                delivered_groups.setdefault(sub.group, []).append(sub)
            else:
                sub.queue.put_nowait(event)
        for group, members in delivered_groups.items():
            idx = self._groups_rr.get(group, 0) % len(members)
            self._groups_rr[group] = idx + 1
            members[idx].queue.put_nowait(event)
        return event

    def subscribe(
        self, pattern: str, handler: Handler, *, name: str | None = None, group: str | None = None
    ) -> Subscription:
        sub = Subscription(
            self, pattern, handler, name=name or f"sub-{len(self._subs)}", group=group
        )
        self._subs.append(sub)
        if self._running:
            sub.start()
        else:
            # Start lazily on next start(); but since start() is usually called
            # first, start now if loop is running.
            try:
                asyncio.get_running_loop()
                sub.start()
            except RuntimeError:  # pragma: no cover
                pass
        return sub

    async def history(
        self,
        *,
        topic: str | None = None,
        actor: str | None = None,
        type: str | None = None,
        limit: int = 200,
    ) -> list[Event]:
        out: list[Event] = []
        for ev in reversed(self._history):
            if topic and ev.topic != topic:
                continue
            if actor and ev.actor != actor:
                continue
            if type and not _matches(type, ev.type):
                continue
            out.append(ev)
            if len(out) >= limit:
                break
        return list(reversed(out))

    @property
    def event_count(self) -> int:
        return self._n


_GLOBAL_BUS: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process-wide Event Bus (set by the platform on boot)."""
    global _GLOBAL_BUS
    if _GLOBAL_BUS is None:
        _GLOBAL_BUS = InMemoryEventBus()
    return _GLOBAL_BUS


def set_event_bus(bus: EventBus) -> None:
    global _GLOBAL_BUS
    _GLOBAL_BUS = bus
