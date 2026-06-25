# -*- coding: utf-8 -*-
"""Tests for the inert market breadth readiness contract."""

from __future__ import annotations

import json

from src.services.market_breadth_readiness_service import (
    MARKET_BREADTH_MEASURE_IDS,
    MARKET_BREADTH_READINESS_STATES,
    build_market_breadth_readiness_contract,
)


def test_market_breadth_readiness_contract_separates_measures_and_markets() -> None:
    payload = build_market_breadth_readiness_contract(
        market_snapshots={
            "US": {
                "source": "polygon_us_grouped_daily",
                "sourceType": "authorized_licensed_feed",
                "freshness": "delayed",
                "fulfilledMetrics": [
                    "ADVANCERS",
                    "DECLINERS",
                    "ADVANCE_DECLINE_RATIO",
                    "NEW_HIGHS",
                    "NEW_LOWS",
                    "HIGH_LOW_RATIO",
                ],
                "items": [{"symbol": "RSP_SPY", "value": 0.12}],
            },
            "CN": {
                "source": "tickflow",
                "sourceType": "public_api",
                "freshness": "cached",
                "items": [
                    {"symbol": "ADVANCERS", "value": 2800},
                    {"symbol": "DECLINERS", "value": 1700},
                    {"symbol": "ADV_RATIO", "value": 61.2},
                ],
            },
        }
    )

    measures = {item["measureId"]: item for item in payload["measures"]}
    markets = {item["market"]: item for item in payload["markets"]}

    assert payload["contractVersion"] == "market_breadth_readiness_v1"
    assert payload["consumerSafe"] is True
    assert payload["readinessStates"] == list(MARKET_BREADTH_READINESS_STATES)
    assert set(measures) == set(MARKET_BREADTH_MEASURE_IDS)

    assert measures["advance_decline"]["marketStates"] == {
        "US": "available",
        "CN": "stale",
        "HK": "not_configured",
    }
    assert measures["new_highs_lows"]["marketStates"]["US"] == "available"
    assert measures["percent_above_ma"]["state"] == "missing"
    assert measures["sector_participation"]["state"] == "missing"
    assert measures["volume_breadth"]["state"] == "missing"
    assert measures["equal_weight_cap_weight_proxy"]["marketStates"]["US"] == "available"

    assert markets["US"]["supportedMeasures"] == [
        "advance_decline",
        "new_highs_lows",
        "equal_weight_cap_weight_proxy",
    ]
    assert "CN" in measures["advance_decline"]["supportedMarkets"]
    assert "HK" in measures["advance_decline"]["missingMarkets"]
    assert markets["HK"]["state"] == "not_configured"
    assert markets["HK"]["supportedMeasures"] == []


def test_market_breadth_readiness_contract_fails_closed_for_missing_or_disabled_provider() -> None:
    payload = build_market_breadth_readiness_contract(
        provider_disabled=True,
        market_snapshots={
            "US": {"source": "unavailable", "freshness": "unavailable", "items": []},
            "CN": {"source": "fallback", "freshness": "fallback", "items": []},
        },
    )

    assert payload["providerState"]["state"] == "disabled"
    assert payload["markets"][0]["state"] == "disabled_by_flag"
    assert {item["state"] for item in payload["measures"]} == {"disabled_by_flag"}
    assert all(item["supportedMarkets"] == [] for item in payload["measures"])


def test_market_breadth_readiness_contract_is_sanitized_and_has_no_fake_scores_or_advice() -> None:
    payload = build_market_breadth_readiness_contract(
        market_snapshots={
            "US": {
                "source": "unavailable",
                "freshness": "unavailable",
                "rawPayload": {"token": "SECRET", "requestId": "REQ-1"},
                "traceId": "TRACE-1",
                "stackTrace": "Traceback token=SECRET",
                "items": [
                    {
                        "symbol": "ADVANCERS",
                        "value": 9999,
                        "providerPayload": {"buy": "now"},
                    }
                ],
            }
        }
    )

    serialized = json.dumps(payload, ensure_ascii=False)
    lowered = serialized.lower()

    for marker in (
        "rawPayload",
        "raw_payload",
        "providerPayload",
        "requestId",
        "traceId",
        "stackTrace",
        "cacheKey",
        "token",
        "SECRET",
        "buy now",
        "target price",
    ):
        assert marker not in serialized
        assert marker.lower() not in lowered

    assert "breadthScore" not in serialized
    assert "breadthThrust" not in serialized
    assert payload["scoreEligible"] is False
