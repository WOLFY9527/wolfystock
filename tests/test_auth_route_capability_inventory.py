# -*- coding: utf-8 -*-
"""Inventory contract tests for auth/RBAC route-capability boundaries."""

from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute

from api.route_access_policy import is_public_baseline_read
from api.v1 import api_v1_router
from scripts.auth_route_capability_inventory import (
    FrontendRouteDeclarationError,
    build_backend_inventory,
    build_frontend_inventory,
    parse_frontend_route_declarations,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "auth"
APP_TSX = REPO_ROOT / "apps" / "dsa-web" / "src" / "App.tsx"
ADMIN_CAPABILITIES_TS = REPO_ROOT / "apps" / "dsa-web" / "src" / "utils" / "adminCapabilities.ts"
AUTH_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "auth.py"
ADMIN_LOGS_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "admin_logs.py"
ADMIN_USERS_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "admin_users.py"
MARKET_PROVIDER_OPERATIONS_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "market_provider_operations.py"
AGENT_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "agent.py"
SCANNER_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "scanner.py"
USAGE_ENDPOINT_TS = REPO_ROOT / "api" / "v1" / "endpoints" / "usage.py"

BACKEND_FIXTURE = FIXTURE_DIR / "backend_route_capability_inventory.json"
FRONTEND_FIXTURE = FIXTURE_DIR / "frontend_route_capability_inventory.json"

FORBIDDEN_FIXTURE_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session token",
    "session-token",
    "passwordhash",
    "password_hash",
    "api_key",
    "access_token",
    "refresh_token",
    "secret",
    "private_key",
    "webhook",
)
ADMIN_CAPABILITY_CASES = {
    "/settings/system": "canReadSystemConfig",
    "/admin/logs": "canReadOpsLogs",
    "/admin/evidence-workflow": "canReadOpsLogs",
    "/admin/notifications": "canReadNotifications",
    "/admin/market-providers": "canReadProviders",
    "/admin/provider-circuits": "canReadProviders",
    "/admin/cost-observability": "canReadCostObservability",
}
EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS = {
    ("GET", "/api/v1/backtest/rule/runs/{run_id}/robustness-evidence.json"): {
        "auth_dependency_label": "authenticated_user",
        "capability_label": None,
        "note": "Backtest robustness evidence is authenticated-user scoped outside the admin control-plane inventory.",
    },
    ("GET", "/api/v1/backtest/rule/runs/{run_id}/regime-attribution-readiness.json"): {
        "auth_dependency_label": "authenticated_user",
        "capability_label": None,
        "note": "Backtest regime attribution readiness export is authenticated-user scoped outside the admin control-plane inventory.",
    },
    ("GET", "/api/v1/backtest/rule/runs/{run_id}/execution-model-metadata.json"): {
        "auth_dependency_label": "authenticated_user",
        "capability_label": None,
        "note": "Backtest execution model metadata export is authenticated-user scoped outside the admin control-plane inventory.",
    },
    ("GET", "/api/v1/backtest/rule/runs/{run_id}/oos-parameter-readiness.json"): {
        "auth_dependency_label": "authenticated_user",
        "capability_label": None,
        "note": "Backtest OOS parameter readiness export is authenticated-user scoped outside the admin control-plane inventory.",
    },
}
EXPECTED_TRANSITIONAL_ADMIN_USER_ALLOWLIST = {}
EXPECTED_T1463_MIGRATED_ROUTE_CAPABILITIES = {
    ("POST", "/api/v1/agent/chat/send"): "ops:notifications:write",
    ("GET", "/api/v1/scanner/watchlists/today"): "scanner:admin:read",
    ("GET", "/api/v1/scanner/watchlists/recent"): "scanner:admin:read",
    ("GET", "/api/v1/scanner/status"): "scanner:admin:read",
    ("GET", "/api/v1/usage/summary"): "cost:observability:read",
}
EXPECTED_CONTROL_PLANE_GROUP_ROUTE_COUNTS = {
    "agent.operator_diagnostics": 3,
    "agent.admin_send": 1,
    "scanner.admin_watchlists_and_status": 3,
    "usage.admin_summary": 1,
    "quant.duckdb.read": 6,
    "quant.duckdb.write": 3,
    "admin.users.read": 2,
    "admin.users.activity_read": 1,
    "admin.users.portfolio_read": 4,
    "admin.users.security_write": 4,
    "admin.activity.read": 1,
    "admin.logs.read": 8,
    "admin.logs.write": 1,
    "admin.ops.status": 2,
    "admin.mission_control": 1,
    "admin.notifications.read": 2,
    "admin.notifications.write": 5,
    "admin.cost.read": 5,
    "admin.providers.read": 13,
    "market.professional_data_capabilities_admin": 1,
    "market.operator_diagnostics": 3,
    "system.config.read": 2,
    "system.config.validate": 1,
    "system.config.write": 3,
    "system.provider_tests.write": 3,
}
BACKEND_ONLY_WRITE_CAPABILITY_LABELS = {
    "ops:notifications:write",
    "ops:providers:write",
    "ops:system_config:write",
}
FRONTEND_ADMIN_READ_CAPABILITY_LABELS = {
    "ops:notifications:read",
    "ops:providers:read",
    "ops:system_config:read",
}
SURFACE_CLASSIFICATION_VOCABULARY = {
    "public_consumer_safe_read",
    "authenticated_member",
    "admin_capability",
    "operator_diagnostic",
    "bounded_auth_endpoint",
    "bounded_health_docs_surface",
}
DOCS_AND_SCHEMA_ROUTE_CLASSIFICATIONS = {
    ("GET", "/docs"): "bounded_health_docs_surface",
    ("GET", "/redoc"): "bounded_health_docs_surface",
    ("GET", "/openapi.json"): "bounded_health_docs_surface",
}
EXPECTED_SURFACE_ROUTE_CLASSIFICATIONS = {
    ("GET", "/api/v1/market/data-readiness"): "operator_diagnostic",
    ("GET", "/api/v1/market/data-source-gap-registry"): "operator_diagnostic",
    ("GET", "/api/v1/market/cn-provider-health"): "operator_diagnostic",
    ("GET", "/api/v1/market/provider-fit-advisor"): "admin_capability",
    ("GET", "/api/v1/market/professional-data-capabilities/admin"): "admin_capability",
    ("GET", "/api/v1/agent/status"): "operator_diagnostic",
    ("GET", "/api/v1/agent/models"): "operator_diagnostic",
    ("GET", "/api/v1/agent/provider-health"): "operator_diagnostic",
    ("GET", "/api/v1/agent/skills"): "authenticated_member",
    ("GET", "/api/v1/agent/stock-research"): "authenticated_member",
    ("POST", "/api/v1/agent/chat"): "authenticated_member",
    ("GET", "/api/v1/agent/chat/sessions"): "authenticated_member",
    ("GET", "/api/v1/agent/chat/sessions/{session_id}"): "authenticated_member",
    ("DELETE", "/api/v1/agent/chat/sessions/{session_id}"): "authenticated_member",
    ("POST", "/api/v1/agent/chat/stream"): "authenticated_member",
    ("POST", "/api/v1/agent/chat/send"): "admin_capability",
    ("GET", "/api/v1/research/radar"): "authenticated_member",
    ("GET", "/api/v1/research/queue"): "authenticated_member",
    ("POST", "/api/v1/user-alerts/rules/{rule_id}/dry-run"): "authenticated_member",
    ("GET", "/api/v1/stocks/{stock_code}/quote"): "public_consumer_safe_read",
    ("GET", "/api/v1/stocks/{stock_code}/structure-decision"): "authenticated_member",
    ("POST", "/api/v1/stocks/structure-decisions/batch"): "authenticated_member",
    ("POST", "/api/v1/scanner/run"): "authenticated_member",
    ("GET", "/api/v1/scanner/runs"): "authenticated_member",
    ("GET", "/api/v1/scanner/strategy-simulation"): "authenticated_member",
    ("GET", "/api/v1/scanner/runs/{run_id}"): "authenticated_member",
    ("GET", "/api/v1/scanner/runs/{run_id}/research-overlay"): "authenticated_member",
    ("GET", "/api/v1/scanner/watchlists/today"): "admin_capability",
    ("GET", "/api/v1/scanner/watchlists/recent"): "admin_capability",
    ("GET", "/api/v1/scanner/status"): "admin_capability",
    ("GET", "/api/v1/scanner/themes"): "authenticated_member",
    ("POST", "/api/v1/scanner/themes"): "authenticated_member",
    ("GET", "/api/v1/watchlist/"): "authenticated_member",
    ("GET", "/api/v1/watchlist/items"): "authenticated_member",
    ("POST", "/api/v1/watchlist/items"): "authenticated_member",
    ("POST", "/api/v1/watchlist/items/from-scanner-candidate"): "authenticated_member",
    ("DELETE", "/api/v1/watchlist/items/{item_id}"): "authenticated_member",
    ("GET", "/api/v1/watchlist/research-overlay"): "authenticated_member",
    ("GET", "/api/v1/watchlist/refresh-status"): "authenticated_member",
    ("POST", "/api/v1/watchlist/refresh-scores"): "authenticated_member",
    ("GET", "/api/v1/usage/summary"): "admin_capability",
    ("GET", "/api/v1/options/lab"): "authenticated_member",
    ("GET", "/api/v1/options/gamma"): "authenticated_member",
    ("GET", "/api/v1/options/underlyings/{symbol}/summary"): "authenticated_member",
    ("GET", "/api/v1/options/underlyings/{symbol}/expirations"): "authenticated_member",
    ("GET", "/api/v1/options/underlyings/{symbol}/chain"): "authenticated_member",
    ("GET", "/api/v1/options/underlyings/{symbol}/structure"): "authenticated_member",
    ("POST", "/api/v1/options/analyze"): "authenticated_member",
    ("POST", "/api/v1/options/decision/evaluate"): "authenticated_member",
    ("POST", "/api/v1/options/scenario"): "authenticated_member",
    ("POST", "/api/v1/options/strategies/compare"): "authenticated_member",
    ("POST", "/api/v1/options/strategies/analyze"): "authenticated_member",
    ("GET", "/api/v1/admin/logs/storage/summary"): "admin_capability",
    ("POST", "/api/v1/admin/users/onboard"): "admin_capability",
    ("GET", "/api/v1/admin/ops/status"): "admin_capability",
    ("GET", "/api/v1/admin/ops/surface-readiness"): "admin_capability",
    ("GET", "/api/v1/admin/mission-control"): "admin_capability",
    ("GET", "/api/v1/admin/cost/duplicate-summary"): "admin_capability",
    ("GET", "/api/v1/admin/cost/summary"): "admin_capability",
    ("POST", "/api/v1/admin/cost/quota-dry-run"): "admin_capability",
    ("GET", "/api/v1/admin/cost/llm-ledger-summary"): "admin_capability",
    ("GET", "/api/v1/admin/provider-circuits"): "admin_capability",
    ("GET", "/api/v1/admin/providers/quota-windows"): "admin_capability",
    ("GET", "/api/v1/admin/providers/sla-readiness"): "admin_capability",
    ("GET", "/api/v1/admin/providers/operations-matrix"): "admin_capability",
    ("GET", "/api/v1/admin/provider-usage-ledger"): "admin_capability",
    ("GET", "/api/v1/admin/market-providers/operations"): "admin_capability",
    ("GET", "/api/v1/admin/market-provider-operations"): "admin_capability",
    ("GET", "/api/v1/admin/provider-activation-verifier"): "admin_capability",
    ("GET", "/api/v1/admin/historical-ohlcv/cache-preflight"): "admin_capability",
    ("POST", "/api/v1/admin/historical-ohlcv/cache-preflight/seed"): "admin_capability",
    ("GET", "/api/v1/quant/duckdb/health"): "admin_capability",
    ("GET", "/api/v1/system/config"): "admin_capability",
}
EXPECTED_OPERATOR_DIAGNOSTIC_ROUTE_CLASSIFICATIONS = {
    ("GET", "/api/v1/market/data-readiness"),
    ("GET", "/api/v1/market/data-source-gap-registry"),
    ("GET", "/api/v1/market/cn-provider-health"),
    ("GET", "/api/v1/agent/status"),
    ("GET", "/api/v1/agent/models"),
    ("GET", "/api/v1/agent/provider-health"),
}
EXPECTED_LEGACY_ROUTE_SURFACE_CLASSIFICATIONS: set[tuple[str, str]] = set()
EXPECTED_OPTIONS_AUTH_REQUIRED_ROUTE_CLASSIFICATIONS = {
    signature
    for signature, classification in EXPECTED_SURFACE_ROUTE_CLASSIFICATIONS.items()
    if signature[1].startswith("/api/v1/options/") and classification == "authenticated_member"
}
UNWRAPPED_REGISTERED_ROUTE_EXCEPTIONS = {
    "market_overview": {
        "path": "/market-overview",
        "localized_path": "market-overview",
        "test_probe": "queryByText('auth-guard:Market Overview')",
    },
}
AUTH_ROUTE_REQUEST_GUARD_MARKERS = (
    "resolve_current_user(request)",
    "_serialize_current_user(request)",
    "_require_admin_current_user(request)",
)
EXPECTED_AUTH_ROUTE_SOURCE_INVENTORY = {
    ("GET", "/status"): "public",
    ("GET", "/me"): "request_guarded",
    ("GET", "/preferences/notifications"): "request_guarded",
    ("PUT", "/preferences/notifications"): "request_guarded",
    ("POST", "/reauth"): "request_guarded",
    ("POST", "/mfa/enroll/start"): "request_guarded",
    ("POST", "/mfa/enroll/verify"): "request_guarded",
    ("POST", "/mfa/verify"): "request_guarded",
    ("POST", "/mfa/disable"): "request_guarded",
    ("POST", "/mfa/recovery-codes/generate"): "request_guarded",
    ("POST", "/mfa/recovery-codes/verify"): "request_guarded",
    ("POST", "/mfa/recovery-codes/rotate"): "request_guarded",
    ("POST", "/verify-password"): "request_guarded",
    ("POST", "/settings"): "request_guarded",
    ("POST", "/login"): "public",
    ("POST", "/reset-password/request"): "public",
    ("POST", "/change-password"): "request_guarded",
    ("POST", "/logout"): "public",
}
EXPECTED_AUTH_ROUTE_SOURCE_SPECIAL_CASES: set[str] = set()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_strings(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_secret_free_fixture(payload: Any) -> None:
    text = "\n".join(_iter_strings(payload)).lower()
    for forbidden in FORBIDDEN_FIXTURE_TERMS:
        assert forbidden not in text


def _extract_capability_from_call(call: object | None) -> str | None:
    if call is None:
        return None
    closure = getattr(call, "__closure__", None) or ()
    for cell in closure:
        value = getattr(cell, "cell_contents", None)
        if isinstance(value, str) and ":" in value:
            return value
    try:
        source = inspect.getsource(call)
    except (OSError, TypeError):
        return None
    match = re.search(r"require_admin_capability\(\s*[\"']([^\"']+)[\"']\s*\)", source)
    if match:
        return match.group(1)
    return None


def _route_auth_metadata(route: APIRoute) -> dict[str, str | None]:
    dependency_label: str | None = None
    capability_label: str | None = None

    for dependency in route.dependant.dependencies:
        call = getattr(dependency, "call", None)
        name = getattr(call, "__name__", "") or ""
        qualname = getattr(call, "__qualname__", "") or ""
        capability = _extract_capability_from_call(call)

        if capability:
            dependency_label = "admin_capability"
            capability_label = capability
            break
        if name == "require_admin_user":
            dependency_label = dependency_label or "admin_user"
            continue
        if name == "get_current_user":
            dependency_label = dependency_label or "authenticated_user"
            continue
        if name == "get_optional_current_user":
            dependency_label = dependency_label or "optional_current_user"
            continue
        if "require_admin_capability" in qualname:
            dependency_label = "admin_capability"
            capability_label = capability_label or capability
            break

    return {
        "auth_dependency_label": dependency_label,
        "capability_label": capability_label,
    }


def _collect_live_routes() -> dict[tuple[str, str], dict[str, str | None]]:
    def iter_effective_routes(routes: list[Any]):
        for route in routes:
            if isinstance(route, APIRoute) or (
                hasattr(route, "dependant") and hasattr(route, "methods") and hasattr(route, "path")
            ):
                yield route
                continue
            effective_candidates = getattr(route, "effective_candidates", None)
            if callable(effective_candidates):
                yield from iter_effective_routes(list(effective_candidates()))

    collected: dict[tuple[str, str], dict[str, str | None]] = {}
    for route in iter_effective_routes(api_v1_router.routes):
        metadata = _route_auth_metadata(route)
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            collected[(method, route.path)] = {
                "method": method,
                "path": route.path,
                **metadata,
            }
    return collected


def _route_matches_group(route: dict[str, str | None], group: dict[str, Any]) -> bool:
    if route["auth_dependency_label"] != group["auth_dependency_label"]:
        return False
    if route["method"] not in set(group["methods"]):
        return False
    if group["capability_label"] != route["capability_label"]:
        return False
    return re.match(group["path_pattern"], route["path"] or "") is not None


def _classification_signature(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry["method"]), str(entry["path"]))


def _surface_classification_entries(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    return list(fixture["route_surface_classifications"])


def _surface_classification_by_signature(
    fixture: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    entries = _surface_classification_entries(fixture)
    by_signature = {_classification_signature(entry): entry for entry in entries}
    assert len(by_signature) == len(entries)
    return by_signature


def _matched_route_signatures(
    live_routes: dict[tuple[str, str], dict[str, str | None]],
    group: dict[str, Any],
) -> list[tuple[str, str]]:
    return sorted(
        (route["method"], route["path"] or "")
        for route in live_routes.values()
        if _route_matches_group(route, group)
    )


def _extract_route_block(source: str, marker: str, closing: str) -> str:
    start = source.index(marker)
    end = source.index(closing, start)
    return source[start:end]


def _format_auth_route_special_case(
    *,
    function_name: str,
    decorator_name: str,
    methods: list[str] | None,
    path: str | None,
) -> str:
    methods_label = ",".join(methods or ["<dynamic-methods>"])
    path_label = path or "<dynamic-path>"
    return f"{decorator_name}:{methods_label} {path_label} [{function_name}]"


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _collect_auth_route_source_inventory(
    source: str,
) -> tuple[dict[tuple[str, str], dict[str, str]], set[str]]:
    tree = ast.parse(source)
    lines = source.splitlines()
    inventory: dict[tuple[str, str], dict[str, str]] = {}
    special_cases: set[str] = set()

    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue

        body_start = node.body[0].lineno - 1 if node.body else node.lineno - 1
        body = "\n".join(lines[body_start : node.end_lineno or body_start])
        classification = (
            "request_guarded"
            if any(marker in body for marker in AUTH_ROUTE_REQUEST_GUARD_MARKERS)
            else "public"
        )

        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
            ):
                continue

            decorator_name = decorator.func.attr
            path = _literal_string(decorator.args[0] if decorator.args else None)
            if decorator_name in {"get", "post", "put", "delete", "patch"}:
                methods = [decorator_name.upper()]
            else:
                methods = None

            if methods is None or path is None:
                special_cases.add(
                    _format_auth_route_special_case(
                        function_name=node.name,
                        decorator_name=decorator_name,
                        methods=methods,
                        path=path,
                    )
                )
                continue

            for method in methods:
                signature = (method, path)
                assert signature not in inventory, f"duplicate auth route decorator for {signature}"
                inventory[signature] = {
                    "method": method,
                    "path": path,
                    "classification": classification,
                    "function_name": node.name,
                    "body": body,
                }

    return inventory, special_cases


def _guest_restriction_markers(path: str) -> set[str]:
    base = path.split("/:")[0]
    parent = base.rsplit("/", 1)[0] if "/" in base[1:] else base
    return {
        path,
        base,
        base + "/",
        parent,
        parent + "/",
    }


def _is_control_plane_route(route: dict[str, str | None]) -> bool:
    path = route["path"] or ""
    if path.startswith("/api/v1/admin/") or path.startswith("/api/v1/system/"):
        return True
    return path in {
        "/api/v1/agent/chat/send",
        "/api/v1/scanner/status",
        "/api/v1/scanner/watchlists/today",
        "/api/v1/scanner/watchlists/recent",
        "/api/v1/usage/summary",
        "/api/v1/quant/duckdb/health",
        "/api/v1/quant/duckdb/init",
        "/api/v1/quant/duckdb/ingest-ohlcv",
        "/api/v1/quant/duckdb/build-factors",
        "/api/v1/quant/duckdb/factor-snapshot",
        "/api/v1/quant/duckdb/validate-factor-path",
        "/api/v1/quant/duckdb/compare-runtime-context",
        "/api/v1/quant/duckdb/coverage",
        "/api/v1/quant/duckdb/benchmark",
        "/api/v1/agent/status",
        "/api/v1/agent/models",
        "/api/v1/agent/provider-health",
        "/api/v1/market/data-readiness",
        "/api/v1/market/data-source-gap-registry",
        "/api/v1/market/cn-provider-health",
        "/api/v1/market/professional-data-capabilities/admin",
    }


def test_auth_route_inventory_fixtures_do_not_contain_secret_like_material() -> None:
    _assert_secret_free_fixture(_load_json(BACKEND_FIXTURE))
    _assert_secret_free_fixture(_load_json(FRONTEND_FIXTURE))


def test_route_capability_inventory_fixtures_match_canonical_generator() -> None:
    assert _load_json(BACKEND_FIXTURE) == build_backend_inventory(REPO_ROOT)
    assert _load_json(FRONTEND_FIXTURE) == build_frontend_inventory(REPO_ROOT)


def test_root_docs_inventory_wording_matches_t286_auth_mode_matrix() -> None:
    fixture = build_backend_inventory(REPO_ROOT)
    classifications = _surface_classification_by_signature(fixture)

    for signature in DOCS_AND_SCHEMA_ROUTE_CLASSIFICATIONS:
        note = str(classifications[signature]["transitional_note"] or "").lower()
        assert "auth is enabled" in note
        assert "auth is disabled" in note
        assert "non-production" in note
        assert "production" in note
        assert "403" in note


def test_backend_route_capability_inventory_covers_current_dependency_guarded_routes() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()
    protected_live_routes = [
        route
        for route in live_routes.values()
        if route["auth_dependency_label"] in {"authenticated_user", "admin_user", "admin_capability"}
    ]

    unmatched_routes = []
    for route in protected_live_routes:
        route_key = (route["method"], route["path"])
        if route_key in EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS:
            expected = EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS[route_key]
            assert route["auth_dependency_label"] == expected["auth_dependency_label"]
            assert route["capability_label"] == expected["capability_label"]
            continue
        matched_group = next((group for group in fixture["protected_groups"] if _route_matches_group(route, group)), None)
        if matched_group is None:
            unmatched_routes.append(route)
            continue
        if matched_group["auth_dependency_label"] == "admin_user":
            assert matched_group["transitional_note"], f"missing transitional note for {matched_group['route_id']}"
        if matched_group["auth_dependency_label"] == "admin_capability":
            assert matched_group["capability_label"], f"missing capability label for {matched_group['route_id']}"

    assert unmatched_routes == []

    for group in fixture["protected_groups"]:
        matches = [route for route in protected_live_routes if _route_matches_group(route, group)]
        assert matches, f"inventory group no longer matches any live route: {group['route_id']}"


def test_authenticated_route_exceptions_remain_explicit_and_narrow() -> None:
    live_routes = _collect_live_routes()

    for route_key, expected in EXPLICIT_AUTHENTICATED_ROUTE_EXCEPTIONS.items():
        live = live_routes[route_key]
        assert live["auth_dependency_label"] == expected["auth_dependency_label"]
        assert live["capability_label"] == expected["capability_label"]
        assert "admin control-plane" in expected["note"].lower()


def test_backend_public_and_optional_user_routes_are_not_mislabeled_as_admin_only() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()

    for sample in fixture["public_samples"]:
        live = live_routes[(sample["method"], sample["path"])]
        expected = sample["auth_dependency_label"]
        if expected == "public":
            assert live["auth_dependency_label"] is None
        else:
            assert live["auth_dependency_label"] == expected
        assert live["capability_label"] is None


def test_admin_observability_route_inventory_keeps_capabilities_and_transitional_gaps_explicit() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    groups = {group["route_id"]: group for group in fixture["protected_groups"]}

    quant_duckdb_read = groups["quant.duckdb.read"]
    quant_duckdb_write = groups["quant.duckdb.write"]
    admin_logs_read = groups["admin.logs.read"]
    admin_logs_write = groups["admin.logs.write"]
    admin_mission_control = groups["admin.mission_control"]
    admin_users_read = groups["admin.users.read"]
    admin_users_activity_read = groups["admin.users.activity_read"]
    admin_activity_read = groups["admin.activity.read"]
    provider_observability = groups["admin.providers.read"]
    agent_admin_send = groups["agent.admin_send"]
    scanner_admin = groups["scanner.admin_watchlists_and_status"]
    usage_admin = groups["usage.admin_summary"]

    assert agent_admin_send["auth_dependency_label"] == "admin_capability"
    assert agent_admin_send["capability_label"] == "ops:notifications:write"
    assert agent_admin_send["transitional_note"] is None
    assert scanner_admin["auth_dependency_label"] == "admin_capability"
    assert scanner_admin["capability_label"] == "scanner:admin:read"
    assert scanner_admin["transitional_note"] is None
    assert usage_admin["auth_dependency_label"] == "admin_capability"
    assert usage_admin["capability_label"] == "cost:observability:read"
    assert usage_admin["transitional_note"] is None
    assert admin_users_read["auth_dependency_label"] == "admin_capability"
    assert admin_users_read["capability_label"] == "users:read"
    assert admin_users_read["transitional_note"] is None
    assert admin_users_activity_read["auth_dependency_label"] == "admin_capability"
    assert admin_users_activity_read["capability_label"] == "users:activity:read"
    assert admin_users_activity_read["transitional_note"] is None
    assert quant_duckdb_read["auth_dependency_label"] == "admin_capability"
    assert quant_duckdb_read["capability_label"] == "quant:admin:read"
    assert quant_duckdb_read["transitional_note"] is None
    assert quant_duckdb_write["auth_dependency_label"] == "admin_capability"
    assert quant_duckdb_write["capability_label"] == "quant:admin:write"
    assert quant_duckdb_write["transitional_note"] is None
    assert admin_activity_read["auth_dependency_label"] == "admin_capability"
    assert admin_activity_read["capability_label"] == "users:activity:read"
    assert admin_activity_read["transitional_note"] is None
    assert admin_logs_read["auth_dependency_label"] == "admin_capability"
    assert admin_logs_read["capability_label"] == "ops:logs:read"
    assert admin_logs_write["auth_dependency_label"] == "admin_capability"
    assert admin_logs_write["capability_label"] == "ops:logs:write"
    assert admin_mission_control["auth_dependency_label"] == "admin_capability"
    assert admin_mission_control["capability_label"] == "ops:logs:read"
    assert admin_mission_control["transitional_note"] is None
    assert provider_observability["auth_dependency_label"] == "admin_capability"
    assert provider_observability["capability_label"] == "ops:providers:read"
    assert provider_observability["transitional_note"] is None

    admin_users_source = ADMIN_USERS_ENDPOINT_TS.read_text(encoding="utf-8")
    admin_logs_source = ADMIN_LOGS_ENDPOINT_TS.read_text(encoding="utf-8")
    market_provider_source = MARKET_PROVIDER_OPERATIONS_ENDPOINT_TS.read_text(encoding="utf-8")
    quant_source = (REPO_ROOT / "api" / "v1" / "endpoints" / "quant.py").read_text(encoding="utf-8")
    agent_source = AGENT_ENDPOINT_TS.read_text(encoding="utf-8")
    scanner_source = SCANNER_ENDPOINT_TS.read_text(encoding="utf-8")
    usage_source = USAGE_ENDPOINT_TS.read_text(encoding="utf-8")

    assert 'require_admin_capability("ops:notifications:write")' in agent_source
    assert 'require_admin_capability("scanner:admin:read")' in scanner_source
    assert 'require_admin_capability("cost:observability:read")' in usage_source
    assert 'require_admin_capability("users:read")' in admin_users_source
    assert 'require_admin_capability("users:activity:read")' in admin_users_source
    assert "/users/onboard" in admin_users_source
    assert 'require_admin_capability("quant:admin:read")' in quant_source
    assert 'require_admin_capability("quant:admin:write")' in quant_source
    assert 'require_admin_capability("ops:logs:read")' in admin_logs_source
    assert 'require_admin_capability("ops:logs:write")' in admin_logs_source
    assert 'require_admin_capability("ops:providers:read")' in market_provider_source


def test_no_remaining_require_admin_user_route_groups_in_control_plane_inventory() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    coarse_admin_groups = {
        group["route_id"]: group
        for group in fixture["protected_groups"]
        if group["auth_dependency_label"] == "admin_user"
    }

    assert coarse_admin_groups == EXPECTED_TRANSITIONAL_ADMIN_USER_ALLOWLIST


def test_control_plane_route_inventory_fails_closed_without_explicit_classification() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()
    groups = {group["route_id"]: group for group in fixture["protected_groups"]}

    assert set(EXPECTED_CONTROL_PLANE_GROUP_ROUTE_COUNTS).issubset(groups)

    classified_route_signatures: set[tuple[str, str]] = set()
    for group in groups.values():
        matches = _matched_route_signatures(live_routes, group)
        for method, path in matches:
            route = live_routes[(method, path)]
            if route["auth_dependency_label"] in {"admin_user", "admin_capability"} and _is_control_plane_route(route):
                classified_route_signatures.add((method, path))

    live_control_plane_signatures = {
        (route["method"], route["path"] or "")
        for route in live_routes.values()
        if route["auth_dependency_label"] in {"admin_user", "admin_capability"} and _is_control_plane_route(route)
    }

    assert classified_route_signatures == live_control_plane_signatures


def test_backend_route_surface_classification_vocabulary_and_no_go_markers_are_explicit() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    entries = _surface_classification_entries(fixture)

    assert set(fixture["surface_classification_vocabulary"]) == SURFACE_CLASSIFICATION_VOCABULARY
    assert entries

    for entry in entries:
        classification = entry["surface_classification"]
        assert classification in SURFACE_CLASSIFICATION_VOCABULARY
        assert set(entry) == {
            "route_id",
            "path",
            "method",
            "surface_classification",
            "auth_dependency_label",
            "capability_label",
            "no_go_marker",
            "transitional_note",
        }
        assert entry["no_go_marker"] is None, entry["route_id"]
        if classification == "public_consumer_safe_read":
            assert entry["auth_dependency_label"] == "public", entry["route_id"]
            assert entry["capability_label"] is None, entry["route_id"]
            assert "route-access policy" in str(entry["transitional_note"]), entry["route_id"]
        if classification == "bounded_health_docs_surface":
            assert not entry["path"].startswith("/api/v1/"), entry["route_id"]


def test_backend_route_surface_classification_covers_target_live_surfaces() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    live_routes = _collect_live_routes()
    classifications = _surface_classification_by_signature(fixture)

    assert set(classifications) == set(live_routes) | set(DOCS_AND_SCHEMA_ROUTE_CLASSIFICATIONS)
    assert len(classifications) == len(live_routes) + len(DOCS_AND_SCHEMA_ROUTE_CLASSIFICATIONS)
    for signature, expected_classification in EXPECTED_SURFACE_ROUTE_CLASSIFICATIONS.items():
        assert classifications[signature]["surface_classification"] == expected_classification

    for signature, entry in classifications.items():
        if signature in DOCS_AND_SCHEMA_ROUTE_CLASSIFICATIONS:
            continue
        assert signature in live_routes
        entry = classifications[signature]
        live = live_routes[signature]
        expected_dependency = entry["auth_dependency_label"]
        if entry["surface_classification"] == "bounded_auth_endpoint":
            assert signature[1].startswith("/api/v1/auth/")
        elif entry["surface_classification"] == "public_consumer_safe_read":
            assert live["auth_dependency_label"] in {None, "optional_current_user"}
        else:
            assert live["auth_dependency_label"] == (None if expected_dependency == "public" else expected_dependency)
        assert live["capability_label"] == entry["capability_label"]


def test_docs_openapi_and_operator_diagnostic_surfaces_are_not_product_routes() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    classifications = _surface_classification_by_signature(fixture)

    for signature, expected_classification in DOCS_AND_SCHEMA_ROUTE_CLASSIFICATIONS.items():
        entry = classifications[signature]
        assert entry["surface_classification"] == expected_classification
        assert entry["auth_dependency_label"] == "admin_user"
        assert entry["capability_label"] is None
        assert "api.app" in str(entry["transitional_note"])

    for signature in EXPECTED_OPERATOR_DIAGNOSTIC_ROUTE_CLASSIFICATIONS:
        entry = classifications[signature]
        assert entry["surface_classification"] == "operator_diagnostic"
        assert entry["auth_dependency_label"] == "admin_capability"
        assert entry["capability_label"] == "ops:providers:read"
        assert entry["no_go_marker"] is None
        assert entry["transitional_note"]

    for signature, expected_capability in EXPECTED_T1463_MIGRATED_ROUTE_CAPABILITIES.items():
        entry = classifications[signature]
        assert entry["surface_classification"] == "admin_capability"
        assert entry["auth_dependency_label"] == "admin_capability"
        assert entry["capability_label"] == expected_capability
        assert entry["no_go_marker"] is None
        assert entry["transitional_note"]

    assert EXPECTED_LEGACY_ROUTE_SURFACE_CLASSIFICATIONS == set()

    api_v1_doc_like_labels = [
        entry
        for entry in classifications.values()
        if entry["path"].startswith("/api/v1/")
        and entry["surface_classification"] == "bounded_health_docs_surface"
    ]
    assert api_v1_doc_like_labels == []


def test_options_inventory_matches_auth_required_fixture_only_frontend_gate_contract() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    classifications = _surface_classification_by_signature(fixture)
    app_source = APP_TSX.read_text(encoding="utf-8")

    assert len(EXPECTED_OPTIONS_AUTH_REQUIRED_ROUTE_CLASSIFICATIONS) == 11
    for signature in EXPECTED_OPTIONS_AUTH_REQUIRED_ROUTE_CLASSIFICATIONS:
        entry = classifications[signature]
        note = str(entry["transitional_note"])
        note_text = note.lower()
        assert entry["surface_classification"] == "authenticated_member"
        assert entry["auth_dependency_label"] == "authenticated_user"
        assert entry["capability_label"] is None
        assert entry["no_go_marker"] is None
        assert "fixture/demo" in note
        assert "production Options decisioning" in note
        assert "member-gated" in note_text
        assert "route-local dependency" in note_text
        assert "registeredsurfaceroute" in note_text
        assert "policy_adjudication_required" not in note_text
        if signature[0] == "GET":
            concrete_path = signature[1].replace("{symbol}", "TEM")
            assert not is_public_baseline_read(signature[0], concrete_path)

    assert any(
        entry.path == "/options-lab" and entry.wrapper == "RegisteredSurfaceRoute"
        for entry in parse_frontend_route_declarations(app_source)
    )
    assert "routePathname.startsWith('/options-lab')" in app_source
    assert "return <ConsumerProtectedFrame moduleName={moduleName} />;" in app_source


def test_backend_write_only_capabilities_do_not_leak_into_frontend_read_route_flags() -> None:
    frontend_fixture = _load_json(FRONTEND_FIXTURE)
    frontend_capability_labels = {
        entry["capability_label"]
        for entry in frontend_fixture["admin_surface_routes"]
    }
    capability_source = ADMIN_CAPABILITIES_TS.read_text(encoding="utf-8")

    assert FRONTEND_ADMIN_READ_CAPABILITY_LABELS.issubset(frontend_capability_labels)
    assert frontend_capability_labels.isdisjoint(BACKEND_ONLY_WRITE_CAPABILITY_LABELS)
    for capability in BACKEND_ONLY_WRITE_CAPABILITY_LABELS:
        assert capability not in capability_source


def test_request_guarded_auth_routes_remain_explicit_in_auth_endpoint_source() -> None:
    fixture = _load_json(BACKEND_FIXTURE)
    auth_source = AUTH_ENDPOINT_TS.read_text(encoding="utf-8")
    route_inventory, _ = _collect_auth_route_source_inventory(auth_source)

    for entry in fixture["request_guarded_auth_routes"]:
        guard_kind = entry["guard_kind"]
        methods = entry.get("methods") or [entry["method"]]
        if "path_pattern" in entry:
            pattern = re.compile(entry["path_pattern"])
            matched_routes = [
                route
                for route in route_inventory.values()
                if route["method"] in methods and pattern.match(f"/api/v1/auth{route['path']}")
            ]
            assert matched_routes, f"missing auth route pattern {entry['route_id']}"
            for route in matched_routes:
                body = route["body"]
                if guard_kind == "request_current_user":
                    assert (
                        "resolve_current_user(request)" in body
                        or "_serialize_current_user(request)" in body
                        or "_require_admin_current_user(request)" in body
                    ), f"missing request guard in {route['method']} {route['path']}"
        else:
            api_path = entry["path"].replace("/api/v1/auth", "")
            for method in methods:
                route = route_inventory[(method, api_path)]
                body = route["body"]
                if guard_kind == "request_current_user":
                    assert (
                        "resolve_current_user(request)" in body
                        or "_serialize_current_user(request)" in body
                        or "_require_admin_current_user(request)" in body
                    ), f"missing request guard in {entry['path']}"
                else:
                    assert "resolve_current_user(request)" not in body and "_serialize_current_user(request)" not in body
        assert methods


def test_auth_route_source_inventory_is_method_aware_and_fails_closed() -> None:
    auth_source = AUTH_ENDPOINT_TS.read_text(encoding="utf-8")
    route_inventory, special_cases = _collect_auth_route_source_inventory(auth_source)

    assert special_cases == EXPECTED_AUTH_ROUTE_SOURCE_SPECIAL_CASES
    assert {
        route_signature: route["classification"]
        for route_signature, route in route_inventory.items()
    } == EXPECTED_AUTH_ROUTE_SOURCE_INVENTORY


def test_frontend_route_inventory_matches_admin_capability_map_and_wrapper_boundaries() -> None:
    fixture = _load_json(FRONTEND_FIXTURE)
    app_source = APP_TSX.read_text(encoding="utf-8")
    capability_source = ADMIN_CAPABILITIES_TS.read_text(encoding="utf-8")

    declarations = parse_frontend_route_declarations(app_source)
    by_path = {entry.path: entry for entry in declarations}
    admin_wrapped_paths = {entry.path for entry in declarations if entry.wrapper == "AdminSurfaceRoute"}
    registered_wrapped_paths = {entry.path for entry in declarations if entry.wrapper == "RegisteredSurfaceRoute"}

    for entry in fixture["admin_surface_routes"]:
        assert entry["path"] in admin_wrapped_paths
        assert entry["localized_path"] == entry["path"].lstrip("/")
        expected_flag = entry["capability_flag"]
        route_prefix = entry["path"].replace("/:userId", "").replace("/:runId", "")
        if entry["route_id"] == "admin.users.userId.activity":
            assert "const userRouteSuffix = pathname.slice('/admin/users'.length).replace(/^\\/+|\\/+$/g, '');" in capability_source
            assert "segments.length >= 2 && segments[segments.length - 1] === 'activity'" in capability_source
            assert "capabilityFlags.canReadUserActivity" in capability_source
            assert "capabilityFlags.canReadUsers" in capability_source
        elif route_prefix in ADMIN_CAPABILITY_CASES:
            assert ADMIN_CAPABILITY_CASES[route_prefix] == expected_flag
            assert route_prefix in capability_source
            assert expected_flag in capability_source
        assert str(entry["capability_label"]) in capability_source

    for entry in fixture["registered_surface_routes"]:
        assert entry["path"] in registered_wrapped_paths
        assert entry["localized_path"] == entry["path"].lstrip("/")

    for prefix in fixture["guest_redirect_prefixes"]:
        assert prefix in admin_wrapped_paths

    for entry in fixture["public_routes"]:
        assert entry["path"] in by_path
        assert by_path[entry["path"]].wrapper is None

    assert "/market/rotation-radar" not in registered_wrapped_paths
    assert "/market/rotation-radar" not in admin_wrapped_paths
    assert sum(entry.wrapper == "AdminSurfaceRoute" for entry in declarations) == 12
    assert sum(entry.wrapper == "RegisteredSurfaceRoute" for entry in declarations) == 11
    assert by_path["/guest"].wrapper is None
    assert by_path["/market/rotation-radar"].wrapper is None
    assert by_path["/admin/providers"].redirect_to == "/admin/market-providers"

    formatted_source = """
const unrelated = { path: '/ignored', element: <AdminSurfaceRoute><Ignored /></AdminSurfaceRoute> };
const routeDefinitions: AppRouteDefinition[] = [
  {
    placement: 'shell',
    path: '/admin/example',
    element:
      <AdminSurfaceRoute>
        <Example />
      </AdminSurfaceRoute>,
  },
  { placement: 'shell', path: '/member/example', element: <RegisteredSurfaceRoute><Example /></RegisteredSurfaceRoute> },
  { placement: 'shell', path: '/alias', redirectTo: '/member/example', localizedRedirectTo: '../member/example' },
  { placement: 'shell', path: '/public/example', element: <Example /> },
];
"""
    formatted_declarations = parse_frontend_route_declarations(formatted_source)
    assert [(entry.path, entry.wrapper, entry.redirect_to) for entry in formatted_declarations] == [
        ("/admin/example", "AdminSurfaceRoute", None),
        ("/member/example", "RegisteredSurfaceRoute", None),
        ("/alias", None, "/member/example"),
        ("/public/example", None, None),
    ]

    for invalid_source, message in [
        (
            "const routeDefinitions: AppRouteDefinition[] = [{ placement: 'shell', path: '/admin', element: <UnknownSurfaceRoute><Page /></UnknownSurfaceRoute> }];",
            "unknown protected wrapper",
        ),
        (
            "const routeDefinitions: AppRouteDefinition[] = [{ placement: 'shell', path: '/admin', element: <AdminSurfaceRoute><Page /></AdminSurfaceRoute> ",
            "unterminated routeDefinitions array",
        ),
        (
            """const routeDefinitions: AppRouteDefinition[] = [
{ placement: 'shell', path: '/same', element: <AdminSurfaceRoute><Page /></AdminSurfaceRoute> },
{ placement: 'shell', path: '/same', element: <RegisteredSurfaceRoute><Page /></RegisteredSurfaceRoute> },
];""",
            "contradictory protected route declaration",
        ),
        (
            "const routeDefinitions: AppRouteDefinition[] = [{ placement: 'shell', path: '/admin', element: <AdminSurfaceRoute><Page /> }];",
            "unclosed protected wrapper",
        ),
    ]:
        with pytest.raises(FrontendRouteDeclarationError, match=message):
            parse_frontend_route_declarations(invalid_source)

    first = build_frontend_inventory(REPO_ROOT)
    second = build_frontend_inventory(REPO_ROOT)
    assert json.dumps(first, ensure_ascii=False, indent=2, sort_keys=False) == json.dumps(
        second, ensure_ascii=False, indent=2, sort_keys=False
    )
