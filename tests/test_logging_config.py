# -*- coding: utf-8 -*-
"""Runtime file logging sink and redaction tests."""

from __future__ import annotations

import logging
from pathlib import Path

from src.logging_config import ensure_runtime_file_logging, redact_log_metadata


def _remove_handlers(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def test_ensure_runtime_file_logging_adds_dated_local_sink_without_replacing_console(tmp_path: Path) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    _remove_handlers(root)
    console_handler = logging.StreamHandler()
    root.addHandler(console_handler)

    try:
        result = ensure_runtime_file_logging(log_prefix="api_server", log_dir=str(tmp_path), today="20260617")

        assert result["enabled"] is True
        assert result["status"] == "active"
        assert result["path"] == str(tmp_path / "api_server_20260617.log")
        assert console_handler in root.handlers
        assert any(
            isinstance(handler, logging.FileHandler)
            and Path(str(getattr(handler, "baseFilename", ""))) == tmp_path / "api_server_20260617.log"
            for handler in root.handlers
        )

        logging.getLogger("tests.runtime_logging").info("runtime sink smoke")
        logging.getLogger("tests.runtime_logging").warning("Authorization: Bearer raw-token")
        for handler in root.handlers:
            handler.flush()
        log_text = (tmp_path / "api_server_20260617.log").read_text(encoding="utf-8")
        assert "runtime sink smoke" in log_text
        assert "raw-token" not in log_text
        assert "<redacted>" in log_text
    finally:
        _remove_handlers(root)
        for handler in original_handlers:
            root.addHandler(handler)


def test_ensure_runtime_file_logging_is_idempotent_for_same_target(tmp_path: Path) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    _remove_handlers(root)

    try:
        first = ensure_runtime_file_logging(log_prefix="api_server", log_dir=str(tmp_path), today="20260617")
        second = ensure_runtime_file_logging(log_prefix="api_server", log_dir=str(tmp_path), today="20260617")

        target = str(tmp_path / "api_server_20260617.log")
        matching_handlers = [
            handler
            for handler in root.handlers
            if isinstance(handler, logging.FileHandler) and str(getattr(handler, "baseFilename", "")) == target
        ]
        assert first["status"] == "active"
        assert second["status"] == "active"
        assert second["alreadyConfigured"] is True
        assert len(matching_handlers) == 1
    finally:
        _remove_handlers(root)
        for handler in original_handlers:
            root.addHandler(handler)


def test_redact_log_metadata_removes_sensitive_headers_tokens_and_passwords() -> None:
    payload = {
        "Authorization": "Bearer raw-token",
        "Cookie": "dsa_session=raw-session",
        "Set-Cookie": "dsa_session=raw-session",
        "api_key": "provider-key",
        "password": "plain-password",
        "nested": {
            "sessionId": "session-123",
            "safe": "metadata-only",
            "items": [{"token": "abc"}, {"status": "ok"}],
        },
    }

    redacted = redact_log_metadata(payload)
    text = str(redacted).lower()

    assert "raw-token" not in text
    assert "raw-session" not in text
    assert "provider-key" not in text
    assert "plain-password" not in text
    assert redacted["Authorization"] == "<redacted>"
    assert redacted["Cookie"] == "<redacted>"
    assert redacted["nested"]["safe"] == "metadata-only"
    assert redacted["nested"]["items"][0]["token"] == "<redacted>"
    assert redacted["nested"]["items"][1]["status"] == "ok"
