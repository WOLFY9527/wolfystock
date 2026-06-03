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
