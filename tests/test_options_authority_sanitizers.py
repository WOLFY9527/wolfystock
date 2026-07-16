# -*- coding: utf-8 -*-
"""Golden offline parity for shared Options authority sanitization."""

from __future__ import annotations

import pytest

from src.services.options_authority_sanitizers import (
    coerce_bool,
    flatten_text,
    sanitize_date_range,
    sanitize_mapping,
    sanitize_sequence,
)
from src.services.options_event_calendar_authority import (
    build_options_event_calendar_authority_diagnostic,
)
from src.services.options_expiration_calendar_authority import (
    build_options_expiration_calendar_authority_diagnostic,
)
from src.services.options_expiration_source_candidate_evidence import (
    build_expiration_calendar_source_candidate_evidence,
)
from src.services.options_iv_rank_authority import build_options_iv_rank_authority_diagnostic


def _authority_text(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "token" in text.lower() or any(character.lower() not in "abcdefghijklmnopqrstuvwxyz0123456789_:-+./" for character in text):
        return "redacted"
    return text


@pytest.fixture
def offline_operator_evidence_fixture() -> dict[str, object]:
    """Static payloads only; these tests must not contact a provider."""

    return {
        "malformed": {"providerId": {"unexpected": "mapping"}},
        "nested": {
            "safe": "provider_label",
            "credentialToken": "token=do-not-leak",
            "items": ["weekly", {"inner": "monthly"}, None, 2, False],
        },
        "dateRange": {"from": "2026-06-19", "to": "2026-08-21"},
        "calendarSla": {
            "maxAgePolicy": "300s",
            "providerSlaStatus": "met",
            "freshnessSeconds": 12,
            "freshnessState": "fresh",
            "latencyState": "normal",
        },
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        (True, True),
        ("enabled", True),
        ("disabled", False),
        ("unknown", None),
        (0, False),
        (2, True),
    ],
)
def test_options_authority_sanitizers_preserve_golden_null_and_boolean_values(
    value: object,
    expected: bool | None,
) -> None:
    assert coerce_bool(value) is expected


def test_options_authority_sanitizers_preserve_golden_mapping_sequence_date_and_flattening(
    offline_operator_evidence_fixture: dict[str, object],
) -> None:
    nested = offline_operator_evidence_fixture["nested"]
    assert sanitize_mapping(nested, sanitize_text=_authority_text) == {
        "safe": "provider_label",
        "redacted": "redacted",
        "items": ["weekly", {"inner": "monthly"}, 2, False],
    }
    assert sanitize_sequence(("weekly", {"inner": "monthly"}, None, 2, False), sanitize_text=_authority_text) == [
        "weekly",
        {"inner": "monthly"},
        2,
        False,
    ]
    assert sanitize_sequence([range(2)], sanitize_text=_authority_text) == ["redacted"]
    assert sanitize_date_range(offline_operator_evidence_fixture["dateRange"], sanitize_text=_authority_text) == {
        "start": "2026-06-19",
        "end": "2026-08-21",
    }
    assert flatten_text(["proxy", {"source": ["fixture", "note"]}], sanitize_text=_authority_text) == "proxy fixture note"


def test_four_operator_evidence_paths_preserve_golden_offline_sanitization(
    offline_operator_evidence_fixture: dict[str, object],
) -> None:
    nested = offline_operator_evidence_fixture["nested"]
    date_range = offline_operator_evidence_fixture["dateRange"]
    calendar_sla = offline_operator_evidence_fixture["calendarSla"]

    event = build_options_event_calendar_authority_diagnostic(
        {
            **offline_operator_evidence_fixture["malformed"],
            "eventTypesCovered": ["earnings", {"ignored": "nested"}, None],
            "dateRange": date_range,
            "sessionMetadata": nested,
            "slaEvidence": calendar_sla,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
        }
    )
    expiration = build_options_expiration_calendar_authority_diagnostic(
        {
            **offline_operator_evidence_fixture["malformed"],
            "expirationDates": ["2026-06-19", {"ignored": "nested"}, None],
            "dateRange": date_range,
            "coverageMetadata": nested,
            "slaEvidence": calendar_sla,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
        }
    )
    iv_rank = build_options_iv_rank_authority_diagnostic(
        {
            **offline_operator_evidence_fixture["malformed"],
            "dateRange": date_range,
            "coverageMetadata": nested,
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "met",
                "freshnessSeconds": 12,
            },
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
        }
    )
    candidate = build_expiration_calendar_source_candidate_evidence(
        {
            "candidateSourceName": {"unexpected": "mapping"},
            "provenanceChain": ["licensed_provider", nested, None],
            "observedDateRange": date_range,
            "sampleExpirationDates": ["2026-06-19", {"ignored": "nested"}, None],
            "asOf": "2026-05-26T12:00:00Z",
            "freshnessStatement": "fresh",
            "maxAgePolicy": "300s",
        }
    )

    assert event["providerId"] == "redacted"
    assert event["eventTypesCovered"] == ["earnings"]
    assert event["dateRange"] == {"start": "2026-06-19", "end": "2026-08-21"}
    assert event["sessionMetadata"] == {
        "safe": "provider_label",
        "redacted": "redacted",
        "items": ["weekly", {"inner": "monthly"}, 2, False],
    }
    assert event["authorityEvidenceChecklist"]["sla_freshness"]["present"] is True

    assert expiration["providerId"] == "redacted"
    assert expiration["expirationDates"] == ["2026-06-19"]
    assert expiration["dateRange"] == {"start": "2026-06-19", "end": "2026-08-21"}
    assert expiration["coverageMetadata"] == event["sessionMetadata"]
    assert expiration["authorityEvidenceChecklist"]["sla_freshness"]["present"] is True

    assert iv_rank["providerId"] == "redacted"
    assert iv_rank["dateRange"] == {"start": "2026-06-19", "end": "2026-08-21"}
    assert iv_rank["coverageMetadata"] == event["sessionMetadata"]
    assert iv_rank["authorityEvidenceChecklist"]["sla_freshness"]["present"] is True

    assert candidate["sourceIdentity"]["candidateSourceName"] == "redacted"
    assert candidate["provenance"]["provenanceChain"] == [
        "licensed_provider",
        {
            "safe": "provider_label",
            "redacted": "redacted",
            "items": ["weekly", {"inner": "monthly"}, 2, False],
        },
    ]
    assert candidate["expirationCoverage"]["observedDateRange"] == {
        "from": "2026-06-19",
        "to": "2026-08-21",
    }
    assert candidate["freshnessSla"] == {
        "asOf": "2026-05-26T12:00:00Z",
        "freshnessStatement": "fresh",
        "maxAgePolicy": "300s",
    }
