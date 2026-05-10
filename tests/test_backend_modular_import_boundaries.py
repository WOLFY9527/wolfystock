# -*- coding: utf-8 -*-
"""Inventory guard for current backend modular import boundaries."""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
CONTRACTS_ROOT = SRC_ROOT / "contracts"
SERVICES_ROOT = SRC_ROOT / "services"
ACTIVE_CONTRACT_NAMESPACES = {"data_quality", "evidence"}
INACTIVE_BACKEND_NAMESPACE_MODULES = (
    "src.platform",
    "src.domains",
)
PROVIDER_PRIMITIVE_MODULE_CANDIDATES = (
    "src.providers.types",
    "src.providers.errors",
    "src.providers.policy",
)
FORBIDDEN_PROVIDER_RUNTIME_PREFIXES = (
    "data_provider",
    "src.services.market_cache",
    "src.services.analysis_provider_planner",
    "src.services.market_scanner_service",
    "src.services.market_rotation_radar_service",
    "src.services.options_lab_service",
    "src.services.rule_backtest_service",
    "src.services.portfolio_service",
    "src.services.portfolio_risk_diagnostics",
    "api.v1.endpoints",
    "openai",
    "litellm",
    "requests",
    "httpx",
    "pandas",
)
EXPECTED_API_UPWARD_IMPORT_SERVICE_FILES = {
    "src/services/admin_activity_service.py",
    "src/services/admin_portfolio_service.py",
    "src/services/admin_user_service.py",
    "src/services/duplicate_cost_summary_service.py",
    "src/services/options_lab_service.py",
}
API_UPWARD_IMPORT_PATTERN = re.compile(
    r"^\s*(?:from|import)\s+api\.v1(?:\.schemas|\.endpoints|\b)",
    re.MULTILINE,
)


def _contracts_child_namespaces() -> set[str]:
    return {
        path.name
        for path in CONTRACTS_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }


def _existing_provider_primitive_modules() -> tuple[str, ...]:
    modules: list[str] = []
    for module_name in PROVIDER_PRIMITIVE_MODULE_CANDIDATES:
        module_path = REPO_ROOT / f"{module_name.replace('.', '/')}.py"
        if module_path.exists():
            modules.append(module_name)
    return tuple(modules)


def _import_in_subprocess(module_name: str, tracked_prefixes: tuple[str, ...]) -> set[str]:
    script = f"""
import importlib
import json
import sys

module_name = {module_name!r}
tracked_prefixes = {tracked_prefixes!r}

importlib.import_module(module_name)

loaded_modules = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in tracked_prefixes)
)
print(json.dumps({{"loaded_modules": loaded_modules}}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    return set(payload["loaded_modules"])


def _has_loaded_prefix(loaded_modules: set[str], prefix: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for name in loaded_modules)


def _services_with_api_upward_imports() -> set[str]:
    matches: set[str] = set()
    for service_file in SERVICES_ROOT.rglob("*.py"):
        if API_UPWARD_IMPORT_PATTERN.search(service_file.read_text(encoding="utf-8")):
            matches.add(service_file.relative_to(REPO_ROOT).as_posix())
    return matches


def test_platform_and_domains_namespaces_are_not_active_yet() -> None:
    for module_name in INACTIVE_BACKEND_NAMESPACE_MODULES:
        assert importlib.util.find_spec(module_name) is None, (
            f"{module_name} must stay absent until an explicit boundary plan "
            "lands with focused architecture tests"
        )


def test_contracts_namespace_remains_limited_to_inert_evidence_and_data_quality() -> None:
    from src import contracts

    assert _contracts_child_namespaces() == ACTIVE_CONTRACT_NAMESPACES, (
        "src.contracts should remain limited to inert evidence/data_quality "
        "namespaces until a reviewed boundary plan lands"
    )
    assert set(contracts.__all__) == ACTIVE_CONTRACT_NAMESPACES


def test_provider_primitives_stay_lightweight() -> None:
    tracked_prefixes = tuple(
        sorted(set(_existing_provider_primitive_modules()) | set(FORBIDDEN_PROVIDER_RUNTIME_PREFIXES))
    )

    for module_name in _existing_provider_primitive_modules():
        loaded_modules = _import_in_subprocess(module_name, tracked_prefixes)

        assert module_name in loaded_modules, f"expected to import {module_name}"
        for forbidden_prefix in FORBIDDEN_PROVIDER_RUNTIME_PREFIXES:
            assert not _has_loaded_prefix(
                loaded_modules,
                forbidden_prefix,
            ), (
                f"{module_name} unexpectedly imported runtime-heavy dependency "
                f"{forbidden_prefix}"
            )


def test_api_schema_upward_import_inventory_is_explicit() -> None:
    matched_files = _services_with_api_upward_imports()

    assert matched_files == EXPECTED_API_UPWARD_IMPORT_SERVICE_FILES, (
        "New src.services -> api.v1 upward imports require explicit architecture review. "
        f"Expected {sorted(EXPECTED_API_UPWARD_IMPORT_SERVICE_FILES)}, "
        f"found {sorted(matched_files)}"
    )
