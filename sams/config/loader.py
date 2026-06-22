"""YAML config loading with ``${ENV}`` expansion.

Secrets are never stored in config — they are *referenced* (``${ANTHROPIC_API_KEY}``)
and resolved at runtime from the environment (spec 12.5).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..core.yamlutil import safe_load as yaml_safe_load
from .models import (
    PermissionsConfig,
    PlatformConfig,
    RosterConfig,
    SamsConfig,
)

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-(.*?))?\}")


def _expand(value: Any) -> Any:
    """Recursively expand ``${VAR}`` / ``${VAR:-default}`` references."""
    if isinstance(value, str):
        def repl(m: re.Match[str]) -> str:
            var, default = m.group(1), m.group(2)
            return os.environ.get(var, default if default is not None else "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load_dotenv(workspace_root: str | Path = ".") -> None:
    """Load ``<workspace>/.env`` into the environment (without overriding existing).

    Lets the user paste secrets like ``CLICKUP_API_TOKEN`` / ``ANTHROPIC_API_KEY``
    into one file instead of exporting them each session.
    """
    p = Path(workspace_root) / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file with env expansion. Returns ``{}`` if missing."""
    p = Path(path)
    if not p.exists():
        return {}
    raw = yaml_safe_load(p.read_text()) or {}
    return _expand(raw)


def _spec(doc: dict[str, Any]) -> dict[str, Any]:
    """SAMS manifests follow the k8s-style ``{apiVersion, kind, spec}`` shape."""
    return doc.get("spec", doc) if isinstance(doc, dict) else {}


def load_config(
    workspace_root: str | Path = ".",
    *,
    environment: str | None = None,
    mode: str | None = None,
) -> SamsConfig:
    """Load ``configs/{sams,agents,permissions}.yaml`` into a :class:`SamsConfig`.

    Missing files fall back to sane defaults, so a fresh checkout boots.
    ``mode``/``environment`` overrides (e.g. ``sams up --mode development``)
    take precedence over the files.
    """
    root = Path(workspace_root)
    load_dotenv(root)  # pull secrets from .env before anything reads the environment
    cfg_dir = root / "configs"

    platform_doc = _spec(load_yaml(cfg_dir / "sams.yaml"))
    roster_doc = _spec(load_yaml(cfg_dir / "agents.yaml"))
    perms_doc = _spec(load_yaml(cfg_dir / "permissions.yaml"))

    platform = PlatformConfig.model_validate(platform_doc) if platform_doc else PlatformConfig()
    roster = RosterConfig.model_validate(roster_doc) if roster_doc else RosterConfig()
    permissions = (
        PermissionsConfig.model_validate(perms_doc) if perms_doc else PermissionsConfig()
    )

    if mode:
        permissions.mode = mode  # type: ignore[assignment]

    env = environment or os.environ.get("SAMS_ENV", "dev")

    return SamsConfig(
        platform=platform,
        roster=roster,
        permissions=permissions,
        environment=env,
        workspace_root=str(root),
    )
