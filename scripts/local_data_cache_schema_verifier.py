#!/usr/bin/env python3
"""Read-only local OHLCV and quote snapshot cache schema verifier."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.local_quote_snapshot_provider import LocalQuoteSnapshotJsonProvider
from src.services.quote_snapshot_readiness import (
    DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS,
    QuoteSnapshotReadinessRequest,
    QuoteSnapshotReadinessService,
)
from src.services.starter_market_data import STARTER_MARKET_DATA_SYMBOLS


CONTRACT_VERSION = "local_data_cache_schema_verifier_v1"
DEFAULT_US_SYMBOLS = STARTER_MARKET_DATA_SYMBOLS
CANONICAL_ADJUSTED_COLUMN = "adjusted_close"
ADJUSTED_ALIASES = (
    "adjusted_close",
    "adjustedClose",
    "adj_close",
    "Adj Close",
    "Adjusted Close",
)


def build_local_data_cache_schema_payload(
    *,
    us_symbols: Sequence[str] | None,
    ohlcv_cache_dir: str | Path,
    quote_cache_path: str | Path | None = None,
    required_bars: int = 60,
    require_adjusted: bool = False,
    max_age_seconds: int | None = None,
) -> dict[str, Any]:
    symbols = _normalize_symbols(us_symbols)
    required = max(1, int(required_bars or 1))
    cache_dir = Path(str(ohlcv_cache_dir)).expanduser()
    quote_path = Path(str(quote_cache_path)).expanduser() if quote_cache_path else None
    max_age = max(1, int(max_age_seconds or DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS))
    base = _base_payload(symbols=symbols, required_bars=required, require_adjusted=require_adjusted)

    if not _is_readable_dir(cache_dir):
        payload = _fail_closed(
            base,
            reason="ohlcv_cache_dir_unreadable",
            next_action="Provide a readable local OHLCV parquet cache directory, then rerun the verifier.",
        )
        payload["ohlcv"] = _empty_ohlcv_payload(symbols=symbols, required_bars=required, require_adjusted=require_adjusted)
        payload["quoteSnapshotCache"] = _quote_not_requested_payload()
        return payload

    ohlcv = _inspect_ohlcv_cache(
        symbols=symbols,
        cache_dir=cache_dir,
        required_bars=required,
        require_adjusted=require_adjusted,
    )
    base["ohlcv"] = ohlcv

    if quote_path is not None:
        quote = _inspect_quote_cache(symbols=symbols, quote_cache_path=quote_path, max_age_seconds=max_age)
        base["quoteSnapshotCache"] = quote
        if quote.get("failedClosed") is True:
            base["status"] = "failed_closed"
            base["reason"] = "quote_cache_unreadable"
            base["missingRequirements"] = _missing_requirements(ohlcv=ohlcv, quote=quote)
            base["nextOperatorAction"] = (
                "Provide a readable quote snapshot JSON cache with valid rows for the requested symbols, "
                "then rerun the verifier."
            )
            return base
    else:
        quote = _quote_not_requested_payload()
        base["quoteSnapshotCache"] = quote

    missing = _missing_requirements(ohlcv=ohlcv, quote=quote)
    base["missingRequirements"] = missing
    if ohlcv.get("unreadableSymbols"):
        base["status"] = "failed_closed"
        base["reason"] = "ohlcv_parquet_unreadable"
        base["nextOperatorAction"] = (
            "Replace unreadable local OHLCV parquet files with valid cache files, then rerun the verifier."
        )
        return base
    base["status"] = "ok" if not missing else "partial"
    base["nextOperatorAction"] = _next_operator_action(status=base["status"], missing_requirements=missing)
    return base


def _inspect_ohlcv_cache(
    *,
    symbols: Sequence[str],
    cache_dir: Path,
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    by_symbol: dict[str, Any] = {}
    missing_symbols: list[str] = []
    insufficient_symbols: list[str] = []
    missing_adjusted_symbols: list[str] = []
    unreadable_symbols: list[str] = []

    for symbol in symbols:
        file_path = cache_dir / f"{symbol}.parquet"
        row = _inspect_symbol_parquet(
            symbol=symbol,
            file_path=file_path,
            required_bars=required_bars,
            require_adjusted=require_adjusted,
        )
        by_symbol[symbol] = row
        if row["fileExists"] is not True:
            missing_symbols.append(symbol)
        if row["readState"] == "unreadable":
            unreadable_symbols.append(symbol)
        if row["hasRequiredBars"] is not True:
            insufficient_symbols.append(symbol)
        if require_adjusted and row["adjustmentState"] != "available":
            missing_adjusted_symbols.append(symbol)

    return {
        "requiredBars": required_bars,
        "requireAdjusted": bool(require_adjusted),
        "canonicalAdjustedColumn": CANONICAL_ADJUSTED_COLUMN,
        "acceptedAdjustedAliases": list(ADJUSTED_ALIASES),
        "requestedSymbols": list(symbols),
        "missingSymbols": missing_symbols,
        "unreadableSymbols": unreadable_symbols,
        "insufficientBarSymbols": insufficient_symbols,
        "missingAdjustedSymbols": missing_adjusted_symbols,
        "symbols": by_symbol,
    }


def _inspect_symbol_parquet(
    *,
    symbol: str,
    file_path: Path,
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    try:
        exists = file_path.is_file()
    except OSError:
        exists = False
    if not exists:
        return _symbol_payload(
            symbol=symbol,
            file_exists=False,
            row_count=0,
            columns=[],
            adjusted_aliases=[],
            has_required_bars=False,
            adjustment_state="missing" if require_adjusted else "not_required",
            read_state="missing",
        )

    try:
        frame = pd.read_parquet(file_path)
    except Exception:
        return _symbol_payload(
            symbol=symbol,
            file_exists=True,
            row_count=0,
            columns=[],
            adjusted_aliases=[],
            has_required_bars=False,
            adjustment_state="missing" if require_adjusted else "not_required",
            read_state="unreadable",
        )

    columns = [str(column) for column in frame.columns]
    aliases = [alias for alias in ADJUSTED_ALIASES if alias in columns]
    row_count = int(len(frame.index))
    return _symbol_payload(
        symbol=symbol,
        file_exists=True,
        row_count=row_count,
        columns=columns,
        adjusted_aliases=aliases,
        has_required_bars=row_count >= required_bars,
        adjustment_state="available" if aliases else ("missing" if require_adjusted else "not_required"),
        read_state="readable",
    )


def _symbol_payload(
    *,
    symbol: str,
    file_exists: bool,
    row_count: int,
    columns: Sequence[str],
    adjusted_aliases: Sequence[str],
    has_required_bars: bool,
    adjustment_state: str,
    read_state: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "fileExists": bool(file_exists),
        "readState": read_state,
        "rowCount": int(row_count),
        "columns": list(columns),
        "adjustedAliasesPresent": list(adjusted_aliases),
        "canonicalAdjustedColumn": CANONICAL_ADJUSTED_COLUMN,
        "hasRequiredBars": bool(has_required_bars),
        "adjustmentState": adjustment_state,
    }


def _inspect_quote_cache(*, symbols: Sequence[str], quote_cache_path: Path, max_age_seconds: int) -> dict[str, Any]:
    if not _is_readable_file(quote_cache_path):
        return _quote_failed_closed_payload(max_age_seconds=max_age_seconds)

    service = QuoteSnapshotReadinessService(provider=LocalQuoteSnapshotJsonProvider(cache_path=quote_cache_path))
    result = service.fetch(
        QuoteSnapshotReadinessRequest(symbols=tuple(symbols), market="us", max_age_seconds=max_age_seconds)
    )
    readiness = result.readiness
    provider_state = str(readiness.get("providerState") or "")
    if provider_state == "provider_unavailable" and not readiness.get("availableSymbols"):
        return _quote_failed_closed_payload(max_age_seconds=max_age_seconds, readiness=readiness)

    return {
        "pathProvided": True,
        "coverageState": str(readiness.get("availabilityState") or "missing"),
        "required": True,
        "maxAgeSeconds": max_age_seconds,
        "failedClosed": False,
        "readiness": readiness,
    }


def _quote_not_requested_payload() -> dict[str, Any]:
    return {
        "pathProvided": False,
        "coverageState": "not_requested",
        "required": False,
        "failedClosed": False,
        "readiness": None,
    }


def _quote_failed_closed_payload(
    *,
    max_age_seconds: int,
    readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "pathProvided": True,
        "coverageState": "unreadable",
        "required": True,
        "maxAgeSeconds": max_age_seconds,
        "failedClosed": True,
        "readiness": dict(readiness or {}),
    }


def _missing_requirements(*, ohlcv: Mapping[str, Any], quote: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if ohlcv.get("missingSymbols"):
        missing.append("ohlcv_files_missing")
    if ohlcv.get("unreadableSymbols"):
        missing.append("ohlcv_parquet_unreadable")
    if ohlcv.get("insufficientBarSymbols"):
        missing.append("required_bars_missing")
    if ohlcv.get("missingAdjustedSymbols"):
        missing.append("adjusted_prices_missing")
    if quote.get("failedClosed") is True:
        missing.append("quote_snapshot_cache_unreadable")
    elif quote.get("required") and quote.get("coverageState") != "available":
        missing.append("quote_snapshot_missing")
    return missing


def _next_operator_action(*, status: str, missing_requirements: Sequence[str]) -> str:
    if status == "ok":
        return "Local OHLCV bars, adjusted aliases, and requested quote snapshot coverage are available."
    if "adjusted_prices_missing" in missing_requirements:
        return "Refresh or repair local OHLCV parquet files so every requested symbol includes an adjusted close alias."
    if "required_bars_missing" in missing_requirements or "ohlcv_files_missing" in missing_requirements:
        return "Seed or refresh the local OHLCV parquet cache for the requested symbols, then rerun the verifier."
    if "quote_snapshot_missing" in missing_requirements:
        return "Refresh the local quote snapshot cache for the requested symbols, then rerun the verifier."
    return "Review missing requirements, repair the local cache inputs, then rerun the verifier."


def _base_payload(*, symbols: Sequence[str], required_bars: int, require_adjusted: bool) -> dict[str, Any]:
    return {
        "contractVersion": CONTRACT_VERSION,
        "status": "partial",
        "consumerSafe": True,
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "requestedSymbols": list(symbols),
        "requiredBars": required_bars,
        "requireAdjusted": bool(require_adjusted),
        "canonicalAdjustedColumn": CANONICAL_ADJUSTED_COLUMN,
        "missingRequirements": [],
        "nextOperatorAction": "",
    }


def _fail_closed(base: dict[str, Any], *, reason: str, next_action: str) -> dict[str, Any]:
    payload = dict(base)
    payload["status"] = "failed_closed"
    payload["reason"] = reason
    payload["missingRequirements"] = [reason]
    payload["nextOperatorAction"] = next_action
    return payload


def _empty_ohlcv_payload(
    *,
    symbols: Sequence[str],
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    return {
        "requiredBars": required_bars,
        "requireAdjusted": bool(require_adjusted),
        "canonicalAdjustedColumn": CANONICAL_ADJUSTED_COLUMN,
        "acceptedAdjustedAliases": list(ADJUSTED_ALIASES),
        "requestedSymbols": list(symbols),
        "missingSymbols": list(symbols),
        "unreadableSymbols": [],
        "insufficientBarSymbols": list(symbols),
        "missingAdjustedSymbols": list(symbols) if require_adjusted else [],
        "symbols": {},
    }


def _is_readable_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_readable_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _normalize_symbols(symbols: Sequence[str] | None) -> list[str]:
    values = symbols or DEFAULT_US_SYMBOLS
    normalized: list[str] = []
    for value in values:
        symbol = str(value or "").strip().upper()
        if symbol and symbol not in normalized:
            normalized.append(symbol)
    return normalized or list(DEFAULT_US_SYMBOLS)


def _parse_symbols(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--us-symbols", default=",".join(DEFAULT_US_SYMBOLS))
    parser.add_argument("--ohlcv-cache-dir", required=True)
    parser.add_argument("--quote-cache-path", default="")
    parser.add_argument("--required-bars", type=int, default=60)
    parser.add_argument("--require-adjusted", action="store_true")
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS)
    args = parser.parse_args(argv)

    payload = build_local_data_cache_schema_payload(
        us_symbols=_parse_symbols(args.us_symbols),
        ohlcv_cache_dir=args.ohlcv_cache_dir,
        quote_cache_path=args.quote_cache_path.strip() or None,
        required_bars=max(1, int(args.required_bars or 1)),
        require_adjusted=bool(args.require_adjusted),
        max_age_seconds=max(1, int(args.max_age_seconds or 1)),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if payload.get("status") == "failed_closed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
