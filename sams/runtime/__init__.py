"""The Agent Runtime — the execution sandbox where agents actually run (spec 3.4).

Each agent is a supervised worker that pulls its assignment, loads its prompt /
capabilities / tools, calls its LLM provider, executes tool calls within its
permission scope, and streams progress back to the Event Bus.
"""

from .runner import AgentRuntime

__all__ = ["AgentRuntime"]
