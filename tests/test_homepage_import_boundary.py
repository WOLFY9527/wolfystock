# -*- coding: utf-8 -*-
"""Static import-boundary guards for standalone homepage services."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
HOMEPAGE_SERVICE_MODULES = (
    "homepage_intelligence_service",
    "homepage_capabilities_service",
    "homepage_module_manifest_service",
    "homepage_demo_payload_service",
    "homepage_explanation_service",
    "market_session_status_service",
    "source_freshness_summary_service",
    "event_window_service",
    "market_pulse_service",
    "money_flow_service",
    "event_radar_service",
    "research_queue_service",
    "personal_summary_service",
    "public_data_quality_service",
)
FORBIDDEN_IMPORT_PREFIXES_BY_CATEGORY = {
    "provider runtime modules": (
        "data_provider",
        "src.providers",
        "src.services.analysis_provider_planner",
        "src.services.cn_hk_connect_flow_provider",
        "src.services.cn_provider_health_service",
        "src.services.market_overview_tickflow_breadth_provider",
        "src.services.market_provider_operations_service",
        "src.services.options_market_data_provider",
        "src.services.polygon_us_breadth_provider",
        "src.services.provider_circuit_observer",
        "src.services.provider_fit_advisor_service",
        "src.services.provider_plan_advisor",
        "src.services.provider_usage_ledger",
        "src.services.rotation_radar_quote_provider",
        "src.services.stock_service_provider_adapter",
        "src.services.market_overview_binance_transport",
        "src.services.market_overview_sentiment_transport",
        "src.services.market_overview_sina_transport",
        "src.services.market_overview_yfinance_transport",
    ),
    "broker/order/trade execution modules": (
        "broker",
        "brokers",
        "order",
        "orders",
        "trade",
        "trades",
        "trading",
        "ib_insync",
        "src.services.broker",
        "src.services.order",
        "src.services.trade",
        "src.services.trading",
        "src.services.portfolio_ibkr_sync_service",
    ),
    "auth/session/RBAC internals": (
        "api.deps",
        "api.middlewares.auth",
        "api.v1.endpoints.auth",
        "src.admin_rbac",
        "src.auth",
        "src.auth_context",
        "src.repositories.auth_repo",
        "src.services.admin_mfa_service",
        "src.services.admin_security_service",
        "src.services.admin_user_onboarding_service",
    ),
    "network clients": (
        "aiohttp",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
    ),
    "direct live providers": (
        "akshare",
        "pytdx",
        "yfinance",
    ),
    "dashboard overview coupling": (
        "src.services.dashboard_overview_service",
    ),
}


def _service_path(module_name: str) -> Path:
    return REPO_ROOT / "src" / "services" / f"{module_name}.py"


def _matches_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(f"{prefix}.")


def _collect_direct_absolute_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level != 0 or not node.module:
            continue

        imported_modules.add(node.module)
        imported_modules.update(
            f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"
        )

    return imported_modules


def _forbidden_import_hits(imported_modules: set[str]) -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}
    for category, prefixes in FORBIDDEN_IMPORT_PREFIXES_BY_CATEGORY.items():
        matches = sorted(
            module_name
            for module_name in imported_modules
            if any(_matches_prefix(module_name, prefix) for prefix in prefixes)
        )
        if matches:
            violations[category] = matches
    return violations


@pytest.mark.parametrize("module_name", HOMEPAGE_SERVICE_MODULES)
def test_homepage_standalone_services_avoid_protected_direct_imports(module_name: str) -> None:
    service_path = _service_path(module_name)
    assert service_path.exists(), f"homepage service missing: {service_path.relative_to(REPO_ROOT)}"

    violations = _forbidden_import_hits(_collect_direct_absolute_imports(service_path))

    assert not violations, (
        f"{service_path.relative_to(REPO_ROOT)} must remain a standalone homepage service "
        "without direct provider runtime, broker/order/trade execution, auth/session/RBAC, "
        "network client, live-provider, or dashboard overview imports. "
        f"Found forbidden imports: {violations}"
    )
