from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from src.services.starter_market_data import STARTER_MARKET_DATA_SYMBOLS
from src.services.us_ohlcv_coverage_readiness import (
    US_OHLCV_COVERAGE_READINESS_CONTRACT_VERSION,
    build_us_ohlcv_coverage_readiness,
    resolve_us_ohlcv_coverage_universe,
)


def _frame(rows: int, *, start: date = date(2026, 1, 1)) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": start + timedelta(days=index),
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
                "volume": 1_000_000 + index,
                "adjusted_close": 100.5 + index,
            }
            for index in range(rows)
        ]
    )


def _by_symbol(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["symbol"]): item for item in items}


def test_resolve_us_ohlcv_coverage_universe_keeps_starter_tier_zero_order() -> None:
    universe = resolve_us_ohlcv_coverage_universe(tier="starter")

    assert universe["tier"] == "starter"
    assert universe["symbols"] == list(STARTER_MARKET_DATA_SYMBOLS)
    assert universe["source"] == "starter_market_data_symbols"
    assert universe["configured"] is False
    assert universe["consumerSafe"] is True


def test_resolve_us_ohlcv_coverage_universe_uses_configured_tier_one_without_duplicates() -> None:
    universe = resolve_us_ohlcv_coverage_universe(
        tier="tier1",
        env={"WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS": " nvda, AAPL, not-us!, NVDA, SPY "},
    )

    assert universe["tier"] == "tier1"
    assert universe["source"] == "WOLFYSTOCK_US_OHLCV_TIER1_SYMBOLS"
    assert universe["configured"] is True
    assert universe["symbols"] == ["NVDA", "AAPL", "SPY"]


def test_build_us_ohlcv_coverage_readiness_reports_full_partial_and_missing_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frames = {"SPY": _frame(90), "QQQ": _frame(12)}

    def fake_load(symbol: str, **_: Any) -> SimpleNamespace:
        frame = frames.get(str(symbol).upper())
        if frame is None:
            return SimpleNamespace(status="missing", dataframe=None)
        return SimpleNamespace(status="hit", dataframe=frame)

    monkeypatch.setattr(
        "src.services.us_ohlcv_coverage_readiness.load_local_us_daily_history",
        fake_load,
    )

    payload = build_us_ohlcv_coverage_readiness(
        symbols=["SPY", "QQQ", "AAPL"],
        parquet_dir=tmp_path,
        required_bars=60,
        today=date(2026, 4, 1),
    )

    assert payload["contractVersion"] == US_OHLCV_COVERAGE_READINESS_CONTRACT_VERSION
    assert payload["coverageState"] == "partial"
    assert payload["summary"] == {
        "totalSymbols": 3,
        "readySymbols": 1,
        "partialSymbols": 1,
        "missingSymbols": 1,
        "requiredBars": 60,
    }
    assert payload["source"] == {
        "sourceClass": "local_us_parquet_cache",
        "sourcePath": "configured_parquet_dir",
        "provider": "local_us_parquet",
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }

    by_symbol = _by_symbol(payload["symbols"])
    assert by_symbol["SPY"]["overallState"] == "ready"
    assert by_symbol["SPY"]["usableBars"] == 90
    assert by_symbol["SPY"]["missingBars"] == 0
    assert by_symbol["SPY"]["dateRange"] == {"start": "2026-01-01", "end": "2026-03-31"}
    assert by_symbol["SPY"]["sufficientFor"] == {
        "chart": True,
        "backtest": True,
        "scanner": True,
    }
    assert by_symbol["QQQ"]["overallState"] == "insufficient_history"
    assert by_symbol["QQQ"]["usableBars"] == 12
    assert by_symbol["QQQ"]["missingBars"] == 48
    assert by_symbol["QQQ"]["missingRequirements"] == ["insufficient_history"]
    assert by_symbol["AAPL"]["overallState"] == "missing_cache"
    assert by_symbol["AAPL"]["usableBars"] == 0
    assert by_symbol["AAPL"]["missingRequirements"] == ["missing_cache", "insufficient_history"]
    assert all(item["consumerSafe"] is True for item in payload["symbols"])


def test_build_us_ohlcv_coverage_readiness_reports_not_configured_without_default_path() -> None:
    payload = build_us_ohlcv_coverage_readiness(
        symbols=["SPY"],
        parquet_dir=None,
        required_bars=60,
        env={},
    )

    assert payload["coverageState"] == "not_configured"
    assert payload["summary"]["readySymbols"] == 0
    assert payload["symbols"][0]["overallState"] == "missing_cache"
    assert payload["symbols"][0]["providerState"] == "not_configured"
    assert payload["symbols"][0]["missingRequirements"] == ["missing_cache", "insufficient_history"]
