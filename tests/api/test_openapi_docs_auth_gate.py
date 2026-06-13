# -*- coding: utf-8 -*-
"""Regression tests for root OpenAPI and docs auth gating."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.auth import create_session
from src.multi_user import ROLE_ADMIN, ROLE_USER
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


@pytest.fixture()
def docs_auth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_auth_globals()
    DatabaseManager.reset_instance()

    db_path = tmp_path / "docs-auth.db"
    env_path = tmp_path / ".env"
    env_path.write_text(
        f"ADMIN_AUTH_ENABLED=true\nDATABASE_PATH={db_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(auth, "_is_auth_enabled_from_env", lambda: True)
    auth._auth_enabled = True

    db = DatabaseManager(db_url=f"sqlite:///{db_path}")
    db.create_or_update_app_user(
        user_id="docs-admin",
        username="docs-admin",
        display_name="Docs Admin",
        role=ROLE_ADMIN,
        is_active=True,
    )
    db.create_or_update_app_user(
        user_id="docs-user",
        username="docs-user",
        display_name="Docs User",
        role=ROLE_USER,
        is_active=True,
    )

    client = TestClient(create_app(static_dir=tmp_path / "missing-static"))
    try:
        yield client
    finally:
        client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()


@pytest.fixture()
def docs_auth_disabled_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_auth_globals()
    DatabaseManager.reset_instance()

    db_path = tmp_path / "docs-auth-disabled.db"
    env_path = tmp_path / ".env"
    env_path.write_text(
        f"ADMIN_AUTH_ENABLED=false\nDATABASE_PATH={db_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.setattr(auth, "_get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(auth, "_is_auth_enabled_from_env", lambda: False)
    auth._auth_enabled = False

    DatabaseManager(db_url=f"sqlite:///{db_path}")
    client = TestClient(create_app(static_dir=tmp_path / "missing-static"))
    try:
        yield client
    finally:
        client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()


def _set_user_cookie(client: TestClient) -> None:
    client.cookies.set(
        auth.COOKIE_NAME,
        create_session(user_id="docs-user", username="docs-user", role=ROLE_USER),
    )


def _set_admin_cookie(client: TestClient) -> None:
    client.cookies.set(
        auth.COOKIE_NAME,
        create_session(user_id="docs-admin", username="docs-admin", role=ROLE_ADMIN),
    )


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_root_docs_surfaces_require_login_when_auth_enabled(docs_auth_client: TestClient, path: str) -> None:
    response = docs_auth_client.get(path, follow_redirects=False)

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized", "message": "Login required"}
    assert "set-cookie" not in {key.lower() for key in response.headers}
    assert "traceback" not in response.text.lower()


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_root_docs_surfaces_reject_non_admin_users_when_auth_enabled(
    docs_auth_client: TestClient,
    path: str,
) -> None:
    _set_user_cookie(docs_auth_client)

    response = docs_auth_client.get(path, follow_redirects=False)

    assert response.status_code == 403
    assert response.json() == {"error": "admin_required", "message": "Admin access required"}
    assert "docs-user" not in response.text


@pytest.mark.parametrize(
    ("path", "content_marker"),
    [
        ("/openapi.json", "\"openapi\":"),
        ("/docs", "Swagger UI"),
        ("/redoc", "ReDoc"),
    ],
)
def test_root_docs_surfaces_allow_admin_users_when_auth_enabled(
    docs_auth_client: TestClient,
    path: str,
    content_marker: str,
) -> None:
    _set_admin_cookie(docs_auth_client)

    response = docs_auth_client.get(path, follow_redirects=False)

    assert response.status_code == 200
    assert content_marker in response.text


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_root_docs_surfaces_remain_available_when_auth_disabled(
    docs_auth_disabled_client: TestClient,
    path: str,
) -> None:
    response = docs_auth_disabled_client.get(path, follow_redirects=False)

    assert response.status_code == 200


def test_existing_api_v1_openapi_surface_stays_blocked_for_anonymous_users_when_auth_enabled(
    docs_auth_client: TestClient,
) -> None:
    response = docs_auth_client.get("/api/v1/openapi.json", follow_redirects=False)

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized", "message": "Login required"}
