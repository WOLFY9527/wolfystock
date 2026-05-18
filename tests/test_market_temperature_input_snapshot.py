# -*- coding: utf-8 -*-
"""Shared market temperature input snapshot contracts."""

from __future__ import annotations

import copy
from unittest.mock import Mock, patch

import pytest

from src.services.market_overview_service import MarketOverviewService


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
    assert {"source", "updatedAt", "scores", "confidence", "isReliable", "fallbackUsed", "providerHealth", "evidenceSnapshot"}.issubset(temperature_payload)
    assert {"source", "updatedAt", "items", "confidence", "isReliable", "fallbackUsed", "providerHealth", "evidenceSnapshot"}.issubset(briefing_payload)
