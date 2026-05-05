import time

import pytest

from src.services.analysis_provider_planner import (
    AnalysisProviderExecutor,
    DataCategory,
    ProviderQuotaExceeded,
    ProviderTimeout,
    build_analysis_provider_plan,
)
from src.services.llm_instrumentation import (
    reset_llm_event_counters,
    set_llm_event_sink,
    snapshot_llm_event_counters,
)


@pytest.fixture(autouse=True)
def reset_provider_counters():
    reset_llm_event_counters()
    set_llm_event_sink(None)
    yield
    set_llm_event_sink(None)
    reset_llm_event_counters()


def _events(name):
    return [entry for entry in snapshot_llm_event_counters() if entry["event"] == name]


def test_category_uses_only_primary_provider_when_primary_succeeds():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])

    result = executor.execute_category(
        plan.categories[DataCategory.QUOTE],
        symbol="ORCL",
        providers={
            "alpaca": lambda: calls.append("alpaca") or {"price": 100},
            "finnhub": lambda: calls.append("finnhub") or {"price": 101},
        },
    )

    assert result.data == {"price": 100}
    assert result.source_provider == "alpaca"
    assert result.is_fallback is False
    assert calls == ["alpaca"]


def test_fallback_provider_is_called_after_primary_timeout():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])

    result = executor.execute_category(
        plan.categories[DataCategory.QUOTE],
        symbol="ORCL",
        providers={
            "alpaca": lambda: calls.append("alpaca") or (_ for _ in ()).throw(ProviderTimeout("slow")),
            "finnhub": lambda: calls.append("finnhub") or {"price": 101},
        },
    )

    assert result.data == {"price": 101}
    assert result.source_provider == "finnhub"
    assert result.is_fallback is True
    assert calls == ["alpaca", "finnhub"]


def test_fallback_attempt_counter_preserves_provider_order():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])

    result = executor.execute_category(
        plan.categories[DataCategory.QUOTE],
        symbol="ORCL",
        providers={
            "alpaca": lambda: calls.append("alpaca") or {},
            "finnhub": lambda: calls.append("finnhub") or {"price": 101},
        },
    )

    assert result.source_provider == "finnhub"
    assert calls == ["alpaca", "finnhub"]
    fallback_events = _events("provider_fallback_attempt")
    assert len(fallback_events) == 1
    assert fallback_events[0]["labels"]["provider"] == "alpaca"
    assert fallback_events[0]["labels"]["retry_reason_bucket"] == "insufficient_payload"


def test_circuit_open_provider_is_skipped():
    calls = []
    executor = AnalysisProviderExecutor(failure_threshold=1, cooldown_seconds=60)
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])

    first = executor.execute_category(
        plan.categories[DataCategory.QUOTE],
        symbol="ORCL",
        providers={
            "alpaca": lambda: calls.append("alpaca") or (_ for _ in ()).throw(ProviderTimeout("slow")),
            "finnhub": lambda: calls.append("finnhub") or {"price": 101},
        },
    )
    second = executor.execute_category(
        plan.categories[DataCategory.QUOTE],
        symbol="ORCL",
        providers={
            "alpaca": lambda: calls.append("alpaca_again") or {"price": 102},
            "finnhub": lambda: calls.append("finnhub_again") or {"price": 103},
        },
    )

    assert first.source_provider == "finnhub"
    assert second.source_provider == "finnhub"
    assert "alpaca_again" not in calls
    assert calls[:2] == ["alpaca", "finnhub"]


def test_quota_errors_do_not_retry_same_provider_repeatedly():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.FUNDAMENTALS])

    result = executor.execute_category(
        plan.categories[DataCategory.FUNDAMENTALS],
        symbol="ORCL",
        providers={
            "fmp": lambda: calls.append("fmp") or (_ for _ in ()).throw(ProviderQuotaExceeded("429")),
            "finnhub": lambda: calls.append("finnhub") or {"pe": 20},
        },
    )

    assert result.source_provider == "finnhub"
    assert result.is_fallback is True
    assert calls == ["fmp", "finnhub"]


def test_timeout_emits_timeout_and_failed_counters_without_changing_fallback():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])

    result = executor.execute_category(
        plan.categories[DataCategory.QUOTE],
        symbol="ORCL",
        providers={
            "alpaca": lambda: calls.append("alpaca") or (_ for _ in ()).throw(ProviderTimeout("slow")),
            "finnhub": lambda: calls.append("finnhub") or {"price": 101},
        },
    )

    assert result.source_provider == "finnhub"
    assert calls == ["alpaca", "finnhub"]
    assert _events("provider_timeout")
    failed = _events("provider_call_failed")
    assert failed
    assert failed[0]["labels"]["error_bucket"] == "timeout"


def test_quota_risk_classification_emits_bounded_counter():
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.FUNDAMENTALS])

    result = executor.execute_category(
        plan.categories[DataCategory.FUNDAMENTALS],
        symbol="ORCL",
        providers={
            "fmp": lambda: (_ for _ in ()).throw(ProviderQuotaExceeded("429 raw provider body should not leak")),
            "finnhub": lambda: {"pe": 20},
        },
    )

    assert result.source_provider == "finnhub"
    quota_events = _events("provider_quota_risk_observed")
    assert len(quota_events) == 1
    assert quota_events[0]["labels"]["error_bucket"] == "rate_limited"
    assert "raw provider body" not in str(quota_events[0]["labels"])


def test_independent_categories_run_concurrently_and_duplicate_provider_category_is_lazy():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan(
        "ORCL",
        market="us",
        categories=[
            DataCategory.QUOTE,
            DataCategory.FUNDAMENTALS,
            DataCategory.NEWS,
            DataCategory.TECHNICAL_INDICATORS,
        ],
    )

    def slow(category, provider):
        def _call():
            calls.append((category, provider, "start", time.monotonic()))
            time.sleep(0.2)
            calls.append((category, provider, "end", time.monotonic()))
            return {category: provider}

        return _call

    started = time.monotonic()
    results = executor.execute_plan(
        plan,
        symbol="ORCL",
        providers_by_category={
            DataCategory.QUOTE: {
                "alpaca": slow("quote", "alpaca"),
                "finnhub": slow("quote", "finnhub"),
            },
            DataCategory.FUNDAMENTALS: {"fmp": slow("fundamentals", "fmp")},
            DataCategory.NEWS: {"gnews": slow("news", "gnews")},
            DataCategory.TECHNICAL_INDICATORS: {"fmp": slow("technical", "fmp")},
        },
        max_workers=4,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.55
    assert results[DataCategory.QUOTE].source_provider == "alpaca"
    assert ("quote", "finnhub", "start") not in [(c, p, s) for c, p, s, _ in calls]
    assert {category for category, _, state, _ in calls if state == "start"} == {
        "quote",
        "fundamentals",
        "news",
        "technical",
    }
