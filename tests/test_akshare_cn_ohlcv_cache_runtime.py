from __future__ import annotations

import json
from datetime import date

import pandas as pd

from src.repositories.stock_repo import StockRepository
from src.services.akshare_cn_ohlcv_cache import (
    AKSHARE_CN_DAILY_SOURCE,
    LOCAL_CN_DB_SOURCE,
    AkshareCnOhlcvRuntime,
    build_akshare_cn_ohlcv_runtime_status,
)
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvReadinessRequest,
    HistoricalOhlcvReadinessService,
)
from src.services.historical_ohlcv_runtime_adapter import HistoricalOhlcvRuntimeAdapter
from src.services.stock_service import StockService
from src.storage import DatabaseManager
from unittest.mock import patch


class _FakeAkshareFetcher:
    def __init__(self, frame: pd.DataFrame | None = None, error: Exception | None = None) -> None:
        self.frame = frame if frame is not None else _akshare_frame(5)
        self.error = error
        self.calls: list[dict[str, object]] = []

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30) -> pd.DataFrame:
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
        return self.frame.copy()


def _repo(tmp_path) -> StockRepository:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'stock-cache.db'}")
    return StockRepository(db)


def _akshare_frame(count: int, *, start: str = "2026-01-01") -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=count, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "code": ["600519"] * count,
            "open": [100.0 + index for index in range(count)],
            "high": [101.0 + index for index in range(count)],
            "low": [99.0 + index for index in range(count)],
            "close": [100.5 + index for index in range(count)],
            "volume": [1000.0 + index for index in range(count)],
            "amount": [100_000.0 + index for index in range(count)],
            "pct_chg": [0.0] * count,
        }
    )


def test_default_disabled_runtime_returns_safe_status_without_provider_call(tmp_path) -> None:
    fetcher = _FakeAkshareFetcher(error=AssertionError("provider call attempted"))
    runtime = AkshareCnOhlcvRuntime(
        enabled=False,
        repository=_repo(tmp_path),
        dependency_checker=lambda: True,
        fetcher_factory=lambda: fetcher,
    )

    payload = runtime.get_history_data("600519", days=30)
    status = build_akshare_cn_ohlcv_runtime_status(enabled=False, dependency_checker=lambda: True)

    assert fetcher.calls == []
    assert payload["data"] == []
    assert payload["source"] == "unavailable"
    assert payload["diagnostics"]["status"] == "disabled"
    assert payload["diagnostics"]["reason"] == "disabled_by_config"
    assert status["runtimeStatus"] == "disabled"
    assert status["externalProviderCalls"] is False
    assert status["consumerSafe"] is True


def test_stock_service_default_disabled_cn_history_skips_general_fetcher_manager(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "stock-service.db"))
    DatabaseManager.reset_instance()

    with patch("data_provider.base.DataFetcherManager", side_effect=AssertionError("general provider manager called")):
        payload = StockService().get_history_data("600519", days=30)

    assert payload["data"] == []
    assert payload["source"] == "unavailable"
    assert payload["diagnostics"]["status"] == "disabled"
    assert payload["diagnostics"]["reason"] == "disabled_by_config"


def test_enabled_runtime_dependency_missing_returns_safe_status_without_provider_call(tmp_path) -> None:
    fetcher = _FakeAkshareFetcher(error=AssertionError("provider call attempted"))
    runtime = AkshareCnOhlcvRuntime(
        enabled=True,
        repository=_repo(tmp_path),
        dependency_checker=lambda: False,
        fetcher_factory=lambda: fetcher,
    )

    payload = runtime.get_history_data("600519", days=30)
    status = build_akshare_cn_ohlcv_runtime_status(enabled=True, dependency_checker=lambda: False)

    assert fetcher.calls == []
    assert payload["data"] == []
    assert payload["source"] == "unavailable"
    assert payload["diagnostics"]["status"] == "dependency_missing"
    assert payload["diagnostics"]["reason"] == "dependency_missing"
    assert status["runtimeStatus"] == "dependency_missing"
    assert "token" not in json.dumps(status, ensure_ascii=False).lower()


def test_fake_akshare_response_normalizes_persists_and_flows_through_historical_adapter(tmp_path) -> None:
    fetcher = _FakeAkshareFetcher(_akshare_frame(8))
    runtime = AkshareCnOhlcvRuntime(
        enabled=True,
        repository=_repo(tmp_path),
        dependency_checker=lambda: True,
        fetcher_factory=lambda: fetcher,
    )

    adapter = HistoricalOhlcvRuntimeAdapter(history_runtime=runtime)
    result = HistoricalOhlcvReadinessService(provider=adapter).fetch(
        HistoricalOhlcvReadinessRequest(
            symbol="600519",
            market="cn",
            timeframe="1d",
            required_bars=5,
            require_adjusted=True,
        )
    )

    assert fetcher.calls == [{"stock_code": "600519", "start_date": None, "end_date": None, "days": 5}]
    assert len(result.bars) == 5
    assert result.bars[0].as_dict() == {
        "date": "2026-01-04",
        "open": 103.0,
        "high": 104.0,
        "low": 102.0,
        "close": 103.5,
        "volume": 1003.0,
        "adjustedClose": 103.5,
    }
    assert result.readiness["providerState"] == "available"
    assert result.readiness["adjustmentState"] == "available"
    assert result.readiness["overallState"] == "ready"


def test_local_cache_hit_avoids_second_akshare_provider_call(tmp_path) -> None:
    repo = _repo(tmp_path)
    first_fetcher = _FakeAkshareFetcher(_akshare_frame(6))
    first_runtime = AkshareCnOhlcvRuntime(
        enabled=True,
        repository=repo,
        dependency_checker=lambda: True,
        fetcher_factory=lambda: first_fetcher,
    )
    first_payload = first_runtime.get_history_data("600519", days=5)

    second_fetcher = _FakeAkshareFetcher(error=AssertionError("provider call attempted"))
    second_runtime = AkshareCnOhlcvRuntime(
        enabled=True,
        repository=repo,
        dependency_checker=lambda: True,
        fetcher_factory=lambda: second_fetcher,
    )
    second_payload = second_runtime.get_history_data("600519", days=5)

    assert first_fetcher.calls == [{"stock_code": "600519", "start_date": None, "end_date": None, "days": 5}]
    assert second_fetcher.calls == []
    assert first_payload["source"] == AKSHARE_CN_DAILY_SOURCE
    assert second_payload["source"] == LOCAL_CN_DB_SOURCE
    assert [row["date"] for row in second_payload["data"]] == [
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
        "2026-01-06",
    ]


def test_provider_exception_is_redacted_and_reported_as_runtime_unavailable(tmp_path) -> None:
    fetcher = _FakeAkshareFetcher(
        error=RuntimeError("providerName=AkshareFetcher token=secret Traceback raw_payload={secret}")
    )
    runtime = AkshareCnOhlcvRuntime(
        enabled=True,
        repository=_repo(tmp_path),
        dependency_checker=lambda: True,
        fetcher_factory=lambda: fetcher,
    )

    payload = runtime.get_history_data("600519", days=30)
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert payload["data"] == []
    assert payload["source"] == "unavailable"
    assert payload["diagnostics"]["status"] == "runtime_unavailable"
    assert payload["diagnostics"]["reason"] == "runtime_unavailable"
    assert payload["diagnostics"]["errorType"] == "RuntimeError"
    for forbidden in ("token", "secret", "traceback", "raw_payload", "aksharefetcher"):
        assert forbidden not in serialized


def test_insufficient_stale_and_missing_adjustments_classifications_remain_honest() -> None:
    runtime = AkshareCnOhlcvRuntime(
        enabled=True,
        repository=None,
        dependency_checker=lambda: True,
        fetcher_factory=lambda: _FakeAkshareFetcher(_akshare_frame(3, start="2026-01-01")),
        persist_cache=False,
    )
    adapter = HistoricalOhlcvRuntimeAdapter(history_runtime=runtime)

    result = HistoricalOhlcvReadinessService(provider=adapter).fetch(
        HistoricalOhlcvReadinessRequest(
            symbol="600519",
            market="cn",
            timeframe="1d",
            end=date(2026, 1, 10),
            required_bars=5,
            require_adjusted=False,
        )
    )

    assert result.readiness["usableBars"] == 3
    assert result.readiness["missingBars"] == 2
    assert result.readiness["freshnessState"] == "stale"
    assert result.readiness["adjustmentState"] == "not_required"
    assert "insufficient_history" in result.readiness["missingRequirements"]
    assert "stale_data" in result.readiness["missingRequirements"]
