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
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.official_macro_transport import run_official_macro_live_smoke
from src.services.options_market_data_provider import (
    LIVE_OPTIONS_PROVIDER_NAMES,
    OptionsLiveProviderConfig,
    build_options_provider_live_readiness_preflight,
)
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


def _collect_options_lab_provider_preflight() -> dict[str, Any]:
    config = OptionsLiveProviderConfig.from_env()
    providers: list[dict[str, Any]] = []
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
        providers.append(_compact_options_lab_provider_preflight(preflight))
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
    result: dict[str, Any] = {
        "officialMacroDiagnostic": official_macro_diagnostic,
        "alpacaRotationDiagnostic": alpaca_rotation_diagnostic,
        "polygonUsBreadthDiagnostic": polygon_us_breadth_diagnostic,
        "optionsLabProviderPreflight": _collect_options_lab_provider_preflight(),
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = collect_diagnostic_bundle(
            base_url=args.base_url,
            timeout_seconds=args.timeout_seconds,
            include_live_smoke=args.live_smoke,
        )
    except Exception:
        fallback = {
            "officialMacroDiagnostic": _skipped_official_macro_diagnostic("unexpected_error"),
            "alpacaRotationDiagnostic": _skipped_alpaca_rotation_diagnostic("unexpected_error"),
            "polygonUsBreadthDiagnostic": _skipped_polygon_us_breadth_diagnostic("unexpected_error"),
            "optionsLabProviderPreflight": _collect_options_lab_provider_preflight(),
            "usBreadthAuthorityDiagnostic": build_us_breadth_missing_authority_diagnostic(),
            "discrepancies": [],
        }
        print(json.dumps(fallback, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
