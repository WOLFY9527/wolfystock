# -*- coding: utf-8 -*-
"""Pure source-tier trust gate contracts for Market Intelligence."""

from __future__ import annotations

import importlib
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec


class _ForbiddenImportBlocker(MetaPathFinder):
    def __init__(self) -> None:
        self.blocked: list[str] = []

    def find_spec(self, fullname: str, path: object | None, target: object | None = None) -> ModuleSpec | None:
        forbidden_prefixes = (
            "requests",
            "httpx",
            "yfinance",
            "src.services.market_cache",
            "src.services.market_overview_service",
            "src.services.market_rotation_radar_service",
            "src.services.liquidity_monitor_service",
            "src.storage",
        )
        for prefix in forbidden_prefixes:
            if fullname == prefix or fullname.startswith(f"{prefix}."):
                self.blocked.append(fullname)
                raise AssertionError(f"market_intelligence_trust_gate imported forbidden module {fullname}")
        return None


def test_market_intelligence_trust_gate_import_is_inert() -> None:
    sys.modules.pop("src.services.market_intelligence_trust_gate", None)
    blocker = _ForbiddenImportBlocker()
    before = set(sys.modules)
    sys.meta_path.insert(0, blocker)
    try:
        module = importlib.import_module("src.services.market_intelligence_trust_gate")
    finally:
        sys.meta_path.remove(blocker)

    after = set(sys.modules)
    assert module is not None
    assert blocker.blocked == []
    assert "src.services.market_cache" not in after - before
    assert "src.storage" not in after - before


def test_fallback_static_web_and_synthetic_sources_cannot_be_reliable() -> None:
    from src.services.market_intelligence_trust_gate import evaluate_market_intelligence_trust

    cases = [
        (
            {
                "source": "fallback",
                "sourceType": "fallback_static",
                "freshness": "live",
                "isFallback": True,
                "coverage": 1.0,
            },
            "static_fallback",
        ),
        (
            {
                "sourceTier": "public_web_fallback",
                "freshness": "live",
                "coverage": 1.0,
            },
            "public_web_fallback",
        ),
        (
            {
                "source": "synthetic_fixture",
                "sourceType": "synthetic_fixture",
                "freshness": "live",
                "isSynthetic": True,
                "coverage": 1.0,
            },
            "synthetic",
        ),
    ]

    for payload, expected_tier in cases:
        result = evaluate_market_intelligence_trust(payload)

        assert result["sourceTier"] == expected_tier
        assert result["isReliable"] is False
        assert result["trustLevel"] == "weak"
        assert result["conclusionAllowed"] is False
        assert result["scoreCap"] < 1.0
        assert result["freshness"] not in {"fresh", "live"}
        assert result["degradationReasons"]
        assert result["warning"]


def test_stale_data_caps_trust_below_reliable() -> None:
    from src.services.market_intelligence_trust_gate import evaluate_market_intelligence_trust

    result = evaluate_market_intelligence_trust(
        {
            "source": "treasury",
            "sourceType": "official_public",
            "freshness": "stale",
            "isStale": True,
            "coverage": 1.0,
        }
    )

    assert result["sourceTier"] == "official_public"
    assert result["isReliable"] is False
    assert result["trustLevel"] == "usable_with_caution"
    assert result["scoreCap"] == 0.6
    assert result["conclusionAllowed"] is True
    assert "stale_source" in result["degradationReasons"]


def test_low_coverage_caps_trust_and_blocks_conclusions() -> None:
    from src.services.market_intelligence_trust_gate import evaluate_market_intelligence_trust

    result = evaluate_market_intelligence_trust(
        {
            "source": "fred",
            "sourceType": "official_public",
            "freshness": "fresh",
            "coverage": 0.35,
        }
    )

    assert result["isReliable"] is False
    assert result["trustLevel"] == "weak"
    assert result["scoreCap"] == 0.4
    assert result["conclusionAllowed"] is False
    assert "low_coverage" in result["degradationReasons"]


def test_mixed_source_tiers_are_partial_and_usable_with_caution() -> None:
    from src.services.market_intelligence_trust_gate import evaluate_market_intelligence_trust_from_sources

    result = evaluate_market_intelligence_trust_from_sources(
        [
            {
                "source": "treasury",
                "sourceType": "official_public",
                "freshness": "fresh",
                "coverage": 1.0,
            },
            {
                "source": "cache",
                "sourceType": "cache_snapshot",
                "freshness": "cached",
                "coverage": 1.0,
            },
        ],
        coverage=0.6,
    )

    assert result["sourceTier"] == "snapshot"
    assert result["freshness"] == "partial"
    assert result["isReliable"] is False
    assert result["trustLevel"] == "usable_with_caution"
    assert result["conclusionAllowed"] is True
    assert result["scoreCap"] == 0.7
    assert "mixed_source_tiers" in result["degradationReasons"]
    assert "partial_coverage" in result["degradationReasons"]


def test_official_fresh_high_coverage_data_can_be_reliable() -> None:
    from src.services.market_intelligence_trust_gate import evaluate_market_intelligence_trust

    result = evaluate_market_intelligence_trust(
        {
            "source": "fred",
            "sourceType": "official_public",
            "freshness": "fresh",
            "coverage": 1.0,
        }
    )

    assert result == {
        "isReliable": True,
        "trustLevel": "reliable",
        "coverage": 1.0,
        "sourceTier": "official_public",
        "freshness": "fresh",
        "degradationReasons": [],
        "scoreCap": 1.0,
        "conclusionAllowed": True,
        "warning": None,
    }


def test_unavailable_data_cannot_produce_strong_conclusions() -> None:
    from src.services.market_intelligence_trust_gate import evaluate_market_intelligence_trust

    result = evaluate_market_intelligence_trust(
        {
            "source": "unavailable",
            "sourceType": "missing",
            "freshness": "live",
            "isUnavailable": True,
            "coverage": 1.0,
        }
    )

    assert result["sourceTier"] == "unavailable"
    assert result["freshness"] == "unavailable"
    assert result["trustLevel"] == "unavailable"
    assert result["isReliable"] is False
    assert result["scoreCap"] == 0.0
    assert result["coverage"] == 0.0
    assert result["conclusionAllowed"] is False
    assert "unavailable_source" in result["degradationReasons"]
