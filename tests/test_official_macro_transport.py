# -*- coding: utf-8 -*-
"""Fixture tests for official macro transport helpers."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.services.official_macro_transport import (
    FRED_OBSERVATIONS_URL,
    NYFED_SOFR_UNSUPPORTED_REASON,
    TREASURY_DAILY_RATES_CSV_URL,
    build_fred_observations_request,
    build_supported_fred_requests,
    build_treasury_daily_rates_request,
    parse_fred_observations_payload,
    parse_nyfed_sofr_payload,
    parse_treasury_daily_rates_csv,
    parse_treasury_daily_rates_rows,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "official_macro"
MODULE_PATH = REPO_ROOT / "src" / "services" / "official_macro_transport.py"
FORBIDDEN_IMPORT_PREFIXES = ("requests", "httpx", "aiohttp", "urllib3", "yfinance")


def _load_json_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_text_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _module_imports() -> set[str]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_official_macro_transport_stays_stdlib_only() -> None:
    forbidden_imports = sorted(
        module
        for module in _module_imports()
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert forbidden_imports == []


def test_build_supported_fred_requests_covers_expected_series() -> None:
    requests = build_supported_fred_requests()

    assert [request.params["series_id"] for request in requests] == ["VIXCLS", "DGS2", "DGS10", "DGS30", "SOFR"]
    assert all(request.url == FRED_OBSERVATIONS_URL for request in requests)
    assert all(request.requires_api_key for request in requests)
    assert all(request.source_type == "official_public" for request in requests)


def test_build_fred_observations_request_omits_api_key_when_not_supplied() -> None:
    request = build_fred_observations_request("DGS10", limit=7, observation_start="2026-05-01")

    assert request.method == "GET"
    assert request.url == FRED_OBSERVATIONS_URL
    assert request.params == {
        "series_id": "DGS10",
        "file_type": "json",
        "sort_order": "desc",
        "limit": "7",
        "observation_start": "2026-05-01",
    }
    assert request.source_id == "fred:DGS10"
    assert request.requires_api_key is True


def test_build_fred_observations_request_rejects_unsupported_series() -> None:
    with pytest.raises(ValueError, match="unsupported FRED series"):
        build_fred_observations_request("DXY")


@pytest.mark.parametrize(
    ("series_id", "fixture_name", "expected_value", "expected_date", "expected_hint"),
    [
        ("VIXCLS", "fred_vixcls.json", 18.22, "2026-05-13", "daily_close"),
        ("DGS2", "fred_dgs2.json", 3.87, "2026-05-13", "daily_rate"),
        ("DGS10", "fred_dgs10.json", 4.45, "2026-05-12", "daily_rate"),
        ("DGS30", "fred_dgs30.json", 4.89, "2026-05-13", "daily_rate"),
        ("SOFR", "fred_sofr.json", 5.31, "2026-05-13", "daily_fixing"),
    ],
)
def test_parse_fred_observations_payload_from_fixtures(
    series_id: str,
    fixture_name: str,
    expected_value: float,
    expected_date: str,
    expected_hint: str,
) -> None:
    observation = parse_fred_observations_payload(series_id, _load_json_fixture(fixture_name))

    assert observation.symbol == series_id
    assert observation.value == expected_value
    assert observation.date == expected_date
    assert observation.as_of == expected_date
    assert observation.source_id == f"fred:{series_id}"
    assert observation.source_type == "official_public"
    assert observation.freshness_hint == expected_hint
    assert observation.unavailable_reason is None


def test_parse_fred_observations_payload_returns_unavailable_for_missing_values() -> None:
    payload = {
        "observations": [
            {"date": "2026-05-13", "value": "."},
            {"date": "2026-05-12", "value": "N/A"},
        ]
    }

    observation = parse_fred_observations_payload("DGS2", payload)

    assert observation.value is None
    assert observation.date is None
    assert observation.as_of is None
    assert observation.unavailable_reason == "fred_observation_value_unavailable"


def test_build_treasury_daily_rates_request_matches_official_csv_download() -> None:
    request = build_treasury_daily_rates_request()

    assert request.method == "GET"
    assert request.url == TREASURY_DAILY_RATES_CSV_URL
    assert request.params == {"_format": "csv", "type": "daily_treasury_yield_curve"}
    assert request.source_id == "treasury:daily_treasury_yield_curve"
    assert request.requires_api_key is False


def test_parse_treasury_daily_rates_csv_returns_latest_2y_10y_30y() -> None:
    observations = parse_treasury_daily_rates_csv(_load_text_fixture("treasury_daily_rates.csv"))

    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "DGS2",
            "value": 3.87,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS10",
            "value": 4.41,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS30",
            "value": 4.89,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
    ]


def test_parse_treasury_daily_rates_rows_handles_json_like_rows_and_missing_value() -> None:
    observations = parse_treasury_daily_rates_rows(
        [
            {"Date": "2026-05-12", "2 Yr": "3.91", "10 Yr": "4.45", "30 Yr": "4.92"},
            {"Date": "2026-05-13", "2 Year": "3.87", "10 Year": "4.41", "30 Year": "N/A"},
        ]
    )

    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "DGS2",
            "value": 3.87,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS10",
            "value": 4.41,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS30",
            "value": None,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": "treasury_rate_unavailable",
        },
    ]


def test_parse_nyfed_sofr_payload_is_explicitly_unsupported_without_repo_shape() -> None:
    observation = parse_nyfed_sofr_payload({"unexpected": "shape"})

    assert observation.to_dict() == {
        "symbol": "SOFR",
        "value": None,
        "date": None,
        "asOf": None,
        "source_id": "nyfed:sofr",
        "source_type": "official_public",
        "freshness_hint": "unsupported_shape",
        "unavailable_reason": NYFED_SOFR_UNSUPPORTED_REASON,
    }
