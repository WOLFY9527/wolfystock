# -*- coding: utf-8 -*-
"""Guard future provider/freshness contracts as import-boundary only.

These namespaces do not exist yet and are not contract boundaries today:
- ``src.contracts.providers``
- ``src.contracts.freshness``

If they are added in the future, they must remain inert and must not pull in
provider runtime, MarketCache, live-call clients, API routers, frontend code,
or domain services.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_ROOT = REPO_ROOT / "src" / "contracts"
CURRENT_CONTRACT_NAMESPACES = {"data_quality", "evidence"}
FUTURE_PROVIDER_CONTRACT_MODULES = (
    "src.contracts.providers",
    "src.contracts.freshness",
)
FORBIDDEN_PROVIDER_CONTRACT_RUNTIME_PREFIXES = (
    "src.providers.http",
    "src.providers.validation",
    "data_provider",
    "src.services.market_cache",
    "src.services.analysis_provider_planner",
    "src.services.market_scanner_service",
    "src.services.rule_backtest_service",
    "src.services.portfolio",
    "src.services.portfolio_service",
    "src.services.portfolio_risk_diagnostics",
    "api.v1.endpoints",
    "requests",
    "httpx",
    "openai",
    "litellm",
    "pandas",
    "apps.dsa-web",
    "apps.dsa_web",
)


def _contracts_child_namespaces() -> set[str]:
    return {
        path.name
        for path in CONTRACTS_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }


def _has_loaded_prefix(loaded_modules: set[str], prefix: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for name in loaded_modules)


def _optional_import_payload(module_name: str) -> dict[str, object]:
    script = f"""
import importlib
import importlib.util
import json
import sys

module_name = {module_name!r}
tracked_prefixes = ('src.contracts',) + {FORBIDDEN_PROVIDER_CONTRACT_RUNTIME_PREFIXES!r}
spec = importlib.util.find_spec(module_name)

if spec is None:
    print(json.dumps({{"exists": False, "loaded_modules": []}}))
else:
    importlib.import_module(module_name)
    loaded_modules = sorted(
        name
        for name in sys.modules
        if any(name == prefix or name.startswith(prefix + ".") for prefix in tracked_prefixes)
    )
    print(json.dumps({{"exists": True, "loaded_modules": loaded_modules}}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_provider_and_freshness_contract_namespaces_are_not_present_yet() -> None:
    assert _contracts_child_namespaces() == CURRENT_CONTRACT_NAMESPACES

    for module_name in FUTURE_PROVIDER_CONTRACT_MODULES:
        payload = _optional_import_payload(module_name)
        assert payload["exists"] is False, f"{module_name} must stay absent until a real contract boundary exists"


def test_future_provider_or_freshness_contracts_must_remain_inert_if_added() -> None:
    for module_name in FUTURE_PROVIDER_CONTRACT_MODULES:
        payload = _optional_import_payload(module_name)

        if payload["exists"] is False:
            continue

        loaded_modules = set(payload["loaded_modules"])
        assert module_name in loaded_modules

        for forbidden_prefix in FORBIDDEN_PROVIDER_CONTRACT_RUNTIME_PREFIXES:
            assert not _has_loaded_prefix(
                loaded_modules,
                forbidden_prefix,
            ), f"{module_name} unexpectedly imported runtime dependency: {forbidden_prefix}"
