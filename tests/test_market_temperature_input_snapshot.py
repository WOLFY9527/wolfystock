# -*- coding: utf-8 -*-
"""Shared market temperature input snapshot contracts."""

from __future__ import annotations

import copy
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from src.services.market_overview_service import MarketOverviewService
from src.services.official_macro_transport import MacroObservation


@pytest.fixture(autouse=True)
def _reset_market_state() -> None:
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    MarketOverviewService._market_cache.wait_for_refreshes(timeout=2)
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def _shared_temperature_inputs() -> dict:
    return {
        "indices": {
            "source": "sina",
            "sourceLabel": "新浪财经",
            "freshness": "live",
            "items": [
                {
                    "symbol": "000001.SH",
                    "value": 4100.0,
                    "changePercent": 0.7,
                    "source": "sina",
                    "freshness": "live",
                    "isFallback": False,
                }
            ],
        },
        "breadth": {
            "source": "tickflow",
            "sourceLabel": "TickFlow",
            "freshness": "live",
            "items": [
                {
                    "symbol": "ADV_RATIO",
                    "value": 61.0,
                    "change": 1.0,
                    "source": "tickflow",
                    "freshness": "live",
                    "isFallback": False,
                }
            ],
        },
        "flows": {
            "source": "eastmoney",
            "sourceLabel": "东方财富",
            "freshness": "live",
            "items": [
                {
                    "symbol": "CN_ETF",
                    "value": 15.0,
                    "changePercent": 0.3,
                    "source": "eastmoney",
                    "freshness": "live",
                    "isFallback": False,
                }
            ],
        },
        "sectors": {
            "source": "yahoo",
            "sourceLabel": "Yahoo Finance",
            "freshness": "delayed",
            "items": [
                {
                    "symbol": "TECH",
                    "value": 1.0,
                    "changePercent": 0.5,
                    "source": "yahoo",
                    "freshness": "delayed",
                    "isFallback": False,
                }
            ],
        },
        "rates": {
            "source": "treasury",
            "sourceLabel": "US Treasury",
            "freshness": "cached",
            "items": [
                {
                    "symbol": "US10Y",
                    "value": 4.2,
                    "changePercent": -0.2,
                    "source": "treasury",
                    "sourceType": "official_public",
                    "freshness": "cached",
                    "isFallback": False,
                },
                {
                    "symbol": "VIX",
                    "value": 16.2,
                    "changePercent": -1.1,
                    "source": "fred",
                    "sourceType": "official_public",
                    "freshness": "cached",
                    "isFallback": False,
                },
            ],
        },
        "fx": {
            "source": "yahoo",
            "sourceLabel": "Yahoo Finance",
            "freshness": "delayed",
            "items": [
                {
                    "symbol": "DXY",
                    "value": 104.3,
                    "changePercent": -0.4,
                    "source": "yahoo",
                    "freshness": "delayed",
                    "isFallback": False,
                }
            ],
        },
        "futures": {
            "source": "yahoo",
            "sourceLabel": "Yahoo Finance",
            "freshness": "delayed",
            "items": [
                {
                    "symbol": "ES",
                    "value": 5238.0,
                    "changePercent": 0.2,
                    "source": "yahoo",
                    "freshness": "delayed",
                    "isFallback": False,
                },
                {
                    "symbol": "NQ",
                    "value": 18320.0,
                    "changePercent": 0.4,
                    "source": "yahoo",
                    "freshness": "delayed",
                    "isFallback": False,
                },
                {
                    "symbol": "YM",
                    "value": 39000.0,
                    "changePercent": -0.1,
                    "source": "yahoo",
                    "freshness": "delayed",
                    "isFallback": False,
                },
            ],
        },
        "sentiment": {
            "source": "cnn",
            "sourceLabel": "CNN",
            "freshness": "cached",
            "items": [
                {
                    "symbol": "FGI",
                    "value": 60,
                    "change": 1.0,
                    "source": "cnn",
                    "freshness": "cached",
                    "isFallback": False,
                }
            ],
        },
        "crypto": {
            "source": "binance",
            "sourceLabel": "Binance",
            "freshness": "live",
            "items": [
                {
                    "symbol": "BTC",
                    "value": 87000.0,
                    "changePercent": 1.4,
                    "source": "binance",
                    "freshness": "live",
                    "isFallback": False,
                },
                {
                    "symbol": "ETH",
                    "value": 3200.0,
                    "changePercent": 1.1,
                    "source": "binance",
                    "freshness": "live",
                    "isFallback": False,
                },
            ],
        },
        "fallback_notice": True,
    }


def _call_public(method_name: str, service: MarketOverviewService) -> dict:
    with patch("src.services.market_overview_service.ExecutionLogService") as log_service:
        log_service.return_value.record_market_overview_fetch.return_value = f"log-{method_name}"
        return getattr(service, method_name)()


def test_temperature_then_briefing_reuses_the_same_input_bundle_within_ttl() -> None:
    service = MarketOverviewService()
    build_inputs = Mock(return_value=_shared_temperature_inputs())

    with patch.object(service, "_build_market_temperature_inputs", build_inputs):
        temperature_payload = _call_public("get_market_temperature", service)
        briefing_payload = _call_public("get_market_briefing", service)

    assert build_inputs.call_count == 1
    assert temperature_payload["source"] == "computed"
    assert briefing_payload["source"] == "computed"
    assert briefing_payload["isReliable"] is True


def test_briefing_then_temperature_reuses_the_same_input_bundle_within_ttl() -> None:
    service = MarketOverviewService()
    build_inputs = Mock(return_value=_shared_temperature_inputs())

    with patch.object(service, "_build_market_temperature_inputs", build_inputs):
        briefing_payload = _call_public("get_market_briefing", service)
        temperature_payload = _call_public("get_market_temperature", service)

    assert build_inputs.call_count == 1
    assert briefing_payload["source"] == "computed"
    assert temperature_payload["source"] == "computed"
    assert temperature_payload["isReliable"] is True


def test_shared_temperature_input_snapshot_keeps_fallback_stale_and_unavailable_metadata_truthful() -> None:
    service = MarketOverviewService()
    inputs = copy.deepcopy(_shared_temperature_inputs())
    inputs["rates"]["items"][0].update(
        {
            "source": "fallback",
            "sourceLabel": "备用数据",
            "freshness": "fallback",
            "isFallback": True,
        }
    )
    inputs["fx"]["items"][0].update(
        {
            "freshness": "stale",
            "isStale": True,
        }
    )
    inputs["crypto"].update(
        {
            "source": "unavailable",
            "sourceLabel": "不可用",
            "freshness": "fallback",
            "isFallback": True,
            "items": [],
        }
    )

    with patch.object(service, "_build_market_temperature_inputs", return_value=inputs):
        snapshot = service._get_market_temperature_input_snapshot()

    assert snapshot["rates"]["items"][0]["freshness"] == "fallback"
    assert snapshot["rates"]["items"][0]["isFallback"] is True
    assert snapshot["fx"]["items"][0]["freshness"] == "stale"
    assert snapshot["fx"]["items"][0]["isStale"] is True
    assert snapshot["crypto"]["source"] == "unavailable"
    assert snapshot["crypto"]["freshness"] == "fallback"
    assert snapshot["crypto"]["isFallback"] is True


def test_failed_input_build_does_not_poison_future_refresh() -> None:
    service = MarketOverviewService()
    build_inputs = Mock(side_effect=[RuntimeError("provider down"), _shared_temperature_inputs()])

    with patch.object(service, "_build_market_temperature_inputs", build_inputs):
        with pytest.raises(RuntimeError, match="provider down"):
            service._get_market_temperature_input_snapshot()

        snapshot = service._get_market_temperature_input_snapshot()

    assert build_inputs.call_count == 2
    assert snapshot["indices"]["source"] == "sina"
    assert snapshot["futures"]["items"][0]["symbol"] == "ES"


def test_public_temperature_and_briefing_shapes_do_not_leak_the_shared_input_snapshot() -> None:
    service = MarketOverviewService()
    build_inputs = Mock(return_value=_shared_temperature_inputs())

    with patch.object(service, "_build_market_temperature_inputs", build_inputs):
        temperature_payload = _call_public("get_market_temperature", service)
        briefing_payload = _call_public("get_market_briefing", service)

    assert build_inputs.call_count == 1
    assert "temperatureInputSnapshot" not in temperature_payload
    assert "temperatureInputSnapshot" not in briefing_payload
    assert {"source", "updatedAt", "scores", "marketRegimeSynthesis", "confidence", "isReliable", "fallbackUsed", "providerHealth", "evidenceSnapshot"}.issubset(temperature_payload)
    assert {"source", "updatedAt", "items", "confidence", "isReliable", "fallbackUsed", "providerHealth", "evidenceSnapshot"}.issubset(briefing_payload)
    assert temperature_payload["marketRegimeSynthesis"]["notInvestmentAdvice"] is True
    assert "primaryRegime" in temperature_payload["marketRegimeSynthesis"]
    assert temperature_payload["marketDecisionSemantics"]["directionReadiness"]["notInvestmentAdvice"] is True
    assert temperature_payload["marketDecisionSemantics"]["directionReadiness"]["status"] in {
        "direction_ready",
        "partial_context_only",
        "data_insufficient",
    }


def test_temperature_input_builder_uses_internal_snapshots_without_public_wrapper_side_effects() -> None:
    service = MarketOverviewService()
    public_methods = (
        "get_cn_indices",
        "get_cn_breadth",
        "get_cn_flows",
        "get_sector_rotation",
        "get_rates",
        "get_volatility",
        "get_fx_commodities",
        "get_futures",
        "get_market_sentiment",
        "get_crypto",
    )

    def fallback_snapshot(_cache_key: str, _fetcher: object, fallback_factory: object) -> dict:
        return fallback_factory()  # type: ignore[operator]

    with patch.object(service, "_cached_payload", side_effect=fallback_snapshot):
        with ExitStack() as stack:
            public_mocks = [
                stack.enter_context(patch.object(service, method_name, side_effect=AssertionError(f"public wrapper called: {method_name}")))
                for method_name in public_methods
            ]
            inputs = service._build_market_temperature_inputs()

    for public_mock in public_mocks:
        assert public_mock.call_count == 0
    assert set(inputs) >= {"indices", "breadth", "flows", "sectors", "rates", "fx", "futures", "sentiment", "crypto"}
    assert inputs["rates"]["freshness"] == "fallback"
    assert inputs["crypto"]["freshness"] == "fallback"
    assert inputs["crypto"]["isFallback"] is True


def test_temperature_score_inputs_add_source_authority_diagnostics() -> None:
    service = MarketOverviewService()

    coinbase_item = service._guard_market_temperature_score_input(
        {
            "symbol": "BTC",
            "value": 87000.0,
            "changePercent": 1.4,
            "source": "coinbase_public",
            "sourceType": "exchange_public",
            "freshness": "live",
            "isFallback": False,
            "isReliable": True,
            "excluded": False,
            "confidenceWeight": 1.0,
        },
        panel_key="crypto",
    )
    proxy_item = service._guard_market_temperature_score_input(
        {
            "symbol": "ES",
            "value": 5238.0,
            "changePercent": 0.2,
            "source": "yahoo",
            "sourceType": "unofficial_public_api",
            "freshness": "delayed",
            "isFallback": False,
            "isReliable": True,
            "excluded": False,
            "confidenceWeight": 0.7,
        },
        panel_key="futures",
    )

    assert coinbase_item["sourceAuthorityAllowed"] is False
    assert coinbase_item["scoreContributionAllowed"] is False
    assert coinbase_item["sourceAuthorityRouteRejected"] is True
    assert coinbase_item["sourceAuthorityReason"] == "source_authority_router_rejected"
    assert "provider_forbidden_for_use_case" in coinbase_item["routeRejectedReasonCodes"]
    assert coinbase_item["excluded"] is True
    assert coinbase_item["confidenceWeight"] == 0.0
    assert coinbase_item["sourceAuthorityRouter"]["diagnosticOnly"] is True
    assert coinbase_item["sourceAuthorityRouter"]["providerRuntimeCalled"] is False
    assert coinbase_item["sourceAuthorityRouter"]["networkCallsEnabled"] is False
    assert coinbase_item["sourceAuthorityRouter"]["request"]["useCase"] == "market_temperature"
    assert coinbase_item["sourceAuthorityRouter"]["request"]["capability"] == "crypto_ticker"
    assert coinbase_item["sourceAuthorityRouter"]["request"]["allowNetwork"] is False

    assert proxy_item["sourceAuthorityAllowed"] is False
    assert proxy_item["scoreContributionAllowed"] is False
    assert proxy_item["sourceAuthorityRouteRejected"] is False
    assert proxy_item["sourceAuthorityReason"] == "proxy_context_only"
    assert proxy_item["routeRejectedReasonCodes"] == []


def test_temperature_inputs_preserve_official_macro_authority_metadata_after_rates_volatility_merge() -> None:
    service = MarketOverviewService()
    current = datetime.now(timezone(timedelta(hours=8)))
    today = current.date().isoformat()
    previous = (current - timedelta(days=1)).date().isoformat()
    official_points = {
        "VIXCLS": [
            MacroObservation("VIXCLS", 18.4, today, today, "fred:VIXCLS", "official_public", "daily_close"),
            MacroObservation("VIXCLS", 19.2, previous, previous, "fred:VIXCLS", "official_public", "daily_close"),
        ],
        "DGS2": [
            MacroObservation("DGS2", 4.82, today, today, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
            MacroObservation("DGS2", 4.79, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
        ],
        "DGS10": [
            MacroObservation("DGS10", 4.41, today, today, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
            MacroObservation("DGS10", 4.36, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
        ],
        "DGS30": [
            MacroObservation("DGS30", 4.63, today, today, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
            MacroObservation("DGS30", 4.58, previous, previous, "treasury:daily_treasury_yield_curve", "official_public", "daily_rate"),
        ],
        "SOFR": [
            MacroObservation("SOFR", 5.31, today, today, "fred:SOFR", "official_public", "daily_fixing"),
            MacroObservation("SOFR", 5.30, previous, previous, "fred:SOFR", "official_public", "daily_fixing"),
        ],
        "WALCL": [
            MacroObservation("WALCL", 7485000.0, today, today, "fred:WALCL", "official_public", "weekly_fed_h41"),
            MacroObservation("WALCL", 7475000.0, previous, previous, "fred:WALCL", "official_public", "weekly_fed_h41"),
        ],
        "RRPONTSYD": [
            MacroObservation("RRPONTSYD", 432.2, today, today, "fred:RRPONTSYD", "official_public", "daily_fed_rrp"),
            MacroObservation("RRPONTSYD", 455.0, previous, previous, "fred:RRPONTSYD", "official_public", "daily_fed_rrp"),
        ],
        "WTREGEN": [
            MacroObservation("WTREGEN", 812000.0, today, today, "fred:WTREGEN", "official_public", "weekly_fed_h41"),
            MacroObservation("WTREGEN", 826000.0, previous, previous, "fred:WTREGEN", "official_public", "weekly_fed_h41"),
        ],
        "WRESBAL": [
            MacroObservation("WRESBAL", 3260000.0, today, today, "fred:WRESBAL", "official_public", "weekly_fed_h41"),
            MacroObservation("WRESBAL", 3240000.0, previous, previous, "fred:WRESBAL", "official_public", "weekly_fed_h41"),
        ],
        "DTWEXBGS": [
            MacroObservation("DTWEXBGS", 128.42, today, today, "fred:DTWEXBGS", "official_public", "daily_trade_weighted_usd"),
            MacroObservation("DTWEXBGS", 128.10, previous, previous, "fred:DTWEXBGS", "official_public", "daily_trade_weighted_usd"),
        ],
    }

    def cached_payload(cache_key: str, _fetcher: object, fallback_factory: object) -> dict:
        if cache_key == "rates":
            return service._fetch_rates_snapshot()
        if cache_key == "volatility":
            return service._fetch_volatility()
        if cache_key == "macro":
            return service._fetch_macro()
        return fallback_factory()  # type: ignore[operator]

    with (
        patch.object(service, "_cached_payload", side_effect=cached_payload),
        patch.object(service, "_official_macro_points", return_value=official_points),
        patch.object(service, "_quote_items", return_value=[]),
        patch.object(service, "_atr_item", return_value=None),
    ):
        inputs = service._build_market_temperature_inputs_from_internal_snapshots()

    rates_by_symbol = {
        str(item["symbol"]): item
        for item in inputs["rates"]["items"]
        if isinstance(item, dict)
        and item.get("symbol")
        in {"VIX", "US2Y", "US10Y", "US30Y", "SOFR", "FED_ASSETS", "FED_RRP", "TGA", "RESERVES"}
    }

    assert set(rates_by_symbol) == {"VIX", "US2Y", "US10Y", "US30Y", "SOFR", "FED_ASSETS", "FED_RRP", "TGA", "RESERVES"}
    for symbol, item in rates_by_symbol.items():
        assert item["sourceType"] == "official_public"
        assert item["sourceTier"] == "official_public"
        assert item["sourceAuthorityAllowed"] is True, symbol
        assert item["scoreContributionAllowed"] is True, symbol
        assert item["sourceAuthorityReason"] is None
        assert item["routeRejectedReasonCodes"] == []
        assert item["freshness"] in {"cached", "delayed"}
        if symbol in {"FED_ASSETS", "FED_RRP", "TGA", "RESERVES"}:
            assert item["officialSeriesId"] in {"WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"}

    fx_by_symbol = {
        str(item["symbol"]): item
        for item in inputs["fx"]["items"]
        if isinstance(item, dict) and item.get("symbol") == "USD_TWI"
    }
    assert set(fx_by_symbol) == {"USD_TWI"}
    usd_item = fx_by_symbol["USD_TWI"]
    assert usd_item["label"] == "Trade-weighted USD"
    assert usd_item["sourceType"] == "official_public"
    assert usd_item["sourceTier"] == "official_public"
    assert usd_item["sourceAuthorityAllowed"] is True
    assert usd_item["scoreContributionAllowed"] is True
    assert usd_item["officialSeriesId"] == "DTWEXBGS"
    assert "DXY" not in str(usd_item.get("label"))


def test_temperature_score_helpers_skip_explicit_non_scoring_inputs() -> None:
    service = MarketOverviewService()
    items = [
        {
            "symbol": "ES",
            "value": 5238.0,
            "changePercent": 2.5,
            "scoreContributionAllowed": False,
        },
        {
            "symbol": "NQ",
            "value": 18100.0,
            "changePercent": 1.0,
            "scoreContributionAllowed": True,
        },
    ]

    assert service._avg_change(items, {"ES", "NQ"}) == 1.0
    assert service._item_change(items, "ES") is None
    assert service._item_value(items, "ES") is None


def test_sector_rotation_projection_preserves_authority_and_ranking_metadata() -> None:
    service = MarketOverviewService()

    payload = service._project_sector_rotation_snapshot(
        {
            "source": "computed",
            "sourceLabel": "Computed",
            "freshness": "cached",
            "updatedAt": "2026-05-20T10:00:00+08:00",
            "generatedAt": "2026-05-20T10:00:00+08:00",
            "metadata": {
                "quoteProvider": {"asOf": "2026-05-20T10:00:00+08:00"},
                "observedEvidence": {"asOf": "2026-05-20T10:00:00+08:00"},
            },
            "themes": [
                {
                    "id": "ai_applications",
                    "name": "AI Applications",
                    "market": "US",
                    "rotationScore": 72,
                    "relativeStrength": {"averageRelativeStrengthPercent": 2.3},
                    "source": "alpaca",
                    "sourceLabel": "Alpaca",
                    "sourceTier": "tier_1_configured",
                    "trustLevel": "high",
                    "freshness": "cached",
                    "scoreContributionAllowed": True,
                    "sourceAuthorityAllowed": True,
                    "sourceAuthorityReason": None,
                    "rankEligible": True,
                    "headlineEligible": True,
                    "scoreCap": 0.92,
                    "rankingTrust": {
                        "sourceTier": "tier_1_configured",
                        "trustLevel": "high",
                        "freshness": "cached",
                        "scoreCap": 0.92,
                        "conclusionAllowed": True,
                    },
                    "degradationReasons": ["quote_window_narrow"],
                    "rotationStateEvidence": {
                        "schemaVersion": "rotation_state_evidence_v1",
                        "source": "alpaca",
                        "sourceConfidence": {"freshness": "cached"},
                    },
                }
            ],
        }
    )

    item = payload["items"][0]
    assert item["sourceAuthorityAllowed"] is True
    assert item["sourceAuthorityReason"] is None
    assert item["scoreContributionAllowed"] is True
    assert item["rankEligible"] is True
    assert item["headlineEligible"] is True
    assert item["scoreCap"] == 0.92
    assert item["rankingTrust"]["scoreCap"] == 0.92
    assert item["degradationReasons"] == ["quote_window_narrow"]
    assert item["sourceTier"] == "tier_1_configured"
    assert item["trustLevel"] == "high"


def test_public_rates_method_keeps_public_wrapper_shape() -> None:
    service = MarketOverviewService()

    with (
        patch.object(service, "_cached_payload", return_value=service._fallback_rates_snapshot()),
        patch("src.services.market_overview_service.ExecutionLogService") as log_service,
    ):
        log_service.return_value.record_market_overview_fetch.return_value = "log-rates"
        payload = service.get_rates()

    assert payload["panelName"] == "RatesCard"
    assert payload["logSessionId"] == "log-rates"
    assert "providerHealth" in payload
    assert "evidenceSnapshot" in payload
    assert payload["items"]
