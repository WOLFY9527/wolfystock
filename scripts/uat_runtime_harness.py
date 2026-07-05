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
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.seed_uat_consumer_test_accounts import seed_uat_consumer_test_accounts
from scripts.uat_fresh_build_verifier import (
    VerificationResult,
    read_backend_info,
    resolve_repo_root,
    run_frontend_build,
    verify_frontend_static_build,
    verify_generated_artifact_hygiene,
    verify_git_preflight,
)
from scripts.uat_runtime_smoke_pack import clean_base_url, run_runtime_smoke


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_EVIDENCE_DIR = Path("output/runtime-verification")
DEFAULT_READINESS_TIMEOUT_SECONDS = 90.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 5.0
WOLFYSTOCK_HTML_MARKERS = ("WolfyStock", "/assets/")
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


def start_runtime(repo_root: Path, *, host: str, port: int, python_bin: str | None = None) -> subprocess.Popen[str]:
    python = python_bin or str(repo_root / ".venv" / "bin" / "python")
    if not Path(python).exists():
        python = sys.executable
    command = [python, str(repo_root / "main.py"), "--serve-only", "--host", host, "--port", str(port)]
    return subprocess.Popen(
        command,
        cwd=repo_root,
        env=build_uat_runtime_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_owned_runtime(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


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
    base_url: str,
    expected_git_sha: str,
    runtime_pid: int,
    runtime_cwd: str | None,
    asset_identity: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "directUrl": base_url,
        "expectedGitSha": expected_git_sha,
        "runtimePid": runtime_pid,
        "runtimeCwd": runtime_cwd,
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


def write_evidence(evidence_dir: Path, evidence: Mapping[str, Any]) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / "uat-runtime-harness-evidence.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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
    base_url = clean_base_url(f"http://{host}:{int(port)}")
    source = validate_source(repo_root, expected_sha)
    if not source["ok"]:
        evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence))
        return EXIT_FAILED, evidence

    owner = find_port_owner(host, port)
    if owner is not None:
        evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
        evidence["portOwner"] = owner.__dict__
        evidence["failure"] = "port_occupied_by_unrelated_process"
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence))
        return EXIT_FAILED, evidence

    if not skip_build:
        build_exit = run_frontend_build(repo_root)
        if build_exit != 0:
            evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
            evidence["failure"] = "frontend_build_failed"
            evidence["buildExitCode"] = build_exit
            evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence))
            return EXIT_FAILED, evidence

    local_build = verify_frontend_static_build(
        static_root=static_root,
        backend_info=read_backend_info(repo_root),
        repo_root=repo_root,
    )
    if not local_build.ok:
        evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
        evidence["failure"] = "frontend_build_provenance_failed"
        evidence["localBuild"] = _verification_dict(local_build)
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence))
        return EXIT_FAILED, evidence

    uat_accounts = None
    if prepare_uat_accounts:
        uat_accounts = seed_uat_consumer_test_accounts()
        if uat_accounts.get("status") != "seeded":
            evidence = _base_evidence(repo_root, base_url, source, status="FAIL")
            evidence["failure"] = "uat_account_preparation_failed"
            evidence["uatAccountPreparation"] = uat_accounts
            evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence))
            return EXIT_FAILED, evidence

    process: subprocess.Popen[str] | None = None
    try:
        process = start_runtime(repo_root, host=host, port=port)
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
        evidence.update(
            {
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
                "workbuddyHandoff": build_workbuddy_handoff(
                    base_url=base_url,
                    expected_git_sha=source["gitSha"],
                    runtime_pid=process.pid,
                    runtime_cwd=runtime_cwd,
                    asset_identity=asset_identity,
                ),
                "identityErrors": identity_errors,
            }
        )
        evidence["evidencePath"] = str(write_evidence(evidence_dir, evidence))
        return (EXIT_OK if not identity_errors else EXIT_FAILED), evidence
    finally:
        if stop_runtime_after:
            stop_owned_runtime(process)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, launch, and verify a deterministic local UAT runtime.")
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


def _verification_dict(result: VerificationResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "payload": result.payload,
        "errorCodes": result.error_codes,
        "warningCodes": result.warning_codes,
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
