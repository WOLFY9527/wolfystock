from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from scripts.market_regime_evidence_verifier import main


START_DATE = date(2026, 1, 2)
SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]


def _write_ohlcv_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for symbol in SYMBOLS:
        rows = []
        for index in range(60):
            close = 100.0 + index
            rows.append(
                {
                    "date": (START_DATE + timedelta(days=index)).isoformat(),
                    "open": close - 0.5,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1_000_000 + index,
                    "adjusted_close": close,
                }
            )
        pd.DataFrame(rows).to_parquet(cache_dir / f"{symbol}.parquet", index=False)


def _write_quote_cache(cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "quotes": [
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
                    for index, symbol in enumerate(SYMBOLS)
                ]
            }
        ),
        encoding="utf-8",
    )


def test_cli_outputs_market_regime_evidence_pack_from_explicit_local_paths(tmp_path: Path, capsys) -> None:
    ohlcv_cache_dir = tmp_path / "us-parquet-cache"
    quote_cache_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv_cache(ohlcv_cache_dir)
    _write_quote_cache(quote_cache_path)

    exit_code = main(
        [
            "--market",
            "US",
            "--symbols",
            ",".join(SYMBOLS),
            "--benchmark-symbol",
            "SPY",
            "--growth-proxy-symbol",
            "QQQ",
            "--required-bars",
            "60",
            "--ohlcv-cache-dir",
            str(ohlcv_cache_dir),
            "--quote-cache-path",
            str(quote_cache_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["contractVersion"] == "market_regime_evidence_pack_v1"
    assert payload["status"] == "ok"
    assert payload["consumerSafe"] is True
    assert payload["evidence"]["historicalOhlcvCoverage"]["requiredBars"] == 60
    assert payload["quoteSnapshotEvidence"]["availableSymbols"] == SYMBOLS
