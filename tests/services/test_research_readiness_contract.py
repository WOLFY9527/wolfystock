# -*- coding: utf-8 -*-
"""Tests for the inert research-readiness projection contract."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.research_readiness_contract import (
    RESEARCH_READINESS_CONTRACT_VERSION,
    READINESS_STATE_VALUES,
    build_research_readiness_v1,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/research_readiness_contract.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.data_source_router",
    "src.services.provider_capability_matrix",
    "src.services.analysis_provider_planner",
)
REQUIRED_CONTRACT_FIELDS = {
    "researchReady",
    "readinessState",
    "verdictLabel",
    "blockingReasons",
    "missingEvidence",
    "evidenceCoverage",
    "sourceAuthority",
    "freshnessFloor",
    "consumerActionBoundary",
    "nextEvidenceNeeded",
    "debugRef",
}
FORBIDDEN_LABEL_WORDS = ("buy", "sell", "order", "trade", "下单", "买入", "卖出", "交易")


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _score_grade_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "requiredEvidence": ["technical", "fundamentals", "news"],
        "evidence": [
            {
                "domain": "technical",
                "source": "polygon_us_grouped_daily",
                "sourceType": "authorized_licensed_feed",
                "sourceTier": "score_grade",
                "trustLevel": "score_grade",
                "freshness": "fresh",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "coverage": 1.0,
            },
            {
                "domain": "fundamentals",
                "source": "fmp",
                "sourceType": "official_public",
                "sourceTier": "score_grade",
                "trustLevel": "score_grade",
                "freshness": "fresh",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "coverage": 1.0,
            },
            {
                "domain": "news",
                "source": "finnhub",
                "sourceType": "official_public",
                "sourceTier": "score_grade",
                "trustLevel": "score_grade_when_configured",
                "freshness": "fresh",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "coverage": 1.0,
            },
        ],
        "dataQualityReport": {
            "missingDomains": [],
            "confidenceCap": 1.0,
            "scoreCap": 1.0,
        },
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "source": "research_packet",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "score_grade",
        "trustLevel": "score_grade",
        "freshness": "fresh",
        "noAdviceBoundary": True,
        "debugRef": "analysis:run-123",
    }
    payload.update(overrides)
    return payload


def test_research_readiness_helper_is_pure_deterministic_and_json_safe() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    payload = _score_grade_payload()
    original = copy.deepcopy(payload)

    first = build_research_readiness_v1(payload)
    second = build_research_readiness_v1(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert REQUIRED_CONTRACT_FIELDS <= set(first)
    assert first["contractVersion"] == RESEARCH_READINESS_CONTRACT_VERSION


def test_ready_requires_complete_score_grade_evidence_authority_and_freshness() -> None:
    readiness = build_research_readiness_v1(_score_grade_payload())

    assert readiness["researchReady"] is True
    assert readiness["readinessState"] == "ready"
    assert readiness["readinessState"] in READINESS_STATE_VALUES
    assert readiness["verdictLabel"] == "研究证据可用"
    assert readiness["blockingReasons"] == []
    assert readiness["missingEvidence"] == []
    assert readiness["sourceAuthority"] == "scoreGradeAllowed"
    assert readiness["freshnessFloor"] == "fresh"
    assert readiness["consumerActionBoundary"] == "no_advice"
    assert readiness["nextEvidenceNeeded"] == []


def test_observe_only_keeps_observation_evidence_out_of_score_grade_readiness() -> None:
    payload = _score_grade_payload(
        evidence=[
            {
                "domain": "technical",
                "source": "yfinance_proxy",
                "sourceType": "public_proxy",
                "sourceTier": "unofficial_public_api",
                "trustLevel": "usable_with_caution",
                "freshness": "delayed",
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": False,
                "observationOnly": True,
                "coverage": 1.0,
                "proxyOnly": True,
            }
        ],
        requiredEvidence=["technical"],
        sourceAuthorityAllowed=False,
        scoreContributionAllowed=False,
        observationOnly=True,
        source="yfinance_proxy",
        sourceType="public_proxy",
        freshness="delayed",
    )

    readiness = build_research_readiness_v1(payload)

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "observe_only"
    assert readiness["verdictLabel"] == "仅观察"
    assert readiness["sourceAuthority"] == "observationOnly"
    assert readiness["consumerActionBoundary"] == "observe_only"
    assert "observation_only" in readiness["blockingReasons"]
    assert "source_authority_not_score_grade" in readiness["blockingReasons"]
    assert readiness["evidenceCoverage"] == {
        "scoreGradeCount": 0,
        "observationOnlyCount": 1,
        "missingCount": 0,
        "totalCount": 1,
    }


def test_insufficient_reports_missing_domains_from_data_quality_report() -> None:
    readiness = build_research_readiness_v1(
        _score_grade_payload(
            requiredEvidence=["technical", "fundamentals", "news", "macro"],
            dataQualityReport={"missingDomains": ["macro"], "confidenceCap": 0.6},
        )
    )

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "insufficient"
    assert readiness["verdictLabel"] == "证据不足"
    assert readiness["missingEvidence"] == ["macro"]
    assert "missing_required_evidence" in readiness["blockingReasons"]
    assert "score_cap_active" in readiness["blockingReasons"]
    assert readiness["nextEvidenceNeeded"][0] == "补充宏观证据"
    assert readiness["evidenceCoverage"]["missingCount"] == 1


def test_blocked_reports_safety_or_no_execution_boundaries_without_advice_copy() -> None:
    readiness = build_research_readiness_v1(
        _score_grade_payload(
            noAdviceBoundary=False,
            noOrderBoundary=True,
            noTradingBoundary=True,
            consumerActionBoundary="no_trade",
        )
    )

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "blocked"
    assert readiness["verdictLabel"] == "研究结论受限"
    assert readiness["consumerActionBoundary"] == "no_trade"
    assert "no_advice_boundary_missing" in readiness["blockingReasons"]
    assert "consumer_action_blocked" in readiness["blockingReasons"]
    assert all(word not in readiness["verdictLabel"].lower() for word in FORBIDDEN_LABEL_WORDS)


def test_waiting_state_is_preserved_for_pending_data_or_process() -> None:
    readiness = build_research_readiness_v1(
        _score_grade_payload(
            processingState="waiting",
            pendingEvidence=["news"],
            dataQualityReport={"missingDomains": ["news"], "status": "pending"},
        )
    )

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "waiting"
    assert readiness["verdictLabel"] == "等待证据更新"
    assert "evidence_pending" in readiness["blockingReasons"]
    assert readiness["missingEvidence"] == ["news"]
    assert readiness["nextEvidenceNeeded"][0] == "等待新闻证据"


def test_unknown_missing_metadata_fails_closed_and_never_becomes_ready() -> None:
    readiness = build_research_readiness_v1({})

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "insufficient"
    assert readiness["sourceAuthority"] == "unavailable"
    assert readiness["freshnessFloor"] == "unknown"
    assert readiness["consumerActionBoundary"] == "no_advice"
    assert "critical_metadata_missing" in readiness["blockingReasons"]
    assert "source_authority" in readiness["missingEvidence"]
    assert "freshness" in readiness["missingEvidence"]


def test_stale_fallback_proxy_fixture_and_synthetic_inputs_are_capped_to_observe_only() -> None:
    readiness = build_research_readiness_v1(
        _score_grade_payload(
            requiredEvidence=["technical", "fundamentals"],
            evidence=[
                {
                    "domain": "technical",
                    "source": "yfinance_proxy",
                    "sourceType": "public_proxy",
                    "freshness": "stale",
                    "proxyOnly": True,
                    "isStale": True,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "domain": "fundamentals",
                    "source": "fixture",
                    "sourceType": "synthetic_fixture",
                    "freshness": "synthetic",
                    "isFallback": True,
                    "isSynthetic": True,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
            ],
            source="yfinance_proxy",
            sourceType="public_proxy",
            freshness="stale",
            proxyOnly=True,
            isFallback=True,
            sourceAuthorityAllowed=True,
            scoreContributionAllowed=True,
        )
    )

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "observe_only"
    assert readiness["sourceAuthority"] == "observationOnly"
    assert readiness["freshnessFloor"] == "synthetic"
    assert "public_proxy_evidence" in readiness["blockingReasons"]
    assert "stale_evidence" in readiness["blockingReasons"]
    assert "fallback_evidence" in readiness["blockingReasons"]
    assert "synthetic_evidence" in readiness["blockingReasons"]
    assert readiness["evidenceCoverage"] == {
        "scoreGradeCount": 0,
        "observationOnlyCount": 2,
        "missingCount": 0,
        "totalCount": 2,
    }


def test_evidence_coverage_counts_score_grade_observation_only_and_missing_domains() -> None:
    readiness = build_research_readiness_v1(
        _score_grade_payload(
            requiredEvidence=["technical", "fundamentals", "news", "macro"],
            evidence=[
                {
                    "domain": "technical",
                    "source": "polygon_us_grouped_daily",
                    "sourceType": "authorized_licensed_feed",
                    "sourceTier": "score_grade",
                    "trustLevel": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "domain": "fundamentals",
                    "source": "fmp",
                    "sourceType": "official_public",
                    "sourceTier": "score_grade",
                    "trustLevel": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "domain": "news",
                    "source": "gnews",
                    "sourceType": "public_api",
                    "trustLevel": "usable_with_caution",
                    "freshness": "delayed",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "observationOnly": True,
                },
            ],
        )
    )

    assert readiness["evidenceCoverage"] == {
        "scoreGradeCount": 2,
        "observationOnlyCount": 1,
        "missingCount": 1,
        "totalCount": 4,
    }
    assert readiness["missingEvidence"] == ["macro"]
    assert readiness["readinessState"] == "insufficient"
