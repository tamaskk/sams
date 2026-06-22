"""Security & permissions (spec Section 12).

* :class:`PermissionEngine` — deny-by-default access control with separation of
  duties, plus **Development Mode** (full autonomy in dev so the build loop never
  stops; scoped to dev only).
* :class:`SecurityGate` — the enforced approval + source-control checkpoint.
"""

from .permissions import PermissionEngine, PermissionDenied
from .gate import GateRequest, SecurityGate

__all__ = ["PermissionEngine", "PermissionDenied", "SecurityGate", "GateRequest"]
