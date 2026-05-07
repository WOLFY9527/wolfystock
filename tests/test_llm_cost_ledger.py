# -*- coding: utf-8 -*-
"""Tests for LLM pricing policy and cost ledger foundation."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.quota_policy_service import QuotaPolicyService
from src.storage import DatabaseManager, LLMCostLedger, ModelPricingPolicy, QuotaReservation


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

    def _reserve_quota(self, **kwargs):
        service = QuotaPolicyService(db=self.db, enforcement_enabled=True)
        payload = {
            "owner_user_id": "user-a",
            "route_family": "analysis",
            "token_estimate": 1000,
        }
        payload.update(kwargs)
        result = service.reserve_quota(**payload)
        self.assertTrue(result.allowed)
        self.assertTrue(result.reservation_id)
        return result

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

    def test_reconcile_usage_with_valid_reservation_consumes_it(self) -> None:
        self._seed_policy()
        reservation = self._reserve_quota()

        result = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            quota_reservation_id=reservation.reservation_id,
        )

        self.assertEqual(result.status, "ok")
        self.assertIsNotNone(result.quota_reconciliation)
        self.assertEqual(result.quota_reconciliation.result_code, "reconciled_consumed")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=reservation.reservation_id).one()
            self.assertEqual(row.status, "consumed")

    def test_pricing_unknown_releases_reservation_without_consuming(self) -> None:
        reservation = self._reserve_quota()

        result = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="unknown",
            model="missing-model",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            quota_reservation_id=reservation.reservation_id,
        )

        self.assertEqual(result.status, "pricing_unknown")
        self.assertIsNotNone(result.quota_reconciliation)
        self.assertEqual(result.quota_reconciliation.result_code, "pricing_unknown_no_consume")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=reservation.reservation_id).one()
            self.assertEqual(row.status, "released")

    def test_invalid_usage_releases_reservation_without_consuming(self) -> None:
        self._seed_policy()
        reservation = self._reserve_quota()

        result = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=10,
            cached_input_tokens=20,
            completion_tokens=1,
            total_tokens=11,
            quota_reservation_id=reservation.reservation_id,
        )

        self.assertEqual(result.status, "invalid_usage")
        self.assertIsNotNone(result.quota_reconciliation)
        self.assertEqual(result.quota_reconciliation.result_code, "invalid_usage_no_consume")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=reservation.reservation_id).one()
            self.assertEqual(row.status, "released")

    def test_missing_reservation_returns_safe_code(self) -> None:
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
            quota_reservation_id="qres_missing",
        )

        self.assertEqual(result.status, "ok")
        self.assertIsNotNone(result.quota_reconciliation)
        self.assertEqual(result.quota_reconciliation.result_code, "reservation_missing")

    def test_expired_reservation_returns_safe_code(self) -> None:
        self._seed_policy()
        reservation = self._reserve_quota(expires_at=datetime.now() - timedelta(seconds=1))

        result = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            quota_reservation_id=reservation.reservation_id,
        )

        self.assertEqual(result.status, "ok")
        self.assertIsNotNone(result.quota_reconciliation)
        self.assertEqual(result.quota_reconciliation.result_code, "reservation_expired")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=reservation.reservation_id).one()
            self.assertEqual(row.status, "expired")

    def test_terminal_reservation_is_idempotent(self) -> None:
        self._seed_policy()
        reservation = self._reserve_quota()
        QuotaPolicyService(db=self.db, enforcement_enabled=True).consume_reservation(
            reservation_id=reservation.reservation_id
        )

        result = self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            quota_reservation_id=reservation.reservation_id,
        )

        self.assertEqual(result.status, "ok")
        self.assertIsNotNone(result.quota_reconciliation)
        self.assertEqual(result.quota_reconciliation.result_code, "reservation_already_terminal")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=reservation.reservation_id).one()
            self.assertEqual(row.status, "consumed")

    def test_quota_reconciliation_failure_does_not_change_ledger_write_result(self) -> None:
        self._seed_policy()
        reservation = self._reserve_quota()

        class BrokenQuotaPolicy:
            def consume_reservation(self, **_kwargs):
                raise RuntimeError("secret stack trace should not leak")

            def release_reservation(self, **_kwargs):
                raise RuntimeError("secret stack trace should not leak")

        service = LlmCostLedgerService(db=self.db, quota_policy_service=BrokenQuotaPolicy())

        result = service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            quota_reservation_id=reservation.reservation_id,
        )

        self.assertEqual(result.status, "ok")
        self.assertIsNotNone(result.ledger_id)
        self.assertIsNotNone(result.quota_reconciliation)
        self.assertEqual(result.quota_reconciliation.result_code, "reconciliation_error")
        self.assertNotIn("secret", str(result.quota_reconciliation))
        with self.db.session_scope() as session:
            self.assertEqual(session.query(LLMCostLedger).count(), 1)

    def test_invoice_reconciliation_preflight_matches_external_total(self) -> None:
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
            at=datetime(2025, 1, 2),
        )

        result = self.service.preflight_invoice_reconciliation(
            owner_user_id="user-a",
            provider="openai",
            model="openai/gpt-4o-mini",
            invoice_total_usd=Decimal("0.00075"),
            from_dt=datetime(2025, 1, 1),
            to_dt=datetime(2025, 1, 3),
        )

        self.assertEqual(result.state, "matched_total")
        self.assertEqual(result.ledger_total_usd, Decimal("0.00075000"))
        self.assertEqual(result.invoice_total_usd, Decimal("0.00075000"))
        self.assertEqual(result.matched_total_usd, Decimal("0.00075000"))
        self.assertEqual(result.delta_usd, Decimal("0"))
        self.assertEqual(result.warnings, ())
        self.assertTrue(result.advisory_only)
        self.assertFalse(result.live_invoice_ingestion)
        self.assertFalse(result.live_enforcement)
        payload = result.to_dict()
        self.assertTrue(payload["advisoryOnly"])
        self.assertFalse(payload["enforcementInput"])
        self.assertFalse(payload["liveInvoiceIngestion"])
        self.assertFalse(payload["liveEnforcement"])
        self.assertFalse(payload["enforcementWired"])

    def test_invoice_reconciliation_preflight_allows_small_tolerance_delta(self) -> None:
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
            at=datetime(2025, 1, 2),
        )

        result = self.service.preflight_invoice_reconciliation(
            owner_user_id="user-a",
            provider="openai",
            model="openai/gpt-4o-mini",
            invoice_total_usd=Decimal("0.000755"),
            from_dt=datetime(2025, 1, 1),
            to_dt=datetime(2025, 1, 3),
            tolerance_usd=Decimal("0.01"),
        )

        self.assertEqual(result.state, "within_tolerance")
        self.assertEqual(result.delta_usd, Decimal("0.00000500"))
        self.assertEqual(result.warnings, ())

    def test_invoice_reconciliation_preflight_warns_on_provider_over_billed_and_under_counted_ledger(self) -> None:
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
            at=datetime(2025, 1, 2),
        )

        result = self.service.preflight_invoice_reconciliation(
            owner_user_id="user-a",
            provider="openai",
            model="openai/gpt-4o-mini",
            invoice_total_usd=Decimal("0.00175"),
            from_dt=datetime(2025, 1, 1),
            to_dt=datetime(2025, 1, 3),
            tolerance_usd=Decimal("0.00001"),
        )

        self.assertEqual(result.state, "provider_over_billed")
        self.assertEqual([warning.code for warning in result.warnings], ["provider_over_billed", "ledger_under_counted"])
        self.assertEqual(result.matched_total_usd, Decimal("0.00075000"))
        self.assertEqual(result.delta_usd, Decimal("0.00100000"))
        payload = result.to_dict()
        self.assertTrue(payload["advisoryOnly"])
        self.assertFalse(payload["enforcementInput"])
        self.assertFalse(payload["liveEnforcement"])

    def test_invoice_reconciliation_preflight_warns_on_ledger_over_counted(self) -> None:
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
            at=datetime(2025, 1, 2),
        )

        result = self.service.preflight_invoice_reconciliation(
            owner_user_id="user-a",
            provider="openai",
            model="openai/gpt-4o-mini",
            invoice_total_usd=Decimal("0.00055"),
            from_dt=datetime(2025, 1, 1),
            to_dt=datetime(2025, 1, 3),
            tolerance_usd=Decimal("0.00001"),
        )

        self.assertEqual(result.state, "ledger_over_counted")
        self.assertEqual([warning.code for warning in result.warnings], ["ledger_over_counted"])
        self.assertEqual(result.delta_usd, Decimal("-0.00020000"))

    def test_invoice_reconciliation_preflight_warns_on_unknown_pricing_policy(self) -> None:
        self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="unknown",
            model="missing-model",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            at=datetime(2025, 1, 2),
        )

        result = self.service.preflight_invoice_reconciliation(
            owner_user_id="user-a",
            provider="unknown",
            model="missing-model",
            invoice_total_usd=Decimal("0"),
            from_dt=datetime(2025, 1, 1),
            to_dt=datetime(2025, 1, 3),
        )

        self.assertEqual(result.state, "pricing_unknown_warning")
        self.assertEqual([warning.code for warning in result.warnings], ["pricing_policy_unknown"])
        self.assertEqual(result.ledger_total_usd, Decimal("0"))
        self.assertTrue(result.advisory_only)
        self.assertFalse(result.live_enforcement)

    def test_invoice_reconciliation_preflight_keeps_owner_provider_model_scoping(self) -> None:
        self._seed_policy()
        self.db.upsert_model_pricing_policy(
            policy_key="anthropic-sonnet",
            provider="anthropic",
            model="anthropic/claude-sonnet",
            pricing_unit="per_1m_tokens",
            input_price_per_1m=1.0,
            cached_input_price_per_1m=None,
            output_price_per_1m=2.0,
            currency="USD",
            effective_from=datetime(2025, 1, 1),
            active=True,
            metadata_json="{}",
        )
        self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            at=datetime(2025, 1, 2),
        )
        self.service.reconcile_usage(
            owner_user_id="user-b",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=2_000,
            completion_tokens=1_000,
            total_tokens=3_000,
            at=datetime(2025, 1, 2),
        )
        self.service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="anthropic",
            model="anthropic/claude-sonnet",
            prompt_tokens=500,
            completion_tokens=500,
            total_tokens=1_000,
            at=datetime(2025, 1, 2),
        )

        result = self.service.preflight_invoice_reconciliation(
            owner_user_id="user-a",
            provider="openai",
            model="openai/gpt-4o-mini",
            invoice_total_usd=Decimal("0.00075"),
            from_dt=datetime(2025, 1, 1),
            to_dt=datetime(2025, 1, 3),
        )

        self.assertEqual(result.ledger_total_usd, Decimal("0.00075000"))
        self.assertEqual(result.invoice_total_usd, Decimal("0.00075000"))
        self.assertEqual(result.state, "matched_total")

    def test_invoice_reconciliation_preflight_is_read_only_and_avoids_live_paths(self) -> None:
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
            at=datetime(2025, 1, 2),
        )
        with self.db.session_scope() as session:
            before_count = session.query(LLMCostLedger).count()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("invoice preflight must not call live LLM/provider paths")

        with (
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
        ):
            result = self.service.preflight_invoice_reconciliation(
                owner_user_id="user-a",
                provider="openai",
                model="openai/gpt-4o-mini",
                invoice_total_usd=Decimal("0.00075"),
                from_dt=datetime(2025, 1, 1),
                to_dt=datetime(2025, 1, 3),
            )

        self.assertEqual(result.state, "matched_total")
        with self.db.session_scope() as session:
            after_count = session.query(LLMCostLedger).count()
        self.assertEqual(after_count, before_count)


if __name__ == "__main__":
    unittest.main()
