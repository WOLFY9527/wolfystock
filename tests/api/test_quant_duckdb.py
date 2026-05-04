# -*- coding: utf-8 -*-
"""API coverage for optional DuckDB quant analytics endpoints."""

from __future__ import annotations

import pytest

from api.deps import CurrentUser
from api.v1.schemas.quant import (
    QuantDuckDBBuildFactorsRequest,
    QuantDuckDBCompareRuntimeContextRequest,
    QuantDuckDBFactorSnapshotRequest,
    QuantDuckDBIngestRequest,
    QuantDuckDBInitRequest,
    QuantDuckDBValidateFactorPathRequest,
    QuantOHLCVRow,
)
from api.v1.endpoints import quant
from src.services.quant_analytics.duckdb_service import QuantDuckDBService


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def test_health_endpoint_returns_safe_disabled_status(tmp_path) -> None:
    db_path = tmp_path / "quant.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    payload = quant.get_duckdb_health(service=service, _admin=_admin_user()).model_dump(by_alias=True)

    assert payload["enabled"] is False
    assert payload["status"] == "disabled"
    assert payload["schemaInitialized"] is False
    assert "databasePath" in payload
    assert str(tmp_path) not in payload["databasePath"]
    assert not db_path.exists()


def test_benchmark_endpoint_returns_unavailable_when_disabled(tmp_path) -> None:
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=False)

    payload = quant.run_duckdb_benchmark(service=service, _admin=_admin_user()).model_dump(by_alias=True)

    assert payload["status"] == "disabled"
    assert payload["engine"] == "duckdb"
    assert payload["factorRows"] == 0


def test_init_endpoint_creates_schema_when_enabled(tmp_path) -> None:
    pytest.importorskip("duckdb")
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)

    payload = quant.initialize_duckdb_schema(
        request=QuantDuckDBInitRequest(),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)

    assert payload["status"] == "ok"
    assert payload["schemaInitialized"] is True
    assert service.health()["schemaInitialized"] is True


def test_ingest_build_coverage_and_benchmark_endpoints_use_payload_rows(tmp_path) -> None:
    pytest.importorskip("duckdb")
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    quant.initialize_duckdb_schema(
        request=QuantDuckDBInitRequest(),
        service=service,
        _admin=_admin_user(),
    )
    rows = [
        QuantOHLCVRow(
            symbol="AAA",
            tradeDate=f"2026-01-{day:02d}",
            open=10 + day,
            high=11 + day,
            low=9 + day,
            close=10 + day,
            volume=1000 + day,
            source="pytest",
        )
        for day in range(1, 23)
    ]

    ingest_payload = quant.ingest_duckdb_ohlcv(
        request=QuantDuckDBIngestRequest(source="payload", rows=rows),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)
    build_payload = quant.build_duckdb_factors(
        request=QuantDuckDBBuildFactorsRequest(symbols=["AAA"]),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)
    coverage_payload = quant.get_duckdb_coverage(service=service, _admin=_admin_user()).model_dump(by_alias=True)
    benchmark_payload = quant.run_duckdb_benchmark(service=service, _admin=_admin_user()).model_dump(by_alias=True)

    assert ingest_payload["status"] == "ok"
    assert ingest_payload["ingestedRows"] == 22
    assert build_payload["status"] == "ok"
    assert build_payload["factorRows"] == 22
    assert coverage_payload["totalOhlcvRows"] == 22
    assert coverage_payload["totalFactorRows"] == 22
    assert benchmark_payload["status"] == "ok"
    assert benchmark_payload["dataMode"] == "real"
    assert benchmark_payload["rowsScanned"] == 22


def test_factor_snapshot_endpoint_returns_validation_context(tmp_path) -> None:
    pytest.importorskip("duckdb")
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    quant.initialize_duckdb_schema(request=QuantDuckDBInitRequest(), service=service, _admin=_admin_user())
    rows = [
        QuantOHLCVRow(
            symbol="AAA",
            tradeDate=f"2026-01-{day:02d}",
            open=10 + day,
            high=11 + day,
            low=9 + day,
            close=10 + day,
            volume=1000 + day,
            source="pytest",
        )
        for day in range(1, 23)
    ]
    quant.ingest_duckdb_ohlcv(
        request=QuantDuckDBIngestRequest(source="payload", rows=rows),
        service=service,
        _admin=_admin_user(),
    )
    quant.build_duckdb_factors(
        request=QuantDuckDBBuildFactorsRequest(symbols=["AAA"]),
        service=service,
        _admin=_admin_user(),
    )

    payload = quant.get_duckdb_factor_snapshot(
        request=QuantDuckDBFactorSnapshotRequest(
            symbols=["AAA", "MISSING"],
            asOfDate="2026-01-22",
            lookbackDays=2,
            factors=["return_1d", "factor_score"],
        ),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)

    assert payload["status"] == "ok"
    assert payload["dataMode"] == "real"
    assert payload["rowCount"] == 2
    assert payload["missingSymbols"] == ["MISSING"]
    assert payload["coverage"]["coveredSymbols"] == 1
    assert payload["snapshots"]


def test_validate_factor_path_endpoint_reports_data_mode_and_coverage(tmp_path) -> None:
    pytest.importorskip("duckdb")
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    quant.initialize_duckdb_schema(request=QuantDuckDBInitRequest(), service=service, _admin=_admin_user())

    payload = quant.validate_duckdb_factor_path(
        request=QuantDuckDBValidateFactorPathRequest(symbols=["AAA"], startDate="2026-01-01", endDate="2026-01-03"),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)

    assert payload["status"] == "empty"
    assert payload["dataMode"] == "empty"
    assert payload["coverage"]["requestedSymbols"] == 1
    assert payload["coverage"]["coveredSymbols"] == 0
    assert payload["missingSymbols"] == ["AAA"]


def test_compare_runtime_context_endpoint_is_disabled_without_writing(tmp_path) -> None:
    db_path = tmp_path / "disabled.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    payload = quant.compare_duckdb_runtime_context(
        request=QuantDuckDBCompareRuntimeContextRequest(symbols=["AAA"], scannerSnapshot={"AAA": {"score": 80}}),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)

    assert payload["status"] == "disabled"
    assert payload["dataMode"] == "disabled"
    assert payload["diagnostics"]["productionRuntimeChanged"] is False
    assert not db_path.exists()


def test_ingest_endpoint_disabled_does_not_write_database(tmp_path) -> None:
    db_path = tmp_path / "disabled.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    payload = quant.ingest_duckdb_ohlcv(
        request=QuantDuckDBIngestRequest(
            source="payload",
            rows=[
                QuantOHLCVRow(
                    symbol="AAA",
                    tradeDate="2026-01-01",
                    open=1,
                    high=2,
                    low=1,
                    close=2,
                    volume=100,
                )
            ],
        ),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)

    assert payload["status"] == "disabled"
    assert payload["ingestedRows"] == 0
    assert not db_path.exists()
