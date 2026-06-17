# -*- coding: utf-8 -*-
"""Tests for the inert Research Packet v1 helper contract."""

from __future__ import annotations

import ast
import copy
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.packet_redaction_fuzzer import (
    assert_packet_output_redacted,
    redaction_fuzzer_payload,
    redaction_fuzzer_strings,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/research_packet_v1.py"
LANE_NAMES = (
    "priceHistory",
    "technicals",
    "fundamentals",
    "earnings",
    "filings",
    "newsCatalysts",
    "sentiment",
    "valuation",
    "sectorTheme",
    "macroLiquidity",
)
REQUIRED_TOP_LEVEL_FIELDS = {
    "contractVersion",
    "packetIdentity",
    "runtimePosture",
    "lanes",
    "sourceProvenanceSummary",
    "evidenceCitations",
    "dataCoverageRows",
    "redactionPosture",
    "noAdviceBoundary",
    "consumerProjection",
}
REQUIRED_LANE_FIELDS = {
    "status",
    "freshness",
    "coverage",
    "evidenceRefs",
    "dataCoverageRowRef",
    "rightToDisplay",
    "limitations",
    "nextEvidenceNeeded",
    "consumerState",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "apps",
    "data_provider",
    "dotenv",
    "duckdb",
    "environs",
    "fastapi",
    "httpx",
    "psycopg",
    "pydantic_settings",
    "redis",
    "requests",
    "server",
    "sqlalchemy",
    "src.config",
    "src.core",
    "src.repositories",
    "src.services.analysis_service",
    "src.services.market_cache",
    "src.services.market_cache_redis_backend",
    "src.services.report_renderer",
    "src.storage",
    "starlette",
    "urllib",
    "urllib3",
    "websocket",
    "websockets",
)
FORBIDDEN_CONSUMER_TOKENS = (
    "sourceauthorityallowed",
    "scorecontributionallowed",
    "reasoncode",
    "reasonfamilies",
    "provider",
    "sourcetier",
    "sourcetype",
    "official_public",
    "authorized_licensed_feed",
    "public_proxy",
    "unofficial_proxy",
    "fallback_static",
    "synthetic_fixture",
    "polygon",
    "tushare",
    "cache",
    "runtime",
    "api",
    "raw",
    "diagnostic",
    "remediation",
    "trace",
    "directive",
)


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.research_packet_v1")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in RED run
        pytest.fail(f"research_packet_v1 helper missing: {exc}")


def _matches_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(f"{prefix}.")


def _helper_imports() -> set[str]:
    if not HELPER_PATH.exists():
        pytest.fail(f"helper file missing: {HELPER_PATH}")
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _base_sidecars(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": "AAPL",
        "market": "us",
        "generatedAt": "2026-06-08T09:30:00Z",
        "asOf": "2026-06-08",
        "reportLanguage": "zh",
        "researchReadiness": {
            "contractVersion": "research_readiness_v1",
            "researchReady": False,
            "readinessState": "observe_only",
            "missingEvidence": ["earnings"],
            "blockingReasons": ["provider_timeout"],
            "sourceAuthority": "scoreGradeAllowed",
            "freshnessFloor": "fresh",
            "nextEvidenceNeeded": ["补充财报证据"],
        },
        "singleStockEvidencePacket": {
            "contractVersion": "single_stock_evidence_packet_v1",
            "symbol": "AAPL",
            "market": "us",
            "packetState": "degraded",
            "domains": {
                "priceHistory": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "evidenceCount": 2,
                    "topEvidenceRefs": ["price-ref-1", "price-ref-2"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "technicals": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["tech-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "fundamentals": {
                    "status": "degraded",
                    "sourceTier": "authorized_licensed_feed",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "stale",
                    "fallbackOrProxy": True,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["fund-ref-1"],
                    "missingReasons": ["provider_timeout", "fallback_proxy_evidence"],
                    "nextEvidenceNeeded": ["补充基本面证据"],
                },
                "earnings": {
                    "status": "missing",
                    "sourceTier": "unknown",
                    "providerAuthority": "unavailable",
                    "freshness": "unknown",
                    "fallbackOrProxy": False,
                    "evidenceCount": 0,
                    "topEvidenceRefs": [],
                    "missingReasons": ["missing_required_evidence"],
                    "nextEvidenceNeeded": ["补充财报证据"],
                },
                "filings": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["filing-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "news": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["news-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "catalysts": {
                    "status": "available",
                    "sourceTier": "public_proxy",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["catalyst-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "sentiment": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["sentiment-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "valuation": {
                    "status": "available",
                    "sourceTier": "authorized_licensed_feed",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["valuation-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "sectorTheme": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["theme-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "macroLiquidity": {
                    "status": "degraded",
                    "sourceTier": "fallback_static",
                    "providerAuthority": "observationOnly",
                    "freshness": "fallback",
                    "fallbackOrProxy": True,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["macro-ref-1"],
                    "missingReasons": ["fallback_proxy_evidence"],
                    "nextEvidenceNeeded": ["补充宏观流动性证据"],
                },
            },
        },
        "evidenceCoverageFrame": {
            "priceHistory": {"status": "available"},
            "fundamentals": {"status": "degraded", "missingReasons": ["stale_evidence"]},
            "earnings": {"status": "missing"},
        },
        "evidenceCitationFrame": {
            "contractVersion": "home_report_evidence_citation_frame_v1",
            "frameState": "observe_only",
            "citedEvidence": [
                {
                    "id": "news-1",
                    "domain": "news",
                    "label": "Revenue update",
                    "summary": "Recent revenue context is available for observation.",
                    "sourceId": "Polygon",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "asOf": "2026-06-08",
                    "limitation": "reasonCode=provider_timeout",
                },
                {
                    "id": "cat-1",
                    "domain": "catalysts",
                    "label": "Product event",
                    "summary": "Upcoming product event is tracked as context.",
                    "sourceId": "Tushare",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "asOf": "2026-06-08",
                },
            ],
            "domainCoverage": [
                {"domain": "news", "status": "available", "evidenceRefIds": ["news-1"]},
                {"domain": "catalysts", "status": "available", "evidenceRefIds": ["cat-1"]},
            ],
        },
        "sourceProvenanceFrame": [
            {
                "contractVersion": "source_provenance_v1",
                "sourceId": "polygon-live",
                "sourceLabel": "Polygon",
                "evidenceDomain": "priceHistory",
                "authorityTier": "score_grade",
                "freshnessState": "live",
                "sourceTier": "official_public",
                "fallbackOrProxy": False,
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "sourceAuthorityAllowed": True,
                "limitations": [],
                "nextEvidenceNeeded": [],
                "debugRef": "trace:price",
            },
            {
                "contractVersion": "source_provenance_v1",
                "sourceId": "fundamentals-fallback",
                "sourceLabel": "Tushare",
                "evidenceDomain": "fundamentals",
                "authorityTier": "score_grade",
                "freshnessState": "fallback",
                "sourceTier": "authorized_licensed_feed",
                "fallbackOrProxy": True,
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "sourceAuthorityAllowed": True,
                "limitations": ["provider_timeout", "cache_key=abc"],
                "nextEvidenceNeeded": ["maintainer remediation: rotate provider"],
                "debugRef": "trace:fund",
            },
        ],
        "dataCoverageRows": [
            {
                "surfaceId": "single_stock",
                "fieldKey": "price_context",
                "evidenceFamily": "priceHistory",
                "freshnessState": "fresh",
                "rightToDisplay": "granted",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "observationOnly": False,
                "providerId": "polygon",
                "sourceType": "official_public",
            },
            {
                "surfaceId": "single_stock",
                "fieldKey": "fundamental_context",
                "evidenceFamily": "fundamentals",
                "freshnessState": "fresh",
                "rightToDisplay": "granted",
                "isStale": True,
                "isPartial": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "observationOnly": False,
                "providerId": "tushare",
                "sourceType": "authorized_licensed_feed",
            },
            {
                "surfaceId": "single_stock",
                "fieldKey": "news_context",
                "evidenceFamily": "newsCatalysts",
                "freshnessState": "fresh",
                "rightToDisplay": "granted",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "observationOnly": False,
                "providerId": "polygon",
                "sourceType": "official_public",
            },
        ],
    }
    payload.update(overrides)
    return payload


def _consumer_visible_packet_payload(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "consumerProjection": packet["consumerProjection"],
        "evidenceCitations": packet["evidenceCitations"],
        "lanes": packet["lanes"],
        "dataCoverageRows": packet["dataCoverageRows"],
    }


def test_helper_does_not_import_protected_runtime_domains() -> None:
    imported_modules = _helper_imports()
    static_violations = {
        module_name
        for module_name in imported_modules
        if any(_matches_prefix(module_name, prefix) for prefix in FORBIDDEN_IMPORT_PREFIXES)
    }
    assert not static_violations

    before = set(sys.modules)
    _load_helper_module()
    loaded_during_import = set(sys.modules) - before
    dynamic_violations = {
        module_name
        for module_name in loaded_during_import
        if any(_matches_prefix(module_name, prefix) for prefix in FORBIDDEN_IMPORT_PREFIXES)
    }
    assert not dynamic_violations


def test_missing_sidecars_fail_closed_with_required_contract_shape() -> None:
    helper = _load_helper_module()

    packet = helper.build_research_packet_v1(
        {
            "symbol": "AAPL",
            "market": "us",
            "generatedAt": "2026-06-08T09:30:00Z",
            "asOf": "2026-06-08",
            "reportLanguage": "zh",
        }
    )

    assert packet["contractVersion"] == "research_packet_v1"
    assert REQUIRED_TOP_LEVEL_FIELDS <= set(packet)
    assert packet["packetIdentity"] == {
        "symbol": "AAPL",
        "market": "us",
        "generatedAt": "2026-06-08T09:30:00Z",
        "asOf": "2026-06-08",
        "reportLanguage": "zh",
    }
    assert packet["runtimePosture"] == {
        "diagnosticOnly": True,
        "observationOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
        "authorityGrant": False,
    }
    assert tuple(packet["lanes"]) == LANE_NAMES
    for lane in packet["lanes"].values():
        assert REQUIRED_LANE_FIELDS <= set(lane)
        assert lane["status"] == "unavailable"
        assert lane["freshness"] == "unknown"
        assert lane["coverage"] == "missing"
        assert lane["evidenceRefs"] == []
        assert lane["dataCoverageRowRef"] is None
        assert lane["rightToDisplay"] == "unavailable"
        assert lane["consumerState"] == "UNAVAILABLE"

    assert packet["evidenceCitations"] == []
    assert packet["consumerProjection"]["status"] == "UNAVAILABLE"


def test_degraded_lane_evidence_stays_observation_only_and_not_fully_displayable() -> None:
    helper = _load_helper_module()

    packet = helper.build_research_packet_v1(_base_sidecars())
    fundamentals = packet["lanes"]["fundamentals"]

    assert packet["runtimePosture"]["observationOnly"] is True
    assert packet["runtimePosture"]["authorityGrant"] is False
    assert fundamentals["status"] in {"delayed", "partial", "insufficient"}
    assert fundamentals["freshness"] == "fallback"
    assert fundamentals["coverage"] == "partial"
    assert fundamentals["rightToDisplay"] != "granted"
    assert fundamentals["consumerState"] in {"DELAYED", "PARTIAL", "INSUFFICIENT"}
    assert "当前信号置信度较低，仅供观察。" in fundamentals["limitations"]


def test_display_right_and_authority_are_never_inferred_from_source_or_freshness() -> None:
    helper = _load_helper_module()
    sidecars = _base_sidecars(dataCoverageRows=[])

    packet = helper.build_research_packet_v1(sidecars)
    price_history = packet["lanes"]["priceHistory"]

    assert price_history["freshness"] == "fresh"
    assert price_history["evidenceRefs"]
    assert price_history["rightToDisplay"] == "unavailable"
    assert price_history["status"] == "insufficient"
    assert price_history["consumerState"] == "INSUFFICIENT"
    assert packet["runtimePosture"]["authorityGrant"] is False
    assert packet["sourceProvenanceSummary"]["authorityGrant"] is False


def test_consumer_projection_redacts_raw_internal_and_advice_vocabulary() -> None:
    helper = _load_helper_module()

    packet = helper.build_research_packet_v1(_base_sidecars())
    serialized_consumer = json.dumps(packet["consumerProjection"], ensure_ascii=False).lower()

    for token in FORBIDDEN_CONSUMER_TOKENS:
        assert token not in serialized_consumer
    assert re.search(r"\b[a-z]+_[a-z_]+\b", serialized_consumer) is None

    for citation in packet["evidenceCitations"]:
        assert "sourceId" not in citation
        assert "providerAuthority" not in citation
        assert "sourceTier" not in citation

    serialized_rows = json.dumps(packet["dataCoverageRows"], ensure_ascii=False).lower()
    assert "providerid" not in serialized_rows
    assert "sourcetype" not in serialized_rows
    assert "sourceauthorityallowed" not in serialized_rows
    assert "scorecontributionallowed" not in serialized_rows


def test_consumer_visible_projection_redacts_shared_fuzzer_payloads() -> None:
    helper = _load_helper_module()
    sidecars = _base_sidecars()
    fuzzer_payload = redaction_fuzzer_payload()
    fuzzer_strings = redaction_fuzzer_strings()

    sidecars["researchReadiness"]["blockingReasons"] = [
        "provider_timeout",
        "cache_refresh_pending",
        "debug_trace_unavailable",
    ]
    sidecars["researchReadiness"]["nextEvidenceNeeded"] = fuzzer_strings[:3]
    sidecars["singleStockEvidencePacket"]["domains"]["news"]["missingReasons"] = [
        "provider_timeout",
        "raw_schema_trace",
    ]
    sidecars["singleStockEvidencePacket"]["domains"]["news"]["nextEvidenceNeeded"] = fuzzer_strings[3:6]
    sidecars["evidenceCitationFrame"]["citedEvidence"].append(
        {
            "id": "fuzzer-citation",
            "domain": "news",
            "label": "provider cache debug trace",
            "summary": fuzzer_payload["rawJsonDump"],
            "sourceId": "DebugProvider",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "asOf": "2026-06-08",
        }
    )
    sidecars["sourceProvenanceFrame"].append(
        {
            "contractVersion": "source_provenance_v1",
            "sourceId": "raw-provider-trace",
            "sourceLabel": "RawProvider",
            "evidenceDomain": "news",
            "sourceTier": "public_proxy",
            "fallbackOrProxy": True,
            "limitations": fuzzer_strings,
            "nextEvidenceNeeded": fuzzer_strings,
            "debugRef": "trace:raw:requestId=REQ-123",
        }
    )
    sidecars["dataCoverageRows"].append(
        {
            "surfaceId": "single_stock",
            "fieldKey": "news_context",
            "evidenceFamily": "news",
            "freshnessState": "fresh",
            "rightToDisplay": "granted",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "providerId": "debug-provider",
            "sourceType": "public_proxy",
            "rawPayload": fuzzer_payload,
        }
    )

    packet = helper.build_research_packet_v1(sidecars)

    assert_packet_output_redacted(
        _consumer_visible_packet_payload(packet),
        surface="research_packet_v1.consumer_visible",
    )


def test_output_is_deterministic_json_safe_and_does_not_mutate_inputs() -> None:
    helper = _load_helper_module()
    sidecars = _base_sidecars()
    original = copy.deepcopy(sidecars)

    first = helper.build_research_packet_v1(sidecars)
    second = helper.build_research_packet_v1(copy.deepcopy(sidecars))

    assert sidecars == original
    assert first == second
    json.dumps(first, ensure_ascii=False, sort_keys=True)
