# -*- coding: utf-8 -*-
"""Tests for the optional DuckDB quant analytics service."""

from __future__ import annotations

import importlib
from datetime import date, timedelta
from pathlib import Path

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


def test_disabled_service_health_wins_over_missing_duckdb(tmp_path, monkeypatch) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "duckdb":
            raise ModuleNotFoundError("No module named 'duckdb'")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    db_path = tmp_path / "quant" / "disabled.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    health = service.health()

    assert health["enabled"] is False
    assert health["status"] == "disabled"
    assert health["available"] is False
    assert health["error"] == "DuckDB quant engine is disabled"
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


def test_enabled_missing_database_read_diagnostics_do_not_create_file(tmp_path) -> None:
    _require_duckdb()
    db_path = tmp_path / "missing.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=True)

    health = service.health()
    coverage = service.get_coverage()
    benchmark = service.benchmark_factor_query()
    candidates = service.query_signal_candidates()

    assert health["status"] == "empty"
    assert health["available"] is True
    assert health["schemaInitialized"] is False
    assert coverage["status"] == "empty"
    assert coverage["emptyReason"] == "DuckDB database does not exist"
    assert benchmark["status"] == "empty"
    assert benchmark["dataMode"] == "empty"
    assert candidates == []
    assert not db_path.exists()


def test_corrupt_database_read_diagnostics_return_sanitized_unavailable(tmp_path) -> None:
    _require_duckdb()
    db_path = tmp_path / "corrupt.duckdb"
    db_path.write_bytes(b"not a duckdb database")
    service = QuantDuckDBService(database_path=str(db_path), enabled=True)

    health = service.health()
    coverage = service.get_coverage()
    benchmark = service.benchmark_factor_query()
    snapshot = service.get_factor_snapshot(symbols=["AAA"])
    validation = service.validate_factor_coverage(symbols=["AAA"])

    for payload in (health, coverage, benchmark, snapshot, validation):
        assert payload["status"] == "unavailable"
        assert payload["error"] == "DuckDB database is unavailable: corrupt_or_unreadable"
        assert str(tmp_path) not in payload["error"]
        assert "Traceback" not in payload["error"]


def test_permission_denied_read_diagnostic_returns_sanitized_unavailable(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "permission.duckdb"
    db_path.write_bytes(b"")
    service = QuantDuckDBService(database_path=str(db_path), enabled=True)

    monkeypatch.setattr(service, "_duckdb_status", lambda: (True, "test", None))

    def deny_connect(*_args, **_kwargs):
        raise PermissionError(f"permission denied: {db_path}")

    monkeypatch.setattr(service, "_connect", deny_connect)

    health = service.health()
    coverage = service.get_coverage()
    benchmark = service.benchmark_factor_query()

    for payload in (health, coverage, benchmark):
        assert payload["status"] == "unavailable"
        assert payload["error"] == "DuckDB database is unavailable: permission_denied"
        assert str(tmp_path) not in payload["error"]


def test_schema_mismatch_read_diagnostic_returns_sanitized_unavailable(tmp_path) -> None:
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "schema-mismatch.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE ohlcv_daily(symbol TEXT)")
        conn.execute("CREATE TABLE factor_daily(symbol TEXT)")
    service = QuantDuckDBService(database_path=str(db_path), enabled=True)

    coverage = service.get_coverage()
    benchmark = service.benchmark_factor_query()

    for payload in (coverage, benchmark):
        assert payload["status"] == "unavailable"
        assert payload["error"] == "DuckDB database is unavailable: schema_mismatch"
        assert str(tmp_path) not in payload["error"]


def test_concurrent_init_build_boundary_is_documented_as_not_production_ready() -> None:
    database_runbook = " ".join(
        Path("docs/operations/database.md").read_text().split()
    )

    assert "Run only one DuckDB init/ingest/build action at a time during local smoke" in database_runbook
    assert "single-flight" in database_runbook
    assert "not a production readiness claim" in database_runbook


def test_large_payload_ingest_is_bounded_before_normalizing_or_writing_rows(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()

    result = service.ingest_ohlcv(_sample_rows(days=QuantDuckDBService.MAX_PAYLOAD_ROWS + 1))

    assert result["status"] == "invalid_request"
    assert result["ingestedRows"] == 0
    assert result["symbolCount"] == 0
    assert result["error"] == "DuckDB payload ingest row limit exceeded"


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

    result = service.ingest_ohlcv(_sample_rows(days=5))

    assert result["status"] == "ok"
    assert result["ingestedRows"] == 5
    assert result["symbolCount"] == 1
    assert result["durationMs"] >= 0


def test_duplicate_ingest_replaces_rows_without_double_counting(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()

    rows = _sample_rows(days=5)
    first = service.ingest_ohlcv(rows)
    second = service.ingest_ohlcv(rows)
    coverage = service.get_coverage()

    assert first["ingestedRows"] == 5
    assert second["ingestedRows"] == 5
    assert coverage["totalOhlcvRows"] == 5
    assert coverage["symbolCount"] == 1


def test_disabled_ingest_does_not_create_database_file(tmp_path) -> None:
    db_path = tmp_path / "quant" / "disabled.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    result = service.ingest_ohlcv(_sample_rows(days=2))

    assert result["status"] == "disabled"
    assert not db_path.exists()


def test_build_basic_factors_and_ma_values_are_deterministic(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv(_sample_rows(days=25))

    result = service.build_basic_factors()

    assert result["status"] == "ok"
    assert result["factorRows"] == 25
    rows = service.query_signal_candidates(as_of_date="2026-01-20", limit=1)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAA"
    assert rows[0]["ma5"] == pytest.approx(18.0)
    assert rows[0]["ma20"] == pytest.approx(10.5)
    assert rows[0]["return1d"] == pytest.approx(1 / 19)
    assert rows[0]["closeVsMa20"] == pytest.approx(20.0 / 10.5 - 1)


def test_coverage_reports_ohlcv_and_factor_state(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv(_sample_rows("AAA", 25) + _sample_rows("BBB", 10))
    service.build_basic_factors()

    result = service.get_coverage(sample_limit=2)

    assert result["status"] == "ok"
    assert result["totalOhlcvRows"] == 35
    assert result["totalFactorRows"] == 35
    assert result["symbolCount"] == 2
    assert result["minTradeDate"] == "2026-01-01"
    assert result["maxTradeDate"] == "2026-01-25"
    assert result["latestFactorDate"] == "2026-01-25"
    assert len(result["symbols"]) == 2


def test_ingest_ohlcv_from_existing_store_is_bounded_and_dry_run_safe(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True, max_benchmark_symbols=1)
    service.initialize_schema()

    class FakeRow:
        def __init__(self, code: str, offset: int) -> None:
            self.code = code
            self.date = date(2026, 1, 1) + timedelta(days=offset)
            self.open = 10.0 + offset
            self.high = 11.0 + offset
            self.low = 9.0 + offset
            self.close = 10.5 + offset
            self.volume = 1000 + offset
            self.amount = self.close * self.volume
            self.data_source = "stock_daily"

    class FakeRepo:
        def list_distinct_codes(self) -> list[str]:
            return ["AAA", "BBB"]

        def get_recent_daily_rows(self, *, code: str, limit: int) -> list[FakeRow]:
            return [FakeRow(code, 1), FakeRow(code, 0)]

    dry_run = service.ingest_ohlcv_from_existing_store(stock_repository=FakeRepo(), dry_run=True)
    coverage_after_dry_run = service.get_coverage()
    ingested = service.ingest_ohlcv_from_existing_store(stock_repository=FakeRepo())
    coverage_after_ingest = service.get_coverage()

    assert dry_run["status"] == "dry_run"
    assert dry_run["symbolCount"] == 1
    assert dry_run["availableRows"] == 2
    assert coverage_after_dry_run["totalOhlcvRows"] == 0
    assert ingested["status"] == "ok"
    assert ingested["ingestedRows"] == 2
    assert coverage_after_ingest["totalOhlcvRows"] == 2


def test_benchmark_returns_elapsed_and_counts(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv(_sample_rows("AAA", 25) + _sample_rows("BBB", 25))
    service.build_basic_factors()

    result = service.benchmark_factor_query(symbol_limit=1)

    assert result["status"] == "ok"
    assert result["engine"] == "duckdb"
    assert result["elapsedMs"] >= 0
    assert result["durationMs"] >= 0
    assert result["factorRows"] == 25
    assert result["rowsScanned"] == 25
    assert result["symbolsScanned"] == 1
    assert result["symbolCount"] == 1
    assert result["dateCount"] == 25
    assert result["dataMode"] == "real"
    assert result["queryType"] == "factor_daily_top_scores"
    assert result["topResults"]


def test_factor_snapshot_reports_requested_symbols_and_missing_symbols(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv(_sample_rows("AAA", 25) + _sample_rows("BBB", 25))
    service.build_basic_factors()

    result = service.get_factor_snapshot(
        symbols=["AAA", "BBB", "MISSING"],
        as_of_date="2026-01-25",
        lookback_days=2,
        factors=["return_1d", "factor_score"],
    )

    assert result["status"] == "ok"
    assert result["dataMode"] == "real"
    assert result["rowCount"] == 4
    assert result["coverage"]["requestedSymbols"] == 3
    assert result["coverage"]["coveredSymbols"] == 2
    assert result["missingSymbols"] == ["MISSING"]
    assert result["factorDates"] == ["2026-01-24", "2026-01-25"]
    assert set(result["factors"]) == {"return_1d", "factor_score"}
    assert {row["symbol"] for row in result["snapshots"]} == {"AAA", "BBB"}
    assert all(set(row["factors"]) == {"return_1d", "factor_score"} for row in result["snapshots"])


def test_factor_snapshot_disabled_does_not_create_database_file(tmp_path) -> None:
    db_path = tmp_path / "disabled" / "quant.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    result = service.get_factor_snapshot(symbols=["AAA"], as_of_date="2026-01-01")

    assert result["status"] == "disabled"
    assert result["dataMode"] == "disabled"
    assert result["rowCount"] == 0
    assert result["missingSymbols"] == ["AAA"]
    assert not db_path.exists()


def test_validate_factor_coverage_reports_insufficient_symbols(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv(_sample_rows("AAA", 25) + _sample_rows("SHORT", 3))
    service.build_basic_factors()

    result = service.validate_factor_coverage(
        symbols=["AAA", "SHORT", "MISSING"],
        start_date="2026-01-01",
        end_date="2026-01-25",
        min_factor_rows=20,
    )

    assert result["status"] == "insufficient"
    assert result["dataMode"] == "real"
    assert result["coverage"]["requestedSymbols"] == 3
    assert result["coverage"]["coveredSymbols"] == 2
    assert result["coverage"]["sufficientSymbols"] == 1
    assert result["missingSymbols"] == ["MISSING"]
    assert result["insufficientSymbols"] == ["SHORT"]
    assert result["rowCount"] == 28


def test_compare_runtime_context_returns_diagnostics_not_decisions(tmp_path) -> None:
    _require_duckdb()
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    service.initialize_schema()
    service.ingest_ohlcv(_sample_rows("AAA", 25))
    service.build_basic_factors()

    result = service.compare_factor_context(
        symbols=["AAA", "MISSING"],
        scanner_snapshot={"AAA": {"score": 88.0}},
        backtest_snapshot={"AAA": {"returnPct": 10.0}},
        date_range={"startDate": "2026-01-20", "endDate": "2026-01-25"},
    )

    assert result["status"] == "insufficient"
    assert result["dataMode"] == "real"
    assert result["runtimeContexts"] == ["scanner", "backtest"]
    assert result["diagnostics"]["missingSymbols"] == ["MISSING"]
    assert result["diagnostics"]["productionRuntimeChanged"] is False
    assert "decision" not in result


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
