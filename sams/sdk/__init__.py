"""The Agent SDK — base classes, manifest loader, decorators, registries.

This is the public surface agent authors import:

    from sams.sdk import Agent, capability, hook, tool

Authoring an agent is a first-class, low-friction operation requiring **no core
changes** (spec Section 6): write a declarative manifest, optionally add a
handler class, register it, and the Orchestrator can route work to it.
"""

from .decorators import capability, hook, tool, HOOK_NAMES
from .manifest import (
    AgentManifest,
    CapabilityPack,
    ManifestModel,
    ManifestSpec,
    ModelBinding,
    Permissions,
    load_manifest,
    load_pack,
)
from .agent import Agent, AgentContext
from .registry import (
    AgentRegistry,
    CapabilityRegistry,
    ToolRegistry,
    ToolSpec,
)

__all__ = [
    "Agent",
    "AgentContext",
    "capability",
    "hook",
    "tool",
    "HOOK_NAMES",
    "AgentManifest",
    "ManifestModel",
    "ManifestSpec",
    "ModelBinding",
    "Permissions",
    "CapabilityPack",
    "load_manifest",
    "load_pack",
    "AgentRegistry",
    "CapabilityRegistry",
    "ToolRegistry",
    "ToolSpec",
]
