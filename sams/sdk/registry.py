"""Registries: tools, capabilities, and agents.

* :class:`ToolRegistry` — every callable tool (native + MCP), permission-gated.
* :class:`CapabilityRegistry` — capability -> agents that provide it (routing).
* :class:`AgentRegistry` — agent id -> manifest (+ resolved handler class).

Registration is *hot*: adding an agent or tool at runtime requires no restart
(spec 6.6).
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from .decorators import TOOL_ATTR
from .manifest import AgentManifest

log = logging.getLogger("sams.registry")


@dataclass
class ToolSpec:
    id: str
    fn: Callable[..., Awaitable[Any]]
    requires_permission: str
    description: str = ""


class ToolRegistry:
    """Holds all callable tools. Tools are permission-gated at call time."""

    _global: "ToolRegistry | None" = None

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    @classmethod
    def global_instance(cls) -> "ToolRegistry":
        if cls._global is None:
            cls._global = ToolRegistry()
        return cls._global

    def register_fn(self, fn: Callable) -> ToolSpec:
        meta = getattr(fn, TOOL_ATTR, None)
        if meta is None:
            raise ValueError(f"{fn} is not decorated with @tool")
        spec = ToolSpec(
            id=meta["id"],
            fn=fn,
            requires_permission=meta["requires_permission"],
            description=meta["description"],
        )
        self._tools[spec.id] = spec
        return spec

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.id] = spec

    def get(self, tool_id: str) -> ToolSpec | None:
        if tool_id in self._tools:
            return self._tools[tool_id]
        # Wildcard tool grants like "fs.*" or "git.*" in manifests resolve to
        # any matching concrete tool; the gate enforces the real permission.
        return None

    def ids(self) -> list[str]:
        return sorted(self._tools)

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())


class CapabilityRegistry:
    """capability id -> set of agent ids that provide it (Orchestrator routing)."""

    def __init__(self) -> None:
        self._providers: dict[str, set[str]] = {}

    def declare(self, agent_id: str, capabilities: list[str]) -> None:
        for cap in capabilities:
            self._providers.setdefault(cap, set()).add(agent_id)

    def retract(self, agent_id: str) -> None:
        for providers in self._providers.values():
            providers.discard(agent_id)

    def providers_of(self, capability: str) -> set[str]:
        return set(self._providers.get(capability, set()))

    def capabilities(self) -> list[str]:
        return sorted(self._providers)


class AgentRegistry:
    """agent id -> manifest, with lazy handler-class resolution."""

    def __init__(self, *, capabilities: CapabilityRegistry | None = None) -> None:
        self._manifests: dict[str, AgentManifest] = {}
        self.capabilities = capabilities or CapabilityRegistry()

    def add(self, manifest: AgentManifest) -> AgentManifest:
        if manifest.id in self._manifests:
            log.info("replacing manifest for %s (hot-swap)", manifest.id)
        self._manifests[manifest.id] = manifest
        self.capabilities.declare(manifest.id, manifest.capabilities)
        return manifest

    def remove(self, agent_id: str) -> None:
        self._manifests.pop(agent_id, None)
        self.capabilities.retract(agent_id)

    def get(self, agent_id: str) -> AgentManifest | None:
        return self._manifests.get(agent_id)

    def all(self) -> list[AgentManifest]:
        return list(self._manifests.values())

    def ids(self) -> list[str]:
        return sorted(self._manifests)

    def install_pack(self, pack: Any, agent_id: str) -> list[str]:
        """Install a CapabilityPack onto an agent (spec 6.3) — adds its provided
        capabilities + tools to the target manifest. Returns the new capability ids."""
        manifest = self._manifests.get(agent_id)
        if manifest is None:
            raise KeyError(f"no agent {agent_id}")
        added: list[str] = []
        for prov in pack.spec.provides:
            if prov.id not in manifest.spec.capabilities:
                manifest.spec.capabilities.append(prov.id)
                added.append(prov.id)
            for t in prov.tools:
                if t not in manifest.spec.tools:
                    manifest.spec.tools.append(t)
        self.capabilities.declare(agent_id, manifest.capabilities)
        return added

    def resolve_handler(self, manifest: AgentManifest) -> type | None:
        """Import the handler class named in ``spec.handler`` ("path.py:Class")."""
        ref = manifest.spec.handler
        if not ref:
            return None
        mod_ref, _, cls_name = ref.partition(":")
        if not cls_name:
            raise ValueError(f"handler {ref!r} must be 'module_or_path:ClassName'")
        if mod_ref.endswith(".py"):
            path = self._resolve_path(mod_ref, manifest)
            spec = importlib.util.spec_from_file_location(f"sams_handler_{path.stem}", path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load handler module {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(mod_ref)
        return getattr(module, cls_name)

    @staticmethod
    def _resolve_path(mod_ref: str, manifest: AgentManifest) -> Path:
        """Try the path as-given (workspace-relative), then relative to the
        manifest's directory, then just its basename next to the manifest."""
        candidates = [Path(mod_ref)]
        if manifest.source:
            mdir = Path(manifest.source).parent
            candidates += [mdir / mod_ref, mdir / Path(mod_ref).name]
        for c in candidates:
            if c.exists():
                return c.resolve()
        raise ImportError(f"handler module not found for {mod_ref!r} (tried {candidates})")
