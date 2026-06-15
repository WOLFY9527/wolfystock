# -*- coding: utf-8 -*-
"""Focused contract tests for homepage cockpit capability and manifest metadata."""

from __future__ import annotations

import json

from src.services.homepage_capabilities_service import HomepageCapabilitiesService
from src.services.homepage_module_manifest_service import HomepageModuleManifestService


EXPECTED_COCKPIT_MODULE_KEYS = [
    "dailyMarketBrief",
    "riskRegime",
    "crossAssetIndicators",
    "eventImpactMap",
    "driverChain",
    "themeCapitalFlow",
    "researchPriorities",
    "evidenceQuality",
    "ratesPricing",
    "volatilityPositioning",
    "liquidityCredit",
    "marketBreadth",
    "afterCloseDevelopments",
    "scenarioWatchlist",
    "earningsCatalysts",
    "geopoliticalCommodityRisk",
    "aiCapexInfrastructure",
    "policyRegulationWatch",
    "styleLeadershipRotation",
    "preSessionResearchChecklist",
]

FORBIDDEN_PUBLIC_MARKERS = [
    "provider",
    "url",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "raw",
    "fallback",
    "debug",
    "internal",
    "router",
    "endpoint",
    "launch",
    "navigate",
    "买入",
    "卖出",
    "下单",
    "交易建议",
    "target price",
    "trading signal",
]


def _dump(payload: object) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_capabilities_describe_all_current_cockpit_modules_without_dropping_compatibility_flags() -> None:
    payload = HomepageCapabilitiesService().build_snapshot().model_dump(mode="json")

    assert [section["key"] for section in payload["sections"]] == EXPECTED_COCKPIT_MODULE_KEYS
    assert all(section["supported"] is True for section in payload["sections"])
    assert set(EXPECTED_COCKPIT_MODULE_KEYS).issubset(payload["capabilities"])

    for key in EXPECTED_COCKPIT_MODULE_KEYS:
        assert payload["capabilities"][key] is True

    for legacy_key in [
        "marketPulse",
        "moneyFlowProxy",
        "eventRadar",
        "personalSummary",
        "researchQueue",
        "publicDataQuality",
        "sessionStatus",
        "eventWindows",
        "noAdviceBoundary",
    ]:
        assert payload["capabilities"][legacy_key] is True


def test_manifest_is_deterministic_and_lists_current_cockpit_modules_in_contract_order() -> None:
    service = HomepageModuleManifestService()

    first = service.build_manifest()
    second = service.build_manifest()

    assert first == second
    assert [module["key"] for module in first["modules"]] == EXPECTED_COCKPIT_MODULE_KEYS


def test_manifest_marks_sample_proxy_and_no_evidence_boundaries_without_live_claims() -> None:
    payload = HomepageModuleManifestService().build_manifest(as_of="2026-06-15T00:00:00Z")
    by_key = {module["key"]: module for module in payload["modules"]}

    assert by_key["dailyMarketBrief"]["availability"] == "sample"
    assert by_key["riskRegime"]["availability"] == "proxy"
    assert by_key["eventImpactMap"]["availability"] == "sample"
    assert by_key["researchPriorities"]["availability"] == "no_evidence"
    assert by_key["evidenceQuality"]["availability"] == "sample"
    assert by_key["evidenceQuality"]["reviewPoint"] == "复核证据质量摘要仍聚焦公开展示核查。"

    for module in payload["modules"]:
        assert module["integrationStatus"] == "standalone"
        assert module["publicStatus"] == "public"
        assert module["availability"] in {"sample", "proxy", "no_evidence"}
        assert module["dataQuality"]["state"] in {"partial", "no_evidence"}
        assert "观察" in module["reviewPoint"] or "研究" in module["reviewPoint"] or "复核" in module["reviewPoint"]

    dumped = _dump(payload).lower()
    assert "live" not in dumped
    assert "实时" not in dumped


def test_public_cockpit_metadata_does_not_leak_internal_or_action_markers() -> None:
    outputs = [
        HomepageCapabilitiesService().build_snapshot(),
        HomepageModuleManifestService().build_manifest(as_of="2026-06-15T00:00:00Z"),
    ]

    dumped = "\n".join(_dump(output).lower() for output in outputs)

    leaked = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker.lower() in dumped]
    assert leaked == []


def test_manifest_public_copy_does_not_include_internal_diagnostics_marker() -> None:
    dumped = _dump(HomepageModuleManifestService().build_manifest(as_of="2026-06-15T00:00:00Z"))

    assert "内部诊断" not in dumped
