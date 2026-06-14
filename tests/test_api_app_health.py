# -*- coding: utf-8 -*-
"""Tests for app liveness/readiness and task queue lifecycle wiring."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.app as api_app
from api.app import create_app


class _SessionStub:
    def __init__(self) -> None:
        self.executed = []

    def execute(self, statement):
        self.executed.append(str(statement))
        return 1

    def close(self) -> None:
        return None


class _DatabaseStub:
    def __init__(self) -> None:
        self.session = _SessionStub()

    def get_session(self):
        return self.session


class _BrokenDatabaseStub:
    def get_session(self):
        raise RuntimeError(
            "OperationalError postgres://raw-user:raw-password@db.example.test/wolfystock "
            "/Users/example/app.py raw-secret-token"
        )


class _QueueStub:
    def __init__(self, runtime_status: dict | None = None) -> None:
        self.runtime_status = runtime_status or {
            "mode": "process_local",
            "single_process_required": True,
            "configured_worker_count": 1,
            "topology_ok": True,
            "shutdown": False,
            "accepting_new_tasks": True,
            "worker_hints": {},
        }
        self.shutdown_calls = []

    def get_runtime_status(self) -> dict:
        return dict(self.runtime_status)

    def shutdown(self, *, wait: bool = False, cancel_futures: bool = True) -> None:
        self.shutdown_calls.append((wait, cancel_futures))


def _forbidden_startup_call(label: str):
    def _raise(*_args, **_kwargs):
        raise AssertionError(f"{label} should not run during app creation/startup")

    return _raise


def _forbid_market_overview_startup_calls(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.market_cache.MarketCache.get_or_refresh",
        _forbidden_startup_call("MarketCache prewarm"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.ExecutionLogService.record_market_overview_fetch",
        _forbidden_startup_call("market overview fetch logging"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_binance_ticker_snapshot",
        _forbidden_startup_call("binance market overview provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_binance_funding_row",
        _forbidden_startup_call("binance funding provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_binance_kline_history_rows",
        _forbidden_startup_call("binance kline provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_alternative_fear_greed_payload",
        _forbidden_startup_call("alternative sentiment provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_cnn_fear_greed_payload",
        _forbidden_startup_call("cnn sentiment provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_sina_cn_index_rows",
        _forbidden_startup_call("sina cn indices provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_tickflow_cn_breadth_snapshot",
        _forbidden_startup_call("tickflow breadth provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_yfinance_quote_history_frame",
        _forbidden_startup_call("yfinance quote provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_yfinance_spy_atr_history_frame",
        _forbidden_startup_call("yfinance atr provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_fred_observation_points",
        _forbidden_startup_call("fred macro provider"),
    )
    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_treasury_daily_rate_observation_points",
        _forbidden_startup_call("treasury macro provider"),
    )


def _assert_public_health_payload_is_safe(payload: dict) -> None:
    text = str(payload).lower()
    forbidden_markers = (
        "checks",
        "warnings",
        "detail",
        "worker_hints",
        "configured_worker_count",
        "single_process_required",
        "launchverdict",
        "postgres://",
        "raw-password",
        "raw-secret-token",
        "/users/",
        "runtimeerror",
        "operationalerror",
        "traceback",
    )
    for marker in forbidden_markers:
        assert marker not in text


class ApiAppHealthTestCase(unittest.TestCase):
    def _make_app(self, *, queue_stub: _QueueStub | None = None, db_stub: _DatabaseStub | None = None):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        static_dir = Path(temp_dir.name)
        queue = queue_stub or _QueueStub()
        db = db_stub or _DatabaseStub()
        service = object()
        patches = [
            patch("api.app.SystemConfigService", return_value=service),
            patch("api.app.get_task_queue", return_value=queue),
            patch("api.app.get_db", return_value=db),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        app = create_app(static_dir=static_dir)
        return app, queue, db

    def test_live_health_endpoint_reports_process_alive(self) -> None:
        app, _, _ = self._make_app()

        with TestClient(app) as client:
            response = client.get("/api/health/live")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "live")
        self.assertIs(payload["ready"], True)
        self.assertNotIn("checks", payload)
        self.assertNotIn("warnings", payload)

    def test_ready_health_endpoint_checks_storage_and_queue_topology(self) -> None:
        app, _, db = self._make_app()

        with TestClient(app) as client:
            response = client.get("/api/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["mode"], "ready")
        self.assertIs(payload["ready"], True)
        _assert_public_health_payload_is_safe(payload)
        self.assertTrue(db.session.executed)

    def test_default_health_alias_uses_readiness_contract(self) -> None:
        app, _, _ = self._make_app()

        with TestClient(app) as client:
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "ready")
        self.assertEqual(payload["status"], "ready")
        self.assertIs(payload["ready"], True)
        _assert_public_health_payload_is_safe(payload)

    def test_ready_health_returns_503_when_task_queue_topology_is_unsafe(self) -> None:
        queue = _QueueStub(
            runtime_status={
                "mode": "process_local",
                "single_process_required": True,
                "configured_worker_count": 2,
                "topology_ok": False,
                "shutdown": False,
                "accepting_new_tasks": True,
                "worker_hints": {"WEB_CONCURRENCY": 2},
            }
        )
        app, _, _ = self._make_app(queue_stub=queue)

        with TestClient(app) as client:
            response = client.get("/api/health/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertIs(payload["ready"], False)
        _assert_public_health_payload_is_safe(payload)

    def test_ready_health_returns_unavailable_without_leaking_storage_exception(self) -> None:
        app, _, _ = self._make_app(db_stub=_BrokenDatabaseStub())

        with TestClient(app) as client:
            response = client.get("/api/health/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["mode"], "ready")
        self.assertIs(payload["ready"], False)
        _assert_public_health_payload_is_safe(payload)

    def test_ready_health_reports_maintenance_without_queue_diagnostics(self) -> None:
        queue = _QueueStub(
            runtime_status={
                "mode": "process_local",
                "single_process_required": True,
                "configured_worker_count": 1,
                "topology_ok": True,
                "shutdown": True,
                "accepting_new_tasks": False,
                "worker_hints": {"WEB_CONCURRENCY": 1},
            }
        )
        app, _, _ = self._make_app(queue_stub=queue)

        with TestClient(app) as client:
            response = client.get("/api/health/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "maintenance")
        self.assertIs(payload["ready"], False)
        _assert_public_health_payload_is_safe(payload)

    def test_ready_health_reports_unknown_without_raw_internal_details(self) -> None:
        app, _, _ = self._make_app()

        with patch("api.app._storage_readiness_check", return_value=(False, {"status": "mystery"})):
            with TestClient(app) as client:
                response = client.get("/api/health/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "unknown")
        self.assertIs(payload["ready"], False)
        _assert_public_health_payload_is_safe(payload)

    def test_app_lifespan_shuts_down_task_queue_explicitly(self) -> None:
        queue = _QueueStub()
        app, _, _ = self._make_app(queue_stub=queue)

        with TestClient(app) as client:
            response = client.get("/api/health/live")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(queue.shutdown_calls, [(False, True)])


def test_importing_api_app_does_not_trigger_market_overview_providers_or_prewarm(monkeypatch) -> None:
    _forbid_market_overview_startup_calls(monkeypatch)

    reloaded = importlib.reload(api_app)

    assert reloaded.app is not None


def test_create_app_does_not_trigger_market_overview_providers_or_prewarm(monkeypatch, tmp_path: Path) -> None:
    _forbid_market_overview_startup_calls(monkeypatch)

    app = api_app.create_app(static_dir=tmp_path)

    assert app is not None


def test_lifespan_skips_crypto_realtime_startup_when_disabled(monkeypatch, tmp_path: Path) -> None:
    queue = _QueueStub()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("CRYPTO_REALTIME_ENABLED", "0")
    monkeypatch.setattr(api_app, "SystemConfigService", lambda: object())
    monkeypatch.setattr(api_app, "get_task_queue", lambda: queue)
    monkeypatch.setattr(
        api_app,
        "get_crypto_realtime_service",
        _forbidden_startup_call("crypto realtime service"),
    )

    app = api_app.create_app(static_dir=tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert not hasattr(app.state, "crypto_realtime_service")
    assert queue.shutdown_calls == [(False, True)]


if __name__ == "__main__":
    unittest.main()
