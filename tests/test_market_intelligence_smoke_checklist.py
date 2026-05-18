# -*- coding: utf-8 -*-
"""Market Intelligence smoke coverage and manual checklist contract."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
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


def test_market_intelligence_checklist_captures_scope_and_validation_commands() -> None:
    checklist = CHECKLIST_PATH.read_text(encoding="utf-8")

    assert "python3 -m pytest tests/test_market_intelligence_smoke_checklist.py -q" in checklist
    assert "tests/test_market_overview_snapshot.py" in checklist
    assert "tests/test_liquidity_monitor_service.py" in checklist
    assert "tests/test_market_rotation_radar_service.py" in checklist
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
        "/api/v1/market/rotation-radar?market=US",
        "/api/v1/market/sector-rotation",
    ):
        assert endpoint in checklist
    assert "backend-only" in checklist
    assert "not frontend visual validation" in checklist
    assert "not trading or investment signal execution" in checklist
    assert "No provider order changes." in checklist
    assert "No MarketCache core changes." in checklist
    assert "No scoring/ranking/stage changes." in checklist


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
    assert temperature_payload["scores"]["overall"]["label"] == "数据不足"

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

    assert briefing_payload["source"] == "fallback"
    assert briefing_payload["freshness"] == "fallback"
    assert briefing_payload["freshness"] != "live"
    assert briefing_payload["isFallback"] is True
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
    assert radar_payload["metadata"]["quoteProvider"]["present"] is True
    assert radar_payload["metadata"]["quoteProvider"]["sourceType"] == "cache_snapshot"
    top_theme = radar_payload["themes"][0]
    assert top_theme["freshness"] == "delayed"
    assert top_theme["freshness"] != "live"
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
    assert fallback_radar["themes"][0]["rotationStateEvidence"]["state"] == "insufficient_evidence"
