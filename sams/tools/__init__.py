"""Built-in tools — how agents touch the outside world (spec 6.5, 19.2).

Importing this package registers every built-in tool into the global
:class:`~sams.sdk.registry.ToolRegistry`. MCP servers add further tools at
runtime as ``mcp.<server>.<tool>`` (spec 9.3).
"""

from . import builtin  # noqa: F401  (import side-effect: registers tools)

__all__ = ["builtin"]
