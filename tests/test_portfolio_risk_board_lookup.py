# -*- coding: utf-8 -*-
"""Unit tests for the portfolio risk board lookup adapter seam."""

from __future__ import annotations

import builtins
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_risk_board_lookup import PortfolioRiskBoardLookup


class PortfolioRiskBoardLookupTestCase(unittest.TestCase):
    def test_fetch_belong_boards_import_failure_fails_open(self) -> None:
        adapter = PortfolioRiskBoardLookup()
        original_import = builtins.__import__

        def raising_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "data_provider.base":
                raise RuntimeError("provider init failed")
            return original_import(name, globals, locals, fromlist, level)

        with unittest.mock.patch("builtins.__import__", side_effect=raising_import):
            self.assertEqual(adapter.fetch_belong_boards("600519"), [])
            self.assertEqual(adapter.fetch_belong_boards("600519"), [])

        self.assertEqual(adapter._data_manager_init_error, "provider init failed")

    def test_fetch_belong_boards_uses_lazy_per_instance_manager_cache(self) -> None:
        manager_instances: list[FakeManager] = []

        class FakeManager:
            def __init__(self) -> None:
                self.calls: list[str] = []
                manager_instances.append(self)

            def get_belong_boards(self, symbol: str):
                self.calls.append(symbol)
                return [{"name": "白酒", "type": "行业"}]

        fake_package = types.ModuleType("data_provider")
        fake_package.__path__ = []
        fake_module = types.ModuleType("data_provider.base")
        fake_module.DataFetcherManager = FakeManager
        fake_package.base = fake_module

        with unittest.mock.patch.dict(
            sys.modules,
            {"data_provider": fake_package, "data_provider.base": fake_module},
        ):
            first_adapter = PortfolioRiskBoardLookup()
            second_adapter = PortfolioRiskBoardLookup()

            self.assertEqual(first_adapter.fetch_belong_boards("600519"), [{"name": "白酒", "type": "行业"}])
            self.assertEqual(first_adapter.fetch_belong_boards("000001"), [{"name": "白酒", "type": "行业"}])
            self.assertEqual(second_adapter.fetch_belong_boards("300750"), [{"name": "白酒", "type": "行业"}])

        self.assertEqual(len(manager_instances), 2)
        self.assertEqual(manager_instances[0].calls, ["600519", "000001"])
        self.assertEqual(manager_instances[1].calls, ["300750"])

    def test_fetch_belong_boards_non_list_result_returns_empty_list(self) -> None:
        adapter = PortfolioRiskBoardLookup()
        adapter._data_manager = SimpleNamespace(get_belong_boards=lambda _symbol: {"name": "白酒"})

        self.assertEqual(adapter.fetch_belong_boards("600519"), [])

    def test_fetch_belong_boards_provider_lookup_exceptions_bubble(self) -> None:
        adapter = PortfolioRiskBoardLookup()
        adapter._data_manager = SimpleNamespace(get_belong_boards=MagicMock(side_effect=ValueError("lookup failed")))

        with self.assertRaisesRegex(ValueError, "lookup failed"):
            adapter.fetch_belong_boards("600519")

    def test_portfolio_risk_service_fetch_belong_boards_uses_constructor_injected_lookup(self) -> None:
        fake_lookup = SimpleNamespace(fetch_belong_boards=MagicMock(return_value=[{"name": "白酒", "type": "行业"}]))
        service = PortfolioRiskService(
            repo=MagicMock(),
            portfolio_service=MagicMock(),
            config=SimpleNamespace(),
            board_lookup=fake_lookup,
        )

        result = service._fetch_belong_boards("600519")

        self.assertEqual(result, [{"name": "白酒", "type": "行业"}])
        fake_lookup.fetch_belong_boards.assert_called_once_with("600519")


if __name__ == "__main__":
    unittest.main()
