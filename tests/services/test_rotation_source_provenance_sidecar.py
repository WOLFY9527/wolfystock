# -*- coding: utf-8 -*-
"""Tests for helper-only Rotation provenance sidecar builder."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.rotation_source_provenance_sidecar import (
    ROTATION_SOURCE_PROVENANCE_VERSION,
    build_rotation_source_provenance_sidecar,
    summarize_rotation_source_provenance_sidecar,
)
from src.services.source_provenance_contract import SOURCE_PROVENANCE_CONTRACT_VERSION


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/rotation_source_provenance_sidecar.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "bot",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "src.services.market_cache",
    "src.services.market_rotation_radar_service",
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


def test_readyish_rotation_payload_builds_expected_domains() -> None:
    sidecar = build_rotation_source_provenance_sidecar(
        theme={
            "themeId": "semiconductors",
            "market": "US",
            "source": "rotation_quote_spine",
            "sourceLabel": "Rotation Quote Spine",
            "sourceType": "authorized_licensed_feed",
            "sourceTier": "authorized_licensed_feed",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "observationOnly": False,
            "relativeStrength": {
                "averageRelativeStrengthPercent": 8.4,
                "benchmark": "QQQ",
                "source": "rotation_quote_spine",
            },
            "breadth": {
                "percentUp": 68.0,
                "percentOutperformingBenchmark": 64.0,
                "coveragePercent": 1.0,
            },
            "volume": {"averageRelativeVolume": 1.24},
            "proxyQuality": {
                "hasMissingRequiredProxy": False,
                "hasStaleProxy": False,
                "label": "实时代理完整",
                "freshness": "fresh",
            },
            "trend": [0.1, 0.3, 0.45, 0.6],
            "riskLabels": [],
        },
        readiness={
            "status": "ready",
            "hasSufficientEvidence": True,
            "missingReasonCodes": [],
            "coverageLabels": ["代理强度", "广度确认", "量能确认", "跨时窗延续"],
        },
        evidence_snapshot={
            "source": "rotation_theme_quote_breadth",
            "sourceLabel": "Rotation Theme Quote Breadth",
            "sourceType": "official_public",
            "freshness": "fresh",
            "breadthEvidence": {"observedMembers": 18, "configuredMembers": 20},
            "relativeStrengthEvidence": {"benchmark": "QQQ"},
            "fundFlowEvidence": {
                "source": "rotation_proxy_flow_model",
                "sourceLabel": "Rotation Proxy Flow Model",
                "methodology": "proxy_flow",
                "freshness": "fresh",
            },
        },
        market_context={
            "market": "US",
            "marketUniverse": "US",
            "source": "rotation_market_universe",
            "sourceLabel": "Rotation Market Universe",
            "sourceType": "official_public",
            "freshness": "cached",
        },
    )

    assert sidecar["contractVersion"] == ROTATION_SOURCE_PROVENANCE_VERSION
    assert sidecar["sourceProvenanceContractVersion"] == SOURCE_PROVENANCE_CONTRACT_VERSION
    assert sidecar["entryCount"] == 9
    assert sidecar["scoreContributionAllowedCount"] == 9
    assert sidecar["observationOnlyCount"] == 0
    assert sidecar["evidenceDomainCounts"] == {
        "macro": 2,
        "market_data": 4,
        "research": 2,
        "portfolio": 1,
    }

    by_debug = {entry["debugRef"]: entry for entry in sidecar["entries"]}
    assert set(by_debug) == {
        "source-provenance:rotation:breadth",
        "source-provenance:rotation:freshness",
        "source-provenance:rotation:fundflow",
        "source-provenance:rotation:marketuniverse",
        "source-provenance:rotation:relativestrength",
        "source-provenance:rotation:rotation",
        "source-provenance:rotation:sectortheme",
        "source-provenance:rotation:taxonomy",
        "source-provenance:rotation:trend",
    }
    assert by_debug["source-provenance:rotation:rotation"]["authorityTier"] == "score_grade"
    assert by_debug["source-provenance:rotation:marketuniverse"]["freshnessState"] == "cached"
    assert by_debug["source-provenance:rotation:taxonomy"]["sourceTier"] == "official_public"


def test_taxonomy_only_theme_fails_closed_for_all_domains() -> None:
    sidecar = build_rotation_source_provenance_sidecar(
        theme={
            "themeId": "ai",
            "market": "US",
            "source": "local_taxonomy",
            "sourceLabel": "Local Taxonomy",
            "sourceType": "taxonomy_only",
            "freshness": "fallback",
            "staticThemeOnly": True,
            "taxonomyOnly": True,
            "observationOnly": True,
            "relativeStrength": {"averageRelativeStrengthPercent": None},
            "proxyQuality": {"hasMissingRequiredProxy": True},
        },
        readiness={
            "status": "insufficient",
            "hasSufficientEvidence": False,
            "missingReasonCodes": ["taxonomy_only", "local_market_data_missing", "real_flow_missing"],
        },
    )

    assert sidecar["entryCount"] == 9
    assert sidecar["observationOnlyCount"] == 9
    assert sidecar["scoreContributionAllowedCount"] == 0
    assert all(entry["observationOnly"] is True for entry in sidecar["entries"])
    assert all("taxonomy_only" in entry["limitations"] for entry in sidecar["entries"])
    assert all("authoritative_rotation_runtime_evidence" in entry["nextEvidenceNeeded"] for entry in sidecar["entries"])


def test_cn_observation_only_proxy_theme_stays_fail_closed() -> None:
    sidecar = build_rotation_source_provenance_sidecar(
        theme={
            "themeId": "power_grid",
            "market": "CN",
            "source": "yfinance_proxy_cn_rotation",
            "sourceLabel": "Yahoo Finance CN Rotation",
            "sourceType": "unofficial_proxy",
            "freshness": "delayed",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "observationOnly": True,
            "relativeStrength": {"averageRelativeStrengthPercent": 4.1},
            "breadth": {"percentUp": 55.0, "percentOutperformingBenchmark": 52.0},
            "volume": {"averageRelativeVolume": 1.1},
            "proxyQuality": {"hasMissingRequiredProxy": False, "label": "代理数据"},
            "trend": [0.02, 0.05, 0.07],
        },
        readiness={
            "status": "observe_only",
            "hasSufficientEvidence": True,
            "missingReasonCodes": ["cn_proxy_observation_only"],
        },
    )

    assert sidecar["observationOnlyCount"] == 9
    assert sidecar["scoreContributionAllowedCount"] == 0
    assert sidecar["fallbackOrProxyCount"] == 9
    assert all(entry["sourceTier"] == "proxy" for entry in sidecar["entries"])
    assert all(entry["freshnessState"] == "delayed" for entry in sidecar["entries"])


def test_missing_structured_relative_strength_fails_closed() -> None:
    sidecar = build_rotation_source_provenance_sidecar(
        theme={
            "themeId": "ai",
            "market": "US",
            "source": "rotation_quote_spine",
            "sourceLabel": "Rotation Quote Spine",
            "sourceType": "authorized_licensed_feed",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "observationOnly": False,
            "relativeStrength": {},
            "breadth": {"percentUp": 66.0, "percentOutperformingBenchmark": 61.0},
            "volume": {"averageRelativeVolume": 1.12},
            "proxyQuality": {"hasMissingRequiredProxy": False},
        },
        readiness={
            "status": "insufficient",
            "hasSufficientEvidence": False,
            "missingReasonCodes": ["relative_strength_missing"],
        },
    )

    by_debug = {entry["debugRef"]: entry for entry in sidecar["entries"]}
    rs_entry = by_debug["source-provenance:rotation:relativestrength"]
    rotation_entry = by_debug["source-provenance:rotation:rotation"]

    assert rs_entry["observationOnly"] is True
    assert rs_entry["scoreContributionAllowed"] is False
    assert "relative_strength_missing" in rs_entry["limitations"]
    assert "structured_relative_strength" in rs_entry["nextEvidenceNeeded"]
    assert rotation_entry["observationOnly"] is True
    assert rotation_entry["scoreContributionAllowed"] is False


def test_stale_fallback_and_proxy_markers_downgrade_all_domains() -> None:
    sidecar = build_rotation_source_provenance_sidecar(
        theme={
            "themeId": "software",
            "market": "US",
            "source": "rotation_fallback_snapshot",
            "sourceLabel": "Rotation Fallback Snapshot",
            "sourceType": "fallback_static",
            "freshness": "stale",
            "fallbackUsed": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "relativeStrength": {"averageRelativeStrengthPercent": 3.2},
            "breadth": {"percentUp": 51.0, "percentOutperformingBenchmark": 48.0},
            "volume": {"averageRelativeVolume": 1.03},
            "proxyQuality": {"hasMissingRequiredProxy": False, "hasStaleProxy": True},
        },
        readiness={
            "status": "observe_only",
            "hasSufficientEvidence": True,
            "missingReasonCodes": ["stale_source", "fallback_static"],
        },
    )

    assert sidecar["observationOnlyCount"] == 9
    assert sidecar["scoreContributionAllowedCount"] == 0
    assert all(entry["fallbackOrProxy"] is True for entry in sidecar["entries"])
    assert all("fallback_or_proxy_source" in entry["limitations"] for entry in sidecar["entries"])
    assert any(entry["freshnessState"] == "stale" for entry in sidecar["entries"])


def test_leakage_guardrails_and_json_stable_output() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    sidecar = build_rotation_source_provenance_sidecar(
        theme={
            "themeId": "ai",
            "market": "US",
            "source": "provider_payload_session_cookie",
            "sourceLabel": "Internal raw payload token",
            "sourceType": "fixture_demo",
            "freshness": "demo",
            "observationOnly": True,
            "relativeStrength": {"averageRelativeStrengthPercent": None},
            "proxyQuality": {"hasMissingRequiredProxy": True},
            "trend": ["provider_payload_secret"],
        },
        readiness={
            "status": "blocked",
            "hasSufficientEvidence": False,
            "missingReasonCodes": ["fixture_only", "relative_strength_missing"],
        },
        evidence_snapshot={
            "fundFlowEvidence": {
                "source": "provider_payload_token",
                "sourceLabel": "Internal payload",
                "methodology": "fixture_demo",
                "freshness": "demo",
            }
        },
    )
    encoded = json.dumps(sidecar, ensure_ascii=False, sort_keys=True).lower()
    for blocked in ("token", "cookie", "session", "payload", "internal", "raw", "secret"):
        assert blocked not in encoded
    assert json.loads(json.dumps(sidecar, ensure_ascii=False, sort_keys=True)) == sidecar
    assert summarize_rotation_source_provenance_sidecar(sidecar["entries"])["entryCount"] == sidecar["entryCount"]
