# -*- coding: utf-8 -*-
"""Tests for local model pricing policy import/update workflow."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.model_pricing_policy_import_service import ModelPricingPolicyImportService
from src.storage import DatabaseManager, ModelPricingPolicy


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class ModelPricingPolicyImportServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()
        self.importer = ModelPricingPolicyImportService(db=self.db)
        self.ledger = LlmCostLedgerService(db=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _record(self, **overrides):
        record = {
            "provider": " OpenAI ",
            "model": "OpenAI/GPT-4O-MINI",
            "input_price_per_1m": "0.15000000",
            "cached_input_price_per_1m": None,
            "output_price_per_1m": "0.60000000",
            "currency": "USD",
            "effective_from": "2025-01-01T00:00:00",
            "source_label": "Sample pricing fixture, not verified current",
            "source_url": "https://openai.com/api/pricing/",
            "active": True,
            "metadata": {"pricing_status": "sample", "api_key": "not-a-real-key"},
        }
        record.update(overrides)
        return record

    def test_valid_policy_import_creates_policy(self) -> None:
        summary = self.importer.import_records([self._record()])

        self.assertEqual(summary.created, 1)
        with self.db.session_scope() as session:
            row = session.query(ModelPricingPolicy).one()
            self.assertEqual(row.provider, "openai")
            self.assertEqual(row.model, "openai/gpt-4o-mini")

    def test_importing_same_policy_is_idempotent(self) -> None:
        first = self.importer.import_records([self._record()])
        second = self.importer.import_records([self._record()])

        self.assertEqual(first.created, 1)
        self.assertEqual(second.skipped, 1)
        with self.db.session_scope() as session:
            self.assertEqual(session.query(ModelPricingPolicy).count(), 1)

    def test_newer_effective_date_coexists_with_old_policy(self) -> None:
        self.importer.import_records(
            [
                self._record(effective_from="2025-01-01T00:00:00", input_price_per_1m="0.10"),
                self._record(effective_from="2025-02-01T00:00:00", input_price_per_1m="0.20"),
            ]
        )

        with self.db.session_scope() as session:
            rows = session.query(ModelPricingPolicy).order_by(ModelPricingPolicy.effective_from).all()
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row.active for row in rows))

    def test_deactivate_superseded_is_explicit(self) -> None:
        self.importer.import_records([self._record(effective_from="2025-01-01T00:00:00")])
        self.importer.import_records(
            [self._record(effective_from="2025-02-01T00:00:00")],
            deactivate_superseded=True,
        )

        with self.db.session_scope() as session:
            rows = session.query(ModelPricingPolicy).order_by(ModelPricingPolicy.effective_from).all()
            self.assertEqual(len(rows), 2)
            self.assertFalse(rows[0].active)
            self.assertEqual(rows[0].effective_until, datetime(2025, 2, 1))
            self.assertTrue(rows[1].active)

    def test_active_lookup_chooses_correct_policy_by_effective_date(self) -> None:
        self.importer.import_records(
            [
                self._record(effective_from="2025-01-01T00:00:00", input_price_per_1m="0.10"),
                self._record(effective_from="2025-02-01T00:00:00", input_price_per_1m="0.20"),
            ]
        )

        old = self.ledger.calculate_cost(
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            route_family="analysis",
            call_type="analysis",
            at=datetime(2025, 1, 15),
        )
        new = self.ledger.calculate_cost(
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            route_family="analysis",
            call_type="analysis",
            at=datetime(2025, 2, 15),
        )

        self.assertEqual(str(old.input_cost_usd), "0.10000000")
        self.assertEqual(str(new.input_cost_usd), "0.20000000")

    def test_inactive_policy_is_ignored(self) -> None:
        self.importer.import_records([self._record(active=False)])

        result = self.ledger.calculate_cost(
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=1000,
            route_family="analysis",
            call_type="analysis",
            at=datetime(2025, 1, 2),
        )

        self.assertEqual(result.status, "pricing_inactive")

    def test_negative_price_rejected(self) -> None:
        summary = self.importer.import_records([self._record(input_price_per_1m="-0.01")])

        self.assertEqual(summary.rejected, 1)
        self.assertEqual(summary.items[0].reason_code, "negative_price")

    def test_missing_provider_or_model_rejected(self) -> None:
        summary = self.importer.import_records(
            [
                self._record(provider=""),
                self._record(model=""),
            ]
        )

        self.assertEqual(summary.rejected, 2)
        self.assertEqual([item.reason_code for item in summary.items], ["missing_provider", "missing_model"])

    def test_cached_input_price_optional(self) -> None:
        summary = self.importer.import_records([self._record(cached_input_price_per_1m=None)])

        self.assertEqual(summary.created, 1)
        with self.db.session_scope() as session:
            row = session.query(ModelPricingPolicy).one()
            self.assertIsNone(row.cached_input_price_per_1m)

    def test_metadata_sanitizer_drops_secret_like_keys(self) -> None:
        self.importer.import_records(
            [
                self._record(
                    metadata={
                        "review_status": "sample",
                        "api_key": "not-a-real-key",
                        "nested": {"token": "not-a-real-token", "keep": "ok"},
                    }
                )
            ]
        )

        with self.db.session_scope() as session:
            row = session.query(ModelPricingPolicy).one()
            metadata = row.to_dict()["metadata"]

        self.assertEqual(metadata, {"review_status": "sample", "nested": {"keep": "ok"}})

    def test_source_url_and_label_stored_safely(self) -> None:
        self.importer.import_records(
            [
                self._record(
                    source_label="Provider public pricing page",
                    source_url="https://api-docs.deepseek.com/quick_start/pricing",
                )
            ]
        )

        with self.db.session_scope() as session:
            row = session.query(ModelPricingPolicy).one()
            self.assertEqual(row.source_label, "Provider public pricing page")
            self.assertEqual(row.source_url, "https://api-docs.deepseek.com/quick_start/pricing")

    def test_source_url_with_secret_query_is_rejected(self) -> None:
        summary = self.importer.import_records(
            [self._record(source_url="https://example.com/pricing?api_key=not-a-real-key")]
        )

        self.assertEqual(summary.rejected, 1)
        self.assertEqual(summary.items[0].reason_code, "invalid_source_url")

    def test_no_live_network_pricing_scrape_is_used(self) -> None:
        summary = self.importer.import_records([self._record()])

        self.assertEqual(summary.created, 1)


if __name__ == "__main__":
    unittest.main()
