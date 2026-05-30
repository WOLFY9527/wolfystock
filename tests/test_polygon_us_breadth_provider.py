# -*- coding: utf-8 -*-
"""Polygon grouped-daily US breadth adapter contracts."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from scripts.diagnose_polygon_market_overview_activation import (
    build_market_overview_activation_smoke_output,
)
from src.services.polygon_us_breadth_provider import (
    POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON,
    POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON,
    POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON,
    POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON,
    POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON,
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD,
    POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE,
    POLYGON_US_BREADTH_REASON_RESPONSE_INVALID,
    POLYGON_US_BREADTH_REASON_UNAUTHORIZED,
    POLYGON_US_EASTERN_TZ,
    compute_polygon_us_breadth,
    diagnostic_summary,
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


def _prior_weekdays(observation_date: str, count: int) -> list[str]:
    cursor = date.fromisoformat(observation_date) - timedelta(days=1)
    dates: list[str] = []
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    return dates


def _high_low_rows(
    *,
    aaa_high: float = 14.0,
    aaa_low: float = 8.0,
    bbb_high: float = 22.0,
    bbb_low: float = 18.0,
    ccc_high: float = 33.0,
    ccc_low: float = 28.0,
) -> list[dict[str, object]]:
    return [
        {"T": "AAA", "o": 9.0, "c": 10.0, "h": aaa_high, "l": aaa_low},
        {"T": "BBB", "o": 22.0, "c": 20.0, "h": bbb_high, "l": bbb_low},
        {"T": "CCC", "o": 28.0, "c": 30.0, "h": ccc_high, "l": ccc_low},
    ]


def _complete_high_low_history(observation_date: str, sessions: int = 3) -> tuple[tuple[str, dict[str, object]], ...]:
    return tuple(
        (history_date, _grouped_payload(_high_low_rows()))
        for history_date in _prior_weekdays(observation_date, sessions)
    )


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


def test_market_overview_polygon_smoke_output_is_sanitized_reason_only() -> None:
    output = build_market_overview_activation_smoke_output(
        {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "missingMetrics": list(US_BREADTH_SYMBOLS),
            "reasonCodes": [POLYGON_US_BREADTH_REASON_UNAUTHORIZED],
            "metrics": {"advancers": 1, "decliners": 2},
            "rawPayload": {"providerPayload": "raw-provider-value"},
        }
    )

    assert output == {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": False,
        "reason": POLYGON_US_BREADTH_REASON_UNAUTHORIZED,
        "status": "unauthorized_or_entitlement_denied",
        "entitlement": "denied_or_unavailable",
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "missingRequiredSymbols": list(US_BREADTH_SYMBOLS),
        "missingRequiredWindows": [],
    }
    serialized = json.dumps(output, ensure_ascii=False)
    assert "raw-provider-value" not in serialized
    assert "rawPayload" not in serialized
    assert "advancers" not in serialized


def test_market_overview_polygon_smoke_reports_unprobed_high_low_window() -> None:
    output = build_market_overview_activation_smoke_output(
        {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledMetrics": list(US_BREADTH_SYMBOLS),
            "missingMetrics": [],
            "reasonCodes": [],
            "highLowLookbackSessions": 1,
        }
    )

    assert output["status"] == "score_ready"
    assert output["missingRequiredSymbols"] == ["NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"]
    assert output["missingRequiredWindows"] == ["high_low_lookback"]


def test_polygon_activation_uses_env_file_key_when_process_env_is_missing(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("POLYGON_API_KEY=polygon-test-key\n", encoding="utf-8")
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.setenv("ENV_FILE", str(env_path))
    seen_key_present = False
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
        nonlocal seen_key_present
        seen_key_present = api_key == "polygon-test-key"
        return 200, payloads[date]

    result = run_polygon_us_breadth_activation(
        transport=transport,
        now=datetime(2026, 5, 22, 12, tzinfo=POLYGON_US_EASTERN_TZ),
        min_coverage_count=3,
        high_low_lookback_sessions=1,
    )

    assert seen_key_present is True
    assert "POLYGON_API_KEY" not in os.environ
    assert result["credentialsPresent"] is True
    assert result["providerConstructed"] is True
    assert result["sourceAuthorityAllowed"] is True
    assert result["scoreContributionAllowed"] is True


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


def test_empty_polygon_grouped_daily_with_key_reports_unavailable_not_live() -> None:
    def transport(date: str, api_key: str, timeout: float) -> tuple[int, dict[str, object]]:
        return 200, _grouped_payload([])

    result = run_polygon_us_breadth_activation(
        api_key="test-key",
        transport=transport,
        now=datetime(2026, 5, 22, 12, tzinfo=POLYGON_US_EASTERN_TZ),
        min_coverage_count=3,
    )

    assert result["credentialsPresent"] is True
    assert result["providerConstructed"] is True
    assert result["probePassed"] is False
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["reasonCodes"] == [POLYGON_US_BREADTH_REASON_COVERAGE_BELOW_THRESHOLD]


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


def test_missing_previous_grouped_daily_payload_keeps_ad_breadth_non_scoring() -> None:
    result = compute_polygon_us_breadth(
        _grouped_payload([
            {"T": "AAA", "o": 10.0, "c": 11.0},
            {"T": "BBB", "o": 20.0, "c": 18.0},
            {"T": "CCC", "o": 30.0, "c": 30.0},
        ]),
        observation_date="2026-05-21",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
    )

    assert result["comparisonBasis"] == "open_close"
    assert result["previousObservationDate"] is None
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["metrics"]["advancers"] == 1
    assert result["metrics"]["decliners"] == 1
    assert result["metrics"]["unchanged"] == 1
    assert POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE in result["reasonCodes"]


def test_malformed_previous_grouped_daily_payload_keeps_ad_breadth_non_scoring() -> None:
    result = compute_polygon_us_breadth(
        _grouped_payload([
            {"T": "AAA", "o": 10.0, "c": 11.0},
            {"T": "BBB", "o": 20.0, "c": 18.0},
            {"T": "CCC", "o": 30.0, "c": 30.0},
        ]),
        previous_payload={"status": "OK", "resultsCount": "bad", "results": []},
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
    )

    assert result["comparisonBasis"] == "open_close"
    assert result["previousObservationDate"] is None
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE in result["reasonCodes"]


def test_low_coverage_previous_grouped_daily_payload_keeps_ad_breadth_non_scoring() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0},
        {"T": "BBB", "o": 20.0, "c": 18.0},
        {"T": "CCC", "o": 30.0, "c": 30.0},
    ])
    previous = _grouped_payload([
        {"T": "AAA", "o": 9.0, "c": 10.0},
    ])

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
    )

    assert result["comparisonBasis"] == "open_close"
    assert result["previousObservationDate"] is None
    assert result["previousCoverageCount"] == 1
    assert result["comparisonCoverageCount"] == 1
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert POLYGON_US_BREADTH_REASON_PREVIOUS_CLOSE_UNAVAILABLE in result["reasonCodes"]


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
    assert result["previousCoverageCount"] == 4
    assert result["comparisonCoverageCount"] == 4
    assert result["comparisonBasis"] == "previous_close"
    assert result["previousObservationDate"] == "2026-05-20"
    assert result["sourceMetadataValid"] is True
    assert result["sourceAuthorityAllowed"] is True
    assert result["scoreContributionAllowed"] is True
    assert result["broadMarketClaimAllowed"] is False
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
    assert result["authorityBasis"] == "computed_from_authorized_polygon_history"
    assert result["officialExchangePublishedBreadth"] is False
    assert result["fullBreadthAuthority"] is False
    assert POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON in result["reasonCodes"]
    assert {"NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"}.issubset(result["missingMetrics"])
    assert diagnostic_summary(result)["comparisonBasis"] == "previous_close"
    assert diagnostic_summary(result)["previousObservationDate"] == "2026-05-20"


def test_valid_polygon_history_computes_high_low_breadth_without_official_overclaim() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0, "h": 15.0, "l": 9.0},
        {"T": "BBB", "o": 20.0, "c": 18.0, "h": 21.0, "l": 17.0},
        {"T": "CCC", "o": 30.0, "c": 30.0, "h": 32.0, "l": 29.0},
    ])
    previous = _grouped_payload(_high_low_rows())

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        historical_payloads=_complete_high_low_history("2026-05-21"),
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
        high_low_lookback_sessions=3,
        min_high_low_eligible_count=3,
    )

    assert result["source"] == "polygon_us_grouped_daily"
    assert result["authorityBasis"] == "computed_from_authorized_polygon_history"
    assert result["universe"] == "polygon_us_grouped_daily_ex_otc"
    assert result["officialExchangePublishedBreadth"] is False
    assert result["fullBreadthAuthority"] is False
    assert result["sourceAuthorityAllowed"] is True
    assert result["scoreContributionAllowed"] is True
    assert result["broadMarketClaimAllowed"] is False
    assert result["fulfilledMetrics"] == list(US_BREADTH_SYMBOLS)
    assert result["missingMetrics"] == []
    assert result["reasonCodes"] == []
    assert result["metrics"]["newHighs"] == 1
    assert result["metrics"]["newLows"] == 1
    assert result["metrics"]["highLowRatio"] == 1.0
    assert result["highLowLookbackSessions"] == 3
    assert result["highLowEligibleCount"] == 3
    assert result["highLowEligibleThreshold"] == 3
    assert diagnostic_summary(result)["fulfilledMetrics"] == list(US_BREADTH_SYMBOLS)


def test_insufficient_polygon_history_keeps_ad_fulfilled_and_high_low_fail_closed() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0, "h": 15.0, "l": 9.0},
        {"T": "BBB", "o": 20.0, "c": 18.0, "h": 21.0, "l": 17.0},
        {"T": "CCC", "o": 30.0, "c": 30.0, "h": 32.0, "l": 29.0},
    ])
    previous = _grouped_payload(_high_low_rows())

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        historical_payloads=_complete_high_low_history("2026-05-21", sessions=2),
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
        high_low_lookback_sessions=3,
        min_high_low_eligible_count=3,
    )

    assert result["comparisonBasis"] == "previous_close"
    assert result["sourceAuthorityAllowed"] is True
    assert result["scoreContributionAllowed"] is True
    assert result["fulfilledMetrics"] == [
        "ADVANCERS",
        "DECLINERS",
        "UNCHANGED",
        "ADVANCE_DECLINE_RATIO",
    ]
    assert {"NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"}.issubset(result["missingMetrics"])
    assert result["metrics"]["newHighs"] is None
    assert result["metrics"]["newLows"] is None
    assert result["metrics"]["highLowRatio"] is None
    assert result["reasonCodes"] == [POLYGON_HIGH_LOW_HISTORY_INSUFFICIENT_LOOKBACK_REASON]


def test_polygon_history_date_gap_keeps_high_low_fail_closed() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0, "h": 15.0, "l": 9.0},
        {"T": "BBB", "o": 20.0, "c": 18.0, "h": 21.0, "l": 17.0},
        {"T": "CCC", "o": 30.0, "c": 30.0, "h": 32.0, "l": 29.0},
    ])
    previous = _grouped_payload(_high_low_rows())
    gap_history = tuple(
        (history_date, _grouped_payload(_high_low_rows()))
        for history_date in ("2026-05-20", "2026-05-18", "2026-05-15")
    )

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        historical_payloads=gap_history,
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
        high_low_lookback_sessions=3,
        min_high_low_eligible_count=3,
    )

    assert result["fulfilledMetrics"] == [
        "ADVANCERS",
        "DECLINERS",
        "UNCHANGED",
        "ADVANCE_DECLINE_RATIO",
    ]
    assert result["reasonCodes"] == [POLYGON_HIGH_LOW_HISTORY_DATE_GAP_REASON]


def test_polygon_history_below_eligible_threshold_keeps_high_low_fail_closed() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0, "h": 15.0, "l": 9.0},
        {"T": "BBB", "o": 20.0, "c": 18.0, "h": 21.0, "l": 17.0},
        {"T": "CCC", "o": 30.0, "c": 30.0, "h": 32.0, "l": 29.0},
    ])
    previous = _grouped_payload(_high_low_rows())
    history = list(_complete_high_low_history("2026-05-21"))
    history[-1] = (
        history[-1][0],
        _grouped_payload(_high_low_rows(aaa_high=float("nan"))),
    )

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        historical_payloads=tuple(history),
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
        high_low_lookback_sessions=3,
        min_high_low_eligible_count=3,
    )

    assert result["highLowEligibleCount"] == 2
    assert result["highLowEligibleThreshold"] == 3
    assert result["reasonCodes"] == [POLYGON_HIGH_LOW_HISTORY_BELOW_THRESHOLD_REASON]


def test_mixed_source_polygon_history_keeps_high_low_fail_closed() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0, "h": 15.0, "l": 9.0},
        {"T": "BBB", "o": 20.0, "c": 18.0, "h": 21.0, "l": 17.0},
        {"T": "CCC", "o": 30.0, "c": 30.0, "h": 32.0, "l": 29.0},
    ])
    previous = _grouped_payload(_high_low_rows())
    history = list(_complete_high_low_history("2026-05-21"))
    history[1] = (history[1][0], {**history[1][1], "source": "yfinance_proxy"})

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        historical_payloads=tuple(history),
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
        high_low_lookback_sessions=3,
        min_high_low_eligible_count=3,
    )

    assert result["fulfilledMetrics"] == [
        "ADVANCERS",
        "DECLINERS",
        "UNCHANGED",
        "ADVANCE_DECLINE_RATIO",
    ]
    assert result["reasonCodes"] == [POLYGON_HIGH_LOW_HISTORY_MIXED_SOURCE_REASON]


def test_malformed_polygon_history_keeps_high_low_fail_closed() -> None:
    latest = _grouped_payload([
        {"T": "AAA", "o": 10.0, "c": 11.0, "h": 15.0, "l": 9.0},
        {"T": "BBB", "o": 20.0, "c": 18.0, "h": 21.0, "l": 17.0},
        {"T": "CCC", "o": 30.0, "c": 30.0, "h": 32.0, "l": 29.0},
    ])
    previous = _grouped_payload(_high_low_rows())
    history = list(_complete_high_low_history("2026-05-21"))
    history[1] = (history[1][0], {"status": "OK", "resultsCount": "bad", "results": []})

    result = compute_polygon_us_breadth(
        latest,
        previous_payload=previous,
        historical_payloads=tuple(history),
        observation_date="2026-05-21",
        previous_observation_date="2026-05-20",
        now=datetime(2026, 5, 22, 12, tzinfo=ZoneInfo("America/New_York")),
        min_coverage_count=3,
        high_low_lookback_sessions=3,
        min_high_low_eligible_count=3,
    )

    assert result["fulfilledMetrics"] == [
        "ADVANCERS",
        "DECLINERS",
        "UNCHANGED",
        "ADVANCE_DECLINE_RATIO",
    ]
    assert result["reasonCodes"] == [POLYGON_HIGH_LOW_HISTORY_MALFORMED_REASON]


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
        high_low_lookback_sessions=1,
    )

    assert calls == ["2026-05-21", "2026-05-20"]
    assert result["observationDate"] == "2026-05-21"
    assert result["previousObservationDate"] == "2026-05-20"
    assert result["comparisonBasis"] == "previous_close"
    assert result["sourceAuthorityAllowed"] is True
