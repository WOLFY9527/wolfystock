# -*- coding: utf-8 -*-
"""Consumer-safe error envelope regressions for selected API endpoints."""

from __future__ import annotations

import json
import logging
import os
import re
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
    expected_detail: dict[str, object] | None = None,
) -> None:
    assert response.status_code == status_code
    payload = response.json()
    assert payload["error"] == error
    assert payload["code"] == error
    assert payload["message"] == message
    assert payload["status"] == status_code
    if retryable is not None:
        assert payload["retryable"] is retryable
    if expected_detail is None:
        assert "detail" not in payload
    else:
        assert payload.get("detail") == expected_detail
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden_markers = FORBIDDEN_LEAK_MARKERS
    if expected_detail is not None:
        forbidden_markers = tuple(
            marker for marker in forbidden_markers if marker not in {"detail", "reasonCode"}
        )
    for marker in forbidden_markers:
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


def test_history_internal_error_response_is_consumer_safe_and_logged(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    history_failure = "history service failure marker"

    class FailingHistoryService:
        def get_history_list(self, **kwargs):
            raise RuntimeError(history_failure)

    monkeypatch.setattr(
        "api.v1.endpoints.history._build_history_service",
        lambda db_manager, current_user: FailingHistoryService(),
    )
    caplog.set_level(logging.ERROR, logger="api.v1.endpoints.history")

    response = client.get("/api/v1/history")

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="History data is temporarily unavailable. Please retry later.",
    )
    assert history_failure in caplog.text


def test_history_detail_internal_error_preserves_report_id_without_raw_exception(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    report_id = "report-safe-id-291"

    class FailingHistoryService:
        def resolve_and_get_detail(self, _record_id: str):
            raise RuntimeError(RAW_LEAK_TEXT)

    monkeypatch.setattr(
        "api.v1.endpoints.history._build_history_service",
        lambda db_manager, current_user: FailingHistoryService(),
    )
    caplog.set_level(logging.ERROR, logger="api.v1.endpoints.history")

    response = client.get(f"/api/v1/history/{report_id}")

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="History data is temporarily unavailable. Please retry later.",
        retryable=True,
        expected_detail={"reportId": report_id, "reasonCode": "history_internal_error"},
    )
    assert RAW_LEAK_TEXT in caplog.text


def test_history_detail_internal_error_omits_unsafe_report_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsafe_report_id = "token=SECRET"

    class FailingHistoryService:
        def resolve_and_get_detail(self, _record_id: str):
            raise RuntimeError(RAW_LEAK_TEXT)

    monkeypatch.setattr(
        "api.v1.endpoints.history._build_history_service",
        lambda db_manager, current_user: FailingHistoryService(),
    )

    response = client.get(f"/api/v1/history/{unsafe_report_id}")

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="History data is temporarily unavailable. Please retry later.",
        retryable=True,
        expected_detail={"reasonCode": "history_internal_error"},
    )


def test_analysis_sync_internal_error_preserves_request_and_task_ids_without_raw_exception(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_analysis(*_args, **_kwargs):
        raise RuntimeError(RAW_LEAK_TEXT)

    monkeypatch.setattr("api.v1.endpoints.analysis._raise_if_llm_model_unavailable", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("src.services.analysis_service.AnalysisService.analyze_stock", fail_analysis)
    caplog.set_level(logging.ERROR, logger="api.v1.endpoints.analysis")

    response = client.post(
        "/api/v1/analysis/analyze",
        json={"stock_code": "AAPL", "async_mode": False},
    )

    assert response.status_code == 500
    payload = response.json()
    request_id = payload.get("detail", {}).get("requestId")
    task_id = payload.get("detail", {}).get("taskId")
    assert isinstance(request_id, str) and re.fullmatch(r"[a-f0-9]{32}", request_id)
    assert task_id == request_id
    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="AI analysis is temporarily unavailable. Please retry later.",
        retryable=True,
        expected_detail={
            "requestId": request_id,
            "taskId": task_id,
            "reasonCode": "analysis_internal_error",
        },
    )
    assert RAW_LEAK_TEXT in caplog.text


def test_analysis_status_internal_error_preserves_task_id_without_raw_exception(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    task_id = "task-safe-id-291"

    class FailingAnalysisRepository:
        def __init__(self, *args, **kwargs):
            pass

        def get_latest_record(self, **kwargs):
            raise RuntimeError(RAW_LEAK_TEXT)

    monkeypatch.setattr("api.v1.endpoints.analysis.AnalysisRepository", FailingAnalysisRepository)
    caplog.set_level(logging.ERROR, logger="api.v1.endpoints.analysis")

    response = client.get(f"/api/v1/analysis/status/{task_id}")

    _assert_safe_error_payload(
        response,
        status_code=500,
        error="internal_error",
        message="Analysis task status is temporarily unavailable. Please retry later.",
        retryable=True,
        expected_detail={"taskId": task_id, "reasonCode": "analysis_status_internal_error"},
    )
    assert RAW_LEAK_TEXT in caplog.text


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
