# -*- coding: utf-8 -*-
"""Backtest public-boundary regressions for auth-disabled transitional mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.auth as auth
from api.middlewares.auth import add_auth_middleware
from api.v1 import api_v1_router
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import DatabaseManager


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROUTE_CLASSIFICATION_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "auth" / "backend_route_capability_inventory.json"
BACKTEST_READ_SURFACES = (
    "/api/v1/backtest/runs",
    "/api/v1/backtest/results",
    "/api/v1/backtest/performance",
    "/api/v1/backtest/rule/runs",
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


def _build_backtest_boundary_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    auth_enabled: bool,
) -> tuple[TestClient, DatabaseManager]:
    _reset_auth_globals()
    DatabaseManager.reset_instance()
    db_path = tmp_path / f"backtest-public-boundary-{auth_enabled}.db"
    env_path = tmp_path / ".env"
    env_path.write_text(
        f"ADMIN_AUTH_ENABLED={'true' if auth_enabled else 'false'}\nDATABASE_PATH={db_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(auth, "_is_auth_enabled_from_env", lambda: auth_enabled)
    auth._auth_enabled = auth_enabled

    db = DatabaseManager(db_url=f"sqlite:///{db_path}")
    app = FastAPI()
    add_auth_middleware(app)
    app.include_router(api_v1_router)
    return TestClient(app), db


def _route_inventory() -> dict[str, object]:
    return json.loads(BACKEND_ROUTE_CLASSIFICATION_FIXTURE.read_text(encoding="utf-8"))


def test_backtest_inventory_remains_authenticated_member_not_public_surface() -> None:
    inventory = _route_inventory()
    groups = {group["route_id"]: group for group in inventory["protected_groups"]}
    backtest_group = groups["backtest.member_surface"]

    assert backtest_group["surface"] == "backtest"
    assert backtest_group["auth_dependency_label"] == "authenticated_user"
    assert backtest_group["capability_label"] is None
    assert backtest_group["transitional_note"] is None
    assert backtest_group["auth_dependency_label"] not in {"public", "anonymous"}

    backtest_public_classifications = [
        entry
        for entry in inventory["route_surface_classifications"]
        if str(entry["path"]).startswith("/api/v1/backtest/")
        and entry["surface_classification"] != "authenticated_member"
    ]
    assert backtest_public_classifications == []


def test_backtest_routes_require_user_boundary_when_auth_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _build_backtest_boundary_client(tmp_path, monkeypatch, auth_enabled=True)
    try:
        responses = {path: client.get(path) for path in BACKTEST_READ_SURFACES}

        assert {path: response.status_code for path, response in responses.items()} == {
            path: 401 for path in BACKTEST_READ_SURFACES
        }
        for response in responses.values():
            assert response.json() == {"error": "unauthorized", "message": "Login required"}
    finally:
        client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()


def test_auth_disabled_backtest_transitional_access_is_no_go_not_public_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db = _build_backtest_boundary_client(tmp_path, monkeypatch, auth_enabled=False)
    try:
        responses = {path: client.get(path) for path in BACKTEST_READ_SURFACES}
        statuses = {path: response.status_code for path, response in responses.items()}
        evidence = {
            "surface": "backtest",
            "classification": "authenticated_member",
            "authMode": "disabled_transitional",
            "authDisabledPublicIngressSafe": False,
            "anonymousPublicSafe": False,
            "publicLaunchApproval": "NO-GO",
            "transitionalAccessObserved": all(status == 200 for status in statuses.values()),
            "transitionalBootstrapUserObserved": db.get_app_user(BOOTSTRAP_ADMIN_USER_ID) is not None,
            "statuses": statuses,
        }

        assert evidence == {
            "surface": "backtest",
            "classification": "authenticated_member",
            "authMode": "disabled_transitional",
            "authDisabledPublicIngressSafe": False,
            "anonymousPublicSafe": False,
            "publicLaunchApproval": "NO-GO",
            "transitionalAccessObserved": True,
            "transitionalBootstrapUserObserved": True,
            "statuses": {path: 200 for path in BACKTEST_READ_SURFACES},
        }
    finally:
        client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()
