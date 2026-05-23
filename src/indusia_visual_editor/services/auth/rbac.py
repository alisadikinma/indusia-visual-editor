"""RBAC convenience aliases.

`require_role` lives in `dependencies.py` so that module can be imported
without pulling RBAC if a route only needs `get_current_user`. Re-exported
here to give phase 13.4 callers a single import surface and to keep room
for future role-set helpers (e.g. `require_admin_or_self`)."""

from indusia_visual_editor.services.auth.dependencies import (
    get_current_user,
    require_role,
)

require_admin = require_role("admin")
require_engineer = require_role("admin", "engineer")
require_any = require_role("admin", "engineer", "viewer")

__all__ = [
    "get_current_user",
    "require_role",
    "require_admin",
    "require_engineer",
    "require_any",
]
