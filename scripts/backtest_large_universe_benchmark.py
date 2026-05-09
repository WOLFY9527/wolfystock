#!/usr/bin/env python3
"""Local synthetic benchmark for large-universe rule backtest planning.

This script intentionally avoids RuleBacktestService persistence, live provider
fetches, DuckDB, and production data. It measures the current deterministic
engine over synthetic in-memory OHLCV bars so large-universe planning has a
repeatable local baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.rule_backtest_engine import ParsedStrategy, RuleBacktestEngine
from src.services.rule_backtest_service import RuleBacktestService

BENCHMARK_VERSION = "backtest-large-universe-synthetic-v1"


@dataclass(frozen=True)
class SymbolTiming:
    symbol: str
    elapsed_ms: float
    bars: int
    trades: int
    equity_points: int
    audit_rows: int
    legacy_exposure_rows: int | None


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _bounded_symbols(value: str) -> int:
    parsed = _positive_int(value)
    if parsed > 5000:
        raise argparse.ArgumentTypeError("synthetic benchmark cap is 5000 symbols")
    return parsed


def _build_strategy() -> ParsedStrategy:
    return ParsedStrategy(
        version="v1",
        timeframe="daily",
        source_text="5日均线上穿20日均线买入，下穿卖出",
        normalized_text="5日均线上穿20日均线买入，下穿卖出",
        entry={"indicator": "ma_crossover", "direction": "above", "fast_period": 5, "slow_period": 20},
        exit={"indicator": "ma_crossover", "direction": "below", "fast_period": 5, "slow_period": 20},
        confidence=1.0,
        needs_confirmation=False,
        ambiguities=[],
        summary={
            "entry": "买入条件：SMA5 上穿 SMA20",
            "exit": "卖出条件：SMA5 下穿 SMA20",
            "risk": "无额外风控",
        },
        max_lookback=20,
        strategy_kind="moving_average_crossover",
        setup={"fast_period": 5, "slow_period": 20, "fast_type": "simple", "slow_type": "simple"},
        strategy_spec={
            "version": "v1",
            "strategy_type": "moving_average_crossover",
            "strategy_family": "moving_average_crossover",
            "timeframe": "daily",
            "max_lookback": 20,
            "signal": {
                "indicator_family": "moving_average",
                "fast_period": 5,
                "slow_period": 20,
                "fast_type": "simple",
                "slow_type": "simple",
                "entry_condition": "fast_crosses_above_slow",
                "exit_condition": "fast_crosses_below_slow",
            },
            "execution": {
                "frequency": "daily",
                "signal_timing": "bar_close",
                "fill_timing": "next_bar_open",
            },
            "position_behavior": {
                "direction": "long_only",
                "entry_sizing": "all_cash",
                "max_positions": 1,
                "pyramiding": False,
            },
            "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
        },
        executable=True,
        normalization_state="normalized",
        detected_strategy_family="moving_average_crossover",
        interpretation_confidence=1.0,
    )


def _build_bars(symbol: str, *, bars: int, offset: int) -> list[SimpleNamespace]:
    start = date(2020, 1, 1)
    base = 50.0 + float(offset % 37)
    rows: list[SimpleNamespace] = []
    for index in range(bars):
        point_date = start + timedelta(days=index)
        trend = index * (0.018 + ((offset % 5) * 0.002))
        wave = ((index + offset) % 29 - 14) * 0.11
        close = max(1.0, base + trend + wave)
        open_price = close - 0.18 + ((index + offset) % 3 - 1) * 0.04
        high = max(open_price, close) + 0.35
        low = max(0.01, min(open_price, close) - 0.35)
        rows.append(
            SimpleNamespace(
                code=symbol,
                date=point_date,
                open=round(open_price, 6),
                high=round(high, 6),
                low=round(low, 6),
                close=round(close, 6),
                volume=float(1_000_000 + offset * 100 + index * 10),
            )
        )
    return rows


def _result_to_exposure_inputs(result: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    equity_curve = [point.to_dict() for point in result.equity_curve]
    trades = [trade.to_dict() for trade in result.trades]
    return equity_curve, trades


def run_benchmark(*, symbols: int, bars: int, include_legacy_exposure: bool) -> dict[str, Any]:
    engine = RuleBacktestEngine()
    parsed_strategy = _build_strategy()
    timings: list[SymbolTiming] = []
    total_trades = 0
    total_equity_points = 0
    total_audit_rows = 0

    tracemalloc.start()
    started = time.perf_counter()
    for index in range(symbols):
        symbol = f"SYN{index + 1:05d}"
        symbol_started = time.perf_counter()
        result = engine.run(
            code=symbol,
            parsed_strategy=parsed_strategy,
            bars=_build_bars(symbol, bars=bars, offset=index),
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            lookback_bars=bars,
        )
        audit_rows = engine._build_audit_ledger(
            equity_curve=result.equity_curve,
            benchmark_curve=result.benchmark_curve,
            buy_and_hold_curve=result.buy_and_hold_curve,
            benchmark_summary=result.benchmark_summary,
        )
        legacy_exposure_rows: int | None = None
        if include_legacy_exposure:
            equity_payload, trade_payload = _result_to_exposure_inputs(result)
            legacy_exposure_rows = len(RuleBacktestService._build_exposure_curve(equity_payload, trade_payload))

        elapsed_ms = (time.perf_counter() - symbol_started) * 1000.0
        trade_count = len(result.trades)
        equity_points = len(result.equity_curve)
        audit_count = len(audit_rows)
        total_trades += trade_count
        total_equity_points += equity_points
        total_audit_rows += audit_count
        timings.append(
            SymbolTiming(
                symbol=symbol,
                elapsed_ms=round(elapsed_ms, 4),
                bars=bars,
                trades=trade_count,
                equity_points=equity_points,
                audit_rows=audit_count,
                legacy_exposure_rows=legacy_exposure_rows,
            )
        )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    per_symbol = [item.elapsed_ms for item in timings]
    payload = {
        "version": BENCHMARK_VERSION,
        "mode": "synthetic_in_memory_no_provider_no_persistence",
        "symbols": symbols,
        "bars_per_symbol": bars,
        "include_legacy_exposure": include_legacy_exposure,
        "elapsed_ms": round(elapsed_ms, 4),
        "avg_symbol_ms": round(mean(per_symbol), 4) if per_symbol else 0.0,
        "max_symbol_ms": round(max(per_symbol), 4) if per_symbol else 0.0,
        "symbols_per_second": round((symbols / elapsed_ms) * 1000.0, 4) if elapsed_ms > 0 else None,
        "total_trades": total_trades,
        "total_equity_points": total_equity_points,
        "total_audit_rows": total_audit_rows,
        "memory": {
            "current_mb": round(current_bytes / (1024 * 1024), 4),
            "peak_mb": round(peak_bytes / (1024 * 1024), 4),
        },
        "sample_timings": [item.__dict__ for item in timings[: min(10, len(timings))]],
        "guardrails": {
            "live_provider_calls": False,
            "production_data_reads": False,
            "production_writes": False,
            "duckdb_runtime": False,
            "launch_approval_semantics": False,
        },
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local synthetic large-universe rule backtest benchmark without live providers or persistence."
    )
    parser.add_argument("--symbols", type=_bounded_symbols, default=100, help="Synthetic symbol count, capped at 5000.")
    parser.add_argument("--bars", type=_positive_int, default=252, help="Synthetic daily bars per symbol.")
    parser.add_argument(
        "--include-legacy-exposure",
        action="store_true",
        help="Also measure the legacy O(days * trades) exposure helper on each synthetic result.",
    )
    parser.add_argument("--json", action="store_true", help="Print compact JSON instead of human-readable text.")
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON benchmark payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_benchmark(
        symbols=int(args.symbols),
        bars=int(args.bars),
        include_legacy_exposure=bool(args.include_legacy_exposure),
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"version: {payload['version']}")
        print(f"mode: {payload['mode']}")
        print(f"symbols: {payload['symbols']}")
        print(f"bars_per_symbol: {payload['bars_per_symbol']}")
        print(f"elapsed_ms: {payload['elapsed_ms']}")
        print(f"avg_symbol_ms: {payload['avg_symbol_ms']}")
        print(f"symbols_per_second: {payload['symbols_per_second']}")
        print(f"peak_memory_mb: {payload['memory']['peak_mb']}")
        print("guardrails: no live providers, no production reads/writes, no DuckDB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
