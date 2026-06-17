# -*- coding: utf-8 -*-
"""Scanner packet integration coverage for the research narrative composer."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.research_narrative_composer import RESEARCH_NARRATIVE_SECTION_TITLES
from src.services.research_narrative_scanner_adapter import (
    compose_scanner_candidate_research_narrative,
    scanner_candidate_packet_to_research_narrative_input,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "src" / "services" / "research_narrative_scanner_adapter.py"
SCANNER_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_adapters" / "scanner_candidate_packet.json"
FORBIDDEN_OUTPUT_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "position sizing",
    "provider",
    "cache",
    "runtime",
    "debug",
    "raw",
    "payload",
    "schema",
    "trace",
    "token",
    "authorization",
    "sourceauthorityallowed",
    "scorecontributionallowed",
    "reasoncode",
    "adminreasoncodes",
    "provider_unavailable",
    "history_insufficient",
    "fallback_source",
)


def _scanner_fixture() -> dict:
    return json.loads(SCANNER_FIXTURE_PATH.read_text(encoding="utf-8"))


def _section_map(payload: dict) -> dict[str, list[str]]:
    return {section["title"]: section["body"] for section in payload["sections"]}


def _rendered_text(payload: dict) -> str:
    return " ".join(
        str(item)
        for section in payload["sections"]
        for item in [section["title"], *section["body"]]
    ).lower()


def test_scanner_candidate_packet_fixture_composes_observation_only_narrative() -> None:
    source_packet = _scanner_fixture()

    composer_input = scanner_candidate_packet_to_research_narrative_input(source_packet)
    payload = compose_scanner_candidate_research_narrative(source_packet).to_dict()
    sections = _section_map(payload)

    assert tuple(sections) == RESEARCH_NARRATIVE_SECTION_TITLES
    assert composer_input["symbol"] == "PLTR"
    assert composer_input["currentObservation"] == (
        "PLTR scanner evidence is available for observation-only review."
    )
    assert sections["Current observation"] == [composer_input["currentObservation"]]
    assert any(
        item.startswith("Trend evidence: Complete evidence observed")
        for item in sections["Evidence supporting the observation"]
    )
    assert "Data quality is partial." in sections["Evidence limiting the observation"]
    assert sections["Data freshness"] == [
        "Latest evidence timestamp observed: 2026-05-08.",
        "Freshness labels observed: limited; most constrained label: limited.",
    ]
    assert sections["Research next step"] == [
        "Review the scanner evidence buckets with one independent confirmation point."
    ]
    assert sections["No-advice disclosure"] == [
        "For research observation only. It does not provide personalized financial advice or account action instructions."
    ]


def test_scanner_adapter_redacts_raw_diagnostics_and_advice_terms() -> None:
    source_packet = _scanner_fixture()
    evidence_packet = source_packet["diagnostics"]["evidence_packet"]
    evidence_packet["adminReasonCodes"].extend(
        ["provider_timeout", "sourceAuthorityAllowed", "buy_now"]
    )
    evidence_packet["providerObservation"] = {
        "providerName": "UnsafeProvider",
        "rawPayload": {"token": "secret"},
        "debugTrace": "traceback",
    }
    evidence_packet["trendEvidence"]["facts"].append(
        {"label": "raw payload", "value": "buy now at the target price"}
    )

    payload = compose_scanner_candidate_research_narrative(source_packet).to_dict()
    rendered = _rendered_text(payload)

    assert "trend evidence" in rendered
    assert "observation-only" in rendered
    for term in FORBIDDEN_OUTPUT_TERMS:
        assert term not in rendered


def test_scanner_adapter_does_not_import_live_ai_or_data_access_modules() -> None:
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    forbidden_modules = {
        "api",
        "apps",
        "data_provider",
        "requests",
        "httpx",
        "src.config",
        "src.core",
        "src.repositories",
        "src.services.ai_service",
        "src.services.litellm_runtime",
        "src.services.market_cache",
        "src.services.provider_usage_ledger",
        "src.services.report_renderer",
    }

    assert forbidden_modules.isdisjoint(imported_modules)
