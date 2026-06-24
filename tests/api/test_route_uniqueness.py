# -*- coding: utf-8 -*-
"""Regression tests for duplicate FastAPI route registration."""

from __future__ import annotations

import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from api.app import create_app
from tests.api.route_table_helpers import iter_effective_api_routes


class ApiRouteUniquenessTestCase(unittest.TestCase):
    def test_registered_api_routes_have_unique_method_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(static_dir=Path(temp_dir))

        routes_by_method_path: dict[tuple[str, str], list[str]] = defaultdict(list)
        for route in iter_effective_api_routes(app.routes):
            for method in route.methods or set():
                if method in {"HEAD", "OPTIONS"}:
                    continue
                routes_by_method_path[(method, route.path)].append(route.name)

        duplicates = {
            key: names
            for key, names in sorted(routes_by_method_path.items())
            if len(names) > 1
        }

        self.assertEqual(duplicates, {})

    def test_app_route_table_exposes_mac118_api_contract_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(static_dir=Path(temp_dir))

        routes_by_signature = {
            (method, route.path): route.endpoint
            for route in iter_effective_api_routes(app.routes)
            for method in route.methods or set()
            if method not in {"HEAD", "OPTIONS"}
        }

        self.assertEqual(
            {
                ("GET", "/api/v1/admin/historical-ohlcv/cache-preflight"),
                ("GET", "/api/v1/scanner/status"),
                ("GET", "/api/v1/stocks/{stock_code}/structure-decision"),
                ("GET", "/api/v1/backtest/performance"),
            }
            - set(routes_by_signature),
            set(),
        )
