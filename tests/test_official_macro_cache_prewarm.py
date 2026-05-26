# -*- coding: utf-8 -*-
"""Official macro cache prewarm entrypoint contracts."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

import scripts.official_macro_cache_prewarm as prewarm
from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.services.official_macro_liquidity_cache_contracts import build_official_us_rates_cache_bundle
from src.services.official_macro_transport import build_fred_observations_request


@pytest.fixture(autouse=True)
def clear_market_overview_caches() -> None:
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def _official_item(symbol: str, series_id: str, value: float = 1.0) -> dict[str, object]:
    return {
        "symbol": symbol,
        "label": symbol,
        "officialSeriesId": series_id,
        "value": value,
        "source": "fred",
        "sourceId": f"fred:{series_id}",
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "freshness": "cached",
        "asOf": "2026-05-20",
        "updatedAt": "2026-05-20",
        "isFallback": False,
        "isUnavailable": False,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
    }


def _official_rates_payload() -> dict[str, object]:
    return {
        "source": "mixed",
        "sourceType": "official_public",
        "freshness": "cached",
        "items": [
            _official_item("US2Y", "DGS2", 4.1),
            _official_item("US10Y", "DGS10", 4.3),
            _official_item("US30Y", "DGS30", 4.5),
            _official_item("SOFR", "SOFR", 4.8),
            _official_item("US10Y2Y", "T10Y2Y", -0.2),
            _official_item("US10Y3M", "T10Y3M", -0.9),
        ],
    }


def _official_macro_payload() -> dict[str, object]:
    return {
        "source": "mixed",
        "sourceType": "official_public",
        "freshness": "cached",
        "items": [
            _official_item("VIX", "VIXCLS", 16.0),
            _official_item("US2Y", "DGS2", 4.1),
            _official_item("US10Y", "DGS10", 4.3),
            _official_item("US30Y", "DGS30", 4.5),
            _official_item("SOFR", "SOFR", 4.8),
            _official_item("US10Y2Y", "T10Y2Y", -0.2),
            _official_item("US10Y3M", "T10Y3M", -0.9),
            _official_item("USD_TWI", "DTWEXBGS", 128.0),
            _official_item("FED_ASSETS", "WALCL", 7400000.0),
            _official_item("FED_RRP", "RRPONTSYD", 450.0),
            _official_item("TGA", "WTREGEN", 820000.0),
            _official_item("RESERVES", "WRESBAL", 3300000.0),
        ],
    }


def test_transport_supports_curve_spread_fred_series_requests() -> None:
    assert build_fred_observations_request("T10Y2Y").params["series_id"] == "T10Y2Y"
    assert build_fred_observations_request("T10Y3M").params["series_id"] == "T10Y3M"


def test_dry_run_reports_targets_without_constructing_service() -> None:
    def fail_factory() -> object:
        raise AssertionError("dry-run must not construct MarketOverviewService")

    result = prewarm.run_prewarm(write=False, service_factory=fail_factory)

    assert result["dryRun"] is True
    assert result["writeAttempted"] is False
    assert result["result"] == "dry_run_no_write"
    assert {panel["cacheKey"] for panel in result["targetPanels"]} == {"rates", "macro"}
    rates_panel = next(panel for panel in result["targetPanels"] if panel["cacheKey"] == "rates")
    assert rates_panel["writeAttempted"] is False
    assert rates_panel["writeWouldBeAttemptedWithWrite"] is True
    assert rates_panel["targetGroups"][0]["symbols"] == ["US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"]
    assert rates_panel["targetGroups"][0]["series"] == ["DGS2", "DGS10", "DGS30", "SOFR", "T10Y2Y", "T10Y3M"]
    macro_panel = next(panel for panel in result["targetPanels"] if panel["cacheKey"] == "macro")
    macro_us_rates_group = next(group for group in macro_panel["targetGroups"] if group["name"] == "us_rates")
    assert macro_us_rates_group["symbols"] == ["US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"]
    assert macro_us_rates_group["series"] == ["DGS2", "DGS10", "DGS30", "SOFR", "T10Y2Y", "T10Y3M"]


def test_service_prewarm_uses_existing_cached_payload_and_snapshot_writer(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketOverviewService(cn_hk_connect_flow_provider=lambda: None)
    rates_fetch = Mock(return_value=_official_rates_payload())
    macro_fetch = Mock(return_value=_official_macro_payload())
    save_snapshot = Mock()
    monkeypatch.setattr(service, "_fetch_rates_snapshot", rates_fetch)
    monkeypatch.setattr(service, "_fetch_macro", macro_fetch)
    monkeypatch.setattr(service, "_save_persistent_snapshot", save_snapshot)

    payloads = service.prewarm_official_macro_cache()

    assert set(payloads) == {"rates", "macro"}
    assert rates_fetch.call_count == 1
    assert macro_fetch.call_count == 1
    assert [call.args[0] for call in save_snapshot.call_args_list] == ["rates", "macro"]
    assert MarketOverviewService._market_data_cache["rates"]["items"][0]["symbol"] == "US2Y"
    assert MarketOverviewService._market_data_cache["macro"]["items"][0]["symbol"] == "VIX"


def test_write_mode_invokes_market_overview_prewarm_callable() -> None:
    class FakeCache:
        def __init__(self) -> None:
            self.wait_calls: list[float] = []

        def wait_for_refreshes(self, timeout: float) -> bool:
            self.wait_calls.append(timeout)
            return True

    class FakeService:
        def __init__(self) -> None:
            self._market_cache = FakeCache()
            self.calls = 0

        def prewarm_official_macro_cache(self) -> dict[str, dict[str, object]]:
            self.calls += 1
            return {
                "rates": _official_rates_payload(),
                "macro": _official_macro_payload(),
            }

    created: list[FakeService] = []

    def factory() -> FakeService:
        service = FakeService()
        created.append(service)
        return service

    result = prewarm.run_prewarm(write=True, service_factory=factory)

    assert result["dryRun"] is False
    assert result["writeAttempted"] is True
    assert result["result"] == "write_attempted"
    assert created[0].calls == 1
    assert created[0]._market_cache.wait_calls == [prewarm.REFRESH_WAIT_TIMEOUT_SECONDS]
    assert {panel["cacheKey"] for panel in result["panels"]} == {"rates", "macro"}
    rates_panel = next(panel for panel in result["panels"] if panel["cacheKey"] == "rates")
    macro_panel = next(panel for panel in result["panels"] if panel["cacheKey"] == "macro")
    assert rates_panel["targetSymbolsFound"] == ["US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"]
    assert "T10Y2Y" in {item["series"] for item in rates_panel["targetDiagnostics"]}
    assert "T10Y3M" in {item["series"] for item in rates_panel["targetDiagnostics"]}
    assert "US10Y2Y" in macro_panel["targetSymbolsFound"]
    assert "US10Y3M" in macro_panel["targetSymbolsFound"]


def test_budget_blocked_and_missing_key_diagnostics_remain_non_scoring() -> None:
    budget_blocked = {
        "symbol": "US10Y",
        "label": "US 10Y",
        "officialSeriesId": "DGS10",
        "value": 4.3,
        "source": "fred",
        "sourceId": "fred:DGS10",
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "freshness": "unavailable",
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "sourceAuthorityReason": "budget_exhausted",
        "routeRejectedReasonCodes": ["budget_blocked_official_macro_route"],
    }
    missing_key = {
        "symbol": "USD_TWI",
        "label": "Trade-weighted USD",
        "officialSeriesId": "DTWEXBGS",
        "source": "fred",
        "sourceId": "fred:DTWEXBGS",
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "freshness": "unavailable",
        "isUnavailable": True,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "sourceAuthorityReason": "missing_api_key",
        "officialOverlayFailureReason": "missing_api_key",
        "routeRejectedReasonCodes": ["missing_api_key"],
    }

    class FakeService:
        def prewarm_official_macro_cache(self) -> dict[str, dict[str, object]]:
            return {
                "rates": {"source": "mixed", "items": [budget_blocked]},
                "macro": {"source": "mixed", "items": [missing_key]},
            }

    result = prewarm.run_prewarm(write=True, service_factory=FakeService)

    diagnostics = {
        diagnostic["symbol"]: diagnostic
        for panel in result["panels"]
        for diagnostic in panel["targetDiagnostics"]
    }
    assert diagnostics["US10Y"]["sourceAuthorityReason"] == "budget_exhausted"
    assert diagnostics["US10Y"]["scoreContributionAllowed"] is False
    assert diagnostics["USD_TWI"]["officialOverlayFailureReason"] == "missing_api_key"
    assert diagnostics["USD_TWI"]["scoreContributionAllowed"] is False

    bundle = build_official_us_rates_cache_bundle([budget_blocked])
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["scoreGradeEvidenceAllowed"] is False
    assert "budget_blocked_official_macro_route" in bundle["reasonCodes"]
