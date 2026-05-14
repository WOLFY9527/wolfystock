# -*- coding: utf-8 -*-
"""AST guards for Market Overview provider/runtime boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from src.services.market_data_source_registry import project_source_provenance


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKET_ENDPOINT_FILE = REPO_ROOT / "api" / "v1" / "endpoints" / "market.py"
MARKET_OVERVIEW_SERVICE_FILE = REPO_ROOT / "src" / "services" / "market_overview_service.py"
OFFICIAL_MACRO_TRANSPORT_FILE = REPO_ROOT / "src" / "services" / "official_macro_transport.py"
MARKET_OVERVIEW_BINANCE_TRANSPORT_FILE = REPO_ROOT / "src" / "services" / "market_overview_binance_transport.py"
MARKET_OVERVIEW_SENTIMENT_TRANSPORT_FILE = REPO_ROOT / "src" / "services" / "market_overview_sentiment_transport.py"
MARKET_OVERVIEW_SINA_TRANSPORT_FILE = REPO_ROOT / "src" / "services" / "market_overview_sina_transport.py"
MARKET_OVERVIEW_TICKFLOW_BREADTH_PROVIDER_FILE = REPO_ROOT / "src" / "services" / "market_overview_tickflow_breadth_provider.py"
MARKET_OVERVIEW_YFINANCE_TRANSPORT_FILE = REPO_ROOT / "src" / "services" / "market_overview_yfinance_transport.py"
MARKET_OVERVIEW_TRANSPORT_FILES = (
    OFFICIAL_MACRO_TRANSPORT_FILE,
    MARKET_OVERVIEW_BINANCE_TRANSPORT_FILE,
    MARKET_OVERVIEW_SENTIMENT_TRANSPORT_FILE,
    MARKET_OVERVIEW_SINA_TRANSPORT_FILE,
    MARKET_OVERVIEW_YFINANCE_TRANSPORT_FILE,
)
FORBIDDEN_TRANSPORT_IMPORT_PREFIXES = (
    "api",
    "fastapi",
    "apps",
    "data_provider",
    "src.providers",
    "src.services.analysis_provider_planner",
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.market_provider_operations_service",
)
FORBIDDEN_TICKFLOW_PROVIDER_IMPORT_PREFIXES = (
    "api",
    "fastapi",
    "apps",
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.market_provider_operations_service",
)


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


def _module_imports_matching_prefixes(path: Path, prefixes: tuple[str, ...]) -> set[str]:
    return {
        module
        for module in _module_imports_for_file(path)
        if any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)
    }


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


def _yfinance_history_call_shapes(path: Path) -> list[dict[str, object]]:
    call_shapes: list[dict[str, object]] = []
    for node in ast.walk(_python_tree(path)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "history":
            continue
        ticker_call = node.func.value
        if not isinstance(ticker_call, ast.Call) or not isinstance(ticker_call.func, ast.Attribute):
            continue
        if ticker_call.func.attr != "Ticker":
            continue
        keyword_map = {
            keyword.arg: keyword.value.value
            for keyword in node.keywords
            if keyword.arg and isinstance(keyword.value, ast.Constant)
        }
        ticker_arg = ticker_call.args[0].value if ticker_call.args and isinstance(ticker_call.args[0], ast.Constant) else None
        call_shapes.append(
            {
                "ticker": ticker_arg,
                "period": keyword_map.get("period"),
                "interval": keyword_map.get("interval"),
                "auto_adjust": keyword_map.get("auto_adjust"),
            }
        )
    return call_shapes


def _method_call_names(path: Path, class_name: str, method_name: str) -> set[str]:
    tree = _python_tree(path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or child.name != method_name:
                continue
            calls: set[str] = set()
            for descendant in ast.walk(child):
                if not isinstance(descendant, ast.Call):
                    continue
                if isinstance(descendant.func, ast.Attribute):
                    calls.add(descendant.func.attr)
                elif isinstance(descendant.func, ast.Name):
                    calls.add(descendant.func.id)
            return calls
    raise AssertionError(f"expected {class_name}.{method_name} in {path}")


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


def test_market_overview_service_extracts_raw_transport_boundaries() -> None:
    service_imports = _module_imports_for_file(MARKET_OVERVIEW_SERVICE_FILE)
    service_urls = _requests_get_urls(MARKET_OVERVIEW_SERVICE_FILE)

    assert "src.services.market_data_source_registry" in service_imports
    assert "src.services.official_macro_source_registry" in service_imports
    assert "src.services.official_macro_transport" in service_imports
    assert "src.services.market_overview_binance_transport" in service_imports
    assert "src.services.market_overview_sentiment_transport" in service_imports
    assert "src.services.market_overview_sina_transport" in service_imports
    assert "src.services.market_overview_tickflow_breadth_provider" in service_imports
    assert "src.services.market_overview_yfinance_transport" in service_imports
    assert "data_provider.tickflow_fetcher" not in service_imports
    assert not {
        module
        for module in service_imports
        if module == "requests"
        or module.startswith("requests.")
        or module == "yfinance"
        or module.startswith("yfinance.")
    }
    assert not {
        url
        for url in service_urls
        if "binance.com" in url
        or "sinajs.cn" in url
        or "dataviz.cnn.io" in url
        or "alternative.me" in url
    }


def test_market_overview_tickflow_breadth_provider_keeps_runtime_boundary_narrow() -> None:
    provider_imports = _module_imports_for_file(MARKET_OVERVIEW_TICKFLOW_BREADTH_PROVIDER_FILE)

    assert "data_provider.tickflow_fetcher" in provider_imports
    assert "src.config" in provider_imports
    assert not _module_imports_matching_prefixes(
        MARKET_OVERVIEW_TICKFLOW_BREADTH_PROVIDER_FILE,
        FORBIDDEN_TICKFLOW_PROVIDER_IMPORT_PREFIXES,
    )
    assert not {
        module
        for module in provider_imports
        if module == "requests"
        or module.startswith("requests.")
        or module == "yfinance"
        or module.startswith("yfinance.")
    }


def test_market_overview_service_keeps_cn_flows_and_tickflow_breadth_separate() -> None:
    cn_breadth_calls = _method_call_names(
        MARKET_OVERVIEW_SERVICE_FILE,
        "MarketOverviewService",
        "_fetch_cn_breadth_snapshot",
    )
    cn_flows_calls = _method_call_names(
        MARKET_OVERVIEW_SERVICE_FILE,
        "MarketOverviewService",
        "_fetch_cn_flows_snapshot",
    )

    assert "fetch_tickflow_cn_breadth_snapshot" in cn_breadth_calls
    assert "fetch_tickflow_cn_breadth_snapshot" not in cn_flows_calls
    assert "_fallback_cn_flows_snapshot" in cn_flows_calls


def test_market_overview_service_keeps_cn_flows_and_sector_rotation_fetchers_fallback_only() -> None:
    cn_flows_calls = _method_call_names(
        MARKET_OVERVIEW_SERVICE_FILE,
        "MarketOverviewService",
        "_fetch_cn_flows_snapshot",
    )
    sector_rotation_calls = _method_call_names(
        MARKET_OVERVIEW_SERVICE_FILE,
        "MarketOverviewService",
        "_fetch_sector_rotation_snapshot",
    )

    assert cn_flows_calls == {"_fallback_cn_flows_snapshot"}
    assert sector_rotation_calls == {"_fallback_sector_rotation_snapshot"}


def test_market_overview_tickflow_source_contract_stays_explicit_public_provider_not_snapshot() -> None:
    source_text = MARKET_OVERVIEW_TICKFLOW_BREADTH_PROVIDER_FILE.read_text(encoding="utf-8")
    provenance = project_source_provenance(
        source="tickflow",
        source_type="public_api",
        freshness="delayed",
    )

    assert '_TICKFLOW_SOURCE = "tickflow"' in source_text
    assert '_TICKFLOW_SOURCE_LABEL = "TickFlow"' in source_text
    assert '_TICKFLOW_SOURCE_TYPE = "public_api"' in source_text
    assert provenance["sourceType"] == "public_proxy"
    assert provenance["sourceLabel"] == "TickFlow"
    assert provenance["sourceType"] != "cache_snapshot"


def test_market_overview_transport_modules_stay_runtime_lightweight() -> None:
    actual_mapping = {
        path.name: _module_imports_matching_prefixes(path, FORBIDDEN_TRANSPORT_IMPORT_PREFIXES)
        for path in MARKET_OVERVIEW_TRANSPORT_FILES
    }

    assert actual_mapping == {
        path.name: set()
        for path in MARKET_OVERVIEW_TRANSPORT_FILES
    }


def test_market_overview_raw_http_calls_are_confined_to_http_transport_modules() -> None:
    actual_mapping = {
        path.name: _requests_get_urls(path)
        for path in (
            MARKET_OVERVIEW_BINANCE_TRANSPORT_FILE,
            MARKET_OVERVIEW_SENTIMENT_TRANSPORT_FILE,
            MARKET_OVERVIEW_SINA_TRANSPORT_FILE,
            MARKET_OVERVIEW_YFINANCE_TRANSPORT_FILE,
            OFFICIAL_MACRO_TRANSPORT_FILE,
            MARKET_OVERVIEW_SERVICE_FILE,
        )
    }

    assert actual_mapping == {
        "official_macro_transport.py": set(),
        "market_overview_binance_transport.py": {
            "https://api.binance.com/api/v3/ticker/24hr",
            "https://api.binance.com/api/v3/klines",
            "https://fapi.binance.com/fapi/v1/premiumIndex",
        },
        "market_overview_sentiment_transport.py": {
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            "https://api.alternative.me/fng/",
        },
        "market_overview_sina_transport.py": {
            "https://hq.sinajs.cn/list=",
        },
        "market_overview_yfinance_transport.py": set(),
        "market_overview_service.py": set(),
    }


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


def test_market_overview_sentiment_transport_limits_raw_http_calls_to_sentiment_urls() -> None:
    transport_urls = _requests_get_urls(MARKET_OVERVIEW_SENTIMENT_TRANSPORT_FILE)

    assert transport_urls == {
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://api.alternative.me/fng/",
    }


def test_market_overview_yfinance_transport_owns_yfinance_history_call_shapes() -> None:
    transport_imports = _module_imports_for_file(MARKET_OVERVIEW_YFINANCE_TRANSPORT_FILE)

    assert "yfinance" in transport_imports
    assert _requests_get_urls(MARKET_OVERVIEW_YFINANCE_TRANSPORT_FILE) == set()
    assert _yfinance_history_call_shapes(MARKET_OVERVIEW_YFINANCE_TRANSPORT_FILE) == [
        {
            "ticker": None,
            "period": "5d",
            "interval": "1d",
            "auto_adjust": False,
        },
        {
            "ticker": "SPY",
            "period": "1mo",
            "interval": "1d",
            "auto_adjust": False,
        },
    ]


def test_market_overview_yfinance_history_calls_are_confined_to_yfinance_transport() -> None:
    assert _yfinance_history_call_shapes(OFFICIAL_MACRO_TRANSPORT_FILE) == []
    assert _yfinance_history_call_shapes(MARKET_OVERVIEW_BINANCE_TRANSPORT_FILE) == []
    assert _yfinance_history_call_shapes(MARKET_OVERVIEW_SENTIMENT_TRANSPORT_FILE) == []
    assert _yfinance_history_call_shapes(MARKET_OVERVIEW_SINA_TRANSPORT_FILE) == []
    assert _yfinance_history_call_shapes(MARKET_OVERVIEW_SERVICE_FILE) == []
