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
    SourceConfidenceContract,
    SourceFreshness,
    coerce_source_confidence_contract,
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
