# -*- coding: utf-8 -*-
"""Pure request builders and fixture parsers for official macro transports."""

from __future__ import annotations

from dataclasses import dataclass, field
import csv
from datetime import datetime
from io import StringIO
import json
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
TREASURY_DAILY_RATES_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/daily-treasury-rates.csv/all/all"
)
OFFICIAL_SOURCE_TYPE = "official_public"
FRED_SUPPORTED_SERIES_IDS = (
    "BAMLH0A0HYM2",
    "CPIAUCSL",
    "DFF",
    "VIXCLS",
    "DGS2",
    "DGS10",
    "DGS30",
    "PPIACO",
    "SOFR",
)
FRED_DEFAULT_REQUEST_SERIES_IDS = ("VIXCLS", "DGS2", "DGS10", "DGS30", "SOFR")
TREASURY_RATE_SYMBOLS = ("DGS2", "DGS10", "DGS30")
TREASURY_COLUMN_ALIASES = {
    "DGS2": ("2 Yr", "2 YR", "2-Year", "2 Year"),
    "DGS10": ("10 Yr", "10 YR", "10-Year", "10 Year"),
    "DGS30": ("30 Yr", "30 YR", "30-Year", "30 Year"),
}
FRED_FRESHNESS_HINTS = {
    "BAMLH0A0HYM2": "daily_credit_stress",
    "CPIAUCSL": "monthly_inflation_index",
    "DFF": "daily_policy_rate",
    "VIXCLS": "daily_close",
    "DGS2": "daily_rate",
    "DGS10": "daily_rate",
    "DGS30": "daily_rate",
    "PPIACO": "monthly_inflation_index",
    "SOFR": "daily_fixing",
}
TREASURY_FRESHNESS_HINT = "daily_1530_et"
NYFED_SOFR_UNSUPPORTED_REASON = "nyfed_sofr_shape_undocumented"
DEFAULT_TRANSPORT_TIMEOUT_SECONDS = 4.0


@dataclass(frozen=True)
class MacroTransportRequest:
    method: str
    url: str
    params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    source_id: str = ""
    source_type: str = OFFICIAL_SOURCE_TYPE
    requires_api_key: bool = False


@dataclass(frozen=True)
class MacroObservation:
    symbol: str
    value: float | None
    date: str | None
    as_of: str | None
    source_id: str
    source_type: str
    freshness_hint: str
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "value": self.value,
            "date": self.date,
            "asOf": self.as_of,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "freshness_hint": self.freshness_hint,
            "unavailable_reason": self.unavailable_reason,
        }


def build_supported_fred_requests(*, api_key: str | None = None, limit: int = 5) -> list[MacroTransportRequest]:
    resolved_api_key = _resolve_fred_api_key(api_key)
    return [
        build_fred_observations_request(series_id, api_key=resolved_api_key, limit=limit)
        for series_id in FRED_DEFAULT_REQUEST_SERIES_IDS
    ]


def build_fred_observations_request(
    series_id: str,
    *,
    api_key: str | None = None,
    limit: int = 5,
    sort_order: str = "desc",
    observation_start: str | None = None,
    observation_end: str | None = None,
) -> MacroTransportRequest:
    normalized_series = _validate_fred_series_id(series_id)
    resolved_api_key = _resolve_fred_api_key(api_key)
    params = {
        "series_id": normalized_series,
        "file_type": "json",
        "sort_order": sort_order,
        "limit": str(limit),
    }
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end
    if resolved_api_key:
        params["api_key"] = resolved_api_key
    return MacroTransportRequest(
        method="GET",
        url=FRED_OBSERVATIONS_URL,
        params=params,
        source_id=f"fred:{normalized_series}",
        source_type=OFFICIAL_SOURCE_TYPE,
        requires_api_key=True,
    )


def build_treasury_daily_rates_request() -> MacroTransportRequest:
    return MacroTransportRequest(
        method="GET",
        url=TREASURY_DAILY_RATES_CSV_URL,
        params={"_format": "csv", "type": "daily_treasury_yield_curve"},
        source_id="treasury:daily_treasury_yield_curve",
        source_type=OFFICIAL_SOURCE_TYPE,
    )


def parse_fred_observations_payload(series_id: str, payload: Any) -> MacroObservation:
    normalized_series = _validate_fred_series_id(series_id)
    source_id = f"fred:{normalized_series}"
    freshness_hint = FRED_FRESHNESS_HINTS[normalized_series]
    points = parse_fred_observation_points_payload(normalized_series, payload, limit=1)
    if not points:
        return _unavailable_observation(
            normalized_series,
            source_id=source_id,
            freshness_hint=freshness_hint,
            reason="fred_observation_value_unavailable",
        )
    return points[0]


def parse_fred_observation_points_payload(
    series_id: str,
    payload: Any,
    *,
    limit: int = 2,
) -> list[MacroObservation]:
    normalized_series = _validate_fred_series_id(series_id)
    source_id = f"fred:{normalized_series}"
    freshness_hint = FRED_FRESHNESS_HINTS[normalized_series]

    if not isinstance(payload, Mapping):
        return []

    observations = payload.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return []

    valid_points: list[tuple[str, float]] = []
    for item in observations:
        if not isinstance(item, Mapping):
            continue
        raw_date = _normalize_iso_date(item.get("date"))
        raw_value = _parse_numeric(item.get("value"))
        if raw_date is None or raw_value is None:
            continue
        valid_points.append((raw_date, raw_value))

    valid_points.sort(key=lambda item: item[0], reverse=True)
    return [
        MacroObservation(
            symbol=normalized_series,
            value=value,
            date=point_date,
            as_of=point_date,
            source_id=source_id,
            source_type=OFFICIAL_SOURCE_TYPE,
            freshness_hint=freshness_hint,
        )
        for point_date, value in valid_points[: max(0, limit)]
    ]


def parse_treasury_daily_rates_csv(text: str) -> list[MacroObservation]:
    reader = csv.DictReader(StringIO(text))
    return parse_treasury_daily_rates_rows(list(reader))


def parse_treasury_daily_rates_rows(rows: Iterable[Mapping[str, Any]]) -> list[MacroObservation]:
    materialized_rows = [row for row in rows if isinstance(row, Mapping)]
    source_id = "treasury:daily_treasury_yield_curve"

    latest_row: Mapping[str, Any] | None = None
    latest_date: str | None = None
    for row in materialized_rows:
        row_date = _normalize_treasury_date(row.get("Date") or row.get("DATE") or row.get("date"))
        if row_date is None:
            continue
        if latest_date is None or row_date > latest_date:
            latest_date = row_date
            latest_row = row

    if latest_row is None or latest_date is None:
        return [
            _unavailable_observation(
                symbol,
                source_id=source_id,
                freshness_hint=TREASURY_FRESHNESS_HINT,
                reason="treasury_rates_missing_rows",
            )
            for symbol in TREASURY_RATE_SYMBOLS
        ]

    observations: list[MacroObservation] = []
    for symbol in TREASURY_RATE_SYMBOLS:
        value = _parse_numeric(_lookup_treasury_value(latest_row, symbol))
        if value is None:
            observations.append(
                _unavailable_observation(
                    symbol,
                    source_id=source_id,
                    freshness_hint=TREASURY_FRESHNESS_HINT,
                    reason="treasury_rate_unavailable",
                    date=latest_date,
                    as_of=latest_date,
                )
            )
            continue
        observations.append(
            MacroObservation(
                symbol=symbol,
                value=value,
                date=latest_date,
                as_of=latest_date,
                source_id=source_id,
                source_type=OFFICIAL_SOURCE_TYPE,
                freshness_hint=TREASURY_FRESHNESS_HINT,
            )
        )
    return observations


def parse_treasury_daily_rate_observation_points_csv(text: str, *, limit: int = 2) -> dict[str, list[MacroObservation]]:
    reader = csv.DictReader(StringIO(text))
    return parse_treasury_daily_rate_observation_points_rows(list(reader), limit=limit)


def parse_treasury_daily_rate_observation_points_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int = 2,
) -> dict[str, list[MacroObservation]]:
    materialized_rows = [row for row in rows if isinstance(row, Mapping)]
    sorted_rows = sorted(
        (
            (_normalize_treasury_date(row.get("Date") or row.get("DATE") or row.get("date")), row)
            for row in materialized_rows
        ),
        key=lambda item: item[0] or "",
        reverse=True,
    )
    source_id = "treasury:daily_treasury_yield_curve"
    points: dict[str, list[MacroObservation]] = {symbol: [] for symbol in TREASURY_RATE_SYMBOLS}
    for row_date, row in sorted_rows:
        if row_date is None:
            continue
        for symbol in TREASURY_RATE_SYMBOLS:
            if len(points[symbol]) >= max(0, limit):
                continue
            value = _parse_numeric(_lookup_treasury_value(row, symbol))
            if value is None:
                continue
            points[symbol].append(
                MacroObservation(
                    symbol=symbol,
                    value=value,
                    date=row_date,
                    as_of=row_date,
                    source_id=source_id,
                    source_type=OFFICIAL_SOURCE_TYPE,
                    freshness_hint=TREASURY_FRESHNESS_HINT,
                )
            )
    return points


def parse_nyfed_sofr_payload(_: Any) -> MacroObservation:
    return _unavailable_observation(
        "SOFR",
        source_id="nyfed:sofr",
        freshness_hint="unsupported_shape",
        reason=NYFED_SOFR_UNSUPPORTED_REASON,
    )


def fetch_fred_observation_points(
    series_id: str,
    *,
    api_key: str | None = None,
    limit: int = 2,
    timeout: float = DEFAULT_TRANSPORT_TIMEOUT_SECONDS,
) -> list[MacroObservation]:
    request = build_fred_observations_request(series_id, api_key=api_key, limit=limit)
    payload = json.loads(_fetch_transport_bytes(request, timeout=timeout).decode("utf-8"))
    return parse_fred_observation_points_payload(series_id, payload, limit=limit)


def fetch_treasury_daily_rate_observation_points(
    *,
    limit: int = 2,
    timeout: float = DEFAULT_TRANSPORT_TIMEOUT_SECONDS,
) -> dict[str, list[MacroObservation]]:
    request = build_treasury_daily_rates_request()
    text = _fetch_transport_bytes(request, timeout=timeout).decode("utf-8-sig")
    return parse_treasury_daily_rate_observation_points_csv(text, limit=limit)


def _fetch_transport_bytes(request: MacroTransportRequest, *, timeout: float) -> bytes:
    query = urlencode(request.params)
    url = f"{request.url}?{query}" if query else request.url
    http_request = Request(url=url, headers=request.headers, method=request.method)
    with urlopen(http_request, timeout=timeout) as response:
        return response.read()


def _resolve_fred_api_key(explicit_api_key: str | None) -> str | None:
    normalized_explicit = _text(explicit_api_key)
    if normalized_explicit:
        return normalized_explicit
    try:
        from src.config import Config

        return _text(getattr(Config.get_instance(), "fred_api_key", None)) or None
    except Exception:
        return None


def _lookup_treasury_value(row: Mapping[str, Any], symbol: str) -> Any:
    for column_name in TREASURY_COLUMN_ALIASES[symbol]:
        if column_name in row:
            return row[column_name]
    normalized_map = {_normalize_column_name(key): value for key, value in row.items()}
    for column_name in TREASURY_COLUMN_ALIASES[symbol]:
        normalized_name = _normalize_column_name(column_name)
        if normalized_name in normalized_map:
            return normalized_map[normalized_name]
    return None


def _normalize_column_name(value: Any) -> str:
    return " ".join(str(value or "").replace("-", " ").split()).lower()


def _unavailable_observation(
    symbol: str,
    *,
    source_id: str,
    freshness_hint: str,
    reason: str,
    date: str | None = None,
    as_of: str | None = None,
) -> MacroObservation:
    return MacroObservation(
        symbol=symbol,
        value=None,
        date=date,
        as_of=as_of,
        source_id=source_id,
        source_type=OFFICIAL_SOURCE_TYPE,
        freshness_hint=freshness_hint,
        unavailable_reason=reason,
    )


def _validate_fred_series_id(series_id: str) -> str:
    normalized = _text(series_id).upper()
    if normalized not in FRED_SUPPORTED_SERIES_IDS:
        raise ValueError(f"unsupported FRED series: {series_id}")
    return normalized


def _parse_numeric(value: Any) -> float | None:
    text = _text(value)
    if not text or text in {".", "N/A", "NaN", "nan"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_iso_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _normalize_treasury_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _text(value: Any) -> str:
    return str(value or "").strip()
