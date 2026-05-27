# -*- coding: utf-8 -*-
"""Pure contract tests for single-stock evidence metadata boundaries."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from src.services.single_stock_evidence_contract import build_single_stock_evidence_contract


REPO_ROOT = Path(__file__).resolve().parents[1]


def _boundary(contract: dict[str, object], claim: str) -> dict[str, object]:
    return next(item for item in contract["claimBoundaries"] if item["claim"] == claim)


def test_degraded_fallback_source_cannot_claim_live_or_fresh_evidence() -> None:
    contract = build_single_stock_evidence_contract(
        {
            "domain": "quote",
            "symbol": "AAPL",
            "providerId": "iex",
            "sourceType": "direct_feed",
            "asOf": "2026-05-27T09:30:00Z",
            "observedAt": "2026-05-27T09:30:01Z",
            "generatedAt": "2026-05-27T09:30:02Z",
            "freshness": "live",
            "isFallback": True,
            "confidenceWeight": 0.98,
        }
    )

    assert contract["diagnosticOnly"] is True
    assert contract["authorityGrant"] is False
    assert contract["observationOnly"] is True
    assert contract["freshness"] == "fallback"
    assert contract["confidenceWeight"] <= 0.4
    assert contract["capReason"] == "fallback_source"
    assert contract["degradationReason"] == "fallback_source"

    boundary = _boundary(contract, "live_or_fresh_reliable")
    assert boundary["allowed"] is False
    assert boundary["reasonCode"] == "fallback_source"


def test_mixed_quote_fields_preserve_field_level_refs() -> None:
    contract = build_single_stock_evidence_contract(
        {
            "domain": "quote",
            "symbol": "AAPL",
            "providerId": "mixed_quote_bundle",
            "sourceType": "mixed",
            "asOf": "2026-05-27T09:30:00Z",
            "observedAt": "2026-05-27T09:30:01Z",
            "generatedAt": "2026-05-27T09:30:02Z",
            "freshness": "fresh",
            "fieldRefs": {
                "lastPrice": {
                    "providerId": "iex",
                    "sourceType": "direct_feed",
                    "asOf": "2026-05-27T09:30:00Z",
                    "freshness": "live",
                },
                "bid": {
                    "providerId": "sip",
                    "sourceType": "consolidated_feed",
                    "asOf": "2026-05-27T09:30:00Z",
                    "freshness": "fresh",
                },
                "ask": {
                    "sourceNote": "auction_indication",
                },
            },
        }
    )

    assert contract["fieldRefs"] == {
        "lastPrice": {
            "providerId": "iex",
            "sourceType": "direct_feed",
            "asOf": "2026-05-27T09:30:00Z",
            "freshness": "live",
        },
        "bid": {
            "providerId": "sip",
            "sourceType": "consolidated_feed",
            "asOf": "2026-05-27T09:30:00Z",
            "freshness": "fresh",
        },
        "ask": {
            "sourceNote": "auction_indication",
        },
    }

    boundary = _boundary(contract, "field_level_provenance")
    assert boundary["allowed"] is True
    assert boundary["reasonCode"] == "field_refs_present"


def test_missing_freshness_metadata_blocks_live_claims() -> None:
    contract = build_single_stock_evidence_contract(
        {
            "domain": "intraday",
            "symbol": "TSLA",
            "providerId": "official_intraday_feed",
            "sourceType": "direct_feed",
            "freshness": "live",
            "confidenceWeight": 0.92,
        }
    )

    assert contract["observationOnly"] is True
    assert contract["freshness"] == "unknown"
    assert contract["capReason"] == "freshness_not_proven"
    assert contract["degradationReason"] == "freshness_not_proven"

    boundary = _boundary(contract, "live_or_fresh_reliable")
    assert boundary["allowed"] is False
    assert boundary["reasonCode"] == "freshness_not_proven"


@pytest.mark.parametrize(
    ("payload", "expected_freshness", "expected_cap", "expected_reason"),
    [
        (
            {
                "domain": "fundamentals",
                "symbol": "MSFT",
                "providerId": "fundamental_vendor",
                "sourceType": "licensed_feed",
                "asOf": "2026-05-27",
                "freshness": "fresh",
                "isStale": True,
                "confidenceWeight": 0.95,
            },
            "stale",
            0.6,
            "stale_source",
        ),
        (
            {
                "domain": "technicals",
                "symbol": "NVDA",
                "providerId": "technical_vendor",
                "sourceType": "licensed_feed",
                "asOf": "2026-05-27T09:30:00Z",
                "freshness": "fresh",
                "isPartial": True,
                "confidenceWeight": 0.9,
                "coverage": 0.5,
                "missingFields": ["macdSignal"],
            },
            "partial",
            0.7,
            "partial_coverage",
        ),
    ],
)
def test_stale_or_partial_evidence_triggers_confidence_cap(
    payload: dict[str, object],
    expected_freshness: str,
    expected_cap: float,
    expected_reason: str,
) -> None:
    contract = build_single_stock_evidence_contract(payload)

    assert contract["freshness"] == expected_freshness
    assert contract["confidenceWeight"] <= expected_cap
    assert contract["capReason"] == expected_reason
    assert contract["degradationReason"] == expected_reason
    assert contract["observationOnly"] is True


def test_url_like_secret_like_and_payload_shaped_strings_are_sanitized() -> None:
    contract = build_single_stock_evidence_contract(
        {
            "domain": "catalyst",
            "symbol": "META",
            "providerId": "https://provider.example.com/private?token=abc",
            "sourceType": "Authorization: Bearer very-secret",
            "asOf": "2026-05-27T09:30:00Z",
            "observedAt": "2026-05-27T09:30:01Z",
            "generatedAt": "2026-05-27T09:30:02Z",
            "freshness": "fresh",
            "fallbackChain": [
                "cache_hit",
                "https://fallback.example.com",
                "{\"headers\":{\"authorization\":\"secret\"}}",
            ],
            "missingFields": [
                "headline",
                "{\"raw_payload\":true}",
            ],
            "budgetSkipReason": "account_id=998877",
            "fieldRefs": {
                "headline": {
                    "providerId": "gnews",
                    "sourceNote": "{\"payload\":true}",
                }
            },
        }
    )

    assert contract["providerId"] == "redacted"
    assert contract["sourceType"] == "redacted"
    assert contract["fallbackChain"] == ["cache_hit", "redacted", "redacted"]
    assert contract["missingFields"] == ["headline", "redacted"]
    assert contract["budgetSkipReason"] == "redacted"
    assert contract["fieldRefs"]["headline"] == {
        "providerId": "gnews",
        "sourceNote": "redacted",
    }


def test_contract_module_import_is_inert_and_requires_no_runtime_clients() -> None:
    script = """
import sys
before = set(sys.modules)
import src.services.single_stock_evidence_contract
after = set(sys.modules)
for forbidden in [
    "data_provider",
    "data_provider.base",
    "src.config",
    "src.services.market_cache",
    "src.services.stock_service_provider_adapter",
    "api.v1.schemas.analysis",
    "requests",
    "httpx",
]:
    assert forbidden not in after - before, f"unexpected import side effect: {forbidden}"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
