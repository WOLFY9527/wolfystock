#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a sanitized Polygon Market Overview activation smoke."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import setup_env
from src.services.polygon_us_breadth_provider import (
    POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
    POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON,
    POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON,
    POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON,
    POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON,
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
    POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON,
    POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD,
    POLYGON_US_BREADTH_REASON_EOD_STALE,
    POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE,
    POLYGON_US_BREADTH_REASON_RESPONSE_INVALID,
    POLYGON_US_BREADTH_REASON_UNAUTHORIZED,
    diagnostic_summary,
    run_polygon_us_breadth_activation,
)
from src.services.us_breadth_contracts import (
    US_BREADTH_MISSING_PROVIDER_REASON,
    US_BREADTH_SYMBOLS,
)

EXIT_OK = 0
EXIT_FAILED = 1
SMOKE_HIGH_LOW_LOOKBACK_SESSIONS = 1

_HIGH_LOW_SYMBOLS = ("NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO")
_HIGH_LOW_REASONS = {
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON,
    POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON,
    POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
    POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON,
    POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON,
    POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON,
}
_MISSING_WINDOW_BY_REASON = {
    POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE: "previous_close_comparison",
    POLYGON_US_BREADTH_REASON_EOD_STALE: "fresh_eod_window",
    POLYGON_US_BREADTH_REASON_RESPONSE_INVALID: "recent_grouped_daily_window",
    **{reason: "high_low_lookback" for reason in _HIGH_LOW_REASONS},
}


def build_market_overview_activation_smoke_output(result: Mapping[str, Any]) -> dict[str, object]:
    """Return the bounded operator-facing Polygon readiness smoke shape."""

    reason_codes = [str(code) for code in result.get("reasonCodes") or [] if str(code)]
    reason = reason_codes[0] if reason_codes else None
    credentials_present = bool(result.get("credentialsPresent"))
    source_authority_allowed = bool(result.get("sourceAuthorityAllowed"))
    score_contribution_allowed = bool(result.get("scoreContributionAllowed"))
    probe_passed = bool(result.get("probePassed"))
    return {
        "credentialsPresent": credentials_present,
        "providerConstructed": bool(result.get("providerConstructed")),
        "probePassed": probe_passed,
        "reason": reason,
        "status": _activation_status(
            reason=reason,
            credentials_present=credentials_present,
            source_authority_allowed=source_authority_allowed,
            score_contribution_allowed=score_contribution_allowed,
            probe_passed=probe_passed,
        ),
        "entitlement": _entitlement_status(reason, credentials_present, probe_passed),
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "missingRequiredSymbols": _missing_required_symbols(result),
        "missingRequiredWindows": _missing_required_windows(result, reason_codes),
    }


def main() -> int:
    try:
        setup_env()
        summary = diagnostic_summary(
            run_polygon_us_breadth_activation(
                high_low_lookback_sessions=SMOKE_HIGH_LOW_LOOKBACK_SESSIONS,
            )
        )
        output = build_market_overview_activation_smoke_output(summary)
    except Exception:
        output = _unexpected_error_output()
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return EXIT_FAILED
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return EXIT_OK


def _activation_status(
    *,
    reason: str | None,
    credentials_present: bool,
    source_authority_allowed: bool,
    score_contribution_allowed: bool,
    probe_passed: bool,
) -> str:
    if not credentials_present or reason == US_BREADTH_MISSING_PROVIDER_REASON:
        return "missing_credentials"
    if reason == POLYGON_US_BREADTH_REASON_UNAUTHORIZED:
        return "unauthorized_or_entitlement_denied"
    if reason == POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD:
        return "insufficient_coverage"
    if reason == POLYGON_US_BREADTH_REASON_EOD_STALE:
        return "stale_eod"
    if reason == POLYGON_US_BREADTH_REASON_RESPONSE_INVALID:
        return "unavailable_or_invalid_response"
    if probe_passed and source_authority_allowed and score_contribution_allowed:
        return "score_ready"
    return "not_score_ready"


def _entitlement_status(
    reason: str | None,
    credentials_present: bool,
    probe_passed: bool,
) -> str:
    if not credentials_present:
        return "not_checked"
    if reason == POLYGON_US_BREADTH_REASON_UNAUTHORIZED:
        return "denied_or_unavailable"
    if probe_passed:
        return "usable_for_grouped_daily"
    return "unknown"


def _missing_required_symbols(result: Mapping[str, Any]) -> list[str]:
    missing = {str(symbol) for symbol in result.get("missingMetrics") or [] if str(symbol)}
    if _uses_bounded_high_low_window(result):
        missing.update(_HIGH_LOW_SYMBOLS)
    return [symbol for symbol in US_BREADTH_SYMBOLS if symbol in missing]


def _missing_required_windows(result: Mapping[str, Any], reason_codes: list[str]) -> list[str]:
    windows = [_MISSING_WINDOW_BY_REASON[reason] for reason in reason_codes if reason in _MISSING_WINDOW_BY_REASON]
    if _uses_bounded_high_low_window(result):
        windows.append("high_low_lookback")
    return list(dict.fromkeys(windows))


def _uses_bounded_high_low_window(result: Mapping[str, Any]) -> bool:
    try:
        probed_sessions = int(result.get("highLowLookbackSessions") or POLYGON_HIGH_LOW_LOOKBACK_SESSIONS)
    except (TypeError, ValueError):
        return False
    return 0 < probed_sessions < POLYGON_HIGH_LOW_LOOKBACK_SESSIONS


def _unexpected_error_output() -> dict[str, object]:
    return {
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "reason": "unexpected_error",
        "status": "unexpected_error",
        "entitlement": "unknown",
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "missingRequiredSymbols": list(US_BREADTH_SYMBOLS),
        "missingRequiredWindows": [],
    }


if __name__ == "__main__":
    raise SystemExit(main())
