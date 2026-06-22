"""The Kanban board, cards, and columns."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.ids import bump_card_counter, next_card_number

if TYPE_CHECKING:
    from ..core.event_bus import EventBus

log = logging.getLogger("sams.kanban")

# The board is a role pipeline: a task starts in To Do, then flows through each
# skill's column in order (Planner → Designer → Developer → Reviewer → Tester → Deployer).
COLUMNS = ["To Do", "Planner", "Designer", "Developer", "Reviewer", "Tester", "Deployer", "Committed"]


@dataclass
class ChecklistItem:
    item: str
    done: bool = False


@dataclass
class Card:
    id: str
    title: str
    status: str = "To Do"
    assignee: str | None = None
    labels: list[str] = field(default_factory=list)
    priority: str = "Medium"
    milestone: str | None = None
    progress: float = 0.0
    checklist: list[ChecklistItem] = field(default_factory=list)
    repo: str | None = None
    github_item: int | None = None
    description: str = ""
    project: str | None = None  # the working directory where the task is done
    # Pipeline state (the role-column automation):
    stage_status: str = "idle"  # idle | working | done | awaiting_validation | deploying | rejected | error
    outputs: dict[str, str] = field(default_factory=dict)  # column/stage -> agent output summary
    gate_id: str | None = None  # the human-validation gate when in Deployer
    image: str | None = None  # absolute path to an attached reference image (given to the agent)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "assignee": self.assignee,
            "labels": list(self.labels),
            "priority": self.priority,
            "milestone": self.milestone,
            "progress": self.progress,
            "checklist": [{"item": c.item, "done": c.done} for c in self.checklist],
            "repo": self.repo,
            "github_item": self.github_item,
            "description": self.description,
            "project": self.project,
            "stage_status": self.stage_status,
            "outputs": dict(self.outputs),
            "gate_id": self.gate_id,
            "image": self.image,
        }


class KanbanBoard:
    def __init__(self, event_bus: "EventBus | None" = None, *, space: str = "main.space",
                 repo: str | None = None, storage_path: str | Path | None = None) -> None:
        self.event_bus = event_bus
        self.space = space
        self.repo = repo
        self._cards: dict[str, Card] = {}
        self._storage = Path(storage_path) if storage_path else None

    # --- persistence ---------------------------------------------------------
    def persist(self) -> None:
        """Save the board to disk so cards survive a restart."""
        if not self._storage:
            return
        self._storage.parent.mkdir(parents=True, exist_ok=True)
        data = {"cards": [c.to_dict() for c in self._cards.values()]}
        tmp = self._storage.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._storage)

    def load(self) -> int:
        """Load cards from disk (called on boot). Returns the count loaded."""
        if not self._storage or not self._storage.exists():
            return 0
        try:
            data = json.loads(self._storage.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("could not read kanban state %s", self._storage)
            return 0
        for cd in data.get("cards", []):
            stage = cd.get("stage_status", "idle")
            # Work interrupted by the restart isn't really running any more.
            if stage in ("working", "deploying", "awaiting_validation"):
                stage = "idle"
            card = Card(
                id=cd["id"], title=cd.get("title", ""), status=cd.get("status", "To Do"),
                assignee=cd.get("assignee"), labels=list(cd.get("labels", [])),
                priority=cd.get("priority", "Medium"), milestone=cd.get("milestone"),
                progress=cd.get("progress", 0.0),
                checklist=[ChecklistItem(c["item"], c.get("done", False)) for c in cd.get("checklist", [])],
                repo=cd.get("repo"), github_item=cd.get("github_item"),
                description=cd.get("description", ""), project=cd.get("project"),
                stage_status=stage, outputs=dict(cd.get("outputs", {})), gate_id=None,
                image=cd.get("image"),
            )
            self._cards[card.id] = card
        bump_card_counter(self._cards.keys())
        return len(self._cards)

    # --- queries -------------------------------------------------------------
    def get(self, card_id: str) -> Card | None:
        return self._cards.get(card_id)

    def all(self) -> list[Card]:
        return list(self._cards.values())

    def by_column(self) -> dict[str, list[Card]]:
        cols: dict[str, list[Card]] = {c: [] for c in COLUMNS}
        for card in self._cards.values():
            cols.setdefault(card.status, []).append(card)
        return cols

    def with_label(self, label: str) -> list[Card]:
        return [c for c in self._cards.values() if label in c.labels]

    # --- mutations (all emit events) ----------------------------------------
    async def create(
        self,
        title: str,
        *,
        column: str = "To Do",
        labels: list[str] | None = None,
        assignee: str | None = None,
        priority: str = "Medium",
        milestone: str | None = None,
        checklist: list[str] | None = None,
        description: str = "",
        project: str | None = None,
        actor: str | None = None,
        card_id: str | None = None,
    ) -> Card:
        card = Card(
            id=card_id or next_card_number(),
            title=title,
            status=column,
            assignee=assignee,
            labels=labels or [],
            priority=priority,
            milestone=milestone,
            checklist=[ChecklistItem(c) for c in (checklist or [])],
            repo=self.repo,
            description=description,
            project=project,
        )
        self._cards[card.id] = card
        await self._emit("kanban.card.created", card, {"column": column}, actor)
        return card

    async def move(self, card_id: str, to: str, *, actor: str | None = None) -> Card:
        card = self._require(card_id)
        frm = card.status
        if frm == to:
            return card
        card.status = to
        await self._emit("kanban.card.moved", card, {"from": frm, "to": to}, actor)
        return card

    async def label(self, card_id: str, label: str, *, actor: str | None = None) -> Card:
        card = self._require(card_id)
        if label not in card.labels:
            card.labels.append(label)
        await self._emit("kanban.card.labeled", card, {"label": label}, actor)
        return card

    async def update(
        self,
        card_id: str,
        *,
        progress: float | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        milestone: str | None = None,
        check: str | None = None,
        actor: str | None = None,
    ) -> Card:
        card = self._require(card_id)
        if progress is not None:
            card.progress = max(0.0, min(1.0, progress))
        if assignee is not None:
            card.assignee = assignee
        if priority is not None:
            card.priority = priority
        if milestone is not None:
            card.milestone = milestone
        if check is not None:
            for item in card.checklist:
                if item.item == check:
                    item.done = True
        await self._emit("kanban.card.updated", card, {"progress": card.progress}, actor)
        return card

    async def edit(
        self,
        card_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        project: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
        assignee: str | None = None,
        milestone: str | None = None,
        actor: str | None = None,
    ) -> Card:
        """Update any subset of a card's editable fields (used by the edit modal)."""
        card = self._require(card_id)
        if title is not None:
            card.title = title
        if description is not None:
            card.description = description
        if project is not None:
            card.project = project or None
        if priority is not None:
            card.priority = priority
        if labels is not None:
            card.labels = list(labels)
        if assignee is not None:
            card.assignee = assignee or None
        if milestone is not None:
            card.milestone = milestone or None
        await self._emit("kanban.card.updated", card, {}, actor)
        return card

    async def delete(self, card_id: str, *, actor: str | None = None) -> bool:
        card = self._cards.pop(card_id, None)
        if card is None:
            return False
        if self.event_bus:
            await self.event_bus.emit(
                "kanban.card.deleted", {"card_id": card_id, "title": card.title},
                actor=actor, space=self.space,
            )
        return True

    # --- internals -----------------------------------------------------------
    def _require(self, card_id: str) -> Card:
        card = self._cards.get(card_id)
        if card is None:
            raise KeyError(f"no card {card_id}")
        return card

    async def _emit(self, type: str, card: Card, extra: dict[str, Any], actor: str | None) -> None:
        if not self.event_bus:
            return
        await self.event_bus.emit(
            type,
            {"card_id": card.id, "title": card.title, **extra},
            actor=actor,
            space=self.space,
        )
