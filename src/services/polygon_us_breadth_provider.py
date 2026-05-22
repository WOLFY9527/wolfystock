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
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

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
POLYGON_US_BREADTH_AUTHORITY_BASIS = "computed_from_authorized_polygon_grouped_daily"
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

POLYGON_US_BREADTH_REASON_UNAUTHORIZED = "polygon_unauthorized"
POLYGON_US_BREADTH_REASON_RESPONSE_INVALID = "polygon_response_invalid"
POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD = "polygon_coverage_below_threshold"
POLYGON_US_BREADTH_REASON_EOD_STALE = "polygon_eod_stale"
POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE = "polygon_previous_close_unavailable"
POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON = "polygon_high_low_history_unavailable"

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


@dataclass(frozen=True, slots=True)
class _ParsedGroupedDaily:
    ok: bool
    results_count: int
    rows: tuple[_GroupedDailyRow, ...]
    reason: str | None = None


def run_polygon_us_breadth_activation(
    *,
    api_key: str | None = None,
    transport: PolygonTransport | None = None,
    now: datetime | None = None,
    min_coverage_count: int = POLYGON_US_BREADTH_MIN_COVERAGE_COUNT,
    timeout_seconds: float = POLYGON_US_BREADTH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch recent grouped daily rows and return a sanitized activation summary."""

    credential = _text(api_key) if api_key is not None else _text(os.getenv("POLYGON_API_KEY"))
    if not credential:
        return _fail_closed_summary(
            reason_codes=(US_BREADTH_MISSING_PROVIDER_REASON,),
            credentials_present=False,
            provider_constructed=False,
        )

    fetch = transport or _default_polygon_transport
    candidates = recent_completed_us_trading_dates(now=now)
    latest_payload: Mapping[str, Any] | None = None
    latest_date: str | None = None
    latest_reason = POLYGON_US_BREADTH_REASON_RESPONSE_INVALID
    latest_index = -1

    for index, candidate in enumerate(candidates):
        status_code, payload = fetch(candidate, credential, timeout_seconds)
        if status_code in {401, 403}:
            return _fail_closed_summary(
                reason_codes=(POLYGON_US_BREADTH_REASON_UNAUTHORIZED,),
                credentials_present=True,
                provider_constructed=True,
                observation_date=candidate,
            )
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
        status_code, payload = fetch(candidate, credential, timeout_seconds)
        if status_code != 200:
            continue
        parsed = parse_polygon_grouped_daily_payload(payload)
        if parsed.ok:
            previous_payload = payload
            previous_date = candidate
            break

    return compute_polygon_us_breadth(
        latest_payload,
        previous_payload=previous_payload,
        observation_date=latest_date,
        previous_observation_date=previous_date,
        now=now,
        min_coverage_count=min_coverage_count,
        credentials_present=True,
        provider_constructed=True,
    )


def compute_polygon_us_breadth(
    payload: Mapping[str, Any] | None,
    *,
    previous_payload: Mapping[str, Any] | None = None,
    observation_date: str,
    previous_observation_date: str | None = None,
    now: datetime | None = None,
    min_coverage_count: int = POLYGON_US_BREADTH_MIN_COVERAGE_COUNT,
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
    fulfilled_metrics = (
        list(_AD_FULFILLED_METRICS if ad_ratio is not None else _AD_FULFILLED_METRICS[:-1])
        if previous_close_available
        else []
    )
    missing_metrics = [
        symbol
        for symbol in US_BREADTH_SYMBOLS
        if symbol not in fulfilled_metrics
    ]
    reason_codes = [POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON]
    if not previous_close_available:
        reason_codes.insert(0, POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE)
    if ad_ratio is None:
        reason_codes.append(POLYGON_US_BREADTH_REASON_RESPONSE_INVALID)

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
    broad_market_claim_allowed = bool(score_allowed and set(US_BREADTH_SYMBOLS).issubset(set(fulfilled_metrics)))
    metrics = {
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "advanceDeclineRatio": ad_ratio,
        "newHighs": None,
        "newLows": None,
        "highLowRatio": None,
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
        "sourceMetadataValid": source_metadata_valid,
        "sourceAuthorityAllowed": authority_allowed,
        "scoreContributionAllowed": score_allowed,
        "broadMarketClaimAllowed": broad_market_claim_allowed,
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
        open_price = _parse_finite_float(item.get("o") or item.get("open"))
        close_price = _parse_finite_float(item.get("c") or item.get("close"))
        if not ticker or open_price is None or close_price is None:
            continue
        rows.append(_GroupedDailyRow(ticker=ticker, open_price=open_price, close_price=close_price))

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


def diagnostic_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return the bounded JSON shape used by the operator diagnostic script."""

    return {
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
        "sourceMetadataValid": bool(result.get("sourceMetadataValid")),
        "sourceAuthorityAllowed": bool(result.get("sourceAuthorityAllowed")),
        "scoreContributionAllowed": bool(result.get("scoreContributionAllowed")),
        "broadMarketClaimAllowed": bool(result.get("broadMarketClaimAllowed")),
        "fulfilledMetrics": list(result.get("fulfilledMetrics") or []),
        "missingMetrics": list(result.get("missingMetrics") or []),
        "reasonCodes": list(result.get("reasonCodes") or []),
    }


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
    except (TimeoutError, URLError, OSError, ValueError, json.JSONDecodeError):
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
        "sourceMetadataValid": _source_metadata_valid(),
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "broadMarketClaimAllowed": False,
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
        and POLYGON_US_BREADTH_AUTHORITY_BASIS == "computed_from_authorized_polygon_grouped_daily"
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


def _parse_finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON",
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
    "recent_completed_us_trading_dates",
    "run_polygon_us_breadth_activation",
]
