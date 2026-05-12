# -*- coding: utf-8 -*-
"""Contract tests for the pure Yahoo/yfinance symbol conversion boundary."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from data_provider.yfinance_fetcher import YfinanceFetcher
from src.services.stock_service import StockService
from src.utils.yfinance_symbol import (
    get_us_index_yf_symbol,
    to_yfinance_symbol,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600519", "600519.SS"),
        ("000001", "000001.SZ"),
        ("hk00700", "0700.HK"),
        ("AAPL", "AAPL"),
        ("SPX", "^GSPC"),
        ("512400", "512400.SS"),
        ("920748", "920748.BJ"),
    ],
)
def test_to_yfinance_symbol_preserves_existing_market_parity(raw: str, expected: str) -> None:
    assert to_yfinance_symbol(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SPX", ("^GSPC", "标普500指数")),
        ("DJI", ("^DJI", "道琼斯工业指数")),
        ("NASDAQ", ("^IXIC", "纳斯达克综合指数")),
        ("AAPL", (None, None)),
    ],
)
def test_get_us_index_yf_symbol_matches_expected_aliases(
    raw: str,
    expected: tuple[str | None, str | None],
) -> None:
    assert get_us_index_yf_symbol(raw) == expected


def test_yfinance_fetcher_convert_stock_code_delegates_to_pure_utility(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_to_yfinance_symbol(stock_code: str) -> str:
        calls.append(stock_code)
        return "TEST.SYMBOL"

    monkeypatch.setattr("data_provider.yfinance_fetcher.to_yfinance_symbol", fake_to_yfinance_symbol)

    fetcher = YfinanceFetcher()

    assert fetcher._convert_stock_code("hk00700") == "TEST.SYMBOL"
    assert calls == ["hk00700"]


def test_stock_service_intraday_uses_pure_symbol_utility_without_changing_download_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DummyManager:
        def get_stock_name(self, stock_code: str) -> str:
            return f"NAME-{stock_code}"

    class _DummyYFinanceModule:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def download(self, **kwargs):
            self.calls.append(dict(kwargs))
            return pd.DataFrame(
                {
                    "Open": [10.0],
                    "High": [11.0],
                    "Low": [9.5],
                    "Close": [10.5],
                    "Volume": [1000.0],
                },
                index=pd.DatetimeIndex(["2026-05-12 09:35:00"], name="Datetime"),
            )

    dummy_yf = _DummyYFinanceModule()
    converted_symbols: list[str] = []

    def fake_to_yfinance_symbol(stock_code: str) -> str:
        converted_symbols.append(stock_code)
        return "0700.HK"

    monkeypatch.setitem(sys.modules, "yfinance", dummy_yf)
    monkeypatch.setattr("data_provider.base.DataFetcherManager", _DummyManager)
    monkeypatch.setattr("src.services.stock_service.to_yfinance_symbol", fake_to_yfinance_symbol)

    payload = StockService().get_intraday_data("hk00700", interval="5m", range_period="1d")

    assert converted_symbols == ["hk00700"]
    assert payload["stock_name"] == "NAME-hk00700"
    assert payload["source"] == "yfinance"
    assert len(payload["data"]) == 1
    assert dummy_yf.calls == [
        {
            "tickers": "0700.HK",
            "period": "1d",
            "interval": "5m",
            "progress": False,
            "auto_adjust": True,
            "prepost": True,
            "multi_level_index": True,
        }
    ]


def test_yfinance_symbol_module_stays_runtime_lightweight() -> None:
    script = """
import importlib
import json
import sys

tracked_prefixes = (
    "src.utils.yfinance_symbol",
    "data_provider",
    "pandas",
    "requests",
    "httpx",
)

importlib.import_module("src.utils.yfinance_symbol")
loaded_modules = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in tracked_prefixes)
)
print(json.dumps({"loaded_modules": loaded_modules}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    loaded_modules = set(json.loads(completed.stdout)["loaded_modules"])
    assert "src.utils.yfinance_symbol" in loaded_modules
    assert not any(
        name == "data_provider" or name.startswith("data_provider.")
        for name in loaded_modules
    )
    assert not any(name == "pandas" or name.startswith("pandas.") for name in loaded_modules)
    assert not any(name == "requests" or name.startswith("requests.") for name in loaded_modules)
    assert not any(name == "httpx" or name.startswith("httpx.") for name in loaded_modules)
