# -*- coding: utf-8 -*-
"""Tests for the inert Liquidity limited-confidence projection helper."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from src.services.liquidity_limited_confidence_projection import (
    LIQUIDITY_LIMITED_CONFIDENCE_PROJECTION_VERSION,
    project_liquidity_limited_confidence,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/liquidity_limited_confidence_projection.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "apps",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "yfinance",
    "src.services.market_cache",
    "src.services.data_source_router",
    "src.services.liquidity_monitor_service",
    "src.services.liquidity_impulse_synthesis_service",
    "src.services.official_macro_liquidity_cache_contracts",
)


def _payload(
    *indicators: dict[str, Any],
    score: int = 37,
    regime: str = "supportive",
    score_contribution_allowed: bool = True,
    source_authority_allowed: bool = True,
) -> dict[str, Any]:
    return {
        "score": {"value": score, "regime": regime, "confidence": 0.82},
        "scoreContributionAllowed": score_contribution_allowed,
        "sourceAuthorityAllowed": source_authority_allowed,
        "indicators": list(indicators),
    }


def _pillar(
    key: str,
    pillar: str,
    direction: str,
    *,
    score_grade: bool = False,
    source: str = "fred",
    source_type: str = "official_public",
    freshness: str = "cached",
    included_in_score: bool | None = None,
    score_contribution_allowed: bool | None = None,
    source_authority_allowed: bool | None = None,
    is_fallback: bool = False,
    is_stale: bool = False,
    is_synthetic: bool = False,
    is_unavailable: bool = False,
) -> dict[str, Any]:
    if included_in_score is None:
        included_in_score = score_grade
    if score_contribution_allowed is None:
        score_contribution_allowed = score_grade
    if source_authority_allowed is None:
        source_authority_allowed = True
    input_row = {
        "key": key.upper(),
        "source": source,
        "sourceType": source_type,
        "freshness": freshness,
        "isFallback": is_fallback,
        "isStale": is_stale,
        "isSynthetic": is_synthetic,
        "isUnavailable": is_unavailable,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
    }
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "pillar": pillar,
        "direction": direction,
        "status": "live" if not is_unavailable else "unavailable",
        "freshness": freshness,
        "source": source,
        "sourceType": source_type,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "includedInScore": included_in_score,
        "scoreContribution": 6 if score_grade else 0,
        "coverageDiagnostics": {
            "sourceTier": source_type,
            "freshness": freshness,
            "scoreContributionAllowed": score_contribution_allowed,
            "sourceAuthorityAllowed": source_authority_allowed,
            "proxyOnly": "proxy" in source_type or "yfinance" in source,
        },
        "evidence": {
            "source": source,
            "sourceType": source_type,
            "freshness": freshness,
            "inputs": [input_row],
        },
    }


def test_projection_helper_is_pure_deterministic_and_inert() -> None:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    assert not [name for name in imports if name.startswith(FORBIDDEN_IMPORT_PREFIXES)]

    payload = _payload(
        _pillar("rates", "rates_pressure", "contracting", score_grade=True),
        _pillar("fed", "fed_liquidity", "contracting", score_grade=False),
    )
    original = copy.deepcopy(payload)

    first = project_liquidity_limited_confidence(payload)
    second = project_liquidity_limited_confidence(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert first["version"] == LIQUIDITY_LIMITED_CONFIDENCE_PROJECTION_VERSION
    assert first["authorityGrant"] is False
    assert first["decisionGrade"] is False


def test_single_score_grade_pillar_returns_limited_without_market_direction() -> None:
    projection = project_liquidity_limited_confidence(
        _payload(_pillar("rates", "rates_pressure", "contracting", score_grade=True))
    )

    assert projection["status"] == "single_indicator_limited"
    assert projection["confidence"] == "limited"
    assert projection["marketDirection"] is None
    assert projection["limitedConfidenceObservation"]["type"] == "single_indicator_limited"
    assert projection["limitedConfidenceObservation"]["marketDirection"] is None
    assert projection["authorityGrant"] is False
    assert projection["decisionGrade"] is False


def test_score_grade_plus_confirming_official_observation_enables_limited_direction() -> None:
    projection = project_liquidity_limited_confidence(
        _payload(
            _pillar("rates", "rates_pressure", "contracting", score_grade=True),
            _pillar("fed", "fed_liquidity", "contracting", score_grade=False),
        )
    )

    assert projection["status"] == "market_direction_limited"
    assert projection["confidence"] == "limited"
    assert projection["marketDirection"] == "contracting"
    assert projection["evidenceRule"] == "score_grade_plus_official_or_cache_observation"
    assert projection["qualifiedScoreGradePillarCount"] == 1
    assert projection["qualifiedObservationPillarCount"] == 1
    assert projection["authorityGrant"] is False
    assert projection["decisionGrade"] is False


def test_two_independent_official_or_cache_observation_pillars_enable_limited_direction() -> None:
    projection = project_liquidity_limited_confidence(
        _payload(
            _pillar("fed", "fed_liquidity", "expanding", score_grade=False, source_type="cache_snapshot"),
            _pillar("breadth", "breadth_confirmation", "expanding", score_grade=False),
        )
    )

    assert projection["status"] == "market_direction_limited"
    assert projection["marketDirection"] == "expanding"
    assert projection["evidenceRule"] == "two_independent_official_or_cache_observations"
    assert projection["qualifiedScoreGradePillarCount"] == 0
    assert projection["qualifiedObservationPillarCount"] == 2
    assert projection["confidence"] == "limited"


def test_conflicting_observation_does_not_upgrade_single_score_grade() -> None:
    projection = project_liquidity_limited_confidence(
        _payload(
            _pillar("rates", "rates_pressure", "contracting", score_grade=True),
            _pillar("fed", "fed_liquidity", "expanding", score_grade=False),
        )
    )

    assert projection["status"] == "single_indicator_limited"
    assert projection["marketDirection"] is None
    assert projection["limitedConfidenceObservation"]["type"] == "single_indicator_limited"
    assert "conflicting_official_or_cache_observation" in projection["blockingReasons"]


def test_same_pillar_observations_do_not_count_as_independent_pillars() -> None:
    projection = project_liquidity_limited_confidence(
        _payload(
            _pillar("fed_a", "fed_liquidity", "expanding", score_grade=False),
            _pillar("fed_b", "fed_liquidity", "expanding", score_grade=False, source_type="cache_snapshot"),
        )
    )

    assert projection["status"] == "insufficient_evidence"
    assert projection["marketDirection"] is None
    assert projection["qualifiedObservationPillarCount"] == 1
    assert "independent_pillar_count_below_minimum" in projection["blockingReasons"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"source": "yfinance", "source_type": "official_public"},
        {"source": "yfinance_proxy", "source_type": "official_public"},
        {"source": "proxy_feed", "source_type": "public_proxy"},
        {"source": "proxy_feed", "source_type": "unofficial_proxy"},
        {"source": "fallback", "source_type": "fallback_static", "freshness": "fallback", "is_fallback": True},
        {"source": "fred", "source_type": "official_public", "freshness": "stale", "is_stale": True},
        {"source": "fixture", "source_type": "synthetic_fixture", "freshness": "synthetic", "is_synthetic": True},
        {"source": "missing", "source_type": "unavailable", "freshness": "unavailable", "is_unavailable": True},
    ],
)
def test_non_qualifying_sources_never_satisfy_minimum_evidence(overrides: dict[str, Any]) -> None:
    projection = project_liquidity_limited_confidence(
        _payload(
            _pillar("rates", "rates_pressure", "contracting", score_grade=True),
            _pillar("candidate", "fed_liquidity", "contracting", score_grade=False, **overrides),
        )
    )

    assert projection["status"] == "single_indicator_limited"
    assert projection["marketDirection"] is None
    assert projection["qualifiedObservationPillarCount"] == 0
    assert projection["disqualifiedEvidenceCount"] >= 1


def test_projection_preserves_score_regime_and_authority_flags_verbatim() -> None:
    payload = _payload(
        _pillar("rates", "rates_pressure", "contracting", score_grade=True),
        score=37,
        regime="stress_watch",
        score_contribution_allowed=True,
        source_authority_allowed=True,
    )

    projection = project_liquidity_limited_confidence(payload)

    assert projection["inputState"]["score"] == {"value": 37, "regime": "stress_watch", "confidence": 0.82}
    assert projection["inputState"]["regime"] == "stress_watch"
    assert projection["inputState"]["scoreContributionAllowed"] is True
    assert projection["inputState"]["sourceAuthorityAllowed"] is True
    assert payload["score"]["value"] == 37
    assert payload["score"]["regime"] == "stress_watch"
    assert payload["scoreContributionAllowed"] is True
    assert payload["sourceAuthorityAllowed"] is True
    assert projection["authorityGrant"] is False
    assert projection["decisionGrade"] is False


def test_projection_fails_closed_when_no_minimum_evidence_exists() -> None:
    projection = project_liquidity_limited_confidence(
        _payload(
            _pillar(
                "proxy",
                "fed_liquidity",
                "expanding",
                score_grade=False,
                source="yfinance_proxy",
                source_type="unofficial_proxy",
                freshness="stale",
                is_stale=True,
            )
        )
    )

    assert projection["status"] == "insufficient_evidence"
    assert projection["confidence"] == "low"
    assert projection["marketDirection"] is None
    assert projection["limitedConfidenceObservation"] is None
    assert projection["authorityGrant"] is False
    assert projection["decisionGrade"] is False
