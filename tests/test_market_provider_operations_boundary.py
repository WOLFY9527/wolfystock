# -*- coding: utf-8 -*-
"""Boundary guards for the read-only market provider operations service."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from src.services.market_cache import market_cache
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
FORBIDDEN_PROVIDER_OPERATIONS_RUNTIME_PATTERNS = (
    r"\breset_instance\(",
    r"\bvalidate_provider_connection\(",
    r"\btest_builtin_data_source\(",
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'market-provider-operations-boundary.sqlite'}")
    MarketProviderOperationsService.clear_summary_cache()
    market_cache.clear()
    yield
    MarketProviderOperationsService.clear_summary_cache()
    market_cache.clear()
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
    for pattern in FORBIDDEN_PROVIDER_OPERATIONS_RUNTIME_PATTERNS:
        assert re.search(pattern, source_text) is None, (
            "Market Provider Operations must stay observer-only. Do not add "
            "singleton resets or provider runtime validation probes to the read "
            f"model service; keep `{pattern}` out of this file"
        )


def test_market_provider_operations_service_does_not_import_market_overview_runtime() -> None:
    imported_modules = _market_provider_operations_imports()
    source_text = MARKET_PROVIDER_OPERATIONS_SERVICE_PATH.read_text(encoding="utf-8")

    assert "src.services.market_overview_service" not in imported_modules
    assert "market_overview_service" not in source_text


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


@pytest.mark.parametrize(
    ("cache_key", "source", "expected_label"),
    [
        ("indices", "eastmoney", "东方财富"),
        ("cn_indices", "sina", "新浪财经"),
        ("crypto", "binance", "Binance"),
        ("rates", "yahoo", "Yahoo Finance"),
        ("funds_flow", "fred", "FRED"),
        ("macro", "treasury", "US Treasury"),
        ("temperature", "computed", "系统计算"),
        ("market_briefing", "mixed", "多来源"),
        ("futures", "public", "公开数据"),
        ("cn_short_sentiment", "fallback", "备用数据"),
        ("fx_commodities", "polygon_us_grouped_daily", "Polygon grouped daily US equities"),
    ],
)
def test_market_provider_operations_known_source_labels_match_previous_visible_labels(
    cache_key: str,
    source: str,
    expected_label: str,
) -> None:
    market_cache.set(
        cache_key,
        {
            "source": source,
            "freshness": "cached",
            "updatedAt": "2026-05-24T10:00:00+08:00",
            "items": [],
        },
        ttl_seconds=60,
    )

    payload = MarketProviderOperationsService(
        cache=market_cache,
        db=DatabaseManager.get_instance(),
    ).get_operations(window="24h")

    item = next(item for item in payload["items"] if item["cacheKey"] == cache_key)
    assert item["sourceLabel"] == expected_label


def test_market_provider_operations_unknown_source_label_stays_empty() -> None:
    market_cache.set(
        "indices",
        {
            "source": "unregistered_provider",
            "freshness": "cached",
            "updatedAt": "2026-05-24T10:00:00+08:00",
            "items": [],
        },
        ttl_seconds=60,
    )

    payload = MarketProviderOperationsService(
        cache=market_cache,
        db=DatabaseManager.get_instance(),
    ).get_operations(window="24h")

    item = next(item for item in payload["items"] if item["cacheKey"] == "indices")
    assert item["sourceLabel"] is None
