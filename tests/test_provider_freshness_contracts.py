# -*- coding: utf-8 -*-
"""Provider freshness and fallback disclosure contracts.

These tests are intentionally synthetic/offline. They must not call live
providers or change provider routing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from src.services.analysis_provider_planner import (
    AnalysisProviderExecutor,
    DataCategory,
    ProviderTimeout,
    build_analysis_provider_plan,
)
from src.services.market_overview_service import (
    MarketOverviewService,
    classify_market_payload_reliability,
    get_freshness_status,
)


CN_TZ = timezone(timedelta(hours=8))


class _ProviderAuthError(RuntimeError):
    status_code = 403


def _quote_plan():
    return build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE]).categories[
        DataCategory.QUOTE
    ]


@pytest.mark.parametrize(
    ("source", "expected_freshness"),
    [
        ("fallback", "fallback"),
        ("mock", "mock"),
        ("synthetic", "fallback"),
    ],
)
def test_fallback_mock_and_synthetic_sources_are_never_labeled_live(source: str, expected_freshness: str) -> None:
    now = datetime(2026, 5, 8, 10, 0, tzinfo=CN_TZ)

    freshness = get_freshness_status(now.isoformat(timespec="seconds"), "crypto", source, False, now=now)

    assert freshness["freshness"] == expected_freshness
    assert freshness["isFallback"] is True
    assert freshness["freshness"] != "live"


def test_freshness_and_provider_health_semantics_cover_supported_states() -> None:
    service = MarketOverviewService()
    now = datetime(2026, 5, 8, 10, 0, tzinfo=CN_TZ)

    live = get_freshness_status(now.isoformat(timespec="seconds"), "crypto", "binance", False, now=now)
    stale = get_freshness_status(
        (now - timedelta(hours=2)).isoformat(timespec="seconds"),
        "crypto",
        "binance",
        False,
        now=now,
    )
    fallback = get_freshness_status(now.isoformat(timespec="seconds"), "crypto", "fallback", True, now=now)
    mixed = classify_market_payload_reliability(
        {
            "source": "mixed",
            "items": [
                {"symbol": "BTC", "value": 75000, "source": "binance", "freshness": "live"},
                {"symbol": "STABLECOIN_LIQUIDITY", "value": 0, "source": "fallback", "freshness": "fallback"},
            ],
        },
        category="crypto",
    )
    unavailable_health = service._provider_health(
        {"source": "unavailable", "freshness": "fallback", "items": []},
        "sentiment",
        duration_ms=1,
        error_summary=None,
    )
    refreshing_health = service._provider_health(
        {
            "source": "binance",
            "freshness": "live",
            "isRefreshing": True,
            "items": [{"symbol": "BTC", "value": 75000, "source": "binance", "freshness": "live"}],
        },
        "crypto",
        duration_ms=1,
        error_summary=None,
    )

    assert live["freshness"] == "live"
    assert stale["freshness"] == "stale"
    assert stale["isStale"] is True
    assert fallback["freshness"] == "fallback"
    assert mixed["kind"] == "mixed"
    assert mixed["fallbackItemCount"] == 1
    assert unavailable_health["status"] == "unavailable"
    assert refreshing_health["status"] == "refreshing"


@pytest.mark.parametrize(
    ("primary", "expected_reason"),
    [
        (lambda: (_ for _ in ()).throw(ProviderTimeout("slow")), "timeout"),
        (lambda: (_ for _ in ()).throw(_ProviderAuthError("Forbidden token=SECRET")), "auth_error"),
        (lambda: {}, "invalid_payload"),
        (lambda: {"symbol": "ORCL"}, "invalid_payload"),
        (lambda: ["malformed"], "invalid_payload"),
    ],
)
def test_provider_failure_cases_fall_back_without_relabeling_primary_as_live(primary, expected_reason: str) -> None:
    calls: list[str] = []
    executor = AnalysisProviderExecutor()

    result = executor.execute_category(
        _quote_plan(),
        symbol="ORCL",
        providers={
            "alpaca": lambda: calls.append("alpaca") or primary(),
            "finnhub": lambda: calls.append("finnhub") or {"price": 101},
        },
        sufficient=lambda data: isinstance(data, dict) and isinstance(data.get("price"), (int, float)),
    )

    assert result.source_provider == "finnhub"
    assert result.is_fallback is True
    assert calls == ["alpaca", "finnhub"]
    assert result.attempts[0]["reason"] == expected_reason
    assert result.attempts[0]["status"] == "failed"
    assert "SECRET" not in json.dumps(result.metadata())


def test_offline_reliability_audit_cli_outputs_bounded_json_without_network_calls() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/provider_reliability_audit.py", "--offline"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)

    assert set(payload) == {
        "providersChecked",
        "freshnessPosture",
        "fallbackPosture",
        "networkCallsExecuted",
        "manualReviewRequired",
    }
    assert payload["networkCallsExecuted"] is False
    assert payload["manualReviewRequired"] is True
    assert isinstance(payload["providersChecked"], list)
    assert "live" in payload["freshnessPosture"]["statesCovered"]
    assert payload["fallbackPosture"]["mockAsLiveAllowed"] is False
