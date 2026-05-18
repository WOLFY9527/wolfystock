# -*- coding: utf-8 -*-
"""Unit tests for additive rotation state evidence helpers."""

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
            "yfinance",
            "requests",
            "httpx",
            "openai",
            "src.core.pipeline",
            "src.services.market_scanner_service",
            "src.services.market_cache",
            "src.services.options_lab_service",
            "src.core.rule_backtest_engine",
        )
        for prefix in forbidden_prefixes:
            if fullname == prefix or fullname.startswith(f"{prefix}."):
                self.blocked.append(fullname)
                raise AssertionError(f"rotation_state_evidence imported forbidden module {fullname}")
        return None


def _theme_payload(**overrides):
    payload = {
        "id": "ai_applications",
        "market": "US",
        "taxonomyType": "theme_cluster",
        "rotationScore": 73,
        "stage": "early_watch",
        "confidence": 0.59,
        "riskLabels": [],
        "source": "computed",
        "sourceLabel": "主题篮子计算",
        "sourceClass": "custom",
        "dataQuality": "quote_backed",
        "dataCoverage": "quote_backed",
        "staticThemeOnly": False,
        "asOf": "2026-05-07T09:45:00+00:00",
        "updatedAt": "2026-05-07T09:50:00+00:00",
        "breadth": {
            "observedMembers": 3,
            "configuredMembers": 3,
            "coveragePercent": 100.0,
            "percentUp": 100.0,
            "percentOutperformingBenchmark": 100.0,
        },
        "volume": {
            "averageRelativeVolume": 1.53,
            "availableMemberCount": 3,
            "label": "量能扩张",
        },
        "relativeStrength": {
            "benchmark": "QQQ",
            "benchmarkChangePercent": 0.4,
            "averageThemeChangePercent": 2.4,
            "averageRelativeStrengthPercent": 2.0,
            "vsBenchmarks": {"QQQ": 2.0, "SPY": 2.2},
        },
        "synchronization": {
            "sameDirectionPercent": 100.0,
            "aboveVwapPercent": 100.0,
            "persistencePercent": 100.0,
            "persistenceScore": 1.0,
            "label": "同步扩散",
        },
        "leadership": {
            "leadershipConcentrationPercent": 34.0,
            "broadParticipationPercent": 66.0,
            "topMembers": [{"symbol": "APP"}, {"symbol": "PLTR"}],
        },
        "proxyQuality": {
            "label": "ETF 代理完整",
            "coveragePercent": 100.0,
            "availableProxyCount": 4,
            "totalProxyCount": 4,
            "requiredProxies": ["QQQ", "SPY", "IWM", "IGV"],
            "freshness": "delayed",
            "hasMissingRequiredProxy": False,
            "hasStaleProxy": False,
            "missingReasons": {},
            "explanation": "ETF 代理完整：ETF 代理覆盖 4/4，缺口 无。",
        },
        "timeWindows": {
            "5m": {"available": True, "isFallback": False, "isStale": False, "averageChangePercent": 0.8},
            "15m": {"available": True, "isFallback": False, "isStale": False, "averageChangePercent": 1.6},
            "60m": {"available": True, "isFallback": False, "isStale": False, "averageChangePercent": 2.2},
            "1d": {"available": True, "isFallback": False, "isStale": False, "averageChangePercent": 2.4},
        },
        "persistenceEvidence": {
            "score": 1.0,
            "label": "跨时窗延续",
            "availableWindows": ["5m", "15m", "60m", "1d"],
            "missingWindows": [],
            "staleOrFallbackWindows": [],
            "positiveWindowCount": 4,
            "negativeWindowCount": 0,
            "sameDirectionWindowCount": 4,
            "requiredWindows": ["5m", "15m", "60m", "1d"],
            "explanation": "跨时窗延续：可用 5m/15m/60m/1d，缺失 无，备用/过期 无。",
        },
    }
    payload.update(overrides)
    return payload


def test_rotation_state_evidence_import_is_inert() -> None:
    sys.modules.pop("src.services.rotation_state_evidence", None)
    blocker = _ForbiddenImportBlocker()
    before = set(sys.modules)
    sys.meta_path.insert(0, blocker)
    try:
        module = importlib.import_module("src.services.rotation_state_evidence")
    finally:
        sys.meta_path.remove(blocker)

    after = set(sys.modules)
    assert module is not None
    assert blocker.blocked == []
    assert "src.services.market_cache" not in after - before
    assert "src.services.market_scanner_service" not in after - before


def test_proxy_only_rotation_state_evidence_never_enables_flow_language() -> None:
    from src.services.rotation_state_evidence import build_rotation_state_evidence

    evidence = build_rotation_state_evidence(
        _theme_payload(),
        {
            "market": "US",
            "taxonomyVersion": "sector_rotation_taxonomy_v1",
            "computedAt": "2026-05-07T09:50:00+00:00",
        },
    )

    assert evidence["schemaVersion"] == "rotation_state_evidence_v1"
    assert evidence["state"] == "acceleration"
    assert evidence["stateLabel"] == "加速扩张观察"
    assert evidence["flowEvidenceType"] == "proxy_only"
    assert evidence["flowLanguageAllowed"] is False
    assert evidence["signals"]["fundFlow"]["label"] == "轮动代理证据"
    assert "资金流入确认" not in evidence["uiSummary"]
    assert "真实资金流" not in evidence["stateExplanation"]


def test_taxonomy_only_non_us_evidence_stays_insufficient_and_safe() -> None:
    from src.services.rotation_state_evidence import build_rotation_state_evidence

    theme = _theme_payload(
        id="CN:theme_cluster:ai_compute",
        market="CN",
        staticThemeOnly=True,
        source="local_taxonomy",
        sourceLabel="静态主题库",
        dataQuality="taxonomy_only",
        dataCoverage="taxonomy_only",
        confidence=0.12,
        stage="weak_or_no_signal",
        breadth={
            "observedMembers": 0,
            "configuredMembers": 3,
            "coveragePercent": 0,
            "percentUp": None,
            "percentOutperformingBenchmark": None,
        },
        volume={"averageRelativeVolume": None, "availableMemberCount": 0, "label": "待接入本地行情"},
        relativeStrength={
            "benchmark": "CN_LOCAL_TAXONOMY",
            "benchmarkChangePercent": None,
            "averageThemeChangePercent": None,
            "averageRelativeStrengthPercent": None,
            "vsBenchmarks": {},
        },
        proxyQuality={
            "label": "静态主题库",
            "coveragePercent": 0,
            "availableProxyCount": 0,
            "totalProxyCount": 0,
            "requiredProxies": [],
            "freshness": "fallback",
            "hasMissingRequiredProxy": False,
            "hasStaleProxy": False,
            "missingReasons": {},
            "explanation": "当前为静态主题库，本地行情覆盖后可计算轮动强度。",
        },
        timeWindows={
            "5m": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
            "15m": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
            "60m": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
            "1d": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
        },
        persistenceEvidence={
            "score": 0.0,
            "label": "跨时窗证据待补齐",
            "availableWindows": [],
            "missingWindows": ["5m", "15m", "60m", "1d"],
            "staleOrFallbackWindows": ["5m", "15m", "60m", "1d"],
            "positiveWindowCount": 0,
            "negativeWindowCount": 0,
            "sameDirectionWindowCount": 0,
            "requiredWindows": ["5m", "15m", "60m", "1d"],
            "explanation": "跨时窗证据待补齐：可用 无，缺失 5m/15m/60m/1d，备用/过期 5m/15m/60m/1d。",
        },
    )

    evidence = build_rotation_state_evidence(
        theme,
        {
            "market": "CN",
            "taxonomyVersion": "sector_rotation_taxonomy_v1",
            "computedAt": "2026-05-07T09:50:00+00:00",
        },
    )

    assert evidence["state"] == "insufficient_evidence"
    assert evidence["stateLabel"] == "证据不足"
    assert evidence["flowEvidenceType"] == "none"
    assert evidence["flowLanguageAllowed"] is False
    assert "待接入本地行情" in evidence["requiredDataStatus"]["missingLabels"]
    assert "真实资金流暂缺" in evidence["requiredDataStatus"]["missingLabels"]
    assert "分类观察" in evidence["uiSummary"]


def test_rotation_state_evidence_can_flag_overheated_divergence_and_fading() -> None:
    from src.services.rotation_state_evidence import build_rotation_state_evidence

    overheated = build_rotation_state_evidence(
        _theme_payload(
            riskLabels=["gap_fade_risk", "single_name_driven"],
            leadership={"leadershipConcentrationPercent": 72.0, "broadParticipationPercent": 28.0, "topMembers": [{"symbol": "APP"}]},
            volume={"averageRelativeVolume": 2.7, "availableMemberCount": 3, "label": "量能确认"},
        ),
        {"market": "US", "taxonomyVersion": "sector_rotation_taxonomy_v1"},
    )
    divergence = build_rotation_state_evidence(
        _theme_payload(
            riskLabels=["thin_breadth", "stale_or_incomplete_windows"],
            breadth={
                "observedMembers": 3,
                "configuredMembers": 3,
                "coveragePercent": 100.0,
                "percentUp": 34.0,
                "percentOutperformingBenchmark": 34.0,
            },
            relativeStrength={
                "benchmark": "QQQ",
                "benchmarkChangePercent": 0.4,
                "averageThemeChangePercent": 1.8,
                "averageRelativeStrengthPercent": 1.4,
                "vsBenchmarks": {"QQQ": 1.4},
            },
        ),
        {"market": "US", "taxonomyVersion": "sector_rotation_taxonomy_v1"},
    )
    fading = build_rotation_state_evidence(
        _theme_payload(
            stage="cooling_watch",
            breadth={
                "observedMembers": 3,
                "configuredMembers": 3,
                "coveragePercent": 100.0,
                "percentUp": 22.0,
                "percentOutperformingBenchmark": 18.0,
            },
            synchronization={
                "sameDirectionPercent": 36.0,
                "aboveVwapPercent": 33.0,
                "persistencePercent": 25.0,
                "persistenceScore": 0.2,
                "label": "分类观察",
            },
            persistenceEvidence={
                "score": 0.2,
                "label": "跨时窗降温",
                "availableWindows": ["15m", "60m", "1d"],
                "missingWindows": ["5m"],
                "staleOrFallbackWindows": [],
                "positiveWindowCount": 1,
                "negativeWindowCount": 2,
                "sameDirectionWindowCount": 2,
                "requiredWindows": ["5m", "15m", "60m", "1d"],
                "explanation": "跨时窗降温：可用 15m/60m/1d，缺失 5m，备用/过期 无。",
            },
        ),
        {"market": "US", "taxonomyVersion": "sector_rotation_taxonomy_v1"},
    )

    assert overheated["state"] == "overheated"
    assert overheated["stateLabel"] == "过热拥挤观察"
    assert divergence["state"] == "divergence"
    assert divergence["stateLabel"] == "强弱分歧观察"
    assert fading["state"] == "fading"
    assert fading["stateLabel"] == "降温走弱观察"


def test_rotation_state_ui_summary_stays_user_safe() -> None:
    from src.services.rotation_state_evidence import build_rotation_state_evidence

    evidence = build_rotation_state_evidence(
        _theme_payload(),
        {"market": "US", "taxonomyVersion": "sector_rotation_taxonomy_v1"},
    )

    summary = evidence["uiSummary"]
    lowered = summary.lower()
    assert "provider" not in lowered
    assert "raw" not in lowered
    assert "debug" not in lowered
    assert "schema" not in lowered


def test_rotation_state_evidence_adds_signal_snapshot_metadata_and_caps_weak_partial_inputs() -> None:
    from src.services.rotation_state_evidence import build_rotation_state_evidence

    evidence = build_rotation_state_evidence(
        _theme_payload(
            freshness="live",
            breadth={
                "observedMembers": 2,
                "configuredMembers": 4,
                "coveragePercent": 50.0,
                "percentUp": 50.0,
                "percentOutperformingBenchmark": 25.0,
            },
            volume={
                "averageRelativeVolume": 0.94,
                "availableMemberCount": 2,
                "label": "量能偏弱",
            },
            relativeStrength={
                "benchmark": "QQQ",
                "benchmarkChangePercent": 0.4,
                "averageThemeChangePercent": 0.5,
                "averageRelativeStrengthPercent": 0.1,
                "vsBenchmarks": {"QQQ": 0.1},
            },
            synchronization={
                "sameDirectionPercent": 50.0,
                "aboveVwapPercent": 25.0,
                "persistencePercent": 50.0,
                "persistenceScore": 0.4,
                "label": "同步性不足",
            },
            timeWindows={
                "5m": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
                "15m": {"available": True, "isFallback": False, "isStale": False, "averageChangePercent": 0.2},
                "60m": {"available": False, "isFallback": False, "isStale": True, "averageChangePercent": None},
                "1d": {"available": True, "isFallback": False, "isStale": False, "averageChangePercent": 0.5},
            },
            persistenceEvidence={
                "score": 0.4,
                "label": "跨时窗证据不足",
                "availableWindows": ["15m", "1d"],
                "missingWindows": ["5m", "60m"],
                "staleOrFallbackWindows": ["5m", "60m"],
                "positiveWindowCount": 1,
                "negativeWindowCount": 0,
                "sameDirectionWindowCount": 1,
                "requiredWindows": ["5m", "15m", "60m", "1d"],
                "explanation": "跨时窗证据不足：可用 15m/1d，缺失 5m/60m，备用/过期 5m/60m。",
            },
        ),
        {"market": "US", "taxonomyVersion": "sector_rotation_taxonomy_v1"},
    )

    snapshot = evidence["evidenceSnapshot"]
    overall = snapshot["sourceConfidence"]
    relative_strength = snapshot["signals"]["relativeStrength"]["sourceConfidence"]
    persistence = snapshot["signals"]["persistence"]["sourceConfidence"]
    vwap = snapshot["signals"]["vwapParticipation"]["sourceConfidence"]

    assert snapshot["contractVersion"] == "source_confidence_contract_v1"
    assert overall["freshness"] == "partial"
    assert overall["isPartial"] is True
    assert overall["isFallback"] is False
    assert overall["isStale"] is False
    assert overall["confidenceWeight"] <= 0.7
    assert overall["coverage"] == 0.5
    assert snapshot["degradedSignalCount"] >= 3
    assert snapshot["signals"]["relativeStrength"]["status"] == "weak"
    assert relative_strength["freshness"] == "partial"
    assert relative_strength["isPartial"] is True
    assert relative_strength["isUnavailable"] is False
    assert persistence["freshness"] == "partial"
    assert persistence["isPartial"] is True
    assert vwap["freshness"] == "partial"
    assert vwap["isPartial"] is True
    assert vwap["isUnavailable"] is False


def test_rotation_state_evidence_marks_fallback_stale_and_unavailable_snapshot_inputs_as_degraded() -> None:
    from src.services.rotation_state_evidence import build_rotation_state_evidence

    fallback_evidence = build_rotation_state_evidence(
        _theme_payload(
            source="fallback",
            sourceLabel="备用数据",
            freshness="fallback",
            isFallback=True,
            confidence=0.12,
            breadth={
                "observedMembers": 0,
                "configuredMembers": 4,
                "coveragePercent": 0.0,
                "percentUp": None,
                "percentOutperformingBenchmark": None,
            },
            volume={"averageRelativeVolume": None, "availableMemberCount": 0, "label": "成交额扩张证据不足"},
            relativeStrength={
                "benchmark": "QQQ",
                "benchmarkChangePercent": None,
                "averageThemeChangePercent": None,
                "averageRelativeStrengthPercent": None,
                "vsBenchmarks": {},
            },
            synchronization={
                "sameDirectionPercent": None,
                "aboveVwapPercent": None,
                "persistencePercent": None,
                "persistenceScore": 0.0,
                "label": "同步性证据不足",
            },
            timeWindows={
                "5m": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
                "15m": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
                "60m": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
                "1d": {"available": False, "isFallback": True, "isStale": False, "averageChangePercent": None},
            },
            persistenceEvidence={
                "score": 0.0,
                "label": "跨时窗证据待补齐",
                "availableWindows": [],
                "missingWindows": ["5m", "15m", "60m", "1d"],
                "staleOrFallbackWindows": ["5m", "15m", "60m", "1d"],
                "positiveWindowCount": 0,
                "negativeWindowCount": 0,
                "sameDirectionWindowCount": 0,
                "requiredWindows": ["5m", "15m", "60m", "1d"],
                "explanation": "跨时窗证据待补齐：可用 无，缺失 5m/15m/60m/1d，备用/过期 5m/15m/60m/1d。",
            },
        ),
        {"market": "US", "taxonomyVersion": "sector_rotation_taxonomy_v1"},
    )
    stale_evidence = build_rotation_state_evidence(
        _theme_payload(
            freshness="stale",
            isStale=True,
            timeWindows={
                "5m": {"available": True, "isFallback": False, "isStale": True, "averageChangePercent": 0.4},
                "15m": {"available": True, "isFallback": False, "isStale": True, "averageChangePercent": 0.8},
                "60m": {"available": True, "isFallback": False, "isStale": True, "averageChangePercent": 1.1},
                "1d": {"available": True, "isFallback": False, "isStale": True, "averageChangePercent": 1.3},
            },
            persistenceEvidence={
                "score": 0.6,
                "label": "跨时窗待确认",
                "availableWindows": ["5m", "15m", "60m", "1d"],
                "missingWindows": [],
                "staleOrFallbackWindows": ["5m", "15m", "60m", "1d"],
                "positiveWindowCount": 4,
                "negativeWindowCount": 0,
                "sameDirectionWindowCount": 4,
                "requiredWindows": ["5m", "15m", "60m", "1d"],
                "explanation": "跨时窗待确认：可用 5m/15m/60m/1d，缺失 无，备用/过期 5m/15m/60m/1d。",
            },
        ),
        {"market": "US", "taxonomyVersion": "sector_rotation_taxonomy_v1"},
    )

    fallback_snapshot = fallback_evidence["evidenceSnapshot"]
    stale_snapshot = stale_evidence["evidenceSnapshot"]

    assert fallback_snapshot["sourceConfidence"]["freshness"] == "fallback"
    assert fallback_snapshot["sourceConfidence"]["isFallback"] is True
    assert fallback_snapshot["sourceConfidence"]["confidenceWeight"] <= 0.4
    assert fallback_snapshot["signals"]["relativeStrength"]["sourceConfidence"]["freshness"] == "unavailable"
    assert fallback_snapshot["signals"]["relativeStrength"]["sourceConfidence"]["isUnavailable"] is True
    assert fallback_snapshot["signals"]["breadth"]["sourceConfidence"]["freshness"] == "unavailable"
    assert fallback_snapshot["signals"]["vwapParticipation"]["sourceConfidence"]["freshness"] == "unavailable"
    assert stale_snapshot["sourceConfidence"]["freshness"] == "stale"
    assert stale_snapshot["sourceConfidence"]["isStale"] is True
    assert stale_snapshot["sourceConfidence"]["confidenceWeight"] <= 0.6
    assert stale_snapshot["signals"]["persistence"]["sourceConfidence"]["freshness"] == "stale"
