# -*- coding: utf-8 -*-
"""Scanner API schema coverage for backward-compatible diagnostics."""

from api.v1.schemas.scanner import ScannerRunDetailResponse
from src.core.scanner_theme_registry import get_scanner_theme


def test_crypto_mining_theme_registry_has_11_symbols() -> None:
    theme = get_scanner_theme("crypto_miners")

    assert theme is not None
    assert theme.label_zh == "加密矿企"
    assert list(theme.symbols) == ["MARA", "RIOT", "CLSK", "IREN", "CIFR", "HUT", "BTDR", "WULF", "CORZ", "BITF", "HIVE"]


def test_scanner_run_response_accepts_legacy_shortlist_without_diagnostics() -> None:
    response = ScannerRunDetailResponse(
        id=1,
        market="us",
        profile="us_preopen_v1",
        status="completed",
        universe_name="us_liquid",
        shortlist_size=0,
        universe_size=0,
        preselected_size=0,
        evaluated_size=0,
    )

    assert response.shortlist == []
    assert response.selected == []
    assert response.candidates == []
    assert response.scannerContextFrame == {}
    assert response.summary.universe_count == 0


def test_scanner_run_response_accepts_additive_cn_blocked_scanner_context_frame() -> None:
    response = ScannerRunDetailResponse(
        id=2,
        market="cn",
        profile="cn_preopen_v1",
        status="failed",
        universe_name="cn_liquid",
        shortlist_size=0,
        universe_size=0,
        preselected_size=0,
        evaluated_size=0,
        scannerContextFrame={
            "marketReadiness": {
                "contractVersion": "research_readiness_v1",
                "researchReady": False,
                "market": "cn",
                "universeType": "default",
                "readinessState": "blocked",
                "blockingReasons": ["universe_source_unavailable"],
                "missingEvidence": ["technical", "freshness"],
                "providerAuthority": "unavailable",
                "freshness": "unavailable",
                "sourceTier": "unavailable",
                "nextEvidenceNeeded": ["补充技术面证据"],
                "noAdviceBoundary": True,
            },
            "universePolicy": {
                "type": "default",
                "label": "Profile default universe",
                "reason": "scanner_profile_default_universe",
            },
            "noAdviceBoundary": True,
        },
    )

    assert response.status == "failed"
    assert response.scannerContextFrame["marketReadiness"]["readinessState"] == "blocked"
    assert response.scannerContextFrame["marketReadiness"]["providerAuthority"] == "unavailable"
    assert response.scannerContextFrame["universePolicy"]["type"] == "default"
