# -*- coding: utf-8 -*-
"""Offline contracts for the pure data source routing policy foundation."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

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


def test_scanner_diagnostics_routes_cn_observation_sidecars_as_observation_only() -> None:
    stock_list_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity",
            use_case="scanner_diagnostics",
            capability="cn_stock_list",
            freshness_need="delayed",
            scoring_allowed=False,
            symbol="000001.SZ",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    snapshot_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity",
            use_case="scanner_diagnostics",
            capability="cn_realtime_snapshot",
            freshness_need="delayed",
            scoring_allowed=False,
            symbol="000001.SZ",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    history_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity",
            use_case="scanner_diagnostics",
            capability="cn_history_daily",
            freshness_need="delayed",
            scoring_allowed=False,
            symbol="000001.SZ",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(stock_list_plan.primary_candidates) == set()
    assert _ids(stock_list_plan.observation_candidates) == {"akshare"}
    assert stock_list_plan.cache_required is True
    assert stock_list_plan.score_contribution_allowed is False
    assert all(candidate.observation_only is True for candidate in stock_list_plan.observation_candidates)
    assert all(candidate.score_contribution_allowed is False for candidate in stock_list_plan.observation_candidates)

    assert _ids(snapshot_plan.primary_candidates) == set()
    assert _ids(snapshot_plan.observation_candidates) == {"akshare"}
    assert snapshot_plan.cache_required is True
    assert snapshot_plan.score_contribution_allowed is False
    assert all(candidate.observation_only is True for candidate in snapshot_plan.observation_candidates)
    assert all(candidate.score_contribution_allowed is False for candidate in snapshot_plan.observation_candidates)

    assert _ids(history_plan.primary_candidates) == set()
    assert _ids(history_plan.observation_candidates) == {"pytdx", "baostock"}
    assert history_plan.cache_required is True
    assert history_plan.score_contribution_allowed is False
    assert all(candidate.observation_only is True for candidate in history_plan.observation_candidates)
    assert all(candidate.score_contribution_allowed is False for candidate in history_plan.observation_candidates)


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


def test_market_temperature_route_rejects_akshare_and_pytdx_as_scoring_authorities() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity_index",
            use_case="market_temperature",
            capability="quote",
            freshness_need="live",
            scoring_allowed=True,
            symbol="000001.SH",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert "akshare" in _ids(plan.forbidden_providers)
    assert "pytdx_existing_baseline" in _ids(plan.forbidden_providers)
    assert "provider_forbidden_for_use_case" in plan.reason_codes["akshare"]
    assert "provider_forbidden_for_use_case" in plan.reason_codes["pytdx_existing_baseline"]


def test_market_briefing_routes_keep_authority_checks_diagnostic_only() -> None:
    crypto_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="crypto",
            asset_type="crypto",
            use_case="market_briefing",
            capability="crypto_ticker",
            freshness_need="live",
            scoring_allowed=False,
            product_id="BTC-USD",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    index_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity_index",
            use_case="market_briefing",
            capability="index_quote",
            freshness_need="live",
            scoring_allowed=False,
            symbol="000001.SH",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert crypto_plan.score_contribution_allowed is False
    assert crypto_plan.required_source_types == ("official_public", "exchange_public", "cache_snapshot")
    assert crypto_plan.freshness_floor == "live"
    assert crypto_plan.trust_floor == "score_grade"
    assert "live_network_forbidden" in crypto_plan.reason_codes["plan"]
    assert "coinbase_public" in _ids(crypto_plan.forbidden_providers)
    assert "provider_forbidden_for_use_case" in crypto_plan.reason_codes["coinbase_public"]

    forbidden = _ids(index_plan.forbidden_providers)
    assert {"akshare", "baostock", "pytdx_existing_baseline", "sec_edgar", "yfinance_current_baseline", "yahooquery"}.issubset(forbidden)
    assert "provider_forbidden_for_use_case" in index_plan.reason_codes["akshare"]
    assert "provider_forbidden_for_use_case" in index_plan.reason_codes["sec_edgar"]


def test_market_overview_observation_routes_keep_coinbase_pytdx_and_akshare_non_scoring() -> None:
    coinbase_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="crypto",
            asset_type="crypto",
            use_case="venue_observation",
            capability="venue_ticker",
            freshness_need="delayed",
            scoring_allowed=False,
            product_id="BTC-USD",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    pytdx_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity",
            use_case="market_observation",
            capability="cn_realtime_quote",
            freshness_need="delayed",
            scoring_allowed=False,
            symbol="000001.SZ",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    akshare_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="equity",
            use_case="market_observation",
            capability="cn_market_stats",
            freshness_need="delayed",
            scoring_allowed=False,
            symbol="000001.SZ",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(coinbase_plan.primary_candidates) == set()
    assert _ids(coinbase_plan.observation_candidates) == {"coinbase_public"}
    assert coinbase_plan.cache_required is True
    assert coinbase_plan.score_contribution_allowed is False

    assert _ids(pytdx_plan.primary_candidates) == set()
    assert _ids(pytdx_plan.observation_candidates) == {"pytdx"}
    assert pytdx_plan.cache_required is True
    assert pytdx_plan.score_contribution_allowed is False

    assert _ids(akshare_plan.primary_candidates) == set()
    assert _ids(akshare_plan.observation_candidates) == {"akshare"}
    assert akshare_plan.cache_required is True
    assert akshare_plan.score_contribution_allowed is False


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


def test_liquidity_score_grade_quote_rejects_akshare_as_scoring_provider() -> None:
    liquidity_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="liquidity_score",
            capability="quote",
            freshness_need="delayed",
            scoring_allowed=True,
            symbol="SPY",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert "akshare" in _ids(liquidity_plan.forbidden_providers)
    assert "provider_forbidden_for_use_case" in liquidity_plan.reason_codes["akshare"]
    assert liquidity_plan.score_contribution_allowed is True


def test_rotation_radar_quote_route_rejects_yfinance_as_score_grade_authority() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="rotation_radar",
            capability="quote",
            freshness_need="live",
            scoring_allowed=True,
            symbol="QQQ",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert "yfinance_current_baseline" in _ids(plan.forbidden_providers)
    assert "provider_forbidden_for_use_case" in plan.reason_codes["yfinance_current_baseline"]
    assert "score_inputs" in plan.reason_codes["yfinance_current_baseline"]
    assert "provider_not_capable" in plan.reason_codes["yfinance_current_baseline"]
    assert plan.required_source_types == ("official_public", "exchange_public", "cache_snapshot")
    assert plan.freshness_floor == "live"
    assert plan.trust_floor == "score_grade"
    assert "live_network_forbidden" in plan.reason_codes["plan"]
    assert plan.cache_required is True
    assert plan.score_contribution_allowed is True


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


def test_market_regime_and_liquidity_impulse_routes_surface_missing_authorized_us_flow_and_breadth() -> None:
    flow_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="market_regime",
            capability="us_etf_flow_daily",
            freshness_need="daily",
            scoring_allowed=False,
            symbol="SPY",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    breadth_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="liquidity_impulse",
            capability="us_market_breadth_constituents",
            freshness_need="daily",
            scoring_allowed=False,
            symbol="SPY",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(flow_plan.primary_candidates) == {"authorized.us_etf_flow"}
    assert _ids(flow_plan.observation_candidates) == set()
    assert flow_plan.cache_required is True
    assert flow_plan.score_contribution_allowed is False
    assert flow_plan.degradation_policy == "require_authorized_feed_or_explicit_missing"
    assert {
        "missing_provider_configuration",
        "authorization_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(flow_plan.reason_codes["plan"]))
    assert {"yfinance_current_baseline", "yahooquery", "akshare", "baostock", "coinbase_public"}.issubset(
        _ids(flow_plan.forbidden_providers)
    )

    flow_candidate = flow_plan.primary_candidates[0]
    assert flow_candidate.missing_provider_reason == "authorized_us_etf_flow_feed_not_configured"
    assert flow_candidate.paid_data_likely_required is True
    assert flow_candidate.key_required is True
    assert flow_candidate.no_default_live_http_calls is True

    assert _ids(breadth_plan.primary_candidates) == {"official_or_authorized.us_market_breadth"}
    assert _ids(breadth_plan.observation_candidates) == set()
    assert breadth_plan.cache_required is True
    assert breadth_plan.score_contribution_allowed is False
    assert breadth_plan.degradation_policy == "require_authorized_feed_or_explicit_missing"
    assert {
        "missing_provider_configuration",
        "authorization_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(breadth_plan.reason_codes["plan"]))
    assert {
        "yfinance_current_baseline",
        "yahooquery",
        "akshare",
        "baostock",
        "pytdx_existing_baseline",
    }.issubset(_ids(breadth_plan.forbidden_providers))

    breadth_candidate = breadth_plan.primary_candidates[0]
    assert breadth_candidate.missing_provider_reason == "authorized_us_market_breadth_feed_not_configured"
    assert breadth_candidate.paid_data_likely_required is True
    assert breadth_candidate.key_required is True
    assert breadth_candidate.no_default_live_http_calls is True


def test_liquidity_score_uses_canonical_us_etf_flow_daily_route() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="fund",
            use_case="liquidity_score",
            capability="us_etf_flow_daily",
            freshness_need="daily",
            scoring_allowed=True,
            symbol="ETF",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(plan.primary_candidates) == {"authorized.us_etf_flow"}
    assert _ids(plan.observation_candidates) == set()
    assert plan.cache_required is True
    assert plan.score_contribution_allowed is True
    assert plan.degradation_policy == "require_authorized_feed_or_explicit_missing"
    assert {
        "cache_required",
        "missing_provider_configuration",
        "authorization_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(plan.reason_codes["plan"]))


def test_legacy_etf_flow_alias_fails_closed_without_canonical_route() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="fund",
            use_case="liquidity_score",
            capability="etf_flow",
            freshness_need="daily",
            scoring_allowed=True,
            symbol="ETF",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(plan.primary_candidates) == set()
    assert _ids(plan.observation_candidates) == set()
    assert plan.score_contribution_allowed is False
    assert plan.degradation_policy == "reject_legacy_capability_alias"
    assert {
        "legacy_capability_alias_rejected",
        "canonical_capability_required",
    }.issubset(set(plan.reason_codes["plan"]))


def test_authorized_us_breadth_detail_routes_stay_missing_and_fail_closed_for_scoring() -> None:
    advancers_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="liquidity_impulse",
            capability="us_advancers_decliners",
            freshness_need="daily",
            scoring_allowed=False,
            symbol="SPY",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    highs_lows_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="market_overview",
            capability="us_new_highs_lows",
            freshness_need="daily",
            scoring_allowed=False,
            symbol="SPY",
            allow_network=False,
            reproducibility_required=False,
        )
    )
    above_ma_plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="market_regime",
            capability="us_above_ma_breadth",
            freshness_need="daily",
            scoring_allowed=False,
            symbol="SPY",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    for plan in (advancers_plan, highs_lows_plan, above_ma_plan):
        assert _ids(plan.primary_candidates) == {"official_or_authorized.us_market_breadth"}
        assert _ids(plan.observation_candidates) == set()
        assert plan.cache_required is True
        assert plan.score_contribution_allowed is False
        assert {
            "missing_provider_configuration",
            "authorization_required",
            "freshness_floor_required",
            "coverage_floor_required",
        }.issubset(set(plan.reason_codes["plan"]))
        assert {
            "yfinance_current_baseline",
            "yahooquery",
            "akshare",
            "baostock",
            "pytdx_existing_baseline",
        }.issubset(_ids(plan.forbidden_providers))

    forbidden = {
        candidate.provider_id: set(advancers_plan.reason_codes[candidate.provider_id])
        for candidate in advancers_plan.forbidden_providers
    }
    assert "provider_forbidden_for_use_case" in forbidden["yfinance_current_baseline"]
    assert "provider_not_capable" in forbidden["yfinance_current_baseline"]


def test_rotation_radar_true_flow_route_rejects_proxy_and_exchange_snapshot_replacements() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="equity",
            use_case="rotation_radar",
            capability="us_sector_etf_flow",
            freshness_need="daily",
            scoring_allowed=False,
            symbol="XLK",
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(plan.primary_candidates) == {"authorized.us_etf_flow"}
    assert plan.score_contribution_allowed is False
    assert {
        "missing_provider_configuration",
        "authorization_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(plan.reason_codes["plan"]))
    assert "yfinance_current_baseline" in _ids(plan.forbidden_providers)
    assert "yahooquery" in _ids(plan.forbidden_providers)
    assert "coinbase_public" in _ids(plan.forbidden_providers)
    assert "provider_forbidden_for_use_case" in plan.reason_codes["yfinance_current_baseline"]
    assert "provider_forbidden_for_use_case" in plan.reason_codes["coinbase_public"]
    assert "provider_not_capable" in plan.reason_codes["yfinance_current_baseline"]


def test_official_fed_liquidity_contract_routes_stay_missing_cache_required_and_non_scoring() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="US",
            asset_type="macro",
            use_case="liquidity_impulse",
            capability="fed_liquidity",
            freshness_need="daily",
            scoring_allowed=False,
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(plan.primary_candidates) == {"official_public.fed_liquidity"}
    assert _ids(plan.observation_candidates) == set()
    assert plan.cache_required is True
    assert plan.background_refresh_required is True
    assert plan.score_contribution_allowed is False
    assert plan.degradation_policy == "require_official_release_cache_or_explicit_missing"
    assert plan.required_source_types == ("official_public", "cache_snapshot")
    assert plan.freshness_floor == "delayed"
    assert plan.trust_floor == "official_liquidity_context_or_missing"
    assert {
        "cache_required",
        "missing_provider_configuration",
        "release_schedule_required",
        "release_lag_expected",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(plan.reason_codes["plan"]))
    assert {
        "coinbase_public",
        "yfinance_current_baseline",
        "yahooquery",
        "akshare",
        "baostock",
        "pytdx_existing_baseline",
    }.issubset(_ids(plan.forbidden_providers))

    candidate = plan.primary_candidates[0]
    assert candidate.source_type == "official_public"
    assert candidate.source_tier == "official_public"
    assert candidate.observation_only is True
    assert candidate.score_contribution_allowed is False
    assert candidate.missing_provider_reason == "official_fed_liquidity_contract_not_configured"


def test_cn_money_market_contract_routes_stay_missing_cache_required_and_non_scoring() -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market="CN",
            asset_type="macro",
            use_case="market_overview",
            capability="cn_money_market_rates",
            freshness_need="delayed",
            scoring_allowed=False,
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(plan.primary_candidates) == {"official_public.cn_money_market_rates"}
    assert _ids(plan.observation_candidates) == set()
    assert plan.cache_required is True
    assert plan.background_refresh_required is True
    assert plan.score_contribution_allowed is False
    assert plan.degradation_policy == "require_official_release_cache_or_explicit_missing"
    assert plan.required_source_types == ("official_public", "cache_snapshot")
    assert plan.freshness_floor == "delayed"
    assert plan.trust_floor == "official_liquidity_context_or_missing"
    assert {
        "cache_required",
        "missing_provider_configuration",
        "session_calendar_required",
        "holiday_calendar_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(plan.reason_codes["plan"]))
    assert {
        "coinbase_public",
        "yfinance_current_baseline",
        "yahooquery",
        "akshare",
        "baostock",
        "pytdx_existing_baseline",
    }.issubset(_ids(plan.forbidden_providers))

    candidate = plan.primary_candidates[0]
    assert candidate.source_type == "missing"
    assert candidate.source_tier == "official_public"
    assert candidate.observation_only is True
    assert candidate.score_contribution_allowed is False
    assert candidate.missing_provider_reason == "official_cn_money_market_rates_contract_not_configured"


@pytest.mark.parametrize(
    (
        "use_case",
        "market",
        "asset_type",
        "capability",
        "expected_provider_id",
        "expected_source_tier",
        "expected_missing_reason",
        "expected_reason_codes",
    ),
    [
        (
            "liquidity_impulse",
            "forex",
            "forex",
            "fx_dxy",
            "official_or_authorized.fx_dxy",
            "official_or_authorized_fx_feed",
            "authorized_dxy_feed_not_configured",
            {
                "cache_required",
                "missing_provider_configuration",
                "authorization_required",
                "session_market_hours_required",
                "freshness_floor_required",
                "coverage_floor_required",
            },
        ),
        (
            "market_overview",
            "CN",
            "equity",
            "cn_hk_connect_flow",
            "authorized.cn_hk_connect_flow",
            "authorized_licensed_feed",
            "authorized_cn_hk_connect_flow_feed_not_configured",
            {
                "cache_required",
                "missing_provider_configuration",
                "authorization_required",
                "session_calendar_required",
                "coverage_floor_required",
            },
        ),
        (
            "liquidity_impulse",
            "US",
            "futures",
            "index_futures",
            "exchange_or_broker_authorized.index_futures",
            "exchange_or_broker_authorized_feed",
            "authorized_index_futures_feed_not_configured",
            {
                "cache_required",
                "missing_provider_configuration",
                "authorization_required",
                "extended_hours_session_required",
                "freshness_floor_required",
                "coverage_floor_required",
            },
        ),
        (
            "rotation_radar",
            "US",
            "equity",
            "real_sector_theme_flow_evidence",
            "authorized.real_sector_theme_flow",
            "authorized_licensed_feed",
            "authorized_real_sector_theme_flow_not_configured",
            {
                "cache_required",
                "missing_provider_configuration",
                "authorization_required",
                "taxonomy_to_real_flow_mapping_required",
                "freshness_floor_required",
                "coverage_floor_required",
            },
        ),
    ],
)
def test_missing_market_intelligence_authority_contracts_route_as_explicit_non_scoring_gaps(
    use_case: str,
    market: str,
    asset_type: str,
    capability: str,
    expected_provider_id: str,
    expected_source_tier: str,
    expected_missing_reason: str,
    expected_reason_codes: set[str],
) -> None:
    plan = DataSourceRouter.resolve(
        DataSourceRouteRequest(
            market=market,
            asset_type=asset_type,
            use_case=use_case,
            capability=capability,
            freshness_need="daily",
            scoring_allowed=False,
            allow_network=False,
            reproducibility_required=False,
        )
    )

    assert _ids(plan.primary_candidates) == {expected_provider_id}
    assert _ids(plan.observation_candidates) == set()
    assert plan.cache_required is True
    assert plan.score_contribution_allowed is False
    assert expected_reason_codes.issubset(set(plan.reason_codes["plan"]))

    candidate = plan.primary_candidates[0]
    assert candidate.source_type == "missing"
    assert candidate.source_tier == expected_source_tier
    assert candidate.observation_only is True
    assert candidate.score_contribution_allowed is False
    assert candidate.missing_provider_reason == expected_missing_reason
    if capability == "index_futures":
        assert plan.required_symbols == ("NQ", "ES", "YM", "RTY")
        assert plan.session == "extended_hours"


def test_route_diagnostic_snapshot_serializes_missing_provider_fields_for_authorized_flow_contracts() -> None:
    request = DataSourceRouteRequest(
        market="US",
        asset_type="equity",
        use_case="liquidity_impulse",
        capability="us_etf_creation_redemption",
        freshness_need="daily",
        scoring_allowed=False,
        symbol="SPY",
        allow_network=False,
        reproducibility_required=False,
    )

    snapshot = build_data_source_route_diagnostic_snapshot(request).to_dict()

    assert snapshot["primaryCandidates"] == [
        {
            "providerId": "authorized.us_etf_flow",
            "providerName": "Authorized US ETF Flow",
            "capability": "us_etf_creation_redemption",
            "sourceType": "missing",
            "sourceTier": "authorized_licensed_feed",
            "trustLevel": "score_grade_when_configured",
            "freshnessExpectation": "licensed_daily_or_delayed_fund_flow",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "paidDataLikelyRequired": True,
            "keyRequired": True,
            "enabledByDefault": False,
            "noDefaultLiveHttpCalls": True,
            "missingProviderReason": "authorized_us_etf_flow_feed_not_configured",
        }
    ]


def test_route_diagnostic_snapshot_serializes_official_liquidity_contract_fields() -> None:
    request = DataSourceRouteRequest(
        market="US",
        asset_type="macro",
        use_case="liquidity_impulse",
        capability="fed_liquidity",
        freshness_need="daily",
        scoring_allowed=False,
        allow_network=False,
        reproducibility_required=False,
    )

    snapshot = build_data_source_route_diagnostic_snapshot(request).to_dict()

    assert snapshot["primaryCandidates"] == [
        {
            "providerId": "official_public.fed_liquidity",
            "providerName": "Official Fed Liquidity",
            "capability": "fed_liquidity",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "trustLevel": "score_grade_when_configured",
            "freshnessExpectation": "daily_or_weekly_public_release_lag",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "paidDataLikelyRequired": False,
            "keyRequired": False,
            "enabledByDefault": False,
            "noDefaultLiveHttpCalls": True,
            "missingProviderReason": "official_fed_liquidity_contract_not_configured",
        }
    ]
    assert snapshot["requiredSourceTypes"] == ["official_public", "cache_snapshot"]
    assert {
        "cache_required",
        "missing_provider_configuration",
        "release_schedule_required",
        "release_lag_expected",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(snapshot["reasonCodes"]["plan"]))


def test_route_diagnostic_snapshot_serializes_index_futures_bundle_requirements() -> None:
    request = DataSourceRouteRequest(
        market="US",
        asset_type="futures",
        use_case="liquidity_impulse",
        capability="index_futures",
        freshness_need="delayed",
        scoring_allowed=False,
        symbol="NQ",
        allow_network=False,
        reproducibility_required=False,
    )

    snapshot = build_data_source_route_diagnostic_snapshot(request).to_dict()

    assert snapshot["requiredSourceTypes"] == ["cache_snapshot"]
    assert snapshot["freshnessFloor"] == "delayed"
    assert snapshot["trustFloor"] == "authorized_index_futures_or_missing"
    assert snapshot["requiredSymbols"] == ["NQ", "ES", "YM", "RTY"]
    assert snapshot["session"] == "extended_hours"
    assert {
        "cache_required",
        "missing_provider_configuration",
        "authorization_required",
        "extended_hours_session_required",
        "freshness_floor_required",
        "coverage_floor_required",
    }.issubset(set(snapshot["reasonCodes"]["plan"]))


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
        "paidDataLikelyRequired": False,
        "keyRequired": False,
        "enabledByDefault": False,
        "noDefaultLiveHttpCalls": True,
        "missingProviderReason": None,
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
