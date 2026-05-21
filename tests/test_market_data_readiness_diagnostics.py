# -*- coding: utf-8 -*-
"""Tests for local-only market data readiness diagnostics."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
import requests

from src.services.market_data_readiness_diagnostics import build_market_data_readiness_diagnostics


ALL_OPTIONAL_MODULES = {"pyarrow", "fastparquet", "tushare", "pytdx", "akshare", "efinance"}


def _spec_finder_with(available_modules: set[str], seen: list[str] | None = None):
    def _finder(module_name: str):
        if seen is not None:
            seen.append(module_name)
        return object() if module_name in available_modules else None

    return _finder


def _find_check(payload: dict, check_id: str) -> dict:
    return next(check for check in payload["checks"] if check["id"] == check_id)


def _assert_path_not_disclosed(payload: dict, path: Path) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)

    assert str(path) not in serialized
    assert str(path.parent) not in serialized


def test_parquet_dir_missing_reports_misconfigured(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing-us-parquet"

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(missing_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with(ALL_OPTIONAL_MODULES),
    ).to_dict()

    parquet_check = _find_check(payload, "local_us_parquet_dir")

    assert payload["readinessStatus"] == "misconfigured"
    assert parquet_check["status"] == "misconfigured"
    assert parquet_check["details"]["envKey"] == "LOCAL_US_PARQUET_DIR"
    assert parquet_check["details"]["pathConfigured"] is True
    assert parquet_check["details"]["pathBasename"] == "missing-us-parquet"
    assert parquet_check["details"]["storageKind"] == "local_filesystem"
    _assert_path_not_disclosed(payload, missing_dir)


def test_parquet_dir_inspection_error_redacts_configured_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parquet_dir = tmp_path / "private-us-parquet"

    def _raise_os_error(self):
        raise OSError(f"permission denied: {self}")

    monkeypatch.setattr(Path, "exists", _raise_os_error)

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with(ALL_OPTIONAL_MODULES),
    ).to_dict()

    parquet_check = _find_check(payload, "local_us_parquet_dir")

    assert payload["readinessStatus"] == "misconfigured"
    assert parquet_check["status"] == "misconfigured"
    assert parquet_check["details"]["reason"] == "path_inspection_failed"
    assert parquet_check["details"]["errorType"] == "OSError"
    assert parquet_check["details"]["pathConfigured"] is True
    assert parquet_check["details"]["pathBasename"] == "private-us-parquet"
    _assert_path_not_disclosed(payload, parquet_dir)


def test_parquet_dir_set_but_engine_missing_reports_misconfigured(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    engine_check = _find_check(payload, "parquet_engine")

    assert payload["readinessStatus"] == "misconfigured"
    assert engine_check["status"] == "misconfigured"
    assert engine_check["details"]["checkedModules"] == ["pyarrow", "fastparquet"]


def test_parquet_engine_available_reports_ready(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    engine_check = _find_check(payload, "parquet_engine")

    assert payload["readinessStatus"] == "ready"
    assert engine_check["status"] == "ready"
    assert engine_check["details"]["availableModules"] == ["pyarrow"]


def test_tushare_token_missing_reports_boolean_only(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()

    payload = build_market_data_readiness_diagnostics(
        env={"LOCAL_US_PARQUET_DIR": str(parquet_dir)},
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    token_check = _find_check(payload, "tushare_token")

    assert token_check["status"] == "missing"
    assert token_check["secretConfigured"] is False
    assert "envKey" not in token_check.get("details", {})


def test_tushare_token_present_is_redacted_from_payload(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    secret = "super-secret-token"

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": secret,
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    token_check = _find_check(payload, "tushare_token")
    serialized = json.dumps(payload, ensure_ascii=False)

    assert token_check["status"] == "ready"
    assert token_check["secretConfigured"] is True
    assert secret not in serialized


def test_representative_file_missing_reports_partial(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    (parquet_dir / "AAPL.parquet").touch()

    payload = build_market_data_readiness_diagnostics(
        representative_symbols=["AAPL", "MSFT"],
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    file_check = _find_check(payload, "local_us_parquet_representative_files")

    assert payload["readinessStatus"] == "partial"
    assert file_check["status"] == "partial"
    assert file_check["details"]["missingSymbols"] == ["MSFT"]
    assert file_check["details"]["existingCount"] == 1


def test_diagnostics_stay_inert_without_network_or_provider_runtime_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    (parquet_dir / "AAPL.parquet").touch()
    seen_modules: list[str] = []

    def _fail_socket(*args, **kwargs):
        raise AssertionError("network call attempted")

    def _fail_request(*args, **kwargs):
        raise AssertionError("http request attempted")

    monkeypatch.setattr(socket, "create_connection", _fail_socket)
    monkeypatch.setattr(requests.sessions.Session, "request", _fail_request)

    payload = build_market_data_readiness_diagnostics(
        representative_symbols=["AAPL"],
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}, seen_modules),
    ).to_dict()

    assert payload["diagnosticOnly"] is True
    assert payload["providerRuntimeCalled"] is False
    assert payload["networkCallsEnabled"] is False
    assert seen_modules == ["pyarrow", "fastparquet", "tushare", "pytdx", "akshare", "efinance"]
