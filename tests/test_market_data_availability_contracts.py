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
    MarketOverviewService,
    classify_market_payload_reliability,
    get_freshness_status,
)
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))


class _FrameColumn:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _HistoryFrame:
    def __init__(self, closes: list[float], *, as_of: datetime) -> None:
        self.empty = False
        self.index = [as_of - timedelta(days=1), as_of]
        self._columns = {
            "Close": _FrameColumn(closes),
        }

    def __getitem__(self, key: str) -> _FrameColumn:
        return self._columns[key]

    def __contains__(self, key: str) -> bool:
        return key in self._columns


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


def _payload_provenance(payload: dict[str, Any]) -> dict[str, str]:
    return project_source_provenance(
        source=payload.get("source"),
        source_type=payload.get("sourceType"),
        source_label=payload.get("sourceLabel"),
        freshness=payload.get("freshness"),
        is_fallback=bool(
            payload.get("isFallback")
            or payload.get("fallbackUsed")
            or payload.get("fallback_used")
        ),
        is_stale=bool(payload.get("isStale")),
        is_from_snapshot=bool(payload.get("isFromSnapshot")),
        no_external_calls=bool(payload.get("noExternalCalls")),
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


def test_us_breadth_future_stub_proxy_and_fallback_never_project_as_official_or_live() -> None:
    cases = {
        "future_stub": project_source_provenance(
            source="disabled_live_stub",
            source_type="disabled_live_stub",
            freshness="fallback",
        ),
        "yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "fallback_static": project_source_provenance(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
        ),
    }

    assert cases["future_stub"]["sourceType"] == "fallback_static"
    assert cases["yfinance_proxy"]["sourceType"] == "unofficial_proxy"
    assert cases["fallback_static"]["sourceType"] == "fallback_static"
    assert all(
        payload["sourceType"] not in {"official_public", "exchange_public"}
        for payload in cases.values()
    )
    assert all(payload["freshnessLabel"] != "实时" for payload in cases.values())


def test_fx_commodities_and_futures_proxy_or_stub_provenance_never_projects_as_official_or_live() -> None:
    cases = {
        "fx_fallback_static": project_source_provenance(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
        ),
        "fx_yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
        "futures_delayed_stub": project_source_provenance(
            source="disabled_live_stub",
            source_type="disabled_live_stub",
            freshness="delayed",
        ),
        "futures_yfinance_proxy": project_source_provenance(
            source="yfinance_proxy",
            source_type="proxy_public",
            freshness="delayed",
        ),
    }

    assert cases["fx_fallback_static"]["sourceType"] == "fallback_static"
    assert cases["fx_yfinance_proxy"]["sourceType"] == "unofficial_proxy"
    assert cases["futures_delayed_stub"]["sourceType"] == "disabled_live_stub"
    assert cases["futures_yfinance_proxy"]["sourceType"] == "unofficial_proxy"
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


def test_market_overview_fallback_only_panels_project_to_fallback_static_not_live() -> None:
    service = MarketOverviewService()

    for getter in (service.get_cn_flows, service.get_rates):
        payload = getter()
        provenance = _payload_provenance(payload)

        assert payload["isFallback"] is True
        assert payload["freshness"] == "fallback"
        assert payload["sourceLabel"] == "备用数据"
        assert provenance["sourceType"] == "fallback_static"
        assert provenance["sourceLabel"] == "备用数据"
        assert provenance["freshnessLabel"] != "实时"


def test_market_overview_fx_commodities_proxy_payload_projects_to_unofficial_proxy_not_live() -> None:
    service = MarketOverviewService()
    as_of = datetime.now(CN_TZ) - timedelta(minutes=30)
    frames = {
        "DX-Y.NYB": _HistoryFrame([104.0, 104.3], as_of=as_of),
        "CNH=X": _HistoryFrame([7.20, 7.24], as_of=as_of),
        "JPY=X": _HistoryFrame([155.3, 156.4], as_of=as_of),
        "EURUSD=X": _HistoryFrame([1.071, 1.066], as_of=as_of),
        "GC=F": _HistoryFrame([2350.0, 2368.7], as_of=as_of),
        "CL=F": _HistoryFrame([79.1, 78.4], as_of=as_of),
        "BZ=F": _HistoryFrame([82.7, 82.1], as_of=as_of),
        "HG=F": _HistoryFrame([4.58, 4.63], as_of=as_of),
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.services.market_overview_service.fetch_yfinance_quote_history_frame",
            lambda ticker: frames[ticker],
        )
        with pytest.MonkeyPatch.context() as log_mp:
            class _LogService:
                def record_market_overview_fetch(self, **_: Any) -> str:
                    return "log-3"

            log_mp.setattr("src.services.market_overview_service.ExecutionLogService", _LogService)
            payload = service.get_fx_commodities()

    provenance = _payload_provenance(payload)
    dxy_provenance = _payload_provenance(next(item for item in payload["items"] if item["symbol"] == "DXY"))

    assert payload["source"] == "yfinance_proxy"
    assert payload["freshness"] == "delayed"
    assert payload["providerHealth"]["status"] == "cache"
    assert provenance["sourceType"] == "unofficial_proxy"
    assert dxy_provenance["sourceType"] == "unofficial_proxy"
    assert provenance["freshnessLabel"] != "实时"
    assert dxy_provenance["freshnessLabel"] != "实时"


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
    assert indicators["us_etf_flow_proxy"]["label"] == "US ETF 资金代理"
    assert indicators["us_etf_flow_proxy"]["status"] == "partial"
    assert indicators["us_breadth_proxy"]["includedInScore"] is True
    assert indicators["us_breadth_proxy"]["label"] == "US 广度代理"
    assert indicators["us_breadth_proxy"]["status"] == "partial"
    assert indicators["cn_hk_flows"]["includedInScore"] is False
    assert indicators["cn_hk_flows"]["status"] == "unavailable"
    assert indicators["cn_hk_flows"]["freshness"] == "fallback"
    assert indicators["futures_premarket"]["includedInScore"] is False
    assert indicators["futures_premarket"]["status"] == "unavailable"
    assert indicators["futures_premarket"]["freshness"] == "fallback"
