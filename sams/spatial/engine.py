"""The Spatial Engine: spaces, the default office layout, agent placement,
spatial commands, and live event-driven scene updates."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..core.events import Event
from .primitives import Appearance, Binding, Primitive, Room, Transform

if TYPE_CHECKING:
    from ..core.event_bus import EventBus

log = logging.getLogger("sams.spatial")

# Canonical office layout: primitive name -> grid position [x, y, z] in a 12x10 room.
DEFAULT_LAYOUT: list[tuple[str, str, list[float]]] = [
    ("Desk", "Desk 01", [2.0, 0.0, 2.0]),
    ("Desk", "Desk 02", [2.0, 0.0, 4.0]),
    ("Desk", "Desk 03", [2.0, 0.0, 6.0]),
    ("Desk", "Desk 04", [4.0, 0.0, 2.0]),
    ("Desk", "Desk 05", [4.0, 0.0, 4.0]),
    ("Desk", "Desk 06", [4.0, 0.0, 6.0]),
    ("Whiteboard", "Whiteboard", [7.5, 2.0, 1.0]),
    ("Kanban Wall", "Kanban Wall", [10.0, 1.5, 3.0]),
    ("Vault", "Vault", [10.5, 0.0, 7.0]),
    ("Security Gate", "Security Gate", [7.5, 0.0, 9.0]),
    ("Lounge", "Lounge", [1.5, 0.0, 8.5]),
    ("Event Stream", "Event Stream", [10.0, 1.5, 9.0]),
    ("Terminal", "Terminal", [6.0, 0.0, 5.0]),
]


@dataclass
class AgentMarker:
    id: str
    name: str
    color: str
    state: str = "idle"
    home: str = "Lounge"
    position: list[float] = field(default_factory=lambda: [1.5, 0.0, 8.5])
    target: list[float] = field(default_factory=lambda: [1.5, 0.0, 8.5])
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "state": self.state,
            "home": self.home,
            "position": self.position,
            "target": self.target,
            "telemetry": self.telemetry,
        }


class Space:
    def __init__(self, space_id: str, room: Room | None = None) -> None:
        self.space_id = space_id
        self.room = room or Room()
        self.primitives: dict[str, Primitive] = {}
        self.primitive_by_name: dict[str, Primitive] = {}
        self.agents: dict[str, AgentMarker] = {}

    def add_primitive(self, prim: Primitive) -> Primitive:
        self.primitives[prim.id] = prim
        self.primitive_by_name[prim.name] = prim
        return prim

    def position_of(self, primitive_name: str) -> list[float]:
        prim = self.primitive_by_name.get(primitive_name)
        if prim:
            x, y, z = prim.transform.position
            return [x, 0.0, z]
        # Unknown home (e.g. "System", "labs.space") -> the Lounge.
        lounge = self.primitive_by_name.get("Lounge")
        return [lounge.transform.position[0], 0.0, lounge.transform.position[2]] if lounge else [1.5, 0.0, 8.5]

    def scene_graph(self) -> dict[str, Any]:
        return {
            "space_id": self.space_id,
            "room": self.room.to_dict(),
            "primitives": [p.to_dict() for p in self.primitives.values()],
            "agents": [a.to_dict() for a in self.agents.values()],
        }


# State -> where the agent stands (spec 4.3 spatial cues).
_STATE_STATION = {
    "idle": "Lounge",
    "initializing": None,  # at home
    "assigned": None,
    "working": None,
    "reviewing": "Security Gate",
    "blocked": "Security Gate",
    "error": None,
    "complete": None,
    "paused": "Lounge",
}


class SpatialEngine:
    def __init__(self, event_bus: "EventBus") -> None:
        self.event_bus = event_bus
        self.spaces: dict[str, Space] = {}

    # --- spaces & layout -----------------------------------------------------
    def create_space(self, space_id: str, *, room: Room | None = None, default_layout: bool = True,
                     file: str | None = None) -> Space:
        # A `.spatial` asset, if present, defines the room + primitives (spec 2.4).
        loaded = self._load_spatial(file) if file else None
        if loaded is not None:
            space = Space(space_id, room=loaded[0])
            for prim in loaded[1]:
                space.add_primitive(prim)
            self.spaces[space_id] = space
            return space

        space = Space(space_id, room=room)
        if default_layout:
            for ptype, name, pos in DEFAULT_LAYOUT:
                space.add_primitive(Primitive.create(ptype, name, position=pos))
            # Couple the Whiteboard to Desk 01 (spec 7.3 example).
            wb = space.primitive_by_name.get("Whiteboard")
            if wb:
                wb.bindings.append(Binding(channel="whiteboard.data", to="/work/boards"))
        self.spaces[space_id] = space
        return space

    @staticmethod
    def _load_spatial(file: str | None) -> tuple[Room, list[Primitive]] | None:
        import json
        from pathlib import Path

        if not file or not Path(file).exists():
            return None
        try:
            doc = json.loads(Path(file).read_text())
            r = doc.get("room", {})
            room = Room(
                width=r.get("width", 12.0), depth=r.get("depth", 10.0),
                height=r.get("height", 3.0), grid=r.get("grid", 0.5),
            )
            prims: list[Primitive] = []
            for p in doc.get("primitives", []):
                pos = p.get("transform", {}).get("position", [0, 0, 0])
                prim = Primitive.create(p["type"], p.get("name"), position=pos)
                for b in p.get("bindings", []):
                    prim.bindings.append(Binding(channel=b["channel"], to=b["to"]))
                prims.append(prim)
            return room, prims
        except Exception:  # noqa: BLE001 - bad asset falls back to default layout
            log.warning("failed to load spatial asset %s; using default layout", file)
            return None

    def get_space(self, space_id: str) -> Space | None:
        return self.spaces.get(space_id)

    def scene(self, space_id: str) -> dict[str, Any]:
        space = self.spaces.get(space_id)
        return space.scene_graph() if space else {}

    # --- spatial commands (spec 7.5) ----------------------------------------
    async def add_primitive(self, space_id: str, type: str, name: str | None = None,
                            position: list[float] | None = None) -> Primitive:
        space = self._require(space_id)
        prim = Primitive.create(type, name, position=position)
        space.add_primitive(prim)
        await self.event_bus.emit(
            "spatial.primitive.added",
            {"primitive_id": prim.id, "type": type, "name": prim.name},
            space=space_id,
        )
        return prim

    async def bind_directory(self, space_id: str, primitive_name: str, path: str) -> None:
        space = self._require(space_id)
        prim = space.primitive_by_name.get(primitive_name)
        if not prim:
            raise KeyError(f"no primitive {primitive_name} in {space_id}")
        prim.bindings.append(Binding(channel="fs.dir", to=path))
        await self.event_bus.emit(
            "spatial.binding.created",
            {"primitive_id": prim.id, "channel": "fs.dir", "to": path},
            space=space_id,
        )

    async def resize_grid(self, space_id: str, *, width: float, depth: float, height: float = 3.0,
                          grid: float = 0.5) -> None:
        space = self._require(space_id)
        space.room = Room(width=width, depth=depth, height=height, grid=grid)
        await self.event_bus.emit(
            "spatial.grid.resized", {"width": width, "depth": depth}, space=space_id
        )

    # --- agent placement -----------------------------------------------------
    def place_agent(self, space_id: str, *, agent_id: str, name: str, color: str,
                    home: str, state: str = "idle", telemetry: dict[str, Any] | None = None) -> AgentMarker:
        space = self._require(space_id)
        pos = space.position_of(home)
        marker = AgentMarker(
            id=agent_id, name=name, color=color, state=state, home=home,
            position=list(pos), target=list(pos), telemetry=telemetry or {},
        )
        self._apply_state(space, marker, state)
        space.agents[agent_id] = marker
        return marker

    # --- live wiring: the scene reacts to the event stream -------------------
    def wire(self) -> None:
        self.event_bus.subscribe("agent.*", self._on_agent_event, name="spatial:agents")
        self.event_bus.subscribe("vault.file.changed", self._on_vault_event, name="spatial:vault")
        self.event_bus.subscribe("kanban.card.moved", self._on_kanban_event, name="spatial:kanban")
        self.event_bus.subscribe("security.gate.*", self._on_gate_event, name="spatial:gate")

    async def _on_agent_event(self, event: Event) -> None:
        space = self.spaces.get(event.space or "")
        if space is None or event.actor is None:
            return

        if event.type == "agent.spawned":
            p = event.payload
            self.place_agent(
                space.space_id,
                agent_id=p["agent"],
                name=p.get("name", p["agent"]),
                color=p.get("color", "#9CA3AF"),
                home=p.get("home", "Lounge"),
                state=p.get("state", "initializing"),
            )
            return

        if event.type == "agent.despawned":
            space.agents.pop(event.actor, None)
            return

        marker = space.agents.get(event.actor)
        if marker is None:
            return
        if event.type == "agent.state.changed":
            state = event.payload.get("state", marker.state)
            self._apply_state(space, marker, state)
            tel = event.payload.get("telemetry")
            if tel:
                marker.telemetry.update(tel)
        elif event.type == "agent.progress":
            marker.telemetry["progress"] = event.payload.get("progress", marker.telemetry.get("progress", 0))

    async def _on_vault_event(self, event: Event) -> None:
        space = self.spaces.get(event.space or "")
        if space and (vault := space.primitive_by_name.get("Vault")):
            vault.active = True  # the client pulses the glow, then it settles

    async def _on_kanban_event(self, event: Event) -> None:
        space = self.spaces.get(event.space or "")
        if space and event.actor and (marker := space.agents.get(event.actor)):
            # The agent steps to the Kanban Wall as it moves a card.
            marker.target = space.position_of("Kanban Wall")

    async def _on_gate_event(self, event: Event) -> None:
        space = self.spaces.get(event.space or "")
        if space and (gate := space.primitive_by_name.get("Security Gate")):
            gate.active = event.type == "security.gate.requested"

    # --- internals -----------------------------------------------------------
    def _apply_state(self, space: Space, marker: AgentMarker, state: str) -> None:
        marker.state = state
        station = _STATE_STATION.get(state)
        if station:
            marker.target = space.position_of(station)
        else:
            marker.target = space.position_of(marker.home)
        # Working agents light up their station.
        if marker.home in space.primitive_by_name:
            space.primitive_by_name[marker.home].active = state == "working"

    def _require(self, space_id: str) -> Space:
        space = self.spaces.get(space_id)
        if space is None:
            raise KeyError(f"no space {space_id}")
        return space
