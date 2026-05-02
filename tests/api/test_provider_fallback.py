import time

from src.services.analysis_provider_planner import (
    AnalysisProviderExecutor,
    DataCategory,
    ProviderQuotaExceeded,
    ProviderTimeout,
    build_analysis_provider_plan,
)


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
