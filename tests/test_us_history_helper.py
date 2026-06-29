# -*- coding: utf-8 -*-
"""Regression tests for shared US history loading helpers."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.services.us_history_helper import (
    LOCAL_US_PARQUET_SOURCE,
    LocalUsHistoryLoadResult,
    fetch_daily_history_with_local_us_fallback,
    get_configured_us_stock_parquet_dir,
    get_us_stock_parquet_dir,
    load_local_us_daily_history,
    persist_local_us_daily_history,
)


def _posix(value: object) -> str:
    return str(value).replace("\\", "/")


class UsHistoryHelperTestCase(unittest.TestCase):
    def test_fetch_daily_history_prefers_local_us_parquet_hit(self) -> None:
        local_df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})
        manager = MagicMock()

        with patch(
            "src.services.us_history_helper.load_local_us_daily_history",
            return_value=LocalUsHistoryLoadResult(
                stock_code="AAPL",
                path=Path("/tmp/AAPL.parquet"),
                status="hit",
                dataframe=local_df,
            ),
        ):
            df, source = fetch_daily_history_with_local_us_fallback(
                "AAPL",
                days=20,
                manager=manager,
                log_context="[test history]",
            )

        self.assertIs(df, local_df)
        self.assertEqual(source, LOCAL_US_PARQUET_SOURCE)
        manager.get_daily_data.assert_not_called()

    def test_fetch_daily_history_falls_back_to_api_with_normalized_dates(self) -> None:
        fallback_df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})
        manager = MagicMock()
        manager.get_daily_data.return_value = (fallback_df, "stub_api")

        with patch(
            "src.services.us_history_helper.load_local_us_daily_history",
            return_value=LocalUsHistoryLoadResult(
                stock_code="AAPL",
                path=Path("/tmp/AAPL.parquet"),
                status="missing",
            ),
        ):
            df, source = fetch_daily_history_with_local_us_fallback(
                "aapl",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                days=20,
                manager=manager,
                log_context="[test history]",
            )

        self.assertIs(df, fallback_df)
        self.assertEqual(source, "stub_api")
        manager.get_daily_data.assert_called_once_with(
            stock_code="AAPL",
            start_date="2024-01-01",
            end_date="2024-01-31",
            days=20,
        )

    def test_get_us_stock_parquet_dir_prefers_local_us_env_over_legacy_env(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LOCAL_US_PARQUET_DIR": "/tmp/local-priority",
                "US_STOCK_PARQUET_DIR": "/tmp/legacy-fallback",
            },
            clear=False,
        ):
            self.assertEqual(_posix(get_us_stock_parquet_dir()), "/tmp/local-priority")

    def test_get_configured_us_stock_parquet_dir_distinguishes_missing_env_from_default(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LOCAL_US_PARQUET_DIR": "",
                "US_STOCK_PARQUET_DIR": "",
            },
            clear=False,
        ):
            self.assertIsNone(get_configured_us_stock_parquet_dir())
            self.assertEqual(_posix(get_us_stock_parquet_dir()), "/root/us_test/data/normalized/us")

    def test_load_local_us_daily_history_can_fail_closed_when_cache_path_is_not_configured(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LOCAL_US_PARQUET_DIR": "",
                "US_STOCK_PARQUET_DIR": "",
            },
            clear=False,
        ):
            result = load_local_us_daily_history("AAPL", require_configured_dir=True)

        self.assertEqual(result.status, "not_configured")
        self.assertIsNone(result.dataframe)

    def test_persist_local_us_daily_history_writes_normalized_parquet_cache(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "trade_date": "2026-01-02",
                    "open": "100.0",
                    "high": "102.0",
                    "low": "99.0",
                    "close": "101.0",
                    "volume": "12345",
                    "adjusted_close": "100.5",
                }
            ]
        )
        written: dict[str, object] = {}

        def fake_to_parquet(self, path, index=False):  # noqa: ANN001
            written["path"] = path
            written["index"] = index
            written["frame"] = self.copy()

        with patch.dict("os.environ", {"LOCAL_US_PARQUET_DIR": "/tmp/us-cache"}, clear=False):
            with patch.object(pd.DataFrame, "to_parquet", fake_to_parquet):
                result = persist_local_us_daily_history("aapl", raw)

        self.assertEqual(result.status, "saved")
        self.assertEqual(result.rows, 1)
        self.assertEqual(_posix(written["path"]), "/tmp/us-cache/AAPL.parquet")
        self.assertEqual(written["index"], False)
        saved_frame = written["frame"]
        self.assertEqual(list(saved_frame["date"].dt.strftime("%Y-%m-%d")), ["2026-01-02"])
        self.assertEqual(float(saved_frame["adjusted_close"].iloc[0]), 100.5)

    def test_persist_local_us_daily_history_rejects_non_us_symbol_without_write(self) -> None:
        raw = pd.DataFrame(
            [{"date": "2026-01-02", "open": 1, "high": 1, "low": 1, "close": 1}]
        )

        with patch.object(pd.DataFrame, "to_parquet", side_effect=AssertionError("should not write")):
            result = persist_local_us_daily_history("600519", raw)

        self.assertEqual(result.status, "not_applicable")


if __name__ == "__main__":
    unittest.main()
