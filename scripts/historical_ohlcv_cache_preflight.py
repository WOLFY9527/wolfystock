#!/usr/bin/env python3
"""Emit historical OHLCV cache preflight or explicit seed JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.historical_ohlcv_cache_preflight import HistoricalOhlcvCachePreflightService


def _parse_symbols(value: str | None) -> list[str]:
    if not value:
        return []
    symbols = []
    for item in value.split(","):
        symbol = str(item or "").strip().upper()
        if symbol:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cn-symbols", default=None, help="Comma-separated CN symbols; defaults to representative set.")
    parser.add_argument("--us-symbols", default=None, help="Comma-separated US symbols; defaults to representative set.")
    parser.add_argument("--required-bars", type=int, default=60)
    parser.add_argument("--no-require-adjusted", action="store_true")
    parser.add_argument("--seed", action="store_true", help="Run the seed control path; defaults to dry-run.")
    parser.add_argument("--execute", action="store_true", help="Execute seed when flags and allowlist permit it.")
    args = parser.parse_args(argv)

    service = HistoricalOhlcvCachePreflightService()
    symbols_by_market = None
    if args.cn_symbols is not None or args.us_symbols is not None:
        symbols_by_market = {
            "cn": _parse_symbols(args.cn_symbols),
            "us": _parse_symbols(args.us_symbols),
        }
    kwargs = {
        "symbols_by_market": symbols_by_market,
        "required_bars": max(1, int(args.required_bars or 60)),
        "require_adjusted": not bool(args.no_require_adjusted),
    }
    if args.seed:
        payload = service.seed(**kwargs, dry_run=not bool(args.execute))
    else:
        payload = service.preflight(**kwargs, dry_run=True)

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
