#!/usr/bin/env python3
"""Read-only local Market Regime read model verifier."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.market_regime_evidence_service import (  # noqa: E402
    DEFAULT_BENCHMARK_SYMBOL,
    DEFAULT_GROWTH_PROXY_SYMBOL,
    DEFAULT_MARKET_REGIME_SYMBOLS,
    DEFAULT_REQUIRED_BARS,
)
from src.services.market_regime_read_model_service import build_market_regime_read_model  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = build_market_regime_read_model(
        market=args.market,
        symbols=_parse_symbols(args.symbols),
        benchmark_symbol=args.benchmark_symbol,
        growth_proxy_symbol=args.growth_proxy_symbol,
        required_bars=args.required_bars,
        ohlcv_cache_dir=args.ohlcv_cache_dir,
        quote_snapshot_cache_path=args.quote_cache_path,
        require_adjusted=not args.no_require_adjusted,
        quote_max_age_seconds=args.quote_max_age_seconds,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("status") in {"ok", "partial"} else 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a read-only Market Regime product read model from local OHLCV parquet and quote snapshot JSON."
    )
    parser.add_argument("--market", default="US")
    parser.add_argument("--symbols", default=",".join(DEFAULT_MARKET_REGIME_SYMBOLS))
    parser.add_argument("--benchmark-symbol", default=DEFAULT_BENCHMARK_SYMBOL)
    parser.add_argument("--growth-proxy-symbol", default=DEFAULT_GROWTH_PROXY_SYMBOL)
    parser.add_argument("--required-bars", type=int, default=DEFAULT_REQUIRED_BARS)
    parser.add_argument("--ohlcv-cache-dir", required=True)
    parser.add_argument("--quote-cache-path")
    parser.add_argument("--quote-max-age-seconds", type=int, default=60 * 60 * 24)
    parser.add_argument("--no-require-adjusted", action="store_true")
    return parser


def _parse_symbols(value: str | None) -> list[str]:
    symbols: list[str] = []
    for item in str(value or "").split(","):
        symbol = item.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


if __name__ == "__main__":
    raise SystemExit(main())
