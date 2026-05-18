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
from src.services.market_data_source_registry import resolve_source_label, resolve_source_type
from src.services.market_scanner_service import MarketScannerService, ScannerRuntimeError
from src.services.scanner_evidence_packet import SCANNER_EVIDENCE_VERSION
from src.storage import DatabaseManager, MarketScannerRun


def _make_history(
    *,
    start_price: float,
    slope: float,
    amount_base: float,
    volume_base: float,
    bars: int = 100,
) -> pd.DataFrame:
    end_date = pd.Timestamp("2026-04-30")
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
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.stock_repo = StockRepository(self.db)
        self.data_manager = FakeScannerDataManager()
        self.service = MarketScannerService(self.db, data_manager=self.data_manager)

        local_history = self.data_manager.histories["600001"].copy()
        self.stock_repo.save_dataframe(local_history, "600001", data_source="LocalWarmCache")

    def tearDown(self) -> None:
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

    def test_apply_score_caps_and_explainability_preserves_strong_scores(self) -> None:
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

        result = self.service._load_local_stock_list_fallback()

        scanner_repo.list_recent_analysis_symbols.assert_called_once_with()
        stock_repo.list_distinct_codes.assert_called_once_with()
        self.assertTrue(result["success"])
        frame = result["data"]
        self.assertEqual(frame["code"].tolist(), ["600001", "600002", "300123"])
        self.assertEqual(frame["name"].tolist()[:2], ["算力龙头", "机器人核心"])

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
