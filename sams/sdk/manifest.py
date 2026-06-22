"""The Agent manifest schema — the complete, canonical schema from spec 6.2.

A manifest is the declarative definition of an agent. Most agents are
declarative-only (no code); a manifest may also point at a ``handler`` class for
code-backed behavior (6.1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from ..core.yamlutil import safe_load as yaml_safe_load


class ModelBinding(BaseModel):
    provider: Literal["anthropic", "openai", "google", "local", "mock"] = "anthropic"
    name: str = "claude-sonnet-4"
    params: dict[str, Any] = Field(default_factory=lambda: {"temperature": 0.4, "max_tokens": 4096})


class Permissions(BaseModel):
    read: list[str] = Field(default_factory=list)
    write: list[str] = Field(default_factory=list)
    approve: bool = False
    tools: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=lambda: ["dev"])


class MemoryConfig(BaseModel):
    scope: Literal["private", "space", "global"] = "private"
    retention: str = "30d"


class HomeConfig(BaseModel):
    primitive: str = "Desk"
    room: str = "main"


class RoutingTrigger(BaseModel):
    on: str
    when: str | None = None


class RoutingConfig(BaseModel):
    priority: Literal["low", "normal", "high"] = "normal"
    concurrency: int = 1
    triggers: list[RoutingTrigger] = Field(default_factory=list)


class ManifestMetadata(BaseModel):
    id: str
    name: str
    color: str = "#9CA3AF"
    avatar: str = "robot"
    version: str = "1.0.0"
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = ""

    @field_validator("id")
    @classmethod
    def _kebab(cls, v: str) -> str:
        if not v or v != v.lower():
            raise ValueError(f"agent id must be lowercase kebab-case: {v!r}")
        return v


class ManifestSpec(BaseModel):
    role: str
    seniority: Literal["junior", "mid", "senior", "principal"] = "mid"
    model: ModelBinding = Field(default_factory=ModelBinding)
    systemPrompt: str = ""
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    permissions: Permissions = Field(default_factory=Permissions)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    home: HomeConfig = Field(default_factory=HomeConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    handler: str | None = None  # "module/path.py:ClassName"
    isolation: Literal["light", "standard", "hard"] = "standard"
    approves: bool = False  # convenience mirror of permissions.approve


class ManifestModel(BaseModel):
    """The full ``{apiVersion, kind, metadata, spec}`` document."""

    apiVersion: str = "sams/v1"
    kind: Literal["Agent"] = "Agent"
    metadata: ManifestMetadata
    spec: ManifestSpec


class AgentManifest:
    """Convenience wrapper exposing common fields directly off the model."""

    def __init__(self, model: ManifestModel, *, source: str | None = None) -> None:
        self.model = model
        self.source = source

    # --- flattened accessors -------------------------------------------------
    @property
    def id(self) -> str:
        return self.model.metadata.id

    @property
    def name(self) -> str:
        return self.model.metadata.name

    @property
    def color(self) -> str:
        return self.model.metadata.color

    @property
    def metadata(self) -> ManifestMetadata:
        return self.model.metadata

    @property
    def spec(self) -> ManifestSpec:
        return self.model.spec

    @property
    def capabilities(self) -> list[str]:
        return self.model.spec.capabilities

    @property
    def can_approve(self) -> bool:
        return self.model.spec.permissions.approve or self.model.spec.approves

    def to_dict(self) -> dict[str, Any]:
        return self.model.model_dump(mode="json")

    @classmethod
    def from_dict(cls, doc: dict[str, Any], *, source: str | None = None) -> "AgentManifest":
        return cls(ManifestModel.model_validate(doc), source=source)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentManifest {self.id} ({self.name})>"


def load_manifest(path: str | Path) -> AgentManifest:
    """Load and validate an agent manifest from a ``.agent.yaml`` file."""
    p = Path(path)
    doc = yaml_safe_load(p.read_text())
    if not isinstance(doc, dict):
        raise ValueError(f"manifest {p} is not a mapping")
    return AgentManifest.from_dict(doc, source=str(p))


# --------------------------------------------------------------------------- #
# Capability packs (spec 6.3)
# --------------------------------------------------------------------------- #
class PackProvision(BaseModel):
    id: str
    tools: list[str] = Field(default_factory=list)
    prompt: str | None = None


class PackSpec(BaseModel):
    provides: list[PackProvision] = Field(default_factory=list)
    appliesTo: dict[str, list[str]] = Field(default_factory=dict)


class CapabilityPack(BaseModel):
    apiVersion: str = "sams/v1"
    kind: Literal["CapabilityPack"] = "CapabilityPack"
    metadata: dict[str, Any]
    spec: PackSpec


def load_pack(path: str | Path) -> CapabilityPack:
    doc = yaml_safe_load(Path(path).read_text())
    return CapabilityPack.model_validate(doc)
