#!/usr/bin/env python3
"""Read-only combined local data-chain operator verifier."""

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

from src.services.historical_ohlcv_cache_preflight import sanitize_historical_ohlcv_preflight_payload
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvReadinessRequest,
    HistoricalOhlcvReadinessService,
    build_backtest_historical_ohlcv_readiness,
)
from src.services.local_quote_snapshot_provider import LocalQuoteSnapshotJsonProvider
from src.services.quote_snapshot_readiness import QuoteSnapshotReadinessRequest, QuoteSnapshotReadinessService
from src.services.scanner_ohlcv_readiness import summarize_scanner_ohlcv_readiness
from src.services.scanner_universe_readiness import build_scanner_universe_readiness_from_coverage
from src.services.starter_market_data import STARTER_MARKET_DATA_SYMBOLS
from src.services.yfinance_us_ohlcv_cache_provider import YfinanceUsOhlcvCacheProvider


CONTRACT_VERSION = "data_chain_operator_verifier_v1"
DEFAULT_US_SYMBOLS = STARTER_MARKET_DATA_SYMBOLS
SCANNER_BLOCKING_FAMILIES = ("historical_ohlcv", "adjusted_prices", "quote_snapshot")


class ExplicitLocalUsOhlcvParquetCache:
    """Read-only OHLCV parquet cache adapter for an explicit operator path."""

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir).expanduser()

    def load(
        self,
        symbol: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int | None = None,
    ) -> pd.DataFrame | None:
        path = self.cache_dir / f"{str(symbol or '').strip().upper()}.parquet"
        try:
            frame = pd.read_parquet(path)
        except Exception:
            return None
        normalized = _normalize_ohlcv_frame(frame)
        if normalized is None or normalized.empty:
            return None
        filtered = normalized.copy()
        if start_date:
            filtered = filtered[filtered["date"] >= pd.to_datetime(start_date)]
        if end_date:
            filtered = filtered[filtered["date"] <= pd.to_datetime(end_date)]
        if days:
            filtered = filtered.tail(max(1, int(days)))
        if filtered.empty:
            return None
        return filtered.reset_index(drop=True)

    def save(self, symbol: str, frame: pd.DataFrame) -> int:
        raise RuntimeError("data_chain_operator_verifier is read-only")


def build_data_chain_verifier_payload(
    *,
    us_symbols: Sequence[str] | None = None,
    ohlcv_cache_dir: str | Path | None,
    quote_cache_path: str | Path | None,
    required_bars: int = 60,
    benchmark_symbol: str = "SPY",
    requested_symbol: str = "AAPL",
    max_age_seconds: int = 60 * 60 * 24,
) -> dict[str, Any]:
    symbols = _normalize_symbols(us_symbols)
    required = max(1, int(required_bars or 60))
    benchmark = _normalize_symbol(benchmark_symbol) or "SPY"
    requested = _normalize_symbol(requested_symbol) or (symbols[0] if symbols else "AAPL")
    base = _base_payload(
        symbols=symbols,
        required_bars=required,
        benchmark_symbol=benchmark,
        requested_symbol=requested,
        max_age_seconds=max(1, int(max_age_seconds or 1)),
    )

    validation_errors = _validate_inputs(
        ohlcv_cache_dir=ohlcv_cache_dir,
        quote_cache_path=quote_cache_path,
        symbols=symbols,
        requested_symbol=requested,
        benchmark_symbol=benchmark,
    )
    if validation_errors:
        payload = {
            **base,
            "status": "failed_closed",
            "reason": "invalid_inputs",
            "inputErrors": validation_errors,
            "historicalOhlcv": {},
            "quoteSnapshot": {},
            "backtestReadiness": {},
            "scannerReadiness": {},
            "availableDataClasses": [],
            "missingDataFamilies": ["historical_ohlcv", "quote_snapshot"],
            "blockedProductSurfaces": ["Scanner", "Backtest"],
            "nextOperatorAction": "Provide readable local OHLCV parquet and quote snapshot JSON paths, then rerun the verifier.",
        }
        return _sanitize(payload)

    cache = ExplicitLocalUsOhlcvParquetCache(Path(str(ohlcv_cache_dir)).expanduser())
    ohlcv_provider = YfinanceUsOhlcvCacheProvider(
        cache=cache,
        provider_fetch_enabled=False,
    )
    ohlcv_service = HistoricalOhlcvReadinessService(provider=ohlcv_provider)
    quote_service = QuoteSnapshotReadinessService(
        provider=LocalQuoteSnapshotJsonProvider(cache_path=quote_cache_path)
    )

    historical_readiness = _historical_readiness_by_symbol(
        service=ohlcv_service,
        symbols=symbols,
        required_bars=required,
    )
    historical = _historical_summary(
        readiness_by_symbol=historical_readiness,
        requested_symbols=symbols,
        required_bars=required,
    )
    quote = dict(
        quote_service.fetch(
            QuoteSnapshotReadinessRequest(
                symbols=tuple(symbols),
                market="us",
                max_age_seconds=max(1, int(max_age_seconds or 1)),
            )
        ).readiness
    )
    quote_coverage = _quote_coverage_state(quote, symbols)
    scanner = _scanner_readiness(
        historical_readiness=historical_readiness,
        historical=historical,
        quote=quote,
        quote_coverage=quote_coverage,
        symbols=symbols,
        required_bars=required,
    )
    backtest = _backtest_readiness(
        service=ohlcv_service,
        requested_symbol=requested,
        benchmark_symbol=benchmark,
        required_bars=required,
    )
    available_classes = _available_data_classes(
        historical=historical,
        quote_coverage=quote_coverage,
        backtest=backtest,
        scanner=scanner,
    )
    missing_families = _missing_data_families(
        historical=historical,
        quote_coverage=quote_coverage,
        backtest=backtest,
        scanner=scanner,
    )
    blocked_surfaces = _blocked_product_surfaces(
        missing_families=missing_families,
        backtest=backtest,
        scanner=scanner,
    )
    status = "ok" if not missing_families else "partial"
    payload = {
        **base,
        "status": status,
        "historicalOhlcv": historical,
        "quoteSnapshot": quote,
        "backtestReadiness": {
            "requestedSymbol": requested,
            "benchmarkSymbol": benchmark,
            "data110": backtest,
        },
        "scannerReadiness": scanner,
        "availableDataClasses": available_classes,
        "missingDataFamilies": missing_families,
        "blockedProductSurfaces": blocked_surfaces,
        "nextOperatorAction": _next_operator_action(
            status=status,
            missing_families=missing_families,
            historical=historical,
            quote=quote,
            backtest=backtest,
            scanner=scanner,
        ),
    }
    return _sanitize(payload)


def _base_payload(
    *,
    symbols: Sequence[str],
    required_bars: int,
    benchmark_symbol: str,
    requested_symbol: str,
    max_age_seconds: int,
) -> dict[str, Any]:
    return {
        "contractVersion": CONTRACT_VERSION,
        "status": "failed_closed",
        "consumerSafe": True,
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "providerCallsEnabled": False,
        "seedExecutionEnabled": False,
        "symbols": list(symbols),
        "requiredBars": required_bars,
        "benchmarkSymbol": benchmark_symbol,
        "requestedSymbol": requested_symbol,
        "maxAgeSeconds": max_age_seconds,
    }


def _validate_inputs(
    *,
    ohlcv_cache_dir: str | Path | None,
    quote_cache_path: str | Path | None,
    symbols: Sequence[str],
    requested_symbol: str,
    benchmark_symbol: str,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    ohlcv_path = Path(str(ohlcv_cache_dir or "")).expanduser()
    quote_path = Path(str(quote_cache_path or "")).expanduser()
    if not str(ohlcv_cache_dir or "").strip() or not ohlcv_path.is_dir():
        errors.append({"field": "ohlcvCacheDir", "code": "unreadable_or_missing"})
    if not str(quote_cache_path or "").strip() or not quote_path.is_file():
        errors.append({"field": "quoteCachePath", "code": "unreadable_or_missing"})
    elif not _quote_json_shape_is_valid(quote_path):
        errors.append({"field": "quoteCachePath", "code": "malformed_json"})
    if not symbols:
        errors.append({"field": "usSymbols", "code": "empty_or_invalid"})
    if requested_symbol and requested_symbol not in set(symbols):
        errors.append({"field": "requestedSymbol", "code": "outside_bounded_universe"})
    if benchmark_symbol and benchmark_symbol not in set(symbols):
        errors.append({"field": "benchmarkSymbol", "code": "outside_bounded_universe"})
    return errors


def _quote_json_shape_is_valid(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    rows = payload.get("quotes") if isinstance(payload, Mapping) else payload
    return isinstance(rows, list)


def _historical_readiness_by_symbol(
    *,
    service: HistoricalOhlcvReadinessService,
    symbols: Sequence[str],
    required_bars: int,
) -> dict[str, dict[str, Any]]:
    return {
        symbol: service.fetch(
            HistoricalOhlcvReadinessRequest(
                symbol=symbol,
                market="us",
                timeframe="1d",
                required_bars=required_bars,
                lookback_bars=required_bars,
                require_adjusted=True,
            )
        ).readiness
        for symbol in symbols
    }


def _historical_summary(
    *,
    readiness_by_symbol: Mapping[str, Mapping[str, Any]],
    requested_symbols: Sequence[str],
    required_bars: int,
) -> dict[str, Any]:
    available_symbols: list[str] = []
    adjusted_symbols: list[str] = []
    missing_symbols: list[str] = []
    insufficient_symbols: list[str] = []
    missing_adjusted_symbols: list[str] = []
    symbol_rows: list[dict[str, Any]] = []

    for symbol in requested_symbols:
        readiness = dict(readiness_by_symbol.get(symbol) or {})
        provider_available = readiness.get("providerState") == "available"
        usable_bars = _safe_int(readiness.get("usableBars"))
        enough_bars = provider_available and usable_bars >= required_bars and _safe_int(readiness.get("missingBars")) == 0
        adjusted_available = readiness.get("adjustmentState") == "available"
        if enough_bars:
            available_symbols.append(symbol)
        elif provider_available:
            insufficient_symbols.append(symbol)
        else:
            missing_symbols.append(symbol)
        if enough_bars and adjusted_available:
            adjusted_symbols.append(symbol)
        elif enough_bars:
            missing_adjusted_symbols.append(symbol)
        symbol_rows.append(
            {
                "symbol": symbol,
                "providerState": readiness.get("providerState"),
                "overallState": readiness.get("overallState"),
                "usableBars": usable_bars,
                "missingBars": _safe_int(readiness.get("missingBars")),
                "adjustmentState": readiness.get("adjustmentState"),
                "freshnessState": readiness.get("freshnessState"),
                "missingRequirements": list(readiness.get("missingRequirements") or []),
            }
        )

    coverage_state = (
        "available"
        if len(available_symbols) == len(requested_symbols)
        else "partial"
        if available_symbols or insufficient_symbols
        else "missing"
    )
    adjusted_state = (
        "available"
        if len(adjusted_symbols) == len(requested_symbols)
        else "missing"
        if missing_adjusted_symbols or available_symbols
        else "unknown"
    )
    return {
        "coverageState": coverage_state,
        "adjustedCoverageState": adjusted_state,
        "requiredBars": required_bars,
        "requestedSymbols": list(requested_symbols),
        "availableSymbols": available_symbols,
        "adjustedSymbols": adjusted_symbols,
        "missingSymbols": missing_symbols,
        "insufficientSymbols": insufficient_symbols,
        "missingAdjustedSymbols": missing_adjusted_symbols,
        "symbols": symbol_rows,
        "consumerSafe": True,
    }


def _scanner_readiness(
    *,
    historical_readiness: Mapping[str, Mapping[str, Any]],
    historical: Mapping[str, Any],
    quote: Mapping[str, Any],
    quote_coverage: str,
    symbols: Sequence[str],
    required_bars: int,
) -> dict[str, Any]:
    scanner_summary = summarize_scanner_ohlcv_readiness(
        market="us",
        profile="combined_operator_verifier",
        diagnostics={
            "candidate_diagnostics": {
                symbol: {"historicalOhlcvReadiness": readiness}
                for symbol, readiness in historical_readiness.items()
            }
        },
        candidates=[],
    )
    missing_families = _scanner_missing_families(
        historical=historical,
        quote_coverage=quote_coverage,
    )
    available_symbols = list(historical.get("availableSymbols") or [])
    adjusted_symbols = set(historical.get("adjustedSymbols") or [])
    quote_symbols = set(quote.get("availableSymbols") or [])
    eligible_symbols = [
        symbol for symbol in symbols if symbol in available_symbols and symbol in adjusted_symbols and symbol in quote_symbols
    ]
    blocked_symbols = [symbol for symbol in symbols if symbol not in eligible_symbols]
    scanner_universe = build_scanner_universe_readiness_from_coverage(
        market="us",
        universe_status="available",
        universe_size=len(symbols),
        last_updated_at=None,
        freshness_state=str(quote.get("freshnessState") or "operator_verifier"),
        quote_coverage=quote_coverage,
        history_coverage="available" if historical.get("coverageState") == "available" else "partial",
        blocked=bool(missing_families),
        historical_requirements=list(scanner_summary.get("missingRequirements") or []),
        seeded_symbols=available_symbols,
        eligible_symbols=eligible_symbols,
        blocked_symbols=blocked_symbols,
        missing_data_families=missing_families,
        operator_next_action=_scanner_next_action(missing_families, required_bars=required_bars),
    )
    return {
        "historicalOhlcvSummary": scanner_summary,
        "quoteSnapshotReadiness": dict(quote),
        "scannerUniverseReadiness": scanner_universe,
        "cacheBackedSymbolCount": len(available_symbols),
        "eligibleSymbolCount": len(eligible_symbols),
        "candidateGenerationExecuted": False,
        "consumerSafe": True,
    }


def _backtest_readiness(
    *,
    service: HistoricalOhlcvReadinessService,
    requested_symbol: str,
    benchmark_symbol: str,
    required_bars: int,
) -> dict[str, Any]:
    result = service.fetch(
        HistoricalOhlcvReadinessRequest(
            symbol=requested_symbol,
            market="us",
            timeframe="1d",
            required_bars=required_bars,
            lookback_bars=required_bars,
            require_adjusted=True,
            benchmark_symbol=benchmark_symbol,
            benchmark_required=True,
        )
    )
    return build_backtest_historical_ohlcv_readiness(result.readiness)


def _available_data_classes(
    *,
    historical: Mapping[str, Any],
    quote_coverage: str,
    backtest: Mapping[str, Any],
    scanner: Mapping[str, Any],
) -> list[str]:
    values: list[str] = []
    if historical.get("coverageState") == "available":
        values.append("historical_ohlcv")
    if historical.get("adjustedCoverageState") == "available":
        values.append("adjusted_prices")
    if quote_coverage == "available":
        values.append("quote_snapshot")
    if backtest.get("executable") is True:
        values.append("backtest_data110")
    universe = (scanner.get("scannerUniverseReadiness") or {}) if isinstance(scanner, Mapping) else {}
    if universe.get("status") == "available":
        values.append("scanner_universe")
    return values


def _missing_data_families(
    *,
    historical: Mapping[str, Any],
    quote_coverage: str,
    backtest: Mapping[str, Any],
    scanner: Mapping[str, Any],
) -> list[str]:
    families: list[str] = []

    def add(value: str) -> None:
        if value not in families:
            families.append(value)

    if historical.get("coverageState") != "available":
        add("historical_ohlcv")
    if historical.get("coverageState") == "available" and historical.get("adjustedCoverageState") != "available":
        add("adjusted_prices")
    if quote_coverage != "available":
        add("quote_snapshot")
    for value in backtest.get("missingDataFamilies") or []:
        if value in {"historical_ohlcv", "adjusted_prices", "benchmark_ohlcv"}:
            add("historical_ohlcv" if value == "benchmark_ohlcv" else value)
    universe = (scanner.get("scannerUniverseReadiness") or {}) if isinstance(scanner, Mapping) else {}
    for value in universe.get("missingDataFamilies") or []:
        if value in SCANNER_BLOCKING_FAMILIES:
            add(value)
    return families


def _blocked_product_surfaces(
    *,
    missing_families: Sequence[str],
    backtest: Mapping[str, Any],
    scanner: Mapping[str, Any],
) -> list[str]:
    blocked: list[str] = []
    universe = (scanner.get("scannerUniverseReadiness") or {}) if isinstance(scanner, Mapping) else {}
    if universe.get("status") != "available":
        blocked.append("Scanner")
    if backtest.get("executable") is not True:
        blocked.append("Backtest")
    if "historical_ohlcv" in set(missing_families) and "DATA-110" not in blocked:
        blocked.append("DATA-110")
    return blocked


def _scanner_missing_families(*, historical: Mapping[str, Any], quote_coverage: str) -> list[str]:
    families: list[str] = []
    if historical.get("coverageState") != "available":
        families.append("historical_ohlcv")
    if historical.get("coverageState") == "available" and historical.get("adjustedCoverageState") != "available":
        families.append("adjusted_prices")
    if quote_coverage != "available":
        families.append("quote_snapshot")
    return families


def _quote_coverage_state(quote: Mapping[str, Any], symbols: Sequence[str]) -> str:
    available = set(quote.get("availableSymbols") or [])
    requested = set(symbols)
    if requested and available == requested and not quote.get("missingSymbols") and not quote.get("staleSymbols"):
        return "available"
    if available:
        return "partial"
    return "missing"


def _next_operator_action(
    *,
    status: str,
    missing_families: Sequence[str],
    historical: Mapping[str, Any],
    quote: Mapping[str, Any],
    backtest: Mapping[str, Any],
    scanner: Mapping[str, Any],
) -> str:
    if status == "ok":
        return "Local OHLCV, adjusted coverage, quote snapshot, DATA-110, and Scanner readiness are available for the bounded symbols."
    missing = set(missing_families)
    if "historical_ohlcv" in missing:
        return "Seed or refresh local OHLCV parquet rows for the explicitly requested symbols, then rerun the verifier."
    if "adjusted_prices" in missing:
        return "Provide real adjusted OHLCV coverage or adjustment metadata through the existing OHLCV cache workflow, then rerun the verifier."
    if "quote_snapshot" in missing:
        return "Refresh or provide local quote snapshot JSON rows for the explicitly requested symbols, then rerun the verifier."
    return (
        str(backtest.get("nextOperatorAction") or "")
        or str(((scanner.get("scannerUniverseReadiness") or {}).get("nextOperatorAction")) or "")
        or str(quote.get("nextOperatorAction") or "")
        or str(historical.get("nextOperatorAction") or "")
        or "Inspect local data-chain readiness and rerun the verifier."
    )


def _scanner_next_action(missing_families: Sequence[str], *, required_bars: int) -> str:
    missing = set(missing_families)
    if not missing:
        return "Scanner local data-chain readiness is available for the bounded starter symbols; candidate generation was not executed."
    if "historical_ohlcv" in missing:
        return f"Provide at least {required_bars} local OHLCV bars for every bounded Scanner symbol."
    if "adjusted_prices" in missing:
        return "Provide real adjusted prices or adjustment metadata before Scanner candidate generation."
    if "quote_snapshot" in missing:
        return "Provide quote snapshot coverage before Scanner candidate generation."
    return "Inspect missing Scanner local data families before candidate generation."


def _normalize_ohlcv_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return None
    df = frame.copy()
    if "trade_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"trade_date": "date"})
    for candidate in ("adjusted_close", "adjustedClose", "adj_close", "Adj Close", "Adjusted Close"):
        if candidate in df.columns:
            if candidate != "adjusted_close":
                df = df.rename(columns={candidate: "adjusted_close"})
            break
    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return None
    return df.sort_values("date").reset_index(drop=True)


def _normalize_symbols(symbols: Sequence[str] | None) -> list[str]:
    result: list[str] = []
    for value in symbols or DEFAULT_US_SYMBOLS:
        symbol = _normalize_symbol(value)
        if symbol and symbol not in result:
            result.append(symbol)
    if symbols is None:
        return result or list(DEFAULT_US_SYMBOLS)
    return result


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not symbol:
        return ""
    if not all(ch.isalnum() or ch in {".", "-", "_"} for ch in symbol):
        return ""
    return symbol[:16]


def _parse_symbols(value: str | None) -> list[str]:
    return [_normalize_symbol(item) for item in str(value or "").split(",") if _normalize_symbol(item)]


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _sanitize(payload: Mapping[str, Any]) -> dict[str, Any]:
    return sanitize_historical_ohlcv_preflight_payload(dict(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--us-symbols", default=",".join(DEFAULT_US_SYMBOLS))
    parser.add_argument("--ohlcv-cache-dir", required=True)
    parser.add_argument("--quote-cache-path", required=True)
    parser.add_argument("--required-bars", type=int, default=60)
    parser.add_argument("--benchmark-symbol", default="SPY")
    parser.add_argument("--requested-symbol", default="AAPL")
    parser.add_argument("--max-age-seconds", type=int, default=60 * 60 * 24)
    args = parser.parse_args(argv)

    payload = build_data_chain_verifier_payload(
        us_symbols=_parse_symbols(args.us_symbols),
        ohlcv_cache_dir=args.ohlcv_cache_dir,
        quote_cache_path=args.quote_cache_path,
        required_bars=max(1, int(args.required_bars or 60)),
        benchmark_symbol=args.benchmark_symbol,
        requested_symbol=args.requested_symbol,
        max_age_seconds=max(1, int(args.max_age_seconds or 1)),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if payload.get("status") == "failed_closed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
