from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from scripts.local_data_cache_schema_verifier import build_local_data_cache_schema_payload, main


def _write_parquet(cache_dir, symbol: str, rows: int, *, adjusted: bool) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    data = []
    for index in range(rows):
        row = {
            "date": f"2026-01-{(index % 28) + 1:02d}",
            "open": 100.0 + index,
            "high": 101.0 + index,
            "low": 99.0 + index,
            "close": 100.5 + index,
            "volume": 1_000_000 + index,
        }
        if adjusted:
            row["adjusted_close"] = 100.25 + index
        data.append(row)
    pd.DataFrame(data).to_parquet(cache_dir / f"{symbol.upper()}.parquet", index=False)


def _write_quote_cache(path, *symbols: str) -> None:
    path.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": symbol,
                        "market": "us",
                        "last": 500.0 + index,
                        "previousClose": 499.0 + index,
                        "volume": 1000 + index,
                        "asOf": datetime.now(timezone.utc).isoformat(),
                        "currency": "USD",
                        "source": "operator_cache",
                    }
                    for index, symbol in enumerate(symbols)
                ]
            }
        ),
        encoding="utf-8",
    )


def test_ohlcv_parquet_with_adjusted_close_and_required_bars_is_available(tmp_path) -> None:
    cache_dir = tmp_path / "us-parquet-cache"
    _write_parquet(cache_dir, "SPY", 60, adjusted=True)

    payload = build_local_data_cache_schema_payload(
        us_symbols=["SPY"],
        ohlcv_cache_dir=cache_dir,
        required_bars=60,
        require_adjusted=True,
    )

    assert payload["status"] == "ok"
    symbol = payload["ohlcv"]["symbols"]["SPY"]
    assert symbol["fileExists"] is True
    assert symbol["rowCount"] == 60
    assert symbol["adjustedAliasesPresent"] == ["adjusted_close"]
    assert symbol["canonicalAdjustedColumn"] == "adjusted_close"
    assert symbol["hasRequiredBars"] is True
    assert symbol["adjustmentState"] == "available"
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False


def test_ohlcv_parquet_without_adjusted_alias_reports_missing_adjustment(tmp_path) -> None:
    cache_dir = tmp_path / "us-parquet-cache"
    _write_parquet(cache_dir, "QQQ", 60, adjusted=False)

    payload = build_local_data_cache_schema_payload(
        us_symbols=["QQQ"],
        ohlcv_cache_dir=cache_dir,
        required_bars=60,
        require_adjusted=True,
    )

    assert payload["status"] == "partial"
    symbol = payload["ohlcv"]["symbols"]["QQQ"]
    assert symbol["fileExists"] is True
    assert symbol["rowCount"] == 60
    assert symbol["adjustedAliasesPresent"] == []
    assert symbol["adjustmentState"] == "missing"
    assert "adjusted_prices_missing" in payload["missingRequirements"]


def test_missing_parquet_file_reports_partial_with_missing_symbol(tmp_path) -> None:
    cache_dir = tmp_path / "us-parquet-cache"
    cache_dir.mkdir()

    payload = build_local_data_cache_schema_payload(
        us_symbols=["AAPL"],
        ohlcv_cache_dir=cache_dir,
        required_bars=60,
        require_adjusted=True,
    )

    assert payload["status"] == "partial"
    assert payload["ohlcv"]["missingSymbols"] == ["AAPL"]
    assert payload["ohlcv"]["symbols"]["AAPL"]["fileExists"] is False
    assert payload["ohlcv"]["symbols"]["AAPL"]["rowCount"] == 0


def test_unreadable_parquet_file_fails_closed_without_exception_leak(tmp_path) -> None:
    cache_dir = tmp_path / "us-parquet-cache"
    cache_dir.mkdir()
    (cache_dir / "MSFT.parquet").write_text("not parquet", encoding="utf-8")

    payload = build_local_data_cache_schema_payload(
        us_symbols=["MSFT"],
        ohlcv_cache_dir=cache_dir,
        required_bars=60,
        require_adjusted=True,
    )

    assert payload["status"] == "failed_closed"
    assert payload["reason"] == "ohlcv_parquet_unreadable"
    assert payload["ohlcv"]["unreadableSymbols"] == ["MSFT"]
    assert payload["ohlcv"]["symbols"]["MSFT"]["readState"] == "unreadable"
    assert "Traceback" not in json.dumps(payload, ensure_ascii=False)


def test_optional_quote_cache_json_with_all_requested_symbols_is_available(tmp_path) -> None:
    cache_dir = tmp_path / "us-parquet-cache"
    quote_cache = tmp_path / "us-starter-quotes.json"
    _write_parquet(cache_dir, "SPY", 60, adjusted=True)
    _write_parquet(cache_dir, "QQQ", 60, adjusted=True)
    _write_quote_cache(quote_cache, "SPY", "QQQ")

    payload = build_local_data_cache_schema_payload(
        us_symbols=["SPY", "QQQ"],
        ohlcv_cache_dir=cache_dir,
        quote_cache_path=quote_cache,
        required_bars=60,
        require_adjusted=True,
    )

    assert payload["status"] == "ok"
    quote = payload["quoteSnapshotCache"]
    assert quote["pathProvided"] is True
    assert quote["coverageState"] == "available"
    assert quote["readiness"]["requestedSymbols"] == ["SPY", "QQQ"]
    assert quote["readiness"]["availableSymbols"] == ["SPY", "QQQ"]
    assert quote["readiness"]["missingSymbols"] == []


def test_invalid_quote_cache_path_or_malformed_json_fails_closed(tmp_path) -> None:
    cache_dir = tmp_path / "us-parquet-cache"
    _write_parquet(cache_dir, "SPY", 60, adjusted=True)
    malformed = tmp_path / "bad-quotes.json"
    malformed.write_text("{not-json", encoding="utf-8")

    missing_payload = build_local_data_cache_schema_payload(
        us_symbols=["SPY"],
        ohlcv_cache_dir=cache_dir,
        quote_cache_path=tmp_path / "missing.json",
        required_bars=60,
        require_adjusted=True,
    )
    malformed_payload = build_local_data_cache_schema_payload(
        us_symbols=["SPY"],
        ohlcv_cache_dir=cache_dir,
        quote_cache_path=malformed,
        required_bars=60,
        require_adjusted=True,
    )

    assert missing_payload["status"] == "failed_closed"
    assert missing_payload["reason"] == "quote_cache_unreadable"
    assert malformed_payload["status"] == "failed_closed"
    assert malformed_payload["reason"] == "quote_cache_unreadable"
    assert "Traceback" not in json.dumps(malformed_payload, ensure_ascii=False)


def test_cli_outputs_json_and_returns_failed_closed_for_bad_ohlcv_dir(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "--us-symbols",
            "SPY",
            "--ohlcv-cache-dir",
            str(tmp_path / "missing-dir"),
            "--required-bars",
            "60",
            "--require-adjusted",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["status"] == "failed_closed"
    assert payload["reason"] == "ohlcv_cache_dir_unreadable"
    assert payload["consumerSafe"] is True
