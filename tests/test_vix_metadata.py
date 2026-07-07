# -*- coding: utf-8 -*-
"""Tests for the VIX / volatility snapshot authority contract."""

from __future__ import annotations

import json

from src.services.vix_metadata import normalize_vix_quote_metadata


def test_official_vix_snapshot_authority_contract_is_fail_closed_for_scores() -> None:
    item = normalize_vix_quote_metadata(
        {
            "symbol": "VIX",
            "label": "VIX",
            "value": 16.2,
            "source": "fred",
            "sourceId": "fred:VIXCLS",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "officialSeriesId": "VIXCLS",
            "asOf": "2026-07-06T20:00:00Z",
            "updatedAt": "2026-07-06T20:05:00Z",
            "freshness": "delayed",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        }
    )

    snapshot = item["volatilityAuthoritySnapshot"]

    assert snapshot["snapshotId"] == "volatility:VIX:fred:VIXCLS:2026-07-06T20:00:00Z"
    assert snapshot["instrumentIdentity"] == {
        "symbol": "VIX",
        "canonicalSymbol": "VIX",
        "officialSeriesId": "VIXCLS",
        "identityState": "canonical_official_vix",
    }
    assert snapshot["sourceId"] == "fred:VIXCLS"
    assert snapshot["sourceType"] == "official_public"
    assert snapshot["authorityState"] == "official"
    assert snapshot["observationTime"] == "2026-07-06T20:00:00Z"
    assert snapshot["retrievalTime"] == "2026-07-06T20:05:00Z"
    assert snapshot["freshnessState"] == "delayed"
    assert snapshot["delayedStaleReason"] == "official_delayed_publication"
    assert snapshot["coverageState"] == "available"
    assert snapshot["proxyFallback"] is False
    assert snapshot["consumerEligibility"] == {
        "marketOverview": True,
        "liquidity": True,
        "scenarioBaseline": True,
    }
    assert snapshot["scoreEligibility"] == {
        "allowed": False,
        "reason": "volatility_snapshot_score_default_closed",
    }
    assert item["scoreContributionAllowed"] is False
    assert item["scoreAuthorityEligible"] is False
    assert item["sourceAuthorityState"] == "official"
    assert item["volatilitySnapshotId"] == snapshot["snapshotId"]


def test_yfinance_vix_proxy_stays_distinguishable_and_observation_only() -> None:
    item = normalize_vix_quote_metadata(
        {
            "symbol": "VIX",
            "label": "VIX",
            "value": 17.1,
            "source": "yfinance",
            "sourceId": "yfinance:^VIX",
            "sourceType": "public_proxy",
            "asOf": "2026-07-06T19:59:00Z",
            "updatedAt": "2026-07-06T20:01:00Z",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        }
    )

    snapshot = item["volatilityAuthoritySnapshot"]

    assert snapshot["authorityState"] == "proxy"
    assert snapshot["proxyFallback"] is True
    assert snapshot["freshnessState"] == "delayed"
    assert snapshot["delayedStaleReason"] == "unofficial_proxy_delayed"
    assert snapshot["consumerEligibility"] == {
        "marketOverview": True,
        "liquidity": False,
        "scenarioBaseline": False,
    }
    assert snapshot["scoreEligibility"] == {
        "allowed": False,
        "reason": "unofficial_proxy_not_score_grade",
    }
    assert item["sourceType"] == "unofficial_proxy"
    assert item["sourceAuthorityAllowed"] is False
    assert item["scoreContributionAllowed"] is False
    assert item["observationOnly"] is True
    assert "Yahoo Finance" in str(item["sourceLabel"])


def test_vix_identity_substitution_is_rejected_without_relabeling_as_vixcls() -> None:
    item = normalize_vix_quote_metadata(
        {
            "symbol": "VIX",
            "label": "VIX",
            "value": 28.4,
            "source": "fred",
            "sourceId": "fred:VXNCLS",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "officialSeriesId": "VXNCLS",
            "asOf": "2026-07-06T20:00:00Z",
            "updatedAt": "2026-07-06T20:05:00Z",
            "freshness": "delayed",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        }
    )

    snapshot = item["volatilityAuthoritySnapshot"]

    assert snapshot["instrumentIdentity"]["officialSeriesId"] == "VXNCLS"
    assert snapshot["instrumentIdentity"]["identityState"] == "identity_mismatch"
    assert snapshot["authorityState"] == "blocked"
    assert snapshot["coverageState"] == "rejected"
    assert snapshot["delayedStaleReason"] == "identity_mismatch"
    assert snapshot["consumerEligibility"] == {
        "marketOverview": False,
        "liquidity": False,
        "scenarioBaseline": False,
    }
    assert snapshot["scoreEligibility"] == {
        "allowed": False,
        "reason": "identity_mismatch",
    }
    assert item["sourceAuthorityAllowed"] is False
    assert item["scoreContributionAllowed"] is False
    assert item["officialSeriesId"] == "VXNCLS"


def test_vix_authority_snapshot_is_consumer_safe_and_has_no_raw_provider_markers() -> None:
    item = normalize_vix_quote_metadata(
        {
            "symbol": "VIX",
            "source": "fred",
            "sourceId": "fred:VIXCLS",
            "sourceType": "official_public",
            "officialSeriesId": "VIXCLS",
            "asOf": "2026-07-06T20:00:00Z",
            "updatedAt": "2026-07-06T20:05:00Z",
            "freshness": "cached",
            "providerName": "internal-provider",
            "rawPayload": {"secret": "value"},
            "requestId": "req-123",
        }
    )

    serialized = json.dumps(item["volatilityAuthoritySnapshot"], sort_keys=True)

    assert "providerName" not in serialized
    assert "rawPayload" not in serialized
    assert "requestId" not in serialized
    assert "internal-provider" not in serialized
