# -*- coding: utf-8 -*-
"""Focused tests for owner context propagation into LLM usage accounting."""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.agent.llm_adapter import LLMResponse
from src.agent.runner import run_agent_loop
from src.agent.tools.registry import ToolRegistry
from src.analyzer import GeminiAnalyzer
from src.services.scanner_ai_service import ScannerAiInterpretationService
from src.storage import DatabaseManager, LLMCostLedger, LLMUsage


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class LlmOwnerContextPropagationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_authenticated_analyzer_usage_writes_owner_user_id(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._call_litellm = MagicMock(
            return_value=(
                "synthetic response",
                "openai/gpt-4o-mini",
                {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                [],
            )
        )

        result = analyzer.generate_text_with_meta(
            "synthetic prompt",
            call_type="analysis",
            owner_user_id="user-id-123",
            route_family="analysis",
        )

        self.assertEqual(result["text"], "synthetic response")
        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            self.assertEqual(row.owner_user_id, "user-id-123")
            self.assertIsNone(row.guest_bucket_hash)
            self.assertEqual(row.route_family, "analysis")
            self.assertEqual(row.call_type, "analysis")

    def test_guest_analyzer_usage_writes_guest_bucket_hash(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._call_litellm = MagicMock(
            return_value=(
                "synthetic guest response",
                "gemini/gemini-2.5-flash",
                {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
                [],
            )
        )

        result = analyzer.generate_text_with_meta(
            "synthetic prompt",
            call_type="analysis",
            guest_bucket_hash="guest-hash-abc",
            route_family="guest_preview",
        )

        self.assertEqual(result["text"], "synthetic guest response")
        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            self.assertIsNone(row.owner_user_id)
            self.assertEqual(row.guest_bucket_hash, "guest-hash-abc")
            self.assertEqual(row.route_family, "guest_preview")

    def test_agent_runner_uses_user_id_not_username(self) -> None:
        adapter = MagicMock()
        adapter.call_with_tools.return_value = LLMResponse(
            content="final answer",
            provider="openai",
            model="openai/gpt-4o-mini",
            usage={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        )

        result = run_agent_loop(
            messages=[{"role": "user", "content": "hello"}],
            tool_registry=ToolRegistry(),
            llm_adapter=adapter,
            owner_user_id="actual-user-id",
            max_steps=1,
        )

        self.assertTrue(result.success)
        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            self.assertEqual(row.owner_user_id, "actual-user-id")
            self.assertNotEqual(row.owner_user_id, "alice")

    def test_legacy_global_usage_still_writes_null_owner(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._call_litellm = MagicMock(
            return_value=(
                "synthetic response",
                "deepseek/deepseek-v3",
                {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                [],
            )
        )

        analyzer.generate_text_with_meta("synthetic prompt", call_type="market_review")

        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            self.assertIsNone(row.owner_user_id)
            self.assertIsNone(row.guest_bucket_hash)

    def test_generate_text_with_meta_threads_owner_and_guest_identity_metadata(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._call_litellm = MagicMock(
            return_value=(
                "synthetic response",
                "openai/gpt-4o-mini",
                {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9},
                [],
            )
        )

        with patch("src.analyzer.persist_llm_usage") as mock_persist:
            analyzer.generate_text_with_meta(
                "same prompt",
                call_type="analysis",
                owner_user_id="user-owner-1",
                route_family="analysis",
            )
            analyzer.generate_text_with_meta(
                "same prompt",
                call_type="analysis",
                guest_bucket_hash="guest-bucket-1",
                route_family="guest_preview",
            )

        self.assertEqual(mock_persist.call_count, 2)
        owner_kwargs = mock_persist.call_args_list[0].kwargs
        guest_kwargs = mock_persist.call_args_list[1].kwargs

        self.assertEqual(
            owner_kwargs["request_hash"],
            owner_kwargs["metadata"]["llm_identity"]["attempt_hash"],
        )
        self.assertEqual(
            guest_kwargs["request_hash"],
            guest_kwargs["metadata"]["llm_identity"]["attempt_hash"],
        )
        self.assertEqual(owner_kwargs["metadata"]["llm_identity"]["owner_scope"], "owner")
        self.assertEqual(owner_kwargs["metadata"]["llm_identity"]["surface"], "analysis")
        self.assertEqual(guest_kwargs["metadata"]["llm_identity"]["owner_scope"], "guest")
        self.assertEqual(guest_kwargs["metadata"]["llm_identity"]["surface"], "guest_preview")
        self.assertNotEqual(
            owner_kwargs["metadata"]["llm_identity"]["logical_hash"],
            guest_kwargs["metadata"]["llm_identity"]["logical_hash"],
        )
        self.assertNotEqual(owner_kwargs["request_hash"], guest_kwargs["request_hash"])

    def test_generate_text_with_meta_separates_prompt_version_by_call_type(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._call_litellm = MagicMock(
            return_value=(
                "synthetic response",
                "openai/gpt-4o-mini",
                {"prompt_tokens": 6, "completion_tokens": 7, "total_tokens": 13},
                [],
            )
        )

        with patch("src.analyzer.persist_llm_usage") as mock_persist:
            analyzer.generate_text_with_meta(
                "same prompt",
                call_type="analysis",
                owner_user_id="user-owner-1",
                route_family="analysis",
            )
            analyzer.generate_text_with_meta(
                "same prompt",
                call_type="market_review",
                owner_user_id="user-owner-1",
                route_family="analysis",
            )

        self.assertEqual(mock_persist.call_count, 2)
        analysis_kwargs = mock_persist.call_args_list[0].kwargs
        market_kwargs = mock_persist.call_args_list[1].kwargs
        self.assertEqual(analysis_kwargs["metadata"]["llm_identity"]["version"], "analysis_v1")
        self.assertEqual(market_kwargs["metadata"]["llm_identity"]["version"], "market_review_v1")
        self.assertNotEqual(
            analysis_kwargs["metadata"]["llm_identity"]["logical_hash"],
            market_kwargs["metadata"]["llm_identity"]["logical_hash"],
        )
        self.assertNotEqual(analysis_kwargs["request_hash"], market_kwargs["request_hash"])

    def test_pricing_unknown_writes_safe_row_without_raw_prompt_or_payload(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._call_litellm = MagicMock(
            return_value=(
                "synthetic response",
                "unknown/missing-model",
                {"prompt_tokens": 9, "completion_tokens": 10, "total_tokens": 19},
                [],
            )
        )

        analyzer.generate_text_with_meta(
            "do not persist this prompt",
            call_type="analysis",
            owner_user_id="user-id-123",
        )

        with self.db.session_scope() as session:
            ledger = session.query(LLMCostLedger).one()
            usage = session.query(LLMUsage).one()
            self.assertEqual(ledger.status, "pricing_unknown")
            self.assertEqual(ledger.total_tokens, 19)
            metadata = ledger.to_dict()["metadata"]
            self.assertEqual(metadata["llm_identity"]["owner_scope"], "owner")
            self.assertEqual(metadata["llm_identity"]["surface"], "analysis")
            self.assertEqual(metadata["llm_identity"]["version"], "analysis_v1")
            self.assertEqual(metadata["llm_identity"]["attempt_hash"], ledger.request_hash)
            self.assertEqual(usage.total_tokens, 19)

    def test_ledger_observer_failure_does_not_change_llm_response(self) -> None:
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        analyzer._call_litellm = MagicMock(
            return_value=(
                "synthetic response survives",
                "openai/gpt-4o-mini",
                {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                [],
            )
        )

        with patch(
            "src.services.llm_cost_ledger_service.LlmCostLedgerService.reconcile_usage",
            side_effect=RuntimeError("ledger unavailable"),
        ):
            result = analyzer.generate_text_with_meta(
                "synthetic prompt",
                call_type="analysis",
                owner_user_id="user-id-123",
            )

        self.assertEqual(result["text"], "synthetic response survives")
        with self.db.session_scope() as session:
            self.assertEqual(session.query(LLMUsage).count(), 1)
            self.assertEqual(session.query(LLMCostLedger).count(), 0)

    def test_scanner_ai_passes_owner_context_to_analyzer_seam(self) -> None:
        captured: dict = {}

        class FakeAnalyzer:
            def is_available(self):
                return True

            def generate_text_with_meta(self, *args, **kwargs):
                captured.update(kwargs)
                return {
                    "text": (
                        '{"summary":"s","opportunity_type":"其他",'
                        '"risk_interpretation":"r","watch_plan":"w"}'
                    ),
                    "model": "openai/gpt-4o-mini",
                    "provider": "openai",
                    "usage": {},
                    "attempt_trace": [],
                }

        service = ScannerAiInterpretationService(
            config=SimpleNamespace(scanner_ai_enabled=True, scanner_ai_top_n=1),
            analyzer_factory=lambda: FakeAnalyzer(),
            owner_user_id="scanner-user-id",
        )
        candidates, _diagnostics = service.interpret_shortlist(
            profile=SimpleNamespace(market="cn", key="cn_a_preopen_v1"),
            candidates=[{"symbol": "600519", "rank": 1, "score": 90, "diagnostics": {}}],
        )

        self.assertEqual(candidates[0]["ai_interpretation"]["status"], "generated")
        self.assertEqual(captured["owner_user_id"], "scanner-user-id")
        self.assertEqual(captured["route_family"], "scanner_ai")


if __name__ == "__main__":
    unittest.main()
