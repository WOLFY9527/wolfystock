#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic local UAT runtime harness for WolfyStock.

This script composes the existing fresh-build verifier, local UAT account
seeder, and runtime smoke logic into one local command. It owns only the
process it starts and writes evidence under output/runtime-verification/.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO, Mapping, Sequence
from uuid import uuid4

if os.name == "nt":
    from ctypes import wintypes

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_EVIDENCE_DIR = Path("output/runtime-verification")
DEFAULT_READINESS_TIMEOUT_SECONDS = 90.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 5.0
WOLFYSTOCK_HTML_MARKERS = ("WolfyStock", "/assets/")
FRONTEND_REQUIRED_BINARIES = ("tsc", "vite")
FRONTEND_INSTALL_COMMAND = ("npm", "--prefix", "apps/dsa-web", "ci")
UAT_ENV_OVERRIDES = {
    "APP_ENV": "uat",
    "CRYPTO_REALTIME_ENABLED": "false",
    "WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true",
    "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "false",
    "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": "false",
    "WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED": "false",
    "PREFETCH_REALTIME_QUOTES": "false",
}
PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")

EXIT_OK = 0
EXIT_FAILED = 1


def is_windows() -> bool:
    return os.name == "nt"


@dataclass(frozen=True)
class PortOwner:
    pid: int
    cwd: str | None
    command: str | None


@dataclass(frozen=True)
class RunContext:
    run_id: str
    start_time: str
    evidence_dir: Path
    evidence_path: Path
    run_log_path: Path


@dataclass(frozen=True)
class ProcessProbe:
    state: str
    windows_error: int | None = None


@dataclass(frozen=True)
class EvidenceCandidate:
    path: Path
    loaded: bool
    evidence: dict[str, Any] | None
    freshness: dict[str, Any]
    timestamp: datetime | None
    run_id: str
    mtime: float
    legacy: bool
    selection_reason: str


class DirectNoProxyHttpClient:
    """Small urllib client that explicitly ignores process proxy settings."""

    def __init__(self, *, timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS) -> None:
        self.timeout = float(timeout)
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, method: str, url: str, headers: dict[str, str] | None = None) -> Any:
        request = urllib.request.Request(
            url,
            method=method,
            headers={"User-Agent": "wolfystock-uat-runtime-harness/1", **(headers or {})},
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return _HttpResponse(int(response.status), response.read())
        except urllib.error.HTTPError as exc:
            return _HttpResponse(int(exc.code), exc.read())


class _HttpResponse:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = int(status_code)
        self.content = bytes(content)
        self.text = self.content.decode("utf-8", errors="ignore")

    def json(self) -> dict[str, Any]:
        payload = json.loads(self.text)
        if not isinstance(payload, dict):
            raise ValueError("json_root_not_object")
        return payload


def resolve_repo_root(start: Path | None = None) -> Path:
    """Resolve repo root without importing the full application graph."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / "AGENTS.md").is_file():
            return candidate
    return REPO_ROOT


def read_backend_info(repo_root: Path) -> Any:
    from scripts.uat_fresh_build_verifier import read_backend_info as _read_backend_info

    return _read_backend_info(repo_root)


def run_frontend_build(repo_root: Path) -> int:
    from scripts.uat_fresh_build_verifier import run_frontend_build as _run_frontend_build

    return _run_frontend_build(repo_root)


def verify_frontend_static_build(**kwargs: Any) -> Any:
    from scripts.uat_fresh_build_verifier import verify_frontend_static_build as _verify_frontend_static_build

    return _verify_frontend_static_build(**kwargs)


def verify_generated_artifact_hygiene(repo_root: Path) -> list[str]:
    from scripts.uat_fresh_build_verifier import verify_generated_artifact_hygiene as _verify_generated_artifact_hygiene

    return _verify_generated_artifact_hygiene(repo_root)


def verify_git_preflight(repo_root: Path) -> list[str]:
    from scripts.uat_fresh_build_verifier import verify_git_preflight as _verify_git_preflight

    return _verify_git_preflight(repo_root)


def seed_uat_consumer_test_accounts() -> dict[str, Any]:
    from scripts.seed_uat_consumer_test_accounts import (
        seed_uat_consumer_test_accounts as _seed_uat_consumer_test_accounts,
    )

    return _seed_uat_consumer_test_accounts()


def clean_base_url(raw_url: str) -> str:
    return str(raw_url or "").strip().rstrip("/")


def run_runtime_smoke(**kwargs: Any) -> dict[str, Any]:
    from scripts.uat_runtime_smoke_pack import run_runtime_smoke as _run_runtime_smoke

    return _run_runtime_smoke(**kwargs)


def build_uat_runtime_env(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.update(UAT_ENV_OVERRIDES)
    env["NO_PROXY"] = _merge_no_proxy(env.get("NO_PROXY"))
    env["no_proxy"] = _merge_no_proxy(env.get("no_proxy"))
    for key in PROXY_ENV_KEYS:
        env.pop(key, None)
    return env


def expected_provider_isolation() -> dict[str, Any]:
    return {
        "mode": "uat_no_live_providers",
        "env": dict(UAT_ENV_OVERRIDES),
        "previousAaplStructureDecisionPath": [
            "browser /stocks/AAPL/structure-decision",
            "GET /api/v1/stocks/AAPL/structure-decision",
            "StockStructureDecisionService._load_daily_history",
            "StockService.get_history_data",
            "fetch_daily_history_with_local_us_fallback",
            "DataFetcherManager provider fallback / yfinance when local US parquet is missing",
        ],
        "uatBehavior": (
            "WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS=true blocks StockService live quote/name/history provider "
            "fallbacks; missing local cache stays unavailable."
        ),
        "productionBehaviorUnchanged": True,
    }


def validate_source(repo_root: Path, expected_sha: str | None) -> dict[str, Any]:
    backend = read_backend_info(repo_root)
    actual_sha = str(backend.git_sha or "").strip()
    errors = verify_git_preflight(repo_root)
    if expected_sha and actual_sha != expected_sha:
        errors.append("git_sha_mismatch")
    errors.extend(verify_generated_artifact_hygiene(repo_root))
    return {
        "ok": not errors,
        "gitSha": actual_sha,
        "branch": str(backend.branch or ""),
        "commitTimestamp": str(backend.commit_timestamp or ""),
        "expectedGitSha": expected_sha,
        "errorCodes": errors,
    }


def ensure_frontend_dependencies(repo_root: Path) -> dict[str, Any]:
    web_dir = Path(repo_root) / "apps" / "dsa-web"
    lockfile = web_dir / "package-lock.json"
    missing_bins = [
        name
        for name in FRONTEND_REQUIRED_BINARIES
        if not (web_dir / "node_modules" / ".bin" / name).is_file()
    ]
    npm_path = shutil.which("npm")
    install_command = list(FRONTEND_INSTALL_COMMAND)
    result: dict[str, Any] = {
        "required": bool(missing_bins),
        "action": "pending" if missing_bins else "skipped",
        "skipReason": None if missing_bins else "frontend_toolchain_available",
        "installCommand": install_command,
        "exitStatus": None,
        "missingBinaries": missing_bins,
        "lockfile": {
            "path": "apps/dsa-web/package-lock.json",
            "sha256": _sha256_file(lockfile),
            "exists": lockfile.is_file(),
        },
        "reasonCodes": [],
    }
    if not missing_bins:
        return result
    if not lockfile.is_file():
        result.update(
            {
                "action": "failed",
                "exitStatus": None,
                "reasonCodes": ["frontend_package_lock_missing"],
            }
        )
        return result
    if not npm_path:
        result.update(
            {
                "action": "failed",
                "exitStatus": None,
                "reasonCodes": ["npm_unavailable"],
            }
        )
        return result

    completed = subprocess.run([npm_path, *FRONTEND_INSTALL_COMMAND[1:]], cwd=repo_root, check=False)
    result["exitStatus"] = int(completed.returncode)
    if completed.returncode == 0:
        result["action"] = "installed"
        result["reasonCodes"] = []
    else:
        result["action"] = "failed"
        result["reasonCodes"] = ["frontend_dependency_install_failed"]
    return result


def find_port_owner(host: str, port: int) -> PortOwner | None:
    if not _can_connect(host, port):
        return None
    if is_windows():
        return _find_windows_port_owner(port)
    lsof = shutil.which("lsof")
    if not lsof:
        return PortOwner(pid=-1, cwd=None, command="unknown: lsof unavailable")
    completed = subprocess.run(
        [lsof, "-nP", "-iTCP:%d" % int(port), "-sTCP:LISTEN", "-F", "pc"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    pid: int | None = None
    command: str | None = None
    for line in completed.stdout.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pid = int(line[1:])
        elif line.startswith("c"):
            command = line[1:] or None
    if pid is None:
        return PortOwner(pid=-1, cwd=None, command=command or "unknown")
    return PortOwner(pid=pid, cwd=process_cwd(pid), command=process_command(pid) or command)


def process_cwd(pid: int) -> str | None:
    if pid <= 0:
        return None
    if is_windows():
        return None
    proc_cwd = Path("/proc") / str(pid) / "cwd"
    try:
        if proc_cwd.exists():
            return str(proc_cwd.resolve())
    except Exception:
        pass
    pwdx = shutil.which("pwdx")
    if pwdx:
        completed = subprocess.run([pwdx, str(pid)], capture_output=True, text=True, check=False, timeout=5)
        if completed.returncode == 0 and ":" in completed.stdout:
            return completed.stdout.split(":", 1)[1].strip() or None
    lsof = shutil.which("lsof")
    if lsof:
        completed = subprocess.run(
            [lsof, "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        for line in completed.stdout.splitlines():
            if line.startswith("n"):
                return line[1:] or None
    return None


def process_executable(pid: int) -> str | None:
    if pid <= 0:
        return None
    if is_windows():
        script = (
            "$proc = Get-CimInstance Win32_Process -Filter \"ProcessId = %d\" -ErrorAction SilentlyContinue;"
            "if ($null -ne $proc -and $proc.ExecutablePath) { [Console]::Out.Write($proc.ExecutablePath) }"
        ) % int(pid)
        completed = _run_windows_powershell(script)
        if completed is None or completed.returncode != 0:
            return None
        return completed.stdout.strip() or None
    proc_exe = Path("/proc") / str(pid) / "exe"
    try:
        if proc_exe.exists():
            return str(proc_exe.resolve())
    except Exception:
        pass
    lsof = shutil.which("lsof")
    if lsof:
        completed = subprocess.run(
            [lsof, "-a", "-p", str(pid), "-d", "txt", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        for line in completed.stdout.splitlines():
            if line.startswith("n") and Path(line[1:]).is_file():
                return line[1:]
    ps = shutil.which("ps")
    if not ps:
        return None
    completed = subprocess.run(
        [ps, "-p", str(pid), "-o", "comm="],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return completed.stdout.strip() or None if completed.returncode == 0 else None


def process_command(pid: int) -> str | None:
    if pid <= 0:
        return None
    if is_windows():
        return _windows_process_command(pid)
    ps = shutil.which("ps")
    if not ps:
        return None
    completed = subprocess.run(
        [ps, "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def process_start_time(pid: int) -> str | None:
    if is_windows():
        return _windows_process_start_time(pid)
    ps = shutil.which("ps")
    if pid <= 0 or not ps:
        return None
    completed = subprocess.run(
        [ps, "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return completed.stdout.strip() or None if completed.returncode == 0 else None


def _probe_process(pid: int) -> ProcessProbe:
    if pid <= 0:
        return ProcessProbe(state="absent")
    if is_windows():
        return _probe_windows_process(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return ProcessProbe(state="absent")
    except PermissionError:
        return ProcessProbe(state="alive")
    return ProcessProbe(state="alive")


def _terminate_pid(pid: int) -> None:
    if not is_windows():
        os.kill(pid, signal.SIGTERM)
        return
    handle, error = _open_windows_process(_windows_terminate_access(), pid)
    if not handle:
        if error == 5:
            raise PermissionError(13, "access denied", None, error)
        if error in {87, 1168}:
            raise ProcessLookupError(pid)
        raise OSError(error or 0, f"OpenProcess failed for pid {pid}")
    try:
        if not _windows_kernel32().TerminateProcess(handle, 15):
            error = ctypes.get_last_error()
            if error == 5:
                raise PermissionError(13, "access denied", None, error)
            if error in {87, 1168}:
                raise ProcessLookupError(pid)
            raise OSError(error, f"TerminateProcess failed for pid {pid}")
    finally:
        _windows_kernel32().CloseHandle(handle)


def _normalize_command_line(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _windows_process_start_time(pid: int) -> str | None:
    handle, _error = _open_windows_process(_windows_query_access(), pid)
    if not handle:
        return None
    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    try:
        if not _windows_kernel32().GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            return None
        timestamp = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        if timestamp <= 0:
            return None
        unix_seconds = (timestamp - 116444736000000000) / 10_000_000
        return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).isoformat()
    finally:
        _windows_kernel32().CloseHandle(handle)


def _windows_process_command(pid: int) -> str | None:
    script = (
        "$proc = Get-CimInstance Win32_Process -Filter \"ProcessId = %d\" -ErrorAction SilentlyContinue;"
        "if ($null -ne $proc -and $proc.CommandLine) { [Console]::Out.Write($proc.CommandLine) }"
    ) % int(pid)
    completed = _run_windows_powershell(script)
    if completed is None or completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _find_windows_port_owner(port: int) -> PortOwner | None:
    script = (
        "$connections = @(Get-NetTCPConnection -State Listen -LocalPort %d -ErrorAction SilentlyContinue "
        "| Sort-Object -Property OwningProcess,LocalAddress,LocalPort "
        "| Select-Object -First 1);"
        "if ($connections.Count -lt 1) { exit 0 };"
        "$ownerProcessId = [int]$connections[0].OwningProcess;"
        "$command = $null;"
        "try { $proc = Get-CimInstance Win32_Process -Filter \"ProcessId = $ownerProcessId\" -ErrorAction Stop; $command = $proc.CommandLine } catch {};"
        "@{ pid = $ownerProcessId; command = $command } | ConvertTo-Json -Compress"
    ) % int(port)
    completed = _run_windows_powershell(script)
    if completed is None or completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return PortOwner(
        pid=_safe_int(payload.get("pid")),
        cwd=None,
        command=str(payload.get("command") or "") or None,
    )


def _run_windows_powershell(script: str) -> subprocess.CompletedProcess[str] | None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return None
    return subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


def _probe_windows_process(pid: int) -> ProcessProbe:
    handle, error = _open_windows_process(_windows_query_access(), pid)
    if not handle:
        if error == 5:
            return ProcessProbe(state="access_denied", windows_error=error)
        if error in {87, 1168}:
            return ProcessProbe(state="absent", windows_error=error)
        return ProcessProbe(state="unknown", windows_error=error)
    exit_code = wintypes.DWORD()
    try:
        if not _windows_kernel32().GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            error = ctypes.get_last_error()
            return ProcessProbe(state="unknown", windows_error=error)
        return ProcessProbe(state="alive" if int(exit_code.value) == 259 else "absent")
    finally:
        _windows_kernel32().CloseHandle(handle)


def _open_windows_process(access: int, pid: int) -> tuple[int | None, int | None]:
    handle = _windows_kernel32().OpenProcess(int(access), False, int(pid))
    if handle:
        return int(handle), None
    return None, ctypes.get_last_error()


def _windows_query_access() -> int:
    return 0x00100000 | 0x1000


def _windows_terminate_access() -> int:
    return _windows_query_access() | 0x0001


def _windows_kernel32() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def start_runtime(
    repo_root: Path,
    *,
    host: str,
    port: int,
    python_bin: str | None = None,
    run_log_path: Path | None = None,
) -> subprocess.Popen[str]:
    python = str(_select_runtime_python(repo_root, python_bin=python_bin))
    command = [python, str(repo_root / "main.py"), "--serve-only", "--host", host, "--port", str(port)]
    log_handle: IO[str] | int
    if run_log_path is not None:
        run_log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = run_log_path.open("a", encoding="utf-8", buffering=1)
    else:
        log_handle = subprocess.DEVNULL
    process = subprocess.Popen(
        command,
        cwd=repo_root,
        env=build_uat_runtime_env(),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if run_log_path is not None and hasattr(log_handle, "close"):
        setattr(process, "_wolfystock_run_log_handle", log_handle)
    return process


def _default_venv_python(repo_root: Path) -> Path:
    if is_windows():
        return repo_root / ".venv" / "Scripts" / "python.exe"
    return repo_root / ".venv" / "bin" / "python"


def _select_runtime_python(repo_root: Path, *, python_bin: str | None = None) -> Path:
    requested = Path(python_bin) if python_bin else _default_venv_python(repo_root)
    if requested.exists():
        return requested
    return Path(sys.executable)


def build_interpreter_identity(expected_path: Path, observed_path: str | None) -> dict[str, Any]:
    expected_requested = str(expected_path)
    expected_resolved = str(expected_path.resolve())
    observed_resolved = str(Path(observed_path).resolve()) if observed_path else None
    if not observed_resolved:
        status = "unverified"
    elif observed_resolved == expected_resolved:
        status = "verified"
    else:
        status = "mismatch"
    return {
        "status": status,
        "expectedRequestedPath": expected_requested,
        "expectedResolvedPath": expected_resolved,
        "observedPath": observed_path,
        "observedResolvedPath": observed_resolved,
    }


def stop_owned_runtime(process: subprocess.Popen[str] | None) -> dict[str, Any]:
    if process is None:
        return {"status": "absent", "reasonCode": "runtime_already_absent"}
    if process.poll() is not None:
        _close_runtime_log_handle(process)
        return {"status": "absent", "reasonCode": "runtime_already_absent"}
    process.terminate()
    try:
        process.wait(timeout=10)
        _close_runtime_log_handle(process)
        return {"status": "stopped", "signal": "terminate"}
    except subprocess.TimeoutExpired:
        return {"status": "rejected", "reasonCode": "terminate_timeout", "signal": "terminate"}


def pid_is_alive(pid: int) -> bool:
    return _probe_process(pid).state == "alive"


def stop_runtime_from_evidence(
    evidence_path: Path,
    *,
    required_sha: str | None = None,
    enforce_current: bool = False,
    selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = load_evidence(evidence_path)
    freshness = _classify_evidence_freshness(evidence, required_sha=required_sha)
    selection_payload = _merge_selection_payload(
        selection,
        path=evidence_path,
        default_mode="explicit",
        default_reason="explicit_evidence_path",
        freshness=freshness,
    )

    def _finish_stop_result(result: dict[str, Any]) -> dict[str, Any]:
        result.setdefault("evidencePath", str(evidence_path))
        result.setdefault("selection", selection_payload)
        result.setdefault("evidenceFreshness", freshness)
        _append_lifecycle_event(evidence_path, result)
        return result

    if enforce_current and freshness.get("classification") != "CURRENT":
        result = {
            "status": "rejected",
            "reasonCode": "evidence_not_current",
            "evidencePath": str(evidence_path),
            "selection": selection_payload,
            "evidenceFreshness": freshness,
        }
        return _finish_stop_result(result)
    run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
    runtime = evidence.get("runtime") if isinstance(evidence.get("runtime"), Mapping) else {}
    pid = _safe_int(run.get("pid"))
    expected_cwd = str(run.get("cwd") or "")
    expected_command = _normalize_command_line(runtime.get("command"))
    if pid <= 0:
        result = {"status": "rejected", "reasonCode": "pid_missing", "pid": pid}
        return _finish_stop_result(result)

    if runtime.get("ownedByHarness") is not True:
        result = {
            "status": "rejected",
            "reasonCode": "not_harness_owned",
            "pid": pid,
        }
        return _finish_stop_result(result)

    probe = _probe_process(pid)
    if probe.state == "absent":
        result = {
            "status": "absent",
            "reasonCode": "runtime_already_absent",
            "pid": pid,
            "processState": probe.state,
            "windowsError": probe.windows_error,
        }
        return _finish_stop_result(result)
    if probe.state == "access_denied":
        result = {
            "status": "rejected",
            "reasonCode": "access_denied",
            "pid": pid,
            "processState": probe.state,
            "windowsError": probe.windows_error,
        }
        return _finish_stop_result(result)
    if probe.state != "alive":
        result = {
            "status": "rejected",
            "reasonCode": "ownership_unverifiable",
            "pid": pid,
            "processState": probe.state,
            "windowsError": probe.windows_error,
        }
        return _finish_stop_result(result)

    expected_start = str(runtime.get("processStartTime") or "").strip()
    observed_start = str(process_start_time(pid) or "").strip()
    if is_windows() and not expected_start:
        result = {
            "status": "rejected",
            "reasonCode": "ownership_unverifiable",
            "pid": pid,
            "missingIdentity": ["processStartTime"],
        }
        return _finish_stop_result(result)
    if is_windows() and expected_start and not observed_start:
        reprobe = _probe_process(pid)
        if reprobe.state == "absent":
            result = {"status": "absent", "reasonCode": "runtime_already_absent", "pid": pid}
            return _finish_stop_result(result)
        if reprobe.state == "access_denied":
            result = {"status": "rejected", "reasonCode": "access_denied", "pid": pid}
            return _finish_stop_result(result)
        result = {
            "status": "rejected",
            "reasonCode": "ownership_unverifiable",
            "pid": pid,
            "expectedProcessStartTime": expected_start,
            "observedProcessStartTime": observed_start or None,
        }
        return _finish_stop_result(result)
    if expected_start and observed_start and expected_start != observed_start:
        result = {
            "status": "rejected",
            "reasonCode": "pid_reused",
            "pid": pid,
            "expectedProcessStartTime": expected_start,
            "observedProcessStartTime": observed_start,
        }
        return _finish_stop_result(result)

    observed_cwd = process_cwd(pid)
    observed_command = _normalize_command_line(process_command(pid))
    if expected_cwd:
        if observed_cwd and Path(observed_cwd).resolve() != Path(expected_cwd).resolve():
            result = {
                "status": "rejected",
                "reasonCode": "pid_cwd_mismatch",
                "pid": pid,
                "expectedCwd": expected_cwd,
                "observedCwd": observed_cwd,
            }
            return _finish_stop_result(result)
        if not observed_cwd:
            if not is_windows():
                result = {
                    "status": "rejected",
                    "reasonCode": "pid_cwd_unavailable",
                    "pid": pid,
                    "expectedCwd": expected_cwd,
                    "observedCwd": observed_cwd,
                }
                return _finish_stop_result(result)
            if not expected_command or not observed_command:
                result = {
                    "status": "rejected",
                    "reasonCode": "ownership_unverifiable",
                    "pid": pid,
                    "expectedCwd": expected_cwd,
                    "observedCwd": observed_cwd,
                    "expectedCommand": expected_command or None,
                    "observedCommand": observed_command or None,
                }
                return _finish_stop_result(result)
            if expected_command != observed_command:
                result = {
                    "status": "rejected",
                    "reasonCode": "pid_command_mismatch",
                    "pid": pid,
                    "expectedCommand": expected_command,
                    "observedCommand": observed_command,
                }
                return _finish_stop_result(result)
    elif is_windows() and expected_command and observed_command and expected_command != observed_command:
        result = {
            "status": "rejected",
            "reasonCode": "pid_command_mismatch",
            "pid": pid,
            "expectedCommand": expected_command,
            "observedCommand": observed_command,
        }
        return _finish_stop_result(result)

    listener = runtime.get("listener") if isinstance(runtime.get("listener"), Mapping) else {}
    expected_port = _safe_int(listener.get("port") or run.get("port"))
    expected_host = str(listener.get("host") or DEFAULT_HOST)
    if expected_port > 0:
        owner = find_port_owner(expected_host, expected_port)
        if owner is not None and owner.pid != pid:
            result = {
                "status": "rejected",
                "reasonCode": "pid_port_owner_mismatch",
                "pid": pid,
                "expectedPort": expected_port,
                "observedPortOwner": owner.__dict__,
            }
            return _finish_stop_result(result)
        if owner is None:
            result = {
                "status": "rejected",
                "reasonCode": "pid_not_port_owner",
                "pid": pid,
                "expectedPort": expected_port,
            }
            return _finish_stop_result(result)

    try:
        _terminate_pid(pid)
    except ProcessLookupError:
        result = {"status": "absent", "reasonCode": "runtime_already_absent", "pid": pid}
        return _finish_stop_result(result)
    except PermissionError:
        result = {"status": "rejected", "reasonCode": "access_denied", "pid": pid}
        return _finish_stop_result(result)
    except OSError as exc:
        result = {
            "status": "rejected",
            "reasonCode": "terminate_failed",
            "pid": pid,
            "errorType": type(exc).__name__,
            "windowsError": getattr(exc, "winerror", None),
        }
        return _finish_stop_result(result)
    result = {"status": "stopped", "reasonCode": "task_owned_pid_terminated", "pid": pid, "cwd": observed_cwd}
    return _finish_stop_result(result)


def wait_for_readiness(client: DirectNoProxyHttpClient, base_url: str, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + float(timeout_seconds)
    last_status: int | None = None
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            response = client.request("GET", urllib.parse.urljoin(f"{base_url}/", "api/health"))
            last_status = int(response.status_code)
            if 200 <= last_status < 300:
                return {"ok": True, "httpStatus": last_status, "error": None}
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(0.5)
    return {"ok": False, "httpStatus": last_status, "error": last_error or "readiness_timeout"}


def verify_direct_asset_identity(
    client: DirectNoProxyHttpClient,
    base_url: str,
    asset_identity: Mapping[str, Any],
) -> dict[str, Any]:
    response = client.request("GET", base_url + "/")
    body = response.text or ""
    expected_asset = str(asset_identity.get("mainJsAssetFilename") or "")
    expected_index_hash = str(asset_identity.get("indexHtmlHash") or "")
    marker_ok = int(response.status_code) == 200 and all(marker in body for marker in WOLFYSTOCK_HTML_MARKERS)
    asset_ref_ok = bool(expected_asset and expected_asset in body)
    observed_index_hash = hashlib.sha256(_response_content(response)).hexdigest()
    index_hash_ok = bool(expected_index_hash and observed_index_hash == expected_index_hash)
    observed_asset_hashes: dict[str, str | None] = {}
    asset_hashes_ok = True
    for filename, expected_hash in dict(asset_identity.get("assetHashes") or {}).items():
        asset_response = client.request("GET", f"{base_url}/assets/{filename}")
        observed_hash = hashlib.sha256(_response_content(asset_response)).hexdigest()
        observed_asset_hashes[str(filename)] = observed_hash
        if int(asset_response.status_code) != 200 or not expected_hash or observed_hash != expected_hash:
            asset_hashes_ok = False

    reason_codes: list[str] = []
    if not marker_ok or not asset_ref_ok:
        reason_codes.append("direct_http_html_identity_mismatch")
    if not index_hash_ok or not asset_hashes_ok:
        reason_codes.append("served_asset_hash_mismatch")
    return {
        "ok": marker_ok and asset_ref_ok and index_hash_ok and asset_hashes_ok,
        "httpStatus": int(response.status_code),
        "wolfyStockHtml": marker_ok,
        "expectedAssetPresent": asset_ref_ok,
        "expectedAssetFilename": expected_asset or None,
        "expectedIndexHtmlHash": expected_index_hash or None,
        "observedIndexHtmlHash": observed_index_hash,
        "expectedAssetHashes": dict(asset_identity.get("assetHashes") or {}),
        "observedAssetHashes": observed_asset_hashes,
        "reasonCodes": reason_codes,
    }


def _response_content(response: Any) -> bytes:
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content
    return str(getattr(response, "text", "") or "").encode("utf-8")


def build_asset_identity(static_root: Path, local_payload: Mapping[str, Any]) -> dict[str, Any]:
    index_path = static_root / "index.html"
    main_asset = str(local_payload.get("frontendMainAssetFilename") or "")
    return {
        "frontendBuildPath": str(static_root),
        "indexHtmlHash": _sha256_file(index_path),
        "mainJsAssetFilename": main_asset or None,
        "mainCssAssetFilenames": _css_assets(static_root),
        "assetHashes": _asset_hashes(static_root, [main_asset, *_css_assets(static_root)]),
        "localBuildProvenance": dict(local_payload),
        "buildIdentity": local_payload.get("frontendBuildIdentity"),
    }


def build_workbuddy_handoff(
    *,
    run_id: str,
    base_url: str,
    expected_git_sha: str,
    runtime_pid: int,
    runtime_cwd: str | None,
    asset_identity: Mapping[str, Any],
    run_log_path: str,
    run_start_time: str,
) -> dict[str, Any]:
    return {
        "runId": run_id,
        "directUrl": base_url,
        "expectedGitSha": expected_git_sha,
        "runtimePid": runtime_pid,
        "runtimeCwd": runtime_cwd,
        "browserActionWindow": {
            "startAfter": run_start_time,
            "correlationOnly": True,
            "note": "Use this window to correlate browser actions with the run log; it does not prove causal network attribution.",
        },
        "runtimeLogWindow": {
            "path": run_log_path,
            "startTime": run_start_time,
            "activityScope": "run_scoped_child_stdout_stderr",
            "correlationOnly": True,
            "causalAttribution": {
                "automatic": False,
                "mode": "correlation_only",
            },
        },
        "assetIdentity": {
            "indexHtmlHash": asset_identity.get("indexHtmlHash"),
            "mainJsAssetFilename": asset_identity.get("mainJsAssetFilename"),
            "mainCssAssetFilenames": asset_identity.get("mainCssAssetFilenames"),
            "assetHashes": asset_identity.get("assetHashes"),
        },
        "browserRequirements": {
            "freshContextSession": True,
            "proxyBypassForLocalhost": True,
            "serviceWorkersBlockedOrVerifiedClean": True,
            "noReusedOldTabOrSession": True,
        },
    }


def create_run_context(evidence_dir: Path) -> RunContext:
    start_time = datetime.now(timezone.utc).isoformat()
    compact_time = start_time.replace("-", "").replace(":", "").split(".", 1)[0]
    run_id = f"uat-{compact_time}-{uuid4().hex[:8]}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    return RunContext(
        run_id=run_id,
        start_time=start_time,
        evidence_dir=evidence_dir,
        evidence_path=evidence_dir / f"{run_id}-evidence.json",
        run_log_path=evidence_dir / f"{run_id}-runtime.log",
    )


def write_evidence(evidence_dir: Path, evidence: Mapping[str, Any], *, run_context: RunContext | None = None) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = run_context.evidence_path if run_context else evidence_dir / "uat-runtime-harness-evidence.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_evidence(evidence_path: Path) -> dict[str, Any]:
    payload = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evidence_root_not_object")
    return payload


def _evidence_sha_fields(evidence: Mapping[str, Any]) -> dict[str, str | None]:
    source = evidence.get("source") if isinstance(evidence.get("source"), Mapping) else {}
    run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
    runtime = evidence.get("runtime") if isinstance(evidence.get("runtime"), Mapping) else {}
    return {
        "sourceGitSha": _clean_optional_string(source.get("gitSha")),
        "sourceExpectedGitSha": _clean_optional_string(source.get("expectedGitSha")),
        "runSha": _clean_optional_string(run.get("sha")),
        "runtimeSha": _clean_optional_string(runtime.get("sha")),
    }


def _classify_evidence_freshness(evidence: Mapping[str, Any], *, required_sha: str | None) -> dict[str, Any]:
    sha_fields = _evidence_sha_fields(evidence)
    present = {key: value for key, value in sha_fields.items() if value}
    malformed = {key: value for key, value in present.items() if not _looks_like_git_sha(value)}
    required = _clean_optional_string(required_sha)
    run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
    run_id = _clean_optional_string(run.get("runId"))

    result: dict[str, Any] = {
        "classification": "UNKNOWN",
        "reasonCode": "sha_provenance_missing",
        "historicalOnly": False,
        "requiredSha": required,
        "runId": run_id,
        "sha": sha_fields,
    }
    if malformed:
        result.update(
            {
                "classification": "INVALID",
                "reasonCode": "sha_provenance_malformed",
                "malformedFields": malformed,
                "historicalOnly": True,
            }
        )
        return result

    authoritative_values = {
        value
        for key, value in present.items()
        if key in {"sourceGitSha", "sourceExpectedGitSha", "runSha", "runtimeSha"} and value
    }
    if len(authoritative_values) > 1:
        result.update(
            {
                "classification": "MISMATCH",
                "reasonCode": "sha_provenance_conflict",
                "historicalOnly": True,
            }
        )
        return result
    if not authoritative_values:
        return result

    evidence_sha = next(iter(authoritative_values))
    result["evidenceSha"] = evidence_sha
    if not required:
        result.update({"classification": "UNKNOWN", "reasonCode": "required_sha_missing"})
        return result
    if evidence_sha == required:
        result.update({"classification": "CURRENT", "reasonCode": "required_sha_matched"})
        return result
    result.update(
        {
            "classification": "STALE",
            "reasonCode": "required_sha_not_matched",
            "historicalOnly": True,
        }
    )
    return result


def _clean_optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _looks_like_git_sha(value: str) -> bool:
    return 7 <= len(value) <= 64 and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _parse_evidence_timestamp(evidence: Mapping[str, Any]) -> tuple[datetime | None, str]:
    run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
    for field_name, raw in (("generatedAt", evidence.get("generatedAt")), ("run.startTime", run.get("startTime"))):
        value = _clean_optional_string(raw)
        if not value:
            continue
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None, f"malformed_{field_name.replace('.', '_')}"
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc), field_name
    return None, "timestamp_missing"


def _selection_payload(
    *,
    path: Path,
    mode: str,
    selection_reason: str,
    freshness: Mapping[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "selectionReason": selection_reason,
        "evidencePath": str(path),
        "freshnessClassification": (freshness or {}).get("classification"),
        "freshnessReasonCode": (freshness or {}).get("reasonCode"),
        "runId": (freshness or {}).get("runId"),
        "requiredSha": (freshness or {}).get("requiredSha"),
        "evidenceSha": (freshness or {}).get("evidenceSha"),
        "timestamp": timestamp.isoformat() if timestamp else None,
        "historicalOnly": bool((freshness or {}).get("historicalOnly")),
    }


def _merge_selection_payload(
    selection: Mapping[str, Any] | None,
    *,
    path: Path,
    default_mode: str,
    default_reason: str,
    freshness: Mapping[str, Any],
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    payload = _selection_payload(
        path=path,
        mode=str((selection or {}).get("mode") or default_mode),
        selection_reason=str((selection or {}).get("selectionReason") or default_reason),
        freshness=freshness,
        timestamp=timestamp,
    )
    for key, value in (selection or {}).items():
        if value is not None:
            payload[key] = value
    return payload


def _candidate_selection_bucket(candidate: EvidenceCandidate) -> int:
    classification = str(candidate.freshness.get("classification") or "")
    if not candidate.loaded or classification == "INVALID":
        return 0
    if classification == "CURRENT":
        return 5
    if classification == "STALE":
        return 4
    if classification == "UNKNOWN":
        return 3 if candidate.timestamp else 2
    if classification == "MISMATCH":
        return 1
    return 1


def _build_evidence_candidate(path: Path, *, required_sha: str | None) -> EvidenceCandidate:
    legacy = path.name == "uat-runtime-harness-evidence.json"
    try:
        evidence = load_evidence(path)
        freshness = _classify_evidence_freshness(evidence, required_sha=required_sha)
        timestamp, timestamp_reason = _parse_evidence_timestamp(evidence)
        run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
        run_id = str(run.get("runId") or "")
        if freshness["classification"] == "INVALID":
            reason = str(freshness.get("reasonCode") or "invalid_provenance")
        elif timestamp is not None:
            reason = f"provenance_{freshness['classification'].lower()}_embedded_timestamp"
        elif not legacy:
            reason = f"provenance_{freshness['classification'].lower()}_filename"
        else:
            reason = f"legacy_fallback_{timestamp_reason}"
        return EvidenceCandidate(
            path=path,
            loaded=True,
            evidence=evidence,
            freshness=freshness,
            timestamp=timestamp,
            run_id=run_id,
            mtime=path.stat().st_mtime,
            legacy=legacy,
            selection_reason=reason,
        )
    except Exception as exc:
        freshness = {
            "classification": "INVALID",
            "reasonCode": "evidence_unreadable",
            "historicalOnly": True,
            "requiredSha": _clean_optional_string(required_sha),
            "errorType": type(exc).__name__,
            "sha": {},
        }
        return EvidenceCandidate(
            path=path,
            loaded=False,
            evidence=None,
            freshness=freshness,
            timestamp=None,
            run_id="",
            mtime=path.stat().st_mtime if path.exists() else 0.0,
            legacy=legacy,
            selection_reason="invalid_unreadable",
        )


def build_run_identity(
    *,
    run_context: RunContext,
    repo_root: Path,
    source: Mapping[str, Any],
    pid: int | None,
    cwd: str | None,
    port: int,
    asset_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "runId": run_context.run_id,
        "sha": source.get("gitSha"),
        "pid": pid,
        "cwd": cwd or str(repo_root),
        "startTime": run_context.start_time,
        "port": int(port),
        "assetIdentity": dict(asset_identity or {}),
        "evidencePath": str(run_context.evidence_path),
        "runLogPath": str(run_context.run_log_path),
    }


def build_runtime_log(run_context: RunContext, process: subprocess.Popen[str] | None = None) -> dict[str, Any]:
    run_context.run_log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"runId={run_context.run_id}",
        f"startTime={run_context.start_time}",
    ]
    if process is not None:
        lines.append(f"pid={process.pid}")
    existing = run_context.run_log_path.read_text(encoding="utf-8") if run_context.run_log_path.exists() else ""
    missing = [line for line in lines if line and line not in existing.splitlines()]
    if missing:
        with run_context.run_log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(missing) + "\n")
    if not existing and not missing:
        run_context.run_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": str(run_context.run_log_path),
        "startTime": run_context.start_time,
        "pid": process.pid if process is not None else None,
        "boundary": "per_run_file",
        "activityScope": "child_stdout_stderr_for_run",
        "historicalLogsRetained": True,
    }


def contamination_awareness(owner_before: PortOwner | None, *, direct_http: Mapping[str, Any] | None = None) -> dict[str, Any]:
    flags: list[str] = []
    if owner_before is not None:
        flags.append("port_already_owned_before_harness_start")
    if direct_http and not bool(direct_http.get("ok")):
        flags.append("direct_http_identity_unverified")
    return {
        "browserAttribution": "correlation_only",
        "unrelatedActivityMayContaminateCausalAttribution": bool(flags),
        "reasonCodes": flags,
        "coordination": "does_not_kill_browsers_or_unrelated_processes",
    }


def run_harness(
    *,
    repo_root: Path,
    expected_sha: str | None,
    host: str,
    port: int,
    evidence_dir: Path,
    skip_build: bool = False,
    prepare_uat_accounts: bool = False,
    stop_runtime_after: bool = False,
    readiness_timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any]]:
    repo_root = repo_root.resolve()
    static_root = repo_root / "static"
    evidence_dir = evidence_dir.resolve()
    run_context = create_run_context(evidence_dir)
    base_url = clean_base_url(f"http://{host}:{int(port)}")
    source = validate_source(repo_root, expected_sha)
    if not source["ok"]:
        evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
        evidence["run"] = build_run_identity(
            run_context=run_context,
            repo_root=repo_root,
            source=source,
            pid=None,
            cwd=str(repo_root),
            port=port,
        )
        evidence["runtimeLog"] = build_runtime_log(run_context)
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence, run_context=run_context))
        return EXIT_FAILED, evidence

    owner = find_port_owner(host, port)
    if owner is not None:
        evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
        evidence["run"] = build_run_identity(
            run_context=run_context,
            repo_root=repo_root,
            source=source,
            pid=None,
            cwd=str(repo_root),
            port=port,
        )
        evidence["runtimeLog"] = build_runtime_log(run_context)
        evidence["portOwner"] = owner.__dict__
        evidence["failure"] = "port_occupied_by_unrelated_process"
        evidence["contaminationAwareness"] = contamination_awareness(owner)
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence, run_context=run_context))
        evidence["run"]["evidencePath"] = evidence["evidencePath"]
        return EXIT_FAILED, evidence

    dependency_bootstrap = ensure_frontend_dependencies(repo_root)
    if dependency_bootstrap.get("action") == "failed":
        evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
        evidence["run"] = build_run_identity(
            run_context=run_context,
            repo_root=repo_root,
            source=source,
            pid=None,
            cwd=str(repo_root),
            port=port,
        )
        evidence["runtimeLog"] = build_runtime_log(run_context)
        evidence["frontendDependencyBootstrap"] = dependency_bootstrap
        evidence["failure"] = "frontend_dependency_bootstrap_failed"
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence, run_context=run_context))
        evidence["run"]["evidencePath"] = evidence["evidencePath"]
        return EXIT_FAILED, evidence

    if not skip_build:
        build_exit = run_frontend_build(repo_root)
        if build_exit != 0:
            evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
            evidence["run"] = build_run_identity(
                run_context=run_context,
                repo_root=repo_root,
                source=source,
                pid=None,
                cwd=str(repo_root),
                port=port,
            )
            evidence["runtimeLog"] = build_runtime_log(run_context)
            evidence["frontendDependencyBootstrap"] = dependency_bootstrap
            evidence["failure"] = "frontend_build_failed"
            evidence["buildExitCode"] = build_exit
            evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence, run_context=run_context))
            evidence["run"]["evidencePath"] = evidence["evidencePath"]
            return EXIT_FAILED, evidence

    local_build = verify_frontend_static_build(
        static_root=static_root,
        backend_info=read_backend_info(repo_root),
        repo_root=repo_root,
        require_build_identity=True,
    )
    if not local_build.ok:
        evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
        evidence["run"] = build_run_identity(
            run_context=run_context,
            repo_root=repo_root,
            source=source,
            pid=None,
            cwd=str(repo_root),
            port=port,
        )
        evidence["runtimeLog"] = build_runtime_log(run_context)
        evidence["frontendDependencyBootstrap"] = dependency_bootstrap
        evidence["failure"] = "frontend_build_provenance_failed"
        evidence["localBuild"] = _verification_dict(local_build)
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence, run_context=run_context))
        evidence["run"]["evidencePath"] = evidence["evidencePath"]
        return EXIT_FAILED, evidence

    uat_accounts = None
    if prepare_uat_accounts:
        uat_accounts = seed_uat_consumer_test_accounts()
        if uat_accounts.get("status") != "seeded":
            evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
            evidence["run"] = build_run_identity(
                run_context=run_context,
                repo_root=repo_root,
                source=source,
                pid=None,
                cwd=str(repo_root),
                port=port,
            )
            evidence["runtimeLog"] = build_runtime_log(run_context)
            evidence["frontendDependencyBootstrap"] = dependency_bootstrap
            evidence["failure"] = "uat_account_preparation_failed"
            evidence["uatAccountPreparation"] = uat_accounts
            evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence, run_context=run_context))
            evidence["run"]["evidencePath"] = evidence["evidencePath"]
            return EXIT_FAILED, evidence

    process: subprocess.Popen[str] | None = None
    try:
        runtime_log = build_runtime_log(run_context)
        expected_python = _select_runtime_python(repo_root)
        process = start_runtime(
            repo_root,
            host=host,
            port=port,
            python_bin=str(expected_python),
            run_log_path=run_context.run_log_path,
        )
        runtime_log = build_runtime_log(run_context, process)
        client = DirectNoProxyHttpClient()
        readiness = wait_for_readiness(client, base_url, timeout_seconds=readiness_timeout_seconds)
        runtime_cwd = process_cwd(process.pid)
        runtime_executable = process_executable(process.pid)
        runtime_command = process_command(process.pid)
        interpreter_identity = build_interpreter_identity(expected_python, runtime_executable)
        identity_errors: list[str] = []
        if runtime_cwd and Path(runtime_cwd).resolve() != repo_root:
            identity_errors.append("runtime_cwd_mismatch")
        elif not runtime_cwd and not is_windows():
            identity_errors.append("runtime_cwd_unverified")
        if interpreter_identity["status"] == "mismatch":
            identity_errors.append("runtime_interpreter_mismatch")
        elif interpreter_identity["status"] != "verified":
            identity_errors.append("runtime_interpreter_unverified")
        if not readiness["ok"]:
            identity_errors.append("runtime_readiness_failed")

        asset_identity = build_asset_identity(static_root, local_build.payload)
        direct_http = verify_direct_asset_identity(client, base_url, asset_identity) if readiness["ok"] else {
            "ok": False,
            "reasonCodes": ["readiness_unavailable"],
        }
        if not direct_http["ok"]:
            identity_errors.extend(direct_http.get("reasonCodes") or ["direct_http_failed"])

        smoke_report = run_runtime_smoke(
            base_url=base_url,
            client=client,
            git_head=source["gitSha"],
            local_build_result=local_build,
            admin_status_payload=None,
            surface_readiness_payload=None,
            auth_headers=None,
        )
        runtime = {
            "pid": process.pid,
            "cwd": runtime_cwd,
            "command": runtime_command,
            "interpreter": interpreter_identity,
            "listener": {"host": host, "port": int(port), "baseUrl": base_url},
            "processStartTime": process_start_time(process.pid),
            "ownedByHarness": True,
        }
        if smoke_report.get("checks", {}).get("runtimeBundle", {}).get("status") != "PASS":
            identity_errors.append("served_asset_identity_unverified")

        evidence = _base_evidence(repo_root, base_url, source, status="PASS" if not identity_errors else "FAIL")
        run_identity = build_run_identity(
            run_context=run_context,
            repo_root=repo_root,
            source=source,
            pid=process.pid,
            cwd=runtime_cwd,
            port=port,
            asset_identity=asset_identity,
        )
        evidence.update(
            {
                "run": run_identity,
                "runtimeLog": runtime_log,
                "frontendDependencyBootstrap": dependency_bootstrap,
                "runtime": runtime,
                "readiness": readiness,
                "proxyIsolation": {
                    "directClient": "urllib ProxyHandler({})",
                    "removedEnvKeys": list(PROXY_ENV_KEYS),
                    "noProxyMerged": True,
                },
                "directHttpHealth": readiness,
                "directHttpHtml": direct_http,
                "frontend": asset_identity,
                "providerIsolation": expected_provider_isolation(),
                "cryptoRealtimeIsolation": {"env": "CRYPTO_REALTIME_ENABLED=false", "productionDefaultChanged": False},
                "uatAccountPreparation": uat_accounts
                or {
                    "status": "skipped",
                    "writeScope": "none",
                    "optInFlag": "--prepare-uat-accounts",
                },
                "smokeReport": smoke_report,
                "contaminationAwareness": contamination_awareness(owner, direct_http=direct_http),
                "workbuddyHandoff": build_workbuddy_handoff(
                    run_id=run_context.run_id,
                    base_url=base_url,
                    expected_git_sha=source["gitSha"],
                    runtime_pid=process.pid,
                    runtime_cwd=runtime_cwd,
                    asset_identity=asset_identity,
                    run_log_path=str(run_context.run_log_path),
                    run_start_time=run_context.start_time,
                ),
                "identityErrors": identity_errors,
            }
        )
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence, run_context=run_context))
        evidence["run"]["evidencePath"] = evidence["evidencePath"]
        return (EXIT_OK if not identity_errors else EXIT_FAILED), evidence
    finally:
        if stop_runtime_after:
            stop_result = stop_owned_runtime(process)
            if process is not None:
                build_runtime_log(run_context, process)
            try:
                if "evidence" in locals():
                    evidence["runtimeStop"] = {
                        **stop_result,
                        "stopTime": datetime.now(timezone.utc).isoformat(),
                    }
                    write_evidence(evidence_dir, evidence, run_context=run_context)
            except Exception:
                pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, launch, and verify a deterministic local UAT runtime.")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Read an existing run evidence JSON and emit machine-readable preflight JSON.",
    )
    parser.add_argument(
        "--stop-from-evidence",
        action="store_true",
        help="Stop only the task-owned runtime described by an evidence JSON file.",
    )
    parser.add_argument(
        "--evidence-path",
        type=Path,
        default=None,
        help="Evidence JSON path for --preflight or --stop-from-evidence.",
    )
    parser.add_argument("--repo-root", type=Path, default=None, help="Repository root. Defaults to git root.")
    parser.add_argument("--expected-sha", default=None, help="Fail if HEAD does not match this SHA.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Local bind host.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local bind port.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR, help="Evidence output directory.")
    parser.add_argument("--skip-build", action="store_true", help="Use only for diagnostics; default rebuilds frontend.")
    parser.add_argument(
        "--prepare-uat-accounts",
        action="store_true",
        help="Opt in to local non-production DB writes for deterministic UAT consumer accounts.",
    )
    parser.add_argument("--stop-runtime-after", action="store_true", help="Stop only the runtime started by this harness.")
    parser.add_argument("--readiness-timeout", type=float, default=DEFAULT_READINESS_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true", help="Print full JSON evidence to stdout.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = args.repo_root or resolve_repo_root()
    evidence_dir = args.evidence_dir
    if not evidence_dir.is_absolute():
        evidence_dir = repo_root / evidence_dir

    if args.preflight:
        if args.evidence_path:
            evidence_path = args.evidence_path
            selection = _selection_payload(
                path=evidence_path,
                mode="explicit",
                selection_reason="explicit_evidence_path",
            )
        else:
            evidence_path, selection = _latest_evidence_path(
                evidence_dir,
                required_sha=args.expected_sha,
                return_selection=True,
            )
        try:
            result = run_preflight(
                evidence_path=evidence_path,
                expected_sha=args.expected_sha,
                host=args.host,
                port=args.port,
                selection=selection,
            )
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            result = _preflight_error_result(evidence_path=evidence_path, error=exc)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_OK if result.get("status") == "PASS" else EXIT_FAILED

    if args.stop_from_evidence:
        implicit_stop = args.evidence_path is None
        if args.evidence_path:
            evidence_path = args.evidence_path
            selection = _selection_payload(
                path=evidence_path,
                mode="explicit",
                selection_reason="explicit_evidence_path",
            )
        else:
            evidence_path, selection = _latest_evidence_path(
                evidence_dir,
                required_sha=args.expected_sha,
                return_selection=True,
            )
        try:
            result = stop_runtime_from_evidence(
                evidence_path,
                required_sha=args.expected_sha,
                enforce_current=implicit_stop,
                selection=selection,
            )
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            result = {
                "status": "rejected",
                "reasonCode": "evidence_unreadable",
                "evidencePath": str(evidence_path),
                "errorType": type(exc).__name__,
            }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_OK if result.get("status") in {"stopped", "absent"} else EXIT_FAILED

    exit_code, evidence = run_harness(
        repo_root=repo_root,
        expected_sha=args.expected_sha,
        host=args.host,
        port=args.port,
        evidence_dir=evidence_dir,
        skip_build=bool(args.skip_build),
        prepare_uat_accounts=bool(args.prepare_uat_accounts),
        stop_runtime_after=bool(args.stop_runtime_after),
        readiness_timeout_seconds=float(args.readiness_timeout),
    )

    if args.json:
        json.dump(evidence, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        _print_summary(evidence)
    return exit_code


def _base_evidence(repo_root: Path, base_url: str, source: Mapping[str, Any], *, status: str) -> dict[str, Any]:
    return {
        "contract": "wolfystock_uat_runtime_harness_v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "worktreePath": str(repo_root),
        "baseUrl": base_url,
        "source": dict(source),
    }


def _verification_dict(result: Any) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "payload": result.payload,
        "errorCodes": result.error_codes,
        "warningCodes": result.warning_codes,
    }


def run_preflight(
    *,
    evidence_path: Path,
    expected_sha: str | None,
    host: str,
    port: int | None = None,
    selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = load_evidence(evidence_path)
    run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
    runtime = evidence.get("runtime") if isinstance(evidence.get("runtime"), Mapping) else {}
    source = evidence.get("source") if isinstance(evidence.get("source"), Mapping) else {}
    frontend = evidence.get("frontend") if isinstance(evidence.get("frontend"), Mapping) else {}
    run_port = _safe_int(port if port is not None else run.get("port"))
    run_pid = _safe_int(run.get("pid"))
    expected_cwd = str(run.get("cwd") or "")
    expected_start = str(runtime.get("processStartTime") or "").strip()
    expected_command = _normalize_command_line(runtime.get("command"))
    expected_asset = dict(run.get("assetIdentity") if isinstance(run.get("assetIdentity"), Mapping) else frontend)
    expected_asset_name = str(expected_asset.get("mainJsAssetFilename") or frontend.get("mainJsAssetFilename") or "")
    expected_asset_hashes = (
        dict(expected_asset.get("assetHashes"))
        if isinstance(expected_asset.get("assetHashes"), Mapping)
        else {}
    )
    expected_build_identity = (
        dict(expected_asset.get("buildIdentity"))
        if isinstance(expected_asset.get("buildIdentity"), Mapping)
        else {}
    )
    expected_interpreter = (
        dict(runtime.get("interpreter"))
        if isinstance(runtime.get("interpreter"), Mapping)
        else {}
    )

    freshness = _classify_evidence_freshness(evidence, required_sha=expected_sha)
    checks: dict[str, dict[str, Any]] = {}
    evidence_status = str(evidence.get("status") or "")
    checks["evidenceStatus"] = _preflight_check(evidence_status == "PASS", expected="PASS", observed=evidence_status)

    observed_sha = str(source.get("gitSha") or run.get("sha") or "")
    sha_expected = expected_sha or str(run.get("sha") or "")
    checks["sha"] = _preflight_check(
        bool(observed_sha and (not sha_expected or observed_sha == sha_expected)),
        expected=sha_expected,
        observed=observed_sha,
    )
    checks["evidenceFreshness"] = _preflight_check(
        freshness.get("classification") == "CURRENT" if expected_sha else freshness.get("classification") != "INVALID",
        expected="CURRENT" if expected_sha else "readable_non_invalid_provenance",
        observed=freshness,
    )

    probe = _probe_process(run_pid)
    alive = probe.state == "alive"
    checks["pidAlive"] = _preflight_check(
        alive,
        expected={"state": "alive"},
        observed={"state": probe.state, "windowsError": probe.windows_error},
    )
    checks["ownedByHarness"] = _preflight_check(
        runtime.get("ownedByHarness") is True,
        expected=True,
        observed=runtime.get("ownedByHarness"),
    )

    owner = find_port_owner(host, run_port)
    owner_payload = owner.__dict__ if owner else None
    checks["pidOwnsPort"] = _preflight_check(
        bool(owner and owner.pid == run_pid),
        expected={"pid": run_pid, "port": run_port},
        observed=owner_payload,
    )

    observed_cwd = process_cwd(run_pid) if run_pid > 0 else None
    if expected_cwd and observed_cwd:
        cwd_ok = Path(observed_cwd).resolve() == Path(expected_cwd).resolve()
        checks["cwd"] = _preflight_check(cwd_ok, expected=expected_cwd, observed=observed_cwd)
    elif is_windows() and expected_cwd and observed_cwd is None:
        checks["cwd"] = _preflight_check_unavailable(
            expected=expected_cwd,
            observed={"cwd": None, "reasonCode": "cwd_unobservable"},
        )
    else:
        checks["cwd"] = _preflight_check(False, expected=expected_cwd, observed=observed_cwd)

    observed_start = str(process_start_time(run_pid) or "").strip() if run_pid > 0 else ""
    start_required = is_windows() or bool(expected_start)
    checks["processStartTime"] = _preflight_check(
        bool(not start_required or (expected_start and observed_start and expected_start == observed_start)),
        expected=expected_start or ("present" if start_required else None),
        observed=observed_start or None,
    )

    observed_command = _normalize_command_line(process_command(run_pid)) if run_pid > 0 else ""
    command_required = bool(
        is_windows()
        and (
            expected_command
            or (expected_cwd and observed_cwd is None)
        )
    )
    command_ok = bool(
        not command_required
        or (expected_command and observed_command and expected_command == observed_command)
    )
    checks["commandIdentity"] = _preflight_check(
        command_ok,
        expected=expected_command or ("present" if command_required else None),
        observed=observed_command or None,
    )

    expected_interpreter_path = str(expected_interpreter.get("expectedResolvedPath") or "")
    observed_executable = process_executable(run_pid) if run_pid > 0 else None
    if expected_interpreter_path:
        observed_interpreter = build_interpreter_identity(Path(expected_interpreter_path), observed_executable)
    else:
        observed_interpreter = {
            "status": "unverified",
            "expectedResolvedPath": None,
            "observedPath": observed_executable,
        }
    checks["interpreterIdentity"] = _preflight_check(
        bool(
            expected_interpreter.get("status") == "verified"
            and observed_interpreter.get("status") == "verified"
        ),
        expected=expected_interpreter or "verified_interpreter_identity",
        observed=observed_interpreter,
    )

    expected_index_hash = str(expected_asset.get("indexHtmlHash") or "")
    expected_main_hash = str(expected_asset_hashes.get(expected_asset_name) or "")
    checks["assetIdentity"] = _preflight_check(
        bool(expected_index_hash and expected_asset_name and expected_main_hash),
        expected="index_and_main_asset_hashes",
        observed=expected_asset,
    )
    checks["buildIdentity"] = _preflight_check(
        bool(
            expected_build_identity.get("contract") == "wolfystock_frontend_build_identity_v1"
            and str(expected_build_identity.get("gitSha") or "") == observed_sha
            and str(expected_build_identity.get("repositoryRoot") or "") == expected_cwd
            and str(expected_build_identity.get("indexHtmlSha256") or "") == expected_index_hash
            and str(expected_build_identity.get("mainJsAssetFilename") or "") == expected_asset_name
            and str(expected_build_identity.get("mainJsAssetSha256") or "") == expected_main_hash
        ),
        expected={
            "contract": "wolfystock_frontend_build_identity_v1",
            "gitSha": observed_sha,
            "repositoryRoot": expected_cwd,
        },
        observed=expected_build_identity or None,
    )

    direct_http = _preflight_direct_http(host=host, port=run_port, expected_asset=expected_asset)
    checks["directNoProxyHttp"] = _preflight_check(
        bool(direct_http.get("ok")),
        expected={
            "noProxy": True,
            "asset": expected_asset_name or None,
            "indexHtmlHash": expected_index_hash or None,
            "assetHashes": expected_asset_hashes,
        },
        observed=direct_http,
    )

    start_time = str(run.get("startTime") or "")
    checks["runStartTimestamp"] = _preflight_check(bool(start_time), expected="present", observed=start_time)

    run_log_path = str(run.get("runLogPath") or "")
    checks["runLogPath"] = _preflight_check(
        bool(run_log_path),
        expected="bound_run_log_path",
        observed={"path": run_log_path, "exists": Path(run_log_path).exists() if run_log_path else False},
    )

    status = "PASS" if all(item["status"] != "FAIL" for item in checks.values()) else "FAIL"
    return {
        "contract": "wolfystock_uat_runtime_preflight_v1",
        "status": status,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evidencePath": str(evidence_path),
        "selection": _merge_selection_payload(
            selection,
            path=evidence_path,
            default_mode="explicit",
            default_reason="explicit_evidence_path",
            freshness=freshness,
        ),
        "evidenceFreshness": freshness,
        "host": host,
        "port": run_port,
        "run": {
            "runId": run.get("runId"),
            "sha": observed_sha,
            "pid": run_pid,
            "cwd": expected_cwd,
            "startTime": start_time,
            "port": run_port,
            "assetIdentity": expected_asset,
            "interpreterIdentity": expected_interpreter,
            "evidencePath": str(run.get("evidencePath") or evidence_path),
            "runLogPath": run_log_path,
        },
        "checks": checks,
    }


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def _merge_no_proxy(value: str | None) -> str:
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    for item in ("127.0.0.1", "localhost", "::1"):
        if item not in parts:
            parts.append(item)
    return ",".join(parts)


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def _css_assets(static_root: Path) -> list[str]:
    assets_dir = static_root / "assets"
    if not assets_dir.is_dir():
        return []
    return sorted(path.name for path in assets_dir.glob("*.css") if path.is_file())


def _asset_hashes(static_root: Path, filenames: Sequence[str]) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for filename in filenames:
        if not filename:
            continue
        hashes[filename] = _sha256_file(static_root / "assets" / filename)
    return hashes


def _preflight_direct_http(
    *,
    host: str,
    port: int,
    expected_asset: Mapping[str, Any],
) -> dict[str, Any]:
    base_url = clean_base_url(f"http://{host}:{int(port)}")
    try:
        return {
            **verify_direct_asset_identity(DirectNoProxyHttpClient(), base_url, expected_asset),
            "noProxy": True,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "expectedAssetFilename": str(expected_asset.get("mainJsAssetFilename") or "") or None,
            "noProxy": True,
        }


def _preflight_check(ok: bool, *, expected: Any, observed: Any) -> dict[str, Any]:
    return {
        "status": "PASS" if ok else "FAIL",
        "expected": expected,
        "observed": observed,
    }


def _preflight_check_unavailable(*, expected: Any, observed: Any) -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "expected": expected,
        "observed": observed,
    }


def _preflight_error_result(*, evidence_path: Path, error: Exception) -> dict[str, Any]:
    return {
        "contract": "wolfystock_uat_runtime_preflight_v1",
        "status": "FAIL",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evidencePath": str(evidence_path),
        "checks": {
            "evidenceReadable": {
                "status": "FAIL",
                "expected": "readable_json_object",
                "observed": {
                    "errorType": type(error).__name__,
                    "reasonCode": "evidence_unreadable",
                },
            }
        },
    }


def _append_lifecycle_event(evidence_path: Path, result: Mapping[str, Any]) -> None:
    try:
        evidence = load_evidence(evidence_path)
        events = evidence.get("lifecycleEvents")
        if not isinstance(events, list):
            events = []
        events.append({"at": datetime.now(timezone.utc).isoformat(), **dict(result)})
        evidence["lifecycleEvents"] = events
        Path(evidence_path).write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        return


def _close_runtime_log_handle(process: subprocess.Popen[str]) -> None:
    handle = getattr(process, "_wolfystock_run_log_handle", None)
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _latest_evidence_path(
    evidence_dir: Path,
    *,
    required_sha: str | None = None,
    requested_run_id: str | None = None,
    return_selection: bool = False,
) -> Path | tuple[Path, dict[str, Any]]:
    candidates: list[Path] = sorted(evidence_dir.glob("uat-*-evidence.json"), key=lambda item: item.name)
    legacy = evidence_dir / "uat-runtime-harness-evidence.json"
    if legacy.exists():
        candidates.append(legacy)
    if candidates:
        ranked = [_build_evidence_candidate(path, required_sha=required_sha) for path in candidates]
        requested = _clean_optional_string(requested_run_id)
        if requested:
            exact = [candidate for candidate in ranked if candidate.loaded and candidate.run_id == requested]
            if exact:
                selected = sorted(
                    exact,
                    key=lambda candidate: (
                        -_candidate_selection_bucket(candidate),
                        -(candidate.timestamp.timestamp() if candidate.timestamp else float("-inf")),
                        candidate.path.name,
                    ),
                )[0]
                payload = _selection_payload(
                    path=selected.path,
                    mode="implicit",
                    selection_reason="requested_run_id_match",
                    freshness=selected.freshness,
                    timestamp=selected.timestamp,
                )
                return (selected.path, payload) if return_selection else selected.path

        selected = sorted(
            ranked,
            key=lambda candidate: (
                -_candidate_selection_bucket(candidate),
                -(candidate.timestamp.timestamp() if candidate.timestamp else float("-inf")),
                candidate.legacy,
                candidate.path.name,
                -candidate.mtime,
            ),
        )[0]
        if selected.loaded and selected.freshness.get("classification") != "INVALID":
            payload = _selection_payload(
                path=selected.path,
                mode="implicit",
                selection_reason=selected.selection_reason,
                freshness=selected.freshness,
                timestamp=selected.timestamp,
            )
            return (selected.path, payload) if return_selection else selected.path
        valid = [candidate for candidate in ranked if candidate.loaded and candidate.freshness.get("classification") != "INVALID"]
        if valid:
            fallback = sorted(valid, key=lambda candidate: (candidate.path.name, -candidate.mtime))[0]
            payload = _selection_payload(
                path=fallback.path,
                mode="implicit",
                selection_reason="valid_legacy_compatibility_fallback",
                freshness=fallback.freshness,
                timestamp=fallback.timestamp,
            )
            return (fallback.path, payload) if return_selection else fallback.path
        payload = _selection_payload(
            path=selected.path,
            mode="implicit",
            selection_reason="no_valid_evidence_candidate",
            freshness=selected.freshness,
            timestamp=selected.timestamp,
        )
        return (selected.path, payload) if return_selection else selected.path
    raise FileNotFoundError(f"no UAT runtime evidence JSON found under {evidence_dir}")


def _print_summary(evidence: Mapping[str, Any]) -> None:
    print(f"UAT runtime harness: {evidence.get('status')}")
    print(f"Worktree: {evidence.get('worktreePath')}")
    print(f"Git SHA: {evidence.get('source', {}).get('gitSha')}")
    runtime = evidence.get("runtime") if isinstance(evidence.get("runtime"), Mapping) else {}
    if runtime:
        print(f"Runtime PID: {runtime.get('pid')}")
        print(f"Runtime CWD: {runtime.get('cwd')}")
    print(f"Evidence: {evidence.get('evidencePath')}")
    if evidence.get("identityErrors"):
        print("Errors: " + ", ".join(str(item) for item in evidence.get("identityErrors") or []))
    if evidence.get("failure"):
        print(f"Failure: {evidence.get('failure')}")


if __name__ == "__main__":
    raise SystemExit(main())
