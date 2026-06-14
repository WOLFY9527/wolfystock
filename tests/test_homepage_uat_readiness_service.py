# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage UAT readiness checklist contract."""

from __future__ import annotations

import json

import pytest

from src.services.homepage_uat_readiness_service import HomepageUatReadinessService


EXPECTED_TOP_LEVEL_KEYS = [
    "status",
    "asOf",
    "checks",
    "summary",
    "noAdviceDisclosure",
    "dataQuality",
]
EXPECTED_CHECK_KEYS = [
    "backend_contract",
    "frontend_visual_review",
    "public_copy_safety",
    "data_quality_boundary",
    "qa_execution",
]
ALLOWED_CHECK_STATUSES = {"pass", "review", "blocked", "no_evidence"}
ALLOWED_OWNER_AREAS = {"backend_contract", "frontend_ui", "data_quality", "copy", "qa"}


def _build_payload() -> dict[str, object]:
    service = HomepageUatReadinessService()
    return service.build_checklist(as_of="2026-06-15T09:30:00Z")


def _dump_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_default_checklist_serializes_the_public_contract_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["status"] == "review"
    assert payload["asOf"] == "2026-06-15T09:30:00Z"
    assert payload["summary"] == "首页视觉验收可进入人工复核，但仍需前端界面与 QA 执行结果确认。"
    assert payload["noAdviceDisclosure"] == "本清单仅用于首页视觉验收准备度复核，不构成投资建议或交易指令。"
    assert payload["dataQuality"] == {
        "status": "review",
        "label": "需人工复核",
        "publicMessage": "清单为静态合同，不执行实时行情或数据源检查。",
    }

    checks = payload["checks"]
    assert isinstance(checks, list)
    assert [check["key"] for check in checks] == EXPECTED_CHECK_KEYS
    assert all(set(check.keys()) == {"key", "label", "status", "publicMessage", "ownerArea", "required"} for check in checks)


def test_default_checklist_is_deterministic_with_fixed_timestamp() -> None:
    service = HomepageUatReadinessService()

    first = service.build_checklist(as_of="2026-06-15T09:30:00Z")
    second = service.build_checklist(as_of="2026-06-15T09:30:00Z")

    assert first == second


def test_check_statuses_owner_areas_and_required_flags_are_bounded() -> None:
    payload = _build_payload()

    assert payload["status"] in ALLOWED_CHECK_STATUSES
    for check in payload["checks"]:
        assert check["status"] in ALLOWED_CHECK_STATUSES
        assert check["ownerArea"] in ALLOWED_OWNER_AREAS
        assert isinstance(check["required"], bool)


def test_required_blockers_are_reflected_in_top_level_status() -> None:
    payload = _build_payload()

    required_checks = [check for check in payload["checks"] if check["required"]]
    assert required_checks
    assert not any(check["status"] == "blocked" for check in required_checks)
    assert any(check["status"] == "review" for check in required_checks)
    assert payload["status"] == "review"


@pytest.mark.parametrize(
    "forbidden",
    [
        "买入",
        "卖出",
        "下单",
        "交易信号",
        "trading signal",
        "buy now",
        "sell now",
        "target price",
        "止损",
        "止盈",
        "保证收益",
        "稳赚",
    ],
)
def test_checklist_is_not_presented_as_trading_advice(forbidden: str) -> None:
    dumped = _dump_payload(_build_payload()).lower()
    assert forbidden.lower() not in dumped


@pytest.mark.parametrize(
    "forbidden",
    [
        "traceback",
        "provider",
        "token",
        "session",
        "secret",
        "apiKey",
        "reasonCode",
        "trustLevel",
        "sourceType",
        "raw",
        "debug",
        "internal.example",
        "cookie",
        "/tmp/",
    ],
)
def test_checklist_does_not_leak_internal_diagnostics_or_secrets(forbidden: str) -> None:
    dumped = _dump_payload(_build_payload()).lower()
    assert forbidden.lower() not in dumped
