"""The Spatial Engine — the world model and scene graph (spec 3.5, 7).

Owns rooms, grid, primitives, placements, bindings, and couplings, and translates
**functional state** (a card moved, a file changed) into **spatial representation**
(an agent walking to the Kanban Wall, a glow on the Vault). It is a live
projection of the Event Bus.
"""

from .primitives import (
    Appearance,
    Binding,
    Primitive,
    PRIMITIVE_TYPES,
    Room,
    Transform,
)
from .engine import AgentMarker, Space, SpatialEngine

__all__ = [
    "SpatialEngine",
    "Space",
    "AgentMarker",
    "Primitive",
    "PRIMITIVE_TYPES",
    "Room",
    "Transform",
    "Appearance",
    "Binding",
]
