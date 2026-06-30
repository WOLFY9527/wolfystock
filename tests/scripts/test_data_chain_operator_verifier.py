from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from scripts.data_chain_operator_verifier import build_data_chain_verifier_payload, main


START_DATE = date(2026, 1, 2)
SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]


def _write_ohlcv_cache(
    cache_dir: Path,
    symbols: list[str],
    *,
    bars: int = 60,
    adjusted: bool = True,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        rows = []
        for index in range(bars):
            row = {
                "date": (START_DATE + timedelta(days=index)).isoformat(),
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
                "volume": 1_000_000 + index,
            }
            if adjusted:
                row["adjusted_close"] = 100.25 + index
            rows.append(row)
        pd.DataFrame(rows).to_parquet(cache_dir / f"{symbol}.parquet", index=False)


def _write_quote_cache(cache_path: Path, symbols: list[str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "symbol": symbol,
            "market": "us",
            "last": 100.0 + index,
            "previousClose": 99.0 + index,
            "volume": 1_000_000 + index,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "source": "local_quote_snapshot_cache",
        }
        for index, symbol in enumerate(symbols)
    ]
    cache_path.write_text(json.dumps({"quotes": rows}), encoding="utf-8")


def _build_payload(
    tmp_path: Path,
    *,
    ohlcv_symbols: list[str] | None = None,
    quote_symbols: list[str] | None = None,
    adjusted: bool = True,
) -> dict:
    ohlcv_cache_dir = tmp_path / "us-parquet-cache"
    quote_cache_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    if ohlcv_symbols is not None:
        _write_ohlcv_cache(ohlcv_cache_dir, ohlcv_symbols, adjusted=adjusted)
    if quote_symbols is not None:
        _write_quote_cache(quote_cache_path, quote_symbols)
    return build_data_chain_verifier_payload(
        us_symbols=SYMBOLS,
        ohlcv_cache_dir=ohlcv_cache_dir,
        quote_cache_path=quote_cache_path,
        required_bars=60,
        benchmark_symbol="SPY",
        requested_symbol="AAPL",
        max_age_seconds=86_400,
    )


def test_adjusted_ohlcv_and_quote_snapshot_available_returns_ok(tmp_path: Path) -> None:
    payload = _build_payload(tmp_path, ohlcv_symbols=SYMBOLS, quote_symbols=SYMBOLS)

    assert payload["status"] == "ok"
    assert payload["consumerSafe"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert payload["historicalOhlcv"]["coverageState"] == "available"
    assert payload["historicalOhlcv"]["adjustedCoverageState"] == "available"
    assert payload["quoteSnapshot"]["availabilityState"] == "available"
    assert payload["backtestReadiness"]["data110"]["executable"] is True
    assert payload["scannerReadiness"]["scannerUniverseReadiness"]["status"] == "available"
    assert payload["missingDataFamilies"] == []
    assert payload["blockedProductSurfaces"] == []
    assert set(payload["availableDataClasses"]) >= {
        "historical_ohlcv",
        "adjusted_prices",
        "quote_snapshot",
        "backtest_data110",
    }


def test_ohlcv_present_but_adjusted_missing_reports_adjusted_prices(tmp_path: Path) -> None:
    payload = _build_payload(
        tmp_path,
        ohlcv_symbols=SYMBOLS,
        quote_symbols=SYMBOLS,
        adjusted=False,
    )

    assert payload["status"] == "partial"
    assert payload["historicalOhlcv"]["coverageState"] == "available"
    assert payload["historicalOhlcv"]["adjustedCoverageState"] == "missing"
    assert "adjusted_prices" in payload["missingDataFamilies"]
    assert "historical_ohlcv" not in payload["missingDataFamilies"]
    assert "quote_snapshot" not in payload["missingDataFamilies"]
    assert payload["backtestReadiness"]["data110"]["executable"] is False
    assert "adjusted_prices" in payload["scannerReadiness"]["scannerUniverseReadiness"]["missingDataFamilies"]


def test_adjusted_ohlcv_available_but_quote_missing_reports_quote_snapshot(tmp_path: Path) -> None:
    payload = _build_payload(
        tmp_path,
        ohlcv_symbols=SYMBOLS,
        quote_symbols=["SPY", "QQQ", "MSFT", "NVDA", "TSLA"],
    )

    assert payload["status"] == "partial"
    assert payload["historicalOhlcv"]["adjustedCoverageState"] == "available"
    assert payload["quoteSnapshot"]["availabilityState"] == "partial"
    assert payload["quoteSnapshot"]["missingSymbols"] == ["AAPL"]
    assert "quote_snapshot" in payload["missingDataFamilies"]
    assert "historical_ohlcv" not in payload["missingDataFamilies"]
    assert "adjusted_prices" not in payload["missingDataFamilies"]


def test_ohlcv_missing_reports_historical_ohlcv(tmp_path: Path) -> None:
    payload = _build_payload(
        tmp_path,
        ohlcv_symbols=["SPY", "QQQ", "MSFT", "NVDA", "TSLA"],
        quote_symbols=SYMBOLS,
    )

    assert payload["status"] == "partial"
    assert payload["historicalOhlcv"]["coverageState"] == "partial"
    assert payload["historicalOhlcv"]["missingSymbols"] == ["AAPL"]
    assert "historical_ohlcv" in payload["missingDataFamilies"]
    assert "quote_snapshot" not in payload["missingDataFamilies"]
    assert payload["backtestReadiness"]["data110"]["executable"] is False


def test_invalid_paths_or_malformed_quote_json_fail_closed(tmp_path: Path) -> None:
    missing_payload = build_data_chain_verifier_payload(
        us_symbols=SYMBOLS,
        ohlcv_cache_dir=tmp_path / "missing-cache",
        quote_cache_path=tmp_path / "missing-quotes.json",
        required_bars=60,
        benchmark_symbol="SPY",
        requested_symbol="AAPL",
        max_age_seconds=86_400,
    )
    assert missing_payload["status"] == "failed_closed"
    assert missing_payload["reason"] == "invalid_inputs"
    assert "raw" not in json.dumps(missing_payload, ensure_ascii=False).lower()

    ohlcv_cache_dir = tmp_path / "us-parquet-cache"
    _write_ohlcv_cache(ohlcv_cache_dir, SYMBOLS)
    quote_cache_path = tmp_path / "bad-quotes.json"
    quote_cache_path.write_text("{not valid json", encoding="utf-8")
    malformed_payload = build_data_chain_verifier_payload(
        us_symbols=SYMBOLS,
        ohlcv_cache_dir=ohlcv_cache_dir,
        quote_cache_path=quote_cache_path,
        required_bars=60,
        benchmark_symbol="SPY",
        requested_symbol="AAPL",
        max_age_seconds=86_400,
    )
    assert malformed_payload["status"] == "failed_closed"
    assert malformed_payload["reason"] == "invalid_inputs"
    assert "traceback" not in json.dumps(malformed_payload, ensure_ascii=False).lower()


def test_requested_or_benchmark_symbol_outside_explicit_universe_fails_closed(tmp_path: Path) -> None:
    ohlcv_cache_dir = tmp_path / "us-parquet-cache"
    quote_cache_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv_cache(ohlcv_cache_dir, SYMBOLS)
    _write_quote_cache(quote_cache_path, SYMBOLS)

    payload = build_data_chain_verifier_payload(
        us_symbols=["SPY", "QQQ", "MSFT"],
        ohlcv_cache_dir=ohlcv_cache_dir,
        quote_cache_path=quote_cache_path,
        required_bars=60,
        benchmark_symbol="SPY",
        requested_symbol="AAPL",
        max_age_seconds=86_400,
    )

    assert payload["status"] == "failed_closed"
    assert payload["reason"] == "invalid_inputs"
    assert payload["inputErrors"] == [
        {"field": "requestedSymbol", "code": "outside_bounded_universe"}
    ]


def test_cli_reads_explicit_local_paths_without_mutation(tmp_path: Path, capsys) -> None:
    ohlcv_cache_dir = tmp_path / "us-parquet-cache"
    quote_cache_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv_cache(ohlcv_cache_dir, SYMBOLS)
    _write_quote_cache(quote_cache_path, SYMBOLS)

    exit_code = main(
        [
            "--us-symbols",
            ",".join(SYMBOLS),
            "--ohlcv-cache-dir",
            str(ohlcv_cache_dir),
            "--quote-cache-path",
            str(quote_cache_path),
            "--required-bars",
            "60",
            "--benchmark-symbol",
            "SPY",
            "--requested-symbol",
            "AAPL",
            "--max-age-seconds",
            "86400",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
