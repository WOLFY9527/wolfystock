# -*- coding: utf-8 -*-
"""Market Intelligence smoke coverage and manual checklist contract."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.storage import DatabaseManager


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "liquidity_monitor"
CHECKLIST_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "market-overview"
    / "market-intelligence-smoke-checklist.md"
)


@pytest.fixture(autouse=True)
def _reset_market_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_OVERVIEW_SNAPSHOT_TEST_DB", "1")
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'market-intelligence-smoke.sqlite'}")
    market_cache.clear()
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    market_cache.clear()
    MarketOverviewService._market_cache.wait_for_refreshes(timeout=2)
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    DatabaseManager.reset_instance()


def _load_liquidity_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _live_indices_payload(value: float = 5120.25) -> dict:
    return {
        "source": "yahoo",
        "sourceLabel": "Yahoo Finance",
        "updatedAt": "2026-05-18T09:30:00+08:00",
        "asOf": "2026-05-18T09:30:00+08:00",
        "freshness": "live",
        "items": [
            {
                "symbol": "SPX",
                "label": "S&P 500",
                "value": value,
                "changePercent": 0.42,
                "source": "yahoo",
                "sourceLabel": "Yahoo Finance",
                "freshness": "live",
                "isFallback": False,
            }
        ],
    }


def _quote(
    symbol: str,
    change: float,
    *,
    volume_ratio: float = 1.0,
    freshness: str = "delayed",
) -> dict:
    return {
        "symbol": symbol,
        "name": symbol,
        "price": 100.0,
        "changePercent": change,
        "volume": 1_000_000 * volume_ratio,
        "averageVolume": 1_000_000,
        "vwap": 99.0,
        "freshness": freshness,
        "isStale": freshness == "stale",
        "isFallback": False,
        "source": "smoke_fixture",
        "sourceLabel": "Smoke Fixture",
        "sourceType": "synthetic_fixture",
        "asOf": "2026-05-18T01:45:00+00:00",
        "timeWindows": {
            "1d": {
                "changePercent": change,
                "relativeVolume": volume_ratio,
                "freshness": freshness,
                "asOf": "2026-05-18T01:45:00+00:00",
            }
        },
    }


def _assert_rotation_headline_lists_are_eligible(payload: dict) -> None:
    summary = payload["summary"]
    headline_ids: set[str] = set()
    for list_name in ("strongestThemes", "acceleratingThemes"):
        for theme in summary[list_name]:
            assert theme["rankEligible"] is True, f"{list_name} contains rank-ineligible {theme['id']}"
            assert theme["headlineEligible"] is True, f"{list_name} contains headline-ineligible {theme['id']}"
            assert theme["rankingLane"] == "headline", f"{list_name} contains non-headline lane {theme['id']}"
            assert theme.get("observationOnly") is False, f"{list_name} contains observation-only {theme['id']}"
            assert theme.get("taxonomyOnly") is False, f"{list_name} contains taxonomy-only {theme['id']}"
            headline_ids.add(theme["id"])
    observation_ids = {theme["id"] for theme in summary.get("observationThemes", [])}
    taxonomy_ids = {theme["id"] for theme in summary.get("taxonomyThemes", [])}
    assert headline_ids.isdisjoint(observation_ids), "headline lists overlap observation lane"
    assert headline_ids.isdisjoint(taxonomy_ids), "headline lists overlap taxonomy lane"
    assert all(theme["rankingLane"] == "observation" for theme in summary.get("observationThemes", []))
    assert all(theme["rankingLane"] == "taxonomy" for theme in summary.get("taxonomyThemes", []))


def _assert_market_overview_panel_has_display_contract(payload: dict) -> None:
    for item in payload.get("items", []):
        assert item.get("freshness"), f"{item.get('symbol')} missing freshness"
        if item.get("value") is None:
            assert item.get("freshness") not in {"live", "fresh"}, f"{item.get('symbol')} missing value marked live"
            assert item.get("isUnavailable") or item.get("degradationReason"), (
                f"{item.get('symbol')} missing unavailable/degradation evidence"
            )
            assert item.get("degradationReason"), f"{item.get('symbol')} missing degradationReason"
            assert item.get("trustLevel") in {"unavailable", "weak"}, f"{item.get('symbol')} missing weak/unavailable trust"
            continue
        assert item.get("value") != "N/A", f"{item.get('symbol')} explicit value collapsed to N/A"
        assert item.get("sourceTier"), f"{item.get('symbol')} missing sourceTier"
        assert item.get("trustLevel"), f"{item.get('symbol')} missing trustLevel"


class _FrameColumn:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _HistoryFrame:
    def __init__(self, closes: list[float], *, as_of: datetime) -> None:
        self.empty = False
        self.index = [as_of]
        self._columns = {"Close": _FrameColumn(closes)}

    def __getitem__(self, key: str) -> _FrameColumn:
        return self._columns[key]

    def __contains__(self, key: str) -> bool:
        return key in self._columns


def test_market_intelligence_checklist_captures_scope_and_validation_commands() -> None:
    checklist = CHECKLIST_PATH.read_text(encoding="utf-8")

    assert "python3 -m pytest tests/test_market_intelligence_smoke_checklist.py -q" in checklist
    assert "tests/test_market_overview_core_quote_repair.py" in checklist
    assert "tests/test_market_overview_snapshot.py" in checklist
    assert "tests/test_liquidity_monitor_service.py" in checklist
    assert "tests/test_rotation_theme_registry.py" in checklist
    assert "tests/test_market_rotation_radar_service.py" in checklist
    assert "tests/test_cn_provider_health_service.py" in checklist
    assert "tests/api/test_cn_provider_health.py" in checklist
    assert "tests/api/test_market_rotation_radar.py" in checklist
    assert "python3 -m py_compile" in checklist
    assert "git diff --check" in checklist
    assert "./scripts/release_secret_scan.sh" in checklist
    for endpoint in (
        "/api/v1/market-overview/indices",
        "/api/v1/market-overview/volatility",
        "/api/v1/market-overview/macro",
        "/api/v1/market-overview/sentiment",
        "/api/v1/market/temperature",
        "/api/v1/market/market-briefing",
        "/api/v1/market/liquidity-monitor",
        "/api/v1/market/cn-provider-health",
        "/api/v1/market/rotation-radar?market=US",
        "/api/v1/market/sector-rotation",
    ):
        assert endpoint in checklist
    assert "backend-only" in checklist
    assert "not frontend visual validation" in checklist
    assert "not trading or investment signal execution" in checklist
    assert "No provider order changes." in checklist
    assert "No MarketCache core changes." in checklist
    assert "Fallback/static Rotation Radar themes must stay observation-only and out of headline rankings." in checklist
    assert "No provider score/stage formula changes." in checklist
    assert "Core quote indicators" in checklist
    for symbol in ("SPX", "VIX", "HSI", "US10Y", "DXY", "BTC"):
        assert symbol in checklist
    assert "sourceTier" in checklist
    assert "trustLevel" in checklist
    assert "requiredProviderClass" in checklist
    assert "scoreContributionAllowed" in checklist
    assert "scoreExclusionReason" in checklist
    assert "requiredRealSourceForScore" in checklist
    assert "proxyObservationOnlyReason" in checklist
    assert "`scoreContribution=0`" in checklist
    assert "N/A is allowed only with explicit unavailable evidence" in checklist
    assert "metadata-only" in checklist
    assert "market quotes" in checklist
    assert "K-lines" in checklist
    assert "symbol universes" in checklist
    assert "raw provider payloads" in checklist
    assert "scoring output" in checklist
    assert "observationOnly=true" in checklist
    assert "scoreContributionAllowed=false" in checklist
    assert "pytdx may be `usable_with_caution` when healthy" in checklist
    assert "AKShare stays `weak`" in checklist
    assert "missing dependency / probe failure states must degrade" in checklist
    assert "`temperatureAvailable=false`" in checklist
    assert "`disabledReason=insufficient_reliable_inputs`" in checklist
    assert "Observation-only Rotation Radar themes must not appear in `summary.strongestThemes` or `summary.acceleratingThemes`." in checklist
    assert "`summary.observationThemes` and `summary.taxonomyThemes` must remain separate from headline lists." in checklist
    assert "Headline indicators must not render ambiguous N/A when a backend item has a numeric value." in checklist
    assert "Missing headline indicator values must include `isUnavailable`, `degradationReason`, non-live `freshness`, and weak/unavailable trust metadata." in checklist


def test_market_intelligence_smoke_aligns_proxy_vix_freshness_and_trust_metadata() -> None:
    service = MarketOverviewService()
    # Keep the proxy fixture inside the delayed window so the test validates
    # source alignment instead of accidental wall-clock staleness.
    as_of = datetime.now(timezone.utc) - timedelta(minutes=10)

    def history(ticker: str) -> _HistoryFrame:
        if ticker == "^VIX":
            return _HistoryFrame([18.0, 15.0], as_of=as_of)
        raise RuntimeError(f"{ticker} fixture unavailable")

    with (
        patch("src.services.market_overview_service.fetch_yfinance_quote_history_frame", side_effect=history),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=history, create=True),
        patch.object(service, "_official_macro_points", return_value={}),
        patch.object(service, "_atr_item", return_value=None),
        patch("src.services.market_overview_service.ExecutionLogService") as log_service,
    ):
        log_service.return_value.record_market_overview_fetch.return_value = "log-vix-smoke"
        volatility_payload = service.get_volatility()
        liquidity_payload = LiquidityMonitorService(db=DatabaseManager.get_instance()).get_liquidity_monitor()

    market_vix = next(item for item in volatility_payload["items"] if item["symbol"] == "VIX")
    liquidity_vix = next(item for item in liquidity_payload["indicators"] if item["key"] == "vix_pressure")

    assert volatility_payload["freshness"] == "delayed"
    assert volatility_payload["freshness"] not in {"live", "fresh"}
    assert market_vix["freshness"] == liquidity_vix["freshness"] == "delayed"
    assert market_vix["sourceType"] == liquidity_vix["evidence"]["inputs"][0]["sourceType"] == "unofficial_proxy"
    assert market_vix["sourceTier"] == liquidity_vix["coverageDiagnostics"]["sourceTier"]
    assert market_vix["trustLevel"] == liquidity_vix["coverageDiagnostics"]["trustLevel"] == "usable_with_caution"
    assert market_vix["source"] in {"yfinance", "yfinance_proxy"}
    assert liquidity_vix["evidence"]["source"] == "yfinance_proxy"
    assert liquidity_vix["includedInScore"] is False
    assert liquidity_vix["scoreContribution"] == 0
    assert liquidity_vix["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert liquidity_vix["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert liquidity_vix["coverageDiagnostics"]["requiredRealSourceForScore"] is True
    assert liquidity_vix["coverageDiagnostics"]["proxyObservationOnlyReason"] == "proxy_only_missing_real_source"
    _assert_market_overview_panel_has_display_contract(volatility_payload)


def test_market_overview_liquidity_and_degraded_temperature_stay_truthful() -> None:
    service = MarketOverviewService()
    service._cached_payload(
        "indices",
        Mock(return_value=_live_indices_payload()),
        Mock(return_value={"source": "fallback", "freshness": "fallback", "isFallback": True, "items": []}),
    )
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()

    stale_indices = service._cached_payload(
        "indices",
        Mock(side_effect=RuntimeError("indices request timed out")),
        Mock(return_value={"source": "fallback", "freshness": "fallback", "isFallback": True, "items": []}),
    )

    assert stale_indices["source"] == "yahoo"
    assert stale_indices["freshness"] == "stale"
    assert stale_indices["freshness"] != "live"
    assert stale_indices["isStale"] is True
    assert stale_indices["isFallback"] is False
    assert stale_indices["isFromSnapshot"] is True
    assert stale_indices["items"][0]["freshness"] == "stale"

    official_liquidity = LiquidityMonitorResponse(
        **_load_liquidity_fixture("official_cached_macro_rates_context.json")
    ).model_dump()
    degraded_liquidity = LiquidityMonitorResponse(
        **_load_liquidity_fixture("provider_unavailable_stale_malformed_context.json")
    ).model_dump()

    assert official_liquidity["freshness"]["status"] in {"cached", "delayed", "stale"}
    assert official_liquidity["freshness"]["status"] != "live"
    assert any(indicator["evidence"]["inputs"] for indicator in official_liquidity["indicators"])
    assert degraded_liquidity["freshness"]["status"] in {"fallback", "stale", "delayed"}
    assert degraded_liquidity["freshness"]["status"] != "live"
    assert any(
        indicator["evidence"]["isFallback"]
        or indicator["evidence"]["isUnavailable"]
        or indicator["evidence"]["isPartial"]
        for indicator in degraded_liquidity["indicators"]
    )

    with patch.object(service, "_build_market_temperature_inputs", return_value=service._fallback_market_temperature_inputs()):
        temperature_payload = service.get_market_temperature()

    assert temperature_payload["source"] == "fallback"
    assert temperature_payload["freshness"] == "fallback"
    assert temperature_payload["freshness"] != "live"
    assert temperature_payload["isFallback"] is True
    assert temperature_payload["isReliable"] is False
    assert temperature_payload["temperatureAvailable"] is False
    assert temperature_payload["insufficientReliableInputs"] is True
    assert temperature_payload["disabledReason"] == "insufficient_reliable_inputs"
    assert temperature_payload["unavailableReason"] == "insufficient_reliable_inputs"
    assert temperature_payload["requiredReliableInputCount"] == 5
    assert temperature_payload["conclusionAllowed"] is False
    assert temperature_payload["trustLevel"] in {"weak", "unavailable"}
    assert temperature_payload["scoreCap"] <= 0.4
    assert temperature_payload["scores"]["overall"]["label"] == "数据不足"
    assert temperature_payload["evidenceSnapshot"]["degradationReason"] == "provider_unavailable"

    market_cache.clear()
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()

    degraded_temperature_inputs = copy.deepcopy(service._fallback_market_temperature_inputs())
    for key, source in (("indices", "sina"), ("rates", "sina"), ("crypto", "binance")):
        panel = degraded_temperature_inputs[key]
        panel["source"] = source
        panel["sourceLabel"] = "实时数据"
        panel["fallbackUsed"] = False
        panel["isFallback"] = False
        panel["freshness"] = "live"
        for idx, item in enumerate(panel.get("items", [])):
            if idx != 0:
                continue
            item["source"] = source
            item["sourceLabel"] = "实时数据"
            item["fallbackUsed"] = False
            item["isFallback"] = False
            item["freshness"] = "live"

    with patch.object(service, "_build_market_temperature_inputs", return_value=degraded_temperature_inputs):
        degraded_temperature_payload = service.get_market_temperature()

    assert degraded_temperature_payload["source"] == "mixed"
    assert degraded_temperature_payload["isFallback"] is False
    assert degraded_temperature_payload["fallbackUsed"] is True
    assert degraded_temperature_payload["isReliable"] is False
    assert degraded_temperature_payload["temperatureAvailable"] is False
    assert degraded_temperature_payload["insufficientReliableInputs"] is True
    assert degraded_temperature_payload["disabledReason"] == "insufficient_reliable_inputs"
    assert degraded_temperature_payload["unavailableReason"] == "insufficient_reliable_inputs"
    assert degraded_temperature_payload["requiredReliableInputCount"] == 5
    assert degraded_temperature_payload["conclusionAllowed"] is False
    assert degraded_temperature_payload["trustLevel"] == "weak"
    assert degraded_temperature_payload["scoreCap"] <= 0.4
    assert degraded_temperature_payload["freshness"] == "partial"
    assert degraded_temperature_payload["providerHealth"]["status"] == "partial"
    assert "low_coverage" in degraded_temperature_payload["degradationReasons"]
    assert degraded_temperature_payload["confidence"] < 0.25
    assert degraded_temperature_payload["evidenceSnapshot"]["coverage"] < 0.25
    assert degraded_temperature_payload["evidenceSnapshot"]["degradationReason"] == "partial_coverage"
    assert degraded_temperature_payload["scores"]["overall"]["label"] == "数据不足"

    market_cache.clear()
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()

    legacy_sentiment_only_inputs = {
        "indices": {"items": []},
        "breadth": {"items": []},
        "flows": {"items": []},
        "sectors": {"items": []},
        "rates": {"items": []},
        "fx": {"items": []},
        "futures": {"items": []},
        "sentiment": {
            "source": "cnn",
            "sourceLabel": "CNN",
            "freshness": "live",
            "isFallback": False,
            "items": [
                {
                    "symbol": "FGI",
                    "label": "Fear & Greed",
                    "value": 52,
                    "unit": "score",
                    "source": "cnn",
                    "freshness": "live",
                    "isFallback": False,
                }
            ],
        },
        "crypto": {"items": []},
        "fallback_notice": True,
    }
    with patch.object(service, "_build_market_temperature_inputs", return_value=legacy_sentiment_only_inputs):
        briefing_payload = service.get_market_briefing()

    assert briefing_payload["source"] == "mixed"
    assert briefing_payload["freshness"] == "partial"
    assert briefing_payload["isFallback"] is False
    assert briefing_payload["fallbackUsed"] is True
    assert briefing_payload["temperatureAvailable"] is False
    assert briefing_payload["disabledReason"] == "insufficient_reliable_inputs"
    assert briefing_payload["conclusionAllowed"] is False
    assert briefing_payload["isReliable"] is False
    assert all(item["category"] == "risk" for item in briefing_payload["items"])
    assert all(item["severity"] in {"warning", "neutral"} for item in briefing_payload["items"])


def test_rotation_radar_and_sector_rotation_projection_keep_evidence_non_live_when_degraded() -> None:
    quotes = {
        "QQQ": _quote("QQQ", 0.4),
        "SPY": _quote("SPY", 0.2),
        "IWM": _quote("IWM", 0.1),
        "IGV": _quote("IGV", 0.6),
        "APP": _quote("APP", 3.0, volume_ratio=1.8),
        "PLTR": _quote("PLTR", 2.4, volume_ratio=1.5),
        "CRM": _quote("CRM", 1.8, volume_ratio=1.3),
    }
    radar_service = MarketRotationRadarService(
        quote_provider=lambda symbols: {
            "quotes": {symbol: copy.deepcopy(quotes[symbol]) for symbol in symbols if symbol in quotes},
            "metadata": {
                "quoteMode": "proxy",
                "sourceType": "cache_snapshot",
                "freshness": "delayed",
                "asOf": "2026-05-18T01:45:00+00:00",
                "noExternalCalls": True,
            },
        },
        now_provider=lambda: datetime(2026, 5, 18, 1, 50, tzinfo=timezone.utc),
    )

    radar_payload = radar_service.get_rotation_radar()
    assert radar_payload["source"] == "computed"
    assert radar_payload["freshness"] == "delayed"
    assert radar_payload["freshness"] != "live"
    _assert_rotation_headline_lists_are_eligible(radar_payload)
    assert radar_payload["metadata"]["quoteProvider"]["present"] is True
    assert radar_payload["metadata"]["quoteProvider"]["sourceType"] == "cache_snapshot"
    top_theme = radar_payload["themes"][0]
    assert top_theme["freshness"] == "delayed"
    assert top_theme["freshness"] != "live"
    assert top_theme["themeDefinition"]["themeId"]
    assert top_theme["proxyEvidence"]["claimBoundary"]
    assert top_theme["scoreBreakdown"]["finalScore"] == top_theme["rotationScore"]
    assert top_theme["weightBreakdown"]["relativeStrength"] == 0.28
    assert top_theme["rotationStateEvidence"]["evidenceSnapshot"]["contractVersion"] == "source_confidence_contract_v1"
    assert top_theme["rotationStateEvidence"]["sourceConfidence"]["freshness"] in {"delayed", "partial"}
    assert top_theme["rotationStateEvidence"]["sourceConfidence"]["freshness"] != "live"

    projected_payload = MarketOverviewService()._project_sector_rotation_snapshot(radar_payload)
    assert projected_payload["source"] == "computed"
    assert projected_payload["freshness"] == "delayed"
    assert projected_payload["freshness"] != "live"
    assert projected_payload["radarSnapshot"]["freshness"] == "delayed"
    assert projected_payload["items"]
    projected_item = projected_payload["items"][0]
    assert projected_item["freshness"] == "delayed"
    assert projected_item["freshness"] != "live"
    assert projected_item["rotationStateEvidence"]["sourceConfidence"]["freshness"] in {"delayed", "partial"}
    assert projected_item["rotationStateEvidence"]["sourceConfidence"]["freshness"] != "live"
    assert projected_item["sourceFreshnessEvidence"]["freshness"] == "delayed"

    fallback_radar = MarketRotationRadarService().get_rotation_radar()
    assert fallback_radar["isFallback"] is True
    assert fallback_radar["freshness"] == "fallback"
    assert fallback_radar["freshness"] != "live"
    assert fallback_radar["metadata"]["quoteProvider"]["status"] == "absent"
    assert fallback_radar["summary"]["strongestThemes"] == []
    assert fallback_radar["summary"]["acceleratingThemes"] == []
    _assert_rotation_headline_lists_are_eligible(fallback_radar)
    assert fallback_radar["summary"]["eligibleThemeCount"] == 0
    assert "没有可用于头部排名" in fallback_radar["summary"]["noHeadlineReason"]
    assert "fallback/static" in fallback_radar["summary"]["headlineWarning"]
    assert all(theme["rankEligible"] is False for theme in fallback_radar["themes"])
    assert all(theme["headlineEligible"] is False for theme in fallback_radar["themes"])
    assert all(theme["scoreContributionAllowed"] is False for theme in fallback_radar["themes"])
    assert all(theme["rankingLane"] == "observation" for theme in fallback_radar["themes"])
    assert all(theme["scoreBreakdown"] for theme in fallback_radar["themes"])
    assert fallback_radar["themes"][0]["rotationStateEvidence"]["state"] == "insufficient_evidence"

    taxonomy_radar = MarketRotationRadarService().get_rotation_radar(market="CN")
    assert taxonomy_radar["summary"]["strongestThemes"] == []
    assert taxonomy_radar["summary"]["acceleratingThemes"] == []
    _assert_rotation_headline_lists_are_eligible(taxonomy_radar)
    assert taxonomy_radar["summary"]["taxonomyThemes"]
    assert all(theme["rankingLane"] == "taxonomy" for theme in taxonomy_radar["summary"]["taxonomyThemes"])
