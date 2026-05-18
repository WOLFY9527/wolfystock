# -*- coding: utf-8 -*-
"""
===================================
Report Engine - Content integrity tests
===================================

Tests for check_content_integrity, apply_placeholder_fill, and retry/placeholder behavior.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult, GeminiAnalyzer, check_content_integrity, apply_placeholder_fill
from src.services.llm_identity_semantics import build_llm_identity_contract


class TestCheckContentIntegrity(unittest.TestCase):
    """Content integrity check tests."""

    def test_pass_when_all_required_present(self) -> None:
        """Integrity passes when all mandatory fields are present."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="持有",
            analysis_summary="稳健",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "持有观望"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110元"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_fail_when_analysis_summary_empty(self) -> None:
        """Integrity fails when analysis_summary is empty."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="持有",
            analysis_summary="",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "持有"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("analysis_summary", missing)

    def test_fail_when_one_sentence_missing(self) -> None:
        """Integrity fails when core_conclusion.one_sentence is missing."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="持有",
            analysis_summary="稳健",
            decision_type="hold",
            dashboard={
                "core_conclusion": {},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.core_conclusion.one_sentence", missing)

    def test_fail_when_stop_loss_missing_for_buy(self) -> None:
        """Integrity fails when stop_loss missing and decision_type is buy."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="买入",
            analysis_summary="稳健",
            decision_type="buy",
            dashboard={
                "core_conclusion": {"one_sentence": "可买入"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.battle_plan.sniper_points.stop_loss", missing)

    def test_pass_when_stop_loss_missing_for_sell(self) -> None:
        """Integrity passes when stop_loss missing and decision_type is sell."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看空",
            sentiment_score=35,
            operation_advice="卖出",
            analysis_summary="弱势",
            decision_type="sell",
            dashboard={
                "core_conclusion": {"one_sentence": "建议卖出"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_fail_when_risk_alerts_missing(self) -> None:
        """Integrity fails when intelligence.risk_alerts field is missing."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="持有",
            analysis_summary="稳健",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "持有"},
                "intelligence": {},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.intelligence.risk_alerts", missing)


class TestApplyPlaceholderFill(unittest.TestCase):
    """Placeholder fill tests."""

    def test_fills_missing_analysis_summary(self) -> None:
        """Placeholder fills analysis_summary when missing."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="持有",
            analysis_summary="",
            decision_type="hold",
            dashboard={},
        )
        apply_placeholder_fill(result, ["analysis_summary"])
        self.assertEqual(result.analysis_summary, "待补充")

    def test_fills_missing_stop_loss(self) -> None:
        """Placeholder fills stop_loss when missing."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="买入",
            analysis_summary="稳健",
            decision_type="buy",
            dashboard={"battle_plan": {"sniper_points": {}}},
        )
        apply_placeholder_fill(result, ["dashboard.battle_plan.sniper_points.stop_loss"])
        self.assertEqual(
            result.dashboard["battle_plan"]["sniper_points"]["stop_loss"],
            "待补充",
        )

    def test_fills_risk_alerts_empty_list(self) -> None:
        """Placeholder fills risk_alerts with empty list when missing."""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="看多",
            sentiment_score=70,
            operation_advice="持有",
            analysis_summary="稳健",
            decision_type="hold",
            dashboard={"intelligence": {}},
        )
        apply_placeholder_fill(result, ["dashboard.intelligence.risk_alerts"])
        self.assertEqual(result.dashboard["intelligence"]["risk_alerts"], [])


class TestIntegrityRetryPrompt(unittest.TestCase):
    """Retry prompt construction tests."""

    def test_retry_prompt_includes_previous_response(self) -> None:
        """Retry prompt should carry previous response so补全是增量的。"""
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()
        prompt = analyzer._build_integrity_retry_prompt(
            "原始提示",
            '{"analysis_summary": "已有内容"}',
            ["dashboard.core_conclusion.one_sentence"],
        )
        self.assertIn("原始提示", prompt)
        self.assertIn('{"analysis_summary": "已有内容"}', prompt)
        self.assertIn("dashboard.core_conclusion.one_sentence", prompt)

    def test_analyze_emits_integrity_retry_event(self) -> None:
        """Integrity retry should be observable without changing retry behavior."""
        cfg = MagicMock()
        cfg.report_language = "zh"
        cfg.gemini_request_delay = 0
        cfg.report_integrity_enabled = True
        cfg.report_integrity_retry = 1
        cfg.litellm_model = "gemini/gemini-2.5-flash"
        cfg.llm_temperature = 0.7

        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._router = None
        analyzer._litellm_available = True

        incomplete = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="震荡",
            sentiment_score=50,
            operation_advice="持有",
            analysis_summary="",
            decision_type="hold",
            dashboard={},
        )
        complete = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="震荡",
            sentiment_score=50,
            operation_advice="持有",
            analysis_summary="完整分析",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "持有观望"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "100"}},
            },
        )

        with patch("src.analyzer.get_config", return_value=cfg), \
             patch.object(analyzer, "_format_prompt", return_value="prompt"), \
             patch.object(
                 analyzer,
                 "_call_litellm",
                 side_effect=[
                     ("{}", "gemini/gemini-2.5-flash", {}, []),
                     ("{}", "gemini/gemini-2.5-flash", {}, []),
                 ],
             ) as mock_call, \
             patch.object(analyzer, "_parse_response", side_effect=[incomplete, complete]), \
             patch.object(analyzer, "_build_integrity_retry_prompt", return_value="retry prompt"), \
             patch.object(analyzer, "_fill_alpha_vantage_from_context", return_value=None), \
             patch.object(analyzer, "_build_market_snapshot", return_value={}), \
             patch("src.analyzer.persist_llm_usage"), \
             patch("src.analyzer.emit_llm_event") as mock_event:
            result = analyzer.analyze({"code": "600519", "stock_name": "贵州茅台"})

        self.assertEqual(result.analysis_summary, "完整分析")
        self.assertEqual(mock_call.call_count, 2)
        emitted = [call.args[0] for call in mock_event.call_args_list]
        self.assertIn("llm_integrity_retry", emitted)

    def test_analyze_threads_distinct_attempt_hashes_across_integrity_retry(self) -> None:
        cfg = MagicMock()
        cfg.report_language = "zh"
        cfg.gemini_request_delay = 0
        cfg.report_integrity_enabled = True
        cfg.report_integrity_retry = 1
        cfg.litellm_model = "gemini/gemini-2.5-flash"
        cfg.llm_temperature = 0.7
        cfg.home_quick_analysis_enabled = True
        cfg.home_quick_analysis_temperature = 0.2
        cfg.home_quick_analysis_max_output_tokens = 4096
        cfg.home_analysis_log_full_prompt = False
        cfg.debug = False

        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._router = None
        analyzer._litellm_available = True

        incomplete = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="震荡",
            sentiment_score=50,
            operation_advice="持有",
            analysis_summary="",
            decision_type="hold",
            dashboard={},
        )
        complete = AnalysisResult(
            code="600519",
            name="贵州茅台",
            trend_prediction="震荡",
            sentiment_score=50,
            operation_advice="持有",
            analysis_summary="完整分析",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "持有观望"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "100"}},
            },
        )
        identities = []

        def capture_identity(**kwargs):
            identity = build_llm_identity_contract(**kwargs)
            identities.append(identity)
            return identity

        with patch("src.analyzer.get_config", return_value=cfg), \
             patch("src.analyzer.get_effective_litellm_model", return_value="gemini/gemini-2.5-flash"), \
             patch.object(analyzer, "_get_analysis_system_prompt", return_value="system"), \
             patch.object(analyzer, "_format_prompt", return_value="base prompt"), \
             patch.object(
                 analyzer,
                 "_call_litellm",
                 side_effect=[
                     ("{}", "gemini/gemini-2.5-flash", {"total_tokens": 11}, []),
                     ("{}", "gemini/gemini-2.5-flash", {"total_tokens": 12}, []),
                 ],
             ), \
             patch.object(analyzer, "_parse_response", side_effect=[incomplete, complete]), \
             patch.object(analyzer, "_build_integrity_retry_prompt", return_value="retry prompt"), \
             patch.object(analyzer, "_fill_alpha_vantage_from_context", return_value=None), \
             patch.object(analyzer, "_build_market_snapshot", return_value={}), \
             patch("src.analyzer.build_llm_identity_contract", side_effect=capture_identity) as mock_identity, \
             patch("src.analyzer.persist_llm_usage") as mock_persist, \
             patch("src.analyzer.emit_llm_event"):
            result = analyzer.analyze(
                {"code": "600519", "stock_name": "贵州茅台"},
                owner_user_id="owner-1",
                route_family="analysis",
            )

        self.assertEqual(result.analysis_summary, "完整分析")
        self.assertEqual(mock_identity.call_count, 2)
        self.assertEqual(
            [call.kwargs["retry_attempt_index"] for call in mock_identity.call_args_list],
            [0, 1],
        )
        self.assertEqual(mock_identity.call_args_list[0].kwargs["prompt_text"], "base prompt")
        self.assertEqual(mock_identity.call_args_list[1].kwargs["prompt_text"], "base prompt")
        self.assertEqual(mock_identity.call_args_list[0].kwargs["surface"], "analysis")
        self.assertEqual(len(identities), 2)
        self.assertEqual(identities[0].logical_request_hash, identities[1].logical_request_hash)
        self.assertNotEqual(identities[0].billable_attempt_hash, identities[1].billable_attempt_hash)
        persisted = mock_persist.call_args.kwargs
        self.assertEqual(persisted["request_hash"], identities[1].billable_attempt_hash)
        self.assertEqual(
            persisted["metadata"]["llm_identity"]["logical_hash"],
            identities[1].logical_request_hash,
        )
        self.assertEqual(
            persisted["metadata"]["llm_identity"]["attempt_hash"],
            identities[1].billable_attempt_hash,
        )
