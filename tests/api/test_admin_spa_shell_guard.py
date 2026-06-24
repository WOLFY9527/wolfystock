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
    (static_dir / "favicon.ico").write_text("icon", encoding="utf-8")
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
    "path",
    [
        "/admin",
        "/admin/users",
        "/admin/logs",
        "/admin/system",
        "/admin/provider",
        "/admin/market-providers",
        "/admin/provider-circuits",
        "/zh/admin",
        "/zh/admin/users",
        "/zh/admin/logs",
        "/zh/admin/system",
        "/zh/admin/provider",
        "/zh/admin/market-providers",
        "/en/admin",
        "/en/admin/users",
        "/en/admin/logs",
        "/en/admin/system",
        "/en/admin/provider",
        "/en/admin/market-providers",
        "/en/admin/provider-circuits",
    ],
)
def test_unauthenticated_direct_admin_spa_routes_serve_shell_for_fail_closed_hydration(
    auth_enabled_spa_client,
    path: str,
) -> None:
    client, _ = auth_enabled_spa_client

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert response.text == "<html>admin-spa-shell</html>"


def test_authenticated_admin_keeps_direct_admin_spa_shell_access(auth_enabled_spa_client) -> None:
    client, db = auth_enabled_spa_client
    _set_admin_cookie(client, db)

    response = client.get("/admin/market-providers", follow_redirects=False)

    assert response.status_code == 200
    assert response.text == "<html>admin-spa-shell</html>"


@pytest.mark.parametrize(
    "path",
    [
        "/backtest",
        "/scanner",
        "/watchlist",
        "/holdings",
        "/scenario-lab",
        "/market-overview",
        "/research-radar",
        "/stock/600519",
        "/stock/ORCL",
        "/stock/600519/structure-decision",
        "/stocks/ORCL/structure-decision",
        "/decision-cockpit",
    ],
)
def test_core_direct_spa_routes_serve_shell_for_refresh_and_deep_links(
    auth_enabled_spa_client,
    path: str,
) -> None:
    client, _ = auth_enabled_spa_client

    response = client.get(path, follow_redirects=False)

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
    health = client.get("/api/health", follow_redirects=False)
    unknown_api = client.get("/api/does-not-exist", follow_redirects=False)
    unknown_api_v1 = client.get("/api/v1/does-not-exist", follow_redirects=False)
    scanner_status = client.get("/api/v1/scanner/status", follow_redirects=False)
    private_admin_api = client.get("/api/v1/admin/market-providers/operations", follow_redirects=False)
    asset = client.get("/assets/app.js", follow_redirects=False)
    favicon = client.get("/favicon.ico", follow_redirects=False)

    assert bare_api.status_code == 404
    assert bare_api.json() == {"error": "not_found", "message": "API endpoint /api not found"}
    assert health.status_code in {200, 503}
    assert health.headers["content-type"].startswith("application/json")
    assert "status" in health.json()
    assert unknown_api.status_code == 404
    assert unknown_api.headers["content-type"].startswith("application/json")
    assert "admin-spa-shell" not in unknown_api.text
    assert unknown_api_v1.status_code in {401, 404}
    assert unknown_api_v1.headers["content-type"].startswith("application/json")
    assert "admin-spa-shell" not in unknown_api_v1.text
    assert scanner_status.status_code == 401
    assert scanner_status.json() == {"error": "unauthorized", "message": "Login required"}
    assert private_admin_api.status_code == 401
    assert private_admin_api.json() == {"error": "unauthorized", "message": "Login required"}
    assert asset.status_code == 200
    assert asset.text == "console.log('asset');\n"
    assert favicon.status_code == 200
    assert favicon.text == "icon"


def test_admin_spa_guard_preserves_docs_and_openapi_routes(auth_enabled_spa_client) -> None:
    client, db = auth_enabled_spa_client
    _set_admin_cookie(client, db)

    docs = client.get("/docs", follow_redirects=False)
    openapi = client.get("/openapi.json", follow_redirects=False)

    assert docs.status_code == 200
    assert "Swagger UI" in docs.text
    assert openapi.status_code == 200
    assert openapi.headers["content-type"].startswith("application/json")
    assert "paths" in openapi.json()
