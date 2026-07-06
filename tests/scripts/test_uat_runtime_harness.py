from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.uat_runtime_harness as harness
from scripts.uat_fresh_build_verifier import VerificationResult


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> dict[str, object]:
        return json.loads(self.text or "{}")


class _FakeClient:
    def __init__(self, *, asset_name: str = "index-CKPdXr8Q.js") -> None:
        self.asset_name = asset_name
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, headers: dict[str, str] | None = None) -> _FakeResponse:
        self.calls.append((method, url))
        if url.endswith("/api/health"):
            return _FakeResponse(200, '{"status":"ok"}')
        if url.endswith("/"):
            return _FakeResponse(
                200,
                f'<html><title>WolfyStock</title><script type="module" src="/assets/{self.asset_name}"></script></html>',
            )
        if url.endswith(f"/assets/{self.asset_name}"):
            return _FakeResponse(200, "console.log('ok');")
        return _FakeResponse(200, "{}")


class _FakeProcess:
    pid = 43210

    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


class _AlreadyAbsentProcess:
    pid = 54321

    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def poll(self) -> int:
        return 7

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def _write_static(root: Path, *, asset_name: str = "index-CKPdXr8Q.js") -> None:
    static = root / "static"
    assets = static / "assets"
    assets.mkdir(parents=True)
    (static / "index.html").write_text(
        f'<html><title>WolfyStock</title><script type="module" src="/assets/{asset_name}"></script></html>',
        encoding="utf-8",
    )
    (assets / asset_name).write_text("console.log('ok');\n", encoding="utf-8")
    (assets / "index-CSS123.css").write_text("body{color:#111}\n", encoding="utf-8")


def _local_build(asset_name: str = "index-CKPdXr8Q.js") -> VerificationResult:
    return VerificationResult(
        ok=True,
        payload={
            "backendGitSha": "45b6965d",
            "backendBranch": "codex/t157-deterministic-uat-runtime-harness",
            "frontendMainAssetFilename": asset_name,
            "frontendMainAssetHash": "CKPdXr8Q",
            "frontendStaticBuildTimestamp": "2026-07-05T00:00:00+00:00",
            "freshnessStatus": "fresh",
            "stale": False,
        },
    )


def _valid_source(expected_sha: str = "45b6965d") -> dict[str, object]:
    return {
        "ok": True,
        "gitSha": expected_sha,
        "branch": "codex/t164-uat-harness-hardening",
        "commitTimestamp": "2026-07-05T00:00:00+00:00",
        "expectedGitSha": expected_sha,
        "errorCodes": [],
    }


def test_build_uat_runtime_env_removes_proxy_vars_and_sets_isolation_flags() -> None:
    env = harness.build_uat_runtime_env(
        {
            "HTTP_PROXY": "http://proxy.invalid:8080",
            "HTTPS_PROXY": "http://proxy.invalid:8443",
            "ALL_PROXY": "socks5://proxy.invalid:1080",
            "NO_PROXY": "example.invalid",
        }
    )

    assert "HTTP_PROXY" not in env
    assert "HTTPS_PROXY" not in env
    assert "ALL_PROXY" not in env
    assert env["CRYPTO_REALTIME_ENABLED"] == "false"
    assert env["WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS"] == "true"
    assert env["WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED"] == "false"
    assert env["WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED"] == "false"
    assert "127.0.0.1" in env["NO_PROXY"]
    assert "localhost" in env["NO_PROXY"]


def test_frontend_dependency_bootstrap_runs_npm_ci_when_required(monkeypatch, tmp_path: Path) -> None:
    web_dir = tmp_path / "apps" / "dsa-web"
    (web_dir / "node_modules" / ".bin").mkdir(parents=True)
    (web_dir / "node_modules" / ".bin" / "vite").write_text("#!/bin/sh\n", encoding="utf-8")
    (web_dir / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    monkeypatch.setattr(harness.shutil, "which", lambda name: "/usr/local/bin/npm" if name == "npm" else None)

    def _run(command, cwd, check):
        commands.append(tuple(command))
        assert cwd == tmp_path
        assert check is False
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(harness.subprocess, "run", _run)

    result = harness.ensure_frontend_dependencies(tmp_path)

    assert result["action"] == "installed"
    assert result["required"] is True
    assert result["installCommand"] == ["npm", "--prefix", "apps/dsa-web", "ci"]
    assert result["exitStatus"] == 0
    assert result["lockfile"]["path"] == "apps/dsa-web/package-lock.json"
    assert result["lockfile"]["sha256"]
    assert commands == [("/usr/local/bin/npm", "--prefix", "apps/dsa-web", "ci")]


def test_frontend_dependency_bootstrap_skips_when_toolchain_usable(monkeypatch, tmp_path: Path) -> None:
    web_dir = tmp_path / "apps" / "dsa-web"
    (web_dir / "node_modules" / ".bin").mkdir(parents=True)
    (web_dir / "node_modules" / ".bin" / "tsc").write_text("#!/bin/sh\n", encoding="utf-8")
    (web_dir / "node_modules" / ".bin" / "vite").write_text("#!/bin/sh\n", encoding="utf-8")
    (web_dir / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
    monkeypatch.setattr(harness.shutil, "which", lambda name: "/usr/local/bin/npm" if name == "npm" else None)
    monkeypatch.setattr(harness.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("npm ci must be skipped"))

    result = harness.ensure_frontend_dependencies(tmp_path)

    assert result["action"] == "skipped"
    assert result["required"] is False
    assert result["skipReason"] == "frontend_toolchain_available"
    assert result["installCommand"] == ["npm", "--prefix", "apps/dsa-web", "ci"]
    assert result["exitStatus"] is None


def test_frontend_dependency_bootstrap_records_install_failure(monkeypatch, tmp_path: Path) -> None:
    web_dir = tmp_path / "apps" / "dsa-web"
    web_dir.mkdir(parents=True)
    (web_dir / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
    monkeypatch.setattr(harness.shutil, "which", lambda name: "/usr/local/bin/npm" if name == "npm" else None)
    monkeypatch.setattr(
        harness.subprocess,
        "run",
        lambda command, cwd, check: subprocess.CompletedProcess(command, 19),
    )

    result = harness.ensure_frontend_dependencies(tmp_path)

    assert result["action"] == "failed"
    assert result["required"] is True
    assert result["exitStatus"] == 19
    assert result["reasonCodes"] == ["frontend_dependency_install_failed"]


def test_run_harness_rejects_existing_port_owner_without_starting_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        harness,
        "validate_source",
        lambda _repo_root, _expected_sha: {
            "ok": True,
            "gitSha": "45b6965d",
            "branch": "test",
            "commitTimestamp": "2026-07-05T00:00:00+00:00",
            "expectedGitSha": "45b6965d",
            "errorCodes": [],
        },
    )
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=1234, cwd="/tmp/other", command="python other.py"),
    )
    monkeypatch.setattr(
        harness,
        "start_runtime",
        lambda *_args, **_kwargs: pytest.fail("runtime must not start when port is already owned"),
    )

    exit_code, evidence = harness.run_harness(
        repo_root=tmp_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8000,
        evidence_dir=tmp_path / "output" / "runtime-verification",
        skip_build=True,
    )

    assert exit_code == 1
    assert evidence["status"] == "FAIL"
    assert evidence["failure"] == "port_occupied_by_unrelated_process"
    assert evidence["portOwner"]["pid"] == 1234
    assert Path(evidence["evidencePath"]).is_file()


def test_run_harness_writes_machine_readable_evidence_and_stops_owned_runtime(monkeypatch, tmp_path: Path) -> None:
    _write_static(tmp_path)
    fake_process = _FakeProcess()
    monkeypatch.setattr(harness, "validate_source", lambda _repo_root, _expected_sha: _valid_source())
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
    monkeypatch.setattr(
        harness,
        "ensure_frontend_dependencies",
        lambda _repo_root: {
            "action": "skipped",
            "required": False,
            "skipReason": "frontend_toolchain_available",
            "installCommand": ["npm", "--prefix", "apps/dsa-web", "ci"],
            "exitStatus": None,
            "lockfile": {"path": "apps/dsa-web/package-lock.json", "sha256": "lockhash"},
            "reasonCodes": [],
        },
    )
    monkeypatch.setattr(harness, "run_frontend_build", lambda _repo_root: 0)
    monkeypatch.setattr(harness, "verify_frontend_static_build", lambda **_kwargs: _local_build())
    monkeypatch.setattr(harness, "read_backend_info", lambda _repo_root: object())
    monkeypatch.setattr(harness, "start_runtime", lambda *_args, **_kwargs: fake_process)
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "process_command", lambda _pid: "python main.py --serve-only --host 127.0.0.1 --port 8000")
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "Sun Jul  5 00:00:00 2026")
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())
    monkeypatch.setattr(
        harness,
        "run_runtime_smoke",
        lambda **_kwargs: {"checks": {"runtimeBundle": {"status": "PASS"}}, "summaryStatus": "PARTIAL"},
    )

    exit_code, evidence = harness.run_harness(
        repo_root=tmp_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8000,
        evidence_dir=tmp_path / "output" / "runtime-verification",
        skip_build=True,
        stop_runtime_after=True,
    )

    assert exit_code == 0
    assert fake_process.terminated is True
    assert evidence["run"]["runId"]
    assert evidence["run"]["pid"] == 43210
    assert evidence["run"]["cwd"] == str(tmp_path.resolve())
    assert evidence["run"]["port"] == 8000
    assert evidence["run"]["evidencePath"] == evidence["evidencePath"]
    assert evidence["run"]["runLogPath"] == evidence["runtimeLog"]["path"]
    assert Path(evidence["runtimeLog"]["path"]).name.startswith(evidence["run"]["runId"])
    assert evidence["frontendDependencyBootstrap"]["action"] == "skipped"
    assert evidence["status"] == "PASS"
    assert evidence["runtime"]["pid"] == 43210
    assert evidence["runtime"]["cwd"] == str(tmp_path.resolve())
    assert evidence["frontend"]["mainJsAssetFilename"] == "index-CKPdXr8Q.js"
    assert evidence["frontend"]["mainCssAssetFilenames"] == ["index-CSS123.css"]
    assert evidence["directHttpHtml"]["ok"] is True
    assert evidence["providerIsolation"]["productionBehaviorUnchanged"] is True
    assert evidence["cryptoRealtimeIsolation"]["productionDefaultChanged"] is False
    assert evidence["contaminationAwareness"]["browserAttribution"] == "correlation_only"
    assert evidence["contaminationAwareness"]["unrelatedActivityMayContaminateCausalAttribution"] is False
    assert evidence["workbuddyHandoff"]["runId"] == evidence["run"]["runId"]
    assert evidence["workbuddyHandoff"]["runtimeLogWindow"]["path"] == evidence["runtimeLog"]["path"]
    assert evidence["workbuddyHandoff"]["runtimeLogWindow"]["activityScope"] == "run_scoped_child_stdout_stderr"
    assert evidence["workbuddyHandoff"]["runtimeLogWindow"]["causalAttribution"]["automatic"] is False
    assert evidence["workbuddyHandoff"]["browserRequirements"]["freshContextSession"] is True
    written = json.loads(Path(evidence["evidencePath"]).read_text(encoding="utf-8"))
    assert written["contract"] == "wolfystock_uat_runtime_harness_v1"
    assert written["workbuddyHandoff"]["expectedGitSha"] == "45b6965d"
    assert written["run"]["evidencePath"] == evidence["evidencePath"]


def test_run_harness_fails_when_dependency_bootstrap_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness, "validate_source", lambda _repo_root, _expected_sha: _valid_source())
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
    monkeypatch.setattr(
        harness,
        "ensure_frontend_dependencies",
        lambda _repo_root: {
            "action": "failed",
            "required": True,
            "skipReason": None,
            "installCommand": ["npm", "--prefix", "apps/dsa-web", "ci"],
            "exitStatus": 19,
            "lockfile": {"path": "apps/dsa-web/package-lock.json", "sha256": "lockhash"},
            "reasonCodes": ["frontend_dependency_install_failed"],
        },
    )
    monkeypatch.setattr(harness, "run_frontend_build", lambda _repo_root: pytest.fail("build must not run after install failure"))

    exit_code, evidence = harness.run_harness(
        repo_root=tmp_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8101,
        evidence_dir=tmp_path / "output" / "runtime-verification",
    )

    assert exit_code == 1
    assert evidence["status"] == "FAIL"
    assert evidence["failure"] == "frontend_dependency_bootstrap_failed"
    assert evidence["frontendDependencyBootstrap"]["exitStatus"] == 19


def test_preflight_pass_reports_machine_readable_current_run_identity(monkeypatch, tmp_path: Path) -> None:
    evidence = {
        "contract": "wolfystock_uat_runtime_harness_v1",
        "status": "PASS",
        "source": {"gitSha": "45b6965d"},
        "run": {
            "runId": "uat-20260705T000000Z-abc12345",
            "pid": 43210,
            "cwd": str(tmp_path.resolve()),
            "startTime": "2026-07-05T00:00:00+00:00",
            "port": 8102,
            "assetIdentity": {"indexHtmlHash": "indexhash", "mainJsAssetFilename": "index-CKPdXr8Q.js"},
            "evidencePath": str(tmp_path / "evidence.json"),
            "runLogPath": str(tmp_path / "run.log"),
        },
        "runtime": {"pid": 43210, "cwd": str(tmp_path.resolve()), "listener": {"port": 8102}},
        "frontend": {"indexHtmlHash": "indexhash", "mainJsAssetFilename": "index-CKPdXr8Q.js"},
        "directHttpHtml": {"ok": True},
        "runtimeLog": {"path": str(tmp_path / "run.log"), "startTime": "2026-07-05T00:00:00+00:00"},
    }
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=43210, cwd=str(tmp_path.resolve()), command="python main.py --serve-only"),
    )
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())

    result = harness.run_preflight(
        evidence_path=evidence_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8102,
    )

    assert result["status"] == "PASS"
    assert result["checks"]["pidAlive"]["status"] == "PASS"
    assert result["checks"]["pidOwnsPort"]["status"] == "PASS"
    assert result["checks"]["cwd"]["status"] == "PASS"
    assert result["checks"]["directNoProxyHttp"]["status"] == "PASS"
    assert result["run"]["runId"] == "uat-20260705T000000Z-abc12345"
    assert result["run"]["runLogPath"] == str(tmp_path / "run.log")


def test_preflight_fails_for_wrong_port_owner(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "status": "PASS",
                "source": {"gitSha": "45b6965d"},
                "run": {
                    "runId": "uat-run",
                    "pid": 43210,
                    "cwd": str(tmp_path.resolve()),
                    "startTime": "2026-07-05T00:00:00+00:00",
                    "port": 8103,
                    "assetIdentity": {"mainJsAssetFilename": "index-CKPdXr8Q.js"},
                    "evidencePath": str(evidence_path),
                    "runLogPath": str(tmp_path / "run.log"),
                },
                "frontend": {"mainJsAssetFilename": "index-CKPdXr8Q.js"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=99999, cwd="/tmp/other", command="python other.py"),
    )
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())

    result = harness.run_preflight(
        evidence_path=evidence_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8103,
    )

    assert result["status"] == "FAIL"
    assert result["checks"]["pidOwnsPort"]["status"] == "FAIL"
    assert result["checks"]["pidOwnsPort"]["observed"]["pid"] == 99999


def test_preflight_cli_returns_machine_readable_failure_for_missing_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    missing = tmp_path / "missing-evidence.json"

    result = harness.main(["--preflight", "--evidence-path", str(missing), "--json"])

    assert result == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["contract"] == "wolfystock_uat_runtime_preflight_v1"
    assert payload["status"] == "FAIL"
    assert payload["checks"]["evidenceReadable"]["status"] == "FAIL"
    assert payload["checks"]["evidenceReadable"]["observed"]["reasonCode"] == "evidence_unreadable"


def test_safe_stop_rejects_wrong_pid_cwd_identity(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {"ownedByHarness": True, "processStartTime": "Sun Jul  5 00:00:00 2026"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "Sun Jul  5 00:00:00 2026")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: "/tmp/other")
    monkeypatch.setattr(harness.os, "kill", lambda *_args, **_kwargs: pytest.fail("wrong cwd process must not be killed"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "pid_cwd_mismatch"
    assert result["pid"] == 43210


def test_safe_stop_records_already_absent_without_killing(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {"ownedByHarness": True, "processStartTime": "Sun Jul  5 00:00:00 2026"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "pid_is_alive", lambda _pid: False)
    monkeypatch.setattr(harness.os, "kill", lambda *_args, **_kwargs: pytest.fail("absent process must not be killed"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "absent"
    assert result["reasonCode"] == "runtime_already_absent"


def test_safe_stop_rejects_not_harness_owned_without_killing(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {"ownedByHarness": False},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness.os, "kill", lambda *_args, **_kwargs: pytest.fail("unowned process must not be killed"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "not_harness_owned"


def test_safe_stop_rejects_reused_pid_without_killing(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "Sun Jul  5 00:00:00 2026",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "Sun Jul  5 00:01:00 2026")
    monkeypatch.setattr(harness.os, "kill", lambda *_args, **_kwargs: pytest.fail("reused pid must not be killed"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "pid_reused"


def test_safe_stop_rejects_wrong_port_owner_without_killing(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run", "port": 8123},
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "Sun Jul  5 00:00:00 2026",
                    "listener": {"host": "127.0.0.1", "port": 8123},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "Sun Jul  5 00:00:00 2026")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=99999, cwd="/tmp/other", command="python other.py"),
    )
    monkeypatch.setattr(harness.os, "kill", lambda *_args, **_kwargs: pytest.fail("wrong port owner must not be killed"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "pid_port_owner_mismatch"
    assert result["observedPortOwner"]["pid"] == 99999


def test_safe_stop_rejects_missing_port_owner_without_killing(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run", "port": 8124},
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "Sun Jul  5 00:00:00 2026",
                    "listener": {"host": "127.0.0.1", "port": 8124},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "Sun Jul  5 00:00:00 2026")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
    monkeypatch.setattr(harness.os, "kill", lambda *_args, **_kwargs: pytest.fail("missing port owner must not be killed"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "pid_not_port_owner"


def test_stop_owned_runtime_reports_already_absent() -> None:
    process = _AlreadyAbsentProcess()

    result = harness.stop_owned_runtime(process)

    assert result["status"] == "absent"
    assert process.terminated is False
    assert process.killed is False


def test_start_runtime_captures_child_stdout_and_stderr_in_run_scoped_log(tmp_path: Path) -> None:
    main_py = tmp_path / "main.py"
    main_py.write_text(
        "import sys\n"
        "print('child stdout current run')\n"
        "print('child stderr current run', file=sys.stderr)\n",
        encoding="utf-8",
    )
    context = harness.create_run_context(tmp_path / "evidence")
    harness.build_runtime_log(context)

    process = harness.start_runtime(
        tmp_path,
        host="127.0.0.1",
        port=8125,
        python_bin=sys.executable,
        run_log_path=context.run_log_path,
    )
    process.wait(timeout=10)
    harness.stop_owned_runtime(process)
    runtime_log = harness.build_runtime_log(context, process)

    text = context.run_log_path.read_text(encoding="utf-8")
    assert f"runId={context.run_id}" in text
    assert f"pid={process.pid}" in text
    assert "child stdout current run" in text
    assert "child stderr current run" in text
    assert runtime_log["activityScope"] == "child_stdout_stderr_for_run"


def test_run_log_file_is_current_child_stream_only(tmp_path: Path) -> None:
    first_repo = tmp_path / "first"
    second_repo = tmp_path / "second"
    first_repo.mkdir()
    second_repo.mkdir()
    (first_repo / "main.py").write_text("print('first child stream')\n", encoding="utf-8")
    (second_repo / "main.py").write_text("print('second child stream')\n", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    first_context = harness.create_run_context(evidence_dir)
    second_context = harness.create_run_context(evidence_dir)

    first_process = harness.start_runtime(
        first_repo,
        host="127.0.0.1",
        port=8126,
        python_bin=sys.executable,
        run_log_path=first_context.run_log_path,
    )
    second_process = harness.start_runtime(
        second_repo,
        host="127.0.0.1",
        port=8127,
        python_bin=sys.executable,
        run_log_path=second_context.run_log_path,
    )
    first_process.wait(timeout=10)
    second_process.wait(timeout=10)
    harness.stop_owned_runtime(first_process)
    harness.stop_owned_runtime(second_process)

    first_text = first_context.run_log_path.read_text(encoding="utf-8")
    second_text = second_context.run_log_path.read_text(encoding="utf-8")
    assert "first child stream" in first_text
    assert "second child stream" not in first_text
    assert "second child stream" in second_text
    assert "first child stream" not in second_text


def test_preflight_cli_missing_evidence_does_not_import_heavy_runtime_modules(tmp_path: Path) -> None:
    missing = tmp_path / "missing-evidence.json"
    code = _import_guard_script(
        ["scripts/uat_runtime_harness.py", "--preflight", "--evidence-path", str(missing), "--json"]
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert "blocked import" not in result.stderr
    assert "evidence_unreadable" in result.stdout


def test_stop_from_evidence_cli_missing_evidence_does_not_import_heavy_runtime_modules(tmp_path: Path) -> None:
    missing = tmp_path / "missing-evidence.json"
    code = _import_guard_script(
        ["scripts/uat_runtime_harness.py", "--stop-from-evidence", "--evidence-path", str(missing), "--json"]
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert "blocked import" not in result.stderr
    assert "evidence_unreadable" in result.stdout


def test_direct_script_help_entrypoint_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/uat_runtime_harness.py", "--help"],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "deterministic local UAT runtime" in result.stdout


def _import_guard_script(argv: list[str]) -> str:
    return (
        "import builtins, json, runpy, sys\n"
        f"sys.argv = {argv!r}\n"
        "blocked = (\n"
        "    'pandas',\n"
        "    'src.storage',\n"
        "    'src.repositories.auth_repo',\n"
        "    'scripts.seed_uat_consumer_test_accounts',\n"
        "    'scripts.uat_fresh_build_verifier',\n"
        "    'scripts.uat_runtime_smoke_pack',\n"
        ")\n"
        "orig_import = builtins.__import__\n"
        "def guarded_import(name, *args, **kwargs):\n"
        "    if any(name == item or name.startswith(item + '.') for item in blocked):\n"
        "        raise AssertionError('blocked import: ' + name)\n"
        "    return orig_import(name, *args, **kwargs)\n"
        "builtins.__import__ = guarded_import\n"
        "try:\n"
        "    runpy.run_path(sys.argv[0], run_name='__main__')\n"
        "except SystemExit as exc:\n"
        "    raise SystemExit(exc.code)\n"
    )
