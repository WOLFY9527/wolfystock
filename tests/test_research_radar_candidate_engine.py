# -*- coding: utf-8 -*-
"""Contract tests for the standalone Research Radar Candidate Engine."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.research_radar_candidate_engine import (
    RESEARCH_RADAR_CANDIDATE_ENGINE_SCHEMA_VERSION,
    build_research_radar_candidate_queue,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DRIVER_KEYS = {
    "relativeStrength",
    "volumeExpansion",
    "trendStructure",
    "themeAlignment",
    "regimeFit",
    "eventCatalyst",
    "liquidityTradability",
    "evidenceQuality",
}
ALLOWED_PRIORITIES = {"high", "medium", "low"}
ALLOWED_BIASES = {
    "strengthContinuation",
    "breakoutWatch",
    "pullbackWatch",
    "eventDriven",
    "volatilityRisk",
    "avoidLowEvidence",
    "mixed",
}
FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "position",
    "target",
    "stop",
    "recommendation",
    "下单",
    "买入",
    "卖出",
    "止损",
    "止盈",
    "目标",
    "仓位",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "src.services.market_scanner_service",
    "src.services.watchlist_service",
    "src.services.market_overview_service",
    "src.services.market_rotation_radar_service",
    "api.deps",
    "src.auth",
    "src.storage",
)


@dataclass(frozen=True)
class CandidateInput:
    symbol: str
    relative_strength: float
    volume_expansion: float
    trend_state: str
    themes: tuple[str, ...]
    avg_amount_20: float
    evidence_quality: str


def _serialized_values(payload: object) -> str:
    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)
    return json.dumps(values, ensure_ascii=False, sort_keys=True).lower()


def _assert_queue_item_shape(item: dict[str, Any]) -> None:
    assert {"ticker", "symbol", "priority", "researchBias", "driverScores", "explanation", "riskFlags", "noAdviceDisclosure"}.issubset(
        item
    )
    assert item["priority"] in ALLOWED_PRIORITIES
    assert item["researchBias"] in ALLOWED_BIASES
    assert set(item["driverScores"]) == EXPECTED_DRIVER_KEYS
    assert all(isinstance(score, int) for score in item["driverScores"].values())
    assert all(0 <= score <= 100 for score in item["driverScores"].values())
    assert set(item["explanation"]) == {"whyOnRadar", "whatToVerify", "whyNotHigherPriority", "evidenceGaps", "invalidationObservations"}
    assert isinstance(item["duplicateEvidenceMerged"], int)
    assert item["noAdviceDisclosure"]


def test_research_radar_builds_prioritized_queue_with_required_contract_shape() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "ticker": "ALFA",
                "relativeStrength": 88,
                "volumeExpansion": 1.8,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "eventCatalyst": {"state": "confirmed", "label": "earnings review"},
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.88},
            },
            {
                "ticker": "BETA",
                "relativeStrength": 52,
                "volumeExpansion": 1.0,
                "trendStructure": "range",
                "themes": ["Defensive"],
                "avgDollarVolume": 8_000_000,
                "evidenceQuality": {"state": "partial", "score": 0.54},
            },
        ],
        market_regime_context={
            "regime": "risk_on",
            "favorableThemes": ["AI Infrastructure", "Semiconductors"],
            "unfavorableThemes": ["Defensive"],
        },
        theme_leadership_context={
            "dominantThemes": [
                {"name": "AI Infrastructure", "leadershipScore": 86},
                {"name": "Semiconductors", "leadershipScore": 80},
            ]
        },
    )

    assert payload["schemaVersion"] == RESEARCH_RADAR_CANDIDATE_ENGINE_SCHEMA_VERSION
    assert [item["ticker"] for item in payload["researchQueue"]] == ["ALFA", "BETA"]
    assert payload["researchQueue"][0]["priority"] == "high"
    assert payload["researchQueue"][0]["researchBias"] in {"strengthContinuation", "breakoutWatch", "eventDriven"}
    assert len([score for score in payload["researchQueue"][0]["driverScores"].values() if score >= 65]) >= 3
    assert payload["researchQueue"][1]["priority"] in {"medium", "low"}

    for item in payload["researchQueue"]:
        _assert_queue_item_shape(item)

    assert payload["summary"]["dominantThemes"] == ["AI Infrastructure", "Semiconductors"]
    assert payload["summary"]["marketContextFit"] in {"supportive", "mixed", "neutral", "conflicting", "unavailable"}
    assert payload["summary"]["queueQuality"] in {"strong", "mixed", "thin", "low_evidence"}


def test_missing_evidence_and_low_liquidity_force_low_priority_and_avoid_low_evidence() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "symbol": "THIN",
                "relativeStrength": 91,
                "volumeExpansion": 2.4,
                "trendStructure": "breakout",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 1_500_000,
                "evidenceQuality": {"state": "missing", "score": 0.18, "missing": ["priceHistory", "newsCatalyst"]},
            }
        ],
        theme_leadership_context={"dominantThemes": ["AI Infrastructure"]},
    )

    item = payload["researchQueue"][0]

    assert item["ticker"] == "THIN"
    assert item["priority"] == "low"
    assert item["researchBias"] == "avoidLowEvidence"
    assert "low_liquidity" in item["riskFlags"]
    assert "missing_evidence" in item["riskFlags"]
    assert payload["summary"]["evidenceGaps"] == ["priceHistory", "newsCatalyst"]


def test_theme_boost_does_not_override_poor_evidence_or_conflicting_regime() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "ticker": "HOT",
                "relativeStrength": 84,
                "volumeExpansion": 1.7,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 95_000_000,
                "evidenceQuality": {"state": "partial", "score": 0.42, "missing": ["fundamentals"]},
            }
        ],
        market_regime_context={
            "regime": "risk_off",
            "unfavorableThemes": ["AI Infrastructure"],
        },
        theme_leadership_context={"dominantThemes": ["AI Infrastructure"]},
    )

    item = payload["researchQueue"][0]

    assert item["driverScores"]["themeAlignment"] >= 65
    assert item["driverScores"]["regimeFit"] < 50
    assert item["priority"] != "high"
    assert "theme_regime_conflict" in item["riskFlags"]
    assert "fundamentals" in payload["summary"]["evidenceGaps"]


def test_missing_regime_context_is_neutral_and_dataclass_inputs_are_supported() -> None:
    payload = build_research_radar_candidate_queue(
        [
            CandidateInput(
                symbol="OMEGA",
                relative_strength=72,
                volume_expansion=1.35,
                trend_state="pullback_near_support",
                themes=("Industrials",),
                avg_amount_20=80_000_000,
                evidence_quality="complete",
            )
        ],
        market_regime_context=None,
        stock_structure_context={"OMEGA": {"extensionPct": -3.2, "volatilityPct": 3.1}},
        theme_leadership_context={"themes": [{"theme": "Industrials", "score": 70}]},
    )

    item = payload["researchQueue"][0]

    assert item["driverScores"]["regimeFit"] == 50
    assert item["priority"] == "medium"
    assert item["researchBias"] == "pullbackWatch"
    assert payload["summary"]["marketContextFit"] == "neutral"


def test_research_radar_output_is_deterministic_and_public_safe() -> None:
    candidates = [
        {"symbol": "CCC", "relativeStrength": 70, "volumeExpansion": 1.4, "avgDollarVolume": 50_000_000},
        {"symbol": "AAA", "relativeStrength": 70, "volumeExpansion": 1.4, "avgDollarVolume": 50_000_000},
    ]

    first = build_research_radar_candidate_queue(candidates)
    second = build_research_radar_candidate_queue(list(reversed(candidates)))

    assert [item["ticker"] for item in first["researchQueue"]] == ["AAA", "CCC"]
    assert first == second

    serialized = _serialized_values(first)
    leaked = [term for term in FORBIDDEN_PUBLIC_TERMS if term.lower() in serialized]
    assert leaked == []


def test_research_radar_service_has_no_runtime_or_protected_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "research_radar_candidate_engine.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported_modules.add(node.module)
            imported_modules.update(
                f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"
            )

    violations = sorted(
        module
        for module in imported_modules
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert violations == []


def test_duplicate_candidates_keep_strongest_evidence_and_record_merge_count() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "ticker": "DUPL",
                "relativeStrength": 48,
                "volumeExpansion": 0.9,
                "trendStructure": "range",
                "themes": ["Defensive"],
                "avgDollarVolume": 8_000_000,
                "evidenceQuality": {"state": "missing", "score": 0.18, "missing": ["priceHistory"]},
            },
            {
                "ticker": "DUPL",
                "relativeStrength": 88,
                "volumeExpansion": 1.8,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.88},
            },
        ],
        market_regime_context={"regime": "riskOn", "favorableThemes": ["AI Infrastructure"]},
        theme_leadership_context={"dominantThemes": [{"name": "AI Infrastructure", "leadershipScore": 86}]},
    )

    assert [item["ticker"] for item in payload["researchQueue"]] == ["DUPL"]
    item = payload["researchQueue"][0]
    assert item["priority"] == "high"
    assert item["driverScores"]["evidenceQuality"] >= 80
    assert item["duplicateEvidenceMerged"] == 1
    assert payload["summary"]["duplicateEvidenceMerged"] == 1


def test_stable_sort_uses_evidence_quality_before_symbol_when_priority_and_score_tie() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "ticker": "AAA",
                "relativeStrength": 85,
                "volumeExpansion": 1.2,
                "trendStructure": "range",
                "avgDollarVolume": 80_000_000,
                "evidenceQuality": {"state": "partial", "score": 0.60},
            },
            {
                "ticker": "ZZZ",
                "relativeStrength": 70,
                "volumeExpansion": 1.2,
                "trendStructure": "range",
                "avgDollarVolume": 80_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.80},
            },
        ]
    )

    assert [item["ticker"] for item in payload["researchQueue"]] == ["ZZZ", "AAA"]


def test_regime_labels_adjust_fit_without_creating_advice_or_overriding_mixed_regime() -> None:
    risk_on = build_research_radar_candidate_queue(
        [
            {
                "ticker": "BRK",
                "relativeStrength": 82,
                "volumeExpansion": 1.7,
                "trendStructure": "breakout",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 100_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.86},
            }
        ],
        market_regime_context={"regime": "riskOn"},
    )["researchQueue"][0]
    mixed = build_research_radar_candidate_queue(
        [
            {
                "ticker": "BRK",
                "relativeStrength": 82,
                "volumeExpansion": 1.7,
                "trendStructure": "breakout",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 100_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.86},
            }
        ],
        market_regime_context={"regime": "mixed"},
    )["researchQueue"][0]

    assert risk_on["driverScores"]["regimeFit"] >= 70
    assert risk_on["priority"] == "high"
    assert mixed["driverScores"]["regimeFit"] <= 45
    assert mixed["priority"] != "high"
    assert any("mixed" in text.lower() for text in mixed["explanation"]["whyNotHigherPriority"])


def test_risk_off_and_event_risk_support_low_evidence_or_volatility_watch_biases() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "ticker": "VOLR",
                "relativeStrength": 62,
                "volumeExpansion": 1.1,
                "trendStructure": "volatile",
                "volatilityPct": 9.2,
                "avgDollarVolume": 70_000_000,
                "evidenceQuality": {"state": "partial", "score": 0.56},
            },
            {
                "ticker": "GAPR",
                "relativeStrength": 86,
                "volumeExpansion": 1.6,
                "trendStructure": "confirmed_uptrend",
                "avgDollarVolume": 70_000_000,
                "evidenceQuality": {"state": "missing", "score": 0.22},
            },
        ],
        market_regime_context={"regime": "eventRisk"},
    )

    by_ticker = {item["ticker"]: item for item in payload["researchQueue"]}
    assert by_ticker["VOLR"]["researchBias"] == "volatilityRisk"
    assert by_ticker["VOLR"]["driverScores"]["regimeFit"] >= 60
    assert by_ticker["GAPR"]["researchBias"] == "avoidLowEvidence"
    assert by_ticker["GAPR"]["driverScores"]["regimeFit"] >= 60


def test_stale_fallback_proxy_and_sample_only_evidence_caps_priority_and_explains_gaps() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "ticker": "WEAK",
                "relativeStrength": 92,
                "volumeExpansion": 2.1,
                "trendStructure": "breakout",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 140_000_000,
                "evidenceQuality": {
                    "state": "complete",
                    "score": 0.92,
                    "isStale": True,
                    "isFallback": True,
                    "isProxy": True,
                    "sampleOnly": True,
                },
            }
        ],
        market_regime_context={"regime": "riskOn"},
        theme_leadership_context={"dominantThemes": ["AI Infrastructure"]},
    )

    item = payload["researchQueue"][0]
    assert item["priority"] != "high"
    assert item["driverScores"]["evidenceQuality"] < 60
    assert {"staleEvidence", "fallbackEvidence", "proxyEvidence", "sampleOnlyEvidence"}.issubset(
        set(item["explanation"]["evidenceGaps"])
    )
    assert "low_evidence_quality" in item["riskFlags"]


def test_queue_diversity_avoids_all_high_priority_entries_from_same_theme_when_alternatives_exist() -> None:
    payload = build_research_radar_candidate_queue(
        [
            {
                "ticker": "AI1",
                "relativeStrength": 90,
                "volumeExpansion": 1.9,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.9},
            },
            {
                "ticker": "AI2",
                "relativeStrength": 89,
                "volumeExpansion": 1.9,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.9},
            },
            {
                "ticker": "SEMI",
                "relativeStrength": 88,
                "volumeExpansion": 1.8,
                "trendStructure": "confirmed_uptrend",
                "themes": ["Semiconductors"],
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.9},
            },
        ],
        market_regime_context={"regime": "riskOn", "favorableThemes": ["AI Infrastructure", "Semiconductors"]},
        theme_leadership_context={
            "dominantThemes": [
                {"name": "AI Infrastructure", "leadershipScore": 90},
                {"name": "Semiconductors", "leadershipScore": 88},
            ]
        },
    )

    high_items = [item for item in payload["researchQueue"] if item["priority"] == "high"]
    high_themes = [
        item["ticker"]
        for item in high_items
        if item["ticker"] in {"AI1", "AI2", "SEMI"}
    ]
    assert "SEMI" in high_themes
    assert not ({"AI1", "AI2"}.issubset(high_themes) and "SEMI" not in high_themes)
    assert payload["summary"]["queueDiversity"]["status"] == "diversified"
