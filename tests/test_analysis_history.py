# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 分析历史存储单元测试
===================================

职责：
1. 验证分析历史保存逻辑
2. 验证上下文快照保存开关
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

try:
    from fastapi.testclient import TestClient
    from api.app import create_app
    from api.v1.endpoints.history import get_history_detail, get_history_markdown
except ModuleNotFoundError:
    TestClient = None
    create_app = None
    get_history_detail = None
    get_history_markdown = None

from src.config import Config
from src.storage import DatabaseManager, AnalysisHistory, BacktestResult, StockDaily
from src.analyzer import AnalysisResult
from src.services.history_service import HistoryService
from scripts.clean_test_history import clean_test_history_records
import src.auth as auth

class AnalysisHistoryTestCase(unittest.TestCase):
    """分析历史存储测试"""

    def setUp(self) -> None:
        """为每个用例初始化独立数据库"""
        auth._auth_enabled = False
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_analysis_history.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        """清理资源"""
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _build_result(self) -> AnalysisResult:
        """构造分析结果"""
        return AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=78,
            trend_prediction="看多",
            operation_advice="持有",
            analysis_summary="基本面稳健，短期震荡",
        )

    def _assert_no_forbidden_keys(self, value, forbidden_keys: tuple[str, ...]) -> None:
        normalized_forbidden = {
            "".join(ch for ch in key.lower() if ch.isalnum())
            for key in forbidden_keys
        }
        found: list[str] = []

        def walk(node, path: str = "$") -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    normalized_key = "".join(ch for ch in str(key).lower() if ch.isalnum())
                    child_path = f"{path}.{key}"
                    if normalized_key in normalized_forbidden:
                        found.append(child_path)
                    walk(child, child_path)
            elif isinstance(node, list):
                for index, child in enumerate(node):
                    walk(child, f"{path}[{index}]")

        walk(value)
        self.assertEqual(found, [])

    def _save_history(self, query_id: str) -> int:
        """保存一条测试历史记录并返回主键 ID。"""
        result = self._build_result()
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            return row.id

    def test_save_analysis_history_with_snapshot(self) -> None:
        """保存历史记录并写入上下文快照"""
        result = self._build_result()
        result.dashboard = {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "理想买入点：125.5元",
                    "secondary_buy": "120",
                    "stop_loss": "止损位：110元",
                    "take_profit": "目标位：150.0元",
                }
            }
        }
        context_snapshot = {"enhanced_context": {"code": "600519"}}

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_001",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=context_snapshot,
            save_snapshot=True
        )

        self.assertEqual(saved, 1)

        history = self.db.get_analysis_history(code="600519", days=7, limit=10)
        self.assertEqual(len(history), 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            self.assertEqual(row.query_id, "query_001")
            self.assertIsNotNone(row.context_snapshot)
            self.assertEqual(row.ideal_buy, 125.5)
            self.assertEqual(row.secondary_buy, 120.0)
            self.assertEqual(row.stop_loss, 110.0)
            self.assertEqual(row.take_profit, 150.0)

    def test_save_analysis_history_without_snapshot(self) -> None:
        """关闭快照保存时不写入 context_snapshot"""
        result = self._build_result()

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_002",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot={"foo": "bar"},
            save_snapshot=False
        )

        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            self.assertIsNone(row.context_snapshot)

    def test_save_analysis_history_persists_model_used(self) -> None:
        """model_used should be persisted in raw_result for history detail."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.0-flash"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_003",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_003").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            payload = json.loads(row.raw_result or "{}")
            self.assertEqual(payload.get("model_used"), "gemini/gemini-2.0-flash")

    def test_history_detail_hides_placeholder_model_used(self) -> None:
        """Placeholder model values should be normalized to None in detail response."""
        result = self._build_result()
        result.model_used = "unknown"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_004",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_004").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertIsNone(detail.get("model_used"))

    def test_history_detail_prefers_persisted_report_payload_over_rebuilt_snapshot(self) -> None:
        """History detail should prefer the exact persisted report payload when it exists."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.0-flash"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_persisted_report_001",
            report_type="detailed",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_persisted_report_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            row.raw_result = json.dumps({
                "code": "600519",
                "name": "贵州茅台",
                "model_used": "gemini/gemini-2.0-flash",
                "persisted_report": {
                    "meta": {
                        "query_id": "query_persisted_report_001",
                        "stock_code": "600519",
                        "stock_name": "贵州茅台",
                        "report_type": "detailed",
                        "report_language": "zh",
                        "created_at": "2026-04-27T10:00:00Z",
                        "model_used": "gemini/gemini-2.0-flash",
                    },
                    "summary": {
                        "analysis_summary": "这是持久化后的完整报告摘要",
                        "operation_advice": "等待更优确认",
                        "trend_prediction": "趋势延续但要防回撤",
                        "sentiment_score": 73,
                        "sentiment_label": "乐观",
                    },
                    "strategy": {
                        "ideal_buy": "1680 - 1705",
                        "secondary_buy": "1660 - 1670",
                        "stop_loss": "1628",
                        "take_profit": "1788",
                    },
                    "details": {
                        "news_summary": "持久化新闻摘要",
                        "standard_report": {
                            "summary_panel": {
                                "stock": "贵州茅台",
                                "ticker": "600519",
                                "one_sentence": "持久化标准报告应被原样返回",
                            },
                            "technical_fields": [
                                {"label": "MACD", "value": "持久化后的技术结论"}
                            ],
                        },
                    },
                },
            })
            record_id = row.id
            session.commit()

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("analysis_summary"), "这是持久化后的完整报告摘要")
        self.assertEqual(detail.get("ideal_buy"), "1680 - 1705")
        self.assertEqual(detail.get("secondary_buy"), "1660 - 1670")
        self.assertEqual(detail.get("stop_loss"), "1628")
        self.assertEqual(detail.get("take_profit"), "1788")
        self.assertEqual(detail.get("news_content"), "持久化新闻摘要")
        self.assertEqual(
            detail.get("standard_report", {}).get("summary_panel", {}).get("one_sentence"),
            "持久化标准报告应被原样返回",
        )

    def test_history_detail_rejects_persisted_report_with_mismatched_symbol(self) -> None:
        """History detail should not attach stale AAPL payloads to an ORCL history row."""
        result = AnalysisResult(
            code="ORCL",
            name="Oracle",
            sentiment_score=52,
            trend_prediction="Neutral",
            operation_advice="Observe",
            analysis_summary="ORCL row summary",
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_mismatched_persisted_report_001",
            report_type="detailed",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_mismatched_persisted_report_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            row.raw_result = json.dumps({
                "code": "AAPL",
                "name": "Apple",
                "persisted_report": {
                    "meta": {
                        "query_id": "query_mismatched_persisted_report_001",
                        "stock_code": "AAPL",
                        "stock_name": "Apple",
                        "report_type": "detailed",
                        "created_at": "2026-06-07T08:00:00Z",
                    },
                    "summary": {
                        "analysis_summary": "AAPL stale report content",
                        "operation_advice": "Buy",
                        "trend_prediction": "Bullish",
                        "sentiment_score": 88,
                    },
                    "strategy": {
                        "ideal_buy": "AAPL entry",
                        "stop_loss": "AAPL stop loss",
                        "take_profit": "AAPL target price",
                    },
                    "details": {
                        "standard_report": {
                            "summary_panel": {
                                "stock": "Apple",
                                "ticker": "AAPL",
                                "one_sentence": "AAPL stale report content",
                            },
                        },
                    },
                },
                "dashboard": {
                    "summary": {
                        "ticker": "AAPL",
                        "one_sentence": "AAPL stale dashboard content",
                    },
                },
            })
            record_id = row.id
            session.commit()

        detail = HistoryService(self.db).get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("stock_code"), "ORCL")
        self.assertEqual(detail.get("analysis_summary"), "ORCL row summary")
        self.assertNotIn("AAPL", json.dumps(detail, ensure_ascii=False))
        self.assertEqual(detail.get("raw_result"), {})
        self.assertEqual(
            detail.get("standard_report", {}).get("summary_panel", {}).get("ticker"),
            "ORCL",
        )

        if get_history_detail is not None:
            report = get_history_detail(str(record_id), db_manager=self.db)
            payload = report.model_dump(mode="json", by_alias=True, exclude_none=True)
            self.assertEqual(payload["meta"]["stock_code"], "ORCL")
            self.assertNotIn("AAPL", json.dumps(payload, ensure_ascii=False))

    def test_attach_persisted_report_enriches_canonical_payload_and_exposes_generated_at(self) -> None:
        result = self._build_result()
        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_canonical_report_001",
            report_type="detailed",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        generated_at = "2026-04-28T17:30:00+08:00"
        attached = self.db.attach_analysis_report_payload(
            query_id="query_canonical_report_001",
            report_payload={
                "meta": {
                    "query_id": "query_canonical_report_001",
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "company_name": "贵州茅台",
                    "report_type": "detailed",
                    "report_language": "zh",
                    "created_at": "2026-04-28T17:29:00+08:00",
                    "report_generated_at": generated_at,
                    "generated_at": generated_at,
                    "is_test": True,
                    "strategy_type": "hold",
                },
                "summary": {
                    "analysis_summary": "数据库中的 canonical report 应成为唯一真源",
                    "operation_advice": "持有",
                    "trend_prediction": "震荡偏强",
                    "sentiment_score": 78,
                    "sentiment_label": "乐观",
                    "strategy_summary": "等待确认后按节奏执行",
                },
                "strategy": {
                    "ideal_buy": "1680 - 1705",
                    "stop_loss": "1628",
                    "take_profit": "1788",
                },
                "details": {
                    "news_summary": "持久化新闻摘要",
                },
                "decision_trace": {
                    "engine_version": "analysis_decision_trace_v1",
                    "symbol": "600519",
                    "market": "CN",
                    "decision_fields": {
                        "action": {"value": "hold", "source": "rule"},
                        "score": {"value": 78, "source": "rule"},
                    },
                    "data_sources": [
                        {"name": "quote", "status": "used", "provider": "test"},
                    ],
                    "llm": {"used": True, "schema_validated": False},
                },
            },
        )
        self.assertEqual(attached, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_canonical_report_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            raw_result = json.loads(row.raw_result or "{}")
            persisted_report = raw_result.get("persisted_report") or {}

        self.assertEqual(persisted_report.get("meta", {}).get("id"), row.id)
        self.assertEqual(persisted_report.get("meta", {}).get("generated_at"), generated_at)
        self.assertEqual(persisted_report.get("meta", {}).get("report_generated_at"), generated_at)
        self.assertEqual(persisted_report.get("meta", {}).get("company_name"), "贵州茅台")
        self.assertTrue(persisted_report.get("meta", {}).get("is_test"))
        self.assertEqual(persisted_report.get("meta", {}).get("strategy_type"), "hold")
        self.assertEqual(persisted_report.get("summary", {}).get("strategy_summary"), "等待确认后按节奏执行")
        self.assertEqual(
            persisted_report.get("decision_trace", {}).get("engine_version"),
            "analysis_decision_trace_v1",
        )

        service = HistoryService(self.db)
        history_list = service.get_history_list(page=1, limit=10)
        self.assertEqual(history_list["items"][0]["generated_at"], generated_at)
        self.assertTrue(history_list["items"][0]["is_test"])

        detail = service.get_history_detail_by_id(row.id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("id"), row.id)
        self.assertEqual(detail.get("report_generated_at"), generated_at)
        self.assertEqual(detail.get("company_name"), "贵州茅台")
        self.assertTrue(detail.get("is_test"))
        self.assertEqual(detail.get("decision_trace", {}).get("symbol"), "600519")
        self.assertEqual(detail.get("decision_trace", {}).get("llm", {}).get("schema_validated"), False)

        if get_history_detail is not None:
            report = get_history_detail(str(row.id), db_manager=self.db)
            self.assertEqual(report.decision_trace.get("symbol"), "600519")
            self.assertEqual(report.decision_trace.get("llm", {}).get("schema_validated"), False)

    def test_history_detail_accepts_dict_raw_result(self) -> None:
        """_record_to_detail_dict should handle dict raw_result without json.loads errors."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.0-flash"
        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_005",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_005").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            row.raw_result = {"model_used": "unknown", "extra": "v"}

            service = HistoryService(self.db)
            detail = service._record_to_detail_dict(row)

        self.assertIsNotNone(detail)
        self.assertIsInstance(detail.get("raw_result"), dict)
        self.assertIsNone(detail.get("model_used"))

    def test_extract_time_contract_derives_market_session_date_from_timestamp(self) -> None:
        contract = HistoryService._extract_time_contract(
            {
                "enhanced_context": {
                    "market_timestamp": "2026-03-27T13:32:41-04:00",
                    "market_session_date": "2026-03-28",
                    "session_type": "intraday_snapshot",
                }
            }
        )

        self.assertEqual(contract["market_session_date"], "2026-03-27")
        self.assertEqual(contract["market_timestamp"], "2026-03-27T13:32:41-04:00")
        self.assertEqual(contract["session_type"], "intraday_snapshot")

    def test_merge_market_snapshot_repairs_completed_session_prev_close_basis(self) -> None:
        merged = HistoryService._merge_market_snapshot_from_context(
            {
                "close": 167.52,
                "prev_close": 167.52,
                "change_amount": 0.0,
                "pct_chg": 0.0,
                "session_type": "last_completed_session",
            },
            {
                "enhanced_context": {
                    "session_type": "last_completed_session",
                    "today": {
                        "close": 167.52,
                        "pct_chg": -2.17,
                        "high": 171.0,
                        "low": 167.1,
                        "data_source": "yfinance_eod",
                    },
                    "yesterday": {
                        "close": 171.24,
                        "data_source": "yfinance_eod",
                    },
                    "realtime": {
                        "price": 167.52,
                        "change_pct": -2.17,
                    },
                }
            },
        )

        self.assertAlmostEqual(float(merged["close"]), 167.52, places=2)
        self.assertAlmostEqual(float(merged["prev_close"]), 171.24, places=2)
        self.assertAlmostEqual(float(merged["change_amount"]), -3.72, places=2)
        self.assertAlmostEqual(float(merged["pct_chg"]), -2.17, places=2)
        self.assertAlmostEqual(float(merged["price"]), 167.52, places=2)
        self.assertEqual(merged["source"], "yfinance_eod")

    def test_history_detail_prefers_raw_sniper_strings(self) -> None:
        """History detail should display the original sniper point strings from raw_result."""
        result = self._build_result()
        result.dashboard = {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "理想买入点：125.5元",
                    "secondary_buy": "120-121 元分批",
                    "stop_loss": "跌破 110 元止损",
                    "take_profit": "目标位：150.0元",
                }
            }
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_006",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_006").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("ideal_buy"), "理想买入点：125.5元")
        self.assertEqual(detail.get("secondary_buy"), "120-121 元分批")
        self.assertEqual(detail.get("stop_loss"), "跌破 110 元止损")
        self.assertEqual(detail.get("take_profit"), "目标位：150.0元")

    def test_history_detail_falls_back_to_numeric_sniper_columns(self) -> None:
        """History detail should still fall back to stored numeric sniper columns when raw strings are unavailable."""
        result = self._build_result()
        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_007",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_007").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            row.ideal_buy = 125.5
            row.secondary_buy = 120.0
            row.stop_loss = 110.0
            row.take_profit = 150.0
            row.raw_result = json.dumps({"model_used": "gemini/gemini-2.0-flash"})
            session.commit()
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("ideal_buy"), "125.5")
        self.assertEqual(detail.get("secondary_buy"), "120.0")
        self.assertEqual(detail.get("stop_loss"), "110.0")
        self.assertEqual(detail.get("take_profit"), "150.0")

    def test_history_detail_uses_fundamental_snapshot_fallback_when_context_missing(self) -> None:
        """When context_snapshot is disabled, detail API should fallback to fundamental_snapshot."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        query_id = "query_fundamental_fallback_001"
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        self.db.save_fundamental_snapshot(
            query_id=query_id,
            code="600519",
            payload={
                "earnings": {
                    "data": {
                        "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                        "dividend": {"ttm_dividend_yield_pct": 2.6, "ttm_cash_dividend_per_share": 1.3},
                    }
                }
            },
        )

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.details.financial_report["report_date"], "2025-12-31")
        self.assertEqual(report.details.dividend_metrics["ttm_dividend_yield_pct"], 2.6)

    def test_history_detail_returns_null_fundamental_fields_when_snapshot_absent(self) -> None:
        """Detail API should keep new fields nullable when no context/fundamental snapshot exists."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_fundamental_fallback_002"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertIsNone(report.details.financial_report)
        self.assertIsNone(report.details.dividend_metrics)
        self.assertIsNone(report.decision_trace)
        self.assertNotEqual((report.report_quality or {}).get("schema_status"), "ok")

    def test_history_detail_rebuilds_standard_report_from_context_snapshot(self) -> None:
        result = AnalysisResult(
            code="NVDA",
            name="NVIDIA",
            sentiment_score=82,
            trend_prediction="看多",
            operation_advice="持有",
            analysis_summary="等待确认",
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "battle_plan": {},
                "intelligence": {},
            },
        )
        context_snapshot = {
            "enhanced_context": {
                "market_timestamp": "2026-03-27T09:35:00-04:00",
                "market_session_date": "2026-03-27",
                "report_generated_at": "2026-03-27T21:35:00+08:00",
                "session_type": "intraday_snapshot",
                "today": {
                    "close": 125.3,
                    "open": 123.5,
                    "high": 126.2,
                    "low": 122.9,
                    "pct_chg": 1.87,
                    "volume": 4500000,
                    "amount": 880000000,
                    "ma5": 123.4567,
                    "ma10": 122.1234,
                    "ma20": 120.9876,
                },
                "yesterday": {"close": 123.0},
                "realtime": {
                    "price": 125.3,
                    "pre_close": 123.0,
                    "change_amount": 2.3,
                    "change_pct": 1.87,
                    "amplitude": 2.68,
                    "volume": 4500000,
                    "amount": 880000000,
                    "open_price": 123.5,
                    "high": 126.2,
                    "low": 122.9,
                    "volume_ratio": 1.35,
                    "turnover_rate": 0.88,
                    "source": "yfinance",
                    "vwap": 124.9876,
                    "pb_ratio": 9.87,
                    "total_mv": 123400000000,
                    "circ_mv": 100000000000,
                },
                "technicals": {
                    "ma5": {"value": 123.4567, "status": "ok"},
                    "ma10": {"value": 122.1234, "status": "ok"},
                    "ma20": {"value": 120.9876, "status": "ok"},
                    "rsi14": {"value": 56.777, "status": "ok"},
                },
                "fundamentals": {
                    "normalized": {
                        "marketCap": 123400000000,
                        "priceToBook": 9.87,
                        "sharesOutstanding": 5000000000,
                        "fiftyTwoWeekHigh": 199.876,
                        "fiftyTwoWeekLow": 99.123,
                    }
                },
                "fundamental_context": {
                    "valuation": {
                        "data": {
                            "market_cap": 123400000000,
                            "pb_ratio": 9.87,
                            "shares_outstanding": 5000000000,
                            "52week_high": 199.876,
                            "52week_low": 99.123,
                        }
                    },
                    "earnings": {
                        "data": {
                            "financial_report": {
                                "revenue": 10000000000,
                                "net_income": 2500000000,
                            }
                        }
                    },
                },
                "earnings_analysis": {
                    "quarterly_series": [{"revenue": 10000000000, "net_income": 2500000000}],
                    "derived_metrics": {"yoy_net_income_change": 0.12},
                },
            }
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_context_standard_report_001",
            report_type="full",
            news_content="news",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_context_standard_report_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        detail = HistoryService(self.db).get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        std = detail["standard_report"]
        self.assertEqual(std["summary_panel"]["ticker"], "NVDA")
        self.assertEqual(std["table_sections"]["market"]["title"], "行情表")
        regular = {item["label"]: item["value"] for item in std["market"]["regular_fields"]}
        technical = {item["label"]: item["value"] for item in std["technical_fields"]}
        fundamental = {item["label"]: item["value"] for item in std["fundamental_fields"]}

        self.assertEqual(regular["昨收"], "123.00")
        self.assertEqual(regular["涨跌额"], "2.30")
        self.assertEqual(regular["涨跌幅"], "1.87%")
        self.assertEqual(regular["成交量"], "450.00万")
        self.assertEqual(regular["成交额"], "8.80亿")
        self.assertEqual(technical["MA5"], "123.46")
        self.assertEqual(technical["MA10"], "122.12")
        self.assertEqual(technical["VWAP"], "124.99")
        self.assertEqual(fundamental["市净率(最新值)"], "9.87")
        self.assertEqual(fundamental["52周最高"], "199.88")
        self.assertEqual(fundamental["净利润(TTM)"], "25.00亿")
        self.assertEqual(detail["market_timestamp"], "2026-03-27T09:35:00-04:00")
        self.assertEqual(detail["market_session_date"], "2026-03-27")
        self.assertEqual(detail["report_generated_at"], "2026-03-27T21:35:00+08:00")

    def test_get_analysis_context_ignores_future_dated_us_snapshot_rows(self) -> None:
        with self.db.get_session() as session:
            session.add_all(
                [
                    StockDaily(
                        code="NVDA",
                        date=date(2026, 3, 28),
                        open=169.99,
                        high=170.97,
                        low=167.55,
                        close=168.99,
                        volume=107549476,
                        data_source="yfinance_realtime_snapshot",
                    ),
                    StockDaily(
                        code="NVDA",
                        date=date(2026, 3, 27),
                        open=176.17,
                        high=176.50,
                        low=171.14,
                        close=171.24,
                        volume=182162282,
                        data_source="yfinance",
                    ),
                    StockDaily(
                        code="NVDA",
                        date=date(2026, 3, 26),
                        open=174.00,
                        high=177.00,
                        low=173.50,
                        close=175.00,
                        volume=150000000,
                        data_source="yfinance",
                    ),
                ]
            )
            session.commit()

        class _FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                base = datetime(2026, 3, 27, 20, 0, 0)
                return base.replace(tzinfo=tz) if tz is not None else base

        with patch("src.storage.datetime", _FakeDateTime):
            context = self.db.get_analysis_context("NVDA")

        self.assertIsNotNone(context)
        self.assertEqual(context["date"], "2026-03-27")
        self.assertEqual(context["today"]["close"], 171.24)
        self.assertEqual(context["yesterday"]["close"], 175.00)

    def test_merge_dashboard_from_context_replaces_placeholder_zero_values(self) -> None:
        merged = HistoryService._merge_dashboard_from_context(
            {
                "data_perspective": {
                    "trend_status": {
                        "trend_score": 0,
                        "signal_score": "0.00",
                    },
                    "price_position": {
                        "current_price": 0,
                        "ma5": 0,
                        "ma10": "0.00",
                        "ma20": 0.0,
                        "ma60": 0,
                    },
                    "volume_analysis": {
                        "volume_ratio": 0.0,
                        "turnover_rate": "0.00",
                    },
                }
            },
            {
                "enhanced_context": {
                    "today": {
                        "close": 362.19,
                        "ma5": None,
                        "ma10": None,
                        "ma20": 392.81,
                    },
                    "realtime": {
                        "price": 362.19,
                        "volume_ratio": 1.24,
                        "turnover_rate": 0.99,
                        "volume_ratio_desc": "资金回流",
                    },
                    "technicals": {
                        "ma60": {"value": 415.74, "status": "ok"},
                    },
                    "trend_analysis": {
                        "trend_strength": 20,
                        "signal_score": 36,
                        "ma_alignment": "空头/震荡",
                        "volume_status": "正常",
                        "bias_ma5": None,
                    },
                }
            },
        )

        data_perspective = merged["data_perspective"]
        self.assertEqual(data_perspective["trend_status"]["trend_score"], 20)
        self.assertEqual(data_perspective["trend_status"]["signal_score"], 36)
        self.assertEqual(data_perspective["trend_status"]["ma_alignment"], "空头/震荡")
        self.assertEqual(data_perspective["price_position"]["current_price"], 362.19)
        self.assertEqual(data_perspective["price_position"]["ma20"], 392.81)
        self.assertEqual(data_perspective["price_position"]["ma60"], 415.74)
        self.assertEqual(data_perspective["volume_analysis"]["volume_ratio"], 1.24)
        self.assertEqual(data_perspective["volume_analysis"]["turnover_rate"], 0.99)
        self.assertEqual(data_perspective["volume_analysis"]["volume_meaning"], "资金回流")

    def test_history_detail_endpoint_exposes_time_contract_meta(self) -> None:
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_history_time_contract_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="full",
            news_content="news",
            context_snapshot={
                "enhanced_context": {
                    "market_timestamp": "2026-03-27T09:35:00-04:00",
                    "market_session_date": "2026-03-27",
                    "news_published_at": "2026-03-27T09:00:00-04:00",
                    "report_generated_at": "2026-03-27T21:35:00+08:00",
                }
            },
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.market_timestamp, "2026-03-27T09:35:00-04:00")
        self.assertEqual(report.meta.market_session_date, "2026-03-27")
        self.assertEqual(report.meta.news_published_at, "2026-03-27T09:00:00-04:00")
        self.assertEqual(report.meta.report_generated_at, "2026-03-27T21:35:00+08:00")

    def test_history_detail_endpoint_exposes_company_name_and_is_test(self) -> None:
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_history_company_name_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="detailed",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        attached = self.db.attach_analysis_report_payload(
            query_id=query_id,
            report_payload={
                "meta": {
                    "query_id": query_id,
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "company_name": "贵州茅台",
                    "report_type": "detailed",
                    "report_language": "zh",
                    "generated_at": "2026-04-28T17:35:00+08:00",
                    "report_generated_at": "2026-04-28T17:35:00+08:00",
                    "is_test": True,
                },
                "summary": {
                    "analysis_summary": "测试公司名返回",
                },
                "details": {},
            },
        )
        self.assertEqual(attached, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.stock_name, "贵州茅台")
        self.assertEqual(report.meta.company_name, "贵州茅台")
        self.assertTrue(report.meta.is_test)
        payload = report.model_dump(mode="json", by_alias=True, exclude_none=True)
        serialized_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for forbidden_marker in (
            "researchPacketV1",
            "researchPacket",
            "research_packet_v1",
            "runtimePosture",
            "dataCoverageRows",
            '"lanes"',
        ):
            self.assertNotIn(forbidden_marker, serialized_payload)
        self._assert_no_forbidden_keys(
            payload,
            (
                "researchPacketV1",
                "researchPacket",
                "research_packet_v1",
                "runtimePosture",
                "dataCoverageRows",
                "lanes",
                "laneInternals",
                "laneDiagnostics",
                "rawProviderPayload",
                "rawSourcePayload",
                "rawCachePayload",
                "rawLaneInternals",
                "providerRoute",
                "cacheDebug",
                "cacheKey",
                "reasonCode",
                "reasonFamilies",
                "backendTrace",
                "backendDiagnostics",
                "internalDiagnostics",
                "routerInternals",
            ),
        )

    @patch("src.auth.is_auth_enabled", return_value=False)
    def test_history_detail_api_omits_raw_debug_containers(self, mock_auth) -> None:
        """History detail API should project safe report fields without raw/debug containers."""
        if TestClient is None or create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_history_raw_container_sanitizer_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="detailed",
            news_content="新闻摘要",
            context_snapshot={
                "enhanced_context": {
                    "market_timestamp": "2026-03-27T09:35:00-04:00",
                    "report_generated_at": "2026-03-27T21:35:00+08:00",
                },
                "raw_provider_payload": "CONTEXT_RAW_PAYLOAD_SHOULD_NOT_LEAK",
            },
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.session_scope() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            row.raw_result = json.dumps({
                "code": "600519",
                "model_used": "fixture-model",
                "raw_ai_response": {
                    "content": "RAW_AI_RESPONSE_SHOULD_NOT_LEAK",
                    "hidden_reasoning": "HIDDEN_REASONING_SHOULD_NOT_LEAK",
                },
                "persisted_report": {
                    "meta": {
                        "query_id": query_id,
                        "stock_code": "600519",
                        "stock_name": "贵州茅台",
                        "company_name": "贵州茅台",
                        "report_type": "detailed",
                        "report_language": "zh",
                    },
                    "summary": {
                        "analysis_summary": "安全摘要仍应返回",
                        "operation_advice": "继续跟踪",
                        "trend_prediction": "震荡偏强",
                        "sentiment_score": 72,
                    },
                    "strategy": {
                        "ideal_buy": "1680 - 1705",
                        "stop_loss": "1628",
                    },
                    "details": {
                        "news_summary": "安全新闻摘要",
                        "raw_ai_response": {
                            "content": "PERSISTED_RAW_AI_SHOULD_NOT_LEAK",
                            "traceback": "TRACEBACK_SHOULD_NOT_LEAK",
                        },
                        "standard_report": {
                            "summary_panel": {
                                "ticker": "600519",
                                "one_sentence": "安全标准报告摘要",
                            },
                            "technical_fields": [
                                {"label": "MACD", "value": "金叉后放量", "source": "历史报告"},
                            ],
                            "debug_schema": {"traceback": "TRACEBACK_SHOULD_NOT_LEAK"},
                            "provider_payload_ref": "PROVIDER_PAYLOAD_REF_SHOULD_NOT_LEAK",
                            "internal_diagnostics": "token=HISTORY_DETAIL_SHOULD_NOT_LEAK",
                        },
                    },
                },
            }, ensure_ascii=False)
            record_id = row.id

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        client = TestClient(create_app(static_dir=static_dir))

        response = client.get(f"/api/v1/history/{record_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        details = payload.get("details") or {}

        self.assertEqual(payload["summary"]["analysis_summary"], "安全摘要仍应返回")
        self.assertEqual(payload["strategy"]["ideal_buy"], "1680 - 1705")
        self.assertEqual(details.get("news_content"), "安全新闻摘要")
        self.assertEqual(
            details.get("standard_report", {}).get("summary_panel", {}).get("one_sentence"),
            "安全标准报告摘要",
        )
        for raw_container in (
            "raw_result",
            "rawResult",
            "raw_ai_response",
            "rawAiResponse",
            "context_snapshot",
            "contextSnapshot",
        ):
            self.assertNotIn(raw_container, details)

        serialized_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for forbidden_marker in (
            "RAW_AI_RESPONSE_SHOULD_NOT_LEAK",
            "PERSISTED_RAW_AI_SHOULD_NOT_LEAK",
            "HIDDEN_REASONING_SHOULD_NOT_LEAK",
            "CONTEXT_RAW_PAYLOAD_SHOULD_NOT_LEAK",
            "TRACEBACK_SHOULD_NOT_LEAK",
            "PROVIDER_PAYLOAD_REF_SHOULD_NOT_LEAK",
            "HISTORY_DETAIL_SHOULD_NOT_LEAK",
            "raw_ai_response",
            "context_snapshot",
            "provider_payload_ref",
            "internal_diagnostics",
        ):
            self.assertNotIn(forbidden_marker, serialized_payload)
        self._assert_no_forbidden_keys(
            payload,
            (
                "raw_result",
                "rawResult",
                "raw_ai_response",
                "rawAiResponse",
                "context_snapshot",
                "contextSnapshot",
                "rawProviderPayload",
                "provider_payload_ref",
                "debug_schema",
                "traceback",
                "internal_diagnostics",
            ),
        )

        with self.db.get_session() as session:
            persisted_row = session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first()
            if persisted_row is None:
                self.fail("未找到保存的历史记录")
            self.assertIn("RAW_AI_RESPONSE_SHOULD_NOT_LEAK", persisted_row.raw_result or "")
            self.assertIn("CONTEXT_RAW_PAYLOAD_SHOULD_NOT_LEAK", persisted_row.context_snapshot or "")

    def test_clean_test_history_script_deletes_only_flagged_rows(self) -> None:
        self.assertEqual(
            self.db.save_analysis_history(
                result=self._build_result(),
                query_id="query_clean_test_001",
                report_type="simple",
                news_content="新闻摘要",
                context_snapshot=None,
                save_snapshot=False,
                is_test=True,
            ),
            1,
        )
        self.assertEqual(
            self.db.save_analysis_history(
                result=self._build_result(),
                query_id="query_clean_test_002",
                report_type="simple",
                news_content="新闻摘要",
                context_snapshot=None,
                save_snapshot=False,
                is_test=False,
            ),
            1,
        )

        self.assertEqual(clean_test_history_records(dry_run=True), 1)

        with self.db.get_session() as session:
            dry_run_remaining = session.query(AnalysisHistory).order_by(AnalysisHistory.query_id.asc()).all()

        self.assertEqual(
            [row.query_id for row in dry_run_remaining],
            ["query_clean_test_001", "query_clean_test_002"],
        )

        self.assertEqual(clean_test_history_records(), 1)

        with self.db.get_session() as session:
            remaining = session.query(AnalysisHistory).order_by(AnalysisHistory.query_id.asc()).all()

        self.assertEqual([row.query_id for row in remaining], ["query_clean_test_001", "query_clean_test_002"])

        self.assertEqual(clean_test_history_records(dry_run=False), 1)

        with self.db.get_session() as session:
            deleted_remaining = session.query(AnalysisHistory).order_by(AnalysisHistory.query_id.asc()).all()

        self.assertEqual([row.query_id for row in deleted_remaining], ["query_clean_test_002"])

    def test_history_markdown_localizes_english_report_and_placeholder_name(self) -> None:
        """History markdown should preserve report_language for English reports."""
        result = AnalysisResult(
            code="AAPL",
            name="股票AAPL",
            sentiment_score=78,
            trend_prediction="Bullish",
            operation_advice="Buy",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
            dashboard={
                "core_conclusion": {
                    "one_sentence": "Favor buying on pullbacks.",
                    "position_advice": {
                        "no_position": "Open a starter position.",
                        "has_position": "Hold and trail the stop.",
                    },
                },
                "intelligence": {
                    "risk_alerts": [],
                },
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "180-182",
                        "stop_loss": "172",
                        "take_profit": "195",
                    }
                },
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_markdown_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_markdown_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("Stock Research Observation Report", markdown)
        self.assertIn("Research Summary", markdown)
        self.assertIn("Observation Plan", markdown)
        self.assertIn("Score / Observation / Trend", markdown)
        self.assertIn("News Published (BJT)", markdown)
        self.assertNotIn("新闻发布时间（北京时间）", markdown)
        self.assertIn("Unnamed Stock (AAPL)", markdown)
        self.assertIn("Research Observation Dashboard", markdown)
        self.assertIn("Continue observing until the research packet is complete.", markdown)
        self.assertIn("Continue tracking the risk boundary.", markdown)
        forbidden_markdown_terms = (
            "Open a starter position",
            "Hold and trail the stop",
            "Buy",
            "Decision Dashboard",
            "Decision Summary",
            "Stock Analysis Report",
            "Ideal buy",
            "Stop loss",
            "target price",
            "position sizing",
            "battle plan",
            "sniper",
        )
        for term in forbidden_markdown_terms:
            self.assertNotIn(term, markdown, term)

    def test_history_detail_localizes_english_summary_fields(self) -> None:
        """History detail should localize summary enums for English reports."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = AnalysisResult(
            code="AAPL",
            name="股票AAPL",
            sentiment_score=78,
            trend_prediction="看多",
            operation_advice="买入",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_detail_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_detail_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)

        self.assertEqual(report.meta.report_language, "en")
        self.assertEqual(report.meta.stock_name, "Unnamed Stock")
        self.assertEqual(report.summary.operation_advice, "Positive observation")
        self.assertNotIn("Buy", report.summary.operation_advice)
        self.assertEqual(report.summary.trend_prediction, "Bullish")
        self.assertEqual(report.summary.sentiment_label, "Bullish")

    def test_history_markdown_includes_bias_value_without_unsafe_emoji(self) -> None:
        """English markdown should keep bias value display and avoid incorrect risk emoji text."""
        result = AnalysisResult(
            code="AAPL",
            name="股票AAPL",
            sentiment_score=80,
            trend_prediction="Bullish",
            operation_advice="Buy",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
            dashboard={
                "data_perspective": {
                    "price_position": {
                        "current_price": 190.5,
                        "ma5": 188.0,
                        "ma10": 184.5,
                        "ma20": 179.2,
                        "bias_ma5": 1.33,
                        "bias_status": "Safe",
                        "support_level": 184.5,
                        "resistance_level": 195.0,
                    }
                }
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_markdown_bias_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_markdown_bias_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("**乖离率(MA5)**: 1.33%", markdown)
        self.assertNotIn("🚨Safe", markdown)

    def test_history_markdown_export_filters_advice_provider_and_diagnostics(self) -> None:
        """Markdown export should sanitize advice wording and raw diagnostics only at the API seam."""
        if get_history_markdown is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = AnalysisResult(
            code="AAPL",
            name="Apple",
            sentiment_score=82,
            trend_prediction="Bullish",
            operation_advice="Buy",
            analysis_summary=(
                "研究摘要：基本面收入保持增长，重大产品事件值得继续跟踪；"
                "buy on pullback, stop loss, take profit, target price, position sizing."
            ),
            report_language="zh",
            dashboard={
                "core_conclusion": {
                    "one_sentence": (
                        "研究摘要：基本面收入保持增长，重大产品事件值得继续跟踪；"
                        "buy on pullback, stop loss, take profit, target price, position sizing."
                    ),
                    "position_advice": {
                        "no_position": "空仓者建议：立即 buy，原因 reasonCode=provider_missing",
                        "has_position": "持仓者建议：sell if stop loss breaks",
                    },
                },
                "intelligence": {
                    "sentiment_summary": "事件：新品发布会提升关注度。",
                    "earnings_outlook": "基本面：收入与利润率保持观察价值。",
                    "positive_catalysts": ["事件跟踪：服务收入增长。"],
                    "risk_alerts": ["Market Feed provider trace raw diagnostics"],
                    "latest_news": "Yahoo Finance / Finnhub / Alpacafetcher provider trace",
                },
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "理想买入点 180-182",
                        "secondary_buy": "次优买入点 176",
                        "stop_loss": "止损位 168",
                        "take_profit": "目标一区 195 / 目标二区 205",
                    },
                    "position_strategy": {
                        "suggested_position": "position sizing 20%",
                        "entry_plan": "建仓策略：buy in batches",
                        "risk_control": "风控策略：stop loss",
                    },
                    "action_checklist": ["reasonCode=backend_snake_case", "字段待接入"],
                },
                "structured_analysis": {
                    "fundamentals": {
                        "normalized": {
                            "trailingPE": 28.4,
                            "totalRevenue": 391035000000,
                            "netIncomeToCommon": 97000000000,
                            "returnOnEquity": 1.47,
                        },
                    },
                    "fundamental_context": {
                        "earnings": {
                            "data": {
                                "earnings_outlook": "基本面：收入与利润率保持观察价值。"
                            }
                        }
                    },
                },
            },
        )

        self.assertEqual(
            self.db.save_analysis_history(
                result=result,
                query_id="query_markdown_export_safety_001",
                report_type="full",
                news_content="news",
                context_snapshot=None,
                save_snapshot=False,
            ),
            1,
        )

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_markdown_export_safety_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        raw_markdown = HistoryService(self.db).get_markdown_report(str(record_id))
        self.assertIsNotNone(raw_markdown)
        self.assertIn("关键价格区间", raw_markdown)
        self.assertNotIn("理想买入点", raw_markdown)
        self.assertIn("Missing Field Audit", raw_markdown)
        self.assertIn("Yahoo Finance", raw_markdown)

        detail_report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(detail_report.summary.operation_advice, "正向观察")
        self.assertNotIn("买入", detail_report.summary.operation_advice)

        response = get_history_markdown(str(record_id), db_manager=self.db)
        exported = response.content

        forbidden_terms = (
            "理想买入点",
            "次优买入点",
            "止损位",
            "目标一区",
            "目标二区",
            "空仓者建议",
            "持仓者建议",
            "建仓策略",
            "风控策略",
            "作战计划",
            "狙击点位",
            "stop loss",
            "take profit",
            "target price",
            "position sizing",
            "Alpacafetcher",
            "Yahoo Finance",
            "Finnhub",
            "Market Feed",
            "Missing Field Audit",
            "Full Truth",
            "integrated_unavailable",
            "接口未返回",
            "字段待接入",
            "reasonCode",
            "backend_snake_case",
            "raw diagnostics",
        )
        exported_lower = exported.lower()
        for term in forbidden_terms:
            self.assertNotIn(term.lower(), exported_lower)

        self.assertNotRegex(exported, r"\b(buy|sell)\b")
        self.assertNotRegex(exported, r"\b[a-z]+(?:_[a-z0-9]+)+\b")
        self.assertIn("研究摘要", exported)
        self.assertIn("基本面", exported)
        self.assertIn("事件", exported)
        self.assertIn("### Evidence", exported)
        self.assertIn("研究数据边界", exported)

    def test_delete_analysis_history_records_also_cleans_backtests(self) -> None:
        """删除历史记录时应一并清理关联回测结果。"""
        record_id = self._save_history("query_delete_001")

        with self.db.session_scope() as session:
            session.add(BacktestResult(
                analysis_history_id=record_id,
                code="600519",
                analysis_date=None,
                eval_window_days=10,
                engine_version="v1",
                eval_status="pending",
            ))

        deleted = self.db.delete_analysis_history_records([record_id])
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first())
            self.assertEqual(
                session.query(BacktestResult).filter(BacktestResult.analysis_history_id == record_id).count(),
                0,
            )

    def test_history_list_ignores_placeholder_stock_name_in_persisted_meta(self) -> None:
        """历史列表应回退到真实股票名，避免展示待确认股票占位文案。"""
        record_id = self._save_history("query_history_placeholder_name_001")

        with self.db.session_scope() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first()
            if row is None:
                self.fail("未找到测试历史记录")
            row.name = "Tesla"
            row.raw_result = json.dumps({
                "persisted_report": {
                    "meta": {
                        "stock_code": "TSLA",
                        "stock_name": "待确认股票",
                        "company_name": "待确认股票",
                    }
                }
            }, ensure_ascii=False)

        response = HistoryService(self.db).get_history_list(limit=20)
        self.assertEqual(response["total"], 1)
        self.assertEqual(response["items"][0]["stock_name"], "Tesla")
        self.assertEqual(response["items"][0]["company_name"], "Tesla")

    @patch("src.auth.is_auth_enabled", return_value=False)
    def test_delete_history_api_deletes_selected_records(self, mock_auth) -> None:
        """DELETE /api/v1/history should remove only the requested records."""
        if TestClient is None or create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        record_id_1 = self._save_history("query_delete_api_001")
        record_id_2 = self._save_history("query_delete_api_002")

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        client = TestClient(create_app(static_dir=static_dir))

        response = client.request(
            "DELETE",
            "/api/v1/history",
            json={"record_ids": [record_id_1]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("deleted"), 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_1).first())
            self.assertIsNotNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_2).first())

    @patch("src.auth.is_auth_enabled", return_value=False)
    def test_delete_history_api_delete_all_clears_all_history(self, mock_auth) -> None:
        """DELETE /api/v1/history with delete_all should clear the current user's history."""
        if TestClient is None or create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        record_id_1 = self._save_history("query_delete_all_api_001")
        record_id_2 = self._save_history("query_delete_all_api_002")

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        client = TestClient(create_app(static_dir=static_dir))

        response = client.request(
            "DELETE",
            "/api/v1/history",
            json={"record_ids": [record_id_1], "delete_all": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("deleted"), 2)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_1).first())
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_2).first())


if __name__ == "__main__":
    unittest.main()
