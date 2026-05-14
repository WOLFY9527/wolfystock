# -*- coding: utf-8 -*-
"""Unit tests for additive portfolio risk diagnostics metadata."""

from __future__ import annotations

import json
import unittest
from datetime import date
from types import SimpleNamespace

from src.services.portfolio_risk_diagnostics import build_portfolio_risk_diagnostics


class _FakeRepo:
    def __init__(self, *, trades=None, cash_entries=None, corporate_actions=None):
        self._trades = dict(trades or {})
        self._cash_entries = dict(cash_entries or {})
        self._corporate_actions = dict(corporate_actions or {})

    def list_trades(self, account_id: int, as_of: date, *, include_voided: bool = False):
        rows = list(self._trades.get(account_id, []))
        if include_voided:
            return rows
        return [row for row in rows if bool(getattr(row, "is_active", True))]

    def list_cash_ledger(self, account_id: int, as_of: date):
        return list(self._cash_entries.get(account_id, []))

    def list_corporate_actions(self, account_id: int, as_of: date):
        return list(self._corporate_actions.get(account_id, []))


class _FakePortfolioService:
    def __init__(self, *, repo: _FakeRepo, connections=None, sync_states=None):
        self.repo = repo
        self._connections = list(connections or [])
        self._sync_states = dict(sync_states or {})

    def list_broker_connections(self, *, portfolio_account_id=None, broker_type=None, status=None):
        rows = [row for row in self._connections if portfolio_account_id is None or row["portfolio_account_id"] == portfolio_account_id]
        if broker_type is not None:
            rows = [row for row in rows if row.get("broker_type") == broker_type]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def get_latest_broker_sync_state(self, *, portfolio_account_id: int):
        return self._sync_states.get(portfolio_account_id)


class PortfolioRiskDiagnosticsTestCase(unittest.TestCase):
    def test_builds_stale_fx_diagnostics_without_changing_snapshot_values(self) -> None:
        snapshot = {
            "as_of": "2026-05-10",
            "cost_method": "fifo",
            "currency": "CNY",
            "account_count": 1,
            "total_cash": 300.0,
            "total_market_value": 910.0,
            "total_equity": 1210.0,
            "fx_stale": True,
            "fx_rates": [
                {
                    "from_currency": "USD",
                    "to_currency": "CNY",
                    "rate": 7.1,
                    "rate_date": "2026-05-08",
                    "source": "manual",
                    "is_stale": True,
                    "updated_at": "2026-05-08T09:25:00",
                    "source_direction": "direct",
                }
            ],
            "analytics": {"risk": {"fx_unavailable": False}},
            "accounts": [
                {
                    "account_id": 1,
                    "account_name": "Main",
                    "market": "us",
                    "base_currency": "CNY",
                    "total_cash": 300.0,
                    "total_market_value": 910.0,
                    "positions": [
                        {
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "quantity": 1.0,
                            "market_value_base": 910.0,
                            "display_fx_status": "stale",
                        }
                    ],
                }
            ],
        }
        repo = _FakeRepo(
            trades={
                1: [
                    SimpleNamespace(
                        id=11,
                        trade_uid="TR-001",
                        dedup_hash="DEDUP-001",
                        is_active=True,
                    )
                ]
            },
            cash_entries={1: [SimpleNamespace(id=21, currency="CNY")]},
            corporate_actions={1: []},
        )
        service = _FakePortfolioService(repo=repo)

        diagnostics = build_portfolio_risk_diagnostics(
            portfolio_service=service,
            snapshot=snapshot,
            account_id=1,
            as_of=date(2026, 5, 10),
            cost_method="fifo",
        )

        self.assertEqual(snapshot["accounts"][0]["positions"][0]["market_value_base"], 910.0)
        self.assertEqual(diagnostics["fxFreshnessState"], "stale")
        self.assertLessEqual(diagnostics["confidenceCap"]["value"], 75)
        self.assertIn("FX 汇率已过期", diagnostics["confidenceCap"]["limitation_labels"])
        self.assertEqual(diagnostics["portfolioRiskEvidence"]["engine"], "portfolio_risk")
        self.assertEqual(
            {item["key"] for item in diagnostics["portfolioRiskEvidence"]["required_evidence"]},
            {
                "holdings.lineage",
                "cash.ledger",
                "transactions.lineage",
                "fx.freshness",
                "cost_basis.method",
                "source.authority",
                "sync_import.status",
            },
        )
        self.assertTrue(diagnostics["portfolioRiskEvidence"]["admin_diagnostics"]["sanitized_only"])
        self.assertFalse(diagnostics["portfolioRiskEvidence"]["admin_diagnostics"]["raw_payload_stored"])
        self.assertEqual(
            [
                {
                    "source_ref_id": item["source_ref_id"],
                    "provider": item["provider"],
                    "category": item["category"],
                    "source_class": item["source_class"],
                    "raw_payload_stored": item["raw_payload_stored"],
                    "sanitized_reason_code": item["sanitized_reason_code"],
                }
                for item in diagnostics["portfolioRiskEvidence"]["source_refs"]
            ],
            [
                {
                    "source_ref_id": "portfolio_snapshot",
                    "provider": "portfolio_snapshot",
                    "category": "portfolio",
                    "source_class": "local",
                    "raw_payload_stored": False,
                    "sanitized_reason_code": "snapshot_summary_only",
                },
                {
                    "source_ref_id": "fx_snapshot",
                    "provider": "fx_cache",
                    "category": "portfolio",
                    "source_class": "local",
                    "raw_payload_stored": False,
                    "sanitized_reason_code": "fx_summary_only",
                },
            ],
        )

    def test_missing_holdings_cash_and_unknown_authority_fail_closed(self) -> None:
        snapshot = {
            "as_of": "2026-05-10",
            "cost_method": "fifo",
            "currency": "CNY",
            "account_count": 1,
            "total_cash": 0.0,
            "total_market_value": 100.0,
            "total_equity": 100.0,
            "fx_stale": False,
            "fx_rates": [],
            "analytics": {"risk": {"fx_unavailable": True}},
            "accounts": [
                {
                    "account_id": 7,
                    "account_name": "Unknown",
                    "market": "global",
                    "base_currency": "CNY",
                    "total_cash": 0.0,
                    "total_market_value": 100.0,
                    "positions": [
                        {
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "quantity": 1.0,
                            "market_value_base": 100.0,
                            "display_fx_status": "unavailable",
                        }
                    ],
                }
            ],
        }
        service = _FakePortfolioService(repo=_FakeRepo())

        diagnostics = build_portfolio_risk_diagnostics(
            portfolio_service=service,
            snapshot=snapshot,
            account_id=7,
            as_of=date(2026, 5, 10),
            cost_method="fifo",
        )

        self.assertEqual(diagnostics["holdingsLineageState"], "missing")
        self.assertEqual(diagnostics["cashLedgerCompletenessState"], "missing")
        self.assertEqual(diagnostics["sourceAuthorityState"], "unknown")
        self.assertEqual(diagnostics["confidenceCap"]["decision_status"], "禁止判断")
        self.assertLessEqual(diagnostics["confidenceCap"]["value"], 40)
        self.assertIn("持仓来源待核验", diagnostics["confidenceCap"]["limitation_labels"])
        self.assertIn("现金流水不完整", diagnostics["confidenceCap"]["limitation_labels"])
        self.assertIn("依据需复核", diagnostics["confidenceCap"]["limitation_labels"])
        self.assertIn("数据不足，禁止判断", diagnostics["confidenceCap"]["limitation_labels"])

    def test_benchmark_factor_gaps_and_sensitive_fields_are_sanitized(self) -> None:
        snapshot = {
            "as_of": "2026-05-10",
            "cost_method": "avg",
            "currency": "USD",
            "account_count": 1,
            "total_cash": 5000.0,
            "total_market_value": 2500.0,
            "total_equity": 7500.0,
            "fx_stale": False,
            "fx_rates": [],
            "analytics": {"risk": {"fx_unavailable": False}},
            "accounts": [
                {
                    "account_id": 3,
                    "account_name": "IBKR",
                    "market": "us",
                    "base_currency": "USD",
                    "total_cash": 5000.0,
                    "total_market_value": 2500.0,
                    "positions": [
                        {
                            "symbol": "MSFT",
                            "market": "us",
                            "currency": "USD",
                            "quantity": 10.0,
                            "market_value_base": 2500.0,
                            "display_fx_status": "live",
                        }
                    ],
                }
            ],
        }
        repo = _FakeRepo(
            trades={3: [SimpleNamespace(id=31, trade_uid=None, dedup_hash="SAFE-DEDUP", is_active=True)]},
            cash_entries={3: [SimpleNamespace(id=41, currency="USD")]},
            corporate_actions={3: []},
        )
        service = _FakePortfolioService(
            repo=repo,
            connections=[
                {
                    "id": 8,
                    "portfolio_account_id": 3,
                    "broker_type": "ibkr",
                    "status": "active",
                    "import_mode": "file",
                    "last_imported_at": "2026-05-10T10:00:00",
                    "last_import_source": "ibkr",
                    "sync_metadata": {"token": "SUPERSECRET"},
                }
            ],
            sync_states={
                3: {
                    "sync_status": "success",
                    "snapshot_date": "2026-05-10",
                    "synced_at": "2026-05-10T10:30:00",
                    "payload": {"cookie": "VERYSECRET", "rawImportBody": "RAWSECRET"},
                }
            },
        )

        diagnostics = build_portfolio_risk_diagnostics(
            portfolio_service=service,
            snapshot=snapshot,
            account_id=3,
            as_of=date(2026, 5, 10),
            cost_method="avg",
        )

        self.assertEqual(diagnostics["benchmarkMappingState"], "unmapped")
        self.assertEqual(diagnostics["factorMappingState"], "unmapped")
        self.assertIn("benchmark_relative_claims_disabled", diagnostics["confidenceCap"]["disabled_claims"])
        self.assertIn("factor_risk_claims_disabled", diagnostics["confidenceCap"]["disabled_claims"])
        self.assertIn("基准映射暂缺", diagnostics["confidenceCap"]["limitation_labels"])
        self.assertIn("因子映射暂缺", diagnostics["confidenceCap"]["limitation_labels"])
        self.assertTrue(diagnostics["portfolioRiskEvidence"]["admin_diagnostics"]["sanitized_only"])
        self.assertFalse(diagnostics["portfolioRiskEvidence"]["admin_diagnostics"]["raw_payload_stored"])

        payload_text = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("SUPERSECRET", payload_text)
        self.assertNotIn("VERYSECRET", payload_text)
        self.assertNotIn("RAWSECRET", payload_text)


if __name__ == "__main__":
    unittest.main()
