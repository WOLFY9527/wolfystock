# -*- coding: utf-8 -*-
"""Official macro cache prewarm entrypoint contracts."""

from __future__ import annotations

import json
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


def _ready_readiness_summary() -> dict[str, object]:
    return {
        "readiness": "ready",
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "requiredSeriesStatus": {
            "DTWEXBGS": "fulfilled",
            "WALCL": "fulfilled",
            "RRPONTSYD": "fulfilled",
            "WTREGEN": "fulfilled",
            "WRESBAL": "fulfilled",
        },
        "missingSeries": [],
        "staleSeries": [],
        "reason": None,
    }


def _blocked_readiness_summary() -> dict[str, object]:
    return {
        "readiness": "blocked",
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "requiredSeriesStatus": {
            "DTWEXBGS": "fulfilled",
            "WALCL": "missing",
            "RRPONTSYD": "fulfilled",
            "WTREGEN": "fulfilled",
            "WRESBAL": "fulfilled",
        },
        "missingSeries": ["WALCL"],
        "staleSeries": [],
        "reason": "series_coverage",
        "rawProviderPayload": {"token": "SECRET"},
    }


def test_transport_supports_curve_spread_fred_series_requests() -> None:
    assert build_fred_observations_request("T10Y2Y").params["series_id"] == "T10Y2Y"
    assert build_fred_observations_request("T10Y3M").params["series_id"] == "T10Y3M"


def test_dry_run_reports_blocked_readiness_missing_walcl_without_constructing_service() -> None:
    def fail_factory() -> object:
        raise AssertionError("dry-run must not construct MarketOverviewService")

    result = prewarm.run_prewarm(
        write=False,
        service_factory=fail_factory,
        readiness_probe=_blocked_readiness_summary,
    )

    assert result["dryRun"] is True
    assert result["writeEnabled"] is False
    assert result["writeAttempted"] is False
    assert result["readiness"] == "blocked"
    assert result["reason"] == "series_coverage"
    assert result["requiredSeries"] == ["DTWEXBGS", "WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert result["fulfilledSeries"] == ["DTWEXBGS", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert result["missingSeries"] == ["WALCL"]
    assert result["staleSeries"] == []
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["cacheRowsWouldWrite"] == 2
    assert result["cacheRowsWritten"] == 0
    assert result["writeEfficacy"] == "not_written"
    assert result["scoreGradeUsable"] is False
    assert result["degradedTargetCount"] == 0
    assert result["degradedTargetSymbols"] == []
    assert result["degradedTargetReasons"] == []
    assert result["writtenButNotScoreGradeReason"] == "write_not_attempted"
    assert result["writeEvidence"] == {
        "cacheRowsWouldWrite": 2,
        "cacheRowsWritten": 0,
        "scoreGradeUsable": False,
        "writeAttempted": False,
        "writeEnabled": False,
        "writeEfficacy": "not_written",
        "writtenButNotScoreGradeReason": "write_not_attempted",
    }
    assert result["seriesReadiness"] == [
        {
            "blocked": False,
            "blockedReason": None,
            "freshnessPolicy": "official_h10_weekly_batch_t_plus_7",
            "group": "usd_pressure",
            "series": "DTWEXBGS",
            "status": "fulfilled",
            "symbol": "USD_TWI",
        },
        {
            "blocked": True,
            "blockedReason": "series_coverage",
            "freshnessPolicy": "official_weekly_fed_liquidity_t_plus_7",
            "group": "fed_liquidity",
            "series": "WALCL",
            "status": "missing",
            "symbol": "FED_ASSETS",
        },
        {
            "blocked": False,
            "blockedReason": None,
            "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
            "group": "fed_liquidity",
            "series": "RRPONTSYD",
            "status": "fulfilled",
            "symbol": "FED_RRP",
        },
        {
            "blocked": False,
            "blockedReason": None,
            "freshnessPolicy": "official_weekly_fed_liquidity_t_plus_7",
            "group": "fed_liquidity",
            "series": "WTREGEN",
            "status": "fulfilled",
            "symbol": "TGA",
        },
        {
            "blocked": False,
            "blockedReason": None,
            "freshnessPolicy": "official_weekly_fed_liquidity_t_plus_7",
            "group": "fed_liquidity",
            "series": "WRESBAL",
            "status": "fulfilled",
            "symbol": "RESERVES",
        },
    ]
    assert result["result"] == "dry_run_no_write"
    assert {panel["cacheKey"] for panel in result["targetPanels"]} == {"rates", "macro"}
    rates_panel = next(panel for panel in result["targetPanels"] if panel["cacheKey"] == "rates")
    assert rates_panel["writeAttempted"] is False
    assert rates_panel["writeWouldBeAttemptedWithWrite"] is True
    assert rates_panel["writeEfficacy"] == "not_written"
    assert rates_panel["scoreGradeUsable"] is False
    assert rates_panel["targetGroups"][0]["symbols"] == ["US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"]
    assert rates_panel["targetGroups"][0]["series"] == ["DGS2", "DGS10", "DGS30", "SOFR", "T10Y2Y", "T10Y3M"]
    macro_panel = next(panel for panel in result["targetPanels"] if panel["cacheKey"] == "macro")
    macro_us_rates_group = next(group for group in macro_panel["targetGroups"] if group["name"] == "us_rates")
    assert macro_panel["writeEfficacy"] == "not_written"
    assert macro_panel["scoreGradeUsable"] is False
    assert macro_us_rates_group["symbols"] == ["US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"]
    assert macro_us_rates_group["series"] == ["DGS2", "DGS10", "DGS30", "SOFR", "T10Y2Y", "T10Y3M"]
    assert "rawProviderPayload" not in result
    assert "SECRET" not in str(result)


def test_dry_run_reports_ready_when_activation_readiness_is_fulfilled() -> None:
    result = prewarm.run_prewarm(
        write=False,
        service_factory=lambda: (_ for _ in ()).throw(AssertionError("dry-run must not construct service")),
        readiness_probe=_ready_readiness_summary,
    )

    assert result["dryRun"] is True
    assert result["readiness"] == "ready"
    assert result["reason"] is None
    assert result["fulfilledSeries"] == ["DTWEXBGS", "WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert result["missingSeries"] == []
    assert result["staleSeries"] == []
    assert result["sourceAuthorityAllowed"] is True
    assert result["scoreContributionAllowed"] is True
    assert result["cacheRowsWouldWrite"] == 2
    assert result["cacheRowsWritten"] == 0
    assert result["writeEfficacy"] == "not_written"
    assert result["scoreGradeUsable"] is False
    assert result["degradedTargetCount"] == 0
    assert result["degradedTargetSymbols"] == []
    assert result["degradedTargetReasons"] == []
    assert result["writtenButNotScoreGradeReason"] == "write_not_attempted"
    assert all(item["status"] == "fulfilled" for item in result["seriesReadiness"])
    assert result["writeEvidence"]["writeEfficacy"] == "not_written"
    assert result["writeEvidence"]["cacheRowsWouldWrite"] == 2


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

    result = prewarm.run_prewarm(
        write=True,
        service_factory=factory,
        readiness_probe=_ready_readiness_summary,
    )

    assert result["dryRun"] is False
    assert result["writeAttempted"] is True
    assert result["result"] == "write_attempted"
    assert result["cacheRowsWritten"] == 2
    assert result["writeEfficacy"] == "written_score_grade_usable"
    assert result["scoreGradeUsable"] is True
    assert result["degradedTargetCount"] == 0
    assert result["degradedTargetSymbols"] == []
    assert result["degradedTargetReasons"] == []
    assert result["writtenButNotScoreGradeReason"] is None
    assert created[0].calls == 1
    assert created[0]._market_cache.wait_calls == [prewarm.REFRESH_WAIT_TIMEOUT_SECONDS]
    assert {panel["cacheKey"] for panel in result["panels"]} == {"rates", "macro"}
    rates_panel = next(panel for panel in result["panels"] if panel["cacheKey"] == "rates")
    macro_panel = next(panel for panel in result["panels"] if panel["cacheKey"] == "macro")
    assert rates_panel["writeEfficacy"] == "written_score_grade_usable"
    assert rates_panel["scoreGradeUsable"] is True
    assert rates_panel["degradedTargetCount"] == 0
    assert macro_panel["writeEfficacy"] == "written_score_grade_usable"
    assert macro_panel["scoreGradeUsable"] is True
    assert macro_panel["degradedTargetCount"] == 0
    assert rates_panel["targetSymbolsFound"] == ["US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"]
    assert "T10Y2Y" in {item["series"] for item in rates_panel["targetDiagnostics"]}
    assert "T10Y3M" in {item["series"] for item in rates_panel["targetDiagnostics"]}
    assert "US10Y2Y" in macro_panel["targetSymbolsFound"]
    assert "US10Y3M" in macro_panel["targetSymbolsFound"]


def test_write_mode_refuses_to_write_when_readiness_is_blocked() -> None:
    result = prewarm.run_prewarm(
        write=True,
        service_factory=lambda: (_ for _ in ()).throw(AssertionError("blocked readiness must not construct service")),
        readiness_probe=_blocked_readiness_summary,
    )

    assert result["dryRun"] is False
    assert result["writeEnabled"] is True
    assert result["writeAttempted"] is False
    assert result["readiness"] == "blocked"
    assert result["reason"] == "series_coverage"
    assert result["missingSeries"] == ["WALCL"]
    assert result["cacheRowsWouldWrite"] == 0
    assert result["cacheRowsWritten"] == 0
    assert result["writeEfficacy"] == "not_written"
    assert result["scoreGradeUsable"] is False
    assert result["degradedTargetCount"] == 0
    assert result["degradedTargetSymbols"] == []
    assert result["degradedTargetReasons"] == []
    assert result["writtenButNotScoreGradeReason"] == "write_not_attempted"
    assert result["result"] == "readiness_blocked"
    assert "panels" not in result
    assert "SECRET" not in str(result)


def test_write_cli_returns_nonzero_when_readiness_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(prewarm, "_run_cache_readiness_smoke", _blocked_readiness_summary)

    exit_code = prewarm.main(["--write"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "readiness_blocked"
    assert payload["writeEnabled"] is True
    assert payload["writeAttempted"] is False
    assert payload["readiness"] == "blocked"
    assert payload["missingSeries"] == ["WALCL"]
    assert payload["cacheRowsWritten"] == 0
    assert payload["writeEfficacy"] == "not_written"
    assert payload["scoreGradeUsable"] is False
    assert payload["writtenButNotScoreGradeReason"] == "write_not_attempted"
    assert "SECRET" not in json.dumps(payload)


def test_write_mode_reports_degraded_targets_as_not_score_grade_usable() -> None:
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

    result = prewarm.run_prewarm(
        write=True,
        service_factory=FakeService,
        readiness_probe=_ready_readiness_summary,
    )

    assert result["cacheRowsWritten"] == 2
    assert result["writeEfficacy"] == "written_not_score_grade_usable"
    assert result["scoreGradeUsable"] is False
    assert result["degradedTargetCount"] == 2
    assert result["degradedTargetSymbols"] == ["US10Y", "USD_TWI"]
    assert result["degradedTargetReasons"] == ["budget_exhausted", "missing_api_key"]
    assert result["writtenButNotScoreGradeReason"] == "degraded_target_diagnostics"

    panels = {panel["cacheKey"]: panel for panel in result["panels"]}
    assert panels["rates"]["writeEfficacy"] == "written_not_score_grade_usable"
    assert panels["rates"]["scoreGradeUsable"] is False
    assert panels["rates"]["degradedTargetCount"] == 1
    assert panels["rates"]["degradedTargetSymbols"] == ["US10Y"]
    assert panels["rates"]["degradedTargetReasons"] == ["budget_exhausted"]
    assert panels["rates"]["writtenButNotScoreGradeReason"] == "degraded_target_diagnostics"
    assert panels["macro"]["writeEfficacy"] == "written_not_score_grade_usable"
    assert panels["macro"]["scoreGradeUsable"] is False
    assert panels["macro"]["degradedTargetCount"] == 1
    assert panels["macro"]["degradedTargetSymbols"] == ["USD_TWI"]
    assert panels["macro"]["degradedTargetReasons"] == ["missing_api_key"]
    assert panels["macro"]["writtenButNotScoreGradeReason"] == "degraded_target_diagnostics"

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
