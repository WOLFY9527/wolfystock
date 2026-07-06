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
    build_scanner_universe_lifecycle_readiness,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Activate a deterministic local scanner universe version from explicit JSON input.",
    )
    parser.add_argument("--source", required=True, help="Path to local JSON input with market/sourceClass/generatedAt/asOf/symbols.")
    parser.add_argument("--market", required=True, choices=("cn", "us", "hk", "CN", "US", "HK"))
    parser.add_argument("--root", default=None, help="Lifecycle store root. Defaults to SCANNER_UNIVERSE_LIFECYCLE_ROOT or ./data/scanner_universe_lifecycle.")
    parser.add_argument("--minimum-coverage-threshold", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    store = ScannerUniverseLifecycleStore(root=args.root)
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
    return 0 if result.get("status") == "activated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
