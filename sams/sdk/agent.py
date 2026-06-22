"""The base :class:`Agent` and the :class:`AgentContext` handed to hooks/capabilities.

An agent author subclasses :class:`Agent` only when they need code-backed behavior
(a custom capability or hook). Everything an author touches — ``self.tools.*``,
``self.think(...)``, ``ctx.emit(...)``, ``ctx.vault.read(...)`` — is wired here so
the handler example in spec 6.2 runs verbatim.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from .decorators import CAPABILITY_ATTR, HOOK_ATTR, HOOK_NAMES
from .manifest import AgentManifest

if TYPE_CHECKING:  # avoid import cycles; these are duck-typed at runtime
    from ..core.event_bus import EventBus

log = logging.getLogger("sams.agent")


class AgentServices(Protocol):
    """The runtime capabilities an :class:`Agent` needs, injected by the runtime.

    Keeping this a Protocol means the SDK has no hard dependency on the vault,
    kanban, gate, or provider modules — they're wired in by the platform.
    """

    event_bus: "EventBus"
    vault: Any
    kanban: Any
    gate: Any
    workspace_root: str

    async def call_tool(self, agent: "Agent", tool_id: str, *args: Any, **kwargs: Any) -> Any: ...

    def provider_for(self, manifest: AgentManifest) -> Any: ...


@dataclass
class ShellResult:
    stdout: str
    stderr: str
    code: int


class ShellRunner:
    """Minimal async shell, used by tools like ``shell.run`` / ``test.run``.

    Real subprocess execution is gated behind ``SAMS_ALLOW_SHELL=1`` (defaults to
    a simulated result) so the platform is safe to run out of the box.
    """

    def __init__(self, cwd: str = ".") -> None:
        self.cwd = cwd

    async def run(self, command: str, *, timeout: float = 60.0) -> ShellResult:
        import asyncio
        import os

        if os.environ.get("SAMS_ALLOW_SHELL") != "1":
            return ShellResult(stdout=f"[simulated] $ {command}\nok\n", stderr="", code=0)
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=self.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return ShellResult(stdout="", stderr="timeout", code=124)
        return ShellResult(out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode or 0)


class ToolProxy:
    """``ctx.tools.web_fetch(url)`` -> calls the ``web.fetch`` tool through the gate.

    Method name underscores map to tool-id dots (``git_pr_create`` -> ``git.pr.create``).
    """

    def __init__(self, agent: "Agent") -> None:
        self._agent = agent

    def __getattr__(self, name: str):
        tool_id = name.replace("_", ".")

        async def _call(*args: Any, **kwargs: Any) -> Any:
            return await self._agent._call_tool(tool_id, *args, **kwargs)

        return _call


@dataclass
class Completion:
    """The result of :meth:`Agent.think` — a single LLM completion."""

    text: str
    markdown: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    structured: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.markdown:
            self.markdown = self.text

    @property
    def fixes(self) -> list[Any]:
        return self.structured.get("fixes", [])


class AgentLogger:
    """Per-agent logger that mirrors lines into the agent-log event stream."""

    LEVELS = {"info": "INFO", "success": "SUCCESS", "warn": "WARN", "error": "ERROR", "idle": "IDLE"}

    def __init__(self, ctx: "AgentContext") -> None:
        self._ctx = ctx

    def _emit(self, level: str, msg: str) -> None:
        line = f"{self.LEVELS.get(level, 'INFO')}"
        log.info("[%s] %s %s", self._ctx.agent.id, line, msg)
        # Agent logs are events too, so the console/observability stack sees them.
        self._ctx._schedule_emit(
            "agent.log", {"level": line, "message": msg, "agent": self._ctx.agent.id}
        )

    def info(self, msg: str) -> None:
        self._emit("info", msg)

    def success(self, msg: str) -> None:
        self._emit("success", msg)

    def warn(self, msg: str) -> None:
        self._emit("warn", msg)

    def error(self, msg: str) -> None:
        self._emit("error", msg)

    def idle(self, msg: str) -> None:
        self._emit("idle", msg)


@dataclass
class AgentContext:
    """The context object passed to every hook and capability.

    Carries the live bus, vault, kanban, gate, the current task, and convenience
    helpers (``emit``, ``slug``, ``json``).
    """

    agent: "Agent"
    services: AgentServices
    space: str
    trace_id: str
    task: Any | None = None
    log: AgentLogger = field(init=False)

    def __post_init__(self) -> None:
        self.log = AgentLogger(self)

    # --- convenience accessors ----------------------------------------------
    @property
    def tools(self) -> ToolProxy:
        return self.agent.tools

    @property
    def vault(self) -> Any:
        return self.services.vault

    @property
    def kanban(self) -> Any:
        return self.services.kanban

    @property
    def gate(self) -> Any:
        return self.services.gate

    @property
    def shell(self) -> ShellRunner:
        return ShellRunner(cwd=getattr(self.services, "workspace_root", "."))

    # --- helpers -------------------------------------------------------------
    async def emit(self, type: str, payload: dict[str, Any] | None = None) -> Any:
        return await self.services.event_bus.emit(
            type, payload or {}, actor=self.agent.id, space=self.space, trace_id=self.trace_id
        )

    def _schedule_emit(self, type: str, payload: dict[str, Any]) -> None:
        """Fire-and-forget emit used by the logger (sync call sites)."""
        import asyncio

        try:
            asyncio.get_running_loop().create_task(self.emit(type, payload))
        except RuntimeError:  # pragma: no cover - no loop (tests)
            pass

    @staticmethod
    def slug(text: str) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return s or "item"

    @staticmethod
    def json(text: str) -> Any:
        return json.loads(text)


class Agent:
    """Base class for all SAMS agents.

    Declarative-only agents use this class directly; code-backed agents subclass
    it and add ``@capability`` / ``@hook`` methods (spec 6.1).
    """

    def __init__(self, manifest: AgentManifest, services: AgentServices) -> None:
        self.manifest = manifest
        self.id = manifest.id
        self.name = manifest.name
        self.color = manifest.color
        self._services = services
        self.tools = ToolProxy(self)
        self._capabilities: dict[str, Any] = {}
        self._hooks: dict[str, list[Any]] = {}
        self._ctx: AgentContext | None = None
        self._discover()

    # --- discovery -----------------------------------------------------------
    def _discover(self) -> None:
        for name in dir(self):
            if name.startswith("__"):
                continue
            try:
                attr = getattr(self, name)
            except Exception:  # noqa: BLE001 - skip properties that raise
                continue
            if not callable(attr):
                continue
            cap = getattr(attr, CAPABILITY_ATTR, None)
            if cap:
                self._capabilities[cap] = attr
            hk = getattr(attr, HOOK_ATTR, None)
            if hk:
                self._hooks.setdefault(hk, []).append(attr)

    # --- context -------------------------------------------------------------
    def bind_context(self, ctx: AgentContext) -> None:
        self._ctx = ctx

    @property
    def ctx(self) -> AgentContext:
        if self._ctx is None:
            raise RuntimeError(f"agent {self.id} has no bound context")
        return self._ctx

    # --- capabilities & hooks ------------------------------------------------
    def provides(self, capability_id: str) -> bool:
        return capability_id in self._capabilities or capability_id in self.manifest.capabilities

    def has_handler_for(self, capability_id: str) -> bool:
        return capability_id in self._capabilities

    async def invoke_capability(self, capability_id: str, ctx: AgentContext, **kwargs: Any) -> Any:
        fn = self._capabilities.get(capability_id)
        if fn is None:
            raise KeyError(f"agent {self.id} has no handler for capability {capability_id}")
        return await fn(ctx, **kwargs)

    async def run_hooks(self, hook_name: str, ctx: AgentContext, *args: Any) -> None:
        if hook_name not in HOOK_NAMES:
            raise ValueError(f"unknown hook {hook_name!r}")
        for fn in self._hooks.get(hook_name, []):
            await fn(ctx, *args)

    # --- LLM + tools ---------------------------------------------------------
    async def think(self, prompt: str, *, context: Any = None, **params: Any) -> Completion:
        provider = self._services.provider_for(self.manifest)
        return await provider.complete(
            agent=self,
            system=self.manifest.spec.systemPrompt,
            prompt=prompt,
            context=context,
            params={**self.manifest.spec.model.params, **params},
        )

    async def _call_tool(self, tool_id: str, *args: Any, **kwargs: Any) -> Any:
        return await self._services.call_tool(self, tool_id, *args, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Agent {self.id} ({self.name})>"
