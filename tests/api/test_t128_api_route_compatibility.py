# -*- coding: utf-8 -*-
"""T-128 API route compatibility regression tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market_provider_operations
import src.auth as auth
from src.config import Config
from src.storage import DatabaseManager


FORBIDDEN_INTERNAL_MARKERS = (
    "authorization",
    "bearer",
    "cookie",
    "set-cookie",
    "password",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "secret",
    "private_key",
    "requestId",
    "request_id",
    "traceId",
    "trace_id",
    "exceptionClass",
    "exception_class",
    "exceptionChain",
    "exception_chain",
    "cacheKey",
    "cache_key",
    "rawCacheKey",
    "raw_cache_key",
    "Traceback",
    "<html",
    "<!doctype html",
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read", "cost:observability:read"),
    )


@pytest.fixture()
def route_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_path = tmp_path / ".env"
    db_path = tmp_path / "t128_route_compatibility.db"
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><html><body>SPA shell</body></html>", encoding="utf-8")
    env_path.write_text(
        "\n".join(
            [
                "STOCK_LIST=600519",
                "GEMINI_API_KEY=test",
                "ADMIN_AUTH_ENABLED=false",
                f"DATABASE_PATH={db_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    Config.reset_instance()
    _reset_auth_globals()
    DatabaseManager.reset_instance()

    app = create_app(static_dir=static_dir)
    app.dependency_overrides[get_current_user] = _admin_user
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        _reset_auth_globals()


def _assert_json_not_spa(response) -> dict:
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/json")
    body = response.text.lower()
    assert "<html" not in body
    assert "<!doctype html" not in body
    return response.json()


def _assert_no_forbidden_internals(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = serialized.lower()
    for marker in FORBIDDEN_INTERNAL_MARKERS:
        assert marker not in serialized
        assert marker.lower() not in lowered


def test_admin_market_provider_operations_compatibility_alias_returns_safe_json(
    route_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeOperationsService:
        def get_operations(self, *, window: str = "24h"):
            return {
                "generatedAt": "2026-06-25T00:00:00",
                "window": {"key": window, "since": window},
                "summary": {"totalItems": 0, "unavailableCount": 0},
                "items": [],
                "eventRollups": [],
                "cacheStates": [{"cacheKey": "market-overview:secret", "status": "unavailable"}],
                "limitations": ["provider_operations_observation_empty"],
                "adminLogDrillThrough": {"label": "查看 Admin Logs", "route": "/zh/admin/logs", "query": {}},
                "metadata": {
                    "source": "market_cache_and_admin_logs",
                    "readOnly": True,
                    "externalProviderCalls": False,
                    "cacheMutation": False,
                    "summaryCache": {"key": "GET:/api/v1/admin/market-providers/operations:v1:24h"},
                },
            }

    monkeypatch.setattr(market_provider_operations, "MarketProviderOperationsService", _FakeOperationsService)

    payload = _assert_json_not_spa(route_client.get("/api/v1/admin/market-provider-operations"))

    assert payload["metadata"]["readOnly"] is True
    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["items"] == []
    _assert_no_forbidden_internals(payload)


@pytest.mark.parametrize(
    "path, expected_key",
    [
        ("/api/v1/admin/provider-circuits", "metadata"),
        ("/api/v1/admin/cost/summary", "metadata"),
    ],
)
def test_admin_observability_compatibility_aliases_return_json_without_spa(
    route_client: TestClient,
    path: str,
    expected_key: str,
) -> None:
    payload = _assert_json_not_spa(route_client.get(path))

    assert expected_key in payload
    _assert_no_forbidden_internals(payload)


def test_watchlist_root_compatibility_endpoint_returns_empty_json_state(route_client: TestClient) -> None:
    payload = _assert_json_not_spa(route_client.get("/api/v1/watchlist/"))

    assert payload == {"items": []}
    _assert_no_forbidden_internals(payload)


@pytest.mark.parametrize("path", ["/api/v1/options/lab", "/api/v1/options/gamma"])
def test_options_compatibility_endpoints_return_explicit_unavailable_json(path: str, route_client: TestClient) -> None:
    payload = _assert_json_not_spa(route_client.get(path))

    serialized = json.dumps(payload, ensure_ascii=False)
    assert any(state in serialized for state in ("provider_missing", "entitlement_required", "not_available", "unavailable"))
    assert "totalDealerGammaExposure" not in payload or payload["totalDealerGammaExposure"] is None
    _assert_no_forbidden_internals(payload)
