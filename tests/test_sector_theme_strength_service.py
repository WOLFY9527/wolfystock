# -*- coding: utf-8 -*-
"""Focused tests for the homepage sector/theme strength scaffold."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from api.v1.schemas.sector_theme_strength import SectorThemeStrengthItemModel
from src.services.sector_theme_strength_service import (
    NO_ADVICE_DISCLOSURE,
    SectorThemeStrengthService,
)


def test_build_summary_serializes_strongest_and_weakest_lists():
    service = SectorThemeStrengthService()

    summary = service.build_summary(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "strongest": [
                {
                    "name": "半导体",
                    "category": "sector",
                    "relativeStrength": 0.82,
                    "breadth": 0.74,
                    "diffusionStatus": "diffusing",
                    "leadershipStatus": "stronger",
                    "observation": "相对强弱领先且扩散到更多成员，仅供观察。",
                    "dataQuality": {"status": "ready", "observation": "example/test data only"},
                },
                {
                    "name": "AI Infra",
                    "category": "theme",
                    "relativeStrength": 0.77,
                    "breadth": 0.68,
                    "diffusionStatus": "concentrated",
                    "leadershipStatus": "stronger",
                    "observation": "强势主要由少数龙头带动，仍属观察口径。",
                    "dataQuality": {"status": "ready", "observation": "example/test data only"},
                },
            ],
            "weakest": [
                {
                    "name": "公用事业",
                    "category": "sector",
                    "relativeStrength": -0.41,
                    "breadth": 0.28,
                    "diffusionStatus": "narrowing",
                    "leadershipStatus": "weaker",
                    "observation": "相对强弱偏弱且扩散不足，仅供观察。",
                    "dataQuality": {"status": "ready", "observation": "example/test data only"},
                }
            ],
            "leadership": {
                "status": "concentrated",
                "observation": "当前强势主要集中在少数龙头，扩散仍待继续观察。",
                "dataQuality": {"status": "ready", "observation": "example/test data only"},
            },
            "diffusion": {
                "status": "diffusing",
                "observation": "强势从龙头向更多成员扩散，但不构成交易指令。",
                "dataQuality": {"status": "ready", "observation": "example/test data only"},
            },
            "concentration": {
                "status": "concentrated",
                "observation": "龙头集中度偏高，需继续观察集中是否缓解。",
                "dataQuality": {"status": "ready", "observation": "example/test data only"},
            },
            "dataQuality": {
                "status": "ready",
                "observation": "example/test data only",
            },
        }
    )

    payload = summary.model_dump(mode="json")

    assert payload["status"] == "ready"
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert [item["name"] for item in payload["strongest"]] == ["半导体", "AI Infra"]
    assert [item["name"] for item in payload["weakest"]] == ["公用事业"]
    assert payload["leadership"]["status"] == "concentrated"
    assert payload["diffusion"]["status"] == "diffusing"
    assert payload["concentration"]["status"] == "concentrated"


def test_build_summary_defaults_to_safe_no_evidence_contract():
    service = SectorThemeStrengthService()

    summary = service.build_summary()
    payload = summary.model_dump(mode="json")

    assert payload["status"] == "no_evidence"
    assert payload["strongest"] == []
    assert payload["weakest"] == []
    assert payload["leadership"]["status"] == "no_evidence"
    assert payload["diffusion"]["status"] == "no_evidence"
    assert payload["concentration"]["status"] == "no_evidence"
    assert payload["dataQuality"]["status"] == "no_evidence"
    assert payload["noAdviceDisclosure"] == NO_ADVICE_DISCLOSURE
    assert "仅供观察" in payload["leadership"]["observation"]


def test_statuses_are_bounded():
    with pytest.raises(ValidationError):
        SectorThemeStrengthItemModel(
            name="异常主题",
            category="theme",
            relativeStrength=0.2,
            breadth=0.4,
            diffusionStatus="breakout",
            leadershipStatus="stronger",
            observation="仅供观察。",
            dataQuality={"status": "ready", "observation": "example/test data only"},
        )


def test_service_strips_prohibited_trading_advice_terms():
    service = SectorThemeStrengthService()

    summary = service.build_summary(
        {
            "strongest": [
                {
                    "name": "半导体",
                    "category": "sector",
                    "relativeStrength": 0.91,
                    "breadth": 0.72,
                    "diffusionStatus": "diffusing",
                    "leadershipStatus": "stronger",
                    "observation": "建议买入龙头并上调目标价，buy now。",
                    "dataQuality": {"status": "ready", "observation": "ready to trade"},
                }
            ],
            "leadership": {
                "status": "concentrated",
                "observation": "立即交易并加仓的表述不应保留。",
                "dataQuality": {"status": "ready", "observation": "buy signal"},
            },
        }
    )

    serialized = json.dumps(summary.model_dump(mode="json"), ensure_ascii=False)

    for forbidden in ("买入", "目标价", "buy now", "立即交易", "加仓", "trade"):
        assert forbidden not in serialized.lower()
    assert "仅供观察" in serialized


def test_service_drops_internal_diagnostics_and_secret_markers():
    service = SectorThemeStrengthService()

    summary = service.build_summary(
        {
            "strongest": [
                {
                    "name": "算力",
                    "category": "theme",
                    "relativeStrength": 0.61,
                    "breadth": 0.66,
                    "diffusionStatus": "diffusing",
                    "leadershipStatus": "stronger",
                    "observation": "traceback token secret reasonCode sourceType fallback http://internal",
                    "dataQuality": {
                        "status": "ready",
                        "observation": "debug raw diagnostics trustLevel API_KEY",
                    },
                    "reasonCode": "should-not-leak",
                    "sourceType": "internal_only",
                }
            ],
            "dataQuality": {
                "status": "ready",
                "observation": "provider payload debug token secret",
            },
        }
    )

    payload = summary.model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    for forbidden in (
        "traceback",
        "token",
        "secret",
        "reasoncode",
        "trustlevel",
        "sourcetype",
        "fallback",
        "http://",
        "debug",
        "raw diagnostics",
        "api_key",
    ):
        assert forbidden not in serialized
