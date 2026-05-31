# -*- coding: utf-8 -*-
"""Polygon grouped-daily computed US breadth adapter.

This module reads only ``POLYGON_API_KEY`` and computes EOD advance/decline
breadth from Polygon's full-market grouped daily endpoint. It does not expose
secrets, does not call the Polygon snapshot endpoint, and does not fabricate
new-high/new-low metrics without a historical lookback.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from src.utils.dotenv_loader import read_dotenv_values
from src.services.us_breadth_contracts import (
    US_BREADTH_MISSING_PROVIDER_REASON,
    US_BREADTH_SYMBOLS,
)


POLYGON_US_EASTERN_TZ = ZoneInfo("America/New_York")
POLYGON_US_BREADTH_SOURCE = "polygon_us_grouped_daily"
POLYGON_US_BREADTH_SOURCE_LABEL = "Polygon grouped daily US equities (computed breadth)"
POLYGON_US_BREADTH_SOURCE_TYPE = "authorized_licensed_feed"
POLYGON_US_BREADTH_SOURCE_TIER = "official_or_authorized_licensed_feed"
POLYGON_US_BREADTH_TRUST_LEVEL = "score_grade_for_computed_ad_metrics_when_fresh"
POLYGON_US_BREADTH_AUTHORITY_BASIS = "computed_from_authorized_polygon_history"
POLYGON_US_BREADTH_UNIVERSE = "polygon_us_grouped_daily_ex_otc"
POLYGON_US_BREADTH_ENDPOINT_TEMPLATE = (
    "https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date}"
)
POLYGON_US_BREADTH_TIMEOUT_SECONDS = 4.0
POLYGON_US_BREADTH_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
POLYGON_US_BREADTH_RECENT_DATE_LIMIT = 4
POLYGON_US_BREADTH_MIN_COVERAGE_COUNT = 8000
POLYGON_US_BREADTH_MAX_CALENDAR_LAG_DAYS = 4
POLYGON_US_BREADTH_MAX_BUSINESS_LAG_DAYS = 2
POLYGON_HIGH_LOW_LOOKBACK_SESSIONS = 252
POLYGON_HIGH_LOW_MIN_ELIGIBLE_COUNT = 8000

POLYGON_US_BREADTH_REASON_UNAUTHORIZED = "polygon_unauthorized"
POLYGON_US_BREADTH_REASON_RESPONSE_INVALID = "polygon_response_invalid"
POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD = "polygon_coverage_below_threshold"
POLYGON_US_BREADTH_REASON_EOD_STALE = "polygon_eod_stale"
POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE = "polygon_previous_close_unavailable"
POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON = "polygon_high_low_history_unavailable"
POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON = "polygon_high_low_history_malformed"
POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON = "polygon_high_low_history_mixed_source"
POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON = "polygon_high_low_history_insufficient_lookback"
POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON = "polygon_high_low_history_date_gap"
POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON = "polygon_high_low_history_below_threshold"
POLYGON_HIGH_LOW_HISTORY_DIAGNOSTIC_SESSION_CAP_REASON = "polygon_high_low_history_diagnostic_session_cap"
POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON = "polygon_high_low_history_timeout"
POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON = "polygon_high_low_ratio_unavailable"
_POLYGON_TRANSPORT_REASON_KEY = "_polygonTransportReason"

_AD_FULFILLED_METRICS = (
    "ADVANCERS",
    "DECLINERS",
    "UNCHANGED",
    "ADVANCE_DECLINE_RATIO",
)
_HIGH_LOW_METRICS = ("NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO")
_EPSILON = 1e-12

PolygonTransport = Callable[[str, str, float], tuple[int, Mapping[str, Any] | None]]


@dataclass(frozen=True, slots=True)
class _GroupedDailyRow:
    ticker: str
    open_price: float
    close_price: float
    high_price: float | None = None
    low_price: float | None = None


@dataclass(frozen=True, slots=True)
class _ParsedGroupedDaily:
    ok: bool
    results_count: int
    rows: tuple[_GroupedDailyRow, ...]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class _HighLowComputation:
    ok: bool
    new_highs: int | None = None
    new_lows: int | None = None
    high_low_ratio: float | None = None
    fulfilled_sessions: int = 0
    eligible_count: int = 0
    eligible_threshold: int = 0
    lookback_sessions: int = POLYGON_HIGH_LOW_LOOKBACK_SESSIONS
    reason: str | None = None


def run_polygon_us_breadth_activation(
    *,
    api_key: str | None = None,
    transport: PolygonTransport | None = None,
    now: datetime | None = None,
    min_coverage_count: int = POLYGON_US_BREADTH_MIN_COVERAGE_COUNT,
    high_low_lookback_sessions: int = POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
    min_high_low_eligible_count: int = POLYGON_HIGH_LOW_MIN_ELIGIBLE_COUNT,
    timeout_seconds: float = POLYGON_US_BREADTH_TIMEOUT_SECONDS,
    high_low_max_history_sessions: int | None = None,
    high_low_timeout_budget_seconds: float | None = None,
) -> dict[str, Any]:
    """Fetch recent grouped daily rows and return a sanitized activation summary."""

    credential = _text(api_key) if api_key is not None else _polygon_api_key()
    if not credential:
        return _fail_closed_summary(
            reason_codes=(US_BREADTH_MISSING_PROVIDER_REASON,),
            credentials_present=False,
            provider_constructed=False,
        )

    required_lookback_sessions = _positive_int_or_default(
        high_low_lookback_sessions,
        default=POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
    )
    request_timeout_seconds = _positive_float_or_default(
        timeout_seconds,
        default=POLYGON_US_BREADTH_TIMEOUT_SECONDS,
        minimum=0.1,
    )
    diagnostic_session_cap = _optional_positive_int(high_low_max_history_sessions)
    history_session_limit = (
        min(required_lookback_sessions, diagnostic_session_cap)
        if diagnostic_session_cap is not None
        else required_lookback_sessions
    )
    timeout_budget_seconds = _optional_positive_float(high_low_timeout_budget_seconds)
    started_at = monotonic() if timeout_budget_seconds is not None else None
    diagnostic_controls_enabled = diagnostic_session_cap is not None or timeout_budget_seconds is not None

    fetch = transport or _default_polygon_transport
    fetched_payloads: dict[str, tuple[int, Mapping[str, Any] | None]] = {}

    def fetch_grouped_daily(candidate_date: str) -> tuple[int, Mapping[str, Any] | None]:
        if candidate_date not in fetched_payloads:
            try:
                fetched_payloads[candidate_date] = fetch(candidate_date, credential, request_timeout_seconds)
            except (TimeoutError, URLError, OSError):
                fetched_payloads[candidate_date] = (
                    0,
                    {_POLYGON_TRANSPORT_REASON_KEY: POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON},
                )
        return fetched_payloads[candidate_date]

    def high_low_budget_expired() -> bool:
        return bool(
            started_at is not None
            and timeout_budget_seconds is not None
            and monotonic() - started_at >= timeout_budget_seconds
        )

    candidates = recent_completed_us_trading_dates(now=now)
    latest_payload: Mapping[str, Any] | None = None
    latest_date: str | None = None
    latest_reason = POLYGON_US_BREADTH_REASON_RESPONSE_INVALID
    latest_index = -1

    for index, candidate in enumerate(candidates):
        if diagnostic_controls_enabled and high_low_budget_expired():
            latest_reason = POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON
            break
        status_code, payload = fetch_grouped_daily(candidate)
        if status_code in {401, 403}:
            return _fail_closed_summary(
                reason_codes=(POLYGON_US_BREADTH_REASON_UNAUTHORIZED,),
                credentials_present=True,
                provider_constructed=True,
                observation_date=candidate,
            )
        transport_reason = _transport_failure_reason(payload)
        if status_code == 0 and diagnostic_controls_enabled and transport_reason:
            latest_reason = transport_reason
            break
        parsed = parse_polygon_grouped_daily_payload(payload)
        if status_code == 200 and parsed.ok:
            latest_payload = payload
            latest_date = candidate
            latest_index = index
            break
        latest_reason = parsed.reason or POLYGON_US_BREADTH_REASON_RESPONSE_INVALID

    if latest_payload is None or latest_date is None:
        return _fail_closed_summary(
            reason_codes=(latest_reason,),
            credentials_present=True,
            provider_constructed=True,
        )

    previous_payload: Mapping[str, Any] | None = None
    previous_date: str | None = None
    for candidate in candidates[latest_index + 1 :]:
        if diagnostic_controls_enabled and high_low_budget_expired():
            return _fail_closed_summary(
                reason_codes=(POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON,),
                credentials_present=True,
                provider_constructed=True,
                observation_date=latest_date,
            )
        status_code, payload = fetch_grouped_daily(candidate)
        transport_reason = _transport_failure_reason(payload)
        if status_code == 0 and diagnostic_controls_enabled and transport_reason:
            return _fail_closed_summary(
                reason_codes=(transport_reason,),
                credentials_present=True,
                provider_constructed=True,
                observation_date=latest_date,
            )
        if status_code != 200:
            continue
        parsed = parse_polygon_grouped_daily_payload(payload)
        if parsed.ok:
            previous_payload = payload
            previous_date = candidate
            break

    historical_payloads: tuple[tuple[str, Mapping[str, Any] | None], ...] | None = None
    high_low_diagnostic_reason: str | None = None
    high_low_diagnostic_fulfilled_sessions: int | None = None
    if previous_payload is not None and previous_date:
        history_items: list[tuple[str, Mapping[str, Any] | None]] = []
        successful_history_sessions = 0
        for history_date in prior_completed_us_trading_dates(
            latest_date,
            limit=history_session_limit,
        ):
            if diagnostic_controls_enabled and high_low_budget_expired():
                high_low_diagnostic_reason = POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON
                break
            status_code, payload = fetch_grouped_daily(history_date)
            transport_reason = _transport_failure_reason(payload)
            if status_code == 0 and diagnostic_controls_enabled and transport_reason:
                high_low_diagnostic_reason = transport_reason
                break
            if status_code == 200:
                successful_history_sessions += 1
            history_items.append((history_date, payload if status_code == 200 else None))
        historical_payloads = tuple(history_items)
        high_low_diagnostic_fulfilled_sessions = successful_history_sessions
        if (
            high_low_diagnostic_reason is None
            and diagnostic_session_cap is not None
            and history_session_limit < required_lookback_sessions
        ):
            high_low_diagnostic_reason = POLYGON_HIGH_LOW_HISTORY_DIAGNOSTIC_SESSION_CAP_REASON

    result = compute_polygon_us_breadth(
        latest_payload,
        previous_payload=previous_payload,
        historical_payloads=historical_payloads,
        observation_date=latest_date,
        previous_observation_date=previous_date,
        now=now,
        min_coverage_count=min_coverage_count,
        high_low_lookback_sessions=required_lookback_sessions,
        min_high_low_eligible_count=min_high_low_eligible_count,
        credentials_present=True,
        provider_constructed=True,
    )
    if not diagnostic_controls_enabled:
        return result
    return _apply_high_low_diagnostics(
        result,
        diagnostic_reason=high_low_diagnostic_reason,
        fulfilled_sessions=high_low_diagnostic_fulfilled_sessions,
        session_cap=diagnostic_session_cap,
        timeout_budget_seconds=timeout_budget_seconds,
        per_request_timeout_seconds=request_timeout_seconds,
    )


def compute_polygon_us_breadth(
    payload: Mapping[str, Any] | None,
    *,
    previous_payload: Mapping[str, Any] | None = None,
    historical_payloads: (
        Mapping[str, Mapping[str, Any] | None]
        | Sequence[tuple[str, Mapping[str, Any] | None]]
        | None
    ) = None,
    observation_date: str,
    previous_observation_date: str | None = None,
    now: datetime | None = None,
    min_coverage_count: int = POLYGON_US_BREADTH_MIN_COVERAGE_COUNT,
    high_low_lookback_sessions: int = POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
    min_high_low_eligible_count: int = POLYGON_HIGH_LOW_MIN_ELIGIBLE_COUNT,
    credentials_present: bool = True,
    provider_constructed: bool = True,
) -> dict[str, Any]:
    """Compute score-eligible AD breadth when freshness and coverage gates pass."""

    coverage_threshold = max(1, int(min_coverage_count))
    parsed = parse_polygon_grouped_daily_payload(payload)
    if not parsed.ok:
        return _fail_closed_summary(
            reason_codes=(parsed.reason or POLYGON_US_BREADTH_REASON_RESPONSE_INVALID,),
            credentials_present=credentials_present,
            provider_constructed=provider_constructed,
            observation_date=observation_date,
            coverage_threshold=coverage_threshold,
        )

    coverage_count = len(parsed.rows)
    if coverage_count < coverage_threshold:
        return _fail_closed_summary(
            reason_codes=(POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD,),
            credentials_present=credentials_present,
            provider_constructed=provider_constructed,
            observation_date=observation_date,
            coverage_count=coverage_count,
            coverage_threshold=coverage_threshold,
        )

    freshness = polygon_eod_freshness(observation_date, now=now)
    if not freshness["freshnessValid"]:
        return _fail_closed_summary(
            reason_codes=(POLYGON_US_BREADTH_REASON_EOD_STALE,),
            credentials_present=credentials_present,
            provider_constructed=provider_constructed,
            observation_date=observation_date,
            coverage_count=coverage_count,
            coverage_threshold=coverage_threshold,
            freshness_valid=False,
        )

    comparison = parse_polygon_grouped_daily_payload(previous_payload)
    previous_close_by_ticker = {row.ticker: row.close_price for row in comparison.rows} if comparison.ok else {}
    previous_coverage_count = len(comparison.rows) if comparison.ok else 0
    matched_rows = tuple(row for row in parsed.rows if row.ticker in previous_close_by_ticker)
    comparison_coverage_count = len(matched_rows) if previous_observation_date and comparison.ok else 0
    previous_close_available = bool(
        previous_observation_date
        and comparison.ok
        and previous_coverage_count >= coverage_threshold
        and comparison_coverage_count >= coverage_threshold
    )
    rows_for_comparison = matched_rows if previous_close_available else parsed.rows
    comparison_basis = "previous_close" if previous_close_available else "open_close"

    advancers = 0
    decliners = 0
    unchanged = 0
    for row in rows_for_comparison:
        comparison_price = previous_close_by_ticker[row.ticker] if previous_close_available else row.open_price
        if row.close_price > comparison_price + _EPSILON:
            advancers += 1
        elif row.close_price < comparison_price - _EPSILON:
            decliners += 1
        else:
            unchanged += 1

    ad_ratio = round(advancers / decliners, 3) if decliners > 0 else None
    high_low = (
        _compute_polygon_high_low_breadth(
            parsed.rows,
            historical_payloads=historical_payloads,
            observation_date=observation_date,
            coverage_threshold=coverage_threshold,
            lookback_sessions=high_low_lookback_sessions,
            min_eligible_count=min_high_low_eligible_count,
        )
        if previous_close_available
        else _HighLowComputation(
            ok=False,
            reason=POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
            lookback_sessions=max(1, int(high_low_lookback_sessions)),
            eligible_threshold=max(1, int(min_high_low_eligible_count)),
        )
    )
    fulfilled_metrics = (
        list(_AD_FULFILLED_METRICS if ad_ratio is not None else _AD_FULFILLED_METRICS[:-1])
        if previous_close_available
        else []
    )
    if high_low.ok:
        fulfilled_metrics.extend(["NEW_HIGHS", "NEW_LOWS"])
        if high_low.high_low_ratio is not None:
            fulfilled_metrics.append("HIGH_LOW_RATIO")
    missing_metrics = [
        symbol
        for symbol in US_BREADTH_SYMBOLS
        if symbol not in fulfilled_metrics
    ]
    reason_codes: list[str] = []
    if not previous_close_available:
        reason_codes.append(POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE)
    if ad_ratio is None:
        reason_codes.append(POLYGON_US_BREADTH_REASON_RESPONSE_INVALID)
    if high_low.reason:
        reason_codes.append(high_low.reason)

    source_metadata_valid = _source_metadata_valid()
    authority_allowed = bool(
        credentials_present
        and provider_constructed
        and parsed.ok
        and previous_close_available
        and coverage_count >= coverage_threshold
        and comparison_coverage_count >= coverage_threshold
        and freshness["freshnessValid"]
        and source_metadata_valid
        and ad_ratio is not None
    )
    score_allowed = bool(authority_allowed and fulfilled_metrics)
    broad_market_claim_allowed = False
    metrics = {
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "advanceDeclineRatio": ad_ratio,
        "newHighs": high_low.new_highs if high_low.ok else None,
        "newLows": high_low.new_lows if high_low.ok else None,
        "highLowRatio": high_low.high_low_ratio if high_low.ok else None,
    }
    return {
        "credentialsPresent": credentials_present,
        "providerConstructed": provider_constructed,
        "probePassed": authority_allowed,
        "observationDate": observation_date,
        "previousObservationDate": previous_observation_date if previous_close_available else None,
        "comparisonBasis": comparison_basis,
        "asOf": observation_date,
        "freshnessValid": bool(freshness["freshnessValid"]),
        "freshnessPolicy": freshness,
        "coverageCount": coverage_count,
        "previousCoverageCount": previous_coverage_count,
        "comparisonCoverageCount": comparison_coverage_count,
        "rawResultsCount": parsed.results_count,
        "coverageThreshold": coverage_threshold,
        "highLowLookbackSessions": high_low.lookback_sessions,
        "highLowFulfilledSessions": high_low.fulfilled_sessions,
        "highLowEligibleCount": high_low.eligible_count,
        "highLowEligibleThreshold": high_low.eligible_threshold,
        "sourceMetadataValid": source_metadata_valid,
        "sourceAuthorityAllowed": authority_allowed,
        "scoreContributionAllowed": score_allowed,
        "broadMarketClaimAllowed": broad_market_claim_allowed,
        "officialExchangePublishedBreadth": False,
        "fullBreadthAuthority": False,
        "observationOnly": not score_allowed,
        "fulfilledMetrics": fulfilled_metrics,
        "missingMetrics": missing_metrics,
        "reasonCodes": reason_codes,
        "metrics": metrics,
        "source": POLYGON_US_BREADTH_SOURCE,
        "sourceLabel": POLYGON_US_BREADTH_SOURCE_LABEL,
        "sourceType": POLYGON_US_BREADTH_SOURCE_TYPE,
        "sourceTier": POLYGON_US_BREADTH_SOURCE_TIER,
        "trustLevel": POLYGON_US_BREADTH_TRUST_LEVEL,
        "authorityBasis": POLYGON_US_BREADTH_AUTHORITY_BASIS,
        "universe": POLYGON_US_BREADTH_UNIVERSE,
        "adjusted": True,
        "includeOtc": False,
    }


def parse_polygon_grouped_daily_payload(payload: Mapping[str, Any] | None) -> _ParsedGroupedDaily:
    """Strictly parse Polygon grouped-daily payloads into valid OHLC rows."""

    if not isinstance(payload, Mapping):
        return _ParsedGroupedDaily(False, 0, (), POLYGON_US_BREADTH_REASON_RESPONSE_INVALID)
    status = _text(payload.get("status")).upper()
    if status != "OK":
        return _ParsedGroupedDaily(False, 0, (), POLYGON_US_BREADTH_REASON_RESPONSE_INVALID)
    results_count = _parse_int(payload.get("resultsCount"))
    results = payload.get("results")
    if results_count is None or not isinstance(results, list):
        return _ParsedGroupedDaily(False, 0, (), POLYGON_US_BREADTH_REASON_RESPONSE_INVALID)

    rows: list[_GroupedDailyRow] = []
    for item in results:
        if not isinstance(item, Mapping):
            continue
        ticker = _text(item.get("T") or item.get("ticker")).upper()
        open_price = _parse_finite_float(_first_present(item, "o", "open"))
        close_price = _parse_finite_float(_first_present(item, "c", "close"))
        high_price = _parse_finite_float(_first_present(item, "h", "high"))
        low_price = _parse_finite_float(_first_present(item, "l", "low"))
        if not ticker or open_price is None or close_price is None:
            continue
        rows.append(
            _GroupedDailyRow(
                ticker=ticker,
                open_price=open_price,
                close_price=close_price,
                high_price=high_price,
                low_price=low_price,
            )
        )

    return _ParsedGroupedDaily(True, int(results_count), tuple(rows))


def recent_completed_us_trading_dates(
    *,
    now: datetime | None = None,
    limit: int = POLYGON_US_BREADTH_RECENT_DATE_LIMIT,
) -> tuple[str, ...]:
    """Return recent completed US weekdays; holidays are intentionally not modeled."""

    current = (now or datetime.now(POLYGON_US_EASTERN_TZ)).astimezone(POLYGON_US_EASTERN_TZ)
    cursor = current.date()
    if current.hour < 18:
        cursor -= timedelta(days=1)

    dates: list[str] = []
    while len(dates) < max(1, int(limit)):
        if cursor.weekday() < 5:
            dates.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    return tuple(dates)


def prior_completed_us_trading_dates(
    observation_date: str,
    *,
    limit: int = POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
) -> tuple[str, ...]:
    """Return completed US weekdays before an observation date."""

    parsed = _parse_date(observation_date)
    if parsed is None:
        return ()
    cursor = parsed - timedelta(days=1)
    dates: list[str] = []
    while len(dates) < max(1, int(limit)):
        if cursor.weekday() < 5:
            dates.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    return tuple(dates)


def polygon_eod_freshness(observation_date: str, *, now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(POLYGON_US_EASTERN_TZ)).astimezone(POLYGON_US_EASTERN_TZ).date()
    parsed = _parse_date(observation_date)
    if parsed is None:
        return {
            "freshnessValid": False,
            "reason": POLYGON_US_BREADTH_REASON_RESPONSE_INVALID,
        }
    calendar_lag_days = max(0, (current - parsed).days)
    business_lag_days = _business_lag_days(parsed, current)
    accepted = (
        calendar_lag_days <= POLYGON_US_BREADTH_MAX_CALENDAR_LAG_DAYS
        and business_lag_days <= POLYGON_US_BREADTH_MAX_BUSINESS_LAG_DAYS
    )
    return {
        "freshnessValid": accepted,
        "freshnessPolicy": "polygon_grouped_daily_eod_recent_completed_us_weekday",
        "calendarAssumption": "US/Eastern weekdays; exchange holidays not modeled",
        "maxAcceptedLagDays": POLYGON_US_BREADTH_MAX_CALENDAR_LAG_DAYS,
        "maxAcceptedBusinessLagDays": POLYGON_US_BREADTH_MAX_BUSINESS_LAG_DAYS,
        "calendarLagDays": calendar_lag_days,
        "businessLagDays": business_lag_days,
        "freshnessDecision": "accepted" if accepted else "stale",
        "staleReason": None if accepted else POLYGON_US_BREADTH_REASON_EOD_STALE,
    }


def _compute_polygon_high_low_breadth(
    latest_rows: Sequence[_GroupedDailyRow],
    *,
    historical_payloads: (
        Mapping[str, Mapping[str, Any] | None]
        | Sequence[tuple[str, Mapping[str, Any] | None]]
        | None
    ),
    observation_date: str,
    coverage_threshold: int,
    lookback_sessions: int,
    min_eligible_count: int,
) -> _HighLowComputation:
    lookback = max(1, int(lookback_sessions))
    absolute_floor = max(1, int(min_eligible_count))
    eligible_threshold = max(absolute_floor, math.ceil(0.8 * len(latest_rows)))
    base = {
        "eligible_threshold": eligible_threshold,
        "lookback_sessions": lookback,
    }
    history_items = _normalize_historical_payloads(historical_payloads)
    if not history_items:
        return _HighLowComputation(
            ok=False,
            reason=POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
            **base,
        )
    if len(history_items) < lookback:
        return _HighLowComputation(
            ok=False,
            reason=POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON,
            **base,
        )

    lookback_items = history_items[:lookback]
    expected_dates = prior_completed_us_trading_dates(observation_date, limit=lookback)
    actual_dates = tuple(history_date for history_date, _ in lookback_items)
    if not expected_dates or actual_dates != expected_dates:
        fulfilled_sessions = _count_matching_prefix(expected_dates, actual_dates)
        return _HighLowComputation(
            ok=False,
            fulfilled_sessions=fulfilled_sessions,
            reason=POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON,
            **base,
        )

    history_by_date: list[dict[str, _GroupedDailyRow]] = []
    fulfilled_sessions = 0
    for _, history_payload in lookback_items:
        if history_payload is None:
            return _HighLowComputation(
                ok=False,
                fulfilled_sessions=fulfilled_sessions,
                reason=POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
                **base,
            )
        if not _history_source_valid(history_payload):
            return _HighLowComputation(
                ok=False,
                fulfilled_sessions=fulfilled_sessions,
                reason=POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON,
                **base,
            )
        parsed_history = parse_polygon_grouped_daily_payload(history_payload)
        if not parsed_history.ok:
            return _HighLowComputation(
                ok=False,
                fulfilled_sessions=fulfilled_sessions,
                reason=POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON,
                **base,
            )
        if len(parsed_history.rows) < coverage_threshold:
            return _HighLowComputation(
                ok=False,
                fulfilled_sessions=fulfilled_sessions,
                reason=POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
                **base,
            )
        history_by_date.append(
            {
                row.ticker: row
                for row in parsed_history.rows
                if row.high_price is not None and row.low_price is not None
            }
        )
        fulfilled_sessions += 1

    latest_by_ticker = {
        row.ticker: row
        for row in latest_rows
        if row.high_price is not None and row.low_price is not None
    }
    eligible_count = 0
    new_highs = 0
    new_lows = 0
    for ticker, latest in latest_by_ticker.items():
        prior_rows = [history_rows.get(ticker) for history_rows in history_by_date]
        if any(row is None for row in prior_rows):
            continue
        prior_highs = [row.high_price for row in prior_rows if row and row.high_price is not None]
        prior_lows = [row.low_price for row in prior_rows if row and row.low_price is not None]
        if len(prior_highs) < lookback or len(prior_lows) < lookback:
            continue
        eligible_count += 1
        if latest.high_price is not None and latest.high_price >= max(prior_highs) - _EPSILON:
            new_highs += 1
        if latest.low_price is not None and latest.low_price <= min(prior_lows) + _EPSILON:
            new_lows += 1

    if eligible_count < eligible_threshold:
        return _HighLowComputation(
            ok=False,
            fulfilled_sessions=fulfilled_sessions,
            eligible_count=eligible_count,
            reason=POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
            **base,
        )

    high_low_ratio = round(new_highs / new_lows, 3) if new_lows > 0 else None
    return _HighLowComputation(
        ok=True,
        new_highs=new_highs,
        new_lows=new_lows,
        high_low_ratio=high_low_ratio,
        fulfilled_sessions=fulfilled_sessions,
        eligible_count=eligible_count,
        reason=None if high_low_ratio is not None else POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON,
        **base,
    )


def _normalize_historical_payloads(
    historical_payloads: (
        Mapping[str, Mapping[str, Any] | None]
        | Sequence[tuple[str, Mapping[str, Any] | None]]
        | None
    ),
) -> tuple[tuple[str, Mapping[str, Any] | None], ...]:
    if historical_payloads is None:
        return ()
    if isinstance(historical_payloads, Mapping):
        return tuple(
            (str(history_date), payload)
            for history_date, payload in sorted(historical_payloads.items(), reverse=True)
        )
    return tuple((str(history_date), payload) for history_date, payload in historical_payloads)


def _history_source_valid(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return True
    source = _text(payload.get("source") or payload.get("sourceId") or payload.get("provider"))
    return not source or source == POLYGON_US_BREADTH_SOURCE


def _count_matching_prefix(expected_dates: Sequence[str], actual_dates: Sequence[str]) -> int:
    count = 0
    for expected, actual in zip(expected_dates, actual_dates):
        if expected != actual:
            break
        count += 1
    return count


def diagnostic_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return the bounded JSON shape used by the operator diagnostic script."""

    summary = {
        "credentialsPresent": bool(result.get("credentialsPresent")),
        "providerConstructed": bool(result.get("providerConstructed")),
        "probePassed": bool(result.get("probePassed")),
        "observationDate": result.get("observationDate"),
        "previousObservationDate": result.get("previousObservationDate"),
        "comparisonBasis": result.get("comparisonBasis"),
        "freshnessValid": bool(result.get("freshnessValid")),
        "coverageCount": int(result.get("coverageCount") or 0),
        "previousCoverageCount": int(result.get("previousCoverageCount") or 0),
        "comparisonCoverageCount": int(result.get("comparisonCoverageCount") or 0),
        "coverageThreshold": int(result.get("coverageThreshold") or 0),
        "highLowLookbackSessions": int(result.get("highLowLookbackSessions") or 0),
        "highLowFulfilledSessions": int(result.get("highLowFulfilledSessions") or 0),
        "highLowEligibleCount": int(result.get("highLowEligibleCount") or 0),
        "highLowEligibleThreshold": int(result.get("highLowEligibleThreshold") or 0),
        "sourceMetadataValid": bool(result.get("sourceMetadataValid")),
        "sourceAuthorityAllowed": bool(result.get("sourceAuthorityAllowed")),
        "scoreContributionAllowed": bool(result.get("scoreContributionAllowed")),
        "broadMarketClaimAllowed": bool(result.get("broadMarketClaimAllowed")),
        "officialExchangePublishedBreadth": bool(result.get("officialExchangePublishedBreadth")),
        "fullBreadthAuthority": bool(result.get("fullBreadthAuthority")),
        "fulfilledMetrics": list(result.get("fulfilledMetrics") or []),
        "missingMetrics": list(result.get("missingMetrics") or []),
        "reasonCodes": list(result.get("reasonCodes") or []),
    }
    for key in (
        "perRequestTimeoutSeconds",
        "timeoutBudgetSeconds",
        "diagnosticSessionCap",
    ):
        if key in result:
            summary[key] = result.get(key)
    return summary


def _apply_high_low_diagnostics(
    result: Mapping[str, Any],
    *,
    diagnostic_reason: str | None,
    fulfilled_sessions: int | None,
    session_cap: int | None,
    timeout_budget_seconds: float | None,
    per_request_timeout_seconds: float,
) -> dict[str, Any]:
    updated = dict(result)
    updated["perRequestTimeoutSeconds"] = per_request_timeout_seconds
    updated["timeoutBudgetSeconds"] = timeout_budget_seconds
    updated["diagnosticSessionCap"] = session_cap
    if diagnostic_reason:
        updated["highLowFulfilledSessions"] = max(0, int(fulfilled_sessions or 0))
        updated["reasonCodes"] = _replace_high_low_reason_codes(
            result.get("reasonCodes") or [],
            diagnostic_reason,
        )
        missing_metrics = list(result.get("missingMetrics") or [])
        for metric in _HIGH_LOW_METRICS:
            if metric not in missing_metrics:
                missing_metrics.append(metric)
        updated["missingMetrics"] = missing_metrics
    return updated


def _replace_high_low_reason_codes(reason_codes: Sequence[Any], replacement: str) -> list[str]:
    replaced: list[str] = []
    inserted = False
    for raw_reason in reason_codes:
        reason = str(raw_reason)
        if reason in {
            POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
            POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON,
            POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON,
            POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON,
            POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON,
            POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
            POLYGON_HIGH_LOW_HISTORY_DIAGNOSTIC_SESSION_CAP_REASON,
            POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON,
            POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON,
        }:
            if not inserted:
                replaced.append(replacement)
                inserted = True
            continue
        replaced.append(reason)
    if not inserted:
        replaced.append(replacement)
    return replaced


def _transport_failure_reason(payload: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    reason = _text(payload.get(_POLYGON_TRANSPORT_REASON_KEY))
    return reason or None


def _default_polygon_transport(
    observation_date: str,
    api_key: str,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, Any] | None]:
    query = urlencode({
        "adjusted": "true",
        "include_otc": "false",
        "apiKey": api_key,
    })
    url = f"{POLYGON_US_BREADTH_ENDPOINT_TEMPLATE.format(date=observation_date)}?{query}"
    request = Request(url, headers={"User-Agent": "WolfyStock Polygon US breadth diagnostic"})
    try:
        with urlopen(request, timeout=max(0.1, float(timeout_seconds))) as response:
            raw = response.read(POLYGON_US_BREADTH_MAX_RESPONSE_BYTES + 1)
            if len(raw) > POLYGON_US_BREADTH_MAX_RESPONSE_BYTES:
                return int(response.status), None
            return int(response.status), _parse_json_bytes(raw)
    except HTTPError as exc:
        raw = exc.read(POLYGON_US_BREADTH_MAX_RESPONSE_BYTES + 1)
        payload = _parse_json_bytes(raw) if raw else None
        return int(exc.code), payload
    except TimeoutError:
        return 0, {_POLYGON_TRANSPORT_REASON_KEY: POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON}
    except URLError as exc:
        if isinstance(getattr(exc, "reason", None), TimeoutError):
            return 0, {_POLYGON_TRANSPORT_REASON_KEY: POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON}
        return 0, None
    except (OSError, ValueError, json.JSONDecodeError):
        return 0, None


def _fail_closed_summary(
    *,
    reason_codes: tuple[str, ...],
    credentials_present: bool,
    provider_constructed: bool,
    observation_date: str | None = None,
    coverage_count: int = 0,
    coverage_threshold: int = 0,
    freshness_valid: bool = False,
) -> dict[str, Any]:
    return {
        "credentialsPresent": credentials_present,
        "providerConstructed": provider_constructed,
        "probePassed": False,
        "observationDate": observation_date,
        "previousObservationDate": None,
        "comparisonBasis": None,
        "asOf": observation_date,
        "freshnessValid": freshness_valid,
        "coverageCount": coverage_count,
        "previousCoverageCount": 0,
        "comparisonCoverageCount": 0,
        "coverageThreshold": coverage_threshold,
        "highLowLookbackSessions": POLYGON_HIGH_LOW_LOOKBACK_SESSIONS,
        "highLowFulfilledSessions": 0,
        "highLowEligibleCount": 0,
        "highLowEligibleThreshold": POLYGON_HIGH_LOW_MIN_ELIGIBLE_COUNT,
        "sourceMetadataValid": _source_metadata_valid(),
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "broadMarketClaimAllowed": False,
        "officialExchangePublishedBreadth": False,
        "fullBreadthAuthority": False,
        "observationOnly": True,
        "fulfilledMetrics": [],
        "missingMetrics": list(US_BREADTH_SYMBOLS),
        "reasonCodes": list(reason_codes),
        "metrics": {
            "advancers": None,
            "decliners": None,
            "unchanged": None,
            "advanceDeclineRatio": None,
            "newHighs": None,
            "newLows": None,
            "highLowRatio": None,
        },
        "source": POLYGON_US_BREADTH_SOURCE,
        "sourceLabel": POLYGON_US_BREADTH_SOURCE_LABEL,
        "sourceType": POLYGON_US_BREADTH_SOURCE_TYPE,
        "sourceTier": POLYGON_US_BREADTH_SOURCE_TIER,
        "trustLevel": POLYGON_US_BREADTH_TRUST_LEVEL,
        "authorityBasis": POLYGON_US_BREADTH_AUTHORITY_BASIS,
        "universe": POLYGON_US_BREADTH_UNIVERSE,
    }


def _source_metadata_valid() -> bool:
    return bool(
        POLYGON_US_BREADTH_SOURCE_LABEL.startswith("Polygon")
        and "computed" in POLYGON_US_BREADTH_SOURCE_LABEL
        and POLYGON_US_BREADTH_AUTHORITY_BASIS == "computed_from_authorized_polygon_history"
        and POLYGON_US_BREADTH_UNIVERSE == "polygon_us_grouped_daily_ex_otc"
    )


def _business_lag_days(start: date, end: date) -> int:
    if start >= end:
        return 0
    cursor = start + timedelta(days=1)
    days = 0
    while cursor <= end:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


def _parse_json_bytes(raw: bytes) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _positive_int_or_default(value: Any, *, default: int) -> int:
    parsed = _parse_int(value)
    return parsed if parsed and parsed > 0 else max(1, int(default))


def _optional_positive_int(value: Any) -> int | None:
    parsed = _parse_int(value)
    return parsed if parsed and parsed > 0 else None


def _parse_finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _positive_float_or_default(value: Any, *, default: float, minimum: float) -> float:
    parsed = _parse_finite_float(value)
    if parsed is None or parsed <= 0:
        parsed = float(default)
    return max(float(minimum), parsed)


def _optional_positive_float(value: Any) -> float | None:
    parsed = _parse_finite_float(value)
    return parsed if parsed is not None and parsed > 0 else None


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _polygon_api_key() -> str:
    configured = _text(os.getenv("POLYGON_API_KEY"))
    if configured:
        return configured

    env_file = _text(os.getenv("ENV_FILE"))
    if not env_file:
        return ""
    env_path = Path(env_file)
    try:
        values = read_dotenv_values(env_path)
    except (OSError, ValueError):
        return ""
    return _text(values.get("POLYGON_API_KEY"))


__all__ = [
    "POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON",
    "POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON",
    "POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON",
    "POLYGON_HIGH_LOW_HISTORY_DIAGNOSTIC_SESSION_CAP_REASON",
    "POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON",
    "POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON",
    "POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON",
    "POLYGON_HIGH_LOW_HISTORY_TIMEOUT_REASON",
    "POLYGON_HIGH_LOW_LOOKBACK_SESSIONS",
    "POLYGON_HIGH_LOW_MIN_ELIGIBLE_COUNT",
    "POLYGON_HIGH_LOW_RATIO_UNAVAILABLE_REASON",
    "POLYGON_US_BREADTH_AUTHORITY_BASIS",
    "POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD",
    "POLYGON_US_BREADTH_REASON_EOD_STALE",
    "POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE",
    "POLYGON_US_BREADTH_REASON_RESPONSE_INVALID",
    "POLYGON_US_BREADTH_REASON_UNAUTHORIZED",
    "POLYGON_US_BREADTH_SOURCE",
    "POLYGON_US_BREADTH_SOURCE_LABEL",
    "POLYGON_US_BREADTH_SOURCE_TIER",
    "POLYGON_US_BREADTH_SOURCE_TYPE",
    "POLYGON_US_BREADTH_TRUST_LEVEL",
    "POLYGON_US_BREADTH_UNIVERSE",
    "POLYGON_US_EASTERN_TZ",
    "compute_polygon_us_breadth",
    "diagnostic_summary",
    "parse_polygon_grouped_daily_payload",
    "polygon_eod_freshness",
    "prior_completed_us_trading_dates",
    "recent_completed_us_trading_dates",
    "run_polygon_us_breadth_activation",
]
