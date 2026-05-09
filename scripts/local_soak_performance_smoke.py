#!/usr/bin/env python3
"""Local soak performance smoke.

Safe default behavior is offline route inspection only. HTTP timing probes run
only when both --base-url and --allow-network are provided, and only use
read-only GET routes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.staging_integration_smoke import (
    DEFAULT_TIMEOUT_SECONDS,
    EXIT_FAILED,
    EXIT_OK,
    HttpProbeResult,
    _clean_base_url,
    _write_json,
    load_route_inventory,
    safe_http_get,
)


SLOW_WARN_MS = 1000.0
SMOKE_VERSION = "local-soak-performance-v1"


@dataclass(frozen=True)
class RouteProbe:
    id: str
    method: str
    path: str
    label: str
    may_call_live_providers: bool = False
    session_context_required: bool = False


ROUTES: tuple[RouteProbe, ...] = (
    RouteProbe("public_health", "GET", "/api/health", "Public API readiness"),
    RouteProbe("auth_status", "GET", "/api/v1/auth/status", "Auth status contract"),
    RouteProbe(
        "market_overview_indices",
        "GET",
        "/api/v1/market-overview/indices",
        "Market overview indices",
        may_call_live_providers=True,
    ),
    RouteProbe(
        "market_overview_volatility",
        "GET",
        "/api/v1/market-overview/volatility",
        "Market overview volatility",
        may_call_live_providers=True,
    ),
    RouteProbe(
        "market_overview_macro",
        "GET",
        "/api/v1/market-overview/macro",
        "Market overview macro",
        may_call_live_providers=True,
    ),
    RouteProbe(
        "market_overview_sentiment",
        "GET",
        "/api/v1/market-overview/sentiment",
        "Market overview sentiment",
        may_call_live_providers=True,
    ),
    RouteProbe("scanner_themes", "GET", "/api/v1/scanner/themes", "Scanner theme universe"),
)


def classify_http_probe(result: HttpProbeResult, *, elapsed_ms: float) -> tuple[str, bool, str]:
    """Classify a sanitized HTTP result without using response bodies."""
    status_code = result.status_code
    reason_code = result.reason_code or "unknown"
    if status_code is None:
        return "fail", True, reason_code or "no_http_response"
    if status_code in {401, 403}:
        return "manual-review-required", True, "auth_required"
    if status_code == 404:
        return "fail", False, "route_missing"
    if status_code >= 500:
        return "fail", True, reason_code
    if 200 <= status_code < 300:
        if elapsed_ms > SLOW_WARN_MS:
            return "warn", False, "slow_response"
        return "pass", False, "ok"
    if status_code == 429:
        return "warn", True, "rate_limited"
    return "warn", True, reason_code


def _offline_classification(*, route_registered: bool, allow_network: bool, base_url: str | None) -> tuple[str, bool, str]:
    if not route_registered:
        return "fail", False, "route_missing"
    if allow_network and not base_url:
        return "manual-review-required", True, "base_url_required"
    if base_url and not allow_network:
        return "manual-review-required", True, "network_opt_in_required"
    return "manual-review-required", True, "network_not_enabled"


def _smoke_status(results: Iterable[dict[str, Any]]) -> str:
    routes = list(results)
    if any(route.get("classification") == "fail" for route in routes):
        return "fail"
    if any(route.get("classification") == "warn" for route in routes):
        return "warn"
    if any(route.get("manualReviewRequired") for route in routes):
        return "manual-review-required"
    return "pass"


def _measure_route(
    route: RouteProbe,
    *,
    routes_registered: set[tuple[str, str]],
    base_url: str | None,
    allow_network: bool,
    timeout: float,
) -> dict[str, Any]:
    route_registered = (route.method, route.path) in routes_registered
    started = time.perf_counter()
    network_executed = False
    status_code: int | None = None
    provider_call_allowed = bool(allow_network and base_url)

    if route_registered and provider_call_allowed:
        probe = safe_http_get(str(base_url), route.path, timeout)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        network_executed = True
        status_code = probe.status_code
        classification, manual_review, reason_code = classify_http_probe(probe, elapsed_ms=elapsed_ms)
    else:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        classification, manual_review, reason_code = _offline_classification(
            route_registered=route_registered,
            allow_network=allow_network,
            base_url=base_url,
        )

    if route.session_context_required and classification != "fail":
        manual_review = True
        if classification == "pass":
            classification = "manual-review-required"

    return {
        "id": route.id,
        "label": route.label,
        "method": route.method,
        "path": route.path,
        "routeRegistered": route_registered,
        "mayCallLiveProviders": route.may_call_live_providers,
        "statusCode": status_code,
        "elapsed_ms": elapsed_ms,
        "classification": classification,
        "reasonCode": reason_code,
        "manualReviewRequired": manual_review,
        "networkCallsExecuted": network_executed,
        "destructiveWritesExecuted": False,
    }


def run_smoke(
    *,
    base_url: str | None = None,
    allow_network: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout_must_be_positive")
    cleaned_base_url = _clean_base_url(base_url) if base_url else None
    route_inventory = load_route_inventory()
    routes = [
        _measure_route(
            route,
            routes_registered=route_inventory,
            base_url=cleaned_base_url,
            allow_network=allow_network,
            timeout=timeout,
        )
        for route in ROUTES
    ]
    network_calls = any(route["networkCallsExecuted"] for route in routes)
    manual_review = [route["id"] for route in routes if route["manualReviewRequired"]]
    return {
        "tool": SMOKE_VERSION,
        "smokeStatus": _smoke_status(routes),
        "routes": routes,
        "routeCount": len(routes),
        "timeoutSeconds": timeout,
        "networkProbeRequested": bool(cleaned_base_url),
        "allowNetwork": bool(allow_network),
        "networkCallsExecuted": network_calls,
        "destructiveWritesExecuted": False,
        "liveProviderCallsAllowed": bool(allow_network),
        "manualReviewRequired": manual_review,
        "safety": {
            "httpMethods": ["GET"],
            "rawResponseBodiesCaptured": False,
            "authenticatedUnsafePostExecuted": False,
            "portfolioWatchlistSettingsAdminMutated": False,
            "notificationsSent": False,
            "aiLiveCallsExecutedByScript": False,
            "releaseApproved": False,
            "productionRuntimeBehaviorChanged": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Local backend URL. HTTP probes require this and --allow-network.")
    parser.add_argument("--allow-network", action="store_true", help="Opt in to bounded read-only HTTP GET probes.")
    parser.add_argument("--json-output", type=Path, help="Optional path to write the JSON summary.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP probe timeout in seconds.")
    args = parser.parse_args(argv)

    try:
        summary = run_smoke(
            base_url=args.base_url,
            allow_network=args.allow_network,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return EXIT_FAILED

    if args.json_output:
        _write_json(summary, args.json_output)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_FAILED if summary["smokeStatus"] == "fail" else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
