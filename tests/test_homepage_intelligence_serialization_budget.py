# -*- coding: utf-8 -*-
"""Smoke tests for homepage intelligence serialization size and stability."""

from __future__ import annotations

import json
import socket

import httpx
import requests

from api.v1.schemas.homepage_intelligence import HomepageIntelligenceResponse
from src.services.homepage_intelligence_service import HomepageIntelligenceService


HOMEPAGE_INTELLIGENCE_SERIALIZATION_BUDGET_BYTES = 96_000


def _build_serialized_bundle() -> tuple[dict[str, object], str]:
    payload = HomepageIntelligenceService().build_bundle()
    response = HomepageIntelligenceResponse.model_validate(payload)
    json_payload = response.model_dump(mode="json")
    serialized = json.dumps(
        json_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return json_payload, serialized


def _stable_public_projection(payload: dict[str, object]) -> dict[str, object]:
    intelligence_cockpit = payload["intelligenceCockpit"]
    cockpit_modules = payload["cockpitModules"]
    return {
        "schemaVersion": payload["schemaVersion"],
        "scope": payload["scope"],
        "sampleOnly": payload["sampleOnly"],
        "intelligenceCockpit": {
            "schemaVersion": intelligence_cockpit["schemaVersion"],
            "sectionOrder": intelligence_cockpit["sectionOrder"],
            "sectionKeys": [section["key"] for section in intelligence_cockpit["sections"]],
        },
        "cockpitModules": {
            "schemaVersion": cockpit_modules["schemaVersion"],
            "moduleOrder": cockpit_modules["moduleOrder"],
            "moduleKeys": [module["key"] for module in cockpit_modules["modules"]],
        },
    }


def test_homepage_intelligence_bundle_serialization_budget_smoke(monkeypatch) -> None:
    def _fail_network(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("homepage intelligence bundle should not require network calls")

    monkeypatch.setattr(socket, "create_connection", _fail_network)
    monkeypatch.setattr(requests.sessions.Session, "request", _fail_network)
    monkeypatch.setattr(httpx.Client, "request", _fail_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", _fail_network)

    _, serialized = _build_serialized_bundle()

    assert len(serialized.encode("utf-8")) < HOMEPAGE_INTELLIGENCE_SERIALIZATION_BUDGET_BYTES


def test_homepage_intelligence_bundle_has_deterministic_stable_public_keys() -> None:
    first_payload, first_serialized = _build_serialized_bundle()
    second_payload, second_serialized = _build_serialized_bundle()

    assert _stable_public_projection(first_payload) == _stable_public_projection(second_payload)
    assert first_serialized == second_serialized
