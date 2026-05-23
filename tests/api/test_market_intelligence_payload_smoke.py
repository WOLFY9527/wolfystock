# -*- coding: utf-8 -*-
"""Authenticated local smoke for Market Intelligence payload contracts."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
from src.config import Config
from src.services.cn_hk_flow_contracts import AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID
from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.services import market_rotation_radar_service as radar_service_module
from src.storage import DatabaseManager


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "liquidity_monitor"
CN_TZ = timezone(timedelta(hours=8))


class _NoOpExecutionLogService:
    def record_market_overview_fetch(self, **_: object) -> str:
        return "market-intelligence-smoke-noop"


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


def _clear_shared_market_state() -> None:
    market_cache.clear()
    MarketOverviewService._cache.clear()
    MarketOverviewService._market_data_cache.clear()
    clear_rotation_cache = getattr(
        radar_service_module,
        "_clear_shared_rotation_radar_snapshot_cache",
        None,
    )
    if clear_rotation_cache:
        clear_rotation_cache()


def _load_liquidity_fixture(name: str) -> dict:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return LiquidityMonitorResponse(**payload).model_dump(exclude_none=True)


def _authorized_cn_hk_flow_payload() -> dict[str, object]:
    as_of = datetime.now(CN_TZ).replace(microsecond=0).isoformat()
    return {
        "providerId": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "source": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "authorized_licensed_feed",
        "asOf": as_of,
        "tradingDate": "2026-05-23",
        "session": "morning",
        "freshness": "delayed",
        "observations": [
            {"symbol": "NORTHBOUND", "value": 42.6, "unit": "亿 CNY", "currency": "CNY"},
            {"symbol": "SOUTHBOUND", "value": 28.4, "unit": "亿 HKD", "currency": "HKD"},
            {"symbol": "CN_ETF", "value": 15.8, "unit": "亿 CNY", "currency": "CNY"},
        ],
    }


def _polygon_us_breadth_activation() -> dict[str, object]:
    return {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": True,
        "observationDate": "2026-05-21",
        "previousObservationDate": "2026-05-20",
        "comparisonBasis": "previous_close",
        "asOf": "2026-05-21",
        "freshnessValid": True,
        "coverageCount": 12000,
        "previousCoverageCount": 11950,
        "comparisonCoverageCount": 11950,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "fulfilledMetrics": [
            "ADVANCERS",
            "DECLINERS",
            "UNCHANGED",
            "ADVANCE_DECLINE_RATIO",
        ],
        "missingMetrics": ["NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"],
        "reasonCodes": ["polygon_high_low_history_unavailable"],
        "metrics": {
            "advancers": 7000,
            "decliners": 4000,
            "unchanged": 1000,
            "advanceDeclineRatio": 1.75,
            "newHighs": None,
            "newLows": None,
            "highLowRatio": None,
        },
        "source": "polygon_us_grouped_daily",
        "sourceLabel": "Polygon grouped daily US equities (computed breadth)",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_or_authorized_licensed_feed",
        "trustLevel": "score_grade_for_computed_ad_metrics_when_fresh",
        "authorityBasis": "computed_from_authorized_polygon_history",
        "universe": "polygon_us_grouped_daily_ex_otc",
        "officialExchangePublishedBreadth": False,
        "fullBreadthAuthority": False,
    }


def _crypto_snapshot() -> dict[str, object]:
    updated_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
    return {
        "items": [
            {
                "symbol": "BTC",
                "label": "Bitcoin",
                "price": 71000.0,
                "value": 71000.0,
                "change": 1.5,
                "changePercent": 1.5,
                "trend": [70000.0, 71000.0],
                "source": "binance",
                "last_update": updated_at,
            }
        ],
        "last_update": updated_at,
        "updatedAt": updated_at,
        "asOf": updated_at,
        "fallback_used": False,
        "fallbackUsed": False,
        "source": "binance",
    }


@pytest.fixture(autouse=True)
def _clear_market_state() -> Iterator[None]:
    _clear_shared_market_state()
    yield
    _clear_shared_market_state()


@pytest.fixture
def authenticated_client() -> Iterator[TestClient]:
    _reset_auth_globals()
    with tempfile.TemporaryDirectory(prefix="market-intelligence-smoke-") as temp_dir:
        root = Path(temp_dir)
        env_path = root / ".env"
        db_path = root / "market-intelligence-smoke.sqlite"
        static_dir = root / "empty-static"
        static_dir.mkdir()
        env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=AAPL",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        env_overrides = {
            "ENV_FILE": str(env_path),
            "DATABASE_PATH": str(db_path),
            "ADMIN_AUTH_ENABLED": "true",
        }
        with patch.dict(os.environ, env_overrides, clear=False), patch(
            "api.app.should_auto_start_crypto_realtime",
            return_value=False,
        ), patch(
            "src.services.market_overview_service.ExecutionLogService",
            _NoOpExecutionLogService,
        ):
            Config.reset_instance()
            DatabaseManager.reset_instance()
            app = create_app(static_dir=static_dir)
            with TestClient(app, raise_server_exceptions=False) as client:
                login = client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "market-smoke",
                        "displayName": "Market Smoke",
                        "createUser": True,
                        "password": "secret123",
                        "passwordConfirm": "secret123",
                    },
                )
                assert login.status_code == 200, login.text
                yield client
            DatabaseManager.reset_instance()
            Config.reset_instance()
            _reset_auth_globals()


def test_authenticated_us_breadth_payload_smoke_uses_polygon_contract_without_exchange_claim(
    authenticated_client: TestClient,
) -> None:
    with patch(
        "src.services.market_overview_service.run_polygon_us_breadth_activation",
        return_value=_polygon_us_breadth_activation(),
    ):
        response = authenticated_client.get("/api/v1/market/us-breadth")

    assert response.status_code == 200, response.text
    payload = response.json()
    by_symbol = {item["symbol"]: item for item in payload["items"]}
    assert payload["source"] == "polygon_us_grouped_daily"
    assert payload["officialExchangePublishedBreadth"] is False
    assert payload["fullBreadthAuthority"] is False
    assert payload["breadthClaimType"] == "computed_authorized_polygon_grouped_daily_breadth"
    assert payload["broadMarketClaimAllowed"] is False
    assert payload["scoreContributionAllowed"] is True
    assert payload["authorityDiagnostics"]["reasonCodes"] == ["polygon_high_low_history_unavailable"]
    assert by_symbol["NEW_HIGHS"]["value"] is None
    assert by_symbol["NEW_HIGHS"]["scoreContributionAllowed"] is False
    assert by_symbol["NEW_HIGHS"]["sourceAuthorityReason"] == "polygon_high_low_history_unavailable"


def test_authenticated_cn_flows_payload_smoke_keeps_authorized_feed_diagnostic_only(
    authenticated_client: TestClient,
) -> None:
    with patch(
        "src.services.market_overview_service.AuthorizedCnHkConnectFlowCacheProvider",
        return_value=lambda: _authorized_cn_hk_flow_payload(),
    ):
        response = authenticated_client.get("/api/v1/market/cn-flows")

    assert response.status_code == 200, response.text
    payload = response.json()
    northbound = next(item for item in payload["items"] if item["symbol"] == "NORTHBOUND")
    southbound = next(item for item in payload["items"] if item["symbol"] == "SOUTHBOUND")
    assert payload["providerId"] == AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID
    assert payload["source"] == AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID
    assert payload["sourceType"] == "authorized_licensed_feed"
    assert payload["cacheOnly"] is True
    assert payload["externalProviderCalls"] is False
    assert payload["observationOnly"] is True
    assert payload["scoreContributionAllowed"] is False
    assert payload["sourceFreshnessEvidence"]["externalProviderCalls"] is False
    assert northbound["observationOnly"] is True
    assert northbound["scoreContributionAllowed"] is False
    assert southbound["observationOnly"] is True
    assert southbound["scoreContributionAllowed"] is False


def test_authenticated_liquidity_monitor_payload_smoke_stays_cache_only_and_caps_proxy_inputs(
    authenticated_client: TestClient,
) -> None:
    fixture_payload = _load_liquidity_fixture("missing_macro_rates_proxy_fallback_context.json")
    with patch(
        "api.v1.endpoints.liquidity_monitor.LiquidityMonitorService",
    ) as service_cls:
        service_cls.return_value.get_liquidity_monitor.return_value = fixture_payload
        response = authenticated_client.get("/api/v1/market/liquidity-monitor")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    usd_pressure = next(item for item in payload["indicators"] if item["key"] == "usd_pressure")
    breadth = next(item for item in payload["indicators"] if item["key"] == "us_breadth_proxy")
    assert usd_pressure["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert breadth["coverageDiagnostics"]["scoreContributionAllowed"] is False
    usd_input = next(item for item in usd_pressure["evidence"]["inputs"] if item["key"] == "USD_TWI")
    breadth_input = next(item for item in breadth["evidence"]["inputs"] if item["key"] == "SECTORS_UP")
    assert usd_input["freshness"] == "unavailable"
    assert usd_input["scoreContributionAllowed"] is False
    assert usd_input["sourceAuthorityReason"] == "usd_pressure_missing_series"
    assert breadth_input["observationOnly"] is True
    assert breadth_input["scoreContributionAllowed"] is False
    assert breadth_input["sourceAuthorityReason"] == "representative_sample_not_full_market_breadth"


def test_authenticated_market_overview_funds_flow_payload_smoke_keeps_proxy_wording_non_authoritative(
    authenticated_client: TestClient,
) -> None:
    quotes = {
        "SPY": {"value": 520.0, "change_pct": 0.6, "trend": [516.0, 520.0], "volume": 60_000_000},
        "QQQ": {"value": 460.0, "change_pct": 1.1, "trend": [454.0, 460.0], "volume": 45_000_000},
        "IWM": {"value": 210.0, "change_pct": -0.3, "trend": [211.0, 210.0], "volume": 22_000_000},
    }

    with patch.object(
        MarketOverviewService,
        "_latest_quote",
        autospec=True,
        side_effect=lambda _self, ticker: quotes[ticker],
    ):
        response = authenticated_client.get("/api/v1/market-overview/funds-flow")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "yfinance_proxy"
    assert payload["sourceType"] == "unofficial_public_api"
    assert payload["sourceLabel"] == "Yahoo Finance"
    assert payload["observationOnly"] is True
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert payload["sourceAuthorityReason"] == "quote_derived_etf_flow_proxy"
    assert {item["symbol"] for item in payload["items"]} == {"ETF", "INSTITUTIONAL", "INDUSTRY"}
    assert all(item["observationOnly"] is True for item in payload["items"])
    assert all(item["scoreContributionAllowed"] is False for item in payload["items"])
    assert all(item["sourceAuthorityReason"] == "quote_derived_etf_flow_proxy" for item in payload["items"])


def test_authenticated_crypto_payload_smoke_marks_sidecar_observation_unavailable_not_score_grade(
    authenticated_client: TestClient,
) -> None:
    with patch.object(
        MarketOverviewService,
        "_fetch_crypto_market_snapshot",
        autospec=True,
        return_value=_crypto_snapshot(),
    ):
        response = authenticated_client.get("/api/v1/market/crypto")

    assert response.status_code == 200, response.text
    payload = response.json()
    sidecar = payload["providerHealth"]["venueObservations"]["coinbase"]
    assert payload["source"] == "binance"
    assert payload["fallbackUsed"] is False
    assert sidecar["providerId"] == "coinbase_public"
    assert sidecar["freshness"] == "unavailable"
    assert sidecar["observationOnly"] is True
    assert sidecar["scoreContributionAllowed"] is False
    assert sidecar["degradationReason"] == "observation_unavailable"
    assert sidecar["records"] == []


def test_authenticated_rotation_radar_payload_smoke_stays_read_only_without_quote_provider(
    authenticated_client: TestClient,
) -> None:
    with patch(
        "api.v1.endpoints.market.get_rotation_radar_quote_provider",
        return_value=None,
    ):
        response = authenticated_client.get("/api/v1/market/rotation-radar?market=US")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["endpoint"] == "/api/v1/market/rotation-radar"
    assert payload["metadata"]["noExternalCalls"] is True
    assert payload["metadata"]["quoteProvider"]["present"] is False
    assert payload["metadata"]["quoteProvider"]["status"] == "absent"
    assert payload["isFallback"] is True
    assert payload["freshness"] == "fallback"
    assert payload["summary"]["eligibleThemeCount"] == 0
    assert payload["summary"]["headlineEligibleThemeCount"] == 0
    assert payload["summary"]["observationThemeCount"] == len(payload["themes"])
    assert all(theme["observationOnly"] is True for theme in payload["themes"])
    assert all(theme["scoreContributionAllowed"] is False for theme in payload["themes"])
