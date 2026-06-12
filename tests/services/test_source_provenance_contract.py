# -*- coding: utf-8 -*-
"""Tests for the helper-only source provenance contract skeleton."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.source_provenance_contract import (
    SOURCE_PROVENANCE_CONTRACT_VERSION,
    build_fallback_proxy_source_provenance,
    build_fixture_demo_source_provenance,
    build_observation_only_source_provenance,
    build_score_grade_source_provenance,
    build_source_provenance_sidecar,
    build_source_provenance,
    build_stale_source_provenance,
    build_unknown_source_provenance,
    summarize_source_provenance,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/source_provenance_contract.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
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


def test_helper_is_pure_inert_and_json_stable() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    entries = [
        build_score_grade_source_provenance(
            source_id="polygon_us_grouped_daily",
            source_label="Polygon grouped daily US equities",
            evidence_domain="quote",
            debug_ref="provider:polygon:quote",
        ),
        build_fallback_proxy_source_provenance(
            source_id="yfinance_proxy",
            source_label="Yahoo Finance",
            evidence_domain="macro",
            debug_ref="provider:yfinance:macro",
        ),
    ]
    summary = summarize_source_provenance(entries)

    assert json.loads(json.dumps(summary, ensure_ascii=False, sort_keys=True)) == summary


def test_unknown_source_fails_closed() -> None:
    entry = build_source_provenance(
        source_id="TRADIER_API_TOKEN",
        source_label="raw provider payload token",
        evidence_domain="unknown_domain",
        authority_tier="authorized",
        freshness_state="live",
        source_tier="authorized_licensed_feed",
        fallback_or_proxy=False,
        observation_only=False,
        score_contribution_allowed=True,
        debug_ref="env:tradier_api_token:router",
    )

    assert entry == {
        "contractVersion": SOURCE_PROVENANCE_CONTRACT_VERSION,
        "sourceId": "unknown_source",
        "sourceLabel": "未知来源",
        "evidenceDomain": "general",
        "authorityTier": "unknown",
        "freshnessState": "unknown",
        "sourceTier": "unknown",
        "fallbackOrProxy": True,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "limitations": ["unknown_source"],
        "nextEvidenceNeeded": ["verified_source_metadata"],
        "debugRef": "source-provenance:unknown",
    }


def test_stale_and_fallback_proxy_builders_downgrade_to_safe_observation_only_states() -> None:
    stale = build_stale_source_provenance(
        source_id="fred_existing_baseline",
        source_label="FRED",
        evidence_domain="macro",
        debug_ref="fred:macro",
    )
    proxy = build_fallback_proxy_source_provenance(
        source_id="yfinance_proxy",
        source_label="Yahoo Finance",
        evidence_domain="quote",
        freshness_state="delayed",
        debug_ref="yfinance:quote",
    )

    assert stale["freshnessState"] == "stale"
    assert stale["observationOnly"] is True
    assert stale["scoreContributionAllowed"] is False
    assert "stale_source" in stale["limitations"]

    assert proxy["sourceTier"] == "proxy"
    assert proxy["fallbackOrProxy"] is True
    assert proxy["observationOnly"] is True
    assert proxy["scoreContributionAllowed"] is False
    assert "fallback_or_proxy_source" in proxy["limitations"]


def test_score_grade_and_observation_only_paths_stay_distinct() -> None:
    score_grade = build_score_grade_source_provenance(
        source_id="polygon_us_grouped_daily",
        source_label="Polygon grouped daily US equities",
        evidence_domain="quote",
        debug_ref="polygon:quote",
    )
    observation = build_observation_only_source_provenance(
        source_id="local_db",
        source_label="本地数据库历史",
        evidence_domain="research",
        debug_ref="local-db:research",
    )

    assert score_grade["authorityTier"] == "score_grade"
    assert score_grade["freshnessState"] == "fresh"
    assert score_grade["observationOnly"] is False
    assert score_grade["scoreContributionAllowed"] is True
    assert score_grade["limitations"] == ["unknown_source"] or score_grade["limitations"] == []

    assert observation["authorityTier"] == "observation_only"
    assert observation["observationOnly"] is True
    assert observation["scoreContributionAllowed"] is False
    assert "observation_only" in observation["limitations"]


def test_fixture_demo_builder_is_synthetic_and_fail_closed() -> None:
    entry = build_fixture_demo_source_provenance(debug_ref="fixture:demo")

    assert entry["authorityTier"] == "fixture"
    assert entry["freshnessState"] == "synthetic"
    assert entry["sourceTier"] == "fixture"
    assert entry["fallbackOrProxy"] is True
    assert entry["observationOnly"] is True
    assert entry["scoreContributionAllowed"] is False
    assert "synthetic_source" in entry["limitations"]


def test_summary_aggregates_by_authority_freshness_and_domain_with_stable_entry_order() -> None:
    summary = summarize_source_provenance(
        [
            build_fallback_proxy_source_provenance(
                source_id="yfinance_proxy",
                source_label="Yahoo Finance",
                evidence_domain="macro",
                debug_ref="z-debug",
            ),
            build_score_grade_source_provenance(
                source_id="polygon_us_grouped_daily",
                source_label="Polygon grouped daily US equities",
                evidence_domain="quote",
                debug_ref="a-debug",
            ),
            build_unknown_source_provenance(evidence_domain="portfolio", debug_ref="x-debug"),
        ]
    )

    assert summary["contractVersion"] == SOURCE_PROVENANCE_CONTRACT_VERSION
    assert summary["entryCount"] == 3
    assert summary["authorityTierCounts"] == {
        "observation_only": 1,
        "score_grade": 1,
        "unknown": 1,
    }
    assert summary["freshnessStateCounts"] == {
        "fallback": 1,
        "fresh": 1,
        "unknown": 1,
    }
    assert summary["evidenceDomainCounts"] == {
        "macro": 1,
        "market_data": 1,
        "portfolio": 1,
    }
    assert summary["fallbackOrProxyCount"] == 2
    assert summary["observationOnlyCount"] == 2
    assert summary["scoreContributionAllowedCount"] == 1
    assert [entry["debugRef"] for entry in summary["entries"]] == [
        "source-provenance:a",
        "source-provenance:unknown",
        "source-provenance:z",
    ]


def test_sidecar_builder_wraps_summary_without_changing_payload_shape() -> None:
    entries = [
        build_fallback_proxy_source_provenance(
            source_id="yfinance_proxy",
            source_label="Yahoo Finance",
            evidence_domain="macro",
            debug_ref="z-debug",
        ),
        build_score_grade_source_provenance(
            source_id="polygon_us_grouped_daily",
            source_label="Polygon grouped daily US equities",
            evidence_domain="quote",
            debug_ref="a-debug",
        ),
    ]
    summary = summarize_source_provenance(entries)

    sidecar = build_source_provenance_sidecar(
        contract_version="sample_source_provenance_sidecar_v1",
        entries=entries,
    )

    assert sidecar == {
        "contractVersion": "sample_source_provenance_sidecar_v1",
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
    assert json.loads(json.dumps(sidecar, ensure_ascii=False, sort_keys=True)) == sidecar


def test_leakage_guardrails_sanitize_sensitive_strings_from_consumer_fields() -> None:
    entry = build_source_provenance(
        source_id="provider_payload_session_cookie",
        source_label="Internal debug stack trace with token",
        evidence_domain="portfolio",
        authority_tier="official_public",
        freshness_state="cached",
        source_tier="cache_snapshot",
        fallback_or_proxy=False,
        observation_only=False,
        score_contribution_allowed=True,
        limitations=["provider_timeout", "session_cookie_exposed", "cache_raw_payload"],
        next_evidence_needed=["fresh provider payload", "authorized_source"],
        debug_ref="cache:raw:session:token",
    )
    consumer_values = json.dumps(
        {
            "sourceId": entry["sourceId"],
            "sourceLabel": entry["sourceLabel"],
            "limitations": entry["limitations"],
            "nextEvidenceNeeded": entry["nextEvidenceNeeded"],
            "debugRef": entry["debugRef"],
        },
        ensure_ascii=False,
    ).lower()

    for blocked in ("token", "cookie", "session", "payload", "internal", "stack", "raw"):
        assert blocked not in consumer_values
    assert entry["sourceId"] == "unknown_source"
    assert entry["sourceLabel"] == "未知来源"
    assert entry["debugRef"] == "source-provenance:unknown"
    assert entry["limitations"] == ["unknown_source"]
    assert entry["nextEvidenceNeeded"] == ["verified_source_metadata"]
