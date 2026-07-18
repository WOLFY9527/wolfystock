from __future__ import annotations

import pandas as pd
import pytest

from src.services.stock_service import (
    StockService,
    _prepare_intraday_yfinance_request,
)


def test_prepare_intraday_yfinance_request_preserves_symbol_and_download_kwargs() -> None:
    symbol, download_kwargs = _prepare_intraday_yfinance_request(
        "hk00700",
        interval="5m",
        range_period="1d",
    )

    assert symbol == "0700.HK"
    assert download_kwargs == {
        "tickers": "0700.HK",
        "period": "1d",
        "interval": "5m",
        "progress": False,
        "auto_adjust": True,
        "prepost": True,
        "multi_level_index": True,
    }


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"interval": "4m", "range_period": "1d"}, "不支持的 interval 参数: 4m"),
        ({"interval": "5m", "range_period": "2d"}, "不支持的 range 参数: 2d"),
    ],
)
def test_prepare_intraday_yfinance_request_rejects_unsupported_parameters(
    kwargs: dict[str, str],
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _prepare_intraday_yfinance_request("AAPL", **kwargs)


def test_get_intraday_data_uses_prepared_download_kwargs_without_mutation(
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
    prepared_calls: list[tuple[str, str, str]] = []

    def fake_prepare(stock_code: str, interval: str, range_period: str) -> tuple[str, dict[str, object]]:
        prepared_calls.append((stock_code, interval, range_period))
        return (
            "0700.HK",
            {
                "tickers": "0700.HK",
                "period": range_period,
                "interval": interval,
                "progress": False,
                "auto_adjust": True,
                "prepost": True,
                "multi_level_index": True,
            },
        )

    monkeypatch.setattr("src.services.stock_service._prepare_intraday_yfinance_request", fake_prepare)

    payload = StockService(
        provider_manager=_DummyManager(),
        intraday_transport=dummy_yf.download,
    ).get_intraday_data("hk00700", interval="5m", range_period="1d")

    assert prepared_calls == [("hk00700", "5m", "1d")]
    assert payload["stock_name"] == "NAME-hk00700"
    assert payload["source"] == "yfinance"
    assert payload["source_type"] == "unofficial_proxy"
    assert payload["freshness"] == "delayed"
    assert payload["is_fallback"] is False
    assert payload["is_stale"] is False
    assert payload["is_partial"] is False
    assert payload["is_synthetic"] is False
    assert payload["is_unavailable"] is False
    assert payload["sourceConfidence"] == {
        "source": "yfinance",
        "sourceLabel": "Yahoo Finance intraday proxy",
        "asOf": "2026-05-12T09:35:00",
        "freshness": "delayed",
        "isFallback": False,
        "isStale": False,
        "isPartial": False,
        "isSynthetic": False,
        "isUnavailable": False,
        "confidenceWeight": 0.7,
        "coverage": 1.0,
        "degradationReason": "delayed_source",
        "capReason": None,
    }
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
