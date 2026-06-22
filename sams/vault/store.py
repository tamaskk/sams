"""The Vault store: versioned file storage under the ``vault://`` scheme.

Every write is versioned and emits ``vault.file.changed``; memory writes emit
``vault.memory.written`` — so the spatial UI can glow the Vault and the audit log
captures provenance.
"""

from __future__ import annotations

import json
import logging
import shutil
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .memory import VaultMemory

if TYPE_CHECKING:
    from ..core.event_bus import EventBus

log = logging.getLogger("sams.vault")


def _parse_uri(uri: str) -> str:
    """``vault://src/main.py`` -> ``src/main.py``. Bare paths pass through."""
    if uri.startswith("vault://"):
        return uri[len("vault://") :]
    return uri.lstrip("/")


class Vault(ABC):
    memory: VaultMemory

    @abstractmethod
    async def read(self, uri: str) -> str: ...

    @abstractmethod
    async def write(self, uri: str, content: str, *, actor: str | None = None) -> str: ...

    @abstractmethod
    async def exists(self, uri: str) -> bool: ...

    @abstractmethod
    async def list(self, prefix: str = "") -> list[str]: ...

    @abstractmethod
    async def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def gc(self) -> int: ...

    @abstractmethod
    async def stats(self) -> dict[str, Any]: ...


class LocalVault(Vault):
    """Filesystem-backed Vault. Files live under ``<root>/files``; versions under
    ``<root>/.versions``; long-term memory under ``<root>/memory``."""

    def __init__(self, root: str | Path, event_bus: "EventBus | None" = None, *, space: str = "main.space") -> None:
        self.root = Path(root)
        self.files_root = self.root / "files"
        self.versions_root = self.root / ".versions"
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.versions_root.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self.space = space
        self.memory = VaultMemory(self.root / "memory")
        self._versions: dict[str, int] = {}
        self._linked_agents: set[str] = set()
        self._load_version_index()

    def _load_version_index(self) -> None:
        idx = self.root / ".versions" / "index.json"
        if idx.exists():
            self._versions = json.loads(idx.read_text())

    def _save_version_index(self) -> None:
        (self.versions_root / "index.json").write_text(json.dumps(self._versions))

    def _abs(self, uri: str) -> Path:
        rel = _parse_uri(uri)
        path = (self.files_root / rel).resolve()
        # Prevent path traversal outside the vault.
        if self.files_root.resolve() not in path.parents and path != self.files_root.resolve():
            raise ValueError(f"path {uri} escapes the vault")
        return path

    async def read(self, uri: str) -> str:
        path = self._abs(uri)
        if not path.exists():
            raise FileNotFoundError(uri)
        return path.read_text()

    async def write(self, uri: str, content: str, *, actor: str | None = None) -> str:
        rel = _parse_uri(uri)
        path = self._abs(uri)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Snapshot the previous version before overwriting.
        version = self._versions.get(rel, 0) + 1
        if path.exists():
            vdir = self.versions_root / rel
            vdir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, self.versions_root / f"{rel}.v{version - 1}")
        path.write_text(content)
        self._versions[rel] = version
        self._save_version_index()

        if actor:
            self._linked_agents.add(actor)
        if self.event_bus:
            await self.event_bus.emit(
                "vault.file.changed",
                {"uri": f"vault://{rel}", "version": version, "bytes": len(content)},
                actor=actor,
                space=self.space,
            )
        return f"vault://{rel}"

    async def exists(self, uri: str) -> bool:
        return self._abs(uri).exists()

    async def list(self, prefix: str = "") -> list[str]:
        base = self.files_root / _parse_uri(prefix) if prefix else self.files_root
        if not base.exists():
            return []
        out = []
        root = base if base.is_dir() else base.parent
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out.append(f"vault://{p.relative_to(self.files_root)}")
        return out

    async def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        q = query.lower()
        hits: list[dict[str, Any]] = []
        for p in self.files_root.rglob("*"):
            if not p.is_file():
                continue
            try:
                text = p.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            if q in text.lower() or q in p.name.lower():
                idx = text.lower().find(q)
                snippet = text[max(0, idx - 40) : idx + 80] if idx >= 0 else text[:80]
                hits.append({"uri": f"vault://{p.relative_to(self.files_root)}", "snippet": snippet})
            if len(hits) >= limit:
                break
        return hits

    async def gc(self) -> int:
        """Remove old versioned snapshots; return count reclaimed (spec: Janitor)."""
        removed = 0
        for p in self.versions_root.rglob("*.v*"):
            if p.is_file():
                p.unlink()
                removed += 1
        if self.event_bus and removed:
            await self.event_bus.emit("vault.gc.completed", {"reclaimed": removed}, space=self.space)
        return removed

    async def stats(self) -> dict[str, Any]:
        files = [p for p in self.files_root.rglob("*") if p.is_file()]
        modules = {p.parent for p in files}
        return {
            "files": len(files),
            "modules": len(modules),
            "agents_linked": len(self._linked_agents),
            "memories": self.memory.count(),
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
