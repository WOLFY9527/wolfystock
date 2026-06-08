# -*- coding: utf-8 -*-
"""Focused tests for DatabaseManager DB URL log redaction."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from src.storage import DatabaseManager, _redact_db_url_for_log


def test_database_manager_initialization_log_redacts_sensitive_sqlite_query_values(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    DatabaseManager.reset_instance()
    db_path = tmp_path / "redaction.sqlite"
    credential_value = "unit-test-not-a-real-db-credential"
    token_value = "unit-test-not-a-real-auth-value"
    db_url = f"sqlite:///{db_path}?password={credential_value}&token={token_value}&mode=ro"

    try:
        with caplog.at_level(logging.INFO, logger="src.storage"):
            DatabaseManager(db_url=db_url)
    finally:
        DatabaseManager.reset_instance()

    log_text = caplog.text
    assert "数据库初始化完成:" in log_text
    assert credential_value not in log_text
    assert token_value not in log_text
    assert "password=***" in log_text
    assert "token=***" in log_text
    assert "mode=ro" in log_text


def test_redact_db_url_for_log_masks_postgres_password_and_sensitive_query_values() -> None:
    password_value = "unit-test-not-a-real-pg-credential"
    token_value = "unit-test-not-a-real-query-token"
    secret_value = "unit-test-not-a-real-query-secret"
    db_url = (
        "postgresql+psycopg2://db_user:"
        f"{password_value}@db.example.invalid:5432/wolfy"
        f"?sslmode=require&access_token={token_value}&client_secret={secret_value}"
    )

    redacted = _redact_db_url_for_log(db_url)

    assert password_value not in redacted
    assert token_value not in redacted
    assert secret_value not in redacted
    assert "db_user:***@db.example.invalid:5432" in redacted
    assert "sslmode=require" in redacted
    assert "access_token=***" in redacted
    assert "client_secret=***" in redacted


def test_redact_db_url_for_log_handles_sqlite_paths_and_malformed_strings_safely(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "safe.sqlite"
    sqlite_url = f"sqlite:///{sqlite_path}"

    assert _redact_db_url_for_log(sqlite_url) == sqlite_url
    assert _redact_db_url_for_log("not a url token=unit-test-not-a-real-value") == "not a url token=***"


def test_database_manager_topology_debug_log_redacts_url_values(caplog: pytest.LogCaptureFixture) -> None:
    DatabaseManager.reset_instance()
    password_value = "unit-test-not-a-real-debug-credential"
    token_value = "unit-test-not-a-real-debug-token"
    topology = {
        "primary_runtime": "sqlite",
        "postgres_bridge": {
            "enabled": False,
            "url": f"postgresql://db_user:{password_value}@db.example.invalid/wolfy?token={token_value}",
        },
        "stores": {
            "phase_f": {"enabled": False, "mode": "disabled"},
            "phase_g": {"enabled": False, "mode": "disabled"},
        },
    }

    try:
        with patch.object(DatabaseManager, "describe_database_topology", return_value=topology):
            with caplog.at_level(logging.DEBUG, logger="src.storage"):
                DatabaseManager(db_url="sqlite:///:memory:")
    finally:
        DatabaseManager.reset_instance()

    log_text = caplog.text
    assert "数据库拓扑详情:" in log_text
    assert password_value not in log_text
    assert token_value not in log_text
    assert "db_user:***@db.example.invalid" in log_text
    assert "token=***" in log_text
