from concurrent.futures import ThreadPoolExecutor
import time

import pytest

from src.services.analysis_provider_planner import (
    AnalysisProviderExecutor,
    DataCategory,
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


def _event_counts():
    return {entry["event"]: entry["count"] for entry in snapshot_llm_event_counters()}


def test_same_provider_category_symbol_request_is_coalesced_when_concurrent():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.FUNDAMENTALS])
    category_plan = plan.categories[DataCategory.FUNDAMENTALS]

    def primary():
        calls.append("fmp")
        time.sleep(0.1)
        return {"pe": 21}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                executor.execute_category,
                category_plan,
                symbol="ORCL",
                providers={"fmp": primary},
            )
            for _ in range(2)
        ]
        results = [future.result() for future in futures]

    assert [result.data for result in results] == [{"pe": 21}, {"pe": 21}]
    assert calls == ["fmp"]


def test_cache_hit_avoids_second_real_provider_call():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])
    category_plan = plan.categories[DataCategory.QUOTE]

    def primary():
        calls.append("alpaca")
        return {"price": 100}

    first = executor.execute_category(
        category_plan,
        symbol="ORCL",
        providers={"alpaca": primary},
    )
    second = executor.execute_category(
        category_plan,
        symbol="ORCL",
        providers={"alpaca": primary},
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.data == {"price": 100}
    assert calls == ["alpaca"]


def test_provider_cache_hit_emits_counter_without_provider_call():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])
    category_plan = plan.categories[DataCategory.QUOTE]

    def primary():
        calls.append("alpaca")
        return {"price": 100}

    executor.execute_category(category_plan, symbol="ORCL", providers={"alpaca": primary})
    reset_llm_event_counters()

    result = executor.execute_category(category_plan, symbol="ORCL", providers={"alpaca": primary})

    assert result.cache_hit is True
    assert calls == ["alpaca"]
    counts = _event_counts()
    assert counts["provider_cache_hit"] == 1
    assert "provider_call_started" not in counts


def test_provider_cache_miss_emits_start_and_completed_on_success():
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])
    category_plan = plan.categories[DataCategory.QUOTE]

    result = executor.execute_category(
        category_plan,
        symbol="ORCL",
        providers={"alpaca": lambda: {"price": 100}},
    )

    assert result.source_provider == "alpaca"
    counts = _event_counts()
    assert counts["provider_cache_miss"] == 1
    assert counts["provider_duplicate_candidate_observed"] == 1
    assert counts["provider_call_started"] == 1
    assert counts["provider_call_completed"] == 1


def test_provider_inflight_join_emits_counter_without_duplicate_call():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.FUNDAMENTALS])
    category_plan = plan.categories[DataCategory.FUNDAMENTALS]

    def primary():
        calls.append("fmp")
        time.sleep(0.1)
        return {"pe": 21}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(executor.execute_category, category_plan, symbol="ORCL", providers={"fmp": primary})
            for _ in range(2)
        ]
        results = [future.result() for future in futures]

    assert [result.data for result in results] == [{"pe": 21}, {"pe": 21}]
    assert calls == ["fmp"]
    counts = _event_counts()
    assert counts["provider_inflight_join"] == 1


def test_provider_metric_sink_failure_is_swallowed():
    calls = []
    executor = AnalysisProviderExecutor()
    plan = build_analysis_provider_plan("ORCL", market="us", categories=[DataCategory.QUOTE])
    category_plan = plan.categories[DataCategory.QUOTE]

    def failing_sink(event_name, labels):
        calls.append((event_name, labels))
        raise RuntimeError("metric sink down")

    set_llm_event_sink(failing_sink)

    result = executor.execute_category(
        category_plan,
        symbol="ORCL",
        providers={"alpaca": lambda: {"price": 100}},
    )

    assert result.source_provider == "alpaca"
    assert calls
    assert _event_counts()["provider_call_started"] == 1
