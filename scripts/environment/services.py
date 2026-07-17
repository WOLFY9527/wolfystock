from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .errors import EnvironmentFailure
from .manager import managed_python_path
from .runtime import cleanup_run, create_run_context, project_test_environment, write_run_json

if TYPE_CHECKING:
    from .manager import EnvironmentManager


def reserve_backend_socket() -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    return listener, int(listener.getsockname()[1])


def reserve_frontend_port() -> int:
    reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        reservation.bind(("127.0.0.1", 0))
        port = int(reservation.getsockname()[1])
    finally:
        reservation.close()
    return port


def _terminate_process(process: Any) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name != "nt" and isinstance(process, subprocess.Popen):
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            if os.name != "nt" and isinstance(process, subprocess.Popen):
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


class ProcessGroup:
    def __init__(self) -> None:
        self.processes: list[tuple[str, Any]] = []
        self._rolled_back: set[int] = set()

    def add(self, name: str, process: Any) -> None:
        self.processes.append((name, process))

    def rollback(self) -> None:
        for _name, process in reversed(self.processes):
            if process.pid in self._rolled_back:
                continue
            self._rolled_back.add(process.pid)
            _terminate_process(process)


def _vite_config(root: Path, context: Any, *, backend_port: int, frontend_port: int) -> Path:
    source = (root / "apps" / "dsa-web" / "vite.config.ts").resolve(strict=True).as_posix()
    config = context.service_dir / "vite.wolfy.config.ts"
    payload = (
        f"import base from {json.dumps(source)}\n"
        "export default {\n"
        "  ...base,\n"
        "  plugins: [\n"
        "    ...((base.plugins || []).filter(Boolean)),\n"
        "    { name: 'wolfy-run-readiness', configureServer(server) {\n"
        "      server.middlewares.use('/__wolfy__/ready', (_request, response) => {\n"
        "        response.setHeader('Content-Type', 'application/json')\n"
        f"        response.end(JSON.stringify({{ runId: {json.dumps(context.run_id)} }}))\n"
        "      })\n"
        "    } },\n"
        "  ],\n"
        f"  cacheDir: {json.dumps(str(context.frontend_dir / 'vite-cache'))},\n"
        "  server: {\n"
        "    ...(base.server || {}),\n"
        "    host: '127.0.0.1',\n"
        f"    port: {frontend_port},\n"
        "    strictPort: true,\n"
        "    proxy: {\n"
        "      ...((base.server && base.server.proxy) || {}),\n"
        f"      '/api': {{ target: 'http://127.0.0.1:{backend_port}', changeOrigin: true }},\n"
        "    },\n"
        "  },\n"
        f"  build: {{ ...(base.build || {{}}), outDir: {json.dumps(str(context.frontend_dir / 'build'))}, emptyOutDir: true }},\n"
        "}\n"
    )
    config.write_text(payload, encoding="utf-8")
    return config


def _wait_for_http(
    url: str,
    processes: list[subprocess.Popen[Any]],
    *,
    expected_run_id: str | None = None,
    timeout: float = 45.0,
) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    last_status = "not_ready"
    while time.monotonic() < deadline:
        for process in processes:
            if process.poll() is not None:
                raise EnvironmentFailure("development_service_exited", "a development service exited before readiness")
        try:
            with opener.open(url, timeout=1.0) as response:
                if 200 <= response.status < 400:
                    if expected_run_id is not None:
                        try:
                            payload = json.loads(response.read(16 * 1024))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            last_status = "identity_response_invalid"
                            continue
                        if not isinstance(payload, dict) or payload.get("runId") != expected_run_id:
                            last_status = "identity_mismatch"
                            continue
                    return
                last_status = f"http_{response.status}"
        except (OSError, urllib.error.URLError):
            last_status = "connection_pending"
        time.sleep(0.1)
    if last_status in {"identity_mismatch", "identity_response_invalid"}:
        raise EnvironmentFailure("development_service_identity_mismatch", "development service run identity did not match")
    raise EnvironmentFailure("development_service_not_ready", f"development service readiness timed out: {last_status}")


def _state_path(cache_root: Path, run_id: str) -> Path:
    return cache_root / "runs" / "active" / run_id / "services" / "dev.json"


def run_development_services(root: Path, manager: "EnvironmentManager") -> dict[str, Any]:
    run_id = "dev-" + os.urandom(8).hex()
    context = create_run_context(manager.cache_root, run_id=run_id)
    try:
        verified = manager.verify(run_id=run_id)
        write_run_json(context, "environment-evidence.json", verified.evidence)
    except (EnvironmentFailure, OSError, ValueError):
        cleanup_run(context, success=False)
        raise
    backend_socket, backend_port = reserve_backend_socket()
    frontend_port = reserve_frontend_port()
    while frontend_port == backend_port:
        frontend_port = reserve_frontend_port()
    node = shutil.which("node")
    if not node:
        backend_socket.close()
        cleanup_run(context, success=False)
        raise EnvironmentFailure("managed_node_missing", "Node executable is unavailable")
    environment = project_test_environment(
        dict(os.environ),
        context,
        managed_python=managed_python_path(root),
        node_bin=Path(node).parent,
        command=["dev"],
    )
    environment["WOLFYSTOCK_ENV_FINGERPRINT"] = verified.combined_fingerprint
    backend_log = context.logs_dir / "backend.log"
    frontend_log = context.logs_dir / "frontend.log"
    backend_handle = backend_log.open("a", encoding="utf-8")
    frontend_handle = frontend_log.open("a", encoding="utf-8")
    group = ProcessGroup()
    try:
        backend_command = [
            str(managed_python_path(root)),
            str(root / "scripts" / "wolfy_service.py"),
            "--run-id",
            run_id,
            "backend",
        ]
        popen_options: dict[str, Any] = {
            "cwd": root,
            "env": environment,
            "stdout": backend_handle,
            "stderr": subprocess.STDOUT,
            "start_new_session": True,
        }
        if os.name == "nt":
            backend_socket.close()
            backend_command.extend(["--port", str(backend_port)])
        else:
            backend_command.extend(["--fd", str(backend_socket.fileno())])
            popen_options["pass_fds"] = (backend_socket.fileno(),)
        backend = subprocess.Popen(backend_command, **popen_options)
        group.add("backend", backend)
        config = _vite_config(root, context, backend_port=backend_port, frontend_port=frontend_port)
        vite = verified.web.path / "node_modules" / ".bin" / "vite"
        if not vite.is_file():
            raise EnvironmentFailure("vite_executable_missing", "verified Web snapshot has no Vite executable")
        frontend_command = [
            node,
            str(vite.resolve(strict=True)),
            str(root / "apps" / "dsa-web"),
            "--config",
            str(config),
            "--host",
            "127.0.0.1",
            "--port",
            str(frontend_port),
            "--strictPort",
            "--clearScreen",
            "false",
        ]
        frontend = subprocess.Popen(
            frontend_command,
            cwd=root,
            env=environment,
            stdout=frontend_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        group.add("frontend", frontend)
        backend_socket.close()
        _wait_for_http(
            f"http://127.0.0.1:{backend_port}/__wolfy__/ready",
            [backend, frontend],
            expected_run_id=run_id,
        )
        _wait_for_http(f"http://127.0.0.1:{backend_port}/api/health/live", [backend, frontend])
        _wait_for_http(
            f"http://127.0.0.1:{frontend_port}/__wolfy__/ready",
            [backend, frontend],
            expected_run_id=run_id,
        )
        _wait_for_http(f"http://127.0.0.1:{frontend_port}/", [backend, frontend])
        state = {
            "schemaVersion": "wolfystock_dev_service_state_v1",
            "runId": run_id,
            "processes": {
                "backend": {"pid": backend.pid, "identity": f"wolfy_service.py --run-id {run_id}"},
                "frontend": {"pid": frontend.pid, "identity": str(config)},
            },
        }
        _state_path(manager.cache_root, run_id).write_text(
            json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        return {
            "status": "ready",
            "environmentFingerprint": verified.combined_fingerprint,
            "runId": run_id,
            "frontendUrl": f"http://127.0.0.1:{frontend_port}",
            "backendUrl": f"http://127.0.0.1:{backend_port}",
            "processIds": {"frontend": frontend.pid, "backend": backend.pid},
            "logs": {"frontend": str(frontend_log), "backend": str(backend_log)},
            "readiness": {"frontend": "ready", "backend": "ready"},
        }
    except Exception:
        backend_socket.close()
        group.rollback()
        cleanup_run(context, success=False)
        raise
    finally:
        backend_handle.close()
        frontend_handle.close()


def _process_command(pid: int, *, platform_name: str | None = None) -> str | None:
    current_platform = platform_name or os.name
    if current_platform == "nt":
        script = (
            f"$process = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
            "if ($null -ne $process) { $process.CommandLine }"
        )
        command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script]
    else:
        command = ["ps", "-p", str(pid), "-o", "command="]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def stop_development_services(cache_root: Path, run_id: str) -> dict[str, Any]:
    state_path = _state_path(cache_root, run_id)
    if not state_path.is_file():
        return {"status": "already_stopped", "runId": run_id}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EnvironmentFailure("development_state_invalid", "development service state is invalid") from exc
    processes = state.get("processes") if isinstance(state, dict) else None
    if not isinstance(processes, dict):
        raise EnvironmentFailure("development_state_invalid", "development service state is invalid")
    stopped: list[int] = []
    for details in processes.values():
        if not isinstance(details, dict) or type(details.get("pid")) is not int:
            raise EnvironmentFailure("development_state_invalid", "development process identity is invalid")
        pid = details["pid"]
        command = _process_command(pid)
        if command is None:
            continue
        if run_id not in command:
            raise EnvironmentFailure("development_process_identity_mismatch", "refusing to stop an unrelated process")
        try:
            if os.name != "nt":
                os.killpg(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except ProcessLookupError:
            continue
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(_process_command(pid) is not None for pid in stopped):
        time.sleep(0.1)
    for pid in stopped:
        command = _process_command(pid)
        if command is None:
            continue
        if run_id not in command:
            raise EnvironmentFailure("development_process_identity_mismatch", "refusing to stop an unrelated process")
        try:
            if os.name != "nt":
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    context = create_run_context(cache_root, run_id=run_id)
    cleanup_run(context, success=True)
    return {"status": "stopped" if stopped else "already_stopped", "runId": run_id, "processIds": stopped}
