"""GitHub / version-control integration (spec 9.2).

Provides bidirectional Kanban ↔ GitHub Projects sync and maps PR lifecycle
events onto the Event Bus so workflows can trigger. The reference implementation
keeps an in-process mirror (no network) and emits ``integration.github.*`` events;
a real deployment swaps the mirror for GitHub API calls behind the same surface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..core.events import Event

if TYPE_CHECKING:
    from ..core.event_bus import EventBus
    from ..kanban.board import KanbanBoard

log = logging.getLogger("sams.integrations.github")


class GitHubSync:
    def __init__(self, event_bus: "EventBus", kanban: "KanbanBoard", *,
                 space: str = "main.space", repo: str = "sams/spatial-os",
                 project: str = "SAMS Platform") -> None:
        self.event_bus = event_bus
        self.kanban = kanban
        self.space = space
        self.repo = repo
        self.project = project
        self._card_to_item: dict[str, int] = {}
        self._next_item = 128

    def wire(self) -> None:
        # Card changes -> GitHub Project items (outbound).
        self.event_bus.subscribe("kanban.card.created", self._on_card, name="github:card.created")
        self.event_bus.subscribe("kanban.card.moved", self._on_card, name="github:card.moved")
        # PR lifecycle is already on the bus (emitted by git.* tools); mirror status.
        self.event_bus.subscribe("git.pr.merged", self._on_pr_merged, name="github:pr.merged")

    async def _on_card(self, event: Event) -> None:
        card_id = event.payload.get("card_id")
        if not card_id:
            return
        item = self._card_to_item.get(card_id)
        if item is None:
            item = self._next_item
            self._next_item += 1
            self._card_to_item[card_id] = item
            card = self.kanban.get(card_id)
            if card:
                card.github_item = item
        await self.event_bus.emit(
            "integration.github.synced",
            {"repo": self.repo, "project": self.project, "card_id": card_id,
             "github_item": item, "status": event.payload.get("to", "synced")},
            space=self.space,
        )

    async def _on_pr_merged(self, event: Event) -> None:
        # Approved changes automatically sync to the Vault (spec 8.5).
        await self.event_bus.emit(
            "integration.github.pr.synced",
            {"pr": event.payload.get("pr"), "merged_to": "main", "synced_to_vault": True},
            space=self.space,
        )

    # --- inbound (a GitHub webhook becomes an event) -------------------------
    async def on_inbound(self, kind: str, payload: dict[str, Any]) -> None:
        """Translate an inbound GitHub webhook into a bus event."""
        mapping = {
            "pull_request.opened": "git.pr.opened",
            "pull_request.closed": "git.pr.merged",
            "push": "git.branch.pushed",
        }
        event_type = mapping.get(kind, f"git.{kind}")
        await self.event_bus.emit(event_type, payload, space=self.space)
