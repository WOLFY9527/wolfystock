# -*- coding: utf-8 -*-
"""Diagnostic-only IV-rank authority contract tests."""

from __future__ import annotations

import pytest

from src.services.options_authority_policy_matrix import (
    CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS,
)
from src.services.options_iv_rank_authority import (
    INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
    REQUIRED_FUTURE_IV_RANK_AUTHORITY_EVIDENCE_FIELDS,
    build_options_iv_rank_authority_diagnostic,
)


def test_missing_iv_rank_authority_is_distinct_from_non_authoritative_proxy_data() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(None)

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "missing"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "iv_rank_authority_missing",
        "iv_rank_source_unknown_or_missing",
        "iv_rank_historical_option_iv_series_missing",
        "iv_rank_provider_reported_percentile_missing",
        "iv_rank_source_authority_missing",
        "iv_rank_asof_or_freshness_missing",
        "iv_rank_lookback_missing",
        "iv_rank_methodology_missing",
        "iv_rank_coverage_metadata_missing",
    ]
    assert diagnostic["requiredFutureAuthorityEvidence"] == list(
        REQUIRED_FUTURE_IV_RANK_AUTHORITY_EVIDENCE_FIELDS
    )
    assert "authorityPolicySource" in diagnostic["requiredFutureAuthorityEvidence"]


def test_synthetic_fixture_proxy_iv_rank_stays_non_authoritative_with_explicit_gap_codes() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "synthetic_options_lab_fixture",
            "sourceType": "synthetic_fixture_proxy",
            "ivRankStatus": "available",
            "ivRankSource": "synthetic_fixture_proxy",
            "methodology": "local_min_max_percentile_from_proxy_history_plus_selected_contract_iv",
            "historicalOptionIvSeriesAvailable": False,
            "coverageMetadata": {
                "proxyHistoryPoints": 7,
                "currentIvSampleCount": 2,
                "currentIvDerivedFrom": "selected_contract_implied_volatility",
            },
            "sandboxOrProduction": "not_provider_sourced",
            "notes": ["test_only_low_confidence"],
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["providerId"] == "synthetic_options_lab_fixture"
    assert diagnostic["sourceType"] == "synthetic_fixture_proxy"
    assert diagnostic["ivRankStatus"] == "available"
    assert diagnostic["reasonCodes"] == [
        "iv_rank_authority_missing",
        "iv_rank_synthetic_fixture_proxy",
        "iv_rank_fixture_not_authoritative",
        "iv_rank_historical_option_iv_series_missing",
        "iv_rank_provider_reported_percentile_missing",
        "iv_rank_source_authority_missing",
        "iv_rank_asof_or_freshness_missing",
        "iv_rank_lookback_missing",
    ]


def test_request_supplied_iv_rank_object_remains_non_authoritative_even_if_fully_shaped() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "request_payload",
            "sourceType": "request_supplied",
            "sourceAuthority": "provider_self_claim",
            "ivRankStatus": "available",
            "ivRankSource": "request_shaped",
            "providerReportedIvPercentile": 64.0,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "user_supplied_rank",
            "coverageMetadata": {"contractsCovered": 12},
            "sandboxOrProduction": "production",
            "providerDecisionAuthorityClaim": True,
            "recommendationAuthorityClaim": True,
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "iv_rank_authority_missing",
        "iv_rank_request_supplied_not_authoritative",
        "iv_rank_request_shaped_not_authoritative",
        "iv_rank_provider_self_claim_ignored",
        "iv_rank_historical_option_iv_series_missing",
    ]


def test_internal_policy_is_required_before_any_iv_rank_payload_can_be_authoritative() -> None:
    claimed = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "tradier",
            "sourceType": "live",
            "sourceAuthority": "provider_reported",
            "ivRankStatus": "available",
            "ivRankSource": "provider_reported",
            "providerReportedIvPercentile": 63.0,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "provider_reported_iv_percentile",
            "coverageMetadata": {"contractsCovered": 84},
            "sandboxOrProduction": "sandbox",
            "providerDecisionAuthorityClaim": True,
        }
    )
    authorized = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "future_authorized_provider",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "provider_reported",
            "providerReportedIvPercentile": 63.0,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "provider_reported_iv_percentile",
            "coverageMetadata": {
                "symbolCoverage": ["TEM"],
                "underlyingCoverage": ["TEM"],
                "contractUniverseCoverage": "complete",
                "moneynessSelectionRules": "delta_25_to_75",
                "expirySelectionRules": "monthly_atm_preferred",
                "missingDataPolicy": "skip_sparse_contracts",
                "contractsCovered": 84,
            },
            "sandboxOrProduction": "production",
            "provenance": {"approvedProvider": "future_authorized_provider"},
            "entitlementMetadata": {
                "optionsIvHistoryEntitlement": True,
                "liveDelayedStatus": "live",
                "environment": "production",
                "decisionUseRights": True,
                "redistributionRights": True,
                "auditTimestamp": "2026-05-26T12:01:00Z",
            },
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "within_sla",
                "freshnessSeconds": 12,
                "freshnessState": "fresh",
            },
            "methodologyMetadata": {
                "methodologyVersion": "provider_v2",
                "calculationBasis": "provider_reported_iv_surface_history",
                "percentileRankDefinition": "1y_percentile",
            },
        }
    )

    assert claimed["authoritative"] is False
    assert claimed["authorityState"] == "non_authoritative"
    assert "iv_rank_provider_self_claim_ignored" in claimed["reasonCodes"]

    assert authorized["authoritative"] is True
    assert authorized["authorityState"] == "authoritative"
    assert authorized["reasonCodes"] == []
    assert authorized["authorityEvidenceGapFamilies"] == []
    assert authorized["authorityEvidenceChecklist"] == {
        "provenance": {
            "present": True,
            "required": True,
            "fields": [
                "approved_provider",
                "licensed_source",
                "approved_internal_derived_source",
            ],
        },
        "entitlement": {
            "present": True,
            "required": True,
            "fields": [
                "options_iv_history_entitlement",
                "live_delayed_status",
                "environment",
                "decision_use_rights",
                "redistribution_rights",
                "audit_timestamp",
            ],
        },
        "sla_freshness": {
            "present": True,
            "required": True,
            "fields": [
                "as_of",
                "freshness",
                "max_age_policy",
                "provider_sla_status",
                "freshness_seconds",
                "freshness_state",
                "latency_or_error_state",
            ],
        },
        "methodology": {
            "present": True,
            "required": True,
            "fields": [
                "provider_reported_iv_rank_or_percentile",
                "deterministic_derived_iv_rank",
                "methodology_version",
                "percentile_or_rank_definition",
                "calculation_basis",
            ],
        },
        "lookback_date_range": {
            "present": True,
            "required": True,
            "fields": [
                "lookback_window",
                "date_range_start",
                "date_range_end",
            ],
        },
        "option_iv_evidence": {
            "present": True,
            "required": True,
            "fields": [
                "approved_historical_option_iv_series_availability",
                "provider_reported_iv_rank",
                "provider_reported_iv_percentile",
            ],
        },
        "coverage_scope": {
            "present": True,
            "required": True,
            "fields": [
                "symbol_or_underlying_coverage",
                "contract_universe_coverage",
                "moneyness_selection_rules",
                "expiry_selection_rules",
                "missing_data_policy",
                "coverage_metadata",
            ],
        },
    }


def test_snake_case_provider_self_claim_alias_is_ignored_for_iv_rank() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "request_payload",
            "sourceType": "request_supplied",
            "sourceAuthority": "provider_self_claim",
            "ivRankStatus": "available",
            "ivRankSource": "request_shaped",
            "providerReportedIvPercentile": 64.0,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "user_supplied_rank",
            "coverageMetadata": {"contractsCovered": 12},
            "sandboxOrProduction": "production",
            "provider_decision_authority_claim": True,
            "recommendation_authority_claim": True,
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "iv_rank_authority_missing",
        "iv_rank_request_supplied_not_authoritative",
        "iv_rank_request_shaped_not_authoritative",
        "iv_rank_provider_self_claim_ignored",
        "iv_rank_historical_option_iv_series_missing",
    ]


def test_proxy_iv_rank_and_provider_self_claim_only_marker_stay_non_authoritative() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "tradier",
            "sourceType": "proxy",
            "sourceAuthority": "provider_self_claim_only",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "provider_reported",
            "providerReportedIvRank": 61.0,
            "providerReportedIvPercentile": 63.0,
            "historicalOptionIvSeriesAvailable": True,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "provider_reported_iv_percentile",
            "coverageMetadata": {"contractsCovered": 84},
            "sandboxOrProduction": "sandbox",
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert "iv_rank_proxy_not_authoritative" in diagnostic["reasonCodes"]
    assert "iv_rank_provider_self_claim_only_not_authoritative" in diagnostic["reasonCodes"]


def test_historical_iv_proxy_payload_remains_non_authoritative() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "synthetic_options_lab_fixture",
            "sourceType": "fixture",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "historical_iv_proxy",
            "historicalOptionIvSeriesAvailable": True,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "historical_iv_proxy_percentile",
            "coverageMetadata": {"contractsCovered": 84},
            "sandboxOrProduction": "production",
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert "iv_rank_fixture_not_authoritative" in diagnostic["reasonCodes"]


@pytest.mark.parametrize(
    ("provider_id", "source_type", "expected_reason_code"),
    (
        ("synthetic_options_lab_fixture", "fixture", "iv_rank_fixture_not_authoritative"),
        ("synthetic_options_lab_fixture", "synthetic", "iv_rank_synthetic_not_authoritative"),
        ("tradier", "fallback", "iv_rank_fallback_not_authoritative"),
        ("tradier", "dry_run", "iv_rank_dry_run_not_authoritative"),
        ("tradier", "adapter_contract", "iv_rank_adapter_contract_not_authoritative"),
        ("request_payload", "request_shaped", "iv_rank_request_shaped_not_authoritative"),
        ("request_payload", "request_supplied", "iv_rank_request_supplied_not_authoritative"),
        ("tradier", "proxy", "iv_rank_proxy_not_authoritative"),
    ),
)
def test_blocked_iv_rank_source_classes_stay_non_authoritative(
    provider_id: str,
    source_type: str,
    expected_reason_code: str,
) -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": provider_id,
            "sourceType": source_type,
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "provider_reported",
            "providerReportedIvRank": 61.0,
            "providerReportedIvPercentile": 63.0,
            "historicalOptionIvSeriesAvailable": True,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "provider_reported_iv_percentile",
            "coverageMetadata": {
                "symbolCoverage": ["TEM"],
                "underlyingCoverage": ["TEM"],
                "contractUniverseCoverage": "complete",
                "moneynessSelectionRules": "delta_25_to_75",
                "expirySelectionRules": "monthly_atm_preferred",
                "missingDataPolicy": "skip_sparse_contracts",
                "contractsCovered": 84,
            },
            "sandboxOrProduction": "production",
            "provenance": {"approvedProvider": "future_authorized_provider"},
            "entitlementMetadata": {
                "optionsIvHistoryEntitlement": True,
                "liveDelayedStatus": "live",
                "environment": "production",
                "decisionUseRights": True,
                "redistributionRights": True,
                "auditTimestamp": "2026-05-26T12:01:00Z",
            },
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "within_sla",
                "freshnessSeconds": 12,
                "freshnessState": "fresh",
            },
            "methodologyMetadata": {
                "methodologyVersion": "provider_v2",
                "calculationBasis": "provider_reported_iv_surface_history",
                "percentileRankDefinition": "1y_percentile",
            },
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert expected_reason_code in diagnostic["reasonCodes"]


def test_selected_contract_current_iv_and_greeks_alone_do_not_create_iv_rank_authority() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "tradier",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "selected_contract_current_iv",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "30d",
            "methodology": "selected_contract_current_iv_and_greeks_snapshot",
            "coverageMetadata": {
                "contractUniverseCoverage": "complete",
                "contractsCovered": 84,
                "symbolCoverage": ["TEM"],
            },
            "sandboxOrProduction": "production",
            "provenance": {"approvedProvider": "tradier"},
            "entitlementMetadata": {
                "optionsIvHistoryEntitlement": True,
                "liveDelayedStatus": "live",
                "environment": "production",
                "decisionUseRights": True,
                "redistributionRights": True,
                "auditTimestamp": "2026-05-26T12:01:00Z",
            },
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "within_sla",
                "freshnessSeconds": 12,
                "freshnessState": "fresh",
            },
            "methodologyMetadata": {
                "methodologyVersion": "v1",
                "calculationBasis": "selected_contract_current_iv_and_greeks",
                "percentileRankDefinition": "none_current_snapshot_only",
            },
            "selectedContractIv": 0.62,
            "currentIv": 0.62,
            "greeks": {"delta": 0.61, "midIv": 0.62},
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert "iv_rank_current_iv_or_greeks_context_only" in diagnostic["reasonCodes"]


def test_underlying_realized_volatility_remains_context_only_for_iv_rank_authority() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "tradier",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "underlying_realized_volatility_context",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "underlying_realized_volatility_proxy_rank",
            "coverageMetadata": {
                "contractUniverseCoverage": "complete",
                "contractsCovered": 84,
                "symbolCoverage": ["TEM"],
            },
            "sandboxOrProduction": "production",
            "provenance": {"approvedProvider": "tradier"},
            "entitlementMetadata": {
                "optionsIvHistoryEntitlement": True,
                "liveDelayedStatus": "delayed",
                "environment": "production",
                "decisionUseRights": True,
                "redistributionRights": True,
                "auditTimestamp": "2026-05-26T12:01:00Z",
            },
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "within_sla",
                "freshnessSeconds": 12,
                "freshnessState": "fresh",
            },
            "methodologyMetadata": {
                "methodologyVersion": "v1",
                "calculationBasis": "underlying_realized_volatility",
                "percentileRankDefinition": "realized_volatility_proxy",
            },
            "historicalOptionIvSeriesAvailable": True,
            "underlyingRealizedVolatility": 0.34,
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert "iv_rank_underlying_realized_volatility_context_only" in diagnostic["reasonCodes"]


def test_coverage_complete_without_checklist_evidence_stays_non_authoritative() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "tradier",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "provider_reported",
            "providerReportedIvPercentile": 63.0,
            "coverageMetadata": {
                "symbolCoverage": ["TEM"],
                "underlyingCoverage": ["TEM"],
                "contractUniverseCoverage": "complete",
                "contractsCovered": 84,
            },
            "sandboxOrProduction": "production",
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["authorityEvidenceGapFamilies"] == [
        "provenance",
        "entitlement",
        "sla_freshness",
        "methodology",
        "lookback_date_range",
        "coverage_scope",
    ]
    assert diagnostic["reasonCodes"] == [
        "iv_rank_authority_missing",
        "iv_rank_historical_option_iv_series_missing",
        "iv_rank_provenance_evidence_missing",
        "iv_rank_entitlement_evidence_missing",
        "iv_rank_sla_evidence_missing",
        "iv_rank_methodology_evidence_missing",
        "iv_rank_lookback_evidence_missing",
        "iv_rank_coverage_scope_evidence_missing",
        "iv_rank_current_provider_not_authoritative",
        "iv_rank_coverage_not_authority",
    ]
    assert diagnostic["authorityEvidenceChecklist"] == {
        "provenance": {
            "present": False,
            "required": True,
            "fields": [
                "approved_provider",
                "licensed_source",
                "approved_internal_derived_source",
            ],
        },
        "entitlement": {
            "present": False,
            "required": True,
            "fields": [
                "options_iv_history_entitlement",
                "live_delayed_status",
                "environment",
                "decision_use_rights",
                "redistribution_rights",
                "audit_timestamp",
            ],
        },
        "sla_freshness": {
            "present": False,
            "required": True,
            "fields": [
                "as_of",
                "freshness",
                "max_age_policy",
                "provider_sla_status",
                "freshness_seconds",
                "freshness_state",
                "latency_or_error_state",
            ],
        },
        "methodology": {
            "present": False,
            "required": True,
            "fields": [
                "provider_reported_iv_rank_or_percentile",
                "deterministic_derived_iv_rank",
                "methodology_version",
                "percentile_or_rank_definition",
                "calculation_basis",
            ],
        },
        "lookback_date_range": {
            "present": False,
            "required": True,
            "fields": [
                "lookback_window",
                "date_range_start",
                "date_range_end",
            ],
        },
        "option_iv_evidence": {
            "present": True,
            "required": True,
            "fields": [
                "approved_historical_option_iv_series_availability",
                "provider_reported_iv_rank",
                "provider_reported_iv_percentile",
            ],
        },
        "coverage_scope": {
            "present": False,
            "required": True,
            "fields": [
                "symbol_or_underlying_coverage",
                "contract_universe_coverage",
                "moneyness_selection_rules",
                "expiry_selection_rules",
                "missing_data_policy",
                "coverage_metadata",
            ],
        },
    }


def test_authoritative_iv_rank_requires_full_checklist_evidence() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "future_authorized_provider",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "provider_reported",
            "providerReportedIvPercentile": 63.0,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "provider_reported_iv_percentile",
            "coverageMetadata": {
                "symbolCoverage": ["TEM"],
                "underlyingCoverage": ["TEM"],
                "contractUniverseCoverage": "complete",
                "moneynessSelectionRules": "delta_25_to_75",
                "expirySelectionRules": "monthly_atm_preferred",
                "missingDataPolicy": "skip_sparse_contracts",
                "contractsCovered": 84,
            },
            "sandboxOrProduction": "production",
            "provenance": {"approvedProvider": "future_authorized_provider"},
            "entitlementMetadata": {
                "optionsIvHistoryEntitlement": True,
                "liveDelayedStatus": "live",
                "environment": "production",
                "decisionUseRights": True,
                "redistributionRights": True,
                "auditTimestamp": "2026-05-26T12:01:00Z",
            },
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "within_sla",
                "freshnessSeconds": 12,
                "freshnessState": "fresh",
            },
            "methodologyMetadata": {
                "methodologyVersion": "provider_v2",
                "calculationBasis": "provider_reported_iv_surface_history",
                "percentileRankDefinition": "1y_percentile",
            },
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "authoritative"
    assert diagnostic["authoritative"] is True
    assert diagnostic["reasonCodes"] == []


@pytest.mark.parametrize("provider_id", CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS)
def test_current_runtime_providers_do_not_become_iv_rank_authoritative(
    provider_id: str,
) -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": provider_id,
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "provider_reported",
            "providerReportedIvRank": 61.0,
            "providerReportedIvPercentile": 63.0,
            "historicalOptionIvSeriesAvailable": True,
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "provider_reported_iv_percentile",
            "coverageMetadata": {
                "symbolCoverage": ["TEM"],
                "underlyingCoverage": ["TEM"],
                "contractUniverseCoverage": "complete",
                "moneynessSelectionRules": "delta_25_to_75",
                "expirySelectionRules": "monthly_atm_preferred",
                "missingDataPolicy": "skip_sparse_contracts",
                "contractsCovered": 84,
            },
            "sandboxOrProduction": "production",
            "provenance": {"approvedProvider": provider_id},
            "entitlementMetadata": {
                "optionsIvHistoryEntitlement": True,
                "liveDelayedStatus": "live",
                "environment": "production",
                "decisionUseRights": True,
                "redistributionRights": True,
                "auditTimestamp": "2026-05-26T12:01:00Z",
            },
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "within_sla",
                "freshnessSeconds": 12,
                "freshnessState": "fresh",
            },
            "methodologyMetadata": {
                "methodologyVersion": "provider_v2",
                "calculationBasis": "provider_reported_iv_surface_history",
                "percentileRankDefinition": "1y_percentile",
            },
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert "iv_rank_current_provider_not_authoritative" in diagnostic["reasonCodes"]


def test_provider_capabilities_and_coverage_metadata_do_not_create_iv_rank_authority() -> None:
    diagnostic = build_options_iv_rank_authority_diagnostic(
        {
            "providerId": "future_candidate_provider",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            "ivRankStatus": "available",
            "ivRankSource": "provider_capabilities",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "lookbackWindow": "252d",
            "methodology": "provider_capability_self_claim",
            "coverageMetadata": {
                "symbolCoverage": ["TEM"],
                "underlyingCoverage": ["TEM"],
                "contractUniverseCoverage": "complete",
                "moneynessSelectionRules": "delta_25_to_75",
                "expirySelectionRules": "monthly_atm_preferred",
                "missingDataPolicy": "skip_sparse_contracts",
                "contractsCovered": 84,
            },
            "providerCapabilities": {
                "historicalIvHistory": True,
                "ivRankPercentile": True,
                "redistributionRights": True,
            },
            "sandboxOrProduction": "production",
            "provenance": {"approvedProvider": "future_candidate_provider"},
            "entitlementMetadata": {
                "optionsIvHistoryEntitlement": True,
                "liveDelayedStatus": "live",
                "environment": "production",
                "decisionUseRights": True,
                "redistributionRights": True,
                "auditTimestamp": "2026-05-26T12:01:00Z",
            },
            "slaMetadata": {
                "maxAgePolicy": "300s",
                "providerSlaStatus": "within_sla",
                "freshnessSeconds": 12,
                "freshnessState": "fresh",
            },
            "methodologyMetadata": {
                "methodologyVersion": "provider_v2",
                "calculationBasis": "provider_capability_claim",
                "percentileRankDefinition": "self_claim_only",
            },
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert "iv_rank_option_iv_evidence_missing" in diagnostic["reasonCodes"]
    assert "iv_rank_coverage_not_authority" in diagnostic["reasonCodes"]
