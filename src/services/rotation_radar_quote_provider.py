# -*- coding: utf-8 -*-
"""US rotation radar quote provider with configured-provider and yfinance fallback."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, time as clock_time
from math import ceil
import os
from time import monotonic
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from data_provider.alpaca_fetcher import AlpacaFetcher
from data_provider.provider_credentials import ProviderCredentialBundle, get_provider_credentials
from src.services.market_overview_yfinance_transport import fetch_yfinance_quote_history_frame
from src.services.data_source_router import DataSourceRouteRequest
from src.services.data_source_router_diagnostics import build_data_source_route_diagnostic_snapshot
from src.services.rotation_theme_registry import list_rotation_theme_definitions

QuoteProvider = Callable[[Iterable[str]], Mapping[str, Any]]

_QUOTE_SOURCE = "yfinance_proxy"
_QUOTE_SOURCE_LABEL = "Yahoo Finance"
_QUOTE_MODE = "proxy"
_QUOTE_SOURCE_TYPE = "unofficial_public_api"
_QUOTE_SOURCE_TIER = "unofficial_public_api"
_QUOTE_PROVIDER_TIER = "tier_2_delayed_proxy"
_QUOTE_CONFIDENCE_WEIGHT = 0.5
_CONFIGURED_SOURCE = "alpaca"
_CONFIGURED_SOURCE_TYPE = "official_public"
_CONFIGURED_SOURCE_TIER = "broker_authorized"
_CONFIGURED_PROVIDER_TIER = "tier_1_configured"
_CONFIGURED_CONFIDENCE_WEIGHT = 0.9
_CONFIGURED_PROVIDER_ID = "alpaca"
_QUOTE_PROVIDER_ORDER = ("alpaca", "yfinance")
_ALPACA_MAX_SYMBOLS_PER_WINDOW = 32
_ALPACA_MAX_PROBE_SYMBOLS = 12
_ALPACA_STABLE_ACTIVATION_PROBE_SYMBOLS = ("SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV")
_ROTATION_RADAR_AUTHORITY_ETF_UNIVERSE = _ALPACA_STABLE_ACTIVATION_PROBE_SYMBOLS
_ALPACA_PER_WINDOW_TIMEOUT_SECONDS = 2.5
_ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS = 8.0
_ALPACA_PROVIDER_DEADLINE_SECONDS = 3.0
_ALPACA_PER_WINDOW_TIMEOUT_ENV = "ROTATION_RADAR_ALPACA_PER_WINDOW_TIMEOUT_SECONDS"
_ALPACA_TOTAL_PROVIDER_BUDGET_ENV = "ROTATION_RADAR_ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS"
_ALPACA_PROVIDER_DEADLINE_ENV = "ROTATION_RADAR_ALPACA_PROVIDER_DEADLINE_SECONDS"
_ALPACA_MAX_PER_WINDOW_TIMEOUT_SECONDS = 30.0
_ALPACA_MAX_TOTAL_PROVIDER_BUDGET_SECONDS = 120.0
_ALPACA_MAX_PROVIDER_DEADLINE_SECONDS = 120.0
_ALPACA_MINIMUM_ACTIVATION_SUCCESS_RATIO = 0.75
_US_EASTERN_TZ = ZoneInfo("America/New_York")
_US_REGULAR_SESSION_OPEN = clock_time(9, 30)
_US_REGULAR_SESSION_CLOSE = clock_time(16, 0)
_ALPACA_TIMEFRAMES = {
    "5m": ("5Min", timedelta(hours=2), 48),
    "15m": ("15Min", timedelta(hours=6), 48),
    "60m": ("1Hour", timedelta(days=3), 72),
    "1d": ("1Day", timedelta(days=45), 45),
}
_INTRADAY_WINDOWS = ("5m", "15m", "60m")
_SHORT_INTRADAY_WINDOWS = ("5m", "15m")
_OBSERVATION_GRADE_WINDOWS = ("60m", "1d")
_FAILED_SYMBOL_LIST_LIMIT = 8
_QUOTE_PROVIDER_MAX_WORKERS = 6
_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS = 2.5
_UNAVAILABLE_SYMBOL_COOLDOWN_SECONDS = 1800.0
_UNAVAILABLE_SYMBOL_STATE: Dict[str, Dict[str, Any]] = {}
_PROVIDER_DIAGNOSTIC_REASON_LIMIT = 8
_CONFIGURED_FAILURE_CLASSES = {
    "missing_credentials",
    "entitlement_denied",
    "auth_failed",
    "interval_mapping",
    "market_session",
    "calendar",
    "rate_limited",
    "proxy_unreachable",
    "connect_timeout",
    "read_timeout",
    "provider_timeout",
    "network_unreachable",
    "timeout",
    "empty_response",
    "symbol_not_found",
    "provider_error",
    "unknown",
}
_CONFIGURED_FAILURE_PRIORITY = (
    "auth_failed",
    "entitlement_denied",
    "interval_mapping",
    "market_session",
    "calendar",
    "rate_limited",
    "proxy_unreachable",
    "connect_timeout",
    "read_timeout",
    "provider_timeout",
    "network_unreachable",
    "timeout",
    "empty_response",
    "symbol_not_found",
    "provider_error",
    "missing_credentials",
    "unknown",
)
_ACTIVATION_BLOCKERS = {
    "credentials",
    "auth",
    "entitlement",
    "interval_mapping",
    "market_session",
    "market_closed_window_empty",
    "calendar",
    "proxy_unreachable",
    "connect_timeout",
    "read_timeout",
    "provider_timeout",
    "network_unreachable",
    "timeout",
    "empty_response",
    "feed_intraday_empty",
    "intraday_short_window_empty",
    "short_window_coverage",
    "symbol_coverage",
    "provider_error",
    "unknown",
}
_TIMEOUT_FAILURE_CLASSES = {"connect_timeout", "read_timeout", "provider_timeout", "timeout"}
_NETWORK_FAILURE_CLASSES = {"proxy_unreachable", "network_unreachable"}
_ALPACA_CREDENTIAL_ENV_NAMES = {
    "key_id": "ALPACA_API_KEY_ID",
    "secret_key": "ALPACA_API_SECRET_KEY",
}
_CREDENTIAL_SOURCE_VALUES = {"env", "config", "control_plane", "unavailable", "unknown"}
_SOURCE_AUTHORITY_REJECTED_REASON = "source_authority_router_rejected"
_ROTATION_RADAR_PROXY_AUTHORITY_SOURCES = {"yahoo", "yahooquery", "yfinance", "yfinance_proxy"}
_ROTATION_RADAR_PROXY_AUTHORITY_SOURCE_TYPES = {"unofficial_proxy", "unofficial_public_api"}


@dataclass
class _ProviderAttempt:
    quotes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failed_symbol_reasons: Dict[str, str] = field(default_factory=dict)
    status: str = "not_configured"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _AlpacaQuoteResult:
    quote: Optional[Dict[str, Any]] = None
    window_failure_reasons: Dict[str, str] = field(default_factory=dict)


@dataclass
class _ConfiguredActivationStageResult:
    quotes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failed_symbol_reasons: Dict[str, str] = field(default_factory=dict)
    request_window_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    symbol_failure_samples: list[Dict[str, str]] = field(default_factory=list)
    timeout_symbol_count: int = 0


@dataclass(frozen=True)
class _IntradayWindowRequestPlan:
    start: datetime
    end: datetime
    selection_mode: str
    session_state: str
    session_date: str


def get_rotation_radar_quote_provider() -> QuoteProvider:
    _apply_rotation_radar_provider_deadline_override()
    return load_rotation_radar_quotes


def get_rotation_radar_provider_diagnostics() -> Dict[str, Any]:
    """Return sanitized configured-provider credential diagnostics without network calls."""

    credentials = get_provider_credentials(_CONFIGURED_PROVIDER_ID)
    limits = _configured_activation_limits()
    return {
        **_configured_provider_base_metadata(credentials),
        "maxSymbolsPerWindow": limits["maxSymbolsPerWindow"],
        "maxProbeSymbols": limits["maxProbeSymbols"],
        "perWindowTimeout": limits["perWindowTimeout"],
        "totalProviderBudget": limits["totalProviderBudget"],
        "barFetchTimeout": limits["barFetchTimeout"],
        "providerDeadlineSeconds": _runtime_provider_deadline_seconds(),
    }


def run_rotation_radar_alpaca_live_smoke(
    *,
    per_window_timeout: Optional[float] = None,
    total_provider_budget: Optional[float] = None,
    bar_fetch_timeout: Optional[float] = None,
    connectivity_check: bool = False,
) -> Dict[str, Any]:
    """Run a bounded Alpaca-only activation smoke for rotation radar diagnostics."""

    smoke_symbols = tuple(_ALPACA_STABLE_ACTIVATION_PROBE_SYMBOLS)
    effective_bar_fetch_timeout = bar_fetch_timeout
    if effective_bar_fetch_timeout is None and per_window_timeout is not None:
        effective_bar_fetch_timeout = per_window_timeout
    override_applied = any(
        value is not None
        for value in (per_window_timeout, total_provider_budget, bar_fetch_timeout)
    )
    configured_attempt = _load_configured_provider_quotes(
        smoke_symbols,
        per_window_timeout=per_window_timeout,
        total_provider_budget=total_provider_budget,
        bar_fetch_timeout=effective_bar_fetch_timeout,
        connectivity_check=connectivity_check,
    )
    provider_diagnostics = _provider_activation_diagnostics(
        requested_symbols=smoke_symbols,
        quotes=configured_attempt.quotes,
        failed_symbol_reasons=configured_attempt.failed_symbol_reasons,
        configured_attempt=configured_attempt,
        yfinance_attempt=_ProviderAttempt(status="not_requested"),
        window_coverage={},
        source_summary={"sourceTier": _CONFIGURED_SOURCE_TIER if configured_attempt.quotes else "unknown"},
    )
    diagnostics = provider_diagnostics["alpacaActivationDiagnostics"]
    raw_reason = diagnostics.get("reason")
    endpoint_reachability = _safe_endpoint_reachability(
        configured_attempt.metadata.get("endpointReachability")
    )
    bar_timeout = _non_negative_float(
        configured_attempt.metadata.get("barFetchTimeout"),
        _default_bar_fetch_timeout(),
    )
    per_window = _non_negative_float(
        provider_diagnostics.get("perWindowTimeout"),
        float(_ALPACA_PER_WINDOW_TIMEOUT_SECONDS),
    )
    total_budget = _non_negative_float(
        provider_diagnostics.get("totalProviderBudget"),
        float(_ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS),
    )
    return {
        "credentialsPresent": bool(diagnostics.get("credentialsPresent", False)),
        "credentialSource": _safe_credential_source(provider_diagnostics.get("credentialSource")),
        "providerConstructed": bool(diagnostics.get("providerConstructed", False)),
        "configuredProviderFeed": str(
            provider_diagnostics.get("configuredProviderFeed")
            or provider_diagnostics.get("feed")
            or "iex"
        ),
        "feedEntitlementStatus": str(provider_diagnostics.get("feedEntitlementStatus") or "unknown"),
        "probePassed": bool(diagnostics.get("probePassed", False)),
        "freshnessValid": bool(diagnostics.get("freshnessValid", False)),
        "sourceMetadataValid": bool(diagnostics.get("sourceMetadataValid", False)),
        "sourceAuthorityAllowed": bool(diagnostics.get("sourceAuthorityAllowed", False)),
        "scoreContributionAllowed": bool(diagnostics.get("scoreContributionAllowed", False)),
        "fulfilledWindows": _as_string_sequence(diagnostics.get("fulfilledWindows")),
        "missingWindows": _as_string_sequence(diagnostics.get("missingWindows")),
        "staleWindows": _as_string_sequence(diagnostics.get("staleWindows")),
        "reason": str(raw_reason).strip() if raw_reason is not None else None,
        "activationBlocker": str(provider_diagnostics.get("activationBlocker") or raw_reason or "").strip() or None,
        "providerFailureReasons": _as_string_sequence(provider_diagnostics.get("providerFailureReasons")),
        "perWindowTimeout": per_window,
        "totalProviderBudget": total_budget,
        "barFetchTimeout": bar_timeout,
        "effectiveTimeoutBudgets": {
            "perWindowTimeout": per_window,
            "totalProviderBudget": total_budget,
            "barFetchTimeout": bar_timeout,
            "overrideApplied": bool(override_applied),
        },
        "timeoutDiagnosis": _smoke_timeout_diagnosis(
            provider_diagnostics=provider_diagnostics,
            endpoint_reachability=endpoint_reachability,
        ),
        "endpointReachability": endpoint_reachability,
        "proxyEnvironment": _safe_proxy_environment(provider_diagnostics.get("proxyEnvironment")),
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _short_intraday_window_request_plan(
    window: str,
    *,
    now_utc: Optional[datetime] = None,
) -> _IntradayWindowRequestPlan:
    current_utc = (now_utc or _utc_now()).astimezone(timezone.utc)
    current_et = current_utc.astimezone(_US_EASTERN_TZ)
    _, lookback, _ = _ALPACA_TIMEFRAMES[window]
    interval_minutes = 5 if window == "5m" else 15
    session_date = current_et.date()
    session_open = datetime.combine(session_date, _US_REGULAR_SESSION_OPEN, tzinfo=_US_EASTERN_TZ)
    session_close = datetime.combine(session_date, _US_REGULAR_SESSION_CLOSE, tzinfo=_US_EASTERN_TZ)
    minimum_completed_end = session_open + timedelta(minutes=interval_minutes)

    if current_et.weekday() >= 5:
        target_date = _previous_us_weekday(session_date)
        session_state = "weekend"
        selection_mode = "recent_completed_regular_session"
        request_end_et = datetime.combine(target_date, _US_REGULAR_SESSION_CLOSE, tzinfo=_US_EASTERN_TZ)
    elif current_et < session_open:
        target_date = _previous_us_weekday(session_date)
        session_state = "pre_market"
        selection_mode = "recent_completed_regular_session"
        request_end_et = datetime.combine(target_date, _US_REGULAR_SESSION_CLOSE, tzinfo=_US_EASTERN_TZ)
    elif current_et >= session_close:
        target_date = session_date
        session_state = "after_close"
        selection_mode = "recent_completed_regular_session"
        request_end_et = session_close
    else:
        floored_end = _floor_datetime_to_minutes(current_et, interval_minutes)
        if floored_end < minimum_completed_end:
            target_date = _previous_us_weekday(session_date)
            session_state = "insufficient_live_window"
            selection_mode = "recent_completed_regular_session"
            request_end_et = datetime.combine(target_date, _US_REGULAR_SESSION_CLOSE, tzinfo=_US_EASTERN_TZ)
        else:
            target_date = session_date
            session_state = "regular_open"
            selection_mode = "current_regular_session"
            request_end_et = min(floored_end, session_close)

    target_session_open = datetime.combine(target_date, _US_REGULAR_SESSION_OPEN, tzinfo=_US_EASTERN_TZ)
    request_start_et = max(target_session_open, request_end_et - lookback)
    return _IntradayWindowRequestPlan(
        start=request_start_et.astimezone(timezone.utc),
        end=request_end_et.astimezone(timezone.utc),
        selection_mode=selection_mode,
        session_state=session_state,
        session_date=target_date.isoformat(),
    )


def _short_intraday_window_plan_metadata(
    *,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Dict[str, str]]:
    current_utc = now_utc or _utc_now()
    metadata: Dict[str, Dict[str, str]] = {}
    for window in _SHORT_INTRADAY_WINDOWS:
        plan = _short_intraday_window_request_plan(window, now_utc=current_utc)
        metadata[window] = {
            "selectionMode": plan.selection_mode,
            "sessionState": plan.session_state,
            "sessionDate": plan.session_date,
            "start": plan.start.isoformat(),
            "end": plan.end.isoformat(),
        }
    return metadata


def _previous_us_weekday(value: Any) -> Any:
    previous = value - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return previous


def _floor_datetime_to_minutes(value: datetime, interval_minutes: int) -> datetime:
    floored = value.replace(second=0, microsecond=0)
    remainder = floored.minute % max(1, int(interval_minutes))
    if remainder:
        floored -= timedelta(minutes=remainder)
    return floored


def load_rotation_radar_quotes(symbols: Iterable[str]) -> Dict[str, Any]:
    requested_symbols = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    configured_attempt = _load_configured_provider_quotes(requested_symbols)
    quotes: Dict[str, Dict[str, Any]] = dict(configured_attempt.quotes)
    yfinance_symbols = [symbol for symbol in requested_symbols if symbol not in quotes]
    yfinance_attempt = _load_yfinance_quotes(yfinance_symbols)
    quotes.update(yfinance_attempt.quotes)

    failed_symbol_reasons = {
        symbol: reason
        for symbol, reason in {
            **configured_attempt.failed_symbol_reasons,
            **yfinance_attempt.failed_symbol_reasons,
        }.items()
        if symbol not in quotes
    }
    provider_metadata = _quote_metadata(
        requested_symbols=requested_symbols,
        quotes=quotes,
        failed_symbol_reasons=failed_symbol_reasons,
        configured_attempt=configured_attempt,
        yfinance_attempt=yfinance_attempt,
    )

    return {
        "quotes": quotes,
        "metadata": provider_metadata,
    }


def _load_configured_provider_quotes(
    symbols: Sequence[str],
    *,
    per_window_timeout: Optional[float] = None,
    total_provider_budget: Optional[float] = None,
    bar_fetch_timeout: Optional[float] = None,
    connectivity_check: bool = False,
) -> _ProviderAttempt:
    now_utc = _utc_now()
    credentials = get_provider_credentials(_CONFIGURED_PROVIDER_ID)
    limits = _configured_activation_limits(
        per_window_timeout=per_window_timeout,
        total_provider_budget=total_provider_budget,
        bar_fetch_timeout=bar_fetch_timeout,
    )
    metadata = _configured_provider_base_metadata(credentials)
    metadata.update({
        "maxSymbolsPerWindow": limits["maxSymbolsPerWindow"],
        "maxProbeSymbols": limits["maxProbeSymbols"],
        "perWindowTimeout": limits["perWindowTimeout"],
        "totalProviderBudget": limits["totalProviderBudget"],
        "barFetchTimeout": limits["barFetchTimeout"],
        "providerDeadlineSeconds": _runtime_provider_deadline_seconds(),
        "endpointReachability": _endpoint_reachability_not_checked(),
    })
    metadata["shortIntradayWindowPlans"] = _short_intraday_window_plan_metadata(now_utc=now_utc)
    if credentials.is_partial:
        return _ProviderAttempt(
            status="incomplete_credentials",
            metadata=_with_request_window_diagnostics(
                metadata,
                symbols=symbols,
                failure_class="missing_credentials",
            ),
        )
    if not credentials.is_configured:
        return _ProviderAttempt(
            status="not_configured",
            metadata=_with_request_window_diagnostics(
                metadata,
                symbols=symbols,
                failure_class="missing_credentials",
            ),
        )

    data_feed = str(metadata.get("feed") or credentials.extras.get("data_feed") or "iex").strip().lower() or "iex"
    metadata.update({
        "configuredProviderStatus": "configured",
        "configuredProviderFeed": data_feed,
        "feed": data_feed,
        "feedEntitlementStatus": "unknown",
    })
    try:
        fetcher = AlpacaFetcher(
            api_key_id=str(credentials.key_id or ""),
            secret_key=str(credentials.secret_key or ""),
            data_feed=data_feed,
            timeout=limits["barFetchTimeout"],
        )
    except Exception as exc:
        failure_reason = _sanitize_provider_failure_reason(str(exc))
        return _ProviderAttempt(
            status="provider_unavailable",
            failed_symbol_reasons={symbol: "provider_unavailable" for symbol in symbols},
            metadata={
                **metadata,
                "configuredProviderStatus": "provider_unavailable",
                "providerConstructed": False,
                "providerFailureReason": failure_reason,
                "providerFailureReasons": [failure_reason],
            },
        )
    metadata["providerConstructed"] = True
    proxy_diagnostics = getattr(fetcher, "proxy_diagnostics", None)
    if callable(proxy_diagnostics):
        try:
            metadata["proxyEnvironment"] = _safe_proxy_environment(proxy_diagnostics())
        except Exception:
            metadata["proxyEnvironment"] = {}
    if connectivity_check:
        metadata["endpointReachability"] = _run_endpoint_reachability_check(
            fetcher,
            timeout=limits["barFetchTimeout"],
        )

    max_workers = max(1, int(_QUOTE_PROVIDER_MAX_WORKERS))
    activation_probe_symbols = _configured_provider_stable_probe_symbols(
        symbols,
        max_probe_symbols=limits["maxProbeSymbols"],
    )
    diagnostic_probe_symbols = _configured_provider_probe_symbols(
        symbols,
        max_probe_symbols=limits["maxProbeSymbols"],
        stable_probe_symbols=activation_probe_symbols,
    )
    long_tail_probe_symbols = tuple(
        symbol for symbol in diagnostic_probe_symbols if symbol not in set(activation_probe_symbols)
    )
    quotes: Dict[str, Dict[str, Any]] = {}
    failed_symbol_reasons: Dict[str, str] = {}
    request_window_results = _empty_request_window_results(0)
    activation_request_window_results = _empty_request_window_results(0)
    symbol_failure_samples: list[Dict[str, str]] = []
    provider_budget_exceeded = False
    timeout_symbol_count = 0
    skipped_due_to_budget_count = 0
    activation_scope = "probe_only"
    requested_stage_symbols: set[str] = set()
    budget_started_at = monotonic()

    def remaining_budget() -> float:
        return limits["totalProviderBudget"] - (monotonic() - budget_started_at)

    activation_stage = _load_configured_provider_symbol_batch(
        fetcher=fetcher,
        symbols=activation_probe_symbols,
        data_feed=data_feed,
        timeout_seconds=min(limits["perWindowTimeout"], max(remaining_budget(), 0.001)),
        max_workers=max_workers,
        now_utc=now_utc,
    )
    _merge_configured_activation_stage(
        request_window_results,
        symbol_failure_samples,
        quotes,
        failed_symbol_reasons,
        activation_stage,
    )
    _merge_configured_activation_stage(
        activation_request_window_results,
        [],
        {},
        {},
        activation_stage,
    )
    requested_stage_symbols.update(activation_probe_symbols)
    timeout_symbol_count += activation_stage.timeout_symbol_count
    provider_budget_exceeded = provider_budget_exceeded or activation_stage.timeout_symbol_count > 0
    activation_minimum_success_count = _minimum_required_success_count(len(activation_probe_symbols))
    activation_window_results = _finalize_request_window_results(
        activation_request_window_results,
        minimum_success_count=activation_minimum_success_count,
    )
    activation_probe_succeeded = bool(activation_probe_symbols) and all(
        bool(activation_window_results.get(window, {}).get("fulfilled"))
        for window in _ALPACA_TIMEFRAMES
    )

    if long_tail_probe_symbols:
        budget_left = remaining_budget()
        if budget_left <= 0:
            provider_budget_exceeded = True
            skipped_due_to_budget_count += len(long_tail_probe_symbols)
        else:
            diagnostic_stage = _load_configured_provider_symbol_batch(
                fetcher=fetcher,
                symbols=long_tail_probe_symbols,
                data_feed=data_feed,
                timeout_seconds=min(limits["perWindowTimeout"], max(budget_left, 0.001)),
                max_workers=max_workers,
                now_utc=now_utc,
            )
            _merge_configured_activation_stage(
                request_window_results,
                symbol_failure_samples,
                quotes,
                failed_symbol_reasons,
                diagnostic_stage,
            )
            requested_stage_symbols.update(long_tail_probe_symbols)
            timeout_symbol_count += diagnostic_stage.timeout_symbol_count
            provider_budget_exceeded = provider_budget_exceeded or diagnostic_stage.timeout_symbol_count > 0

    remaining_symbols = [symbol for symbol in symbols if symbol not in requested_stage_symbols]
    if not symbols:
        activation_scope = "full_universe"
    elif activation_probe_succeeded and not remaining_symbols:
        activation_scope = "full_universe"
    elif activation_probe_succeeded and remaining_symbols:
        if remaining_budget() <= 0:
            provider_budget_exceeded = True
            skipped_due_to_budget_count += len(remaining_symbols)
        else:
            activation_scope = "partial_universe"
            while remaining_symbols:
                budget_left = remaining_budget()
                if budget_left <= 0:
                    provider_budget_exceeded = True
                    skipped_due_to_budget_count += len(remaining_symbols)
                    break
                batch = remaining_symbols[:limits["maxSymbolsPerWindow"]]
                remaining_symbols = remaining_symbols[len(batch):]
                batch_stage = _load_configured_provider_symbol_batch(
                    fetcher=fetcher,
                    symbols=batch,
                    data_feed=data_feed,
                    timeout_seconds=min(limits["perWindowTimeout"], max(budget_left, 0.001)),
                    max_workers=max_workers,
                    now_utc=now_utc,
                )
                _merge_configured_activation_stage(
                    request_window_results,
                    symbol_failure_samples,
                    quotes,
                    failed_symbol_reasons,
                    batch_stage,
                )
                requested_stage_symbols.update(batch)
                timeout_symbol_count += batch_stage.timeout_symbol_count
                if batch_stage.timeout_symbol_count:
                    provider_budget_exceeded = True
                    skipped_due_to_budget_count += len(remaining_symbols)
                    break
            if not provider_budget_exceeded and not remaining_symbols:
                activation_scope = "full_universe"

    if quotes and (failed_symbol_reasons or provider_budget_exceeded or skipped_due_to_budget_count):
        status = "partial"
    elif quotes:
        status = "success"
    else:
        status = "fallback" if symbols else "success"
    request_window_results = _finalize_request_window_results(
        request_window_results,
    )
    activation_window_results = _finalize_request_window_results(
        activation_request_window_results,
        minimum_success_count=activation_minimum_success_count,
    )
    diagnostic_fulfilled_windows = _fulfilled_windows_from_request_results(request_window_results)
    diagnostic_missing_windows = _missing_windows_from_request_results(request_window_results)
    configured_fulfilled_windows = _fulfilled_windows_from_request_results(activation_window_results)
    configured_missing_windows = _missing_windows_from_request_results(activation_window_results)
    configured_failure_reasons = [
        *_failure_classes_from_request_results(request_window_results),
        *(["timeout"] if provider_budget_exceeded or timeout_symbol_count or skipped_due_to_budget_count else []),
    ]
    provider_failure_reasons = (
        _bounded_unique_reasons(_sort_failure_classes(configured_failure_reasons))
        if configured_failure_reasons
        else _bounded_unique_reasons(failed_symbol_reasons.values())
    )
    provider_failure_reason = provider_failure_reasons[0] if provider_failure_reasons else None
    any_configured_provider_data_available = _any_configured_provider_data_available(request_window_results)
    configured_provider_window_coverage_met = bool(configured_fulfilled_windows)
    partial_activation_eligible = bool(configured_fulfilled_windows and configured_missing_windows)
    minimum_activation_coverage_met = configured_provider_window_coverage_met
    dominant_provider_blocker = _dominant_provider_blocker(
        request_window_results=request_window_results,
        provider_failure_reasons=provider_failure_reasons,
    )
    activation_limits = {
        "maxSymbolsPerWindow": limits["maxSymbolsPerWindow"],
        "maxProbeSymbols": limits["maxProbeSymbols"],
        "perWindowTimeout": limits["perWindowTimeout"],
        "totalProviderBudget": limits["totalProviderBudget"],
        "providerDeadlineSeconds": _runtime_provider_deadline_seconds(),
        "probeSymbolCount": len(diagnostic_probe_symbols),
        "activationProbeSymbolCount": len(activation_probe_symbols),
        "diagnosticProbeSymbolCount": len(diagnostic_probe_symbols),
        "fullUniverseSymbolCount": len(symbols),
        "providerBudgetExceeded": bool(provider_budget_exceeded),
        "timeoutSymbolCount": int(timeout_symbol_count),
        "skippedDueToBudgetCount": int(skipped_due_to_budget_count),
        "activationScope": activation_scope,
        "minimumActivationCoverageMet": minimum_activation_coverage_met,
        "minimumActivationSuccessRatio": _activation_success_ratio(),
        "minimumActivationSuccessCount": activation_minimum_success_count,
        "anyConfiguredProviderDataAvailable": any_configured_provider_data_available,
        "configuredProviderWindowCoverageMet": configured_provider_window_coverage_met,
        "partialActivationEligible": partial_activation_eligible,
        "dominantProviderBlocker": dominant_provider_blocker,
        "stableActivationProbeSymbols": list(activation_probe_symbols),
        "longTailProbeSymbols": list(long_tail_probe_symbols),
    }
    return _ProviderAttempt(
        quotes=quotes,
        failed_symbol_reasons=failed_symbol_reasons,
        status=status,
        metadata={
            **metadata,
            **activation_limits,
            "configuredProviderStatus": status if status != "success" else "success",
            "configuredProviderFeed": data_feed,
            "feed": data_feed,
            "providerConstructed": True,
            "providerFailureReason": provider_failure_reason,
            "providerFailureReasons": provider_failure_reasons,
            "requestWindowResults": request_window_results,
            "activationWindowResults": activation_window_results,
            "diagnosticWindowResults": request_window_results,
            "diagnosticFulfilledWindows": diagnostic_fulfilled_windows,
            "diagnosticMissingWindows": diagnostic_missing_windows,
            "symbolFailureSamples": symbol_failure_samples[:_FAILED_SYMBOL_LIST_LIMIT],
            "successSymbolsByWindow": _symbols_by_window_from_request_results(
                request_window_results,
                "successSymbols",
            ),
            "failedSymbolsByWindow": _symbols_by_window_from_request_results(
                request_window_results,
                "failedSymbols",
            ),
            "timedOutSymbolsByWindow": _symbols_by_window_from_request_results(
                request_window_results,
                "timedOutSymbols",
            ),
            "emptyResponseSymbolsByWindow": _symbols_by_window_from_request_results(
                request_window_results,
                "emptyResponseSymbols",
            ),
            "configuredFulfilledWindows": configured_fulfilled_windows,
            "configuredMissingWindows": configured_missing_windows,
            "configuredProviderFulfilledWindows": configured_fulfilled_windows,
            "configuredProviderMissingWindows": configured_missing_windows,
        },
    )


def _configured_activation_limits(
    *,
    per_window_timeout: Optional[float] = None,
    total_provider_budget: Optional[float] = None,
    bar_fetch_timeout: Optional[float] = None,
) -> Dict[str, Any]:
    env_per_window_timeout = _runtime_env_timeout_override(
        _ALPACA_PER_WINDOW_TIMEOUT_ENV,
        max_value=_ALPACA_MAX_PER_WINDOW_TIMEOUT_SECONDS,
    )
    default_per_window_timeout = (
        env_per_window_timeout
        if env_per_window_timeout is not None
        else float(_ALPACA_PER_WINDOW_TIMEOUT_SECONDS)
    )
    default_total_provider_budget = _runtime_env_timeout_default(
        _ALPACA_TOTAL_PROVIDER_BUDGET_ENV,
        default=float(_ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS),
        max_value=_ALPACA_MAX_TOTAL_PROVIDER_BUDGET_SECONDS,
    )
    default_bar_fetch_timeout = (
        env_per_window_timeout
        if env_per_window_timeout is not None and per_window_timeout is None and bar_fetch_timeout is None
        else _default_bar_fetch_timeout()
    )
    return {
        "maxSymbolsPerWindow": max(1, int(_ALPACA_MAX_SYMBOLS_PER_WINDOW)),
        "maxProbeSymbols": max(1, int(_ALPACA_MAX_PROBE_SYMBOLS)),
        "perWindowTimeout": _positive_timeout_value(
            per_window_timeout,
            default_per_window_timeout,
            max_value=_ALPACA_MAX_PER_WINDOW_TIMEOUT_SECONDS,
        ),
        "totalProviderBudget": _positive_timeout_value(
            total_provider_budget,
            default_total_provider_budget,
            max_value=_ALPACA_MAX_TOTAL_PROVIDER_BUDGET_SECONDS,
        ),
        "barFetchTimeout": _positive_timeout_value(
            bar_fetch_timeout,
            default_bar_fetch_timeout,
            max_value=_ALPACA_MAX_PER_WINDOW_TIMEOUT_SECONDS,
        ),
    }


def _default_bar_fetch_timeout() -> float:
    return float(max(1, int(float(_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS))))


def _runtime_provider_deadline_seconds() -> float:
    return _runtime_env_timeout_default(
        _ALPACA_PROVIDER_DEADLINE_ENV,
        default=float(_ALPACA_PROVIDER_DEADLINE_SECONDS),
        max_value=_ALPACA_MAX_PROVIDER_DEADLINE_SECONDS,
    )


def _apply_rotation_radar_provider_deadline_override() -> float:
    deadline = _runtime_provider_deadline_seconds()
    try:
        from src.services import market_rotation_radar_service

        market_rotation_radar_service._QUOTE_PROVIDER_TIMEOUT_SECONDS = deadline
    except Exception:
        pass
    return deadline


def _runtime_env_timeout_default(env_name: str, *, default: float, max_value: float) -> float:
    parsed = _runtime_env_timeout_override(env_name, max_value=max_value)
    return float(default) if parsed is None else parsed


def _runtime_env_timeout_override(env_name: str, *, max_value: float) -> Optional[float]:
    raw_value = os.environ.get(env_name)
    if raw_value is None:
        return None
    raw_text = str(raw_value).strip()
    if not raw_text:
        return None
    try:
        parsed = float(raw_text)
    except Exception:
        return None
    if parsed <= 0:
        return None
    return min(parsed, float(max_value))


def _positive_timeout_value(value: Any, default: float, *, max_value: Optional[float] = None) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    if parsed <= 0:
        parsed = float(default)
    if max_value is not None:
        parsed = min(parsed, float(max_value))
    return max(0.001, parsed)


def _configured_provider_probe_symbols(
    symbols: Sequence[str],
    *,
    max_probe_symbols: int,
    stable_probe_symbols: Sequence[str] = (),
) -> tuple[str, ...]:
    requested = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
    candidates: list[str] = []
    candidates.extend(str(symbol) for symbol in stable_probe_symbols)
    for theme in list_rotation_theme_definitions("US"):
        candidates.extend(str(symbol) for symbol in theme.proxy_etfs)
        candidates.extend(str(symbol) for symbol in theme.benchmark_symbols)
    for theme in list_rotation_theme_definitions("US"):
        candidates.extend(str(symbol) for symbol in theme.primary_symbols[:1])
    candidates.extend(str(symbol) for symbol in symbols)

    probe: list[str] = []
    seen: set[str] = set()
    for raw_symbol in candidates:
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol or symbol in seen or symbol not in requested:
            continue
        seen.add(symbol)
        probe.append(symbol)
        if len(probe) >= max_probe_symbols:
            break
    return tuple(probe)


def _configured_provider_stable_probe_symbols(
    symbols: Sequence[str],
    *,
    max_probe_symbols: int,
) -> tuple[str, ...]:
    requested = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
    candidates = [symbol for symbol in _ALPACA_STABLE_ACTIVATION_PROBE_SYMBOLS if symbol in requested]
    if not candidates:
        candidates = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    probe: list[str] = []
    seen: set[str] = set()
    for symbol in candidates:
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        probe.append(symbol)
        if len(probe) >= max(1, int(max_probe_symbols)):
            break
    return tuple(probe)


def _load_configured_provider_symbol_batch(
    *,
    fetcher: AlpacaFetcher,
    symbols: Sequence[str],
    data_feed: str,
    timeout_seconds: float,
    max_workers: int,
    now_utc: datetime,
) -> _ConfiguredActivationStageResult:
    batch_symbols = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    result = _ConfiguredActivationStageResult(
        request_window_results=_empty_request_window_results(0),
    )
    if not batch_symbols:
        return result

    executor = ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), len(batch_symbols))))
    future_to_symbol = {
        executor.submit(_quote_from_alpaca_fetcher, fetcher, symbol, data_feed, now_utc): symbol
        for symbol in batch_symbols
    }
    processed_futures = set()
    try:
        for future in as_completed(future_to_symbol, timeout=max(float(timeout_seconds), 0.001)):
            processed_futures.add(future)
            symbol = future_to_symbol[future]
            _record_configured_future_result(result, future, symbol)
    except FuturesTimeoutError:
        for future, symbol in future_to_symbol.items():
            if future in processed_futures:
                continue
            if future.done():
                _record_configured_future_result(result, future, symbol)
                continue
            symbol = future_to_symbol[future]
            _record_symbol_request_attempt(result.request_window_results)
            _record_symbol_window_failures(
                result.request_window_results,
                result.symbol_failure_samples,
                symbol=symbol,
                failure_reasons={window: "timeout" for window in _ALPACA_TIMEFRAMES},
            )
            result.failed_symbol_reasons[symbol] = "quote_fetch_failed"
            result.timeout_symbol_count += 1
            future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return result


def _record_configured_future_result(
    result: _ConfiguredActivationStageResult,
    future: Any,
    symbol: str,
) -> None:
    _record_symbol_request_attempt(result.request_window_results)
    try:
        quote_result = future.result()
    except Exception as exc:
        failure_class = _classify_configured_failure(exc)
        _record_symbol_window_failures(
            result.request_window_results,
            result.symbol_failure_samples,
            symbol=symbol,
            failure_reasons={window: failure_class for window in _ALPACA_TIMEFRAMES},
        )
        result.failed_symbol_reasons[symbol] = _legacy_symbol_failure_reason([failure_class])
        return
    quote = quote_result.quote if isinstance(quote_result, _AlpacaQuoteResult) else quote_result
    window_failure_reasons = (
        quote_result.window_failure_reasons if isinstance(quote_result, _AlpacaQuoteResult) else {}
    )
    _record_symbol_window_outcome(
        result.request_window_results,
        result.symbol_failure_samples,
        symbol=symbol,
        quote=quote,
        window_failure_reasons=window_failure_reasons,
    )
    if quote is None:
        result.failed_symbol_reasons[symbol] = _legacy_symbol_failure_reason(window_failure_reasons.values())
        return
    result.quotes[symbol] = quote


def _record_symbol_request_attempt(request_window_results: Dict[str, Dict[str, Any]]) -> None:
    for window in _ALPACA_TIMEFRAMES:
        request_window_results.setdefault(
            window,
            {
                "requestedSymbolCount": 0,
                "successCount": 0,
                "failureCount": 0,
                "failureClasses": {},
                "dominantFailureClass": None,
                "failureSymbolsByClass": {},
                "timedOutSymbols": [],
                "emptyResponseSymbols": [],
                "successSymbols": [],
                "failedSymbols": [],
                "successRatio": 0.0,
                "minimumRequiredSuccessRatio": _activation_success_ratio(),
                "minimumRequiredSuccessCount": 0,
                "fulfilled": False,
            },
        )
        request_window_results[window]["requestedSymbolCount"] = int(
            request_window_results[window].get("requestedSymbolCount") or 0
        ) + 1


def _merge_configured_activation_stage(
    request_window_results: Dict[str, Dict[str, Any]],
    symbol_failure_samples: list[Dict[str, str]],
    quotes: Dict[str, Dict[str, Any]],
    failed_symbol_reasons: Dict[str, str],
    stage: _ConfiguredActivationStageResult,
) -> None:
    quotes.update(stage.quotes)
    failed_symbol_reasons.update(stage.failed_symbol_reasons)
    for window in _ALPACA_TIMEFRAMES:
        source = stage.request_window_results.get(window, {})
        target = request_window_results.setdefault(window, _empty_request_window_results(0)[window])
        target["requestedSymbolCount"] = int(target.get("requestedSymbolCount") or 0) + int(
            source.get("requestedSymbolCount") or 0
        )
        target["successCount"] = int(target.get("successCount") or 0) + int(source.get("successCount") or 0)
        target["failureCount"] = int(target.get("failureCount") or 0) + int(source.get("failureCount") or 0)
        target_classes = target.setdefault("failureClasses", {})
        for failure_class, count in dict(source.get("failureClasses") or {}).items():
            normalized = _normalize_configured_failure_class(failure_class)
            target_classes[normalized] = int(target_classes.get(normalized) or 0) + int(count or 0)
        target_symbols_by_class = target.setdefault("failureSymbolsByClass", {})
        for failure_class, raw_symbols in dict(source.get("failureSymbolsByClass") or {}).items():
            normalized = _normalize_configured_failure_class(failure_class)
            target_symbols = target_symbols_by_class.setdefault(normalized, [])
            _extend_bounded_symbols(target_symbols, raw_symbols)
        _extend_bounded_symbols(target.setdefault("timedOutSymbols", []), source.get("timedOutSymbols"))
        _extend_bounded_symbols(target.setdefault("emptyResponseSymbols", []), source.get("emptyResponseSymbols"))
        _extend_bounded_symbols(target.setdefault("successSymbols", []), source.get("successSymbols"))
        _extend_bounded_symbols(target.setdefault("failedSymbols", []), source.get("failedSymbols"))
    for sample in stage.symbol_failure_samples:
        if len(symbol_failure_samples) >= _FAILED_SYMBOL_LIST_LIMIT:
            break
        symbol_failure_samples.append(sample)


def _configured_provider_base_metadata(credentials: ProviderCredentialBundle) -> Dict[str, Any]:
    missing_fields = _credential_env_field_names(credentials.missing_fields)
    data_feed = str(credentials.extras.get("data_feed") or "iex").strip().lower() or "iex"
    provider_failure_reason: Optional[str] = None
    provider_failure_reasons: list[str] = []
    configured_status = "configured" if credentials.is_configured else "not_configured"
    if credentials.is_partial:
        configured_status = "incomplete_credentials"
        provider_failure_reason = "credential_fields_missing"
        provider_failure_reasons = [provider_failure_reason]
    elif not credentials.is_configured and missing_fields:
        provider_failure_reason = "credentials_missing"
        provider_failure_reasons = [provider_failure_reason]
    return {
        "configuredProvider": _CONFIGURED_PROVIDER_ID,
        "configuredProviderStatus": configured_status,
        "configuredProviderAttempted": True,
        "providerAttempted": True,
        "configuredProviderName": _CONFIGURED_PROVIDER_ID,
        "credentialsPresent": bool(credentials.is_configured),
        "credentialFieldsMissing": missing_fields,
        "missingCredentialFields": missing_fields,
        "credentialSource": _credential_source(credentials),
        "providerConstructed": False,
        "providerFailureReason": provider_failure_reason,
        "providerFailureReasons": provider_failure_reasons,
        "configuredProviderFeed": data_feed,
        "feed": data_feed,
        "feedEntitlementStatus": "unknown" if credentials.is_configured else "not_checked",
    }


def _with_request_window_diagnostics(
    metadata: Mapping[str, Any],
    *,
    symbols: Sequence[str],
    failure_class: str,
) -> Dict[str, Any]:
    request_window_results = _empty_request_window_results(len(symbols))
    symbol_failure_samples: list[Dict[str, str]] = []
    for symbol in symbols:
        _record_symbol_window_failures(
            request_window_results,
            symbol_failure_samples,
            symbol=symbol,
            failure_reasons={window: failure_class for window in _ALPACA_TIMEFRAMES},
        )
    finalized_results = _finalize_request_window_results(request_window_results)
    provider_failure_reasons = _bounded_unique_reasons(_as_string_sequence(metadata.get("providerFailureReasons")))
    fulfilled_windows = _fulfilled_windows_from_request_results(finalized_results)
    missing_windows = _missing_windows_from_request_results(finalized_results)
    any_configured_provider_data_available = _any_configured_provider_data_available(finalized_results)
    configured_provider_window_coverage_met = bool(fulfilled_windows)
    return {
        **dict(metadata),
        "requestWindowResults": finalized_results,
        "activationWindowResults": finalized_results,
        "diagnosticWindowResults": finalized_results,
        "symbolFailureSamples": symbol_failure_samples[:_FAILED_SYMBOL_LIST_LIMIT],
        "successSymbolsByWindow": _symbols_by_window_from_request_results(finalized_results, "successSymbols"),
        "failedSymbolsByWindow": _symbols_by_window_from_request_results(finalized_results, "failedSymbols"),
        "timedOutSymbolsByWindow": _symbols_by_window_from_request_results(finalized_results, "timedOutSymbols"),
        "emptyResponseSymbolsByWindow": _symbols_by_window_from_request_results(finalized_results, "emptyResponseSymbols"),
        "configuredFulfilledWindows": fulfilled_windows,
        "configuredMissingWindows": missing_windows,
        "configuredProviderFulfilledWindows": fulfilled_windows,
        "configuredProviderMissingWindows": missing_windows,
        "diagnosticFulfilledWindows": fulfilled_windows,
        "diagnosticMissingWindows": missing_windows,
        "anyConfiguredProviderDataAvailable": any_configured_provider_data_available,
        "configuredProviderWindowCoverageMet": configured_provider_window_coverage_met,
        "partialActivationEligible": bool(fulfilled_windows and missing_windows),
        "dominantProviderBlocker": _dominant_provider_blocker(
            request_window_results=finalized_results,
            provider_failure_reasons=provider_failure_reasons,
        ),
        "minimumActivationCoverageMet": configured_provider_window_coverage_met,
        "minimumActivationSuccessRatio": _activation_success_ratio(),
        "minimumActivationSuccessCount": _minimum_required_success_count(len(symbols)),
        "providerFailureReasons": provider_failure_reasons,
    }


def _empty_request_window_results(requested_symbol_count: int) -> Dict[str, Dict[str, Any]]:
    requested_count = max(0, int(requested_symbol_count or 0))
    return {
        window: {
            "requestedSymbolCount": requested_count,
            "successCount": 0,
            "failureCount": 0,
            "failureClasses": {},
            "dominantFailureClass": None,
            "failureSymbolsByClass": {},
            "timedOutSymbols": [],
            "emptyResponseSymbols": [],
            "successSymbols": [],
            "failedSymbols": [],
            "successRatio": 0.0,
            "minimumRequiredSuccessRatio": _activation_success_ratio(),
            "minimumRequiredSuccessCount": _minimum_required_success_count(requested_count),
            "fulfilled": False,
        }
        for window in _ALPACA_TIMEFRAMES
    }


def _record_symbol_window_outcome(
    request_window_results: Dict[str, Dict[str, Any]],
    symbol_failure_samples: list[Dict[str, str]],
    *,
    symbol: str,
    quote: Optional[Mapping[str, Any]],
    window_failure_reasons: Mapping[str, str],
) -> None:
    time_windows = quote.get("timeWindows") if isinstance(quote, Mapping) else {}
    for window in _ALPACA_TIMEFRAMES:
        slot = time_windows.get(window) if isinstance(time_windows, Mapping) else None
        if isinstance(slot, Mapping) and slot.get("available", True):
            request_window_results[window]["successCount"] += 1
            _append_bounded_symbol(request_window_results[window].setdefault("successSymbols", []), symbol)
            continue
        failure_class = (
            str(window_failure_reasons.get(window) or "").strip()
            or _classify_configured_failure(slot.get("reason") if isinstance(slot, Mapping) else "")
            or "unknown"
        )
        _record_window_failure(
            request_window_results,
            symbol_failure_samples,
            symbol=symbol,
            window=window,
            failure_class=failure_class,
        )


def _record_symbol_window_failures(
    request_window_results: Dict[str, Dict[str, Any]],
    symbol_failure_samples: list[Dict[str, str]],
    *,
    symbol: str,
    failure_reasons: Mapping[str, str],
) -> None:
    for window in _ALPACA_TIMEFRAMES:
        _record_window_failure(
            request_window_results,
            symbol_failure_samples,
            symbol=symbol,
            window=window,
            failure_class=str(failure_reasons.get(window) or "unknown"),
        )


def _record_window_failure(
    request_window_results: Dict[str, Dict[str, Any]],
    symbol_failure_samples: list[Dict[str, str]],
    *,
    symbol: str,
    window: str,
    failure_class: str,
) -> None:
    normalized = _normalize_configured_failure_class(failure_class)
    window_result = request_window_results.setdefault(
        window,
        {
            "requestedSymbolCount": 0,
            "successCount": 0,
            "failureCount": 0,
            "failureClasses": {},
            "dominantFailureClass": None,
            "failureSymbolsByClass": {},
            "timedOutSymbols": [],
            "emptyResponseSymbols": [],
            "fulfilled": False,
        },
    )
    window_result["failureCount"] = int(window_result.get("failureCount") or 0) + 1
    failure_classes = window_result.setdefault("failureClasses", {})
    failure_classes[normalized] = int(failure_classes.get(normalized) or 0) + 1
    failure_symbols_by_class = window_result.setdefault("failureSymbolsByClass", {})
    _append_bounded_symbol(failure_symbols_by_class.setdefault(normalized, []), symbol)
    if _is_timeout_failure_class(normalized):
        _append_bounded_symbol(window_result.setdefault("timedOutSymbols", []), symbol)
    if normalized == "empty_response":
        _append_bounded_symbol(window_result.setdefault("emptyResponseSymbols", []), symbol)
    _append_bounded_symbol(window_result.setdefault("failedSymbols", []), symbol)
    if len(symbol_failure_samples) < _FAILED_SYMBOL_LIST_LIMIT:
        symbol_failure_samples.append({
            "symbol": _sanitize_symbol(symbol),
            "window": str(window),
            "failureClass": normalized,
        })


def _finalize_request_window_results(
    request_window_results: Mapping[str, Mapping[str, Any]],
    *,
    minimum_success_count: int = 0,
) -> Dict[str, Dict[str, Any]]:
    finalized: Dict[str, Dict[str, Any]] = {}
    success_floor = max(0, int(minimum_success_count or 0))
    for window in _ALPACA_TIMEFRAMES:
        raw = request_window_results.get(window, {})
        requested_count = max(0, int(raw.get("requestedSymbolCount") or 0))
        success_count = max(0, int(raw.get("successCount") or 0))
        failure_count = max(0, int(raw.get("failureCount") or 0))
        required_success_count = min(
            requested_count,
            success_floor if success_floor else _minimum_required_success_count(requested_count),
        )
        failure_classes = {
            _normalize_configured_failure_class(failure_class): max(0, int(count or 0))
            for failure_class, count in dict(raw.get("failureClasses") or {}).items()
            if max(0, int(count or 0)) > 0
        }
        failure_symbols_by_class = _failure_symbols_by_class(raw.get("failureSymbolsByClass"))
        success_ratio = _success_ratio(success_count, requested_count)
        finalized[window] = {
            "requestedSymbolCount": requested_count,
            "successCount": success_count,
            "failureCount": failure_count,
            "failureClasses": failure_classes,
            "dominantFailureClass": _dominant_failure_class(failure_classes),
            "failureSymbolsByClass": failure_symbols_by_class,
            "timedOutSymbols": _bounded_unique_symbols(
                _as_string_sequence(raw.get("timedOutSymbols"))
                or failure_symbols_by_class.get("timeout", [])
            ),
            "emptyResponseSymbols": _bounded_unique_symbols(
                _as_string_sequence(raw.get("emptyResponseSymbols"))
                or failure_symbols_by_class.get("empty_response", [])
            ),
            "successSymbols": _bounded_unique_symbols(_as_string_sequence(raw.get("successSymbols"))),
            "failedSymbols": _bounded_unique_symbols(_as_string_sequence(raw.get("failedSymbols"))),
            "successRatio": success_ratio,
            "minimumRequiredSuccessRatio": _activation_success_ratio(),
            "minimumRequiredSuccessCount": required_success_count,
            "fulfilled": bool(requested_count > 0 and success_count >= required_success_count),
        }
    return finalized


def _fulfilled_windows_from_request_results(request_window_results: Mapping[str, Mapping[str, Any]]) -> list[str]:
    return [
        window
        for window in _ALPACA_TIMEFRAMES
        if bool(request_window_results.get(window, {}).get("fulfilled"))
    ]


def _missing_windows_from_request_results(request_window_results: Mapping[str, Mapping[str, Any]]) -> list[str]:
    return [
        window
        for window in _ALPACA_TIMEFRAMES
        if not bool(request_window_results.get(window, {}).get("fulfilled"))
    ]


def _activation_success_ratio() -> float:
    return round(max(0.0, min(1.0, float(_ALPACA_MINIMUM_ACTIVATION_SUCCESS_RATIO))), 4)


def _minimum_required_success_count(requested_symbol_count: int) -> int:
    requested_count = max(0, int(requested_symbol_count or 0))
    if requested_count <= 0:
        return 0
    return max(1, int(ceil(requested_count * _activation_success_ratio())))


def _success_ratio(success_count: int, requested_count: int) -> float:
    requested = max(0, int(requested_count or 0))
    if requested <= 0:
        return 0.0
    return round(max(0.0, int(success_count or 0)) / requested, 4)


def _append_bounded_symbol(symbols: list[str], symbol: Any) -> None:
    normalized = _sanitize_symbol(symbol)
    if not normalized or normalized in symbols or len(symbols) >= _FAILED_SYMBOL_LIST_LIMIT:
        return
    symbols.append(normalized)


def _extend_bounded_symbols(symbols: list[str], values: Any) -> None:
    for value in _as_string_sequence(values):
        _append_bounded_symbol(symbols, value)


def _symbols_by_window_from_request_results(
    request_window_results: Mapping[str, Mapping[str, Any]],
    field_name: str,
) -> Dict[str, list[str]]:
    return {
        window: _bounded_unique_symbols(_as_string_sequence(request_window_results.get(window, {}).get(field_name)))
        for window in _ALPACA_TIMEFRAMES
    }


def _failure_symbols_by_class(raw_symbols_by_class: Any) -> Dict[str, list[str]]:
    if not isinstance(raw_symbols_by_class, Mapping):
        return {}
    sanitized: Dict[str, list[str]] = {}
    for failure_class, symbols in raw_symbols_by_class.items():
        normalized = _normalize_configured_failure_class(failure_class)
        sanitized_symbols = _bounded_unique_symbols(_as_string_sequence(symbols))
        if sanitized_symbols:
            sanitized[normalized] = sanitized_symbols
    return sanitized


def _any_configured_provider_data_available(
    request_window_results: Mapping[str, Mapping[str, Any]]
) -> bool:
    return any(
        int(request_window_results.get(window, {}).get("successCount") or 0) > 0
        for window in _ALPACA_TIMEFRAMES
    )


def _dominant_provider_blocker(
    *,
    request_window_results: Mapping[str, Mapping[str, Any]],
    provider_failure_reasons: Sequence[str],
) -> Optional[str]:
    failure_classes: Dict[str, int] = {}
    for window in _ALPACA_TIMEFRAMES:
        result = request_window_results.get(window, {})
        raw_classes = result.get("failureClasses") if isinstance(result, Mapping) else {}
        if not isinstance(raw_classes, Mapping):
            continue
        for failure_class, count in raw_classes.items():
            normalized = _normalize_configured_failure_class(failure_class)
            failure_classes[normalized] = failure_classes.get(normalized, 0) + max(0, int(count or 0))
    dominant = _dominant_failure_class(failure_classes)
    if dominant:
        return dominant
    primary = _primary_failure_class(provider_failure_reasons)
    return primary


def _failure_classes_from_request_results(request_window_results: Mapping[str, Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for window in _ALPACA_TIMEFRAMES:
        result = request_window_results.get(window, {})
        failure_classes = result.get("failureClasses") if isinstance(result, Mapping) else {}
        if isinstance(failure_classes, Mapping):
            reasons.extend(str(reason) for reason in failure_classes)
    return _bounded_unique_reasons(_sort_failure_classes(reasons))


def _sort_failure_classes(reasons: Iterable[str]) -> list[str]:
    seen = {reason for reason in reasons if str(reason or "").strip()}
    return [
        reason
        for reason in _CONFIGURED_FAILURE_PRIORITY
        if reason in seen
    ] + sorted(reason for reason in seen if reason not in _CONFIGURED_FAILURE_PRIORITY)


def _dominant_failure_class(failure_classes: Mapping[str, int]) -> Optional[str]:
    if not failure_classes:
        return None
    return max(
        failure_classes.items(),
        key=lambda item: (int(item[1] or 0), -_failure_class_rank(item[0]), str(item[0])),
    )[0]


def _failure_class_rank(failure_class: str) -> int:
    try:
        return _CONFIGURED_FAILURE_PRIORITY.index(str(failure_class))
    except ValueError:
        return len(_CONFIGURED_FAILURE_PRIORITY)


def _normalize_configured_failure_class(failure_class: Any) -> str:
    normalized = str(failure_class or "").strip().lower()
    return normalized if normalized in _CONFIGURED_FAILURE_CLASSES else "unknown"


def _is_timeout_failure_class(failure_class: Any) -> bool:
    return _normalize_configured_failure_class(failure_class) in _TIMEOUT_FAILURE_CLASSES


def _is_network_failure_class(failure_class: Any) -> bool:
    return _normalize_configured_failure_class(failure_class) in _NETWORK_FAILURE_CLASSES


def _sanitize_symbol(symbol: Any) -> str:
    text = str(symbol or "").strip().upper()
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
    return "".join(char for char in text if char in allowed)[:24]


def _credential_env_field_names(missing_fields: Sequence[str]) -> list[str]:
    return [
        _ALPACA_CREDENTIAL_ENV_NAMES.get(str(field), str(field))
        for field in missing_fields
        if str(field or "").strip()
    ]


def _credential_source(credentials: ProviderCredentialBundle) -> str:
    source = str(getattr(credentials, "credential_source", "") or "").strip()
    if source in _CREDENTIAL_SOURCE_VALUES:
        return source
    if credentials.is_configured or credentials.is_partial:
        return "unknown"
    return "unavailable"


def _load_yfinance_quotes(symbols: Sequence[str]) -> _ProviderAttempt:
    quotes: Dict[str, Dict[str, Any]] = {}
    failed_symbols: list[str] = []
    failed_symbol_count = 0
    failed_symbol_reasons: Dict[str, str] = {}
    unavailable_reason_counts: Dict[str, int] = {}
    now_monotonic = monotonic()

    for symbol in symbols:
        cooldown_reason = _cooldown_reason(symbol, now_monotonic)
        if cooldown_reason:
            failed_symbol_count = _record_failed_symbol(
                symbol=symbol,
                reason=cooldown_reason,
                failed_symbols=failed_symbols,
                failed_symbol_count=failed_symbol_count,
                unavailable_reason_counts=unavailable_reason_counts,
                failed_symbol_reasons=failed_symbol_reasons,
            )
            continue

    fetch_symbols = [symbol for symbol in symbols if symbol not in failed_symbols]
    timeout_seconds = max(float(_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS), 0.001)
    max_workers = max(1, min(int(_QUOTE_PROVIDER_MAX_WORKERS), len(fetch_symbols) or 1))
    executor = ThreadPoolExecutor(max_workers=max_workers)
    future_to_symbol = {
        executor.submit(fetch_yfinance_quote_history_frame, symbol): symbol
        for symbol in fetch_symbols
    }
    try:
        for future in as_completed(future_to_symbol, timeout=timeout_seconds):
            symbol = future_to_symbol[future]
            try:
                frame = future.result()
            except Exception as exc:
                reason = _sanitize_unavailable_reason(str(exc))
                if reason in {"symbol_unavailable", "quote_unavailable"}:
                    _mark_symbol_unavailable(symbol, reason, now_monotonic)
                failed_symbol_count = _record_failed_symbol(
                    symbol=symbol,
                    reason=reason,
                    failed_symbols=failed_symbols,
                    failed_symbol_count=failed_symbol_count,
                    unavailable_reason_counts=unavailable_reason_counts,
                    failed_symbol_reasons=failed_symbol_reasons,
                )
                continue
            quote = _quote_from_history_frame(symbol, frame)
            if quote is None:
                reason = "symbol_unavailable"
                _mark_symbol_unavailable(symbol, reason, now_monotonic)
                failed_symbol_count = _record_failed_symbol(
                    symbol=symbol,
                    reason=reason,
                    failed_symbols=failed_symbols,
                    failed_symbol_count=failed_symbol_count,
                    unavailable_reason_counts=unavailable_reason_counts,
                    failed_symbol_reasons=failed_symbol_reasons,
                )
                continue
            quotes[symbol] = quote
    except FuturesTimeoutError:
        pending_symbols = [
            future_to_symbol[future]
            for future in future_to_symbol
            if not future.done()
        ]
        for symbol in pending_symbols:
            failed_symbol_count = _record_failed_symbol(
                symbol=symbol,
                reason="quote_fetch_failed",
                failed_symbols=failed_symbols,
                failed_symbol_count=failed_symbol_count,
                unavailable_reason_counts=unavailable_reason_counts,
                failed_symbol_reasons=failed_symbol_reasons,
            )
            future = next(
                (candidate for candidate, candidate_symbol in future_to_symbol.items() if candidate_symbol == symbol),
                None,
            )
            if future is not None:
                future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if quotes and failed_symbol_count:
        status = "partial"
    elif quotes:
        status = "success"
    else:
        status = "fallback" if symbols else "not_requested"
    unavailable_reason = _dominant_label(unavailable_reason_counts, default="symbol_unavailable") if unavailable_reason_counts else None
    return _ProviderAttempt(
        quotes=quotes,
        failed_symbol_reasons=failed_symbol_reasons,
        status=status,
        metadata={
            "unavailableReason": unavailable_reason,
            "failedSymbols": _bounded_unique_symbols(failed_symbols),
            "failedSymbolCount": failed_symbol_count,
        },
    )


def _quote_metadata(
    *,
    requested_symbols: Sequence[str],
    quotes: Mapping[str, Dict[str, Any]],
    failed_symbol_reasons: Mapping[str, str],
    configured_attempt: _ProviderAttempt,
    yfinance_attempt: _ProviderAttempt,
) -> Dict[str, Any]:
    freshness_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    source_label_counts: Dict[str, int] = {}
    source_tier_counts: Dict[str, int] = {}
    window_coverage = {window: 0 for window in ("5m", "15m", "60m", "1d")}
    as_of_candidates: list[str] = []
    for quote in quotes.values():
        freshness = str(quote.get("freshness") or "unknown")
        freshness_counts[freshness] = freshness_counts.get(freshness, 0) + 1
        source = str(quote.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
        source_label = str(quote.get("sourceLabel") or source)
        source_label_counts[source_label] = source_label_counts.get(source_label, 0) + 1
        source_tier = str(quote.get("sourceTier") or "unknown")
        source_tier_counts[source_tier] = source_tier_counts.get(source_tier, 0) + 1
        for window, slot in (quote.get("timeWindows") or {}).items():
            if window in window_coverage and isinstance(slot, Mapping) and slot.get("available", True):
                window_coverage[window] += 1
        if quote.get("asOf"):
            as_of_candidates.append(str(quote["asOf"]))

    requested_symbol_count = len(requested_symbols)
    usable_symbol_count = len(quotes)
    coverage_percent = round((usable_symbol_count / requested_symbol_count) * 100, 1) if requested_symbol_count else 0.0
    failed_symbol_count = len(failed_symbol_reasons)
    if usable_symbol_count == 0 and requested_symbol_count:
        status = "fallback"
    elif failed_symbol_count:
        status = "partial"
    else:
        status = "success"
    quote_mode = _metadata_quote_mode(quotes)
    source_summary = _metadata_source_summary(quotes)
    freshness = _metadata_freshness(
        quotes=quotes,
        failed_symbol_count=failed_symbol_count,
        fallback_used=bool(yfinance_attempt.quotes and configured_attempt.quotes),
    )
    confidence_weight = _confidence_weight(
        quotes=quotes,
        coverage_percent=coverage_percent,
        failed_symbol_count=failed_symbol_count,
    )
    unavailable_reason = (
        _dominant_label(_count_values(failed_symbol_reasons.values()), default="symbol_unavailable")
        if failed_symbol_reasons else None
    )
    provider_diagnostics = _provider_activation_diagnostics(
        requested_symbols=requested_symbols,
        quotes=quotes,
        failed_symbol_reasons=failed_symbol_reasons,
        configured_attempt=configured_attempt,
        yfinance_attempt=yfinance_attempt,
        window_coverage=window_coverage,
        source_summary=source_summary,
    )
    source_authority = _source_authority_diagnostics(
        source_summary=source_summary,
        provider_diagnostics=provider_diagnostics,
        status=status,
    )
    etf_authority_spine = _etf_authority_spine_diagnostics(
        requested_symbols=requested_symbols,
        quotes=quotes,
        configured_attempt=configured_attempt,
        provider_diagnostics=provider_diagnostics,
    )
    return {
        "status": status,
        "quoteMode": quote_mode,
        "source": source_summary["source"],
        "sourceLabel": source_summary["sourceLabel"],
        "sourceType": source_summary["sourceType"],
        "sourceTier": source_summary["sourceTier"],
        "providerTier": source_summary["providerTier"],
        "freshness": freshness,
        "asOf": max(as_of_candidates) if as_of_candidates else None,
        "confidenceWeight": confidence_weight,
        "degradationReasons": _degradation_reasons(
            coverage_percent=coverage_percent,
            failed_symbol_count=failed_symbol_count,
            source_summary=source_summary,
            freshness=freshness,
        ),
        "providerOrder": list(_QUOTE_PROVIDER_ORDER),
        "providerTimeoutSeconds": float(_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS),
        "configuredProviderStatus": configured_attempt.metadata.get("configuredProviderStatus", configured_attempt.status),
        "configuredProvider": _CONFIGURED_PROVIDER_ID,
        "configuredProviderFeed": configured_attempt.metadata.get("configuredProviderFeed"),
        "configuredProviderFailedSymbols": _bounded_unique_symbols(list(configured_attempt.failed_symbol_reasons)),
        "configuredProviderFailedSymbolCount": len(configured_attempt.failed_symbol_reasons),
        "configuredProviderFailedSymbolReasons": {
            symbol: configured_attempt.failed_symbol_reasons[symbol]
            for symbol in _bounded_unique_symbols(list(configured_attempt.failed_symbol_reasons))
        },
        "yfinanceProviderStatus": yfinance_attempt.status,
        "providerDiagnostics": {
            **provider_diagnostics,
            **source_authority,
            "etfAuthoritySpine": etf_authority_spine,
        },
        "noExternalCalls": False,
        "failedSymbols": _bounded_unique_symbols(list(failed_symbol_reasons)),
        "failedSymbolCount": failed_symbol_count,
        "failedSymbolReasons": {
            symbol: failed_symbol_reasons[symbol]
            for symbol in _bounded_unique_symbols(list(failed_symbol_reasons))
        },
        "unavailableReason": unavailable_reason,
        "coverage": {
            "requestedSymbolCount": requested_symbol_count,
            "usableSymbolCount": usable_symbol_count,
            "coveragePercent": coverage_percent,
        },
        "windowCoverage": {
            window: {
                "requestedSymbolCount": requested_symbol_count,
                "usableSymbolCount": count,
                "coveragePercent": round((count / requested_symbol_count) * 100, 1) if requested_symbol_count else 0.0,
            }
            for window, count in window_coverage.items()
        },
        "sourceCounts": source_counts,
        "sourceLabelCounts": source_label_counts,
        "sourceTierCounts": source_tier_counts,
        "freshnessCounts": freshness_counts,
        **source_authority,
    }


def _rotation_radar_quote_route_request() -> DataSourceRouteRequest:
    return DataSourceRouteRequest(
        market="US",
        asset_type="equity",
        use_case="rotation_radar",
        capability="quote",
        freshness_need="live",
        scoring_allowed=True,
        allow_network=False,
        reproducibility_required=False,
    )


def _source_authority_diagnostics(
    *,
    source_summary: Mapping[str, str],
    provider_diagnostics: Mapping[str, Any],
    status: str,
) -> Dict[str, Any]:
    route_snapshot = build_data_source_route_diagnostic_snapshot(
        _rotation_radar_quote_route_request()
    ).to_dict()
    source = str(source_summary.get("source") or "").strip().lower()
    source_type = str(source_summary.get("sourceType") or "").strip().lower()
    yfinance_fallback_used = bool(provider_diagnostics.get("yfinanceFallbackUsed", False))
    present = status not in {"fallback", "not_requested"}
    configured_activation_reason = _configured_activation_authority_reason(provider_diagnostics)

    route_rejected_reason_codes: list[str] = []
    source_authority_allowed = present
    source_authority_route_rejected = False
    source_authority_reason = None

    if (
        yfinance_fallback_used
        or source in _ROTATION_RADAR_PROXY_AUTHORITY_SOURCES
        or source_type in _ROTATION_RADAR_PROXY_AUTHORITY_SOURCE_TYPES
    ):
        route_rejected_reason_codes = list(
            route_snapshot.get("reasonCodes", {}).get("yfinance_current_baseline")
            or ("provider_not_eligible_for_scoring_route",)
        )
        source_authority_allowed = False
        source_authority_route_rejected = True
        source_authority_reason = _SOURCE_AUTHORITY_REJECTED_REASON
    elif source == _CONFIGURED_SOURCE and configured_activation_reason:
        source_authority_allowed = False
        source_authority_reason = configured_activation_reason
    elif not present:
        source_authority_allowed = False
        source_authority_reason = "provider_absent"

    return {
        "sourceAuthorityAllowed": bool(source_authority_allowed),
        "scoreContributionAllowed": bool(source_authority_allowed),
        "sourceAuthorityRouteRejected": bool(source_authority_route_rejected),
        "sourceAuthorityReason": source_authority_reason,
        "routeRejectedReasonCodes": route_rejected_reason_codes,
        "sourceAuthorityRouter": route_snapshot,
    }


def _configured_activation_authority_reason(provider_diagnostics: Mapping[str, Any]) -> Optional[str]:
    activation = provider_diagnostics.get("alpacaActivationDiagnostics")
    if not isinstance(activation, Mapping):
        return None
    if bool(activation.get("sourceAuthorityAllowed")) and bool(activation.get("scoreContributionAllowed")):
        return None
    reason = str(activation.get("reason") or "").strip()
    return reason or "alpaca_activation_gate_failed"


def _provider_activation_diagnostics(
    *,
    requested_symbols: Sequence[str],
    quotes: Mapping[str, Dict[str, Any]],
    failed_symbol_reasons: Mapping[str, str],
    configured_attempt: _ProviderAttempt,
    yfinance_attempt: _ProviderAttempt,
    window_coverage: Mapping[str, int],
    source_summary: Mapping[str, str],
) -> Dict[str, Any]:
    requested_windows = list(_ALPACA_TIMEFRAMES)
    requested_symbol_count = len(requested_symbols)
    request_window_results = _diagnostic_request_window_results(
        configured_attempt.metadata.get("requestWindowResults"),
        requested_symbol_count=requested_symbol_count,
    )
    provider_constructed = bool(configured_attempt.metadata.get("providerConstructed"))
    probe_symbol_count = _non_negative_int(configured_attempt.metadata.get("probeSymbolCount"), 0)
    activation_probe_symbol_count = _non_negative_int(
        configured_attempt.metadata.get("activationProbeSymbolCount"),
        probe_symbol_count or requested_symbol_count,
    )
    diagnostic_probe_symbol_count = _non_negative_int(
        configured_attempt.metadata.get("diagnosticProbeSymbolCount"),
        probe_symbol_count or requested_symbol_count,
    )
    activation_window_results = _diagnostic_request_window_results(
        configured_attempt.metadata.get("activationWindowResults"),
        requested_symbol_count=activation_probe_symbol_count or requested_symbol_count,
    )
    activation_results_for_coverage = activation_window_results or request_window_results
    if request_window_results:
        fulfilled_windows = _as_string_sequence(
            configured_attempt.metadata.get("configuredProviderFulfilledWindows")
        ) or _fulfilled_windows_from_request_results(activation_results_for_coverage)
        missing_windows = _as_string_sequence(
            configured_attempt.metadata.get("configuredProviderMissingWindows")
        ) or _missing_windows_from_request_results(activation_results_for_coverage)
    else:
        fulfilled_windows = [
            window
            for window in requested_windows
            if requested_symbol_count > 0 and int(window_coverage.get(window, 0)) >= requested_symbol_count
        ]
        missing_windows = [
            window
            for window in requested_windows
            if requested_symbol_count > 0 and int(window_coverage.get(window, 0)) < requested_symbol_count
        ]
    diagnostic_fulfilled_windows = _as_string_sequence(
        configured_attempt.metadata.get("diagnosticFulfilledWindows")
    ) or _fulfilled_windows_from_request_results(request_window_results)
    diagnostic_missing_windows = _as_string_sequence(
        configured_attempt.metadata.get("diagnosticMissingWindows")
    ) or _missing_windows_from_request_results(request_window_results)
    yfinance_fallback_used = yfinance_attempt.status != "not_requested"
    static_basket_fallback_used = bool(requested_symbol_count and not quotes)
    final_source_tier = str(source_summary.get("sourceTier") or "unknown")
    request_failure_classes = _failure_classes_from_request_results(request_window_results)
    full_universe_symbol_count = _non_negative_int(
        configured_attempt.metadata.get("fullUniverseSymbolCount"),
        requested_symbol_count,
    )
    provider_budget_exceeded = bool(configured_attempt.metadata.get("providerBudgetExceeded", False))
    timeout_symbol_count = _non_negative_int(configured_attempt.metadata.get("timeoutSymbolCount"), 0)
    skipped_due_to_budget_count = _non_negative_int(
        configured_attempt.metadata.get("skippedDueToBudgetCount"),
        0,
    )
    activation_scope = _activation_scope(configured_attempt.metadata.get("activationScope"))
    any_configured_provider_data_available = bool(
        configured_attempt.metadata.get("anyConfiguredProviderDataAvailable", False)
    ) or _any_configured_provider_data_available(request_window_results)
    configured_provider_window_coverage_met = bool(
        configured_attempt.metadata.get("configuredProviderWindowCoverageMet", False)
    ) or bool(fulfilled_windows)
    partial_activation_eligible = bool(
        configured_attempt.metadata.get("partialActivationEligible", False)
    ) or bool(fulfilled_windows and missing_windows)
    minimum_activation_coverage_met = bool(
        configured_attempt.metadata.get(
            "minimumActivationCoverageMet",
            configured_provider_window_coverage_met,
        )
    ) and configured_provider_window_coverage_met
    minimum_activation_success_ratio = _non_negative_float(
        configured_attempt.metadata.get("minimumActivationSuccessRatio"),
        _activation_success_ratio(),
    )
    minimum_activation_success_count = _non_negative_int(
        configured_attempt.metadata.get("minimumActivationSuccessCount"),
        _minimum_required_success_count(activation_probe_symbol_count or requested_symbol_count),
    )
    provider_failure_reasons = _bounded_unique_reasons(
        [
            *_as_string_sequence(configured_attempt.metadata.get("providerFailureReasons")),
            *(request_failure_classes if provider_constructed else []),
            *([] if request_failure_classes else configured_attempt.failed_symbol_reasons.values()),
            *failed_symbol_reasons.values(),
            *_quote_window_failure_reasons(quotes),
            *(["timeout"] if provider_budget_exceeded or timeout_symbol_count or skipped_due_to_budget_count else []),
        ]
    )
    dominant_provider_blocker = str(configured_attempt.metadata.get("dominantProviderBlocker") or "").strip()
    if not dominant_provider_blocker:
        dominant_provider_blocker = _dominant_provider_blocker(
            request_window_results=request_window_results,
            provider_failure_reasons=provider_failure_reasons,
        ) or ""
    short_intraday_window_plans = configured_attempt.metadata.get("shortIntradayWindowPlans")
    if not isinstance(short_intraday_window_plans, Mapping):
        short_intraday_window_plans = _short_intraday_window_plan_metadata()
    fallback_provider_used = bool(yfinance_fallback_used or static_basket_fallback_used)
    feed_entitlement_status = _feed_entitlement_status(
        configured_attempt.metadata,
        provider_failure_reasons=provider_failure_reasons,
        fulfilled_windows=fulfilled_windows,
        missing_windows=missing_windows,
    )
    activation_blocker = _activation_blocker(
        credentials_present=bool(configured_attempt.metadata.get("credentialsPresent")),
        provider_constructed=provider_constructed,
        provider_failure_reasons=provider_failure_reasons,
        fulfilled_windows=fulfilled_windows,
        missing_windows=missing_windows,
        request_window_results=request_window_results,
        short_intraday_window_plans=short_intraday_window_plans,
        yfinance_fallback_used=yfinance_fallback_used,
        static_basket_fallback_used=static_basket_fallback_used,
    )
    recommended_action = _recommended_action(
        credentials_present=bool(configured_attempt.metadata.get("credentialsPresent")),
        provider_constructed=provider_constructed,
        fulfilled_windows=fulfilled_windows,
        missing_windows=missing_windows,
        provider_failure_reasons=provider_failure_reasons,
        activation_blocker=activation_blocker,
    )
    activation_hint = _activation_hint(
        credentials_present=bool(configured_attempt.metadata.get("credentialsPresent")),
        provider_constructed=provider_constructed,
        fulfilled_windows=fulfilled_windows,
        missing_windows=missing_windows,
        provider_failure_reasons=provider_failure_reasons,
        activation_scope=activation_scope,
        minimum_activation_coverage_met=minimum_activation_coverage_met,
        provider_budget_exceeded=provider_budget_exceeded,
        timeout_symbol_count=timeout_symbol_count,
        skipped_due_to_budget_count=skipped_due_to_budget_count,
        probe_symbol_count=probe_symbol_count,
        full_universe_symbol_count=full_universe_symbol_count,
        activation_blocker=activation_blocker,
    )
    alpaca_activation_diagnostics = _alpaca_activation_diagnostics(
        configured_quotes=configured_attempt.quotes,
        probe_symbols=_bounded_unique_symbols(
            _as_string_sequence(configured_attempt.metadata.get("stableActivationProbeSymbols"))
        ),
        activation_window_results=activation_window_results,
        credentials_present=bool(configured_attempt.metadata.get("credentialsPresent")),
        provider_constructed=provider_constructed,
        provider_failure_reasons=provider_failure_reasons,
        activation_blocker=activation_blocker,
    )
    return {
        "configuredProviderAttempted": bool(configured_attempt.metadata.get("configuredProviderAttempted", True)),
        "providerAttempted": bool(configured_attempt.metadata.get("providerAttempted", True)),
        "configuredProviderName": str(
            configured_attempt.metadata.get("configuredProviderName")
            or configured_attempt.metadata.get("configuredProvider")
            or _CONFIGURED_PROVIDER_ID
        ),
        "credentialsPresent": bool(configured_attempt.metadata.get("credentialsPresent")),
        "credentialSource": _safe_credential_source(configured_attempt.metadata.get("credentialSource")),
        "credentialFieldsMissing": list(_as_string_sequence(
            configured_attempt.metadata.get(
                "credentialFieldsMissing",
                configured_attempt.metadata.get("missingCredentialFields"),
            )
        )),
        "providerConstructed": provider_constructed,
        "providerFailureReason": (
            str(configured_attempt.metadata.get("providerFailureReason"))
            if configured_attempt.metadata.get("providerFailureReason")
            else (provider_failure_reasons[0] if provider_failure_reasons else None)
        ),
        "configuredProviderFeed": configured_attempt.metadata.get("configuredProviderFeed"),
        "feed": str(
            configured_attempt.metadata.get("feed")
            or configured_attempt.metadata.get("configuredProviderFeed")
            or "iex"
        ),
        "proxyEnvironment": _safe_proxy_environment(configured_attempt.metadata.get("proxyEnvironment")),
        "feedEntitlementStatus": feed_entitlement_status,
        "requestedWindows": requested_windows,
        "fulfilledWindows": fulfilled_windows,
        "missingWindows": missing_windows,
        "configuredProviderFulfilledWindows": fulfilled_windows,
        "configuredProviderMissingWindows": missing_windows,
        "requestWindowResults": request_window_results,
        "activationWindowResults": activation_window_results,
        "diagnosticWindowResults": request_window_results,
        "shortIntradayWindowPlans": dict(short_intraday_window_plans),
        "diagnosticFulfilledWindows": diagnostic_fulfilled_windows,
        "diagnosticMissingWindows": diagnostic_missing_windows,
        "successSymbolsByWindow": _symbols_by_window_from_request_results(
            request_window_results,
            "successSymbols",
        ),
        "failedSymbolsByWindow": _symbols_by_window_from_request_results(
            request_window_results,
            "failedSymbols",
        ),
        "timedOutSymbolsByWindow": _symbols_by_window_from_request_results(
            request_window_results,
            "timedOutSymbols",
        ),
        "emptyResponseSymbolsByWindow": _symbols_by_window_from_request_results(
            request_window_results,
            "emptyResponseSymbols",
        ),
        "maxSymbolsPerWindow": _non_negative_int(
            configured_attempt.metadata.get("maxSymbolsPerWindow"),
            int(_ALPACA_MAX_SYMBOLS_PER_WINDOW),
        ),
        "maxProbeSymbols": _non_negative_int(
            configured_attempt.metadata.get("maxProbeSymbols"),
            int(_ALPACA_MAX_PROBE_SYMBOLS),
        ),
        "perWindowTimeout": _non_negative_float(
            configured_attempt.metadata.get("perWindowTimeout"),
            float(_ALPACA_PER_WINDOW_TIMEOUT_SECONDS),
        ),
        "totalProviderBudget": _non_negative_float(
            configured_attempt.metadata.get("totalProviderBudget"),
            float(_ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS),
        ),
        "providerDeadlineSeconds": _non_negative_float(
            configured_attempt.metadata.get("providerDeadlineSeconds"),
            float(_ALPACA_PROVIDER_DEADLINE_SECONDS),
        ),
        "probeSymbolCount": probe_symbol_count,
        "activationProbeSymbolCount": activation_probe_symbol_count,
        "diagnosticProbeSymbolCount": diagnostic_probe_symbol_count,
        "stableActivationProbeSymbols": _bounded_unique_symbols(
            _as_string_sequence(configured_attempt.metadata.get("stableActivationProbeSymbols"))
        ),
        "longTailProbeSymbols": _bounded_unique_symbols(
            _as_string_sequence(configured_attempt.metadata.get("longTailProbeSymbols"))
        ),
        "fullUniverseSymbolCount": full_universe_symbol_count,
        "providerBudgetExceeded": provider_budget_exceeded,
        "timeoutSymbolCount": timeout_symbol_count,
        "skippedDueToBudgetCount": skipped_due_to_budget_count,
        "activationScope": activation_scope,
        "anyConfiguredProviderDataAvailable": any_configured_provider_data_available,
        "configuredProviderWindowCoverageMet": configured_provider_window_coverage_met,
        "partialActivationEligible": partial_activation_eligible,
        "dominantProviderBlocker": dominant_provider_blocker or None,
        "minimumActivationCoverageMet": minimum_activation_coverage_met,
        "minimumActivationSuccessRatio": minimum_activation_success_ratio,
        "minimumActivationSuccessCount": minimum_activation_success_count,
        "symbolSuccessCount": len(quotes),
        "symbolFailureCount": len(failed_symbol_reasons),
        "symbolFailureSamples": _sanitize_symbol_failure_samples(
            configured_attempt.metadata.get("symbolFailureSamples")
        ),
        "providerFailureReasons": provider_failure_reasons,
        "recommendedAction": recommended_action,
        "activationHint": activation_hint,
        "alpacaActivationDiagnostics": alpaca_activation_diagnostics,
        "liveActivationStatus": _live_activation_status(
            credentials_present=bool(configured_attempt.metadata.get("credentialsPresent")),
            provider_constructed=provider_constructed,
            fulfilled_windows=fulfilled_windows,
            missing_windows=missing_windows,
            provider_failure_reasons=provider_failure_reasons,
            yfinance_fallback_used=yfinance_fallback_used,
            static_basket_fallback_used=static_basket_fallback_used,
            activation_blocker=activation_blocker,
            activation_scope=activation_scope,
            minimum_activation_coverage_met=minimum_activation_coverage_met,
        ),
        "activationBlocker": activation_blocker,
        "fallbackProviderUsed": fallback_provider_used,
        "yfinanceFallbackUsed": yfinance_fallback_used,
        "fallbackYfinanceUsed": yfinance_fallback_used,
        "staticBasketFallbackUsed": static_basket_fallback_used,
        "finalSourceTier": final_source_tier,
        "trustLevel": _provider_trust_level(
            final_source_tier=final_source_tier,
            provider_constructed=provider_constructed,
            fulfilled_windows=fulfilled_windows,
            missing_windows=missing_windows,
            symbol_failure_count=len(failed_symbol_reasons),
            yfinance_fallback_used=yfinance_fallback_used,
            static_basket_fallback_used=static_basket_fallback_used,
        ),
    }


def _alpaca_activation_diagnostics(
    *,
    configured_quotes: Mapping[str, Dict[str, Any]],
    probe_symbols: Sequence[str],
    activation_window_results: Mapping[str, Mapping[str, Any]],
    credentials_present: bool,
    provider_constructed: bool,
    provider_failure_reasons: Sequence[str],
    activation_blocker: Optional[str],
) -> Dict[str, Any]:
    stale_windows: list[str] = []
    source_metadata_invalid_windows: list[str] = []
    for symbol in probe_symbols:
        quote = configured_quotes.get(symbol)
        if not isinstance(quote, Mapping):
            continue
        time_windows = quote.get("timeWindows")
        if not isinstance(time_windows, Mapping):
            continue
        for window in _ALPACA_TIMEFRAMES:
            slot = time_windows.get(window)
            if not isinstance(slot, Mapping) or not slot.get("available", True):
                continue
            if str(slot.get("freshness") or "").strip().lower() == "stale" and window not in stale_windows:
                stale_windows.append(window)
            if not _alpaca_activation_slot_source_valid(slot) and window not in source_metadata_invalid_windows:
                source_metadata_invalid_windows.append(window)
    fulfilled_windows = _fulfilled_windows_from_request_results(activation_window_results)
    missing_windows = _missing_windows_from_request_results(activation_window_results)
    probe_passed = bool(probe_symbols) and not missing_windows
    freshness_valid = not stale_windows
    source_metadata_valid = not source_metadata_invalid_windows
    source_authority_allowed = bool(
        credentials_present
        and provider_constructed
        and probe_passed
        and freshness_valid
        and source_metadata_valid
    )
    reason = None
    if not credentials_present:
        reason = "credentials"
    elif not provider_constructed:
        reason = _primary_failure_class(provider_failure_reasons) or "provider_error"
    elif not probe_passed:
        reason = str(activation_blocker or "window_coverage").strip() or "window_coverage"
    elif not freshness_valid:
        reason = "stale_window"
    elif not source_metadata_valid:
        reason = "source_metadata_invalid"
    return {
        "credentialsPresent": bool(credentials_present),
        "providerConstructed": bool(provider_constructed),
        "probeSymbols": list(probe_symbols),
        "probePassed": bool(probe_passed),
        "fulfilledWindows": fulfilled_windows,
        "missingWindows": missing_windows,
        "freshnessValid": bool(freshness_valid),
        "staleWindows": stale_windows,
        "sourceMetadataValid": bool(source_metadata_valid),
        "sourceMetadataInvalidWindows": source_metadata_invalid_windows,
        "sourceAuthorityAllowed": bool(source_authority_allowed),
        "scoreContributionAllowed": bool(source_authority_allowed),
        "reason": reason,
    }


def _etf_authority_spine_diagnostics(
    *,
    requested_symbols: Sequence[str],
    quotes: Mapping[str, Dict[str, Any]],
    configured_attempt: _ProviderAttempt,
    provider_diagnostics: Mapping[str, Any],
) -> Dict[str, Any]:
    requested = {str(symbol).strip().upper() for symbol in requested_symbols if str(symbol).strip()}
    universe = [
        symbol
        for symbol in _ROTATION_RADAR_AUTHORITY_ETF_UNIVERSE
        if symbol in requested or symbol in quotes or symbol in configured_attempt.quotes
    ]
    activation = provider_diagnostics.get("alpacaActivationDiagnostics")
    activation = dict(activation) if isinstance(activation, Mapping) else {}
    fulfilled_windows = _as_string_sequence(activation.get("fulfilledWindows"))
    missing_windows = _as_string_sequence(activation.get("missingWindows"))
    stale_windows = _as_string_sequence(activation.get("staleWindows"))
    activation_reason = str(activation.get("reason") or "").strip() or None
    activation_allowed = bool(activation.get("sourceAuthorityAllowed"))

    rows: list[Dict[str, Any]] = []
    as_of_candidates: list[str] = []
    freshness_values: list[str] = []
    source_labels: list[str] = []
    source_tiers: list[str] = []
    any_partial = False

    for symbol in universe:
        quote = quotes.get(symbol)
        row = _etf_authority_spine_row(
            symbol=symbol,
            quote=quote if isinstance(quote, Mapping) else None,
            activation_allowed=activation_allowed,
            activation_reason=activation_reason,
            fulfilled_windows=fulfilled_windows,
            missing_windows=missing_windows,
            stale_windows=stale_windows,
        )
        rows.append(row)
        if row["asOf"]:
            as_of_candidates.append(str(row["asOf"]))
        if row["freshness"]:
            freshness_values.append(str(row["freshness"]))
        if row["sourceLabel"]:
            source_labels.append(str(row["sourceLabel"]))
        if row["sourceTier"]:
            source_tiers.append(str(row["sourceTier"]))
        if row["trustLevel"] == "partial":
            any_partial = True

    reason_codes = _etf_authority_reason_codes(
        activation_reason=activation_reason,
        missing_windows=missing_windows,
        stale_windows=stale_windows,
    )
    if activation_allowed and rows:
        trust_level = "active"
    elif activation_reason in {"credentials", "missing_credentials", "auth_failed", "provider_error"}:
        trust_level = "unavailable"
    elif rows and (any_partial or any(row.get("sourceLabel") for row in rows)):
        trust_level = "partial"
    else:
        trust_level = "unavailable"

    return {
        "universe": universe,
        "requiredWindows": list(_ALPACA_TIMEFRAMES),
        "fulfilledWindows": fulfilled_windows,
        "missingWindows": missing_windows,
        "staleWindows": stale_windows,
        "freshness": _etf_authority_freshness(freshness_values),
        "asOf": max(as_of_candidates) if as_of_candidates else None,
        "sourceLabel": _dominant_label(_count_values(source_labels), default=None) if source_labels else None,
        "sourceTier": _dominant_label(_count_values(source_tiers), default=None) if source_tiers else None,
        "trustLevel": trust_level,
        "sourceAuthorityAllowed": bool(activation_allowed and rows),
        "scoreContributionAllowed": bool(activation_allowed and rows),
        "reasonCodes": reason_codes,
        "quotes": rows,
    }


def _etf_authority_spine_row(
    *,
    symbol: str,
    quote: Optional[Mapping[str, Any]],
    activation_allowed: bool,
    activation_reason: Optional[str],
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
    stale_windows: Sequence[str],
) -> Dict[str, Any]:
    time_windows = quote.get("timeWindows") if isinstance(quote, Mapping) else {}
    time_windows = time_windows if isinstance(time_windows, Mapping) else {}
    row_fulfilled_windows = [
        window
        for window in _ALPACA_TIMEFRAMES
        if _etf_authority_window_slot_valid(time_windows.get(window))
    ]
    row_missing_windows = [window for window in _ALPACA_TIMEFRAMES if window not in row_fulfilled_windows]
    row_stale_windows = [
        window
        for window in row_fulfilled_windows
        if str((time_windows.get(window) or {}).get("freshness") or "").strip().lower() == "stale"
    ]
    quote_is_configured = bool(
        isinstance(quote, Mapping)
        and str(quote.get("source") or "").strip().lower() == _CONFIGURED_SOURCE
        and str(quote.get("sourceTier") or "").strip().lower() == _CONFIGURED_SOURCE_TIER
    )
    row_allowed = bool(
        activation_allowed
        and quote_is_configured
        and row_fulfilled_windows == list(_ALPACA_TIMEFRAMES)
        and not row_stale_windows
    )
    reason_codes = _etf_authority_reason_codes(
        activation_reason=activation_reason,
        missing_windows=row_missing_windows or missing_windows,
        stale_windows=row_stale_windows or stale_windows,
        quote_missing=not isinstance(quote, Mapping),
    )
    if row_allowed:
        trust_level = "active"
    elif isinstance(quote, Mapping):
        trust_level = "partial"
    else:
        trust_level = "unavailable"
    return {
        "symbol": symbol,
        "windowsFulfilled": row_fulfilled_windows,
        "freshness": quote.get("freshness") if isinstance(quote, Mapping) else None,
        "asOf": quote.get("asOf") if isinstance(quote, Mapping) else None,
        "sourceLabel": quote.get("sourceLabel") if isinstance(quote, Mapping) else None,
        "sourceTier": quote.get("sourceTier") if isinstance(quote, Mapping) else None,
        "trustLevel": trust_level,
        "sourceAuthorityAllowed": row_allowed,
        "scoreContributionAllowed": row_allowed,
        "reasonCodes": reason_codes,
    }


def _etf_authority_window_slot_valid(slot: Any) -> bool:
    return bool(
        isinstance(slot, Mapping)
        and slot.get("available")
        and _alpaca_activation_slot_source_valid(slot)
    )


def _etf_authority_reason_codes(
    *,
    activation_reason: Optional[str],
    missing_windows: Sequence[str],
    stale_windows: Sequence[str],
    quote_missing: bool = False,
) -> list[str]:
    reason_codes: list[str] = []
    if activation_reason:
        reason_codes.append(str(activation_reason))
    if quote_missing:
        reason_codes.append("quote_missing")
    if missing_windows:
        reason_codes.extend(f"missing_window:{window}" for window in missing_windows)
    if stale_windows:
        reason_codes.extend(f"stale_window:{window}" for window in stale_windows)
    return list(dict.fromkeys(reason_codes))


def _etf_authority_freshness(values: Sequence[str]) -> Optional[str]:
    normalized = [str(value or "").strip().lower() for value in values if str(value or "").strip()]
    if not normalized:
        return None
    for candidate in ("live", "delayed", "cached", "stale", "fallback"):
        if candidate in normalized:
            return candidate
    return normalized[0]


def _alpaca_activation_slot_source_valid(slot: Mapping[str, Any]) -> bool:
    return (
        str(slot.get("source") or "").strip().lower() == _CONFIGURED_SOURCE
        and str(slot.get("sourceType") or "").strip().lower() == _CONFIGURED_SOURCE_TYPE
        and str(slot.get("sourceTier") or "").strip().lower() == _CONFIGURED_SOURCE_TIER
        and str(slot.get("providerTier") or "").strip().lower() == _CONFIGURED_PROVIDER_TIER
    )


def _safe_credential_source(value: Any) -> str:
    source = str(value or "").strip()
    return source if source in _CREDENTIAL_SOURCE_VALUES else "unknown"


def _safe_proxy_environment(value: Any) -> Dict[str, bool]:
    if not isinstance(value, Mapping):
        return {}
    keys = (
        "sessionTrustEnv",
        "httpProxyConfigured",
        "httpsProxyConfigured",
        "allProxyConfigured",
        "proxyEnvConfigured",
        "alpacaHttpsProxyEligible",
    )
    return {key: bool(value.get(key, False)) for key in keys if key in value}


def _endpoint_reachability_not_checked() -> Dict[str, Any]:
    return {
        "attempted": False,
        "status": "not_checked",
        "failureClass": None,
        "httpStatusClass": None,
    }


def _run_endpoint_reachability_check(fetcher: AlpacaFetcher, *, timeout: float) -> Dict[str, Any]:
    reachability = getattr(fetcher, "endpoint_reachability", None)
    if not callable(reachability):
        return _endpoint_reachability_not_checked()
    try:
        return _safe_endpoint_reachability(reachability(timeout=timeout))
    except Exception as exc:
        failure_class = _classify_configured_failure(exc)
        status = "timeout" if _is_timeout_failure_class(failure_class) else "unreachable"
        if failure_class not in _TIMEOUT_FAILURE_CLASSES and failure_class not in _NETWORK_FAILURE_CLASSES:
            status = "provider_error"
        return {
            "attempted": True,
            "status": status,
            "failureClass": failure_class,
            "httpStatusClass": None,
        }


def _safe_endpoint_reachability(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return _endpoint_reachability_not_checked()
    status = str(value.get("status") or "").strip()
    if status not in {"not_checked", "reachable", "unreachable", "timeout", "provider_error", "unknown"}:
        status = "unknown"
    failure_class = value.get("failureClass")
    if failure_class is not None:
        failure_class = _normalize_configured_failure_class(failure_class)
    http_status_class = value.get("httpStatusClass")
    http_status_class = str(http_status_class).strip() if http_status_class is not None else None
    if http_status_class not in {None, "1xx", "2xx", "3xx", "4xx", "5xx"}:
        http_status_class = None
    return {
        "attempted": bool(value.get("attempted", False)),
        "status": status,
        "failureClass": failure_class,
        "httpStatusClass": http_status_class,
    }


def _smoke_timeout_diagnosis(
    *,
    provider_diagnostics: Mapping[str, Any],
    endpoint_reachability: Mapping[str, Any],
) -> Dict[str, Any]:
    request_window_results = _diagnostic_request_window_results(
        provider_diagnostics.get("requestWindowResults"),
        requested_symbol_count=_non_negative_int(provider_diagnostics.get("activationProbeSymbolCount"), 0),
    )
    window_failure_classes = _count_window_failure_classes(request_window_results)
    dominant_window_failure = _dominant_failure_class(window_failure_classes)
    activation_blocker = str(provider_diagnostics.get("activationBlocker") or "").strip()
    provider_failure_reasons = _as_string_sequence(provider_diagnostics.get("providerFailureReasons"))
    timeout_reasons = [
        reason
        for reason in [activation_blocker, dominant_window_failure, *provider_failure_reasons]
        if _is_timeout_failure_class(reason)
    ]
    timeout_observed = bool(timeout_reasons)
    skipped_due_to_budget_count = _non_negative_int(provider_diagnostics.get("skippedDueToBudgetCount"), 0)
    timeout_symbol_count = _non_negative_int(provider_diagnostics.get("timeoutSymbolCount"), 0)
    probe_budget_exhausted = bool(skipped_due_to_budget_count > 0)
    per_window_bar_fetch_timed_out = bool(
        timeout_symbol_count > 0
        or any(_is_timeout_failure_class(reason) for reason in window_failure_classes)
    )
    endpoint_status = str(endpoint_reachability.get("status") or "not_checked")
    empty_response_observed = bool(
        window_failure_classes.get("empty_response")
        or activation_blocker in {"empty_response", "feed_intraday_empty", "market_closed_window_empty"}
    )
    feed_window_choice = _smoke_feed_window_choice(
        provider_diagnostics.get("shortIntradayWindowPlans"),
        activation_blocker=activation_blocker,
    )

    if not timeout_observed and not empty_response_observed:
        category = "not_timeout"
    elif endpoint_status in {"unreachable", "timeout"} or _is_network_failure_class(activation_blocker):
        category = "endpoint_reachability"
    elif probe_budget_exhausted:
        category = "probe_budget_exhausted"
    elif per_window_bar_fetch_timed_out:
        category = "per_window_bar_fetch_timeout"
    elif activation_blocker in {"feed_intraday_empty", "market_closed_window_empty"}:
        category = "feed_window_choice"
    elif empty_response_observed:
        category = "no_recent_bars"
    else:
        category = "unknown"

    return {
        "category": category,
        "timeoutObserved": timeout_observed,
        "probeBudgetExhausted": probe_budget_exhausted,
        "perWindowBarFetchTimedOut": per_window_bar_fetch_timed_out,
        "endpointReachabilityStatus": endpoint_status,
        "feedWindowChoice": feed_window_choice,
        "noRecentBarsObserved": empty_response_observed,
        "dominantWindowFailureClass": dominant_window_failure,
    }


def _count_window_failure_classes(
    request_window_results: Mapping[str, Mapping[str, Any]]
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for result in request_window_results.values():
        failure_classes = result.get("failureClasses") if isinstance(result, Mapping) else {}
        if not isinstance(failure_classes, Mapping):
            continue
        for failure_class, count in failure_classes.items():
            normalized = _normalize_configured_failure_class(failure_class)
            counts[normalized] = counts.get(normalized, 0) + max(0, int(count or 0))
    return counts


def _smoke_feed_window_choice(raw_plans: Any, *, activation_blocker: str) -> str:
    if activation_blocker not in {
        "feed_intraday_empty",
        "market_closed_window_empty",
        "intraday_short_window_empty",
        "short_window_coverage",
    }:
        return "not_evaluated"
    if not isinstance(raw_plans, Mapping):
        return "unknown"
    modes = {
        str(plan.get("selectionMode") or "").strip()
        for window, plan in raw_plans.items()
        if window in _SHORT_INTRADAY_WINDOWS and isinstance(plan, Mapping)
    }
    modes.discard("")
    if not modes:
        return "unknown"
    if len(modes) == 1:
        return next(iter(modes))
    return "mixed"


def _activation_scope(value: Any) -> str:
    scope = str(value or "").strip()
    return scope if scope in {"probe_only", "partial_universe", "full_universe"} else "probe_only"


def _non_negative_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return max(0, int(default or 0))


def _non_negative_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, float(value))
    except Exception:
        return max(0.0, float(default or 0.0))


def _provider_trust_level(
    *,
    final_source_tier: str,
    provider_constructed: bool,
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
    symbol_failure_count: int,
    yfinance_fallback_used: bool,
    static_basket_fallback_used: bool,
) -> str:
    if static_basket_fallback_used or final_source_tier == "static_fallback":
        return "unavailable"
    if final_source_tier == _CONFIGURED_SOURCE_TIER and provider_constructed:
        if not missing_windows and symbol_failure_count == 0 and not yfinance_fallback_used:
            return "active"
        return "partial"
    if final_source_tier == "mixed":
        return "partial"
    if yfinance_fallback_used or final_source_tier == _QUOTE_SOURCE_TIER:
        return "degraded"
    if fulfilled_windows and not missing_windows and symbol_failure_count == 0:
        return "active"
    return "partial" if fulfilled_windows else "degraded"


def _live_activation_status(
    *,
    credentials_present: bool,
    provider_constructed: bool,
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
    provider_failure_reasons: Sequence[str],
    yfinance_fallback_used: bool,
    static_basket_fallback_used: bool,
    activation_blocker: Optional[str],
    activation_scope: str,
    minimum_activation_coverage_met: bool,
) -> str:
    if static_basket_fallback_used:
        return "unavailable"
    if _is_network_failure_class(activation_blocker):
        return "unavailable"
    if _is_timeout_failure_class(activation_blocker):
        if minimum_activation_coverage_met and fulfilled_windows:
            return "partial"
        return "unavailable"
    if not credentials_present:
        return "unavailable"
    if not provider_constructed:
        return "unavailable"
    if fulfilled_windows and not missing_windows and not yfinance_fallback_used and activation_scope == "full_universe":
        return "active"
    if fulfilled_windows:
        return "partial"
    return "unavailable"


def _activation_blocker(
    *,
    credentials_present: bool,
    provider_constructed: bool,
    provider_failure_reasons: Sequence[str],
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
    request_window_results: Mapping[str, Mapping[str, Any]],
    short_intraday_window_plans: Mapping[str, Any],
    yfinance_fallback_used: bool,
    static_basket_fallback_used: bool,
) -> Optional[str]:
    if fulfilled_windows and not missing_windows and not yfinance_fallback_used and not static_basket_fallback_used:
        return None
    if not credentials_present:
        return "credentials"
    raw_reasons = {
        str(reason or "").strip().lower()
        for reason in provider_failure_reasons
        if str(reason or "").strip()
    }
    normalized_reasons = {
        _normalize_configured_failure_class(reason)
        for reason in raw_reasons
        if str(reason or "").strip()
    }
    short_window_blocker = _short_window_activation_blocker(
        fulfilled_windows=fulfilled_windows,
        missing_windows=missing_windows,
        request_window_results=request_window_results,
        short_intraday_window_plans=short_intraday_window_plans,
    )
    if short_window_blocker:
        return short_window_blocker
    if "auth_failed" in normalized_reasons:
        return "auth"
    if "entitlement_denied" in normalized_reasons:
        return "entitlement"
    if "interval_mapping" in normalized_reasons:
        return "interval_mapping"
    if "market_session" in normalized_reasons:
        return "market_session"
    if "calendar" in normalized_reasons:
        return "calendar"
    for failure_class in (
        "proxy_unreachable",
        "connect_timeout",
        "read_timeout",
        "provider_timeout",
        "network_unreachable",
    ):
        if failure_class in normalized_reasons:
            return failure_class
    if "timeout" in normalized_reasons or "quote_fetch_failed" in raw_reasons:
        return "timeout"
    if "empty_response" in normalized_reasons:
        return "empty_response"
    if "symbol_not_found" in normalized_reasons:
        return "symbol_coverage"
    if (
        "provider_error" in normalized_reasons
        or "provider_unavailable" in raw_reasons
        or "rate_limited" in normalized_reasons
    ):
        return "provider_error"
    if not provider_constructed:
        return "provider_error"
    if missing_windows:
        return "unknown"
    return None


def _short_window_activation_blocker(
    *,
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
    request_window_results: Mapping[str, Mapping[str, Any]],
    short_intraday_window_plans: Mapping[str, Any],
) -> Optional[str]:
    fulfilled = {str(window) for window in fulfilled_windows}
    missing = {str(window) for window in missing_windows}
    if not set(_OBSERVATION_GRADE_WINDOWS).issubset(fulfilled):
        return None
    if not missing.intersection(_SHORT_INTRADAY_WINDOWS):
        return None
    short_failure_counts: Dict[str, int] = {}
    for window in _SHORT_INTRADAY_WINDOWS:
        result = request_window_results.get(window, {})
        failure_classes = result.get("failureClasses") if isinstance(result, Mapping) else {}
        if isinstance(failure_classes, Mapping):
            for failure_class, count in failure_classes.items():
                normalized = _normalize_configured_failure_class(failure_class)
                short_failure_counts[normalized] = short_failure_counts.get(normalized, 0) + max(0, int(count or 0))
    dominant_short_failure = _dominant_failure_class(short_failure_counts)
    if dominant_short_failure == "auth_failed":
        return "auth"
    if dominant_short_failure == "entitlement_denied":
        return "entitlement"
    if dominant_short_failure == "interval_mapping":
        return "interval_mapping"
    if dominant_short_failure == "calendar":
        return "calendar"
    if dominant_short_failure == "market_session":
        return "market_closed_window_empty"
    if (
        dominant_short_failure in _NETWORK_FAILURE_CLASSES
        or dominant_short_failure in {"connect_timeout", "read_timeout", "provider_timeout"}
    ):
        return dominant_short_failure
    if dominant_short_failure in {"rate_limited", "timeout"}:
        return "timeout"
    if dominant_short_failure == "symbol_not_found":
        return "symbol_coverage"
    if dominant_short_failure == "provider_error":
        return "provider_error"
    if dominant_short_failure == "empty_response":
        if _short_intraday_windows_selected_outside_regular_session(short_intraday_window_plans):
            return "market_closed_window_empty"
        return "feed_intraday_empty"
    return "short_window_coverage"


def _short_intraday_windows_selected_outside_regular_session(
    short_intraday_window_plans: Mapping[str, Any],
) -> bool:
    for window in _SHORT_INTRADAY_WINDOWS:
        plan = short_intraday_window_plans.get(window)
        if not isinstance(plan, Mapping):
            continue
        if str(plan.get("selectionMode") or "").strip() == "recent_completed_regular_session":
            return True
    return False


def _diagnostic_request_window_results(
    raw_results: Any,
    *,
    requested_symbol_count: int,
) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw_results, Mapping):
        return {}
    finalized: Dict[str, Dict[str, Any]] = {}
    for window in _ALPACA_TIMEFRAMES:
        raw = raw_results.get(window, {})
        if not isinstance(raw, Mapping):
            continue
        failure_classes = {
            _normalize_configured_failure_class(failure_class): max(0, int(count or 0))
            for failure_class, count in dict(raw.get("failureClasses") or {}).items()
            if max(0, int(count or 0)) > 0
        }
        failure_symbols_by_class = _failure_symbols_by_class(raw.get("failureSymbolsByClass"))
        success_count = max(0, int(raw.get("successCount") or 0))
        failure_count = max(0, int(raw.get("failureCount") or 0))
        requested_count = max(0, int(raw.get("requestedSymbolCount") or requested_symbol_count))
        required_success_count = min(
            requested_count,
            _non_negative_int(
                raw.get("minimumRequiredSuccessCount"),
                _minimum_required_success_count(requested_count),
            ),
        )
        finalized[window] = {
            "requestedSymbolCount": requested_count,
            "successCount": success_count,
            "failureCount": failure_count,
            "failureClasses": failure_classes,
            "dominantFailureClass": _dominant_failure_class(failure_classes),
            "failureSymbolsByClass": failure_symbols_by_class,
            "timedOutSymbols": _bounded_unique_symbols(
                _as_string_sequence(raw.get("timedOutSymbols"))
                or failure_symbols_by_class.get("timeout", [])
            ),
            "emptyResponseSymbols": _bounded_unique_symbols(
                _as_string_sequence(raw.get("emptyResponseSymbols"))
                or failure_symbols_by_class.get("empty_response", [])
            ),
            "successSymbols": _bounded_unique_symbols(_as_string_sequence(raw.get("successSymbols"))),
            "failedSymbols": _bounded_unique_symbols(_as_string_sequence(raw.get("failedSymbols"))),
            "successRatio": _non_negative_float(
                raw.get("successRatio"),
                _success_ratio(success_count, requested_count),
            ),
            "minimumRequiredSuccessRatio": _non_negative_float(
                raw.get("minimumRequiredSuccessRatio"),
                _activation_success_ratio(),
            ),
            "minimumRequiredSuccessCount": required_success_count,
            "fulfilled": bool(raw.get("fulfilled")) if "fulfilled" in raw else bool(
                requested_count > 0 and success_count >= required_success_count
            ),
        }
    return finalized


def _feed_entitlement_status(
    metadata: Mapping[str, Any],
    *,
    provider_failure_reasons: Sequence[str],
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
) -> str:
    explicit = str(metadata.get("feedEntitlementStatus") or "").strip()
    if explicit and explicit not in {"unknown", "not_checked"}:
        return explicit
    reason_set = {str(reason or "").strip() for reason in provider_failure_reasons if str(reason or "").strip()}
    if "auth_failed" in reason_set:
        return "auth_failed"
    if "entitlement_denied" in reason_set:
        return "entitlement_denied"
    if "rate_limited" in reason_set:
        return "rate_limited"
    if reason_set.intersection(_NETWORK_FAILURE_CLASSES):
        return "not_inferable"
    if any(_is_timeout_failure_class(reason) for reason in reason_set):
        return "timeout"
    if reason_set.intersection({"interval_mapping", "market_session", "calendar"}):
        return "not_inferable"
    if "empty_response" in reason_set or "symbol_not_found" in reason_set:
        return "not_inferable" if not fulfilled_windows else "partial"
    if "missing_credentials" in reason_set:
        return "not_checked"
    if fulfilled_windows and missing_windows:
        return "not_inferable"
    return explicit or "unknown"


def _recommended_action(
    *,
    credentials_present: bool,
    provider_constructed: bool,
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
    provider_failure_reasons: Sequence[str],
    activation_blocker: Optional[str],
) -> str:
    primary = _primary_failure_class(provider_failure_reasons)
    if not credentials_present:
        return "configure_alpaca_credentials"
    if not provider_constructed:
        return "check_alpaca_provider_configuration"
    if activation_blocker == "market_closed_window_empty":
        return "retry_during_regular_market_session"
    if activation_blocker == "feed_intraday_empty":
        return "verify_intraday_feed_or_recent_session_window"
    if activation_blocker == "proxy_unreachable":
        return "verify_proxy_configuration"
    if activation_blocker in {"connect_timeout", "network_unreachable"}:
        return "verify_alpaca_endpoint_reachability"
    if activation_blocker in {"read_timeout", "provider_timeout"}:
        return "retry_or_increase_alpaca_timeout"
    if primary == "auth_failed":
        return "verify_alpaca_credentials"
    if primary == "entitlement_denied":
        return "enable_feed_entitlement_or_switch_feed"
    if primary == "interval_mapping":
        return "verify_alpaca_interval_mapping"
    if primary == "market_session":
        return "retry_when_market_session_is_open"
    if primary == "calendar":
        return "check_market_calendar"
    if primary == "rate_limited":
        return "retry_after_rate_limit"
    if primary == "timeout":
        return "retry_or_reduce_symbol_batch"
    if primary in {"empty_response", "symbol_not_found"}:
        return "verify_symbol_coverage"
    if primary == "provider_error":
        return "check_alpaca_provider_status"
    if missing_windows:
        return "review_missing_windows"
    if fulfilled_windows:
        return "none"
    return "check_alpaca_provider_status"


def _activation_hint(
    *,
    credentials_present: bool,
    provider_constructed: bool,
    fulfilled_windows: Sequence[str],
    missing_windows: Sequence[str],
    provider_failure_reasons: Sequence[str],
    activation_scope: str,
    minimum_activation_coverage_met: bool,
    provider_budget_exceeded: bool,
    timeout_symbol_count: int,
    skipped_due_to_budget_count: int,
    probe_symbol_count: int,
    full_universe_symbol_count: int,
    activation_blocker: Optional[str],
) -> str:
    primary = _primary_failure_class(provider_failure_reasons) or "unknown"
    if not credentials_present:
        return "Configure Alpaca credentials before Alpaca windows can activate."
    if not provider_constructed:
        return f"Alpaca credentials are present, but the provider could not be constructed: {primary}."
    if activation_blocker == "proxy_unreachable":
        return (
            "Alpaca credentials are present and the provider was constructed, "
            "but the configured proxy could not reach the Alpaca endpoint."
        )
    if activation_blocker in {"connect_timeout", "network_unreachable"}:
        return (
            "Alpaca credentials are present and the provider was constructed, "
            "but the Alpaca endpoint or network path was unreachable."
        )
    if activation_blocker in {"read_timeout", "provider_timeout"}:
        return (
            "Alpaca credentials are present and the provider was constructed, "
            f"but the provider did not return within the configured timeout: {primary}."
        )
    if activation_blocker in {"intraday_short_window_empty", "short_window_coverage"}:
        return (
            "Alpaca long-window coverage is available, but 5m/15m activation is blocked. "
            "Check IEX feed short-interval bars, symbol support, market session timing, "
            "or try reducing the symbol universe."
        )
    if activation_blocker == "market_closed_window_empty":
        return (
            "Alpaca long-window coverage is available, but 5m/15m probes were anchored to the most recent "
            "completed regular US session outside market hours and still returned empty bars."
        )
    if activation_blocker == "feed_intraday_empty":
        return (
            "Alpaca long-window coverage is available, but 5m/15m probes from a completed regular-session "
            "window still returned empty bars."
        )
    if not fulfilled_windows and missing_windows:
        return (
            "Alpaca credentials are present and the provider was constructed, "
            f"but no configured windows were fulfilled: {primary}."
        )
    if fulfilled_windows and missing_windows:
        if minimum_activation_coverage_met and (
            provider_budget_exceeded
            or timeout_symbol_count
            or skipped_due_to_budget_count
        ):
            remaining = max(full_universe_symbol_count - probe_symbol_count, 0)
            if remaining > 0:
                return (
                    f"Alpaca probe succeeded for {probe_symbol_count} symbols; "
                    f"remaining {remaining} symbols were limited by budget or timeout, "
                    f"so activation is partial and missing {'/'.join(missing_windows)} windows: {primary}."
                )
            return (
                f"Alpaca probe succeeded for {probe_symbol_count} symbols; "
                f"activation is partial and missing {'/'.join(missing_windows)} windows: {primary}."
            )
        return (
            "Alpaca provider is active but missing "
            f"{'/'.join(missing_windows)} windows: {primary}."
        )
    if fulfilled_windows:
        if activation_scope == "full_universe" and not provider_budget_exceeded and not timeout_symbol_count and not skipped_due_to_budget_count:
            return "Alpaca feed active for requested 5m/15m/60m/1d windows."
        if minimum_activation_coverage_met:
            remaining = max(full_universe_symbol_count - probe_symbol_count, 0)
            if remaining > 0 and (provider_budget_exceeded or timeout_symbol_count or skipped_due_to_budget_count):
                return (
                    f"Alpaca probe succeeded for {probe_symbol_count} symbols; "
                    f"remaining {remaining} symbols were limited by budget or timeout, so activation is partial."
                )
            return (
                f"Alpaca probe succeeded for {probe_symbol_count} symbols; "
                "activation remains partial until the full universe is covered."
            )
        return "Alpaca feed active for requested 5m/15m/60m/1d windows."
    return f"Alpaca provider did not report window coverage: {primary}."


def _primary_failure_class(provider_failure_reasons: Sequence[str]) -> Optional[str]:
    normalized = [
        _normalize_configured_failure_class(reason)
        for reason in provider_failure_reasons
        if str(reason or "").strip()
    ]
    sorted_reasons = _sort_failure_classes(normalized)
    return sorted_reasons[0] if sorted_reasons else None


def _sanitize_symbol_failure_samples(raw_samples: Any) -> list[Dict[str, str]]:
    if not isinstance(raw_samples, Sequence) or isinstance(raw_samples, (str, bytes)):
        return []
    samples: list[Dict[str, str]] = []
    for raw_sample in raw_samples:
        if not isinstance(raw_sample, Mapping):
            continue
        symbol = _sanitize_symbol(raw_sample.get("symbol"))
        window = str(raw_sample.get("window") or "").strip()
        failure_class = _normalize_configured_failure_class(raw_sample.get("failureClass"))
        if not symbol or window not in _ALPACA_TIMEFRAMES:
            continue
        samples.append({
            "symbol": symbol,
            "window": window,
            "failureClass": failure_class,
        })
        if len(samples) >= _FAILED_SYMBOL_LIST_LIMIT:
            break
    return samples


def _as_string_sequence(value: Any) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _bounded_unique_reasons(reasons: Iterable[Any]) -> list[str]:
    bounded: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        normalized = str(reason or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        bounded.append(normalized)
        if len(bounded) >= _PROVIDER_DIAGNOSTIC_REASON_LIMIT:
            break
    return bounded


def _first_failure_reason(reasons: Iterable[Any]) -> Optional[str]:
    for reason in reasons:
        normalized = str(reason or "").strip()
        if normalized:
            return normalized
    return None


def _quote_window_failure_reasons(quotes: Mapping[str, Dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for quote in quotes.values():
        raw_reasons = quote.get("windowFailureReasons")
        if not isinstance(raw_reasons, Mapping):
            continue
        reasons.extend(str(reason) for reason in raw_reasons.values() if str(reason or "").strip())
    return reasons


def _record_failed_symbol(
    *,
    symbol: str,
    reason: str,
    failed_symbols: list[str],
    failed_symbol_count: int,
    unavailable_reason_counts: Dict[str, int],
    failed_symbol_reasons: Optional[Dict[str, str]] = None,
) -> int:
    failed_symbols.append(symbol)
    unavailable_reason_counts[reason] = unavailable_reason_counts.get(reason, 0) + 1
    if failed_symbol_reasons is not None:
        failed_symbol_reasons[symbol] = reason
    return failed_symbol_count + 1


def _quote_from_alpaca_fetcher(
    fetcher: AlpacaFetcher,
    symbol: str,
    data_feed: str,
    now_utc: Optional[datetime] = None,
) -> _AlpacaQuoteResult:
    end_dt = (now_utc or _utc_now()).astimezone(timezone.utc)
    windows: Dict[str, Dict[str, Any]] = {}
    window_sources: Dict[str, Dict[str, Any]] = {}
    window_failure_reasons: Dict[str, str] = {}
    for window, (timeframe, lookback, limit) in _ALPACA_TIMEFRAMES.items():
        request_start = end_dt - lookback
        request_end = end_dt
        request_plan: Optional[_IntradayWindowRequestPlan] = None
        if window in _SHORT_INTRADAY_WINDOWS:
            request_plan = _short_intraday_window_request_plan(window, now_utc=end_dt)
            request_start = request_plan.start
            request_end = request_plan.end
        try:
            bars = fetcher.get_bars(
                symbol,
                timeframe=timeframe,
                start=request_start.isoformat(),
                end=request_end.isoformat(),
                limit=limit,
            )
        except Exception as exc:
            window_failure_reasons[window] = _classify_configured_failure(exc)
            continue
        materialized_bars = _materialize_bars(bars)
        if not materialized_bars:
            window_failure_reasons[window] = _empty_bars_failure_class(bars)
            continue
        slot = _window_from_alpaca_bars(
            symbol,
            window,
            materialized_bars,
            data_feed=data_feed,
            request_plan=request_plan,
        )
        if slot is not None:
            windows[window] = slot
            window_sources[window] = {
                "bars": bars,
                "slot": slot,
            }

    if not windows:
        if not window_failure_reasons:
            window_failure_reasons = {window: "empty_response" for window in _ALPACA_TIMEFRAMES}
        return _AlpacaQuoteResult(
            quote=None,
            window_failure_reasons=window_failure_reasons,
        )

    preferred_window = next((window for window in ("1d", "60m", "15m", "5m") if window in windows), None)
    if preferred_window is None:
        return _AlpacaQuoteResult(quote=None, window_failure_reasons=window_failure_reasons)
    preferred_slot = windows[preferred_window]
    preferred_bars = window_sources[preferred_window]["bars"]
    last_bar = _last_bar(preferred_bars)
    if last_bar is None:
        return _AlpacaQuoteResult(quote=None, window_failure_reasons=window_failure_reasons)
    close = _number(_field(last_bar, "c", "close", "Close"))
    if close is None:
        return _AlpacaQuoteResult(quote=None, window_failure_reasons=window_failure_reasons)
    high = _number(_field(last_bar, "h", "high", "High"))
    low = _number(_field(last_bar, "l", "low", "Low"))
    volume = _number(_field(last_bar, "v", "volume", "Volume"))
    average_volume = _average_bar_volume(preferred_bars)
    vwap = _number(_field(last_bar, "vw", "vwap", "VWAP"))
    if vwap is None and None not in {high, low, close}:
        vwap = round((float(high) + float(low) + float(close)) / 3, 3)

    volume_ratio = None
    if volume is not None and average_volume not in {None, 0}:
        volume_ratio = round(float(volume) / float(average_volume), 3)

    freshness = _freshest_configured_freshness(windows.values())
    as_of = str(preferred_slot.get("asOf") or "")
    source_label = _configured_source_label(data_feed)
    quote = {
        "symbol": symbol,
        "name": symbol,
        "price": close,
        "changePercent": preferred_slot.get("changePercent"),
        "volume": volume,
        "averageVolume": average_volume,
        "volumeRatio": volume_ratio,
        "vwap": vwap,
        "trend": _trend_from_bars(preferred_bars),
        "timeWindows": windows,
        "freshness": freshness,
        "isFallback": False,
        "isStale": freshness == "stale",
        "source": _CONFIGURED_SOURCE,
        "sourceLabel": source_label,
        "sourceType": _CONFIGURED_SOURCE_TYPE,
        "sourceTier": _CONFIGURED_SOURCE_TIER,
        "providerTier": _CONFIGURED_PROVIDER_TIER,
        "confidenceWeight": _CONFIGURED_CONFIDENCE_WEIGHT,
        "asOf": as_of or None,
    }
    if window_failure_reasons:
        quote["windowFailureReasons"] = window_failure_reasons
    return _AlpacaQuoteResult(
        quote=quote,
        window_failure_reasons=window_failure_reasons,
    )


def _window_from_alpaca_bars(
    symbol: str,
    window: str,
    bars: Any,
    *,
    data_feed: str,
    request_plan: Optional[_IntradayWindowRequestPlan] = None,
) -> Optional[Dict[str, Any]]:
    materialized = _materialize_bars(bars)
    if not materialized:
        return None
    first_bar = materialized[0]
    last_bar = materialized[-1]
    first_close = _number(_field(first_bar, "c", "close", "Close"))
    close = _number(_field(last_bar, "c", "close", "Close"))
    if close is None:
        return None
    change_percent = None
    if first_close not in {None, 0}:
        change_percent = round(((float(close) - float(first_close)) / float(first_close)) * 100, 3)
    volume = _number(_field(last_bar, "v", "volume", "Volume"))
    average_volume = _average_bar_volume(materialized)
    relative_volume = None
    if volume is not None and average_volume not in {None, 0}:
        relative_volume = round(float(volume) / float(average_volume), 3)
    as_of = _as_of_from_bar(last_bar)
    freshness = _configured_freshness_from_as_of(as_of, data_feed=data_feed, window=window)
    payload = {
        "window": window,
        "available": change_percent is not None or relative_volume is not None,
        "changePercent": change_percent,
        "relativeVolume": relative_volume,
        "freshness": freshness,
        "isFallback": False,
        "isStale": freshness == "stale",
        "source": _CONFIGURED_SOURCE,
        "sourceLabel": _configured_source_label(data_feed),
        "sourceType": _CONFIGURED_SOURCE_TYPE,
        "sourceTier": _CONFIGURED_SOURCE_TIER,
        "providerTier": _CONFIGURED_PROVIDER_TIER,
        "asOf": as_of,
        "reason": None if change_percent is not None or relative_volume is not None else "window_unavailable",
    }
    if request_plan is not None:
        payload.update({
            "requestWindowSelectionMode": request_plan.selection_mode,
            "requestSessionState": request_plan.session_state,
            "requestSessionDate": request_plan.session_date,
            "requestStart": request_plan.start.isoformat(),
            "requestEnd": request_plan.end.isoformat(),
        })
    return payload


def _materialize_bars(bars: Any) -> list[Any]:
    if bars is None:
        return []
    if isinstance(bars, pd.DataFrame):
        if bars.empty:
            return []
        return [row for _, row in bars.iterrows()]
    if isinstance(bars, Mapping):
        raw_bars = bars.get("bars")
        if isinstance(raw_bars, Sequence) and not isinstance(raw_bars, (str, bytes)):
            return list(raw_bars)
        return []
    if isinstance(bars, Sequence) and not isinstance(bars, (str, bytes)):
        return list(bars)
    return []


def _empty_bars_failure_class(bars: Any) -> str:
    classified = _classify_configured_failure(_empty_bars_reason_text(bars))
    if classified in {"interval_mapping", "market_session", "calendar"}:
        return classified
    return "empty_response"


def _empty_bars_reason_text(bars: Any) -> str:
    if not isinstance(bars, Mapping):
        return ""
    values: list[str] = []
    for key in (
        "message",
        "error",
        "error_message",
        "reason",
        "detail",
        "code",
        "status",
    ):
        value = bars.get(key)
        if value is not None and str(value).strip():
            values.append(str(value))
    for nested_key in ("meta", "metadata"):
        nested = bars.get(nested_key)
        if not isinstance(nested, Mapping):
            continue
        for value in nested.values():
            if value is not None and str(value).strip():
                values.append(str(value))
    return " ".join(values)


def _last_bar(bars: Any) -> Optional[Any]:
    materialized = _materialize_bars(bars)
    return materialized[-1] if materialized else None


def _average_bar_volume(bars: Any) -> Optional[float]:
    volumes = [
        value
        for value in (_number(_field(bar, "v", "volume", "Volume")) for bar in _materialize_bars(bars))
        if value is not None
    ]
    if len(volumes) > 1:
        volumes = volumes[:-1]
    if not volumes:
        return None
    return round(sum(volumes) / len(volumes), 3)


def _trend_from_bars(bars: Any) -> list[float]:
    values: list[float] = []
    for bar in _materialize_bars(bars):
        close = _number(_field(bar, "c", "close", "Close"))
        if close is not None:
            values.append(close)
    return values


def _as_of_from_bar(bar: Any) -> str:
    raw = _field(bar, "t", "timestamp", "date", "Date")
    if raw is None:
        return _utc_now().isoformat(timespec="seconds")
    try:
        timestamp = pd.Timestamp(raw)
    except Exception:
        return _utc_now().isoformat(timespec="seconds")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.isoformat()


def _configured_freshness_from_as_of(as_of: str, *, data_feed: str, window: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
    except Exception:
        return "delayed"
    current = _utc_now()
    age_seconds = (current - parsed.astimezone(timezone.utc)).total_seconds()
    if age_seconds < 0:
        age_seconds = 0
    if age_seconds >= 3 * 24 * 60 * 60:
        return "stale"
    if window in _INTRADAY_WINDOWS and data_feed.lower() == "sip" and age_seconds <= 20 * 60:
        return "live"
    return "delayed"


def _freshest_configured_freshness(slots: Iterable[Mapping[str, Any]]) -> str:
    values = [str(slot.get("freshness") or "") for slot in slots]
    for candidate in ("live", "delayed", "cached", "stale", "fallback"):
        if candidate in values:
            return candidate
    return "delayed"


def _configured_source_label(data_feed: str) -> str:
    feed = str(data_feed or "iex").strip().upper() or "IEX"
    return f"Alpaca {feed}"


def _metadata_quote_mode(quotes: Mapping[str, Dict[str, Any]]) -> str:
    sources = {str(quote.get("source") or "") for quote in quotes.values()}
    if not quotes:
        return "fallback"
    if sources == {_CONFIGURED_SOURCE}:
        return "configured"
    if sources == {_QUOTE_SOURCE}:
        return _QUOTE_MODE
    return "mixed"


def _metadata_source_summary(quotes: Mapping[str, Dict[str, Any]]) -> Dict[str, str]:
    if not quotes:
        return {
            "source": "fallback",
            "sourceLabel": "备用数据",
            "sourceType": "fallback_static",
            "sourceTier": "static_fallback",
            "providerTier": "fallback",
        }
    sources = {str(quote.get("source") or "") for quote in quotes.values()}
    if sources == {_CONFIGURED_SOURCE}:
        label = _dominant_label(
            _count_values(str(quote.get("sourceLabel") or _configured_source_label("iex")) for quote in quotes.values()),
            default=_configured_source_label("iex"),
        )
        return {
            "source": _CONFIGURED_SOURCE,
            "sourceLabel": label,
            "sourceType": _CONFIGURED_SOURCE_TYPE,
            "sourceTier": _CONFIGURED_SOURCE_TIER,
            "providerTier": _CONFIGURED_PROVIDER_TIER,
        }
    if sources == {_QUOTE_SOURCE}:
        return {
            "source": _QUOTE_SOURCE,
            "sourceLabel": _QUOTE_SOURCE_LABEL,
            "sourceType": _QUOTE_SOURCE_TYPE,
            "sourceTier": _QUOTE_SOURCE_TIER,
            "providerTier": _QUOTE_PROVIDER_TIER,
        }
    return {
        "source": "mixed",
        "sourceLabel": "Alpaca + Yahoo Finance",
        "sourceType": "mixed",
        "sourceTier": _QUOTE_SOURCE_TIER,
        "providerTier": "mixed_configured_and_tier_2",
    }


def _metadata_freshness(
    *,
    quotes: Mapping[str, Dict[str, Any]],
    failed_symbol_count: int,
    fallback_used: bool,
) -> str:
    if not quotes:
        return "fallback"
    if failed_symbol_count or fallback_used:
        return "partial"
    return _dominant_label(_count_values(str(quote.get("freshness") or "unknown") for quote in quotes.values()), default="fallback")


def _confidence_weight(
    *,
    quotes: Mapping[str, Dict[str, Any]],
    coverage_percent: float,
    failed_symbol_count: int,
) -> float:
    if not quotes:
        return 0.0
    base = min(float(quote.get("confidenceWeight") or _QUOTE_CONFIDENCE_WEIGHT) for quote in quotes.values())
    coverage_ratio = max(0.0, min(1.0, coverage_percent / 100.0))
    penalty = 0.1 if failed_symbol_count else 0.0
    return round(max(0.0, min(1.0, base * coverage_ratio - penalty)), 2)


def _degradation_reasons(
    *,
    coverage_percent: float,
    failed_symbol_count: int,
    source_summary: Mapping[str, str],
    freshness: str,
) -> list[str]:
    reasons: list[str] = []
    if failed_symbol_count:
        reasons.append("symbol_failures")
    if coverage_percent <= 0:
        reasons.append("no_coverage")
    elif coverage_percent < 80:
        reasons.append("partial_coverage")
    if source_summary.get("providerTier") == _QUOTE_PROVIDER_TIER:
        reasons.append("tier_2_delayed_proxy")
    elif source_summary.get("providerTier") == "mixed_configured_and_tier_2":
        reasons.append("mixed_provider_tiers")
    if freshness in {"partial", "stale", "fallback"}:
        reasons.append(f"{freshness}_freshness")
    return list(dict.fromkeys(reasons))


def _count_values(values: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return counts


def _quote_from_history_frame(symbol: str, frame: Any) -> Optional[Dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        last_row = frame.iloc[-1]
    except Exception:
        return None

    close = _number(_field(last_row, "Close", "close", "Adj Close", "adj_close"))
    previous_row = frame.iloc[-2] if len(frame) >= 2 else last_row
    previous_close = _number(_field(previous_row, "Close", "close", "Adj Close", "adj_close"))
    high = _number(_field(last_row, "High", "high"))
    low = _number(_field(last_row, "Low", "low"))
    volume = _number(_field(last_row, "Volume", "volume"))
    average_volume = _average_volume(frame)
    vwap = _number(_field(last_row, "VWAP", "vwap"))
    if vwap is None and None not in {high, low, close}:
        vwap = round((float(high) + float(low) + float(close)) / 3, 3)
    if close is None:
        return None

    change_percent = None
    if previous_close not in {None, 0}:
        change_percent = round(((float(close) - float(previous_close)) / float(previous_close)) * 100, 3)

    volume_ratio = None
    if volume is not None and average_volume not in {None, 0}:
        volume_ratio = round(float(volume) / float(average_volume), 3)

    as_of = _as_of_from_index(frame.index[-1] if len(frame.index) else None)
    freshness = _freshness_from_as_of(as_of)
    is_stale = freshness == "stale"

    time_windows = {
        "1d": {
            "changePercent": change_percent,
            "relativeVolume": volume_ratio,
            "freshness": freshness,
            "asOf": as_of,
        }
    }

    return {
        "symbol": symbol,
        "name": symbol,
        "price": close,
        "changePercent": change_percent,
        "volume": volume,
        "averageVolume": average_volume,
        "volumeRatio": volume_ratio,
        "vwap": vwap,
        "trend": _trend_from_frame(frame),
        "timeWindows": time_windows,
        "freshness": freshness,
        "isFallback": False,
        "isStale": is_stale,
        "source": _QUOTE_SOURCE,
        "sourceLabel": _QUOTE_SOURCE_LABEL,
        "sourceType": _QUOTE_SOURCE_TYPE,
        "sourceTier": _QUOTE_SOURCE_TIER,
        "providerTier": _QUOTE_PROVIDER_TIER,
        "confidenceWeight": _QUOTE_CONFIDENCE_WEIGHT,
        "asOf": as_of,
    }


def _field(row: Any, *names: str) -> Any:
    for name in names:
        if isinstance(row, Mapping) and name in row:
            return row.get(name)
        try:
            value = row[name]
        except Exception:
            continue
        if value is not None:
            return value
    return None


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _average_volume(frame: Any) -> Optional[float]:
    try:
        volumes = [float(value) for value in frame.get("Volume", []) if value is not None]
    except Exception:
        return None
    if len(volumes) > 1:
        volumes = volumes[:-1]
    if not volumes:
        return None
    return round(sum(volumes) / len(volumes), 3)


def _trend_from_frame(frame: Any) -> list[float]:
    try:
        close_series = frame.get("Close", [])
    except Exception:
        return []
    values = []
    for value in close_series:
        number = _number(value)
        if number is not None:
            values.append(number)
    return values


def _as_of_from_index(index_value: Any) -> str:
    if index_value is None:
        return _utc_now().isoformat(timespec="seconds")
    try:
        timestamp = pd.Timestamp(index_value)
    except Exception:
        return _utc_now().isoformat(timespec="seconds")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.isoformat()


def _freshness_from_as_of(as_of: str) -> str:
    try:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except Exception:
        return "delayed"
    current = _utc_now()
    return "stale" if (current - parsed).days >= 3 else "delayed"


def _dominant_label(counts: Mapping[str, int], *, default: str) -> str:
    if not counts:
        return default
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _bounded_unique_symbols(symbols: Sequence[str]) -> list[str]:
    bounded: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = _sanitize_symbol(symbol)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        bounded.append(normalized)
        if len(bounded) >= _FAILED_SYMBOL_LIST_LIMIT:
            break
    return bounded


def _sanitize_unavailable_reason(raw_reason: str) -> str:
    normalized = str(raw_reason or "").strip().lower()
    if not normalized:
        return "quote_unavailable"
    if "delisted" in normalized or "no price data" in normalized or "no data" in normalized:
        return "symbol_unavailable"
    if "timeout" in normalized or "request" in normalized or "fetch" in normalized:
        return "quote_fetch_failed"
    return "quote_unavailable"


def _sanitize_provider_failure_reason(raw_reason: str) -> str:
    normalized = str(raw_reason or "").strip().lower()
    if not normalized:
        return "provider_unavailable"
    if "proxyerror" in normalized or "proxy error" in normalized or "unable to connect to proxy" in normalized:
        return "proxy_unreachable"
    if "timeout" in normalized or "request" in normalized or "fetch" in normalized:
        return "quote_fetch_failed"
    return "provider_unavailable"


def _classify_configured_failure(raw_reason: Any) -> str:
    reason_type = ""
    if raw_reason is not None and not isinstance(raw_reason, (str, bytes)):
        reason_type = (
            f"{raw_reason.__class__.__module__}.{raw_reason.__class__.__name__}"
        ).lower()
    normalized = str(raw_reason or "").strip().lower()
    if not normalized and not reason_type:
        return "unknown"
    if (
        "proxyerror" in reason_type
        or "proxyerror" in normalized
        or "proxy error" in normalized
        or "unable to connect to proxy" in normalized
        or "cannot connect to proxy" in normalized
        or "proxy connection" in normalized
    ):
        return "proxy_unreachable"
    if (
        "connecttimeout" in reason_type
        or "connect timeout" in normalized
        or "connect timed out" in normalized
    ):
        return "connect_timeout"
    if (
        "readtimeout" in reason_type
        or "read timeout" in normalized
        or "read timed out" in normalized
    ):
        return "read_timeout"
    if (
        "connectionerror" in reason_type
        or "newconnectionerror" in reason_type
        or "maxretryerror" in reason_type
        or "name resolution" in normalized
        or "temporary failure in name resolution" in normalized
        or "nodename nor servname provided" in normalized
        or "network is unreachable" in normalized
        or "failed to establish a new connection" in normalized
    ):
        return "network_unreachable"
    if (
        "401" in normalized
        or "unauthorized" in normalized
        or "invalid api key" in normalized
        or "invalid key" in normalized
        or "authentication" in normalized
        or "auth failed" in normalized
    ):
        return "auth_failed"
    if (
        "403" in normalized
        or "forbidden" in normalized
        or "entitlement" in normalized
        or "permission" in normalized
        or "subscription" in normalized
    ):
        return "entitlement_denied"
    if (
        "unsupported timeframe" in normalized
        or "unsupported time frame" in normalized
        or "unsupported interval" in normalized
        or "invalid timeframe" in normalized
        or "invalid time frame" in normalized
        or "invalid interval" in normalized
        or "timeframe is not supported" in normalized
        or "time frame is not supported" in normalized
        or "interval is not supported" in normalized
    ):
        return "interval_mapping"
    if (
        "calendar" in normalized
        or "market holiday" in normalized
        or "trading holiday" in normalized
        or "non-trading day" in normalized
        or "non trading day" in normalized
        or "no trading sessions" in normalized
        or "no trading days" in normalized
    ):
        return "calendar"
    if (
        "market closed" in normalized
        or "market is closed" in normalized
        or "outside market hours" in normalized
        or "trading session" in normalized
        or "no active session" in normalized
        or "session closed" in normalized
    ):
        return "market_session"
    if "429" in normalized or "rate limit" in normalized or "too many requests" in normalized:
        return "rate_limited"
    if "timeout" in reason_type:
        return "provider_timeout"
    if "request timeout" in normalized:
        return "timeout"
    if "timeout" in normalized or "timed out" in normalized:
        return "timeout"
    if (
        "delisted" in normalized
        or "no price data" in normalized
        or "no data" in normalized
        or "symbol not found" in normalized
        or "unknown symbol" in normalized
    ):
        return "symbol_not_found"
    if "empty" in normalized or "no bars" in normalized or "未返回" in normalized:
        return "empty_response"
    return "provider_error"


def _legacy_symbol_failure_reason(failure_classes: Iterable[Any]) -> str:
    primary = _primary_failure_class([
        _normalize_configured_failure_class(failure_class)
        for failure_class in failure_classes
        if str(failure_class or "").strip()
    ])
    if primary == "symbol_not_found":
        return "symbol_unavailable"
    if _is_timeout_failure_class(primary):
        return "quote_fetch_failed"
    if primary in {
        "auth_failed",
        "entitlement_denied",
        "interval_mapping",
        "market_session",
        "calendar",
        "rate_limited",
        "proxy_unreachable",
        "network_unreachable",
        "empty_response",
        "provider_error",
    }:
        return "quote_unavailable"
    return "quote_unavailable"


def _sanitize_window_failure_reason(raw_reason: str) -> str:
    return _classify_configured_failure(raw_reason)


def _cooldown_reason(symbol: str, now_monotonic: float) -> Optional[str]:
    state = _UNAVAILABLE_SYMBOL_STATE.get(symbol)
    if not state:
        return None
    retry_after = state.get("retryAfterMonotonic")
    if not isinstance(retry_after, (int, float)) or retry_after <= now_monotonic:
        _UNAVAILABLE_SYMBOL_STATE.pop(symbol, None)
        return None
    return str(state.get("reason") or "symbol_unavailable")


def _mark_symbol_unavailable(symbol: str, reason: str, now_monotonic: float) -> None:
    _UNAVAILABLE_SYMBOL_STATE[symbol] = {
        "reason": reason,
        "retryAfterMonotonic": now_monotonic + _UNAVAILABLE_SYMBOL_COOLDOWN_SECONDS,
    }


load_rotation_radar_quotes.rotation_radar_provider_diagnostics = get_rotation_radar_provider_diagnostics
