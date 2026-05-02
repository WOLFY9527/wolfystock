from concurrent.futures import ThreadPoolExecutor
import time

from src.services.analysis_provider_planner import (
    AnalysisProviderExecutor,
    DataCategory,
    build_analysis_provider_plan,
)


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
