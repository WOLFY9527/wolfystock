# -*- coding: utf-8 -*-
"""Focused tests for the homepage why-it-matters explanation contract."""

from __future__ import annotations

import json

from src.services.homepage_explanation_service import (
    NO_ADVICE_DISCLOSURE,
    HomepageExplanationService,
)


FORBIDDEN_ADVICE_TERMS = (
    "buy",
    "sell",
    "add",
    "reduce",
    "target price",
    "stop-loss",
    "take-profit",
    "predicted return",
    "ai recommendation",
    "order",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "目标价",
    "止损",
    "止盈",
    "投资建议",
    "交易建议",
)

FORBIDDEN_LEAK_TERMS = (
    "traceback",
    "token",
    "session",
    "api_key",
    "apikey",
    "secret",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "fallback",
    "http://",
    "https://",
    "/users/",
)


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_generates_safe_explanation_from_caller_signal() -> None:
    payload = HomepageExplanationService().build_explanations(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "explanations": [
                {
                    "id": "breadth-weakening",
                    "sourceModule": "market_pulse",
                    "title": "广度走弱",
                    "signal": "广度走弱",
                    "relatedSignals": ["breadth", "money_flow"],
                    "reviewPoint": "复核市场内部扩散。",
                    "status": "ready",
                }
            ],
        }
    ).model_dump(mode="json")

    assert set(payload) == {
        "status",
        "asOf",
        "explanations",
        "noAdviceDisclosure",
        "dataQuality",
    }
    assert payload["status"] == "ready"
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["noAdviceDisclosure"] == NO_ADVICE_DISCLOSURE
    assert payload["dataQuality"] == {
        "state": "ready",
        "label": "正常",
        "available": True,
    }
    assert payload["explanations"] == [
        {
            "id": "breadth-weakening",
            "sourceModule": "market_pulse",
            "title": "广度走弱",
            "whyItMatters": "广度走弱说明上涨参与率不足，适合复核市场内部扩散。",
            "relatedSignals": ["breadth", "money_flow"],
            "reviewPoint": "复核市场内部扩散。",
            "status": "ready",
        }
    ]


def test_unsafe_input_is_sanitized() -> None:
    payload = HomepageExplanationService().build_explanations(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "explanations": [
                {
                    "id": "BUY-now-http://unsafe",
                    "sourceModule": "money_flow",
                    "title": "AI recommendation buy now",
                    "whyItMatters": "target price 100，stop-loss 90，predicted return 20%。",
                    "relatedSignals": ["money_flow", "buy_now", "session_id"],
                    "reviewPoint": "submit order now",
                    "status": "ready",
                }
            ],
            "dataQuality": {
                "status": "ready",
                "summary": "traceback token secret api_key",
            },
            "noAdviceDisclosure": "立即下单，构成投资建议。",
        }
    ).model_dump(mode="json")

    explanation = payload["explanations"][0]
    assert explanation["id"] == "money-flow-1"
    assert explanation["title"] == "市场信号说明"
    assert explanation["whyItMatters"] == "资金流向集中说明主线较明确，但需要观察扩散是否改善。"
    assert explanation["reviewPoint"] == "复核相关信号与研究证据。"
    assert explanation["relatedSignals"] == ["money_flow"]
    assert payload["noAdviceDisclosure"] == NO_ADVICE_DISCLOSURE
    assert payload["dataQuality"] == {
        "state": "ready",
        "label": "正常",
        "available": True,
    }


def test_defaults_to_no_evidence_contract() -> None:
    payload = HomepageExplanationService().build_explanations().model_dump(mode="json")

    assert payload["status"] == "no_evidence"
    assert payload["asOf"] is None
    assert payload["explanations"] == []
    assert payload["noAdviceDisclosure"] == NO_ADVICE_DISCLOSURE
    assert payload["dataQuality"] == {
        "state": "no_evidence",
        "label": "暂无证据",
        "available": False,
    }


def test_contract_excludes_internal_diagnostics_and_secret_markers() -> None:
    payload = HomepageExplanationService().build_explanations(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "explanations": [
                {
                    "id": "traceback-session",
                    "sourceModule": "event_radar",
                    "title": "providerRoute debug",
                    "signal": "关键事件窗口",
                    "whyItMatters": "traceback token secret reasonCode http://internal",
                    "relatedSignals": ["event_radar", "session_id", "sourceType"],
                    "reviewPoint": "查看 /Users/test/api_key",
                    "status": "ready",
                }
            ],
            "dataQuality": {
                "status": "ready",
                "summary": "fallback trustLevel sourceType secret",
            },
        }
    ).model_dump(mode="json")

    serialized = _serialized(payload)
    leaked = [term for term in FORBIDDEN_LEAK_TERMS if term in serialized]
    assert leaked == []
    assert payload["explanations"][0]["whyItMatters"] == "关键事件窗口可能提高波动，适合复核相关研究证据。"


def test_contract_excludes_trading_advice_terms() -> None:
    payload = HomepageExplanationService().build_explanations(
        {
            "explanations": [
                {
                    "id": "advice-heavy",
                    "sourceModule": "market_pulse",
                    "title": "买入提示",
                    "whyItMatters": "建议买入、加仓、止损、止盈，并给出 target price。",
                    "relatedSignals": ["breadth", "buy_now", "target_price"],
                    "reviewPoint": "sell now",
                    "status": "ready",
                }
            ]
        }
    ).model_dump(mode="json")

    serialized = _serialized(payload)
    leaked = [term for term in FORBIDDEN_ADVICE_TERMS if term in serialized]
    assert leaked == []
