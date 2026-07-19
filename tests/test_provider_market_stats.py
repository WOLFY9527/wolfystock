# -*- coding: utf-8 -*-
"""Characterization tests for provider-local A-share market statistics."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import pytest

from data_provider import akshare_fetcher as akshare_module
from data_provider import tushare_fetcher as tushare_module
from data_provider.akshare_fetcher import AkshareFetcher
from data_provider.efinance_fetcher import EfinanceFetcher
from data_provider.tushare_fetcher import TushareFetcher


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_MODULE_NAME = "data_provider.market_stats"
HELPER_PATH = REPO_ROOT / "data_provider" / "market_stats.py"
EXPECTED_KEYS = [
    "up_count",
    "down_count",
    "flat_count",
    "limit_up_count",
    "limit_down_count",
    "total_amount",
]


def _calculate_market_stats(df: pd.DataFrame) -> dict[str, object]:
    spec = importlib.util.find_spec(HELPER_MODULE_NAME)
    assert spec is not None, "provider-local market-stats helper missing"
    module = importlib.import_module(HELPER_MODULE_NAME)
    calculate = getattr(module, "calculate_market_stats", None)
    assert callable(calculate), "calculate_market_stats helper missing"
    return calculate(df)


def _representative_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ts_code": "920001.BJ", "name": "*ST BSE", "close": 13.0, "pre_close": 10.0, "amount": 1e8},
            {"ts_code": "688001.SH", "name": "STAR", "close": 12.0, "pre_close": 10.0, "amount": 2e8},
            {"ts_code": "300001.SZ", "name": "ChiNext", "close": 8.0, "pre_close": 10.0, "amount": 3e8},
            {"ts_code": "600001.SH", "name": "*ST Main", "close": 10.5, "pre_close": 10.0, "amount": 4e8},
            {"ts_code": "600002.SH", "name": "Main", "close": 9.0, "pre_close": 10.0, "amount": 5e8},
            {"ts_code": "600003.SH", "name": "Flat", "close": 10.0, "pre_close": 10.0, "amount": 6e8},
            {"ts_code": "600004.SH", "name": "Missing price", "close": None, "pre_close": 10.0, "amount": 7e8},
            {"ts_code": "600005.SH", "name": "Dash price", "close": "-", "pre_close": 10.0, "amount": 8e8},
            {"ts_code": "600006.SH", "name": "Zero amount", "close": 11.0, "pre_close": 10.0, "amount": 0},
            {"ts_code": "600007.SH", "name": "Invalid amount", "close": 11.0, "pre_close": 10.0, "amount": "bad"},
            {"ts_code": "600008.SH", "name": "Zero price", "close": 0.0, "pre_close": 10.0, "amount": 9e8},
            {"ts_code": "600009.SH", "name": "Negative price", "close": -1.0, "pre_close": 10.0, "amount": 10e8},
        ]
    )


def _configure_fetcher(fetcher: object) -> None:
    fetcher._set_random_user_agent = lambda: None
    fetcher._enforce_rate_limit = lambda: None


def test_helper_calculates_all_a_share_count_limit_and_amount_branches() -> None:
    frame = _representative_frame()

    result = _calculate_market_stats(frame)

    assert list(result) == EXPECTED_KEYS
    assert result == {
        "up_count": 4,
        "down_count": 2,
        "flat_count": 1,
        "limit_up_count": 4,
        "limit_down_count": 2,
        "total_amount": np.float64(55.0),
    }
    assert all(type(result[key]) is int for key in EXPECTED_KEYS[:-1])
    assert type(result["total_amount"]) is np.float64
    assert frame.loc[9, "amount"] == "bad"


@pytest.mark.parametrize(
    "row",
    [
        {"代码": "600000", "名称": "Main", "最新价": 11, "昨收": 10, "成交额": 1e8},
        {"股票代码": "600000", "股票名称": "Main", "最新价": 11, "昨日收盘": 10, "成交额": 1e8},
        {"ts_code": "600000.SH", "name": "Main", "close": 11, "pre_close": 10, "amount": 1e8},
        {"stock_code": "SH600000", "name": "Main", "lastPrice": 11, "lastClose": 10, "amount": 1e8},
    ],
    ids=("eastmoney", "efinance", "tushare", "xtdata"),
)
def test_helper_preserves_only_the_existing_column_aliases(row: dict[str, object]) -> None:
    result = _calculate_market_stats(pd.DataFrame([row]))

    assert result == {
        "up_count": 1,
        "down_count": 0,
        "flat_count": 0,
        "limit_up_count": 1,
        "limit_down_count": 0,
        "total_amount": np.float64(1.0),
    }


def test_helper_preserves_existing_column_precedence() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "600000",
                "股票代码": "920001",
                "名称": "Main",
                "股票名称": "*ST secondary",
                "最新价": 11.0,
                "close": 13.0,
                "昨收": 10.0,
                "pre_close": 20.0,
                "成交额": 1e8,
                "amount": 9e8,
            }
        ]
    )

    result = _calculate_market_stats(frame)

    assert result["up_count"] == 1
    assert result["limit_up_count"] == 1
    assert result["total_amount"] == np.float64(1.0)


@pytest.mark.parametrize("missing_column", ("ts_code", "name", "close", "pre_close", "amount"))
def test_helper_keeps_missing_required_alias_groups_unavailable(missing_column: str) -> None:
    frame = pd.DataFrame(
        [{"ts_code": "600000.SH", "name": "Main", "close": 11, "pre_close": 10, "amount": 1e8}]
    ).drop(columns=[missing_column])

    with pytest.raises(KeyError):
        _calculate_market_stats(frame)


def test_helper_distinguishes_empty_required_rows_from_missing_columns() -> None:
    result = _calculate_market_stats(pd.DataFrame(columns=["ts_code", "name", "close", "pre_close", "amount"]))

    assert result == dict.fromkeys(EXPECTED_KEYS[:-1], 0) | {"total_amount": np.float64(0.0)}

    with pytest.raises(KeyError):
        _calculate_market_stats(pd.DataFrame())


@pytest.mark.parametrize(
    ("column", "value", "error_type"),
    [
        ("close", "bad", ValueError),
        ("pre_close", "bad", ValueError),
        ("amount", pd.NA, TypeError),
    ],
)
def test_helper_preserves_invalid_row_errors(column: str, value: object, error_type: type[Exception]) -> None:
    row = {"ts_code": "600000.SH", "name": "Main", "close": 11, "pre_close": 10, "amount": 1e8}
    row[column] = value

    with pytest.raises(error_type):
        _calculate_market_stats(pd.DataFrame([row]))


@pytest.mark.parametrize(
    ("amount", "expected_up"),
    [(0, 0), ("0", 1), (None, 1), (np.nan, 1), ("bad", 1)],
)
def test_helper_preserves_numeric_zero_and_unavailable_amount_distinctions(
    amount: object,
    expected_up: int,
) -> None:
    frame = pd.DataFrame(
        [{"ts_code": "600000.SH", "name": "Main", "close": 11, "pre_close": 10, "amount": amount}]
    )

    result = _calculate_market_stats(frame)

    assert result["up_count"] == expected_up
    assert result["limit_up_count"] == expected_up
    assert result["total_amount"] == np.float64(0.0)


def test_helper_preserves_positive_price_gate_and_zero_pre_close_behavior() -> None:
    frame = pd.DataFrame(
        [
            {"ts_code": "600000.SH", "name": "Zero", "close": 0, "pre_close": 10, "amount": 1e8},
            {"ts_code": "600001.SH", "name": "Negative", "close": -1, "pre_close": 10, "amount": 1e8},
            {"ts_code": "600002.SH", "name": "Zero pre-close", "close": 1, "pre_close": 0, "amount": 1e8},
        ]
    )

    result = _calculate_market_stats(frame)

    assert result["up_count"] == 1
    assert result["down_count"] == 0
    assert result["flat_count"] == 0
    assert result["limit_up_count"] == 0
    assert result["limit_down_count"] == 0
    assert result["total_amount"] == np.float64(3.0)


def test_helper_preserves_limit_price_rounding_tolerance() -> None:
    frame = pd.DataFrame(
        [{"ts_code": "600000.SH", "name": "Main", "close": 11.011, "pre_close": 10.01, "amount": 1e8}]
    )

    result = _calculate_market_stats(frame)

    assert result["limit_up_count"] == 1
    assert result["up_count"] == 1


def test_helper_assumes_provider_supplies_the_a_share_universe() -> None:
    frame = pd.DataFrame(
        [{"ts_code": "UNCLASSIFIED", "name": "Other", "close": 11, "pre_close": 10, "amount": 1e8}]
    )

    result = _calculate_market_stats(frame)

    assert result["up_count"] == 1
    assert result["limit_up_count"] == 1


def test_akshare_facade_keeps_fetch_order_lineage_and_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    lineage: list[dict[str, str]] = []
    fake_akshare = types.ModuleType("akshare")
    fake_akshare.stock_zh_a_spot_em = lambda: calls.append("eastmoney") or _representative_frame()
    fake_akshare.stock_zh_a_spot = lambda: calls.append("sina") or _representative_frame()
    fetcher = AkshareFetcher.__new__(AkshareFetcher)
    _configure_fetcher(fetcher)
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    monkeypatch.setattr(akshare_module, "require_uat_provider_dispatch_allowed", lambda **kwargs: lineage.append(kwargs))

    result = fetcher.get_market_stats()

    assert result is not None
    assert result["up_count"] == 4
    assert calls == ["eastmoney"]
    assert lineage == [
        {"provider": "akshare", "capability": "market_stats", "route": "AkshareFetcher.get_market_stats"}
    ]

    index_rows = _fetch_main_indices(
        "akshare",
        _index_frame("akshare", _index_rows()),
        monkeypatch,
    )
    _assert_index_rows(index_rows, default_source="akshare_sina")

    malformed_rows = _index_rows()
    malformed_rows[0] = {"current": "bad", "change": "bad", "change_pct": "bad"}
    malformed = _fetch_main_indices(
        "akshare",
        _index_frame("akshare", malformed_rows),
        monkeypatch,
    )
    assert malformed is not None
    assert (malformed[0]["current"], malformed[0]["change"], malformed[0]["change_pct"]) == (None, None, None)
    assert not _fetch_main_indices("akshare", pd.DataFrame(), monkeypatch)


def test_efinance_facade_keeps_fetch_cache_boundary_and_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    fetcher = EfinanceFetcher(
        transport=lambda operation, *_args, **_kwargs: (
            calls.append(operation) or _representative_frame()
        )
    )

    result = fetcher.get_market_stats()

    assert result is not None
    assert result["down_count"] == 2
    assert calls == ["stock.get_realtime_quotes"]
    assert fetcher._realtime_cache_state["data"] is not None

    index_rows = _fetch_main_indices(
        "efinance",
        _index_frame("efinance", _index_rows()),
        monkeypatch,
    )
    _assert_index_rows(index_rows, default_source="efinance")

    malformed_rows = _index_rows()
    malformed_rows[0] = {"current": "bad", "change": "bad", "change_pct": "bad"}
    malformed = _fetch_main_indices(
        "efinance",
        _index_frame("efinance", malformed_rows),
        monkeypatch,
    )
    assert malformed is not None
    assert (malformed[0]["current"], malformed[0]["change"], malformed[0]["change_pct"]) == (None, None, None)
    assert not _fetch_main_indices("efinance", pd.DataFrame(), monkeypatch)


def test_tushare_facade_keeps_fetch_scope_lineage_and_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    lineage: list[dict[str, object]] = []
    api = object()
    fetcher = TushareFetcher(api=api)
    fetcher._get_china_now = lambda: datetime(2026, 7, 15, 10, 0)
    fetcher._get_trade_dates = lambda _date: ["20260715"]
    fetcher._call_api_with_rate_limit = (
        lambda api_name, **kwargs: calls.append((api_name, kwargs)) or _representative_frame()
    )
    monkeypatch.setattr(tushare_module, "require_uat_provider_transport_allowed", lambda **kwargs: lineage.append(kwargs))

    result = fetcher.get_market_stats()

    assert result is not None
    assert result["flat_count"] == 1
    assert calls == [("rt_k", {"ts_code": "3*.SZ,6*.SH,0*.SZ,92*.BJ"})]
    assert lineage == [
        {
            "provider": "tushare",
            "capability": "market_stats",
            "route": "TushareFetcher.get_market_stats",
            "injected_transport": api,
        }
    ]


@pytest.mark.parametrize("provider", ("akshare", "efinance", "tushare"))
def test_provider_facades_keep_unavailable_snapshots_distinct_from_numeric_zero(
    provider: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = pd.DataFrame(columns=["ts_code", "name", "close", "pre_close", "amount"])
    if provider == "akshare":
        fake_module = types.ModuleType("akshare")
        fake_module.stock_zh_a_spot_em = lambda: empty
        fake_module.stock_zh_a_spot = lambda: empty
        fetcher = AkshareFetcher.__new__(AkshareFetcher)
        _configure_fetcher(fetcher)
        monkeypatch.setitem(sys.modules, "akshare", fake_module)
        monkeypatch.setattr(akshare_module, "require_uat_provider_dispatch_allowed", lambda **_kwargs: None)
    elif provider == "efinance":
        fetcher = EfinanceFetcher(transport=lambda *_args, **_kwargs: empty)
    else:
        fetcher = TushareFetcher(api=object())
        fetcher._get_china_now = lambda: datetime(2026, 7, 15, 10, 0)
        fetcher._get_trade_dates = lambda _date: ["20260715"]
        fetcher._call_api_with_rate_limit = lambda _api_name, **_kwargs: empty

    assert fetcher.get_market_stats() is None


@pytest.mark.parametrize(
    ("provider", "configure"),
    [
        ("akshare", lambda module: setattr(module, "stock_zh_a_spot_em", lambda: (_ for _ in ()).throw(RuntimeError("fail")))),
        ("efinance", lambda module: setattr(module.stock, "get_realtime_quotes", lambda: (_ for _ in ()).throw(RuntimeError("fail")))),
        ("tushare", lambda _module: None),
    ],
)
def test_provider_facades_keep_provider_errors_unavailable(
    provider: str,
    configure: Callable[[types.ModuleType], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if provider == "akshare":
        fake_module = types.ModuleType("akshare")
        fake_module.stock_zh_a_spot = lambda: (_ for _ in ()).throw(RuntimeError("fail"))
        configure(fake_module)
        fetcher = AkshareFetcher.__new__(AkshareFetcher)
        _configure_fetcher(fetcher)
        monkeypatch.setitem(sys.modules, "akshare", fake_module)
        monkeypatch.setattr(akshare_module, "require_uat_provider_dispatch_allowed", lambda **_kwargs: None)
    elif provider == "efinance":
        fake_module = types.ModuleType("efinance")
        fake_module.stock = types.SimpleNamespace()
        configure(fake_module)
        fetcher = EfinanceFetcher(
            transport=lambda *_args, **_kwargs: fake_module.stock.get_realtime_quotes()
        )
    else:
        fetcher = TushareFetcher(api=object())
        fetcher._get_china_now = lambda: datetime(2026, 7, 15, 10, 0)
        fetcher._get_trade_dates = lambda _date: ["20260715"]
        fetcher._call_api_with_rate_limit = lambda _api_name, **_kwargs: (_ for _ in ()).throw(RuntimeError("fail"))

    assert fetcher.get_market_stats() is None


def test_helper_has_no_provider_selection_network_cache_or_retry_imports() -> None:
    assert HELPER_PATH.exists(), "provider-local market-stats helper missing"
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"), filename=str(HELPER_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden_prefixes = (
        "api",
        "data_provider.base",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "tenacity",
        "src.config",
        "src.services.market_cache",
        "src.services.uat_provider_isolation",
    )
    assert not {name for name in imported if name.startswith(forbidden_prefixes)}


_INDEX_SPECS = (
    ("sh000001", "000001", "上证指数"),
    ("sz399001", "399001", "深证成指"),
    ("sz399006", "399006", "创业板指"),
    ("sh000688", "000688", "科创50"),
    ("sh000016", "000016", "上证50"),
    ("sh000300", "000300", "沪深300"),
)

_INDEX_METADATA = {
    "source": "cached_fixture",
    "observedAt": "2026-07-16T09:30:01+08:00",
    "asOf": "2026-07-16T09:30:00+08:00",
    "freshness": "cached",
    "providerStatus": "partial",
    "coverage": {"price": "available", "change": "partial"},
    "isPartial": True,
    "isProxy": True,
    "isSynthetic": False,
}


def _index_rows() -> list[dict[str, object]]:
    rows = [
        {"current": 101.0, "change": 1.0, "change_pct": 1.0},
        {"current": 99.0, "change": -1.0, "change_pct": -1.0},
        {"current": None, "change": 1.0, "change_pct": 1.0},
        {"current": 100.0, "change": None, "change_pct": 1.0},
        {"current": 100.0, "change": 0.0, "change_pct": None},
        {"current": 0.0, "change": 0.0, "change_pct": 0.0},
    ]
    rows[0].update(_INDEX_METADATA)
    return rows


def _index_frame(provider: str, rows: list[dict[str, object]]) -> pd.DataFrame:
    records = []
    for (sina_code, code, _name), row in zip(_INDEX_SPECS, rows):
        if provider == "akshare":
            record = {
                "代码": sina_code,
                "最新价": row.get("current"),
                "涨跌额": row.get("change"),
                "涨跌幅": row.get("change_pct"),
                "今开": 100.0,
                "最高": 102.0,
                "最低": 99.0,
                "昨收": 100.0,
                "成交量": 1000.0,
                "成交额": 1e8,
            }
        else:
            record = {
                "股票代码": code,
                "最新价": row.get("current"),
                "涨跌额": row.get("change"),
                "涨跌幅": row.get("change_pct"),
                "开盘": 100.0,
                "最高": 102.0,
                "最低": 99.0,
                "成交量": 1000.0,
                "成交额": 1e8,
                "振幅": 3.0,
            }
        record.update({key: value for key, value in row.items() if key in _INDEX_METADATA})
        records.append(record)
    return pd.DataFrame(records)


def _fetch_main_indices(
    provider: str,
    frame: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, object]] | None:
    if provider == "akshare":
        fake_module = types.ModuleType("akshare")
        fake_module.stock_zh_index_spot_sina = lambda: frame
        fetcher = AkshareFetcher.__new__(AkshareFetcher)
        _configure_fetcher(fetcher)
        monkeypatch.setitem(sys.modules, "akshare", fake_module)
        monkeypatch.setattr(
            akshare_module,
            "require_uat_provider_dispatch_allowed",
            lambda **_kwargs: None,
        )
    else:
        fetcher = EfinanceFetcher(
            transport=lambda _operation, *_args, **_kwargs: frame,
        )
    return fetcher.get_main_indices(region="cn")


def _assert_index_rows(
    result: list[dict[str, object]] | None,
    *,
    default_source: str,
) -> None:
    assert result is not None
    assert len(result) == 6
    assert (result[0]["current"], result[0]["change"], result[0]["change_pct"]) == (101.0, 1.0, 1.0)
    assert (result[1]["current"], result[1]["change"], result[1]["change_pct"]) == (99.0, -1.0, -1.0)
    assert result[0]["source"] == "cached_fixture"
    assert result[0]["observed_at"] == _INDEX_METADATA["observedAt"]
    assert result[0]["as_of"] == _INDEX_METADATA["asOf"]
    assert result[0]["freshness"] == "cached"
    assert result[0]["provider_status"] == "partial"
    assert result[0]["coverage"] == _INDEX_METADATA["coverage"]
    assert result[0]["is_partial"] is True
    assert result[0]["is_proxy"] is True
    assert result[0]["is_synthetic"] is False
    assert result[2]["current"] is None
    assert result[2]["source"] == default_source
    assert result[3]["change"] is None
    assert result[4]["change_pct"] is None
    assert (result[5]["current"], result[5]["change"], result[5]["change_pct"]) == (0.0, 0.0, 0.0)
