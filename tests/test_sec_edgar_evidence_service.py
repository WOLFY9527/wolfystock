# -*- coding: utf-8 -*-
"""Offline contracts for SEC EDGAR companyfacts evidence projection."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from data_provider.sec_edgar_provider import parse_companyfacts_payload
from src.services.sec_edgar_evidence_service import project_sec_edgar_companyfacts_evidence


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sec_edgar" / "companyfacts_sample.json"


def test_project_companyfacts_parse_result_to_stable_evidence_records() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = parse_companyfacts_payload(payload)

    projected = project_sec_edgar_companyfacts_evidence(parsed)

    assert len(projected) == 4
    assert [item.concept for item in projected] == [
        "EntityCommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
        "Revenues",
        "Revenues",
    ]
    assert [item.period_end_date for item in projected] == [
        "2024-09-28",
        "2024-06-29",
        "2024-09-28",
        "2024-06-29",
    ]

    first = projected[0]
    assert first.provider_name == "SEC EDGAR"
    assert first.provider_id == "sec_edgar"
    assert first.source == "sec_edgar"
    assert first.source_tier == "official_public"
    assert first.trust_level == "reliable_for_filings_metadata"
    assert first.freshness_expectation == "filing_or_daily"
    assert first.observation_only is True
    assert first.score_contribution_allowed is False
    assert first.evidence_type == "official_company_fact"
    assert first.taxonomy == "dei"
    assert first.concept == "EntityCommonStockSharesOutstanding"
    assert first.unit == "shares"
    assert first.value == 15204137000
    assert first.accession_number == "0000320193-24-000123"
    assert first.form == "10-K"
    assert first.filed_at == "2024-11-01"
    assert first.fiscal_year == 2024
    assert first.fiscal_period == "FY"
    assert first.period_end_date == "2024-09-28"
    assert first.fiscal_end_date == "2024-09-28"
    assert first.frame == "CY2024Q3I"
    assert first.entity_name == "Apple Inc."
    assert first.cik == "0000320193"
    assert first.as_of == "2024-09-28"
    assert first.updated_at == "2024-11-01T14:00:00Z"
    assert (
        first.source_ref
        == "sec_edgar:companyfacts:0000320193:dei:EntityCommonStockSharesOutstanding:shares:0000320193-24-000123:2024-09-28:CY2024Q3I"
    )
    assert first.degradation_reason is None

    first_payload = first.to_dict()
    assert first_payload["providerName"] == "SEC EDGAR"
    assert first_payload["evidenceType"] == "official_company_fact"
    assert first_payload["observationOnly"] is True
    assert first_payload["scoreContributionAllowed"] is False
    assert first_payload["degradationReason"] is None
    assert "raw_payload" not in first_payload
    assert "payload" not in first_payload
    assert "facts" not in first_payload


def test_project_companyfacts_iterable_input_is_deterministic_and_matches_parse_result_projection() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = parse_companyfacts_payload(payload)

    from_parse_result = [item.to_dict() for item in project_sec_edgar_companyfacts_evidence(parsed)]
    from_records = [item.to_dict() for item in project_sec_edgar_companyfacts_evidence(parsed.records)]

    assert from_records == from_parse_result
    assert len(from_records) == len(parsed.records)
    assert parsed.warnings


def test_project_companyfacts_ignores_malformed_rows_by_consuming_only_parsed_records() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = parse_companyfacts_payload(payload)

    projected = project_sec_edgar_companyfacts_evidence(parsed)

    assert [warning.code for warning in parsed.warnings] == [
        "invalid_fact_row",
        "invalid_unit_key",
        "invalid_unit_rows",
    ]
    assert len(projected) == 4
    assert all(item.source_ref.startswith("sec_edgar:companyfacts:") for item in projected)


def test_project_companyfacts_marks_incomplete_optional_metadata_as_degraded_without_dropping_record() -> None:
    parsed = parse_companyfacts_payload(
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

    projected = project_sec_edgar_companyfacts_evidence(parsed)

    assert len(projected) == 1
    evidence = projected[0]
    assert evidence.form is None
    assert evidence.filed_at is None
    assert evidence.fiscal_year is None
    assert evidence.fiscal_period is None
    assert evidence.updated_at is None
    assert evidence.degradation_reason == "incomplete_observation_metadata"


def test_sec_edgar_evidence_service_import_is_metadata_only() -> None:
    script = """
import json
import importlib.util
from pathlib import Path
import sys

module_path = Path.cwd() / "src" / "services" / "sec_edgar_evidence_service.py"
spec = importlib.util.spec_from_file_location("sec_edgar_evidence_service_standalone", module_path)
assert spec is not None
assert spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
blocked = [
    "requests",
    "httpx",
    "urllib.request",
    "urllib3",
]
for name in blocked:
    sys.modules.pop(name, None)
spec.loader.exec_module(module)
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
