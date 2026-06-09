# -*- coding: utf-8 -*-
"""Regression tests for the admin SPA shell fallback guard."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.auth import create_session
from src.multi_user import ROLE_ADMIN
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
def auth_enabled_spa_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _reset_auth_globals()
    DatabaseManager.reset_instance()

    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<html>admin-spa-shell</html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('asset');\n", encoding="utf-8")

    db_path = tmp_path / "admin-spa-shell.db"
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
    client = TestClient(create_app(static_dir=static_dir))
    try:
        yield client, db
    finally:
        client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()


def _set_admin_cookie(client: TestClient, db: DatabaseManager) -> None:
    db.create_or_update_app_user(
        user_id="shell-admin",
        username="shell-admin",
        display_name="Shell Admin",
        role=ROLE_ADMIN,
        is_active=True,
    )
    client.cookies.set(
        auth.COOKIE_NAME,
        create_session(user_id="shell-admin", username="shell-admin", role=ROLE_ADMIN),
    )


@pytest.mark.parametrize(
    ("path", "expected_location"),
    [
        ("/admin", "/guest"),
        ("/admin/market-providers", "/guest"),
        ("/admin/provider-circuits", "/guest"),
        ("/zh/admin", "/zh/guest"),
        ("/zh/admin/market-providers", "/zh/guest"),
        ("/en/admin", "/en/guest"),
        ("/en/admin/provider-circuits", "/en/guest"),
    ],
)
def test_unauthenticated_direct_admin_spa_routes_redirect_to_guest(
    auth_enabled_spa_client,
    path: str,
    expected_location: str,
) -> None:
    client, _ = auth_enabled_spa_client

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == expected_location
    assert "admin-spa-shell" not in response.text


def test_authenticated_admin_keeps_direct_admin_spa_shell_access(auth_enabled_spa_client) -> None:
    client, db = auth_enabled_spa_client
    _set_admin_cookie(client, db)

    response = client.get("/admin/market-providers", follow_redirects=False)

    assert response.status_code == 200
    assert response.text == "<html>admin-spa-shell</html>"


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/guest",
        "/login",
        "/register",
        "/market-overview",
        "/zh/scanner",
        "/fr/admin/market-providers",
    ],
)
def test_admin_spa_guard_preserves_non_admin_spa_routes(auth_enabled_spa_client, path: str) -> None:
    client, _ = auth_enabled_spa_client

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 200
    assert response.text == "<html>admin-spa-shell</html>"


def test_admin_spa_guard_preserves_api_and_static_asset_behavior(auth_enabled_spa_client) -> None:
    client, _ = auth_enabled_spa_client

    bare_api = client.get("/api", follow_redirects=False)
    private_admin_api = client.get("/api/v1/admin/market-providers/operations", follow_redirects=False)
    asset = client.get("/assets/app.js", follow_redirects=False)

    assert bare_api.status_code == 404
    assert bare_api.json() == {"error": "not_found", "message": "API endpoint /api not found"}
    assert private_admin_api.status_code == 401
    assert private_admin_api.json() == {"error": "unauthorized", "message": "Login required"}
    assert asset.status_code == 200
    assert asset.text == "console.log('asset');\n"
