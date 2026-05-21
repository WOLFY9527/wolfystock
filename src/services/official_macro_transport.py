# -*- coding: utf-8 -*-
"""Pure request builders and fixture parsers for official macro transports."""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import csv
from datetime import datetime, timezone
from io import StringIO
import os
import json
import socket
import ssl
import time
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError, URLError
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
TREASURY_FETCH_MAX_ATTEMPTS = 2
HTTPS_CA_BUNDLE_ENV_VARS = ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")
OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS = (
    "VIXCLS",
    "SOFR",
    "DFF",
    "DGS2",
    "DGS10",
    "DGS30",
    "BAMLH0A0HYM2",
)
OFFICIAL_MACRO_LIVE_SMOKE_FRED_SERIES_IDS = OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS
OFFICIAL_MACRO_LIVE_SMOKE_TREASURY_SERIES_IDS = ("DGS2", "DGS10", "DGS30")
OFFICIAL_MACRO_LIVE_SMOKE_AGGREGATE_BUDGET_SECONDS = 8.0
OFFICIAL_MACRO_LIVE_SMOKE_FRED_TIMEOUT_SECONDS = 1.0
OFFICIAL_MACRO_LIVE_SMOKE_TREASURY_TIMEOUT_SECONDS = 1.5
OFFICIAL_MACRO_LIVE_SMOKE_MAX_ATTEMPTS = 3
OFFICIAL_MACRO_LIVE_SMOKE_RETRY_SLEEP_SECONDS = 0.05


class OfficialMacroTransportError(RuntimeError):
    """Sanitized official macro transport failure with a stable reason bucket."""

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        status_code: int | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code
        self.diagnostics = dict(diagnostics or {})


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
    try:
        payload = json.loads(_fetch_transport_bytes(request, timeout=timeout).decode("utf-8"))
    except OfficialMacroTransportError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise OfficialMacroTransportError(
            "parse_error",
            f"{request.source_id or 'official macro'} response could not be parsed",
            diagnostics=_transport_diagnostics(request, timeout=timeout, exception=exc),
        ) from exc
    return parse_fred_observation_points_payload(series_id, payload, limit=limit)


def fetch_treasury_daily_rate_observation_points(
    *,
    limit: int = 2,
    timeout: float = DEFAULT_TRANSPORT_TIMEOUT_SECONDS,
) -> dict[str, list[MacroObservation]]:
    request = build_treasury_daily_rates_request()
    attempts = max(1, int(TREASURY_FETCH_MAX_ATTEMPTS))
    per_attempt_timeout = max(float(timeout) / float(attempts), 0.001)
    last_transport_error: OfficialMacroTransportError | None = None
    for attempt_index in range(attempts):
        try:
            text = _fetch_transport_bytes(request, timeout=per_attempt_timeout).decode("utf-8-sig")
            return parse_treasury_daily_rate_observation_points_csv(text, limit=limit)
        except OfficialMacroTransportError as exc:
            last_transport_error = exc
            if attempt_index + 1 >= attempts or exc.reason not in {"timeout", "transport_error", "empty_response"}:
                raise
        except (UnicodeDecodeError, csv.Error) as exc:
            raise OfficialMacroTransportError(
                "parse_error",
                f"{request.source_id or 'official macro'} response could not be parsed",
                diagnostics=_transport_diagnostics(request, timeout=per_attempt_timeout, exception=exc),
            ) from exc
    if last_transport_error is not None:
        raise last_transport_error
    raise OfficialMacroTransportError(
        "transport_error",
        f"{request.source_id or 'official macro'} transport failed",
        diagnostics=_transport_diagnostics(request, timeout=per_attempt_timeout),
    )


def run_official_macro_live_smoke(
    *,
    now: datetime | None = None,
    aggregate_budget_seconds: float = OFFICIAL_MACRO_LIVE_SMOKE_AGGREGATE_BUDGET_SECONDS,
    fred_timeout_seconds: float = OFFICIAL_MACRO_LIVE_SMOKE_FRED_TIMEOUT_SECONDS,
    treasury_timeout_seconds: float = OFFICIAL_MACRO_LIVE_SMOKE_TREASURY_TIMEOUT_SECONDS,
    max_attempts: int = OFFICIAL_MACRO_LIVE_SMOKE_MAX_ATTEMPTS,
    retry_sleep_seconds: float = OFFICIAL_MACRO_LIVE_SMOKE_RETRY_SLEEP_SECONDS,
) -> dict[str, Any]:
    """Run a bounded FRED/Treasury official macro readiness diagnostic."""

    config_probe = fred_runtime_config_probe()
    credentials_present = bool(config_probe.get("apiKeyPresent"))
    provider_constructed = bool(credentials_present)
    deadline = time.monotonic() + max(0.0, float(aggregate_budget_seconds))
    bounded_max_attempts = max(1, min(int(max_attempts), 4))
    bounded_retry_sleep_seconds = max(0.0, float(retry_sleep_seconds))

    results: dict[str, str] = {series_id: "missing" for series_id in OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS}
    attempts_executed = 0
    transient_missing_series_seen: set[str] = set()

    def remaining_timeout(cap: float) -> float | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        return max(0.001, min(float(cap), remaining))

    if credentials_present:
        pending_series = list(OFFICIAL_MACRO_LIVE_SMOKE_FRED_SERIES_IDS)
        for attempt_index in range(bounded_max_attempts):
            attempts_executed = attempt_index + 1
            current_attempt_missing: list[str] = []
            for series_id in pending_series:
                timeout = remaining_timeout(fred_timeout_seconds)
                if timeout is None:
                    current_attempt_missing.append(series_id)
                    continue
                try:
                    points = fetch_fred_observation_points(series_id, limit=2, timeout=timeout)
                except Exception:
                    points = []
                series_status = _official_macro_smoke_series_status(series_id, points, now=now)
                results[series_id] = series_status
                if series_status == "missing":
                    current_attempt_missing.append(series_id)
            transient_missing_series_seen.update(current_attempt_missing)
            pending_series = [
                series_id
                for series_id in OFFICIAL_MACRO_LIVE_SMOKE_FRED_SERIES_IDS
                if results.get(series_id) != "fulfilled"
            ]
            if not pending_series or attempts_executed >= bounded_max_attempts:
                break
            sleep_budget = remaining_timeout(bounded_retry_sleep_seconds)
            if sleep_budget is None:
                break
            time.sleep(sleep_budget)
    else:
        attempts_executed = 1
        for series_id in OFFICIAL_MACRO_LIVE_SMOKE_FRED_SERIES_IDS:
            results.setdefault(series_id, "missing")
        treasury_timeout = remaining_timeout(treasury_timeout_seconds)
        treasury_points: dict[str, list[MacroObservation]] = {}
        if treasury_timeout is not None:
            try:
                treasury_points = fetch_treasury_daily_rate_observation_points(limit=2, timeout=treasury_timeout)
            except Exception:
                treasury_points = {}
        for series_id in OFFICIAL_MACRO_LIVE_SMOKE_TREASURY_SERIES_IDS:
            series_status = _official_macro_smoke_series_status(series_id, treasury_points.get(series_id, []), now=now)
            results[series_id] = series_status
    if attempts_executed == 0:
        attempts_executed = 1

    fulfilled_series = [
        series_id for series_id in OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS if results.get(series_id) == "fulfilled"
    ]
    stale_series = [
        series_id for series_id in OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS if results.get(series_id) == "stale"
    ]
    missing_series = [
        series_id
        for series_id in OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS
        if results.get(series_id) not in {"fulfilled", "stale"}
    ]
    invalid_metadata_detected = any(
        results.get(series_id) == "invalid_metadata" for series_id in OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS
    )
    freshness_valid = not stale_series
    source_metadata_valid = not invalid_metadata_detected
    probe_passed = not missing_series and freshness_valid and source_metadata_valid
    source_authority_allowed = bool(
        credentials_present
        and provider_constructed
        and probe_passed
        and freshness_valid
        and source_metadata_valid
    )

    reason: str | None = None
    if not credentials_present:
        reason = "credentials"
    elif not freshness_valid:
        reason = "stale_series"
    elif not source_metadata_valid:
        reason = "source_metadata_invalid"
    elif missing_series:
        reason = "series_coverage"
    transient_missing_series = [
        series_id
        for series_id in OFFICIAL_MACRO_LIVE_SMOKE_SERIES_IDS
        if series_id in transient_missing_series_seen and results.get(series_id) == "fulfilled"
    ]

    return {
        "credentialsPresent": credentials_present,
        "providerConstructed": provider_constructed,
        "probePassed": probe_passed,
        "freshnessValid": freshness_valid,
        "sourceMetadataValid": source_metadata_valid,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": source_authority_allowed,
        "fulfilledSeries": fulfilled_series,
        "missingSeries": missing_series,
        "staleSeries": stale_series,
        "reason": reason,
        "attempts": attempts_executed,
        "maxAttempts": bounded_max_attempts,
        "transientMissingSeries": transient_missing_series,
        "finalAttemptMissingSeries": missing_series,
    }


def _fetch_transport_bytes(request: MacroTransportRequest, *, timeout: float) -> bytes:
    ca_bundle_source = _selected_https_ca_bundle_source()
    base_diagnostics = _transport_diagnostics(request, timeout=timeout, ca_bundle_source=ca_bundle_source)
    if request.requires_api_key and not _text(request.params.get("api_key")):
        raise OfficialMacroTransportError(
            "missing_api_key",
            f"{request.source_id or 'official macro'} API key is not configured",
            diagnostics=base_diagnostics,
        )
    query = urlencode(request.params)
    url = f"{request.url}?{query}" if query else request.url
    http_request = Request(url=url, headers=request.headers, method=request.method)
    try:
        https_context, ca_bundle_source = _build_https_context()
        with urlopen(http_request, timeout=timeout, context=https_context) as response:
            status_code = _response_status_code(response)
            if status_code >= 400:
                raise OfficialMacroTransportError(
                    "http_error",
                    f"{request.source_id or 'official macro'} returned HTTP {status_code}",
                    status_code=status_code,
                    diagnostics=_transport_diagnostics(
                        request,
                        timeout=timeout,
                        status_code=status_code,
                        ca_bundle_source=ca_bundle_source,
                    ),
                )
            body = response.read()
    except OfficialMacroTransportError:
        raise
    except HTTPError as exc:
        raise OfficialMacroTransportError(
            "http_error",
            f"{request.source_id or 'official macro'} returned HTTP {exc.code}",
            status_code=exc.code,
            diagnostics=_transport_diagnostics(
                request,
                timeout=timeout,
                exception=exc,
                status_code=exc.code,
                ca_bundle_source=ca_bundle_source,
            ),
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OfficialMacroTransportError(
            "timeout",
            f"{request.source_id or 'official macro'} request timed out",
            diagnostics=_transport_diagnostics(
                request,
                timeout=timeout,
                exception=exc,
                ca_bundle_source=ca_bundle_source,
            ),
        ) from exc
    except URLError as exc:
        reason = classify_official_macro_exception(exc)
        raise OfficialMacroTransportError(
            reason,
            f"{request.source_id or 'official macro'} transport failed",
            diagnostics=_transport_diagnostics(
                request,
                timeout=timeout,
                exception=exc,
                ca_bundle_source=ca_bundle_source,
            ),
        ) from exc
    if not body:
        raise OfficialMacroTransportError(
            "empty_response",
            f"{request.source_id or 'official macro'} returned an empty response",
            diagnostics=base_diagnostics,
        )
    return body


def classify_official_macro_exception(exc: Exception) -> str:
    """Map runtime transport/parser exceptions to safe public reason buckets."""
    if isinstance(exc, OfficialMacroTransportError):
        return exc.reason
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, HTTPError):
        return "http_error"
    if isinstance(exc, URLError):
        if _is_url_timeout(getattr(exc, "reason", None)):
            return "timeout"
        return "transport_error"
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError, csv.Error)):
        return "parse_error"
    if _looks_like_timeout(exc):
        return "timeout"
    return "transport_error"


def _response_status_code(response: Any) -> int:
    raw_status = getattr(response, "status", getattr(response, "code", 200))
    try:
        return int(raw_status)
    except (TypeError, ValueError):
        return 200


def _is_url_timeout(reason: Any) -> bool:
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return True
    return "timed out" in str(reason or "").lower() or "timeout" in str(reason or "").lower()


def _looks_like_timeout(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return "timed out" in text or "timeout" in text or "time out" in text


def _transport_diagnostics(
    request: MacroTransportRequest,
    *,
    timeout: float,
    exception: Exception | None = None,
    status_code: int | None = None,
    ca_bundle_source: str | None = None,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "providerName": _provider_name(request.source_id),
        "endpointHost": urlparse(request.url).netloc,
        "requestedSeries": _requested_series(request),
        "attemptedAt": _utc_now_iso(),
    }
    if ca_bundle_source:
        diagnostics["caBundleSource"] = ca_bundle_source
    try:
        diagnostics["timeoutSeconds"] = round(float(timeout), 3)
    except (TypeError, ValueError):
        pass
    if request.requires_api_key or diagnostics["providerName"] == "fred":
        config_probe = fred_runtime_config_probe()
        diagnostics["configPresent"] = bool(config_probe["configPresent"])
        diagnostics["apiKeyPresent"] = bool(_text(request.params.get("api_key")) or config_probe["apiKeyPresent"])
    if status_code is not None:
        diagnostics["httpStatus"] = int(status_code)
    if exception is not None:
        diagnostics["exceptionClass"] = _exception_class(exception)
        exception_chain = _exception_chain(exception)
        if exception_chain:
            diagnostics["exceptionChain"] = exception_chain
    return {key: value for key, value in diagnostics.items() if value not in (None, "")}


def _selected_https_ca_bundle_source() -> str:
    for source, _ in _https_ca_bundle_candidates():
        return source
    return "system"


def _build_https_context() -> tuple[ssl.SSLContext, str]:
    last_error: Exception | None = None
    for source, cafile in _https_ca_bundle_candidates():
        try:
            if cafile:
                return ssl.create_default_context(cafile=cafile), source
            return ssl.create_default_context(), source
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        try:
            return ssl.create_default_context(), "system"
        except Exception as system_exc:  # pragma: no cover - extremely rare
            raise system_exc from last_error
    return ssl.create_default_context(), "system"


def _https_ca_bundle_candidates() -> list[tuple[str, str | None]]:
    candidates: list[tuple[str, str | None]] = []
    for env_var in HTTPS_CA_BUNDLE_ENV_VARS:
        candidate = _text(os.environ.get(env_var))
        if candidate and os.path.isfile(candidate):
            candidates.append(("env", candidate))
            break
    try:
        certifi = importlib.import_module("certifi")
    except ModuleNotFoundError:
        certifi = None
    except Exception:
        certifi = None
    if certifi is not None:
        candidate = _text(getattr(certifi, "where", lambda: "")())
        if candidate and os.path.isfile(candidate):
            candidates.append(("certifi", candidate))
    candidates.append(("system", None))
    return candidates


def fred_runtime_config_probe() -> dict[str, bool]:
    """Return no-secret FRED config presence metadata for diagnostics."""
    try:
        from src.config import Config

        config = Config.get_instance()
        return {
            "configPresent": config is not None,
            "apiKeyPresent": bool(_text(getattr(config, "fred_api_key", None))),
        }
    except Exception:
        return {"configPresent": False, "apiKeyPresent": False}


def _provider_name(source_id: str | None) -> str:
    prefix = _text(source_id).split(":", 1)[0].lower()
    if prefix:
        return prefix
    return "official_macro"


def _official_macro_smoke_series_status(
    series_id: str,
    points: Sequence[MacroObservation],
    *,
    now: datetime | None = None,
) -> str:
    latest = next((point for point in points if point.value is not None), None)
    if latest is None:
        return "missing"
    if not _official_macro_smoke_source_metadata_valid(series_id, latest):
        return "invalid_metadata"
    if _official_macro_smoke_is_stale(series_id, latest, now=now):
        return "stale"
    return "fulfilled"


def _official_macro_smoke_source_metadata_valid(series_id: str, point: MacroObservation) -> bool:
    if str(point.symbol or "").strip().upper() != str(series_id or "").strip().upper():
        return False
    if str(point.source_type or "").strip().lower() != OFFICIAL_SOURCE_TYPE:
        return False
    try:
        from src.services.official_macro_source_registry import get_official_macro_source_for_transport_source

        contract = get_official_macro_source_for_transport_source(point.source_id)
    except Exception:
        contract = None
    return bool(contract and str(contract.source_type or "").strip().lower() == OFFICIAL_SOURCE_TYPE)


def _official_macro_smoke_is_stale(
    series_id: str,
    point: MacroObservation,
    *,
    now: datetime | None = None,
) -> bool:
    try:
        from src.services.market_overview_service import get_freshness_status

        freshness = get_freshness_status(
            point.as_of or point.date,
            "macro_rate",
            _provider_name(point.source_id),
            False,
            source_type=point.source_type,
            series_id=series_id,
            official_observation_date=point.date,
            now=now,
        )
    except Exception:
        return True
    return str(freshness.get("freshness") or "").strip().lower() == "stale"


def _requested_series(request: MacroTransportRequest) -> str | None:
    series_id = _text(request.params.get("series_id"))
    if series_id:
        return series_id
    return None


def _exception_class(exc: Exception) -> str:
    if isinstance(exc, URLError) and getattr(exc, "reason", None) is not None:
        return type(exc.reason).__name__
    return type(exc).__name__


def _exception_chain(exc: Exception) -> list[str]:
    chain: list[str] = []
    current: Exception | None = exc
    while current is not None:
        name = type(current).__name__
        if not chain or chain[-1] != name:
            chain.append(name)
        next_exc: Exception | None = None
        if isinstance(current, URLError):
            reason = getattr(current, "reason", None)
            if isinstance(reason, Exception):
                next_exc = reason
        if next_exc is None:
            next_exc = current.__cause__ if isinstance(current.__cause__, Exception) else None
        if next_exc is None:
            next_exc = current.__context__ if isinstance(current.__context__, Exception) else None
        current = next_exc
    return chain


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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
