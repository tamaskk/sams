"""Chat, messaging & the AI Assistant (spec 7.16).

Conversation is a first-class surface in SAMS — how humans direct agents, how
agents talk to each other, and how discussion stays anchored to the work. There
is no separate chat app; messaging is woven into the workspace, and every message
is an event (``chat.message.posted`` / ``agent.message``).
"""

from .models import Message, Thread
from .service import ChatService

__all__ = ["ChatService", "Thread", "Message"]
