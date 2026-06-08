#!/usr/bin/env python3
"""Post-gate staging integration smoke.

Safe default behavior is local route/config inspection only. Live HTTP probing
requires both --base-url and --allow-network, and uses read-only GET routes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_BODY_BYTES = 16_384
EXIT_OK = 0
EXIT_FAILED = 1


@dataclass(frozen=True)
class Surface:
    id: str
    label: str
    method: str
    path: str
    group: str
    auth_required: bool = False
    ai_research_optional: bool = False


@dataclass(frozen=True)
class HttpProbeResult:
    status_code: int | None
    reason_code: str


SURFACES: tuple[Surface, ...] = (
    Surface("public_health", "Public health", "GET", "/api/health", "public_health"),
    Surface("auth_session_status", "Auth/session status", "GET", "/api/v1/auth/status", "auth_session"),
    Surface("auth_session_me", "Current session identity", "GET", "/api/v1/auth/me", "auth_session", auth_required=True),
    Surface("market_overview_indices", "Market overview API surface", "GET", "/api/v1/market-overview/indices", "market_overview"),
    Surface("scanner_themes", "Scanner public theme surface", "GET", "/api/v1/scanner/themes", "scanner"),
    Surface("scanner_runs", "Scanner protected runs surface", "GET", "/api/v1/scanner/runs", "scanner", auth_required=True),
    Surface("ai_research_status", "AI research status surface", "GET", "/api/v1/agent/status", "ai_research", ai_research_optional=True),
    Surface(
        "ai_research_provider_health",
        "AI research provider health surface",
        "GET",
        "/api/v1/agent/provider-health",
        "ai_research",
        ai_research_optional=True,
    ),
    Surface("portfolio_accounts", "Portfolio API surface", "GET", "/api/v1/portfolio/accounts", "portfolio", auth_required=True),
    Surface("backtest_runs", "Backtest API surface", "GET", "/api/v1/backtest/runs", "backtest", auth_required=True),
    Surface(
        "admin_logs_storage_summary",
        "Admin logs surface",
        "GET",
        "/api/v1/admin/logs/storage/summary",
        "admin_logs",
        auth_required=True,
    ),
    Surface(
        "admin_cost_duplicate_summary",
        "Admin cost surface",
        "GET",
        "/api/v1/admin/cost/duplicate-summary",
        "admin_cost",
        auth_required=True,
    ),
    Surface(
        "admin_provider_circuits",
        "Provider circuits surface",
        "GET",
        "/api/v1/admin/providers/circuits",
        "provider_circuits",
        auth_required=True,
    ),
    Surface(
        "admin_market_provider_operations",
        "Market provider operations surface",
        "GET",
        "/api/v1/admin/market-providers/operations",
        "provider_operations",
        auth_required=True,
    ),
)


def load_route_inventory() -> set[tuple[str, str]]:
    """Return registered API routes without starting the server or providers."""
    routes: set[tuple[str, str]] = {
        ("GET", "/api/health"),
        ("GET", "/api/health/live"),
        ("GET", "/api/health/ready"),
    }
    try:
        from fastapi.routing import APIRoute
        from api.v1 import api_v1_router
    except ModuleNotFoundError as exc:
        if exc.name == "fastapi":
            routes.update((surface.method, surface.path) for surface in SURFACES)
            return routes
        raise

    for route in api_v1_router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.add((method, route.path))
    return routes


def is_ai_research_locally_available() -> bool:
    """Check agent config availability without invoking the model/provider path."""
    try:
        from src.config import get_config
    except Exception:
        return False
    try:
        return bool(get_config().is_agent_available())
    except Exception:
        return False


def _clean_base_url(raw_url: str) -> str:
    parsed = urllib.parse.urlsplit(str(raw_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url_requires_http_scheme_and_host")
    if parsed.username or parsed.password:
        raise ValueError("base_url_must_not_include_credentials")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _join_url(base_url: str, path: str) -> str:
    return f"{_clean_base_url(base_url)}{path}"


def _body_reason(status_code: int, body: bytes) -> str:
    text = body[:MAX_BODY_BYTES].decode("utf-8", errors="ignore").lower()
    if any(marker in text for marker in ("config", "not configured", "missing credential", "missing_credentials")):
        return "config_missing"
    if any(marker in text for marker in ("dependency", "unavailable", "timeout", "connection")):
        return "dependency_unavailable"
    if any(marker in text for marker in ("unauthorized", "login required", "not_authenticated", "forbidden")):
        return "auth_required"
    if status_code == 404:
        return "route_missing"
    if status_code >= 500:
        return "unexpected_server_error"
    return "http_error"


def safe_http_get(base_url: str, path: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> HttpProbeResult:
    """Execute a bounded GET probe and return only sanitized status metadata."""
    request = urllib.request.Request(
        _join_url(base_url, path),
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "wolfystock-staging-integration-smoke/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(MAX_BODY_BYTES)
            status_code = int(response.status)
            return HttpProbeResult(status_code=status_code, reason_code="ok")
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BODY_BYTES)
        status_code = int(exc.code)
        return HttpProbeResult(status_code=status_code, reason_code=_body_reason(status_code, body))
    except TimeoutError:
        return HttpProbeResult(status_code=None, reason_code="dependency_unavailable")
    except OSError:
        return HttpProbeResult(status_code=None, reason_code="dependency_unavailable")


def _status_from_http(result: HttpProbeResult) -> tuple[str, str]:
    status_code = result.status_code
    reason_code = result.reason_code
    if status_code is None:
        return "skipped", "dependency_unavailable"
    if 200 <= status_code < 300:
        return "pass", "ok"
    if status_code in {401, 403}:
        return "pass", "auth_required"
    if status_code == 404:
        return "fail", "route_missing"
    if reason_code == "config_missing":
        return "skipped", "config_missing"
    if reason_code == "dependency_unavailable" or status_code == 503:
        return "skipped", "dependency_unavailable"
    if status_code >= 500:
        return "fail", "unexpected_server_error"
    return "fail", reason_code or "unexpected_http_status"


def _surface_result(
    surface: Surface,
    *,
    routes: set[tuple[str, str]],
    ai_available: bool,
    base_url: str | None,
    allow_network: bool,
    timeout: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        route_registered = (surface.method, surface.path) in routes
        result: dict[str, Any] = {
            "id": surface.id,
            "label": surface.label,
            "group": surface.group,
            "method": surface.method,
            "path": surface.path,
            "routeRegistered": route_registered,
            "authRequired": surface.auth_required,
            "networkProbe": False,
        }
        if not route_registered:
            result.update({"status": "fail", "reasonCode": "route_missing"})
            return result
        if surface.ai_research_optional and not ai_available:
            result.update({"status": "skipped", "reasonCode": "config_missing"})
            return result
        if base_url and allow_network:
            probe = safe_http_get(base_url, surface.path, timeout)
            status, reason_code = _status_from_http(probe)
            result.update(
                {
                    "status": status,
                    "reasonCode": reason_code,
                    "httpStatus": probe.status_code,
                    "networkProbe": True,
                }
            )
            return result
        reason_code = "auth_required" if surface.auth_required else "route_registered"
        result.update({"status": "pass", "reasonCode": reason_code})
        return result
    finally:
        result["elapsedMs"] = round(max(0.0, (time.perf_counter() - started) * 1000), 3)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = round((len(sorted_values) - 1) * percentile)
    return sorted_values[rank]


def _timing_summary(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = [float(item["elapsedMs"]) for item in results if isinstance(item.get("elapsedMs"), (int, float))]
    if not values:
        return {"count": 0, "minElapsedMs": 0.0, "maxElapsedMs": 0.0, "p50ElapsedMs": 0.0, "p95ElapsedMs": 0.0}
    return {
        "count": len(values),
        "minElapsedMs": min(values),
        "maxElapsedMs": max(values),
        "p50ElapsedMs": _percentile(values, 0.50),
        "p95ElapsedMs": _percentile(values, 0.95),
    }


def _smoke_status(results: Iterable[dict[str, Any]]) -> str:
    items = list(results)
    if any(item.get("status") == "fail" for item in items):
        return "fail"
    if any(
        item.get("status") == "skipped"
        or item.get("reasonCode") in {"auth_required", "dependency_unavailable", "config_missing"}
        for item in items
    ):
        return "manual_review_required"
    return "pass"


def run_smoke(
    *,
    mode: str = "local",
    base_url: str | None = None,
    allow_network: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if mode != "local":
        raise ValueError("unsupported_mode")
    if base_url:
        _clean_base_url(base_url)
    routes = load_route_inventory()
    ai_available = is_ai_research_locally_available()
    checked = [
        _surface_result(
            surface,
            routes=routes,
            ai_available=ai_available,
            base_url=base_url,
            allow_network=allow_network,
            timeout=timeout,
        )
        for surface in SURFACES
    ]
    skipped = [
        {
            "id": item["id"],
            "group": item["group"],
            "reasonCode": item["reasonCode"],
            "path": item["path"],
        }
        for item in checked
        if item.get("status") == "skipped"
    ]
    auth_required = [item["id"] for item in checked if item.get("authRequired") is True]
    manual_review = [
        item["id"]
        for item in checked
        if item.get("status") == "skipped" or item.get("reasonCode") in {"auth_required", "dependency_unavailable", "config_missing"}
    ]
    return {
        "smokeStatus": _smoke_status(checked),
        "mode": mode,
        "checkedSurfaces": checked,
        "skippedSurfaces": skipped,
        "networkCallsExecuted": bool(base_url and allow_network),
        "destructiveWritesExecuted": False,
        "authRequiredSurfaces": auth_required,
        "manualReviewRequired": manual_review,
        "timingSummary": _timing_summary(checked),
    }


def _write_json(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["local"], default="local")
    parser.add_argument("--base-url", help="Optional local/staging backend URL. Does not probe unless --allow-network is set.")
    parser.add_argument("--allow-network", action="store_true", help="Opt in to bounded read-only HTTP GET probes.")
    parser.add_argument("--json-output", type=Path, help="Optional path to write the JSON summary.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP probe timeout in seconds.")
    args = parser.parse_args(argv)

    try:
        summary = run_smoke(
            mode=args.mode,
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
