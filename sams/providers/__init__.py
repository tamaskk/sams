"""Pluggable LLM provider adapters (spec 9.1).

SAMS is model-agnostic. Each agent binds to a provider/model; the binding is
overridable per instance and per environment. ``mock`` needs no API key and
produces deterministic work, so the whole platform runs offline out of the box.
"""

from .base import Completion, LLMProvider, ProviderFactory
from .mock import MockProvider

__all__ = ["Completion", "LLMProvider", "ProviderFactory", "MockProvider"]
