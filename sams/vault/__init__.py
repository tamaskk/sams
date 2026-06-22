"""The Vault — versioned storage and long-term memory (spec 3.6, 4.5).

Stores three classes of data: the codebase, artifacts, and long-term agent
memory. The reference split is Postgres/Mongo/vector-store/object-store; this
local implementation is filesystem-backed so SAMS runs with zero external infra,
behind the same interface a production deployment swaps in.
"""

from .store import LocalVault, Vault
from .memory import Memory, VaultMemory

__all__ = ["Vault", "LocalVault", "VaultMemory", "Memory"]
