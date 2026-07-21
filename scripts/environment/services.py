from __future__ import annotations

import json
import os
import re
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
from .runtime import (
    cleanup_run,
    create_run_context,
    project_development_environment,
    project_test_environment,
    write_run_json,
)

if TYPE_CHECKING:
    from .manager import EnvironmentManager


DEFAULT_FRONTEND_PORT = 5173
DEFAULT_BACKEND_PORT = 8000
_RUN_ID = re.compile(r"dev-[a-z0-9-]{1,64}")
_RECOVERABLE_PROJECTION_FAILURE_CODES = frozenset(
    {
        "worktree_pointer_invalid",
        "worktree_pointer_mismatch",
        "worktree_dependency_link_broken",
    }
)


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


def _reserve_fixed_port(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
        return listener
    except OSError as exc:
        listener.close()
        raise EnvironmentFailure(
            "development_port_occupied",
            f"port {port} is already in use; stop the process using it and run wolfy dev again",
        ) from exc


def reserve_fixed_service_ports(
    *, frontend_port: int = DEFAULT_FRONTEND_PORT, backend_port: int = DEFAULT_BACKEND_PORT
) -> tuple[socket.socket, socket.socket]:
    frontend = _reserve_fixed_port(frontend_port)
    try:
        backend = _reserve_fixed_port(backend_port)
    except EnvironmentFailure:
        frontend.close()
        raise
    return frontend, backend


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
    failure_code: str | None = None,
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
        except urllib.error.HTTPError as exc:
            last_status = f"http_{exc.code}"
            if failure_code is not None and exc.code >= 500:
                raise EnvironmentFailure(
                    failure_code, f"frontend application transform failed with HTTP {exc.code}"
                ) from exc
        except (OSError, urllib.error.URLError):
            last_status = "connection_pending"
        time.sleep(0.1)
    if last_status in {"identity_mismatch", "identity_response_invalid"}:
        raise EnvironmentFailure("development_service_identity_mismatch", "development service run identity did not match")
    raise EnvironmentFailure("development_service_not_ready", f"development service readiness timed out: {last_status}")


def _verify_development_environment(manager: "EnvironmentManager", *, run_id: str) -> Any:
    try:
        return manager.verify(run_id=run_id)
    except EnvironmentFailure as exc:
        if exc.code not in _RECOVERABLE_PROJECTION_FAILURE_CODES:
            raise
    return manager.ensure(offline=False, run_id=run_id)


def _state_path(cache_root: Path, run_id: str) -> Path:
    if _RUN_ID.fullmatch(run_id) is None:
        raise EnvironmentFailure("development_run_id_invalid", "development run ID is invalid")
    return cache_root / "runs" / "active" / run_id / "services" / "dev.json"


def _local_pointer_path(cache_root: Path) -> Path:
    return cache_root / "runs" / "local-dev.json"


def _write_local_pointer(cache_root: Path, run_id: str) -> None:
    pointer = _local_pointer_path(cache_root)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    temporary = pointer.with_name(f".{pointer.name}.{os.urandom(8).hex()}.tmp")
    temporary.write_text(
        json.dumps({"runId": run_id}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, pointer)


def _read_local_run_id(cache_root: Path) -> str | None:
    pointer = _local_pointer_path(cache_root)
    if not pointer.is_file():
        return None
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentFailure("development_state_invalid", "local development identity is invalid") from exc
    run_id = payload.get("runId") if isinstance(payload, dict) else None
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        raise EnvironmentFailure("development_state_invalid", "local development identity is invalid")
    return run_id


def _remove_local_pointer(cache_root: Path, run_id: str) -> None:
    if _read_local_run_id(cache_root) == run_id:
        _local_pointer_path(cache_root).unlink(missing_ok=True)


def _load_service_state(cache_root: Path, run_id: str) -> dict[str, Any] | None:
    state_path = _state_path(cache_root, run_id)
    if not state_path.is_file():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentFailure("development_state_invalid", "development service state is invalid") from exc
    if not isinstance(state, dict) or state.get("schemaVersion") != "wolfystock_dev_service_state_v1":
        raise EnvironmentFailure("development_state_invalid", "development service state is invalid")
    if state.get("runId") != run_id or not isinstance(state.get("processes"), dict):
        raise EnvironmentFailure("development_state_invalid", "development service state is invalid")
    return state


def _validated_processes(state: dict[str, Any], run_id: str) -> dict[str, dict[str, Any]]:
    processes = state["processes"]
    validated: dict[str, dict[str, Any]] = {}
    for name, details in processes.items():
        identity = details.get("identity") if isinstance(details, dict) else None
        expected_identity = (
            (
                isinstance(identity, str)
                and (
                    identity == f"wolfy_service.py --run-id {run_id}"
                    or identity.replace("\\", "/").endswith(
                        f"/scripts/wolfy_service.py --run-id {run_id}"
                    )
                )
            )
            if name == "backend"
            else (
                isinstance(identity, str)
                and run_id in identity
                and identity.replace("\\", "/").endswith("/services/vite.wolfy.config.ts")
                if name == "frontend"
                else False
            )
        )
        if (
            not isinstance(name, str)
            or not isinstance(details, dict)
            or type(details.get("pid")) is not int
            or details["pid"] <= 0
            or not expected_identity
        ):
            raise EnvironmentFailure("development_state_invalid", "development process identity is invalid")
        validated[name] = details
    if len({details["pid"] for details in validated.values()}) != len(validated):
        raise EnvironmentFailure("development_state_invalid", "development process identity is invalid")
    return validated


def _processes_still_owned(state: dict[str, Any], run_id: str) -> dict[str, str]:
    commands: dict[str, str] = {}
    for name, details in _validated_processes(state, run_id).items():
        command = _process_command(details["pid"])
        if command is None:
            continue
        if details["identity"] not in command:
            raise EnvironmentFailure(
                "development_process_identity_mismatch", "refusing to manage an unrelated process"
            )
        commands[name] = command
    return commands


def _http_has_run_identity(url: str, run_id: str) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=1.0) as response:
            payload = json.loads(response.read(16 * 1024))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return 200 <= response.status < 400 and isinstance(payload, dict) and payload.get("runId") == run_id


def _http_is_ready(url: str) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=1.0) as response:
            return 200 <= response.status < 400
    except (OSError, urllib.error.URLError):
        return False


def _cleanup_stale_local_runtime(cache_root: Path, run_id: str) -> None:
    context = create_run_context(cache_root, run_id=run_id)
    cleanup_run(context, success=True)
    _local_pointer_path(cache_root).unlink(missing_ok=True)


def _running_local_payload(cache_root: Path) -> dict[str, Any] | None:
    run_id = _read_local_run_id(cache_root)
    if run_id is None:
        return None
    state = _load_service_state(cache_root, run_id)
    if state is None:
        _cleanup_stale_local_runtime(cache_root, run_id)
        return None
    owned = _processes_still_owned(state, run_id)
    if not owned:
        _cleanup_stale_local_runtime(cache_root, run_id)
        return None
    healthy = (
        set(owned) == {"backend", "frontend"}
        and _http_has_run_identity(
            f"http://127.0.0.1:{DEFAULT_BACKEND_PORT}/__wolfy__/ready", run_id
        )
        and _http_has_run_identity(
            f"http://127.0.0.1:{DEFAULT_FRONTEND_PORT}/__wolfy__/ready", run_id
        )
        and _http_is_ready(f"http://127.0.0.1:{DEFAULT_BACKEND_PORT}/api/health/live")
        and _http_is_ready(f"http://127.0.0.1:{DEFAULT_FRONTEND_PORT}/")
        and _http_is_ready(f"http://127.0.0.1:{DEFAULT_FRONTEND_PORT}/src/main.tsx")
    )
    if not healthy:
        stop_development_services(cache_root, run_id)
        _local_pointer_path(cache_root).unlink(missing_ok=True)
        return None
    processes = _validated_processes(state, run_id)
    return {
        "status": "already_running",
        "runId": run_id,
        "frontendUrl": f"http://127.0.0.1:{DEFAULT_FRONTEND_PORT}",
        "backendUrl": f"http://127.0.0.1:{DEFAULT_BACKEND_PORT}",
        "processIds": {name: details["pid"] for name, details in processes.items()},
        "readiness": {"frontend": "ready", "backend": "ready"},
    }


def run_development_services(
    root: Path, manager: "EnvironmentManager", *, isolated: bool = False
) -> dict[str, Any]:
    if not isolated:
        running = _running_local_payload(manager.cache_root)
        if running is not None:
            return running
    run_id = "dev-" + os.urandom(8).hex()
    context = create_run_context(manager.cache_root, run_id=run_id)
    try:
        verified = _verify_development_environment(manager, run_id=run_id)
        write_run_json(context, "environment-evidence.json", verified.evidence)
    except (EnvironmentFailure, OSError, ValueError):
        cleanup_run(context, success=False)
        raise
    frontend_socket: socket.socket | None = None
    try:
        if isolated:
            backend_socket, backend_port = reserve_backend_socket()
            frontend_port = reserve_frontend_port()
            while frontend_port == backend_port:
                frontend_port = reserve_frontend_port()
        else:
            frontend_socket, backend_socket = reserve_fixed_service_ports()
            frontend_port = DEFAULT_FRONTEND_PORT
            backend_port = DEFAULT_BACKEND_PORT
    except EnvironmentFailure:
        cleanup_run(context, success=False)
        raise
    node = shutil.which("node")
    if not node:
        backend_socket.close()
        if frontend_socket is not None:
            frontend_socket.close()
        cleanup_run(context, success=False)
        raise EnvironmentFailure("managed_node_missing", "Node executable is unavailable")
    if isolated:
        environment = project_test_environment(
            dict(os.environ),
            context,
            managed_python=managed_python_path(root),
            node_bin=Path(node).parent,
            managed_rg_dir=verified.rg.path,
            browser_path=verified.browser.path,
            browser_executable=verified.browser_executable,
            command=["dev"],
        )
    else:
        environment = project_development_environment(
            dict(os.environ),
            context,
            repository_root=root,
            managed_python=managed_python_path(root),
            node_bin=Path(node).parent,
        )
    environment["WOLFYSTOCK_ENV_FINGERPRINT"] = verified.combined_fingerprint
    environment["WOLFYSTOCK_ENV_CACHE"] = str(manager.cache_root)
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
        state = {
            "schemaVersion": "wolfystock_dev_service_state_v1",
            "runId": run_id,
            "processes": {
                "backend": {
                    "pid": backend.pid,
                    "identity": f"{root / 'scripts' / 'wolfy_service.py'} --run-id {run_id}",
                },
            },
        }
        if not isolated:
            write_run_json(context, "dev.json", state)
            _write_local_pointer(manager.cache_root, run_id)
        config = _vite_config(root, context, backend_port=backend_port, frontend_port=frontend_port)
        vite = verified.web.path / "node_modules" / ".bin" / "vite"
        if not vite.is_file():
            raise EnvironmentFailure("vite_executable_missing", "verified Web snapshot has no Vite executable")
        web_root = (root / "apps" / "dsa-web").resolve(strict=True)
        frontend_command = [
            node,
            str(vite.resolve(strict=True)),
            str(web_root),
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
        if frontend_socket is not None:
            frontend_socket.close()
            frontend_socket = None
        frontend = subprocess.Popen(
            frontend_command,
            cwd=web_root,
            env=environment,
            stdout=frontend_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        group.add("frontend", frontend)
        state["processes"]["frontend"] = {
            "pid": frontend.pid,
            "identity": str(config),
        }
        if not isolated:
            write_run_json(context, "dev.json", state)
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
        _wait_for_http(
            f"http://127.0.0.1:{frontend_port}/src/main.tsx",
            [backend, frontend],
            failure_code="development_frontend_transform_failed",
        )
        if isolated:
            write_run_json(context, "dev.json", state)
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
        if frontend_socket is not None:
            frontend_socket.close()
        group.rollback()
        if not isolated:
            _remove_local_pointer(manager.cache_root, run_id)
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
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise EnvironmentFailure(
            "development_process_inspection_failed", "development process identity could not be inspected"
        ) from exc
    if result.returncode == 0:
        return result.stdout.strip() or None
    if current_platform != "nt" and result.returncode == 1:
        return None
    raise EnvironmentFailure(
        "development_process_inspection_failed", "development process identity could not be inspected"
    )


def stop_development_services(cache_root: Path, run_id: str | None = None) -> dict[str, Any]:
    local = run_id is None
    if run_id is None:
        run_id = _read_local_run_id(cache_root)
        if run_id is None:
            return {"status": "already_stopped"}
    state = _load_service_state(cache_root, run_id)
    if state is None:
        if local:
            _cleanup_stale_local_runtime(cache_root, run_id)
        return {"status": "already_stopped", "runId": run_id}
    processes = _validated_processes(state, run_id)
    owned = _processes_still_owned(state, run_id)
    stopped: list[int] = []
    for name in owned:
        details = processes[name]
        pid = details["pid"]
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
        details = next(item for item in processes.values() if item["pid"] == pid)
        if details["identity"] not in command:
            raise EnvironmentFailure("development_process_identity_mismatch", "refusing to stop an unrelated process")
        try:
            if os.name != "nt":
                os.killpg(pid, signal.SIGKILL)
            else:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        remaining = _processes_still_owned(state, run_id)
        if not remaining:
            break
        time.sleep(0.1)
    else:
        raise EnvironmentFailure(
            "development_process_stop_failed", "development processes did not stop within the bounded timeout"
        )
    context = create_run_context(cache_root, run_id=run_id)
    cleanup_run(context, success=True)
    if local:
        _local_pointer_path(cache_root).unlink(missing_ok=True)
    return {"status": "stopped" if stopped else "already_stopped", "runId": run_id, "processIds": stopped}
