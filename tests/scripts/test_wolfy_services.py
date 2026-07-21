from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.environment.services import (
    DEFAULT_BACKEND_PORT,
    DEFAULT_FRONTEND_PORT,
    ProcessGroup,
    _process_command,
    _running_local_payload,
    _vite_config,
    reserve_fixed_service_ports,
    reserve_backend_socket,
    reserve_frontend_port,
    stop_development_services,
)
from scripts.environment.errors import EnvironmentFailure
from scripts.environment.runtime import create_run_context, project_development_environment, write_run_json


class FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.terminated = 0
        self.waited = 0
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated += 1
        self.returncode = 0

    def wait(self, timeout=None) -> int:
        self.waited += 1
        return int(self.returncode or 0)


def test_service_ports_are_nonfixed_and_backend_socket_remains_reserved(tmp_path: Path) -> None:
    backend_socket, backend_port = reserve_backend_socket()
    frontend_port = reserve_frontend_port()
    try:
        assert backend_port not in {5173, 4173, 8000}
        assert frontend_port not in {5173, 4173, 8000}
        with pytest.raises(OSError):
            contender = socket.socket()
            try:
                contender.bind(("127.0.0.1", backend_port))
            finally:
                contender.close()
    finally:
        backend_socket.close()

    assert (DEFAULT_FRONTEND_PORT, DEFAULT_BACKEND_PORT) == (5173, 8000)
    probe_frontend = reserve_frontend_port()
    probe_backend = reserve_frontend_port()
    while probe_backend == probe_frontend:
        probe_backend = reserve_frontend_port()
    frontend_socket, backend_socket = reserve_fixed_service_ports(
        frontend_port=probe_frontend, backend_port=probe_backend
    )
    try:
        assert frontend_socket.getsockname() == ("127.0.0.1", probe_frontend)
        assert backend_socket.getsockname() == ("127.0.0.1", probe_backend)
    finally:
        frontend_socket.close()
        backend_socket.close()

    occupied = socket.socket()
    occupied_port = reserve_frontend_port()
    occupied.bind(("127.0.0.1", occupied_port))
    occupied.listen(1)
    try:
        with pytest.raises(EnvironmentFailure, match=str(occupied_port)) as failure:
            reserve_fixed_service_ports(frontend_port=occupied_port, backend_port=probe_backend)
        assert failure.value.code == "development_port_occupied"
    finally:
        occupied.close()

    occupied = socket.socket()
    occupied_port = reserve_frontend_port()
    occupied.bind(("127.0.0.1", occupied_port))
    occupied.listen(1)
    try:
        with pytest.raises(EnvironmentFailure, match=str(occupied_port)) as failure:
            reserve_fixed_service_ports(frontend_port=probe_frontend, backend_port=occupied_port)
        assert failure.value.code == "development_port_occupied"
    finally:
        occupied.close()


def test_partial_service_startup_rolls_back_started_sibling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = FakeProcess(1001)
    group = ProcessGroup()
    group.add("backend", backend)

    group.rollback()
    group.rollback()

    assert backend.terminated == 1
    assert backend.waited == 1

    backend = FakeProcess(1011)
    frontend = FakeProcess(1012)
    backend.returncode = 1
    group = ProcessGroup()
    group.add("backend", backend)
    group.add("frontend", frontend)
    group.rollback()
    assert backend.terminated == 0
    assert frontend.terminated == 1

    backend = FakeProcess(1021)
    frontend = FakeProcess(1022)
    frontend.returncode = 1
    group = ProcessGroup()
    group.add("backend", backend)
    group.add("frontend", frontend)
    group.rollback()
    assert backend.terminated == 1
    assert frontend.terminated == 0

    cache_root = tmp_path / "cache"
    context = create_run_context(cache_root, run_id="dev-local-fixture")
    write_run_json(
        context,
        "dev.json",
        {
            "schemaVersion": "wolfystock_dev_service_state_v1",
            "runId": context.run_id,
            "processes": {
                "backend": {"pid": 1001, "identity": "wolfy_service.py --run-id dev-local-fixture"},
                "frontend": {"pid": 1002, "identity": str(context.service_dir / "vite.wolfy.config.ts")},
            },
        },
    )
    pointer = cache_root / "runs" / "local-dev.json"
    pointer.write_text('{"runId":"dev-local-fixture"}\n', encoding="utf-8")
    commands = {
        1001: "python wolfy_service.py --run-id dev-local-fixture backend",
        1002: f"node {context.service_dir / 'vite.wolfy.config.ts'}",
    }
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr("scripts.environment.services._process_command", lambda pid: commands.get(pid))
    monkeypatch.setattr("scripts.environment.services._http_has_run_identity", lambda _url, _run_id: True)
    monkeypatch.setattr("scripts.environment.services._http_is_ready", lambda _url: True)

    running = _running_local_payload(cache_root)
    assert running is not None
    assert running["status"] == "already_running"
    assert running["frontendUrl"] == "http://127.0.0.1:5173"
    assert running["backendUrl"] == "http://127.0.0.1:8000"

    def killpg(pid: int, sig: int) -> None:
        killed.append((pid, sig))
        commands.pop(pid, None)

    monkeypatch.setattr("scripts.environment.services.os.killpg", killpg)
    stopped = stop_development_services(cache_root)

    assert stopped["status"] == "stopped"
    assert {pid for pid, _signal in killed} == {1001, 1002}
    assert not pointer.exists()
    assert not context.root.exists()
    assert stop_development_services(cache_root)["status"] == "already_stopped"

    context = create_run_context(cache_root, run_id="dev-stale-fixture")
    write_run_json(
        context,
        "dev.json",
        {
            "schemaVersion": "wolfystock_dev_service_state_v1",
            "runId": context.run_id,
            "processes": {
                "backend": {"pid": 2001, "identity": "wolfy_service.py --run-id dev-stale-fixture"}
            },
        },
    )
    pointer.write_text('{"runId":"dev-stale-fixture"}\n', encoding="utf-8")
    assert stop_development_services(cache_root)["status"] == "already_stopped"
    assert not pointer.exists()
    assert not context.root.exists()

    context = create_run_context(cache_root, run_id="dev-reused-fixture")
    write_run_json(
        context,
        "dev.json",
        {
            "schemaVersion": "wolfystock_dev_service_state_v1",
            "runId": context.run_id,
            "processes": {
                "backend": {"pid": 3001, "identity": "wolfy_service.py --run-id dev-reused-fixture"},
                "frontend": {"pid": 3002, "identity": str(context.service_dir / "vite.wolfy.config.ts")},
            },
        },
    )
    pointer.write_text('{"runId":"dev-reused-fixture"}\n', encoding="utf-8")
    commands[3001] = "python wolfy_service.py --run-id dev-reused-fixture backend"
    commands[3002] = "unrelated-process"
    with pytest.raises(EnvironmentFailure) as mismatch:
        stop_development_services(cache_root)
    assert mismatch.value.code == "development_process_identity_mismatch"
    assert 3001 not in {pid for pid, _signal in killed}
    assert 3002 not in {pid for pid, _signal in killed}
    assert pointer.exists()

    with pytest.raises(EnvironmentFailure) as invalid_run_id:
        stop_development_services(cache_root, "dev-../../outside")
    assert invalid_run_id.value.code == "development_run_id_invalid"


def test_generated_vite_config_is_run_scoped_and_has_no_top_level_await(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "apps" / "dsa-web").mkdir(parents=True)
    (root / "apps" / "dsa-web" / "vite.config.ts").write_text("export default {}\n", encoding="utf-8")
    context = SimpleNamespace(
        run_id="dev-fixture",
        service_dir=tmp_path / "run" / "services",
        frontend_dir=tmp_path / "run" / "frontend",
    )
    context.service_dir.mkdir(parents=True)

    config = _vite_config(root, context, backend_port=41001, frontend_port=41002)
    content = config.read_text(encoding="utf-8")

    assert "await" not in content
    assert "strictPort: true" in content
    assert "wolfy-run-readiness" in content
    assert "dev-fixture" in content
    assert "41001" in content
    assert "41002" in content
    assert str(context.frontend_dir / "vite-cache") in content
    assert str(context.frontend_dir / "build") in content
    assert "node_modules/.vite" not in content
    assert not str(context.frontend_dir).startswith(str(root / "apps" / "dsa-web" / "node_modules"))

    run_context = create_run_context(tmp_path / "cache", run_id="dev-environment-fixture")
    projected = project_development_environment(
        {
            "HTTP_PROXY": "http://proxy.example.test:8080",
            "HTTPS_PROXY": "http://secure-proxy.example.test:8443",
            "ALL_PROXY": "socks5://proxy.example.test:1080",
            "NO_PROXY": "localhost,127.0.0.1",
            "PROVIDER_API_KEY": "configured-by-user",
        },
        run_context,
        repository_root=root,
        managed_python=Path("/managed/bin/python"),
        node_bin=Path("/managed/node/bin"),
    )
    assert projected["ENV_FILE"] == str(root / ".env")
    assert projected["HTTP_PROXY"] == "http://proxy.example.test:8080"
    assert projected["HTTPS_PROXY"] == "http://secure-proxy.example.test:8443"
    assert projected["ALL_PROXY"] == "socks5://proxy.example.test:1080"
    assert projected["NO_PROXY"] == "localhost,127.0.0.1"
    assert projected["PROVIDER_API_KEY"] == "configured-by-user"
    assert projected["DATABASE_PATH"] == str(run_context.database_path)
    assert projected["LOG_DIR"] == str(run_context.logs_dir)
    assert projected["TMPDIR"] == str(run_context.temp_dir)
    assert projected["WOLFYSTOCK_FRONTEND_OUTPUT_DIR"] == str(run_context.frontend_dir)
    assert projected["WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS"] == "true"

    without_proxy = project_development_environment(
        {},
        run_context,
        repository_root=root,
        managed_python=Path("/managed/bin/python"),
        node_bin=Path("/managed/node/bin"),
    )
    assert not ({"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"} & without_proxy.keys())


def test_windows_process_identity_uses_cim_not_posix_ps(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "wolfy --run-id dev-fixture\n", "")

    monkeypatch.setattr("scripts.environment.services.subprocess.run", runner)

    assert _process_command(1234, platform_name="nt") == "wolfy --run-id dev-fixture"
    assert commands[0][0] == "powershell.exe"
    assert "Get-CimInstance" in commands[0][-1]
    assert commands[0][0] != "ps"
