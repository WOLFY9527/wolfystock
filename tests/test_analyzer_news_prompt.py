# -*- coding: utf-8 -*-
"""Tests for analyzer news prompt hard constraints (Issue #697)."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult, GeminiAnalyzer


class AnalyzerNewsPromptTestCase(unittest.TestCase):
    def test_prompt_contains_time_constraints(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "贵州茅台",
            "date": "2026-03-16",
            "today": {},
            "fundamental_context": {
                "earnings": {
                    "data": {
                        "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                        "dividend": {"ttm_cash_dividend_per_share": 1.2, "ttm_dividend_yield_pct": 2.4},
                    }
                }
            },
        }
        fake_cfg = SimpleNamespace(
            news_max_age_days=30,
            news_strategy_profile="medium",  # 7 days
        )
        with patch("src.analyzer.get_config", return_value=fake_cfg):
            prompt = analyzer._format_prompt(context, "贵州茅台", news_context="news")

        self.assertIn("近7日的新闻搜索结果", prompt)
        self.assertIn("每一条都必须带具体日期（YYYY-MM-DD）", prompt)
        self.assertIn("超出近7日窗口的新闻一律忽略", prompt)
        self.assertIn("时间未知、无法确定发布日期的新闻一律忽略", prompt)
        self.assertIn("财报与分红（价值投资口径）", prompt)
        self.assertIn("禁止编造", prompt)

    def test_prompt_prefers_context_news_window_days(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "贵州茅台",
            "date": "2026-03-16",
            "today": {},
            "news_window_days": 1,
        }
        fake_cfg = SimpleNamespace(
            news_max_age_days=30,
            news_strategy_profile="long",  # 30 days if fallback is used
        )
        with patch("src.analyzer.get_config", return_value=fake_cfg):
            prompt = analyzer._format_prompt(context, "贵州茅台", news_context="news")

        self.assertIn("近1日的新闻搜索结果", prompt)
        self.assertIn("超出近1日窗口的新闻一律忽略", prompt)

    def test_prompt_excludes_verbose_provider_diagnostics_but_keeps_critical_quality_facts(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "ORCL",
            "stock_name": "Oracle",
            "date": "2026-05-15",
            "today": {},
            "data_quality": {
                "price_history_status": "partial",
                "technicals_status": "partial",
                "fundamentals_status": "partial",
                "earnings_status": "partial",
                "sentiment_status": "skipped",
                "missing_fields": ["technicals.ma20", "fundamentals.revenue"],
                "warnings": [
                    "provider_failure: optional_news_timeout",
                    "volume_ratio_unavailable",
                ],
                "provider_notes": {
                    "market_data": "quote_fallback",
                    "diagnostics": {
                        "api_key": "super-secret-token",
                        "request_url": "https://secret.example/api",
                        "traceback": "stack trace should never reach prompt",
                    },
                },
            },
            "data_quality_report": {
                "dataQualityTier": "degraded",
                "requiredAvailable": True,
                "importantMissing": ["quote.previous_close"],
                "staleSources": ["quote"],
                "providerTimeouts": ["news"],
                "providerCooldowns": [],
                "confidenceCap": 72,
                "reasonCodes": ["stale_required_source", "partial_optional_enrichment"],
                "freshness": {"marketTimestamp": "2026-05-15T13:30:00Z"},
            },
        }
        fake_cfg = SimpleNamespace(
            news_max_age_days=30,
            news_strategy_profile="short",
        )
        with patch("src.analyzer.get_config", return_value=fake_cfg):
            prompt = analyzer._format_prompt(context, "Oracle", news_context=None)

        self.assertIn("quote.previous_close", prompt)
        self.assertIn("stale_required_source", prompt)
        self.assertIn("marketTimestamp", prompt)
        self.assertIn("quote_fallback", prompt)
        self.assertNotIn("provider_notes", prompt)
        self.assertNotIn("diagnostics", prompt)
        self.assertNotIn("super-secret-token", prompt)
        self.assertNotIn("stack trace should never reach prompt", prompt)
        self.assertNotIn("https://secret.example/api", prompt)

    def test_analyze_does_not_log_prompt_preview_at_info_by_default(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._router = None
        analyzer._litellm_available = True
        analyzer._fill_alpha_vantage_from_context = MagicMock()
        analyzer._build_market_snapshot = MagicMock(return_value={})
        analyzer._check_content_integrity = MagicMock(return_value=(True, []))

        fake_config = SimpleNamespace(
            report_language="zh",
            gemini_request_delay=0.0,
            litellm_model="gemini/gemini-2.5-flash",
            llm_temperature=0.7,
            report_integrity_enabled=False,
            report_integrity_retry=0,
            home_quick_analysis_enabled=True,
            home_quick_analysis_temperature=0.2,
            home_quick_analysis_max_output_tokens=4096,
            home_analysis_log_full_prompt=False,
            debug=False,
        )
        parsed = AnalysisResult(
            code="ORCL",
            name="Oracle",
            sentiment_score=60,
            trend_prediction="震荡",
            operation_advice="持有",
            analysis_summary="完成",
            success=True,
        )

        with patch("src.analyzer.get_config", return_value=fake_config), \
             patch("src.analyzer.get_effective_litellm_model", return_value="gemini/gemini-2.5-flash"), \
             patch.object(analyzer, "_get_analysis_system_prompt", return_value="system"), \
             patch.object(analyzer, "_format_prompt", return_value="SECRET_PROMPT_CONTENT"), \
             patch.object(
                 analyzer,
                 "_call_litellm",
                 return_value=("{}", "gemini/gemini-2.5-flash", {"total_tokens": 12}, []),
             ), \
             patch.object(analyzer, "_parse_response", return_value=parsed), \
             patch("src.analyzer.persist_llm_usage"), \
             patch("src.analyzer.emit_llm_event"):
            with self.assertLogs("src.analyzer", level="INFO") as captured:
                result = analyzer.analyze({"code": "ORCL", "stock_name": "Oracle"}, news_context=None)

        self.assertTrue(result.success)
        joined = "\n".join(captured.output)
        self.assertIn("Prompt 长度", joined)
        self.assertNotIn("LLM Prompt 预览", joined)
        self.assertNotIn("SECRET_PROMPT_CONTENT", joined)


if __name__ == "__main__":
    unittest.main()
