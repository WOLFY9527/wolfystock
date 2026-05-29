# -*- coding: utf-8 -*-
"""Offline contracts for shared source-confidence metadata.

These tests are intentionally synthetic. They must not call providers, touch
MarketCache, or wire the contract into any runtime consumer.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from src.contracts.source_confidence import (
    ProviderCapabilityContract,
    ProviderCapabilitySupportContract,
    ProviderDryRunProbeContract,
    ProviderFitMetadataContract,
    SCORE_GRADE_BLOCKED_SOURCE_TYPES,
    SCORE_GRADE_TRUST_LEVELS,
    ScoreGradeSourceAuthorityResult,
    SourceConfidenceContract,
    SourceFreshness,
    coerce_provider_capability_support_contract,
    coerce_provider_dry_run_probe_contract,
    coerce_provider_fit_metadata_contract,
    coerce_source_confidence_contract,
    evaluate_score_grade_source_authority,
    validate_source_confidence_contract,
)


def test_source_confidence_contract_projects_required_camel_case_fields() -> None:
    contract = coerce_source_confidence_contract(
        {
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "asOf": "2026-05-18T09:30:00+08:00",
            "freshness": "delayed",
            "confidenceWeight": 0.72,
            "coverage": 0.88,
        }
    )

    assert contract.to_dict() == {
        "source": "yfinance_proxy",
        "sourceLabel": "Yahoo Finance",
        "asOf": "2026-05-18T09:30:00+08:00",
        "freshness": "delayed",
        "isFallback": False,
        "isStale": False,
        "isPartial": False,
        "isSynthetic": False,
        "isUnavailable": False,
        "confidenceWeight": 0.72,
        "coverage": 0.88,
        "degradationReason": None,
        "capReason": None,
    }


@pytest.mark.parametrize(
    ("payload", "expected_freshness", "expected_cap", "expected_reason"),
    [
        (
            {
                "source": "fallback",
                "sourceLabel": "Fallback",
                "freshness": "live",
                "isFallback": True,
                "confidenceWeight": 1.0,
                "coverage": 1.0,
            },
            "fallback",
            0.4,
            "fallback_source",
        ),
        (
            {
                "source": "cache",
                "sourceLabel": "Cache",
                "freshness": "fresh",
                "isStale": True,
                "confidenceWeight": 0.95,
                "coverage": 1.0,
            },
            "stale",
            0.6,
            "stale_source",
        ),
        (
            {
                "source": "mixed",
                "sourceLabel": "Mixed",
                "freshness": "live",
                "isPartial": True,
                "confidenceWeight": 0.9,
                "coverage": 0.5,
            },
            "partial",
            0.7,
            "partial_coverage",
        ),
        (
            {
                "source": "unit_fixture",
                "sourceLabel": "Unit Fixture",
                "freshness": "live",
                "isSynthetic": True,
                "confidenceWeight": 0.9,
                "coverage": 1.0,
            },
            "synthetic",
            0.2,
            "synthetic_source",
        ),
        (
            {
                "source": "unavailable",
                "sourceLabel": "Unavailable",
                "freshness": "fresh",
                "isUnavailable": True,
                "confidenceWeight": 0.9,
                "coverage": 1.0,
            },
            "unavailable",
            0.0,
            "unavailable_source",
        ),
    ],
)
def test_degraded_sources_are_capped_and_cannot_masquerade_as_live_or_fresh(
    payload: dict[str, object],
    expected_freshness: str,
    expected_cap: float,
    expected_reason: str,
) -> None:
    contract = coerce_source_confidence_contract(payload)
    projected = contract.to_dict()

    assert projected["freshness"] == expected_freshness
    assert projected["freshness"] not in {"live", "fresh"}
    assert projected["confidenceWeight"] <= expected_cap
    assert projected["capReason"] == expected_reason
    assert validate_source_confidence_contract(contract).is_valid is True


@pytest.mark.parametrize(
    ("payload", "expected_reason"),
    [
        (
            {
                "source": "fallback",
                "sourceLabel": "Fallback",
                "freshness": "live",
                "isFallback": True,
                "confidenceWeight": 1.0,
                "coverage": 1.0,
            },
            "fallback_source",
        ),
        (
            {
                "source": "cache",
                "sourceLabel": "Cache",
                "freshness": "fresh",
                "isStale": True,
                "confidenceWeight": 0.95,
                "coverage": 1.0,
            },
            "stale_source",
        ),
        (
            {
                "source": "mixed",
                "sourceLabel": "Mixed",
                "freshness": "live",
                "isPartial": True,
                "confidenceWeight": 0.9,
                "coverage": 0.5,
            },
            "partial_coverage",
        ),
        (
            {
                "source": "unit_fixture",
                "sourceLabel": "Unit Fixture",
                "freshness": "live",
                "isSynthetic": True,
                "confidenceWeight": 0.9,
                "coverage": 1.0,
            },
            "synthetic_source",
        ),
        (
            {
                "source": "unavailable",
                "sourceLabel": "Unavailable",
                "freshness": "fresh",
                "isUnavailable": True,
                "confidenceWeight": 0.9,
                "coverage": 1.0,
            },
            "unavailable_source",
        ),
    ],
)
def test_degraded_cap_reason_vocabulary_stays_aligned_with_score_grade_authority_gate(
    payload: dict[str, object],
    expected_reason: str,
) -> None:
    contract = coerce_source_confidence_contract(payload)
    result = evaluate_score_grade_source_authority(
        source_type="score_grade",
        source_tier="score_grade",
        trust_level="score_grade_when_configured",
        freshness=contract.freshness.value,
        is_fallback=contract.is_fallback,
        is_stale=contract.is_stale,
        is_synthetic=contract.is_synthetic,
        is_unavailable=contract.is_unavailable,
        score_contribution_allowed=True,
        source_authority_allowed=True,
    )

    assert contract.cap_reason == expected_reason
    assert result == ScoreGradeSourceAuthorityResult(
        allowed=False,
        reason_codes=(expected_reason,),
    )


def test_validator_flags_raw_degraded_source_claiming_live_freshness() -> None:
    raw = SourceConfidenceContract(
        source="fallback",
        source_label="Fallback",
        freshness=SourceFreshness.LIVE,
        is_fallback=True,
        confidence_weight=1.0,
    )

    result = validate_source_confidence_contract(raw)
    issue_codes = {issue.code for issue in result.issues}

    assert result.is_valid is False
    assert "degraded_claims_live_freshness" in issue_codes
    assert "confidence_weight_exceeds_degraded_cap" in issue_codes


def test_provider_capability_contract_documents_caps_without_runtime_ordering() -> None:
    capability = ProviderCapabilityContract(
        provider_id="yahoo_yfinance",
        source="yfinance_proxy",
        source_label="Yahoo Finance",
        domains=("quote", "ohlcv"),
        markets=("US", "HK"),
        freshness_cap=SourceFreshness.DELAYED,
        live_eligible=False,
        delayed_eligible=True,
        fallback_eligible=True,
        confidence_weight_cap=0.75,
        coverage=0.8,
        cap_reason="unofficial_delayed_proxy",
    )

    assert capability.to_dict() == {
        "providerId": "yahoo_yfinance",
        "source": "yfinance_proxy",
        "sourceLabel": "Yahoo Finance",
        "domains": ["quote", "ohlcv"],
        "markets": ["US", "HK"],
        "freshnessCap": "delayed",
        "liveEligible": False,
        "delayedEligible": True,
        "fallbackEligible": True,
        "syntheticEligible": False,
        "confidenceWeightCap": 0.75,
        "coverage": 0.8,
        "capReason": "unofficial_delayed_proxy",
    }


def test_provider_fit_metadata_contract_projects_required_camel_case_fields() -> None:
    contract = coerce_provider_fit_metadata_contract(
        {
            "providerName": "SEC EDGAR",
            "providerId": "sec_edgar",
            "providerCategory": "filings_reference",
            "sourceTier": "official_public",
            "trustLevel": "reliable_for_filings_metadata",
            "freshnessExpectation": "filing_or_daily",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "paidDataLikelyRequired": False,
            "keyRequired": False,
            "liveTestsAvoided": True,
            "cacheRequired": True,
            "backgroundRefreshRecommended": True,
            "enabledByDefault": False,
            "degradationReason": "provider_fit_metadata_only",
            "bestUseCases": ["filings_metadata", "company_facts_reference"],
            "rejectedFor": ["live_quotes", "scoring_inputs"],
            "notRecommendedFor": ["premarket_quotes"],
        }
    )

    assert contract.to_dict() == {
        "providerName": "SEC EDGAR",
        "providerId": "sec_edgar",
        "providerCategory": "filings_reference",
        "sourceTier": "official_public",
        "trustLevel": "reliable_for_filings_metadata",
        "freshnessExpectation": "filing_or_daily",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "paidDataLikelyRequired": False,
        "keyRequired": False,
        "liveTestsAvoided": True,
        "cacheRequired": True,
        "backgroundRefreshRecommended": True,
        "enabledByDefault": False,
        "missingProviderReason": None,
        "degradationReason": "provider_fit_metadata_only",
        "planDependent": False,
        "bestUseCases": ["filings_metadata", "company_facts_reference"],
        "rejectedFor": ["live_quotes", "scoring_inputs"],
        "notRecommendedFor": ["premarket_quotes"],
    }


def test_official_cn_money_market_normalized_rows_carry_non_scoring_source_confidence_fields() -> None:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from src.services.cn_money_market_rates_contracts import (
        OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        build_official_cn_money_market_rates_snapshot,
    )

    now = datetime(2026, 5, 23, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
    as_of = (now - timedelta(minutes=5)).isoformat(timespec="seconds")
    snapshot = build_official_cn_money_market_rates_snapshot(
        {
            "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
            "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "asOf": as_of,
            "publicationDate": "2026-05-23",
            "tradingDate": "2026-05-23",
            "holidayCalendarQualified": True,
            "observations": [
                {"symbol": "DR007", "value": 1.86, "unit": "%"},
                {"symbol": "SHIBOR", "officialSeriesId": "SHIBOR_ON", "value": 1.72, "unit": "%"},
            ],
        },
        now=now,
    )
    dr007 = next(item for item in snapshot["items"] if item["officialSeriesId"] == "DR007")
    contract = coerce_source_confidence_contract(
        {
            "source": dr007["source"],
            "sourceLabel": dr007["sourceLabel"],
            "asOf": dr007["asOf"],
            "freshness": dr007["freshness"],
            "confidenceWeight": 1.0,
            "coverage": snapshot["coverageRatio"],
        }
    )

    assert contract.to_dict()["source"] == OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID
    assert dr007["sourceType"] == "official_public"
    assert dr007["sourceTier"] == "official_public"
    assert dr007["sourceAuthorityAllowed"] is True
    assert dr007["scoreContributionAllowed"] is False
    assert dr007["observationOnly"] is True
    assert snapshot["readinessEligible"] is True
    assert snapshot["scoreGradeEvidenceAllowed"] is True
    assert snapshot["cacheBundleDiagnostics"]["readinessEligible"] is True
    assert snapshot["cacheBundleDiagnostics"]["scoreContributionAllowed"] is False


def test_official_cn_money_market_cache_bundle_readiness_is_fail_closed() -> None:
    from src.services.official_macro_liquidity_cache_contracts import (
        OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
        build_official_cn_money_market_cache_bundle,
    )

    complete_bundle = build_official_cn_money_market_cache_bundle(
        [
            {
                "symbol": "DR007",
                "officialSeriesId": "DR007",
                "value": 1.86,
                "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "delayed",
                "cacheOnly": True,
                "externalProviderCalls": False,
                "sourceAuthorityAllowed": True,
            },
            {
                "symbol": "SHIBOR",
                "officialSeriesId": "SHIBOR_ON",
                "value": 1.72,
                "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "cached",
                "cacheOnly": True,
                "externalProviderCalls": False,
                "sourceAuthorityAllowed": True,
            },
        ]
    )
    partial_bundle = build_official_cn_money_market_cache_bundle(
        [
            {
                "symbol": "DR007",
                "officialSeriesId": "DR007",
                "value": 1.86,
                "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "delayed",
            }
        ]
    )

    assert complete_bundle["providerId"] == OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID
    assert complete_bundle["requiredSeries"] == ["DR007", "SHIBOR_ON"]
    assert complete_bundle["fulfilledSeries"] == ["DR007", "SHIBOR_ON"]
    assert complete_bundle["missingSeries"] == []
    assert complete_bundle["coverageRatio"] == 1.0
    assert complete_bundle["externalProviderCalls"] is False
    assert complete_bundle["readinessEligible"] is True
    assert complete_bundle["scoreGradeEvidenceAllowed"] is True
    assert complete_bundle["cacheSafeOfficialEvidenceAllowed"] is True
    assert complete_bundle["scoreContributionAllowed"] is True
    assert complete_bundle["observationOnly"] is False
    assert partial_bundle["readinessEligible"] is False
    assert partial_bundle["scoreContributionAllowed"] is False
    assert partial_bundle["observationOnly"] is True
    assert partial_bundle["missingSeries"] == ["SHIBOR_ON"]


@pytest.mark.parametrize(
    ("row_updates", "expected_field", "expected_series", "expected_reason"),
    [
        ({}, "missingSeries", ["SHIBOR_ON"], "missing_official_cn_money_market_row"),
        ({"freshness": "stale", "isStale": True}, "staleSeries", ["SHIBOR_ON"], "stale_official_cn_money_market_evidence"),
        ({"source": "fallback", "sourceType": "fallback_static", "isFallback": True}, "fallbackOrProxySeries", ["SHIBOR_ON"], "fallback_or_proxy_source"),
        ({"source": "yfinance_proxy", "sourceType": "unofficial_proxy"}, "fallbackOrProxySeries", ["SHIBOR_ON"], "fallback_or_proxy_source"),
        ({"source": "synthetic", "sourceType": "synthetic_fixture", "freshness": "synthetic"}, "fallbackOrProxySeries", ["SHIBOR_ON"], "fallback_or_proxy_source"),
        ({"freshness": "unavailable", "isUnavailable": True, "value": None}, "unavailableSeries", ["SHIBOR_ON"], "unavailable_official_cn_money_market_evidence"),
        ({"value": "N/A"}, "malformedSeries", ["SHIBOR_ON"], "malformed_official_value"),
    ],
)
def test_official_cn_money_market_cache_bundle_blocks_degraded_rows(
    row_updates: dict[str, object],
    expected_field: str,
    expected_series: list[str],
    expected_reason: str,
) -> None:
    from src.services.official_macro_liquidity_cache_contracts import (
        OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
        build_official_cn_money_market_cache_bundle,
    )

    shibor_row = {
        "symbol": "SHIBOR",
        "officialSeriesId": "SHIBOR_ON",
        "value": 1.72,
        "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "freshness": "delayed",
        "cacheOnly": True,
        "externalProviderCalls": False,
    }
    if row_updates:
        shibor_row.update(row_updates)
        rows = [
            {
                "symbol": "DR007",
                "officialSeriesId": "DR007",
                "value": 1.86,
                "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "delayed",
                "cacheOnly": True,
                "externalProviderCalls": False,
            },
            shibor_row,
        ]
    else:
        rows = [
            {
                "symbol": "DR007",
                "officialSeriesId": "DR007",
                "value": 1.86,
                "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "delayed",
                "cacheOnly": True,
                "externalProviderCalls": False,
            }
        ]

    bundle = build_official_cn_money_market_cache_bundle(rows)

    assert bundle["readinessEligible"] is False
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["sourceAuthorityAllowed"] is False
    assert bundle["observationOnly"] is True
    assert bundle[expected_field] == expected_series
    assert expected_reason in bundle["reasonCodes"]


def test_official_fed_liquidity_cache_bundle_source_confidence_is_fail_closed() -> None:
    from src.services.official_macro_liquidity_cache_contracts import (
        OFFICIAL_FED_LIQUIDITY_PROVIDER_ID,
        build_official_fed_liquidity_cache_bundle,
    )

    complete_bundle = build_official_fed_liquidity_cache_bundle(
        [
            {
                "symbol": "FED_ASSETS",
                "officialSeriesId": "WALCL",
                "value": 7485000.0,
                "source": "fred",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "cached",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
            {
                "symbol": "FED_RRP",
                "officialSeriesId": "RRPONTSYD",
                "value": 432.2,
                "source": "fred",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "cached",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
            {
                "symbol": "TGA",
                "officialSeriesId": "WTREGEN",
                "value": 812000.0,
                "source": "fred",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "cached",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
            {
                "symbol": "RESERVES",
                "officialSeriesId": "WRESBAL",
                "value": 3260000.0,
                "source": "fred",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "cached",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
        ]
    )
    malformed_bundle = build_official_fed_liquidity_cache_bundle(
        [
            {
                "symbol": "FED_ASSETS",
                "officialSeriesId": "WALCL",
                "value": "N/A",
                "source": "fred",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "cached",
            }
        ]
    )

    assert complete_bundle["providerId"] == OFFICIAL_FED_LIQUIDITY_PROVIDER_ID
    assert complete_bundle["scoreContributionAllowed"] is True
    assert complete_bundle["sourceAuthorityAllowed"] is True
    assert complete_bundle["externalProviderCalls"] is False
    assert malformed_bundle["scoreContributionAllowed"] is False
    assert malformed_bundle["sourceAuthorityAllowed"] is False
    assert malformed_bundle["malformedSeries"] == ["WALCL"]
    assert malformed_bundle["observationOnly"] is True


def test_provider_capability_support_contract_projects_license_gated_missing_provider_fields() -> None:
    contract = coerce_provider_capability_support_contract(
        {
            "providerName": "Authorized US ETF Flow",
            "providerId": "authorized.us_etf_flow",
            "capability": "us_etf_creation_redemption",
            "sourceType": "missing",
            "sourceTier": "authorized_licensed_feed",
            "trustLevel": "score_grade_when_configured",
            "freshnessExpectation": "licensed_daily_or_delayed_fund_flow",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "paidDataLikelyRequired": True,
            "keyRequired": True,
            "cacheRequired": True,
            "backgroundRefreshRecommended": True,
            "degradationReason": "authorized_feed_not_configured",
            "missingProviderReason": "authorized_us_etf_flow_feed_not_configured",
        }
    )

    assert isinstance(contract, ProviderCapabilitySupportContract)
    assert contract.to_dict() == {
        "providerName": "Authorized US ETF Flow",
        "providerId": "authorized.us_etf_flow",
        "capability": "us_etf_creation_redemption",
        "sourceType": "missing",
        "sourceTier": "authorized_licensed_feed",
        "trustLevel": "score_grade_when_configured",
        "freshnessExpectation": "licensed_daily_or_delayed_fund_flow",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "paidDataLikelyRequired": True,
        "keyRequired": True,
        "cacheRequired": True,
        "backgroundRefreshRecommended": True,
        "degradationReason": "authorized_feed_not_configured",
        "missingProviderReason": "authorized_us_etf_flow_feed_not_configured",
    }


def test_authorized_index_futures_metadata_contracts_remain_observation_only_and_non_scoring() -> None:
    from src.services.provider_capability_matrix import (
        get_provider_capability_support_contract,
        get_provider_fit_metadata,
    )

    fit = get_provider_fit_metadata("exchange_or_broker_authorized.index_futures")
    support = get_provider_capability_support_contract(
        "exchange_or_broker_authorized.index_futures",
        "index_futures",
    )

    assert fit is not None
    fit_contract = coerce_provider_fit_metadata_contract(fit.to_dict())
    assert fit_contract.provider_id == "exchange_or_broker_authorized.index_futures"
    assert fit_contract.source_tier == "exchange_or_broker_authorized_feed"
    assert fit_contract.observation_only is True
    assert fit_contract.score_contribution_allowed is False
    assert fit_contract.plan_dependent is True
    assert fit_contract.missing_provider_reason == "authorized_index_futures_feed_not_configured"

    assert support is not None
    support_contract = coerce_provider_capability_support_contract(support.to_dict())
    assert support_contract.provider_id == "exchange_or_broker_authorized.index_futures"
    assert support_contract.capability == "index_futures"
    assert support_contract.source_type == "missing"
    assert support_contract.source_tier == "exchange_or_broker_authorized_feed"
    assert support_contract.observation_only is True
    assert support_contract.score_contribution_allowed is False
    assert support_contract.missing_provider_reason == "authorized_index_futures_feed_not_configured"


def test_provider_dry_run_probe_contract_stays_metadata_only_and_secret_safe() -> None:
    contract = coerce_provider_dry_run_probe_contract(
        {
            "providerName": "Finnhub",
            "providerId": "finnhub",
            "enabledByDefault": False,
            "reasonCode": "provider_fit_metadata_only",
            "networkCallExecuted": False,
            "noDefaultLiveHttpCalls": True,
            "httpMethod": "NONE",
            "keyRequired": True,
            "requiredCredentialCount": 1,
            "configuredCredentialCount": 0,
            "requiresCredentialPresenceOnly": True,
            "liveTestsAvoided": True,
            "cacheRequired": True,
            "backgroundRefreshRecommended": True,
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "rawCredentialValuesIncluded": False,
            "providerPayloadValuesIncluded": False,
            "responseBodiesIncluded": False,
            "degradationReason": "provider_fit_metadata_only",
        }
    )

    assert isinstance(contract, ProviderDryRunProbeContract)
    assert contract.to_dict() == {
        "providerName": "Finnhub",
        "providerId": "finnhub",
        "enabledByDefault": False,
        "reasonCode": "provider_fit_metadata_only",
        "networkCallExecuted": False,
        "noDefaultLiveHttpCalls": True,
        "httpMethod": "NONE",
        "keyRequired": True,
        "requiredCredentialCount": 1,
        "configuredCredentialCount": 0,
        "requiresCredentialPresenceOnly": True,
        "liveTestsAvoided": True,
        "cacheRequired": True,
        "backgroundRefreshRecommended": True,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "rawCredentialValuesIncluded": False,
        "providerPayloadValuesIncluded": False,
        "responseBodiesIncluded": False,
        "missingProviderReason": None,
        "degradationReason": "provider_fit_metadata_only",
    }


def test_score_grade_source_authority_result_is_frozen_and_slotted() -> None:
    result = ScoreGradeSourceAuthorityResult(allowed=False, reason_codes=("blocked_source_type",))

    assert result.allowed is False
    assert result.reason_codes == ("blocked_source_type",)
    assert not hasattr(result, "__dict__")
    with pytest.raises(AttributeError):
        result.allowed = True  # type: ignore[misc]


@pytest.mark.parametrize("source_type", sorted(SCORE_GRADE_BLOCKED_SOURCE_TYPES))
def test_score_grade_source_authority_blocks_known_non_authority_source_types(
    source_type: str,
) -> None:
    result = evaluate_score_grade_source_authority(
        source_type=source_type,
        source_tier="score_grade",
        trust_level="score_grade_when_configured",
        score_contribution_allowed=True,
        source_authority_allowed=True,
    )

    assert result == ScoreGradeSourceAuthorityResult(
        allowed=False,
        reason_codes=("blocked_source_type",),
    )


@pytest.mark.parametrize(
    ("updates", "expected_reason"),
    [
        ({"is_fallback": True}, "fallback_source"),
        ({"is_stale": True}, "stale_source"),
        ({"is_synthetic": True}, "synthetic_source"),
        ({"is_unavailable": True}, "unavailable_source"),
        ({"observation_only": True}, "observation_only"),
        ({"score_contribution_allowed": False}, "score_contribution_not_allowed"),
        ({"source_authority_allowed": False}, "source_authority_not_allowed"),
    ],
)
def test_score_grade_source_authority_blocks_degraded_flags_and_disabled_authority(
    updates: dict[str, object],
    expected_reason: str,
) -> None:
    payload: dict[str, object] = {
        "source_type": "score_grade",
        "source_tier": "score_grade",
        "trust_level": "score_grade_when_configured",
        "score_contribution_allowed": True,
        "source_authority_allowed": True,
    }
    payload.update(updates)

    result = evaluate_score_grade_source_authority(**payload)

    assert result.allowed is False
    assert result.reason_codes == (expected_reason,)


@pytest.mark.parametrize(
    ("updates", "expected_reason"),
    [
        ({"source_type": ""}, "missing_source_type"),
        ({"source_tier": ""}, "missing_source_tier"),
        ({"trust_level": ""}, "missing_trust_level"),
        ({"freshness": "fallback"}, "fallback_source"),
        ({"freshness": "stale"}, "stale_source"),
        ({"freshness": "synthetic"}, "synthetic_source"),
        ({"freshness": "unavailable"}, "unavailable_source"),
    ],
)
def test_score_grade_source_authority_fails_closed_for_missing_or_degraded_metadata(
    updates: dict[str, object],
    expected_reason: str,
) -> None:
    payload: dict[str, object] = {
        "source_type": "score_grade",
        "source_tier": "score_grade",
        "trust_level": "score_grade_when_configured",
        "score_contribution_allowed": True,
        "source_authority_allowed": True,
    }
    payload.update(updates)

    result = evaluate_score_grade_source_authority(**payload)

    assert result.allowed is False
    assert result.reason_codes == (expected_reason,)


def test_score_grade_source_authority_allows_explicit_score_grade_source_and_trust() -> None:
    result = evaluate_score_grade_source_authority(
        source_type="score_grade",
        source_tier="score_grade",
        trust_level="score_grade_when_configured",
        score_contribution_allowed=True,
        source_authority_allowed=True,
    )

    assert "score_grade_when_configured" in SCORE_GRADE_TRUST_LEVELS
    assert result == ScoreGradeSourceAuthorityResult(
        allowed=True,
        reason_codes=("score_grade_source_authority_allowed",),
    )


def test_score_grade_source_authority_allows_explicit_reproducible_local_or_stored_contract() -> None:
    result = evaluate_score_grade_source_authority(
        source_type="reproducible_local_or_stored",
        source_tier="reproducible_local_or_stored",
        trust_level="reproducible_local_or_stored",
        freshness="cached",
        score_contribution_allowed=True,
        source_authority_allowed=True,
        allowed_source_types=("reproducible_local_or_stored",),
        allowed_source_tiers=("reproducible_local_or_stored",),
    )

    assert result == ScoreGradeSourceAuthorityResult(
        allowed=True,
        reason_codes=("score_grade_source_authority_allowed",),
    )


def test_score_grade_source_authority_reason_codes_are_stable_and_bounded() -> None:
    result = evaluate_score_grade_source_authority(
        source_type="public_proxy",
        source_tier="unofficial_proxy",
        trust_level="usable_with_caution",
        observation_only=True,
        score_contribution_allowed=False,
        source_authority_allowed=False,
        is_stale=True,
    )

    assert result.allowed is False
    assert result.reason_codes == (
        "blocked_source_type",
        "blocked_source_tier",
        "trust_level_not_allowed",
        "stale_source",
        "observation_only",
        "score_contribution_not_allowed",
        "source_authority_not_allowed",
    )
    assert len(result.reason_codes) <= 8
    assert all(code.isidentifier() for code in result.reason_codes)
    assert "public_proxy" not in result.reason_codes
    assert "unofficial_proxy" not in result.reason_codes


def test_source_confidence_contract_import_is_inert() -> None:
    script = """
import json
import sys
import src.contracts.source_confidence

blocked = [
    "data_provider",
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.market_rotation_radar_service",
    "src.services.liquidity_monitor_service",
    "src.services.market_scanner_service",
    "src.services.portfolio_service",
    "api.v1.endpoints",
    "requests",
    "httpx",
    "pandas",
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
