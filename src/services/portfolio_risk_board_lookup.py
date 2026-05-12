# -*- coding: utf-8 -*-
"""Tiny provider adapter for portfolio risk CN board lookup."""

from __future__ import annotations

from typing import Any


class PortfolioRiskBoardLookup:
    """Fail-open adapter for CN board membership lookup."""

    def __init__(self) -> None:
        self._data_manager = None
        self._data_manager_init_error = ""

    def fetch_belong_boards(self, symbol: str) -> list[dict[str, Any]]:
        manager = self._get_data_manager()
        if manager is None:
            return []
        result = manager.get_belong_boards(symbol)
        if isinstance(result, list):
            return result
        return []

    def _get_data_manager(self):
        if self._data_manager is not None:
            return self._data_manager
        if self._data_manager_init_error:
            return None
        try:
            from data_provider.base import DataFetcherManager

            self._data_manager = DataFetcherManager()
            return self._data_manager
        except Exception as exc:  # pragma: no cover - fail-open initialization
            self._data_manager_init_error = str(exc)
            return None
