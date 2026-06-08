# -*- coding: utf-8 -*-
"""Fixture catalog tests for Research Packet v1 output states."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from typing import Any

import pytest

from src.services.research_packet_v1 import build_research_packet_v1


LANES = (
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
SOURCE_DOMAIN_BY_LANE = {
    "priceHistory": "priceHistory",
    "technicals": "technicals",
    "fundamentals": "fundamentals",
    "earnings": "earnings",
    "filings": "filings",
    "newsCatalysts": "news",
    "sentiment": "sentiment",
    "valuation": "valuation",
    "sectorTheme": "sectorTheme",
    "macroLiquidity": "macroLiquidity",
}
BOUNDED_PRODUCT_STATES = {
    "AVAILABLE",
    "UPDATING",
    "DELAYED",
    "PARTIAL",
    "INSUFFICIENT",
    "PAUSED",
    "UNAVAILABLE",
}
FORBIDDEN_CONSUMER_PATTERNS = (
    r"\bprovider\b",
    r"\bsource\b",
    r"\bcache\b",
    r"\bdebug\b",
    r"\breason\s*code\b",
    r"\breasoncode\b",
    r"\bbackend\b",
    r"\binternal\b",
    r"\badvice\b",
    r"\bapi\b",
    r"\braw\b",
    r"\bruntime\b",
    r"\btrace\b",
    r"\bdiagnostic\b",
    r"\bpolygon\b",
    r"\btushare\b",
    r"\bofficial_public\b",
    r"\bauthorized_licensed_feed\b",
    r"\bpublic_proxy\b",
    r"\bunofficial_proxy\b",
    r"\bfallback_static\b",
    r"\bsynthetic_fixture\b",
    r"\bsourceauthorityallowed\b",
    r"\bscorecontributionallowed\b",
    r"\bsourcetype\b",
    r"\bsourcetier\b",
)
FORBIDDEN_ACTION_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bstop(?:[-\s]?loss)?\b",
    r"\btarget\b",
    r"\bposition[-\s]?sizing\b",
    r"\bexecution[-\s]?readiness\b",
    "买入",
    "卖出",
    "止损",
    "止盈",
    "目标价",
    "仓位",
    "下单",
    "立即交易",
)
SNAKE_CASE_PATTERN = re.compile(r"\b[a-z]+_[a-z0-9_]+\b")


def _identity() -> dict[str, Any]:
    return {
        "symbol": "AAPL",
        "market": "us",
        "generatedAt": "2026-06-08T09:30:00Z",
        "asOf": "2026-06-08",
        "reportLanguage": "zh",
    }


def _available_domain(lane: str) -> dict[str, Any]:
    return {
        "status": "available",
        "sourceTier": "official_public",
        "providerAuthority": "observationOnly",
        "freshness": "fresh",
        "fallbackOrProxy": False,
        "evidenceCount": 1,
        "topEvidenceRefs": [f"{lane}-ref-1"],
        "missingReasons": [],
        "nextEvidenceNeeded": [],
    }


def _display_row(lane: str, **overrides: Any) -> dict[str, Any]:
    row = {
        "surfaceId": "single_stock",
        "lane": lane,
        "fieldKey": f"{lane}-field",
        "evidenceFamily": lane,
        "freshnessState": "fresh",
        "rightToDisplay": "granted",
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "authorityGrant": True,
        "decisionGrade": True,
        "observationOnly": False,
        "providerId": "polygon",
        "sourceType": "official_public",
    }
    row.update(overrides)
    return row


def _citation(lane: str) -> dict[str, Any]:
    return {
        "id": f"{lane}-citation-1",
        "domain": SOURCE_DOMAIN_BY_LANE[lane],
        "label": f"{lane} research context",
        "summary": f"{lane} context is available for observation.",
        "sourceId": "Polygon",
        "providerAuthority": "scoreGradeAllowed",
        "freshness": "fresh",
        "asOf": "2026-06-08",
        "limitation": "reasonCode=provider_timeout",
    }


def _complete_observation_only_sidecars() -> dict[str, Any]:
    domains = {
        SOURCE_DOMAIN_BY_LANE[lane]: _available_domain(lane)
        for lane in LANES
    }
    payload = {
        **_identity(),
        "researchReadiness": {
            "contractVersion": "research_readiness_v1",
            "researchReady": False,
            "readinessState": "observe_only",
            "missingEvidence": [],
            "blockingReasons": [],
            "sourceAuthority": "observationOnly",
            "freshnessFloor": "fresh",
            "nextEvidenceNeeded": [],
        },
        "singleStockEvidencePacket": {
            "contractVersion": "single_stock_evidence_packet_v1",
            "symbol": "AAPL",
            "market": "us",
            "packetState": "available",
            "domains": domains,
        },
        "evidenceCoverageFrame": {
            lane: {"status": "available", "evidenceRefIds": [f"{lane}-coverage-1"]}
            for lane in LANES
        },
        "evidenceCitationFrame": {
            "contractVersion": "home_report_evidence_citation_frame_v1",
            "frameState": "observe_only",
            "citedEvidence": [_citation(lane) for lane in LANES],
            "domainCoverage": [
                {
                    "domain": SOURCE_DOMAIN_BY_LANE[lane],
                    "status": "available",
                    "evidenceRefIds": [f"{lane}-citation-1"],
                }
                for lane in LANES
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
                "observationOnly": True,
                "scoreContributionAllowed": True,
                "sourceAuthorityAllowed": True,
                "limitations": [],
                "nextEvidenceNeeded": [],
                "debugRef": "trace:price",
            }
        ],
        "dataCoverageRows": [_display_row(lane) for lane in LANES],
    }
    return payload


def _missing_sidecars() -> dict[str, Any]:
    return _identity()


def _degraded_lane_sidecars() -> dict[str, Any]:
    payload = _complete_observation_only_sidecars()
    payload["singleStockEvidencePacket"]["domains"]["fundamentals"].update(
        {
            "status": "degraded",
            "freshness": "fallback",
            "fallbackOrProxy": True,
            "missingReasons": ["provider_timeout", "fallback_proxy_evidence"],
            "nextEvidenceNeeded": ["补充基本面证据"],
        }
    )
    for row in payload["dataCoverageRows"]:
        if row["lane"] == "fundamentals":
            row.update({"isStale": True, "isPartial": True})
    return payload


def _unavailable_citation_sidecars() -> dict[str, Any]:
    payload = _complete_observation_only_sidecars()
    payload["dataCoverageRows"] = []
    payload["evidenceCitationFrame"]["citedEvidence"] = [
        {
            "id": "news-private-citation",
            "domain": "news",
            "label": "Provider cache debug item",
            "summary": "reasonCode=provider_timeout raw backend trace",
            "sourceId": "Polygon",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "asOf": "2026-06-08",
        }
    ]
    payload["evidenceCitationFrame"]["domainCoverage"] = [
        {"domain": "news", "status": "available", "evidenceRefIds": ["news-private-citation"]}
    ]
    return payload


def _redacted_provenance_sidecars() -> dict[str, Any]:
    payload = _complete_observation_only_sidecars()
    payload["sourceProvenanceFrame"] = [
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
            "providerTrace": "provider trace id 123",
            "cacheKey": "cache-key-123",
            "debugRef": "trace:price",
            "limitations": [],
            "nextEvidenceNeeded": ["maintainer remediation: rotate provider"],
        },
        {
            "contractVersion": "source_provenance_v1",
            "sourceId": "tushare-fallback",
            "sourceLabel": "Tushare",
            "evidenceDomain": "macroLiquidity",
            "authorityTier": "observation",
            "freshnessState": "fallback",
            "sourceTier": "fallback_static",
            "fallbackOrProxy": True,
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "sourceAuthorityAllowed": False,
            "providerTrace": "provider trace id 456",
            "cacheKey": "cache-key-456",
            "debugRef": "trace:macro",
            "limitations": ["cache_key=abc", "reasonCode=provider_timeout"],
            "nextEvidenceNeeded": ["internal backend remediation"],
        },
    ]
    return payload


def _data_coverage_fail_closed_sidecars() -> dict[str, Any]:
    payload = _complete_observation_only_sidecars()
    payload["dataCoverageRows"] = [
        _display_row("priceHistory", isStale=True),
        _display_row("fundamentals", isPartial=True),
        _display_row("sentiment", freshnessState="synthetic", isSynthetic=True),
        _display_row("macroLiquidity", freshnessState="unavailable", isUnavailable=True),
    ]
    return payload


FIXTURE_CATALOG: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
    ("complete_observation_only", _complete_observation_only_sidecars),
    ("missing_sidecars", _missing_sidecars),
    ("degraded_lane_evidence", _degraded_lane_sidecars),
    ("unavailable_citations", _unavailable_citation_sidecars),
    ("redacted_provenance", _redacted_provenance_sidecars),
    ("data_coverage_fail_closed", _data_coverage_fail_closed_sidecars),
)


def _consumer_visible_payload(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "consumerProjection": packet["consumerProjection"],
        "evidenceCitations": packet["evidenceCitations"],
        "lanes": packet["lanes"],
        "dataCoverageRows": packet["dataCoverageRows"],
    }


def _serialized_consumer_visible_payload(packet: dict[str, Any]) -> str:
    return json.dumps(_consumer_visible_payload(packet), ensure_ascii=False, sort_keys=True)


def _assert_runtime_fail_closed(packet: dict[str, Any]) -> None:
    assert packet["runtimePosture"] == {
        "diagnosticOnly": True,
        "observationOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
        "authorityGrant": False,
    }
    assert packet["noAdviceBoundary"]["personalizedAdviceAllowed"] is False
    assert packet["noAdviceBoundary"]["actionableInstructionAllowed"] is False


def _assert_consumer_projection_states_are_bounded(packet: dict[str, Any]) -> None:
    projection = packet["consumerProjection"]
    states = {projection["status"], *(lane["state"] for lane in projection["lanes"])}
    assert states <= BOUNDED_PRODUCT_STATES
    assert len(projection["lanes"]) == len(LANES)
    assert {lane["lane"] for lane in projection["lanes"]} == set(LANES)


def _assert_no_consumer_leakage(packet: dict[str, Any]) -> None:
    serialized = _serialized_consumer_visible_payload(packet).lower()
    for pattern in (*FORBIDDEN_CONSUMER_PATTERNS, *FORBIDDEN_ACTION_PATTERNS):
        assert re.search(pattern, serialized) is None
    assert SNAKE_CASE_PATTERN.search(serialized) is None


@pytest.mark.parametrize(("fixture_name", "factory"), FIXTURE_CATALOG)
def test_research_packet_fixture_catalog_is_deterministic_json_safe_and_bounded(
    fixture_name: str,
    factory: Callable[[], dict[str, Any]],
) -> None:
    sidecars = factory()
    original = copy.deepcopy(sidecars)

    first = build_research_packet_v1(sidecars)
    second = build_research_packet_v1(copy.deepcopy(sidecars))

    assert sidecars == original, fixture_name
    assert first == second, fixture_name
    assert json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True)) == first
    _assert_runtime_fail_closed(first)
    _assert_consumer_projection_states_are_bounded(first)
    _assert_no_consumer_leakage(first)


def test_complete_but_observation_only_packet_is_available_without_authority_grant() -> None:
    packet = build_research_packet_v1(_complete_observation_only_sidecars())

    assert packet["consumerProjection"]["status"] == "AVAILABLE"
    assert packet["sourceProvenanceSummary"] == {
        "entriesObserved": 1,
        "observationOnly": True,
        "authorityGrant": False,
        "displayableLaneCount": len(LANES),
        "limitedLaneCount": 0,
        "unknownLaneCount": 0,
    }
    assert len(packet["evidenceCitations"]) == len(LANES)
    for lane_name, lane in packet["lanes"].items():
        assert lane_name in LANES
        assert lane["status"] == "available"
        assert lane["consumerState"] == "AVAILABLE"
        assert lane["rightToDisplay"] == "granted"


def test_missing_sidecars_fixture_fails_closed_to_unavailable() -> None:
    packet = build_research_packet_v1(_missing_sidecars())

    assert packet["consumerProjection"]["status"] == "UNAVAILABLE"
    assert packet["evidenceCitations"] == []
    assert packet["dataCoverageRows"] == []
    assert packet["sourceProvenanceSummary"]["authorityGrant"] is False
    for lane in packet["lanes"].values():
        assert lane["status"] == "unavailable"
        assert lane["freshness"] == "unknown"
        assert lane["coverage"] == "missing"
        assert lane["rightToDisplay"] == "unavailable"
        assert lane["consumerState"] == "UNAVAILABLE"


def test_degraded_lane_evidence_is_limited_observation_only() -> None:
    packet = build_research_packet_v1(_degraded_lane_sidecars())
    fundamentals = packet["lanes"]["fundamentals"]

    assert fundamentals["freshness"] == "fallback"
    assert fundamentals["coverage"] == "partial"
    assert fundamentals["rightToDisplay"] == "limited"
    assert fundamentals["consumerState"] == "PARTIAL"
    assert packet["consumerProjection"]["status"] == "PARTIAL"
    assert packet["runtimePosture"]["authorityGrant"] is False


def test_unavailable_citations_are_not_projected_to_consumer_citations() -> None:
    packet = build_research_packet_v1(_unavailable_citation_sidecars())

    assert packet["evidenceCitations"] == []
    assert packet["lanes"]["newsCatalysts"]["rightToDisplay"] == "unavailable"
    assert packet["lanes"]["newsCatalysts"]["consumerState"] == "INSUFFICIENT"
    assert packet["consumerProjection"]["status"] == "INSUFFICIENT"


def test_source_provenance_is_redacted_to_counts_and_fail_closed_flags() -> None:
    packet = build_research_packet_v1(_redacted_provenance_sidecars())

    assert packet["sourceProvenanceSummary"] == {
        "entriesObserved": 2,
        "observationOnly": True,
        "authorityGrant": False,
        "displayableLaneCount": len(LANES),
        "limitedLaneCount": 1,
        "unknownLaneCount": 0,
    }
    assert packet["redactionPosture"] == {
        "providerIdentifiersRedacted": True,
        "sourceDescriptorsRedacted": True,
        "rawDiagnosticsRedacted": True,
        "backendReasonCodesRedacted": True,
        "maintainerInstructionsRedacted": True,
        "consumerProjectionBounded": True,
    }


def test_data_coverage_rows_fail_closed_when_authority_fields_claim_grants() -> None:
    packet = build_research_packet_v1(_data_coverage_fail_closed_sidecars())
    rows_by_lane = {row["lane"]: row for row in packet["dataCoverageRows"]}

    assert set(rows_by_lane) == {"priceHistory", "fundamentals", "sentiment", "macroLiquidity"}
    for row in rows_by_lane.values():
        assert row["observationOnly"] is True
        assert row["rightToDisplay"] in {"limited", "unavailable"}
        assert row["consumerState"] in {"PARTIAL", "INSUFFICIENT"}
        assert "providerId" not in row
        assert "sourceType" not in row
        assert "sourceAuthorityAllowed" not in row
        assert "scoreContributionAllowed" not in row
        assert "authorityGrant" not in row
        assert "decisionGrade" not in row

    assert packet["lanes"]["priceHistory"]["rightToDisplay"] == "limited"
    assert packet["lanes"]["sentiment"]["freshness"] == "synthetic"
    assert packet["lanes"]["macroLiquidity"]["rightToDisplay"] == "limited"
    assert packet["consumerProjection"]["status"] == "INSUFFICIENT"
