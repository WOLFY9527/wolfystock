# -*- coding: utf-8 -*-
"""Consumer-safe error envelope regressions for selected API endpoints."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    litellm_mock = MagicMock()
    litellm_mock.Router = MagicMock()
    sys.modules["litellm"] = litellm_mock

import src.auth as auth
from api.app import create_app
from api.deps import CurrentUser, get_current_user
from src.config import Config
from src.storage import DatabaseManager


RAW_LEAK_TEXT = (
    "Traceback (most recent call last): RuntimeError provider_url=https://provider.example.invalid/path "
    "/srv/wolfystock/internal.py phase=provider_fallback reasonCode=trust_gate_blocked "
    "trustLevel=raw launch verdict=NO_GO token=SECRET session_id=sess-raw api_key=sk-secret"
)

FORBIDDEN_LEAK_MARKERS = (
    "Traceback",
    "RuntimeError",
    "provider.example.invalid",
    "/srv/wolfystock/internal.py",
    "phase",
    "provider_fallback",
    "reasonCode",
    "trustLevel",
    "launch verdict",
    "token",
    "session_id",
    "api_key",
    "sk-secret",
    "SECRET",
    "detail",
    "loc",
    "input",
    "ctx",
    "type",
)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    env_path = tmp_path / ".env"
    db_path = tmp_path / "consumer_safe_errors.db"
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
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}
    Config.reset_instance()
    DatabaseManager.reset_instance()

    app = create_app(static_dir=tmp_path / "empty-static")
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="normal-user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="safe-session-id-is-not-returned",
    )
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    DatabaseManager.reset_instance()
    Config.reset_instance()
    for key in ("ENV_FILE", "DATABASE_PATH", "ADMIN_AUTH_ENABLED"):
        os.environ.pop(key, None)


def _assert_safe_error_payload(
    response,
    *,
    status_code: int,
    error: str,
    message: str,
    retryable: bool | None = None,
) -> None:
    assert response.status_code == status_code
    payload = response.json()
    assert payload["error"] == error
    assert payload["code"] == error
    assert payload["message"] == message
    assert payload["status"] == status_code
    if retryable is not None:
        assert payload["retryable"] is retryable
    assert "detail" not in payload
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for marker in FORBIDDEN_LEAK_MARKERS:
        assert marker not in serialized


def test_portfolio_internal_error_response_is_consumer_safe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingPortfolioService:
        def list_accounts(self, include_inactive: bool = False):
            raise RuntimeError(RAW_LEAK_TEXT)

    monkeypatch.setattr("api.v1.endpoints.portfolio._get_portfolio_service", lambda current_user: FailingPortfolioService())

    response = client.get("/api/v1/portfolio/accounts")

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="Portfolio data is temporarily unavailable. Please retry later.",
    )


def test_scanner_internal_error_response_is_consumer_safe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingScannerService:
        def list_runs(self, **kwargs):
            raise RuntimeError(RAW_LEAK_TEXT)

    monkeypatch.setattr("api.v1.endpoints.scanner._build_scanner_service", lambda db_manager, current_user: FailingScannerService())

    response = client.get("/api/v1/scanner/runs")

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="Scanner data is temporarily unavailable. Please retry later.",
    )


def test_watchlist_internal_error_response_is_consumer_safe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingWatchlistService:
        def list_items(self, owner_id: str):
            raise RuntimeError(RAW_LEAK_TEXT)

    monkeypatch.setattr("api.v1.endpoints.watchlist._get_watchlist_service", lambda: FailingWatchlistService())

    response = client.get("/api/v1/watchlist/items")

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="Watchlist data is temporarily unavailable. Please retry later.",
    )


def test_agent_chat_internal_error_response_is_consumer_safe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "api.v1.endpoints.agent.get_config",
        lambda: SimpleNamespace(is_agent_available=lambda: True),
    )
    monkeypatch.setattr(
        "api.v1.endpoints.agent._build_executor",
        lambda config, skills=None: (_ for _ in ()).throw(RuntimeError(RAW_LEAK_TEXT)),
    )

    response = client.post("/api/v1/agent/chat", json={"message": "summarize NVDA"})

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="AI research is temporarily unavailable. Please retry later.",
    )


def test_validation_error_response_is_consumer_safe_for_body_query_and_path(client: TestClient) -> None:
    body_response = client.post("/api/v1/agent/chat", json={})
    query_response = client.get("/api/v1/history", params={"page": 0})
    path_response = client.delete("/api/v1/portfolio/accounts/not-a-number")

    for response in (body_response, query_response, path_response):
        _assert_safe_error_payload(
            response,
            status_code=422,
            error="validation_error",
            message="请求参数验证失败",
            retryable=False,
        )
