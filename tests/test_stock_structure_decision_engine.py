# -*- coding: utf-8 -*-
"""Tests for the pure stock structure decision engine."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from src.services.stock_structure_decision_engine import (
    STOCK_STRUCTURE_DECISION_SCHEMA_VERSION,
    build_stock_structure_decision,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = REPO_ROOT / "src/services/stock_structure_decision_engine.py"
REQUIRED_COMPONENT_SCORES = {
    "trend",
    "relativeStrength",
    "volumePressure",
    "volatilityCompression",
    "breakoutQuality",
    "pullbackHealth",
    "riskExtension",
    "evidenceQuality",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.market_scanner_service",
    "src.services.scanner_ai_service",
    "src.services.stock_service_provider_adapter",
)
FORBIDDEN_ADVICE_TOKENS = (
    "buy",
    "sell",
    "hold",
    "position",
    "target",
    "stop",
    "entry",
    "exit",
    "买入",
    "卖出",
    "持有",
    "仓位",
    "目标",
    "止损",
    "止盈",
)


def _bar(index: int, close: float, *, volume: float = 1000.0, width: float = 1.2) -> dict[str, Any]:
    return {
        "date": f"2026-01-{index + 1:02d}",
        "open": round(close - width * 0.2, 4),
        "high": round(close + width * 0.5, 4),
        "low": round(close - width * 0.5, 4),
        "close": round(close, 4),
        "volume": round(volume, 4),
    }


def _series(closes: list[float], *, volume: float = 1000.0, width: float = 1.2) -> list[dict[str, Any]]:
    return [_bar(index, close, volume=volume, width=width) for index, close in enumerate(closes)]


def _trend_breakout_fixture() -> list[dict[str, Any]]:
    bars = _series([100 + index * 0.55 for index in range(55)], volume=1200.0, width=1.0)
    prior_range_high = max(float(bar["high"]) for bar in bars[-21:-1])
    last_close = prior_range_high * 1.025
    bars[-1] = _bar(54, last_close, volume=2600.0, width=1.0)
    return bars


def _benchmark_fixture() -> list[dict[str, Any]]:
    return _series([100 + index * 0.12 for index in range(55)], volume=5000.0, width=0.8)


def _extended_fixture() -> list[dict[str, Any]]:
    bars = _series([80 + index * 0.35 for index in range(54)], volume=1100.0, width=0.8)
    bars.append(_bar(54, 123.0, volume=2400.0, width=5.0))
    return bars


def _consolidation_fixture() -> list[dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    for index in range(35):
        width = 4.2 if index < 18 else 0.9
        close = 100 + (index % 4 - 1.5) * 0.18
        bars.append(_bar(index, close, volume=900.0, width=width))
    return bars


def _distribution_fixture() -> list[dict[str, Any]]:
    closes = [120, 121, 122, 123, 124, 125, 124, 123, 123.5, 122.5, 121.8, 121.0, 120.4]
    volumes = [900, 920, 930, 940, 950, 980, 1800, 1850, 1000, 1900, 1950, 2000, 2050]
    return [_bar(index, close, volume=volumes[index], width=1.6) for index, close in enumerate(closes)]


def _assert_common_contract(result: dict[str, Any]) -> None:
    assert result["schemaVersion"] == STOCK_STRUCTURE_DECISION_SCHEMA_VERSION
    assert result["structureState"] in {
        "uptrend",
        "breakout",
        "pullback",
        "consolidation",
        "extended",
        "distribution",
        "breakdown",
        "mixed",
        "lowConfidence",
    }
    assert result["confidence"] in {"high", "medium", "low"}
    assert set(result["componentScores"]) == REQUIRED_COMPONENT_SCORES
    assert set(result["explanation"]) == {
        "whyThisStructure",
        "whatConfirmsIt",
        "whatInvalidatesIt",
        "keyLevels",
    }
    assert set(result["researchNotes"]) == {"watchNext", "needsMoreEvidence", "riskFlags"}
    assert result["noAdviceDisclosure"]


def test_trending_breakout_emits_research_only_breakout_with_component_scores() -> None:
    result = build_stock_structure_decision(
        _trend_breakout_fixture(),
        benchmark_ohlcv=_benchmark_fixture(),
        sector_theme="software infrastructure",
        market_regime={"riskAppetite": "constructive"},
    )

    _assert_common_contract(result)
    assert result["structureState"] == "breakout"
    assert result["confidence"] == "high"
    assert result["componentScores"]["trend"] >= 70
    assert result["componentScores"]["relativeStrength"] >= 65
    assert result["componentScores"]["breakoutQuality"] >= 70
    assert result["componentScores"]["volumePressure"] >= 65
    assert result["componentScores"]["evidenceQuality"] >= 80
    assert result["explanation"]["keyLevels"]
    assert any(level["kind"] == "recentRangeHigh" for level in result["explanation"]["keyLevels"])
    assert "software infrastructure" in " ".join(result["researchNotes"]["watchNext"])


def test_low_quality_or_short_ohlcv_returns_low_confidence_without_guessing() -> None:
    result = build_stock_structure_decision(
        [
            {"open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1000},
            {"open": 10.5, "high": None, "low": 10, "close": 10.2, "volume": 900},
        ]
    )

    _assert_common_contract(result)
    assert result["structureState"] == "lowConfidence"
    assert result["confidence"] == "low"
    assert result["componentScores"]["evidenceQuality"] < 40
    assert result["researchNotes"]["needsMoreEvidence"]
    assert result["explanation"]["keyLevels"] == []


def test_extended_structure_is_flagged_when_price_is_far_above_mean_and_atr_proxy() -> None:
    result = build_stock_structure_decision(_extended_fixture())

    _assert_common_contract(result)
    assert result["structureState"] == "extended"
    assert result["componentScores"]["riskExtension"] >= 70
    assert result["confidence"] in {"medium", "high"}
    assert result["researchNotes"]["riskFlags"]


def test_consolidation_detects_range_compression_and_low_breakout_quality() -> None:
    result = build_stock_structure_decision(_consolidation_fixture())

    _assert_common_contract(result)
    assert result["structureState"] == "consolidation"
    assert result["componentScores"]["volatilityCompression"] >= 70
    assert result["componentScores"]["breakoutQuality"] < 60


def test_distribution_detects_heavy_volume_down_sessions_and_failed_highs() -> None:
    result = build_stock_structure_decision(_distribution_fixture())

    _assert_common_contract(result)
    assert result["structureState"] == "distribution"
    assert result["confidence"] in {"medium", "high"}
    assert result["componentScores"]["volumePressure"] <= 35
    assert any("distribution" in flag.lower() for flag in result["researchNotes"]["riskFlags"])


def test_serialized_output_avoids_advice_or_trading_instruction_vocabulary() -> None:
    result = build_stock_structure_decision(_trend_breakout_fixture(), benchmark_ohlcv=_benchmark_fixture())
    serialized = json.dumps(result, ensure_ascii=False).lower()

    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized
    assert "not personalized financial advice" in serialized
    assert "not an instruction" in serialized


def test_engine_stays_pure_and_provider_runtime_free() -> None:
    if not ENGINE_PATH.exists():
        pytest.fail(f"engine file missing: {ENGINE_PATH}")
    tree = ast.parse(ENGINE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    for forbidden in FORBIDDEN_IMPORT_PREFIXES:
        assert all(not module.startswith(forbidden) for module in imported_modules)
