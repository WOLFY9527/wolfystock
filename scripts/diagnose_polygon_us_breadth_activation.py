#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a bounded Polygon grouped-daily US breadth activation diagnostic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import setup_env
from src.services.polygon_us_breadth_provider import (
    diagnostic_summary,
    run_polygon_us_breadth_activation,
)
from src.services.us_breadth_contracts import US_BREADTH_SYMBOLS

EXIT_OK = 0
EXIT_FAILED = 1


def _unexpected_error_summary() -> dict[str, object]:
    return {
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "observationDate": None,
        "previousObservationDate": None,
        "comparisonBasis": None,
        "freshnessValid": False,
        "coverageCount": 0,
        "previousCoverageCount": 0,
        "comparisonCoverageCount": 0,
        "coverageThreshold": 0,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "broadMarketClaimAllowed": False,
        "fulfilledMetrics": [],
        "missingMetrics": list(US_BREADTH_SYMBOLS),
        "reasonCodes": ["unexpected_error"],
    }


def main() -> int:
    try:
        setup_env()
        summary = diagnostic_summary(run_polygon_us_breadth_activation())
    except Exception:
        print(json.dumps(_unexpected_error_summary(), ensure_ascii=False))
        return EXIT_FAILED
    print(json.dumps(summary, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
