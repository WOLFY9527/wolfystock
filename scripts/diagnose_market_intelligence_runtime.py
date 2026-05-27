#!/usr/bin/env python3
"""Emit a sanitized Market Intelligence runtime diagnostic bundle."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.official_macro_transport import run_official_macro_live_smoke
from src.services.options_market_data_provider import (
    DEFAULT_OPTIONS_FIXTURE_PATH,
    LIVE_OPTIONS_PROVIDER_NAMES,
    OptionsLiveProviderConfig,
    OptionsProviderError,
    OptionsProviderUnavailable,
    TradierOptionsHttpTransport,
    build_options_provider_live_readiness_preflight,
)
from src.services.options_event_calendar_authority import (
    build_options_event_calendar_authority_diagnostic,
)
from src.services.options_expiration_calendar_authority import (
    build_options_expiration_calendar_authority_diagnostic,
)
from src.services.options_iv_rank_authority import build_options_iv_rank_authority_diagnostic
from src.services.polygon_us_breadth_provider import (
    diagnostic_summary as polygon_us_breadth_diagnostic_summary,
    run_polygon_us_breadth_activation,
)
from src.services.rotation_radar_quote_provider import run_rotation_radar_alpaca_live_smoke
from src.services.us_breadth_contracts import (
    US_BREADTH_SYMBOLS,
    build_us_breadth_missing_authority_diagnostic,
)


DEFAULT_TIMEOUT_SECONDS = 3.0
BASE_URL_ENV_VAR = "MARKET_INTELLIGENCE_BASE_URL"
REDACTED = "redacted"
_BLOCKED_REASON_TOKENS = ("token", "secret", "auth", "cookie", "header", "bearer", "apikey", "api_key")
_SAFE_REASON_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_:-")
_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("marketOverviewMacro", "/api/v1/market-overview/macro"),
    ("usBreadth", "/api/v1/market/us-breadth"),
    ("liquidityMonitor", "/api/v1/market/liquidity-monitor"),
    ("rotationRadar", "/api/v1/market/rotation-radar?market=US"),
    ("marketTemperature", "/api/v1/market/temperature"),
    ("dataReadiness", "/api/v1/market/data-readiness"),
)
_OPTIONS_LIVE_PROBE_PROVIDER = "tradier"
_OPTIONS_LIVE_PROBE_ENDPOINT_CLASSES = ("quote", "expirations")
_OPTIONS_CHAIN_PROBE_ENDPOINT_CLASS = "chain"
_OPTIONS_AUTHORITY_DIAGNOSTIC_WARNING = (
    "Authority diagnostics and checklist completeness are diagnostic-only and not decisionGrade."
)


def _skipped_official_macro_diagnostic(reason: str = "not_requested") -> dict[str, Any]:
    return {
        "status": "skipped",
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledSeries": [],
        "missingSeries": [],
        "staleSeries": [],
        "reason": reason,
    }


def _skipped_alpaca_rotation_diagnostic(reason: str = "not_requested") -> dict[str, Any]:
    return {
        "status": "skipped",
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledWindows": [],
        "missingWindows": [],
        "staleWindows": [],
        "reason": reason,
    }


def _skipped_polygon_us_breadth_diagnostic(
    reason_code: str = "not_requested",
) -> dict[str, Any]:
    return {
        "status": "skipped",
        "credentialsPresent": False,
        "probePassed": False,
        "observationDate": None,
        "freshnessValid": False,
        "coverageCount": 0,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledMetrics": [],
        "missingMetrics": list(US_BREADTH_SYMBOLS),
        "reasonCodes": [reason_code],
    }


def _sanitize_reason(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if any(token in lowered for token in _BLOCKED_REASON_TOKENS):
        return REDACTED
    if len(text) > 64 or any(character.lower() not in _SAFE_REASON_CHARS for character in text):
        return REDACTED
    return text


def _sanitize_reason_code(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    blocked_tokens = ("token", "secret", "cookie", "header", "bearer", "apikey", "api_key", "authorization")
    if any(token in lowered for token in blocked_tokens):
        return REDACTED
    if len(text) > 64 or any(character.lower() not in _SAFE_REASON_CHARS for character in text):
        return REDACTED
    return text


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _sanitized_string_list(value: Any) -> list[str]:
    sanitized: list[str] = []
    for item in _string_list(value):
        reason = _sanitize_reason_code(item)
        if reason:
            sanitized.append(reason)
    return sanitized


def _non_negative_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _bounded_options_probe_timeout_seconds(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 2.0
    return max(0.25, min(parsed, 5.0))


def _normalize_options_probe_symbol(symbol: str) -> str:
    text = str(symbol or "TEM").strip().upper()
    return text if text else "TEM"


def _compact_official_macro_diagnostic(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "credentialsPresent": bool(payload.get("credentialsPresent", False)),
        "providerConstructed": bool(payload.get("providerConstructed", False)),
        "probePassed": bool(payload.get("probePassed", False)),
        "freshnessValid": bool(payload.get("freshnessValid", False)),
        "sourceMetadataValid": bool(payload.get("sourceMetadataValid", False)),
        "sourceAuthorityAllowed": bool(payload.get("sourceAuthorityAllowed", False)),
        "scoreContributionAllowed": bool(payload.get("scoreContributionAllowed", False)),
        "fulfilledSeries": _string_list(payload.get("fulfilledSeries")),
        "missingSeries": _string_list(payload.get("missingSeries")),
        "staleSeries": _string_list(payload.get("staleSeries")),
        "reason": _sanitize_reason(payload.get("reason")),
    }


def _compact_alpaca_rotation_diagnostic(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "credentialsPresent": bool(payload.get("credentialsPresent", False)),
        "providerConstructed": bool(payload.get("providerConstructed", False)),
        "probePassed": bool(payload.get("probePassed", False)),
        "freshnessValid": bool(payload.get("freshnessValid", False)),
        "sourceMetadataValid": bool(payload.get("sourceMetadataValid", False)),
        "sourceAuthorityAllowed": bool(payload.get("sourceAuthorityAllowed", False)),
        "scoreContributionAllowed": bool(payload.get("scoreContributionAllowed", False)),
        "fulfilledWindows": _string_list(payload.get("fulfilledWindows")),
        "missingWindows": _string_list(payload.get("missingWindows")),
        "staleWindows": _string_list(payload.get("staleWindows")),
        "reason": _sanitize_reason(payload.get("reason")),
    }


def _compact_polygon_us_breadth_diagnostic(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "credentialsPresent": bool(payload.get("credentialsPresent", False)),
        "probePassed": bool(payload.get("probePassed", False)),
        "observationDate": payload.get("observationDate") if payload.get("observationDate") else None,
        "freshnessValid": bool(payload.get("freshnessValid", False)),
        "coverageCount": _non_negative_int(payload.get("coverageCount")),
        "sourceAuthorityAllowed": bool(payload.get("sourceAuthorityAllowed", False)),
        "scoreContributionAllowed": bool(payload.get("scoreContributionAllowed", False)),
        "fulfilledMetrics": _string_list(payload.get("fulfilledMetrics")),
        "missingMetrics": _string_list(payload.get("missingMetrics")),
        "reasonCodes": _sanitized_string_list(payload.get("reasonCodes")),
    }


def _compact_options_lab_provider_preflight(payload: dict[str, Any]) -> dict[str, Any]:
    credential_contract = dict(payload.get("credentialContract") or {})
    live_probe = dict(payload.get("liveProbe") or {})
    live_probe_enabled = bool(live_probe.get("enabled", False))
    live_probe_explicit_opt_in = bool(live_probe.get("explicitOptIn", False))
    if live_probe_enabled:
        live_probe_status = "ready"
    elif live_probe_explicit_opt_in:
        live_probe_status = "blocked"
    else:
        live_probe_status = "disabled"

    return {
        "providerId": str(payload.get("providerName") or "unknown"),
        "readinessState": str(payload.get("readinessState") or "unknown"),
        "credentialsPresent": bool(payload.get("credentialsPresent", False)),
        "credentialCounts": {
            "required": _non_negative_int(credential_contract.get("requiredCredentialCount")),
            "configured": _non_negative_int(credential_contract.get("configuredCredentialCount")),
            "invalid": _non_negative_int(credential_contract.get("invalidCredentialCount")),
            "partial": _non_negative_int(credential_contract.get("partialCredentialCount")),
        },
        "dryRunEnabled": bool(payload.get("dryRunEnabled", False)),
        "liveCallsEnabled": bool(payload.get("liveHttpCallsEnabled", False)),
        "brokerOrderEnabled": bool(payload.get("brokerOrderPathEnabled", False)),
        "portfolioMutationEnabled": bool(payload.get("portfolioMutationPathEnabled", False)),
        "tradeable": bool(payload.get("tradeableData", False)),
        "liveProbe": {
            "status": live_probe_status,
            "enabled": live_probe_enabled,
            "explicitOptIn": live_probe_explicit_opt_in,
            "reasonCode": _sanitize_reason_code(live_probe.get("reasonCode")) or "unknown",
            "timeoutSeconds": float(live_probe.get("timeoutSeconds") or 0.0),
            "networkCallExecuted": bool(live_probe.get("networkCallExecuted", False)),
        },
    }


def _safe_family_names(value: Any) -> list[str]:
    return _sanitized_string_list(value)


def _compact_options_authority_checklist_summary(payload: Mapping[str, Any]) -> dict[str, list[str]] | None:
    checklist = payload.get("authorityEvidenceChecklist")
    present_families: list[str] = []
    missing_families: list[str] = []

    if isinstance(checklist, Mapping):
        for raw_family, raw_entry in checklist.items():
            family = _sanitize_reason_code(raw_family)
            if not family:
                continue
            entry = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
            if bool(entry.get("present")):
                present_families.append(family)
            else:
                missing_families.append(family)

    missing_families.extend(_safe_family_names(payload.get("authorityEvidenceGapFamilies")))

    deduped_present = list(dict.fromkeys(present_families))
    deduped_missing = list(dict.fromkeys(missing_families))
    summary: dict[str, list[str]] = {}
    if deduped_present:
        summary["presentFamilies"] = deduped_present
    if deduped_missing:
        summary["missingFamilies"] = deduped_missing
    return summary or None


def _compact_options_authority_surface(surface: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "surface": surface,
        "authorityState": str(payload.get("authorityState") or "missing"),
        "authoritative": bool(payload.get("authoritative", False)),
        "diagnosticOnly": bool(payload.get("diagnosticOnly", True)),
        "reasonCodes": _sanitized_string_list(payload.get("reasonCodes"))[:3],
    }
    checklist_summary = _compact_options_authority_checklist_summary(payload)
    if checklist_summary:
        summary["checklistSummary"] = checklist_summary
    return summary


def _collect_options_authority_diagnostics(
    iv_rank_authority: Mapping[str, Any],
    event_calendar_authority: Mapping[str, Any],
    expiration_calendar_authority: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "diagnosticOnly": True,
        "decisionGrade": False,
        "warning": _OPTIONS_AUTHORITY_DIAGNOSTIC_WARNING,
        "surfaces": [
            _compact_options_authority_surface("iv_rank", iv_rank_authority),
            _compact_options_authority_surface("event_calendar", event_calendar_authority),
            _compact_options_authority_surface("expiration_calendar", expiration_calendar_authority),
        ],
    }


def _collect_options_iv_rank_authority() -> dict[str, Any]:
    try:
        fixture = json.loads(DEFAULT_OPTIONS_FIXTURE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return build_options_iv_rank_authority_diagnostic(None)

    proxy_rows = fixture.get("historicalIvProxy") or fixture.get("historical_iv_proxy") or []
    proxy_history_points = 0
    for item in proxy_rows:
        if not isinstance(item, dict):
            continue
        try:
            value = float(item.get("iv"))
        except (TypeError, ValueError):
            continue
        if 0.01 <= value <= 3.0:
            proxy_history_points += 1
    current_iv_sample_count = 0
    for contract in fixture.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        try:
            value = float(contract.get("impliedVolatility"))
        except (TypeError, ValueError):
            continue
        if 0.01 <= value <= 3.0:
            current_iv_sample_count += 1

    first_proxy_source = None
    for item in proxy_rows:
        if isinstance(item, dict) and item.get("source"):
            first_proxy_source = item.get("source")
            break

    return build_options_iv_rank_authority_diagnostic(
        {
            "providerId": fixture.get("source") or fixture.get("providerName"),
            "sourceType": first_proxy_source or "synthetic_fixture_proxy",
            "ivRankStatus": "available" if proxy_history_points and current_iv_sample_count else "unavailable",
            "ivRankSource": first_proxy_source or "synthetic_fixture_proxy",
            "methodology": "local_min_max_percentile_from_proxy_history_plus_selected_contract_iv",
            "historicalOptionIvSeriesAvailable": False,
            "coverageMetadata": {
                "proxyHistoryPoints": proxy_history_points,
                "currentIvSampleCount": current_iv_sample_count,
                "currentIvDerivedFrom": "selected_contract_implied_volatility",
            },
            "sandboxOrProduction": "not_provider_sourced",
            "notes": ["test_only_low_confidence"],
        }
    )


def _collect_options_event_calendar_authority() -> dict[str, Any]:
    try:
        fixture = json.loads(DEFAULT_OPTIONS_FIXTURE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return build_options_event_calendar_authority_diagnostic(None)

    event_calendar = fixture.get("eventCalendar") or fixture.get("event_calendar")
    if not isinstance(event_calendar, Mapping):
        return build_options_event_calendar_authority_diagnostic(None)

    events = event_calendar.get("events") if isinstance(event_calendar, Mapping) else None
    event_rows = events if isinstance(events, list) else []
    event_types: list[str] = []
    event_count = 0
    confirmation_status = None
    event_id = None
    timezone = event_calendar.get("timezone") if isinstance(event_calendar, Mapping) else None
    session_name = None

    for item in event_rows:
        if not isinstance(item, Mapping):
            continue
        event_count += 1
        event_type = item.get("type")
        if event_type and event_type not in event_types:
            event_types.append(event_type)
        if confirmation_status is None:
            confirmation_status = item.get("confirmationStatus") or item.get("confirmation_status")
        if event_id is None:
            event_id = item.get("id") or item.get("eventId")
        if session_name is None:
            session_name = item.get("session")

    session_metadata = {"session": session_name} if session_name else {}
    return build_options_event_calendar_authority_diagnostic(
        {
            "providerId": fixture.get("source") or fixture.get("providerName"),
            "sourceType": "fixture",
            "eventCalendarStatus": "available" if event_count else "unavailable",
            "eventTypesCovered": event_types,
            "underlyingCoverage": [fixture.get("symbol")] if fixture.get("symbol") else [],
            "timezone": timezone,
            "sessionMetadata": session_metadata,
            "confirmationStatus": confirmation_status,
            "eventId": event_id,
            "coverageMetadata": {"eventCount": event_count} if event_count else {},
            "sandboxOrProduction": "not_provider_sourced",
        }
    )


def _collect_options_expiration_calendar_authority() -> dict[str, Any]:
    try:
        fixture = json.loads(DEFAULT_OPTIONS_FIXTURE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return build_options_expiration_calendar_authority_diagnostic(None)

    expiration_rows = fixture.get("expirations") or []
    if not isinstance(expiration_rows, list):
        return build_options_expiration_calendar_authority_diagnostic(None)

    expiration_dates: list[str] = []
    expiration_types: list[str] = []
    as_of = None
    chain_available_count = 0

    for item in expiration_rows:
        if not isinstance(item, Mapping):
            continue
        expiration_date = item.get("date") or item.get("expiration")
        if expiration_date:
            expiration_date = str(expiration_date)
            expiration_dates.append(expiration_date)
        expiration_type = item.get("type")
        if expiration_type and expiration_type not in expiration_types:
            expiration_types.append(str(expiration_type))
        if as_of is None:
            as_of = item.get("asOf") or item.get("as_of")
        if item.get("chainAvailable") is True:
            chain_available_count += 1

    expiration_dates = sorted({value for value in expiration_dates if value})
    coverage_metadata = {}
    if expiration_dates:
        coverage_metadata = {
            "expirationCoverage": "complete",
            "expirationCount": len(expiration_dates),
            "chainAvailability": "complete"
            if chain_available_count == len(expiration_dates)
            else "partial",
        }

    date_range = None
    if expiration_dates:
        date_range = {"start": expiration_dates[0], "end": expiration_dates[-1]}

    return build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": fixture.get("source") or fixture.get("providerName"),
            "sourceType": "fixture",
            "expirationCalendarStatus": "available" if expiration_dates else "unavailable",
            "asOf": as_of,
            "underlying": fixture.get("symbol"),
            "symbol": fixture.get("symbol"),
            "expirationDates": expiration_dates,
            "expirationCount": len(expiration_dates),
            "expirationTypes": expiration_types,
            "dateRange": date_range,
            "coverageMetadata": coverage_metadata,
            "sandboxOrProduction": "not_provider_sourced",
        }
    )


def _tradier_options_api_token_from_env() -> str | None:
    for env_name in ("TRADIER_API_TOKEN", "TRADIER_SANDBOX_API_TOKEN"):
        value = str(os.environ.get(env_name) or "").strip()
        if value:
            return value
    return None


def _build_tradier_options_live_probe_transport(
    *,
    api_token: str,
    timeout_seconds: float,
) -> TradierOptionsHttpTransport:
    return TradierOptionsHttpTransport(
        api_token=api_token,
        timeout_seconds=timeout_seconds,
    )


def _response_shape_status(endpoint_class: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if endpoint_class == "quote":
        quotes = payload.get("quotes") if isinstance(payload, Mapping) else None
        quote = quotes.get("quote") if isinstance(quotes, Mapping) else None
        if isinstance(quote, list):
            return {"status": "list", "count": len(quote)}
        if isinstance(quote, Mapping):
            return {"status": "object", "count": 1}
        return {"status": "missing", "count": 0}
    if endpoint_class == "expirations":
        expirations = payload.get("expirations") if isinstance(payload, Mapping) else None
        dates = expirations.get("date") if isinstance(expirations, Mapping) else None
        if isinstance(dates, list):
            return {"status": "list", "count": len(dates)}
        if isinstance(dates, str) and dates.strip():
            return {"status": "list", "count": 1}
        return {"status": "missing", "count": 0}
    return {"status": "unknown", "count": 0}


def _normalize_options_probe_expiration(expiration: str | None) -> str | None:
    text = str(expiration or "").strip()
    return text or None


def _first_tradier_expiration_date(payload: Mapping[str, Any]) -> str | None:
    expirations = payload.get("expirations") if isinstance(payload, Mapping) else None
    if isinstance(expirations, Mapping):
        raw_dates = expirations.get("date", expirations.get("expiration"))
    else:
        raw_dates = expirations
    if isinstance(raw_dates, str):
        values = [raw_dates]
    elif isinstance(raw_dates, Mapping):
        values = [raw_dates.get("date", raw_dates.get("expiration"))]
    else:
        values = [
            item.get("date", item.get("expiration")) if isinstance(item, Mapping) else item
            for item in list(raw_dates or [])
        ]
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _present_number(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    try:
        float(text)
    except (TypeError, ValueError):
        return False
    return True


def _first_present_value(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and payload.get(key) is not None:
            return payload.get(key)
    return None


def _tradier_chain_option_rows_for_summary(payload: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], str]:
    if not isinstance(payload, Mapping):
        raise OptionsProviderUnavailable(
            "tradier",
            code="options_provider_payload_unmappable",
            message="Options provider payload could not be mapped safely.",
        )
    raw_options = payload.get("options")
    if raw_options is None:
        return [], "missing"
    if not isinstance(raw_options, Mapping):
        raise OptionsProviderUnavailable(
            "tradier",
            code="options_provider_payload_unmappable",
            message="Options provider payload could not be mapped safely.",
        )
    raw_rows = raw_options.get("option")
    if raw_rows is None:
        return [], "missing"
    if isinstance(raw_rows, Mapping):
        return [raw_rows], "object"
    if isinstance(raw_rows, list):
        if not all(isinstance(item, Mapping) for item in raw_rows):
            raise OptionsProviderUnavailable(
                "tradier",
                code="options_provider_payload_unmappable",
                message="Options provider payload could not be mapped safely.",
            )
        return list(raw_rows), "list"
    raise OptionsProviderUnavailable(
        "tradier",
        code="options_provider_payload_unmappable",
        message="Options provider payload could not be mapped safely.",
    )


def _summarize_tradier_chain_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows, shape_status = _tradier_chain_option_rows_for_summary(payload)
    has_bid_ask_count = 0
    has_open_interest_count = 0
    has_iv_greeks_count = 0
    for row in rows:
        greeks = row.get("greeks") if isinstance(row.get("greeks"), Mapping) else {}
        if _present_number(row.get("bid")) and _present_number(row.get("ask")):
            has_bid_ask_count += 1
        if _present_number(_first_present_value(row, ("open_interest", "openInterest", "openinterest"))):
            has_open_interest_count += 1
        iv_value = _first_present_value(
            row,
            ("implied_volatility", "impliedVolatility", "iv"),
        )
        if iv_value is None and isinstance(greeks, Mapping):
            iv_value = _first_present_value(greeks, ("mid_iv", "smv_vol", "iv", "implied_volatility"))
        has_iv = _present_number(iv_value)
        has_greek = isinstance(greeks, Mapping) and any(
            _present_number(greeks.get(key)) for key in ("delta", "gamma", "theta", "vega", "rho")
        )
        if has_iv and has_greek:
            has_iv_greeks_count += 1
    contract_count = len(rows)
    return {
        "responseShape": {"status": shape_status, "count": contract_count},
        "chainContractCount": contract_count,
        "chainHasBidAsk": has_bid_ask_count > 0,
        "chainHasBidAskCount": has_bid_ask_count,
        "chainHasOpenInterest": has_open_interest_count > 0,
        "chainHasOpenInterestCount": has_open_interest_count,
        "chainHasIvGreeks": has_iv_greeks_count > 0,
        "chainHasIvGreeksCount": has_iv_greeks_count,
    }


def _empty_options_chain_summary() -> dict[str, Any]:
    return {
        "chainContractCount": 0,
        "chainHasBidAsk": False,
        "chainHasBidAskCount": 0,
        "chainHasOpenInterest": False,
        "chainHasOpenInterestCount": 0,
        "chainHasIvGreeks": False,
        "chainHasIvGreeksCount": 0,
    }


def _options_live_probe_result(
    *,
    provider_id: str,
    status: str,
    enabled: bool,
    reason_code: str,
    timeout_seconds: float,
    network_call_executed: bool,
    endpoint_results: list[dict[str, Any]],
    quote_shape_status: str = "unknown",
    expiration_count: int = 0,
    chain_summary: dict[str, Any] | None = None,
    sanitized_error_code: str | None = None,
) -> dict[str, Any]:
    chain_summary = chain_summary or _empty_options_chain_summary()
    return {
        "providerId": provider_id,
        "status": status,
        "enabled": enabled,
        "explicitOptIn": True,
        "reasonCode": reason_code,
        "sanitizedErrorCode": sanitized_error_code,
        "timeoutSeconds": timeout_seconds,
        "networkCallExecuted": network_call_executed,
        "endpointClasses": [
            str(result.get("endpointClass"))
            for result in endpoint_results
            if str(result.get("endpointClass") or "").strip()
        ],
        "endpointResults": endpoint_results,
        "quoteShapeStatus": str(quote_shape_status or "unknown"),
        "expirationCount": _non_negative_int(expiration_count),
        "chainContractCount": _non_negative_int(chain_summary.get("chainContractCount")),
        "chainHasBidAsk": bool(chain_summary.get("chainHasBidAsk", False)),
        "chainHasBidAskCount": _non_negative_int(chain_summary.get("chainHasBidAskCount")),
        "chainHasOpenInterest": bool(chain_summary.get("chainHasOpenInterest", False)),
        "chainHasOpenInterestCount": _non_negative_int(chain_summary.get("chainHasOpenInterestCount")),
        "chainHasIvGreeks": bool(chain_summary.get("chainHasIvGreeks", False)),
        "chainHasIvGreeksCount": _non_negative_int(chain_summary.get("chainHasIvGreeksCount")),
        "rawCredentialValuesIncluded": False,
        "providerPayloadValuesIncluded": False,
        "responseBodiesIncluded": False,
        "brokerOrderPathEnabled": False,
        "portfolioMutationPathEnabled": False,
        "tradeableData": False,
    }


def _blocked_options_live_probe(
    *,
    provider_id: str,
    status: str,
    reason_code: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    return _options_live_probe_result(
        provider_id=provider_id,
        status=status,
        enabled=False,
        reason_code=reason_code,
        sanitized_error_code=reason_code,
        timeout_seconds=timeout_seconds,
        network_call_executed=False,
        endpoint_results=[],
    )


def _failed_options_live_probe(
    *,
    provider_id: str,
    error_code: str,
    timeout_seconds: float,
    network_call_executed: bool,
    endpoint_results: list[dict[str, Any]],
    failed_endpoint_class: str,
    quote_shape_status: str = "unknown",
    expiration_count: int = 0,
    chain_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    endpoint_results.append(
        {
            "endpointClass": failed_endpoint_class,
            "status": "error",
            "responseShape": {"status": "unknown", "count": 0},
        }
    )
    return _options_live_probe_result(
        provider_id=provider_id,
        status="failed_sanitized_provider_error",
        enabled=True,
        reason_code=error_code,
        sanitized_error_code=error_code,
        timeout_seconds=timeout_seconds,
        network_call_executed=network_call_executed,
        endpoint_results=endpoint_results,
        quote_shape_status=quote_shape_status,
        expiration_count=expiration_count,
        chain_summary=chain_summary,
    )


def _run_options_live_probe(
    *,
    provider_id: str,
    config: OptionsLiveProviderConfig,
    symbol: str,
    probe_chain: bool = False,
    probe_expiration: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    normalized_provider = str(provider_id or "").strip().lower()
    bounded_timeout = _bounded_options_probe_timeout_seconds(
        timeout_seconds if timeout_seconds is not None else config.live_probe_timeout_seconds
    )
    if normalized_provider != _OPTIONS_LIVE_PROBE_PROVIDER:
        return _blocked_options_live_probe(
            provider_id=normalized_provider or "unknown",
            status="blocked_unsupported_provider",
            reason_code="options_provider_live_probe_unsupported_provider",
            timeout_seconds=bounded_timeout,
        )

    credential_state = config.credential_state(normalized_provider)
    if credential_state != "present":
        reason_code = {
            "malformed": "options_provider_credentials_malformed",
            "partial": "options_provider_credentials_partial",
        }.get(credential_state, "options_provider_credentials_missing")
        status = {
            "malformed": "blocked_malformed_credentials",
            "partial": "blocked_partial_credentials",
        }.get(credential_state, "blocked_missing_credentials")
        return _blocked_options_live_probe(
            provider_id=normalized_provider,
            status=status,
            reason_code=reason_code,
            timeout_seconds=bounded_timeout,
        )

    api_token = _tradier_options_api_token_from_env()
    if not api_token:
        return _blocked_options_live_probe(
            provider_id=normalized_provider,
            status="blocked_missing_credentials",
            reason_code="options_provider_credentials_missing",
            timeout_seconds=bounded_timeout,
        )

    endpoint_results: list[dict[str, Any]] = []
    network_call_executed = False
    current_endpoint_class = _OPTIONS_LIVE_PROBE_ENDPOINT_CLASSES[0]
    quote_shape_status = "unknown"
    expiration_count = 0
    chain_summary = _empty_options_chain_summary()
    try:
        transport = _build_tradier_options_live_probe_transport(
            api_token=api_token,
            timeout_seconds=bounded_timeout,
        )
        normalized_symbol = _normalize_options_probe_symbol(symbol)
        current_endpoint_class = "quote"
        network_call_executed = True
        quote_payload = transport.get_quote(normalized_symbol)
        quote_shape = _response_shape_status("quote", quote_payload)
        quote_shape_status = str(quote_shape.get("status") or "unknown")
        endpoint_results.append(
            {
                "endpointClass": "quote",
                "status": "ok",
                "responseShape": quote_shape,
            }
        )
        current_endpoint_class = "expirations"
        network_call_executed = True
        expirations_payload = transport.get_expirations(normalized_symbol)
        expirations_shape = _response_shape_status("expirations", expirations_payload)
        expiration_count = _non_negative_int(expirations_shape.get("count"))
        endpoint_results.append(
            {
                "endpointClass": "expirations",
                "status": "ok",
                "responseShape": expirations_shape,
            }
        )
        if probe_chain:
            current_endpoint_class = _OPTIONS_CHAIN_PROBE_ENDPOINT_CLASS
            expiration = _normalize_options_probe_expiration(probe_expiration) or _first_tradier_expiration_date(
                expirations_payload
            )
            if not expiration:
                raise OptionsProviderUnavailable(
                    "tradier",
                    code="options_provider_probe_expiration_missing",
                    message="Options provider chain probe expiration is missing.",
                )
            network_call_executed = True
            chain_payload = transport.get_chain(normalized_symbol, expiration=expiration)
            chain_summary = _summarize_tradier_chain_payload(chain_payload)
            endpoint_results.append(
                {
                    "endpointClass": _OPTIONS_CHAIN_PROBE_ENDPOINT_CLASS,
                    "status": "ok",
                    "responseShape": chain_summary["responseShape"],
                }
            )
    except OptionsProviderUnavailable as exc:
        error_code = _sanitize_reason_code(exc.code) or "options_provider_error"
        return _failed_options_live_probe(
            provider_id=normalized_provider,
            error_code=error_code,
            timeout_seconds=bounded_timeout,
            network_call_executed=network_call_executed,
            endpoint_results=endpoint_results,
            failed_endpoint_class=current_endpoint_class,
            quote_shape_status=quote_shape_status,
            expiration_count=expiration_count,
            chain_summary=chain_summary,
        )
    except OptionsProviderError as exc:
        error_code = _sanitize_reason_code(exc.code) or "options_provider_error"
        return _failed_options_live_probe(
            provider_id=normalized_provider,
            error_code=error_code,
            timeout_seconds=bounded_timeout,
            network_call_executed=network_call_executed,
            endpoint_results=endpoint_results,
            failed_endpoint_class=current_endpoint_class,
            quote_shape_status=quote_shape_status,
            expiration_count=expiration_count,
            chain_summary=chain_summary,
        )
    except Exception:
        return _failed_options_live_probe(
            provider_id=normalized_provider,
            error_code="unexpected_error",
            timeout_seconds=bounded_timeout,
            network_call_executed=network_call_executed,
            endpoint_results=endpoint_results,
            failed_endpoint_class=current_endpoint_class,
            quote_shape_status=quote_shape_status,
            expiration_count=expiration_count,
            chain_summary=chain_summary,
        )

    return _options_live_probe_result(
        provider_id=normalized_provider,
        status="passed",
        enabled=True,
        reason_code="options_provider_live_probe_passed",
        sanitized_error_code=None,
        timeout_seconds=bounded_timeout,
        network_call_executed=network_call_executed,
        endpoint_results=endpoint_results,
        quote_shape_status=quote_shape_status,
        expiration_count=expiration_count,
        chain_summary=chain_summary,
    )


def _collect_options_lab_provider_preflight(
    *,
    options_live_probe: bool = False,
    options_provider: str = _OPTIONS_LIVE_PROBE_PROVIDER,
    options_probe_symbol: str = "TEM",
    options_probe_chain: bool = False,
    options_probe_expiration: str | None = None,
    options_probe_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    config = OptionsLiveProviderConfig.from_env()
    providers: list[dict[str, Any]] = []
    normalized_options_provider = str(options_provider or _OPTIONS_LIVE_PROBE_PROVIDER).strip().lower()
    for provider_name in sorted(LIVE_OPTIONS_PROVIDER_NAMES):
        try:
            preflight = build_options_provider_live_readiness_preflight(provider_name, config=config)
        except Exception:
            preflight = {
                "providerName": provider_name,
                "readinessState": "unexpected_error",
                "credentialsPresent": False,
                "credentialContract": {
                    "requiredCredentialCount": 1,
                    "configuredCredentialCount": 0,
                    "invalidCredentialCount": 0,
                    "partialCredentialCount": 0,
                },
                "dryRunEnabled": False,
                "liveHttpCallsEnabled": False,
                "brokerOrderPathEnabled": False,
                "portfolioMutationPathEnabled": False,
                "tradeableData": False,
                "liveProbe": {
                    "enabled": False,
                    "explicitOptIn": False,
                    "reasonCode": "unexpected_error",
                    "timeoutSeconds": 0.0,
                    "networkCallExecuted": False,
                },
            }
        compact = _compact_options_lab_provider_preflight(preflight)
        if options_live_probe and provider_name == normalized_options_provider:
            compact["liveProbe"].update(
                _run_options_live_probe(
                    provider_id=normalized_options_provider,
                    config=config,
                    symbol=options_probe_symbol,
                    probe_chain=options_probe_chain,
                    probe_expiration=options_probe_expiration,
                    timeout_seconds=options_probe_timeout_seconds,
                )
            )
        providers.append(compact)
    return {"providers": providers}


def _collect_polygon_us_breadth_diagnostic() -> dict[str, Any]:
    try:
        return _compact_polygon_us_breadth_diagnostic(
            polygon_us_breadth_diagnostic_summary(run_polygon_us_breadth_activation())
        )
    except Exception:
        return _compact_polygon_us_breadth_diagnostic(
            {
                "credentialsPresent": bool(str(os.getenv("POLYGON_API_KEY") or "").strip()),
                "probePassed": False,
                "observationDate": None,
                "freshnessValid": False,
                "coverageCount": 0,
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": False,
                "fulfilledMetrics": [],
                "missingMetrics": list(US_BREADTH_SYMBOLS),
                "reasonCodes": ["unexpected_error"],
            }
        )


def _normalize_request_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(str(base_url).strip())
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or parsed.path
    path = "" if parsed.netloc else ""
    return urllib.parse.urlunsplit((scheme, netloc, path.rstrip("/"), "", ""))


def _sanitize_base_url_display(base_url: str) -> str:
    normalized = _normalize_request_base_url(base_url)
    parsed = urllib.parse.urlsplit(normalized)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _fetch_json(base_url: str, path: str, timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    url = f"{_normalize_request_base_url(base_url).rstrip('/')}{path}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=max(float(timeout_seconds), 0.1)) as response:
        status_code = int(getattr(response, "status", 200) or 200)
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("endpoint payload must be a JSON object")
    return status_code, payload


def _item_has_value(item: Any) -> bool:
    return isinstance(item, dict) and item.get("value") is not None and not bool(item.get("isUnavailable"))


def _summarize_market_overview_macro(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    available_item_count = sum(1 for item in items if _item_has_value(item))
    provider_status = str(dict(payload.get("providerHealth") or {}).get("status") or "unknown")
    return {
        "available": available_item_count > 0 and provider_status != "unavailable",
        "providerHealthStatus": provider_status,
        "freshness": str(payload.get("freshness") or "unknown"),
        "availableItemCount": available_item_count,
        "unavailableItemCount": max(0, len(items) - available_item_count),
    }


def _summarize_liquidity_monitor(payload: dict[str, Any]) -> dict[str, Any]:
    score = dict(payload.get("score") or {})
    indicators = payload.get("indicators") if isinstance(payload.get("indicators"), list) else []
    included_indicator_count = int(score.get("includedIndicatorCount") or 0)
    score_regime = str(score.get("regime") or "unknown")
    unavailable_indicator_count = sum(
        1
        for indicator in indicators
        if bool(dict(indicator.get("evidence") or {}).get("isUnavailable"))
    )
    available = score_regime != "unavailable" and included_indicator_count > 0
    return {
        "available": available,
        "scoreRegime": score_regime,
        "includedIndicatorCount": included_indicator_count,
        "indicatorCount": len(indicators),
        "unavailableIndicatorCount": unavailable_indicator_count,
        "freshnessStatus": str(dict(payload.get("freshness") or {}).get("status") or "unknown"),
    }


def _summarize_us_breadth(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    provider_status = str(dict(payload.get("providerHealth") or {}).get("status") or "unknown")
    source_authority_allowed = bool(payload.get("sourceAuthorityAllowed", False))
    score_contribution_allowed = bool(payload.get("scoreContributionAllowed", False))
    return {
        "available": bool(source_authority_allowed and score_contribution_allowed),
        "providerHealthStatus": provider_status,
        "freshness": str(payload.get("freshness") or "unknown"),
        "breadthClaimType": str(payload.get("breadthClaimType") or "unknown"),
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "sourceAuthorityReason": _sanitize_reason(payload.get("sourceAuthorityReason")),
        "itemCount": len(items),
    }


def _summarize_rotation_radar(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(payload.get("metadata") or {})
    quote_provider = dict(metadata.get("quoteProvider") or {})
    summary = dict(payload.get("summary") or {})
    headline_eligible_theme_count = int(summary.get("headlineEligibleThemeCount") or 0)
    quote_provider_status = str(quote_provider.get("status") or "unknown")
    return {
        "available": quote_provider_status == "success" or headline_eligible_theme_count > 0,
        "quoteProviderPresent": bool(quote_provider.get("present", False)),
        "quoteProviderStatus": quote_provider_status,
        "freshness": str(payload.get("freshness") or "unknown"),
        "headlineEligibleThemeCount": headline_eligible_theme_count,
        "observationThemeCount": int(summary.get("observationThemeCount") or 0),
    }


def _summarize_market_temperature(payload: dict[str, Any]) -> dict[str, Any]:
    provider_status = str(dict(payload.get("providerHealth") or {}).get("status") or "unknown")
    disabled_reason = _sanitize_reason(payload.get("disabledReason"))
    return {
        "available": bool(payload.get("temperatureAvailable", False)),
        "temperatureAvailable": bool(payload.get("temperatureAvailable", False)),
        "disabledReason": disabled_reason if payload.get("disabledReason") is not None else None,
        "providerHealthStatus": provider_status,
    }


def _summarize_data_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    failing_check_count = sum(
        1 for check in checks if str(dict(check).get("status") or "unknown") in {"missing", "misconfigured"}
    )
    readiness_status = str(payload.get("readinessStatus") or "unknown")
    return {
        "available": readiness_status in {"ready", "partial"},
        "readinessStatus": readiness_status,
        "failingCheckCount": failing_check_count,
        "checkCount": len(checks),
    }


_ENDPOINT_SUMMARIZERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "marketOverviewMacro": _summarize_market_overview_macro,
    "usBreadth": _summarize_us_breadth,
    "liquidityMonitor": _summarize_liquidity_monitor,
    "rotationRadar": _summarize_rotation_radar,
    "marketTemperature": _summarize_market_temperature,
    "dataReadiness": _summarize_data_readiness,
}


def _build_discrepancies(
    official_macro_diagnostic: dict[str, Any],
    alpaca_rotation_diagnostic: dict[str, Any],
    runtime_readiness: dict[str, Any],
) -> list[dict[str, str]]:
    discrepancies: list[dict[str, str]] = []
    if official_macro_diagnostic.get("probePassed") and runtime_readiness.get("marketOverviewMacro", {}).get("available") is False:
        discrepancies.append(
            {
                "code": "diagnostic_pass_runtime_unavailable",
                "diagnostic": "officialMacroDiagnostic",
                "runtimeSurface": "marketOverviewMacro",
            }
        )
    if alpaca_rotation_diagnostic.get("probePassed") and runtime_readiness.get("rotationRadar", {}).get("available") is False:
        discrepancies.append(
            {
                "code": "diagnostic_pass_runtime_unavailable",
                "diagnostic": "alpacaRotationDiagnostic",
                "runtimeSurface": "rotationRadar",
            }
        )
    return discrepancies


def collect_diagnostic_bundle(
    *,
    base_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    include_live_smoke: bool = False,
    options_live_probe: bool = False,
    options_provider: str = _OPTIONS_LIVE_PROBE_PROVIDER,
    options_probe_symbol: str = "TEM",
    options_probe_chain: bool = False,
    options_probe_expiration: str | None = None,
    options_probe_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    if include_live_smoke:
        official_macro_diagnostic = _compact_official_macro_diagnostic(run_official_macro_live_smoke())
        alpaca_rotation_diagnostic = _compact_alpaca_rotation_diagnostic(
            run_rotation_radar_alpaca_live_smoke()
        )
        polygon_us_breadth_diagnostic = _collect_polygon_us_breadth_diagnostic()
    else:
        official_macro_diagnostic = _skipped_official_macro_diagnostic()
        alpaca_rotation_diagnostic = _skipped_alpaca_rotation_diagnostic()
        polygon_us_breadth_diagnostic = _skipped_polygon_us_breadth_diagnostic()
    options_iv_rank_authority = _collect_options_iv_rank_authority()
    options_event_calendar_authority = _collect_options_event_calendar_authority()
    options_expiration_calendar_authority = _collect_options_expiration_calendar_authority()
    result: dict[str, Any] = {
        "officialMacroDiagnostic": official_macro_diagnostic,
        "alpacaRotationDiagnostic": alpaca_rotation_diagnostic,
        "polygonUsBreadthDiagnostic": polygon_us_breadth_diagnostic,
        "optionsLabProviderPreflight": _collect_options_lab_provider_preflight(
            options_live_probe=options_live_probe,
            options_provider=options_provider,
            options_probe_symbol=options_probe_symbol,
            options_probe_chain=options_probe_chain,
            options_probe_expiration=options_probe_expiration,
            options_probe_timeout_seconds=options_probe_timeout_seconds,
        ),
        "optionsAuthorityDiagnostics": _collect_options_authority_diagnostics(
            options_iv_rank_authority,
            options_event_calendar_authority,
            options_expiration_calendar_authority,
        ),
        "optionsIvRankAuthority": options_iv_rank_authority,
        "optionsEventCalendarAuthority": options_event_calendar_authority,
        "optionsExpirationCalendarAuthority": options_expiration_calendar_authority,
        "usBreadthAuthorityDiagnostic": build_us_breadth_missing_authority_diagnostic(),
        "discrepancies": [],
    }

    if not base_url:
        return result

    endpoint_reachability: dict[str, Any] = {
        "baseUrl": _sanitize_base_url_display(base_url),
        "endpoints": [],
    }
    runtime_readiness: dict[str, Any] = {}

    for endpoint_id, path in _ENDPOINTS:
        try:
            status_code, payload = _fetch_json(base_url, path, timeout_seconds)
        except urllib.error.HTTPError as exc:
            endpoint_reachability["endpoints"].append(
                {
                    "id": endpoint_id,
                    "path": path,
                    "ok": False,
                    "statusCode": int(exc.code),
                    "errorType": type(exc).__name__,
                }
            )
            continue
        except Exception as exc:
            endpoint_reachability["endpoints"].append(
                {
                    "id": endpoint_id,
                    "path": path,
                    "ok": False,
                    "errorType": type(exc).__name__,
                }
            )
            continue

        endpoint_reachability["endpoints"].append(
            {
                "id": endpoint_id,
                "path": path,
                "ok": True,
                "statusCode": status_code,
            }
        )
        runtime_readiness[endpoint_id] = _ENDPOINT_SUMMARIZERS[endpoint_id](payload)

    reachable_count = sum(1 for endpoint in endpoint_reachability["endpoints"] if endpoint.get("ok"))
    endpoint_reachability["reachableCount"] = reachable_count
    endpoint_reachability["unreachableCount"] = len(endpoint_reachability["endpoints"]) - reachable_count
    result["endpointReachability"] = endpoint_reachability
    if runtime_readiness:
        result["runtimeReadiness"] = runtime_readiness
        result["discrepancies"] = _build_discrepancies(
            official_macro_diagnostic,
            alpaca_rotation_diagnostic,
            runtime_readiness,
        )
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get(BASE_URL_ENV_VAR),
        help=f"Optional local backend base URL. Defaults to ${BASE_URL_ENV_VAR} when set.",
    )
    parser.add_argument(
        "--live-smoke",
        action="store_true",
        help="Opt in to live provider smoke diagnostics. Default mode stays offline/safe.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-endpoint timeout when querying the optional local backend.",
    )
    parser.add_argument(
        "--options-live-probe",
        action="store_true",
        help="Explicitly run the opt-in Options market-data live probe. Default mode stays offline.",
    )
    parser.add_argument(
        "--options-provider",
        choices=(_OPTIONS_LIVE_PROBE_PROVIDER,),
        default=_OPTIONS_LIVE_PROBE_PROVIDER,
        help="Options provider for --options-live-probe. Initial diagnostic support is Tradier only.",
    )
    parser.add_argument(
        "--options-probe-symbol",
        default="TEM",
        help="US equity symbol for the bounded Options live probe. Defaults to TEM.",
    )
    parser.add_argument(
        "--options-probe-chain",
        action="store_true",
        help="Explicitly include one bounded Tradier option-chain endpoint call in the Options live probe.",
    )
    parser.add_argument(
        "--options-probe-expiration",
        default=None,
        help="Optional explicit expiration for --options-probe-chain. Defaults to the first probed expiration.",
    )
    parser.add_argument(
        "--options-live-probe-timeout-seconds",
        type=float,
        default=None,
        help="Optional bounded timeout for the Options live probe. Defaults to existing Options env convention.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = collect_diagnostic_bundle(
            base_url=args.base_url,
            timeout_seconds=args.timeout_seconds,
            include_live_smoke=args.live_smoke,
            options_live_probe=args.options_live_probe,
            options_provider=args.options_provider,
            options_probe_symbol=args.options_probe_symbol,
            options_probe_chain=args.options_probe_chain,
            options_probe_expiration=args.options_probe_expiration,
            options_probe_timeout_seconds=args.options_live_probe_timeout_seconds,
        )
    except Exception:
        options_iv_rank_authority = _collect_options_iv_rank_authority()
        options_event_calendar_authority = _collect_options_event_calendar_authority()
        options_expiration_calendar_authority = _collect_options_expiration_calendar_authority()
        fallback = {
            "officialMacroDiagnostic": _skipped_official_macro_diagnostic("unexpected_error"),
            "alpacaRotationDiagnostic": _skipped_alpaca_rotation_diagnostic("unexpected_error"),
            "polygonUsBreadthDiagnostic": _skipped_polygon_us_breadth_diagnostic("unexpected_error"),
            "optionsLabProviderPreflight": _collect_options_lab_provider_preflight(),
            "optionsAuthorityDiagnostics": _collect_options_authority_diagnostics(
                options_iv_rank_authority,
                options_event_calendar_authority,
                options_expiration_calendar_authority,
            ),
            "optionsIvRankAuthority": options_iv_rank_authority,
            "optionsEventCalendarAuthority": options_event_calendar_authority,
            "optionsExpirationCalendarAuthority": options_expiration_calendar_authority,
            "usBreadthAuthorityDiagnostic": build_us_breadth_missing_authority_diagnostic(),
            "discrepancies": [],
        }
        print(json.dumps(fallback, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
