# -*- coding: utf-8 -*-
"""Offline contracts for the SEC EDGAR companyfacts fixture parser."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from data_provider.sec_edgar_provider import parse_companyfacts_payload


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sec_edgar" / "companyfacts_sample.json"


def test_parse_companyfacts_fixture_extracts_official_observation_records() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    result = parse_companyfacts_payload(payload)

    assert result.provider_name == "SEC EDGAR"
    assert result.provider_id == "sec_edgar"
    assert result.source_tier == "official_public"
    assert result.trust_level == "reliable_for_filings_metadata"
    assert result.freshness_expectation == "filing_or_daily"
    assert result.observation_only is True
    assert result.score_contribution_allowed is False
    assert result.warnings
    assert [warning.code for warning in result.warnings] == [
        "invalid_fact_row",
        "invalid_unit_key",
        "invalid_unit_rows",
    ]

    records = result.records
    assert len(records) == 4
    assert [record.concept for record in records] == [
        "EntityCommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
        "Revenues",
        "Revenues",
    ]
    assert [record.period_end_date for record in records] == [
        "2024-09-28",
        "2024-06-29",
        "2024-09-28",
        "2024-06-29",
    ]

    first = records[0]
    assert first.provider_name == "SEC EDGAR"
    assert first.provider_id == "sec_edgar"
    assert first.source == "sec_edgar"
    assert first.source_tier == "official_public"
    assert first.trust_level == "reliable_for_filings_metadata"
    assert first.freshness_expectation == "filing_or_daily"
    assert first.observation_only is True
    assert first.score_contribution_allowed is False
    assert first.cik == "0000320193"
    assert first.entity_name == "Apple Inc."
    assert first.taxonomy == "dei"
    assert first.concept == "EntityCommonStockSharesOutstanding"
    assert first.label == "Entity Common Stock, Shares Outstanding"
    assert first.description == "Shares outstanding on the filing date"
    assert first.unit == "shares"
    assert first.value == 15204137000
    assert first.accession_number == "0000320193-24-000123"
    assert first.form == "10-K"
    assert first.filed_at == "2024-11-01"
    assert first.fiscal_year == 2024
    assert first.fiscal_period == "FY"
    assert first.fiscal_end_date == "2024-09-28"
    assert first.frame == "CY2024Q3I"
    assert first.as_of == "2024-09-28"
    assert first.updated_at == "2024-11-01T14:00:00Z"
    assert first.source_ref.startswith(
        "sec_edgar:companyfacts:0000320193:dei:EntityCommonStockSharesOutstanding:shares:0000320193-24-000123"
    )
    assert "raw_payload" not in first.to_dict()


def test_parse_companyfacts_payload_skips_malformed_unit_rows_and_is_noisy_only_via_warnings() -> None:
    result = parse_companyfacts_payload(
        {
            "cik": 32_019_3,
            "entityName": "Apple Inc.",
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": ["not-a-row"],
                            "": [{"end": "2024-09-28", "val": 1}],
                            "USD/shares": {"bad": "shape"},
                        }
                    }
                }
            },
        }
    )

    assert result.records == ()
    assert [warning.code for warning in result.warnings] == [
        "invalid_fact_row",
        "invalid_unit_key",
        "invalid_unit_rows",
    ]


def test_parse_companyfacts_payload_handles_missing_optional_fields_without_crashing() -> None:
    result = parse_companyfacts_payload(
        {
            "cik": "320193",
            "entityName": "Apple Inc.",
            "facts": {
                "dei": {
                    "EntityCommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {
                                    "end": "2024-09-28",
                                    "val": 15204137000,
                                    "accn": "0000320193-24-000123",
                                }
                            ]
                        }
                    }
                }
            },
        }
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record.label is None
    assert record.description is None
    assert record.form is None
    assert record.filed_at is None
    assert record.fiscal_year is None
    assert record.fiscal_period is None
    assert record.fiscal_end_date == "2024-09-28"
    assert record.period_end_date == "2024-09-28"
    assert record.as_of == "2024-09-28"
    assert record.updated_at is None


def test_sec_edgar_parser_import_is_metadata_only() -> None:
    script = """
import json
import importlib.util
from pathlib import Path
import sys

module_path = Path.cwd() / "data_provider" / "sec_edgar_provider.py"
spec = importlib.util.spec_from_file_location("sec_edgar_provider_standalone", module_path)
assert spec is not None
assert spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

blocked = [
    "requests",
    "httpx",
    "urllib.request",
    "urllib3",
]
print(json.dumps({name: name in sys.modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
