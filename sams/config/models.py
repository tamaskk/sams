"""Pydantic models for SAMS configuration (spec Section 10)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# sams.yaml — platform config (10.1)
# --------------------------------------------------------------------------- #
class SpaceRef(BaseModel):
    id: str
    file: str | None = None


class EventBusConfig(BaseModel):
    backend: Literal["in-memory", "redis-streams", "nats"] = "in-memory"
    retention: str = "7d"
    redis_url: str = "redis://localhost:6379/0"


class VaultConfig(BaseModel):
    relational: str | None = None
    documents: str | None = None
    vectors: str | None = None
    objects: str | None = None
    # Local fallback so SAMS runs with zero external infra.
    local_path: str = ".sams/vault"


class LimitsConfig(BaseModel):
    maxConcurrentAgents: int = 24
    maxContextWindow: int = 200000


class ProviderConfig(BaseModel):
    api_key: str | None = None
    default_model: str | None = None
    base_url: str | None = None

    model_config = {"extra": "allow"}


class PlatformConfig(BaseModel):
    """Top-level ``sams.yaml`` ``spec`` block."""

    version: str = "0.9.0"
    defaultSpace: str = "main.space"
    spaces: list[SpaceRef] = Field(default_factory=lambda: [SpaceRef(id="main.space")])
    eventBus: EventBusConfig = Field(default_factory=EventBusConfig)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    mcp: dict[str, Any] = Field(default_factory=dict)
    # Which provider/model agents fall back to when their manifest doesn't pin one,
    # or when running offline. "mock" needs no API key and produces real work.
    defaultProvider: str = "mock"

    model_config = {"extra": "allow"}


# --------------------------------------------------------------------------- #
# agents.yaml — fleet roster (10.2)
# --------------------------------------------------------------------------- #
class AgentRosterEntry(BaseModel):
    ref: str | None = None  # built-in agent id
    manifest: str | None = None  # path to a custom manifest
    model: dict[str, Any] | None = None
    instances: int = 1


class RosterConfig(BaseModel):
    agents: list[AgentRosterEntry] = Field(default_factory=list)
    pools: dict[str, list[str]] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


# --------------------------------------------------------------------------- #
# permissions.yaml — access policy (10.3, 12.6)
# --------------------------------------------------------------------------- #
class DevelopmentMode(BaseModel):
    """Development Mode: full autonomy in dev so the build loop never stops (12.6)."""

    autoApprove: bool = True
    grantAllPermissions: bool = True
    skipConfirmations: bool = True
    allowProtectedBranches: bool = True
    appliesTo: list[str] = Field(default_factory=lambda: ["dev"])


class RolePolicy(BaseModel):
    read: list[str] = Field(default_factory=list)
    write: list[str] = Field(default_factory=list)
    approve: bool = False
    environments: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class PermissionsConfig(BaseModel):
    mode: Literal["development", "standard", "strict"] = "development"
    development: DevelopmentMode = Field(default_factory=DevelopmentMode)
    roles: dict[str, RolePolicy] = Field(default_factory=dict)
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=lambda: {"deny": True})

    model_config = {"extra": "allow"}


# --------------------------------------------------------------------------- #
# The fully assembled configuration handed to the platform.
# --------------------------------------------------------------------------- #
class SamsConfig(BaseModel):
    platform: PlatformConfig = Field(default_factory=PlatformConfig)
    roster: RosterConfig = Field(default_factory=RosterConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    # The active environment (dev/staging/prod) — drives Development Mode scoping.
    environment: str = "dev"
    workspace_root: str = "."

    def dev_mode_active(self) -> bool:
        """True when Development Mode applies to the current environment (12.6)."""
        p = self.permissions
        return p.mode == "development" and self.environment in p.development.appliesTo
