"""Narrow API-owned actor projections for authenticated user-write audits."""

from __future__ import annotations

from api.deps import CurrentUser
from api.request_context import get_request_id


def project_authenticated_audit_actor(
    current_user: CurrentUser,
    *,
    request_id: str | None = None,
) -> dict[str, str | None]:
    """Project a required current user into the existing write-audit actor shape."""
    actor_role = "admin" if current_user.is_admin else "user"
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": actor_role,
        "actor_type": actor_role,
        "session_id": current_user.session_id,
        "request_id": request_id if request_id is not None else get_request_id(),
    }


__all__ = ["project_authenticated_audit_actor"]
