# -*- coding: utf-8 -*-
"""API coverage for optional DuckDB quant analytics endpoints."""

from __future__ import annotations

import pytest

from api.deps import CurrentUser
from api.v1.schemas.quant import QuantDuckDBInitRequest
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
