# -*- coding: utf-8 -*-
"""Focused regression coverage for the research narrative composer."""

from __future__ import annotations

import ast
from pathlib import Path

from src.services.research_narrative_composer import (
    RESEARCH_NARRATIVE_SECTION_TITLES,
    compose_research_narrative,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSER_PATH = REPO_ROOT / "src" / "services" / "research_narrative_composer.py"
FORBIDDEN_OUTPUT_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommend",
    "target",
    "stop",
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
)


def _section_map(payload: dict) -> dict[str, list[str]]:
    return {section["title"]: section["body"] for section in payload["sections"]}


def _rendered_text(payload: dict) -> str:
    return " ".join(
        str(item)
        for section in payload["sections"]
        for item in [section["title"], *section["body"]]
    ).lower()


def test_composes_required_sections_from_structured_evidence_packet() -> None:
    packet = {
        "symbol": "AAPL",
        "currentObservation": "Revenue growth and margin evidence are moving in the same direction.",
        "supportingEvidence": [
            {
                "label": "Revenue trend",
                "summary": "Latest quarterly revenue growth improved versus the prior period",
                "asOf": "2026-06-15",
                "freshness": "fresh",
            },
            {
                "label": "Margin trend",
                "summary": "Gross margin stayed within the recent operating range",
                "asOf": "2026-06-14",
                "freshness": "delayed",
            },
        ],
        "limitingEvidence": [
            {
                "label": "Coverage gap",
                "summary": "Management commentary still needs confirmation from the next filing",
                "asOf": "2026-06-13",
                "freshness": "stale",
            }
        ],
        "researchNextStep": [
            "Compare the next filing with the latest margin and revenue evidence.",
        ],
        "asOf": "2026-06-16",
    }

    result = compose_research_narrative(packet)
    payload = result.to_dict()
    sections = _section_map(payload)

    assert payload["contractVersion"] == "research_narrative_composer_v1"
    assert tuple(sections) == RESEARCH_NARRATIVE_SECTION_TITLES
    assert sections["Current observation"] == [
        "Revenue growth and margin evidence are moving in the same direction."
    ]
    assert sections["Evidence supporting the observation"] == [
        "Revenue trend: Latest quarterly revenue growth improved versus the prior period (as of 2026-06-15).",
        "Margin trend: Gross margin stayed within the recent operating range (as of 2026-06-14).",
    ]
    assert sections["Evidence limiting the observation"] == [
        "Coverage gap: Management commentary still needs confirmation from the next filing (as of 2026-06-13)."
    ]
    assert sections["Data freshness"] == [
        "Latest evidence timestamp observed: 2026-06-16.",
        "Freshness labels observed: fresh, delayed, stale; most constrained label: stale.",
    ]
    assert sections["Research next step"] == [
        "Compare the next filing with the latest margin and revenue evidence."
    ]
    assert "## No-advice disclosure" in result.to_markdown()


def test_filters_advice_and_internal_diagnostic_terms_from_output() -> None:
    packet = {
        "currentObservation": "raw payload says buy now after provider_timeout",
        "supportingEvidence": [
            {"label": "provider debug", "summary": "cache trace recommends a target price"},
            '{"raw_payload": {"token": "secret"}}',
            {"label": "Clean metric", "summary": "Revenue growth remained above the prior period"},
        ],
        "limitingEvidence": [
            {"label": "sourceAuthorityAllowed", "summary": "scoreContributionAllowed reasonCode"},
            {"label": "Clean caveat", "summary": "Coverage still depends on the next public filing"},
        ],
        "researchNextStep": [
            "sell on the next stop loss",
            "Read the next public filing before expanding the evidence set.",
        ],
        "freshness": "cache",
        "asOf": "2026-06-16",
    }

    payload = compose_research_narrative(packet).to_dict()
    sections = _section_map(payload)
    rendered = _rendered_text(payload)

    assert sections["Current observation"] == [
        "The packet highlights Clean metric: Revenue growth remained above the prior period."
    ]
    assert sections["Evidence supporting the observation"] == [
        "Clean metric: Revenue growth remained above the prior period."
    ]
    assert sections["Evidence limiting the observation"] == [
        "Clean caveat: Coverage still depends on the next public filing."
    ]
    assert sections["Research next step"] == [
        "Read the next public filing before expanding the evidence set."
    ]
    assert "recent snapshot" in rendered
    for term in FORBIDDEN_OUTPUT_TERMS:
        assert term not in rendered


def test_accepts_research_packet_v1_style_projection_without_raw_projection_fields() -> None:
    packet = {
        "packetIdentity": {"symbol": "MSFT", "asOf": "2026-06-15"},
        "consumerProjection": {
            "headline": "Data can be used for research observation.",
        },
        "evidenceCitations": [
            {
                "id": "citation-1",
                "lane": "fundamentals",
                "label": "Fundamentals",
                "summary": "Profitability evidence remains available for review",
                "asOf": "2026-06-15",
            }
        ],
        "lanes": {
            "earnings": {
                "freshness": "delayed",
                "limitations": ["Earnings evidence needs the next filing confirmation"],
                "nextEvidenceNeeded": ["Review the next earnings filing when it is available"],
            }
        },
    }

    payload = compose_research_narrative(packet).to_dict()
    sections = _section_map(payload)
    rendered = _rendered_text(payload)

    assert sections["Current observation"] == ["Data can be used for research observation."]
    assert sections["Evidence supporting the observation"] == [
        "Fundamentals: Profitability evidence remains available for review (as of 2026-06-15)."
    ]
    assert sections["Evidence limiting the observation"] == [
        "earnings: Earnings evidence needs the next filing confirmation."
    ]
    assert sections["Research next step"] == [
        "earnings: Review the next earnings filing when it is available."
    ]
    assert "sourceauthorityallowed" not in rendered
    assert "scorecontributionallowed" not in rendered


def test_same_packet_produces_identical_output_and_markdown_contains_no_json_blob() -> None:
    packet = {
        "currentObservation": "Evidence remains mixed and needs one more confirmation point.",
        "supportingEvidence": ["Revenue evidence is available for review."],
        "limitingEvidence": ["Margin evidence is still incomplete."],
        "researchNextStep": "Review the next public filing.",
        "asOf": "2026-06-16",
    }

    first = compose_research_narrative(packet)
    second = compose_research_narrative(dict(packet))

    assert first.to_dict() == second.to_dict()
    markdown = first.to_markdown()
    assert "{" not in markdown
    assert "}" not in markdown
    assert "## Current observation" in markdown
    assert "## Research next step" in markdown


def test_composer_module_does_not_import_live_ai_or_data_access_modules() -> None:
    tree = ast.parse(COMPOSER_PATH.read_text(encoding="utf-8"))
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
