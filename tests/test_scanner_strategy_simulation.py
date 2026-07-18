# -*- coding: utf-8 -*-
"""Tests for scanner strategy historical simulation."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from unittest.mock import patch

import pandas as pd

from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, OWNERSHIP_SCOPE_USER
from src.repositories.scanner_repo import ScannerRepository
from src.repositories.stock_repo import StockRepository
from src.services.market_scanner_service import MarketScannerService
from src.storage import DatabaseManager, MarketScannerCandidate, MarketScannerRun


def _daily_frame(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime([item[0] for item in rows]),
            "open": [item[1] for item in rows],
            "high": [item[1] for item in rows],
            "low": [item[1] for item in rows],
            "close": [item[1] for item in rows],
            "volume": [1_000_000] * len(rows),
            "amount": [10_000_000] * len(rows),
            "pct_chg": pd.Series([item[1] for item in rows]).pct_change().fillna(0.0) * 100.0,
        }
    )


class ScannerStrategySimulationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.db.ensure_bootstrap_admin_user()
        self.repo = ScannerRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        self.service = MarketScannerService(self.db, owner_id=BOOTSTRAP_ADMIN_USER_ID)
        self.datetime_patcher = patch("src.services.market_scanner_service.datetime", wraps=datetime)
        self.scanner_datetime = self.datetime_patcher.start()
        self.scanner_datetime.now.return_value = datetime(2026, 4, 10, 12, 0, 0)

    def tearDown(self) -> None:
        self.datetime_patcher.stop()
        DatabaseManager.reset_instance()

    def _save_run(
        self,
        *,
        run_at: str,
        market: str = "us",
        profile: str = "us_preopen_v1",
        theme_id: str | None = "crypto_miners",
        symbols: list[tuple[str, float]] | None = None,
        evaluated_size: int = 8,
        comparable_evidence: bool = True,
    ) -> int:
        symbols = symbols or [("WULF", 62.0)]
        universe_selection = {
            "universe_type": "theme" if theme_id else "default",
            "theme_id": theme_id,
            "theme_label": "加密矿企" if theme_id else None,
            "requested_symbols_count": 3,
            "accepted_symbols_count": 3,
            "accepted_symbols": [symbol for symbol, _ in symbols],
            "rejected_symbols": [],
        }
        dt = datetime.fromisoformat(run_at)
        run = MarketScannerRun(
            owner_id=BOOTSTRAP_ADMIN_USER_ID,
            scope=OWNERSHIP_SCOPE_USER,
            market=market,
            profile=profile,
            universe_name=f"{market}_scanner_test",
            status="completed",
            shortlist_size=len(symbols),
            universe_size=12,
            preselected_size=8,
            evaluated_size=evaluated_size,
            run_at=dt,
            completed_at=dt,
            source_summary="test",
            summary_json=json.dumps(
                {
                    "profile_label": profile,
                    "watchlist_date": dt.date().isoformat(),
                    "headline": "test run",
                    "shortlisted_codes": [symbol for symbol, _ in symbols],
                    "universe_selection": universe_selection,
                }
            ),
            diagnostics_json=json.dumps(
                {
                    "universe_selection": universe_selection,
                    **(
                        {
                            "dataReadiness": {
                                "state": "ready",
                                "candidateGenerationState": "ready",
                                "candidateGenerationBlockers": [],
                                "selectedCount": len(symbols),
                            }
                        }
                        if comparable_evidence
                        else {}
                    ),
                }
            ),
            universe_notes_json="[]",
            scoring_notes_json="[]",
        )
        candidates = [
            MarketScannerCandidate(
                symbol=symbol,
                name=symbol,
                rank=index,
                score=score,
                quality_hint="test",
                reason_summary="test",
                reasons_json="[]",
                key_metrics_json="[]",
                feature_signals_json="[]",
                risk_notes_json="[]",
                watch_context_json="[]",
                boards_json="[]",
                diagnostics_json=json.dumps(
                    {
                        "last_trade_date": dt.date().isoformat(),
                        **(
                            {
                                "factorEvidence": {
                                    "contractVersion": "scanner_factor_evidence_v1",
                                    "overallState": "valid",
                                    "rankingEligible": True,
                                    "blockers": [],
                                    "requiredFactorCount": 1,
                                    "validRequiredFactorCount": 1,
                                    "factors": [
                                        {
                                            "component": "trend",
                                            "required": True,
                                            "state": "valid",
                                            "scoreContributionAllowed": True,
                                        }
                                    ],
                                },
                                "score_explainability": {
                                    "score_grade_allowed": True,
                                    "cap_reason": None,
                                    "degradation_reason": None,
                                    "source_confidence": {
                                        "scoreContributionAllowed": True,
                                        "sourceAuthorityAllowed": True,
                                        "observationOnly": False,
                                        "isFallback": False,
                                        "isStale": False,
                                        "isPartial": False,
                                        "isSynthetic": False,
                                        "isUnavailable": False,
                                    },
                                },
                            }
                            if comparable_evidence
                            else {}
                        ),
                    }
                ),
            )
            for index, (symbol, score) in enumerate(symbols, start=1)
        ]
        return int(self.repo.save_run_with_candidates(run=run, candidates=candidates).id)

    def _seed_prices(self) -> None:
        self.stock_repo.save_dataframe(
            _daily_frame(
                [
                    ("2026-04-01", 10.0),
                    ("2026-04-02", 10.5),
                    ("2026-04-03", 11.0),
                    ("2026-04-06", 11.2),
                    ("2026-04-07", 11.5),
                    ("2026-04-08", 11.0),
                    ("2026-04-09", 12.0),
                    ("2026-04-10", 12.5),
                ]
            ),
            "WULF",
            data_source="simulation-test",
        )
        self.stock_repo.save_dataframe(
            _daily_frame(
                [
                    ("2026-04-01", 100.0),
                    ("2026-04-02", 101.0),
                    ("2026-04-03", 102.0),
                    ("2026-04-06", 103.0),
                    ("2026-04-07", 104.0),
                    ("2026-04-08", 105.0),
                    ("2026-04-09", 106.0),
                    ("2026-04-10", 107.0),
                ]
            ),
            "SPY",
            data_source="simulation-test",
        )

    def test_returns_insufficient_history_with_fewer_than_two_comparable_runs(self) -> None:
        self._save_run(run_at="2026-04-01T13:30:00")

        result = self.service.build_strategy_simulation(
            market="us",
            profile="us_preopen_v1",
            theme="crypto_miners",
            lookback_days=90,
            forward_days=5,
        )

        self.assertEqual(result["status"], "insufficient_history")
        self.assertEqual(result["window"]["runCount"], 1)
        self.assertIn("历史扫描不足", result["warnings"][0])

    def test_excludes_completed_runs_without_comparable_factor_evidence(self) -> None:
        self._seed_prices()
        self._save_run(run_at="2026-04-01T13:30:00", comparable_evidence=False)
        self._save_run(run_at="2026-04-06T13:30:00")

        result = self.service.build_strategy_simulation(
            market="us",
            profile="us_preopen_v1",
            theme="crypto_miners",
            lookback_days=90,
            forward_days=1,
        )

        self.assertEqual(result["status"], "insufficient_history")
        self.assertEqual(result["window"]["runCount"], 1)
        self.assertEqual(result["summary"]["selectionEvents"], 0)

    def test_filters_matching_theme_profile_market_and_lookback(self) -> None:
        self._seed_prices()
        self._save_run(run_at="2026-04-01T13:30:00")
        self._save_run(run_at="2026-04-02T13:30:00", theme_id="ai_semiconductors_us")
        self._save_run(run_at="2026-04-03T13:30:00", market="hk", profile="hk_preopen_v1")
        self._save_run(run_at="2025-11-01T13:30:00")
        self._save_run(run_at="2026-04-06T13:30:00")

        result = self.service.build_strategy_simulation(
            market="us",
            profile="us_preopen_v1",
            theme="crypto_miners",
            lookback_days=90,
            forward_days=1,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["window"]["runCount"], 2)
        self.assertEqual([item["runId"] for item in result["runs"]], [5, 1])

    def test_calculates_forward_benchmark_excess_and_symbol_aggregation(self) -> None:
        self._seed_prices()
        self._save_run(run_at="2026-04-01T13:30:00", symbols=[("WULF", 62.0)])
        self._save_run(run_at="2026-04-06T13:30:00", symbols=[("WULF", 66.0)])

        result = self.service.build_strategy_simulation(
            market="us",
            profile="us_preopen_v1",
            theme="crypto_miners",
            lookback_days=90,
            forward_days=1,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["summary"]["historicalRuns"], 2)
        self.assertEqual(result["summary"]["selectionEvents"], 2)
        self.assertEqual(result["summary"]["hitRate"], 1.0)
        self.assertEqual(result["summary"]["avgForwardReturnPct"], 3.84)
        self.assertEqual(result["summary"]["medianForwardReturnPct"], 3.84)
        self.assertEqual(result["summary"]["avgBenchmarkReturnPct"], 0.98)
        self.assertEqual(result["summary"]["avgExcessReturnPct"], 2.85)
        self.assertEqual(result["symbols"][0]["symbol"], "WULF")
        self.assertEqual(result["symbols"][0]["selectionCount"], 2)
        self.assertEqual(result["symbols"][0]["avgScore"], 64.0)

    def test_handles_missing_forward_price_data_without_faking_returns(self) -> None:
        self.stock_repo.save_dataframe(_daily_frame([("2026-04-01", 10.0), ("2026-04-02", 11.0)]), "WULF")
        self._save_run(run_at="2026-04-01T13:30:00")
        self._save_run(run_at="2026-04-06T13:30:00")

        result = self.service.build_strategy_simulation(
            market="us",
            profile="us_preopen_v1",
            theme="crypto_miners",
            lookback_days=90,
            forward_days=5,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["summary"]["selectionEvents"], 2)
        self.assertEqual(result["summary"]["dataCoverage"], 0.0)
        self.assertIsNone(result["summary"]["avgForwardReturnPct"])
        self.assertTrue(any("forward price" in item for item in result["warnings"]))

    def test_does_not_trigger_new_scanner_run(self) -> None:
        self._save_run(run_at="2026-04-01T13:30:00")
        self._save_run(run_at="2026-04-06T13:30:00")

        with patch.object(self.service, "run_scan") as run_scan:
            self.service.build_strategy_simulation(
                market="us",
                profile="us_preopen_v1",
                theme="crypto_miners",
                lookback_days=90,
                forward_days=5,
            )

        run_scan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
