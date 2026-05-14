# -*- coding: utf-8 -*-
"""Data availability contracts for visible market, liquidity, and rotation surfaces."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_cache import MarketCache
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_overview_service import (
    classify_market_payload_reliability,
    get_freshness_status,
)
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))


@pytest.fixture()
def isolated_db(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 't101-data-availability.sqlite'}")
    yield DatabaseManager.get_instance()
    DatabaseManager.reset_instance()


def _cache_entry(
    *,
    source: str,
    freshness: str,
    items: list[dict[str, Any]],
    updated_at: str,
    as_of: str,
    is_fallback: bool = False,
    warning: str | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "freshness": freshness,
        "items": items,
        "updatedAt": updated_at,
        "asOf": as_of,
        "isFallback": is_fallback,
        "fallbackUsed": is_fallback,
        "warning": warning,
    }


def _make_service() -> LiquidityMonitorService:
    return LiquidityMonitorService(
        cache=MarketCache(max_workers=1),
        db=DatabaseManager.get_instance(),
    )


def test_non_live_and_proxy_provenance_never_projects_as_official_or_live() -> None:
    cases = {
        "fallback_static": project_source_provenance(
            source="fallback",
            freshness="live",
            is_fallback=True,
        ),
        "synthetic_fixture": project_source_provenance(
            source="synthetic_fixture",
            freshness="synthetic_delayed",
        ),
        "missing": project_source_provenance(
            source="unavailable",
            freshness="unavailable",
        ),
        "yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "tickflow_proxy": project_source_provenance(
            source="tickflow",
            source_type="public_api",
            freshness="delayed",
        ),
    }

    assert cases["fallback_static"]["sourceType"] == "fallback_static"
    assert cases["synthetic_fixture"]["sourceType"] == "synthetic_fixture"
    assert cases["missing"]["sourceType"] == "missing"
    assert cases["yfinance_proxy"]["sourceType"] == "unofficial_proxy"
    assert cases["tickflow_proxy"]["sourceType"] == "public_proxy"
    assert all(
        payload["sourceType"] not in {"official_public", "exchange_public"}
        for payload in cases.values()
    )
    assert all(payload["freshnessLabel"] != "实时" for payload in cases.values())


def test_market_reliability_classifier_excludes_fallback_static_synthetic_missing_and_stale_inputs() -> None:
    cases = [
        (
            "fallback_static",
            {"source": "fallback", "freshness": "fallback", "isFallback": True, "value": 1.0},
            "fallback",
        ),
        (
            "synthetic_fixture",
            {"source": "synthetic_fixture", "freshness": "delayed", "value": 1.0},
            "fallback",
        ),
        (
            "missing",
            {"source": "unavailable", "freshness": "unavailable", "value": None},
            "error",
        ),
        (
            "stale_proxy",
            {"source": "yfinance_proxy", "freshness": "stale", "isStale": True, "value": 1.0},
            "stale",
        ),
    ]

    for _, payload, expected_kind in cases:
        reliability = classify_market_payload_reliability(payload, category="macro_rate")

        assert reliability["kind"] == expected_kind
        assert reliability["isReliable"] is False
        assert reliability["excluded"] is True
        assert reliability["confidenceWeight"] == 0.0


def test_official_daily_macro_observations_stay_delayed_or_stale_not_live() -> None:
    delayed = get_freshness_status(
        "2026-05-14T15:00:00+08:00",
        "macro_rate",
        "treasury",
        False,
        source_type="official_public",
        now=datetime(2026, 5, 14, 16, 0, tzinfo=timezone.utc),
    )
    stale = get_freshness_status(
        "2026-05-10T15:00:00+08:00",
        "macro_rate",
        "treasury",
        False,
        source_type="official_public",
        now=datetime(2026, 5, 14, 16, 0, tzinfo=timezone.utc),
    )

    assert delayed["freshness"] == "delayed"
    assert delayed["isFallback"] is False
    assert delayed["isStale"] is False
    assert delayed["freshness"] != "live"
    assert stale["freshness"] == "stale"
    assert stale["isFallback"] is False
    assert stale["isStale"] is True
    assert stale["warning"]


def test_liquidity_monitor_only_scores_reliable_non_fallback_signals(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")

    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "VIX", "label": "VIX", "changePercent": -2.5, "value": 15.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "cn_flows",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "NORTHBOUND", "label": "北向资金", "value": 88.8}],
            updated_at=now,
            as_of=now,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "futures",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "NQ", "label": "纳指期货", "changePercent": 1.5, "value": 18420.0}],
            updated_at=now,
            as_of=now,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["score"]["includedIndicatorCount"] >= 3
    assert indicators["vix_pressure"]["includedInScore"] is True
    assert indicators["us_etf_flow_proxy"]["includedInScore"] is True
    assert indicators["us_breadth_proxy"]["includedInScore"] is True
    assert indicators["cn_hk_flows"]["includedInScore"] is False
    assert indicators["cn_hk_flows"]["status"] == "unavailable"
    assert indicators["cn_hk_flows"]["freshness"] == "fallback"
    assert indicators["futures_premarket"]["includedInScore"] is False
    assert indicators["futures_premarket"]["status"] == "unavailable"
    assert indicators["futures_premarket"]["freshness"] == "fallback"
