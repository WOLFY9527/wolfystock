# -*- coding: utf-8 -*-
"""Boundary guards for the read-only market provider operations service."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.services.market_provider_operations_service import MarketProviderOperationsService
from src.storage import DatabaseManager


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKET_PROVIDER_OPERATIONS_SERVICE_PATH = REPO_ROOT / "src/services/market_provider_operations_service.py"
MARKET_PROVIDER_OPERATIONS_ENDPOINT_PATH = REPO_ROOT / "api/v1/endpoints/market_provider_operations.py"
FORBIDDEN_PROVIDER_OPERATIONS_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
)
FORBIDDEN_PROVIDER_OPERATIONS_CACHE_PATTERNS = (
    r"\bself\.cache\.get_or_refresh\(",
    r"\bmarket_cache\.get_or_refresh\(",
    r"\bself\.cache\.set\(",
    r"\bmarket_cache\.set\(",
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'market-provider-operations-boundary.sqlite'}")
    MarketProviderOperationsService.clear_summary_cache()
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    MarketProviderOperationsService.clear_summary_cache()
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    DatabaseManager.reset_instance()


def _market_provider_operations_imports() -> set[str]:
    tree = ast.parse(MARKET_PROVIDER_OPERATIONS_SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_market_provider_operations_source_stays_read_only_and_local() -> None:
    imported_modules = _market_provider_operations_imports()
    forbidden_imports = sorted(
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in FORBIDDEN_PROVIDER_OPERATIONS_IMPORT_PREFIXES
        )
    )
    source_text = MARKET_PROVIDER_OPERATIONS_SERVICE_PATH.read_text(encoding="utf-8")

    assert not forbidden_imports, (
        "Market Provider Operations must remain an observer/admin-log/cache-state "
        "surface. Do not add direct provider SDK or raw HTTP imports here. "
        f"Found {forbidden_imports}"
    )
    for pattern in FORBIDDEN_PROVIDER_OPERATIONS_CACHE_PATTERNS:
        assert re.search(pattern, source_text) is None, (
            "Market Provider Operations must stay read-only. Do not refresh or "
            "mutate MarketCache from market_provider_operations_service.py; keep "
            f"`{pattern}` out of this file"
        )


def test_market_provider_operations_endpoint_stays_get_only_read_model_route() -> None:
    tree = ast.parse(MARKET_PROVIDER_OPERATIONS_ENDPOINT_PATH.read_text(encoding="utf-8"))
    route_methods: set[str] = set()
    source_text = MARKET_PROVIDER_OPERATIONS_ENDPOINT_PATH.read_text(encoding="utf-8").lower()

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                route_methods.add(decorator.func.attr)

    assert route_methods == {"get"}, (
        "Market Provider Operations must remain query/read-only. Do not add "
        f"POST/PATCH/DELETE routes here: found decorators {sorted(route_methods)}"
    )
    for forbidden_term in ("cleanup", "dry_run", "use_retention", "refresh", "mutate", "test provider"):
        assert forbidden_term not in source_text, (
            "Market Provider Operations endpoint must stay an observer surface "
            f"without mutation/test semantics; found `{forbidden_term}`"
        )


def test_market_provider_operations_payload_stays_observer_oriented() -> None:
    payload = MarketProviderOperationsService(
        cache=market_cache,
        db=DatabaseManager.get_instance(),
    ).get_operations(window="24h")

    assert payload["metadata"]["source"] == "market_cache_and_admin_logs"
    assert payload["metadata"]["readOnly"] is True
    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["metadata"]["cacheMutation"] is False
    assert isinstance(payload["cacheStates"], list)
    assert isinstance(payload["adminLogDrillThrough"], dict)
