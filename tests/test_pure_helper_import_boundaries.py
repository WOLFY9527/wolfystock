# -*- coding: utf-8 -*-
"""Static import-boundary guards for inert pure helper modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_MODULES = (
    pytest.param("src/services/data_coverage_matrix_contract.py", False, id="data_coverage_matrix_contract"),
    pytest.param("src/services/data_coverage_matrix_builder.py", False, id="data_coverage_matrix_builder"),
    pytest.param("src/services/backtest_factor_lab_readiness.py", False, id="backtest_factor_lab_readiness"),
    pytest.param(
        "src/services/backtest_factor_lab_consumer_projection.py",
        False,
        id="backtest_factor_lab_consumer_projection",
    ),
    pytest.param("src/services/user_alert_evaluation.py", False, id="user_alert_evaluation"),
    pytest.param("src/services/user_alert_dry_run_pipeline.py", False, id="user_alert_dry_run_pipeline"),
    pytest.param("src/services/data_coverage_surface_registry.py", True, id="data_coverage_surface_registry"),
    pytest.param("src/services/data_coverage_surface_snapshot.py", True, id="data_coverage_surface_snapshot"),
    pytest.param("src/services/data_coverage_matrix_batch.py", True, id="data_coverage_matrix_batch"),
    pytest.param(
        "src/services/backtest_factor_lab_report_summary.py",
        True,
        id="backtest_factor_lab_report_summary",
    ),
    pytest.param("src/services/user_alert_event_packet.py", True, id="user_alert_event_packet"),
    pytest.param("src/services/user_alert_suppression_policy.py", True, id="user_alert_suppression_policy"),
    pytest.param("src/services/user_alert_dry_run_summary.py", True, id="user_alert_dry_run_summary"),
    pytest.param("src/services/research_packet_v1.py", True, id="research_packet_v1"),
)
ALERT_LOCAL_PREVIEW_GUARD_TESTS = (
    "tests/test_user_alert_evaluation.py",
    "tests/test_user_alert_event_packet.py",
    "tests/test_user_alert_dry_run_pipeline.py",
    "tests/test_user_alert_dry_run_summary.py",
    "tests/test_user_alert_dry_run_fixtures.py",
    "tests/test_pure_helper_import_boundaries.py",
)
FORBIDDEN_IMPORT_PREFIXES = {
    "api": (
        "api",
        "fastapi",
        "starlette",
        "server",
    ),
    "provider/runtime": (
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
    ),
    "storage/repositories": (
        "src.repositories",
        "src.storage",
        "src.storage_phase_g_observability",
        "src.storage_postgres_bridge",
        "src.storage_topology_report",
        "src.database_doctor",
        "src.database_doctor_smoke",
        "duckdb",
        "psycopg",
        "redis",
        "sqlalchemy",
        "sqlite3",
    ),
    "analysis/report/history": (
        "src.report_language",
        "src.services.analysis_service",
        "src.services.history_service",
        "src.services.report_renderer",
    ),
    "market-cache": (
        "src.services.market_cache",
        "src.services.market_cache_redis_backend",
    ),
    "cache/runtime": (
        "src.services.observation_cache",
        "src.services.official_macro_liquidity_cache_contracts",
    ),
    "notification": (
        "src.notification",
        "src.services.notification_service",
    ),
    "alert-runtime": (
        "src.services.user_alert_service",
    ),
    "core-runtime": (
        "main",
        "server",
        "src.scheduler",
        "src.core",
        "src.services.litellm_runtime",
        "src.services.task_queue",
    ),
    "frontend": (
        "apps",
    ),
    "env/config": (
        "dotenv",
        "decouple",
        "environs",
        "pydantic_settings",
        "src.config",
    ),
    "network-clients": (
        "aiohttp",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
    ),
}


def _module_name_for_path(path: Path) -> str:
    return ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)


def _matches_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(f"{prefix}.")


def _relative_import_base_parts(module_name: str, level: int) -> list[str]:
    parts = module_name.split(".")
    return parts[:-level] if level else parts


def _collect_imported_modules(path: Path) -> set[str]:
    module_name = _module_name_for_path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level == 0:
            if node.module:
                imported_modules.add(node.module)
                imported_modules.update(
                    f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"
                )
            continue

        base_parts = _relative_import_base_parts(module_name, node.level)
        if node.module:
            imported_base = ".".join(base_parts + node.module.split("."))
            imported_modules.add(imported_base)
            imported_modules.update(
                f"{imported_base}.{alias.name}" for alias in node.names if alias.name != "*"
            )
            continue

        for alias in node.names:
            if alias.name == "*":
                imported_modules.add(".".join(base_parts))
            else:
                imported_modules.add(".".join(base_parts + [alias.name]))

    return imported_modules


def _forbidden_import_hits(imported_modules: set[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for category, prefixes in FORBIDDEN_IMPORT_PREFIXES.items():
        matched = sorted(
            module_name
            for module_name in imported_modules
            if any(_matches_prefix(module_name, prefix) for prefix in prefixes)
        )
        if matched:
            hits[category] = matched
    return hits


@pytest.mark.parametrize(("relative_path", "optional"), TARGET_MODULES)
def test_pure_helper_modules_do_not_import_protected_runtime_domains(
    relative_path: str,
    optional: bool,
) -> None:
    module_path = REPO_ROOT / relative_path
    if optional and not module_path.exists():
        pytest.skip(f"optional pure helper not present yet: {relative_path}")

    assert module_path.exists(), f"required pure helper missing: {relative_path}"

    violations = _forbidden_import_hits(_collect_imported_modules(module_path))
    assert not violations, (
        f"{relative_path} must remain a pure inert helper and avoid protected runtime imports. "
        f"Found forbidden imports: {violations}"
    )


@pytest.mark.parametrize("relative_path", ALERT_LOCAL_PREVIEW_GUARD_TESTS)
def test_alert_local_preview_guard_tests_do_not_import_protected_runtime_domains(relative_path: str) -> None:
    test_path = REPO_ROOT / relative_path
    assert test_path.exists(), f"alert local preview guard test missing: {relative_path}"

    violations = _forbidden_import_hits(_collect_imported_modules(test_path))
    assert not violations, (
        f"{relative_path} must test pure alert helpers without importing protected runtime domains. "
        f"Found forbidden imports: {violations}"
    )
