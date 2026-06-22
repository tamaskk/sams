"""The built-in agent catalog (spec Section 5).

Loads the shipped agent manifests from ``agents/builtin/*.agent.yaml``. Adding an
agent to the catalog is just adding a manifest here — no core change (spec 5,
6.9).
"""

from .loader import load_builtin_manifests

__all__ = ["load_builtin_manifests"]
