# -*- coding: utf-8 -*-
"""Offline contracts for the pure data source routing policy foundation."""

from __future__ import annotations

import json
import subprocess
import sys

from src.services.data_source_router import (
    DataSourceRouteRequest,
    DataSourceRouter,
)
from src.services.data_source_router_diagnostics import build_data_source_route_diagnostic_snapshot


def _ids(candidates: tuple[object, ...]) -> set[str]:
    return {getattr(candidate, "provider_id") for candidate in candidates}


def test_sec_edgar_only_plans_filing_and_companyfacts_evidence_routes() -> None:
    filings_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="filings_evidence",
            capability="companyfacts",
            freshness_need="daily",
            scoring_allowed=False,
            cik="0000320193",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    quote_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="market_overview",
            capability="quote",
            freshness_need="live",
            scoring_allowed=True,
            symbol="AAPL",
            allow_network=True,
            reproducibility_required=False,
        )
    )

    assert _ids(filings_plan.primary_candidates) == {"sec_edgar"}
    assert _ids(quote_plan.primary_candidates) == set()
    assert _ids(quote_plan.observation_candidates) == set()
    assert "sec_edgar" in _ids(quote_plan.forbidden_providers)
    assert "provider_forbidden_for_use_case" in quote_plan.reason_codes["sec_edgar"]


def test_stock_evidence_route_accepts_sec_edgar_only_as_non_scoring_sidecar() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="stock",
            use_case="stock_evidence",
            capability="companyfacts",
            freshness_need="daily",
            scoring_allowed=False,
            symbol="AAPL",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(plan.primary_candidates) == {"sec_edgar"}
    assert _ids(plan.observation_candidates) == set()
    assert plan.cache_required is True
    assert plan.score_contribution_allowed is False
    assert plan.degradation_policy == "use_cached_evidence_or_explicit_unavailable"


def test_baostock_is_delayed_cn_history_observation_only_and_never_scoring() -> None:
    delayed_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity",
            use_case="market_observation",
            capability="cn_history_daily",
            freshness_need="delayed",
            scoring_allowed=False,
            symbol="000001.SZ",
            allow_network=True,
            reproducibility_required=False,
        )
    )
    realtime_score_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity",
            use_case="scanner_price_scoring",
            capability="cn_realtime_quote",
            freshness_need="live",
            scoring_allowed=True,
            symbol="000001.SZ",
            allow_network=True,
            reproducibility_required=False,
        )
    )

    assert _ids(delayed_plan.primary_candidates) == set()
    assert _ids(delayed_plan.observation_candidates) == {"baostock"}
    assert delayed_plan.cache_required is True
    assert delayed_plan.score_contribution_allowed is False
    assert all(candidate.score_contribution_allowed is False for candidate in delayed_plan.observation_candidates)
    assert "baostock" in _ids(realtime_score_plan.forbidden_providers)
    assert "scoring_not_allowed" in realtime_score_plan.reason_codes["baostock"]


def test_coinbase_public_remains_crypto_venue_sidecar_only() -> None:
    venue_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="crypto",
            asset_type="crypto",
            use_case="crypto_venue_observation",
            capability="venue_observation",
            freshness_need="live",
            scoring_allowed=False,
            product_id="BTC-USD",
            allow_network=True,
            reproducibility_required=False,
        )
    )
    market_temperature_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="crypto",
            asset_type="crypto",
            use_case="market_temperature",
            capability="quote",
            freshness_need="live",
            scoring_allowed=True,
            product_id="BTC-USD",
            allow_network=True,
            reproducibility_required=False,
        )
    )

    assert _ids(venue_plan.primary_candidates) == set()
    assert _ids(venue_plan.observation_candidates) == {"coinbase_public"}
    assert all(candidate.score_contribution_allowed is False for candidate in venue_plan.observation_candidates)
    assert "coinbase_public" in _ids(market_temperature_plan.forbidden_providers)
    assert "provider_observation_only" in market_temperature_plan.reason_codes["coinbase_public"]
    assert "scoring_not_allowed" in market_temperature_plan.reason_codes["coinbase_public"]


def test_liquidity_score_grade_crypto_quote_rejects_coinbase_public_as_scoring_provider() -> None:
    liquidity_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="crypto",
            asset_type="crypto",
            use_case="liquidity_score",
            capability="quote",
            freshness_need="live",
            scoring_allowed=True,
            product_id="BTC-USD",
            allow_network=True,
            reproducibility_required=False,
        )
    )

    assert "coinbase_public" in _ids(liquidity_plan.forbidden_providers)
    assert "provider_observation_only" in liquidity_plan.reason_codes["coinbase_public"]
    assert "scoring_not_allowed" in liquidity_plan.reason_codes["coinbase_public"]
    assert liquidity_plan.score_contribution_allowed is True


def test_live_score_grade_routes_reject_yfinance_and_proxy_observations() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="market_overview",
            capability="quote",
            freshness_need="live",
            scoring_allowed=True,
            symbol="AAPL",
            allow_network=True,
            reproducibility_required=False,
        )
    )

    assert "yfinance_current_baseline" in _ids(plan.forbidden_providers)
    assert "provider_forbidden_for_use_case" in plan.reason_codes["yfinance_current_baseline"]
    assert "score_inputs" in plan.reason_codes["yfinance_current_baseline"]
    assert plan.required_source_types == ("official_public", "exchange_public", "cache_snapshot")
    assert plan.freshness_floor == "live"
    assert plan.trust_floor == "score_grade"


def test_route_diagnostic_snapshot_serializes_required_fields_without_runtime_calls() -> None:
    request = DataSourceRouteRequest(
        market="US",
        asset_type="equity",
        use_case="filings_evidence",
        capability="companyfacts",
        freshness_need="daily",
        scoring_allowed=False,
        cik="0000320193",
        allow_network=False,
        reproducibility_required=False,
    )

    snapshot = build_data_source_route_diagnostic_snapshot(request).to_dict()

    assert snapshot["diagnosticOnly"] is True
    assert snapshot["providerRuntimeCalled"] is False
    assert snapshot["networkCallsEnabled"] is False
    assert set(snapshot) == {
        "diagnosticOnly",
        "providerRuntimeCalled",
        "networkCallsEnabled",
        "request",
        "primaryCandidates",
        "observationCandidates",
        "forbiddenProviders",
        "cacheRequired",
        "backgroundRefreshRequired",
        "scoreContributionAllowed",
        "degradationPolicy",
        "requiredSourceTypes",
        "freshnessFloor",
        "trustFloor",
        "reasonCodes",
    }

    assert snapshot["request"] == {
        "market": "US",
        "assetType": "equity",
        "useCase": "filings_evidence",
        "capability": "companyfacts",
        "freshnessNeed": "daily",
        "scoringAllowed": False,
        "symbol": None,
        "productId": None,
        "cik": "0000320193",
        "asOf": None,
        "allowNetwork": False,
        "reproducibilityRequired": False,
    }
    assert len(snapshot["primaryCandidates"]) == 1
    assert snapshot["primaryCandidates"][0] == {
        "providerId": "sec_edgar",
        "providerName": "SEC EDGAR",
        "capability": "companyfacts",
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "trustLevel": "reliable_for_filings_metadata",
        "freshnessExpectation": "filing_or_daily",
        "observationOnly": True,
        "scoreContributionAllowed": False,
    }
    assert snapshot["observationCandidates"] == []
    assert "baostock" in {item["providerId"] for item in snapshot["forbiddenProviders"]}
    assert snapshot["cacheRequired"] is True
    assert snapshot["backgroundRefreshRequired"] is True
    assert snapshot["scoreContributionAllowed"] is False
    assert snapshot["degradationPolicy"] == "use_cached_evidence_or_explicit_unavailable"
    assert snapshot["requiredSourceTypes"] == ["official_public", "cache_snapshot"]
    assert snapshot["freshnessFloor"] == "daily"
    assert snapshot["trustFloor"] == "filings_evidence"
    assert snapshot["reasonCodes"]["plan"] == ["cache_required"]


def test_backtest_requires_reproducible_local_or_stored_data() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="backtest",
            capability="ohlcv",
            freshness_need="cached",
            scoring_allowed=True,
            symbol="AAPL",
            allow_network=False,
            reproducibility_required=True,
        )
    )

    assert _ids(plan.primary_candidates) == {"local_cache", "local_ohlcv"}
    assert _ids(plan.observation_candidates) == set()
    assert plan.cache_required is True
    assert plan.background_refresh_required is False
    assert plan.score_contribution_allowed is True
    assert plan.degradation_policy == "fail_closed_without_reproducible_store"
    assert "reproducible_data_required" in plan.reason_codes["plan"]
    assert "cache_required" in plan.reason_codes["plan"]
    assert "coinbase_public" in _ids(plan.forbidden_providers)
    assert "provider_observation_only" in plan.reason_codes["coinbase_public"]


def test_allow_network_false_marks_live_routes_as_cache_only_degradation() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="market_overview",
            capability="quote",
            freshness_need="live",
            scoring_allowed=True,
            symbol="AAPL",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert plan.cache_required is True
    assert "live_network_forbidden" in plan.reason_codes["plan"]


def test_router_import_is_pure_and_does_not_load_provider_runtime_modules() -> None:
    script = """
import json
import sys
import src.services.data_source_router

blocked = [
    "requests",
    "httpx",
    "yfinance",
    "baostock",
    "akshare",
    "openbb",
    "data_provider.base",
    "data_provider.baostock_fetcher",
    "data_provider.sec_edgar_provider",
    "src.services.market_overview_service",
    "src.services.liquidity_monitor_service",
    "src.services.market_rotation_radar_service",
]
print(json.dumps({name: name in sys.modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
