#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a sanitized Polygon Market Overview activation smoke."""

from __future__ import annotations

import json
import math
import signal
import sys
from argparse import ArgumentParser
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Any, Iterator, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import setup_env
from src.services.polygon_us_breadth_provider import (
    POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
    POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON,
    POLYGON_HIGH_LOW_HISTORY_DIAGNOSTIC_SESSION_CAP_REASON,
    POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON,
    POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON,
    POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON,
    POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON,
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
    POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON,
    POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD,
    POLYGON_US_BREADTH_REASON_EOD_STALE,
    POLYGON_US_BREADTH_REASON_HTTP_NON_200,
    POLYGON_US_BREADTH_REASON_NO_VALID_OHLC_ROWS,
    POLYGON_US_BREADTH_REASON_PAYLOAD_NOT_MAPPING,
    POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE,
    POLYGON_US_BREADTH_REASON_RESULTS_COUNT_MISSING,
    POLYGON_US_BREADTH_REASON_RESULTS_NOT_LIST,
    POLYGON_US_BREADTH_REASON_RESPONSE_INVALID,
    POLYGON_US_BREADTH_REASON_STATUS_NOT_OK,
    POLYGON_US_BREADTH_REASON_UNAUTHORIZED,
    POLYGON_US_BREADTH_TIMEOUT_SECONDS,
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
HIGH_LOW_METRICS_MISSING_REASON = "high_low_metrics_missing"
HIGH_LOW_DEFAULT_TIMEOUT_BUDGET_SECONDS = 30.0
HIGH_LOW_DEFAULT_PER_REQUEST_TIMEOUT_SECONDS = min(2.0, POLYGON_US_BREADTH_TIMEOUT_SECONDS)
HIGH_LOW_MIN_PER_REQUEST_TIMEOUT_SECONDS = 0.1

_HIGH_LOW_SYMBOLS = ("NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO")
_HIGH_LOW_TIMEOUT_REASONS = {POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON}
_HIGH_LOW_DIAGNOSTIC_CAP_REASONS = {POLYGON_HIGH_LOW_HISTORY_DIAGNOSTIC_SESSION_CAP_REASON}
_HIGH_LOW_REASONS = {
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON,
    POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON,
    POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
    POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON,
    POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON,
    POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON,
    *_HIGH_LOW_TIMEOUT_REASONS,
    *_HIGH_LOW_DIAGNOSTIC_CAP_REASONS,
}
_INVALID_GROUPED_DAILY_REASONS = {
    POLYGON_US_BREADTH_REASON_RESPONSE_INVALID,
    POLYGON_US_BREADTH_REASON_STATUS_NOT_OK,
    POLYGON_US_BREADTH_REASON_HTTP_NON_200,
    POLYGON_US_BREADTH_REASON_RESULTS_COUNT_MISSING,
    POLYGON_US_BREADTH_REASON_RESULTS_NOT_LIST,
    POLYGON_US_BREADTH_REASON_NO_VALID_OHLC_ROWS,
    POLYGON_US_BREADTH_REASON_PAYLOAD_NOT_MAPPING,
}
_MISSING_WINDOW_BY_REASON = {
    POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE: "previous_close_comparison",
    POLYGON_US_BREADTH_REASON_EOD_STALE: "fresh_eod_window",
    **{reason: "recent_grouped_daily_window" for reason in _INVALID_GROUPED_DAILY_REASONS},
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


def build_high_low_lookback_certification_output(result: Mapping[str, Any]) -> dict[str, object]:
    """Return the sanitized full-lookback certification shape."""

    reason_codes = [str(code) for code in result.get("reasonCodes") or [] if str(code)]
    required_sessions = _positive_int(
        result.get("highLowLookbackSessions"),
        default=POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
    )
    fulfilled_sessions = _positive_int(result.get("highLowFulfilledSessions"), default=0)
    timeout_budget_seconds = _positive_float(
        result.get("timeoutBudgetSeconds"),
        default=HIGH_LOW_DEFAULT_TIMEOUT_BUDGET_SECONDS,
        minimum=HIGH_LOW_MIN_PER_REQUEST_TIMEOUT_SECONDS,
    )
    per_request_timeout_seconds = _positive_float(
        result.get("perRequestTimeoutSeconds"),
        default=HIGH_LOW_DEFAULT_PER_REQUEST_TIMEOUT_SECONDS,
        minimum=HIGH_LOW_MIN_PER_REQUEST_TIMEOUT_SECONDS,
    )
    diagnostic_session_cap = _optional_positive_int(result.get("diagnosticSessionCap"))
    missing_symbols = _missing_high_low_symbols(result)
    reason = _high_low_reason(reason_codes) or (reason_codes[0] if reason_codes else None)
    failure_window = _text(result.get("highLowFailureWindow"))
    failed_date = _text(result.get("highLowFailedDate"))
    failed_session_index = _optional_positive_int(result.get("highLowFailedSessionIndex"))
    attempted_sessions = _positive_int(
        result.get("highLowAttemptedSessions"),
        default=fulfilled_sessions,
    )
    if reason is None and missing_symbols:
        reason = HIGH_LOW_METRICS_MISSING_REASON
    lookback_fulfilled = bool(
        required_sessions >= POLYGON_HIGH_LOW_LOOKBACK_SESSIONS
        and fulfilled_sessions >= required_sessions
        and not missing_symbols
        and reason is None
    )
    return {
        "lookbackRequested": True,
        "lookbackFulfilled": lookback_fulfilled,
        "requiredSessions": required_sessions,
        "fulfilledSessions": fulfilled_sessions,
        "missingSymbols": missing_symbols,
        "reason": reason,
        "timeoutBudgetSeconds": timeout_budget_seconds,
        "perRequestTimeoutSeconds": per_request_timeout_seconds,
        "diagnosticSessionCap": diagnostic_session_cap,
        "failureWindow": failure_window or None,
        "failedDate": failed_date or None,
        "failedSessionIndex": failed_session_index,
        "attemptedSessions": attempted_sessions,
        "fulfilledSessionsMeaning": _fulfilled_sessions_meaning(
            reason=reason,
            failure_window=failure_window or None,
            fulfilled_sessions=fulfilled_sessions,
            missing_symbols=missing_symbols,
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    per_request_timeout_seconds = _positive_float(
        args.per_request_timeout_seconds,
        default=HIGH_LOW_DEFAULT_PER_REQUEST_TIMEOUT_SECONDS,
        minimum=HIGH_LOW_MIN_PER_REQUEST_TIMEOUT_SECONDS,
    )
    timeout_budget_seconds = _positive_float(
        args.timeout_budget_seconds,
        default=HIGH_LOW_DEFAULT_TIMEOUT_BUDGET_SECONDS,
        minimum=HIGH_LOW_MIN_PER_REQUEST_TIMEOUT_SECONDS,
    )
    diagnostic_session_cap = _optional_positive_int(args.high_low_max_sessions)
    try:
        setup_env()
        if args.high_low_lookback:
            with _operator_smoke_deadline(timeout_budget_seconds):
                summary = diagnostic_summary(
                    run_polygon_us_breadth_activation(
                        timeout_seconds=per_request_timeout_seconds,
                        high_low_max_history_sessions=diagnostic_session_cap,
                        high_low_timeout_budget_seconds=timeout_budget_seconds,
                    )
                )
            summary.update(
                {
                    "perRequestTimeoutSeconds": per_request_timeout_seconds,
                    "timeoutBudgetSeconds": timeout_budget_seconds,
                    "diagnosticSessionCap": diagnostic_session_cap,
                }
            )
            output = build_high_low_lookback_certification_output(summary)
        else:
            summary = diagnostic_summary(
                run_polygon_us_breadth_activation(
                    high_low_lookback_sessions=SMOKE_HIGH_LOW_LOOKBACK_SESSIONS,
                )
            )
            output = build_market_overview_activation_smoke_output(summary)
    except (_OperatorSmokeTimeout, TimeoutError):
        output = (
            _high_low_failure_output(
                reason="timeout",
                per_request_timeout_seconds=per_request_timeout_seconds,
                timeout_budget_seconds=timeout_budget_seconds,
                diagnostic_session_cap=diagnostic_session_cap,
            )
            if args.high_low_lookback
            else _unexpected_error_output()
        )
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return EXIT_FAILED
    except KeyboardInterrupt:
        output = (
            _high_low_failure_output(
                reason="interrupted",
                per_request_timeout_seconds=per_request_timeout_seconds,
                timeout_budget_seconds=timeout_budget_seconds,
                diagnostic_session_cap=diagnostic_session_cap,
            )
            if args.high_low_lookback
            else _unexpected_error_output()
        )
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return EXIT_FAILED
    except Exception:
        output = (
            _high_low_failure_output(
                reason="unexpected_error",
                per_request_timeout_seconds=per_request_timeout_seconds,
                timeout_budget_seconds=timeout_budget_seconds,
                diagnostic_session_cap=diagnostic_session_cap,
            )
            if args.high_low_lookback
            else _unexpected_error_output()
        )
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return EXIT_FAILED
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return EXIT_OK


def _parse_args(argv: Sequence[str] | None) -> Any:
    parser = ArgumentParser(description="Run sanitized Polygon Market Overview activation diagnostics.")
    parser.add_argument(
        "--high-low-lookback",
        action="store_true",
        help="Probe full 252-session high/low lookback readiness with sanitized counts only.",
    )
    parser.add_argument(
        "--per-request-timeout-seconds",
        default=None,
        help="High/low lookback diagnostic per-request timeout; invalid values use a safe default.",
    )
    parser.add_argument(
        "--timeout-budget-seconds",
        default=None,
        help="High/low lookback diagnostic total timeout budget; invalid values use a safe default.",
    )
    parser.add_argument(
        "--high-low-max-sessions",
        default=None,
        help="Optional diagnostic cap for high/low historical sessions; invalid values leave it uncapped.",
    )
    return parser.parse_args(argv)


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
    if reason in _INVALID_GROUPED_DAILY_REASONS:
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


def _missing_high_low_symbols(result: Mapping[str, Any]) -> list[str]:
    missing = {str(symbol) for symbol in result.get("missingMetrics") or [] if str(symbol)}
    return [symbol for symbol in _HIGH_LOW_SYMBOLS if symbol in missing]


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


def _high_low_reason(reason_codes: list[str]) -> str | None:
    for reason in reason_codes:
        if reason in _HIGH_LOW_TIMEOUT_REASONS:
            return "timeout"
        if reason in _HIGH_LOW_DIAGNOSTIC_CAP_REASONS:
            return "diagnostic_session_cap"
        if reason in _HIGH_LOW_REASONS:
            return reason
    return None


def _fulfilled_sessions_meaning(
    *,
    reason: str | None,
    failure_window: str | None,
    fulfilled_sessions: int,
    missing_symbols: Sequence[str],
) -> str:
    if fulfilled_sessions <= 0:
        return "no_history_sessions_collected"
    if reason == "diagnostic_session_cap":
        return "successful_history_sessions_collected_before_diagnostic_cap"
    if failure_window == "high_low_lookback_session" and (reason is not None or missing_symbols):
        return "successful_history_sessions_collected_before_failure"
    return "successful_history_sessions_collected"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _positive_float(value: Any, *, default: float, minimum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(parsed) or parsed <= 0:
        return float(default)
    return max(float(minimum), parsed)


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


class _OperatorSmokeTimeout(Exception):
    pass


@contextmanager
def _operator_smoke_deadline(timeout_budget_seconds: float) -> Iterator[None]:
    if not hasattr(signal, "setitimer") or not hasattr(signal, "SIGALRM"):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _raise_timeout(signum: int, frame: FrameType | None) -> None:
        raise _OperatorSmokeTimeout("polygon high/low smoke timeout budget exceeded")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_budget_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


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


def _high_low_failure_output(
    *,
    reason: str,
    per_request_timeout_seconds: float,
    timeout_budget_seconds: float,
    diagnostic_session_cap: int | None,
) -> dict[str, object]:
    return {
        "lookbackRequested": True,
        "lookbackFulfilled": False,
        "requiredSessions": POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
        "fulfilledSessions": 0,
        "missingSymbols": list(_HIGH_LOW_SYMBOLS),
        "reason": reason,
        "timeoutBudgetSeconds": timeout_budget_seconds,
        "perRequestTimeoutSeconds": per_request_timeout_seconds,
        "diagnosticSessionCap": diagnostic_session_cap,
        "failureWindow": None,
        "failedDate": None,
        "failedSessionIndex": None,
        "attemptedSessions": 0,
        "fulfilledSessionsMeaning": "no_history_sessions_collected",
    }


if __name__ == "__main__":
    raise SystemExit(main())
