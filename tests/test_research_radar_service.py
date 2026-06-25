# -*- coding: utf-8 -*-
"""Contract tests for the backend Research Radar API service."""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.services.research_radar_service import (
    RESEARCH_RADAR_API_SCHEMA_VERSION,
    ResearchRadarService,
)
from src.services.research_radar_candidate_engine import build_research_radar_candidate_queue


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PUBLIC_RE = re.compile(
    r"\b(buy|sell|hold|recommendation|target|stop|position\s*siz(?:e|ing))\b|下单|买入|卖出|止损|止盈|目标|仓位",
    re.IGNORECASE,
)
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "src.services.market_scanner_service",
    "src.services.watchlist_service",
    "src.services.market_overview_service",
    "src.services.market_rotation_radar_service",
    "src.auth",
)
INTERNAL_CODE_RE = re.compile(r"[a-z][a-z0-9]*_[a-z0-9_]+|[a-zA-Z]+:[a-zA-Z0-9_.-]+|=")
FORBIDDEN_EVIDENCE_HUB_RE = re.compile(
    r"provider|request[_\s-]?id|trace[_\s-]?id|cache|raw|debug|schemaVersion|token|stack|secret|env",
    re.IGNORECASE,
)


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for nested in value.values():
            result.extend(_string_values(nested))
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for nested in value:
            result.extend(_string_values(nested))
        return result
    return []


def _assert_consumer_issues_safe(issues: object, raw_codes: tuple[str, ...]) -> None:
    serialized = _serialized(issues)
    for raw_code in raw_codes:
        if INTERNAL_CODE_RE.search(raw_code) or raw_code != raw_code.lower():
            assert raw_code.lower() not in serialized
    assert INTERNAL_CODE_RE.search(serialized) is None
    assert FORBIDDEN_PUBLIC_RE.search(serialized) is None


def _assert_display_ready_fields_safe(value: object, raw_codes: tuple[str, ...]) -> None:
    serialized = _serialized(value)
    for raw_code in raw_codes:
        assert raw_code.lower() not in serialized
    assert INTERNAL_CODE_RE.search(serialized) is None
    assert FORBIDDEN_PUBLIC_RE.search(serialized) is None


def _fixed_now() -> datetime:
    return datetime(2026, 6, 15, 9, 30, tzinfo=timezone.utc)


def _assert_required_top_level_shape(payload: dict[str, Any]) -> None:
    assert {
        "schemaVersion",
        "generatedAt",
        "researchQueue",
        "aggregateSummary",
        "evidenceGaps",
        "evidenceGapsRaw",
        "marketContextFit",
        "drilldownTargets",
        "noAdviceDisclosure",
        "dataQuality",
        "evidenceHub",
        "consumerIssues",
        "onboardingGuidance",
        "emptyStateActions",
        "starterResearchWorkflow",
        "firstRunChecklist",
        "suggestedResearchEntrypoints",
        "observationOnly",
        "decisionGrade",
    }.issubset(payload)
    assert payload["schemaVersion"] == RESEARCH_RADAR_API_SCHEMA_VERSION
    assert payload["generatedAt"] == "2026-06-15T09:30:00+00:00"
    assert payload["noAdviceDisclosure"]
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert isinstance(payload["researchQueue"], list)
    assert isinstance(payload["evidenceGaps"], list)
    assert isinstance(payload["evidenceGapsRaw"], list)
    assert isinstance(payload["drilldownTargets"], list)
    assert {"scannerCandidates", "backtestSamples", "stockReadiness", "dataActivation", "missingEvidenceStates"}.issubset(
        payload["evidenceHub"]
    )


def test_build_radar_projects_engine_output_to_required_api_contract() -> None:
    payload = ResearchRadarService(now=_fixed_now).build_radar(
        candidates=[
            {
                "ticker": "ALFA",
                "relativeStrength": 88,
                "volumeExpansion": 1.8,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "eventCatalyst": {"state": "confirmed"},
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.88},
            }
        ],
        market_regime_context={
            "regime": "risk_on",
            "favorableThemes": ["AI Infrastructure"],
        },
        theme_leadership_context={
            "dominantThemes": [{"name": "AI Infrastructure", "leadershipScore": 86}]
        },
    )

    _assert_required_top_level_shape(payload)
    assert payload["marketContextFit"] == "supportive"
    assert payload["dataQuality"]["status"] == "ready"
    assert payload["aggregateSummary"]["priorityCounts"]["high"] == 1

    item = payload["researchQueue"][0]
    assert {
        "symbol",
        "ticker",
        "priority",
        "researchBias",
        "driverScores",
        "whyOnRadar",
        "whatToVerify",
        "whyNotHigherPriority",
        "evidenceGaps",
        "invalidationObservations",
        "duplicateEvidenceMerged",
        "riskFlags",
        "riskFlagsRaw",
        "riskFlagLabels",
        "researchBiasRaw",
        "researchBiasLabel",
        "researchBiasMessage",
        "evidenceGapsRaw",
        "consumerEvidenceGaps",
        "drilldownTargets",
        "evidenceQuality",
        "consumerIssues",
        "noAdviceDisclosure",
        "observationOnly",
        "decisionGrade",
    }.issubset(item)
    assert item["symbol"] == "ALFA"
    assert item["ticker"] == "ALFA"
    assert item["priority"] == "high"
    assert item["researchBiasRaw"] == "eventDriven"
    assert item["researchBias"] == item["researchBiasLabel"]
    assert item["researchBiasLabel"] == "Event-driven observation"
    assert item["researchBiasMessage"]
    assert item["evidenceQuality"]["status"] == "complete"
    assert item["whyOnRadar"]
    assert item["whatToVerify"]
    assert item["whyNotHigherPriority"]
    assert isinstance(item["evidenceGaps"], list)
    assert item["duplicateEvidenceMerged"] == 0
    assert item["invalidationObservations"]
    assert item["drilldownTargets"] == [
        {
            "label": "Structure detail",
            "route": "/stocks/ALFA/structure-decision",
            "reason": "Open the structure workspace for this ticker.",
        }
    ]
    assert payload["drilldownTargets"] == item["drilldownTargets"]
    assert item["observationOnly"] is True
    assert item["decisionGrade"] is False
    assert payload["aggregateSummary"]["duplicateEvidenceMerged"] == 0
    assert payload["aggregateSummary"]["queueDiversity"]["status"] in {"thin", "mixed", "diversified", "concentrated"}

    assert FORBIDDEN_PUBLIC_RE.search(" ".join(_string_values(payload))) is None


def test_empty_or_missing_candidates_fail_closed_with_degraded_queue() -> None:
    payload = ResearchRadarService(now=_fixed_now).build_radar(candidates=[])

    _assert_required_top_level_shape(payload)
    assert payload["researchQueue"] == []
    assert payload["dataQuality"]["status"] == "degraded"
    assert payload["dataQuality"]["missingEvidence"] == ["Research candidates unavailable"]
    assert payload["dataQuality"]["missingEvidenceRaw"] == ["scannerCandidates"]
    assert payload["evidenceGaps"] == ["Research candidates unavailable"]
    assert payload["evidenceGapsRaw"] == ["scannerCandidates"]
    assert payload["marketContextFit"] == "unavailable"
    assert payload["aggregateSummary"]["queueQuality"] == "degraded"
    assert payload["consumerIssues"]
    assert payload["dataQuality"]["consumerIssues"]


def test_research_radar_evidence_hub_surfaces_real_evidence_readiness() -> None:
    calls: list[str] = []

    def _backtest_reader(symbol: str) -> dict[str, object]:
        calls.append(symbol)
        return {
            "code": symbol,
            "prepared_count": 12,
            "sample_readiness_state": "ready",
            "execution_readiness": {"state": "executable", "observation_only": True},
        }

    payload = ResearchRadarService(
        now=_fixed_now,
        backtest_sample_reader=_backtest_reader,
    ).build_radar(
        candidates=[
            {
                "ticker": "ALFA",
                "relativeStrength": 88,
                "volumeExpansion": 1.8,
                "trendScore": 82,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "eventCatalyst": {"state": "confirmed"},
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 88},
            }
        ],
        market_regime_context={
            "regime": "risk_on",
            "favorableThemes": ["AI Infrastructure"],
        },
        theme_leadership_context={
            "dominantThemes": [{"name": "AI Infrastructure", "leadershipScore": 86}]
        },
    )

    hub = payload["evidenceHub"]
    assert calls == ["ALFA"]
    assert hub["scannerCandidates"]["status"] == "available"
    assert hub["scannerCandidates"]["symbols"] == ["ALFA"]
    assert hub["backtestSamples"]["status"] == "available"
    assert hub["backtestSamples"]["evidenceCount"] == 1
    assert hub["stockReadiness"]["status"] == "available"
    assert hub["dataActivation"]["status"] == "available"
    assert hub["missingEvidenceStates"] == []
    assert FORBIDDEN_EVIDENCE_HUB_RE.search(_serialized(hub)) is None
    assert FORBIDDEN_PUBLIC_RE.search(_serialized(hub)) is None


def test_research_radar_evidence_hub_reports_blockers_without_internal_leakage() -> None:
    def _backtest_reader(symbol: str) -> dict[str, object]:
        return {
            "code": symbol,
            "prepared_count": 0,
            "sample_readiness_state": "missing_cache",
            "execution_readiness": {
                "state": "data_disabled",
                "reason_codes": ["provider_missing", "request_id=req-123"],
            },
            "raw_payload": {"trace_id": "trace-999", "token": "secret"},
        }

    payload = ResearchRadarService(
        now=_fixed_now,
        backtest_sample_reader=_backtest_reader,
    ).build_radar(
        candidates=[
            {
                "ticker": "THIN",
                "relativeStrength": 60,
                "volumeExpansion": 1.1,
                "trendStructure": "mixed",
                "avgDollarVolume": 50_000_000,
                "evidenceQuality": {"state": "complete", "score": 70},
            }
        ]
    )

    hub = payload["evidenceHub"]
    assert hub["scannerCandidates"]["status"] == "available"
    assert hub["backtestSamples"]["status"] == "blocked"
    assert hub["backtestSamples"]["blocker"] == "Backtest samples have not been prepared for the radar symbols."
    assert hub["backtestSamples"]["nextDataAction"] == (
        "Open Backtest and prepare or refresh samples for the radar symbols."
    )
    assert hub["stockReadiness"]["status"] in {"available", "partial"}
    assert hub["dataActivation"]["status"] == "partial"
    assert [item["key"] for item in hub["missingEvidenceStates"]] == ["backtest", "data"]
    serialized = _serialized(hub)
    assert FORBIDDEN_EVIDENCE_HUB_RE.search(serialized) is None
    assert FORBIDDEN_PUBLIC_RE.search(serialized) is None


def test_low_evidence_queue_keeps_raw_codes_separate_from_consumer_issues() -> None:
    payload = ResearchRadarService(now=_fixed_now).build_radar(
        candidates=[
            {
                "ticker": "THIN",
                "relativeStrength": 35,
                "volumeExpansion": 0.5,
                "trendStructure": "weak",
                "avgDollarVolume": 1000,
                "evidenceQuality": {
                    "state": "missing",
                    "score": 10,
                    "missing": ["fundamentals", "news", "catalyst", "freshness"],
                },
            }
        ]
    )

    item = payload["researchQueue"][0]
    raw_codes = (
        "avoidLowEvidence",
        "low_liquidity",
        "missing_evidence",
        "fundamentals",
        "news",
        "catalyst",
        "freshness",
    )
    assert item["researchBiasRaw"] == "avoidLowEvidence"
    assert item["researchBias"] == "Low-evidence filter active"
    assert item["researchBiasLabel"] == "Low-evidence filter active"
    assert item["researchBiasMessage"]
    assert {"low_liquidity", "missing_evidence"}.issubset(set(item["riskFlagsRaw"]))
    assert item["riskFlags"] == item["riskFlagLabels"]
    assert "Liquidity is limited" in item["riskFlagLabels"]
    assert "Evidence missing" in item["riskFlagLabels"]
    assert item["evidenceGapsRaw"] == ["fundamentals", "news", "catalyst", "freshness"]
    assert item["evidenceGaps"] == [
        "Company evidence missing",
        "Media context missing",
        "Event context missing",
        "Recency check missing",
    ]
    assert item["evidenceQuality"]["missingEvidenceRaw"] == ["fundamentals", "news", "catalyst", "freshness"]
    assert item["evidenceQuality"]["missingEvidence"] == item["evidenceGaps"]
    assert item["consumerEvidenceGaps"]
    assert item["consumerIssues"]
    assert payload["consumerIssues"]
    _assert_display_ready_fields_safe(
        {
            "researchBias": item["researchBias"],
            "researchBiasLabel": item["researchBiasLabel"],
            "researchBiasMessage": item["researchBiasMessage"],
            "riskFlags": item["riskFlags"],
            "riskFlagLabels": item["riskFlagLabels"],
            "evidenceGaps": item["evidenceGaps"],
            "consumerEvidenceGaps": item["consumerEvidenceGaps"],
            "evidenceQualityMissing": item["evidenceQuality"]["missingEvidence"],
        },
        raw_codes,
    )
    _assert_consumer_issues_safe(item["consumerIssues"], raw_codes)


def test_research_radar_projection_does_not_change_ranking_or_scores_when_labeling_contract() -> None:
    candidates = [
        {
            "ticker": "LOWQ",
            "relativeStrength": 35,
            "volumeExpansion": 0.5,
            "trendStructure": "weak",
            "avgDollarVolume": 1000,
            "evidenceQuality": {"state": "missing", "score": 10, "missing": ["fundamentals"]},
        },
        {
            "ticker": "HIGHQ",
            "relativeStrength": 88,
            "volumeExpansion": 1.8,
            "trendStructure": "confirmed_uptrend",
            "themes": ["AI Infrastructure"],
            "eventCatalyst": {"state": "confirmed"},
            "avgDollarVolume": 120_000_000,
            "evidenceQuality": {"state": "complete", "score": 0.88},
        },
    ]
    market_regime_context = {
        "regime": "risk_on",
        "favorableThemes": ["AI Infrastructure"],
    }
    theme_leadership_context = {
        "dominantThemes": [{"name": "AI Infrastructure", "leadershipScore": 86}]
    }
    engine_payload = build_research_radar_candidate_queue(
        candidates,
        market_regime_context=market_regime_context,
        theme_leadership_context=theme_leadership_context,
    )
    payload = ResearchRadarService(now=_fixed_now).build_radar(
        candidates=candidates,
        market_regime_context=market_regime_context,
        theme_leadership_context=theme_leadership_context,
    )
    engine_queue = list(engine_payload["researchQueue"])

    assert [item["symbol"] for item in payload["researchQueue"]] == [item["symbol"] for item in engine_queue]
    assert [item["priority"] for item in payload["researchQueue"]] == [item["priority"] for item in engine_queue]
    assert [item["driverScores"] for item in payload["researchQueue"]] == [
        item["driverScores"] for item in engine_queue
    ]
    assert [item["researchBiasRaw"] for item in payload["researchQueue"]] == [
        item["researchBias"] for item in engine_queue
    ]
    assert [item["riskFlagsRaw"] for item in payload["researchQueue"]] == [
        item["riskFlags"] for item in engine_queue
    ]
    assert payload["aggregateSummary"]["duplicateEvidenceMerged"] == engine_payload["summary"]["duplicateEvidenceMerged"]
    assert payload["marketContextFit"] == engine_payload["summary"]["marketContextFit"]


def test_unknown_internal_gap_tokens_fall_back_to_generic_consumer_copy() -> None:
    payload = ResearchRadarService(now=_fixed_now).build_radar(
        candidates=[
            {
                "ticker": "UNK",
                "relativeStrength": 45,
                "volumeExpansion": 0.8,
                "trendStructure": "mixed",
                "avgDollarVolume": 5_000_000,
                "evidenceQuality": {
                    "state": "partial",
                    "score": 50,
                    "missing": ["provider_runtime:error=timeout", "source_authority_unknown"],
                },
            }
        ]
    )

    item = payload["researchQueue"][0]
    raw_codes = ("provider_runtime:error=timeout", "source_authority_unknown")
    assert item["evidenceGapsRaw"] == list(raw_codes)
    assert item["evidenceGaps"] == ["Evidence needs review"]
    assert item["evidenceQuality"]["missingEvidenceRaw"] == list(raw_codes)
    assert item["evidenceQuality"]["missingEvidence"] == ["Evidence needs review"]
    _assert_display_ready_fields_safe(
        {
            "evidenceGaps": item["evidenceGaps"],
            "consumerEvidenceGaps": item["consumerEvidenceGaps"],
            "evidenceQualityMissing": item["evidenceQuality"]["missingEvidence"],
            "consumerIssues": item["consumerIssues"],
            "topLevelEvidenceGaps": payload["evidenceGaps"],
            "dataQualityMissingEvidence": payload["dataQuality"]["missingEvidence"],
        },
        raw_codes,
    )


class _FakeScannerRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.runs = [
            SimpleNamespace(id=7, status="failed", market="us", profile="us_preopen_v1"),
            SimpleNamespace(id=8, status="completed", market="us", profile="us_preopen_v1"),
        ]
        self.candidates = [
            SimpleNamespace(
                symbol="BETA",
                name="Beta Inc",
                rank=1,
                score=72.0,
                quality_hint="partial",
                reason_summary="Trend structure needs verification.",
                reasons_json="[]",
                key_metrics_json='["relative strength"]',
                feature_signals_json="[]",
                risk_notes_json='["Evidence is partial."]',
                watch_context_json='["Verify volume persistence."]',
                boards_json='["AI Infrastructure"]',
                diagnostics_json='{"component_scores": {"trend": 76}, "history": {"latest_trade_date": "2026-06-14", "rows": 120}}',
            )
        ]

    def get_recent_runs(self, **kwargs: object) -> list[object]:
        self.calls.append(("get_recent_runs", dict(kwargs)))
        return list(self.runs)

    def get_candidates_for_run(self, run_id: int) -> list[object]:
        self.calls.append(("get_candidates_for_run", {"run_id": run_id}))
        return list(self.candidates if run_id == 8 else [])


class _AdminOnlyScannerRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.mutations: list[tuple[str, dict[str, object]]] = []
        self.admin_run = SimpleNamespace(id=99, status="completed", market="us", profile="us_preopen_v1")
        self.admin_candidate = SimpleNamespace(
            symbol="ADMIN",
            name="Admin Candidate",
            rank=1,
            score=99.0,
            quality_hint="complete",
            reason_summary="Admin-only candidate must not leak.",
            reasons_json="[]",
            key_metrics_json="[]",
            feature_signals_json="[]",
            risk_notes_json="[]",
            watch_context_json="[]",
            boards_json="[]",
            diagnostics_json="{}",
        )

    def get_recent_runs(self, **kwargs: object) -> list[object]:
        self.calls.append(("get_recent_runs", dict(kwargs)))
        if kwargs.get("include_all_owners") is True:
            return [self.admin_run]
        return []

    def get_candidates_for_run(self, run_id: int) -> list[object]:
        self.calls.append(("get_candidates_for_run", {"run_id": run_id}))
        return [self.admin_candidate] if run_id == 99 else []

    def create_run(self, **kwargs: object) -> None:
        self.mutations.append(("create_run", dict(kwargs)))

    def save_candidate(self, **kwargs: object) -> None:
        self.mutations.append(("save_candidate", dict(kwargs)))


def test_latest_scanner_reader_is_read_only_and_uses_user_scope() -> None:
    repo = _FakeScannerRepository()

    payload = ResearchRadarService(scanner_repository=repo, now=_fixed_now).build_from_latest_scanner_run(
        market="us",
        profile="us_preopen_v1",
        owner_id="user-1",
        limit=5,
    )

    assert [item["symbol"] for item in payload["researchQueue"]] == ["BETA"]
    assert repo.calls[0] == (
        "get_recent_runs",
        {
            "market": "us",
            "profile": "us_preopen_v1",
            "limit": 5,
            "scope": "user",
            "owner_id": "user-1",
            "include_all_owners": False,
        },
    )
    assert repo.calls[1] == ("get_candidates_for_run", {"run_id": 8})
    assert payload["aggregateSummary"]["source"]["scannerRunId"] == 8


def test_empty_consumer_radar_adds_onboarding_without_admin_leak_or_mutation() -> None:
    repo = _AdminOnlyScannerRepository()

    payload = ResearchRadarService(scanner_repository=repo, now=_fixed_now).build_from_latest_scanner_run(
        market="us",
        profile="us_preopen_v1",
        owner_id="user-1",
        limit=5,
    )

    _assert_required_top_level_shape(payload)
    assert payload["researchQueue"] == []
    assert payload["aggregateSummary"]["queueCount"] == 0
    assert payload["aggregateSummary"]["source"]["scannerRunId"] is None
    assert payload["onboardingGuidance"]["title"] == "Start a research loop"
    assert payload["onboardingGuidance"]["conditionsDetected"] == [
        "Research Radar has no queue items yet.",
        "No scanner candidates were found for this user scope.",
    ]
    assert [action["route"] for action in payload["emptyStateActions"]] == [
        "/market-overview",
        "/watchlist",
        "/scanner",
        "/research/radar",
    ]
    assert payload["starterResearchWorkflow"] == [
        "Open Market Overview to set broad context.",
        "Create one watchlist item for a symbol you already want to observe.",
        "Run scanner to generate research candidates for review.",
        "Return to Research Radar after adding watchlist context.",
    ]
    assert payload["firstRunChecklist"] == [
        "Market Overview checked for context.",
        "First watchlist item created by the user.",
        "Scanner run completed by the user.",
        "Research Radar reviewed again after watchlist context exists.",
    ]
    assert [entrypoint["surface"] for entrypoint in payload["suggestedResearchEntrypoints"]] == [
        "Market Overview",
        "Watchlist",
        "Scanner",
        "Research Radar",
    ]
    assert repo.calls == [
        (
            "get_recent_runs",
            {
                "market": "us",
                "profile": "us_preopen_v1",
                "limit": 5,
                "scope": "user",
                "owner_id": "user-1",
                "include_all_owners": False,
            },
        )
    ]
    assert repo.mutations == []
    serialized = _serialized(payload)
    assert "admin" not in serialized
    assert "scannercandidates" not in _serialized(payload["onboardingGuidance"])
    _assert_display_ready_fields_safe(
        {
            "onboardingGuidance": payload["onboardingGuidance"],
            "emptyStateActions": payload["emptyStateActions"],
            "starterResearchWorkflow": payload["starterResearchWorkflow"],
            "firstRunChecklist": payload["firstRunChecklist"],
            "suggestedResearchEntrypoints": payload["suggestedResearchEntrypoints"],
        },
        ("scannerCandidates", "admin_only_candidate"),
    )


def test_populated_consumer_radar_keeps_normal_queue_without_onboarding_fallback() -> None:
    payload = ResearchRadarService(now=_fixed_now).build_radar(
        candidates=[
            {
                "ticker": "ALFA",
                "relativeStrength": 88,
                "volumeExpansion": 1.8,
                "trendStructure": "confirmed_uptrend",
                "themes": ["AI Infrastructure"],
                "eventCatalyst": {"state": "confirmed"},
                "avgDollarVolume": 120_000_000,
                "evidenceQuality": {"state": "complete", "score": 0.88},
            }
        ],
        market_regime_context={
            "regime": "risk_on",
            "favorableThemes": ["AI Infrastructure"],
        },
    )

    assert [item["symbol"] for item in payload["researchQueue"]] == ["ALFA"]
    assert payload["onboardingGuidance"] is None
    assert payload["emptyStateActions"] == []
    assert payload["starterResearchWorkflow"] == []
    assert payload["firstRunChecklist"] == []
    assert payload["suggestedResearchEntrypoints"] == []


def test_thin_consumer_radar_keeps_queue_and_adds_onboarding_next_steps() -> None:
    payload = ResearchRadarService(now=_fixed_now).build_radar(
        candidates=[
            {
                "ticker": "THIN",
                "relativeStrength": 60,
                "volumeExpansion": 1.1,
                "trendStructure": "mixed",
                "avgDollarVolume": 50_000_000,
                "evidenceQuality": {"state": "complete", "score": 70},
            }
        ]
    )

    assert [item["symbol"] for item in payload["researchQueue"]] == ["THIN"]
    assert payload["aggregateSummary"]["queueQuality"] == "thin"
    assert payload["onboardingGuidance"]["conditionsDetected"] == ["Research Radar queue is thin."]
    assert payload["emptyStateActions"]
    assert payload["starterResearchWorkflow"]
    assert payload["firstRunChecklist"]
    assert payload["suggestedResearchEntrypoints"]
    _assert_display_ready_fields_safe(
        {
            "onboardingGuidance": payload["onboardingGuidance"],
            "emptyStateActions": payload["emptyStateActions"],
            "starterResearchWorkflow": payload["starterResearchWorkflow"],
            "firstRunChecklist": payload["firstRunChecklist"],
            "suggestedResearchEntrypoints": payload["suggestedResearchEntrypoints"],
        },
        ("queueQuality", "low_evidence"),
    )


def test_research_radar_service_has_no_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "research_radar_service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported_modules.add(node.module)
            imported_modules.update(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*")

    violations = sorted(
        module
        for module in imported_modules
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert violations == []
