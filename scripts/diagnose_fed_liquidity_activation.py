#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a bounded official Fed liquidity live smoke diagnostic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.official_macro_transport import FED_LIQUIDITY_FRED_SERIES_IDS, run_fed_liquidity_live_smoke

EXIT_OK = 0
EXIT_FAILED = 1


def _unexpected_error_summary() -> dict[str, object]:
    return {
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledSeries": [],
        "missingSeries": list(FED_LIQUIDITY_FRED_SERIES_IDS),
        "staleSeries": [],
        "reason": "unexpected_error",
    }


def main() -> int:
    try:
        summary = run_fed_liquidity_live_smoke()
    except Exception:
        print(json.dumps(_unexpected_error_summary(), ensure_ascii=False))
        return EXIT_FAILED
    print(json.dumps(summary, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
