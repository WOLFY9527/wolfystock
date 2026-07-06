# -*- coding: utf-8 -*-
"""Import an explicit local scanner universe into the lifecycle store.

The command validates, normalizes, deduplicates, versions, and safely activates
only repository-local or explicitly supplied JSON input. It does not call
providers, run Scanner, or mutate legacy cache files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.scanner_universe_lifecycle import (  # noqa: E402
    ScannerUniverseLifecycleStore,
    activate_scanner_universe_from_file,
    activate_scanner_universe_from_source,
    build_scanner_universe_lifecycle_readiness,
    dry_run_scanner_universe_source,
    read_scanner_universe_source_file,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, dry-run, or explicitly activate a deterministic scanner universe source.",
    )
    parser.add_argument("--source", default=None, help="Path to local JSON input with source metadata and symbols.")
    parser.add_argument("--market", required=True, choices=("cn", "us", "hk", "CN", "US", "HK"))
    parser.add_argument("--root", default=None, help="Lifecycle store root. Defaults to SCANNER_UNIVERSE_LIFECYCLE_ROOT or ./data/scanner_universe_lifecycle.")
    parser.add_argument("--minimum-coverage-threshold", type=int, default=None)
    parser.add_argument("--max-age-days", type=int, default=3)
    parser.add_argument("--max-shrink-percentage", type=float, default=80.0)
    parser.add_argument("--inspect", action="store_true", help="Inspect and normalize the source without activation.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and diff the source without activation.")
    parser.add_argument("--activate", action="store_true", help="Explicitly activate the source when qualification passes.")
    parser.add_argument("--inspect-active", action="store_true", help="Inspect the active lifecycle version without requiring --source.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    store = ScannerUniverseLifecycleStore(root=args.root)
    if args.inspect_active:
        result = {
            "contractVersion": "scanner_universe_lifecycle_inspect_active_v1",
            "status": "inspected",
            "market": str(args.market).upper(),
            "readOnly": True,
            "noExternalCalls": True,
            "providerCallsEnabled": False,
        }
    else:
        if not args.source:
            raise SystemExit("--source is required unless --inspect-active is used")
        source_projection = read_scanner_universe_source_file(args.source, market=args.market)
        is_source_contract = source_projection.get("sourcePolicyState") != "unknown_policy"
        if args.inspect:
            result = {
                "contractVersion": "scanner_universe_source_inspect_action_v1",
                "status": "inspected",
                "market": str(args.market).upper(),
                "source": source_projection,
                "readOnly": True,
                "noExternalCalls": True,
                "providerCallsEnabled": False,
            }
        elif args.dry_run:
            result = dry_run_scanner_universe_source(
                source_path=args.source,
                store=store,
                market=args.market,
                minimum_coverage_threshold=args.minimum_coverage_threshold,
                max_age_days=args.max_age_days,
                max_shrink_percentage=args.max_shrink_percentage,
            )
        elif args.activate or is_source_contract:
            result = activate_scanner_universe_from_source(
                source_path=args.source,
                store=store,
                market=args.market,
                minimum_coverage_threshold=args.minimum_coverage_threshold,
                max_age_days=args.max_age_days,
                max_shrink_percentage=args.max_shrink_percentage,
            )
        else:
            result = activate_scanner_universe_from_file(
                source_path=args.source,
                store=store,
                market=args.market,
                minimum_coverage_threshold=args.minimum_coverage_threshold,
            )
    readiness = build_scanner_universe_lifecycle_readiness(
        store=store,
        market=args.market,
        minimum_coverage_threshold=args.minimum_coverage_threshold,
    )
    payload: dict[str, Any] = {
        "contractVersion": "scanner_universe_lifecycle_import_cli_v1",
        "action": result,
        "readiness": readiness,
        "readOnly": False,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "scannerRefreshExecuted": False,
        "runtimeBehaviorChanged": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if result.get("status") in {"activated", "accepted", "inspected"}:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
