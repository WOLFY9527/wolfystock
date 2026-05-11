# -*- coding: utf-8 -*-
"""Contract tests for the pure symbol normalization boundary."""

from __future__ import annotations

import pytest

from data_provider.base import (
    canonical_stock_code as provider_canonical_stock_code,
)
from data_provider.base import (
    normalize_stock_code as provider_normalize_stock_code,
)
from src.utils.symbol_normalization import (
    canonical_stock_code,
    normalize_stock_code,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600519", "600519"),
        (" SH600519 ", "600519"),
        ("000001.SZ", "000001"),
        ("600000.SS", "600000"),
        ("BJ920748", "920748"),
        ("920748.BJ", "920748"),
        ("HK00700", "HK00700"),
        ("hk700", "HK00700"),
        ("1810.HK", "HK01810"),
        ("AAPL", "AAPL"),
        ("brk.b", "brk.b"),
        ("", ""),
    ],
)
def test_normalize_stock_code_matches_provider_runtime_semantics(
    raw: str,
    expected: str,
) -> None:
    assert normalize_stock_code(raw) == expected
    assert normalize_stock_code(raw) == provider_normalize_stock_code(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("aapl", "AAPL"),
        (" 600519 ", "600519"),
        ("hk00700", "HK00700"),
        ("", ""),
        (None, ""),
    ],
)
def test_canonical_stock_code_matches_provider_runtime_semantics(
    raw: str | None,
    expected: str,
) -> None:
    assert canonical_stock_code(raw) == expected
    assert canonical_stock_code(raw) == provider_canonical_stock_code(raw)
