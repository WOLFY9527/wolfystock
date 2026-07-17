from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.environment.services import (
    ProcessGroup,
    _process_command,
    _vite_config,
    reserve_backend_socket,
    reserve_frontend_port,
)


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


def test_service_ports_are_nonfixed_and_backend_socket_remains_reserved() -> None:
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


def test_partial_service_startup_rolls_back_started_sibling() -> None:
    backend = FakeProcess(1001)
    group = ProcessGroup()
    group.add("backend", backend)

    group.rollback()
    group.rollback()

    assert backend.terminated == 1
    assert backend.waited == 1


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
