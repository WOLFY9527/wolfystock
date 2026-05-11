# -*- coding: utf-8 -*-
"""Inventory guard for current backend modular import boundaries."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
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
FORBIDDEN_LLM_HELPER_RUNTIME_PREFIXES = (
    "api.v1.endpoints",
    "src.core.pipeline",
    "src.agent",
    "src.services.market_cache",
    "src.services.market_scanner_service",
    "src.services.market_rotation_radar_service",
    "src.services.options_lab_service",
    "src.services.rule_backtest_service",
    "src.services.portfolio_service",
    "src.services.portfolio_risk_diagnostics",
    "data_provider",
    "src.providers",
    "requests",
    "httpx",
    "openai",
    "pandas",
)
LLM_HELPER_IMPORT_GUARD_CASES = (
    {
        "module_name": "src.services.llm_instrumentation",
        "forbidden_prefixes": FORBIDDEN_LLM_HELPER_RUNTIME_PREFIXES,
        "allowed_implementation_prefixes": (),
    },
    {
        "module_name": "src.services.litellm_runtime",
        "forbidden_prefixes": FORBIDDEN_LLM_HELPER_RUNTIME_PREFIXES,
        # This helper is the dedicated LiteLLM import boundary, so the guard
        # intentionally does not forbid litellm itself here.
        "allowed_implementation_prefixes": ("litellm",),
    },
)
ARCH_REVIEW_MESSAGE = "new service-to-API upward imports require explicit architecture review."
EXPECTED_API_SCHEMA_UPWARD_IMPORTS = {
    "src/services/admin_activity_service.py": {"api.v1.schemas.admin_activity"},
    "src/services/admin_portfolio_service.py": {"api.v1.schemas.admin_portfolio"},
    "src/services/admin_user_service.py": {"api.v1.schemas.admin_users"},
    "src/services/duplicate_cost_summary_service.py": {"api.v1.schemas.admin_cost"},
    "src/services/options_lab_service.py": {"api.v1.schemas.options"},
}
# These CurrentUser imports already exist on origin/main; keep the inventory
# explicit until a separate architecture task moves them behind a lower layer.
EXPECTED_LEGACY_API_DEPS_IMPORTS = {
    "src/services/admin_governance_audit_service.py": {"api.deps"},
    "src/services/admin_security_service.py": {"api.deps"},
}
EXPECTED_SERVICE_API_IMPORTS = {
    **EXPECTED_API_SCHEMA_UPWARD_IMPORTS,
    **EXPECTED_LEGACY_API_DEPS_IMPORTS,
}
FORBIDDEN_SERVICE_API_PREFIXES = (
    "api.v1.endpoints",
)


@dataclass(frozen=True)
class ApiImportRecord:
    module: str
    imported_names: tuple[str, ...]
    wildcard: bool = False


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


@lru_cache(maxsize=1)
def _service_api_import_records() -> dict[str, tuple[ApiImportRecord, ...]]:
    matches: dict[str, tuple[ApiImportRecord, ...]] = {}
    for service_file in SERVICES_ROOT.rglob("*.py"):
        tree = ast.parse(service_file.read_text(encoding="utf-8"), filename=str(service_file))
        records: list[ApiImportRecord] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "api" or alias.name.startswith("api."):
                        records.append(ApiImportRecord(module=alias.name, imported_names=(alias.name,)))
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if node.level == 0 and (module_name == "api" or module_name.startswith("api.")):
                    imported_names = tuple(alias.name for alias in node.names)
                    records.append(
                        ApiImportRecord(
                            module=module_name,
                            imported_names=imported_names,
                            wildcard=any(name == "*" for name in imported_names),
                        )
                    )
        if records:
            matches[service_file.relative_to(REPO_ROOT).as_posix()] = tuple(records)
    return matches


def _service_api_import_mapping() -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for service_file, records in _service_api_import_records().items():
        mapping[service_file] = {record.module for record in records}
    return mapping


def _is_forbidden_api_surface(module_name: str) -> bool:
    if any(
        module_name == prefix or module_name.startswith(prefix + ".")
        for prefix in FORBIDDEN_SERVICE_API_PREFIXES
    ):
        return True
    return module_name == "api.v1" or module_name == "api.v1.schemas"


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


def test_llm_helper_modules_stay_lightweight() -> None:
    for case in LLM_HELPER_IMPORT_GUARD_CASES:
        module_name = case["module_name"]
        forbidden_prefixes = tuple(case["forbidden_prefixes"])
        tracked_prefixes = tuple(
            sorted(
                {
                    module_name,
                    *forbidden_prefixes,
                    *case["allowed_implementation_prefixes"],
                }
            )
        )

        loaded_modules = _import_in_subprocess(module_name, tracked_prefixes)

        assert module_name in loaded_modules, f"expected to import {module_name}"
        for forbidden_prefix in forbidden_prefixes:
            assert not _has_loaded_prefix(loaded_modules, forbidden_prefix), (
                f"{module_name} unexpectedly imported runtime-heavy dependency "
                f"{forbidden_prefix}"
            )


def test_api_schema_upward_import_mapping_is_explicit() -> None:
    actual_mapping = {
        service_file: modules
        for service_file, modules in _service_api_import_mapping().items()
        if any(module.startswith("api.v1.schemas.") for module in modules)
    }

    assert actual_mapping == EXPECTED_API_SCHEMA_UPWARD_IMPORTS, (
        f"{ARCH_REVIEW_MESSAGE} "
        f"Expected {EXPECTED_API_SCHEMA_UPWARD_IMPORTS}, found {actual_mapping}"
    )


def test_service_api_upward_import_inventory_is_frozen() -> None:
    actual_mapping = _service_api_import_mapping()

    assert actual_mapping == EXPECTED_SERVICE_API_IMPORTS, (
        f"{ARCH_REVIEW_MESSAGE} "
        f"Expected {EXPECTED_SERVICE_API_IMPORTS}, found {actual_mapping}"
    )


def test_services_do_not_import_forbidden_api_surfaces() -> None:
    forbidden_imports = {
        service_file: sorted(
            {
                record.module
                for record in records
                if _is_forbidden_api_surface(record.module)
            }
        )
        for service_file, records in _service_api_import_records().items()
    }
    forbidden_imports = {
        service_file: modules
        for service_file, modules in forbidden_imports.items()
        if modules
    }

    assert not forbidden_imports, (
        f"{ARCH_REVIEW_MESSAGE} Forbidden API import surfaces: {forbidden_imports}"
    )


def test_services_do_not_use_api_schema_wildcard_imports() -> None:
    wildcard_imports = {
        service_file: sorted(
            {
                record.module
                for record in records
                if record.wildcard and record.module.startswith("api.v1.schemas")
            }
        )
        for service_file, records in _service_api_import_records().items()
    }
    wildcard_imports = {
        service_file: modules
        for service_file, modules in wildcard_imports.items()
        if modules
    }

    assert not wildcard_imports, (
        f"{ARCH_REVIEW_MESSAGE} Wildcard schema imports are forbidden: {wildcard_imports}"
    )
