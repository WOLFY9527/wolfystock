# -*- coding: utf-8 -*-
"""Regression tests that freeze current provider runtime contracts."""

from __future__ import annotations

import tempfile
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from data_provider.base import DataFetchError, DataFetcherManager, build_provider_route_evidence_contract
from data_provider.provider_credentials import ProviderCredentialBundle
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote
from src.repositories.stock_repo import StockRepository
from src.services.agent_stock_evidence_service import StockEvidenceService
from src.services.market_scanner_service import MarketScannerService
from src.services.stock_evidence_quote_adapter import (
    StockEvidenceQuoteAdapter,
    StockEvidenceQuoteSnapshot,
)
from src.services.stock_service_provider_adapter import (
    StockServiceProviderAdapter,
    StockServiceQuoteSnapshot,
)
from src.services.stock_service import StockService
from src.services.us_history_helper import (
    LOCAL_US_PARQUET_SOURCE,
    LocalUsHistoryLoadResult,
    fetch_daily_history_with_local_us_fallback,
)
from src.storage import DatabaseManager
from tests.test_market_scanner_service import (
    FakeHkScannerDataManager,
    FakeScannerDataManager,
    FakeUsScannerDataManager,
    StructuredScannerDataManager,
    seed_hk_local_history,
    seed_us_local_history,
)


class _RealtimeFetcher:
    def __init__(
        self,
        *,
        name: str,
        priority: int,
        quote: UnifiedRealtimeQuote | None = None,
        quotes_by_source: dict[str | None, UnifiedRealtimeQuote | None] | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self.quote = quote
        self.quotes_by_source = dict(quotes_by_source or {})
        self.calls: list[tuple[str, str | None]] = []

    def get_realtime_quote(self, stock_code: str, source: str | None = None):
        self.calls.append((stock_code, source))
        if self.quotes_by_source:
            return self.quotes_by_source.get(source)
        return self.quote


class _DailyHistoryFetcher:
    def __init__(
        self,
        *,
        name: str,
        priority: int,
        result=None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self.result = result
        self.error = error
        self.calls: list[dict[str, object]] = []

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        self.calls.append(
            {
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


class _RemoteNameFetcher:
    name = "RemoteNameFetcher"
    priority = 1

    def __init__(self, result: str = "远程名称") -> None:
        self.result = result
        self.calls: list[str] = []

    def get_stock_name(self, stock_code: str) -> str:
        self.calls.append(stock_code)
        return self.result


class _BoardWarningScannerDataManager(FakeScannerDataManager):
    def get_belong_boards(self, stock_code: str):
        raise RuntimeError(f"board lookup failed for {stock_code}")


def _realtime_config(*, enabled: bool, priority: str = "efinance,akshare_em,tushare") -> SimpleNamespace:
    return SimpleNamespace(
        enable_realtime_quote=enabled,
        realtime_source_priority=priority,
    )


def _in_memory_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


def test_provider_route_evidence_contract_normalizes_trace_and_mixed_source_provenance() -> None:
    contract = build_provider_route_evidence_contract(
        provider_family="market_realtime",
        route_family="cn_realtime_quote",
        trace_entries=[
            {
                "sequence": 1,
                "provider": "market_route",
                "action": "selected",
                "outcome": "ok",
                "status": "ok",
                "message": "CN market route selected: efinance -> akshare_em -> tushare",
            },
            {
                "sequence": 2,
                "provider": "efinance",
                "action": "succeeded",
                "outcome": "partial",
                "status": "partial",
                "reason": "supplement_required",
                "message": "raw provider response ignored",
            },
            {
                "sequence": 3,
                "provider": "akshare_em",
                "action": "succeeded",
                "outcome": "partial",
                "status": "partial",
                "message": "Supplemented fields from raw payload",
            },
            {
                "sequence": 4,
                "provider": "efinance",
                "action": "completed",
                "outcome": "ok",
                "status": "ok",
                "reason": "accepted_with_partial_fields",
            },
        ],
        source_confidence={
            "freshness": "fallback",
            "asOf": "2026-06-10T09:30:00+08:00",
            "isFallback": True,
            "isStale": True,
            "sourceAuthorityState": "diagnostic_observation_only",
        },
        cache_summary={"hit": True, "stale": True, "fallback": False},
    )

    assert contract["contractVersion"] == "provider_route_evidence_v1"
    assert contract["diagnosticOnly"] is True
    assert contract["advisoryOnly"] is True
    assert contract["liveEnforcement"] is False
    assert contract["externalProviderCalls"] is False
    assert contract["providerRuntimeChanged"] is False
    assert contract["marketCacheMutation"] is False
    assert contract["providerFamily"] == "market_realtime"
    assert contract["routeFamily"] == "cn_realtime_quote"
    assert contract["providerCallsExecuted"] is True
    assert contract["sourceAuthority"] == {
        "state": "diagnostic_observation_only",
        "allowed": False,
        "reasonCode": "advisory_only",
    }
    assert contract["freshness"] == {
        "state": "fallback",
        "asOf": "2026-06-10T09:30:00+08:00",
        "isFallback": True,
        "isStale": True,
    }
    assert contract["fallback"] == {
        "state": "mixed_source",
        "mixedSource": True,
        "fallbackObserved": True,
        "primaryProviderFamily": "efinance",
        "supplementalProviderFamilies": ["akshare_em"],
    }
    assert contract["cache"] == {
        "known": True,
        "hit": True,
        "stale": True,
        "fallback": False,
        "state": "hit_stale",
    }
    assert contract["routeTrace"] == [
        {
            "sequence": 1,
            "providerFamily": "market_route",
            "action": "selected",
            "outcome": "ok",
            "status": "ok",
            "reasonCode": None,
        },
        {
            "sequence": 2,
            "providerFamily": "efinance",
            "action": "succeeded",
            "outcome": "partial",
            "status": "partial",
            "reasonCode": "supplement_required",
        },
        {
            "sequence": 3,
            "providerFamily": "akshare_em",
            "action": "succeeded",
            "outcome": "partial",
            "status": "partial",
            "reasonCode": None,
        },
        {
            "sequence": 4,
            "providerFamily": "efinance",
            "action": "completed",
            "outcome": "ok",
            "status": "ok",
            "reasonCode": "accepted_with_partial_fields",
        },
    ]
    assert contract["mixedSourceProvenance"] == [
        {
            "providerFamily": "efinance",
            "role": "primary",
            "outcome": "partial",
            "status": "partial",
            "reasonCode": "supplement_required",
        },
        {
            "providerFamily": "akshare_em",
            "role": "supplemental",
            "outcome": "partial",
            "status": "partial",
            "reasonCode": None,
        },
    ]


def test_provider_route_evidence_contract_sanitizes_mixed_source_without_raw_payload_leakage() -> None:
    contract = build_provider_route_evidence_contract(
        provider_family="market realtime api_key=SECRET",
        route_family="cn quote route",
        trace_entries=[
            {
                "sequence": 1,
                "provider": "https://provider.example.test/feed?token=SECRET",
                "action": "failed",
                "outcome": "failed",
                "status": "failed",
                "reason": "raw_response api_key=SECRET close=123.45",
                "message": "Bearer SECRET raw payload should never be copied",
                "rawPayload": {"close": 123.45, "token": "SECRET"},
                "credentials": {"apiKey": "SECRET"},
            },
            {
                "sequence": 2,
                "provider": "safe_provider",
                "action": "succeeded",
                "outcome": "ok",
                "status": "ok",
                "reason": "accepted",
                "payload": {"price": 123.45},
            },
        ],
        source_confidence={
            "freshness": "fresh",
            "asOf": "2026-06-10T09:30:00+08:00",
            "rawPayload": {"token": "SECRET"},
        },
        mixed_source_provenance=[
            {
                "provider": "unsafe provider token=SECRET",
                "role": "primary",
                "outcome": "ok",
                "rawPayload": {"token": "SECRET"},
            },
            {
                "provider": "safe_provider",
                "role": "supplemental",
                "outcome": "partial",
                "responseBody": "close=123.45 token=SECRET",
            },
        ],
    )

    serialized = json.dumps(contract, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "SECRET",
        "api_key",
        "token",
        "Bearer",
        "raw payload",
        "rawPayload",
        "responseBody",
        "credentials",
        "123.45",
        "provider.example.test",
    ):
        assert forbidden not in serialized
    assert contract["providerFamily"] == "diagnostic_ref_redacted"
    assert contract["routeTrace"][0]["providerFamily"] == "diagnostic_ref_redacted"
    assert contract["routeTrace"][0]["reasonCode"] == "diagnostic_ref_redacted"
    assert contract["mixedSourceProvenance"][0]["providerFamily"] == "diagnostic_ref_redacted"
    assert contract["mixedSourceProvenance"][1]["providerFamily"] == "safe_provider"


def test_provider_route_evidence_contract_defaults_to_advisory_and_does_not_execute_runtime_calls() -> None:
    provider_call = MagicMock(side_effect=AssertionError("provider call executed"))
    cache_refresh = MagicMock(side_effect=AssertionError("cache refresh executed"))

    runtime_guards = [
        patch.object(DataFetcherManager, "_get_alpaca_fetcher", side_effect=AssertionError("alpaca called")),
        patch.object(DataFetcherManager, "_get_twelve_data_fetcher", side_effect=AssertionError("twelve data called")),
        patch.object(DataFetcherManager, "_get_tickflow_fetcher", side_effect=AssertionError("tickflow called")),
        patch.object(DataFetcherManager, "_get_cached_cn_stock_list", side_effect=AssertionError("stock cache read")),
        patch.object(DataFetcherManager, "_put_cached_cn_stock_list", side_effect=AssertionError("stock cache write")),
        patch.object(DataFetcherManager, "_get_cached_cn_realtime_snapshot", side_effect=AssertionError("snapshot cache read")),
        patch.object(DataFetcherManager, "_put_cached_cn_realtime_snapshot", side_effect=AssertionError("snapshot cache write")),
        patch.object(DataFetcherManager, "get_realtime_quote", side_effect=AssertionError("realtime called")),
        patch.object(DataFetcherManager, "get_daily_data", side_effect=AssertionError("daily called")),
    ]
    with (
        runtime_guards[0] as alpaca_guard,
        runtime_guards[1] as twelve_data_guard,
        runtime_guards[2] as tickflow_guard,
        runtime_guards[3] as stock_cache_read_guard,
        runtime_guards[4] as stock_cache_write_guard,
        runtime_guards[5] as snapshot_cache_read_guard,
        runtime_guards[6] as snapshot_cache_write_guard,
        runtime_guards[7] as realtime_guard,
        runtime_guards[8] as daily_guard,
    ):
        contract = build_provider_route_evidence_contract(
            provider_family="market_realtime",
            route_family="us_realtime_quote",
            trace_entries=[
                {
                    "sequence": 1,
                    "provider": "alpaca",
                    "action": "skipped",
                    "outcome": "not_configured",
                    "status": "not_configured",
                    "reason": "provider_not_configured",
                    "runtimeCall": provider_call,
                }
            ],
            cache_summary={
                "hit": False,
                "stale": False,
                "fallback": False,
                "refresh": cache_refresh,
            },
        )

    provider_call.assert_not_called()
    cache_refresh.assert_not_called()
    for guard in (
        alpaca_guard,
        twelve_data_guard,
        tickflow_guard,
        stock_cache_read_guard,
        stock_cache_write_guard,
        snapshot_cache_read_guard,
        snapshot_cache_write_guard,
        realtime_guard,
        daily_guard,
    ):
        guard.assert_not_called()
    assert contract["advisoryOnly"] is True
    assert contract["liveEnforcement"] is False
    assert contract["sourceAuthority"]["allowed"] is False
    assert contract["providerCallsExecuted"] is False
    assert contract["externalProviderCalls"] is False
    assert contract["providerRuntimeChanged"] is False
    assert contract["marketCacheMutation"] is False


def test_realtime_quote_disabled_returns_none_with_normalized_trace_shape() -> None:
    manager = DataFetcherManager(fetchers=[])

    with patch("src.config.get_config", return_value=_realtime_config(enabled=False)):
        quote = manager.get_realtime_quote("600519")

    assert quote is None
    assert manager.get_last_realtime_quote_trace() == [
        {
            "sequence": 1,
            "provider": "market_realtime",
            "action": "skipped",
            "outcome": "not_configured",
            "status": "not_configured",
            "reason": "enable_realtime_quote_disabled",
            "message": "Realtime quote is disabled by config.",
        }
    ]


def test_cn_quote_keeps_first_success_and_only_merges_missing_supplementary_fields() -> None:
    primary = UnifiedRealtimeQuote(
        code="600519",
        name="贵州茅台",
        source=RealtimeSource.EFINANCE,
        price=1700.0,
        amplitude=3.5,
    )
    secondary = UnifiedRealtimeQuote(
        code="600519",
        name="次级名称",
        source=RealtimeSource.AKSHARE_EM,
        price=9999.0,
        amplitude=9.9,
        volume_ratio=1.7,
        turnover_rate=2.6,
    )
    manager = DataFetcherManager(
        fetchers=[
            _RealtimeFetcher(name="EfinanceFetcher", priority=1, quote=primary),
            _RealtimeFetcher(
                name="AkshareFetcher",
                priority=2,
                quotes_by_source={"em": secondary},
            ),
            _RealtimeFetcher(
                name="TushareFetcher",
                priority=3,
                quote=UnifiedRealtimeQuote(
                    code="600519",
                    name="第三来源",
                    source=RealtimeSource.TUSHARE,
                    price=1.0,
                ),
            ),
        ]
    )

    with patch("src.config.get_config", return_value=_realtime_config(enabled=True)):
        quote = manager.get_realtime_quote("SH600519")

    assert quote is not None
    assert quote.code == "600519"
    assert quote.name == "贵州茅台"
    assert quote.source == RealtimeSource.EFINANCE
    assert quote.price == 1700.0
    assert quote.amplitude == 3.5
    assert quote.volume_ratio == 1.7
    assert quote.turnover_rate == 2.6

    trace = manager.get_last_realtime_quote_trace()
    assert trace[0]["provider"] == "market_route"
    assert trace[0]["message"] == "CN market route selected: efinance -> akshare_em -> tushare"
    assert any(
        item["provider"] == "akshare_em"
        and item["action"] == "succeeded"
        and item["outcome"] == "partial"
        and "volume_ratio, turnover_rate" in str(item["message"] or "")
        for item in trace
    )
    assert trace[-1] == {
        "sequence": 9,
        "provider": "efinance",
        "action": "completed",
        "outcome": "ok",
        "status": "ok",
        "reason": "accepted_with_partial_fields",
        "message": "Final market source accepted: efinance (partial fields).",
    }


def test_us_realtime_trace_records_alpaca_fallback_to_yfinance_without_cn_or_hk_calls() -> None:
    yfinance = _RealtimeFetcher(
        name="YfinanceFetcher",
        priority=4,
        quote=UnifiedRealtimeQuote(
            code="AAPL",
            name="Apple",
            source=RealtimeSource.YFINANCE,
            price=210.5,
        ),
    )
    efinance = _RealtimeFetcher(
        name="EfinanceFetcher",
        priority=1,
        quote=UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.EFINANCE, price=1.0),
    )
    akshare = _RealtimeFetcher(
        name="AkshareFetcher",
        priority=2,
        quote=UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.AKSHARE_EM, price=1.0),
    )
    tushare = _RealtimeFetcher(
        name="TushareFetcher",
        priority=3,
        quote=UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.TUSHARE, price=1.0),
    )
    alpaca = _RealtimeFetcher(name="AlpacaFetcher", priority=0, quote=None)
    manager = DataFetcherManager(fetchers=[efinance, akshare, tushare, yfinance])

    with (
        patch("src.config.get_config", return_value=_realtime_config(enabled=True)),
        patch(
            "data_provider.base.get_provider_credentials",
            return_value=ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="configured_id",
                secret_key="configured_pair",
                extras={"data_feed": "iex"},
            ),
        ),
        patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca),
        patch.object(
            manager,
            "_get_twelve_data_fetcher",
            side_effect=AssertionError("US realtime must not construct HK Twelve Data fetcher"),
        ),
    ):
        quote = manager.get_realtime_quote("AAPL")

    assert quote is not None
    assert quote.source == RealtimeSource.YFINANCE
    assert alpaca.calls == [("AAPL", None)]
    assert yfinance.calls == [("AAPL", None)]
    assert efinance.calls == []
    assert akshare.calls == []
    assert tushare.calls == []

    trace = manager.get_last_realtime_quote_trace()
    assert trace == [
        {
            "sequence": 1,
            "provider": "market_route",
            "action": "selected",
            "outcome": "ok",
            "status": "ok",
            "reason": None,
            "message": "US stock route selected: alpaca -> yfinance.",
        },
        {
            "sequence": 2,
            "provider": "alpaca",
            "action": "attempting",
            "outcome": "unknown",
            "status": "unknown",
            "reason": None,
            "message": "Attempting realtime quote from alpaca for AAPL.",
        },
        {
            "sequence": 3,
            "provider": "alpaca",
            "action": "failed",
            "outcome": "empty_result",
            "status": "empty_result",
            "reason": "provider_returned_none",
            "message": "Provider returned no realtime quote.",
        },
        {
            "sequence": 4,
            "provider": "yfinance",
            "action": "attempting",
            "outcome": "unknown",
            "status": "unknown",
            "reason": None,
            "message": "Attempting realtime quote from yfinance for AAPL.",
        },
        {
            "sequence": 5,
            "provider": "yfinance",
            "action": "succeeded",
            "outcome": "ok",
            "status": "ok",
            "reason": None,
            "message": "Realtime quote accepted from yfinance.",
        },
    ]

    contract = build_provider_route_evidence_contract(
        provider_family="market_realtime",
        route_family="us_realtime_quote",
        trace_entries=trace,
    )
    assert contract["advisoryOnly"] is True
    assert contract["liveEnforcement"] is False
    assert contract["noExternalCalls"] is True
    assert contract["externalProviderCalls"] is False
    assert contract["providerRuntimeChanged"] is False
    assert contract["marketCacheMutation"] is False
    assert contract["routeTrace"][0]["providerFamily"] == "market_route"
    assert [item["providerFamily"] for item in contract["routeTrace"][1:]] == [
        "alpaca",
        "alpaca",
        "yfinance",
        "yfinance",
    ]


def test_hk_realtime_trace_records_twelve_data_fallback_to_akshare_hk_without_cn_or_us_calls() -> None:
    twelve_data = _RealtimeFetcher(name="TwelveDataFetcher", priority=0, quote=None)
    akshare = _RealtimeFetcher(
        name="AkshareFetcher",
        priority=2,
        quote=UnifiedRealtimeQuote(
            code="HK01810",
            name="Xiaomi",
            source=RealtimeSource.TWELVE_DATA,
            price=44.2,
        ),
    )
    efinance = _RealtimeFetcher(
        name="EfinanceFetcher",
        priority=1,
        quote=UnifiedRealtimeQuote(code="HK01810", source=RealtimeSource.EFINANCE, price=1.0),
    )
    tushare = _RealtimeFetcher(
        name="TushareFetcher",
        priority=3,
        quote=UnifiedRealtimeQuote(code="HK01810", source=RealtimeSource.TUSHARE, price=1.0),
    )
    manager = DataFetcherManager(fetchers=[efinance, akshare, tushare])

    with (
        patch("src.config.get_config", return_value=_realtime_config(enabled=True)),
        patch(
            "data_provider.base.get_provider_credentials",
            side_effect=AssertionError("HK realtime must not inspect US Alpaca credentials"),
        ),
        patch.object(manager, "_get_twelve_data_fetcher", return_value=twelve_data),
        patch.object(
            manager,
            "_get_alpaca_fetcher",
            side_effect=AssertionError("HK realtime must not construct US Alpaca fetcher"),
        ),
    ):
        quote = manager.get_realtime_quote("1810.HK")

    assert quote is not None
    assert quote.price == 44.2
    assert twelve_data.calls == [("HK01810", None)]
    assert akshare.calls == [("HK01810", "hk")]
    assert efinance.calls == []
    assert tushare.calls == []

    trace = manager.get_last_realtime_quote_trace()
    assert trace == [
        {
            "sequence": 1,
            "provider": "market_route",
            "action": "selected",
            "outcome": "ok",
            "status": "ok",
            "reason": None,
            "message": "HK route selected: twelve_data -> akshare_hk.",
        },
        {
            "sequence": 2,
            "provider": "twelve_data",
            "action": "attempting",
            "outcome": "unknown",
            "status": "unknown",
            "reason": None,
            "message": "Attempting realtime quote from twelve_data for HK01810.",
        },
        {
            "sequence": 3,
            "provider": "twelve_data",
            "action": "failed",
            "outcome": "empty_result",
            "status": "empty_result",
            "reason": "provider_returned_none",
            "message": "Provider returned no realtime quote.",
        },
        {
            "sequence": 4,
            "provider": "akshare_hk",
            "action": "attempting",
            "outcome": "unknown",
            "status": "unknown",
            "reason": None,
            "message": "Attempting realtime quote from akshare_hk for HK01810.",
        },
        {
            "sequence": 5,
            "provider": "akshare_hk",
            "action": "succeeded",
            "outcome": "ok",
            "status": "ok",
            "reason": None,
            "message": "Realtime quote accepted from akshare_hk.",
        },
    ]

    contract = build_provider_route_evidence_contract(
        provider_family="market_realtime",
        route_family="hk_realtime_quote",
        trace_entries=trace,
        source_confidence={"freshness": "fallback", "isFallback": True},
    )
    assert contract["advisoryOnly"] is True
    assert contract["liveEnforcement"] is False
    assert contract["noExternalCalls"] is True
    assert contract["externalProviderCalls"] is False
    assert contract["providerRuntimeChanged"] is False
    assert contract["marketCacheMutation"] is False
    assert contract["fallback"]["state"] == "fallback"
    assert contract["routeTrace"][2]["providerFamily"] == "twelve_data"
    assert contract["routeTrace"][2]["outcome"] == "empty_result"
    assert contract["routeTrace"][-1]["providerFamily"] == "akshare_hk"


def test_unified_realtime_quote_shape_filters_none_and_requires_positive_price() -> None:
    quote = UnifiedRealtimeQuote(
        code="AAPL",
        name="Apple",
        source=RealtimeSource.YFINANCE,
        price=212.8,
        change_pct=6.72,
        volume=None,
        amount=7.72e9,
    )

    assert quote.to_dict() == {
        "code": "AAPL",
        "name": "Apple",
        "source": "yfinance",
        "price": 212.8,
        "change_pct": 6.72,
        "amount": 7.72e9,
    }
    assert quote.has_basic_data() is True
    assert UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=0.0).has_basic_data() is False
    assert UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=None).has_basic_data() is False


def test_us_history_local_hit_bypasses_manager_and_preserves_df_source_contract() -> None:
    local_df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})
    manager = MagicMock()

    with patch(
        "src.services.us_history_helper.load_local_us_daily_history",
        return_value=LocalUsHistoryLoadResult(
            stock_code="AAPL",
            path=Path("/tmp/AAPL.parquet"),
            status="hit",
            dataframe=local_df,
        ),
    ):
        df, source = fetch_daily_history_with_local_us_fallback(
            "AAPL",
            days=20,
            manager=manager,
            log_context="[provider runtime contract]",
        )

    assert df is local_df
    assert source == LOCAL_US_PARQUET_SOURCE
    manager.get_daily_data.assert_not_called()


def test_us_history_remote_fallback_preserves_normalized_symbol_dates_and_source_label() -> None:
    fallback_df = pd.DataFrame({"date": ["2024-01-02"], "close": [101.5]})
    manager = MagicMock()
    manager.get_daily_data.return_value = (fallback_df, "YfinanceFetcher")

    with patch(
        "src.services.us_history_helper.load_local_us_daily_history",
        return_value=LocalUsHistoryLoadResult(
            stock_code="AAPL",
            path=Path("/tmp/AAPL.parquet"),
            status="missing",
        ),
    ):
        df, source = fetch_daily_history_with_local_us_fallback(
            "aapl",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            days=20,
            manager=manager,
            log_context="[provider runtime contract]",
        )

    assert df is fallback_df
    assert source == "YfinanceFetcher"
    manager.get_daily_data.assert_called_once_with(
        stock_code="AAPL",
        start_date="2024-01-01",
        end_date="2024-01-31",
        days=20,
    )


def test_us_daily_history_trace_records_alpaca_failure_then_yfinance_fallback_without_hk_or_cn_calls() -> None:
    daily_frame = pd.DataFrame(
        [
            {"date": "2026-05-01", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.5},
        ]
    )
    yfinance = _DailyHistoryFetcher(
        name="YfinanceFetcher",
        priority=4,
        result=(daily_frame, "YfinanceFetcher"),
    )
    efinance = _DailyHistoryFetcher(
        name="EfinanceFetcher",
        priority=1,
        result=(daily_frame, "EfinanceFetcher"),
    )
    akshare = _DailyHistoryFetcher(
        name="AkshareFetcher",
        priority=2,
        result=(daily_frame, "AkshareFetcher"),
    )
    alpaca = _DailyHistoryFetcher(
        name="AlpacaFetcher",
        priority=0,
        error=TimeoutError("alpaca timeout"),
    )
    manager = DataFetcherManager(fetchers=[efinance, akshare, yfinance])

    with (
        patch(
            "data_provider.base.get_provider_credentials",
            return_value=ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="configured_id",
                secret_key="configured_pair",
                extras={"data_feed": "iex"},
            ),
        ),
        patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca),
        patch.object(
            manager,
            "_get_twelve_data_fetcher",
            side_effect=AssertionError("US daily history must not construct HK Twelve Data fetcher"),
        ),
    ):
        frame, source = manager.get_daily_data("AAPL", days=20)

    assert frame is daily_frame
    assert source == "YfinanceFetcher"
    assert alpaca.calls == [
        {"stock_code": "AAPL", "start_date": None, "end_date": None, "days": 20},
    ]
    assert yfinance.calls == [
        {"stock_code": "AAPL", "start_date": None, "end_date": None, "days": 20},
    ]
    assert efinance.calls == []
    assert akshare.calls == []

    trace = manager.get_last_daily_history_trace()
    assert trace == [
        {
            "sequence": 1,
            "provider": "market_route",
            "action": "selected",
            "outcome": "ok",
            "status": "ok",
            "reason": None,
            "message": "US daily history route selected: AlpacaFetcher -> YfinanceFetcher.",
        },
        {
            "sequence": 2,
            "provider": "AlpacaFetcher",
            "action": "attempting",
            "outcome": "unknown",
            "status": "unknown",
            "reason": None,
            "message": "Attempting daily history from AlpacaFetcher for AAPL.",
        },
        {
            "sequence": 3,
            "provider": "AlpacaFetcher",
            "action": "failed",
            "outcome": "timeout",
            "status": "timeout",
            "reason": "alpaca timeout",
            "message": "Daily history failed on AlpacaFetcher: alpaca timeout",
        },
        {
            "sequence": 4,
            "provider": "YfinanceFetcher",
            "action": "attempting",
            "outcome": "unknown",
            "status": "unknown",
            "reason": None,
            "message": "Attempting daily history from YfinanceFetcher for AAPL.",
        },
        {
            "sequence": 5,
            "provider": "YfinanceFetcher",
            "action": "succeeded",
            "outcome": "ok",
            "status": "ok",
            "reason": None,
            "message": "Daily history accepted from YfinanceFetcher: rows=1.",
        },
    ]

    contract = build_provider_route_evidence_contract(
        provider_family="market_history",
        route_family="us_daily_history",
        trace_entries=trace,
        source_confidence={"freshness": "fallback", "isFallback": True},
    )
    assert contract["advisoryOnly"] is True
    assert contract["liveEnforcement"] is False
    assert contract["noExternalCalls"] is True
    assert contract["externalProviderCalls"] is False
    assert contract["providerRuntimeChanged"] is False
    assert contract["marketCacheMutation"] is False
    assert contract["fallback"]["state"] == "fallback"
    assert contract["routeTrace"][2]["providerFamily"] == "alpacafetcher"
    assert contract["routeTrace"][2]["outcome"] == "timeout"
    assert contract["routeTrace"][-1]["providerFamily"] == "yfinancefetcher"


def test_stock_service_history_payload_preserves_aggregation_shape() -> None:
    daily_df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-01"),
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
                "amount": 10200,
                "pct_chg": 2.0,
            },
            {
                "date": pd.Timestamp("2024-01-02"),
                "open": 10.2,
                "high": 10.8,
                "low": 10.1,
                "close": 10.6,
                "volume": 1200,
                "amount": 12720,
                "pct_chg": 3.92,
            },
        ]
    )
    manager = SimpleNamespace(get_stock_name=lambda stock_code: "Apple")

    with (
        patch("data_provider.base.DataFetcherManager", return_value=manager),
        patch(
            "src.services.stock_service.fetch_daily_history_with_local_us_fallback",
            return_value=(daily_df, LOCAL_US_PARQUET_SOURCE),
        ),
    ):
        payload = StockService().get_history_data("AAPL", period="daily", days=2)

    assert payload["stock_code"] == "AAPL"
    assert payload["stock_name"] == "Apple"
    assert payload["period"] == "daily"
    assert payload["source"] == LOCAL_US_PARQUET_SOURCE
    assert payload["diagnostics"]["status"] == "ok"
    assert payload["sourceConfidence"]["source"] == LOCAL_US_PARQUET_SOURCE
    assert payload["sourceConfidence"]["freshness"] == "fallback"
    assert payload["sourceConfidence"]["isFallback"] is True
    assert payload["sourceConfidence"]["confidenceWeight"] == 0.4
    assert payload["sourceConfidence"]["capReason"] == "fallback_source"
    assert payload["data"] == [
        {
            "date": "2024-01-01",
            "open": 10.0,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1000.0,
            "amount": 10200.0,
            "change_percent": 2.0,
        },
        {
            "date": "2024-01-02",
            "open": 10.2,
            "high": 10.8,
            "low": 10.1,
            "close": 10.6,
            "volume": 1200.0,
            "amount": 12720.0,
            "change_percent": 3.92,
        },
    ]


def _stock_daily_row(
    *,
    code: str,
    trade_date: date,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000.0,
    amount: float = 100000.0,
    pct_chg: float = 0.5,
    data_source: str = "LocalWarmCache",
) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        date=trade_date,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        pct_chg=pct_chg,
        data_source=data_source,
    )


def test_stock_service_us_daily_history_uses_persisted_rows_after_provider_failures_for_core_symbols() -> None:
    provider_trace = [
        {
            "sequence": 1,
            "provider": "AlpacaFetcher",
            "action": "failed",
            "outcome": "failed",
            "status": "failed",
            "reason": "EOF occurred in violation of protocol",
            "message": "Daily history failed on AlpacaFetcher: EOF occurred in violation of protocol",
        },
        {
            "sequence": 2,
            "provider": "YfinanceFetcher",
            "action": "failed",
            "outcome": "empty_result",
            "status": "empty_result",
            "reason": "provider_returned_empty_history",
            "message": "Provider returned no daily history for ORCL.",
        },
    ]

    class _RepoStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def get_recent_daily_rows(self, *, code: str, limit: int):
            self.calls.append((code, limit))
            return [
                _stock_daily_row(
                    code=code,
                    trade_date=date(2026, 5, 14),
                    open_price=100.0,
                    high=102.0,
                    low=99.5,
                    close=101.0,
                ),
                _stock_daily_row(
                    code=code,
                    trade_date=date(2026, 5, 15),
                    open_price=101.0,
                    high=103.0,
                    low=100.5,
                    close=102.25,
                ),
            ]

    for symbol in ("ORCL", "AAPL", "MSFT", "NVDA"):
        repo = _RepoStub()
        manager = SimpleNamespace(
            get_stock_name=lambda stock_code: f"{stock_code} Inc.",
            get_last_daily_history_trace=lambda: provider_trace,
        )
        provider_error = DataFetchError(
            f"美股/美股指数 {symbol} 获取失败:\n"
            "[AlpacaFetcher] (SSLEOFError) EOF occurred in violation of protocol\n"
            f"[YfinanceFetcher] (DataFetchError) Yahoo Finance 未查询到 {symbol} 的数据"
        )

        with (
            patch("src.services.stock_service.StockRepository", return_value=repo),
            patch("data_provider.base.DataFetcherManager", return_value=manager),
            patch(
                "src.services.stock_service.fetch_daily_history_with_local_us_fallback",
                side_effect=provider_error,
            ),
        ):
            payload = StockService().get_history_data(symbol, period="daily", days=365)

        assert payload["stock_code"] == symbol
        assert payload["stock_name"] == f"{symbol} Inc."
        assert payload["source"] == "local_db"
        assert payload["diagnostics"]["status"] == "degraded"
        assert payload["diagnostics"]["reason"] == "provider_failed_local_db_fallback"
        assert payload["diagnostics"]["localFallback"]["rows"] == 2
        assert payload["sourceConfidence"]["source"] == "local_db"
        assert payload["sourceConfidence"]["freshness"] == "fallback"
        assert payload["sourceConfidence"]["isFallback"] is True
        assert payload["sourceConfidence"]["confidenceWeight"] == 0.4
        assert payload["sourceConfidence"]["capReason"] == "fallback_source"
        assert len(payload["data"]) == 2
        assert payload["data"][0]["open"] == 100.0
        assert payload["data"][1]["close"] == 102.25
        assert repo.calls == [(symbol, 365)]


def test_stock_service_us_daily_history_reports_unavailable_without_fake_ohlc_when_providers_and_local_fail() -> None:
    provider_trace = [
        {
            "sequence": 1,
            "provider": "AlpacaFetcher",
            "action": "failed",
            "outcome": "failed",
            "status": "failed",
            "reason": "EOF occurred in violation of protocol",
            "message": "Daily history failed on AlpacaFetcher: EOF occurred in violation of protocol",
        },
        {
            "sequence": 2,
            "provider": "YfinanceFetcher",
            "action": "failed",
            "outcome": "empty_result",
            "status": "empty_result",
            "reason": "provider_returned_empty_history",
            "message": "Provider returned no daily history for ORCL.",
        },
    ]
    repo = SimpleNamespace(get_recent_daily_rows=MagicMock(return_value=[]))
    manager = SimpleNamespace(
        get_stock_name=lambda stock_code: "Oracle",
        get_last_daily_history_trace=lambda: provider_trace,
    )
    provider_error = DataFetchError(
        "美股/美股指数 ORCL 获取失败:\n"
        "[AlpacaFetcher] (SSLEOFError) EOF occurred in violation of protocol\n"
        "[YfinanceFetcher] (DataFetchError) Yahoo Finance 未查询到 ORCL 的数据"
    )

    with (
        patch("src.services.stock_service.StockRepository", return_value=repo),
        patch("data_provider.base.DataFetcherManager", return_value=manager),
        patch(
            "src.services.stock_service.fetch_daily_history_with_local_us_fallback",
            side_effect=provider_error,
        ),
    ):
        payload = StockService().get_history_data("ORCL", period="daily", days=365)

    assert payload["stock_code"] == "ORCL"
    assert payload["stock_name"] == "Oracle"
    assert payload["data"] == []
    assert payload["source"] == "unavailable"
    assert payload["diagnostics"]["status"] == "unavailable"
    assert payload["diagnostics"]["reason"] == "us_daily_history_unavailable"
    assert payload["diagnostics"]["providerTrace"] == provider_trace
    assert payload["sourceConfidence"]["freshness"] == "unavailable"
    assert payload["sourceConfidence"]["isUnavailable"] is True
    assert payload["sourceConfidence"]["confidenceWeight"] == 0.0
    assert payload["sourceConfidence"]["capReason"] == "unavailable_source"
    repo.get_recent_daily_rows.assert_called_once_with(code="ORCL", limit=365)


def test_stock_name_lookup_prefers_cache_before_realtime_and_remote_fetchers() -> None:
    manager = DataFetcherManager.__new__(DataFetcherManager)
    manager._stock_name_cache = {"600519": "缓存名称"}
    manager._fetchers = [_RemoteNameFetcher()]
    manager.get_realtime_quote = MagicMock(
        return_value=UnifiedRealtimeQuote(
            code="600519",
            name="实时名称",
            source=RealtimeSource.EFINANCE,
            price=1700.0,
        )
    )

    name = DataFetcherManager.get_stock_name(manager, "600519")

    assert name == "缓存名称"
    manager.get_realtime_quote.assert_not_called()
    assert manager._fetchers[0].calls == []


def test_stock_name_lookup_uses_realtime_only_when_enabled() -> None:
    manager = DataFetcherManager.__new__(DataFetcherManager)
    manager._fetchers = []
    manager.get_realtime_quote = MagicMock(
        return_value=UnifiedRealtimeQuote(
            code="NVDA",
            name="NVIDIA",
            source=RealtimeSource.YFINANCE,
            price=964.0,
        )
    )

    name = DataFetcherManager.get_stock_name(manager, "NVDA", allow_realtime=True)

    assert name == "NVIDIA"
    manager.get_realtime_quote.assert_called_once_with("NVDA")


def test_stock_name_lookup_short_circuits_us_symbols_to_empty_without_cn_fetchers() -> None:
    manager = DataFetcherManager.__new__(DataFetcherManager)
    remote_fetcher = _RemoteNameFetcher(result="CN fallback name")
    manager._fetchers = [remote_fetcher]
    manager.get_realtime_quote = MagicMock()

    name = DataFetcherManager.get_stock_name(manager, "ORCL", allow_realtime=False)

    assert name == ""
    manager.get_realtime_quote.assert_not_called()
    assert remote_fetcher.calls == []


def test_validate_ticker_exists_accepts_meaningful_quote_name_after_placeholder_lookup() -> None:
    manager = SimpleNamespace(
        get_stock_name=lambda stock_code, allow_realtime=False: "待确认股票",
        get_realtime_quote=lambda stock_code: UnifiedRealtimeQuote(
            code=stock_code,
            name="NVIDIA",
            source=RealtimeSource.YFINANCE,
            price=964.0,
        ),
    )

    with patch("data_provider.base.DataFetcherManager", return_value=manager):
        result = StockService().validate_ticker_exists("NVDA")

    assert result == {
        "stock_code": "NVDA",
        "exists": True,
        "stock_name": "NVIDIA",
    }


def test_stock_service_provider_adapter_returns_service_facing_quote_snapshot() -> None:
    adapter = StockServiceProviderAdapter(
        manager_factory=lambda: SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_amount=2.35,
                change_pct=1.11,
                open_price=213.0,
                high=215.0,
                low=212.5,
                pre_close=212.2,
                volume=1000.0,
                amount=214550.0,
            )
        )
    )

    snapshot = adapter.get_quote_snapshot("AAPL")

    assert snapshot == StockServiceQuoteSnapshot(
        stock_code="AAPL",
        stock_name="Apple",
        current_price=214.55,
        change=2.35,
        change_percent=1.11,
        open=213.0,
        high=215.0,
        low=212.5,
        prev_close=212.2,
        volume=1000.0,
        amount=214550.0,
    )


def test_stock_evidence_quote_preserves_available_provider_source() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_pct=1.23,
                market_timestamp="2026-05-13T08:30:00Z",
            )
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service._quote("AAPL")

    assert {
        key: payload[key]
        for key in ("status", "price", "changePct", "currency", "provider", "updatedAt")
    } == {
        "status": "available",
        "price": 214.55,
        "changePct": 1.23,
        "currency": "USD",
        "provider": "alpaca",
        "updatedAt": "2026-05-13T08:30:00Z",
    }
    assert payload["source"] == "alpaca"
    assert payload["sourceType"] == "local_or_reported"
    assert payload["freshness"] == "unknown"
    assert payload["asOf"] == "2026-05-13T08:30:00Z"
    assert payload["sourceConfidence"]["capReason"] == "freshness_not_proven"
    _assert_quote_diagnostic_authority_is_closed(payload)


def test_stock_evidence_quote_adapter_returns_inert_snapshot_for_basic_quote() -> None:
    adapter = StockEvidenceQuoteAdapter(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_pct=1.23,
                total_mv=3210000000.0,
                pe_ratio=30.2,
                pb_ratio=12.1,
                market_timestamp="2026-05-13T08:30:00Z",
            )
        )
    )

    snapshot = adapter.get_quote_snapshot("AAPL")

    assert snapshot == StockEvidenceQuoteSnapshot(
        source="alpaca",
        price=214.55,
        change_pct=1.23,
        total_mv=3210000000.0,
        pe_ratio=30.2,
        pb_ratio=12.1,
        market_timestamp="2026-05-13T08:30:00Z",
        source_metadata={
            "source": "alpaca",
            "sourceType": "local_or_reported",
            "freshness": "unknown",
            "asOf": "2026-05-13T08:30:00Z",
            "degradationReason": "freshness_not_proven",
            "isFallback": False,
            "isStale": False,
            "isPartial": False,
            "isSynthetic": False,
            "isUnavailable": False,
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "sourceAuthorityAllowed": False,
            "rawPayloadStored": False,
            "sourceConfidence": {
                "source": "alpaca",
                "sourceLabel": "alpaca",
                "asOf": "2026-05-13T08:30:00Z",
                "freshness": "unknown",
                "isFallback": False,
                "isStale": False,
                "isPartial": False,
                "isSynthetic": False,
                "isUnavailable": False,
                "confidenceWeight": 0.3,
                "coverage": 1.0,
                "degradationReason": "freshness_not_proven",
                "capReason": "freshness_not_proven",
            },
        },
    )


def test_stock_evidence_service_keeps_fetcher_manager_constructor_compatibility() -> None:
    fetcher_manager = SimpleNamespace(get_realtime_quote=lambda symbol: None)
    service = StockEvidenceService(
        fetcher_manager=fetcher_manager,
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    assert service.fetcher_manager is fetcher_manager
    assert service.quote_adapter.fetcher_manager is fetcher_manager


def _assert_quote_diagnostic_authority_is_closed(quote: dict[str, object]) -> None:
    assert quote["observationOnly"] is True
    assert quote["scoreContributionAllowed"] is False
    assert quote["sourceAuthorityAllowed"] is False
    assert quote["rawPayloadStored"] is False
    for deferred_key in (
        "providerId",
        "sourceTier",
        "trustLevel",
        "freshnessExpectation",
        "readinessState",
        "authorityGrant",
    ):
        assert deferred_key not in quote
        assert deferred_key not in quote["sourceConfidence"]


def test_stock_evidence_quote_projects_diagnostic_source_confidence_without_promotion() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_pct=1.23,
                total_mv=3210000000.0,
                pe_ratio=30.2,
                pb_ratio=12.1,
                market_timestamp="2026-05-13T08:30:00Z",
            )
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service.get_stock_evidence(["AAPL"])

    item = payload["items"][0]
    quote = item["quote"]
    packet = item["stockEvidencePacket"]
    quote_ref = next(ref for ref in packet["sourceRefs"] if ref["evidenceClass"] == "quote")
    blocked = {boundary["claim"]: boundary for boundary in packet["claimBoundaries"] if not boundary["allowed"]}

    assert list(item)[:6] == ["symbol", "market", "quote", "technical", "fundamental", "news"]
    assert {
        key: quote[key]
        for key in ("status", "price", "changePct", "currency", "provider", "updatedAt")
    } == {
        "status": "available",
        "price": 214.55,
        "changePct": 1.23,
        "currency": "USD",
        "provider": "alpaca",
        "updatedAt": "2026-05-13T08:30:00Z",
    }
    assert quote["source"] == "alpaca"
    assert quote["sourceType"] == "local_or_reported"
    assert quote["freshness"] == "unknown"
    assert quote["asOf"] == "2026-05-13T08:30:00Z"
    assert quote["degradationReason"] == "freshness_not_proven"
    assert quote["isFallback"] is False
    assert quote["isStale"] is False
    assert quote["isPartial"] is False
    assert quote["isSynthetic"] is False
    assert quote["isUnavailable"] is False
    _assert_quote_diagnostic_authority_is_closed(quote)
    assert quote["sourceConfidence"] == {
        "source": "alpaca",
        "sourceLabel": "alpaca",
        "asOf": "2026-05-13T08:30:00Z",
        "freshness": "unknown",
        "isFallback": False,
        "isStale": False,
        "isPartial": False,
        "isSynthetic": False,
        "isUnavailable": False,
        "confidenceWeight": 0.3,
        "coverage": 1.0,
        "degradationReason": "freshness_not_proven",
        "capReason": "freshness_not_proven",
    }
    assert quote_ref["provider"] == "alpaca"
    assert quote_ref["asOf"] == "2026-05-13T08:30:00Z"
    assert quote_ref["sourceType"] == "local_or_reported"
    assert quote_ref["freshness"] == "unknown"
    assert all(evidence["evidenceClass"] != "quote" for evidence in packet["scoreEligibleEvidence"])
    assert blocked["price_is_live"]["reasonCode"] == "quote_freshness_not_proven"


def test_stock_evidence_quote_marks_missing_quote_timestamp_as_partial_diagnostic_only() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_pct=1.23,
                market_timestamp=None,
            )
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service.get_stock_evidence(["AAPL"])

    item = payload["items"][0]
    quote = item["quote"]
    packet = item["stockEvidencePacket"]
    quote_ref = next(ref for ref in packet["sourceRefs"] if ref["evidenceClass"] == "quote")
    blocked = {boundary["claim"]: boundary for boundary in packet["claimBoundaries"] if not boundary["allowed"]}

    assert quote["status"] == "available"
    assert quote["provider"] == "alpaca"
    assert quote["updatedAt"] is None
    assert quote["sourceType"] == "local_or_reported"
    assert quote["freshness"] == "partial"
    assert quote["degradationReason"] == "partial_coverage"
    assert quote["isFallback"] is False
    assert quote["isStale"] is False
    assert quote["isPartial"] is True
    assert quote["isSynthetic"] is False
    assert quote["isUnavailable"] is False
    _assert_quote_diagnostic_authority_is_closed(quote)
    assert quote["sourceConfidence"]["freshness"] == "partial"
    assert quote["sourceConfidence"]["capReason"] == "partial_coverage"
    assert quote_ref["freshness"] == "partial"
    assert all(evidence["evidenceClass"] != "quote" for evidence in packet["scoreEligibleEvidence"])
    assert blocked["price_is_live"]["reasonCode"] == "quote_freshness_not_proven"


def test_stock_evidence_quote_rejects_partial_or_non_basic_quotes_as_unknown() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=0.0,
                change_pct=1.23,
            )
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service._quote("AAPL")

    assert payload["status"] == "unknown"
    assert payload["provider"] == "realtime_quote"
    assert payload["source"] == "realtime_quote"
    assert payload["sourceType"] == "missing"
    assert payload["freshness"] == "unavailable"
    assert payload["isUnavailable"] is True
    _assert_quote_diagnostic_authority_is_closed(payload)


def test_stock_evidence_quote_surfaces_runtime_errors_as_error_status() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=MagicMock(side_effect=RuntimeError("provider down")),
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service._quote("AAPL")

    assert payload["status"] == "error"
    assert payload["provider"] == "realtime_quote"
    assert payload["error"] == "provider down"
    assert payload["sourceType"] == "missing"
    assert payload["freshness"] == "unavailable"
    assert payload["isUnavailable"] is True
    _assert_quote_diagnostic_authority_is_closed(payload)


def test_runtime_fallback_quote_keeps_provider_trace_but_packet_downgrades_live_claims() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Fallback Apple",
                source=RealtimeSource.FALLBACK,
                price=214.55,
                change_pct=-0.42,
                market_timestamp="2026-05-13T08:30:00Z",
            )
        ),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service.get_stock_evidence(["AAPL"])

    item = payload["items"][0]
    packet = item["stockEvidencePacket"]
    quote_ref = next(ref for ref in packet["sourceRefs"] if ref["evidenceClass"] == "quote")
    blocked = {boundary["claim"]: boundary for boundary in packet["claimBoundaries"] if not boundary["allowed"]}

    assert {
        key: item["quote"][key]
        for key in ("status", "price", "changePct", "currency", "provider", "updatedAt")
    } == {
        "status": "available",
        "price": 214.55,
        "changePct": -0.42,
        "currency": "USD",
        "provider": "fallback",
        "updatedAt": "2026-05-13T08:30:00Z",
    }
    assert item["quote"]["source"] == "fallback"
    assert item["quote"]["sourceType"] == "fallback"
    assert item["quote"]["freshness"] == "fallback"
    assert item["quote"]["degradationReason"] == "fallback_source"
    assert item["quote"]["isFallback"] is True
    assert item["quote"]["isStale"] is False
    assert item["quote"]["isPartial"] is False
    assert item["quote"]["isSynthetic"] is False
    assert item["quote"]["isUnavailable"] is False
    _assert_quote_diagnostic_authority_is_closed(item["quote"])
    assert item["quote"]["sourceConfidence"]["confidenceWeight"] == 0.4
    assert item["quote"]["sourceConfidence"]["capReason"] == "fallback_source"
    assert quote_ref["provider"] == "fallback"
    assert quote_ref["asOf"] == "2026-05-13T08:30:00Z"
    assert quote_ref["sourceType"] == "fallback"
    assert quote_ref["freshness"] == "fallback"
    assert all(evidence["evidenceClass"] != "quote" for evidence in packet["scoreEligibleEvidence"])
    assert blocked["price_is_live"]["reasonCode"] == "quote_freshness_not_proven"
    assert "weak_or_fallback_provider_evidence" in packet["confidenceCap"]["reasonCodes"]


def test_runtime_unavailable_quote_keeps_unknown_contract_and_no_fake_live_fields() -> None:
    service = StockEvidenceService(
        fetcher_manager=SimpleNamespace(get_realtime_quote=lambda symbol: None),
        stock_repo=MagicMock(),
        analysis_repo=MagicMock(),
    )

    payload = service.get_stock_evidence(["AAPL"])

    item = payload["items"][0]
    packet = item["stockEvidencePacket"]
    quote_ref = next(ref for ref in packet["sourceRefs"] if ref["evidenceClass"] == "quote")
    blocked = {boundary["claim"]: boundary for boundary in packet["claimBoundaries"] if not boundary["allowed"]}

    assert item["quote"]["status"] == "unknown"
    assert item["quote"]["provider"] == "realtime_quote"
    assert item["quote"]["source"] == "realtime_quote"
    assert item["quote"]["sourceType"] == "missing"
    assert item["quote"]["freshness"] == "unavailable"
    assert item["quote"]["degradationReason"] == "unavailable_source"
    assert item["quote"]["isFallback"] is False
    assert item["quote"]["isStale"] is False
    assert item["quote"]["isPartial"] is False
    assert item["quote"]["isSynthetic"] is False
    assert item["quote"]["isUnavailable"] is True
    _assert_quote_diagnostic_authority_is_closed(item["quote"])
    assert item["quote"]["sourceConfidence"]["confidenceWeight"] == 0.0
    assert item["quote"]["sourceConfidence"]["capReason"] == "unavailable_source"
    assert quote_ref["status"] == "unknown"
    assert quote_ref["asOf"] is None
    assert quote_ref["sourceType"] == "missing"
    assert quote_ref["freshness"] == "unavailable"
    assert all(evidence["evidenceClass"] != "quote" for evidence in packet["scoreEligibleEvidence"])
    assert blocked["price_is_live"]["reasonCode"] == "quote_freshness_not_proven"


def test_cn_scanner_degraded_snapshot_preserves_labels_and_provider_diagnostics() -> None:
    db = _in_memory_db()
    stock_repo = StockRepository(db)
    temp_dir = tempfile.TemporaryDirectory()
    cache_path = Path(temp_dir.name) / "scanner_cn_universe_cache.csv"
    manager = StructuredScannerDataManager(
        snapshot_result={
            "success": False,
            "source": None,
            "data": None,
            "attempts": [
                {
                    "fetcher": "AkshareFetcher",
                    "status": "failed",
                    "reason_code": "akshare_snapshot_fetch_failed",
                    "summary": "akshare unavailable",
                },
                {
                    "fetcher": "EfinanceFetcher",
                    "status": "failed",
                    "reason_code": "efinance_snapshot_fetch_failed",
                    "summary": "efinance timeout",
                },
            ],
            "error_code": "no_realtime_snapshot_available",
            "error_message": "snapshot unavailable",
        }
    )
    for code, history in manager.histories.items():
        stock_repo.save_dataframe(history.copy(), code, data_source="LocalWarmCache")

    result = MarketScannerService(
        db,
        data_manager=manager,
        local_universe_cache_path=str(cache_path),
    ).run_scan(
        market="cn",
        shortlist_size=3,
        universe_limit=50,
        detail_limit=10,
    )
    temp_dir.cleanup()

    scanner_data = result["diagnostics"]["scanner_data"]
    provider_diagnostics = result["diagnostics"]["provider_diagnostics"]

    assert scanner_data["degraded_mode_used"] is True
    assert scanner_data["universe_resolution"]["source"] == "FakeListSource"
    assert scanner_data["snapshot_resolution"]["source"] == "local_history_degraded"
    assert provider_diagnostics["snapshot_source_used"] == "local_history_degraded"
    assert provider_diagnostics["history_source_used"] == "local_db"
    assert provider_diagnostics["fallback_occurred"] is True
    assert provider_diagnostics["fallback_count"] == 2
    assert "local_universe_cache failed (local_universe_cache_missing)" in provider_diagnostics["provider_warnings"]
    assert "AkshareFetcher failed (akshare_snapshot_fetch_failed)" in provider_diagnostics["provider_warnings"]
    assert "snapshot=local_history_degraded" in result["source_summary"]
    assert "history=local_first" in result["source_summary"]


def test_us_and_hk_scanner_route_labels_preserve_quote_sources() -> None:
    us_db = _in_memory_db()
    us_stock_repo = StockRepository(us_db)
    seed_us_local_history(us_stock_repo)
    us_result = MarketScannerService(us_db, data_manager=FakeUsScannerDataManager()).run_scan(
        market="us",
        profile="us_preopen_v1",
        shortlist_size=2,
        universe_limit=50,
        detail_limit=10,
        universe_type="symbols",
        symbols=["NVDA", "PLTR"],
    )

    assert us_result["diagnostics"]["scanner_data"]["snapshot_resolution"]["source"] == "yfinance"
    assert us_result["diagnostics"]["provider_diagnostics"]["quote_source_used"] == "yfinance"
    assert us_result["diagnostics"]["provider_diagnostics"]["snapshot_source_used"] == "yfinance"
    assert "universe=custom_symbols" in us_result["source_summary"]
    assert "snapshot=yfinance" in us_result["source_summary"]

    hk_db = _in_memory_db()
    hk_stock_repo = StockRepository(hk_db)
    seed_hk_local_history(hk_stock_repo)
    hk_result = MarketScannerService(hk_db, data_manager=FakeHkScannerDataManager()).run_scan(
        market="hk",
        profile="hk_preopen_v1",
        shortlist_size=2,
        universe_limit=50,
        detail_limit=10,
        universe_type="symbols",
        symbols=["HK00700", "HK01810"],
    )

    assert hk_result["diagnostics"]["scanner_data"]["snapshot_resolution"]["source"] == "twelve_data"
    assert hk_result["diagnostics"]["provider_diagnostics"]["quote_source_used"] == "twelve_data"
    assert hk_result["diagnostics"]["provider_diagnostics"]["snapshot_source_used"] == "twelve_data"
    assert "universe=custom_symbols" in hk_result["source_summary"]
    assert "snapshot=twelve_data" in hk_result["source_summary"]


def test_scanner_board_lookup_failures_remain_visible_in_candidate_diagnostics() -> None:
    db = _in_memory_db()
    result = MarketScannerService(db, data_manager=_BoardWarningScannerDataManager()).run_scan(
        market="cn",
        shortlist_size=3,
        universe_limit=50,
        detail_limit=10,
    )

    first = result["shortlist"][0]["diagnostics"]
    assert first["board_warning"].startswith("board lookup failed for ")
