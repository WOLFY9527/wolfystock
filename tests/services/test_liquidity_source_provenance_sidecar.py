# -*- coding: utf-8 -*-
"""Tests for helper-only Liquidity provenance sidecar builder."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import src.services.liquidity_source_provenance_sidecar as liquidity_helper
from src.services.source_provenance_contract import SOURCE_PROVENANCE_CONTRACT_VERSION, summarize_source_provenance


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/liquidity_source_provenance_sidecar.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "bot",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "src.services.liquidity_monitor_service",
    "src.services.market_cache",
    "src.settings",
)


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _readyish_payload() -> dict[str, object]:
    return {
        "readiness": {
            "freshness": "cached",
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "reasonCodes": ["source_authority_missing", "score_rights_missing"],
        },
        "observationEvidence": {
            "indicatorEvidence": [
                {
                    "key": "crypto_spot_momentum",
                    "source": "binance_spot",
                    "sourceLabel": "Binance Spot",
                    "sourceType": "authorized_licensed_feed",
                    "freshness": "fresh",
                    "scoreContributionAllowed": True,
                    "coverageObservationOnly": False,
                    "warnings": [],
                },
                {
                    "key": "crypto_funding",
                    "source": "binance_funding",
                    "sourceLabel": "Binance Funding",
                    "sourceType": "exchange_public",
                    "freshness": "cached",
                    "scoreContributionAllowed": False,
                    "coverageObservationOnly": True,
                    "warnings": [],
                },
                {
                    "key": "vix_pressure",
                    "source": "official_vix_bundle",
                    "sourceLabel": "Official VIX",
                    "sourceType": "official_public",
                    "freshness": "fresh",
                    "scoreContributionAllowed": True,
                    "coverageObservationOnly": False,
                    "warnings": [],
                },
                {
                    "key": "us_breadth_proxy",
                    "source": "breadth_proxy_snapshot",
                    "sourceLabel": "US Breadth Proxy",
                    "sourceType": "public_proxy",
                    "freshness": "delayed",
                    "scoreContributionAllowed": False,
                    "coverageObservationOnly": True,
                    "warnings": ["proxy_only"],
                },
            ]
        },
        "capitalFlowSignal": {
            "freshness": "delayed",
            "isFallback": False,
            "isStale": False,
            "isPartial": True,
            "sourceAssetPressure": [
                {
                    "asset": "rates",
                    "freshness": "cached",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "observationOnly": True,
                    "source": "official_us_rates_bundle",
                    "sourceLabel": "Official US Rates",
                    "sourceType": "official_public",
                },
                {
                    "asset": "usd",
                    "freshness": "cached",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "observationOnly": True,
                    "source": "official_usd_bundle",
                    "sourceLabel": "Official USD Pressure",
                    "sourceType": "official_public",
                },
                {
                    "asset": "volatility",
                    "freshness": "fresh",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                    "observationOnly": True,
                    "source": "official_vix_bundle",
                    "sourceLabel": "Official VIX",
                    "sourceType": "official_public",
                },
                {
                    "asset": "growth_ai_software_semis",
                    "freshness": "delayed",
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": True,
                    "observationOnly": True,
                    "source": "breadth_proxy_snapshot",
                    "sourceLabel": "US Breadth Proxy",
                    "sourceType": "public_proxy",
                },
            ],
        },
        "timeSeriesStatus": {
            "macroLiquidity": {"available": True, "source": "official_fed_liquidity_bundle", "sourceLabel": "Fed Liquidity", "sourceType": "official_public", "freshness": "cached"},
            "fundingStress": {"available": True, "source": "binance_funding", "sourceLabel": "Binance Funding", "sourceType": "exchange_public", "freshness": "cached"},
            "creditStress": {"available": True, "source": "official_us_rates_bundle", "sourceLabel": "Official US Rates", "sourceType": "official_public", "freshness": "cached"},
            "policyLiquidity": {"available": True, "source": "official_fed_liquidity_bundle", "sourceLabel": "Fed Liquidity", "sourceType": "official_public", "freshness": "cached"},
        },
        "signalCoverage": {
            "scoreGradeCoverage": 4,
            "observationOnlyEvidenceCount": 3,
            "proxyOnlyScoringCount": 0,
            "missingIndicatorCount": 1,
            "source": "liquidity_coverage_snapshot",
            "sourceLabel": "Liquidity Coverage Snapshot",
            "sourceType": "cache_snapshot",
            "freshness": "cached",
        },
    }


def _legacy_sidecar_payload(contract_version: str, entries: list[dict[str, object]]) -> dict[str, object]:
    summary = summarize_source_provenance(entries)
    return {
        "contractVersion": contract_version,
        "sourceProvenanceContractVersion": SOURCE_PROVENANCE_CONTRACT_VERSION,
        "entryCount": summary["entryCount"],
        "authorityTierCounts": summary["authorityTierCounts"],
        "freshnessStateCounts": summary["freshnessStateCounts"],
        "evidenceDomainCounts": summary["evidenceDomainCounts"],
        "fallbackOrProxyCount": summary["fallbackOrProxyCount"],
        "observationOnlyCount": summary["observationOnlyCount"],
        "scoreContributionAllowedCount": summary["scoreContributionAllowedCount"],
        "entries": entries,
    }


def _legacy_liquidity_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    mapped = liquidity_helper._mapping(payload)
    return sorted(
        [
            liquidity_helper._build_domain_entry(
                domain_key=domain_key,
                evidence_domain=evidence_domain,
                fallback_label=fallback_label,
                payload=mapped,
            )
            for domain_key, evidence_domain, fallback_label in liquidity_helper._DOMAIN_SPECS
        ],
        key=lambda item: (item["sourceId"], item["debugRef"], item["evidenceDomain"]),
    )


def test_helper_is_pure_and_json_stable() -> None:
    from src.services.liquidity_source_provenance_sidecar import (
        LIQUIDITY_SOURCE_PROVENANCE_VERSION,
        build_liquidity_source_provenance_sidecar,
    )

    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    sidecar = build_liquidity_source_provenance_sidecar(_readyish_payload())

    assert sidecar["contractVersion"] == LIQUIDITY_SOURCE_PROVENANCE_VERSION
    assert sidecar["sourceProvenanceContractVersion"] == SOURCE_PROVENANCE_CONTRACT_VERSION
    assert json.loads(json.dumps(sidecar, ensure_ascii=False, sort_keys=True)) == sidecar


def test_readyish_liquidity_payload_matches_legacy_inline_sidecar_wrapper() -> None:
    payload = _readyish_payload()
    from src.services.liquidity_source_provenance_sidecar import (
        LIQUIDITY_SOURCE_PROVENANCE_VERSION,
        build_liquidity_source_provenance_sidecar,
    )

    sidecar = build_liquidity_source_provenance_sidecar(payload)
    expected = _legacy_sidecar_payload(
        LIQUIDITY_SOURCE_PROVENANCE_VERSION,
        _legacy_liquidity_entries(payload),
    )

    assert json.loads(json.dumps(sidecar, ensure_ascii=False, sort_keys=True)) == json.loads(
        json.dumps(expected, ensure_ascii=False, sort_keys=True)
    )


def test_readyish_payload_builds_expected_domain_entries() -> None:
    from src.services.liquidity_source_provenance_sidecar import build_liquidity_source_provenance_sidecar

    sidecar = build_liquidity_source_provenance_sidecar(_readyish_payload())

    assert sidecar["entryCount"] == 9
    assert sidecar["evidenceDomainCounts"] == {
        "macro": 4,
        "market_data": 4,
        "research": 1,
    }

    by_debug = {entry["debugRef"]: entry for entry in sidecar["entries"]}
    assert set(by_debug) == {
        "source-provenance:liquidity-breadth",
        "source-provenance:liquidity-capitalflow",
        "source-provenance:liquidity-creditstress",
        "source-provenance:liquidity-fundingstress",
        "source-provenance:liquidity-liquidity",
        "source-provenance:liquidity-macroliquidity",
        "source-provenance:liquidity-policyliquidity",
        "source-provenance:liquidity-signalcoverage",
        "source-provenance:liquidity-volatility",
    }

    assert by_debug["source-provenance:liquidity-liquidity"]["authorityTier"] == "score_grade"
    assert by_debug["source-provenance:liquidity-liquidity"]["scoreContributionAllowed"] is True
    assert by_debug["source-provenance:liquidity-macroliquidity"]["authorityTier"] == "observation_only"
    assert by_debug["source-provenance:liquidity-capitalflow"]["observationOnly"] is True
    assert by_debug["source-provenance:liquidity-breadth"]["fallbackOrProxy"] is True
    assert by_debug["source-provenance:liquidity-signalcoverage"]["sourceTier"] == "stored_snapshot"


def test_missing_evidence_fails_closed() -> None:
    from src.services.liquidity_source_provenance_sidecar import build_liquidity_source_provenance_sidecar

    sidecar = build_liquidity_source_provenance_sidecar(
        {
            "readiness": {
                "freshness": "unknown",
                "observationOnly": True,
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": False,
            }
        }
    )

    assert sidecar["entryCount"] == 9
    assert sidecar["scoreContributionAllowedCount"] == 0
    assert sidecar["observationOnlyCount"] == 9
    assert all(entry["observationOnly"] is True for entry in sidecar["entries"])
    assert all(entry["scoreContributionAllowed"] is False for entry in sidecar["entries"])
    assert all("unknown_source" in entry["limitations"] for entry in sidecar["entries"])


def test_stale_fallback_and_proxy_sources_downgrade() -> None:
    from src.services.liquidity_source_provenance_sidecar import build_liquidity_source_provenance_sidecar

    payload = _readyish_payload()
    indicator_evidence = payload["observationEvidence"]["indicatorEvidence"]  # type: ignore[index]
    indicator_evidence[0]["freshness"] = "stale"  # type: ignore[index]
    indicator_evidence[0]["scoreContributionAllowed"] = True  # type: ignore[index]
    indicator_evidence[0]["coverageObservationOnly"] = False  # type: ignore[index]
    indicator_evidence[3]["sourceType"] = "unofficial_proxy"  # type: ignore[index]
    indicator_evidence[3]["freshness"] = "fallback"  # type: ignore[index]

    sidecar = build_liquidity_source_provenance_sidecar(payload)
    by_debug = {entry["debugRef"]: entry for entry in sidecar["entries"]}

    liquidity_entry = by_debug["source-provenance:liquidity-liquidity"]
    breadth_entry = by_debug["source-provenance:liquidity-breadth"]

    assert liquidity_entry["freshnessState"] == "stale"
    assert liquidity_entry["observationOnly"] is True
    assert liquidity_entry["scoreContributionAllowed"] is False
    assert "stale_source" in liquidity_entry["limitations"]

    assert breadth_entry["freshnessState"] == "fallback"
    assert breadth_entry["sourceTier"] == "proxy"
    assert breadth_entry["fallbackOrProxy"] is True
    assert breadth_entry["observationOnly"] is True
    assert breadth_entry["scoreContributionAllowed"] is False


def test_unavailable_time_series_fail_closed() -> None:
    from src.services.liquidity_source_provenance_sidecar import build_liquidity_source_provenance_sidecar

    payload = _readyish_payload()
    payload["timeSeriesStatus"]["macroLiquidity"] = {  # type: ignore[index]
        "available": False,
        "reason": "provider_unavailable",
        "freshness": "unavailable",
    }
    payload["timeSeriesStatus"]["policyLiquidity"] = {  # type: ignore[index]
        "available": False,
        "reason": "missing_rows",
        "freshness": "unavailable",
    }

    sidecar = build_liquidity_source_provenance_sidecar(payload)
    by_debug = {entry["debugRef"]: entry for entry in sidecar["entries"]}

    macro_entry = by_debug["source-provenance:liquidity-macroliquidity"]
    policy_entry = by_debug["source-provenance:liquidity-policyliquidity"]

    assert macro_entry["authorityTier"] == "observation_only"
    assert macro_entry["freshnessState"] == "unavailable"
    assert macro_entry["observationOnly"] is True
    assert "unavailable_source" in macro_entry["limitations"]

    assert policy_entry["authorityTier"] == "observation_only"
    assert policy_entry["scoreContributionAllowed"] is False
    assert "policyliquidity_authoritative_time_series" in policy_entry["nextEvidenceNeeded"]


def test_leakage_guardrails_and_fixture_demo_fail_closed() -> None:
    from src.services.liquidity_source_provenance_sidecar import build_liquidity_source_provenance_sidecar

    sidecar = build_liquidity_source_provenance_sidecar(
        {
            "observationEvidence": {
                "indicatorEvidence": [
                    {
                        "key": "vix_pressure",
                        "source": "provider_payload_session_cookie",
                        "sourceLabel": "Internal raw payload token",
                        "sourceType": "fixture_demo",
                        "freshness": "demo",
                        "scoreContributionAllowed": True,
                        "coverageObservationOnly": False,
                        "warnings": ["synthetic_fixture_data"],
                    }
                ]
            },
            "timeSeriesStatus": {
                "macroLiquidity": {
                    "available": True,
                    "source": "provider_payload_session_cookie",
                    "sourceLabel": "Internal secret payload",
                    "sourceType": "fixture",
                    "freshness": "demo",
                }
            },
        }
    )

    consumer_values = json.dumps(sidecar, ensure_ascii=False, sort_keys=True).lower()
    for blocked in ("token", "cookie", "session", "payload", "internal", "raw", "secret"):
        assert blocked not in consumer_values

    unknown_entries = [entry for entry in sidecar["entries"] if entry["debugRef"] == "source-provenance:unknown"]
    assert len(unknown_entries) == 2
    assert all(entry["observationOnly"] is True for entry in unknown_entries)
    assert all(entry["scoreContributionAllowed"] is False for entry in unknown_entries)
    assert all(entry["sourceId"] == "unknown_source" for entry in unknown_entries)
