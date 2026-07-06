#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic local UAT runtime harness for WolfyStock.

This script composes the existing fresh-build verifier, local UAT account
seeder, and runtime smoke logic into one local command. It owns only the
process it starts and writes evidence under output/runtime-verification/.
"""

from __future__ import annotations

import argparse
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
                body = response.read(1024 * 1024).decode("utf-8", errors="ignore")
                return _HttpResponse(int(response.status), body)
        except urllib.error.HTTPError as exc:
            body = exc.read(65536).decode("utf-8", errors="ignore")
            return _HttpResponse(int(exc.code), body)


class _HttpResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = int(status_code)
        self.text = text

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


def process_command(pid: int) -> str | None:
    if pid <= 0:
        return None
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


def start_runtime(
    repo_root: Path,
    *,
    host: str,
    port: int,
    python_bin: str | None = None,
    run_log_path: Path | None = None,
) -> subprocess.Popen[str]:
    python = python_bin or str(repo_root / ".venv" / "bin" / "python")
    if not Path(python).exists():
        python = sys.executable
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
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_runtime_from_evidence(evidence_path: Path) -> dict[str, Any]:
    evidence = load_evidence(evidence_path)
    run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
    runtime = evidence.get("runtime") if isinstance(evidence.get("runtime"), Mapping) else {}
    pid = _safe_int(run.get("pid"))
    expected_cwd = str(run.get("cwd") or "")
    if pid <= 0:
        return {"status": "rejected", "reasonCode": "pid_missing", "pid": pid}

    if runtime.get("ownedByHarness") is not True:
        result = {
            "status": "rejected",
            "reasonCode": "not_harness_owned",
            "pid": pid,
        }
        _append_lifecycle_event(evidence_path, result)
        return result

    if not pid_is_alive(pid):
        result = {"status": "absent", "reasonCode": "runtime_already_absent", "pid": pid}
        _append_lifecycle_event(evidence_path, result)
        return result

    expected_start = str(runtime.get("processStartTime") or "").strip()
    observed_start = str(process_start_time(pid) or "").strip()
    if expected_start and observed_start and expected_start != observed_start:
        result = {
            "status": "rejected",
            "reasonCode": "pid_reused",
            "pid": pid,
            "expectedProcessStartTime": expected_start,
            "observedProcessStartTime": observed_start,
        }
        _append_lifecycle_event(evidence_path, result)
        return result

    observed_cwd = process_cwd(pid)
    if expected_cwd and observed_cwd and Path(observed_cwd).resolve() != Path(expected_cwd).resolve():
        result = {
            "status": "rejected",
            "reasonCode": "pid_cwd_mismatch",
            "pid": pid,
            "expectedCwd": expected_cwd,
            "observedCwd": observed_cwd,
        }
        _append_lifecycle_event(evidence_path, result)
        return result
    if expected_cwd and not observed_cwd:
        result = {
            "status": "rejected",
            "reasonCode": "pid_cwd_unavailable",
            "pid": pid,
            "expectedCwd": expected_cwd,
            "observedCwd": observed_cwd,
        }
        _append_lifecycle_event(evidence_path, result)
        return result

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
            _append_lifecycle_event(evidence_path, result)
            return result
        if owner is None:
            result = {
                "status": "rejected",
                "reasonCode": "pid_not_port_owner",
                "pid": pid,
                "expectedPort": expected_port,
            }
            _append_lifecycle_event(evidence_path, result)
            return result

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        result = {"status": "absent", "reasonCode": "runtime_already_absent", "pid": pid}
        _append_lifecycle_event(evidence_path, result)
        return result
    result = {"status": "stopped", "reasonCode": "task_owned_pid_terminated", "pid": pid, "cwd": observed_cwd}
    _append_lifecycle_event(evidence_path, result)
    return result


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


def verify_direct_html(client: DirectNoProxyHttpClient, base_url: str, local_payload: Mapping[str, Any]) -> dict[str, Any]:
    response = client.request("GET", base_url + "/")
    body = response.text or ""
    expected_asset = str(local_payload.get("frontendMainAssetFilename") or "")
    marker_ok = int(response.status_code) == 200 and all(marker in body for marker in WOLFYSTOCK_HTML_MARKERS)
    asset_ok = bool(expected_asset and expected_asset in body)
    return {
        "ok": marker_ok and asset_ok,
        "httpStatus": int(response.status_code),
        "wolfyStockHtml": marker_ok,
        "expectedAssetPresent": asset_ok,
        "expectedAssetFilename": expected_asset or None,
        "reasonCodes": [] if marker_ok and asset_ok else ["direct_http_html_identity_mismatch"],
    }


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
        process = start_runtime(repo_root, host=host, port=port, run_log_path=run_context.run_log_path)
        runtime_log = build_runtime_log(run_context, process)
        client = DirectNoProxyHttpClient()
        readiness = wait_for_readiness(client, base_url, timeout_seconds=readiness_timeout_seconds)
        runtime_cwd = process_cwd(process.pid)
        runtime_command = process_command(process.pid)
        identity_errors: list[str] = []
        if runtime_cwd and Path(runtime_cwd).resolve() != repo_root:
            identity_errors.append("runtime_cwd_mismatch")
        if not readiness["ok"]:
            identity_errors.append("runtime_readiness_failed")

        direct_http = verify_direct_html(client, base_url, local_build.payload) if readiness["ok"] else {
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
        asset_identity = build_asset_identity(static_root, local_build.payload)
        runtime = {
            "pid": process.pid,
            "cwd": runtime_cwd,
            "command": runtime_command,
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
        evidence_path = args.evidence_path or _latest_evidence_path(evidence_dir)
        try:
            result = run_preflight(
                evidence_path=evidence_path,
                expected_sha=args.expected_sha,
                host=args.host,
                port=args.port,
            )
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            result = _preflight_error_result(evidence_path=evidence_path, error=exc)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_OK if result.get("status") == "PASS" else EXIT_FAILED

    if args.stop_from_evidence:
        evidence_path = args.evidence_path or _latest_evidence_path(evidence_dir)
        try:
            result = stop_runtime_from_evidence(evidence_path)
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
) -> dict[str, Any]:
    evidence = load_evidence(evidence_path)
    run = evidence.get("run") if isinstance(evidence.get("run"), Mapping) else {}
    source = evidence.get("source") if isinstance(evidence.get("source"), Mapping) else {}
    frontend = evidence.get("frontend") if isinstance(evidence.get("frontend"), Mapping) else {}
    run_port = _safe_int(port if port is not None else run.get("port"))
    run_pid = _safe_int(run.get("pid"))
    expected_cwd = str(run.get("cwd") or "")
    expected_asset = dict(run.get("assetIdentity") if isinstance(run.get("assetIdentity"), Mapping) else frontend)
    expected_asset_name = str(expected_asset.get("mainJsAssetFilename") or frontend.get("mainJsAssetFilename") or "")

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

    alive = pid_is_alive(run_pid)
    checks["pidAlive"] = _preflight_check(alive, expected=True, observed=alive)

    owner = find_port_owner(host, run_port)
    owner_payload = owner.__dict__ if owner else None
    checks["pidOwnsPort"] = _preflight_check(
        bool(owner and owner.pid == run_pid),
        expected={"pid": run_pid, "port": run_port},
        observed=owner_payload,
    )

    observed_cwd = process_cwd(run_pid) if run_pid > 0 else None
    cwd_ok = bool(
        expected_cwd
        and observed_cwd
        and Path(observed_cwd).resolve() == Path(expected_cwd).resolve()
    )
    checks["cwd"] = _preflight_check(cwd_ok, expected=expected_cwd, observed=observed_cwd)

    asset_ok = bool(expected_asset.get("indexHtmlHash") or expected_asset_name)
    checks["assetIdentity"] = _preflight_check(asset_ok, expected="non-empty", observed=expected_asset)

    direct_http = _preflight_direct_http(host=host, port=run_port, expected_asset_name=expected_asset_name)
    checks["directNoProxyHttp"] = _preflight_check(
        bool(direct_http.get("ok")),
        expected={"noProxy": True, "asset": expected_asset_name or None},
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

    status = "PASS" if all(item["status"] == "PASS" for item in checks.values()) else "FAIL"
    return {
        "contract": "wolfystock_uat_runtime_preflight_v1",
        "status": status,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evidencePath": str(evidence_path),
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


def _preflight_direct_http(*, host: str, port: int, expected_asset_name: str) -> dict[str, Any]:
    base_url = clean_base_url(f"http://{host}:{int(port)}")
    try:
        response = DirectNoProxyHttpClient().request("GET", base_url + "/")
        body = response.text or ""
        marker_ok = int(response.status_code) == 200 and all(marker in body for marker in WOLFYSTOCK_HTML_MARKERS)
        asset_ok = bool(not expected_asset_name or expected_asset_name in body)
        return {
            "ok": marker_ok and asset_ok,
            "httpStatus": int(response.status_code),
            "wolfyStockHtml": marker_ok,
            "expectedAssetPresent": asset_ok,
            "expectedAssetFilename": expected_asset_name or None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "expectedAssetFilename": expected_asset_name or None,
        }


def _preflight_check(ok: bool, *, expected: Any, observed: Any) -> dict[str, Any]:
    return {
        "status": "PASS" if ok else "FAIL",
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


def _latest_evidence_path(evidence_dir: Path) -> Path:
    matches = sorted(evidence_dir.glob("uat-*-evidence.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]
    legacy = evidence_dir / "uat-runtime-harness-evidence.json"
    if legacy.exists():
        return legacy
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
