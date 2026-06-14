# -*- coding: utf-8 -*-
"""Focused contract tests for the homepage money flow proxy scaffold."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from api.v1.schemas.money_flow import HomeMoneyFlowProxyResponse
from src.services.money_flow_service import MoneyFlowService


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src" / "services" / "money_flow_service.py"

FORBIDDEN_ADVICE_TERMS = (
    "buy",
    "sell",
    "add",
    "reduce",
    "clear",
    "stop-loss",
    "take-profit",
    "target-price",
    "predicted-return",
    "ai recommendation",
    "trading execution",
)
FORBIDDEN_LEAK_MARKERS = (
    "traceback",
    "token",
    "session",
    "api_key",
    "secret",
    "http://",
    "https://",
    "reasoncode",
    "reasoncodes",
    "sourcetype",
    "trustlevel",
    "fallback",
    "confidence",
    "raw payload",
    "raw_payload",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_overview_service",
    "src.services.liquidity_monitor_service",
    "src.services.market_rotation_radar_service",
)


def _serialized_public_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_money_flow_contract_serializes_top_inflow_and_outflow_sections() -> None:
    payload = MoneyFlowService().build_homepage_money_flow_proxy(
        as_of="2026-06-13",
        top_inflows=[
            {
                "name": "算力链",
                "category": "theme",
                "strength": "strong",
                "breadth": "broadening",
                "relativeMove": "strengthening",
                "dataQuality": "partial",
            }
        ],
        top_outflows=[
            {
                "name": "高股息防御",
                "category": "sector",
                "strength": "moderate",
                "breadth": "converging",
                "relativeMove": "weakening",
                "dataQuality": "partial",
            }
        ],
    )

    contract = HomeMoneyFlowProxyResponse.model_validate(payload).model_dump(mode="json")

    assert contract["status"] == "partial"
    assert contract["asOf"] == "2026-06-13"
    assert contract["topInflows"][0]["name"] == "算力链"
    assert contract["topInflows"][0]["direction"] == "inflow"
    assert contract["topOutflows"][0]["name"] == "高股息防御"
    assert contract["topOutflows"][0]["direction"] == "outflow"


def test_money_flow_contract_ranks_and_bounds_top_lists_deterministically() -> None:
    payload = MoneyFlowService().build_homepage_money_flow_proxy(
        as_of="2026-06-13",
        top_inflows=[
            {
                "name": "Beta",
                "category": "theme",
                "strength": "strong",
                "breadth": "broadening",
                "relativeMove": "strengthening",
                "dataQuality": "ready",
            },
            {
                "name": "Alpha",
                "category": "theme",
                "strength": "strong",
                "breadth": "broadening",
                "relativeMove": "strengthening",
                "dataQuality": "ready",
            },
            {
                "name": "Gamma",
                "category": "sector",
                "strength": "moderate",
                "breadth": "broadening",
                "relativeMove": "strengthening",
                "dataQuality": "partial",
            },
            {
                "name": "Delta",
                "category": "sector",
                "strength": "moderate",
                "breadth": "mixed",
                "relativeMove": "flat",
                "dataQuality": "partial",
            },
            {
                "name": "Epsilon",
                "category": "other",
                "strength": "weak",
                "breadth": "mixed",
                "relativeMove": "flat",
                "dataQuality": "no_evidence",
            },
            {
                "name": "Zeta",
                "category": "theme",
                "strength": "weak",
                "breadth": "converging",
                "relativeMove": "weakening",
                "dataQuality": "partial",
                "direction": "outflow",
            },
        ],
        top_outflows=[
            {
                "name": "Low Beta",
                "category": "style",
                "strength": "strong",
                "breadth": "broadening",
                "relativeMove": "strengthening",
                "dataQuality": "partial",
            },
            {
                "name": "Value Yield",
                "category": "style",
                "strength": "moderate",
                "breadth": "converging",
                "relativeMove": "weakening",
                "dataQuality": "partial",
            },
            {
                "name": "Utilities",
                "category": "sector",
                "strength": "weak",
                "breadth": "mixed",
                "relativeMove": "flat",
                "dataQuality": "no_evidence",
            },
            {
                "name": "Staples",
                "category": "sector",
                "strength": "moderate",
                "breadth": "converging",
                "relativeMove": "weakening",
                "dataQuality": "partial",
            },
            {
                "name": "Banks",
                "category": "sector",
                "strength": "moderate",
                "breadth": "converging",
                "relativeMove": "weakening",
                "dataQuality": "partial",
            },
            {
                "name": "Energy",
                "category": "sector",
                "strength": "weak",
                "breadth": "mixed",
                "relativeMove": "flat",
                "dataQuality": "partial",
            },
        ],
        style_bias={"bias": "Growth", "interpretation": "成长 observed flow proxy 相对更强。", "dataQuality": "partial"},
        offensive_defensive_bias={
            "bias": "defensive",
            "interpretation": "防守 observed flow proxy 暂时更占优。",
            "dataQuality": "partial",
        },
    )

    contract = HomeMoneyFlowProxyResponse.model_validate(payload).model_dump(mode="json")

    assert contract["status"] == "ready"
    assert len(contract["topInflows"]) == 5
    assert [item["name"] for item in contract["topInflows"]] == ["Alpha", "Beta", "Gamma", "Delta", "Zeta"]
    assert all(item["direction"] == "inflow" for item in contract["topInflows"])
    assert [item["name"] for item in contract["topOutflows"]] == [
        "Low Beta",
        "Banks",
        "Staples",
        "Value Yield",
        "Energy",
    ]
    assert all(item["direction"] == "outflow" for item in contract["topOutflows"])
    assert contract["styleBias"]["bias"] == "growth"
    assert contract["offensiveDefensiveBias"]["bias"] == "defensive"


def test_money_flow_contract_fails_closed_and_sanitizes_unsafe_inputs() -> None:
    payload = MoneyFlowService().build_homepage_money_flow_proxy(
        as_of="2026-06-13",
        top_inflows=[
            {
                "name": "https://unsafe.example/token=abc",
                "category": "theme",
                "strength": "guaranteed return",
                "breadth": "Traceback",
                "relativeMove": "schemaVersion",
                "interpretation": "Buy now {\"token\": \"abc\"}",
                "dataQuality": "ready",
            }
        ],
        top_outflows=[{"name": "secret-session", "interpretation": "sell now", "dataQuality": "ready"}],
        style_bias={
            "bias": "aggressive://secret",
            "interpretation": "place order now",
            "dataQuality": "ready",
        },
        offensive_defensive_bias={
            "bias": "debug-trace",
            "interpretation": "submit order",
            "dataQuality": "ready",
        },
        interpretation="real-time authoritative fund flow",
    )

    assert payload["status"] == "no_evidence"
    assert payload["asOf"] is None
    assert payload["topInflows"] == []
    assert payload["topOutflows"] == []
    assert payload["styleBias"]["bias"] == "unknown"
    assert payload["offensiveDefensiveBias"]["bias"] == "unknown"
    assert payload["dataQuality"] == {"state": "no_evidence", "label": "暂无证据", "available": False}
    serialized = _serialized_public_payload(payload)
    assert "buy now" not in serialized
    assert "sell now" not in serialized
    assert "token" not in serialized
    assert "https://" not in serialized


def test_money_flow_without_source_wiring_returns_safe_no_evidence_contract() -> None:
    payload = MoneyFlowService().build_homepage_money_flow_proxy()

    assert payload["status"] == "no_evidence"
    assert payload["topInflows"] == []
    assert payload["topOutflows"] == []
    assert payload["dataQuality"] == {"state": "no_evidence", "label": "暂无证据", "available": False}
    assert payload["sourceStatus"]["providerWired"] is False
    assert "暂无证据" in payload["interpretation"]


def test_money_flow_contract_uses_proxy_wording_without_overclaiming_real_fund_flow() -> None:
    payload = MoneyFlowService().build_homepage_money_flow_proxy()
    serialized = _serialized_public_payload(payload)

    assert "observed flow proxy" in serialized
    assert "real fund flow" not in serialized
    assert "authoritative fund flow" not in serialized
    assert "实时资金流" not in serialized
    assert "不能代表实时或权威资金流" in payload["sourceStatus"]["summary"]


def test_money_flow_contract_omits_trading_advice_terms() -> None:
    serialized = _serialized_public_payload(MoneyFlowService().build_homepage_money_flow_proxy())

    for term in FORBIDDEN_ADVICE_TERMS:
        assert term not in serialized


def test_money_flow_contract_omits_internal_diagnostics_and_secret_markers() -> None:
    serialized = _serialized_public_payload(MoneyFlowService().build_homepage_money_flow_proxy())

    for marker in FORBIDDEN_LEAK_MARKERS:
        assert marker not in serialized


def test_money_flow_service_stays_inert_without_provider_or_network_imports() -> None:
    imported_modules = _module_imports(SERVICE_PATH)

    for prefix in FORBIDDEN_IMPORT_PREFIXES:
        assert all(module != prefix and not module.startswith(f"{prefix}.") for module in imported_modules)
