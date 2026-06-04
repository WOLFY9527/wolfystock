# -*- coding: utf-8 -*-
"""Tests for the market scanner service."""

from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from data_provider.base import BaseFetcher, DataFetchError, DataFetcherManager, normalize_stock_code
from src.repositories.stock_repo import StockRepository
from src.core.scanner_profile import get_scanner_profile
from src.core.scanner_theme_registry import create_ai_scanner_theme, get_scanner_theme
from src.services.market_cache import market_cache
from src.services.market_data_source_registry import resolve_source_label, resolve_source_type
from src.services.market_scanner_service import MarketScannerService, ScannerRuntimeError
from src.services.scanner_evidence_packet import SCANNER_EVIDENCE_VERSION, build_scanner_evidence_packet
from src.storage import DatabaseManager, MarketScannerRun


def _make_history(
    *,
    start_price: float,
    slope: float,
    amount_base: float,
    volume_base: float,
    bars: int = 100,
) -> pd.DataFrame:
    end_date = pd.Timestamp(datetime.now().date()) - pd.offsets.BDay(1)
    dates = pd.bdate_range(end=end_date, periods=bars)
    closes = np.array([start_price + slope * idx + 0.12 * np.sin(idx / 5.0) for idx in range(bars)], dtype=float)
    opens = closes * 0.992
    highs = closes * 1.018
    lows = closes * 0.984
    volumes = np.array([volume_base * (1.0 + 0.08 * np.cos(idx / 6.0)) for idx in range(bars)], dtype=float)
    amounts = closes * volumes
    pct_chg = pd.Series(closes).pct_change().fillna(0.0) * 100.0
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "amount": np.maximum(amounts, amount_base),
            "pct_chg": pct_chg,
        }
    )


class FakeScannerDataManager:
    def __init__(self):
        self.daily_history_calls: list[str] = []
        self.stock_list = pd.DataFrame(
            [
                {"code": "600001", "name": "算力龙头"},
                {"code": "600002", "name": "机器人核心"},
                {"code": "300123", "name": "高景气成长"},
                {"code": "600003", "name": "稳健白马"},
                {"code": "000005", "name": "ST风险股"},
                {"code": "830001", "name": "北交所样本"},
            ]
        )
        self.snapshot = pd.DataFrame(
            [
                {
                    "code": "600001",
                    "name": "算力龙头",
                    "price": 18.4,
                    "change_pct": 4.2,
                    "volume": 58_000_000,
                    "amount": 1.25e9,
                    "turnover_rate": 6.2,
                    "volume_ratio": 1.9,
                    "amplitude": 4.5,
                    "change_60d": 24.0,
                },
                {
                    "code": "600002",
                    "name": "机器人核心",
                    "price": 22.6,
                    "change_pct": 3.1,
                    "volume": 41_000_000,
                    "amount": 9.8e8,
                    "turnover_rate": 4.8,
                    "volume_ratio": 1.6,
                    "amplitude": 4.2,
                    "change_60d": 18.5,
                },
                {
                    "code": "300123",
                    "name": "高景气成长",
                    "price": 31.2,
                    "change_pct": 8.6,
                    "volume": 37_000_000,
                    "amount": 8.7e8,
                    "turnover_rate": 13.5,
                    "volume_ratio": 2.2,
                    "amplitude": 7.2,
                    "change_60d": 31.0,
                },
                {
                    "code": "600003",
                    "name": "稳健白马",
                    "price": 12.9,
                    "change_pct": 1.0,
                    "volume": 26_000_000,
                    "amount": 4.6e8,
                    "turnover_rate": 2.0,
                    "volume_ratio": 1.0,
                    "amplitude": 2.8,
                    "change_60d": 9.0,
                },
                {
                    "code": "000005",
                    "name": "ST风险股",
                    "price": 5.0,
                    "change_pct": 1.0,
                    "volume": 12_000_000,
                    "amount": 2.6e8,
                    "turnover_rate": 1.1,
                    "volume_ratio": 0.9,
                    "amplitude": 2.0,
                    "change_60d": 5.0,
                },
                {
                    "code": "830001",
                    "name": "北交所样本",
                    "price": 15.0,
                    "change_pct": 1.5,
                    "volume": 15_000_000,
                    "amount": 3.4e8,
                    "turnover_rate": 1.8,
                    "volume_ratio": 1.0,
                    "amplitude": 2.2,
                    "change_60d": 8.0,
                },
            ]
        )
        self.histories = {
            "600001": _make_history(start_price=11.0, slope=0.085, amount_base=9.0e8, volume_base=48_000_000),
            "600002": _make_history(start_price=15.0, slope=0.065, amount_base=7.2e8, volume_base=34_000_000),
            "300123": _make_history(start_price=18.0, slope=0.11, amount_base=6.5e8, volume_base=31_000_000),
            "600003": _make_history(start_price=10.5, slope=0.03, amount_base=3.2e8, volume_base=21_000_000),
        }
        self.boards = {
            "600001": [{"name": "AI算力"}, {"name": "服务器"}],
            "600002": [{"name": "机器人"}],
            "300123": [{"name": "AI算力"}],
            "600003": [{"name": "家电"}],
        }

    def get_cn_stock_list(self):
        return self.stock_list.copy(), "FakeListSource"

    def get_cn_realtime_snapshot(self):
        return self.snapshot.copy(), "FakeSnapshotSource"

    def get_daily_data(self, code: str, days: int = 140):
        normalized = str(code)
        self.daily_history_calls.append(normalized)
        return self.histories[normalized].copy().tail(days).reset_index(drop=True), "FakeDailySource"

    def get_sector_rankings(self, n: int = 5):
        return ([{"name": "AI算力"}, {"name": "机器人"}][:n], [])

    def get_belong_boards(self, stock_code: str):
        return list(self.boards.get(stock_code, []))


class StructuredScannerDataManager(FakeScannerDataManager):
    def __init__(
        self,
        *,
        stock_list_result: dict | None = None,
        snapshot_result: dict | None = None,
    ):
        super().__init__()
        self.stock_list_attempts = 0
        self.snapshot_attempts = 0
        self._stock_list_result = stock_list_result
        self._snapshot_result = snapshot_result

    def try_get_cn_stock_list(self, preferred_fetchers=None):
        self.stock_list_attempts += 1
        if self._stock_list_result is not None:
            return self._clone_result(self._stock_list_result)
        return {
            "success": True,
            "source": "FakeListSource",
            "data": self.stock_list.copy(),
            "attempts": [{"fetcher": "FakeListSource", "status": "success", "rows": int(len(self.stock_list))}],
            "error_code": None,
            "error_message": None,
        }

    def try_get_cn_realtime_snapshot(self, preferred_fetchers=None):
        self.snapshot_attempts += 1
        if self._snapshot_result is not None:
            return self._clone_result(self._snapshot_result)
        return {
            "success": True,
            "source": "FakeSnapshotSource",
            "data": self.snapshot.copy(),
            "attempts": [{"fetcher": "FakeSnapshotSource", "status": "success", "rows": int(len(self.snapshot))}],
            "error_code": None,
            "error_message": None,
        }

    @staticmethod
    def _clone_result(payload: dict) -> dict:
        cloned = dict(payload)
        data = cloned.get("data")
        if isinstance(data, pd.DataFrame):
            cloned["data"] = data.copy()
        attempts = cloned.get("attempts")
        if isinstance(attempts, list):
            cloned["attempts"] = [dict(item) for item in attempts]
        return cloned


class ObservationScannerDataManager(FakeScannerDataManager):
    def get_cn_stock_list(self):
        stock_list, _ = super().get_cn_stock_list()
        return stock_list, "AkshareFetcher"

    def get_cn_realtime_snapshot(self):
        snapshot, _ = super().get_cn_realtime_snapshot()
        return snapshot, "AkshareFetcher"

    def get_daily_data(self, code: str, days: int = 140):
        history_df, _ = super().get_daily_data(code, days=days)
        return history_df, "PytdxFetcher"


class FakeScannerAiService:
    def interpret_shortlist(self, *, profile, candidates):  # noqa: ANN001
        enriched = [dict(candidate) for candidate in candidates]
        for candidate in enriched:
            diagnostics = dict(candidate.get("_diagnostics") or {})
            ai_payload = {
                "status": "generated",
                "summary": f"{candidate['symbol']} 更像趋势延续中的临界突破观察。",
                "opportunity_type": "临界突破",
                "risk_interpretation": "若竞价过高且量能不跟，容易冲高回落。",
                "watch_plan": "盘前看竞价承接，开盘后看量比是否维持强势。",
                "review_commentary": None,
                "provider": "fake",
                "model": "fake/scanner-ai",
                "generated_at": "2026-04-13T08:30:00",
                "message": None,
                "fallback_used": False,
                "attempt_trace": [],
                "review_commentary_status": "pending_review_data",
            }
            diagnostics["ai_interpretation"] = ai_payload
            candidate["_diagnostics"] = diagnostics
            candidate["ai_interpretation"] = {
                "available": True,
                "status": "generated",
                "summary": ai_payload["summary"],
                "opportunity_type": ai_payload["opportunity_type"],
                "risk_interpretation": ai_payload["risk_interpretation"],
                "watch_plan": ai_payload["watch_plan"],
                "review_commentary": None,
                "provider": ai_payload["provider"],
                "model": ai_payload["model"],
                "generated_at": ai_payload["generated_at"],
                "message": None,
            }
        return enriched, {
            "enabled": True,
            "status": "completed",
            "top_n": len(enriched),
            "attempted_candidates": len(enriched),
            "generated_candidates": len(enriched),
            "failed_candidates": 0,
            "skipped_candidates": 0,
            "models_used": ["fake/scanner-ai"],
            "fallback_used": False,
            "message": f"已为前 {len(enriched)} 名候选生成 AI 解读。",
        }

    def enrich_review_commentary(self, *, profile, candidate, realized_outcome):  # noqa: ANN001
        _ = profile, realized_outcome
        diagnostics = candidate.get("diagnostics") if isinstance(candidate.get("diagnostics"), dict) else {}
        ai_payload = diagnostics.get("ai_interpretation") if isinstance(diagnostics.get("ai_interpretation"), dict) else None
        if not isinstance(ai_payload, dict) or ai_payload.get("review_commentary"):
            return ai_payload
        ai_payload = dict(ai_payload)
        ai_payload["review_commentary"] = "后续表现验证了量能和趋势共振。"
        ai_payload["review_commentary_status"] = "generated"
        return ai_payload

    @staticmethod
    def public_payload_from_diagnostics(payload):  # noqa: ANN001
        if not isinstance(payload, dict):
            return {
                "available": False,
                "status": "skipped",
                "summary": None,
                "opportunity_type": None,
                "risk_interpretation": None,
                "watch_plan": None,
                "review_commentary": None,
                "provider": None,
                "model": None,
                "generated_at": None,
                "message": None,
            }
        return {
            "available": payload.get("status") == "generated",
            "status": payload.get("status"),
            "summary": payload.get("summary"),
            "opportunity_type": payload.get("opportunity_type"),
            "risk_interpretation": payload.get("risk_interpretation"),
            "watch_plan": payload.get("watch_plan"),
            "review_commentary": payload.get("review_commentary"),
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "generated_at": payload.get("generated_at"),
            "message": payload.get("message"),
        }


class RecordingScannerAiService(FakeScannerAiService):
    def __init__(self) -> None:
        self.received_signature: list[tuple[str, int, float]] = []

    def interpret_shortlist(self, *, profile, candidates):  # noqa: ANN001
        self.received_signature = [
            (str(candidate["symbol"]), int(candidate["rank"]), float(candidate["score"]))
            for candidate in candidates
        ]
        return super().interpret_shortlist(profile=profile, candidates=candidates)


class FakeUsScannerDataManager(FakeScannerDataManager):
    def __init__(self):
        super().__init__()
        self._last_realtime_quote_trace: list[dict] = []
        self.realtime_quote_calls: list[str] = []
        self.us_quotes = {
            "NVDA": SimpleNamespace(
                price=964.0,
                pre_close=908.0,
                change_pct=6.17,
                volume=41_000_000,
                amount=3.95e10,
                name="NVIDIA",
                source=SimpleNamespace(value="yfinance"),
            ),
            "AAPL": SimpleNamespace(
                price=212.8,
                pre_close=199.4,
                change_pct=6.72,
                volume=36_500_000,
                amount=7.72e9,
                name="Apple",
                source=SimpleNamespace(value="yfinance"),
            ),
            "PLTR": SimpleNamespace(
                price=27.4,
                pre_close=25.6,
                change_pct=7.03,
                volume=28_000_000,
                amount=7.67e8,
                name="Palantir",
                source=SimpleNamespace(value="yfinance"),
            ),
            "WULF": SimpleNamespace(
                price=21.3,
                pre_close=20.4,
                change_pct=4.41,
                volume=46_000_000,
                amount=9.8e8,
                name="TeraWulf",
                source=SimpleNamespace(value="alpaca"),
            ),
            "MARA": SimpleNamespace(
                price=27.0,
                pre_close=27.5,
                change_pct=-1.82,
                volume=34_000_000,
                amount=9.1e8,
                name="MARA Holdings",
                source=SimpleNamespace(value="alpaca"),
            ),
            "RIOT": SimpleNamespace(
                price=12.6,
                pre_close=12.9,
                change_pct=-2.33,
                volume=29_000_000,
                amount=3.65e8,
                name="Riot Platforms",
                source=SimpleNamespace(value="alpaca"),
            ),
            "CLSK": SimpleNamespace(
                price=16.2,
                pre_close=16.0,
                change_pct=1.25,
                volume=24_000_000,
                amount=3.88e8,
                name="CleanSpark",
                source=SimpleNamespace(value="alpaca"),
            ),
            "IREN": SimpleNamespace(
                price=11.4,
                pre_close=11.2,
                change_pct=1.79,
                volume=20_000_000,
                amount=2.28e8,
                name="IREN",
                source=SimpleNamespace(value="alpaca"),
            ),
            "HUT": SimpleNamespace(
                price=8.1,
                pre_close=8.2,
                change_pct=-1.22,
                volume=18_000_000,
                amount=1.46e8,
                name="Hut 8",
                source=SimpleNamespace(value="alpaca"),
            ),
            "BTDR": SimpleNamespace(
                price=10.4,
                pre_close=10.3,
                change_pct=0.97,
                volume=15_000_000,
                amount=1.56e8,
                name="Bitdeer",
                source=SimpleNamespace(value="alpaca"),
            ),
            "CORZ": SimpleNamespace(
                price=12.2,
                pre_close=12.0,
                change_pct=1.67,
                volume=14_000_000,
                amount=1.71e8,
                name="Core Scientific",
                source=SimpleNamespace(value="alpaca"),
            ),
        }

    def get_realtime_quote(self, symbol: str):
        normalized = str(symbol or "").upper()
        self.realtime_quote_calls.append(normalized)
        quote = self.us_quotes.get(normalized)
        if quote is None:
            self._last_realtime_quote_trace = [
                {"fetcher": "YfinanceFetcher", "status": "failed", "reason_code": "quote_missing"}
            ]
            return None
        self._last_realtime_quote_trace = [
            {"fetcher": "YfinanceFetcher", "status": "success", "symbol": normalized}
        ]
        return quote

    def get_last_realtime_quote_trace(self):
        return list(self._last_realtime_quote_trace)


class FakeHkScannerDataManager(FakeScannerDataManager):
    def __init__(self):
        super().__init__()
        self._last_realtime_quote_trace: list[dict] = []
        self.hk_quotes = {
            "HK00700": SimpleNamespace(
                price=503.5,
                pre_close=496.0,
                change_pct=1.51,
                volume=12_300_000,
                amount=6.19e9,
                name="Tencent Holdings",
                source=SimpleNamespace(value="twelve_data"),
            ),
            "HK01810": SimpleNamespace(
                price=18.9,
                pre_close=18.1,
                change_pct=4.42,
                volume=68_000_000,
                amount=1.27e9,
                name="Xiaomi",
                source=SimpleNamespace(value="twelve_data"),
            ),
            "HK03690": SimpleNamespace(
                price=128.0,
                pre_close=124.6,
                change_pct=2.73,
                volume=14_500_000,
                amount=1.86e9,
                name="Meituan",
                source=SimpleNamespace(value="twelve_data"),
            ),
        }

    def get_realtime_quote(self, symbol: str):
        normalized = normalize_stock_code(str(symbol or "")).upper()
        quote = self.hk_quotes.get(normalized)
        if quote is None:
            self._last_realtime_quote_trace = [
                {"fetcher": "TwelveDataFetcher", "status": "failed", "reason_code": "quote_missing"}
            ]
            return None
        self._last_realtime_quote_trace = [
            {"fetcher": "TwelveDataFetcher", "status": "success", "symbol": normalized}
        ]
        return quote

    def get_last_realtime_quote_trace(self):
        return list(self._last_realtime_quote_trace)


class SlowFaultyScannerDataManager(FakeScannerDataManager):
    def __init__(self, *, delay_seconds: float = 0.05) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds
        self.histories.pop("600003", None)
        self._lock = threading.Lock()
        self._active_history_calls = 0
        self.max_active_history_calls = 0

    def get_daily_data(self, code: str, days: int = 140):
        with self._lock:
            self._active_history_calls += 1
            self.max_active_history_calls = max(self.max_active_history_calls, self._active_history_calls)
        try:
            time.sleep(self.delay_seconds)
            return super().get_daily_data(code, days=days)
        finally:
            with self._lock:
                self._active_history_calls -= 1


class SlowMissingQuoteDataManager(FakeUsScannerDataManager):
    def __init__(self, *, delay_seconds: float = 0.01) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds
        self.us_quotes.pop("PLTR", None)

    def get_realtime_quote(self, symbol: str):
        time.sleep(self.delay_seconds)
        return super().get_realtime_quote(symbol)


def seed_us_local_history(stock_repo: StockRepository) -> None:
    fixtures = {
        "SPY": _make_history(start_price=485.0, slope=0.35, amount_base=3.4e10, volume_base=78_000_000, bars=130),
        "NVDA": _make_history(start_price=710.0, slope=2.15, amount_base=2.9e10, volume_base=48_000_000, bars=130),
        "AAPL": _make_history(start_price=175.0, slope=0.24, amount_base=8.1e9, volume_base=39_000_000, bars=130),
        "PLTR": _make_history(start_price=18.0, slope=0.13, amount_base=7.6e8, volume_base=34_000_000, bars=130),
        "SOFI": _make_history(start_price=6.8, slope=0.03, amount_base=1.2e7, volume_base=950_000, bars=130),
    }
    for code, dataframe in fixtures.items():
        stock_repo.save_dataframe(dataframe.copy(), code, data_source="LocalUsFixture")


def seed_crypto_miner_local_history(stock_repo: StockRepository) -> None:
    fixtures = {
        "SPY": _make_history(start_price=485.0, slope=0.35, amount_base=3.4e10, volume_base=78_000_000, bars=130),
        "WULF": _make_history(start_price=5.0, slope=0.12, amount_base=8.0e8, volume_base=42_000_000, bars=130),
        "MARA": _make_history(start_price=25.0, slope=0.02, amount_base=5.5e8, volume_base=36_000_000, bars=130),
        "RIOT": _make_history(start_price=12.0, slope=0.01, amount_base=3.5e8, volume_base=31_000_000, bars=130),
        "CLSK": _make_history(start_price=14.0, slope=0.04, amount_base=3.2e8, volume_base=24_000_000, bars=130),
        "IREN": _make_history(start_price=9.0, slope=0.03, amount_base=2.9e8, volume_base=22_000_000, bars=130),
        "HUT": _make_history(start_price=8.0, slope=-0.01, amount_base=2.6e8, volume_base=20_000_000, bars=130),
        "BTDR": _make_history(start_price=10.0, slope=0.015, amount_base=2.5e8, volume_base=18_000_000, bars=130),
        "CORZ": _make_history(start_price=11.0, slope=0.02, amount_base=2.4e8, volume_base=17_000_000, bars=130),
        "HIVE": _make_history(start_price=4.5, slope=0.008, amount_base=2.2e8, volume_base=16_000_000, bars=130),
    }
    for code, dataframe in fixtures.items():
        stock_repo.save_dataframe(dataframe.copy(), code, data_source="CryptoMinerFixture")


def seed_hk_local_history(stock_repo: StockRepository) -> None:
    fixtures = {
        "HK02800": _make_history(start_price=19.5, slope=0.03, amount_base=1.3e9, volume_base=82_000_000, bars=130),
        "HK00700": _make_history(start_price=380.0, slope=0.85, amount_base=5.4e9, volume_base=12_000_000, bars=130),
        "HK01810": _make_history(start_price=12.5, slope=0.06, amount_base=1.1e9, volume_base=64_000_000, bars=130),
        "HK03690": _make_history(start_price=102.0, slope=0.28, amount_base=1.9e9, volume_base=16_000_000, bars=130),
        "HK00981": _make_history(start_price=15.0, slope=0.05, amount_base=8.9e8, volume_base=42_000_000, bars=130),
    }
    for code, dataframe in fixtures.items():
        stock_repo.save_dataframe(dataframe.copy(), code, data_source="LocalHkFixture")


class FetcherStub(BaseFetcher):
    def __init__(
        self,
        *,
        name: str,
        priority: int,
        stock_list: pd.DataFrame | None = None,
        snapshot: pd.DataFrame | None = None,
        stock_list_error: Exception | None = None,
        snapshot_error: Exception | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self._stock_list = stock_list.copy() if isinstance(stock_list, pd.DataFrame) else stock_list
        self._snapshot = snapshot.copy() if isinstance(snapshot, pd.DataFrame) else snapshot
        self._stock_list_error = stock_list_error
        self._snapshot_error = snapshot_error
        self.stock_list_calls = 0
        self.snapshot_calls = 0

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (stock_code, start_date, end_date)
        return pd.DataFrame()

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        _ = stock_code
        return df

    def get_stock_list(self):
        self.stock_list_calls += 1
        if self._stock_list_error is not None:
            raise self._stock_list_error
        return self._stock_list.copy() if isinstance(self._stock_list, pd.DataFrame) else self._stock_list

    def get_a_share_spot_snapshot(self):
        self.snapshot_calls += 1
        if self._snapshot_error is not None:
            raise self._snapshot_error
        return self._snapshot.copy() if isinstance(self._snapshot, pd.DataFrame) else self._snapshot


class MarketScannerServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        market_cache.clear()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.stock_repo = StockRepository(self.db)
        self.data_manager = FakeScannerDataManager()
        self._cache_temp_dir = tempfile.TemporaryDirectory()
        self._config_patcher = patch(
            "src.services.market_scanner_service.get_config",
            return_value=SimpleNamespace(
                scanner_local_universe_path=str(
                    Path(self._cache_temp_dir.name) / "scanner_cn_universe_cache.csv"
                )
            ),
        )
        self._config_patcher.start()
        self._scanner_cache_path = Path(self._cache_temp_dir.name) / "scanner_cn_universe_cache.csv"
        self.data_manager.stock_list[["code", "name"]].to_csv(self._scanner_cache_path, index=False)
        self.service = MarketScannerService(self.db, data_manager=self.data_manager)

        local_history = self.data_manager.histories["600001"].copy()
        self.stock_repo.save_dataframe(local_history, "600001", data_source="LocalWarmCache")

    def tearDown(self) -> None:
        self._config_patcher.stop()
        self._cache_temp_dir.cleanup()
        market_cache.clear()
        DatabaseManager.reset_instance()

    def _make_review_df(self, rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
        dates = pd.to_datetime([item[0] for item in rows])
        closes = [item[1] for item in rows]
        highs = [item[2] for item in rows]
        lows = [item[3] for item in rows]
        return pd.DataFrame(
            {
                "date": dates,
                "open": closes,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": [10_000_000] * len(rows),
                "amount": [3.0e8] * len(rows),
                "pct_chg": pd.Series(closes).pct_change().fillna(0.0) * 100.0,
            }
        )

    def _set_run_timestamps(self, run_id: int, run_at_iso: str, completed_at_iso: str) -> None:
        with self.db.get_session() as session:
            run = session.get(MarketScannerRun, run_id)
            assert run is not None
            run.run_at = datetime.fromisoformat(run_at_iso)
            run.completed_at = datetime.fromisoformat(completed_at_iso)
            session.add(run)
            session.commit()

    def _candidate_payload(self, symbol: str, name: str, rank: int, score: float, last_trade_date: str) -> dict:
        return {
            "symbol": symbol,
            "name": name,
            "rank": rank,
            "score": score,
            "quality_hint": "高优先级" if score >= 80 else "优先观察",
            "reason_summary": f"{name} 趋势与量能结构较好。",
            "reasons": [f"{name} 趋势结构完整。"],
            "key_metrics": [{"label": "最新价", "value": "10.00"}],
            "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
            "risk_notes": ["注意弱开回落。"],
            "watch_context": [{"label": "观察触发", "value": "上破前高。"}],
            "boards": ["AI算力"],
            "_diagnostics": {
                "history": {
                    "latest_trade_date": last_trade_date,
                }
            },
        }

    def _record_context_run(
        self,
        *,
        market: str,
        profile: str,
        diagnostics: dict,
        shortlist: list[dict] | None = None,
    ) -> dict:
        resolved_profile = get_scanner_profile(market=market, profile=profile)
        detail = self.service.record_terminal_run(
            market=resolved_profile.market,
            profile=resolved_profile.key,
            profile_label=resolved_profile.label,
            universe_name=resolved_profile.universe_name,
            status="completed",
            headline="context test",
            trigger_mode="manual",
            request_source="test",
            watchlist_date="2026-06-03",
            source_summary="scanner=test",
            diagnostics=diagnostics,
            universe_notes=["context note"],
            scoring_notes=["context score note"],
            shortlist=shortlist
            or [
                self._candidate_payload("NVDA" if market == "us" else "600001", "主候选", 1, 88.0, "2026-06-02"),
                self._candidate_payload("AAPL" if market == "us" else "600002", "次候选", 2, 81.0, "2026-06-02"),
            ],
            universe_size=120,
            preselected_size=20,
            evaluated_size=12,
            scope="user",
        )
        assert detail is not None
        return detail

    @staticmethod
    def _baostock_history_observation(
        *,
        freshness: str,
        as_of: str | None,
        updated_at: str | None,
        attempted_at: str | None = None,
        degradation_reason: str | None = None,
        missing_provider_reason: str | None = None,
        adjustment_method: str = "baostock_adjustflag_2",
    ) -> dict:
        return {
            "providerName": "baostock",
            "providerId": "baostock",
            "source": "baostock",
            "sourceType": "public_proxy",
            "sourceTier": "third_party_free_api",
            "sourceLabel": "BaoStock",
            "trustLevel": "usable_with_caution",
            "freshness": freshness,
            "freshnessExpectation": "t_plus_1_or_delayed",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "keyRequired": False,
            "cacheRequired": True,
            "backgroundRefreshRecommended": True,
            "capability": "cn_history_daily",
            "stage": "scanner_diagnostics",
            "asOf": as_of,
            "updatedAt": updated_at,
            "attemptedAt": attempted_at,
            "degradationReason": degradation_reason,
            "missingProviderReason": missing_provider_reason,
            "adjustmentMethod": adjustment_method,
        }

    def _seed_review_watchlists(self) -> tuple[int, int]:
        rows_600001 = [
            ("2026-04-09", 10.0, 10.2, 9.8),
            ("2026-04-10", 10.2, 10.4, 10.0),
            ("2026-04-13", 10.7, 10.9, 10.4),
            ("2026-04-14", 11.1, 11.3, 10.8),
            ("2026-04-15", 11.0, 11.2, 10.7),
        ]
        rows_600002 = [
            ("2026-04-09", 9.5, 9.7, 9.3),
            ("2026-04-10", 9.4, 9.6, 9.2),
            ("2026-04-13", 9.2, 9.3, 8.9),
            ("2026-04-14", 9.0, 9.1, 8.8),
            ("2026-04-15", 8.9, 9.0, 8.7),
        ]
        rows_300123 = [
            ("2026-04-09", 20.0, 20.2, 19.8),
            ("2026-04-10", 20.5, 20.8, 20.1),
            ("2026-04-13", 21.3, 21.8, 21.0),
            ("2026-04-14", 21.8, 22.2, 21.5),
            ("2026-04-15", 22.1, 22.5, 21.8),
        ]
        rows_benchmark = [
            ("2026-04-09", 4000.0, 4010.0, 3990.0),
            ("2026-04-10", 4020.0, 4035.0, 4010.0),
            ("2026-04-13", 4040.0, 4055.0, 4030.0),
            ("2026-04-14", 4050.0, 4065.0, 4040.0),
            ("2026-04-15", 4060.0, 4075.0, 4050.0),
        ]
        self.stock_repo.save_dataframe(self._make_review_df(rows_600001), "600001", data_source="ReviewFixture")
        self.stock_repo.save_dataframe(self._make_review_df(rows_600002), "600002", data_source="ReviewFixture")
        self.stock_repo.save_dataframe(self._make_review_df(rows_300123), "300123", data_source="ReviewFixture")
        self.stock_repo.save_dataframe(self._make_review_df(rows_benchmark), "000300", data_source="ReviewFixture")

        previous = self.service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="2026-04-10 watchlist",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-10",
            source_summary="scanner=daily",
            diagnostics={},
            universe_notes=[],
            scoring_notes=[],
            shortlist=[
                self._candidate_payload("600001", "算力龙头", 1, 84.0, "2026-04-09"),
                self._candidate_payload("600002", "机器人核心", 2, 78.0, "2026-04-09"),
            ],
            universe_size=300,
            preselected_size=60,
            evaluated_size=40,
        )
        current = self.service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="2026-04-13 watchlist",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-13",
            source_summary="scanner=daily",
            diagnostics={},
            universe_notes=[],
            scoring_notes=[],
            shortlist=[
                self._candidate_payload("300123", "高景气成长", 1, 88.0, "2026-04-10"),
                self._candidate_payload("600001", "算力龙头", 2, 82.0, "2026-04-10"),
            ],
            universe_size=320,
            preselected_size=62,
            evaluated_size=42,
        )
        self._set_run_timestamps(previous["id"], "2026-04-10T08:40:00", "2026-04-10T08:41:00")
        self._set_run_timestamps(current["id"], "2026-04-13T08:40:00", "2026-04-13T08:41:00")
        return previous["id"], current["id"]

    def test_run_scan_builds_ranked_shortlist_and_persists_history(self) -> None:
        result = self.service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["market"], "cn")
        self.assertEqual(result["shortlist_size"], 3)
        self.assertEqual(result["headline"].startswith("今日 A 股盘前优先观察："), True)
        self.assertGreaterEqual(result["diagnostics"]["history_stats"]["local_hits"], 1)
        self.assertIn("scannerContextFrame", result)
        self.assertFalse(result["scannerContextFrame"]["marketReadiness"]["researchReady"])
        self.assertNotIn("600001", self.data_manager.daily_history_calls)

        shortlist = result["shortlist"]
        shortlist_signature = [
            (item["symbol"], item["rank"], round(float(item["score"]), 4))
            for item in shortlist
        ]
        self.assertEqual(shortlist[0]["symbol"], "600001")
        self.assertEqual(shortlist[0]["rank"], 1)
        self.assertTrue(shortlist[0]["reason_summary"])
        self.assertGreaterEqual(len(shortlist[0]["key_metrics"]), 4)
        self.assertGreaterEqual(len(shortlist[0]["risk_notes"]), 1)
        self.assertGreaterEqual(len(shortlist[0]["watch_context"]), 3)
        self.assertIn("AI算力", shortlist[0]["boards"])
        self.assertEqual(
            [item["rank"] for item in shortlist],
            list(range(1, len(shortlist) + 1)),
        )
        self.assertEqual(
            [round(float(item["score"]), 4) for item in shortlist],
            sorted(
                [round(float(item["score"]), 4) for item in shortlist],
                reverse=True,
            ),
        )

        history = self.service.list_runs(market="cn", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["id"], result["id"])
        self.assertEqual(
            history["items"][0]["top_symbols"],
            [item["symbol"] for item in shortlist],
        )

        detail = self.service.get_run_detail(result["id"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["shortlist"][0]["symbol"], "600001")
        self.assertEqual(detail["shortlist"][0]["appeared_in_recent_runs"], 0)
        self.assertEqual(
            [
                (item["symbol"], item["rank"], round(float(item["score"]), 4))
                for item in detail["shortlist"]
            ],
            shortlist_signature,
        )

    def test_get_run_detail_adds_supportive_scanner_context_frame_for_us_runs(self) -> None:
        detail = self._record_context_run(
            market="us",
            profile="us_preopen_v1",
            diagnostics={
                "market_temperature": {
                    "source": "computed",
                    "freshness": "cached",
                    "conclusionAllowed": True,
                    "marketRegimeSynthesis": {
                        "primaryRegime": "risk_on_liquidity_expansion",
                        "confidence": 0.78,
                        "confidenceLabel": "high",
                        "blockers": [],
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                    },
                    "capitalFlowSignal": {
                        "likelyDestination": "growth_ai_software_semis",
                        "explanation": "Liquidity still leans into growth leadership.",
                        "freshness": "cached",
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                        "contradictionCodes": [],
                    },
                    "rotationFamilyRollup": [
                        {
                            "familyId": "ai",
                            "familyLabel": "AI",
                            "themeFlowSignal": {
                                "themeFlowState": "leading",
                                "explanation": "AI themes still lead the tape.",
                                "freshness": "cached",
                                "observationOnly": False,
                                "sourceAuthorityAllowed": True,
                                "scoreContributionAllowed": True,
                            },
                        },
                        {
                            "familyId": "software",
                            "familyLabel": "Software",
                            "themeFlowSignal": {
                                "themeFlowState": "broadening",
                                "explanation": "Software participation is broadening.",
                                "freshness": "cached",
                                "observationOnly": False,
                                "sourceAuthorityAllowed": True,
                                "scoreContributionAllowed": True,
                            },
                        },
                    ],
                },
            },
        )

        frame = detail["scannerContextFrame"]
        self.assertTrue(frame["marketReadiness"]["researchReady"])
        self.assertEqual(frame["marketReadiness"]["readinessState"], "ready")
        self.assertEqual(frame["macroRegime"]["state"], "supportive")
        self.assertEqual(frame["macroRegime"]["source"], "computed")
        self.assertEqual(frame["macroRegime"]["freshness"], "cached")
        self.assertEqual(frame["macroRegime"]["confidence"]["label"], "high")
        self.assertEqual(frame["liquidityFrame"]["state"], "supportive")
        self.assertFalse(frame["liquidityFrame"]["observationOnly"])
        self.assertEqual(frame["assetClassBias"]["state"], "supportive")
        self.assertEqual(frame["themeFrame"]["state"], "supportive")
        self.assertEqual([item["id"] for item in frame["themeFrame"]["themes"]], ["ai", "software"])
        self.assertEqual(frame["universePolicy"]["type"], "default")
        self.assertTrue(frame["noAdviceBoundary"])

    def test_get_run_detail_adapts_cached_market_temperature_context_for_us_runs(self) -> None:
        market_cache.set(
            "temperature_input_snapshot",
            {
                "source": "computed",
                "freshness": "cached",
                "marketRegimeSynthesis": {
                    "primaryRegime": "risk_on_liquidity_expansion",
                    "confidence": 0.78,
                    "confidenceLabel": "high",
                    "blockers": [],
                    "observationOnly": False,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "freshness": "cached",
                },
                "capitalFlowSignal": {
                    "likelyDestination": "growth_ai_software_semis",
                    "explanation": "Liquidity still leans into growth leadership.",
                    "freshness": "cached",
                    "observationOnly": False,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "contradictionCodes": [],
                    "source": "market_overview",
                },
                "rotationFamilyRollup": [
                    {
                        "familyId": "ai",
                        "familyLabel": "AI",
                        "themeFlowSignal": {
                            "themeFlowState": "leading",
                            "explanation": "AI themes still lead the tape.",
                            "freshness": "cached",
                            "observationOnly": False,
                            "sourceAuthorityAllowed": True,
                            "scoreContributionAllowed": True,
                            "source": "rotation_radar",
                        },
                    },
                    {
                        "familyId": "software",
                        "familyLabel": "Software",
                        "themeFlowSignal": {
                            "themeFlowState": "broadening",
                            "explanation": "Software participation is broadening.",
                            "freshness": "cached",
                            "observationOnly": False,
                            "sourceAuthorityAllowed": True,
                            "scoreContributionAllowed": True,
                            "source": "rotation_radar",
                        },
                    },
                ],
            },
            ttl_seconds=60,
        )

        detail = self._record_context_run(
            market="us",
            profile="us_preopen_v1",
            diagnostics={},
        )

        frame = detail["scannerContextFrame"]
        self.assertTrue(frame["marketReadiness"]["researchReady"])
        self.assertEqual(frame["marketReadiness"]["readinessState"], "ready")
        self.assertEqual(frame["macroRegime"]["state"], "supportive")
        self.assertEqual(frame["liquidityFrame"]["state"], "supportive")
        self.assertEqual(frame["assetClassBias"]["state"], "supportive")
        self.assertEqual(frame["themeFrame"]["state"], "supportive")
        self.assertEqual([item["id"] for item in frame["themeFrame"]["themes"]], ["ai", "software"])

    def test_get_run_detail_scanner_context_frame_fail_closes_when_context_missing(self) -> None:
        detail = self._record_context_run(
            market="us",
            profile="us_preopen_v1",
            diagnostics={},
        )

        frame = detail["scannerContextFrame"]
        self.assertFalse(frame["marketReadiness"]["researchReady"])
        self.assertEqual(frame["marketReadiness"]["readinessState"], "insufficient")
        self.assertIn("macro", frame["marketReadiness"]["missingEvidence"])
        self.assertIn("liquidity", frame["marketReadiness"]["missingEvidence"])
        self.assertEqual(frame["macroRegime"]["state"], "insufficient")
        self.assertEqual(frame["liquidityFrame"]["state"], "insufficient")
        self.assertEqual(frame["assetClassBias"]["state"], "observe_only")
        self.assertEqual(frame["themeFrame"]["state"], "insufficient")
        self.assertEqual(frame["themeFrame"]["themes"], [])
        self.assertTrue(frame["noAdviceBoundary"])

    def test_get_run_detail_scanner_context_frame_marks_fallback_proxy_context_observe_only(self) -> None:
        detail = self._record_context_run(
            market="us",
            profile="us_preopen_v1",
            diagnostics={
                "market_temperature": {
                    "source": "mixed",
                    "freshness": "fallback",
                    "conclusionAllowed": False,
                    "marketRegimeSynthesis": {
                        "primaryRegime": "risk_on_liquidity_expansion",
                        "confidence": 0.42,
                        "confidenceLabel": "low",
                        "blockers": [{"key": "proxy_context_only"}],
                        "observationOnly": True,
                        "sourceAuthorityAllowed": False,
                        "scoreContributionAllowed": False,
                    },
                    "capitalFlowSignal": {
                        "likelyDestination": "growth_ai_software_semis",
                        "explanation": "Proxy-only liquidity context.",
                        "freshness": "fallback",
                        "observationOnly": True,
                        "sourceAuthorityAllowed": False,
                        "scoreContributionAllowed": False,
                        "proxyOnly": True,
                        "contradictionCodes": ["proxy_context_only"],
                    },
                    "rotationFamilyRollup": [
                        {
                            "familyId": "ai",
                            "familyLabel": "AI",
                            "themeFlowSignal": {
                                "themeFlowState": "leading",
                                "explanation": "Leadership is still observation-only.",
                                "freshness": "fallback",
                                "observationOnly": True,
                                "sourceAuthorityAllowed": False,
                                "scoreContributionAllowed": False,
                                "proxyOnly": True,
                            },
                        }
                    ],
                },
            },
        )

        frame = detail["scannerContextFrame"]
        self.assertFalse(frame["marketReadiness"]["researchReady"])
        self.assertEqual(frame["marketReadiness"]["readinessState"], "observe_only")
        self.assertEqual(frame["marketReadiness"]["freshnessFloor"], "fallback")
        self.assertEqual(frame["marketReadiness"]["sourceAuthority"], "observationOnly")
        self.assertEqual(frame["macroRegime"]["state"], "observe_only")
        self.assertEqual(frame["liquidityFrame"]["state"], "observe_only")
        self.assertTrue(frame["liquidityFrame"]["proxyOnly"])
        self.assertEqual(frame["assetClassBias"]["state"], "observe_only")
        self.assertEqual(frame["themeFrame"]["state"], "observe_only")
        self.assertTrue(frame["themeFrame"]["proxyOnly"])

    def test_get_run_detail_adapts_cached_fallback_context_as_observe_only(self) -> None:
        market_cache.set(
            "temperature_input_snapshot",
            {
                "source": "mixed",
                "freshness": "fallback",
                "marketRegimeSynthesis": {
                    "primaryRegime": "risk_on_liquidity_expansion",
                    "confidence": 0.42,
                    "confidenceLabel": "low",
                    "blockers": [{"key": "proxy_context_only"}],
                    "observationOnly": True,
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "freshness": "fallback",
                },
                "capitalFlowSignal": {
                    "likelyDestination": "growth_ai_software_semis",
                    "explanation": "Proxy-only liquidity context.",
                    "freshness": "fallback",
                    "observationOnly": True,
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "proxyOnly": True,
                    "contradictionCodes": ["proxy_context_only"],
                    "source": "market_overview",
                },
                "rotationFamilyRollup": [
                    {
                        "familyId": "ai",
                        "familyLabel": "AI",
                        "themeFlowSignal": {
                            "themeFlowState": "leading",
                            "explanation": "Leadership is still observation-only.",
                            "freshness": "fallback",
                            "observationOnly": True,
                            "sourceAuthorityAllowed": False,
                            "scoreContributionAllowed": False,
                            "proxyOnly": True,
                            "source": "rotation_radar",
                        },
                    }
                ],
            },
            ttl_seconds=60,
        )

        detail = self._record_context_run(
            market="us",
            profile="us_preopen_v1",
            diagnostics={},
        )

        frame = detail["scannerContextFrame"]
        self.assertFalse(frame["marketReadiness"]["researchReady"])
        self.assertEqual(frame["marketReadiness"]["readinessState"], "observe_only")
        self.assertEqual(frame["marketReadiness"]["freshnessFloor"], "fallback")
        self.assertEqual(frame["marketReadiness"]["sourceAuthority"], "observationOnly")
        self.assertEqual(frame["macroRegime"]["state"], "observe_only")
        self.assertEqual(frame["liquidityFrame"]["state"], "observe_only")
        self.assertEqual(frame["assetClassBias"]["state"], "observe_only")
        self.assertEqual(frame["themeFrame"]["state"], "observe_only")
        self.assertTrue(frame["liquidityFrame"]["proxyOnly"])
        self.assertTrue(frame["themeFrame"]["proxyOnly"])

    def test_get_run_detail_scanner_context_frame_blocks_unavailable_cn_context(self) -> None:
        detail = self._record_context_run(
            market="cn",
            profile="cn_preopen_v1",
            diagnostics={
                "market_temperature": {
                    "source": "fallback",
                    "freshness": "unavailable",
                    "conclusionAllowed": False,
                    "marketRegimeSynthesis": {
                        "primaryRegime": "data_insufficient",
                        "confidence": 0.0,
                        "confidenceLabel": "insufficient",
                        "blockers": [{"key": "cn_context_unavailable"}],
                        "observationOnly": True,
                        "sourceAuthorityAllowed": False,
                        "scoreContributionAllowed": False,
                    },
                    "capitalFlowSignal": {
                        "liquidityImpulse": "data_insufficient",
                        "explanation": "CN macro/liquidity context unavailable.",
                        "freshness": "unavailable",
                        "observationOnly": True,
                        "sourceAuthorityAllowed": False,
                        "scoreContributionAllowed": False,
                        "missingProviderReason": "cn_context_unavailable",
                    },
                    "rotationFamilyRollup": [],
                },
            },
        )

        frame = detail["scannerContextFrame"]
        self.assertFalse(frame["marketReadiness"]["researchReady"])
        self.assertIn(frame["marketReadiness"]["readinessState"], {"insufficient", "observe_only"})
        self.assertEqual(frame["macroRegime"]["state"], "blocked")
        self.assertEqual(frame["liquidityFrame"]["state"], "blocked")
        self.assertEqual(frame["assetClassBias"]["state"], "blocked")
        self.assertEqual(frame["themeFrame"]["state"], "blocked")
        self.assertTrue(frame["macroRegime"]["blockers"])
        self.assertTrue(frame["liquidityFrame"]["blockers"])

    def test_get_run_detail_preserves_cn_blocked_overlay_over_supportive_cached_context(self) -> None:
        market_cache.set(
            "temperature_input_snapshot",
            {
                "source": "computed",
                "freshness": "cached",
                "marketRegimeSynthesis": {
                    "primaryRegime": "risk_on_liquidity_expansion",
                    "confidence": 0.81,
                    "confidenceLabel": "high",
                    "blockers": [],
                    "observationOnly": False,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "freshness": "cached",
                },
                "capitalFlowSignal": {
                    "likelyDestination": "growth_ai_software_semis",
                    "freshness": "cached",
                    "observationOnly": False,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "contradictionCodes": [],
                    "source": "market_overview",
                },
                "rotationFamilyRollup": [
                    {
                        "familyId": "ai",
                        "familyLabel": "AI",
                        "themeFlowSignal": {
                            "themeFlowState": "leading",
                            "freshness": "cached",
                            "observationOnly": False,
                            "sourceAuthorityAllowed": True,
                            "scoreContributionAllowed": True,
                            "source": "rotation_radar",
                        },
                    }
                ],
            },
            ttl_seconds=60,
        )

        detail = self.service.record_failed_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            trigger_mode="manual",
            request_source="test",
            watchlist_date="2026-06-03",
            error_message="A 股全市场快照不可用。",
            diagnostics={
                "reason_code": "no_realtime_snapshot_available",
                "universe_resolution": {
                    "success": True,
                    "source": "builtin_stock_mapping",
                },
                "snapshot_resolution": {
                    "success": False,
                    "source": None,
                    "error_code": "no_realtime_snapshot_available",
                    "attempts": [
                        {
                            "fetcher": "AkshareFetcher",
                            "status": "failed",
                            "reason_code": "akshare_snapshot_fetch_failed",
                        }
                    ],
                },
                "universe_selection": {"universe_type": "default"},
            },
            source_summary="scanner=test",
            scope="user",
        )

        frame = detail["scannerContextFrame"]
        self.assertEqual(frame["marketReadiness"]["readinessState"], "blocked")
        self.assertEqual(frame["macroRegime"]["state"], "blocked")
        self.assertEqual(frame["liquidityFrame"]["state"], "blocked")
        self.assertEqual(frame["assetClassBias"]["state"], "blocked")
        self.assertEqual(frame["themeFrame"]["state"], "blocked")

    def test_get_run_detail_projects_blocked_cn_universe_readiness(self) -> None:
        detail = self.service.record_failed_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            trigger_mode="manual",
            request_source="test",
            watchlist_date="2026-06-03",
            error_message="A 股股票 universe 不可用。",
            diagnostics={
                "reason_code": "universe_source_unavailable",
                "universe_resolution": {
                    "success": False,
                    "source": None,
                    "error_code": "universe_source_unavailable",
                    "attempts": [
                        {
                            "fetcher": "local_universe_cache",
                            "status": "failed",
                            "reason_code": "local_universe_cache_missing",
                        },
                        {
                            "fetcher": "AkshareFetcher",
                            "status": "failed",
                            "reason_code": "akshare_stock_list_failed",
                        },
                    ],
                },
                "snapshot_resolution": {},
                "universe_selection": {"universe_type": "default"},
            },
            source_summary=(
                "universe=unknown; snapshot=unknown; history=local_first; degraded=no; "
                "universe_attempts=local_universe_cache:failed(local_universe_cache_missing),"
                "AkshareFetcher:failed(akshare_stock_list_failed); snapshot_attempts=none"
            ),
            scope="user",
        )

        frame = detail["scannerContextFrame"]
        readiness = frame["marketReadiness"]
        self.assertEqual(detail["status"], "failed")
        self.assertFalse(readiness["researchReady"])
        self.assertEqual(readiness["market"], "cn")
        self.assertEqual(readiness["universeType"], "default")
        self.assertEqual(readiness["readinessState"], "blocked")
        self.assertIn("universe_source_unavailable", readiness["blockedReasons"])
        self.assertIn("local_universe_cache_missing", readiness["blockedReasons"])
        self.assertIn("technical", readiness["missingEvidence"])
        self.assertEqual(readiness["providerAuthority"], "unavailable")
        self.assertEqual(readiness["sourceAuthority"], "unavailable")
        self.assertEqual(readiness["freshness"], "unavailable")
        self.assertEqual(readiness["sourceTier"], "unavailable")
        self.assertTrue(readiness["noAdviceBoundary"])
        self.assertEqual(frame["universePolicy"]["type"], "default")

    def test_get_run_detail_projects_blocked_cn_snapshot_readiness(self) -> None:
        detail = self.service.record_failed_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            trigger_mode="manual",
            request_source="test",
            watchlist_date="2026-06-03",
            error_message="A 股全市场快照不可用。",
            diagnostics={
                "reason_code": "no_realtime_snapshot_available",
                "universe_resolution": {
                    "success": True,
                    "source": "builtin_stock_mapping",
                    "attempts": [
                        {
                            "fetcher": "builtin_stock_mapping",
                            "status": "success",
                            "rows": 300,
                        }
                    ],
                },
                "snapshot_resolution": {
                    "success": False,
                    "source": None,
                    "error_code": "no_realtime_snapshot_available",
                    "attempts": [
                        {
                            "fetcher": "AkshareFetcher",
                            "status": "failed",
                            "reason_code": "akshare_snapshot_fetch_failed",
                        },
                        {
                            "fetcher": "EfinanceFetcher",
                            "status": "failed",
                            "reason_code": "efinance_snapshot_fetch_failed",
                        },
                    ],
                },
                "universe_selection": {"universe_type": "default"},
            },
            source_summary=(
                "universe=builtin_stock_mapping; snapshot=unknown; history=local_first; degraded=no; "
                "universe_attempts=builtin_stock_mapping:success; "
                "snapshot_attempts=AkshareFetcher:failed(akshare_snapshot_fetch_failed),"
                "EfinanceFetcher:failed(efinance_snapshot_fetch_failed)"
            ),
            scope="user",
        )

        readiness = detail["scannerContextFrame"]["marketReadiness"]
        self.assertEqual(readiness["readinessState"], "blocked")
        self.assertIn("no_realtime_snapshot_available", readiness["blockedReasons"])
        self.assertIn("akshare_snapshot_fetch_failed", readiness["blockedReasons"])
        self.assertIn("freshness", readiness["missingEvidence"])
        self.assertEqual(readiness["providerAuthority"], "unavailable")
        self.assertEqual(readiness["freshness"], "unavailable")
        self.assertTrue(readiness["nextEvidenceNeeded"])

    def test_scanner_context_frame_does_not_mutate_shortlist_rank_or_score(self) -> None:
        shortlist = [
            self._candidate_payload("NVDA", "NVIDIA", 1, 91.2, "2026-06-02"),
            self._candidate_payload("AAPL", "Apple", 2, 86.4, "2026-06-02"),
        ]
        baseline = self._record_context_run(
            market="us",
            profile="us_preopen_v1",
            diagnostics={},
            shortlist=shortlist,
        )
        contextual = self._record_context_run(
            market="us",
            profile="us_preopen_v1",
            diagnostics={
                "market_temperature": {
                    "source": "computed",
                    "freshness": "cached",
                    "conclusionAllowed": True,
                    "marketRegimeSynthesis": {
                        "primaryRegime": "risk_on_liquidity_expansion",
                        "confidence": 0.74,
                        "confidenceLabel": "high",
                        "blockers": [],
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                    },
                    "capitalFlowSignal": {
                        "likelyDestination": "growth_ai_software_semis",
                        "freshness": "cached",
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                    },
                    "rotationFamilyRollup": [
                        {
                            "familyId": "ai",
                            "familyLabel": "AI",
                            "themeFlowSignal": {
                                "themeFlowState": "leading",
                                "freshness": "cached",
                                "observationOnly": False,
                                "sourceAuthorityAllowed": True,
                                "scoreContributionAllowed": True,
                            },
                        }
                    ],
                },
            },
            shortlist=shortlist,
        )

        baseline_signature = [
            (item["symbol"], item["rank"], float(item["score"]))
            for item in baseline["shortlist"]
        ]
        contextual_signature = [
            (item["symbol"], item["rank"], float(item["score"]))
            for item in contextual["shortlist"]
        ]
        self.assertEqual(contextual_signature, baseline_signature)
        self.assertEqual(
            [(item["symbol"], item["rank"], float(item["score"])) for item in contextual["selected"]],
            baseline_signature,
        )

    def test_prepare_shortlist_sorts_by_score_then_symbol_and_assigns_rank_before_ai(self) -> None:
        ai_service = RecordingScannerAiService()
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
            ai_interpretation_service=ai_service,
        )

        ranked_candidates, shortlist, _ = service._prepare_shortlist(
            profile_config=get_scanner_profile(market="us", profile="us_preopen_v1"),
            evaluated_candidates=[
                {"symbol": "NVDA", "score": 91.0},
                {"symbol": "PLTR", "score": 88.5},
                {"symbol": "AAPL", "score": 91.0},
            ],
            resolved_shortlist_size=3,
        )

        expected_signature = [
            ("AAPL", 1, 91.0),
            ("NVDA", 2, 91.0),
            ("PLTR", 3, 88.5),
        ]
        self.assertEqual(
            [(item["symbol"], item["rank"], float(item["score"])) for item in shortlist],
            expected_signature,
        )
        self.assertEqual(
            [(item["symbol"], item["rank"], float(item["score"])) for item in ranked_candidates],
            expected_signature,
        )
        self.assertEqual(ai_service.received_signature, expected_signature)

    def test_finalize_completed_scan_reuses_common_persistence_and_response_flow(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
            ai_interpretation_service=FakeScannerAiService(),
        )
        profile = get_scanner_profile(market="cn", profile="cn_preopen_v1")
        run_started_at = datetime.fromisoformat("2026-04-16T08:40:00")
        run_completed_at = datetime.fromisoformat("2026-04-16T08:41:15")
        evaluated_candidates = [
            self._candidate_payload("600001", "算力龙头", 0, 86.2, "2026-04-15"),
            self._candidate_payload("600002", "机器人核心", 0, 79.5, "2026-04-15"),
        ]
        diagnostics = {
            "market": "cn",
            "profile": profile.key,
            "profile_label": profile.label,
            "stock_list_source": "FakeListSource",
            "snapshot_source": "FakeSnapshotSource",
            "history_mode": "local_first",
        }

        result = service._finalize_completed_scan(
            profile_config=profile,
            run_started_at=run_started_at,
            run_completed_at=run_completed_at,
            scope="user",
            owner_id=service._resolve_persisted_owner_id(scope="user"),
            resolved_shortlist_size=1,
            universe_size=6,
            preselected_size=2,
            evaluated_candidates=evaluated_candidates,
            source_summary="scanner=test",
            universe_notes=["note"],
            scoring_notes=["score-note"],
            diagnostics=diagnostics,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["shortlist_size"], 1)
        self.assertEqual(result["shortlist"][0]["symbol"], "600001")
        self.assertEqual(result["shortlist"][0]["rank"], 1)
        self.assertEqual(result["shortlist"][0]["appeared_in_recent_runs"], 0)
        self.assertEqual(result["diagnostics"]["ai_interpretation"]["status"], "completed")
        self.assertEqual(result["diagnostics"]["run_duration_seconds"], 75.0)

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        self.assertEqual(detail["headline"], result["headline"])
        self.assertEqual(detail["shortlist"][0]["symbol"], "600001")
        self.assertTrue(detail["shortlist"][0]["ai_interpretation"]["available"])

    def test_run_scan_ai_interpretation_remains_additive_to_ranking(self) -> None:
        baseline_service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
        )
        baseline_result = baseline_service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )
        baseline_signature = [
            (item["symbol"], item["rank"], round(float(item["score"]), 4))
            for item in baseline_result["shortlist"]
        ]

        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
            ai_interpretation_service=FakeScannerAiService(),
        )

        result = service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(
            [
                (item["symbol"], item["rank"], round(float(item["score"]), 4))
                for item in result["shortlist"]
            ],
            baseline_signature,
        )
        self.assertEqual(result["diagnostics"]["ai_interpretation"]["status"], "completed")
        self.assertTrue(result["shortlist"][0]["ai_interpretation"]["available"])
        self.assertEqual(result["shortlist"][0]["ai_interpretation"]["opportunity_type"], "临界突破")

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        self.assertIn("review_commentary", detail["shortlist"][0]["ai_interpretation"])

    def test_apply_score_caps_and_explainability_caps_fallback_candidates(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
        )
        candidate = {
            "symbol": "PLTR",
            "name": "Palantir",
            "score": 81.6,
            "reason_summary": "趋势与量能共振。",
            "ret_5d": 6.8,
            "ret_20d": 18.4,
            "avg_amount_20": 7.6e8,
            "amount": 7.67e8,
            "avg_volume_20": 34_000_000,
            "volume_expansion_20": 1.7,
            "atr20_pct": 4.8,
            "_relative_strength_pct": 0.92,
            "_component_scores": {
                "trend": 18.5,
                "momentum": 13.2,
                "liquidity": 14.0,
                "activity": 10.4,
                "volatility_quality": 6.6,
                "relative_strength": 9.2,
                "benchmark_relative": 7.1,
                "gap_context": 4.0,
                "penalties": 1.0,
            },
            "_diagnostics": {
                "history": {
                    "source": "local_db",
                    "latest_trade_date": "2026-05-16",
                    "rows": 130,
                },
                "quote_context": {
                    "available": False,
                    "source": "synthetic",
                },
            },
        }

        service._apply_score_caps_and_explainability(candidate)

        explainability = candidate["_diagnostics"]["score_explainability"]
        self.assertEqual(candidate["raw_score"], 81.6)
        self.assertEqual(candidate["final_score"], 40.0)
        self.assertEqual(candidate["score"], 40.0)
        self.assertEqual(explainability["cap_reason"], "fallback_source")
        self.assertEqual(explainability["degradation_reason"], "fallback_source")
        self.assertEqual(explainability["score_confidence"], 0.4)
        self.assertTrue(explainability["cap_applied"])
        self.assertIn("quote_context", explainability["missing_evidence"])
        self.assertEqual(explainability["source_confidence"]["capReason"], "fallback_source")

    def test_apply_score_caps_and_explainability_caps_degraded_snapshot_provenance(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
        )
        candidate = {
            "symbol": "600001",
            "name": "算力龙头",
            "score": 87.4,
            "reason_summary": "趋势与量能完整。",
            "ret_5d": 7.8,
            "ret_20d": 22.1,
            "avg_amount_20": 9.4e8,
            "amount": 1.26e9,
            "avg_volume_20": 48_000_000,
            "volume_expansion_20": 1.8,
            "atr20_pct": 4.1,
            "_relative_strength_pct": 0.95,
            "snapshot_source": "local_history_degraded",
            "_component_scores": {
                "trend": 18.8,
                "momentum": 13.8,
                "liquidity": 15.2,
                "activity": 10.6,
                "volatility_quality": 6.7,
                "relative_strength": 9.5,
                "benchmark_relative": 7.0,
                "gap_context": 5.8,
                "penalties": 0.0,
            },
            "_diagnostics": {
                "history": {
                    "source": "local_db",
                    "latest_trade_date": "2026-05-16",
                    "rows": 130,
                },
                "quote_context": {
                    "available": True,
                    "source": "akshare",
                },
                "snapshot_source": "local_history_degraded",
                "degraded_mode_used": True,
            },
        }

        service._apply_score_caps_and_explainability(candidate)

        explainability = candidate["_diagnostics"]["score_explainability"]
        self.assertEqual(candidate["raw_score"], 87.4)
        self.assertEqual(candidate["final_score"], 40.0)
        self.assertEqual(candidate["score"], 40.0)
        self.assertEqual(explainability["cap_reason"], "fallback_source")
        self.assertEqual(explainability["degradation_reason"], "fallback_source")
        self.assertEqual(explainability["score_confidence"], 0.4)
        self.assertTrue(explainability["cap_applied"])
        self.assertEqual(explainability["source_confidence"]["capReason"], "fallback_source")
        self.assertTrue(explainability["source_confidence"]["isFallback"])

    def test_apply_score_caps_and_explainability_locks_degraded_source_confidence_tokens(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
        )

        def make_candidate(
            *,
            quote_source: str = "alpaca",
            history_source: str = "local_db",
            history_stale: bool = False,
            atr20_pct: float | None = 3.7,
        ) -> dict:
            return {
                "symbol": "MSFT",
                "name": "Microsoft",
                "score": 83.6,
                "reason_summary": "锁定 scanner 当前 degraded token contract。",
                "ret_5d": 4.1,
                "ret_20d": 12.7,
                "avg_amount_20": 1.2e10,
                "amount": 1.1e10,
                "avg_volume_20": 22_000_000,
                "volume_expansion_20": 1.2,
                "atr20_pct": atr20_pct,
                "_relative_strength_pct": 0.81,
                "boards": ["软件"],
                "_component_scores": {
                    "trend": 18.0,
                    "momentum": 12.0,
                    "liquidity": 15.2,
                    "activity": 9.8,
                    "volatility_quality": 7.4,
                    "relative_strength": 8.1,
                    "benchmark_relative": 6.5,
                    "gap_context": 5.2,
                    "penalties": 0.0,
                },
                "_diagnostics": {
                    "history": {
                        "source": history_source,
                        "latest_trade_date": "2026-05-16",
                        "rows": 130,
                        "stale": history_stale,
                    },
                    "quote_context": {
                        "available": True,
                        "source": quote_source,
                    },
                },
            }

        cases = [
            {
                "token": "synthetic",
                "candidate": make_candidate(quote_source="synthetic"),
                "expected_cap_reason": "fallback_source",
                "expected_degradation_reason": "fallback_source",
                "expected_score_confidence": 0.2,
                "expected_score_cap": 20.0,
                "expected_final_score": 20.0,
                "expected_source_type": "synthetic_fixture",
                "expected_freshness": "synthetic",
                "expected_missing_evidence": [],
                "expected_score_grade_allowed": False,
                "expected_observation_only": True,
                "expected_flags": {
                    "isSynthetic": True,
                    "isUnavailable": False,
                    "isFallback": True,
                    "isStale": False,
                    "isPartial": False,
                },
            },
            {
                "token": "synthetic_fixture",
                "candidate": make_candidate(quote_source="synthetic_fixture"),
                "expected_cap_reason": "synthetic_source",
                "expected_degradation_reason": "synthetic_source",
                "expected_score_confidence": 0.2,
                "expected_score_cap": 20.0,
                "expected_final_score": 20.0,
                "expected_source_type": "synthetic_fixture",
                "expected_freshness": "synthetic",
                "expected_missing_evidence": [],
                "expected_score_grade_allowed": True,
                "expected_observation_only": False,
                "expected_flags": {
                    "isSynthetic": True,
                    "isUnavailable": False,
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                },
            },
            {
                "token": "unavailable",
                "candidate": make_candidate(quote_source="unavailable"),
                "expected_cap_reason": "unavailable_source",
                "expected_degradation_reason": "unavailable_source",
                "expected_score_confidence": 0.0,
                "expected_score_cap": 0.0,
                "expected_final_score": 0.0,
                "expected_source_type": "missing",
                "expected_freshness": "unavailable",
                "expected_missing_evidence": [],
                "expected_score_grade_allowed": True,
                "expected_observation_only": False,
                "expected_flags": {
                    "isSynthetic": False,
                    "isUnavailable": True,
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                },
            },
            {
                "token": "missing",
                "candidate": make_candidate(quote_source="missing"),
                "expected_cap_reason": "unavailable_source",
                "expected_degradation_reason": "unavailable_source",
                "expected_score_confidence": 0.0,
                "expected_score_cap": 0.0,
                "expected_final_score": 0.0,
                "expected_source_type": "missing",
                "expected_freshness": "unavailable",
                "expected_missing_evidence": [],
                "expected_score_grade_allowed": True,
                "expected_observation_only": False,
                "expected_flags": {
                    "isSynthetic": False,
                    "isUnavailable": True,
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": False,
                },
            },
            {
                "token": "fallback_source",
                "candidate": make_candidate(quote_source="fallback"),
                "expected_cap_reason": "fallback_source",
                "expected_degradation_reason": "fallback_source",
                "expected_score_confidence": 0.4,
                "expected_score_cap": 40.0,
                "expected_final_score": 40.0,
                "expected_source_type": "fallback_static",
                "expected_freshness": "fallback",
                "expected_missing_evidence": [],
                "expected_score_grade_allowed": False,
                "expected_observation_only": True,
                "expected_flags": {
                    "isSynthetic": False,
                    "isUnavailable": False,
                    "isFallback": True,
                    "isStale": False,
                    "isPartial": False,
                },
            },
            {
                "token": "stale_source",
                "candidate": make_candidate(history_stale=True),
                "expected_cap_reason": "stale_source",
                "expected_degradation_reason": "stale_source",
                "expected_score_confidence": 0.6,
                "expected_score_cap": 60.0,
                "expected_final_score": 60.0,
                "expected_source_type": "official_public",
                "expected_freshness": "stale",
                "expected_missing_evidence": [],
                "expected_score_grade_allowed": False,
                "expected_observation_only": True,
                "expected_flags": {
                    "isSynthetic": False,
                    "isUnavailable": False,
                    "isFallback": False,
                    "isStale": True,
                    "isPartial": False,
                },
            },
            {
                "token": "partial_coverage",
                "candidate": make_candidate(atr20_pct=None),
                "expected_cap_reason": "partial_coverage",
                "expected_degradation_reason": "partial_coverage",
                "expected_score_confidence": 0.7,
                "expected_score_cap": 70.0,
                "expected_final_score": 70.0,
                "expected_source_type": "official_public",
                "expected_freshness": "partial",
                "expected_missing_evidence": ["risk"],
                "expected_score_grade_allowed": False,
                "expected_observation_only": True,
                "expected_flags": {
                    "isSynthetic": False,
                    "isUnavailable": False,
                    "isFallback": False,
                    "isStale": False,
                    "isPartial": True,
                },
            },
        ]

        for case in cases:
            with self.subTest(token=case["token"]):
                candidate = case["candidate"]

                service._apply_score_caps_and_explainability(candidate)

                explainability = candidate["_diagnostics"]["score_explainability"]
                source_confidence = explainability["source_confidence"]
                self.assertEqual(candidate["raw_score"], 83.6)
                self.assertEqual(candidate["final_score"], case["expected_final_score"])
                self.assertEqual(candidate["score"], case["expected_final_score"])
                for key in (
                    "raw_score",
                    "final_score",
                    "score_cap",
                    "score_confidence",
                    "cap_reason",
                    "degradation_reason",
                    "missing_evidence",
                    "source_confidence",
                ):
                    self.assertIn(key, explainability)
                self.assertEqual(explainability["score_cap"], case["expected_score_cap"])
                self.assertEqual(explainability["score_confidence"], case["expected_score_confidence"])
                self.assertEqual(explainability["cap_reason"], case["expected_cap_reason"])
                self.assertEqual(explainability["degradation_reason"], case["expected_degradation_reason"])
                self.assertEqual(explainability["missing_evidence"], case["expected_missing_evidence"])
                self.assertTrue(explainability["cap_applied"])
                self.assertEqual(explainability["score_grade_allowed"], case["expected_score_grade_allowed"])
                self.assertEqual(source_confidence["capReason"], case["expected_cap_reason"])
                self.assertEqual(source_confidence["degradationReason"], case["expected_degradation_reason"])
                self.assertEqual(source_confidence["confidenceWeight"], case["expected_score_confidence"])
                self.assertEqual(source_confidence["freshness"], case["expected_freshness"])
                self.assertEqual(source_confidence["sourceType"], case["expected_source_type"])
                self.assertEqual(source_confidence["scoreContributionAllowed"], case["expected_score_grade_allowed"])
                self.assertEqual(source_confidence["sourceAuthorityAllowed"], case["expected_score_grade_allowed"])
                self.assertEqual(source_confidence["observationOnly"], case["expected_observation_only"])
                for flag_name, expected_value in case["expected_flags"].items():
                    self.assertEqual(source_confidence[flag_name], expected_value)

    def test_apply_score_caps_and_explainability_caps_stale_and_partial_candidates(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
        )
        stale_candidate = {
            "symbol": "NVDA",
            "name": "NVIDIA",
            "score": 84.3,
            "reason_summary": "趋势完好。",
            "ret_5d": 7.1,
            "ret_20d": 20.4,
            "avg_amount_20": 2.9e10,
            "amount": 3.95e10,
            "avg_volume_20": 48_000_000,
            "volume_expansion_20": 1.5,
            "atr20_pct": 4.2,
            "_relative_strength_pct": 0.94,
            "_component_scores": {
                "trend": 19.0,
                "momentum": 14.2,
                "liquidity": 16.0,
                "activity": 10.8,
                "volatility_quality": 6.8,
                "relative_strength": 9.4,
                "benchmark_relative": 7.5,
                "gap_context": 2.6,
                "penalties": 2.0,
            },
            "_diagnostics": {
                "history": {
                    "source": "local_db",
                    "latest_trade_date": "2026-05-12",
                    "rows": 130,
                    "stale": True,
                },
                "quote_context": {
                    "available": True,
                    "source": "yfinance",
                },
            },
        }
        partial_candidate = {
            "symbol": "AAPL",
            "name": "Apple",
            "score": 79.4,
            "reason_summary": "需要补足风险证据。",
            "ret_5d": 5.4,
            "ret_20d": 15.1,
            "avg_amount_20": 8.1e9,
            "amount": 7.72e9,
            "avg_volume_20": 39_000_000,
            "volume_expansion_20": 1.3,
            "atr20_pct": None,
            "_relative_strength_pct": 0.88,
            "_component_scores": {
                "trend": 18.4,
                "momentum": 12.6,
                "liquidity": 14.8,
                "activity": 10.0,
                "volatility_quality": 8.0,
                "relative_strength": 8.8,
                "benchmark_relative": 6.2,
                "gap_context": 3.6,
                "penalties": 3.0,
            },
            "_diagnostics": {
                "history": {
                    "source": "local_db",
                    "latest_trade_date": "2026-05-16",
                    "rows": 130,
                },
                "quote_context": {
                    "available": True,
                    "source": "yfinance",
                },
            },
        }

        service._apply_score_caps_and_explainability(stale_candidate)
        service._apply_score_caps_and_explainability(partial_candidate)

        stale_explainability = stale_candidate["_diagnostics"]["score_explainability"]
        partial_explainability = partial_candidate["_diagnostics"]["score_explainability"]
        self.assertEqual(stale_candidate["score"], 60.0)
        self.assertEqual(stale_explainability["cap_reason"], "stale_source")
        self.assertEqual(stale_explainability["score_confidence"], 0.6)
        self.assertEqual(partial_candidate["score"], 70.0)
        self.assertEqual(partial_explainability["cap_reason"], "partial_coverage")
        self.assertEqual(partial_explainability["score_confidence"], 0.7)
        self.assertIn("risk", partial_explainability["missing_evidence"])

    def test_apply_score_caps_and_explainability_caps_public_proxy_quote_sources(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
        )
        candidate = {
            "symbol": "MSFT",
            "name": "Microsoft",
            "score": 82.2,
            "reason_summary": "证据完整。",
            "ret_5d": 4.1,
            "ret_20d": 12.7,
            "avg_amount_20": 1.2e10,
            "amount": 1.1e10,
            "avg_volume_20": 22_000_000,
            "volume_expansion_20": 1.2,
            "atr20_pct": 3.7,
            "_relative_strength_pct": 0.81,
            "boards": ["软件"],
            "_component_scores": {
                "trend": 18.0,
                "momentum": 12.0,
                "liquidity": 15.2,
                "activity": 9.8,
                "volatility_quality": 7.4,
                "relative_strength": 8.1,
                "benchmark_relative": 6.5,
                "gap_context": 5.2,
                "penalties": 0.0,
            },
            "_diagnostics": {
                "history": {
                    "source": "local_db",
                    "latest_trade_date": "2026-05-16",
                    "rows": 130,
                },
                "quote_context": {
                    "available": True,
                    "source": "yfinance",
                    "sourceLabel": "Yahoo Finance public proxy",
                },
            },
        }

        service._apply_score_caps_and_explainability(candidate)
        packet = build_scanner_evidence_packet(
            candidate,
            context={
                "market": "us",
                "score_explainability": candidate["_diagnostics"]["score_explainability"],
            },
        )

        explainability = candidate["_diagnostics"]["score_explainability"]
        self.assertEqual(candidate["raw_score"], 82.2)
        self.assertEqual(candidate["final_score"], 75.0)
        self.assertEqual(candidate["score"], 75.0)
        self.assertTrue(explainability["cap_applied"])
        self.assertEqual(explainability["cap_reason"], "proxy_quote_source_capped")
        self.assertEqual(explainability["degradation_reason"], "public_proxy_not_score_grade")
        self.assertEqual(explainability["score_confidence"], 0.75)
        self.assertFalse(explainability["score_grade_allowed"])
        self.assertFalse(explainability["source_confidence"]["scoreContributionAllowed"])
        self.assertEqual(explainability["source_confidence"]["capReason"], "proxy_quote_source_capped")
        self.assertIn("proxy_quote_source_capped", explainability["reason_codes"])
        self.assertIn("public_proxy_not_score_grade", explainability["reason_codes"])
        self.assertEqual(packet["scoreConfidence"], 0.75)
        self.assertEqual(packet["capReason"], "proxy_quote_source_capped")
        self.assertEqual(packet["degradationReason"], "public_proxy_not_score_grade")
        self.assertIn("proxy_quote_source_capped", packet["adminReasonCodes"])
        self.assertIn("public_proxy_not_score_grade", packet["adminReasonCodes"])
        self.assertIn("仅供观察", packet["userFacingLabels"])
        self.assertIn("需人工复核", packet["userFacingLabels"])

    def test_apply_score_caps_and_explainability_preserves_authorized_non_proxy_scores(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeScannerDataManager(),
        )
        candidate = {
            "symbol": "MSFT",
            "name": "Microsoft",
            "score": 82.2,
            "reason_summary": "证据完整。",
            "ret_5d": 4.1,
            "ret_20d": 12.7,
            "avg_amount_20": 1.2e10,
            "amount": 1.1e10,
            "avg_volume_20": 22_000_000,
            "volume_expansion_20": 1.2,
            "atr20_pct": 3.7,
            "_relative_strength_pct": 0.81,
            "boards": ["软件"],
            "_component_scores": {
                "trend": 18.0,
                "momentum": 12.0,
                "liquidity": 15.2,
                "activity": 9.8,
                "volatility_quality": 7.4,
                "relative_strength": 8.1,
                "benchmark_relative": 6.5,
                "gap_context": 5.2,
                "penalties": 0.0,
            },
            "_diagnostics": {
                "history": {
                    "source": "local_db",
                    "latest_trade_date": "2026-05-16",
                    "rows": 130,
                },
                "quote_context": {
                    "available": True,
                    "source": "alpaca",
                    "sourceType": "broker_authorized",
                },
            },
        }

        service._apply_score_caps_and_explainability(candidate)

        explainability = candidate["_diagnostics"]["score_explainability"]
        self.assertEqual(candidate["raw_score"], 82.2)
        self.assertEqual(candidate["final_score"], 82.2)
        self.assertEqual(candidate["score"], 82.2)
        self.assertFalse(explainability["cap_applied"])
        self.assertIsNone(explainability["cap_reason"])
        self.assertIsNone(explainability["degradation_reason"])
        self.assertEqual(explainability["score_confidence"], 1.0)
        self.assertTrue(explainability["score_grade_allowed"])

    def test_run_scan_attaches_additive_evidence_packet_without_extra_provider_calls(self) -> None:
        seed_us_local_history(self.stock_repo)
        data_manager = SlowMissingQuoteDataManager()
        service = MarketScannerService(
            self.db,
            data_manager=data_manager,
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
            universe_type="symbols",
            symbols=["NVDA", "AAPL", "PLTR"],
        )

        self.assertEqual(
            [(item["symbol"], item["rank"], item["score"]) for item in result["shortlist"]],
            [("NVDA", 1, 65.8), ("AAPL", 2, 62.8), ("PLTR", 3, 40.0)],
        )
        self.assertEqual(len(data_manager.realtime_quote_calls), 3)
        self.assertEqual(set(data_manager.realtime_quote_calls), {"NVDA", "AAPL", "PLTR"})

        pltr = next(item for item in result["shortlist"] if item["symbol"] == "PLTR")
        packet = pltr["diagnostics"]["evidence_packet"]
        self.assertEqual(packet["symbol"], "PLTR")
        self.assertEqual(packet["rank"], 3)
        self.assertEqual(packet["score"], 40.0)
        self.assertEqual(packet["rawScore"], 81.6)
        self.assertEqual(packet["finalScore"], 40.0)
        self.assertEqual(packet["capReason"], "fallback_source")
        self.assertEqual(packet["degradationReason"], "fallback_source")
        self.assertEqual(packet["scoreConfidence"], 0.4)
        self.assertEqual(packet["evidenceVersion"], SCANNER_EVIDENCE_VERSION)
        self.assertEqual(packet["freshnessState"], "fallback")
        self.assertIn("仅供观察", packet["userFacingLabels"])
        self.assertIn("需人工复核", packet["userFacingLabels"])
        self.assertIn("部分外部数据暂不可用", packet["userFacingLabels"])
        self.assertNotIn("provider_timeout", json.dumps(packet, ensure_ascii=False))
        self.assertEqual(pltr["raw_score"], 81.6)
        self.assertEqual(pltr["final_score"], 40.0)
        self.assertEqual(pltr["score"], 40.0)
        self.assertEqual(pltr["diagnostics"]["score_explainability"]["cap_reason"], "fallback_source")

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        persisted_packet = next(item for item in detail["shortlist"] if item["symbol"] == "PLTR")["diagnostics"]["evidence_packet"]
        self.assertEqual(persisted_packet["symbol"], "PLTR")
        self.assertEqual(persisted_packet["evidenceVersion"], SCANNER_EVIDENCE_VERSION)

    def test_run_scan_attaches_additive_factor_observations_without_mutating_scores_or_ranks(self) -> None:
        seed_us_local_history(self.stock_repo)
        service = MarketScannerService(
            self.db,
            data_manager=SlowMissingQuoteDataManager(),
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
            universe_type="symbols",
            symbols=["NVDA", "AAPL", "PLTR"],
        )

        self.assertEqual(
            [
                (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
                for item in result["shortlist"]
            ],
            [
                ("NVDA", 1, 65.8, 65.8, 65.8),
                ("AAPL", 2, 62.8, 62.8, 62.8),
                ("PLTR", 3, 40.0, 81.6, 40.0),
            ],
        )

        pltr = next(item for item in result["shortlist"] if item["symbol"] == "PLTR")
        exported = pltr["diagnostics"]["factor_observations"]
        self.assertEqual(
            [item["component"] for item in exported],
            [
                "trend",
                "momentum",
                "liquidity",
                "activity",
                "volatility_quality",
                "relative_strength",
                "benchmark_relative",
                "gap_context",
            ],
        )
        self.assertEqual(exported[0]["observation"]["symbol"], "PLTR")
        self.assertEqual(exported[0]["observation"]["observed_at"], result["run_at"])
        self.assertEqual(exported[0]["observation"]["as_of"], pltr["last_trade_date"])
        self.assertEqual(
            exported[0]["observation_id"],
            (
                "scanner_factor_observation:us:us_preopen_v1:pltr:"
                f"trend.trend_strength_20d:trend:{pltr['last_trade_date']}"
            ),
        )

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        persisted = next(item for item in detail["shortlist"] if item["symbol"] == "PLTR")["diagnostics"]["factor_observations"]
        self.assertEqual([item["observation_id"] for item in persisted], [item["observation_id"] for item in exported])

    def test_run_scan_parallelizes_cn_remote_history_without_drifting_results(self) -> None:
        data_manager = SlowFaultyScannerDataManager()
        service = MarketScannerService(self.db, data_manager=data_manager)

        result = service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertGreaterEqual(data_manager.max_active_history_calls, 2)
        self.assertEqual(
            [(item["symbol"], item["rank"], item["score"]) for item in result["shortlist"]],
            [("600001", 1, 87.7), ("300123", 2, 80.8), ("600002", 3, 78.1)],
        )
        self.assertEqual(
            result["diagnostics"]["history_stats"],
            {
                "local_hits": 1,
                "network_fetches": 3,
                "network_failures": 1,
                "partial_local_fallbacks": 0,
                "skipped_for_history": 1,
            },
        )
        provider_diagnostics = result["diagnostics"]["provider_diagnostics"]
        self.assertEqual(provider_diagnostics["history_source_used"], "FakeDailySource")
        self.assertIn("unavailable", provider_diagnostics["providers_used"])
        self.assertFalse(provider_diagnostics["fallback_occurred"])
        self.assertEqual(provider_diagnostics["missing_data_symbol_count"], 1)

    def test_us_quote_failure_stays_visible_and_history_only_not_live(self) -> None:
        seed_us_local_history(self.stock_repo)
        data_manager = SlowMissingQuoteDataManager()
        service = MarketScannerService(
            self.db,
            data_manager=data_manager,
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
            universe_type="symbols",
            symbols=["NVDA", "AAPL", "PLTR"],
        )

        self.assertEqual(
            [(item["symbol"], item["rank"], item["score"]) for item in result["shortlist"]],
            [("NVDA", 1, 65.8), ("AAPL", 2, 62.8), ("PLTR", 3, 40.0)],
        )
        self.assertEqual(result["diagnostics"]["live_quote_stats"]["attempted_candidates"], 3)
        self.assertEqual(result["diagnostics"]["live_quote_stats"]["available_candidates"], 2)
        self.assertEqual(result["diagnostics"]["live_quote_stats"]["unavailable_candidates"], 1)
        self.assertEqual(result["diagnostics"]["provider_diagnostics"]["provider_failure_count"], 1)
        self.assertFalse(result["diagnostics"]["provider_diagnostics"]["fallback_occurred"])
        candidate_map = {item["symbol"]: item for item in result["candidates"]}
        self.assertEqual(candidate_map["PLTR"]["provider"], "history_only_us_scan")
        pltr = next(item for item in result["shortlist"] if item["symbol"] == "PLTR")
        self.assertFalse(pltr["diagnostics"]["quote_context"]["available"])
        self.assertIsNone(pltr["diagnostics"]["quote_context"]["source"])

    def test_run_scan_supports_us_preopen_profile_and_preserves_market_context(self) -> None:
        seed_us_local_history(self.stock_repo)
        service = MarketScannerService(
            self.db,
            data_manager=FakeUsScannerDataManager(),
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["market"], "us")
        self.assertEqual(result["profile"], "us_preopen_v1")
        self.assertTrue(result["headline"].startswith("今日美股盘前优先观察："))
        self.assertEqual(result["diagnostics"]["benchmark_context"]["benchmark_code"], "SPY")
        self.assertGreaterEqual(result["diagnostics"]["history_stats"]["local_hits"], 4)
        self.assertGreaterEqual(result["diagnostics"]["live_quote_stats"]["available_candidates"], 1)
        self.assertEqual(result["diagnostics"]["universe_filter_stats"]["coverage_strategy"], "seed_supplemented")
        self.assertGreater(result["diagnostics"]["universe_filter_stats"]["supplemented_seed_count"], 0)
        self.assertIn("curated_us_liquid_seed", result["source_summary"])

        shortlist_symbols = [item["symbol"] for item in result["shortlist"]]
        self.assertEqual(len(shortlist_symbols), 2)
        self.assertNotIn("SPY", shortlist_symbols)
        self.assertIn(shortlist_symbols[0], {"NVDA", "AAPL", "PLTR"})
        self.assertEqual(result["shortlist"][0]["diagnostics"]["benchmark_code"], "SPY")
        self.assertTrue(any(metric["label"] == "20D avg $vol" for metric in result["shortlist"][0]["key_metrics"]))
        self.assertTrue(any("Gap" in note or "实时" in note for note in result["shortlist"][0]["risk_notes"]))

        history = service.list_runs(market="us", profile="us_preopen_v1", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["market"], "us")

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        self.assertEqual(detail["market"], "us")
        self.assertEqual(detail["profile_label"], "US Pre-open Scanner v1")

    def test_run_scan_adds_us_candidate_evidence_and_readiness_without_mutating_shortlist(self) -> None:
        seed_us_local_history(self.stock_repo)
        service = MarketScannerService(
            self.db,
            data_manager=SlowMissingQuoteDataManager(delay_seconds=0.0),
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
            universe_type="symbols",
            symbols=["NVDA", "AAPL", "PLTR"],
        )

        shortlist_signature = [
            (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
            for item in result["shortlist"]
        ]
        self.assertEqual(
            shortlist_signature,
            [("NVDA", 1, 65.8, 65.8, 65.8), ("AAPL", 2, 62.8, 62.8, 62.8), ("PLTR", 3, 40.0, 81.6, 40.0)],
        )
        self.assertEqual(
            [
                (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
                for item in result["selected"]
            ],
            shortlist_signature,
        )

        candidate_map = {item["symbol"]: item for item in result["shortlist"]}
        nvda = candidate_map["NVDA"]
        self.assertEqual(nvda["candidateEvidenceFrame"]["contractVersion"], "scanner_candidate_evidence_v1")
        self.assertEqual(
            set(nvda["candidateEvidenceFrame"]["domains"]),
            {
                "technicals",
                "priceHistory",
                "liquidity",
                "volume",
                "gapMomentum",
                "trend",
                "theme",
                "fundamentals",
                "newsCatalyst",
            },
        )
        self.assertEqual(nvda["candidateEvidenceFrame"]["domains"]["technicals"]["state"], "available")
        self.assertEqual(nvda["candidateEvidenceFrame"]["domains"]["priceHistory"]["state"], "available")
        self.assertEqual(nvda["candidateEvidenceFrame"]["domains"]["liquidity"]["state"], "available")
        self.assertEqual(nvda["candidateEvidenceFrame"]["domains"]["fundamentals"]["state"], "missing")
        self.assertEqual(nvda["candidateEvidenceFrame"]["domains"]["newsCatalyst"]["state"], "missing")
        self.assertEqual(nvda["candidateResearchReadiness"]["contractVersion"], "research_readiness_v1")
        self.assertEqual(nvda["candidateResearchReadiness"]["readinessState"], "insufficient")
        self.assertIn("fundamentals", nvda["candidateResearchReadiness"]["missingEvidence"])
        self.assertIn("news", nvda["candidateResearchReadiness"]["missingEvidence"])
        self.assertIn("catalyst", nvda["candidateResearchReadiness"]["missingEvidence"])

        pltr = candidate_map["PLTR"]
        self.assertEqual(pltr["candidateEvidenceFrame"]["coverageState"], "observe_only")
        self.assertEqual(pltr["candidateEvidenceFrame"]["domains"]["gapMomentum"]["state"], "partial")
        self.assertTrue(pltr["candidateEvidenceFrame"]["domains"]["gapMomentum"]["observationOnly"])
        self.assertEqual(pltr["candidateResearchReadiness"]["sourceAuthority"], "observationOnly")
        self.assertIn("source_authority_not_score_grade", pltr["candidateResearchReadiness"]["blockingReasons"])

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        self.assertEqual(
            [
                (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
                for item in detail["shortlist"]
            ],
            shortlist_signature,
        )
        self.assertEqual(
            detail["shortlist"][0]["candidateEvidenceFrame"]["contractVersion"],
            "scanner_candidate_evidence_v1",
        )
        self.assertEqual(
            detail["shortlist"][0]["candidateResearchReadiness"]["contractVersion"],
            "research_readiness_v1",
        )

    def test_run_scan_restricts_us_custom_symbol_universe(self) -> None:
        seed_us_local_history(self.stock_repo)
        service = MarketScannerService(
            self.db,
            data_manager=FakeUsScannerDataManager(),
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
            universe_type="symbols",
            symbols=[" nvda ", "PLTR", "NVDA"],
        )

        self.assertEqual(result["diagnostics"]["universe_selection"]["universe_type"], "symbols")
        self.assertEqual(result["diagnostics"]["coverage_summary"]["input_universe_size"], 2)
        self.assertEqual(result["diagnostics"]["universe_selection"]["requested_symbols_count"], 3)
        self.assertEqual(result["diagnostics"]["universe_selection"]["accepted_symbols_count"], 2)
        self.assertEqual(result["diagnostics"]["universe_selection"]["accepted_symbols"], ["NVDA", "PLTR"])
        self.assertEqual({item["symbol"] for item in result["shortlist"]}, {"NVDA", "PLTR"})

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        self.assertEqual(detail["universe_type"], "symbols")
        self.assertEqual(detail["requested_symbols_count"], 3)
        self.assertEqual(detail["accepted_symbols_count"], 2)

    def test_run_scan_uses_ai_generated_custom_theme_universe(self) -> None:
        seed_us_local_history(self.stock_repo)
        create_ai_scanner_theme(
            theme_id="white_house_service_test",
            label="White House Stocks",
            market="us",
            prompt="Stocks associated with White House policy, federal contracts, and government decisions.",
            manual_symbols=["NVDA"],
        )
        service = MarketScannerService(
            self.db,
            data_manager=FakeUsScannerDataManager(),
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
            universe_type="theme",
            theme_id="white_house_service_test",
        )

        universe = result["diagnostics"]["universe_selection"]
        self.assertEqual(universe["universe_type"], "theme")
        self.assertEqual(universe["theme_id"], "white_house_service_test")
        self.assertIn("NVDA", universe["accepted_symbols"])
        self.assertIn("PLTR", universe["accepted_symbols"])
        self.assertLessEqual({item["symbol"] for item in result["shortlist"]}, set(universe["accepted_symbols"]))

    def test_crypto_mining_theme_diagnostics_return_full_candidate_universe(self) -> None:
        seed_crypto_miner_local_history(self.stock_repo)
        data_manager = FakeUsScannerDataManager()
        service = MarketScannerService(self.db, data_manager=data_manager)
        theme = get_scanner_theme("crypto_miners")
        assert theme is not None

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=1,
            universe_limit=50,
            detail_limit=10,
            universe_type="theme",
            theme_id="crypto_miners",
        )

        self.assertEqual(list(theme.symbols), ["MARA", "RIOT", "CLSK", "IREN", "CIFR", "HUT", "BTDR", "WULF", "CORZ", "BITF", "HIVE"])
        self.assertEqual(result["theme"]["universe_count"], 11)
        self.assertEqual(result["summary"]["universe_count"], 11)
        self.assertEqual(result["summary"]["submitted_count"], 11)
        self.assertEqual(result["summary"]["selected_count"], 1)
        self.assertEqual(result["summary"]["data_failed_count"], 2)
        self.assertFalse(result["summary"]["limited_by_result_cap"])
        self.assertEqual(len(result["candidates"]), 11)
        self.assertEqual(result["selected"], result["shortlist"])
        self.assertTrue(
            {
                "coverage_summary",
                "provider_diagnostics",
                "scanner_data",
                "universe_selection",
            }
            <= set(result["diagnostics"])
        )

        candidate_map = {item["symbol"]: item for item in result["candidates"]}
        for symbol in ("WULF", "HIVE", "CIFR"):
            self.assertTrue(
                {
                    "rank",
                    "status",
                    "score",
                    "provider",
                    "reason",
                    "failed_rules",
                    "missing_fields",
                    "metrics",
                }
                <= set(candidate_map[symbol])
            )
        self.assertEqual(candidate_map["WULF"]["status"], "selected")
        self.assertEqual(candidate_map["WULF"]["provider"], "alpaca")
        self.assertEqual(candidate_map["CIFR"]["status"], "data_failed")
        self.assertIn("history", candidate_map["CIFR"]["missing_fields"])
        self.assertEqual(candidate_map["BITF"]["status"], "data_failed")
        rejected = [item for item in result["candidates"] if item["status"] == "rejected"]
        self.assertGreaterEqual(len(rejected), 1)
        self.assertTrue(all(item["reason"] or item["failed_rules"] for item in rejected))
        self.assertEqual(len(data_manager.daily_history_calls), 0)
        self.assertEqual(len(data_manager.realtime_quote_calls), 9)

    def test_theme_diagnostics_are_not_hidden_by_detail_limit(self) -> None:
        seed_crypto_miner_local_history(self.stock_repo)
        service = MarketScannerService(
            self.db,
            data_manager=FakeUsScannerDataManager(),
        )

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=1,
            universe_limit=50,
            detail_limit=10,
            universe_type="theme",
            theme_id="crypto_miners",
        )

        self.assertEqual(result["summary"]["universe_count"], 11)
        self.assertEqual(result["summary"]["evaluated_count"], 9)
        self.assertEqual(result["summary"]["skipped_count"], 0)
        self.assertEqual({item["symbol"] for item in result["candidates"]}, set(get_scanner_theme("crypto_miners").symbols))

    def test_run_scan_rejects_invalid_or_empty_theme_universe(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeUsScannerDataManager(),
        )

        with self.assertRaisesRegex(ValueError, "未知 scanner theme"):
            service.run_scan(
                market="us",
                profile="us_preopen_v1",
                universe_type="theme",
                theme_id="missing_theme",
            )

        with self.assertRaisesRegex(ValueError, "尚未配置成分股"):
            service.run_scan(
                market="cn",
                profile="cn_preopen_v1",
                universe_type="theme",
                theme_id="optical_module_cpo_cn",
            )

    def test_run_scan_rejects_theme_market_mismatch(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=FakeUsScannerDataManager(),
        )

        with self.assertRaisesRegex(ValueError, "不属于市场 cn"):
            service.run_scan(
                market="cn",
                profile="cn_preopen_v1",
                universe_type="theme",
                theme_id="crypto_miners",
            )

    def test_run_scan_supports_hk_preopen_profile_and_preserves_market_context(self) -> None:
        seed_hk_local_history(self.stock_repo)
        service = MarketScannerService(
            self.db,
            data_manager=FakeHkScannerDataManager(),
        )

        result = service.run_scan(
            market="hk",
            profile="hk_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["market"], "hk")
        self.assertEqual(result["profile"], "hk_preopen_v1")
        self.assertTrue(result["headline"].startswith("今日港股开盘优先观察："))
        self.assertEqual(result["diagnostics"]["benchmark_context"]["benchmark_code"], "HK02800")
        self.assertGreaterEqual(result["diagnostics"]["history_stats"]["local_hits"], 4)
        self.assertGreaterEqual(result["diagnostics"]["live_quote_stats"]["available_candidates"], 1)
        self.assertEqual(result["diagnostics"]["universe_filter_stats"]["coverage_strategy"], "seed_supplemented")
        self.assertGreater(result["diagnostics"]["universe_filter_stats"]["supplemented_seed_count"], 0)
        self.assertIn("curated_hk_liquid_seed", result["source_summary"])

        shortlist_symbols = [item["symbol"] for item in result["shortlist"]]
        self.assertEqual(len(shortlist_symbols), 2)
        self.assertNotIn("HK02800", shortlist_symbols)
        self.assertIn(shortlist_symbols[0], {"HK00700", "HK01810", "HK03690", "HK00981"})
        self.assertTrue(any(metric["label"] == "20日均成交额" for metric in result["shortlist"][0]["key_metrics"]))
        self.assertTrue(any("开盘" in note or "quote" in note for note in result["shortlist"][0]["risk_notes"]))

        history = service.list_runs(market="hk", profile="hk_preopen_v1", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["market"], "hk")

        detail = service.get_run_detail(result["id"])
        assert detail is not None
        self.assertEqual(detail["market"], "hk")
        self.assertEqual(detail["profile_label"], "港股盘前扫描 v1")

    def test_resolve_us_stock_universe_supplements_thin_local_coverage(self) -> None:
        profile = get_scanner_profile(market="us", profile="us_preopen_v1")
        service = MarketScannerService(
            self.db,
            data_manager=FakeUsScannerDataManager(),
        )

        with patch.object(
            MarketScannerService,
            "_load_local_us_universe_from_parquet",
            return_value=["NVDA", "AAPL"],
        ):
            with patch.object(service, "_load_local_us_universe_from_db", return_value=["PLTR"]):
                result = service._resolve_us_stock_universe(profile=profile, target_symbol_count=50)

        self.assertTrue(result["success"])
        self.assertEqual(result["coverage_strategy"], "seed_supplemented")
        self.assertEqual(result["local_symbol_count"], 3)
        self.assertGreater(result["supplemented_seed_count"], 0)
        self.assertGreaterEqual(result["final_symbol_count"], 40)
        self.assertGreaterEqual(result["target_symbol_count"], 50)
        self.assertTrue(result["source"].startswith("local_us_parquet_dir"))
        self.assertIn("curated_us_liquid_seed", result["source"])
        self.assertIn("NVDA", result["data"])
        self.assertIn("PLTR", result["data"])

    def test_resolve_us_stock_universe_falls_back_when_parquet_root_is_inaccessible(self) -> None:
        with patch("src.services.market_scanner_service.Path.exists", side_effect=PermissionError("permission denied")):
            symbols = MarketScannerService._load_local_us_universe_from_parquet(Path("/root/us_test/data/normalized/us"))

        self.assertEqual(symbols, [])

    def test_resolve_hk_stock_universe_respects_requested_target_for_seed_supplement(self) -> None:
        profile = get_scanner_profile(market="hk", profile="hk_preopen_v1")
        service = MarketScannerService(
            self.db,
            data_manager=FakeHkScannerDataManager(),
        )

        with patch.object(service, "_load_local_hk_universe_from_db", return_value=["HK00700", "HK01810"]):
            result = service._resolve_hk_stock_universe(profile=profile, target_symbol_count=30)

        self.assertTrue(result["success"])
        self.assertEqual(result["coverage_strategy"], "seed_supplemented")
        self.assertEqual(result["local_symbol_count"], 2)
        self.assertGreaterEqual(result["target_symbol_count"], 30)
        self.assertGreaterEqual(result["final_symbol_count"], 25)
        self.assertIn("curated_hk_liquid_seed", result["source"])

    def test_load_local_us_universe_from_db_uses_stock_repository_boundary(self) -> None:
        repo = MagicMock()
        repo.list_distinct_codes.return_value = ["NVDA", "aapl", "HK00700", "600001"]
        self.service.stock_repo = repo

        result = self.service._load_local_us_universe_from_db()

        repo.list_distinct_codes.assert_called_once_with()
        self.assertEqual(result, ["AAPL", "NVDA"])

    def test_load_local_stock_list_fallback_uses_repository_boundaries(self) -> None:
        scanner_repo = MagicMock()
        scanner_repo.list_recent_analysis_symbols.return_value = [
            ("600001", "算力龙头"),
            ("600002", "机器人核心"),
        ]
        stock_repo = MagicMock()
        stock_repo.list_distinct_codes.return_value = ["600001", "600002", "300123"]
        self.service.repo = scanner_repo
        self.service.stock_repo = stock_repo
        self.service.owner_id = "owner-a"

        result = self.service._load_local_stock_list_fallback()

        scanner_repo.list_recent_analysis_symbols.assert_called_once_with(
            owner_id="owner-a",
            include_all_owners=False,
        )
        stock_repo.list_distinct_codes.assert_called_once_with()
        self.assertTrue(result["success"])
        frame = result["data"]
        self.assertEqual(frame["code"].tolist(), ["600001", "600002", "300123"])
        self.assertEqual(frame["name"].tolist()[:2], ["算力龙头", "机器人核心"])

    def test_degraded_snapshot_uses_owner_scoped_recent_analysis_names(self) -> None:
        scanner_repo = MagicMock()
        scanner_repo.list_recent_analysis_symbols.return_value = [("600001", "算力龙头")]
        self.service.repo = scanner_repo
        self.service.owner_id = "owner-a"
        profile = get_scanner_profile(market="cn")

        result = self.service._build_degraded_snapshot_from_local_history(
            profile=profile,
            stock_list=None,
            attempts=[],
        )

        scanner_repo.list_recent_analysis_symbols.assert_called_once_with(
            owner_id="owner-a",
            include_all_owners=False,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"].iloc[0]["name"], "算力龙头")

    def test_load_local_history_uses_stock_repository_boundary(self) -> None:
        stock_repo = MagicMock()
        stock_repo.get_recent_daily_rows.return_value = [
            SimpleNamespace(
                date=pd.Timestamp("2026-04-10").date(),
                open=10.0,
                high=10.5,
                low=9.8,
                close=10.2,
                volume=1_000_000,
                amount=10_200_000,
                pct_chg=2.0,
            ),
            SimpleNamespace(
                date=pd.Timestamp("2026-04-11").date(),
                open=10.2,
                high=10.8,
                low=10.1,
                close=10.6,
                volume=1_100_000,
                amount=11_660_000,
                pct_chg=3.92,
            ),
        ]
        self.service.stock_repo = stock_repo

        frame = self.service._load_local_history("600001", history_days=2)

        stock_repo.get_recent_daily_rows.assert_called_once_with(code="600001", limit=2)
        self.assertEqual(frame["close"].tolist(), [10.2, 10.6])

    def test_run_scan_rejects_unknown_market_profile(self) -> None:
        with self.assertRaises(ValueError):
            self.service.run_scan(market="sg")

    def test_run_scan_prefers_local_universe_cache_and_skips_online_stock_list(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        cache_path = Path(temp_dir.name) / "scanner_cn_universe_cache.csv"
        self.data_manager.stock_list[["code", "name"]].to_csv(cache_path, index=False)

        manager = StructuredScannerDataManager()
        service = MarketScannerService(
            self.db,
            data_manager=manager,
            local_universe_cache_path=str(cache_path),
        )

        result = service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(manager.stock_list_attempts, 0)
        self.assertEqual(result["diagnostics"]["scanner_data"]["universe_resolution"]["source"], "local_universe_cache")
        self.assertIn("universe=local_universe_cache", result["source_summary"])

    def test_resolve_cn_stock_universe_uses_builtin_mapping_after_tushare_permission_denied(self) -> None:
        DatabaseManager.reset_instance()
        empty_db = DatabaseManager(db_url="sqlite:///:memory:")
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        cache_path = Path(temp_dir.name) / "scanner_cn_universe_cache.csv"

        manager = DataFetcherManager(
            fetchers=[
                FetcherStub(
                    name="TushareFetcher",
                    priority=1,
                    stock_list_error=DataFetchError("permission denied for stock_basic"),
                )
            ]
        )
        service = MarketScannerService(
            empty_db,
            data_manager=manager,
            local_universe_cache_path=str(cache_path),
        )

        result = service._resolve_cn_stock_universe()

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "builtin_stock_mapping")
        self.assertTrue(cache_path.exists())
        self.assertIn("600519", result["data"]["code"].tolist())
        attempt_codes = [item.get("reason_code") for item in result["attempts"] if item.get("reason_code")]
        self.assertIn("tushare_permission_denied", attempt_codes)

    def test_snapshot_fetcher_manager_falls_back_from_akshare_to_efinance(self) -> None:
        snapshot = self.data_manager.snapshot.copy()
        manager = DataFetcherManager(
            fetchers=[
                FetcherStub(
                    name="AkshareFetcher",
                    priority=1,
                    snapshot_error=DataFetchError("stock_zh_a_spot_em unavailable"),
                ),
                FetcherStub(
                    name="EfinanceFetcher",
                    priority=2,
                    snapshot=snapshot,
                ),
            ]
        )

        result = manager.try_get_cn_realtime_snapshot(
            preferred_fetchers=["AkshareFetcher", "EfinanceFetcher"],
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "EfinanceFetcher")
        self.assertEqual(result["attempts"][0]["reason_code"], "akshare_snapshot_fetch_failed")
        self.assertEqual(result["attempts"][1]["status"], "success")

    def test_snapshot_fetcher_manager_returns_precise_failure_attempts(self) -> None:
        manager = DataFetcherManager(
            fetchers=[
                FetcherStub(
                    name="AkshareFetcher",
                    priority=1,
                    snapshot_error=DataFetchError("stock_zh_a_spot_em unavailable"),
                ),
                FetcherStub(
                    name="EfinanceFetcher",
                    priority=2,
                    snapshot_error=DataFetchError("ef.stock.get_realtime_quotes timeout"),
                ),
            ]
        )

        result = manager.try_get_cn_realtime_snapshot(
            preferred_fetchers=["AkshareFetcher", "EfinanceFetcher"],
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "no_realtime_snapshot_available")
        self.assertEqual(
            [item["reason_code"] for item in result["attempts"]],
            ["akshare_snapshot_fetch_failed", "efinance_snapshot_fetch_failed"],
        )

    def test_snapshot_fetcher_manager_reuses_cached_snapshot_for_same_preferences(self) -> None:
        snapshot = self.data_manager.snapshot.copy()
        fetcher = FetcherStub(
            name="AkshareFetcher",
            priority=1,
            snapshot=snapshot,
        )
        manager = DataFetcherManager(fetchers=[fetcher])

        first = manager.try_get_cn_realtime_snapshot(
            preferred_fetchers=["AkshareFetcher"],
        )
        second = manager.try_get_cn_realtime_snapshot(
            preferred_fetchers=["AkshareFetcher"],
        )

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(fetcher.snapshot_calls, 1)

        first_data = first["data"]
        second_data = second["data"]
        self.assertIsNot(first_data, second_data)
        first_data.loc[first_data.index[0], "name"] = "mutated"
        self.assertNotEqual(first_data.iloc[0]["name"], second_data.iloc[0]["name"])

    def test_run_scan_uses_degraded_mode_when_realtime_snapshot_unavailable(self) -> None:
        for code, history in self.data_manager.histories.items():
            self.stock_repo.save_dataframe(history.copy(), code, data_source="LocalWarmCache")

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
                        "summary": "[AkshareFetcher] (DataFetchError) stock_zh_a_spot_em unavailable",
                    },
                    {
                        "fetcher": "EfinanceFetcher",
                        "status": "failed",
                        "reason_code": "efinance_snapshot_fetch_failed",
                        "summary": "[EfinanceFetcher] (DataFetchError) timeout",
                    },
                ],
                "error_code": "no_realtime_snapshot_available",
                "error_message": "snapshot unavailable",
            }
        )
        service = MarketScannerService(self.db, data_manager=manager)

        result = service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["diagnostics"]["scanner_data"]["degraded_mode_used"])
        self.assertIn("snapshot=local_history_degraded", result["source_summary"])
        self.assertIn("degraded=yes", result["source_summary"])
        self.assertTrue(any("降级快照" in note for note in result["universe_notes"]))
        self.assertTrue(result["shortlist"])
        readiness = result["scannerContextFrame"]["marketReadiness"]
        self.assertFalse(readiness["researchReady"])
        self.assertEqual(readiness["market"], "cn")
        self.assertEqual(readiness["readinessState"], "observe_only")
        self.assertIn("source_authority_not_score_grade", readiness["blockedReasons"])
        self.assertEqual(readiness["providerAuthority"], "observation_only")
        self.assertEqual(readiness["freshness"], "fallback")
        self.assertEqual(readiness["sourceTier"], "fallback_static")
        for item in result["shortlist"]:
            self.assertLessEqual(float(item["score"]), 40.0)
            self.assertEqual(item["diagnostics"]["score_explainability"]["cap_reason"], "fallback_source")
            self.assertEqual(item["diagnostics"]["score_explainability"]["degradation_reason"], "fallback_source")

    def test_run_scan_raises_structured_error_when_no_snapshot_and_no_degraded_mode(self) -> None:
        DatabaseManager.reset_instance()
        empty_db = DatabaseManager(db_url="sqlite:///:memory:")
        empty_service = MarketScannerService(
            empty_db,
            data_manager=StructuredScannerDataManager(
                snapshot_result={
                    "success": False,
                    "source": None,
                    "data": None,
                    "attempts": [
                        {
                            "fetcher": "AkshareFetcher",
                            "status": "failed",
                            "reason_code": "akshare_snapshot_fetch_failed",
                            "summary": "[AkshareFetcher] (DataFetchError) stock_zh_a_spot_em unavailable",
                        },
                        {
                            "fetcher": "EfinanceFetcher",
                            "status": "failed",
                            "reason_code": "efinance_snapshot_fetch_failed",
                            "summary": "[EfinanceFetcher] (DataFetchError) timeout",
                        },
                    ],
                    "error_code": "no_realtime_snapshot_available",
                    "error_message": "snapshot unavailable",
                }
            ),
        )

        with self.assertRaises(ScannerRuntimeError) as ctx:
            empty_service.run_scan(
                market="cn",
                shortlist_size=3,
                universe_limit=50,
                detail_limit=10,
            )

        self.assertEqual(ctx.exception.reason_code, "no_realtime_snapshot_available")
        self.assertIn("snapshot_resolution", ctx.exception.diagnostics)
        self.assertIn("snapshot_attempts", ctx.exception.source_summary or "")

    def test_get_run_detail_includes_comparison_and_realized_outcomes(self) -> None:
        _, current_run_id = self._seed_review_watchlists()

        detail = self.service.get_run_detail(current_run_id)

        assert detail is not None
        self.assertTrue(detail["comparison_to_previous"]["available"])
        self.assertEqual(detail["comparison_to_previous"]["new_count"], 1)
        self.assertEqual(detail["comparison_to_previous"]["retained_count"], 1)
        self.assertEqual(detail["comparison_to_previous"]["dropped_count"], 1)
        self.assertEqual(detail["comparison_to_previous"]["new_symbols"][0]["symbol"], "300123")
        self.assertEqual(detail["comparison_to_previous"]["retained_symbols"][0]["symbol"], "600001")
        self.assertEqual(detail["comparison_to_previous"]["retained_symbols"][0]["rank_delta"], -1)
        self.assertEqual(detail["comparison_to_previous"]["dropped_symbols"][0]["symbol"], "600002")
        self.assertTrue(detail["review_summary"]["available"])
        self.assertGreater(detail["review_summary"]["avg_review_window_return_pct"], 0.0)
        candidate_map = {item["symbol"]: item for item in detail["shortlist"]}
        self.assertEqual(candidate_map["300123"]["realized_outcome"]["review_status"], "ready")
        self.assertEqual(candidate_map["300123"]["realized_outcome"]["thesis_match"], "validated")
        self.assertTrue(candidate_map["300123"]["realized_outcome"]["outperformed_benchmark"])

    def test_list_recent_watchlists_includes_change_and_review_summaries(self) -> None:
        self._seed_review_watchlists()

        response = self.service.list_recent_watchlists(
            market="cn",
            profile="cn_preopen_v1",
            limit_days=5,
        )

        self.assertEqual(response["total"], 2)
        latest = response["items"][0]
        previous = response["items"][1]
        self.assertTrue(latest["change_summary"]["available"])
        self.assertEqual(latest["change_summary"]["new_count"], 1)
        self.assertTrue(latest["review_summary"]["available"])
        self.assertEqual(previous["change_summary"]["available"], False)
        self.assertTrue(previous["review_summary"]["available"])

    def test_operational_status_exposes_recent_quality_summary(self) -> None:
        self._seed_review_watchlists()

        status = self.service.get_operational_status(
            market="cn",
            profile="cn_preopen_v1",
        )

        quality = status["quality_summary"]
        self.assertTrue(quality["available"])
        self.assertEqual(quality["run_count"], 2)
        self.assertEqual(quality["reviewed_run_count"], 2)
        self.assertGreater(quality["avg_shortlist_return_pct"], 0.0)
        self.assertGreater(quality["hit_rate_pct"], 0.0)
        self.assertGreater(quality["positive_candidate_avg_score"], quality["negative_candidate_avg_score"])

    def test_run_scan_returns_coverage_and_provider_diagnostics_summary(self) -> None:
        detail = self.service.run_scan(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
        )

        coverage = detail["diagnostics"].get("coverage_summary")
        providers = detail["diagnostics"].get("provider_diagnostics")

        self.assertIsInstance(coverage, dict)
        self.assertEqual(coverage["input_universe_size"], 6)
        self.assertEqual(coverage["eligible_after_universe_fetch"], 6)
        self.assertEqual(coverage["eligible_after_liquidity_filter"], 4)
        self.assertEqual(coverage["eligible_after_data_availability_filter"], 4)
        self.assertEqual(coverage["ranked_candidate_count"], 4)
        self.assertEqual(coverage["shortlisted_count"], 2)
        self.assertEqual(coverage["excluded_total"], 2)
        excluded_reasons = {item["reason"]: item["count"] for item in coverage["excluded_by_reason"]}
        self.assertEqual(excluded_reasons["filtered_by_profile_constraints"], 2)

        self.assertIsInstance(providers, dict)
        self.assertEqual(providers["configured_primary_provider"], "FakeSnapshotSource")
        self.assertEqual(providers["snapshot_source_used"], "FakeSnapshotSource")
        self.assertEqual(providers["history_source_used"], "FakeDailySource")
        self.assertFalse(providers["fallback_occurred"])
        self.assertEqual(providers["fallback_count"], 0)
        self.assertEqual(providers["provider_failure_count"], 0)
        self.assertEqual(providers["missing_data_symbol_count"], 0)
        self.assertEqual(
            providers["providers_used"],
            ["FakeDailySource", "FakeSnapshotSource", "local_db", "local_universe_cache"],
        )

    def test_run_scan_attaches_cn_provider_observation_metadata_without_changing_scores_or_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_cache = Path(temp_dir) / "baseline-universe-cache.csv"
            observed_cache = Path(temp_dir) / "observed-universe-cache.csv"
            baseline_db = DatabaseManager(db_url="sqlite:///:memory:")
            observed_db = DatabaseManager(db_url="sqlite:///:memory:")
            baseline_service = MarketScannerService(
                baseline_db,
                data_manager=FakeScannerDataManager(),
                local_universe_cache_path=str(baseline_cache),
            )
            baseline = baseline_service.run_scan(
                market="cn",
                profile="cn_preopen_v1",
                shortlist_size=2,
                universe_limit=50,
                detail_limit=10,
            )

            observed_service = MarketScannerService(
                observed_db,
                data_manager=ObservationScannerDataManager(),
                local_universe_cache_path=str(observed_cache),
            )
            observed = observed_service.run_scan(
                market="cn",
                profile="cn_preopen_v1",
                shortlist_size=2,
                universe_limit=50,
                detail_limit=10,
            )

            baseline_shortlist = [
                (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
                for item in baseline["shortlist"]
            ]
            observed_shortlist = [
                (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
                for item in observed["shortlist"]
            ]
            self.assertEqual(observed_shortlist, baseline_shortlist)

            candidate = observed["shortlist"][0]
            observation = candidate["diagnostics"].get("cn_provider_observation")
            self.assertIsInstance(observation, dict)
            self.assertTrue(observation["observationOnly"])
            self.assertFalse(observation["scoreContributionAllowed"])
            entries = observation["entries"]
            self.assertEqual([item["stage"] for item in entries], ["universe", "snapshot"])
            self.assertEqual([item["providerName"] for item in entries], ["akshare", "akshare"])
            self.assertTrue(all(item["observationOnly"] is True for item in entries))
            self.assertTrue(all(item["scoreContributionAllowed"] is False for item in entries))
            self.assertEqual(entries[0]["capability"], "cn_stock_list")
            self.assertEqual(entries[0]["sourceTier"], "unofficial_public_api")
            self.assertEqual(entries[1]["capability"], "cn_realtime_snapshot")
            self.assertEqual(entries[1]["trustLevel"], "weak")
            self.assertEqual(candidate["raw_score"], candidate["final_score"])
            self.assertEqual(candidate["score"], candidate["raw_score"])
            explainability = candidate["diagnostics"]["score_explainability"]
            self.assertIsNone(explainability["cap_reason"])
            self.assertIsNone(explainability["degradation_reason"])
            self.assertEqual(explainability["score_confidence"], 1.0)
            self.assertFalse(explainability["cap_applied"])
            self.assertTrue(explainability["score_grade_allowed"])
            self.assertTrue(explainability["source_confidence"]["scoreContributionAllowed"])
            self.assertFalse(explainability["source_confidence"]["observationOnly"])
            self.assertIsNotNone(candidate["diagnostics"]["evidence_packet"]["providerObservation"])
            self.assertTrue(candidate["diagnostics"]["evidence_packet"]["providerObservation"]["observationOnly"])

    def test_run_scan_attaches_baostock_scanner_diagnostics_sidecar_without_changing_scores_or_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_cache = Path(temp_dir) / "baseline-baostock-cache.csv"
            observed_cache = Path(temp_dir) / "observed-baostock-cache.csv"
            baseline_db = DatabaseManager(db_url="sqlite:///:memory:")
            observed_db = DatabaseManager(db_url="sqlite:///:memory:")
            baseline_service = MarketScannerService(
                baseline_db,
                data_manager=ObservationScannerDataManager(),
                local_universe_cache_path=str(baseline_cache),
            )
            baseline = baseline_service.run_scan(
                market="cn",
                profile="cn_preopen_v1",
                shortlist_size=2,
                universe_limit=50,
                detail_limit=10,
            )

            baostock_by_symbol = {
                "600001": self._baostock_history_observation(
                    freshness="stale",
                    as_of="2026-04-29",
                    updated_at="2026-04-30T06:00:00+08:00",
                    attempted_at="2026-04-30T06:00:00+08:00",
                    degradation_reason="cache_stale",
                    missing_provider_reason=None,
                ),
                "600002": self._baostock_history_observation(
                    freshness="t_plus_1_or_delayed",
                    as_of="2026-04-30",
                    updated_at="2026-04-30T06:00:00+08:00",
                    attempted_at="2026-04-30T06:00:00+08:00",
                ),
            }
            observed_service = MarketScannerService(
                observed_db,
                data_manager=ObservationScannerDataManager(),
                local_universe_cache_path=str(observed_cache),
                baostock_cn_history_observation_resolver=lambda symbol, history_diag: dict(
                    baostock_by_symbol.get(str(symbol), {})
                ),
            )
            observed = observed_service.run_scan(
                market="cn",
                profile="cn_preopen_v1",
                shortlist_size=2,
                universe_limit=50,
                detail_limit=10,
            )

            baseline_shortlist = [
                (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
                for item in baseline["shortlist"]
            ]
            observed_shortlist = [
                (item["symbol"], item["rank"], item["score"], item["raw_score"], item["final_score"])
                for item in observed["shortlist"]
            ]
            self.assertEqual(observed_shortlist, baseline_shortlist)

            candidate = observed["shortlist"][0]
            observation = candidate["diagnostics"].get("cn_provider_observation")
            self.assertIsInstance(observation, dict)
            self.assertTrue(observation["observationOnly"])
            self.assertFalse(observation["scoreContributionAllowed"])
            self.assertEqual(
                [item["stage"] for item in observation["entries"]],
                ["universe", "snapshot", "scanner_diagnostics"],
            )
            self.assertEqual(
                [item["providerName"] for item in observation["entries"]],
                ["akshare", "akshare", "baostock"],
            )
            baostock_entry = observation["entries"][2]
            self.assertEqual(baostock_entry["capability"], "cn_history_daily")
            self.assertEqual(baostock_entry["freshness"], "stale")
            self.assertEqual(baostock_entry["freshnessExpectation"], "t_plus_1_or_delayed")
            self.assertEqual(baostock_entry["sourceType"], "public_proxy")
            self.assertEqual(baostock_entry["sourceTier"], "third_party_free_api")
            self.assertEqual(baostock_entry["trustLevel"], "usable_with_caution")
            self.assertEqual(baostock_entry["asOf"], "2026-04-29")
            self.assertEqual(baostock_entry["updatedAt"], "2026-04-30T06:00:00+08:00")
            self.assertEqual(baostock_entry["attemptedAt"], "2026-04-30T06:00:00+08:00")
            self.assertEqual(baostock_entry["degradationReason"], "cache_stale")
            self.assertIsNone(baostock_entry["missingProviderReason"])
            self.assertEqual(baostock_entry["adjustmentMethod"], "baostock_adjustflag_2")
            self.assertTrue(baostock_entry["observationOnly"])
            self.assertFalse(baostock_entry["scoreContributionAllowed"])

            evidence_observation = candidate["diagnostics"]["evidence_packet"]["providerObservation"]
            self.assertIsInstance(evidence_observation, dict)
            self.assertEqual(evidence_observation["entries"][2]["providerName"], "baostock")
            self.assertEqual(evidence_observation["entries"][2]["freshness"], "stale")

    def test_public_candidate_dict_adds_cn_candidate_evidence_frame_for_observe_only_and_blocked_inputs(self) -> None:
        service = object.__new__(MarketScannerService)
        service.ai_service = MagicMock()
        service.ai_service.public_payload_from_diagnostics.return_value = {"available": False, "status": "skipped"}

        observe_candidate = {
            "symbol": "600001",
            "name": "算力龙头",
            "rank": 1,
            "score": 79.0,
            "raw_score": 79.0,
            "final_score": 79.0,
            "boards": ["AI算力"],
            "_component_scores": {"trend": 18.0},
            "_diagnostics": {
                "history": {
                    "source": "PytdxFetcher",
                    "latest_trade_date": "2026-05-08",
                    "rows": 120,
                },
                "quote_context": {
                    "available": True,
                    "source": "akshare",
                    "sourceType": "public_proxy",
                },
                "cn_provider_observation": {
                    "observationOnly": True,
                    "scoreContributionAllowed": False,
                    "entries": [
                        {
                            "stage": "snapshot",
                            "providerName": "akshare",
                            "sourceType": "public_proxy",
                        }
                    ],
                },
                "score_explainability": {
                    "raw_score": 79.0,
                    "final_score": 79.0,
                    "score_confidence": 1.0,
                    "source_confidence": {
                        "sourceAuthorityAllowed": False,
                        "scoreContributionAllowed": False,
                        "observationOnly": True,
                        "sourceType": "public_proxy",
                        "freshness": "delayed",
                    },
                },
            },
            "ret_5d": 6.0,
            "ret_20d": 18.0,
            "avg_amount_20": 9.0e8,
            "amount": 1.25e9,
            "avg_volume_20": 4.8e7,
            "volume_expansion_20": 1.6,
            "price": 18.4,
            "close": 18.4,
            "ma20": 17.8,
            "ma60": 16.9,
        }
        blocked_candidate = {
            "symbol": "600002",
            "name": "观察样本",
            "rank": 2,
            "score": 35.0,
            "raw_score": 35.0,
            "final_score": 35.0,
            "_diagnostics": {
                "history": {
                    "source": "unavailable",
                    "rows": 0,
                },
                "quote_context": {
                    "available": False,
                    "source": None,
                },
                "score_explainability": {
                    "raw_score": 35.0,
                    "final_score": 35.0,
                    "score_confidence": 0.2,
                    "source_confidence": {
                        "sourceAuthorityAllowed": False,
                        "scoreContributionAllowed": False,
                        "observationOnly": True,
                        "freshness": "unknown",
                        "isUnavailable": True,
                    },
                },
            },
        }

        observed_public = service._public_candidate_dict(observe_candidate)
        blocked_public = service._public_candidate_dict(blocked_candidate)

        self.assertEqual(observed_public["candidateEvidenceFrame"]["coverageState"], "observe_only")
        self.assertEqual(observed_public["candidateEvidenceFrame"]["domains"]["theme"]["state"], "available")
        self.assertTrue(observed_public["candidateEvidenceFrame"]["domains"]["theme"]["observationOnly"])
        self.assertEqual(observed_public["candidateResearchReadiness"]["sourceAuthority"], "observationOnly")
        self.assertEqual(observed_public["candidateResearchReadiness"]["readinessState"], "insufficient")

        self.assertEqual(blocked_public["candidateEvidenceFrame"]["coverageState"], "blocked")
        self.assertEqual(blocked_public["candidateEvidenceFrame"]["domains"]["priceHistory"]["state"], "missing")
        self.assertEqual(blocked_public["candidateEvidenceFrame"]["domains"]["liquidity"]["state"], "missing")
        self.assertEqual(blocked_public["candidateResearchReadiness"]["readinessState"], "blocked")

    def test_attach_cn_provider_observation_metadata_projects_unavailable_baostock_cache_without_mutating_score(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=self.data_manager,
            baostock_cn_history_observation_resolver=lambda symbol, history_diag: self._baostock_history_observation(
                freshness="unavailable",
                as_of=None,
                updated_at=None,
                attempted_at="2026-05-20T09:30:00+08:00",
                degradation_reason="baostock_cache_missing",
                missing_provider_reason="baostock_cache_missing",
            )
            if str(symbol) == "600001"
            else {},
        )
        candidate = {
            "symbol": "600001",
            "name": "算力龙头",
            "score": 82.4,
            "raw_score": 82.4,
            "final_score": 82.4,
            "last_trade_date": "2026-04-30",
            "_diagnostics": {
                "history": {
                    "source": "PytdxFetcher",
                    "latest_trade_date": "2026-04-30",
                }
            },
        }

        service._attach_cn_provider_observation_metadata(
            [candidate],
            stock_list_source="AkshareFetcher",
            snapshot_source="AkshareFetcher",
        )

        self.assertEqual(candidate["score"], 82.4)
        observation = candidate["_diagnostics"]["cn_provider_observation"]
        self.assertEqual([item["providerName"] for item in observation["entries"]], ["akshare", "akshare", "pytdx", "baostock"])
        baostock_entry = observation["entries"][3]
        self.assertEqual(baostock_entry["stage"], "scanner_diagnostics")
        self.assertEqual(baostock_entry["freshness"], "unavailable")
        self.assertIsNone(baostock_entry["asOf"])
        self.assertIsNone(baostock_entry["updatedAt"])
        self.assertEqual(baostock_entry["attemptedAt"], "2026-05-20T09:30:00+08:00")
        self.assertEqual(baostock_entry["degradationReason"], "baostock_cache_missing")
        self.assertEqual(baostock_entry["missingProviderReason"], "baostock_cache_missing")
        self.assertEqual(baostock_entry["adjustmentMethod"], "baostock_adjustflag_2")
        self.assertTrue(baostock_entry["cacheRequired"])
        self.assertTrue(baostock_entry["backgroundRefreshRecommended"])

    def test_attach_cn_provider_observation_metadata_adds_pytdx_history_without_mutating_score(self) -> None:
        candidate = {
            "symbol": "600001",
            "name": "算力龙头",
            "score": 82.4,
            "raw_score": 82.4,
            "final_score": 82.4,
            "last_trade_date": "2026-04-30",
            "_diagnostics": {
                "history": {
                    "source": "PytdxFetcher",
                    "latest_trade_date": "2026-04-30",
                }
            },
        }

        self.service._attach_cn_provider_observation_metadata(
            [candidate],
            stock_list_source="AkshareFetcher",
            snapshot_source="AkshareFetcher",
        )

        self.assertEqual(candidate["score"], 82.4)
        observation = candidate["_diagnostics"]["cn_provider_observation"]
        self.assertEqual([item["stage"] for item in observation["entries"]], ["universe", "snapshot", "history"])
        self.assertEqual([item["providerName"] for item in observation["entries"]], ["akshare", "akshare", "pytdx"])
        history_entry = observation["entries"][2]
        self.assertEqual(history_entry["capability"], "cn_history_daily")
        self.assertEqual(history_entry["trustLevel"], "usable_with_caution")
        self.assertEqual(history_entry["asOf"], "2026-04-30")
        self.assertEqual(history_entry["updatedAt"], "2026-04-30")
        self.assertTrue(history_entry["observationOnly"])
        self.assertFalse(history_entry["scoreContributionAllowed"])

    def test_attach_cn_provider_observation_metadata_degrades_non_eligible_snapshot_provider_with_reason(self) -> None:
        candidate = {
            "symbol": "600001",
            "name": "算力龙头",
            "score": 82.4,
            "raw_score": 82.4,
            "final_score": 82.4,
            "last_trade_date": "2026-04-30",
            "_diagnostics": {
                "history": {
                    "source": "PytdxFetcher",
                    "latest_trade_date": "2026-04-30",
                }
            },
        }

        self.service._attach_cn_provider_observation_metadata(
            [candidate],
            stock_list_source="AkshareFetcher",
            snapshot_source="BaoStockFetcher",
        )

        self.assertEqual(candidate["score"], 82.4)
        observation = candidate["_diagnostics"]["cn_provider_observation"]
        self.assertEqual([item["providerId"] for item in observation["entries"]], ["akshare", "baostock", "pytdx"])
        snapshot_entry = observation["entries"][1]
        self.assertEqual(snapshot_entry["stage"], "snapshot")
        self.assertEqual(snapshot_entry["capability"], "cn_realtime_snapshot")
        self.assertEqual(snapshot_entry["freshness"], "unavailable")
        self.assertEqual(snapshot_entry["degradationReason"], "scanner_observation_route_rejected")
        self.assertEqual(snapshot_entry["missingProviderReason"], "scanner_observation_route_rejected")
        self.assertIn("provider_forbidden_for_use_case", snapshot_entry["routeRejectedReasonCodes"])
        self.assertIn("provider_not_capable", snapshot_entry["routeRejectedReasonCodes"])
        self.assertTrue(snapshot_entry["observationOnly"])
        self.assertFalse(snapshot_entry["scoreContributionAllowed"])

    def test_attach_cn_provider_observation_metadata_rejects_baostock_authority_claim_without_mutating_score(self) -> None:
        service = MarketScannerService(
            self.db,
            data_manager=self.data_manager,
            baostock_cn_history_observation_resolver=lambda symbol, history_diag: {
                **self._baostock_history_observation(
                    freshness="live",
                    as_of="2026-05-20T09:30:00+08:00",
                    updated_at="2026-05-20T09:30:00+08:00",
                    attempted_at="2026-05-20T09:30:00+08:00",
                ),
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "trustLevel": "score_grade",
                "sourceType": "exchange_public",
            }
            if str(symbol) == "600001"
            else {},
        )
        candidate = {
            "symbol": "600001",
            "name": "算力龙头",
            "score": 82.4,
            "raw_score": 82.4,
            "final_score": 82.4,
            "last_trade_date": "2026-04-30",
            "_diagnostics": {
                "history": {
                    "source": "PytdxFetcher",
                    "latest_trade_date": "2026-04-30",
                }
            },
        }

        service._attach_cn_provider_observation_metadata(
            [candidate],
            stock_list_source="AkshareFetcher",
            snapshot_source="AkshareFetcher",
        )

        self.assertEqual(candidate["score"], 82.4)
        observation = candidate["_diagnostics"]["cn_provider_observation"]
        self.assertEqual([item["providerId"] for item in observation["entries"]], ["akshare", "akshare", "pytdx", "baostock"])
        baostock_entry = observation["entries"][3]
        self.assertEqual(baostock_entry["stage"], "scanner_diagnostics")
        self.assertEqual(baostock_entry["freshness"], "unavailable")
        self.assertEqual(baostock_entry["degradationReason"], "scanner_observation_authority_claim_rejected")
        self.assertEqual(baostock_entry["missingProviderReason"], "scanner_observation_authority_claim_rejected")
        self.assertIn("live_authority_claim", baostock_entry["routeRejectedReasonCodes"])
        self.assertIn("scoring_authority_claim", baostock_entry["routeRejectedReasonCodes"])
        self.assertTrue(baostock_entry["observationOnly"])
        self.assertFalse(baostock_entry["scoreContributionAllowed"])

    def test_scanner_runtime_source_tokens_keep_registry_backed_provenance_labels(self) -> None:
        detail = self.service.run_scan(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
        )

        providers = detail["diagnostics"]["provider_diagnostics"]["providers_used"]
        self.assertIn("local_db", providers)
        self.assertIn("local_universe_cache", providers)
        self.assertEqual(resolve_source_type("local_db"), "cache_snapshot")
        self.assertEqual(resolve_source_label("local_db"), "本地数据库历史")
        self.assertEqual(resolve_source_type("local_universe_cache"), "cache_snapshot")
        self.assertEqual(resolve_source_label("local_universe_cache"), "本地候选缓存")

        profile = get_scanner_profile(market="us", profile="us_preopen_v1")
        with patch.object(
            MarketScannerService,
            "_load_local_us_universe_from_parquet",
            return_value=["NVDA", "AAPL"],
        ):
            with patch.object(self.service, "_load_local_us_universe_from_db", return_value=["PLTR"]):
                universe = self.service._resolve_us_stock_universe(profile=profile, target_symbol_count=50)

        self.assertTrue(universe["source"].startswith("local_us_parquet_dir"))
        self.assertIn("curated_us_liquid_seed", universe["source"])
        self.assertEqual(resolve_source_type("local_us_parquet_dir"), "cache_snapshot")
        self.assertEqual(resolve_source_label("local_us_parquet_dir"), "本地 Parquet 历史")
        self.assertEqual(resolve_source_type("curated_us_liquid_seed"), "fallback_static")
        self.assertEqual(resolve_source_label("curated_us_liquid_seed"), "精选美股种子池")

        self.assertEqual(resolve_source_type("local_history_degraded"), "fallback_static")
        self.assertEqual(resolve_source_label("local_history_degraded"), "本地历史降级快照")


if __name__ == "__main__":
    unittest.main()
