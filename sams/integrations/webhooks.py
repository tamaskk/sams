"""Webhooks — inbound webhooks become events; outbound webhooks fire on events
(spec 9.4)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from ..core.events import Event

if TYPE_CHECKING:
    from ..core.event_bus import EventBus

log = logging.getLogger("sams.integrations.webhooks")


class WebhookRouter:
    def __init__(self, event_bus: "EventBus", *, space: str = "main.space") -> None:
        self.event_bus = event_bus
        self.space = space
        self.inbound: dict[str, str] = {}  # path -> emitted event type
        self.outbound: list[dict[str, str]] = []  # [{on, url}]

    def configure(self, config: dict[str, Any]) -> None:
        for item in config.get("inbound", []):
            self.inbound[item["path"]] = item["emits"]
        for item in config.get("outbound", []):
            self.outbound.append({"on": item["on"], "url": item["url"]})
        for hook in self.outbound:
            self.event_bus.subscribe(hook["on"], self._fire_outbound, name=f"webhook:{hook['on']}")

    async def receive(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_type = self.inbound.get(path)
        if not event_type:
            return {"ok": False, "reason": "unknown path"}
        await self.event_bus.emit(event_type, payload, space=self.space)
        return {"ok": True, "emitted": event_type}

    async def _fire_outbound(self, event: Event) -> None:
        for hook in self.outbound:
            if hook["on"] != event.type:
                continue
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(hook["url"], json=event.model_dump_event())
            except Exception as exc:  # noqa: BLE001 - best-effort notification
                log.warning("outbound webhook to %s failed: %s", hook["url"], exc)
