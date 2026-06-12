# -*- coding: utf-8 -*-
"""Tests for the helper-only Market Intelligence provenance sidecar."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import src.services.market_intelligence_source_provenance_sidecar as market_helper
from src.services.market_intelligence_source_provenance_sidecar import (
    MARKET_INTELLIGENCE_SOURCE_PROVENANCE_VERSION,
    build_market_intelligence_source_provenance_sidecar,
)
from src.services.source_provenance_contract import SOURCE_PROVENANCE_CONTRACT_VERSION, summarize_source_provenance


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/market_intelligence_source_provenance_sidecar.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.data_source_router",
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


def _readyish_inputs() -> dict[str, object]:
    return {
        "marketRegime": {
            "source": "market_temperature",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "observationOnly": False,
            "label": "Market temperature regime",
        },
        "liquidity": {
            "source": "capital_flow_signal",
            "sourceType": "authorized_licensed_feed",
            "sourceTier": "authorized_licensed_feed",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "observationOnly": False,
            "sourceLabel": "Capital flow signal",
        },
        "rotation": {
            "source": "rotation_family_rollup",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "cached",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "observationOnly": False,
            "sourceLabel": "Rotation family rollup",
        },
        "breadth": {
            "source": "us_breadth_snapshot",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "observationOnly": False,
            "sourceLabel": "Breadth snapshot",
        },
        "scannerContext": {
            "source": "scanner_context_frame",
            "sourceType": "cache_snapshot",
            "sourceTier": "cache_snapshot",
            "freshness": "cached",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "observationOnly": True,
            "sourceLabel": "Scanner context frame",
        },
        "macroLiquidity": {
            "source": "official_macro_readiness",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "fresh",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "observationOnly": True,
            "sourceLabel": "Official macro readiness",
        },
        "volatility": {
            "source": "volatility_panel",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": False,
            "observationOnly": True,
            "sourceLabel": "Volatility panel",
        },
        "sentiment": {
            "source": "market_sentiment_snapshot",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "fresh",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "observationOnly": True,
            "sourceLabel": "Market sentiment snapshot",
        },
        "sectorTheme": {
            "source": "sector_theme_projection",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "cached",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "observationOnly": True,
            "sourceLabel": "Sector theme projection",
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


def _legacy_market_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    mapped = market_helper._mapping(payload)
    return sorted(
        [
            market_helper._build_domain_entry(domain_key, evidence_domain, fallback_label, mapped[domain_key])
            for domain_key, evidence_domain, fallback_label in market_helper._DOMAIN_SPECS
            if domain_key in mapped
        ],
        key=lambda item: (item["sourceId"], item["debugRef"], item["evidenceDomain"]),
    )


def test_helper_is_pure_and_json_stable() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    sidecar = build_market_intelligence_source_provenance_sidecar(_readyish_inputs())

    assert json.loads(json.dumps(sidecar, ensure_ascii=False, sort_keys=True)) == sidecar


def test_readyish_market_payload_matches_legacy_inline_sidecar_wrapper() -> None:
    payload = _readyish_inputs()
    sidecar = build_market_intelligence_source_provenance_sidecar(payload)
    expected = _legacy_sidecar_payload(
        MARKET_INTELLIGENCE_SOURCE_PROVENANCE_VERSION,
        _legacy_market_entries(payload),
    )

    assert json.loads(json.dumps(sidecar, ensure_ascii=False, sort_keys=True)) == json.loads(
        json.dumps(expected, ensure_ascii=False, sort_keys=True)
    )


def test_readyish_market_payload_builds_all_expected_entries() -> None:
    sidecar = build_market_intelligence_source_provenance_sidecar(_readyish_inputs())

    assert sidecar["contractVersion"] == MARKET_INTELLIGENCE_SOURCE_PROVENANCE_VERSION
    assert sidecar["sourceProvenanceContractVersion"] == SOURCE_PROVENANCE_CONTRACT_VERSION
    assert sidecar["entryCount"] == 9
    assert sidecar["evidenceDomainCounts"] == {
        "macro": 2,
        "market_data": 6,
        "research": 1,
    }
    debug_refs = {entry["debugRef"] for entry in sidecar["entries"]}
    assert debug_refs == {
        "source-provenance:market:breadth",
        "source-provenance:market:liquidity",
        "source-provenance:market:macroliquidity",
        "source-provenance:market:marketregime",
        "source-provenance:market:rotation",
        "source-provenance:market:scannercontext",
        "source-provenance:market:sectortheme",
        "source-provenance:market:sentiment",
        "source-provenance:market:volatility",
    }

    by_debug = {entry["debugRef"]: entry for entry in sidecar["entries"]}
    assert by_debug["source-provenance:market:marketregime"]["scoreContributionAllowed"] is True
    assert by_debug["source-provenance:market:liquidity"]["authorityTier"] == "score_grade"
    assert by_debug["source-provenance:market:scannercontext"]["observationOnly"] is True
    assert by_debug["source-provenance:market:scannercontext"]["scoreContributionAllowed"] is False


def test_missing_evidence_fails_closed() -> None:
    sidecar = build_market_intelligence_source_provenance_sidecar(
        {
            "marketRegime": {
                "source": "market_temperature",
                "freshness": "unknown",
            },
            "liquidity": {},
        }
    )

    assert sidecar["entryCount"] == 2
    assert sidecar["authorityTierCounts"]["observation_only"] == 2
    assert sidecar["observationOnlyCount"] == 2
    assert sidecar["scoreContributionAllowedCount"] == 0
    assert all(entry["observationOnly"] is True for entry in sidecar["entries"])
    assert all(entry["scoreContributionAllowed"] is False for entry in sidecar["entries"])
    assert all("unknown_source" in entry["limitations"] for entry in sidecar["entries"])


def test_stale_fallback_and_proxy_sources_downgrade() -> None:
    sidecar = build_market_intelligence_source_provenance_sidecar(
        {
            "marketRegime": {
                "source": "market_temperature",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "stale",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "observationOnly": False,
            },
            "breadth": {
                "source": "breadth_proxy",
                "sourceType": "unofficial_proxy",
                "sourceTier": "unofficial_proxy",
                "freshness": "fallback",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "observationOnly": False,
                "fallbackUsed": True,
            },
        }
    )

    by_debug = {entry["debugRef"]: entry for entry in sidecar["entries"]}
    regime = by_debug["source-provenance:market:marketregime"]
    breadth = by_debug["source-provenance:market:breadth"]

    assert regime["freshnessState"] == "stale"
    assert regime["observationOnly"] is True
    assert regime["scoreContributionAllowed"] is False
    assert "stale_source" in regime["limitations"]

    assert breadth["freshnessState"] == "fallback"
    assert breadth["sourceTier"] == "proxy"
    assert breadth["fallbackOrProxy"] is True
    assert breadth["observationOnly"] is True
    assert breadth["scoreContributionAllowed"] is False


def test_scanner_context_absent_is_omitted() -> None:
    inputs = _readyish_inputs()
    del inputs["scannerContext"]

    sidecar = build_market_intelligence_source_provenance_sidecar(inputs)

    assert sidecar["entryCount"] == 8
    assert "source-provenance:market:scannercontext" not in {
        entry["debugRef"] for entry in sidecar["entries"]
    }


def test_leakage_guardrails_and_fixture_demo_fail_closed() -> None:
    sidecar = build_market_intelligence_source_provenance_sidecar(
        {
            "sentiment": {
                "source": "provider_payload_session_cookie",
                "sourceLabel": "Internal raw payload token",
                "sourceType": "fixture_demo",
                "sourceTier": "fixture_demo",
                "freshness": "demo",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "observationOnly": False,
                "debugRef": "payload:session:token",
            }
        }
    )

    entry = sidecar["entries"][0]
    consumer_values = json.dumps(entry, ensure_ascii=False).lower()
    for blocked in ("token", "cookie", "session", "payload", "internal", "raw"):
        assert blocked not in consumer_values
    assert entry["sourceId"] == "unknown_source"
    assert entry["sourceLabel"] == "未知来源"
    assert entry["authorityTier"] == "unknown"
    assert entry["scoreContributionAllowed"] is False
