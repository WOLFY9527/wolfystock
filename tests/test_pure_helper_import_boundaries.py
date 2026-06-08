# -*- coding: utf-8 -*-
"""Static import-boundary guards for inert pure helper modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_MODULES = (
    pytest.param("src/services/data_coverage_matrix_contract.py", False, id="data_coverage_matrix_contract"),
    pytest.param("src/services/backtest_factor_lab_readiness.py", False, id="backtest_factor_lab_readiness"),
    pytest.param("src/services/user_alert_evaluation.py", False, id="user_alert_evaluation"),
    pytest.param("src/services/data_coverage_surface_registry.py", True, id="data_coverage_surface_registry"),
    pytest.param("src/services/user_alert_event_packet.py", True, id="user_alert_event_packet"),
    pytest.param("src/services/user_alert_suppression_policy.py", True, id="user_alert_suppression_policy"),
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
    ),
    "storage/repositories": (
        "src.repositories",
        "src.storage",
        "duckdb",
        "psycopg",
        "redis",
        "sqlalchemy",
        "sqlite3",
    ),
    "market-cache": (
        "src.services.market_cache",
        "src.services.market_cache_redis_backend",
    ),
    "notification": (
        "src.notification",
        "src.services.notification_service",
    ),
    "core-runtime": (
        "main",
        "src.core",
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
            continue

        base_parts = _relative_import_base_parts(module_name, node.level)
        if node.module:
            imported_modules.add(".".join(base_parts + node.module.split(".")))
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
