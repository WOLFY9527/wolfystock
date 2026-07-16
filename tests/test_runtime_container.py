"""Focused lifecycle and isolation tests for the FastAPI runtime container."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

import api.app as api_app
from api.deps import get_system_config_service

if TYPE_CHECKING:
    from src.runtime.composition import RuntimeContainer


class _QueueResource:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events
        self.shutdown_calls: list[tuple[bool, bool]] = []

    def get_runtime_status(self) -> dict[str, object]:
        return {
            "mode": "process_local",
            "single_process_required": True,
            "configured_worker_count": 1,
            "topology_ok": True,
            "shutdown": False,
            "accepting_new_tasks": True,
            "worker_hints": {},
        }

    def shutdown(self, *, wait: bool = False, cancel_futures: bool = True) -> None:
        self.shutdown_calls.append((wait, cancel_futures))
        self.events.append(f"stop:{self.name}")


class _CryptoResource:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1
        self.events.append(f"stop:{self.name}")


def _build_container(
    name: str,
    events: list[str],
    *,
    fail_crypto_start: bool = False,
) -> tuple[RuntimeContainer, object, _QueueResource, _CryptoResource]:
    from src.runtime.composition import RuntimeContainer

    system_config_service = object()
    queue = _QueueResource(f"{name}:queue", events)
    crypto = _CryptoResource(f"{name}:crypto", events)

    def build_system_config_service() -> object:
        events.append(f"start:{name}:system-config")
        return system_config_service

    def build_task_queue() -> _QueueResource:
        events.append(f"start:{name}:queue")
        return queue

    def build_crypto_realtime_service(*, auto_start: bool) -> _CryptoResource:
        assert auto_start is True
        events.append(f"start:{name}:crypto")
        if fail_crypto_start:
            raise RuntimeError(f"{name} crypto startup failed")
        return crypto

    container = RuntimeContainer(
        system_config_service_factory=build_system_config_service,
        task_queue_factory=build_task_queue,
        crypto_realtime_service_factory=build_crypto_realtime_service,
        should_start_crypto_realtime=lambda: True,
    )
    return container, system_config_service, queue, crypto


def _add_system_config_identity_route(app) -> None:
    @app.get("/_runtime-test/system-config")
    def system_config_identity(service=Depends(get_system_config_service)) -> dict[str, int]:
        return {"identity": id(service)}


def test_runtime_container_preserves_start_order_and_closes_in_reverse_once() -> None:
    events: list[str] = []
    container, system_config_service, queue, crypto = _build_container("one", events)

    container.start()

    assert container.system_config_service is system_config_service
    assert container.task_queue is queue
    assert container.crypto_realtime_service is crypto
    assert events == [
        "start:one:system-config",
        "start:one:queue",
        "start:one:crypto",
    ]

    container.close()
    container.close()

    assert events[-2:] == ["stop:one:crypto", "stop:one:queue"]
    assert crypto.stop_calls == 1
    assert queue.shutdown_calls == [(False, True)]


def test_runtime_container_rolls_back_partial_startup_failure(tmp_path: Path) -> None:
    events: list[str] = []
    container, _, queue, crypto = _build_container(
        "partial",
        events,
        fail_crypto_start=True,
    )
    app = api_app.create_app(container, static_dir=tmp_path / "missing-static")

    with pytest.raises(RuntimeError, match="partial crypto startup failed"):
        with TestClient(app):
            pytest.fail("startup failure must prevent TestClient from entering")

    container.close()

    assert events == [
        "start:partial:system-config",
        "start:partial:queue",
        "start:partial:crypto",
        "stop:partial:queue",
    ]
    assert queue.shutdown_calls == [(False, True)]
    assert crypto.stop_calls == 0


def test_independent_test_clients_do_not_share_container_state(tmp_path: Path) -> None:
    events: list[str] = []
    first, first_service, first_queue, _ = _build_container("first", events)
    second, second_service, second_queue, _ = _build_container("second", events)
    first_app = api_app.create_app(first, static_dir=tmp_path / "first-static")
    second_app = api_app.create_app(second, static_dir=tmp_path / "second-static")
    _add_system_config_identity_route(first_app)
    _add_system_config_identity_route(second_app)

    assert first_app.state.runtime_container is first
    assert second_app.state.runtime_container is second

    with TestClient(first_app) as first_client:
        with TestClient(second_app) as second_client:
            assert first_client.get("/_runtime-test/system-config").json() == {
                "identity": id(first_service)
            }
            assert second_client.get("/_runtime-test/system-config").json() == {
                "identity": id(second_service)
            }
        assert first_queue.shutdown_calls == []
        assert second_queue.shutdown_calls == [(False, True)]

    assert first_queue.shutdown_calls == [(False, True)]
    assert first_service is not second_service


def test_dependency_overrides_remain_isolated_between_apps(tmp_path: Path) -> None:
    events: list[str] = []
    first, _, _, _ = _build_container("override-first", events)
    second, second_service, _, _ = _build_container("override-second", events)
    first_app = api_app.create_app(first, static_dir=tmp_path / "first-static")
    second_app = api_app.create_app(second, static_dir=tmp_path / "second-static")
    _add_system_config_identity_route(first_app)
    _add_system_config_identity_route(second_app)
    override_service = object()
    first_app.dependency_overrides[get_system_config_service] = lambda: override_service

    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        assert first_client.get("/_runtime-test/system-config").json() == {
            "identity": id(override_service)
        }
        assert second_client.get("/_runtime-test/system-config").json() == {
            "identity": id(second_service)
        }

    assert get_system_config_service not in second_app.dependency_overrides


def test_app_lifespan_has_no_parallel_runtime_construction_or_cleanup_path() -> None:
    lifespan_source = inspect.getsource(api_app.app_lifespan)
    dependency_source = inspect.getsource(get_system_config_service)

    assert "SystemConfigService(" not in lifespan_source
    assert "get_task_queue(" not in lifespan_source
    assert "get_crypto_realtime_service(" not in lifespan_source
    assert ".shutdown(" not in lifespan_source
    assert ".stop(" not in lifespan_source
    assert "SystemConfigService(" not in dependency_source
    assert "runtime_container" in lifespan_source
    assert "runtime_container" in dependency_source
