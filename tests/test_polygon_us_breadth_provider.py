# -*- coding: utf-8 -*-
"""Polygon grouped-daily US breadth adapter contracts."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.services.polygon_us_breadth_provider import (
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD,
    POLYGON_US_BREADTH_REASON_RESPONSE_INVALID,
    POLYGON_US_BREADTH_REASON_UNAUTHORIZED,
    POLYGON_US_EASTERN_TZ,
    compute_polygon_us_breadth,
    run_polygon_us_breadth_activation,
)
from src.services.us_breadth_contracts import (
    US_BREADTH_MISSING_PROVIDER_REASON,
    US_BREADTH_SYMBOLS,
)


def _grouped_payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "OK",
        "resultsCount": len(rows),
        "results": rows,
    }


def test_missing_polygon_key_keeps_us_breadth_fail_closed_with_existing_reason() -> None:
    result = run_polygon_us_breadth_activation(api_key="")

    assert result["credentialsPresent"] is False
    assert result["providerConstructed"] is False
    assert result["probePassed"] is False
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["fulfilledMetrics"] == []
    assert result["missingMetrics"] == list(US_BREADTH_SYMBOLS)
    assert result["reasonCodes"] == [US_BREADTH_MISSING_PROVIDER_REASON]


def test_polygon_unauthorized_response_keeps_us_breadth_fail_closed() -> None:
    def transport(date: str, api_key: str, timeout: float) -> tuple[int, dict[str, object]]:
        return 403, {"status": "ERROR", "error": "forbidden"}

    result = run_polygon_us_breadth_activation(
        api_key="test-key",
        transport=transport,
        now=datetime(2026, 5, 22, 12, tzinfo=POLYGON_US_EASTERN_TZ),
    )

    assert result["credentialsPresent"] is True
    assert result["providerConstructed"] is True
    assert result["probePassed"] is False
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["reasonCodes"] == [POLYGON_US_BREADTH_REASON_UNAUTHORIZED]


def test_malformed_polygon_grouped_response_keeps_us_breadth_fail_closed() -> None:
    result = compute_polygon_us_breadth(
        {"status": "OK", "resultsCount": "bad", "results": []},
        observation_date="2026-05-21",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
    )

    assert result["probePassed"] is False
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["reasonCodes"] == [POLYGON_US_BREADTH_REASON_RESPONSE_INVALID]


def test_low_polygon_coverage_keeps_us_breadth_fail_closed() -> None:
    result = compute_polygon_us_breadth(
        _grouped_payload([
            {"T": "AAA", "o": 10.0, "c": 11.0},
            {"T": "BBB", "o": 20.0, "c": 19.0},
        ]),
        observation_date="2026-05-21",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
    )

    assert result["coverageCount"] == 2
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["reasonCodes"] == [POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD]


def test_fresh_valid_polygon_grouped_daily_computes_ad_breadth_from_previous_close() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0},
        {"T": "BBB", "o": 20.0, "c": 18.0},
        {"T": "CCC", "o": 30.0, "c": 30.0},
        {"T": "DDD", "o": 5.0, "c": 6.0},
    ])
    previous = _grouped_payload([
        {"T": "AAA", "o": 9.0, "c": 10.0},
        {"T": "BBB", "o": 22.0, "c": 20.0},
        {"T": "CCC", "o": 28.0, "c": 30.0},
        {"T": "DDD", "o": 4.0, "c": 7.0},
    ])

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=4,
    )

    assert result["probePassed"] is True
    assert result["freshnessValid"] is True
    assert result["coverageCount"] == 4
    assert result["sourceMetadataValid"] is True
    assert result["sourceAuthorityAllowed"] is True
    assert result["scoreContributionAllowed"] is True
    assert result["fulfilledMetrics"] == [
        "ADVANCERS",
        "DECLINERS",
        "UNCHANGED",
        "ADVANCE_DECLINE_RATIO",
    ]
    assert result["metrics"]["advancers"] == 1
    assert result["metrics"]["decliners"] == 2
    assert result["metrics"]["unchanged"] == 1
    assert result["metrics"]["advanceDeclineRatio"] == 0.5
    assert result["metrics"]["newHighs"] is None
    assert result["metrics"]["newLows"] is None
    assert result["metrics"]["highLowRatio"] is None
    assert result["universe"] == "polygon_us_grouped_daily_ex_otc"
    assert result["authorityBasis"] == "computed_from_authorized_polygon_grouped_daily"
    assert POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON in result["reasonCodes"]
    assert {"NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"}.issubset(result["missingMetrics"])


def test_polygon_activation_fetches_recent_completed_date_and_previous_comparison() -> None:
    calls: list[str] = []
    payloads = {
        "2026-05-21": _grouped_payload([
            {"T": "AAA", "o": 10.0, "c": 11.0},
            {"T": "BBB", "o": 20.0, "c": 18.0},
            {"T": "CCC", "o": 30.0, "c": 30.0},
        ]),
        "2026-05-20": _grouped_payload([
            {"T": "AAA", "o": 9.0, "c": 10.0},
            {"T": "BBB", "o": 22.0, "c": 20.0},
            {"T": "CCC", "o": 29.0, "c": 30.0},
        ]),
    }

    def transport(date: str, api_key: str, timeout: float) -> tuple[int, dict[str, object]]:
        calls.append(date)
        return 200, payloads[date]

    result = run_polygon_us_breadth_activation(
        api_key="test-key",
        transport=transport,
        now=datetime(2026, 5, 22, 12, tzinfo=POLYGON_US_EASTERN_TZ),
        min_coverage_count=3,
    )

    assert calls == ["2026-05-21", "2026-05-20"]
    assert result["observationDate"] == "2026-05-21"
    assert result["previousObservationDate"] == "2026-05-20"
    assert result["sourceAuthorityAllowed"] is True
