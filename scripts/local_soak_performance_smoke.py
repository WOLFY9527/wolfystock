#!/usr/bin/env python3
"""Local soak performance smoke.

Safe default behavior is offline route inspection only. HTTP timing probes run
only when both --base-url and --allow-network are provided, and only use
read-only GET routes.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
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
    MAX_BODY_BYTES,
    _clean_base_url,
    _join_url,
    _write_json,
    load_route_inventory,
    safe_http_get,
)


SLOW_WARN_MS = 1000.0
SLOW_FAIL_MS = 5000.0
SMOKE_VERSION = "local-soak-performance-v1"
AUTH_USERNAME_ENV = "WOLFYSTOCK_TEST_USERNAME"
AUTH_PASSWORD_ENV = "WOLFYSTOCK_TEST_PASSWORD"


@dataclass(frozen=True)
class RouteProbe:
    id: str
    method: str
    path: str
    label: str
    may_call_live_providers: bool = False
    session_context_required: bool = False
    capability_review_required: bool = False


@dataclass(frozen=True)
class AuthLoginResult:
    status_code: int | None
    reason_code: str
    succeeded: bool
    session: Any
    username_label: str | None = None
    role: str | None = None


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


AUTHENTICATED_ROUTES: tuple[RouteProbe, ...] = (
    *ROUTES,
    RouteProbe(
        "admin_logs_storage_summary",
        "GET",
        "/api/v1/admin/logs/storage/summary",
        "Admin logs storage summary",
        session_context_required=True,
        capability_review_required=True,
    ),
    RouteProbe(
        "admin_cost_duplicate_summary",
        "GET",
        "/api/v1/admin/cost/duplicate-summary",
        "Admin cost duplicate summary",
        session_context_required=True,
        capability_review_required=True,
    ),
    RouteProbe(
        "admin_provider_circuits",
        "GET",
        "/api/v1/admin/providers/circuits",
        "Admin provider circuits",
        session_context_required=True,
        capability_review_required=True,
    ),
    RouteProbe(
        "admin_market_provider_operations",
        "GET",
        "/api/v1/admin/market-providers/operations",
        "Admin market provider operations",
        session_context_required=True,
        capability_review_required=True,
    ),
)


def _safe_username_label(username: str | None) -> str | None:
    normalized = str(username or "").strip()
    if not normalized:
        return None
    if normalized.lower() == "admin":
        return "admin"
    return "redacted"


def _json_field(payload: Any, key: str) -> Any:
    if not isinstance(payload, dict):
        return None
    return payload.get(key)


def _bounded_json_from_bytes(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        parsed = json.loads(body[:MAX_BODY_BYTES].decode("utf-8", errors="ignore"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _reason_from_auth_body(status_code: int, body: bytes) -> str:
    payload = _bounded_json_from_bytes(body)
    error = str(payload.get("error") or payload.get("detail") or "").strip()
    if error:
        return error[:80]
    if status_code in {401, 403}:
        return "invalid_login"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "unexpected_server_error"
    return "auth_failed"


def safe_auth_login(*, base_url: str, username: str, password: str, timeout: float) -> AuthLoginResult:
    """Execute the single allowed unsafe request and keep only sanitized auth metadata."""
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    body = json.dumps({"username": username, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        _join_url(base_url, "/api/v1/auth/login"),
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "wolfystock-local-soak-performance-smoke/1",
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            response_body = response.read(MAX_BODY_BYTES)
            payload = _bounded_json_from_bytes(response_body)
            current_user = _json_field(payload, "currentUser")
            role = _json_field(current_user, "role")
            return AuthLoginResult(
                status_code=int(response.status),
                reason_code="ok",
                succeeded=200 <= int(response.status) < 300,
                session=opener,
                username_label=_safe_username_label(username),
                role=str(role) if role else None,
            )
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read(MAX_BODY_BYTES)
        return AuthLoginResult(
            status_code=int(exc.code),
            reason_code=_reason_from_auth_body(int(exc.code), body_bytes),
            succeeded=False,
            session=None,
            username_label=_safe_username_label(username),
            role=None,
        )
    except TimeoutError:
        return AuthLoginResult(
            status_code=None,
            reason_code="dependency_unavailable",
            succeeded=False,
            session=None,
            username_label=_safe_username_label(username),
            role=None,
        )
    except OSError:
        return AuthLoginResult(
            status_code=None,
            reason_code="dependency_unavailable",
            succeeded=False,
            session=None,
            username_label=_safe_username_label(username),
            role=None,
        )


def safe_session_get(session: Any, base_url: str, path: str, timeout: float) -> HttpProbeResult:
    """Execute a bounded authenticated GET and return only sanitized status metadata."""
    request = urllib.request.Request(
        _join_url(base_url, path),
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "wolfystock-local-soak-performance-smoke/1"},
    )
    try:
        with session.open(request, timeout=timeout) as response:
            response.read(MAX_BODY_BYTES)
            return HttpProbeResult(status_code=int(response.status), reason_code="ok")
    except urllib.error.HTTPError as exc:
        exc.read(MAX_BODY_BYTES)
        status_code = int(exc.code)
        if status_code in {401, 403}:
            reason_code = "auth_required"
        elif status_code == 404:
            reason_code = "route_missing"
        elif status_code >= 500:
            reason_code = "unexpected_server_error"
        else:
            reason_code = "http_error"
        return HttpProbeResult(status_code=status_code, reason_code=reason_code)
    except TimeoutError:
        return HttpProbeResult(status_code=None, reason_code="timeout")
    except OSError:
        return HttpProbeResult(status_code=None, reason_code="dependency_unavailable")


def classify_http_probe(result: HttpProbeResult, *, elapsed_ms: float, warn_ms: float = SLOW_WARN_MS) -> tuple[str, bool, str]:
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
        if elapsed_ms > warn_ms:
            return "warn", False, "slow_response"
        return "pass", False, "ok"
    if status_code == 429:
        return "warn", True, "rate_limited"
    return "warn", True, reason_code


def classify_authenticated_probe(
    result: HttpProbeResult,
    *,
    elapsed_ms: float,
    route: RouteProbe,
    warn_ms: float,
    fail_ms: float,
) -> tuple[str, bool, str]:
    status_code = result.status_code
    reason_code = result.reason_code or "unknown"
    if status_code is None:
        return "fail", True, reason_code or "timeout"
    if elapsed_ms >= fail_ms:
        return "fail", True, "timeout_or_fail_threshold"
    if status_code == 404:
        return "fail", False, "route_missing"
    if status_code >= 500:
        return "fail", True, reason_code
    if status_code == 401:
        return "fail", True, "unexpected_auth_required"
    if status_code == 403:
        if route.capability_review_required:
            return "warn", True, "capability_limited"
        return "fail", True, "unexpected_forbidden"
    if 200 <= status_code < 300:
        if elapsed_ms > warn_ms:
            return "warn", route.may_call_live_providers or route.capability_review_required, "slow_response"
        if route.may_call_live_providers:
            return "manual-review-required", True, "live_provider_route_review"
        return "pass", route.capability_review_required, "ok"
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


def _validate_authenticated_routes(routes: Iterable[RouteProbe]) -> None:
    if any(route.method != "GET" for route in routes):
        raise ValueError("unsafe_authenticated_route_method")


def _measure_route(
    route: RouteProbe,
    *,
    routes_registered: set[tuple[str, str]],
    base_url: str | None,
    allow_network: bool,
    timeout: float,
    warn_ms: float = SLOW_WARN_MS,
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
        classification, manual_review, reason_code = classify_http_probe(probe, elapsed_ms=elapsed_ms, warn_ms=warn_ms)
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


def _unprobed_route_result(
    route: RouteProbe,
    *,
    routes_registered: set[tuple[str, str]],
    reason_code: str,
    classification: str = "fail",
) -> dict[str, Any]:
    return {
        "id": route.id,
        "label": route.label,
        "method": route.method,
        "path": route.path,
        "routeRegistered": (route.method, route.path) in routes_registered,
        "mayCallLiveProviders": route.may_call_live_providers,
        "statusCode": None,
        "elapsed_ms": 0.0,
        "classification": classification,
        "reasonCode": reason_code,
        "manualReviewRequired": True,
        "networkCallsExecuted": False,
        "destructiveWritesExecuted": False,
    }


def _measure_authenticated_route(
    route: RouteProbe,
    *,
    routes_registered: set[tuple[str, str]],
    base_url: str,
    session: Any,
    timeout: float,
    warn_ms: float,
    fail_ms: float,
) -> dict[str, Any]:
    route_registered = (route.method, route.path) in routes_registered
    if not route_registered:
        return _unprobed_route_result(route, routes_registered=routes_registered, reason_code="route_missing")

    started = time.perf_counter()
    probe = safe_session_get(session, base_url, route.path, timeout)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    classification, manual_review, reason_code = classify_authenticated_probe(
        probe,
        elapsed_ms=elapsed_ms,
        route=route,
        warn_ms=warn_ms,
        fail_ms=fail_ms,
    )
    return {
        "id": route.id,
        "label": route.label,
        "method": route.method,
        "path": route.path,
        "routeRegistered": route_registered,
        "mayCallLiveProviders": route.may_call_live_providers,
        "statusCode": probe.status_code,
        "elapsed_ms": elapsed_ms,
        "classification": classification,
        "reasonCode": reason_code,
        "manualReviewRequired": manual_review,
        "networkCallsExecuted": True,
        "destructiveWritesExecuted": False,
    }


def run_smoke(
    *,
    base_url: str | None = None,
    allow_network: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    authenticated: bool = False,
    warn_ms: float = SLOW_WARN_MS,
    fail_ms: float = SLOW_FAIL_MS,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout_must_be_positive")
    if warn_ms <= 0:
        raise ValueError("warn_ms_must_be_positive")
    if fail_ms <= 0:
        raise ValueError("fail_ms_must_be_positive")
    if fail_ms < warn_ms:
        raise ValueError("fail_ms_must_be_at_least_warn_ms")
    cleaned_base_url = _clean_base_url(base_url) if base_url else None
    route_inventory = load_route_inventory()
    auth_attempted = bool(authenticated)
    auth_succeeded = False
    auth_reason_code = "not_requested"
    username_label: str | None = None
    role: str | None = None
    authenticated_unsafe_post_executed: bool | str = False

    if authenticated:
        _validate_authenticated_routes(AUTHENTICATED_ROUTES)
        username = os.getenv(AUTH_USERNAME_ENV)
        password = os.getenv(AUTH_PASSWORD_ENV)
        if not cleaned_base_url:
            auth_reason_code = "AUTH_BASE_URL_REQUIRED"
            routes = [
                _unprobed_route_result(route, routes_registered=route_inventory, reason_code=auth_reason_code)
                for route in AUTHENTICATED_ROUTES
            ]
        elif not allow_network:
            auth_reason_code = "AUTH_NETWORK_OPT_IN_REQUIRED"
            routes = [
                _unprobed_route_result(route, routes_registered=route_inventory, reason_code=auth_reason_code)
                for route in AUTHENTICATED_ROUTES
            ]
        elif not username or not password:
            auth_reason_code = "AUTH_ENV_REQUIRED"
            routes = [
                _unprobed_route_result(route, routes_registered=route_inventory, reason_code=auth_reason_code)
                for route in AUTHENTICATED_ROUTES
            ]
        else:
            login_result = safe_auth_login(
                base_url=cleaned_base_url,
                username=username,
                password=password,
                timeout=timeout,
            )
            authenticated_unsafe_post_executed = "login_only"
            auth_succeeded = bool(login_result.succeeded)
            auth_reason_code = login_result.reason_code
            username_label = login_result.username_label
            role = login_result.role
            if not auth_succeeded or login_result.session is None:
                routes = [
                    _unprobed_route_result(route, routes_registered=route_inventory, reason_code="auth_failed")
                    for route in AUTHENTICATED_ROUTES
                ]
            else:
                routes = [
                    _measure_authenticated_route(
                        route,
                        routes_registered=route_inventory,
                        base_url=cleaned_base_url,
                        session=login_result.session,
                        timeout=timeout,
                        warn_ms=warn_ms,
                        fail_ms=fail_ms,
                    )
                    for route in AUTHENTICATED_ROUTES
                ]
    else:
        routes = [
            _measure_route(
                route,
                routes_registered=route_inventory,
                base_url=cleaned_base_url,
                allow_network=allow_network,
                timeout=timeout,
                warn_ms=warn_ms,
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
        "warnMs": warn_ms,
        "failMs": fail_ms,
        "networkProbeRequested": bool(cleaned_base_url),
        "allowNetwork": bool(allow_network),
        "networkCallsExecuted": network_calls,
        "destructiveWritesExecuted": False,
        "authAttempted": auth_attempted,
        "authSucceeded": auth_succeeded,
        "authReasonCode": auth_reason_code,
        "usernameLabel": username_label,
        "role": role,
        "authenticatedUnsafePostExecuted": authenticated_unsafe_post_executed,
        "businessMutationsExecuted": False,
        "notificationsSent": False,
        "rawResponseBodiesCaptured": False,
        "liveProviderCallsAllowed": bool(allow_network),
        "manualReviewRequired": manual_review,
        "safety": {
            "httpMethods": ["GET"] if not authenticated_unsafe_post_executed else ["POST(login_only)", "GET"],
            "rawResponseBodiesCaptured": False,
            "authenticatedUnsafePostExecuted": authenticated_unsafe_post_executed,
            "portfolioWatchlistSettingsAdminMutated": False,
            "businessMutationsExecuted": False,
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
    parser.add_argument("--authenticated", action="store_true", help="Use local test credentials from env for bounded authenticated GET probes.")
    parser.add_argument("--json-output", type=Path, help="Optional path to write the JSON summary.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP probe timeout in seconds.")
    parser.add_argument("--warn-ms", type=float, default=SLOW_WARN_MS, help="Warn threshold for route elapsed time in milliseconds.")
    parser.add_argument("--fail-ms", type=float, default=SLOW_FAIL_MS, help="Fail threshold for route elapsed time in milliseconds.")
    args = parser.parse_args(argv)

    try:
        summary = run_smoke(
            base_url=args.base_url,
            allow_network=args.allow_network,
            timeout=args.timeout,
            authenticated=args.authenticated,
            warn_ms=args.warn_ms,
            fail_ms=args.fail_ms,
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
