"""Configuration: the three declarative YAML files that define a SAMS instance.

* ``sams.yaml``        — platform config (spaces, event bus, vault, limits, providers, mcp).
* ``agents.yaml``      — the fleet roster (which agents run, with what models/pools).
* ``permissions.yaml`` — access policy, including Development Mode.

All three are versioned alongside the workspace and loaded with ``${ENV}`` expansion.
"""

from .models import (
    AgentRosterEntry,
    DevelopmentMode,
    EventBusConfig,
    LimitsConfig,
    PermissionsConfig,
    PlatformConfig,
    ProviderConfig,
    RosterConfig,
    SamsConfig,
    SpaceRef,
    VaultConfig,
)
from .loader import load_config, load_yaml

__all__ = [
    "SamsConfig",
    "PlatformConfig",
    "RosterConfig",
    "PermissionsConfig",
    "AgentRosterEntry",
    "DevelopmentMode",
    "EventBusConfig",
    "LimitsConfig",
    "ProviderConfig",
    "SpaceRef",
    "VaultConfig",
    "load_config",
    "load_yaml",
]
