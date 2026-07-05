from __future__ import annotations

import json
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
    monkeypatch.setattr(
        harness,
        "validate_source",
        lambda _repo_root, _expected_sha: {
            "ok": True,
            "gitSha": "45b6965d",
            "branch": "codex/t157-deterministic-uat-runtime-harness",
            "commitTimestamp": "2026-07-05T00:00:00+00:00",
            "expectedGitSha": "45b6965d",
            "errorCodes": [],
        },
    )
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
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
    assert evidence["status"] == "PASS"
    assert evidence["runtime"]["pid"] == 43210
    assert evidence["runtime"]["cwd"] == str(tmp_path.resolve())
    assert evidence["frontend"]["mainJsAssetFilename"] == "index-CKPdXr8Q.js"
    assert evidence["frontend"]["mainCssAssetFilenames"] == ["index-CSS123.css"]
    assert evidence["directHttpHtml"]["ok"] is True
    assert evidence["providerIsolation"]["productionBehaviorUnchanged"] is True
    assert evidence["cryptoRealtimeIsolation"]["productionDefaultChanged"] is False
    assert evidence["workbuddyHandoff"]["browserRequirements"]["freshContextSession"] is True
    written = json.loads(Path(evidence["evidencePath"]).read_text(encoding="utf-8"))
    assert written["contract"] == "wolfystock_uat_runtime_harness_v1"
    assert written["workbuddyHandoff"]["expectedGitSha"] == "45b6965d"


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
