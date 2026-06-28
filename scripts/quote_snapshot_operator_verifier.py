#!/usr/bin/env python3
"""Operator verifier for the explicit US quote snapshot seam."""

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

from src.services.historical_ohlcv_cache_preflight import sanitize_historical_ohlcv_preflight_payload
from src.services.local_quote_snapshot_provider import LocalQuoteSnapshotJsonProvider
from src.services.quote_snapshot_readiness import (
    QuoteSnapshotProvider,
    QuoteSnapshotReadinessRequest,
    QuoteSnapshotReadinessService,
)
from src.services.scanner_universe_readiness import build_scanner_universe_readiness_from_coverage


CONTRACT_VERSION = "quote_snapshot_operator_verifier_v1"
DEFAULT_VERIFY_SYMBOLS = ("SPY", "QQQ", "AAPL", "MSFT")
QUOTE_SNAPSHOT_LIVE_ENABLED_ENV = "WOLFYSTOCK_US_QUOTE_SNAPSHOT_LIVE_ENABLED"
QUOTE_SNAPSHOT_CACHE_WRITE_ENABLED_ENV = "WOLFYSTOCK_US_QUOTE_SNAPSHOT_CACHE_WRITE_ENABLED"
_TRUTHY = {"1", "true", "yes", "on"}


def build_operator_verifier_payload(
    *,
    mode: str,
    env: Mapping[str, str] | None = None,
    symbols: Sequence[str] | None = None,
    execute: bool = False,
    quote_provider: QuoteSnapshotProvider | None = None,
    max_age_seconds: int = 60 * 60 * 24,
) -> dict[str, Any]:
    verifier = _Verifier(
        env=dict(env or os.environ),
        symbols=_normalize_symbols(symbols),
        quote_provider=quote_provider,
        max_age_seconds=max(1, int(max_age_seconds or 1)),
    )
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode == "inspect":
        payload = verifier.inspect()
    elif normalized_mode == "dry-run":
        payload = verifier.dry_run()
    elif normalized_mode == "execute":
        payload = verifier.execute(execute=execute)
    elif normalized_mode in {"verify-snapshot", "verify-cache"}:
        payload = verifier.verify_snapshot()
    elif normalized_mode == "verify-scanner":
        payload = verifier.verify_scanner()
    else:
        payload = verifier.fail_closed(
            mode=normalized_mode or "unknown",
            reason="unsupported_mode",
            next_action="Choose one of inspect, dry-run, execute, verify-snapshot, or verify-scanner.",
        )
    return sanitize_historical_ohlcv_preflight_payload(payload)


class _Verifier:
    def __init__(
        self,
        *,
        env: Mapping[str, str],
        symbols: Sequence[str],
        quote_provider: QuoteSnapshotProvider | None,
        max_age_seconds: int,
    ) -> None:
        self.env = dict(env)
        self.symbols = list(symbols)
        self.quote_service = QuoteSnapshotReadinessService(provider=quote_provider)
        self.max_age_seconds = max_age_seconds

    def base(self, *, mode: str, status: str, next_action: str) -> dict[str, Any]:
        return {
            "contractVersion": CONTRACT_VERSION,
            "mode": mode,
            "status": status,
            "consumerSafe": True,
            "symbols": list(self.symbols),
            "envGates": self.env_gates(),
            "networkCallsEnabled": False,
            "mutationEnabled": False,
            "nextOperatorAction": next_action,
        }

    def inspect(self) -> dict[str, Any]:
        payload = self.base(
            mode="inspect",
            status="ok",
            next_action="Run dry-run first; verify-snapshot is read-only, execute requires explicit gates.",
        )
        payload["dependencyState"] = {
            "yfinance": _dependency_state("yfinance"),
        }
        payload["dryRunCommand"] = (
            "python scripts/quote_snapshot_operator_verifier.py --mode dry-run "
            "--us-symbols SPY,QQQ,AAPL,MSFT"
        )
        payload["verifyScannerCommand"] = (
            "python scripts/quote_snapshot_operator_verifier.py --mode verify-scanner "
            "--us-symbols SPY,QQQ,AAPL,MSFT"
        )
        return payload

    def dry_run(self) -> dict[str, Any]:
        payload = self.base(
            mode="dry-run",
            status="ok",
            next_action="Dry-run is read-only; run verify-snapshot against an explicit cache/provider reader next.",
        )
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        payload["plannedRequest"] = {
            "market": "us",
            "symbols": list(self.symbols),
            "maxAgeSeconds": self.max_age_seconds,
            "providerFetchDefault": "disabled",
            "cacheMutationDefault": "disabled",
        }
        return payload

    def execute(self, *, execute: bool) -> dict[str, Any]:
        if not execute:
            return self.fail_closed(
                mode="execute",
                reason="missing_explicit_execute_flag",
                next_action="Rerun with --mode execute --execute only after dry-run and verify-snapshot are reviewed.",
            )
        missing = self.missing_execute_gates()
        if missing:
            payload = self.fail_closed(
                mode="execute",
                reason="required_env_gates_disabled",
                next_action="Enable every required env gate, rerun inspect and dry-run, then retry execute.",
            )
            payload["missingRequiredGates"] = missing
            return payload
        return self.fail_closed(
            mode="execute",
            reason="live_fetch_not_implemented",
            next_action="Wire an approved provider/cache writer before using execute mode.",
        )

    def verify_snapshot(self) -> dict[str, Any]:
        readiness = self._quote_readiness()
        status = "ok" if readiness.get("availabilityState") == "available" else "partial"
        payload = self.base(
            mode="verify-snapshot",
            status=status,
            next_action=_snapshot_next_action(readiness),
        )
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        payload["quoteSnapshotReadiness"] = readiness
        return payload

    def verify_scanner(self) -> dict[str, Any]:
        readiness = self._quote_readiness()
        available_symbols = list(readiness.get("availableSymbols") or [])
        missing_symbols = list(readiness.get("missingSymbols") or [])
        stale_symbols = list(readiness.get("staleSymbols") or [])
        quote_coverage = "available" if len(available_symbols) == len(self.symbols) else "partial" if available_symbols else "missing"
        scanner_universe = build_scanner_universe_readiness_from_coverage(
            market="us",
            universe_status="available",
            universe_size=len(self.symbols),
            last_updated_at=None,
            freshness_state=str(readiness.get("freshnessState") or "unknown"),
            quote_coverage=quote_coverage,
            history_coverage="missing",
            blocked=quote_coverage != "available",
            historical_requirements=[],
            seeded_symbols=list(self.symbols),
            eligible_symbols=available_symbols,
            blocked_symbols=missing_symbols + stale_symbols,
            missing_data_families=[] if quote_coverage == "available" else ["quote_snapshot"],
            operator_next_action=_scanner_next_action(readiness),
        )
        payload = self.base(
            mode="verify-scanner",
            status="ok" if quote_coverage == "available" else "partial",
            next_action=_scanner_next_action(readiness),
        )
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        payload["quoteSnapshotReadiness"] = readiness
        payload["scannerReadiness"] = {
            "scannerUniverseReadiness": scanner_universe,
            "quoteBackedSymbolCount": len(available_symbols),
        }
        return payload

    def fail_closed(self, *, mode: str, reason: str, next_action: str) -> dict[str, Any]:
        payload = self.base(mode=mode, status="failed_closed", next_action=next_action)
        payload["reason"] = reason
        payload["dryRun"] = True
        payload["networkCallsEnabled"] = False
        payload["mutationEnabled"] = False
        return payload

    def _quote_readiness(self) -> dict[str, Any]:
        result = self.quote_service.fetch(
            QuoteSnapshotReadinessRequest(
                symbols=tuple(self.symbols),
                market="us",
                max_age_seconds=self.max_age_seconds,
            )
        )
        return dict(result.readiness)

    def env_gates(self) -> list[dict[str, Any]]:
        return [
            _env_gate(
                self.env,
                QUOTE_SNAPSHOT_LIVE_ENABLED_ENV,
                required_for=["execute", "provider_fetch"],
                description="Explicit US quote snapshot live fetch gate.",
            ),
            _env_gate(
                self.env,
                QUOTE_SNAPSHOT_CACHE_WRITE_ENABLED_ENV,
                required_for=["execute", "cache_mutation"],
                description="Explicit US quote snapshot cache write gate.",
            ),
        ]

    def missing_execute_gates(self) -> list[str]:
        return [gate["name"] for gate in self.env_gates() if not bool(gate.get("enabled"))]


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
        if symbol and symbol in DEFAULT_VERIFY_SYMBOLS and symbol not in result:
            result.append(symbol)
    return result or list(DEFAULT_VERIFY_SYMBOLS)


def _parse_symbols(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _snapshot_next_action(readiness: Mapping[str, Any]) -> str:
    if readiness.get("availabilityState") == "available":
        return "Quote snapshot rows are available for the starter symbols; run verify-scanner next."
    if readiness.get("staleSymbols"):
        return "Refresh stale quote snapshot rows for the starter symbols, then rerun verify-snapshot."
    return "Provide explicit local/provider-backed quote snapshot rows for SPY, QQQ, AAPL, and MSFT."


def _scanner_next_action(readiness: Mapping[str, Any]) -> str:
    if readiness.get("availabilityState") == "available":
        return "Scanner quote_snapshot readiness is available for the bounded starter symbols."
    return _snapshot_next_action(readiness)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("inspect", "dry-run", "execute", "verify-snapshot", "verify-scanner"),
        default="inspect",
    )
    parser.add_argument("--us-symbols", default=",".join(DEFAULT_VERIFY_SYMBOLS))
    parser.add_argument("--max-age-seconds", type=int, default=60 * 60 * 24)
    parser.add_argument("--cache-path", default="", help="Explicit read-only local quote snapshot JSON path.")
    parser.add_argument("--execute", action="store_true", help="Required with --mode execute to permit mutation.")
    args = parser.parse_args(argv)
    quote_provider = (
        LocalQuoteSnapshotJsonProvider(cache_path=args.cache_path.strip())
        if str(args.cache_path or "").strip()
        else None
    )

    payload = build_operator_verifier_payload(
        mode=args.mode,
        symbols=_parse_symbols(args.us_symbols),
        max_age_seconds=max(1, int(args.max_age_seconds or 1)),
        execute=bool(args.execute),
        quote_provider=quote_provider,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if payload.get("status") == "failed_closed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
