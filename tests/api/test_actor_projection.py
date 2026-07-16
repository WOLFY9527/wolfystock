"""API-owned authenticated audit actor projection contracts."""

from __future__ import annotations

import importlib

from api.deps import CurrentUser
from api.v1.endpoints import (
    admin_portfolio,
    agent,
    analysis,
    market,
    portfolio,
    user_alerts,
    watchlist,
)
from src.auth_context import AdminActorContext


def _load_projection():
    try:
        module = importlib.import_module("api.actor_projection")
    except ModuleNotFoundError as exc:
        raise AssertionError("API actor projection helper is missing") from exc
    return module.project_authenticated_audit_actor


def _ordinary_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-actor-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="user-session-1",
    )


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="admin-actor-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="admin-session-1",
    )


def test_authenticated_audit_actor_projection_preserves_ordinary_current_user_fields() -> None:
    assert _load_projection()(_ordinary_user()) == {
        "user_id": "user-actor-1",
        "username": "alice",
        "display_name": "Alice",
        "role": "user",
        "actor_type": "user",
        "session_id": "user-session-1",
    }


def test_authenticated_audit_actor_projection_preserves_admin_identity() -> None:
    assert _load_projection()(_admin_user()) == {
        "user_id": "admin-actor-1",
        "username": "admin",
        "display_name": "Admin",
        "role": "admin",
        "actor_type": "admin",
        "session_id": "admin-session-1",
    }


def test_affected_endpoint_audit_recorders_share_one_projection() -> None:
    projection = _load_projection()

    for endpoint in (agent, portfolio, user_alerts, watchlist):
        assert endpoint.project_authenticated_audit_actor is projection
        assert not hasattr(endpoint, "_actor")


def test_guest_public_and_admin_audit_actor_shapes_remain_distinct() -> None:
    guest = analysis._guest_actor("guest-session-1", "guest-query-1")
    public = market._actor(None)
    admin_audit = admin_portfolio._to_admin_actor(_admin_user())

    assert guest == {
        "actor_type": "guest",
        "role": "guest",
        "session_id": "guest-session-1",
        "request_id": "guest-query-1",
        "display_name": "Guest",
    }
    assert public == {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"}
    assert admin_audit == AdminActorContext(
        user_id="admin-actor-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
    )
