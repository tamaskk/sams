"""Stable, human-readable id generation.

SAMS ids are prefixed so they're self-describing in logs and the UI
(``evt_8f3a9c2d``, ``trc_19af``, ``prim_8f3a9c2d``, ``run_4471``). The prefix
conventions mirror the canonical examples in the spec (Sections 2.7, 13).
"""

from __future__ import annotations

import secrets

# Prefixes used across the system, kept here so they're discoverable in one place.
PREFIXES = {
    "event": "evt",
    "trace": "trc",
    "primitive": "prim",
    "run": "run",
    "thread": "thr",
    "message": "msg",
    "task": "SAMS",  # Kanban cards read like SAMS-201
    "gate": "gate",
    "agent_instance": "ai",
}


def new_id(kind: str = "event", *, nbytes: int = 4) -> str:
    """Return a new prefixed id, e.g. ``evt_8f3a9c2d``.

    ``kind`` selects the prefix from :data:`PREFIXES` (defaults to ``event``).
    Unknown kinds are used verbatim as the prefix.
    """
    prefix = PREFIXES.get(kind, kind)
    return f"{prefix}_{secrets.token_hex(nbytes)}"


_counter = 0


def next_card_number(prefix: str = "SAMS") -> str:
    """Monotonic, friendly Kanban card id (``SAMS-201`` style).

    Starts at 201 to match the reference cards in the spec.
    """
    global _counter
    _counter += 1
    return f"{prefix}-{200 + _counter}"


def bump_card_counter(card_ids, prefix: str = "SAMS") -> None:
    """Advance the card counter past already-used ids (after loading from disk)."""
    global _counter
    for cid in card_ids:
        if isinstance(cid, str) and cid.startswith(prefix + "-"):
            try:
                n = int(cid.rsplit("-", 1)[1])
            except ValueError:
                continue
            _counter = max(_counter, n - 200)
