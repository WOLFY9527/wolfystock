# -*- coding: utf-8 -*-
"""Tests for the cache-only liquidity monitor advisory service."""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_cache import MarketCache
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/liquidity_monitor"
LIQUIDITY_MONITOR_SERVICE_PATH = REPO_ROOT / "src/services/liquidity_monitor_service.py"
FROZEN_GOLDEN_NOW = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)
FROZEN_GOLDEN_NOW_ISO = FROZEN_GOLDEN_NOW.isoformat(timespec="seconds")
LIQUIDITY_GOLDEN_FIXTURE_NAMES = (
    "official_cached_macro_rates_context.json",
    "mixed_official_proxy_context.json",
    "missing_macro_rates_proxy_fallback_context.json",
    "credit_stress_observation_only_context.json",
    "delayed_proxy_fx_commodities_context.json",
    "provider_unavailable_stale_malformed_context.json",
)
FORBIDDEN_PUBLIC_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session_id",
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "credential",
    "raw_provider_payload",
    "provider_payload",
    "stack_trace",
    "traceback",
    "http://",
    "https://",
)
FORBIDDEN_LIQUIDITY_MONITOR_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
)
FORBIDDEN_LIQUIDITY_MONITOR_CACHE_PATTERNS = (
    r"\bself\.cache\.get_or_refresh\(",
    r"\bmarket_cache\.get_or_refresh\(",
    r"\bself\.cache\.set\(",
    r"\bmarket_cache\.set\(",
)


class _FakeSeries:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def tolist(self) -> list[Any]:
        return list(self._values)


class _FakeHistoryFrame:
    def __init__(self, closes: list[float], *, volumes: list[float] | None = None, index: list[datetime] | None = None) -> None:
        self._data: Dict[str, list[Any]] = {"Close": list(closes)}
        if volumes is not None:
            self._data["Volume"] = list(volumes)
        self.index = list(index or [])

    @property
    def empty(self) -> bool:
        return not self._data.get("Close")

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __getitem__(self, key: str) -> _FakeSeries:
        return _FakeSeries(self._data[key])


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _iter_strings(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_no_sensitive_public_payload(value: Any) -> None:
    public_text = "\n".join(_iter_strings(value)).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term not in public_text


@pytest.fixture()
def isolated_db(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'liquidity-monitor.sqlite'}")
    yield DatabaseManager.get_instance()
    DatabaseManager.reset_instance()


@pytest.fixture(autouse=True)
def mock_macro_quote_transport():
    with patch(
        "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
        return_value=_FakeHistoryFrame([]),
        create=True,
    ):
        yield


def _cache_entry(
    *,
    source: str,
    freshness: str,
    items: list[Dict[str, Any]],
    updated_at: str,
    as_of: str,
    is_fallback: bool = False,
    warning: str | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "source": source,
        "freshness": freshness,
        "items": items,
        "updatedAt": updated_at,
        "asOf": as_of,
        "isFallback": is_fallback,
        "fallbackUsed": is_fallback,
        "warning": warning,
    }
    return payload


def _make_service() -> LiquidityMonitorService:
    return LiquidityMonitorService(cache=MarketCache(max_workers=1), db=DatabaseManager.get_instance())


def _save_market_overview_snapshot(
    db: DatabaseManager,
    *,
    key: str,
    payload: Dict[str, Any],
) -> None:
    db.save_market_overview_snapshot(key=f"market_overview:{key}", payload=payload)


def _raw_snapshot_payload(
    *,
    source: str,
    items: list[Dict[str, Any]],
    updated_at: str,
    as_of: str,
    freshness: str | None = None,
    fallback_used: bool = False,
    warning: str | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "source": source,
        "items": items,
        "updatedAt": updated_at,
        "asOf": as_of,
        "fallbackUsed": fallback_used,
    }
    if freshness is not None:
        payload["freshness"] = freshness
    if warning is not None:
        payload["warning"] = warning
    return payload


def _liquidity_monitor_imports() -> set[str]:
    tree = ast.parse(LIQUIDITY_MONITOR_SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _cache_only_liquidity_service_payload(build_seed) -> dict[str, Any]:
    service = _make_service()
    quote_map: dict[str, _FakeHistoryFrame] = {}
    build_seed(service, quote_map)
    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            side_effect=lambda ticker: quote_map.get(ticker, _FakeHistoryFrame([])),
            create=True,
        ),
        patch(
            "src.services.liquidity_monitor_service.fetch_binance_funding_row",
            side_effect=RuntimeError("network disabled for golden fixtures"),
        ),
    ):
        return LiquidityMonitorResponse(**service.get_liquidity_monitor()).model_dump()


def _seed_official_cached_macro_rates_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.22,
                    "changePercent": -4.66,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": 0.30, "value": 104.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
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
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_mixed_official_proxy_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.22,
                    "changePercent": -4.66,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "DXY",
                    "label": "DXY",
                    "changePercent": 0.30,
                    "value": 104.2,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_missing_macro_rates_proxy_fallback_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    quote_index = [
        datetime(2026, 5, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 7, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map.update(
        {
            "^VIX": _FakeHistoryFrame([18.0, 15.0], index=quote_index),
            "DX-Y.NYB": _FakeHistoryFrame([104.9, 104.2], index=quote_index),
            "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
            "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
        }
    )


def _seed_credit_stress_observation_only_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.22,
                    "changePercent": -4.66,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "CREDIT",
                    "label": "Credit spreads",
                    "value": 341.0,
                    "change": 12.0,
                    "changePercent": 3.65,
                    "source": "fred",
                    "sourceId": "fred:BAMLH0A0HYM2",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
                    "unit": "bps",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "observationOnly": True,
                    "includedInScore": False,
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": 0.30, "value": 104.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
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
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_delayed_proxy_fx_commodities_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "changePercent": -2.5,
                    "value": 15.2,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "DXY",
                    "label": "DXY",
                    "changePercent": -0.4,
                    "value": 104.2,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "10Y yield",
                    "changePercent": -0.2,
                    "value": 4.1,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                },
                {
                    "symbol": "US30Y",
                    "label": "30Y yield",
                    "changePercent": -0.1,
                    "value": 4.6,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_provider_unavailable_stale_malformed_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    stale_as_of = (FROZEN_GOLDEN_NOW - timedelta(hours=8)).isoformat(timespec="seconds")
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "VIX", "label": "VIX", "changePercent": "oops", "value": None},
                "malformed-entry",
            ],
            updated_at=stale_as_of,
            as_of=stale_as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="stale",
            items=[{"symbol": "US10Y", "label": "10Y yield", "changePercent": "nan", "value": "n/a"}],
            updated_at=stale_as_of,
            as_of=stale_as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="mock",
            freshness="mock",
            is_fallback=True,
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": -0.4, "value": 104.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
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
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
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
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )


def test_liquidity_monitor_runtime_source_stays_cache_only() -> None:
    imported_modules = _liquidity_monitor_imports()
    forbidden_imports = sorted(
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in FORBIDDEN_LIQUIDITY_MONITOR_IMPORT_PREFIXES
        )
    )
    source_text = LIQUIDITY_MONITOR_SERVICE_PATH.read_text(encoding="utf-8")

    assert not forbidden_imports, (
        "Liquidity Monitor must remain a cache-only advisory surface. Do not "
        "add direct provider SDK or raw HTTP imports here; extend it only via "
        f"existing MarketCache snapshots and metadata. Found {forbidden_imports}"
    )
    for pattern in FORBIDDEN_LIQUIDITY_MONITOR_CACHE_PATTERNS:
        assert re.search(pattern, source_text) is None, (
            "Liquidity Monitor must not refresh or mutate MarketCache. "
            "Preserve its existing cache-only/metadata semantics and keep "
            f"`{pattern}` out of liquidity_monitor_service.py"
        )


def test_persistent_raw_macro_snapshot_prefers_official_vix_without_proxy_fetch(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="macro",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIXCLS",
                    "label": "VIX",
                    "value": 18.22,
                    "changePercent": -4.66,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                }
            ],
        ),
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="yfinance_proxy",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        indicator = service._vix_indicator(service._read_panel("volatility"), service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert indicator["status"] == "partial"
    assert "FRED VIXCLS" in indicator["summary"]
    assert "official_public" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_persistent_raw_volatility_snapshot_prefers_official_vix_without_proxy_fetch(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 16.8,
                    "changePercent": -3.2,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                }
            ],
        ),
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="macro",
        payload=_raw_snapshot_payload(
            source="yfinance_proxy",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        indicator = service._vix_indicator(service._read_panel("volatility"), service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert "FRED VIXCLS" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_expired_proxy_volatility_cache_yields_to_newer_official_snapshot_without_proxy_refetch(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    stale_cache_as_of = "2026-05-15T12:00:00+08:00"
    fresh_snapshot_as_of = "2026-05-15T14:15:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                }
            ],
            updated_at=stale_cache_as_of,
            as_of=stale_cache_as_of,
        ),
        ttl_seconds=-1,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=fresh_snapshot_as_of,
            as_of=fresh_snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 16.8,
                    "changePercent": -3.2,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                }
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        panel = service._read_panel("volatility")
        indicator = service._vix_indicator(panel, service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert panel.source == "mixed"
    assert panel.freshness == "delayed"
    assert panel.as_of == fresh_snapshot_as_of
    assert indicator["freshness"] == "delayed"
    assert "FRED VIXCLS" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_mixed_raw_rates_snapshot_with_fallback_used_still_accepts_official_yields(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            fallback_used=True,
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "LEGACY_FILLER",
                    "label": "legacy",
                    "value": 0.0,
                    "source": "fallback",
                    "sourceType": "fallback_static",
                    "isFallback": True,
                },
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        rates_panel = service._read_panel("rates")
        reliable_symbols = {item["symbol"] for item in service._reliable_items(rates_panel, {"US2Y", "US10Y", "US30Y"})}
        indicator = service._us_rates_indicator(rates_panel, service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert rates_panel.is_fallback is False
    assert reliable_symbols == {"US2Y", "US10Y", "US30Y"}
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert "US Treasury" in indicator["summary"]
    assert "official_public" in indicator["summary"]


def test_expired_proxy_rates_cache_yields_to_newer_official_snapshot_without_proxy_refetch(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    stale_cache_as_of = "2026-05-15T12:00:00+08:00"
    fresh_snapshot_as_of = "2026-05-15T14:14:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.82,
                    "changePercent": 0.24,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.42,
                    "changePercent": 0.41,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.69,
                    "changePercent": 0.33,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                },
            ],
            updated_at=stale_cache_as_of,
            as_of=stale_cache_as_of,
        ),
        ttl_seconds=-1,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=fresh_snapshot_as_of,
            as_of=fresh_snapshot_as_of,
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                },
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        panel = service._read_panel("rates")
        indicator = service._us_rates_indicator(panel, service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert panel.source == "mixed"
    assert panel.freshness == "delayed"
    assert panel.as_of == fresh_snapshot_as_of
    assert indicator["freshness"] == "delayed"
    assert "US2Y -0.22%" in indicator["summary"]
    assert "US10Y -0.31%" in indicator["summary"]
    assert "US30Y -0.18%" in indicator["summary"]
    assert "US Treasury" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_raw_rates_snapshot_with_sofr_only_official_data_uses_proxy_yields_for_scoring(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                }
            ],
        ),
    )
    quote_index = [
        datetime(2026, 5, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 7, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
        "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
    }

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            side_effect=lambda ticker: quote_map.get(ticker, _FakeHistoryFrame([])),
            create=True,
        ),
    ):
        indicator = service._us_rates_indicator(service._read_panel("rates"), service._read_panel("macro"))

    assert service._external_provider_calls_used is True
    assert indicator["includedInScore"] is True
    assert indicator["scoreContribution"] == 6
    assert indicator["freshness"] == "delayed"
    assert "US10Y -1.97%" in indicator["summary"]
    assert "US30Y -1.26%" in indicator["summary"]
    assert "SOFR +5.31%" in indicator["summary"]
    assert "Yahoo Finance" in indicator["summary"]
    assert "FRED SOFR" in indicator["summary"]


def test_stale_raw_official_observation_is_marked_stale_and_excluded(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    stale_as_of = (FROZEN_GOLDEN_NOW - timedelta(days=4)).isoformat(timespec="seconds")
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 24.0,
                    "changePercent": 2.1,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": stale_as_of,
                    "asOf": stale_as_of,
                }
            ],
        ),
    )

    with patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW):
        panel = service._read_panel("volatility")

    assert panel.payload["items"][0]["freshness"] == "stale"
    assert service._item_freshness(panel.payload["items"][0], panel) == "stale"
    assert service._reliable_items(panel, {"VIX"}) == []


def test_raw_official_snapshot_without_item_freshness_normalizes_to_delayed_without_fallback(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    snapshot_as_of = "2026-05-14T14:15:00+08:00"
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=snapshot_as_of,
            as_of=snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.4,
                    "changePercent": -2.4,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": snapshot_as_of,
                    "asOf": snapshot_as_of,
                }
            ],
        ),
    )

    with patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 9, 0, tzinfo=CN_TZ)):
        panel = service._read_panel("volatility")

    assert panel.freshness == "delayed"
    assert panel.is_fallback is False
    assert panel.payload["items"][0]["freshness"] == "delayed"
    assert panel.payload["items"][0]["isStale"] is False
    assert service._reliable_items(panel, {"VIX"})[0]["symbol"] == "VIX"


def test_malformed_raw_official_observation_is_skipped_and_proxy_fallback_remains_available(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": "n/a",
                    "changePercent": "oops",
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                }
            ],
        ),
    )
    quote_index = [
        datetime(2026, 5, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 7, 16, 0, tzinfo=timezone.utc),
    ]

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            return_value=_FakeHistoryFrame([18.0, 15.0], index=quote_index),
            create=True,
        ),
    ):
        panel = service._read_panel("volatility")
        indicator = service._vix_indicator(panel, service._read_panel("macro"))

    assert service._reliable_items(panel, {"VIX"}) == []
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert "Yahoo Finance" in indicator["summary"]
    assert "official_public" not in indicator["summary"]


def test_older_snapshot_does_not_override_fresher_cache_candidate(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    cache_as_of = "2026-05-15T14:20:00+08:00"
    older_snapshot_as_of = "2026-05-15T14:14:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.6,
                    "changePercent": -4.4,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "freshness": "cached",
                    "updatedAt": cache_as_of,
                    "asOf": cache_as_of,
                }
            ],
            updated_at=cache_as_of,
            as_of=cache_as_of,
        ),
        ttl_seconds=300,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=older_snapshot_as_of,
            as_of=older_snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 19.8,
                    "changePercent": 1.6,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": older_snapshot_as_of,
                    "asOf": older_snapshot_as_of,
                }
            ],
        ),
    )

    with patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)):
        panel = service._read_panel("volatility")

    assert panel.as_of == cache_as_of
    assert panel.freshness == "cached"
    assert panel.payload["items"][0]["value"] == 15.6
    assert panel.payload["items"][0]["changePercent"] == -4.4


@pytest.mark.parametrize(
    ("db_payload", "expected_source"),
    [
        (
            _raw_snapshot_payload(
                source="mixed",
                updated_at="2026-05-15T14:15:00+08:00",
                as_of="2026-05-15T14:15:00+08:00",
                items=[
                    {
                        "symbol": "VIX",
                        "label": "VIX",
                        "value": "n/a",
                        "changePercent": "oops",
                        "source": "fred",
                        "sourceId": "fred:VIXCLS",
                        "sourceType": "official_public",
                        "sourceLabel": "FRED VIXCLS",
                        "updatedAt": "2026-05-15T14:15:00+08:00",
                        "asOf": "2026-05-15T14:15:00+08:00",
                    }
                ],
            ),
            "mixed",
        ),
        (
            _raw_snapshot_payload(
                source="fallback",
                freshness="fallback",
                updated_at="2026-05-15T14:15:00+08:00",
                as_of="2026-05-15T14:15:00+08:00",
                fallback_used=True,
                items=[
                    {
                        "symbol": "VIX",
                        "label": "VIX",
                        "value": 22.1,
                        "changePercent": 2.2,
                        "source": "fallback",
                        "sourceType": "fallback_static",
                        "sourceLabel": "备用数据",
                        "isFallback": True,
                    }
                ],
            ),
            "mixed",
        ),
    ],
)
def test_malformed_or_fallback_only_snapshot_does_not_override_cache_candidate(
    isolated_db: DatabaseManager,
    db_payload: Dict[str, Any],
    expected_source: str,
) -> None:
    service = _make_service()
    cache_as_of = "2026-05-15T14:20:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.6,
                    "changePercent": -4.4,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "freshness": "cached",
                    "updatedAt": cache_as_of,
                    "asOf": cache_as_of,
                }
            ],
            updated_at=cache_as_of,
            as_of=cache_as_of,
        ),
        ttl_seconds=300,
    )
    _save_market_overview_snapshot(isolated_db, key="volatility", payload=db_payload)

    with patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)):
        panel = service._read_panel("volatility")

    assert panel.source == expected_source
    assert panel.as_of == cache_as_of
    assert panel.freshness == "cached"
    assert panel.payload["items"][0]["value"] == 15.6


def test_liquidity_monitor_metadata_declares_read_only_runtime_boundary(isolated_db: DatabaseManager) -> None:
    payload = _make_service().get_liquidity_monitor()

    assert payload["endpoint"] == "/api/v1/market/liquidity-monitor"
    assert payload["sourceMetadata"] == {
        "externalProviderCalls": True,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
    }
    assert "不触发扫描、回测或组合动作" in payload["advisoryDisclosure"]


def test_unavailable_when_fewer_than_three_reliable_indicators(isolated_db: DatabaseManager) -> None:
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
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 0.8}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()

    assert payload["score"]["value"] == 50
    assert payload["score"]["regime"] == "unavailable"
    assert payload["score"]["confidence"] == 0.3


def test_fallback_stale_mock_and_error_indicators_are_excluded_from_score(isolated_db: DatabaseManager) -> None:
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
            items=[{"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8}, {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3}],
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
        "crypto",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "BTC", "label": "Bitcoin", "changePercent": 3.4, "value": 65000}],
            updated_at=now,
            as_of=now,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="stale",
            items=[{"symbol": "US10Y", "label": "10Y yield", "changePercent": -0.2, "value": 4.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="mock",
            freshness="mock",
            is_fallback=True,
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": -0.4, "value": 104.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["score"]["regime"] == "supportive"
    assert payload["score"]["value"] == 69
    assert indicators["crypto_spot_momentum"]["includedInScore"] is False
    assert indicators["us_rates_pressure"]["includedInScore"] is False
    assert indicators["usd_pressure"]["includedInScore"] is False
    assert indicators["crypto_spot_momentum"]["status"] == "unavailable"
    assert indicators["us_rates_pressure"]["status"] == "unavailable"
    assert indicators["usd_pressure"]["status"] == "unavailable"


def test_reliable_indicators_move_score_deterministically(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    for key, payload in {
        "volatility": _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "VIX", "label": "VIX", "changePercent": -3.0, "value": 14.6}],
            updated_at=now,
            as_of=now,
        ),
        "fx_commodities": _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": -0.6, "value": 103.8}],
            updated_at=now,
            as_of=now,
        ),
        "rates": _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "US10Y", "label": "10Y yield", "changePercent": -0.2, "value": 4.1}],
            updated_at=now,
            as_of=now,
        ),
        "crypto": _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 3.0, "value": 65000},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 2.0, "value": 3200},
                {"symbol": "BNB", "label": "BNB", "changePercent": 1.0, "value": 600},
            ],
            updated_at=now,
            as_of=now,
        ),
        "us_breadth": _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 9}, {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 2}],
            updated_at=now,
            as_of=now,
        ),
        "funds_flow": _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.5}],
            updated_at=now,
            as_of=now,
        ),
    }.items():
        service.cache.set(key, payload, ttl_seconds=30)

    payload = service.get_liquidity_monitor()

    assert payload["score"]["value"] == 87
    assert payload["score"]["regime"] == "abundant"
    assert payload["score"]["confidence"] > 0.5


def test_derived_freshness_uses_weakest_input_freshness(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)
    live = now.isoformat(timespec="seconds")
    delayed = (now - timedelta(minutes=12)).isoformat(timespec="seconds")

    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": live},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": delayed},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.5, "value": 600, "asOf": live},
            ],
            updated_at=live,
            as_of=live,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8, "asOf": live}, {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3, "asOf": delayed}],
            updated_at=live,
            as_of=live,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2, "asOf": live}],
            updated_at=live,
            as_of=live,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["crypto_spot_momentum"]["freshness"] == "delayed"
    assert indicators["us_breadth_proxy"]["freshness"] == "delayed"
    assert payload["freshness"]["weakestIndicatorFreshness"] == "delayed"


def test_crypto_funding_uses_binance_public_endpoint_when_cache_snapshot_lacks_funding(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance_ws",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": now},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": now},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.5, "value": 600, "asOf": now},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    funding_rows = {
        "BTCUSDT": {"lastFundingRate": "0.00012", "time": 1770000000000},
        "ETHUSDT": {"lastFundingRate": "-0.00005", "time": 1770003600000},
    }

    with patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=lambda symbol: funding_rows[symbol]):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"] == {
        "externalProviderCalls": True,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
    }
    assert indicators["crypto_funding"]["status"] == "live"
    assert indicators["crypto_funding"]["freshness"] == "live"
    assert "BTC" in str(indicators["crypto_funding"]["summary"])
    assert "ETH" in str(indicators["crypto_funding"]["summary"])
    assert "Binance" in str(indicators["crypto_funding"]["summary"])
    assert "exchange_public" in str(indicators["crypto_funding"]["summary"])
    assert "cache_snapshot" not in str(indicators["crypto_funding"]["summary"])


def test_crypto_funding_stays_unavailable_when_binance_public_endpoint_fails(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance_ws",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": now},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": now},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    with patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=RuntimeError("funding unavailable")):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicators["crypto_funding"]["status"] == "unavailable"
    assert indicators["crypto_funding"]["freshness"] == "unavailable"
    assert "Binance" in str(indicators["crypto_funding"]["summary"])
    assert "暂不可用" in str(indicators["crypto_funding"]["summary"])


def test_response_source_metadata_reports_runtime_and_cache_boundaries(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    payload = service.get_liquidity_monitor()

    assert payload["sourceMetadata"] == {
        "externalProviderCalls": True,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
    }


def test_crypto_breadth_uses_btc_eth_bnb_vote_not_avg_change(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 8.0, "value": 65000},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": -7.0, "value": 3200},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.0, "value": 600},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
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
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.0}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["crypto_spot_momentum"]["includedInScore"] is True
    assert indicators["crypto_spot_momentum"]["scoreContribution"] == 0
    assert "1/3" in indicators["crypto_spot_momentum"]["summary"]


def test_usd_pressure_uses_reliable_fx_crosses_when_dxy_missing(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[
                {"symbol": "USDCNH", "label": "USD/CNH", "changePercent": 0.28, "value": 7.24},
                {"symbol": "USDJPY", "label": "USD/JPY", "changePercent": 0.39, "value": 156.4},
                {"symbol": "EURUSD", "label": "EUR/USD", "changePercent": -0.28, "value": 1.066},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["usd_pressure"]["includedInScore"] is True
    assert indicators["usd_pressure"]["scoreContribution"] == -6
    assert "USD/CNH" in indicators["usd_pressure"]["summary"]


def test_us_rates_indicator_uses_treasury_basket_when_us10y_missing(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[
                {"symbol": "US2Y", "label": "2Y yield", "changePercent": -0.18, "value": 4.82},
                {"symbol": "US30Y", "label": "30Y yield", "changePercent": -0.11, "value": 4.71},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["us_rates_pressure"]["includedInScore"] is True
    assert indicators["us_rates_pressure"]["scoreContribution"] == 6
    assert "US2Y" in indicators["us_rates_pressure"]["summary"]


def test_us_breadth_indicator_uses_relative_proxy_votes(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 6},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 5},
                {"symbol": "RSP_SPY", "label": "RSP vs SPY", "value": -0.4, "changePercent": -0.4},
                {"symbol": "IWM_SPY", "label": "IWM vs SPY", "value": -0.5, "changePercent": -0.5},
                {"symbol": "QQQ_SPY", "label": "QQQ vs SPY", "value": -0.2, "changePercent": -0.2},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["us_breadth_proxy"]["includedInScore"] is True
    assert indicators["us_breadth_proxy"]["scoreContribution"] == -6
    assert "RSP/SPY" in indicators["us_breadth_proxy"]["summary"]


def test_cn_flow_indicator_uses_reliable_flow_basket_and_cn_breadth_context(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "cn_flows",
        _cache_entry(
            source="eastmoney",
            freshness="live",
            items=[
                {"symbol": "SOUTHBOUND", "label": "Southbound", "value": 28.4},
                {"symbol": "MAINLAND_MAIN", "label": "Mainland main", "value": 18.5},
                {"symbol": "MARGIN_BALANCE", "label": "Margin balance", "value": 31.2},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "cn_breadth",
        _cache_entry(
            source="eastmoney",
            freshness="live",
            items=[
                {"symbol": "EFFECT", "label": "赚钱效应", "value": 64},
                {"symbol": "ADV_RATIO", "label": "上涨比例", "value": 63.2},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["cn_hk_flows"]["includedInScore"] is True
    assert indicators["cn_hk_flows"]["scoreContribution"] == 6
    assert "宽度" in indicators["cn_hk_flows"]["summary"]


def test_vix_indicator_uses_yfinance_proxy_when_volatility_panel_is_unavailable(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^VIX": _FakeHistoryFrame([18.0, 15.0], index=quote_index),
    }

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicators["vix_pressure"]["includedInScore"] is True
    assert indicators["vix_pressure"]["status"] == "partial"
    assert indicators["vix_pressure"]["freshness"] == "delayed"
    assert indicators["vix_pressure"]["scoreContribution"] == 8
    assert "Yahoo Finance" in str(indicators["vix_pressure"]["summary"])
    assert "unofficial_proxy" in str(indicators["vix_pressure"]["summary"])


def test_vix_indicator_prefers_official_macro_cache_over_yfinance_proxy(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.22,
                    "changePercent": -4.66,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                }
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]

    assert indicator["includedInScore"] is True
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "cached"
    assert "FRED VIXCLS" in str(indicator["summary"])
    assert "official_public" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])


def test_vix_indicator_ignores_malformed_official_macro_cache_and_keeps_cached_proxy_truthful(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.2,
                    "changePercent": -2.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "asOf": as_of,
                    "updatedAt": as_of,
                }
            ],
            updated_at=as_of,
            as_of=as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": None,
                    "changePercent": "oops",
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "asOf": as_of,
                    "updatedAt": as_of,
                }
            ],
            updated_at=as_of,
            as_of=as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]

    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert "Yahoo Finance" in str(indicator["summary"])
    assert "类型 official_public" not in str(indicator["summary"])
    assert "类型 proxy_public" in str(indicator["summary"])
    assert "FRED VIXCLS" not in str(indicator["summary"])


def test_yfinance_proxy_panels_remain_delayed_and_not_live_provider_labels(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^VIX": _FakeHistoryFrame([18.0, 15.0], index=quote_index),
    }

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]

    assert indicator["freshness"] == "delayed"
    assert indicator["status"] == "partial"
    assert "新鲜度 delayed" in str(indicator["summary"])
    assert "新鲜度 live" not in str(indicator["summary"])
    assert "类型 unofficial_proxy" in str(indicator["summary"])
    assert "类型 official_public" not in str(indicator["summary"])


def test_usd_pressure_uses_yfinance_dxy_proxy_when_fx_panel_is_unavailable(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "DX-Y.NYB": _FakeHistoryFrame([104.9, 104.2], index=quote_index),
    }

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicators["usd_pressure"]["includedInScore"] is True
    assert indicators["usd_pressure"]["status"] == "partial"
    assert indicators["usd_pressure"]["freshness"] == "delayed"
    assert indicators["usd_pressure"]["scoreContribution"] == 6
    assert "DXY" in str(indicators["usd_pressure"]["summary"])
    assert "Yahoo Finance" in str(indicators["usd_pressure"]["summary"])


def test_us_rates_indicator_uses_yfinance_treasury_proxies_when_rates_panel_is_unavailable(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
        "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
    }

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicators["us_rates_pressure"]["includedInScore"] is True
    assert indicators["us_rates_pressure"]["status"] == "partial"
    assert indicators["us_rates_pressure"]["freshness"] == "delayed"
    assert indicators["us_rates_pressure"]["scoreContribution"] == 6
    assert "US10Y" in str(indicators["us_rates_pressure"]["summary"])
    assert "US30Y" in str(indicators["us_rates_pressure"]["summary"])
    assert "Yahoo Finance" in str(indicators["us_rates_pressure"]["summary"])


def test_us_rates_indicator_prefers_official_macro_cache_and_keeps_sofr_observation_only(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[
                {"symbol": "US2Y", "label": "2Y yield", "changePercent": 0.15, "value": 4.82, "source": "yahoo"},
                {"symbol": "US10Y", "label": "10Y yield", "changePercent": 0.28, "value": 4.51, "source": "yahoo"},
                {"symbol": "US30Y", "label": "30Y yield", "changePercent": 0.12, "value": 4.72, "source": "yahoo"},
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]

    assert indicator["includedInScore"] is True
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "cached"
    assert indicator["scoreContribution"] == 6
    assert "US2Y -0.22%" in str(indicator["summary"])
    assert "US10Y -0.31%" in str(indicator["summary"])
    assert "US30Y -0.18%" in str(indicator["summary"])
    assert "SOFR +5.31" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])


def test_us_rates_indicator_uses_official_macro_cache_when_rates_panel_is_unavailable(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]

    assert indicator["includedInScore"] is True
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "cached"
    assert indicator["scoreContribution"] == 6
    assert "US10Y" in str(indicator["summary"])
    assert "US30Y" in str(indicator["summary"])
    assert "US Treasury" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])


def test_us_rates_indicator_falls_back_to_proxy_yields_when_official_yields_are_malformed(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
        "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
    }
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": "oops",
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": None,
                    "changePercent": None,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert indicator["scoreContribution"] == 6
    assert "US10Y -1.97%" in str(indicator["summary"])
    assert "US30Y -1.26%" in str(indicator["summary"])
    assert "SOFR +5.31%" in str(indicator["summary"])
    assert "Yahoo Finance" in str(indicator["summary"])
    assert "FRED SOFR" in str(indicator["summary"])
    assert "unofficial_proxy / official_public" in str(indicator["summary"])


def test_freshness_latest_as_of_uses_selected_official_snapshot_when_snapshot_wins(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    stale_cache_as_of = "2026-05-15T12:00:00+08:00"
    fresh_snapshot_as_of = "2026-05-15T14:15:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                }
            ],
            updated_at=stale_cache_as_of,
            as_of=stale_cache_as_of,
        ),
        ttl_seconds=-1,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=fresh_snapshot_as_of,
            as_of=fresh_snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 16.8,
                    "changePercent": -3.2,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                }
            ],
        ),
    )
    earlier_official_as_of = "2026-05-15T14:10:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "cached",
                    "updatedAt": earlier_official_as_of,
                    "asOf": earlier_official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "cached",
                    "updatedAt": earlier_official_as_of,
                    "asOf": earlier_official_as_of,
                },
            ],
            updated_at=earlier_official_as_of,
            as_of=earlier_official_as_of,
        ),
        ttl_seconds=300,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2, "updatedAt": earlier_official_as_of, "asOf": earlier_official_as_of}],
            updated_at=earlier_official_as_of,
            as_of=earlier_official_as_of,
        ),
        ttl_seconds=300,
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([]), create=True),
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=RuntimeError("network disabled")),
    ):
        payload = service.get_liquidity_monitor()

    assert payload["freshness"]["latestAsOf"] == fresh_snapshot_as_of
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]
    assert indicator["updatedAt"] == fresh_snapshot_as_of
    assert "FRED VIXCLS" in str(indicator["summary"])


def test_official_credit_stress_observation_is_summary_only_and_does_not_change_score(isolated_db: DatabaseManager) -> None:
    base_as_of = "2026-05-12T16:15:00+08:00"

    def _build_payload(*, include_credit: bool) -> Dict[str, Any]:
        service = _make_service()
        service.cache.set(
            "volatility",
            _cache_entry(
                source="yfinance_proxy",
                freshness="live",
                items=[{"symbol": "VIX", "label": "VIX", "changePercent": -3.0, "value": 14.6}],
                updated_at=base_as_of,
                as_of=base_as_of,
            ),
            ttl_seconds=30,
        )
        service.cache.set(
            "funds_flow",
            _cache_entry(
                source="yfinance_proxy",
                freshness="live",
                items=[{"symbol": "ETF", "label": "ETF flows", "value": 1.2}],
                updated_at=base_as_of,
                as_of=base_as_of,
            ),
            ttl_seconds=30,
        )
        macro_items = [
            {
                "symbol": "US2Y",
                "label": "US 2Y",
                "value": 4.92,
                "changePercent": -0.22,
                "source": "treasury",
                "sourceId": "treasury:DGS2",
                "sourceType": "official_public",
                "sourceLabel": "US Treasury",
                "unit": "%",
                "asOf": base_as_of,
                "updatedAt": base_as_of,
            },
            {
                "symbol": "US10Y",
                "label": "US 10Y",
                "value": 4.31,
                "changePercent": -0.31,
                "source": "treasury",
                "sourceId": "treasury:DGS10",
                "sourceType": "official_public",
                "sourceLabel": "US Treasury",
                "unit": "%",
                "asOf": base_as_of,
                "updatedAt": base_as_of,
            },
            {
                "symbol": "US30Y",
                "label": "US 30Y",
                "value": 4.58,
                "changePercent": -0.18,
                "source": "treasury",
                "sourceId": "treasury:DGS30",
                "sourceType": "official_public",
                "sourceLabel": "US Treasury",
                "unit": "%",
                "asOf": base_as_of,
                "updatedAt": base_as_of,
            },
        ]
        if include_credit:
            macro_items.append(
                {
                    "symbol": "CREDIT",
                    "label": "Credit spreads",
                    "value": 341.0,
                    "change": 12.0,
                    "changePercent": 3.65,
                    "source": "fred",
                    "sourceId": "fred:BAMLH0A0HYM2",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
                    "unit": "bps",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                    "observationOnly": True,
                    "includedInScore": False,
                }
            )
        service.cache.set(
            "macro",
            _cache_entry(
                source="mixed",
                freshness="cached",
                items=macro_items,
                updated_at=base_as_of,
                as_of=base_as_of,
            ),
            ttl_seconds=30,
        )
        return service.get_liquidity_monitor()

    baseline = _build_payload(include_credit=False)
    with_credit = _build_payload(include_credit=True)

    baseline_indicator = {item["key"]: item for item in baseline["indicators"]}["us_rates_pressure"]
    with_credit_indicator = {item["key"]: item for item in with_credit["indicators"]}["us_rates_pressure"]

    assert baseline["score"] == with_credit["score"] == {
        "value": 69,
        "regime": "supportive",
        "confidence": 0.44,
        "includedIndicatorCount": 3,
        "possibleIndicatorWeight": 43,
        "includedIndicatorWeight": 19,
    }
    assert baseline_indicator["includedInScore"] is True
    assert baseline_indicator["scoreWeight"] == 6
    assert baseline_indicator["scoreContribution"] == 6
    assert "CREDIT" not in str(baseline_indicator["summary"])
    assert with_credit_indicator["includedInScore"] is True
    assert with_credit_indicator["scoreWeight"] == 6
    assert with_credit_indicator["scoreContribution"] == 6
    assert "CREDIT +341.00bps" in str(with_credit_indicator["summary"])


LIQUIDITY_GOLDEN_SCENARIOS = (
    ("official_cached_macro_rates_context.json", _seed_official_cached_macro_rates_context),
    ("mixed_official_proxy_context.json", _seed_mixed_official_proxy_context),
    ("missing_macro_rates_proxy_fallback_context.json", _seed_missing_macro_rates_proxy_fallback_context),
    ("credit_stress_observation_only_context.json", _seed_credit_stress_observation_only_context),
    ("delayed_proxy_fx_commodities_context.json", _seed_delayed_proxy_fx_commodities_context),
    ("provider_unavailable_stale_malformed_context.json", _seed_provider_unavailable_stale_malformed_context),
)


@pytest.mark.parametrize(("fixture_name", "build_seed"), LIQUIDITY_GOLDEN_SCENARIOS)
def test_liquidity_monitor_golden_fixtures_match_public_dto_contract(
    isolated_db: DatabaseManager,
    fixture_name: str,
    build_seed,
) -> None:
    del isolated_db
    expected = LiquidityMonitorResponse(**_load_fixture(fixture_name)).model_dump()
    actual = _cache_only_liquidity_service_payload(build_seed)

    assert actual == expected
    _assert_no_sensitive_public_payload(actual)


def test_liquidity_monitor_credit_stress_fixture_remains_observation_only_and_preserves_baseline_score(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    baseline = _cache_only_liquidity_service_payload(_seed_official_cached_macro_rates_context)
    with_credit = _cache_only_liquidity_service_payload(_seed_credit_stress_observation_only_context)

    baseline_indicator = {item["key"]: item for item in baseline["indicators"]}["us_rates_pressure"]
    with_credit_indicator = {item["key"]: item for item in with_credit["indicators"]}["us_rates_pressure"]

    assert baseline["score"] == with_credit["score"] == {
        "value": 69,
        "regime": "supportive",
        "confidence": 0.72,
        "includedIndicatorCount": 5,
        "possibleIndicatorWeight": 43,
        "includedIndicatorWeight": 31,
    }
    assert "CREDIT" not in str(baseline_indicator["summary"])
    assert "CREDIT +341.00bps" in str(with_credit_indicator["summary"])
    assert baseline_indicator["scoreContribution"] == with_credit_indicator["scoreContribution"] == 6


def test_all_liquidity_golden_fixtures_are_explicitly_enumerated_and_sanitized() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert {path.name for path in fixture_paths} == set(LIQUIDITY_GOLDEN_FIXTURE_NAMES)
    for path in fixture_paths:
        _assert_no_sensitive_public_payload(json.loads(path.read_text(encoding="utf-8")))
