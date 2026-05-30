#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a bounded Alpaca-only rotation radar activation diagnostic."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.rotation_radar_quote_provider import run_rotation_radar_alpaca_live_smoke

EXIT_OK = 0
EXIT_FAILED = 1
ENV_PER_WINDOW_TIMEOUT = "ALPACA_ACTIVATION_SMOKE_PER_WINDOW_TIMEOUT"
ENV_TOTAL_PROVIDER_BUDGET = "ALPACA_ACTIVATION_SMOKE_TOTAL_PROVIDER_BUDGET"
ENV_BAR_FETCH_TIMEOUT = "ALPACA_ACTIVATION_SMOKE_BAR_FETCH_TIMEOUT"
ENV_CONNECTIVITY_CHECK = "ALPACA_ACTIVATION_SMOKE_CONNECTIVITY_CHECK"


def _unexpected_error_summary() -> dict[str, object]:
    return {
        "credentialsPresent": False,
        "credentialSource": "unknown",
        "providerConstructed": False,
        "configuredProviderFeed": None,
        "feedEntitlementStatus": "unknown",
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledWindows": [],
        "missingWindows": ["5m", "15m", "60m", "1d"],
        "staleWindows": [],
        "reason": "unexpected_error",
        "activationBlocker": "unexpected_error",
        "providerFailureReasons": ["unexpected_error"],
        "perWindowTimeout": None,
        "totalProviderBudget": None,
        "barFetchTimeout": None,
        "effectiveTimeoutBudgets": {
            "perWindowTimeout": None,
            "totalProviderBudget": None,
            "barFetchTimeout": None,
            "overrideApplied": False,
        },
        "timeoutDiagnosis": {
            "category": "unknown",
            "timeoutObserved": False,
            "probeBudgetExhausted": False,
            "perWindowBarFetchTimedOut": False,
            "endpointReachabilityStatus": "not_checked",
            "feedWindowChoice": "not_evaluated",
            "noRecentBarsObserved": False,
            "dominantWindowFailureClass": None,
        },
        "endpointReachability": {
            "attempted": False,
            "status": "not_checked",
            "failureClass": None,
            "httpStatusClass": None,
        },
        "proxyEnvironment": {},
    }


def _positive_float_arg(raw: str) -> float:
    try:
        value = float(str(raw).strip())
    except Exception as exc:
        raise argparse.ArgumentTypeError("must be a positive number") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return value


def _env_positive_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return None
    try:
        value = float(str(raw).strip())
    except Exception as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def _env_flag(name: str) -> bool:
    value = str(os.getenv(name) or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded sanitized Alpaca-only rotation radar activation diagnostic.",
    )
    parser.add_argument(
        "--per-window-timeout",
        type=_positive_float_arg,
        default=None,
        help=f"Override per-window activation timeout seconds; env: {ENV_PER_WINDOW_TIMEOUT}.",
    )
    parser.add_argument(
        "--total-provider-budget",
        type=_positive_float_arg,
        default=None,
        help=f"Override total Alpaca provider budget seconds; env: {ENV_TOTAL_PROVIDER_BUDGET}.",
    )
    parser.add_argument(
        "--bar-fetch-timeout",
        type=_positive_float_arg,
        default=None,
        help=(
            "Override the per-request Alpaca bars timeout seconds; "
            f"env: {ENV_BAR_FETCH_TIMEOUT}. Defaults to --per-window-timeout when that is set."
        ),
    )
    parser.add_argument(
        "--connectivity-check",
        action="store_true",
        help=f"Also run a payload-free Alpaca endpoint reachability check; env: {ENV_CONNECTIVITY_CHECK}=1.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        per_window_timeout = args.per_window_timeout
        if per_window_timeout is None:
            per_window_timeout = _env_positive_float(ENV_PER_WINDOW_TIMEOUT)
        total_provider_budget = args.total_provider_budget
        if total_provider_budget is None:
            total_provider_budget = _env_positive_float(ENV_TOTAL_PROVIDER_BUDGET)
        bar_fetch_timeout = args.bar_fetch_timeout
        if bar_fetch_timeout is None:
            bar_fetch_timeout = _env_positive_float(ENV_BAR_FETCH_TIMEOUT)
    except ValueError as exc:
        parser.error(str(exc))

    connectivity_check = bool(args.connectivity_check or _env_flag(ENV_CONNECTIVITY_CHECK))
    try:
        summary = run_rotation_radar_alpaca_live_smoke(
            per_window_timeout=per_window_timeout,
            total_provider_budget=total_provider_budget,
            bar_fetch_timeout=bar_fetch_timeout,
            connectivity_check=connectivity_check,
        )
    except Exception:
        print(json.dumps(_unexpected_error_summary(), ensure_ascii=False))
        return EXIT_FAILED
    print(json.dumps(summary, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
