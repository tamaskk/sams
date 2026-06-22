"""The deny-by-default permission engine (spec 12.2, 12.6).

Permissions use URI patterns (``vault://``, ``kanban://``, ``env://``). Agents have
no access unless granted. Separation of duties means producing agents cannot
approve their own gated work.

**Development Mode** (12.6): when ``mode: development`` and the active environment
is in ``development.appliesTo`` (dev only), ``grantAllPermissions`` short-circuits
every check — agents get full read/write/tool scope so nothing interrupts the
build loop. It can never widen to staging/prod.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import SamsConfig
    from ..sdk.manifest import AgentManifest

log = logging.getLogger("sams.permissions")


class PermissionDenied(PermissionError):
    """Raised when an agent attempts an action outside its scope."""


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """``vault://src/**`` -> matches ``vault://src/anything/deep``."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _matches_any(uri: str, patterns: list[str]) -> bool:
    return any(_pattern_to_regex(p).match(uri) for p in patterns)


class PermissionEngine:
    def __init__(self, config: "SamsConfig") -> None:
        self.config = config

    # --- Development Mode ----------------------------------------------------
    @property
    def dev_mode(self) -> bool:
        return self.config.dev_mode_active()

    @property
    def grant_all(self) -> bool:
        return self.dev_mode and self.config.permissions.development.grantAllPermissions

    @property
    def auto_approve(self) -> bool:
        return self.dev_mode and self.config.permissions.development.autoApprove

    @property
    def skip_confirmations(self) -> bool:
        return self.dev_mode and self.config.permissions.development.skipConfirmations

    @property
    def allow_protected_branches(self) -> bool:
        return self.dev_mode and self.config.permissions.development.allowProtectedBranches

    def posture(self) -> dict[str, str]:
        """The status-bar line: ``Gates: auto · Permissions: all · Confirmations: off``."""
        return {
            "mode": self.config.permissions.mode,
            "gates": "auto" if self.auto_approve else "manual",
            "permissions": "all" if self.grant_all else "scoped",
            "confirmations": "off" if self.skip_confirmations else "on",
        }

    # --- checks --------------------------------------------------------------
    def can_read(self, manifest: "AgentManifest", uri: str) -> bool:
        if self.grant_all:
            return True
        return _matches_any(uri, manifest.spec.permissions.read)

    def can_write(self, manifest: "AgentManifest", uri: str) -> bool:
        if self.grant_all:
            return True
        return _matches_any(uri, manifest.spec.permissions.write)

    def can_use_tool(self, manifest: "AgentManifest", tool_id: str) -> bool:
        if self.grant_all:
            return True
        for granted in manifest.spec.tools:
            if granted == tool_id:
                return True
            if granted.endswith(".*") and tool_id.startswith(granted[:-1]):
                return True
            if granted == "mcp.*" and tool_id.startswith("mcp."):
                return True
        return False

    def can_approve(self, manifest: "AgentManifest") -> bool:
        # Note: dev-mode auto-approve is handled by the *gate*, not by granting
        # the agent approve rights — separation of duties is preserved in the log.
        override = self.config.permissions.overrides.get(manifest.id, {})
        if "approve" in override:
            return bool(override["approve"])
        return manifest.can_approve

    def in_environment(self, manifest: "AgentManifest", env: str) -> bool:
        if self.grant_all:
            return True
        return env in manifest.spec.permissions.environments

    def check_tool(self, manifest: "AgentManifest", tool_id: str) -> None:
        if not self.can_use_tool(manifest, tool_id):
            raise PermissionDenied(
                f"agent {manifest.id} is not permitted to use tool {tool_id}"
            )

    def self_approval_blocked(self, manifest: "AgentManifest", produced_by: str | None) -> bool:
        """An agent may never approve its own gated work (12.2)."""
        return produced_by is not None and produced_by == manifest.id

    @staticmethod
    def self_approval_blocked_for(approver_id: str, produced_by: str | None) -> bool:
        """String-level separation-of-duties check used by the Security Gate."""
        return produced_by is not None and approver_id == produced_by
