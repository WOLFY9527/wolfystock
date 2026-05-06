# -*- coding: utf-8 -*-
import time
from concurrent.futures import ThreadPoolExecutor

from src.core.pipeline import _resolve_optional_enrichment
from src.services.analysis_provider_planner import (
    AnalysisProviderExecutor,
    CategoryProviderPlan,
    DataCategory,
    ProviderTimeout,
    build_fast_decision_provider_plan,
)
from src.services.data_criticality import build_data_quality_report, sanitize_reason_codes


def _quality_context(**overrides):
    base = {
        "realtime": {
            "price": 101.0,
            "pre_close": 100.0,
            "open_price": 100.5,
            "high": 102.0,
            "low": 99.5,
            "source": "fixture_quote",
            "market_timestamp": "2026-05-05T16:00:00-04:00",
        },
        "today": {"open": 100.5, "high": 102.0, "low": 99.5, "close": 101.0, "data_source": "fixture_history"},
        "yesterday": {"close": 100.0},
        "market_timestamp": "2026-05-05T16:00:00-04:00",
        "market_session_date": "2026-05-05",
        "report_generated_at": "2026-05-06T01:00:00+00:00",
        "session_type": "intraday_snapshot",
        "market_timezone": "America/New_York",
    }
    base.update(overrides)
    return base


def test_required_quote_and_candles_present_allows_decision_grade():
    report = build_data_quality_report(
        context=_quality_context(),
        data_quality={"missing_fields": [], "sentiment_status": "ok"},
        diagnostics={"news_status": "ok", "failure_reasons": []},
    ).to_api_dict()

    assert report["requiredAvailable"] is True
    assert report["dataQualityTier"] == "decision_grade"
    assert report["confidenceCap"] == 100


def test_required_data_missing_caps_insufficient_to_40():
    context = _quality_context(realtime={}, today={}, yesterday={})
    report = build_data_quality_report(
        context=context,
        data_quality={"missing_fields": []},
        diagnostics={"news_status": "ok"},
    ).to_api_dict()

    assert report["dataQualityTier"] == "insufficient"
    assert report["dataQualityScore"] <= 40
    assert report["confidenceCap"] <= 40
    assert "required_data_missing" in report["reasonCodes"]


def test_missing_fundamentals_caps_but_does_not_fail_when_required_exists():
    report = build_data_quality_report(
        context=_quality_context(),
        data_quality={"missing_fields": ["fundamentals.revenue", "fundamentals.eps"]},
        diagnostics={"news_status": "ok"},
    ).to_api_dict()

    assert report["requiredAvailable"] is True
    assert report["dataQualityTier"] == "analysis_grade"
    assert report["confidenceCap"] <= 70
    assert report["dataQualityTier"] != "insufficient"


def test_optional_news_timeout_does_not_block_quick_decision():
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(time.sleep, 0.2)
        started = time.monotonic()
        value, timed_out, reason = _resolve_optional_enrichment(future, 0.01)
        elapsed = time.monotonic() - started

    assert value is None
    assert timed_out is True
    assert reason == "timeout"
    assert elapsed < 0.1


def test_optional_enrichment_timeout_is_reported_as_pending_gap():
    report = build_data_quality_report(
        context=_quality_context(),
        data_quality={"missing_fields": [], "sentiment_status": "ok"},
        diagnostics={
            "news_status": "skipped",
            "sentiment_status": "ok",
            "fundamentals_status": "ok",
            "earnings_status": "ok",
            "failure_reasons": ["optional_news_timeout"],
        },
        optional_enrichment_pending=True,
    ).to_api_dict()

    assert report["requiredAvailable"] is True
    assert report["dataQualityTier"] == "decision_grade"
    assert report["enrichmentStatus"] == "pending"
    assert report["enrichmentSources"] == ["news", "sentiment", "detailed_fundamentals"]
    assert report["pendingSources"] == ["news"]
    assert report["completedSources"] == ["sentiment", "detailed_fundamentals"]
    assert report["failedSources"] == []
    assert "optional_enrichment_pending" in report["optionalMissing"]
    assert report["enrichmentReasons"]["news"] == ["optional_news_timeout"]


def test_optional_enrichment_failures_are_sanitized_non_blocking_gaps():
    report = build_data_quality_report(
        context=_quality_context(),
        data_quality={
            "missing_fields": ["detailed_fundamentals"],
            "sentiment_status": "failed",
        },
        diagnostics={
            "news_status": "failed",
            "sentiment_status": "failed",
            "sentiment_reason": "provider failed with api_key=sk-test-secret",
            "fundamentals_status": "failed",
            "earnings_status": "failed",
            "failure_reasons": [
                "optional_news_failed",
                "provider failed with api_key=sk-test-secret",
            ],
        },
    ).to_api_dict()

    assert report["requiredAvailable"] is True
    assert report["dataQualityTier"] == "decision_grade"
    assert report["enrichmentStatus"] == "failed"
    assert report["failedSources"] == ["news", "sentiment", "detailed_fundamentals"]
    assert "news" in report["optionalMissing"]
    assert "sentiment" in report["optionalMissing"]
    assert "detailed_fundamentals" in report["optionalMissing"]
    assert "redacted_sensitive_reason" in report["enrichmentReasons"]["sentiment"]
    assert "sk-test-secret" not in str(report)


def test_first_good_wins_does_not_wait_for_slow_fallback():
    executor = AnalysisProviderExecutor()
    called = {"fallback": False}
    plan = CategoryProviderPlan(
        category=DataCategory.QUOTE,
        providers=["primary", "slow_fallback"],
        timeout_seconds=0.05,
        cache_ttl_seconds=1,
        max_attempts=2,
    )

    result = executor.execute_category(
        plan,
        symbol="AAPL",
        providers={
            "primary": lambda: {"price": 101.0},
            "slow_fallback": lambda: called.__setitem__("fallback", True),
        },
    )

    assert result.source_provider == "primary"
    assert called["fallback"] is False


def test_repeated_timeout_enters_hot_path_cooldown_and_skips_provider():
    executor = AnalysisProviderExecutor(failure_threshold=2, cooldown_seconds=60)
    plan = CategoryProviderPlan(
        category=DataCategory.QUOTE,
        providers=["slow", "good"],
        timeout_seconds=0.01,
        cache_ttl_seconds=1,
        max_attempts=2,
    )

    def slow():
        time.sleep(0.1)
        return {"price": 1}

    providers = {"slow": slow, "good": lambda: {"price": 2}}
    assert executor.execute_category(plan, symbol="AAPL", providers=providers).source_provider == "good"
    assert executor.execute_category(plan, symbol="MSFT", providers=providers).source_provider == "good"

    snapshot = executor.hot_path_health_snapshot()
    assert "slow:quote" in snapshot["provider_cooldowns"]

    result = executor.execute_category(plan, symbol="ORCL", providers=providers)
    assert result.source_provider == "good"
    assert result.attempts[0]["provider"] == "slow"
    assert result.attempts[0]["status"] == "skipped"


def test_sanitized_reason_codes_do_not_leak_raw_secret_payloads():
    codes = sanitize_reason_codes([
        "provider failed with api_key=sk-test-secret and token abc",
        "timeout",
    ])

    serialized = " ".join(codes)
    assert "sk-test-secret" not in serialized
    assert "token abc" not in serialized
    assert "redacted_sensitive_reason" in codes
    assert "timeout" in codes


def test_fast_decision_plan_uses_bounded_hot_path_timeouts():
    plan = build_fast_decision_provider_plan(
        "AAPL",
        market="us",
        categories=[DataCategory.QUOTE, DataCategory.FUNDAMENTALS, DataCategory.NEWS],
    )

    assert plan.categories[DataCategory.QUOTE].timeout_seconds == 1.2
    assert plan.categories[DataCategory.FUNDAMENTALS].timeout_seconds == 2.5
    assert plan.categories[DataCategory.NEWS].timeout_seconds == 1.5
