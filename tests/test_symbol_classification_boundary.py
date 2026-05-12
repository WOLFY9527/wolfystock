# -*- coding: utf-8 -*-
"""Contract tests for the pure symbol classification boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from data_provider.base import (
    is_bse_code as provider_is_bse_code,
)
from data_provider.base import (
    is_kc_cy_stock as provider_is_kc_cy_stock,
)
from data_provider.base import (
    is_st_stock as provider_is_st_stock,
)
from data_provider.us_index_mapping import (
    US_INDEX_MAPPING,
    is_us_stock_code as provider_is_us_stock_code,
)
from src.utils.symbol_classification import (
    is_bse_code,
    is_kc_cy_stock,
    is_st_stock,
    is_us_stock_code,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_provider_classification_exports_delegate_to_pure_utils() -> None:
    assert provider_is_bse_code is is_bse_code
    assert provider_is_kc_cy_stock is is_kc_cy_stock
    assert provider_is_st_stock is is_st_stock
    assert provider_is_us_stock_code is is_us_stock_code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AAPL", True),
        ("BRK.B", True),
        (" aapl ", True),
        ("SPX", False),
        ("^GSPC", False),
        ("600519", False),
        ("HK00700", False),
        ("", False),
        (None, False),
    ],
)
def test_is_us_stock_code_matches_provider_runtime_semantics(
    raw: str | None,
    expected: bool,
) -> None:
    assert is_us_stock_code(raw) is expected
    assert is_us_stock_code(raw) == provider_is_us_stock_code(raw)


def test_us_index_mapping_keys_remain_excluded_from_us_stock_classification() -> None:
    for code in US_INDEX_MAPPING:
        assert is_us_stock_code(code) is False
        assert provider_is_us_stock_code(code) is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("920748", True),
        ("838163", True),
        ("430047", True),
        ("920748.BJ", True),
        ("900901", False),
        ("600519", False),
        ("159919", False),
        ("", False),
        (None, False),
    ],
)
def test_is_bse_code_matches_provider_runtime_semantics(
    raw: str | None,
    expected: bool,
) -> None:
    assert is_bse_code(raw) is expected
    assert is_bse_code(raw) == provider_is_bse_code(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ST风险股", True),
        ("*st海航", True),
        ("普通股", False),
        ("", False),
        (None, False),
    ],
)
def test_is_st_stock_matches_provider_runtime_semantics(
    raw: str | None,
    expected: bool,
) -> None:
    assert is_st_stock(raw) is expected
    assert is_st_stock(raw) == provider_is_st_stock(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("688001", True),
        ("300750", True),
        ("300750.SZ", True),
        ("301001", True),
        ("600519", False),
        ("920748", False),
        ("", False),
        (None, False),
    ],
)
def test_is_kc_cy_stock_matches_provider_runtime_semantics(
    raw: str | None,
    expected: bool,
) -> None:
    assert is_kc_cy_stock(raw) is expected
    assert is_kc_cy_stock(raw) == provider_is_kc_cy_stock(raw)


def test_symbol_classification_module_stays_runtime_lightweight() -> None:
    script = """
import importlib
import json
import sys

tracked_prefixes = (
    "src.utils.symbol_classification",
    "data_provider",
    "pandas",
    "requests",
    "httpx",
)

importlib.import_module("src.utils.symbol_classification")
loaded_modules = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in tracked_prefixes)
)
print(json.dumps({"loaded_modules": loaded_modules}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    loaded_modules = set(json.loads(completed.stdout)["loaded_modules"])
    assert "src.utils.symbol_classification" in loaded_modules
    assert not any(
        name == "data_provider" or name.startswith("data_provider.")
        for name in loaded_modules
    )
    assert not any(name == "pandas" or name.startswith("pandas.") for name in loaded_modules)
    assert not any(name == "requests" or name.startswith("requests.") for name in loaded_modules)
    assert not any(name == "httpx" or name.startswith("httpx.") for name in loaded_modules)
