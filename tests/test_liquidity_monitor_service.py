# -*- coding: utf-8 -*-
"""Tests for the cache-only liquidity monitor advisory service."""

from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_cache import MarketCache
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path(__file__).resolve().parents[1]
LIQUIDITY_MONITOR_SERVICE_PATH = REPO_ROOT / "src/services/liquidity_monitor_service.py"
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


def _liquidity_monitor_imports() -> set[str]:
    tree = ast.parse(LIQUIDITY_MONITOR_SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


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
