# -*- coding: utf-8 -*-
"""AST guards for Market Overview provider/runtime boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKET_ENDPOINT_FILE = REPO_ROOT / "api" / "v1" / "endpoints" / "market.py"
MARKET_OVERVIEW_SERVICE_FILE = REPO_ROOT / "src" / "services" / "market_overview_service.py"
MARKET_OVERVIEW_BINANCE_TRANSPORT_FILE = REPO_ROOT / "src" / "services" / "market_overview_binance_transport.py"
MARKET_OVERVIEW_SINA_TRANSPORT_FILE = REPO_ROOT / "src" / "services" / "market_overview_sina_transport.py"


def _market_endpoint_tree() -> ast.AST:
    return ast.parse(MARKET_ENDPOINT_FILE.read_text(encoding="utf-8"), filename=str(MARKET_ENDPOINT_FILE))


def _python_tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function_node(name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(_market_endpoint_tree()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"expected function {name} in {MARKET_ENDPOINT_FILE}")


def _market_overview_service_calls(node: ast.AST) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
            continue
        service_call = child.func.value
        if isinstance(service_call, ast.Call) and isinstance(service_call.func, ast.Name) and service_call.func.id == "MarketOverviewService":
            calls.add(child.func.attr)
    return calls


def _module_imports() -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(_market_endpoint_tree()):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module)
    return imports


def _module_imports_for_file(path: Path) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(_python_tree(path)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module)
    return imports


def _requests_get_urls(path: Path) -> set[str]:
    def _string_prefix(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return _string_prefix(node.left)
        return None

    urls: set[str] = set()
    for node in ast.walk(_python_tree(path)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "requests" or node.func.attr != "get":
            continue
        url_arg = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "url"), None)
        if url_arg is None:
            continue
        url_prefix = _string_prefix(url_arg)
        if url_prefix:
            urls.add(url_prefix)
    return urls


def test_market_endpoints_delegate_to_market_overview_service() -> None:
    expected_calls = {
        "get_crypto": "get_crypto",
        "get_sentiment": "get_market_sentiment",
        "get_cn_indices": "get_cn_indices",
        "get_cn_breadth": "get_cn_breadth",
        "get_cn_flows": "get_cn_flows",
        "get_sector_rotation": "get_sector_rotation",
        "get_us_breadth": "get_us_breadth",
        "get_rates": "get_rates",
        "get_fx_commodities": "get_fx_commodities",
        "get_temperature": "get_market_temperature",
        "get_market_briefing": "get_market_briefing",
        "get_futures": "get_futures",
        "get_cn_short_sentiment": "get_cn_short_sentiment",
    }

    actual_calls = {
        function_name: _market_overview_service_calls(_function_node(function_name))
        for function_name in expected_calls
    }

    assert actual_calls == {
        function_name: {service_method}
        for function_name, service_method in expected_calls.items()
    }


def test_stream_crypto_keeps_market_overview_service_snapshot_fallback() -> None:
    assert "get_crypto" in _market_overview_service_calls(_function_node("stream_crypto"))


def test_market_endpoint_module_avoids_direct_provider_client_imports() -> None:
    forbidden_imports = {
        module
        for module in _module_imports()
        if module == "requests" or module.startswith("data_provider") or module == "yfinance" or module.startswith("yfinance.")
    }

    assert forbidden_imports == set()


def test_market_overview_service_extracts_binance_raw_transport_boundary() -> None:
    service_imports = _module_imports_for_file(MARKET_OVERVIEW_SERVICE_FILE)
    service_urls = _requests_get_urls(MARKET_OVERVIEW_SERVICE_FILE)

    assert "src.services.market_overview_binance_transport" in service_imports
    assert "src.services.market_overview_sina_transport" in service_imports
    assert not {url for url in service_urls if "binance.com" in url or "sinajs.cn" in url}


def test_market_overview_binance_transport_limits_raw_http_calls_to_binance() -> None:
    transport_urls = _requests_get_urls(MARKET_OVERVIEW_BINANCE_TRANSPORT_FILE)

    assert transport_urls == {
        "https://api.binance.com/api/v3/ticker/24hr",
        "https://api.binance.com/api/v3/klines",
        "https://fapi.binance.com/fapi/v1/premiumIndex",
    }


def test_market_overview_sina_transport_limits_raw_http_calls_to_sina() -> None:
    transport_urls = _requests_get_urls(MARKET_OVERVIEW_SINA_TRANSPORT_FILE)

    assert transport_urls == {
        "https://hq.sinajs.cn/list=",
    }
