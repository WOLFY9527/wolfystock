from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.services.market_regime_evidence_service import (
    DEFAULT_MARKET_REGIME_SYMBOLS,
    build_market_regime_evidence_pack,
)


START_DATE = date(2026, 1, 2)
SYMBOLS = list(DEFAULT_MARKET_REGIME_SYMBOLS)


def _series(start: float, step: float, bars: int = 60) -> list[float]:
    return [round(start + (index * step), 4) for index in range(bars)]


def _write_ohlcv(
    cache_dir: Path,
    values_by_symbol: dict[str, list[float]],
    *,
    adjusted_symbols: Iterable[str] | None = None,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    adjusted_set = set(adjusted_symbols if adjusted_symbols is not None else values_by_symbol)
    for symbol, closes in values_by_symbol.items():
        rows = []
        for index, close in enumerate(closes):
            row = {
                "date": (START_DATE + timedelta(days=index)).isoformat(),
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + index,
            }
            if symbol in adjusted_set:
                row["adjusted_close"] = close
            rows.append(row)
        pd.DataFrame(rows).to_parquet(cache_dir / f"{symbol}.parquet", index=False)


def _write_quote_cache(cache_path: Path, symbols: Iterable[str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "symbol": symbol,
            "market": "us",
            "last": 100.0 + index,
            "previousClose": 99.5 + index,
            "volume": 1_000_000 + index,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "source": "local_quote_snapshot_cache",
        }
        for index, symbol in enumerate(symbols)
    ]
    cache_path.write_text(json.dumps({"quotes": rows}), encoding="utf-8")


def _full_values() -> dict[str, list[float]]:
    return {
        "SPY": _series(100, 1.0),
        "QQQ": _series(100, 1.25),
        "AAPL": _series(90, 0.9),
        "MSFT": _series(95, 1.1),
    }


def _build_pack(
    tmp_path: Path,
    *,
    values_by_symbol: dict[str, list[float]] | None = None,
    adjusted_symbols: Iterable[str] | None = None,
    quote_symbols: Iterable[str] | None = SYMBOLS,
    requested_symbols: Iterable[str] = SYMBOLS,
    quote_required: bool = True,
) -> dict:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(
        ohlcv_dir,
        values_by_symbol or _full_values(),
        adjusted_symbols=adjusted_symbols,
    )
    if quote_symbols is not None:
        _write_quote_cache(quote_path, quote_symbols)
    return build_market_regime_evidence_pack(
        market="US",
        symbols=list(requested_symbols),
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path if quote_required else None,
        require_adjusted=True,
    )


def test_full_adjusted_ohlcv_and_quote_snapshot_returns_ok_risk_on_confirming(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path)

    assert pack["consumerSafe"] is True
    assert pack["contractVersion"] == "market_regime_evidence_pack_v1"
    assert pack["status"] == "ok"
    assert pack["market"] == "US"
    assert pack["availableDataClasses"] == [
        "historical_ohlcv",
        "adjusted_prices",
        "benchmark_trend",
        "growth_risk_proxy",
        "breadth_proxy",
        "volatility_proxy",
        "quote_snapshot",
    ]
    assert pack["missingDataFamilies"] == []
    assert pack["blockedProductSurfaces"] == []
    assert pack["regimeSummary"]["label"] == "risk_on_confirming"
    assert pack["regimeSummary"]["status"] == "ok"
    assert pack["benchmarkEvidence"]["symbol"] == "SPY"
    assert pack["benchmarkEvidence"]["return20d"] > 0
    assert pack["benchmarkEvidence"]["closeVsMa20"] == "above"
    assert pack["evidence"]["growthRiskProxy"]["relativeReturn20d"] >= 0
    assert pack["evidence"]["breadthProxy"]["percentAboveMa20"] == 1.0
    assert pack["quoteSnapshotEvidence"]["availableSymbols"] == SYMBOLS


def test_ohlcv_present_but_adjusted_missing_blocks_confident_regime(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, adjusted_symbols=[])

    assert pack["status"] == "partial"
    assert "adjusted_prices" in pack["missingDataFamilies"]
    assert pack["regimeSummary"]["label"] == "insufficient_data"
    assert pack["benchmarkEvidence"]["adjustedClose"] is None
    assert set(pack["dataQuality"]["missingAdjustedData"]) == set(SYMBOLS)


def test_benchmark_below_moving_average_and_weak_breadth_returns_risk_off(tmp_path: Path) -> None:
    values = {
        "SPY": _series(160, -1.0),
        "QQQ": _series(160, -1.2),
        "AAPL": _series(150, -0.8),
        "MSFT": _series(155, -0.9),
    }

    pack = _build_pack(tmp_path, values_by_symbol=values)

    assert pack["status"] == "ok"
    assert pack["regimeSummary"]["label"] == "risk_off"
    assert pack["benchmarkEvidence"]["return20d"] < 0
    assert pack["benchmarkEvidence"]["closeVsMa20"] == "below"
    assert pack["evidence"]["breadthProxy"]["percentAboveMa20"] == 0.0


def test_mixed_benchmark_breadth_and_relative_strength_returns_mixed(tmp_path: Path) -> None:
    values = {
        "SPY": _series(100, 1.0),
        "QQQ": _series(100, 0.2),
        "AAPL": _series(150, -0.7),
        "MSFT": _series(95, 0.7),
    }

    pack = _build_pack(tmp_path, values_by_symbol=values)

    assert pack["status"] == "ok"
    assert pack["regimeSummary"]["label"] == "mixed"
    assert pack["benchmarkEvidence"]["return20d"] > 0
    assert pack["evidence"]["growthRiskProxy"]["relativeReturn20d"] < 0


def test_quote_snapshot_missing_when_quote_path_required_reports_quote_snapshot(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, quote_symbols=["SPY", "QQQ", "MSFT"])

    assert pack["status"] == "partial"
    assert "quote_snapshot" in pack["missingDataFamilies"]
    assert pack["regimeSummary"]["label"] == "insufficient_data"
    assert pack["quoteSnapshotEvidence"]["missingSymbols"] == ["AAPL"]
    assert pack["dataQuality"]["missingQuoteSnapshot"] == ["AAPL"]


def test_quote_snapshot_path_is_optional_and_not_required_for_status_ok(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, quote_symbols=None, quote_required=False)

    assert pack["status"] == "ok"
    assert "quote_snapshot" not in pack["missingDataFamilies"]
    assert "quote_snapshot" not in pack["availableDataClasses"]
    assert pack["quoteSnapshotEvidence"]["availabilityState"] == "not_requested"
    assert pack["quoteSnapshotEvidence"]["missingSymbols"] == []


def test_missing_parquet_file_fails_safely_without_raw_stack_trace(tmp_path: Path) -> None:
    values = _full_values()
    values.pop("AAPL")

    pack = _build_pack(tmp_path, values_by_symbol=values)

    assert pack["status"] == "partial"
    assert "historical_ohlcv" in pack["missingDataFamilies"]
    assert pack["symbolEvidence"]["AAPL"]["coverage"]["state"] == "missing"
    serialized = json.dumps(pack, ensure_ascii=False).lower()
    for forbidden in ("traceback", "exception", "filenotfounderror", "rawpayload"):
        assert forbidden not in serialized


def test_requested_symbol_outside_explicit_universe_fails_closed(tmp_path: Path) -> None:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(ohlcv_dir, _full_values())
    _write_quote_cache(quote_path, SYMBOLS)

    pack = build_market_regime_evidence_pack(
        market="US",
        symbols=["SPY", "QQQ", "AAPL", "TSLA"],
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path,
        require_adjusted=True,
        explicit_universe=SYMBOLS,
    )

    assert pack["status"] == "failed_closed"
    assert pack["regimeSummary"]["label"] == "insufficient_data"
    assert pack["missingDataFamilies"] == ["invalid_symbols"]
    assert pack["dataQuality"]["failClosedReasons"] == ["symbol_outside_explicit_universe"]


def test_consumer_safe_output_contains_no_trading_advice_terms(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path)

    serialized = json.dumps(pack, ensure_ascii=False).lower()
    for forbidden in ("buy", "sell", "hold", "recommendation", "target price", "stop loss"):
        assert forbidden not in serialized
