from src.services.analysis_provider_planner import (
    DataCategory,
    build_analysis_provider_plan,
)
from data_provider.base import DataFetcherManager


class _CnNameFetcher:
    name = "TushareFetcher"
    priority = 1

    def __init__(self):
        self.calls = []

    def get_stock_name(self, stock_code):
        self.calls.append(stock_code)
        return "CN fallback name"


def test_orcl_is_detected_as_us_and_does_not_plan_cn_name_providers():
    plan = build_analysis_provider_plan("ORCL", categories=[DataCategory.STOCK_NAME])

    assert plan.market == "us"
    assert plan.categories[DataCategory.STOCK_NAME].providers[0] == "fmp"
    assert not {"tushare", "pytdx", "baostock"} & set(plan.categories[DataCategory.STOCK_NAME].providers)


def test_cn_symbols_use_cn_providers_for_stock_name_and_quote():
    plan = build_analysis_provider_plan(
        "600519",
        categories=[DataCategory.STOCK_NAME, DataCategory.QUOTE],
    )

    assert plan.market == "cn"
    assert plan.categories[DataCategory.STOCK_NAME].providers[:3] == ["akshare", "tushare", "pytdx"]
    assert "baostock" in plan.categories[DataCategory.STOCK_NAME].providers
    assert "fmp" not in plan.categories[DataCategory.QUOTE].providers


def test_orcl_stock_name_lookup_does_not_call_cn_fetchers(monkeypatch):
    cn_fetcher = _CnNameFetcher()
    manager = DataFetcherManager(fetchers=[cn_fetcher])
    monkeypatch.setattr(manager, "get_realtime_quote", lambda _code: None)

    assert manager.get_stock_name("ORCL") == ""
    assert cn_fetcher.calls == []
