# -*- coding: utf-8 -*-
"""Unit tests for LLM usage tracking (storage + analyzer helper)."""

import sys
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage import DatabaseManager, LLMCostLedger, LLMUsage, persist_llm_usage


def _fresh_db() -> DatabaseManager:
    """Return a DatabaseManager backed by a fresh in-memory SQLite database."""
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    return db


class TestRecordLLMUsage(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_record_single_row(self):
        self.db.record_llm_usage(
            call_type="analysis",
            model="gemini/gemini-2.5-flash",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            stock_code="600519",
        )
        with self.db.session_scope() as session:
            rows = session.query(LLMUsage).all()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.call_type, "analysis")
            self.assertEqual(row.model, "gemini/gemini-2.5-flash")
            self.assertEqual(row.stock_code, "600519")
            self.assertEqual(row.prompt_tokens, 100)
            self.assertEqual(row.completion_tokens, 200)
            self.assertEqual(row.total_tokens, 300)

    def test_record_without_stock_code(self):
        self.db.record_llm_usage(
            call_type="market_review",
            model="openai/gpt-4o",
            prompt_tokens=50,
            completion_tokens=150,
            total_tokens=200,
        )
        with self.db.session_scope() as session:
            rows = session.query(LLMUsage).all()
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0].stock_code)

    def test_record_multiple_rows(self):
        for i in range(5):
            self.db.record_llm_usage(
                call_type="agent",
                model="gemini/gemini-2.5-flash",
                prompt_tokens=10 * i,
                completion_tokens=20 * i,
                total_tokens=30 * i,
            )
        with self.db.session_scope() as session:
            count = session.query(LLMUsage).count()
        self.assertEqual(count, 5)


class TestGetLLMUsageSummary(unittest.TestCase):
    def setUp(self):
        self.db = _fresh_db()
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        # 3 analysis calls today
        for _ in range(3):
            row = LLMUsage(
                call_type="analysis",
                model="gemini/gemini-2.5-flash",
                prompt_tokens=100,
                completion_tokens=200,
                total_tokens=300,
                called_at=now,
            )
            with self.db.session_scope() as session:
                session.add(row)

        # 2 agent calls today
        for _ in range(2):
            row = LLMUsage(
                call_type="agent",
                model="openai/gpt-4o",
                prompt_tokens=50,
                completion_tokens=100,
                total_tokens=150,
                called_at=now,
            )
            with self.db.session_scope() as session:
                session.add(row)

        # 1 old call that should be excluded
        old_row = LLMUsage(
            call_type="analysis",
            model="gemini/gemini-2.5-flash",
            prompt_tokens=999,
            completion_tokens=999,
            total_tokens=999,
            called_at=yesterday,
        )
        with self.db.session_scope() as session:
            session.add(old_row)

    def tearDown(self):
        DatabaseManager.reset_instance()

    def _today_range(self):
        now = datetime.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now

    def test_total_calls_and_tokens(self):
        from_dt, to_dt = self._today_range()
        result = self.db.get_llm_usage_summary(from_dt, to_dt)
        self.assertEqual(result["total_calls"], 5)
        # 3*300 + 2*150 = 900 + 300 = 1200
        self.assertEqual(result["total_tokens"], 1200)

    def test_by_call_type(self):
        from_dt, to_dt = self._today_range()
        result = self.db.get_llm_usage_summary(from_dt, to_dt)
        by_type = {r["call_type"]: r for r in result["by_call_type"]}
        self.assertIn("analysis", by_type)
        self.assertIn("agent", by_type)
        self.assertEqual(by_type["analysis"]["calls"], 3)
        self.assertEqual(by_type["analysis"]["total_tokens"], 900)
        self.assertEqual(by_type["agent"]["calls"], 2)
        self.assertEqual(by_type["agent"]["total_tokens"], 300)

    def test_by_model(self):
        from_dt, to_dt = self._today_range()
        result = self.db.get_llm_usage_summary(from_dt, to_dt)
        by_model = {r["model"]: r for r in result["by_model"]}
        self.assertEqual(by_model["gemini/gemini-2.5-flash"]["calls"], 3)
        self.assertEqual(by_model["openai/gpt-4o"]["calls"], 2)

    def test_empty_range_returns_zeros(self):
        future = datetime(2099, 1, 1)
        result = self.db.get_llm_usage_summary(future, future)
        self.assertEqual(result["total_calls"], 0)
        self.assertEqual(result["total_tokens"], 0)
        self.assertEqual(result["by_call_type"], [])
        self.assertEqual(result["by_model"], [])


class TestPersistUsageHelper(unittest.TestCase):
    """Test that _persist_usage swallows exceptions and writes correctly."""

    def setUp(self):
        self.db = _fresh_db()

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_persist_usage_writes_row(self):
        self.db.upsert_model_pricing_policy(
            policy_key="gemini-flash",
            provider="gemini",
            model="gemini/gemini-2.5-flash",
            pricing_unit="per_1m_tokens",
            input_price_per_1m=0.3,
            output_price_per_1m=2.5,
            effective_from=datetime(2025, 1, 1),
            active=True,
            metadata_json={},
        )
        persist_llm_usage(
            {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "gemini/gemini-2.5-flash",
            call_type="analysis",
            stock_code="000001",
        )
        with self.db.session_scope() as session:
            rows = session.query(LLMUsage).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].total_tokens, 30)
            ledger_rows = session.query(LLMCostLedger).all()
            self.assertEqual(len(ledger_rows), 1)
            self.assertEqual(ledger_rows[0].total_tokens, 30)
            self.assertEqual(ledger_rows[0].status, "ok")

    def test_persist_usage_preserves_owner_when_provided(self):
        persist_llm_usage(
            {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            "openai/gpt-4o-mini",
            call_type="agent",
            owner_user_id="user-owner",
            route_family="agent",
        )

        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            self.assertEqual(row.owner_user_id, "user-owner")
            self.assertEqual(row.route_family, "agent")
            self.assertEqual(row.call_type, "agent")

    def test_persist_usage_allows_null_owner_global_usage(self):
        persist_llm_usage(
            {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
            "deepseek/deepseek-v3",
            call_type="market_review",
        )

        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            self.assertIsNone(row.owner_user_id)
            self.assertEqual(row.provider, "deepseek")
            self.assertEqual(row.status, "pricing_unknown")

    def test_persist_usage_pricing_unknown_does_not_crash(self):
        persist_llm_usage(
            {"prompt_tokens": 5, "completion_tokens": 9, "total_tokens": 14},
            "unknown/missing-model",
            call_type="analysis",
        )

        with self.db.session_scope() as session:
            usage_rows = session.query(LLMUsage).all()
            ledger_row = session.query(LLMCostLedger).one()
            self.assertEqual(len(usage_rows), 1)
            self.assertEqual(ledger_row.status, "pricing_unknown")
            self.assertEqual(ledger_row.total_tokens, 14)

    def test_persist_usage_keeps_raw_usage_append_only_while_deduping_cost_ledger_identity(self):
        self.db.upsert_model_pricing_policy(
            policy_key="openai-gpt-4o-mini",
            provider="openai",
            model="openai/gpt-4o-mini",
            pricing_unit="per_1m_tokens",
            input_price_per_1m=0.15,
            output_price_per_1m=0.6,
            effective_from=datetime(2025, 1, 1),
            active=True,
            metadata_json={},
        )

        for _ in range(2):
            persist_llm_usage(
                {"prompt_tokens": 5, "completion_tokens": 9, "total_tokens": 14},
                "openai/gpt-4o-mini",
                call_type="analysis",
                owner_user_id="user-owner",
                route_family="analysis",
                request_hash="persisted-billable-attempt",
                metadata={"llm_identity": {"attempt_hash": "persisted-billable-attempt", "retry_index": 0}},
            )

        with self.db.session_scope() as session:
            self.assertEqual(session.query(LLMUsage).count(), 2)
            ledger_rows = session.query(LLMCostLedger).all()
            self.assertEqual(len(ledger_rows), 1)
            self.assertEqual(ledger_rows[0].request_hash, "persisted-billable-attempt")
            self.assertEqual(ledger_rows[0].total_tokens, 14)

    def test_persist_usage_ledger_failure_does_not_change_success_result(self):
        with patch(
            "src.services.llm_cost_ledger_service.LlmCostLedgerService.reconcile_usage",
            side_effect=RuntimeError("ledger unavailable"),
        ):
            persist_llm_usage(
                {"prompt_tokens": 8, "completion_tokens": 12, "total_tokens": 20},
                "openai/gpt-4o-mini",
                call_type="analysis",
            )

        with self.db.session_scope() as session:
            self.assertEqual(session.query(LLMUsage).count(), 1)
            self.assertEqual(session.query(LLMCostLedger).count(), 0)

    def test_persist_usage_does_not_store_raw_prompt_payload_or_secrets(self):
        persist_llm_usage(
            {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            "openai/gpt-4o-mini",
            call_type="analysis",
            metadata={
                "prompt": "do not persist",
                "raw_provider_payload": {"token": "secret"},
                "api_key": "secret",
                "cookie": "cookie-value",
                "session_id": "raw-session",
                "stack_trace": "Traceback should not persist",
                "safe_reason": "synthetic_test",
            },
        )

        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            metadata = row.to_dict()["metadata"]
            self.assertEqual(metadata, {"safe_reason": "synthetic_test"})

    def test_persist_usage_handles_empty_usage(self):
        # Should not raise even with an empty dict
        persist_llm_usage({}, "unknown", call_type="agent")
        with self.db.session_scope() as session:
            rows = session.query(LLMUsage).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].total_tokens, 0)
            ledger_rows = session.query(LLMCostLedger).all()
            self.assertEqual(len(ledger_rows), 1)
            self.assertEqual(ledger_rows[0].total_tokens, 0)

    def test_persist_usage_never_raises(self):
        # Pass a deliberately bad db state by resetting the singleton
        DatabaseManager.reset_instance()
        # Should silently swallow the error, not raise
        try:
            persist_llm_usage({"total_tokens": 5}, "m", call_type="analysis")
        except Exception as exc:
            self.fail(f"persist_llm_usage raised unexpectedly: {exc}")


if __name__ == "__main__":
    unittest.main()
