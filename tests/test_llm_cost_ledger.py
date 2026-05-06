# -*- coding: utf-8 -*-
"""Tests for LLM pricing policy and cost ledger foundation."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.storage import DatabaseManager, LLMCostLedger, ModelPricingPolicy


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class LlmCostLedgerServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()
        self.service = LlmCostLedgerService(db=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _seed_policy(self, **kwargs):
        payload = {
            "policy_key": "openai-gpt-4o-mini",
            "provider": "openai",
            "model": "openai/gpt-4o-mini",
            "pricing_unit": "per_1m_tokens",
            "input_price_per_1m": 0.15,
            "cached_input_price_per_1m": 0.075,
            "output_price_per_1m": 0.6,
            "currency": "USD",
            "effective_from": datetime(2025, 1, 1),
            "active": True,
            "metadata_json": "{}",
        }
        payload.update(kwargs)
        self.db.upsert_model_pricing_policy(**payload)

    def test_pricing_lookup_by_provider_model_and_effective_date(self) -> None:
        self._seed_policy()

        result = self.service.lookup_pricing_policy(
            provider="openai",
            model="openai/gpt-4o-mini",
            at=datetime(2025, 1, 2),
        )

        self.assertEqual(result.status, "ok")
        self.assertIsNotNone(result.policy)
        self.assertEqual(result.policy.model, "openai/gpt-4o-mini")

    def test_unknown_model_returns_pricing_unknown(self) -> None:
        result = self.service.calculate_cost(
            provider="unknown",
            model="missing-model",
            prompt_tokens=10,
            completion_tokens=20,
            route_family="analysis",
            call_type="analysis",
        )

        self.assertEqual(result.status, "pricing_unknown")
        self.assertEqual(result.total_cost_usd, 0)

    def test_regular_input_and_output_cost_calculation(self) -> None:
        self._seed_policy(input_price_per_1m=0.2, cached_input_price_per_1m=None, output_price_per_1m=0.8)

        result = self.service.calculate_cost(
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=2_000,
            route_family="analysis",
            call_type="analysis",
            at=datetime(2025, 1, 2),
        )

        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(float(result.input_cost_usd), 0.0002)
        self.assertAlmostEqual(float(result.output_cost_usd), 0.0016)
        self.assertAlmostEqual(float(result.total_cost_usd), 0.0018)

    def test_cached_input_cost_calculation(self) -> None:
        self._seed_policy(input_price_per_1m=0.2, cached_input_price_per_1m=0.05, output_price_per_1m=0.8)

        result = self.service.calculate_cost(
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            cached_input_tokens=400,
            completion_tokens=2_000,
            route_family="analysis",
            call_type="analysis",
            at=datetime(2025, 1, 2),
        )

        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(float(result.cached_input_cost_usd), 0.00002)
        self.assertAlmostEqual(float(result.input_cost_usd), 0.00012)

    def test_deepseek_cache_hit_and_miss_accounting(self) -> None:
        self.db.upsert_model_pricing_policy(
            policy_key="deepseek-v3",
            provider="deepseek",
            model="deepseek/deepseek-v3",
            pricing_unit="per_1m_tokens",
            input_price_per_1m=0.14,
            cached_input_price_per_1m=0.028,
            output_price_per_1m=0.28,
            currency="USD",
            effective_from=datetime(2025, 1, 1),
            active=True,
            metadata_json={},
        )

        result = self.service.calculate_cost(
            provider="deepseek",
            model="deepseek/deepseek-v3",
            prompt_tokens=1_000,
            cached_input_tokens=600,
            completion_tokens=900,
            route_family="analysis",
            call_type="analysis",
            at=datetime(2025, 1, 2),
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.cache_hit_tokens, 600)
        self.assertEqual(result.cache_miss_tokens, 400)
        self.assertAlmostEqual(float(result.total_cost_usd), 0.00014 * 0.4 + 0.000028 * 0.6 + 0.00028 * 0.9)

    def test_openai_cached_input_token_accounting(self) -> None:
        self._seed_policy()

        result = self.service.calculate_cost(
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=2_000,
            cached_input_tokens=750,
            completion_tokens=1_000,
            route_family="analysis",
            call_type="analysis",
            at=datetime(2025, 1, 2),
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.cache_hit_tokens, 750)
        self.assertEqual(result.cache_miss_tokens, 1_250)

    def test_ledger_write_includes_owner_and_route(self) -> None:
        self._seed_policy()

        record = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            cached_input_tokens=250,
        )

        self.assertEqual(record.status, "ok")
        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            self.assertEqual(row.owner_user_id, "user-a")
            self.assertEqual(row.route_family, "analysis")
            self.assertEqual(row.provider, "openai")
            self.assertEqual(row.model, "openai/gpt-4o-mini")

    def test_per_user_summary_differentiates_users(self) -> None:
        self._seed_policy()
        self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
        )
        self.service.reconcile_usage(
            owner_user_id="user-b",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=2_000,
            completion_tokens=500,
            total_tokens=2_500,
        )

        summary = self.service.get_summary(from_dt=datetime.now() - timedelta(days=1), to_dt=datetime.now() + timedelta(days=1))
        by_user = {row["owner_user_id"]: row for row in summary["by_user"]}

        self.assertEqual(by_user["user-a"]["total_tokens"], 2_000)
        self.assertEqual(by_user["user-b"]["total_tokens"], 2_500)

    def test_total_summary_aggregates_all_users(self) -> None:
        self._seed_policy()
        self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
        )
        self.service.reconcile_usage(
            owner_user_id="user-b",
            route_family="scanner_ai",
            call_type="scanner_ai",
            provider="deepseek",
            model="deepseek/deepseek-v3",
            prompt_tokens=500,
            completion_tokens=250,
            total_tokens=750,
        )

        summary = self.service.get_summary(from_dt=datetime.now() - timedelta(days=1), to_dt=datetime.now() + timedelta(days=1))

        self.assertEqual(summary["total"]["total_tokens"], 2_750)
        self.assertEqual(summary["total"]["total_cost_usd"], "0.00075")

    def test_provider_model_summary_aggregates_correctly(self) -> None:
        self._seed_policy()
        self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
        )
        self.service.reconcile_usage(
            owner_user_id="user-b",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=500,
            completion_tokens=250,
            total_tokens=750,
        )

        summary = self.service.get_summary(from_dt=datetime.now() - timedelta(days=1), to_dt=datetime.now() + timedelta(days=1))
        by_provider_model = {row["provider_model"]: row for row in summary["by_provider_model"]}

        self.assertEqual(by_provider_model["openai|openai/gpt-4o-mini"]["total_tokens"], 2_750)

    def test_metadata_sanitizer_drops_secret_like_keys(self) -> None:
        sanitized = self.service.sanitize_metadata(
            {
                "safe_label": "analysis",
                "api_key": "secret",
                "nested": {"token": "secret", "keep": "ok"},
                "provider_payload": {"cookie": "session"},
                "stack_trace": "Traceback should not persist",
            }
        )

        self.assertEqual(sanitized, {"safe_label": "analysis", "nested": {"keep": "ok"}})

    def test_no_raw_prompt_provider_payload_or_secrets_persisted(self) -> None:
        self._seed_policy()

        record = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            metadata={
                "prompt": "do not persist",
                "provider_payload": {"api_key": "secret"},
                "cookie": "session",
                "session_id": "raw-session",
            },
        )

        self.assertEqual(record.status, "ok")
        with self.db.session_scope() as session:
            row = session.query(LLMCostLedger).one()
            metadata = row.to_dict()["metadata"]
            self.assertEqual(metadata, {})

    def test_no_live_provider_or_llm_call_path_is_used(self) -> None:
        self._seed_policy()

        result = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
        )

        self.assertEqual(result.status, "ok")


if __name__ == "__main__":
    unittest.main()
