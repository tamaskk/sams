"""Core: the Event Bus, the event model, and id generation.

This is the asynchronous backbone of SAMS. Every meaningful state change is
published here as an :class:`Event`; the spatial UI, the logs, the orchestrator
and the audit trail are all just subscribers.
"""

from .events import Event, Topic, topic_of
from .event_bus import EventBus, InMemoryEventBus, get_event_bus
from .ids import new_id

__all__ = [
    "Event",
    "Topic",
    "topic_of",
    "EventBus",
    "InMemoryEventBus",
    "get_event_bus",
    "new_id",
]
