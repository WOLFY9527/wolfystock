# -*- coding: utf-8 -*-
"""API contract tests for caller-supplied portfolio scenario risk projections."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from api.deps import CurrentUser, get_current_user
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _make_user() -> CurrentUser:
    return CurrentUser(
        user_id="scenario-risk-user",
        username="scenario-risk-user",
        display_name="Scenario Risk User",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _payload() -> dict[str, Any]:
    return {
        "asOf": "2026-05-18T09:30:00Z",
        "positions": [
            {"symbol": "NVDA", "market_value": 1000.0, "bucket": "AI Semis"},
            {"symbol": "MSFT", "marketValue": 500.0, "bucket": "Mega Cap Software"},
            {"symbol": "BND", "marketValue": 500.0, "bucket": "Defensive Bonds"},
        ],
        "exposures": [
            {"symbol": "NVDA", "label": "QQQ", "label_type": "index_proxy", "exposure": 1.0},
            {"symbol": "MSFT", "label": "QQQ", "labelType": "index_proxy", "exposure": 0.8},
            {"symbol": "NVDA", "label": "ai_theme", "labelType": "theme", "exposure": 1.0},
            {"symbol": "MSFT", "label": "ai_theme", "labelType": "theme", "exposure": 0.5},
        ],
        "scenarioShocks": [
            {"name": "nvda_gap_down", "shocks": {"NVDA": -0.10}},
            {"name": "qqq_proxy_down", "shocks": {"QQQ": -0.05}},
            {"name": "ai_theme_down", "shocks": {"ai_theme": {"shockPct": -8.0, "labelType": "theme"}}},
        ],
    }


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_walk_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_walk_keys(item))
        return keys
    return set()


class ForbiddenServicePath:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"forbidden service path called: {name}")


class ScenarioRiskClient:
    def __enter__(self) -> TestClient:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "portfolio_scenario_risk_api.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        _reset_auth_globals()
        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.app.dependency_overrides[get_current_user] = _make_user
        self.client = TestClient(self.app)
        self.auth_patch = patch("api.middlewares.auth.resolve_current_user", return_value=_make_user())
        self.auth_patch.start()
        return self.client

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.auth_patch.stop()
        self.app.dependency_overrides.clear()
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        _reset_auth_globals()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()


def test_scenario_risk_endpoint_returns_advisory_projection_from_caller_inputs() -> None:
    with ScenarioRiskClient() as client:
        response = client.post("/api/v1/portfolio/scenario-risk", json=_payload())

    assert response.status_code == 200
    payload = response.json()

    assert payload["readModelType"] == "portfolio_scenario_risk_advisory_v1"
    assert payload["advisoryOnly"] is True
    assert payload["executionReadiness"] == "advisory_only_not_trade_execution"
    assert payload["asOf"] == "2026-05-18T09:30:00Z"
    assert payload["coverage"]["totalPositions"] == 3
    assert payload["coverage"]["totalMarketValue"] == 2000.0
    assert payload["coverage"]["labelsWithExplicitCoverage"] == ["AI_THEME", "QQQ"]

    metadata = payload["metadata"]
    assert metadata["sideEffectFree"] is True
    assert metadata["noBrokerSync"] is True
    assert metadata["noAccountingMutation"] is True
    assert metadata["noOrderPlacement"] is True
    assert metadata["notInvestmentAdvice"] is True
    assert metadata["noProviderRuntime"] is True


def test_symbol_proxy_and_theme_shocks_work_from_explicit_exposures() -> None:
    with ScenarioRiskClient() as client:
        response = client.post("/api/v1/portfolio/scenario-risk", json=_payload())

    assert response.status_code == 200
    scenarios = {item["name"]: item for item in response.json()["scenarios"]}

    symbol = scenarios["nvda_gap_down"]
    assert symbol["portfolioImpactPct"] == -5.0
    assert symbol["portfolioImpactAmount"] == -100.0
    assert symbol["missingCoverage"] == []

    proxy = scenarios["qqq_proxy_down"]
    assert proxy["portfolioImpactPct"] == -3.5
    assert proxy["portfolioImpactAmount"] == -70.0
    assert proxy["missingCoverage"] == [{"label": "QQQ", "labelType": "index_proxy", "missingSymbols": ["BND"]}]
    assert proxy["positionContributions"][0]["appliedShocks"][0]["labelType"] == "index_proxy"

    theme = scenarios["ai_theme_down"]
    assert theme["portfolioImpactPct"] == -5.0
    assert theme["portfolioImpactAmount"] == -100.0
    assert theme["missingCoverage"] == [{"label": "AI_THEME", "labelType": "theme", "missingSymbols": ["BND"]}]
    assert theme["positionContributions"][0]["appliedShocks"][0]["labelType"] == "theme"


def test_missing_coverage_is_reported_not_inferred() -> None:
    payload = {
        "asOf": "2026-05-18",
        "positions": [{"symbol": "AAA", "weight": 0.6}, {"symbol": "BBB", "weight": 0.4}],
        "exposures": [{"symbol": "AAA", "label": "growth_theme", "labelType": "theme", "exposure": 1.0}],
        "scenarioShocks": [{"name": "theme_and_currency", "shocks": {"growth_theme": -0.10, "USD": 0.02}}],
    }

    with ScenarioRiskClient() as client:
        response = client.post("/api/v1/portfolio/scenario-risk", json=payload)

    assert response.status_code == 200
    scenario = response.json()["scenarios"][0]
    assert scenario["portfolioImpactPct"] == -6.0
    assert scenario["missingCoverage"] == [
        {"label": "GROWTH_THEME", "labelType": "theme", "missingSymbols": ["BBB"]},
        {"label": "USD", "labelType": "explicit_label", "missingSymbols": ["AAA", "BBB"]},
    ]
    assert response.json()["missingDataWarnings"] == ["scenario_coverage_incomplete"]


def test_forbidden_account_broker_order_and_sync_fields_are_ignored_safely() -> None:
    payload = _payload()
    payload.update(
        {
            "accountId": "acct-1",
            "brokerConnectionId": "broker-1",
            "syncToken": "secret-sync-token",
            "providerFlags": {"forceLive": True},
            "orderId": "order-1",
            "tradeSide": "buy",
            "refreshSnapshot": True,
            "portfolioMutation": True,
        }
    )

    with ScenarioRiskClient() as client:
        response = client.post("/api/v1/portfolio/scenario-risk", json=payload)

    assert response.status_code == 200
    forbidden_keys = {
        "accountId",
        "brokerConnectionId",
        "syncToken",
        "providerFlags",
        "orderId",
        "tradeSide",
        "refreshSnapshot",
        "portfolioMutation",
    }
    assert _walk_keys(response.json()).isdisjoint(forbidden_keys)


def test_endpoint_does_not_invoke_portfolio_broker_provider_fx_or_storage_paths() -> None:
    with ScenarioRiskClient() as client:
        with (
            patch("api.v1.endpoints.portfolio.PortfolioService", side_effect=AssertionError("portfolio service called")),
            patch("api.v1.endpoints.portfolio.PortfolioRiskService", side_effect=AssertionError("risk service called")),
            patch("api.v1.endpoints.portfolio.PortfolioImportService", side_effect=AssertionError("import service called")),
            patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService", side_effect=AssertionError("broker sync called")),
            patch("api.v1.endpoints.portfolio.ExecutionLogService", side_effect=AssertionError("audit log called")),
            patch(
                "api.v1.endpoints.portfolio.default_fx_rate_service",
                new=ForbiddenServicePath(),
            ),
            patch("src.storage.DatabaseManager.get_instance", side_effect=AssertionError("storage called")),
        ):
            response = client.post("/api/v1/portfolio/scenario-risk", json=_payload())

    assert response.status_code == 200


def test_guest_or_unauthorized_access_matches_portfolio_auth_convention() -> None:
    with ScenarioRiskClient() as client:
        client.app.dependency_overrides.clear()
        with patch("api.middlewares.auth.resolve_current_user", return_value=None):
            response = client.post("/api/v1/portfolio/scenario-risk", json=_payload())

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_route_registration_does_not_collide_with_existing_portfolio_paths() -> None:
    with ScenarioRiskClient() as client:
        post_paths = [
            route.path
            for route in client.app.routes
            if "POST" in getattr(route, "methods", set()) and route.path.startswith("/api/v1/portfolio")
        ]

    assert post_paths.count("/api/v1/portfolio/scenario-risk") == 1
