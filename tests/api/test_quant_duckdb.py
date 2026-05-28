# -*- coding: utf-8 -*-
"""API coverage for optional DuckDB quant analytics endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
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


def _admin_user(*, admin_capabilities: tuple[str, ...] = ()) -> CurrentUser:
    return CurrentUser(
        user_id="admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=admin_capabilities,
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _unauthenticated_user() -> CurrentUser:
    raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})


def _client(*, user_factory, service: QuantDuckDBService) -> TestClient:
    app = FastAPI()
    app.include_router(quant.router, prefix="/api/v1/quant")
    app.dependency_overrides[get_current_user] = user_factory
    app.dependency_overrides[quant.get_quant_duckdb_service] = lambda: service
    return TestClient(app)


def test_health_endpoint_requires_quant_admin_read_capability(tmp_path) -> None:
    db_path = tmp_path / "quant.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    response = _client(
        user_factory=lambda: _admin_user(admin_capabilities=("quant:admin:read",)),
        service=service,
    ).get("/api/v1/quant/duckdb/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["enabled"] is False
    assert payload["status"] == "disabled"
    assert payload["schemaInitialized"] is False
    assert "databasePath" in payload
    assert str(tmp_path) not in payload["databasePath"]
    assert not db_path.exists()


def test_init_endpoint_rejects_read_only_quant_admin_capability(tmp_path) -> None:
    db_path = tmp_path / "quant.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    response = _client(
        user_factory=lambda: _admin_user(admin_capabilities=("quant:admin:read",)),
        service=service,
    ).post("/api/v1/quant/duckdb/init", json={})

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "admin_capability_required"
    assert "quant:admin:write" not in response.text
    assert not db_path.exists()


def test_init_endpoint_accepts_quant_admin_write_capability_without_enabling_duckdb(tmp_path) -> None:
    db_path = tmp_path / "quant.duckdb"
    service = QuantDuckDBService(database_path=str(db_path), enabled=False)

    response = _client(
        user_factory=lambda: _admin_user(admin_capabilities=("quant:admin:write",)),
        service=service,
    ).post("/api/v1/quant/duckdb/init", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "disabled"
    assert payload["engine"] == "duckdb"
    assert payload["schemaInitialized"] is False
    assert not db_path.exists()


def test_quant_duckdb_routes_keep_unauthenticated_and_non_capable_requests_rejected(tmp_path) -> None:
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=False)

    unauthenticated = _client(user_factory=_unauthenticated_user, service=service).get("/api/v1/quant/duckdb/health")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["detail"]["error"] == "unauthorized"

    forbidden = _client(user_factory=_regular_user, service=service).get("/api/v1/quant/duckdb/health")
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["error"] == "admin_required"


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


def test_coverage_endpoint_returns_sanitized_unavailable_for_corrupt_database(tmp_path) -> None:
    pytest.importorskip("duckdb")
    db_path = tmp_path / "corrupt.duckdb"
    db_path.write_bytes(b"not a duckdb database")
    service = QuantDuckDBService(database_path=str(db_path), enabled=True)

    payload = quant.get_duckdb_coverage(service=service, _admin=_admin_user()).model_dump(by_alias=True)

    assert payload["status"] == "unavailable"
    assert payload["error"] == "DuckDB database is unavailable: corrupt_or_unreadable"
    assert str(tmp_path) not in payload["error"]
    assert "Traceback" not in payload["error"]


def test_benchmark_endpoint_returns_unavailable_when_disabled(tmp_path) -> None:
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=False)

    payload = quant.run_duckdb_benchmark(service=service, _admin=_admin_user()).model_dump(by_alias=True)

    assert payload["status"] == "disabled"
    assert payload["engine"] == "duckdb"
    assert payload["factorRows"] == 0


def test_payload_ingest_endpoint_rejects_oversized_payload(tmp_path) -> None:
    pytest.importorskip("duckdb")
    service = QuantDuckDBService(database_path=str(tmp_path / "quant.duckdb"), enabled=True)
    quant.initialize_duckdb_schema(request=QuantDuckDBInitRequest(), service=service, _admin=_admin_user())
    rows = [
        QuantOHLCVRow(
            symbol="AAA",
            tradeDate=f"2026-01-{(offset % 28) + 1:02d}",
            open=10,
            high=11,
            low=9,
            close=10,
            volume=1000,
            source="pytest",
        )
        for offset in range(QuantDuckDBService.MAX_PAYLOAD_ROWS + 1)
    ]

    payload = quant.ingest_duckdb_ohlcv(
        request=QuantDuckDBIngestRequest(source="payload", rows=rows),
        service=service,
        _admin=_admin_user(),
    ).model_dump(by_alias=True)

    assert payload["status"] == "invalid_request"
    assert payload["ingestedRows"] == 0
    assert payload["symbolCount"] == 0
    assert payload["error"] == "DuckDB payload ingest row limit exceeded"


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
