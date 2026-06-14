# -*- coding: utf-8 -*-
"""Tests for the standalone Market Pulse snapshot contract scaffold."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from api.v1.schemas.market_pulse import MarketPulseSnapshot
from src.services.market_pulse_service import (
    MARKET_PULSE_ALLOWED_COPY_VALUES,
    MARKET_PULSE_ALLOWED_DATA_QUALITY_STATES,
    MARKET_PULSE_DEFAULT_DISCLOSURE,
    MarketPulseService,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/market_pulse_service.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "yfinance",
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.market_overview_",
    "src.services.liquidity_monitor_service",
    "src.services.liquidity_impulse_synthesis_service",
    "src.services.official_macro",
)
FORBIDDEN_TERMS = (
    "buy now",
    "sell now",
    "add position",
    "reduce position",
    "clear position",
    "stop-loss",
    "take-profit",
    "target-price",
    "predicted-return",
    "ai recommends",
    "broker",
    "order",
    "trade execution",
    "traceback",
    "valueerror",
    "runtimeerror",
    "sourceType",
    "trustLevel",
    "reasonCode",
    "raw confidence",
    "token",
    "session",
    "api key",
    "secret",
)


def _service_imports() -> set[str]:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _complete_payload() -> dict:
    return {
        "asOf": "2026-06-14T09:30:00Z",
        "indices": [
            {"label": "S&P 500", "value": 5300.25, "unit": "pt", "change": 0.8, "state": "走强", "interpretation": "适合研究观察", "dataQuality": "正常"},
            {"label": "Nasdaq", "value": 18880.4, "unit": "pt", "change": 1.1, "state": "走强", "interpretation": "适合研究观察", "dataQuality": "正常"},
            {"label": "Russell 2000", "value": 2110.2, "unit": "pt", "change": -0.2, "state": "中性", "interpretation": "观察", "dataQuality": "观察"},
        ],
        "volatility": {"label": "VIX", "value": 13.4, "unit": "pt", "change": -0.7, "state": "中性", "interpretation": "观察", "dataQuality": "观察"},
        "rates": {"label": "10Y Treasury yield", "value": 4.31, "unit": "%", "change": 0.03, "state": "复核", "interpretation": "复核", "dataQuality": "复核"},
        "dollar": {"label": "Dollar index", "value": 104.2, "unit": "pt", "change": -0.1, "state": "中性", "interpretation": "观察", "dataQuality": "观察"},
        "breadth": {"label": "Market breadth", "value": 56.0, "unit": "%", "change": 2.5, "state": "正常", "interpretation": "适合研究观察", "dataQuality": "正常"},
        "liquidity": {"label": "Liquidity state", "value": None, "unit": None, "change": None, "state": "观察", "interpretation": "适合研究观察", "dataQuality": "观察"},
    }


def test_market_pulse_default_snapshot_has_stable_top_level_shape() -> None:
    snapshot = MarketPulseService().build_snapshot().model_dump(mode="json")

    assert list(snapshot.keys()) == [
        "status",
        "asOf",
        "indices",
        "volatility",
        "rates",
        "dollar",
        "breadth",
        "liquidity",
        "dataQuality",
        "noAdviceDisclosure",
    ]
    assert [item["label"] for item in snapshot["indices"]] == ["S&P 500", "Nasdaq", "Russell 2000"]
    assert MarketPulseSnapshot.model_validate(snapshot).status == "no_evidence"


def test_market_pulse_default_snapshot_is_explicit_no_evidence_and_safe() -> None:
    snapshot = MarketPulseService().build_snapshot().model_dump(mode="json")
    metrics = snapshot["indices"] + [
        snapshot["volatility"],
        snapshot["rates"],
        snapshot["dollar"],
        snapshot["breadth"],
        snapshot["liquidity"],
    ]

    assert snapshot["status"] == "no_evidence"
    assert snapshot["asOf"] is None
    assert snapshot["dataQuality"] == {
        "state": "暂无证据",
        "label": "暂无证据",
        "available": False,
    }
    assert snapshot["noAdviceDisclosure"] == MARKET_PULSE_DEFAULT_DISCLOSURE

    for metric in metrics:
        assert metric["value"] is None
        assert metric["change"] is None
        assert metric["state"] == "暂无证据"
        assert metric["interpretation"] == "暂无证据"
        assert metric["dataQuality"]["state"] == "暂无证据"
        assert metric["dataQuality"]["label"] == "暂无证据"
        assert metric["dataQuality"]["available"] is False


def test_market_pulse_contract_bounds_data_quality_states() -> None:
    snapshot = MarketPulseService().build_snapshot(_complete_payload()).model_dump(mode="json")
    metric_states = {
        item["dataQuality"]["state"]
        for item in snapshot["indices"] + [
            snapshot["volatility"],
            snapshot["rates"],
            snapshot["dollar"],
            snapshot["breadth"],
            snapshot["liquidity"],
        ]
    }

    assert snapshot["status"] == "ready"
    assert snapshot["dataQuality"]["state"] in MARKET_PULSE_ALLOWED_DATA_QUALITY_STATES
    assert snapshot["dataQuality"]["label"] in MARKET_PULSE_ALLOWED_COPY_VALUES
    assert metric_states <= MARKET_PULSE_ALLOWED_DATA_QUALITY_STATES


def test_market_pulse_snapshot_strips_advice_terms_and_internal_markers() -> None:
    payload = _complete_payload()
    payload["indices"][0].update(
        {
            "state": "buy",
            "interpretation": "take-profit",
            "dataQuality": "sourceType",
            "traceback": "Traceback: RuntimeError",
            "providerUrl": "https://private-provider.example/api",
            "token": "secret-token",
            "reasonCode": "provider_timeout",
        }
    )
    payload["volatility"].update(
        {
            "state": "reduce",
            "interpretation": "target-price",
            "dataQuality": "trustLevel",
            "exceptionClass": "ValueError",
            "sessionId": "abc123",
        }
    )

    snapshot = MarketPulseService().build_snapshot(payload).model_dump(mode="json")
    serialized = json.dumps(snapshot, ensure_ascii=False)
    serialized_lower = serialized.lower()

    assert snapshot["indices"][0]["state"] == "观察"
    assert snapshot["indices"][0]["interpretation"] == "观察"
    assert snapshot["indices"][0]["dataQuality"]["state"] == "观察"
    assert snapshot["volatility"]["state"] == "观察"
    assert snapshot["volatility"]["interpretation"] == "观察"
    assert snapshot["volatility"]["dataQuality"]["state"] == "观察"

    for term in FORBIDDEN_TERMS:
        assert term not in serialized_lower
    assert "https://private-provider.example/api" not in serialized


def test_market_pulse_service_is_inert_and_does_not_import_runtime_providers() -> None:
    imports = _service_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)
