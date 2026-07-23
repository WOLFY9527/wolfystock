# -*- coding: utf-8 -*-
"""Focused contracts for portfolio valuation and investment-return truth."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import Config
from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_service import PortfolioService
from src.storage import DatabaseManager


class PortfolioValuationTruthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_environment = {
            key: os.environ.get(key)
            for key in ("ENV_FILE", "DATABASE_PATH", "ADMIN_AUTH_ENABLED")
        }
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.db_path = Path(self.temp_dir.name) / "portfolio-valuation-truth.db"
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
        os.environ["ADMIN_AUTH_ENABLED"] = "false"
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.service = PortfolioService()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    def _save_close(self, symbol: str, on_date: date, close: float) -> None:
        frame = pd.DataFrame(
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
        self.db.save_daily_data(frame, code=symbol, data_source="portfolio-valuation-truth-test")

    def _create_account(self, *, name: str = "Truth", base_currency: str = "USD") -> int:
        account = self.service.create_account(
            name=name,
            broker="Demo",
            market="us",
            base_currency=base_currency,
        )
        return int(account["id"])

    def test_missing_fx_is_unavailable_without_one_to_one_or_zero_exposure(self) -> None:
        account_id = self._create_account(base_currency="CNY")
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=account_id,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1.0,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 2), 100.0)

        snapshot = self.service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )

        position = snapshot["accounts"][0]["positions"][0]
        self.assertEqual(position["market_value_native"], 100.0)
        self.assertEqual(position["currency"], "USD")
        self.assertEqual(position["display_fx_status"], "unavailable")
        self.assertEqual(position["market_value_base"], 0.0)
        self.assertEqual(snapshot["total_market_value"], 0.0)
        self.assertEqual(snapshot["availability"]["valuation"]["state"], "unavailable")
        self.assertEqual(snapshot["availability"]["valuation"]["value_semantics"], "covered_subtotal")
        self.assertEqual(
            snapshot["availability"]["valuation"]["unavailable_native_values"],
            [
                {
                    "component": f"account:{account_id}:position:AAPL:us:USD",
                    "amount": 100.0,
                    "currency": "USD",
                }
            ],
        )
        self.assertEqual(snapshot["performance"]["calculation_state"], "unavailable")
        self.assertIsNone(snapshot["fx_rates"][0]["rate"])

        cash_account_id = self._create_account(name="Native Cash", base_currency="CNY")
        self.service.record_cash_ledger(
            account_id=cash_account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=25.0,
            currency="USD",
        )
        cash_snapshot = self.service.get_portfolio_snapshot(
            account_id=cash_account_id,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )
        self.assertEqual(cash_snapshot["availability"]["valuation"]["state"], "unavailable")
        self.assertEqual(
            cash_snapshot["availability"]["valuation"]["unavailable_native_values"],
            [
                {
                    "component": f"account:{cash_account_id}:cash:USD",
                    "amount": 25.0,
                    "currency": "USD",
                }
            ],
        )

        covered_account_id = self._create_account(name="Covered", base_currency="CNY")
        self.service.record_cash_ledger(
            account_id=covered_account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="CNY",
        )
        partial = self.service.get_portfolio_snapshot(as_of=date(2026, 1, 2), cost_method="fifo")
        self.assertEqual(partial["availability"]["valuation"]["state"], "partial")
        self.assertEqual(partial["total_cash"], 1000.0)
        self.assertEqual(partial["performance"]["calculation_state"], "partial")

    def test_portfolio_truth_model_separates_account_and_valuation_states(self) -> None:
        no_account = self.service.get_portfolio_snapshot(as_of=date(2026, 1, 2), cost_method="fifo")
        self.assertEqual(
            no_account["portfolio_truth"],
            {
                "state": "no_account",
                "account_state": "no_account",
                "valuation_state": "not_applicable",
                "value_semantics": "not_applicable",
                "authoritative_total": None,
                "covered_subtotal": None,
                "account_count": 0,
                "position_count": 0,
            },
        )

        empty_account_id = self._create_account(name="Empty", base_currency="USD")
        no_holdings = self.service.get_portfolio_snapshot(
            account_id=empty_account_id,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )
        self.assertEqual(
            no_holdings["portfolio_truth"],
            {
                "state": "account_no_holdings",
                "account_state": "no_holdings",
                "valuation_state": "fully_valued",
                "value_semantics": "authoritative_total",
                "authoritative_total": 0.0,
                "covered_subtotal": None,
                "account_count": 1,
                "position_count": 0,
            },
        )

        unavailable_account_id = self._create_account(name="Unknown FX", base_currency="CNY")
        self.service.record_cash_ledger(
            account_id=unavailable_account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=25.0,
            currency="USD",
        )
        unavailable = self.service.get_portfolio_snapshot(
            account_id=unavailable_account_id,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )
        self.assertEqual(unavailable["portfolio_truth"]["state"], "valuation_unavailable")
        self.assertEqual(unavailable["portfolio_truth"]["account_state"], "no_holdings")
        self.assertEqual(unavailable["portfolio_truth"]["value_semantics"], "unavailable")
        self.assertIsNone(unavailable["portfolio_truth"]["authoritative_total"])
        self.assertIsNone(unavailable["portfolio_truth"]["covered_subtotal"])

        partial_account_id = self._create_account(name="Partial FX", base_currency="CNY")
        self.service.record_cash_ledger(
            account_id=partial_account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=25.0,
            currency="USD",
        )
        self.service.record_cash_ledger(
            account_id=partial_account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="CNY",
        )
        partial = self.service.get_portfolio_snapshot(
            account_id=partial_account_id,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )
        self.assertEqual(partial["portfolio_truth"]["state"], "valuation_partial")
        self.assertEqual(partial["portfolio_truth"]["value_semantics"], "covered_subtotal")
        self.assertIsNone(partial["portfolio_truth"]["authoritative_total"])
        self.assertEqual(partial["portfolio_truth"]["covered_subtotal"], 100.0)

        zero_account_id = self._create_account(name="Fully Valued Zero", base_currency="USD")
        self.service.record_trade(
            account_id=zero_account_id,
            symbol="ZERO",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1.0,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("ZERO", date(2026, 1, 2), 100.0)
        fully_valued_zero = self.service.get_portfolio_snapshot(
            account_id=zero_account_id,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )
        self.assertEqual(fully_valued_zero["portfolio_truth"]["state"], "fully_valued_zero")
        self.assertEqual(fully_valued_zero["portfolio_truth"]["value_semantics"], "authoritative_total")
        self.assertEqual(fully_valued_zero["portfolio_truth"]["authoritative_total"], 0.0)

        nonzero_account_id = self._create_account(name="Fully Valued Nonzero", base_currency="USD")
        self.service.record_trade(
            account_id=nonzero_account_id,
            symbol="NONZERO",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1.0,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("NONZERO", date(2026, 1, 2), 110.0)
        fully_valued_nonzero = self.service.get_portfolio_snapshot(
            account_id=nonzero_account_id,
            as_of=date(2026, 1, 2),
            cost_method="fifo",
        )
        self.assertEqual(fully_valued_nonzero["portfolio_truth"]["state"], "fully_valued_nonzero")
        self.assertEqual(fully_valued_nonzero["portfolio_truth"]["value_semantics"], "authoritative_total")
        self.assertEqual(fully_valued_nonzero["portfolio_truth"]["authoritative_total"], 10.0)

    def test_multicurrency_components_keep_price_income_fees_fx_and_cash_distinct(self) -> None:
        account_id = self._create_account(base_currency="CNY")
        for rate_date, rate in (
            (date(2026, 2, 1), 7.0),
            (date(2026, 2, 2), 7.5),
            (date(2026, 2, 3), 8.0),
        ):
            self.service.repo.save_fx_rate(
                from_currency="USD",
                to_currency="CNY",
                rate_date=rate_date,
                rate=rate,
                source="reviewed_fixture",
                is_stale=False,
            )
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 2, 1),
            direction="in",
            amount=200.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=account_id,
            symbol="AAPL",
            trade_date=date(2026, 2, 1),
            side="buy",
            quantity=1.0,
            price=100.0,
            fee=2.0,
            market="us",
            currency="USD",
        )
        self.service.record_corporate_action(
            account_id=account_id,
            symbol="AAPL",
            effective_date=date(2026, 2, 2),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=5.0,
        )
        self._save_close("AAPL", date(2026, 2, 3), 110.0)

        snapshot = self.service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=date(2026, 2, 3),
            cost_method="fifo",
        )

        performance = snapshot["performance"]
        pnl = performance["pnl"]
        cash_flows = performance["cash_flows"]
        self.assertEqual(snapshot["availability"]["valuation"]["state"], "available")
        self.assertAlmostEqual(snapshot["total_equity"], 1704.0, places=6)
        self.assertAlmostEqual(cash_flows["deposits"], 1400.0, places=6)
        self.assertAlmostEqual(cash_flows["withdrawals"], 0.0, places=6)
        self.assertAlmostEqual(pnl["price"], 80.0, places=6)
        self.assertAlmostEqual(pnl["income"], 37.5, places=6)
        self.assertAlmostEqual(pnl["fees"], 14.0, places=6)
        self.assertAlmostEqual(pnl["fx"], 200.5, places=6)
        self.assertAlmostEqual(pnl["gross"], 318.0, places=6)
        self.assertAlmostEqual(pnl["net"], 304.0, places=6)
        self.assertEqual(performance["price_basis"], "snapshot_valuation_price_not_executable")

    def test_deposits_and_withdrawals_are_return_and_drawdown_neutral(self) -> None:
        account_id = self._create_account()
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 3, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )
        first = self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 3, 1))
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 3, 2),
            direction="in",
            amount=500.0,
            currency="USD",
        )
        second = self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 3, 2))
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 3, 3),
            direction="out",
            amount=400.0,
            currency="USD",
        )
        third = self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 3, 3))

        for snapshot in (first, second, third):
            self.assertEqual(snapshot["performance"]["pnl"]["net"], 0.0)
            self.assertEqual(snapshot["performance"]["return"]["percent"], 0.0)
            self.assertEqual(snapshot["analytics"]["pnl"]["total"]["amount"], 0.0)
            self.assertEqual(snapshot["analytics"]["pnl"]["total"]["percent"], 0.0)

        self.service.record_trade(
            account_id=account_id,
            symbol="AAPL",
            trade_date=date(2026, 3, 4),
            side="buy",
            quantity=10.0,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 3, 4), 100.0)
        self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 3, 4))
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 3, 5),
            direction="out",
            amount=50.0,
            currency="USD",
        )
        fourth = self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 3, 5))
        self._save_close("AAPL", date(2026, 3, 6), 90.0)
        fifth = self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 3, 6))

        self.assertEqual(fourth["performance"]["pnl"]["net"], 0.0)
        self.assertEqual(fifth["performance"]["pnl"]["net"], -100.0)

        drawdown = PortfolioRiskService(portfolio_service=self.service)._build_drawdown(
            account_id=account_id,
            as_of_date=date(2026, 3, 6),
            cost_method="fifo",
            threshold_pct=15.0,
            lookback_days=30,
            report_currency="USD",
        )
        self.assertEqual(drawdown["series_points"], 6)
        self.assertAlmostEqual(drawdown["max_drawdown_pct"], 9.5238, places=4)
        self.assertAlmostEqual(drawdown["current_drawdown_pct"], 9.5238, places=4)

    def test_dividend_is_included_once_and_return_uses_documented_denominator(self) -> None:
        account_id = self._create_account()
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 4, 1),
            direction="in",
            amount=2000.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=account_id,
            symbol="MSFT",
            trade_date=date(2026, 4, 1),
            side="buy",
            quantity=10.0,
            price=100.0,
            fee=10.0,
            market="us",
            currency="USD",
        )
        self.service.record_corporate_action(
            account_id=account_id,
            symbol="MSFT",
            effective_date=date(2026, 4, 2),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=5.0,
        )
        self._save_close("MSFT", date(2026, 4, 3), 110.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 4, 3))

        performance = snapshot["performance"]
        self.assertEqual(performance["pnl"]["price"], 100.0)
        self.assertEqual(performance["pnl"]["income"], 50.0)
        self.assertEqual(performance["pnl"]["fees"], 10.0)
        self.assertEqual(performance["pnl"]["gross"], 150.0)
        self.assertEqual(performance["pnl"]["net"], 140.0)
        self.assertEqual(performance["return"]["method"], "modified_dietz")
        self.assertEqual(performance["return"]["denominator"], 2000.0)
        self.assertEqual(performance["return"]["denominator_semantics"], "time_weighted_external_cash_flows")
        self.assertEqual(performance["return"]["percent"], 7.0)
        self.assertEqual(snapshot["analytics"]["pnl"]["total"]["amount"], 140.0)
        self.assertEqual(snapshot["analytics"]["pnl"]["total"]["percent"], 7.0)

    def test_return_is_unavailable_without_positive_denominator(self) -> None:
        account_id = self._create_account()
        self.service.record_trade(
            account_id=account_id,
            symbol="AAPL",
            trade_date=date(2026, 5, 1),
            side="buy",
            quantity=1.0,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 5, 2), 110.0)

        snapshot = self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 5, 2))

        return_contract = snapshot["performance"]["return"]
        self.assertEqual(return_contract["status"], "unavailable")
        self.assertIsNone(return_contract["denominator"])
        self.assertIsNone(return_contract["percent"])
        self.assertEqual(return_contract["reason"], "non_positive_denominator")

    def test_account_scoped_performance_does_not_mix_other_accounts(self) -> None:
        first_id = self._create_account(name="First")
        second_id = self._create_account(name="Second")
        self.service.record_cash_ledger(
            account_id=first_id,
            event_date=date(2026, 6, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )
        self.service.record_cash_ledger(
            account_id=second_id,
            event_date=date(2026, 6, 1),
            direction="in",
            amount=3000.0,
            currency="USD",
        )

        first = self.service.get_portfolio_snapshot(account_id=first_id, as_of=date(2026, 6, 1))
        combined = self.service.get_portfolio_snapshot(as_of=date(2026, 6, 1))

        self.assertEqual(first["account_count"], 1)
        self.assertEqual(first["performance"]["cash_flows"]["deposits"], 1000.0)
        self.assertEqual(combined["account_count"], 2)
        self.assertEqual(combined["performance"]["cash_flows"]["deposits"], 4000.0)


if __name__ == "__main__":
    unittest.main()
