# -*- coding: utf-8 -*-
"""Diagnostic-only IV-rank authority contract tests."""

from __future__ import annotations

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
            "coverageMetadata": {"contractsCovered": 84},
            "sandboxOrProduction": "sandbox",
        }
    )

    assert claimed["authoritative"] is False
    assert claimed["authorityState"] == "non_authoritative"
    assert "iv_rank_provider_self_claim_ignored" in claimed["reasonCodes"]

    assert authorized["authoritative"] is True
    assert authorized["authorityState"] == "authoritative"
    assert authorized["reasonCodes"] == []


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
    assert diagnostic["reasonCodes"] == [
        "iv_rank_authority_missing",
        "iv_rank_proxy_not_authoritative",
        "iv_rank_provider_self_claim_only_not_authoritative",
    ]
