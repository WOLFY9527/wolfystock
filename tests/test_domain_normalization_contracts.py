"""Golden parity coverage for converged domain normalization contracts."""

from __future__ import annotations

from src.services import market_overview_service
from src.services import market_scanner_context_adapter
from src.services import official_macro_liquidity_cache_contracts


def test_market_payload_classification_golden_parity() -> None:
    classify_market_payload_availability = market_overview_service.classify_market_payload_availability
    classify_market_payload_reliability = market_overview_service.classify_market_payload_reliability
    cases = (
        (
            {"source": "sina", "freshness": "live", "value": 1.0},
            {
                "fallbackSignaled": False,
                "fallbackOnly": False,
                "itemCount": 0,
                "degradedItemCount": 0,
                "availableItemCount": 0,
            },
            "real",
            "live",
        ),
        (
            {"source": "fallback", "freshness": "fallback", "value": 1.0, "isFallback": True},
            {
                "fallbackSignaled": True,
                "fallbackOnly": True,
                "itemCount": 0,
                "degradedItemCount": 0,
                "availableItemCount": 0,
            },
            "fallback",
            "unavailable",
        ),
        (
            {"source": "mixed", "freshness": "live", "items": [
                {"source": "sina", "freshness": "live", "value": 1.0},
                {"source": "fallback", "freshness": "fallback", "value": 2.0, "isFallback": True},
            ]},
            {
                "fallbackSignaled": False,
                "fallbackOnly": False,
                "itemCount": 2,
                "degradedItemCount": 1,
                "availableItemCount": 1,
            },
            "mixed",
            "partial",
        ),
        (
            {"source": "mixed", "freshness": "unavailable", "isUnavailable": True, "items": [
                {"source": "unavailable", "freshness": "unavailable", "isUnavailable": True},
            ]},
            {
                "fallbackSignaled": False,
                "fallbackOnly": True,
                "itemCount": 1,
                "degradedItemCount": 1,
                "availableItemCount": 0,
            },
            "error",
            "unavailable",
        ),
        (
            {"source": "static_sample", "sourceLabel": "Synthetic fallback", "freshness": "live", "value": 1.0},
            {
                "fallbackSignaled": True,
                "fallbackOnly": False,
                "itemCount": 0,
                "degradedItemCount": 0,
                "availableItemCount": 0,
            },
            "fallback",
            "live",
        ),
    )
    service = object.__new__(market_overview_service.MarketOverviewService)

    for payload, expected_contract, expected_reliability, expected_health in cases:
        contract = classify_market_payload_availability(payload)
        assert {key: contract[key] for key in expected_contract} == expected_contract
        assert classify_market_payload_reliability(payload)["kind"] == expected_reliability
        assert service._provider_health_status(payload) == expected_health
        assert service._is_fallback_only_market_snapshot(payload) is expected_contract["fallbackOnly"]


def test_official_series_alias_normalization_golden_parity() -> None:
    normalize_official_series_aliases = official_macro_liquidity_cache_contracts.normalize_official_series_aliases
    official_us_rates_series_id = official_macro_liquidity_cache_contracts.official_us_rates_series_id
    official_fed_liquidity_series_id = official_macro_liquidity_cache_contracts.official_fed_liquidity_series_id
    official_usd_pressure_series_id = official_macro_liquidity_cache_contracts.official_usd_pressure_series_id
    official_cn_money_market_series_id = official_macro_liquidity_cache_contracts.official_cn_money_market_series_id
    cases = (
        ({"officialSeriesId": " dgs10 "}, ("DGS10",), "DGS10", None, None, None),
        ({"source_id": "fred:T10Y2Y"}, ("T10Y2Y",), "US10Y2Y", None, None, None),
        ({"series_id": "fred:WALCL"}, ("WALCL",), None, "WALCL", None, None),
        ({"symbol": "USD_TWI"}, ("USD_TWI",), None, None, "DTWEXBGS", None),
        ({"key": "shibor o/n"}, ("SHIBOR_O/N",), None, None, None, "SHIBOR_ON"),
        ({"official_series_id": "unknown", "symbol": "US2Y"}, ("UNKNOWN", "US2Y"), "DGS2", None, None, None),
        ({"officialSeriesId": "unknown", "seriesId": "DGS10"}, ("UNKNOWN",), None, None, None, None),
        ({"sourceId": "US10Y:unknown"}, ("UNKNOWN",), None, None, None, None),
    )

    for row, aliases, rates, fed, usd, cn in cases:
        assert normalize_official_series_aliases(row) == aliases
        assert official_us_rates_series_id(row) == rates
        assert official_fed_liquidity_series_id(row) == fed
        assert official_usd_pressure_series_id(row) == usd
        assert official_cn_money_market_series_id(row) == cn


def test_scanner_context_normalization_golden_parity() -> None:
    normalize_scanner_context_inputs = market_scanner_context_adapter.normalize_scanner_context_inputs
    diagnostics = {
        "marketTemperature": {
            "source": "computed",
            "freshness": "cached",
            "regimeSummary": {"primaryRegime": "risk_on", "scoreContributionAllowed": True},
            "liquidityFrame": {"liquidityImpulse": "supportive", "scoreContributionAllowed": True},
            "rotationFamilyRollup": [{"familyId": "ai"}],
            "marketReadiness": {"readinessState": "ready"},
        },
        "liquidityMonitor": {"capitalFlowSignal": {"likelyDestination": "growth"}},
        "rotationRadar": {"families": [{"familyId": "ignored-by-market-context"}]},
    }

    normalized = normalize_scanner_context_inputs(diagnostics)

    assert normalized == {
        "market_context": diagnostics["marketTemperature"],
        "liquidity_context": diagnostics["liquidityMonitor"],
        "rotation_context": diagnostics["rotationRadar"],
        "market_regime": diagnostics["marketTemperature"]["regimeSummary"],
        "liquidity_frame": diagnostics["marketTemperature"]["liquidityFrame"],
        "rotation_families": diagnostics["marketTemperature"]["rotationFamilyRollup"],
        "explicit_readiness": diagnostics["marketTemperature"]["marketReadiness"],
    }
    assert normalized["market_context"] is not diagnostics["marketTemperature"]
    assert normalized["rotation_families"] is not diagnostics["marketTemperature"]["rotationFamilyRollup"]
