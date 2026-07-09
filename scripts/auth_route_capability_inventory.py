#!/usr/bin/env python3
"""Generate route capability inventory fixtures from repository-owned route policy.

This helper imports the FastAPI route registry and policy modules, but it does
not instantiate the app, open databases, read environment configuration, or
change auth behavior. It exists to keep the legacy fixture shape fresh while
making the route registry and access-policy helpers the maintained authority.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.route_access_policy import is_public_baseline_read  # noqa: E402
from api.v1 import api_v1_router  # noqa: E402


BACKEND_FIXTURE_PATH = Path("tests/fixtures/auth/backend_route_capability_inventory.json")
FRONTEND_FIXTURE_PATH = Path("tests/fixtures/auth/frontend_route_capability_inventory.json")
ADMIN_CAPABILITIES_PATH = Path("apps/dsa-web/src/utils/adminCapabilities.ts")
APP_TSX_PATH = Path("apps/dsa-web/src/App.tsx")

SURFACE_CLASSIFICATION_VOCABULARY = [
    "public_static_docs",
    "public_fixture_analysis",
    "authenticated_member",
    "admin_role_only_legacy",
    "admin_capability_required",
    "operator_diagnostic",
    "debug_or_schema_surface",
    "unclassified",
]

DOCS_AND_SCHEMA_SURFACES = [
    {
        "route_id": "docs.swagger_ui",
        "path": "/docs",
        "method": "GET",
        "surface_classification": "debug_or_schema_surface",
        "auth_dependency_label": "admin_user",
        "capability_label": None,
        "no_go_marker": "TODO/NO-GO: root Swagger UI is not public product ingress when auth is enabled; api.app gates it to admins.",
        "transitional_note": "Root Swagger UI is gated by api.app._require_docs_admin_user when auth is enabled; it is only public when auth is disabled.",
    },
    {
        "route_id": "docs.redoc",
        "path": "/redoc",
        "method": "GET",
        "surface_classification": "debug_or_schema_surface",
        "auth_dependency_label": "admin_user",
        "capability_label": None,
        "no_go_marker": "TODO/NO-GO: root ReDoc is not public product ingress when auth is enabled; api.app gates it to admins.",
        "transitional_note": "Root ReDoc is gated by api.app._require_docs_admin_user when auth is enabled; it is only public when auth is disabled.",
    },
    {
        "route_id": "docs.openapi_schema",
        "path": "/openapi.json",
        "method": "GET",
        "surface_classification": "debug_or_schema_surface",
        "auth_dependency_label": "admin_user",
        "capability_label": None,
        "no_go_marker": "TODO/NO-GO: root OpenAPI schema exposure is admin-gated when auth is enabled and must not be treated as product public ingress.",
        "transitional_note": "Root OpenAPI schema is app-level and guarded by api.app._require_docs_admin_user when auth is enabled.",
    },
]

PUBLIC_SAMPLE_SPECS = [
    (
        "market_overview.indices.optional_user_context",
        "GET",
        "/api/v1/market-overview/indices",
        "market_overview",
        "optional_current_user",
        "Guest-safe route may consume optional user context but must not be relabeled as admin-only.",
    ),
    (
        "market.cn_indices.optional_user_context",
        "GET",
        "/api/v1/market/cn-indices",
        "market",
        "optional_current_user",
        "Guest-safe route must remain outside admin-only capability mapping.",
    ),
    (
        "auth.status.public",
        "GET",
        "/api/v1/auth/status",
        "auth",
        "public",
        "Public auth status probe should not silently become protected.",
    ),
]

ROUTE_GROUP_SPECS = [
    ("agent.member_surface", "agent", "authenticated_user", None, "^/api/v1/agent/(?:skills|stock-research|chat|chat/sessions(?:/\\{session_id\\})?|chat/stream)$", ["GET", "POST", "DELETE"], None),
    ("agent.operator_diagnostics", "agent_operator_diagnostics", "admin_capability", "ops:providers:read", "^/api/v1/agent/(?:status|models|provider-health)$", ["GET"], "Agent readiness, model topology, and provider health diagnostics are provider-read admin surfaces."),
    ("agent.admin_send", "agent_admin_send", "admin_capability", "ops:notifications:write", "^/api/v1/agent/chat/send$", ["POST"], None),
    ("market.scenario_baseline.member_surface", "market_scenario_baseline", "authenticated_user", None, "^/api/v1/market/scenario-lab/baseline-snapshots(?:/latest|/\\{snapshot_id\\})?$", ["GET", "POST"], "Scenario durable baseline endpoints are authenticated-user scoped; evaluation remains separately non-persistent."),
    ("analysis.member_surface", "analysis", "authenticated_user", None, "^/api/v1/analysis/(?:analyze|tasks(?:/\\{task_id\\}/progress|/stream)?|status/\\{task_id\\}(?:/poll)?)$", ["GET", "POST"], None),
    ("history.member_surface", "history", "authenticated_user", None, "^/api/v1/history(?:/\\{record_id\\}(?:/(?:news|markdown))?)?$", ["GET", "DELETE"], None),
    ("backtest.member_surface", "backtest", "authenticated_user", None, "^/api/v1/backtest/(?:run|prepare-samples|sample-status|runs|results|performance(?:/\\{code\\})?|samples/clear|results/clear|rule/(?:parse|parameter-sweep|run|universe-jobs(?:/\\{job_id\\}(?:/(?:run|status|diagnostics|results))?)?|runs(?:/\\{run_id\\}(?:/(?:status|support-bundle-manifest|export-index|support-bundle-reproducibility-manifest|execution-trace\\.json|execution-trace\\.csv|cancel|robustness-evidence\\.json|regime-attribution-readiness\\.json|execution-model-metadata\\.json|oos-parameter-readiness\\.json))?)?|compare))$", ["GET", "POST"], None),
    ("scanner.member_surface", "scanner", "authenticated_user", None, "^/api/v1/scanner(?:/(?:run|runs|themes|strategy-simulation|runs/\\{run_id\\}(?:/research-overlay)?))?$", ["GET", "POST"], None),
    ("research.member_surface", "research", "authenticated_user", None, "^/api/v1/research/(?:radar|queue)$", ["GET"], None),
    ("scanner.admin_watchlists_and_status", "scanner_admin", "admin_capability", "scanner:admin:read", "^/api/v1/scanner/(?:watchlists/(?:today|recent)|status)$", ["GET"], None),
    ("portfolio.member_surface", "portfolio", "authenticated_user", None, "^/api/v1/portfolio/(?:accounts(?:/\\{account_id\\})?|fx-rate(?:/refresh)?|broker-connections(?:/\\{connection_id\\})?|sync/ibkr|trades(?:/\\{trade_id\\})?|cash-ledger(?:/\\{entry_id\\})?|corporate-actions(?:/\\{action_id\\})?|snapshot|history|imports/(?:parse|brokers|commit|csv/parse|csv/brokers|csv/commit)|fx/refresh|risk|scenario-risk|structure-review)$", ["GET", "POST", "PUT", "PATCH", "DELETE"], None),
    ("user_alerts.member_surface", "user_alerts", "authenticated_user", None, "^/api/v1/user-alerts/(?:rules(?:/\\{rule_id\\}(?:/dry-run)?)?|events)$", ["GET", "POST", "PATCH", "DELETE"], None),
    ("watchlist.member_surface", "watchlist", "authenticated_user", None, "^/api/v1/watchlist/(?:$|research-overlay|items(?:/\\{item_id\\})?|items/from-scanner-candidate|refresh-scores|refresh-status)$", ["GET", "POST", "DELETE"], None),
    ("stock.member_surface", "stock", "authenticated_user", None, "^/api/v1/stocks/(?:structure-decisions/batch|\\{stock_code\\}/structure-decision)$", ["GET", "POST"], "Consumer stock structure diagnostics are authenticated-user scoped and not public."),
    ("usage.admin_summary", "usage_admin", "admin_capability", "cost:observability:read", "^/api/v1/usage/summary$", ["GET"], None),
    ("quant.duckdb.read", "quant_duckdb_admin", "admin_capability", "quant:admin:read", "^/api/v1/quant/duckdb/(?:health|factor-snapshot|validate-factor-path|compare-runtime-context|coverage|benchmark)$", ["GET", "POST"], None),
    ("quant.duckdb.write", "quant_duckdb_admin", "admin_capability", "quant:admin:write", "^/api/v1/quant/duckdb/(?:init|ingest-ohlcv|build-factors)$", ["POST"], None),
    ("quant.factor_research.read", "quant_factor_research_admin", "admin_capability", "quant:admin:read", "^/api/v1/quant/factor-research/report$", ["POST"], None),
    ("admin.users.read", "admin_user_governance", "admin_capability", "users:read", "^/api/v1/admin/users(?:/\\{user_id\\})?$", ["GET"], None),
    ("admin.users.activity_read", "admin_activity", "admin_capability", "users:activity:read", "^/api/v1/admin/users/\\{user_id\\}/activity$", ["GET"], None),
    ("admin.users.portfolio_read", "admin_user_portfolio", "admin_capability", "users:portfolio:read", "^/api/v1/admin/users/\\{user_id\\}/(?:portfolio-summary|holdings|portfolio-activity|portfolio/accounts/\\{account_id\\})$", ["GET"], None),
    ("admin.users.security_write", "admin_user_security", "admin_capability", "users:security:write", "^/api/v1/admin/users(?:/onboard|/\\{user_id\\}/(?:disable|enable|revoke-sessions))$", ["POST"], "Capability is discoverable through a wrapper helper that also enforces recent admin reauthentication."),
    ("admin.activity.read", "admin_activity", "admin_capability", "users:activity:read", "^/api/v1/admin/activity$", ["GET"], None),
    ("admin.logs.read", "admin_logs", "admin_capability", "ops:logs:read", "^/api/v1/admin/(?:launch-cockpit|logs(?:/storage/summary|/incident-timeline|/data-missing-drilldown|/operator-issue-rollup|/sessions(?:/\\{session_id\\})?|/\\{event_id\\})?)$", ["GET"], None),
    ("admin.logs.write", "admin_logs", "admin_capability", "ops:logs:write", "^/api/v1/admin/logs/cleanup$", ["POST"], None),
    ("admin.ops.status", "admin_ops_status", "admin_capability", "ops:logs:read", "^/api/v1/admin/(?:ops(?:/(?:status|surface-readiness|scanner-universe-readiness|scanner-universe-refresh))?|ops-status|scanner/universe-readiness)$", ["GET", "POST"], None),
    ("admin.mission_control", "admin_mission_control", "admin_capability", "ops:logs:read", "^/api/v1/admin/mission-control$", ["GET"], None),
    ("admin.notifications.read", "admin_notifications", "admin_capability", "ops:notifications:read", "^/api/v1/admin/(?:notification-channels|notifications)$", ["GET"], None),
    ("admin.notifications.write", "admin_notifications", "admin_capability", "ops:notifications:write", "^/api/v1/admin/(?:notification-channels(?:/\\{channel_id\\}(?:/test)?)?|notifications/\\{event_id\\}/ack)$", ["POST", "PATCH", "DELETE"], None),
    ("admin.cost.read", "admin_cost_observability", "admin_capability", "cost:observability:read", "^/api/v1/admin/cost/(?:duplicate-summary|summary|quota-dry-run|llm-ledger-summary|model-pricing-policies)$", ["GET", "POST"], None),
    ("admin.providers.read", "admin_provider_observability", "admin_capability", "ops:providers:read", "^/api/v1/admin/(?:(?:providers/(?:circuits(?:/events)?|quota-windows|probe-events|sla-readiness|operations-matrix)|provider-circuits|provider-usage-ledger)|market-providers(?:/operations)?|market-provider-operations|provider-operations|provider-activation-verifier|historical-ohlcv/(?:cache-preflight(?:/seed)?|us-cache-refresh))$", ["GET", "POST"], None),
    ("market.professional_data_capabilities_admin", "market_professional_data_capabilities_admin", "admin_capability", "ops:providers:read", "^/api/v1/market/professional-data-capabilities/admin$", ["GET"], "Professional data capability inventory is provider-read admin gated and not public."),
    ("market.provider_fit_advisor", "market_provider_fit_advisor", "admin_capability", "ops:providers:read", "^/api/v1/market/provider-fit-advisor$", ["GET"], "Deprecated hidden provider-fit diagnostic route under the market namespace; capability-gated and not public-safe."),
    ("market.operator_diagnostics", "market_operator_diagnostics", "admin_capability", "ops:providers:read", "^/api/v1/market/(?:data-readiness|data-source-gap-registry|cn-provider-health)$", ["GET"], "Operator market diagnostics remain available to provider-read admins and are no longer anonymous consumer surfaces."),
    ("system.config.read", "system_config", "admin_capability", "ops:system_config:read", "^/api/v1/system/config(?:/schema)?$", ["GET"], None),
    ("system.config.validate", "system_config", "admin_capability", "ops:system_config:read", "^/api/v1/system/config/validate$", ["POST"], None),
    ("system.config.write", "system_config", "admin_capability", "ops:system_config:write", "^/api/v1/system/(?:config|actions/(?:runtime-cache/reset|factory-reset))$", ["PUT", "POST"], None),
    ("system.provider_tests.write", "system_provider_tests", "admin_capability", "ops:providers:write", "^/api/v1/system/config/(?:llm/test-channel|data-source/test|data-source/test-builtin)$", ["POST"], None),
]

OPTION_FIXTURE_MARKER = (
    "TODO/NO-GO: authenticated Options research surface remains fixture/demo analysis only; "
    "production Options decisioning needs accepted real provider evidence before launch."
)
OPTION_POLICY_NOTE = (
    "Member-gated by production app-level AuthMiddleware and frontend RegisteredSurfaceRoute; "
    "route-local fixture handlers remain read-only observation-only contracts."
)


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
    return match.group(1) if match else None


def _route_auth_metadata(route: APIRoute) -> dict[str, str | None]:
    dependency_label: str | None = None
    capability_label: str | None = None
    for dependency in route.dependant.dependencies:
        call = getattr(dependency, "call", None)
        name = getattr(call, "__name__", "") or ""
        qualname = getattr(call, "__qualname__", "") or ""
        capability = _extract_capability_from_call(call)
        if capability:
            return {"auth_dependency_label": "admin_capability", "capability_label": capability}
        if name == "require_admin_user":
            dependency_label = dependency_label or "admin_user"
        elif name == "get_current_user":
            dependency_label = dependency_label or "authenticated_user"
        elif name == "get_optional_current_user":
            dependency_label = dependency_label or "optional_current_user"
        elif "require_admin_capability" in qualname:
            return {"auth_dependency_label": "admin_capability", "capability_label": capability_label}
    return {"auth_dependency_label": dependency_label, "capability_label": capability_label}


def _iter_effective_routes(routes: list[Any]):
    for route in routes:
        if isinstance(route, APIRoute) or (
            hasattr(route, "dependant") and hasattr(route, "methods") and hasattr(route, "path")
        ):
            yield route
            continue
        effective_candidates = getattr(route, "effective_candidates", None)
        if callable(effective_candidates):
            yield from _iter_effective_routes(list(effective_candidates()))


def collect_live_routes() -> dict[tuple[str, str], dict[str, str | None]]:
    collected: dict[tuple[str, str], dict[str, str | None]] = {}
    for route in _iter_effective_routes(api_v1_router.routes):
        metadata = _route_auth_metadata(route)
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            collected[(method, route.path)] = {"method": method, "path": route.path, **metadata}
    return dict(sorted(collected.items()))


def _route_matches_group(route: dict[str, str | None], group: dict[str, Any]) -> bool:
    return (
        route["auth_dependency_label"] == group["auth_dependency_label"]
        and route["method"] in set(group["methods"])
        and group["capability_label"] == route["capability_label"]
        and re.match(group["path_pattern"], route["path"] or "") is not None
    )


def _route_id_from_path(path: str) -> str:
    normalized = path.strip("/").replace("/api/v1/", "").replace("/", ".")
    normalized = normalized.replace("{", "").replace("}", "").replace("-", "_")
    return normalized or "root"


def _public_dependency_label(method: str, path: str, route_auth_label: str | None) -> str:
    if route_auth_label == "optional_current_user":
        return "optional_current_user"
    return "public" if route_auth_label is None or is_public_baseline_read(method, path) else str(route_auth_label)


def _surface_entry(
    *,
    route_id: str,
    method: str,
    path: str,
    surface_classification: str,
    auth_dependency_label: str,
    capability_label: str | None,
    no_go_marker: str | None,
    transitional_note: str | None,
) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "path": path,
        "method": method,
        "surface_classification": surface_classification,
        "auth_dependency_label": auth_dependency_label,
        "capability_label": capability_label,
        "no_go_marker": no_go_marker,
        "transitional_note": transitional_note,
    }


def _build_protected_groups(live_routes: dict[tuple[str, str], dict[str, str | None]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    covered: set[tuple[str, str]] = set()
    for route_id, surface, auth_label, capability, pattern, methods, note in ROUTE_GROUP_SPECS:
        group = {
            "route_id": route_id,
            "path_pattern": pattern,
            "methods": methods,
            "surface": surface,
            "auth_dependency_label": auth_label,
            "capability_label": capability,
            "transitional_note": note,
        }
        matches = [
            (route["method"], route["path"] or "")
            for route in live_routes.values()
            if _route_matches_group(route, group)
        ]
        if matches:
            covered.update(matches)
            groups.append(group)

    protected = {
        (route["method"], route["path"] or "")
        for route in live_routes.values()
        if route["auth_dependency_label"] in {"authenticated_user", "admin_user", "admin_capability"}
    }
    unmatched = sorted(protected - covered)
    if unmatched:
        raise RuntimeError(f"route group specs do not cover protected routes: {unmatched}")
    return groups


def _build_public_samples(live_routes: dict[tuple[str, str], dict[str, str | None]]) -> list[dict[str, Any]]:
    samples = []
    for route_id, method, path, surface, expected_label, note in PUBLIC_SAMPLE_SPECS:
        route = live_routes[(method, path)]
        auth_label = _public_dependency_label(method, path, route["auth_dependency_label"])
        if auth_label != expected_label:
            raise RuntimeError(f"unexpected public sample label for {method} {path}: {auth_label}")
        samples.append(
            {
                "route_id": route_id,
                "path": path,
                "method": method,
                "surface": surface,
                "auth_dependency_label": expected_label,
                "capability_label": None,
                "transitional_note": note,
            }
        )
    return samples


def _surface_classification_for_route(route: dict[str, str | None]) -> tuple[str, str | None, str | None]:
    method = str(route["method"])
    path = str(route["path"])
    auth_label = route["auth_dependency_label"]
    if path.startswith("/api/v1/options/"):
        return "authenticated_member", OPTION_FIXTURE_MARKER, OPTION_POLICY_NOTE
    if path.startswith("/api/v1/agent/"):
        if path in {"/api/v1/agent/status", "/api/v1/agent/models", "/api/v1/agent/provider-health"}:
            if auth_label == "admin_capability":
                return "operator_diagnostic", None, "Provider-read admin capability gate preserves agent operator diagnostics outside member product surfaces."
            if auth_label is None:
                return "operator_diagnostic", f"TODO/NO-GO: {path} metadata is not public-ingress safe while route-level auth remains absent.", "Classifies readiness metadata only; no agent behavior changes."
        if auth_label is None:
            return "unclassified", "TODO/NO-GO: decide whether agent skill discovery is public metadata, member-only product metadata, or operator diagnostic metadata.", "Listed explicitly so unknown agent metadata is not silently treated as safe."
    if auth_label == "admin_capability":
        if path in {
            "/api/v1/market/data-readiness",
            "/api/v1/market/data-source-gap-registry",
            "/api/v1/market/cn-provider-health",
        }:
            return "operator_diagnostic", None, "Provider-read admin gate preserves operator diagnostics outside consumer market responses."
        return "admin_capability_required", None, "Capability-gated route projected from live FastAPI dependency metadata."
    if auth_label == "authenticated_user":
        return "authenticated_member", None, None
    if method == "GET" and path == "/api/v1/stocks/{stock_code}/quote":
        return "unclassified", "TODO/NO-GO: stock quote route-level public policy is recorded explicitly here; do not treat it as a beta-safe authenticated member route without a separate quote auth decision.", "Inventory records the current route-level public stock quote policy without changing provider runtime or quote auth behavior."
    return "unclassified", "TODO/NO-GO: route requires explicit surface classification before it can be treated as public-safe.", None


def _include_surface_route(path: str) -> bool:
    return (
        path.startswith("/api/v1/agent/")
        or path.startswith("/api/v1/scanner/")
        or path.startswith("/api/v1/options/")
        or path.startswith("/api/v1/research/")
        or path.startswith("/api/v1/user-alerts/")
        or path.startswith("/api/v1/stocks/")
        or path.startswith("/api/v1/watchlist/")
        or path == "/api/v1/usage/summary"
        or path.startswith("/api/v1/admin/")
        or path.startswith("/api/v1/system/")
        or path.startswith("/api/v1/market/")
        or path.startswith("/api/v1/quant/duckdb/")
    )


def _build_surface_classifications(live_routes: dict[tuple[str, str], dict[str, str | None]]) -> list[dict[str, Any]]:
    entries = list(DOCS_AND_SCHEMA_SURFACES)
    for (method, path), route in live_routes.items():
        if not _include_surface_route(path):
            continue
        classification, no_go, note = _surface_classification_for_route(route)
        auth_label = _public_dependency_label(method, path, route["auth_dependency_label"])
        if path.startswith("/api/v1/options/") and classification == "authenticated_member":
            auth_label = "authenticated_user"
        elif classification == "public_fixture_analysis":
            auth_label = "public"
        entries.append(
            _surface_entry(
                route_id=_route_id_from_path(path),
                method=method,
                path=path,
                surface_classification=classification,
                auth_dependency_label=auth_label,
                capability_label=route["capability_label"],
                no_go_marker=no_go,
                transitional_note=note,
            )
        )
    deduped = {(entry["method"], entry["path"]): entry for entry in entries}
    return [deduped[key] for key in sorted(deduped)]


def _collect_auth_route_source_inventory() -> list[dict[str, Any]]:
    return [
        {"route_id": "auth.status", "path": "/api/v1/auth/status", "method": "GET", "guard_kind": "public"},
        {"route_id": "auth.me", "path": "/api/v1/auth/me", "method": "GET", "guard_kind": "request_current_user"},
        {"route_id": "auth.notification_preferences.read", "path": "/api/v1/auth/preferences/notifications", "method": "GET", "guard_kind": "request_current_user"},
        {"route_id": "auth.notification_preferences.write", "path": "/api/v1/auth/preferences/notifications", "method": "PUT", "guard_kind": "request_current_user"},
        {"route_id": "auth.reauth", "path": "/api/v1/auth/reauth", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.mfa_enroll_start", "path": "/api/v1/auth/mfa/enroll/start", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.mfa_enroll_verify", "path": "/api/v1/auth/mfa/enroll/verify", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.mfa_verify", "path": "/api/v1/auth/mfa/verify", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.mfa_disable", "path": "/api/v1/auth/mfa/disable", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.mfa_recovery_generate", "path": "/api/v1/auth/mfa/recovery-codes/generate", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.mfa_recovery_verify", "path": "/api/v1/auth/mfa/recovery-codes/verify", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.mfa_recovery_rotate", "path": "/api/v1/auth/mfa/recovery-codes/rotate", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.verify_password", "path": "/api/v1/auth/verify-password", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.settings", "path": "/api/v1/auth/settings", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.login", "path": "/api/v1/auth/login", "method": "POST", "guard_kind": "public"},
        {"route_id": "auth.reset_password_request", "path": "/api/v1/auth/reset-password/request", "method": "POST", "guard_kind": "public"},
        {"route_id": "auth.change_password", "path": "/api/v1/auth/change-password", "method": "POST", "guard_kind": "request_current_user"},
        {"route_id": "auth.logout", "path": "/api/v1/auth/logout", "method": "POST", "guard_kind": "request_current_user"},
    ]


def build_backend_inventory(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    _ = Path(repo_root)
    live_routes = collect_live_routes()
    return {
        "protected_groups": _build_protected_groups(live_routes),
        "public_samples": _build_public_samples(live_routes),
        "surface_classification_vocabulary": SURFACE_CLASSIFICATION_VOCABULARY,
        "route_surface_classifications": _build_surface_classifications(live_routes),
        "request_guarded_auth_routes": _collect_auth_route_source_inventory(),
        "metadata": {
            "generator": "scripts/auth_route_capability_inventory.py",
            "authority": [
                "api/v1/router.py",
                "FastAPI APIRoute dependency metadata",
                "api/route_access_policy.py",
                "api/app.py docs gate",
            ],
            "runtimeBehaviorChanged": False,
            "authBehaviorChanged": False,
        },
    }


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _collect_route_paths(source: str, wrapper_name: str) -> list[str]:
    pattern = re.compile(rf'<Route\s+path="([^"]+)"\s+element={{<{wrapper_name}>', re.MULTILINE)
    return sorted({match.group(1) for match in pattern.finditer(source)})


def _flag_capability_map(source: str) -> dict[str, str]:
    match = re.search(r"const\s+capabilityByFlag:[^{]+=\s*\{(?P<body>.*?)\};", source, flags=re.DOTALL)
    if not match:
        return {}
    return {
        item.group("flag"): item.group("capability")
        for item in re.finditer(r"(?P<flag>can[A-Za-z0-9_]+):\s*'(?P<capability>[^']+)'", match.group("body"))
    }


def _frontend_gate_rules(source: str) -> dict[str, str]:
    rules: dict[str, str] = {}
    for match in re.finditer(
        r"if\s*\(\s*pathname\s*===\s*'(?P<path>[^']+)'\s*\|\|\s*pathname\.startsWith\('(?P=path)/'\)\s*,?\s*\)\s*\{\s*return\s+capabilityFlags\.(?P<flag>can[A-Za-z0-9_]+);",
        source,
        flags=re.DOTALL,
    ):
        rules[match.group("path")] = match.group("flag")
    if "isAdminLaunchCockpitPath(pathname)" in source:
        rules["/admin/launch-cockpit"] = "canReadOpsLogs"
    if "isAdminMissionControlPath(pathname)" in source:
        rules["/admin/mission-control"] = "canReadOpsLogs"
    if "pathname === '/admin/users'" in source and "segments[segments.length - 1] === 'activity'" in source:
        rules["/admin/users"] = "canReadUsers"
        rules["/admin/users/:userId"] = "canReadUsers"
        rules["/admin/users/:userId/activity"] = "canReadUserActivity"
    if "pathname === '/admin/market-providers'" in source and "capabilityFlags.canReadProviders" in source:
        rules["/admin/market-providers"] = "canReadProviders"
    if "pathname === '/admin/provider-operations'" in source and "capabilityFlags.canReadProviders" in source:
        rules["/admin/provider-operations"] = "canReadProviders"
    return rules


def _frontend_route_id(path: str) -> str:
    normalized = path.strip("/").replace("/", ".").replace(":", "")
    return normalized.replace("-", "_") or "root"


def build_frontend_inventory(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    root = Path(repo_root)
    app_source = _read_source(root / APP_TSX_PATH)
    capability_source = _read_source(root / ADMIN_CAPABILITIES_PATH)
    flag_capabilities = _flag_capability_map(capability_source)
    gate_rules = _frontend_gate_rules(capability_source)

    admin_routes = []
    for path in _collect_route_paths(app_source, "AdminSurfaceRoute"):
        if not path.startswith("/"):
            continue
        flag = gate_rules.get(path)
        admin_routes.append(
            {
                "route_id": _frontend_route_id(path),
                "path": path,
                "localized_path": path.lstrip("/"),
                "capability_flag": flag,
                "capability_label": flag_capabilities.get(flag or ""),
            }
        )

    registered_routes = []
    for path in _collect_route_paths(app_source, "RegisteredSurfaceRoute"):
        if path.startswith("/"):
            registered_routes.append(
                {"route_id": _frontend_route_id(path), "path": path, "localized_path": path.lstrip("/")}
            )

    public_routes = [
        {"route_id": "guest_home", "path": "/guest", "localized_path": "guest"},
        {"route_id": "market_rotation_radar", "path": "/market/rotation-radar", "localized_path": "market/rotation-radar"},
    ]
    return {
        "admin_surface_routes": admin_routes,
        "registered_surface_routes": registered_routes,
        "guest_paywall_routes": [
            {"route_id": route["route_id"], "path": route["path"], "localized_path": route["localized_path"], "test_probe": f"renderAt('{route['path']}')"}
            for route in registered_routes
            if route["path"] in {"/scanner", "/portfolio", "/backtest", "/options-lab", "/scenario-lab", "/watchlist", "/research/radar"}
        ],
        "guest_redirect_prefixes": [route["path"] for route in admin_routes],
        "public_routes": public_routes,
        "metadata": {
            "generator": "scripts/auth_route_capability_inventory.py",
            "authority": [
                "apps/dsa-web/src/App.tsx",
                "apps/dsa-web/src/utils/adminCapabilities.ts",
            ],
        },
    }


def write_fixtures(repo_root: Path | str = REPO_ROOT) -> None:
    root = Path(repo_root)
    outputs = {
        root / BACKEND_FIXTURE_PATH: build_backend_inventory(root),
        root / FRONTEND_FIXTURE_PATH: build_frontend_inventory(root),
    }
    for path, payload in outputs.items():
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate auth route capability inventory fixtures.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--fixture", choices=("backend", "frontend", "both"), default="both")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.write:
        write_fixtures(args.repo_root)
        return 0
    if args.fixture == "backend":
        payload: Any = build_backend_inventory(args.repo_root)
    elif args.fixture == "frontend":
        payload = build_frontend_inventory(args.repo_root)
    else:
        payload = {
            "backend": build_backend_inventory(args.repo_root),
            "frontend": build_frontend_inventory(args.repo_root),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
