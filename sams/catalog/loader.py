"""Loader for built-in agent manifests."""

from __future__ import annotations

import logging
from pathlib import Path

from ..sdk.manifest import AgentManifest, load_manifest

log = logging.getLogger("sams.catalog")


def load_builtin_manifests(workspace_root: str | Path = ".") -> list[AgentManifest]:
    """Load every ``*.agent.yaml`` under ``agents/builtin``."""
    builtin_dir = Path(workspace_root) / "agents" / "builtin"
    manifests: list[AgentManifest] = []
    if not builtin_dir.exists():
        return manifests
    for f in sorted(builtin_dir.glob("*.agent.yaml")):
        try:
            manifests.append(load_manifest(f))
        except Exception:  # noqa: BLE001
            log.exception("failed to load built-in manifest %s", f)
    return manifests


def _load_dir(directory: Path) -> list[AgentManifest]:
    out: list[AgentManifest] = []
    if not directory.exists():
        return out
    for f in sorted(directory.glob("*.agent.yaml")):
        try:
            out.append(load_manifest(f))
        except Exception:  # noqa: BLE001
            log.exception("failed to load manifest %s", f)
    return out


def load_custom_manifests(workspace_root: str | Path = ".") -> list[AgentManifest]:
    """Load every ``*.agent.yaml`` under ``agents/custom`` and ``agents/roles``."""
    root = Path(workspace_root) / "agents"
    return _load_dir(root / "roles") + _load_dir(root / "custom")
