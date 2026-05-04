# -*- coding: utf-8 -*-
"""Tests for the optional DuckDB quant analytics service."""

from __future__ import annotations

import importlib
from datetime import date, timedelta

import pytest

from src.services.quant_analytics.duckdb_service import QuantDuckDBService


def _sample_rows(symbol: str = "AAA", days: int = 25) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for offset in range(days):
        close = float(offset + 1)
        rows.append(
            {
                "symbol": symbol,
                "trade_date": start + timedelta(days=offset),
                "open": close - 0.5,
                "high": close + 0.5,
                "low": close - 1.0,
                "close": close,
                "volume": 1000 + offset,
                "amount": close * (1000 + offset),
                "market": "US",
                "sector": "Tech",
                "source": "pytest",
            }
        )
    return rows


def _require_duckdb() -> None:
    pytest.importorskip("duckdb")


def test_disabled_service_health_does_not_create_database_file(tmp_path) -> None:
    db_path = tmp_path / "quant" / "wolfystock.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    health = service.health()

    assert health["enabled"] is False
    assert health["status"] == "disabled"
    assert health["schemaInitialized"] is False
    assert not db_path.exists()


def test_missing_duckdb_import_is_reported(tmp_path, monkeypatch) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "duckdb":
            raise ModuleNotFoundError("No module named 'duckdb'")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    service = QuantDuckDBService(database_path=str(tmp_path / "missing.duckdb"), enabled=True)

    health = service.health()

    assert health["available"] is False
    assert health["status"] == "unavailable"
    assert "duckdb" in health["error"].lower()


def test_initialize_schema_creates_tables(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)

    result = service.initialize_schema()

    assert result["status"] == "ok"
    health = service.health()
    assert health["schemaInitialized"] is True


def test_ingest_ohlcv_sample_rows(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()

    result = service.ingest_ohlcv_rows(_sample_rows(days=5))

    assert result == {"status": "ok", "ingestedRows": 5, "symbolCount": 1}


def test_build_basic_factors_and_ma_values_are_deterministic(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv_rows(_sample_rows(days=25))

    result = service.build_basic_factors()

    assert result["status"] == "ok"
    assert result["factorRows"] == 25
    rows = service.query_signal_candidates(as_of_date="2026-01-20", limit=1)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAA"
    assert rows[0]["ma5"] == pytest.approx(18.0)
    assert rows[0]["ma20"] == pytest.approx(10.5)


def test_benchmark_returns_elapsed_and_counts(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv_rows(_sample_rows("AAA", 25) + _sample_rows("BBB", 25))
    service.build_basic_factors()

    result = service.benchmark_factor_query(symbol_limit=1)

    assert result["status"] == "ok"
    assert result["engine"] == "duckdb"
    assert result["elapsedMs"] >= 0
    assert result["factorRows"] == 25
    assert result["symbolCount"] == 1
    assert result["dateCount"] == 25


def test_empty_queries_return_clear_status(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()

    factor_result = service.build_basic_factors()
    benchmark = service.benchmark_factor_query()
    candidates = service.query_signal_candidates(limit=10)

    assert factor_result["status"] == "empty"
    assert factor_result["factorRows"] == 0
    assert benchmark["status"] == "empty"
    assert benchmark["factorRows"] == 0
    assert candidates == []
