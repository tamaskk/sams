"""SDK decorators: ``@capability``, ``@hook``, ``@tool`` (spec 6.1, 6.4, 6.5).

These attach metadata to functions/methods. The :class:`~sams.sdk.agent.Agent`
base class and the :class:`~sams.sdk.registry.ToolRegistry` discover that metadata
at load time, so authors only declare intent — wiring is automatic.
"""

from __future__ import annotations

from typing import Callable

# The canonical lifecycle hook names (spec 6.4).
HOOK_NAMES = (
    "on_spawn",
    "on_assign",
    "on_start",
    "on_tool_call",
    "on_progress",
    "on_complete",
    "on_gate",
    "on_error",
    "on_despawn",
)

CAPABILITY_ATTR = "__sams_capability__"
HOOK_ATTR = "__sams_hook__"
TOOL_ATTR = "__sams_tool__"


def capability(capability_id: str) -> Callable:
    """Mark an async method as PROVIDING a capability the Orchestrator can route to.

        @capability("content.seo_audit")
        async def seo_audit(self, ctx, url: str) -> dict: ...
    """

    def deco(fn: Callable) -> Callable:
        setattr(fn, CAPABILITY_ATTR, capability_id)
        return fn

    return deco


def hook(hook_name: str) -> Callable:
    """Mark an async method as a lifecycle hook (one of :data:`HOOK_NAMES`)."""
    if hook_name not in HOOK_NAMES:
        raise ValueError(f"unknown hook {hook_name!r}; valid hooks: {HOOK_NAMES}")

    def deco(fn: Callable) -> Callable:
        setattr(fn, HOOK_ATTR, hook_name)
        return fn

    return deco


def tool(
    *,
    id: str,
    requires_permission: str | None = None,
    description: str = "",
) -> Callable:
    """Register an async function as a callable tool (spec 6.5).

        @tool(id="seo.lighthouse", requires_permission="tools:seo.lighthouse")
        async def lighthouse(ctx, url: str) -> dict: ...
    """

    def deco(fn: Callable) -> Callable:
        setattr(
            fn,
            TOOL_ATTR,
            {
                "id": id,
                "requires_permission": requires_permission or f"tools:{id}",
                "description": description or (fn.__doc__ or "").strip(),
            },
        )
        # Auto-register into the global tool registry on import.
        from .registry import ToolRegistry

        ToolRegistry.global_instance().register_fn(fn)
        return fn

    return deco
