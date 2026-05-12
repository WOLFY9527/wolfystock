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
API_ROOT = REPO_ROOT / "api"
DATA_PROVIDER_ROOT = REPO_ROOT / "data_provider"
SRC_ROOT = REPO_ROOT / "src"
CONTRACTS_ROOT = SRC_ROOT / "contracts"
SERVICES_ROOT = SRC_ROOT / "services"
ACTIVE_CONTRACT_NAMESPACES = {"data_quality", "evidence"}
INACTIVE_BACKEND_NAMESPACE_MODULES = (
    "src.platform",
    "src.domains",
)
ARCHITECTURE_DOMAIN_CLASSIFICATIONS = {
    "provider-runtime / MarketCache": {
        "data_provider",
        "src.providers",
        "src.services.analysis_provider_planner",
        "src.services.market_cache",
        "src.services.market_provider_operations_service",
        "src.services.options_market_data_provider",
        "src.services.provider_capability_matrix",
        "src.services.provider_circuit_observer",
        "src.services.provider_plan_advisor",
        "src.services.provider_usage_ledger",
        "src.services.quota_policy_service",
    },
    "scanner": {
        "src.services.market_scanner_ops_service",
        "src.services.market_scanner_service",
        "src.services.scanner_ai_service",
        "src.services.scanner_evidence_packet",
    },
    "backtest": {
        "src.services.backtest_professional_readiness",
        "src.services.backtest_service",
        "src.services.local_data_preflight_service",
        "src.services.rule_backtest_service",
    },
    "portfolio": {
        "src.services.admin_portfolio_service",
        "src.services.fx_rate_service",
        "src.services.portfolio_ibkr_sync_service",
        "src.services.portfolio_import_service",
        "src.services.portfolio_risk_diagnostics",
        "src.services.portfolio_risk_service",
        "src.services.portfolio_service",
    },
    "AI routing / cost": {
        "src.services.agent_model_service",
        "src.services.ai_evidence_adapters",
        "src.services.ai_evidence_dry_run_explanation",
        "src.services.duplicate_cost_summary_service",
        "src.services.image_stock_extractor",
        "src.services.litellm_runtime",
        "src.services.llm_cost_ledger_service",
        "src.services.llm_instrumentation",
        "src.services.model_pricing_policy_import_service",
        "src.services.research_budget_profiles",
    },
    "auth / RBAC": {
        "api.deps",
        "api.middlewares.auth",
        "api.middlewares.public_abuse_limiter",
        "api.security_headers",
        "api.v1.endpoints.auth",
        "src.services.admin_governance_audit_service",
        "src.services.admin_mfa_service",
        "src.services.admin_security_service",
        "src.services.admin_user_service",
    },
    "admin observability": {
        "api.v1.endpoints.admin_cost",
        "api.v1.endpoints.admin_logs",
        "api.v1.endpoints.admin_notifications",
        "api.v1.endpoints.admin_portfolio",
        "api.v1.endpoints.admin_provider_circuits",
        "api.v1.endpoints.admin_security",
        "api.v1.endpoints.admin_users",
        "api.v1.endpoints.market_provider_operations",
        "api.v1.endpoints.provider_usage_ledger",
        "src.services.admin_activity_service",
        "src.services.admin_logs_service",
    },
    "shared contracts": {
        "api.v1.schemas",
        "src.contracts",
        "src.services.ai_evidence_packet",
        "src.services.ai_evidence_packet_validator",
        "src.services.data_quality_contract_validator",
        "src.services.data_quality_contracts",
    },
}
EXPECTED_ARCHITECTURE_DOMAINS = {
    "provider-runtime / MarketCache",
    "scanner",
    "backtest",
    "portfolio",
    "AI routing / cost",
    "auth / RBAC",
    "admin observability",
    "shared contracts",
}
EXPECTED_RUNTIME_HEAVY_DOMAIN_CLASSIFICATIONS = {
    "data_provider.akshare_fetcher": "provider-runtime / MarketCache",
    "data_provider.alpaca_fetcher": "provider-runtime / MarketCache",
    "data_provider.baostock_fetcher": "provider-runtime / MarketCache",
    "data_provider.tushare_fetcher": "provider-runtime / MarketCache",
    "data_provider.yfinance_fetcher": "provider-runtime / MarketCache",
    "src.services.market_cache": "provider-runtime / MarketCache",
    "src.services.market_scanner_service": "scanner",
    "src.services.market_scanner_ops_service": "scanner",
    "src.services.scanner_ai_service": "scanner",
    "src.services.backtest_service": "backtest",
    "src.services.rule_backtest_service": "backtest",
    "src.services.portfolio_service": "portfolio",
    "src.services.portfolio_import_service": "portfolio",
    "src.services.portfolio_ibkr_sync_service": "portfolio",
    "src.services.portfolio_risk_diagnostics": "portfolio",
    "src.services.litellm_runtime": "AI routing / cost",
    "src.services.llm_cost_ledger_service": "AI routing / cost",
    "src.services.llm_instrumentation": "AI routing / cost",
    "api.deps": "auth / RBAC",
    "api.middlewares.auth": "auth / RBAC",
    "src.services.admin_security_service": "auth / RBAC",
    "src.services.admin_activity_service": "admin observability",
    "src.services.admin_logs_service": "admin observability",
    "api.v1.endpoints.admin_logs": "admin observability",
    "api.v1.schemas": "shared contracts",
    "src.contracts": "shared contracts",
}
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
    "src/services/options_lab_service.py": {"api.v1.schemas.options"},
}
# Transitional, owned upward imports from services into API schemas.
# These are inventory items, not a pattern to copy into new services.
EXPECTED_SERVICE_API_IMPORTS = EXPECTED_API_SCHEMA_UPWARD_IMPORTS
FORBIDDEN_SERVICE_API_PREFIXES = (
    "api.v1.endpoints",
)
PROVIDER_RUNTIME_IMPORT_PREFIXES = (
    "data_provider",
    "src.services.market_cache",
)
# Transitional provider-runtime touch points. Owners are the domain listed in
# the importing path plus provider-runtime; new entries need architecture review.
EXPECTED_PROVIDER_RUNTIME_IMPORTS = {
    "src/services/agent_stock_evidence_service.py": {
        "data_provider.base",
        "data_provider.realtime_types",
    },
    "src/services/analysis_provider_planner.py": {"data_provider.us_index_mapping"},
    "src/services/crypto_realtime_service.py": {"src.services.market_cache"},
    "src/services/market_overview_service.py": {"src.services.market_cache"},
    "src/services/market_provider_operations_service.py": {"src.services.market_cache"},
    "src/services/market_scanner_service.py": {"data_provider.base"},
    "src/services/portfolio_risk_board_lookup.py": {"data_provider.base"},
    "src/services/rule_backtest_service.py": {
        "data_provider.base",
        "data_provider.us_index_mapping",
    },
    # Stock lookup/intraday helpers are still provider-coupled; classify them as
    # existing provider-runtime imports instead of silently normalizing the seam.
    "src/services/stock_service.py": {
        "data_provider.base",
        "data_provider.yfinance_fetcher",
    },
    "src/services/us_history_helper.py": {"data_provider.base"},
}
RULE_BACKTEST_LLM_IMPORT_PREFIXES = (
    "src.agent",
    "src.config",
)
EXPECTED_RULE_BACKTEST_LLM_IMPORT_BOUNDARY = {
    "src/services/rule_backtest_text_completion.py": {
        "src.agent.llm_adapter",
        "src.config",
    },
}


@dataclass(frozen=True)
class ApiImportRecord:
    module: str
    imported_names: tuple[str, ...]
    wildcard: bool = False


def _module_name_from_path(path: Path, package_root: Path, package_name: str) -> str:
    relative = path.relative_to(package_root).with_suffix("")
    parts = relative.parts
    if parts == ("__init__",):
        return package_name
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join((package_name, *parts))


def _python_modules_under(package_root: Path, package_name: str) -> set[str]:
    return {
        _module_name_from_path(path, package_root, package_name)
        for path in package_root.rglob("*.py")
    }


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


def _classify_backend_module(module_name: str) -> str | None:
    for domain_name, module_prefixes in ARCHITECTURE_DOMAIN_CLASSIFICATIONS.items():
        if any(
            module_name == prefix or module_name.startswith(prefix + ".")
            for prefix in module_prefixes
        ):
            return domain_name
    return None


def _import_mapping_for_prefixes(
    search_roots: tuple[Path, ...],
    import_prefixes: tuple[str, ...],
) -> dict[str, set[str]]:
    matches: dict[str, set[str]] = {}
    for search_root in search_roots:
        for python_file in search_root.rglob("*.py"):
            tree = ast.parse(
                python_file.read_text(encoding="utf-8"),
                filename=str(python_file),
            )
            modules: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        if any(
                            module_name == prefix or module_name.startswith(prefix + ".")
                            for prefix in import_prefixes
                        ):
                            modules.add(module_name)
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""
                    if node.level == 0 and any(
                        module_name == prefix or module_name.startswith(prefix + ".")
                        for prefix in import_prefixes
                    ):
                        modules.add(module_name)

            if modules:
                matches[python_file.relative_to(REPO_ROOT).as_posix()] = modules
    return matches


def _imports_for_file(python_file: Path, import_prefixes: tuple[str, ...]) -> set[str]:
    tree = ast.parse(
        python_file.read_text(encoding="utf-8"),
        filename=str(python_file),
    )
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                if any(
                    module_name == prefix or module_name.startswith(prefix + ".")
                    for prefix in import_prefixes
                ):
                    modules.add(module_name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if node.level == 0 and any(
                module_name == prefix or module_name.startswith(prefix + ".")
                for prefix in import_prefixes
            ):
                modules.add(module_name)
    return modules


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


def test_architecture_manual_domains_have_current_backend_classifications() -> None:
    assert set(ARCHITECTURE_DOMAIN_CLASSIFICATIONS) == EXPECTED_ARCHITECTURE_DOMAINS
    classified_prefixes = [
        module_prefix
        for module_prefixes in ARCHITECTURE_DOMAIN_CLASSIFICATIONS.values()
        for module_prefix in module_prefixes
    ]
    assert len(classified_prefixes) == len(set(classified_prefixes))

    for module_name, expected_domain in EXPECTED_RUNTIME_HEAVY_DOMAIN_CLASSIFICATIONS.items():
        assert _classify_backend_module(module_name) == expected_domain


def test_data_provider_modules_are_classified_as_provider_runtime_internals() -> None:
    concrete_provider_modules = _python_modules_under(DATA_PROVIDER_ROOT, "data_provider") - {
        "data_provider",
    }

    assert concrete_provider_modules, "expected provider runtime modules under data_provider/"
    for module_name in concrete_provider_modules:
        assert (
            _classify_backend_module(module_name) == "provider-runtime / MarketCache"
        ), f"{module_name} must be classified as provider-runtime internals"


def test_provider_runtime_import_inventory_is_explicit() -> None:
    actual_mapping = _import_mapping_for_prefixes(
        (API_ROOT, SERVICES_ROOT, SRC_ROOT / "contracts"),
        PROVIDER_RUNTIME_IMPORT_PREFIXES,
    )

    assert actual_mapping == EXPECTED_PROVIDER_RUNTIME_IMPORTS, (
        "provider-runtime / MarketCache imports outside provider facades are "
        f"transitional inventory items. Expected {EXPECTED_PROVIDER_RUNTIME_IMPORTS}, "
        f"found {actual_mapping}"
    )


def test_provider_symbol_helpers_delegate_to_pure_utils() -> None:
    actual_mapping = {
        "data_provider/base.py": _imports_for_file(
            DATA_PROVIDER_ROOT / "base.py",
            (
                "src.utils.symbol_normalization",
                "src.utils.symbol_classification",
            ),
        ),
        "data_provider/us_index_mapping.py": _imports_for_file(
            DATA_PROVIDER_ROOT / "us_index_mapping.py",
            ("src.utils.symbol_classification",),
        ),
    }

    assert actual_mapping == {
        "data_provider/base.py": {
            "src.utils.symbol_normalization",
            "src.utils.symbol_classification",
        },
        "data_provider/us_index_mapping.py": {"src.utils.symbol_classification"},
    }


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


def test_rule_backtest_llm_import_boundary_is_isolated() -> None:
    actual_mapping = {
        "src/services/rule_backtest_service.py": _imports_for_file(
            SERVICES_ROOT / "rule_backtest_service.py",
            RULE_BACKTEST_LLM_IMPORT_PREFIXES,
        ),
        "src/services/rule_backtest_text_completion.py": _imports_for_file(
            SERVICES_ROOT / "rule_backtest_text_completion.py",
            RULE_BACKTEST_LLM_IMPORT_PREFIXES,
        ),
    }
    actual_mapping = {
        path: modules
        for path, modules in actual_mapping.items()
        if modules
    }

    assert actual_mapping == EXPECTED_RULE_BACKTEST_LLM_IMPORT_BOUNDARY, (
        "rule backtest text completion construction must stay isolated behind the "
        f"dedicated facade. Expected {EXPECTED_RULE_BACKTEST_LLM_IMPORT_BOUNDARY}, "
        f"found {actual_mapping}"
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
