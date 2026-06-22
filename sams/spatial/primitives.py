"""Spatial primitives — placeable objects that bind a place to a capability.

The core primitive types and their material/form are taken from spec 2.3, 7.3 and
7.11 so the world reads at a glance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.ids import new_id

# type -> (material, default form/appearance) per spec 7.11.
PRIMITIVE_TYPES: dict[str, dict[str, Any]] = {
    "Desk": {"material": "wood", "color": "#C8A876", "opacity": 1.0, "edgeGlow": False},
    "Vault": {"material": "metal", "color": "#94A3B8", "opacity": 1.0, "edgeGlow": True},
    "Whiteboard": {"material": "glass", "color": "#7CC3FF", "opacity": 0.65, "edgeGlow": True},
    "Kanban Wall": {"material": "glass", "color": "#DBEAFE", "opacity": 0.7, "edgeGlow": True},
    "Security Gate": {"material": "metal", "color": "#22C55E", "opacity": 1.0, "edgeGlow": True},
    "Lounge": {"material": "fabric", "color": "#EDE9FE", "opacity": 1.0, "edgeGlow": False},
    "Event Stream": {"material": "glass", "color": "#3B82F6", "opacity": 0.6, "edgeGlow": True},
    "Terminal": {"material": "glass", "color": "#0F172A", "opacity": 0.85, "edgeGlow": True},
}


@dataclass
class Transform:
    position: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])

    def to_dict(self) -> dict[str, Any]:
        return {"position": self.position, "rotation": self.rotation, "scale": self.scale}


@dataclass
class Appearance:
    material: str = "matte"
    opacity: float = 1.0
    edgeGlow: bool = False
    color: str = "#CBD5E1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "material": self.material,
            "opacity": self.opacity,
            "edgeGlow": self.edgeGlow,
            "color": self.color,
        }


@dataclass
class Binding:
    channel: str
    to: str

    def to_dict(self) -> dict[str, Any]:
        return {"channel": self.channel, "to": self.to}


@dataclass
class Primitive:
    id: str
    type: str
    name: str
    transform: Transform = field(default_factory=Transform)
    appearance: Appearance = field(default_factory=Appearance)
    tags: list[str] = field(default_factory=list)
    bindings: list[Binding] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)
    active: bool = False  # glow when an agent is working here

    @classmethod
    def create(
        cls,
        type: str,
        name: str | None = None,
        *,
        position: list[float] | None = None,
        tags: list[str] | None = None,
    ) -> "Primitive":
        style = PRIMITIVE_TYPES.get(type, {})
        return cls(
            id=new_id("primitive"),
            type=type,
            name=name or type,
            transform=Transform(position=position or [0.0, 0.0, 0.0]),
            appearance=Appearance(
                material=style.get("material", "matte"),
                opacity=style.get("opacity", 1.0),
                edgeGlow=style.get("edgeGlow", False),
                color=style.get("color", "#CBD5E1"),
            ),
            tags=tags or [type.lower()],
            interactions=_DEFAULT_INTERACTIONS.get(type, []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "transform": self.transform.to_dict(),
            "appearance": self.appearance.to_dict(),
            "tags": self.tags,
            "bindings": [b.to_dict() for b in self.bindings],
            "interactions": self.interactions,
            "active": self.active,
        }


@dataclass
class Room:
    width: float = 12.0
    depth: float = 10.0
    height: float = 3.0
    grid: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"width": self.width, "depth": self.depth, "height": self.height, "grid": self.grid}


_DEFAULT_INTERACTIONS = {
    "Desk": ["bind_directory", "assign_agent", "open_files"],
    "Vault": ["view_status", "browse_files", "inspect_memory"],
    "Whiteboard": ["generate_diagram", "expand_notes", "convert_to_prd"],
    "Kanban Wall": ["new_card", "move_card", "filter", "sync_github"],
    "Security Gate": ["approve", "request_changes", "review_queue"],
    "Lounge": ["assign_idle_agents"],
    "Event Stream": ["inspect_events", "filter"],
    "Terminal": ["run_command", "view_logs"],
}
