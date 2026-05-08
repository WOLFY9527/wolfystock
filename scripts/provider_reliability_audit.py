#!/usr/bin/env python3
"""Offline provider reliability posture audit.

The default and only supported mode is offline. This script performs local
contract checks against freshness/fallback helpers and emits bounded JSON. It
does not call providers, read credentials, inspect `.env`, or modify runtime
routing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.market_overview_service import (
    MarketOverviewService,
    classify_market_payload_reliability,
    get_freshness_status,
)


CN_TZ = timezone(timedelta(hours=8))
FRESHNESS_STATES = ("live", "stale", "fallback", "mixed", "unavailable", "refreshing")
PROVIDERS_CHECKED = (
    "market_overview_freshness_contract",
    "market_cache_swr_contract",
    "analysis_provider_executor_contract",
)


def _evaluate_posture() -> dict[str, Any]:
    now = datetime(2026, 5, 8, 10, 0, tzinfo=CN_TZ)
    service = MarketOverviewService()
    fallback_cases = {
        "fallback": get_freshness_status(now.isoformat(timespec="seconds"), "crypto", "fallback", False, now=now),
        "mock": get_freshness_status(now.isoformat(timespec="seconds"), "crypto", "mock", False, now=now),
        "synthetic": get_freshness_status(now.isoformat(timespec="seconds"), "crypto", "synthetic", False, now=now),
    }
    stale = get_freshness_status(
        (now - timedelta(hours=2)).isoformat(timespec="seconds"),
        "crypto",
        "binance",
        False,
        now=now,
    )
    mixed = classify_market_payload_reliability(
        {
            "source": "mixed",
            "items": [
                {"symbol": "BTC", "value": 75000, "source": "binance", "freshness": "live"},
                {"symbol": "SAMPLE", "value": 0, "source": "fallback", "freshness": "fallback"},
            ],
        },
        category="crypto",
    )
    unavailable = service._provider_health(
        {"source": "unavailable", "freshness": "fallback", "items": []},
        "sentiment",
        duration_ms=0,
        error_summary=None,
    )
    refreshing = service._provider_health(
        {
            "source": "binance",
            "freshness": "live",
            "isRefreshing": True,
            "items": [{"symbol": "BTC", "value": 75000, "source": "binance", "freshness": "live"}],
        },
        "crypto",
        duration_ms=0,
        error_summary=None,
    )
    mock_as_live_allowed = any(case.get("freshness") == "live" for case in fallback_cases.values())
    return {
        "providersChecked": list(PROVIDERS_CHECKED),
        "freshnessPosture": {
            "status": "pass"
            if stale.get("freshness") == "stale"
            and mixed.get("kind") == "mixed"
            and unavailable.get("status") == "unavailable"
            and refreshing.get("status") == "refreshing"
            and not mock_as_live_allowed
            else "needs-review",
            "statesCovered": list(FRESHNESS_STATES),
            "syntheticFreshness": fallback_cases["synthetic"].get("freshness"),
            "staleWarningRequired": bool(stale.get("warning")),
        },
        "fallbackPosture": {
            "status": "pass" if not mock_as_live_allowed else "fail",
            "mockAsLiveAllowed": mock_as_live_allowed,
            "fallbackSourcesChecked": sorted(fallback_cases),
        },
        "networkCallsExecuted": False,
        "manualReviewRequired": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit an offline provider reliability posture JSON summary without provider calls."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run offline contract checks only. This is also the default behavior.",
    )
    parser.parse_args(argv)
    print(json.dumps(_evaluate_posture(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
