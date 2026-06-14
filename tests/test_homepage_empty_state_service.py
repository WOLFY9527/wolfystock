# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage empty-state copy contract."""

from __future__ import annotations

import json

from src.services.homepage_empty_state_service import (
    EXPECTED_HOMEPAGE_EMPTY_STATE_MODULE_KEYS,
    HomepageEmptyStateService,
)


EXPECTED_TOP_LEVEL_KEYS = {
    "status",
    "asOf",
    "emptyStates",
    "noAdviceDisclosure",
    "dataQuality",
}
EXPECTED_EMPTY_STATE_KEYS = {
    "moduleKey",
    "title",
    "message",
    "reviewPoint",
    "state",
}
FORBIDDEN_ADVICE_TERMS = (
    "买入",
    "卖出",
    "下单",
    "交易信号",
    "交易指令",
    "目标价",
    "止损",
    "止盈",
    "投资建议",
    "交易建议",
    "buy",
    "sell",
    "order",
    "target price",
    "stop-loss",
)
FORBIDDEN_INTERNAL_TERMS = (
    "fallback",
    "provider",
    "diagnostic",
    "debug",
    "traceback",
    "raw",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "token",
    "secret",
    "cookie",
    "session",
    "api_key",
    "apikey",
    "http://",
    "https://",
    "/users/",
)
FORBIDDEN_LIVE_DATA_TERMS = (
    "live data",
    "实时数据",
    "real-time",
    "realtime",
)


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _assert_raises_value_error(callback) -> None:
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_build_contract_returns_stable_top_level_shape_and_modules() -> None:
    payload = HomepageEmptyStateService().build_contract().model_dump(mode="json")

    assert set(payload) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["status"] == "ready"
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["noAdviceDisclosure"] == "仅供首页缺省状态说明，不提供个性化建议。"
    assert payload["dataQuality"] == {
        "state": "ready",
        "label": "缺省文案已就绪",
        "available": True,
        "summary": "首页模块缺省说明使用固定公开文案，不包含运行细节。",
    }

    assert [item["moduleKey"] for item in payload["emptyStates"]] == list(
        EXPECTED_HOMEPAGE_EMPTY_STATE_MODULE_KEYS
    )
    for item in payload["emptyStates"]:
        assert set(item) == EXPECTED_EMPTY_STATE_KEYS
        assert item["state"] in {"no_evidence", "unavailable", "partial", "ready"}
        assert item["title"]
        assert item["message"]
        assert item["reviewPoint"]


def test_copy_contract_uses_bounded_public_chinese_copy() -> None:
    payload = HomepageEmptyStateService().build_contract().model_dump(mode="json")

    for item in payload["emptyStates"]:
        assert item["title"].isascii() is False
        assert item["message"].isascii() is False
        assert item["reviewPoint"].isascii() is False
        assert len(item["title"]) <= 24
        assert len(item["message"]) <= 72
        assert len(item["reviewPoint"]) <= 48


def test_copy_contract_excludes_advice_diagnostics_and_live_claims() -> None:
    payload = HomepageEmptyStateService().build_contract().model_dump(mode="json")
    serialized = _serialized(payload)

    leaked_advice = [term for term in FORBIDDEN_ADVICE_TERMS if term.lower() in serialized]
    leaked_internal = [term for term in FORBIDDEN_INTERNAL_TERMS if term.lower() in serialized]
    leaked_live = [term for term in FORBIDDEN_LIVE_DATA_TERMS if term.lower() in serialized]

    assert leaked_advice == []
    assert leaked_internal == []
    assert leaked_live == []


def test_schema_rejects_unknown_module_or_unsafe_copy() -> None:
    from api.v1.schemas.homepage_empty_state import (
        HomepageEmptyStateContract,
        HomepageEmptyStateCopy,
        HomepageEmptyStateDataQuality,
    )

    _assert_raises_value_error(
        lambda: HomepageEmptyStateCopy(
            moduleKey="provider_debug",
            title="内部诊断",
            message="provider fallback raw payload",
            reviewPoint="查看 token",
            state="no_evidence",
        )
    )

    _assert_raises_value_error(
        lambda: HomepageEmptyStateContract(
            status="ready",
            asOf="2026-06-14T09:30:00Z",
            emptyStates=[
                HomepageEmptyStateCopy(
                    moduleKey="market_pulse",
                    title="买入提示",
                    message="建议买入并设置目标价。",
                    reviewPoint="下单前复核。",
                    state="ready",
                )
            ],
            noAdviceDisclosure="仅供首页缺省状态说明，不提供个性化建议。",
            dataQuality=HomepageEmptyStateDataQuality(
                state="ready",
                label="缺省文案已就绪",
                available=True,
                summary="首页模块缺省说明使用固定公开文案，不包含运行细节。",
            ),
        )
    )
