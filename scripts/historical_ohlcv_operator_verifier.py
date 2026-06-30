#!/usr/bin/env python3
"""Operator verifier for the explicit historical OHLCV seed path."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.historical_ohlcv_cache_preflight import (
    DEFAULT_US_REPRESENTATIVE_SYMBOLS,
    HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV,
    HistoricalOhlcvCachePreflightService,
    sanitize_historical_ohlcv_preflight_payload,
)
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvReadinessRequest,
    HistoricalOhlcvReadinessService,
    build_backtest_historical_ohlcv_readiness,
)
from src.services.quote_snapshot_readiness import (
    QuoteSnapshotProvider,
    QuoteSnapshotReadinessRequest,
    QuoteSnapshotReadinessService,
)
from src.services.scanner_ohlcv_readiness import summarize_scanner_ohlcv_readiness
from src.services.scanner_universe_readiness import build_scanner_universe_readiness_from_coverage
from src.services.us_history_helper import get_us_stock_parquet_dir
from src.services.yfinance_us_ohlcv_cache_provider import (
    LocalUsOhlcvParquetCache,
    YFINANCE_US_OHLCV_ENABLE_ENV,
    YfinanceUsOhlcvCacheProvider,
)
from src.services.akshare_cn_ohlcv_cache import RUNTIME_ENABLED_ENV as HISTORICAL_RUNTIME_ENABLED_ENV


CONTRACT_VERSION = "historical_ohlcv_operator_verifier_v1"
DEFAULT_VERIFY_SYMBOLS = tuple(DEFAULT_US_REPRESENTATIVE_SYMBOLS)
BACKTEST_SYMBOL = "AAPL"
BACKTEST_BENCHMARK = "SPY"
_TRUTHY = {"1", "true", "yes", "on"}


def build_operator_verifier_payload(
    *,
    mode: str,
    env: Mapping[str, str] | None = None,
    symbols: Sequence[str] | None = None,
    required_bars: int = 60,
    require_adjusted: bool = True,
    execute: bool = False,
    service: HistoricalOhlcvCachePreflightService | None = None,
    readiness_service: HistoricalOhlcvReadinessService | None = None,
    quote_provider: QuoteSnapshotProvider | None = None,
) -> dict[str, Any]:
    env_map = dict(env or os.environ)
    verifier = _Verifier(
        env=env_map,
        symbols=_normalize_symbols(symbols),
        required_bars=max(1, int(required_bars or 60)),
        require_adjusted=bool(require_adjusted),
        service=service,
        readiness_service=readiness_service,
        quote_provider=quote_provider,
    )
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode == "inspect":
        payload = verifier.inspect()
    elif normalized_mode == "dry-run":
        payload = verifier.dry_run()
    elif normalized_mode == "execute":
        payload = verifier.execute(execute=execute)
    elif normalized_mode == "verify-cache":
        payload = verifier.verify_cache()
    elif normalized_mode == "verify-chain":
        payload = verifier.verify_chain()
    else:
        payload = verifier.fail_closed(
            mode=normalized_mode or "unknown",
            reason="unsupported_mode",
            next_action="Choose one of inspect, dry-run, execute, verify-cache, or verify-chain.",
        )
    return sanitize_historical_ohlcv_preflight_payload(payload)


class _Verifier:
    def __init__(
        self,
        *,
        env: Mapping[str, str],
        symbols: Sequence[str],
        required_bars: int,
        require_adjusted: bool,
        service: HistoricalOhlcvCachePreflightService | None,
        readiness_service: HistoricalOhlcvReadinessService | None,
        quote_provider: QuoteSnapshotProvider | None,
    ) -> None:
        self.env = dict(env)
        self.symbols = list(symbols)
        self.required_bars = required_bars
        self.require_adjusted = require_adjusted
        self.service = service or HistoricalOhlcvCachePreflightService(env=self.env)
        self.readiness_service = readiness_service or HistoricalOhlcvReadinessService(
            provider=YfinanceUsOhlcvCacheProvider(
                cache=LocalUsOhlcvParquetCache(),
                provider_fetch_enabled=False,
            )
        )
        self.quote_service = QuoteSnapshotReadinessService(provider=quote_provider)

    def base(self, *, mode: str, status: str, next_action: str) -> dict[str, Any]:
        return {
            "contractVersion": CONTRACT_VERSION,
            "mode": mode,
            "status": status,
            "consumerSafe": True,
            "symbols": list(self.symbols),
            "requiredBars": self.required_bars,
            "requireAdjusted": self.require_adjusted,
            "envGates": self.env_gates(),
            "cacheLocation": self.cache_location_summary(),
            "nextOperatorAction": next_action,
        }

    def inspect(self) -> dict[str, Any]:
        payload = self.base(
            mode="inspect",
            status="ok",
            next_action="Run dry-run first; execute requires explicit --execute plus all listed gates enabled.",
        )
        payload["dependencyState"] = {
            "yfinance": _dependency_state("yfinance"),
            "akshare": _dependency_state("akshare"),
        }
        payload["dryRunCommand"] = (
            "python scripts/historical_ohlcv_operator_verifier.py --mode dry-run "
            "--us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA"
        )
        payload["executeCommandTemplate"] = (
            "python scripts/historical_ohlcv_operator_verifier.py --mode execute --execute "
            "--us-symbols SPY,QQQ,AAPL,MSFT,NVDA,TSLA"
        )
        return payload

    def dry_run(self) -> dict[str, Any]:
        preflight = self.service.seed(
            symbols_by_market={"cn": [], "us": self.symbols},
            required_bars=self.required_bars,
            require_adjusted=self.require_adjusted,
            dry_run=True,
        )
        payload = self.base(
            mode="dry-run",
            status="ok",
            next_action=_next_action_from_preflight(preflight),
        )
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        payload["preflight"] = preflight
        return payload

    def execute(self, *, execute: bool) -> dict[str, Any]:
        missing = self.missing_execute_gates()
        if not execute:
            payload = self.fail_closed(
                mode="execute",
                reason="missing_explicit_execute_flag",
                next_action="Rerun with --mode execute --execute only after dry-run output is reviewed.",
            )
            payload["preflight"] = self.service.preflight(
                symbols_by_market={"cn": [], "us": self.symbols},
                required_bars=self.required_bars,
                require_adjusted=self.require_adjusted,
                dry_run=True,
            )
            return payload
        if missing:
            payload = self.fail_closed(
                mode="execute",
                reason="required_env_gates_disabled",
                next_action="Enable every required env gate, rerun inspect and dry-run, then retry execute.",
            )
            payload["missingRequiredGates"] = missing
            payload["preflight"] = self.service.preflight(
                symbols_by_market={"cn": [], "us": self.symbols},
                required_bars=self.required_bars,
                require_adjusted=self.require_adjusted,
                dry_run=True,
            )
            return payload

        seed = self.service.seed(
            symbols_by_market={"cn": [], "us": self.symbols},
            required_bars=self.required_bars,
            require_adjusted=self.require_adjusted,
            dry_run=False,
        )
        status = "executed" if int((seed.get("summary") or {}).get("totalBarsWritten") or 0) > 0 else "failed_closed"
        payload = self.base(
            mode="execute",
            status=status,
            next_action=_next_action_from_preflight(seed),
        )
        payload["dryRun"] = False
        payload["seed"] = seed
        return payload

    def verify_cache(self) -> dict[str, Any]:
        preflight = self.service.preflight(
            symbols_by_market={"cn": [], "us": self.symbols},
            required_bars=self.required_bars,
            require_adjusted=self.require_adjusted,
            dry_run=True,
        )
        rows = _us_symbol_rows(preflight)
        ready_count = sum(1 for row in rows if row.get("cacheState") == "cache_hit")
        payload = self.base(
            mode="verify-cache",
            status="ok" if ready_count == len(self.symbols) else "partial",
            next_action=_cache_next_action(rows),
        )
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        payload["cacheRows"] = rows
        payload["summary"] = {
            "symbolsChecked": len(rows),
            "cacheHitCount": ready_count,
            "zeroBarCount": sum(1 for row in rows if int(row.get("cachedBars") or 0) == 0),
        }
        return payload

    def verify_chain(self) -> dict[str, Any]:
        readiness_by_symbol = {
            symbol: self.readiness_service.fetch(
                HistoricalOhlcvReadinessRequest(
                    symbol=symbol,
                    market="us",
                    timeframe="1d",
                    required_bars=self.required_bars,
                    lookback_bars=self.required_bars,
                    require_adjusted=self.require_adjusted,
                )
            ).readiness
            for symbol in self.symbols
        }
        scanner_summary = summarize_scanner_ohlcv_readiness(
            market="us",
            profile="operator_seed_verifier",
            diagnostics={
                "candidate_diagnostics": {
                    symbol: {"historicalOhlcvReadiness": readiness}
                    for symbol, readiness in readiness_by_symbol.items()
                }
            },
            candidates=[],
        )
        seeded_symbols = [
            symbol
            for symbol, readiness in readiness_by_symbol.items()
            if _readiness_has_seeded_bars(readiness, required_bars=self.required_bars)
        ]
        eligible_symbols = [
            symbol
            for symbol, readiness in readiness_by_symbol.items()
            if symbol in seeded_symbols and readiness.get("overallState") == "ready"
        ]
        blocked_symbols = [
            symbol
            for symbol, readiness in readiness_by_symbol.items()
            if symbol not in eligible_symbols
        ]
        scanner_missing_families = _scanner_missing_families_for_seeded_state(
            seeded_symbols=seeded_symbols,
            requirements=scanner_summary.get("missingRequirements"),
        )
        quote_readiness = self.quote_service.fetch(
            QuoteSnapshotReadinessRequest(symbols=tuple(eligible_symbols), market="us")
        ).readiness if eligible_symbols else {}
        quote_available_symbols = list(quote_readiness.get("availableSymbols") or [])
        quote_stale_symbols = list(quote_readiness.get("staleSymbols") or [])
        quote_missing_symbols = list(quote_readiness.get("missingSymbols") or [])
        quote_coverage = (
            "available"
            if eligible_symbols and len(quote_available_symbols) == len(eligible_symbols)
            else "partial"
            if quote_available_symbols
            else "missing"
        )
        if quote_coverage == "available":
            scanner_missing_families = [
                family for family in scanner_missing_families if family != "quote_snapshot"
            ]
        elif "quote_snapshot" not in scanner_missing_families:
            scanner_missing_families.append("quote_snapshot")
        scanner_universe = build_scanner_universe_readiness_from_coverage(
            market="us",
            universe_status="available",
            universe_size=len(self.symbols),
            last_updated_at=None,
            freshness_state="operator_verifier",
            quote_coverage=quote_coverage,
            history_coverage="available" if seeded_symbols else "missing",
            blocked=bool(blocked_symbols) or not eligible_symbols or quote_coverage != "available",
            historical_requirements=scanner_summary.get("missingRequirements"),
            seeded_symbols=seeded_symbols,
            eligible_symbols=quote_available_symbols if quote_coverage == "available" else eligible_symbols,
            blocked_symbols=list(dict.fromkeys([*blocked_symbols, *quote_stale_symbols, *quote_missing_symbols])),
            missing_data_families=scanner_missing_families,
            operator_next_action=_scanner_chain_operator_action(
                seeded_count=len(seeded_symbols),
                requirements=scanner_summary.get("missingRequirements"),
                quote_coverage=quote_coverage,
            ),
        )
        backtest_fetch = self.readiness_service.fetch(
            HistoricalOhlcvReadinessRequest(
                symbol=BACKTEST_SYMBOL,
                market="us",
                timeframe="1d",
                required_bars=self.required_bars,
                lookback_bars=self.required_bars,
                require_adjusted=self.require_adjusted,
                benchmark_symbol=BACKTEST_BENCHMARK,
                benchmark_required=True,
            )
        )
        backtest = build_backtest_historical_ohlcv_readiness(
            backtest_fetch.readiness,
        )
        if backtest["status"] == "available":
            backtest["operatorNextAction"] = "Backtest DATA-110 symbol and benchmark OHLCV requirements are met for this verifier request."
            backtest["nextOperatorAction"] = backtest["operatorNextAction"]

        status = "ok" if eligible_symbols and backtest["status"] == "available" else "partial"
        payload = self.base(
            mode="verify-chain",
            status=status,
            next_action=_chain_next_action(scanner_universe, backtest),
        )
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        payload["scannerReadiness"] = {
            "historicalOhlcvSummary": scanner_summary,
            "quoteSnapshotReadiness": quote_readiness,
            "scannerUniverseReadiness": scanner_universe,
            "cacheBackedSymbolCount": len(seeded_symbols),
        }
        payload["backtestReadiness"] = {
            "symbol": BACKTEST_SYMBOL,
            "benchmarkSymbol": BACKTEST_BENCHMARK,
            "data110": backtest,
        }
        return payload

    def fail_closed(self, *, mode: str, reason: str, next_action: str) -> dict[str, Any]:
        payload = self.base(mode=mode, status="failed_closed", next_action=next_action)
        payload["reason"] = reason
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        return payload

    def env_gates(self) -> list[dict[str, Any]]:
        return [
            _env_gate(
                self.env,
                HISTORICAL_RUNTIME_ENABLED_ENV,
                required_for=["execute", "provider_fetch"],
                description="Global historical OHLCV runtime gate.",
            ),
            _env_gate(
                self.env,
                YFINANCE_US_OHLCV_ENABLE_ENV,
                required_for=["execute", "us_provider_fetch"],
                description="US yfinance OHLCV fetch gate; cache reads do not require it.",
            ),
            _env_gate(
                self.env,
                HISTORICAL_OHLCV_CACHE_SEED_ENABLED_ENV,
                required_for=["execute", "cache_mutation"],
                description="Explicit seed write gate.",
            ),
        ]

    def missing_execute_gates(self) -> list[str]:
        return [
            gate["name"]
            for gate in self.env_gates()
            if not bool(gate.get("enabled"))
        ]

    def cache_location_summary(self) -> dict[str, Any]:
        configured_by = None
        for key in ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR"):
            if str(self.env.get(key) or "").strip():
                configured_by = key
                break
        return {
            "configurable": True,
            "primaryEnv": "LOCAL_US_PARQUET_DIR",
            "legacyFallbackEnv": "US_STOCK_PARQUET_DIR",
            "configuredBy": configured_by or "default",
            "resolvedPathExposed": False,
        }


def _env_gate(env: Mapping[str, str], name: str, *, required_for: Sequence[str], description: str) -> dict[str, Any]:
    raw = env.get(name)
    return {
        "name": name,
        "requiredFor": list(required_for),
        "configured": raw is not None and str(raw).strip() != "",
        "enabled": _enabled(raw),
        "state": "enabled" if _enabled(raw) else "disabled",
        "valueRedacted": True,
        "description": description,
    }


def _enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in _TRUTHY


def _dependency_state(module_name: str) -> dict[str, Any]:
    try:
        available = importlib.util.find_spec(module_name) is not None
    except Exception:
        available = False
    return {"available": available, "detailsExposed": False}


def _normalize_symbols(symbols: Sequence[str] | None) -> list[str]:
    values = symbols or DEFAULT_VERIFY_SYMBOLS
    result: list[str] = []
    for value in values:
        symbol = str(value or "").strip().upper()
        if symbol and symbol in DEFAULT_US_REPRESENTATIVE_SYMBOLS and symbol not in result:
            result.append(symbol)
    return result or list(DEFAULT_VERIFY_SYMBOLS)


def _parse_symbols(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _us_symbol_rows(preflight: Mapping[str, Any]) -> list[dict[str, Any]]:
    us_market = ((preflight.get("markets") or {}).get("us") or {}) if isinstance(preflight, Mapping) else {}
    rows: list[dict[str, Any]] = []
    for item in us_market.get("symbols") or []:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "symbol": item.get("symbol"),
                "status": item.get("status"),
                "cacheState": item.get("cacheState"),
                "cachedBars": int(item.get("cachedBars") or 0),
                "dateRange": item.get("dateRange") or {"start": None, "end": None},
                "latestBarDate": item.get("latestBarDate"),
                "freshnessState": item.get("freshnessState"),
                "adjustmentState": item.get("adjustmentState"),
                "dataState": item.get("dataState"),
                "nextOperatorAction": item.get("nextOperatorAction"),
            }
        )
    return rows


def _next_action_from_preflight(payload: Mapping[str, Any]) -> str:
    rows = _us_symbol_rows(payload)
    if any(row.get("cacheState") != "cache_hit" for row in rows):
        return "Resolve missing provider/config or run explicit seed after dry-run review."
    return "Cache rows are present; run verify-cache and verify-chain before widening seed scope."


def _cache_next_action(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows or any(int(row.get("cachedBars") or 0) == 0 for row in rows):
        return "Run dry-run, enable required gates only if approved, then execute seed for the starter symbols."
    if any(str(row.get("status") or "") in {"stale", "insufficient_coverage", "missing"} for row in rows):
        return "Refresh or reseed local cache rows until bars, range, freshness, and adjustments meet the verifier requirements."
    return "Cache rows are present for the starter symbols; run verify-chain next."


def _readiness_has_seeded_bars(readiness: Mapping[str, Any], *, required_bars: int) -> bool:
    if str(readiness.get("providerState") or "").strip().lower() != "available":
        return False
    usable_bars = _safe_int(readiness.get("usableBars"))
    missing_bars = _safe_int(readiness.get("missingBars"))
    return usable_bars >= max(1, int(required_bars or 0)) and missing_bars <= 0


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _scanner_missing_families_for_seeded_state(
    *,
    seeded_symbols: Sequence[str],
    requirements: Any,
) -> list[str]:
    families: list[str] = ["quote_snapshot"]
    normalized = {str(item or "").strip().lower() for item in requirements or []}
    if "missing_adjustments" in normalized:
        families.append("adjusted_prices")
    if not seeded_symbols:
        families.insert(0, "historical_ohlcv")
    return list(dict.fromkeys(families))


def _scanner_chain_operator_action(*, seeded_count: int, requirements: Any, quote_coverage: str = "missing") -> str:
    normalized = {str(item or "").strip().lower() for item in requirements or []}
    if seeded_count > 0 and quote_coverage == "available" and "missing_adjustments" not in normalized:
        return "Cache-backed historical OHLCV rows and quote snapshots are available for the bounded Scanner verifier."
    if seeded_count > 0 and "missing_adjustments" in normalized:
        return (
            f"Cache-backed historical OHLCV rows exist for {seeded_count} symbol(s); "
            "quote snapshot coverage and adjusted prices or adjustment metadata still block Scanner candidates."
        )
    if seeded_count > 0:
        return (
            f"Cache-backed historical OHLCV rows exist for {seeded_count} symbol(s); "
            "quote snapshot coverage still blocks Scanner candidates."
        )
    return "Seed or refresh historical OHLCV cache rows before Scanner can observe seeded symbols."


def _chain_next_action(scanner_universe: Mapping[str, Any], backtest: Mapping[str, Any]) -> str:
    scanner_missing = set(scanner_universe.get("missingDataFamilies") or [])
    backtest_missing = set(backtest.get("missingDataFamilies") or [])
    rows_present = "historical_ohlcv" not in scanner_missing and int(backtest.get("symbolBarsAvailable") or 0) > 0
    if rows_present and "quote_snapshot" in scanner_missing and "adjusted_prices" in backtest_missing:
        return "Cache rows are present; adjusted prices or adjustment metadata and Scanner quote snapshot coverage still block verify-chain."
    if backtest.get("status") != "available":
        return str(backtest.get("nextOperatorAction") or "Refresh local OHLCV cache rows, then rerun verify-chain.")
    if scanner_universe.get("status") != "available":
        return str(scanner_universe.get("nextOperatorAction") or "Refresh Scanner quote coverage before candidate generation.")
    return "Scanner and Backtest readiness seams can observe the seeded cache rows."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("inspect", "dry-run", "execute", "verify-cache", "verify-chain"),
        default="inspect",
    )
    parser.add_argument("--us-symbols", default=",".join(DEFAULT_VERIFY_SYMBOLS))
    parser.add_argument("--required-bars", type=int, default=60)
    parser.add_argument("--no-require-adjusted", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Required with --mode execute to permit mutation.")
    parser.add_argument("--cache-dir", default="", help="Optional LOCAL_US_PARQUET_DIR override for this process.")
    args = parser.parse_args(argv)

    if args.cache_dir.strip():
        os.environ["LOCAL_US_PARQUET_DIR"] = args.cache_dir.strip()

    _ = get_us_stock_parquet_dir()
    payload = build_operator_verifier_payload(
        mode=args.mode,
        symbols=_parse_symbols(args.us_symbols),
        required_bars=max(1, int(args.required_bars or 60)),
        require_adjusted=not bool(args.no_require_adjusted),
        execute=bool(args.execute),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if payload.get("status") == "failed_closed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
