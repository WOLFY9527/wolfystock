# -*- coding: utf-8 -*-
"""Unit tests for portfolio replay service (P0 PR1 scope)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from sqlalchemy.exc import OperationalError
from sqlalchemy import select

from src.config import Config
from src.repositories.portfolio_repo import PortfolioBusyError, PortfolioRepository
from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_service import PortfolioConflictError, PortfolioOversellError, PortfolioService
from src.storage import (
    DatabaseManager,
    PortfolioCashLedger,
    PortfolioCorporateAction,
    PortfolioDailySnapshot,
    PortfolioPosition,
    PortfolioPositionLot,
    PortfolioTrade,
)


class PortfolioServiceTestCase(unittest.TestCase):
    """Portfolio service replay tests for FIFO/AVG and corporate actions."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.db_path = Path(self.temp_dir.name) / "portfolio_test.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.db = DatabaseManager.get_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _save_close(self, symbol: str, on_date: date, close: float) -> None:
        df = pd.DataFrame(
            [
                {
                    "date": on_date,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1.0,
                    "amount": close,
                    "pct_chg": 0.0,
                }
            ]
        )
        self.db.save_daily_data(df, code=symbol, data_source="unit-test")

    def _ledger_counts(self) -> dict[str, int]:
        with self.db.get_session() as session:
            return {
                "trades": session.query(PortfolioTrade).count(),
                "cash": session.query(PortfolioCashLedger).count(),
                "corporate_actions": session.query(PortfolioCorporateAction).count(),
            }

    def _create_app_user(self, user_id: str, username: str) -> None:
        self.db.create_or_update_app_user(
            user_id=user_id,
            username=username,
            role="user",
            display_name=username.title(),
            is_active=True,
        )

    def test_phase_f_compare_value_helper_normalizes_created_at_timezone_only_drift(self) -> None:
        normalized = self.service._normalize_phase_f_compare_value(
            field_name="created_at",
            value=datetime(2026, 4, 21, 0, 49, 23, 107279, tzinfo=timezone(timedelta(hours=8))),
        )

        self.assertEqual(normalized, "2026-04-21T00:49:23.107279")
        self.assertEqual(
            self.service._normalize_phase_f_compare_value(field_name="symbol", value="AAPL"),
            "AAPL",
        )

    def test_phase_f_result_view_summary_helper_returns_shared_shape(self) -> None:
        summary = self.service._summarize_phase_f_result_view(
            {
                "total": "2",
                "page": None,
                "page_size": "50",
                "items": [
                    {"id": 21, "created_at": "2026-04-21T00:49:23.107279"},
                    {"id": 20, "created_at": "2026-04-21T00:49:22.107279"},
                ],
            }
        )

        self.assertEqual(
            summary,
            {
                "total": 2,
                "page": 1,
                "page_size": 50,
                "page_item_count": 2,
                "ordered_ids": [21, 20],
            },
        )

    def test_phase_f_compare_methods_ignore_created_at_timezone_only_drift_across_surfaces(self) -> None:
        cases = [
            (
                "trade_list",
                self.service._compare_phase_f_trade_list_results,
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 11,
                            "account_id": 1,
                            "trade_uid": None,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "trade_date": "2026-04-21",
                            "side": "buy",
                            "quantity": 10.0,
                            "price": 100.0,
                            "fee": 0.0,
                            "tax": 0.0,
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:23.107279",
                        }
                    ],
                },
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 11,
                            "account_id": 1,
                            "trade_uid": None,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "trade_date": "2026-04-21",
                            "side": "buy",
                            "quantity": 10.0,
                            "price": 100.0,
                            "fee": 0.0,
                            "tax": 0.0,
                            "note": "seed",
                            "created_at": datetime(2026, 4, 21, 0, 49, 23, 107279, tzinfo=timezone(timedelta(hours=8))).isoformat(),
                        }
                    ],
                },
            ),
            (
                "cash_ledger",
                self.service._compare_phase_f_cash_ledger_results,
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 12,
                            "account_id": 1,
                            "event_date": "2026-04-21",
                            "direction": "in",
                            "amount": 1000.0,
                            "currency": "USD",
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:23.107279",
                        }
                    ],
                },
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 12,
                            "account_id": 1,
                            "event_date": "2026-04-21",
                            "direction": "in",
                            "amount": 1000.0,
                            "currency": "USD",
                            "note": "seed",
                            "created_at": datetime(2026, 4, 21, 0, 49, 23, 107279, tzinfo=timezone(timedelta(hours=8))).isoformat(),
                        }
                    ],
                },
            ),
            (
                "corporate_actions",
                self.service._compare_phase_f_corporate_actions_results,
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 13,
                            "account_id": 1,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "effective_date": "2026-04-21",
                            "action_type": "cash_dividend",
                            "cash_dividend_per_share": 1.0,
                            "split_ratio": None,
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:23.107279",
                        }
                    ],
                },
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 13,
                            "account_id": 1,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "effective_date": "2026-04-21",
                            "action_type": "cash_dividend",
                            "cash_dividend_per_share": 1.0,
                            "split_ratio": None,
                            "note": "seed",
                            "created_at": datetime(2026, 4, 21, 0, 49, 23, 107279, tzinfo=timezone(timedelta(hours=8))).isoformat(),
                        }
                    ],
                },
            ),
        ]

        for label, comparer, legacy_view, candidate_view in cases:
            with self.subTest(surface=label):
                self.assertIsNone(comparer(legacy_view=legacy_view, candidate_view=candidate_view))

    def test_phase_f_compare_methods_detect_real_created_at_drift_across_surfaces(self) -> None:
        cases = [
            (
                "trade_list",
                self.service._compare_phase_f_trade_list_results,
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 11,
                            "account_id": 1,
                            "trade_uid": None,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "trade_date": "2026-04-21",
                            "side": "buy",
                            "quantity": 10.0,
                            "price": 100.0,
                            "fee": 0.0,
                            "tax": 0.0,
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:23.107279",
                        }
                    ],
                },
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 11,
                            "account_id": 1,
                            "trade_uid": None,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "trade_date": "2026-04-21",
                            "side": "buy",
                            "quantity": 10.0,
                            "price": 100.0,
                            "fee": 0.0,
                            "tax": 0.0,
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:24.107279+08:00",
                        }
                    ],
                },
            ),
            (
                "cash_ledger",
                self.service._compare_phase_f_cash_ledger_results,
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 12,
                            "account_id": 1,
                            "event_date": "2026-04-21",
                            "direction": "in",
                            "amount": 1000.0,
                            "currency": "USD",
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:23.107279",
                        }
                    ],
                },
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 12,
                            "account_id": 1,
                            "event_date": "2026-04-21",
                            "direction": "in",
                            "amount": 1000.0,
                            "currency": "USD",
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:24.107279+08:00",
                        }
                    ],
                },
            ),
            (
                "corporate_actions",
                self.service._compare_phase_f_corporate_actions_results,
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 13,
                            "account_id": 1,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "effective_date": "2026-04-21",
                            "action_type": "cash_dividend",
                            "cash_dividend_per_share": 1.0,
                            "split_ratio": None,
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:23.107279",
                        }
                    ],
                },
                {
                    "request_context": {"account_id": 1, "page": 1, "page_size": 20},
                    "total": 1,
                    "items": [
                        {
                            "id": 13,
                            "account_id": 1,
                            "symbol": "AAPL",
                            "market": "us",
                            "currency": "USD",
                            "effective_date": "2026-04-21",
                            "action_type": "cash_dividend",
                            "cash_dividend_per_share": 1.0,
                            "split_ratio": None,
                            "note": "seed",
                            "created_at": "2026-04-21T00:49:24.107279+08:00",
                        }
                    ],
                },
            ),
        ]

        for label, comparer, legacy_view, candidate_view in cases:
            with self.subTest(surface=label):
                mismatch = comparer(legacy_view=legacy_view, candidate_view=candidate_view)
                self.assertIsNotNone(mismatch)
                self.assertEqual(mismatch["mismatch_class"], "payload_field_mismatch")
                self.assertEqual(mismatch["first_mismatch_field"], "created_at")

    def test_snapshot_fifo_vs_avg_on_partial_sell(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=100,
            price=10,
            fee=10,
            tax=0,
            market="cn",
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 3),
            side="buy",
            quantity=100,
            price=20,
            fee=10,
            tax=0,
            market="cn",
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 4),
            side="sell",
            quantity=150,
            price=30,
            fee=10,
            tax=5,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 5), 25)

        fifo = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 5), cost_method="fifo")
        avg = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 5), cost_method="avg")

        fifo_acc = fifo["accounts"][0]
        avg_acc = avg["accounts"][0]
        self.assertAlmostEqual(fifo_acc["total_equity"], avg_acc["total_equity"], places=6)

        self.assertAlmostEqual(fifo_acc["realized_pnl"], 2470.0, places=6)
        self.assertAlmostEqual(avg_acc["realized_pnl"], 2220.0, places=6)
        self.assertAlmostEqual(fifo_acc["unrealized_pnl"], 245.0, places=6)
        self.assertAlmostEqual(avg_acc["unrealized_pnl"], 495.0, places=6)

        self.assertEqual(len(fifo_acc["positions"]), 1)
        self.assertEqual(len(avg_acc["positions"]), 1)
        self.assertAlmostEqual(fifo_acc["positions"][0]["quantity"], 50.0, places=6)
        self.assertAlmostEqual(avg_acc["positions"][0]["quantity"], 50.0, places=6)

    def test_snapshot_analytics_expose_pnl_exposure_and_risk(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=100,
            price=10,
            fee=10,
            tax=0,
            market="us",
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 3),
            side="sell",
            quantity=40,
            price=15,
            fee=5,
            tax=0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 4), 20.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 4), cost_method="fifo")
        position = snapshot["accounts"][0]["positions"][0]

        self.assertAlmostEqual(position["market_value_native"], 1200.0, places=6)
        self.assertAlmostEqual(position["cost_basis_native"], 606.0, places=6)
        self.assertAlmostEqual(position["unrealized_pnl_native"], 594.0, places=6)
        self.assertAlmostEqual(position["unrealized_pnl_pct"], 98.019802, places=6)
        self.assertAlmostEqual(snapshot["analytics"]["pnl"]["realized"]["amount"], 191.0, places=6)
        self.assertAlmostEqual(snapshot["analytics"]["pnl"]["unrealized"]["amount"], 594.0, places=6)
        self.assertAlmostEqual(snapshot["analytics"]["pnl"]["total"]["amount"], 785.0, places=6)
        self.assertEqual(snapshot["analytics"]["exposure"]["by_account"][0]["account_id"], aid)
        self.assertEqual(snapshot["analytics"]["exposure"]["by_currency"][0]["currency"], "USD")
        self.assertEqual(snapshot["analytics"]["exposure"]["by_market"][0]["market"], "us")
        self.assertEqual(snapshot["analytics"]["exposure"]["by_symbol"][0]["symbol"], "AAPL")
        self.assertEqual(snapshot["analytics"]["risk"]["holding_count"], 1)
        self.assertIn("single_position_gt_30", snapshot["analytics"]["risk"]["warnings"])

    def test_ledger_cash_movement_and_pnl_after_buy_sell_fixture(self) -> None:
        account = self.service.create_account(name="Ledger", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 2, 1),
            direction="in",
            amount=10000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 2, 2),
            side="buy",
            quantity=30,
            price=100,
            fee=3,
            tax=2,
            market="us",
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 2, 3),
            side="sell",
            quantity=10,
            price=120,
            fee=1,
            tax=2,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 2, 4), 130.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 2, 4), cost_method="fifo")
        account_snapshot = snapshot["accounts"][0]
        position = account_snapshot["positions"][0]

        self.assertAlmostEqual(account_snapshot["total_cash"], 8192.0, places=6)
        self.assertAlmostEqual(account_snapshot["realized_pnl"], 195.333333, places=6)
        self.assertAlmostEqual(account_snapshot["unrealized_pnl"], 596.666667, places=6)
        self.assertAlmostEqual(account_snapshot["fee_total"], 4.0, places=6)
        self.assertAlmostEqual(account_snapshot["tax_total"], 4.0, places=6)
        self.assertAlmostEqual(position["quantity"], 20.0, places=6)
        self.assertAlmostEqual(position["cost_basis_native"], 2003.33333333, places=6)
        self.assertAlmostEqual(position["market_value_native"], 2600.0, places=6)
        self.assertEqual(account_snapshot["realized_pnl_by_symbol"][0]["symbol"], "AAPL")

    def test_corporate_actions_and_ledger_views_are_owner_scoped(self) -> None:
        self._create_app_user("alice-ledger", "alice-ledger")
        self._create_app_user("bob-ledger", "bob-ledger")
        alice = PortfolioService(owner_id="alice-ledger")
        bob = PortfolioService(owner_id="bob-ledger")
        alice_account = alice.create_account(name="Alice", broker="Demo", market="us", base_currency="USD")["id"]
        bob_account = bob.create_account(name="Bob", broker="Demo", market="us", base_currency="USD")["id"]

        for service, account_id, trade_uid in (
            (alice, alice_account, "alice-owner-trade"),
            (bob, bob_account, "bob-owner-trade"),
        ):
            service.record_cash_ledger(
                account_id=account_id,
                event_date=date(2026, 3, 1),
                direction="in",
                amount=1000,
                currency="USD",
            )
            service.record_trade(
                account_id=account_id,
                symbol="AAPL",
                trade_date=date(2026, 3, 2),
                side="buy",
                quantity=10,
                price=50,
                fee=0,
                tax=0,
                market="us",
                currency="USD",
                trade_uid=trade_uid,
            )
        bob.record_corporate_action(
            account_id=bob_account,
            symbol="AAPL",
            effective_date=date(2026, 3, 3),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=1.0,
        )
        self._save_close("AAPL", date(2026, 3, 4), 55.0)

        alice_actions = alice.list_corporate_action_events(page_size=100)
        alice_trades = alice.list_trade_events(page_size=100)
        alice_cash = alice.list_cash_ledger_events(page_size=100)
        alice_snapshot = alice.get_portfolio_snapshot(as_of=date(2026, 3, 4), cost_method="fifo")
        bob_snapshot = bob.get_portfolio_snapshot(as_of=date(2026, 3, 4), cost_method="fifo")

        self.assertEqual(alice_actions["total"], 0)
        self.assertEqual([item["trade_uid"] for item in alice_trades["items"]], ["alice-owner-trade"])
        self.assertEqual([item["account_id"] for item in alice_cash["items"]], [alice_account])
        self.assertEqual(alice_snapshot["account_count"], 1)
        self.assertEqual(alice_snapshot["accounts"][0]["account_id"], alice_account)
        self.assertAlmostEqual(alice_snapshot["accounts"][0]["total_cash"], 500.0, places=6)
        self.assertAlmostEqual(bob_snapshot["accounts"][0]["total_cash"], 510.0, places=6)

        with self.assertRaises(ValueError):
            alice.list_corporate_action_events(account_id=bob_account)
        with self.assertRaises(ValueError):
            alice.get_portfolio_snapshot(account_id=bob_account, as_of=date(2026, 3, 4))

    def test_snapshot_and_risk_reads_do_not_mutate_ledger_state(self) -> None:
        account = self.service.create_account(name="Read Only", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 4, 1),
            direction="in",
            amount=5000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 4, 2),
            side="buy",
            quantity=20,
            price=100,
            fee=2,
            tax=0,
            market="us",
            currency="USD",
        )
        self.service.record_corporate_action(
            account_id=aid,
            symbol="AAPL",
            effective_date=date(2026, 4, 3),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=0.5,
        )
        self._save_close("AAPL", date(2026, 4, 4), 105.0)
        before = self._ledger_counts()

        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 4, 4), cost_method="fifo")
        PortfolioRiskService(portfolio_service=self.service).get_risk_report(
            account_id=aid,
            as_of=date(2026, 4, 4),
            cost_method="fifo",
        )
        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 4, 4), cost_method="fifo")

        self.assertEqual(self._ledger_counts(), before)
        self.assertEqual(self.service.list_trade_events(account_id=aid)["total"], 1)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=aid)["total"], 1)
        self.assertEqual(self.service.list_corporate_action_events(account_id=aid)["total"], 1)
        provenance = PortfolioRiskService(portfolio_service=self.service).get_risk_report(
            account_id=aid,
            as_of=date(2026, 4, 4),
            cost_method="fifo",
        )["sectorSourceProvenance"]
        self.assertTrue(provenance["diagnosticOnly"])
        self.assertTrue(provenance["observationOnly"])
        self.assertFalse(provenance["authorityGrant"])
        self.assertFalse(provenance["decisionGrade"])
        self.assertFalse(provenance["accountingMutation"])
        self.assertFalse(provenance["providerRoutingChanged"])
        self.assertFalse(provenance["externalProviderCallsAdded"])
        self.assertFalse(provenance["marketCacheMutation"])
        self.assertEqual(provenance["summary"]["nonCnNotApplicableCount"], 1)
        self.assertEqual(provenance["items"][0]["classificationState"], "non_cn_not_applicable")
        self.assertEqual(provenance["items"][0]["industryLabel"], "UNCLASSIFIED")
        self.assertFalse(provenance["items"][0]["authorityGrant"])

    def test_risk_read_projection_cache_writes_remain_distinct_from_ledger_authority_rows(self) -> None:
        account = self.service.create_account(name="Risk Cache", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 4, 1),
            direction="in",
            amount=5000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 4, 2),
            side="buy",
            quantity=20,
            price=100,
            fee=2,
            tax=0,
            market="us",
            currency="USD",
        )
        self.service.record_corporate_action(
            account_id=aid,
            symbol="AAPL",
            effective_date=date(2026, 4, 3),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=0.5,
        )
        self._save_close("AAPL", date(2026, 4, 4), 105.0)
        before = self._ledger_counts()

        with self.db.get_session() as session:
            trade_ids_before = [
                row.id
                for row in session.execute(
                    select(PortfolioTrade).where(PortfolioTrade.account_id == aid)
                ).scalars().all()
            ]
            cash_ids_before = [
                row.id
                for row in session.execute(
                    select(PortfolioCashLedger).where(PortfolioCashLedger.account_id == aid)
                ).scalars().all()
            ]
            action_ids_before = [
                row.id
                for row in session.execute(
                    select(PortfolioCorporateAction).where(PortfolioCorporateAction.account_id == aid)
                ).scalars().all()
            ]
            self.assertEqual(
                session.execute(
                    select(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id == aid)
                ).scalars().all(),
                [],
            )

        report = PortfolioRiskService(portfolio_service=self.service).get_risk_report(
            account_id=aid,
            as_of=date(2026, 4, 4),
            cost_method="fifo",
        )

        self.assertIn("riskDiagnostics", report)
        self.assertIn("portfolioRiskEvidence", report)
        self.assertEqual(report["riskDiagnostics"]["sourceAuthority"]["state"], "manual")
        source_refs = {
            item["source_ref_id"]: item
            for item in report["portfolioRiskEvidence"]["source_refs"]
        }
        self.assertEqual(
            {
                key: (
                    value["provider"],
                    value["source_class"],
                    value["sanitized_reason_code"],
                    value["raw_payload_stored"],
                )
                for key, value in source_refs.items()
            },
            {
                "portfolio_snapshot": ("portfolio_snapshot", "local", "snapshot_summary_only", False),
                "fx_snapshot": ("fx_cache", "local", "fx_summary_only", False),
            },
        )
        required_evidence = {
            item["key"]: item
            for item in report["portfolioRiskEvidence"]["required_evidence"]
        }
        self.assertEqual(required_evidence["source.authority"]["reason_codes"], ["source_authority_manual"])
        self.assertEqual(required_evidence["source.authority"]["source_ref_ids"], ["portfolio_snapshot"])
        self.assertTrue(report["portfolioRiskEvidence"]["admin_diagnostics"]["sanitized_only"])
        self.assertFalse(report["portfolioRiskEvidence"]["admin_diagnostics"]["raw_payload_stored"])

        with self.db.get_session() as session:
            snapshot_rows = session.execute(
                select(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id == aid)
            ).scalars().all()
            position_rows = session.execute(
                select(PortfolioPosition).where(PortfolioPosition.account_id == aid)
            ).scalars().all()
            lot_rows = session.execute(
                select(PortfolioPositionLot).where(PortfolioPositionLot.account_id == aid)
            ).scalars().all()
            trade_ids_after = [
                row.id
                for row in session.execute(
                    select(PortfolioTrade).where(PortfolioTrade.account_id == aid)
                ).scalars().all()
            ]
            cash_ids_after = [
                row.id
                for row in session.execute(
                    select(PortfolioCashLedger).where(PortfolioCashLedger.account_id == aid)
                ).scalars().all()
            ]
            action_ids_after = [
                row.id
                for row in session.execute(
                    select(PortfolioCorporateAction).where(PortfolioCorporateAction.account_id == aid)
                ).scalars().all()
            ]

        self.assertEqual(self._ledger_counts(), before)
        self.assertEqual(trade_ids_after, trade_ids_before)
        self.assertEqual(cash_ids_after, cash_ids_before)
        self.assertEqual(action_ids_after, action_ids_before)
        self.assertGreaterEqual(len(snapshot_rows), 1)
        self.assertTrue(any(row.snapshot_date == date(2026, 4, 4) for row in snapshot_rows))
        self.assertGreaterEqual(len(position_rows), 1)
        self.assertGreaterEqual(len(lot_rows), 1)

    def test_snapshot_and_risk_reads_keep_ledger_rows_stable_across_risk_board_outcomes(self) -> None:
        scenarios = (
            (
                "success",
                [{"name": "白酒", "type": "行业"}],
                "白酒",
                0,
                0,
                "cn_board_lookup_resolved",
                "provider_observed",
                "missing",
            ),
            (
                "fallback_proxy",
                [{"name": "代理行业", "type": "行业", "source_type": "fallback_proxy"}],
                "代理行业",
                0,
                0,
                "cn_board_lookup_resolved",
                "fallback",
                "present_not_authoritative",
            ),
            (
                "empty",
                [],
                "UNCLASSIFIED",
                0,
                0,
                "cn_board_lookup_empty",
                "missing",
                "missing",
            ),
            (
                "failure",
                ValueError("provider lookup failed"),
                "UNCLASSIFIED",
                1,
                1,
                "lookup_failure",
                "unknown",
                "unknown",
            ),
        )

        for offset, (
            label,
            board_result,
            expected_industry,
            expected_failed_count,
            expected_error_count,
            expected_state,
            expected_source_kind,
            expected_source_detail_state,
        ) in enumerate(scenarios):
            as_of_date = date(2026, 4, 10 + offset)
            account = self.service.create_account(
                name=f"Board {label}",
                broker="Demo",
                market="cn",
                base_currency="CNY",
            )
            aid = account["id"]
            self.service.record_cash_ledger(
                account_id=aid,
                event_date=as_of_date,
                direction="in",
                amount=5000,
                currency="CNY",
            )
            self.service.record_trade(
                account_id=aid,
                symbol="600519",
                trade_date=as_of_date,
                side="buy",
                quantity=20,
                price=100,
                fee=2,
                tax=0,
                market="cn",
                currency="CNY",
            )
            self.service.record_corporate_action(
                account_id=aid,
                symbol="600519",
                effective_date=as_of_date,
                action_type="cash_dividend",
                market="cn",
                currency="CNY",
                cash_dividend_per_share=0.5,
            )
            self._save_close("600519", as_of_date, 105.0)
            before = self._ledger_counts()

            patch_kwargs = (
                {"side_effect": board_result}
                if isinstance(board_result, Exception)
                else {"return_value": board_result}
            )
            with self.subTest(outcome=label), patch.object(PortfolioRiskService, "_fetch_belong_boards", **patch_kwargs):
                snapshot = self.service.get_portfolio_snapshot(
                    account_id=aid,
                    as_of=as_of_date,
                    cost_method="fifo",
                )
                report = PortfolioRiskService(portfolio_service=self.service).get_risk_report(
                    account_id=aid,
                    as_of=as_of_date,
                    cost_method="fifo",
                )

            self.assertEqual(self._ledger_counts(), before)
            self.assertEqual(self.service.list_trade_events(account_id=aid)["total"], 1)
            self.assertEqual(self.service.list_cash_ledger_events(account_id=aid)["total"], 1)
            self.assertEqual(self.service.list_corporate_action_events(account_id=aid)["total"], 1)
            self.assertEqual(
                snapshot["portfolio_attribution"]["industry_attribution"]["top_industries"][0]["industry"],
                expected_industry,
            )
            self.assertEqual(snapshot["sourceAuthorityState"], "manual")
            self.assertEqual(snapshot["riskDiagnostics"]["sourceAuthority"]["state"], "manual")
            self.assertEqual(report["sourceAuthorityState"], "manual")
            self.assertEqual(report["riskDiagnostics"]["sourceAuthority"]["state"], "manual")
            self.assertEqual(report["fxFreshnessState"], "fresh")
            self.assertTrue(report["portfolioRiskEvidence"]["admin_diagnostics"]["sanitized_only"])
            self.assertFalse(report["portfolioRiskEvidence"]["admin_diagnostics"]["raw_payload_stored"])
            report_source_refs = {
                item["source_ref_id"]: item
                for item in report["portfolioRiskEvidence"]["source_refs"]
            }
            self.assertEqual(
                {
                    key: (
                        value["provider"],
                        value["source_class"],
                        value["sanitized_reason_code"],
                    )
                    for key, value in report_source_refs.items()
                },
                {
                    "portfolio_snapshot": ("portfolio_snapshot", "local", "snapshot_summary_only"),
                    "fx_snapshot": ("fx_cache", "local", "fx_summary_only"),
                },
            )
            self.assertEqual(report["industry_attribution"]["top_industries"][0]["industry"], expected_industry)
            self.assertEqual(report["sector_concentration"]["top_sectors"][0]["sector"], expected_industry)
            self.assertEqual(report["industry_attribution"]["coverage"]["failed_count"], expected_failed_count)
            self.assertEqual(report["sector_concentration"]["coverage"]["failed_count"], expected_failed_count)
            self.assertEqual(len(report["industry_attribution"]["errors"]), expected_error_count)
            self.assertEqual(len(report["sector_concentration"]["errors"]), expected_error_count)
            if expected_error_count:
                self.assertIn("provider lookup failed", report["industry_attribution"]["errors"][0])
                self.assertIn("provider lookup failed", report["sector_concentration"]["errors"][0])
            else:
                self.assertEqual(report["industry_attribution"]["errors"], [])
                self.assertEqual(report["sector_concentration"]["errors"], [])
            provenance = report["sectorSourceProvenance"]
            self.assertTrue(provenance["diagnosticOnly"])
            self.assertTrue(provenance["observationOnly"])
            self.assertFalse(provenance["authorityGrant"])
            self.assertFalse(provenance["decisionGrade"])
            self.assertFalse(provenance["accountingMutation"])
            self.assertFalse(provenance["providerRoutingChanged"])
            self.assertFalse(provenance["externalProviderCallsAdded"])
            self.assertFalse(provenance["marketCacheMutation"])
            self.assertEqual(provenance["classificationAuthority"], "not_authoritative")
            self.assertEqual(provenance["summary"]["symbolMarketCount"], 1)
            self.assertEqual(provenance["summary"]["lookupFailureCount"], expected_failed_count)
            resolved_label = label in {"success", "fallback_proxy"}
            self.assertEqual(provenance["summary"]["cnBoardLookupResolvedCount"], 1 if resolved_label else 0)
            self.assertEqual(provenance["summary"]["emptyBoardLookupCount"], 1 if label == "empty" else 0)
            self.assertEqual(provenance["summary"]["providerObservedCount"], 1 if resolved_label else 0)
            self.assertEqual(provenance["summary"]["fallbackOrProxySourceCount"], 1 if label == "fallback_proxy" else 0)
            item = provenance["items"][0]
            self.assertEqual(item["symbol"], "600519")
            self.assertEqual(item["market"], "cn")
            self.assertEqual(item["classificationState"], expected_state)
            self.assertEqual(item["sourceKind"], expected_source_kind)
            self.assertEqual(item["sourceDetailState"], expected_source_detail_state)
            self.assertEqual(item["industryLabel"], expected_industry)
            self.assertFalse(item["authorityGrant"])
            self.assertFalse(item["decisionGrade"])

    def test_snapshot_and_risk_reads_do_not_mutate_broker_connection_state(self) -> None:
        account = self.service.create_account(name="Broker Safe", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        self.service.create_broker_connection(
            portfolio_account_id=aid,
            broker_type="ibkr",
            broker_name="Interactive Brokers",
            connection_name="Primary IBKR",
            broker_account_ref="U7654321",
            import_mode="file",
            sync_metadata={"source": "flex", "scope": "diagnostic_fixture"},
        )
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 5, 10),
            direction="in",
            amount=5000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 5, 10),
            side="buy",
            quantity=10,
            price=100,
            fee=1,
            tax=0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 5, 10), 105.0)
        before_counts = self._ledger_counts()
        before_connections = [
            {
                "id": item["id"],
                "portfolio_account_id": item["portfolio_account_id"],
                "broker_type": item["broker_type"],
                "broker_account_ref": item["broker_account_ref"],
                "connection_name": item["connection_name"],
                "status": item["status"],
                "import_mode": item["import_mode"],
                "sync_metadata": item["sync_metadata"],
            }
            for item in self.service.list_broker_connections(portfolio_account_id=aid)
        ]

        snapshot = self.service.get_portfolio_snapshot(
            account_id=aid,
            as_of=date(2026, 5, 10),
            cost_method="fifo",
        )
        report = PortfolioRiskService(portfolio_service=self.service).get_risk_report(
            account_id=aid,
            as_of=date(2026, 5, 10),
            cost_method="fifo",
        )

        after_connections = [
            {
                "id": item["id"],
                "portfolio_account_id": item["portfolio_account_id"],
                "broker_type": item["broker_type"],
                "broker_account_ref": item["broker_account_ref"],
                "connection_name": item["connection_name"],
                "status": item["status"],
                "import_mode": item["import_mode"],
                "sync_metadata": item["sync_metadata"],
            }
            for item in self.service.list_broker_connections(portfolio_account_id=aid)
        ]

        self.assertEqual(self._ledger_counts(), before_counts)
        self.assertEqual(before_connections, after_connections)
        self.assertIsNone(self.service.get_latest_broker_sync_state(portfolio_account_id=aid))
        self.assertEqual(snapshot["sourceAuthorityState"], "manual")
        provenance = report["sectorSourceProvenance"]
        self.assertTrue(provenance["diagnosticOnly"])
        self.assertTrue(provenance["observationOnly"])
        self.assertFalse(provenance["authorityGrant"])
        self.assertFalse(provenance["decisionGrade"])
        self.assertFalse(provenance["accountingMutation"])
        self.assertFalse(provenance["providerRoutingChanged"])
        self.assertFalse(provenance["externalProviderCallsAdded"])
        self.assertFalse(provenance["marketCacheMutation"])

    def test_corporate_actions_dividend_and_split(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=100,
            price=10,
            fee=0,
            tax=0,
            market="cn",
            currency="CNY",
        )
        self.service.record_corporate_action(
            account_id=aid,
            symbol="600519",
            effective_date=date(2026, 1, 3),
            action_type="cash_dividend",
            market="cn",
            currency="CNY",
            cash_dividend_per_share=1.0,
        )
        self.service.record_corporate_action(
            account_id=aid,
            symbol="600519",
            effective_date=date(2026, 1, 4),
            action_type="split_adjustment",
            market="cn",
            currency="CNY",
            split_ratio=2.0,
        )
        self._save_close("600519", date(2026, 1, 5), 6.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 5), cost_method="fifo")
        acc = snapshot["accounts"][0]
        pos = acc["positions"][0]

        self.assertAlmostEqual(acc["total_cash"], 9100.0, places=6)
        self.assertAlmostEqual(acc["total_market_value"], 1200.0, places=6)
        self.assertAlmostEqual(acc["total_equity"], 10300.0, places=6)
        self.assertAlmostEqual(pos["quantity"], 200.0, places=6)
        self.assertAlmostEqual(pos["avg_cost"], 5.0, places=6)

    def test_futu_diluted_cost_examples_allow_negative_and_dividend_adjustment(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=100,
            price=10,
            fee=0,
            tax=0,
            market="us",
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 3),
            side="sell",
            quantity=50,
            price=25,
            fee=0,
            tax=0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 4), 25)

        snapshot = self.service.get_portfolio_snapshot(
            account_id=aid,
            as_of=date(2026, 1, 4),
            cost_method="futu_diluted",
        )
        pos = snapshot["accounts"][0]["positions"][0]
        self.assertAlmostEqual(pos["quantity"], 50.0, places=6)
        self.assertAlmostEqual(pos["avg_cost"], -5.0, places=6)

        dividend_account = self.service.create_account(name="Dividend", broker="Demo", market="us", base_currency="USD")
        did = dividend_account["id"]
        self.service.record_cash_ledger(
            account_id=did,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=did,
            symbol="MSFT",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=100,
            price=10,
            fee=0,
            tax=0,
            market="us",
            currency="USD",
        )
        self.service.record_corporate_action(
            account_id=did,
            symbol="MSFT",
            effective_date=date(2026, 1, 3),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=1.0,
        )
        self._save_close("MSFT", date(2026, 1, 4), 10)

        dividend_snapshot = self.service.get_portfolio_snapshot(
            account_id=did,
            as_of=date(2026, 1, 4),
            cost_method="futu_diluted",
        )
        self.assertAlmostEqual(dividend_snapshot["accounts"][0]["positions"][0]["avg_cost"], 9.0, places=6)

    def test_ths_pnl_cost_uses_net_cashflows_and_resets_after_flat(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=100,
            price=10,
            fee=10,
            tax=0,
            market="us",
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 3),
            side="sell",
            quantity=100,
            price=12,
            fee=5,
            tax=0,
            market="us",
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 4),
            side="buy",
            quantity=50,
            price=20,
            fee=0,
            tax=0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 5), 20)

        snapshot = self.service.get_portfolio_snapshot(
            account_id=aid,
            as_of=date(2026, 1, 5),
            cost_method="ths_pnl",
        )
        pos = snapshot["accounts"][0]["positions"][0]
        self.assertAlmostEqual(pos["quantity"], 50.0, places=6)
        self.assertAlmostEqual(pos["avg_cost"], 20.0, places=6)

    def test_same_day_dividend_processed_before_trade(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=2000,
            currency="CNY",
        )
        self.service.record_corporate_action(
            account_id=aid,
            symbol="600519",
            effective_date=date(2026, 1, 2),
            action_type="cash_dividend",
            market="cn",
            currency="CNY",
            cash_dividend_per_share=1.0,
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=100,
            price=10,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 2), 10.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")
        acc = snapshot["accounts"][0]

        self.assertAlmostEqual(acc["total_cash"], 1000.0, places=6)
        self.assertAlmostEqual(acc["total_market_value"], 1000.0, places=6)
        self.assertAlmostEqual(acc["total_equity"], 2000.0, places=6)

    def test_same_day_split_processed_before_trade(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=2000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=100,
            price=10,
            market="cn",
            currency="CNY",
        )
        self.service.record_corporate_action(
            account_id=aid,
            symbol="600519",
            effective_date=date(2026, 1, 2),
            action_type="split_adjustment",
            market="cn",
            currency="CNY",
            split_ratio=2.0,
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="sell",
            quantity=100,
            price=6,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 2), 6.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")
        acc = snapshot["accounts"][0]
        pos = acc["positions"][0]

        self.assertAlmostEqual(acc["realized_pnl"], 100.0, places=6)
        self.assertAlmostEqual(acc["total_cash"], 1600.0, places=6)
        self.assertAlmostEqual(pos["quantity"], 100.0, places=6)
        self.assertAlmostEqual(pos["avg_cost"], 5.0, places=6)

    def test_sell_oversell_rejected_before_write(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=10,
            market="cn",
            currency="CNY",
        )

        with self.assertRaises(PortfolioOversellError):
            self.service.record_trade(
                account_id=aid,
                symbol="600519",
                trade_date=date(2026, 1, 3),
                side="sell",
                quantity=20,
                price=11,
                market="cn",
                currency="CNY",
            )

        trades = self.service.list_trade_events(account_id=aid, page=1, page_size=20)
        self.assertEqual(len(trades["items"]), 1)
        self.assertEqual(trades["items"][0]["side"], "buy")

    def test_duplicate_full_close_sell_keeps_conflict_semantics(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=10,
            market="cn",
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="sell",
            quantity=10,
            price=11,
            market="cn",
            currency="CNY",
            trade_uid="sell-full-close-1",
        )

        with self.assertRaises(PortfolioConflictError) as ctx:
            self.service.record_trade(
                account_id=aid,
                symbol="600519",
                trade_date=date(2026, 1, 2),
                side="sell",
                quantity=10,
                price=11,
                market="cn",
                currency="CNY",
                trade_uid="sell-full-close-1",
            )

        self.assertIn("Duplicate trade_uid", str(ctx.exception))

    def test_broker_connection_crud_roundtrip(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]

        created = self.service.create_broker_connection(
            portfolio_account_id=aid,
            broker_type="ibkr",
            broker_name="Interactive Brokers",
            connection_name="Primary IBKR",
            broker_account_ref="U1234567",
            import_mode="file",
            sync_metadata={"source": "flex"},
        )

        self.assertEqual(created["owner_id"], account["owner_id"])
        self.assertEqual(created["portfolio_account_id"], aid)
        self.assertEqual(created["broker_type"], "ibkr")
        self.assertEqual(created["connection_name"], "Primary IBKR")
        self.assertEqual(created["sync_metadata"], {"source": "flex"})

        listed = self.service.list_broker_connections(portfolio_account_id=aid)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["portfolio_account_name"], "Main")

        updated = self.service.update_broker_connection(
            created["id"],
            connection_name="IBKR Flex",
            status="disabled",
            sync_metadata={"source": "flex", "region": "global"},
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["connection_name"], "IBKR Flex")
        self.assertEqual(updated["status"], "disabled")
        self.assertEqual(updated["sync_metadata"]["region"], "global")

        with self.assertRaises(PortfolioConflictError):
            self.service.create_broker_connection(
                portfolio_account_id=aid,
                broker_type="ibkr",
                connection_name="Duplicate Ref",
                broker_account_ref="U1234567",
            )

    def test_event_delete_respects_owner_scope(self) -> None:
        self.db.create_or_update_app_user(user_id="user-a", username="alice")
        self.db.create_or_update_app_user(user_id="user-b", username="bob")
        service_a = PortfolioService(owner_id="user-a")
        service_b = PortfolioService(owner_id="user-b")

        account = service_a.create_account(name="Alice Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        trade_id = service_a.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )["id"]
        cash_id = service_a.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 2),
            direction="in",
            amount=1000,
            currency="CNY",
        )["id"]
        action_id = service_a.record_corporate_action(
            account_id=aid,
            symbol="600519",
            effective_date=date(2026, 1, 3),
            action_type="cash_dividend",
            market="cn",
            currency="CNY",
            cash_dividend_per_share=1.0,
        )["id"]

        self.assertFalse(service_b.delete_trade_event(trade_id))
        self.assertFalse(service_b.delete_cash_ledger_event(cash_id))
        self.assertFalse(service_b.delete_corporate_action_event(action_id))

        self.assertTrue(service_a.delete_trade_event(trade_id))
        self.assertTrue(service_a.delete_cash_ledger_event(cash_id))
        self.assertTrue(service_a.delete_corporate_action_event(action_id))

    def test_backdated_trade_write_invalidates_future_cache(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 3),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 3), 100.0)
        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 3), cost_method="fifo")

        with self.db.get_session() as session:
            snapshot_count = session.execute(
                select(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id == aid)
            ).scalars().all()
            position_count = session.execute(
                select(PortfolioPosition).where(PortfolioPosition.account_id == aid)
            ).scalars().all()
            lot_count = session.execute(
                select(PortfolioPositionLot).where(PortfolioPositionLot.account_id == aid)
            ).scalars().all()
        self.assertEqual(len(snapshot_count), 1)
        self.assertEqual(len(position_count), 1)
        self.assertEqual(len(lot_count), 1)

        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=5,
            price=80,
            market="cn",
            currency="CNY",
        )

        with self.db.get_session() as session:
            snapshot_rows = session.execute(
                select(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id == aid)
            ).scalars().all()
            position_rows = session.execute(
                select(PortfolioPosition).where(PortfolioPosition.account_id == aid)
            ).scalars().all()
            lot_rows = session.execute(
                select(PortfolioPositionLot).where(PortfolioPositionLot.account_id == aid)
            ).scalars().all()
        self.assertEqual(len(snapshot_rows), 0)
        self.assertEqual(len(position_rows), 0)
        self.assertEqual(len(lot_rows), 0)

    def test_delete_trade_invalidates_cache_and_removes_source_event(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        trade = self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 2), 100.0)
        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        self.assertTrue(self.service.delete_trade_event(trade["id"]))

        with self.db.get_session() as session:
            trade_rows = session.execute(
                select(PortfolioTrade).where(PortfolioTrade.account_id == aid)
            ).scalars().all()
            snapshot_rows = session.execute(
                select(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id == aid)
            ).scalars().all()
            lot_rows = session.execute(
                select(PortfolioPositionLot).where(PortfolioPositionLot.account_id == aid)
            ).scalars().all()
        self.assertEqual(len(trade_rows), 1)
        self.assertFalse(trade_rows[0].is_active)
        self.assertIsNotNone(trade_rows[0].voided_at)
        self.assertEqual(len(snapshot_rows), 0)
        self.assertEqual(len(lot_rows), 0)

    def test_legacy_null_is_active_trade_is_treated_as_active_in_default_list(self) -> None:
        condition_sql = str(PortfolioRepository._active_trade_condition().compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("is_active", condition_sql.lower())
        self.assertIn("is true", condition_sql.lower())
        self.assertIn("is null", condition_sql.lower())

    def test_update_trade_recalculates_holdings_and_keeps_trade_active(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=5000,
            currency="USD",
        )
        trade = self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 3), 125.0)

        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 3), cost_method="fifo")

        updated = self.service.update_trade_event(
            trade["id"],
            quantity=5,
            price=120,
        )

        self.assertEqual(updated["id"], trade["id"])
        self.assertEqual(updated["quantity"], 5.0)
        self.assertEqual(updated["price"], 120.0)
        self.assertTrue(updated["is_active"])
        self.assertIsNone(updated["voided_at"])

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 3), cost_method="fifo")
        account_snapshot = snapshot["accounts"][0]
        self.assertEqual(len(account_snapshot["positions"]), 1)
        self.assertAlmostEqual(account_snapshot["positions"][0]["quantity"], 5.0, places=6)
        self.assertAlmostEqual(account_snapshot["positions"][0]["avg_cost"], 120.0, places=6)
        self.assertAlmostEqual(account_snapshot["total_cash"], 4400.0, places=6)

    def test_update_trade_can_move_symbol_and_currency_without_changing_cost_method_semantics(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="global", base_currency="USD")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="USD",
        )
        trade = self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("00700", date(2026, 1, 3), 400.0)

        updated = self.service.update_trade_event(
            trade["id"],
            symbol="00700",
            market="hk",
            currency="HKD",
            quantity=20,
            price=50,
        )

        self.assertEqual(updated["symbol"], "00700")
        self.assertEqual(updated["market"], "hk")
        self.assertEqual(updated["currency"], "HKD")

        for method in ("fifo", "avg", "futu_diluted", "ths_pnl"):
            snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 3), cost_method=method)
            account_snapshot = snapshot["accounts"][0]
            self.assertEqual([position["symbol"] for position in account_snapshot["positions"]], ["00700"])
            self.assertAlmostEqual(account_snapshot["positions"][0]["quantity"], 20.0, places=6)

    def test_delete_buy_trade_soft_void_removes_active_holding(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000,
            currency="CNY",
        )
        trade = self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 3), 100.0)

        self.assertTrue(self.service.delete_trade_event(trade["id"]))

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 3), cost_method="fifo")
        self.assertEqual(snapshot["accounts"][0]["positions"], [])

        with self.db.get_session() as session:
            row = session.execute(select(PortfolioTrade).where(PortfolioTrade.id == trade["id"])).scalar_one()
        self.assertFalse(row.is_active)
        self.assertIsNotNone(row.voided_at)

    def test_snapshot_analytics_exclude_soft_voided_trade(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        voided = self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="000001",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=5,
            price=10,
            market="cn",
            currency="CNY",
        )
        self.assertTrue(self.service.delete_trade_event(voided["id"]))
        self._save_close("600519", date(2026, 1, 2), 200.0)
        self._save_close("000001", date(2026, 1, 2), 12.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        self.assertEqual([item["symbol"] for item in snapshot["accounts"][0]["positions"]], ["000001"])
        self.assertEqual([item["symbol"] for item in snapshot["analytics"]["exposure"]["by_symbol"]], ["000001"])
        self.assertAlmostEqual(snapshot["analytics"]["pnl"]["unrealized"]["amount"], 10.0, places=6)

    def test_snapshot_analytics_mark_fx_unavailable_but_keep_native_values(self) -> None:
        account = self.service.create_account(name="HK", broker="Demo", market="hk", base_currency="USD")
        aid = account["id"]
        self.service.record_trade(
            account_id=aid,
            symbol="00700",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="hk",
            currency="HKD",
        )
        self._save_close("00700", date(2026, 1, 2), 110.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")
        position = snapshot["accounts"][0]["positions"][0]

        self.assertEqual(position["currency"], "HKD")
        self.assertAlmostEqual(position["market_value_native"], 1100.0, places=6)
        self.assertEqual(position["display_fx_status"], "unavailable")
        self.assertEqual(snapshot["analytics"]["pnl"]["unrealized"]["fx_status"], "unavailable")
        self.assertTrue(snapshot["analytics"]["risk"]["fx_unavailable"])

    def test_delete_sell_trade_restores_prior_quantity(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=5000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        sell_trade = self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="sell",
            quantity=4,
            price=110,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 3), 100.0)

        self.assertTrue(self.service.delete_trade_event(sell_trade["id"]))

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 3), cost_method="fifo")
        self.assertAlmostEqual(snapshot["accounts"][0]["positions"][0]["quantity"], 10.0, places=6)

    def test_update_trade_invalid_id_returns_none(self) -> None:
        self.assertIsNone(self.service.update_trade_event(999999, quantity=5))

    def test_update_trade_rejects_invalid_quantity_and_price(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="us", base_currency="USD")
        aid = account["id"]
        trade = self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="us",
            currency="USD",
        )

        with self.assertRaises(ValueError):
            self.service.update_trade_event(trade["id"], quantity=0)

        with self.assertRaises(ValueError):
            self.service.update_trade_event(trade["id"], price=-1)

    def test_concurrent_sell_race_allows_only_one_write(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=10,
            market="cn",
            currency="CNY",
        )

        barrier = threading.Barrier(3)
        results: list[str] = []
        errors: list[Exception] = []

        def _worker(uid: str) -> None:
            svc = PortfolioService()
            barrier.wait()
            try:
                svc.record_trade(
                    account_id=aid,
                    symbol="600519",
                    trade_date=date(2026, 1, 2),
                    side="sell",
                    quantity=10,
                    price=11,
                    market="cn",
                    currency="CNY",
                    trade_uid=uid,
                )
                results.append(uid)
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        threads = [
            threading.Thread(target=_worker, args=(f"sell-race-{idx}",), daemon=True)
            for idx in range(2)
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], PortfolioOversellError)

        trades = self.service.list_trade_events(account_id=aid, page=1, page_size=20)
        sell_count = sum(1 for item in trades["items"] if item["side"] == "sell")
        self.assertEqual(sell_count, 1)

    def test_concurrent_duplicate_full_close_sell_keeps_conflict_semantics(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=10,
            market="cn",
            currency="CNY",
        )

        barrier = threading.Barrier(3)
        results: list[str] = []
        errors: list[Exception] = []

        def _worker() -> None:
            svc = PortfolioService()
            barrier.wait()
            try:
                svc.record_trade(
                    account_id=aid,
                    symbol="600519",
                    trade_date=date(2026, 1, 2),
                    side="sell",
                    quantity=10,
                    price=11,
                    market="cn",
                    currency="CNY",
                    trade_uid="dup-race-sell-1",
                )
                results.append("ok")
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], PortfolioConflictError)
        self.assertIn("Duplicate trade_uid", str(errors[0]))

    def test_snapshot_uses_batched_latest_close_lookup(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="000001",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=5,
            price=20,
            market="cn",
            currency="CNY",
        )

        with patch.object(
            self.service.repo,
            "get_latest_close",
            side_effect=AssertionError("snapshot read should batch latest-close lookups"),
        ), patch.object(
            self.service.repo,
            "get_latest_closes_with_dates",
            create=True,
            return_value={
                "600519": (100.0, date(2026, 1, 1)),
                "000001": (20.0, date(2026, 1, 1)),
            },
        ) as batch_lookup:
            snapshot = self.service.get_portfolio_snapshot(
                account_id=aid,
                as_of=date(2026, 1, 1),
                cost_method="fifo",
            )

        self.assertEqual(
            {item["symbol"] for item in snapshot["accounts"][0]["positions"]},
            {"600519", "000001"},
        )
        batch_lookup.assert_called_once()
        self.assertEqual(set(batch_lookup.call_args.kwargs["symbols"]), {"600519", "000001"})
        self.assertEqual(batch_lookup.call_args.kwargs["as_of"], date(2026, 1, 1))

    def test_snapshot_uses_actual_latest_close_date_for_price_as_of(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 3), 125.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 5), cost_method="fifo")

        account_snapshot = snapshot["accounts"][0]
        position = account_snapshot["positions"][0]
        self.assertAlmostEqual(position["avg_cost"], 100.0, places=6)
        self.assertAlmostEqual(position["last_price"], 125.0, places=6)
        self.assertAlmostEqual(position["market_value_base"], 1250.0, places=6)
        self.assertAlmostEqual(position["unrealized_pnl_base"], 250.0, places=6)
        self.assertAlmostEqual(position["cost_basis_native"], 1000.0, places=6)
        self.assertAlmostEqual(account_snapshot["total_cash"], 9000.0, places=6)
        self.assertAlmostEqual(account_snapshot["total_market_value"], 1250.0, places=6)
        self.assertAlmostEqual(account_snapshot["unrealized_pnl"], 250.0, places=6)
        self.assertEqual(position["price_source"], "daily_close_quote")
        self.assertEqual(position["price_as_of"], "2026-01-03")
        self.assertFalse(position["is_price_fallback"])

    def test_snapshot_discloses_avg_cost_price_fallback_without_mutating_ledger(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )

        before_counts = self._ledger_counts()
        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")
        after_counts = self._ledger_counts()

        position = snapshot["accounts"][0]["positions"][0]
        self.assertEqual(before_counts, after_counts)
        self.assertAlmostEqual(position["avg_cost"], 100.0, places=6)
        self.assertAlmostEqual(position["last_price"], 100.0, places=6)
        self.assertAlmostEqual(position["market_value_base"], 1000.0, places=6)
        self.assertAlmostEqual(position["unrealized_pnl_base"], 0.0, places=6)
        self.assertAlmostEqual(position["cost_basis_native"], 1000.0, places=6)
        self.assertEqual(position["price_source"], "avg_cost_fallback")
        self.assertEqual(position["price_source_label"], "Average cost fallback")
        self.assertIsNone(position["price_as_of"])
        self.assertTrue(position["is_price_fallback"])
        self.assertEqual(position["price_fallback_reason"], "current_quote_unavailable")
        self.assertLess(position["valuation_confidence"], 0.5)

    def test_snapshot_marks_live_close_prices_without_fallback_disclosure(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 2), 125.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        position = snapshot["accounts"][0]["positions"][0]
        self.assertAlmostEqual(position["last_price"], 125.0, places=6)
        self.assertAlmostEqual(position["market_value_base"], 1250.0, places=6)
        self.assertAlmostEqual(position["unrealized_pnl_base"], 250.0, places=6)
        self.assertEqual(position["price_source"], "daily_close_quote")
        self.assertEqual(position["price_source_label"], "Daily close quote")
        self.assertEqual(position["price_as_of"], "2026-01-02")
        self.assertFalse(position["is_price_fallback"])
        self.assertIsNone(position["price_fallback_reason"])
        self.assertGreaterEqual(position["valuation_confidence"], 1.0)

    def test_repeated_snapshot_read_reuses_cached_snapshot_without_replay_or_writeback(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 2), 100.0)

        first = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        with self.db.get_session() as session:
            snapshot_row = session.execute(
                select(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id == aid)
            ).scalar_one()
            position_ids_before = [
                row.id
                for row in session.execute(
                    select(PortfolioPosition).where(PortfolioPosition.account_id == aid)
                ).scalars().all()
            ]
            lot_ids_before = [
                row.id
                for row in session.execute(
                    select(PortfolioPositionLot).where(PortfolioPositionLot.account_id == aid)
                ).scalars().all()
            ]
            snapshot_updated_at_before = snapshot_row.updated_at

        with patch.object(
            self.service,
            "_build_account_snapshot",
            side_effect=AssertionError("warm snapshot read should reuse cached snapshot"),
        ):
            second = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        self.assertEqual(second, first)

        with self.db.get_session() as session:
            snapshot_row_after = session.execute(
                select(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id == aid)
            ).scalar_one()
            position_ids_after = [
                row.id
                for row in session.execute(
                    select(PortfolioPosition).where(PortfolioPosition.account_id == aid)
                ).scalars().all()
            ]
            lot_ids_after = [
                row.id
                for row in session.execute(
                    select(PortfolioPositionLot).where(PortfolioPositionLot.account_id == aid)
                ).scalars().all()
            ]

        self.assertEqual(snapshot_row_after.updated_at, snapshot_updated_at_before)
        self.assertEqual(position_ids_after, position_ids_before)
        self.assertEqual(lot_ids_after, lot_ids_before)

    def test_historical_cached_snapshot_does_not_reuse_newer_position_cache(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        first_snapshot = self.service.get_portfolio_snapshot(
            account_id=aid,
            as_of=date(2026, 1, 1),
            cost_method="fifo",
        )

        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=5,
            price=110,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 2), 110.0)
        second_snapshot = self.service.get_portfolio_snapshot(
            account_id=aid,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )
        historical_snapshot = self.service.get_portfolio_snapshot(
            account_id=aid,
            as_of=date(2026, 1, 1),
            cost_method="fifo",
        )

        self.assertEqual(first_snapshot["accounts"][0]["positions"][0]["quantity"], 10.0)
        self.assertEqual(second_snapshot["accounts"][0]["positions"][0]["quantity"], 15.0)
        self.assertEqual(historical_snapshot["accounts"][0]["positions"][0]["quantity"], 10.0)
        self.assertEqual(historical_snapshot["accounts"][0]["total_equity"], first_snapshot["accounts"][0]["total_equity"])

    def test_snapshot_cache_refreshes_after_market_data_update(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 2),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 2), 100.0)
        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        self._save_close("600519", date(2026, 1, 2), 120.0)
        refreshed = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        position = refreshed["accounts"][0]["positions"][0]
        self.assertAlmostEqual(position["last_price"], 120.0, places=6)
        self.assertAlmostEqual(position["market_value_base"], 1200.0, places=6)
        self.assertAlmostEqual(refreshed["accounts"][0]["total_equity"], 10200.0, places=6)

    def test_portfolio_write_session_maps_sqlite_locked_error(self) -> None:
        repo = PortfolioRepository(db_manager=self.db)
        session = self.db.get_session()
        stmt_exc = OperationalError(
            "BEGIN IMMEDIATE",
            None,
            sqlite3.OperationalError("database is locked"),
        )

        with patch.object(self.db, "get_session", return_value=session):
            with patch.object(
                session.connection(),
                "exec_driver_sql",
                side_effect=stmt_exc,
            ):
                with self.assertRaises(PortfolioBusyError):
                    with repo.portfolio_write_session():
                        pass


if __name__ == "__main__":
    unittest.main()
