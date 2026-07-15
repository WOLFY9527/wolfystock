from __future__ import annotations

import hashlib
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
        self.content = text.encode("utf-8")

    def json(self) -> dict[str, object]:
        return json.loads(self.text or "{}")


class _FakeClient:
    def __init__(
        self,
        *,
        asset_name: str = "index-CKPdXr8Q.js",
        main_asset_body: str = "console.log('ok');\n",
    ) -> None:
        self.asset_name = asset_name
        self.main_asset_body = main_asset_body
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
            return _FakeResponse(200, self.main_asset_body)
        if url.endswith("/assets/index-CSS123.css"):
            return _FakeResponse(200, "body{color:#111}\n")
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
        newline="\n",
    )
    (assets / asset_name).write_text("console.log('ok');\n", encoding="utf-8", newline="\n")
    (assets / "index-CSS123.css").write_text("body{color:#111}\n", encoding="utf-8", newline="\n")


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


def _evidence_asset_identity(repo_root: Path, *, git_sha: str = "45b6965d") -> dict[str, object]:
    asset_name = "index-CKPdXr8Q.js"
    index_body = (
        f'<html><title>WolfyStock</title><script type="module" src="/assets/{asset_name}"></script></html>'
    )
    main_body = "console.log('ok');\n"
    css_body = "body{color:#111}\n"
    index_hash = hashlib.sha256(index_body.encode("utf-8")).hexdigest()
    main_hash = hashlib.sha256(main_body.encode("utf-8")).hexdigest()
    css_hash = hashlib.sha256(css_body.encode("utf-8")).hexdigest()
    return {
        "indexHtmlHash": index_hash,
        "mainJsAssetFilename": asset_name,
        "mainCssAssetFilenames": ["index-CSS123.css"],
        "assetHashes": {
            asset_name: main_hash,
            "index-CSS123.css": css_hash,
        },
        "buildIdentity": {
            "contract": "wolfystock_frontend_build_identity_v1",
            "gitSha": git_sha,
            "repositoryRoot": str(repo_root.resolve()),
            "indexHtmlSha256": index_hash,
            "mainJsAssetFilename": asset_name,
            "mainJsAssetSha256": main_hash,
        },
    }


def _evidence_interpreter() -> dict[str, object]:
    executable = str(Path(sys.executable).resolve())
    return {
        "status": "verified",
        "expectedRequestedPath": sys.executable,
        "expectedResolvedPath": executable,
        "observedPath": executable,
        "observedResolvedPath": executable,
    }


def _valid_source(expected_sha: str = "45b6965d") -> dict[str, object]:
    return {
        "ok": True,
        "gitSha": expected_sha,
        "branch": "codex/t164-uat-harness-hardening",
        "commitTimestamp": "2026-07-05T00:00:00+00:00",
        "expectedGitSha": expected_sha,
        "errorCodes": [],
    }


def _write_uat_evidence(
    evidence_dir: Path,
    *,
    run_id: str,
    source_sha: str | None = "45b6965d",
    run_sha: str | None = "45b6965d",
    expected_sha: str | None = None,
    runtime_sha: str | None = None,
    generated_at: str | None = "2026-07-05T00:00:00+00:00",
    start_time: str | None = "2026-07-05T00:00:00+00:00",
    pid: int = 43210,
    port: int = 8102,
    status: str = "PASS",
) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    source: dict[str, object] = {}
    if source_sha is not None:
        source["gitSha"] = source_sha
    if expected_sha is not None:
        source["expectedGitSha"] = expected_sha
    run: dict[str, object] = {
        "runId": run_id,
        "pid": pid,
        "cwd": str(evidence_dir.resolve()),
        "port": port,
        "assetIdentity": _evidence_asset_identity(evidence_dir, git_sha=source_sha or run_sha or "45b6965d"),
        "runLogPath": str(evidence_dir / f"{run_id}-runtime.log"),
    }
    if run_sha is not None:
        run["sha"] = run_sha
    if start_time is not None:
        run["startTime"] = start_time
    runtime: dict[str, object] = {
        "ownedByHarness": True,
        "processStartTime": "2026-07-05T00:00:00+00:00",
        "command": f"{sys.executable} main.py --serve-only --port {port}",
        "interpreter": _evidence_interpreter(),
        "listener": {"host": "127.0.0.1", "port": port},
    }
    if runtime_sha is not None:
        runtime["sha"] = runtime_sha
    payload: dict[str, object] = {
        "contract": "wolfystock_uat_runtime_harness_v1",
        "status": status,
        "source": source,
        "run": run,
        "runtime": runtime,
        "frontend": dict(run["assetIdentity"]),
    }
    if generated_at is not None:
        payload["generatedAt"] = generated_at
    filename = "uat-runtime-harness-evidence.json" if run_id == "legacy" else f"{run_id}-evidence.json"
    path = evidence_dir / filename
    run["evidencePath"] = str(path)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _patch_preflight_identity_ok(monkeypatch, tmp_path: Path, *, port: int = 8102) -> None:
    command = f"{sys.executable} main.py --serve-only --port {port}"
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "process_executable", lambda _pid: str(Path(sys.executable).resolve()))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(harness, "process_command", lambda _pid: command)
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=43210, cwd=str(tmp_path.resolve()), command=command),
    )
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())


def test_latest_evidence_prefers_current_provenance_over_newer_stale_mtime(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    stale = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-stale",
        source_sha="1111111",
        run_sha="1111111",
        generated_at="2026-07-05T00:00:00+00:00",
        start_time="2026-07-05T00:00:00+00:00",
    )
    current = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000001-current",
        source_sha="45b6965d",
        run_sha="45b6965d",
        generated_at="2026-07-05T00:00:01+00:00",
        start_time="2026-07-05T00:00:01+00:00",
    )
    os.utime(current, (100, 100))
    os.utime(stale, (200, 200))

    selected = harness._latest_evidence_path(evidence_dir, required_sha="45b6965d")

    assert selected == current


def test_explicit_preflight_path_wins_over_implicit_current_candidate(monkeypatch, tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    explicit = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-explicit",
        source_sha="1111111",
        run_sha="1111111",
        generated_at="2026-07-05T00:00:00+00:00",
        start_time="2026-07-05T00:00:00+00:00",
    )
    _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000100-current",
        source_sha="45b6965d",
        run_sha="45b6965d",
        generated_at="2026-07-05T00:01:00+00:00",
        start_time="2026-07-05T00:01:00+00:00",
    )
    _patch_preflight_identity_ok(monkeypatch, evidence_dir)

    result = harness.run_preflight(
        evidence_path=explicit,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8102,
        selection={"mode": "explicit", "selectionReason": "explicit_evidence_path"},
    )

    assert result["evidencePath"] == str(explicit)
    assert result["selection"]["mode"] == "explicit"
    assert result["selection"]["freshnessClassification"] == "STALE"
    assert result["evidenceFreshness"]["classification"] == "STALE"


def test_latest_evidence_uses_embedded_timestamp_before_mtime(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    older = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-older",
        generated_at="2026-07-05T00:00:00+00:00",
        start_time="2026-07-05T00:00:00+00:00",
    )
    newer = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000100-newer",
        generated_at="2026-07-05T00:01:00+00:00",
        start_time="2026-07-05T00:01:00+00:00",
    )
    os.utime(newer, (100, 100))
    os.utime(older, (200, 200))

    selected = harness._latest_evidence_path(evidence_dir, required_sha="45b6965d")

    assert selected == newer


def test_latest_evidence_tie_breaks_deterministically_by_path(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    first = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-aaaa",
        generated_at="2026-07-05T00:00:00+00:00",
        start_time="2026-07-05T00:00:00+00:00",
    )
    second = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-bbbb",
        generated_at="2026-07-05T00:00:00+00:00",
        start_time="2026-07-05T00:00:00+00:00",
    )
    os.utime(first, (100, 100))
    os.utime(second, (100, 100))

    selected = harness._latest_evidence_path(evidence_dir, required_sha="45b6965d")

    assert selected == first


def test_latest_evidence_rejects_invalid_json_candidate(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    valid = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-valid",
        generated_at="2026-07-05T00:00:00+00:00",
        start_time="2026-07-05T00:00:00+00:00",
    )
    invalid = evidence_dir / "uat-20260705T000001-invalid-evidence.json"
    invalid.write_text("{", encoding="utf-8")
    os.utime(valid, (100, 100))
    os.utime(invalid, (200, 200))

    selected = harness._latest_evidence_path(evidence_dir, required_sha="45b6965d")

    assert selected == valid


def test_latest_evidence_handles_malformed_timestamp_as_legacy_compatibility(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    malformed_timestamp = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-malformed",
        generated_at="not-a-timestamp",
        start_time="also-not-a-timestamp",
    )
    valid_timestamp = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000001-valid",
        generated_at="2026-07-05T00:00:01+00:00",
        start_time="2026-07-05T00:00:01+00:00",
    )
    os.utime(valid_timestamp, (100, 100))
    os.utime(malformed_timestamp, (200, 200))

    selected, selection = harness._latest_evidence_path(
        evidence_dir,
        required_sha="45b6965d",
        return_selection=True,
    )

    assert selected == valid_timestamp
    assert selection["selectionReason"] == "provenance_current_embedded_timestamp"


def test_evidence_freshness_classification_states(tmp_path: Path) -> None:
    current = harness.load_evidence(
        _write_uat_evidence(tmp_path / "current", run_id="uat-current", source_sha="45b6965d", run_sha="45b6965d")
    )
    stale = harness.load_evidence(
        _write_uat_evidence(tmp_path / "stale", run_id="uat-stale", source_sha="1111111", run_sha="1111111")
    )
    unknown = harness.load_evidence(
        _write_uat_evidence(tmp_path / "unknown", run_id="uat-unknown", source_sha=None, run_sha=None)
    )
    mismatch = harness.load_evidence(
        _write_uat_evidence(tmp_path / "mismatch", run_id="uat-mismatch", source_sha="45b6965d", run_sha="1111111")
    )
    invalid = harness.load_evidence(
        _write_uat_evidence(tmp_path / "invalid", run_id="uat-invalid", source_sha="not-a-sha", run_sha="not-a-sha")
    )

    assert harness._classify_evidence_freshness(current, required_sha="45b6965d")["classification"] == "CURRENT"
    assert harness._classify_evidence_freshness(stale, required_sha="45b6965d")["classification"] == "STALE"
    assert harness._classify_evidence_freshness(unknown, required_sha="45b6965d")["classification"] == "UNKNOWN"
    assert harness._classify_evidence_freshness(mismatch, required_sha="45b6965d")["classification"] == "MISMATCH"
    assert harness._classify_evidence_freshness(invalid, required_sha="45b6965d")["classification"] == "INVALID"


def test_preflight_exposes_selection_reason_and_stale_explicit_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    evidence_path = _write_uat_evidence(
        tmp_path,
        run_id="uat-20260705T000000-stale",
        source_sha="1111111",
        run_sha="1111111",
    )
    _patch_preflight_identity_ok(monkeypatch, tmp_path)

    result = harness.run_preflight(
        evidence_path=evidence_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8102,
        selection={"mode": "explicit", "selectionReason": "explicit_evidence_path"},
    )

    assert result["status"] == "FAIL"
    assert result["evidenceFreshness"]["classification"] == "STALE"
    assert result["evidenceFreshness"]["historicalOnly"] is True
    assert result["selection"]["mode"] == "explicit"
    assert result["selection"]["selectionReason"] == "explicit_evidence_path"


def test_preflight_cli_implicit_latest_exposes_selection_reason(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    evidence_dir = tmp_path / "evidence"
    selected = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000001-current",
        source_sha="45b6965d",
        run_sha="45b6965d",
        generated_at="2026-07-05T00:00:01+00:00",
        start_time="2026-07-05T00:00:01+00:00",
    )
    _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-stale",
        source_sha="1111111",
        run_sha="1111111",
        generated_at="2026-07-05T00:00:00+00:00",
        start_time="2026-07-05T00:00:00+00:00",
    )
    _patch_preflight_identity_ok(monkeypatch, evidence_dir)

    exit_code = harness.main(
        [
            "--preflight",
            "--expected-sha",
            "45b6965d",
            "--evidence-dir",
            str(evidence_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["evidencePath"] == str(selected)
    assert payload["selection"]["mode"] == "implicit"
    assert payload["selection"]["selectionReason"] == "provenance_current_embedded_timestamp"
    assert payload["selection"]["freshnessClassification"] == "CURRENT"


def test_stop_rejects_stale_evidence_before_termination_when_current_authority_required(
    monkeypatch,
    tmp_path: Path,
) -> None:
    evidence_path = _write_uat_evidence(
        tmp_path,
        run_id="uat-20260705T000000-stale",
        source_sha="1111111",
        run_sha="1111111",
    )
    monkeypatch.setattr(harness, "_terminate_pid", lambda _pid: pytest.fail("stale evidence must not terminate"))

    result = harness.stop_runtime_from_evidence(
        evidence_path,
        required_sha="45b6965d",
        enforce_current=True,
    )

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "evidence_not_current"
    assert result["evidenceFreshness"]["classification"] == "STALE"


def test_stop_from_evidence_cli_implicit_stale_rejects_before_identity_checks(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    evidence_dir = tmp_path / "evidence"
    stale = _write_uat_evidence(
        evidence_dir,
        run_id="uat-20260705T000000-stale",
        source_sha="1111111",
        run_sha="1111111",
    )
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: pytest.fail("stale evidence must not probe process"))
    monkeypatch.setattr(harness, "_terminate_pid", lambda _pid: pytest.fail("stale evidence must not terminate"))

    exit_code = harness.main(
        [
            "--stop-from-evidence",
            "--expected-sha",
            "45b6965d",
            "--evidence-dir",
            str(evidence_dir),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "rejected"
    assert payload["reasonCode"] == "evidence_not_current"
    assert payload["evidencePath"] == str(stale)
    assert payload["selection"]["mode"] == "implicit"
    assert payload["evidenceFreshness"]["classification"] == "STALE"


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


def test_direct_http_client_reads_full_raw_response_bytes() -> None:
    body = b"x" * (1024 * 1024 + 37)
    read_args: list[tuple[object, ...]] = []

    class _RawResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *args):
            read_args.append(args)
            return body

    class _RawOpener:
        def open(self, *_args, **_kwargs):
            return _RawResponse()

    client = harness.DirectNoProxyHttpClient()
    client._opener = _RawOpener()

    response = client.request("GET", "http://127.0.0.1:8000/assets/index-large.js")

    assert response.content == body
    assert len(response.text) == len(body)
    assert read_args == [()]


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


def test_run_harness_fails_closed_for_invalid_prebuilt_web_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness, "validate_source", lambda _repo_root, _expected_sha: _valid_source())
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
    monkeypatch.setattr(
        harness,
        "verify_web_build_artifact",
        lambda *_args: type("Result", (), {"ok": False, "payload": {}, "error_codes": ["artifact_asset_mismatch"], "warning_codes": []})(),
    )
    monkeypatch.setattr(harness, "ensure_frontend_dependencies", lambda *_args: pytest.fail("artifact mode must not bootstrap dependencies"))
    monkeypatch.setattr(harness, "run_frontend_build", lambda *_args: pytest.fail("artifact mode must not rebuild"))

    exit_code, evidence = harness.run_harness(
        repo_root=tmp_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8000,
        evidence_dir=tmp_path / "output" / "runtime-verification",
        web_artifact=tmp_path / "static" / ".wolfystock-web-build-artifact.json",
    )

    assert exit_code == 1
    assert evidence["failure"] == "prebuilt_web_artifact_failed"
    assert evidence["frontendDependencyBootstrap"]["action"] == "verified_prebuilt_artifact"


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
    monkeypatch.setattr(harness, "process_executable", lambda _pid: str(Path(sys.executable).resolve()))
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
    assert evidence["runtime"]["interpreter"]["status"] == "verified"
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


def test_run_harness_fails_closed_for_wrong_process_cwd(monkeypatch, tmp_path: Path) -> None:
    _write_static(tmp_path)
    fake_process = _FakeProcess()
    monkeypatch.setattr(harness, "validate_source", lambda _repo_root, _expected_sha: _valid_source())
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
    monkeypatch.setattr(
        harness,
        "ensure_frontend_dependencies",
        lambda _repo_root: {"action": "skipped", "required": False, "reasonCodes": []},
    )
    monkeypatch.setattr(harness, "verify_frontend_static_build", lambda **_kwargs: _local_build())
    monkeypatch.setattr(harness, "read_backend_info", lambda _repo_root: object())
    monkeypatch.setattr(harness, "start_runtime", lambda *_args, **_kwargs: fake_process)
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str((tmp_path / "other").resolve()))
    monkeypatch.setattr(harness, "process_executable", lambda _pid: str(Path(sys.executable).resolve()))
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

    assert exit_code == 1
    assert evidence["status"] == "FAIL"
    assert "runtime_cwd_mismatch" in evidence["identityErrors"]


def test_run_harness_fails_closed_for_mismatched_interpreter(monkeypatch, tmp_path: Path) -> None:
    _write_static(tmp_path)
    fake_process = _FakeProcess()
    monkeypatch.setattr(harness, "validate_source", lambda _repo_root, _expected_sha: _valid_source())
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
    monkeypatch.setattr(
        harness,
        "ensure_frontend_dependencies",
        lambda _repo_root: {"action": "skipped", "required": False, "reasonCodes": []},
    )
    monkeypatch.setattr(harness, "verify_frontend_static_build", lambda **_kwargs: _local_build())
    monkeypatch.setattr(harness, "read_backend_info", lambda _repo_root: object())
    monkeypatch.setattr(harness, "start_runtime", lambda *_args, **_kwargs: fake_process)
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "process_executable", lambda _pid: "/usr/bin/false")
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

    assert exit_code == 1
    assert evidence["runtime"]["interpreter"]["status"] == "mismatch"
    assert "runtime_interpreter_mismatch" in evidence["identityErrors"]


def test_interpreter_identity_accepts_same_macos_framework_version() -> None:
    expected = Path("/opt/python/Python.framework/Versions/3.11/bin/python3.11")
    observed = "/opt/python/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python"

    identity = harness.build_interpreter_identity(expected, observed)

    assert identity["status"] == "verified"
    assert identity["equivalenceBasis"] == "python_framework_version"


def test_direct_http_asset_identity_rejects_same_filename_with_different_bytes(tmp_path: Path) -> None:
    _write_static(tmp_path)
    identity = harness.build_asset_identity(tmp_path / "static", _local_build().payload)

    result = harness.verify_direct_asset_identity(
        _FakeClient(main_asset_body="console.log('stale bundle');\n"),
        "http://127.0.0.1:8000",
        identity,
    )

    assert result["ok"] is False
    assert "served_asset_hash_mismatch" in result["reasonCodes"]


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
    expected_command = "python main.py --serve-only --host 127.0.0.1 --port 8102"
    asset_identity = _evidence_asset_identity(tmp_path)
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
            "assetIdentity": asset_identity,
            "evidencePath": str(tmp_path / "evidence.json"),
            "runLogPath": str(tmp_path / "run.log"),
        },
        "runtime": {
            "pid": 43210,
            "cwd": str(tmp_path.resolve()),
            "ownedByHarness": True,
            "processStartTime": "2026-07-05T00:00:00+00:00",
            "command": expected_command,
            "interpreter": _evidence_interpreter(),
            "listener": {"port": 8102},
        },
        "frontend": asset_identity,
        "directHttpHtml": {"ok": True},
        "runtimeLog": {"path": str(tmp_path / "run.log"), "startTime": "2026-07-05T00:00:00+00:00"},
    }
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "process_executable", lambda _pid: str(Path(sys.executable).resolve()))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(harness, "process_command", lambda _pid: expected_command)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=43210, cwd=str(tmp_path.resolve()), command=expected_command),
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
    assert result["checks"]["ownedByHarness"]["status"] == "PASS"
    assert result["checks"]["processStartTime"]["status"] == "PASS"
    assert result["checks"]["commandIdentity"]["status"] == "PASS"
    assert result["checks"]["interpreterIdentity"]["status"] == "PASS"
    assert result["checks"]["buildIdentity"]["status"] == "PASS"
    assert result["checks"]["directNoProxyHttp"]["status"] == "PASS"
    assert result["run"]["runId"] == "uat-20260705T000000Z-abc12345"
    assert result["run"]["runLogPath"] == str(tmp_path / "run.log")


def test_preflight_windows_allows_unobservable_cwd_when_stronger_identity_matches(
    monkeypatch,
    tmp_path: Path,
) -> None:
    expected_command = "python main.py --serve-only --host 127.0.0.1 --port 8102"
    asset_identity = _evidence_asset_identity(tmp_path)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "contract": "wolfystock_uat_runtime_harness_v1",
                "status": "PASS",
                "source": {"gitSha": "45b6965d"},
                "run": {
                    "runId": "uat-run",
                    "pid": 43210,
                    "cwd": str(tmp_path.resolve()),
                    "startTime": "2026-07-05T00:00:00+00:00",
                    "port": 8102,
                    "assetIdentity": asset_identity,
                    "evidencePath": str(evidence_path),
                    "runLogPath": str(tmp_path / "run.log"),
                },
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "2026-07-05T00:00:00+00:00",
                    "command": expected_command,
                    "interpreter": _evidence_interpreter(),
                    "listener": {"host": "127.0.0.1", "port": 8102},
                },
                "frontend": asset_identity,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "is_windows", lambda: True)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: None)
    monkeypatch.setattr(harness, "process_executable", lambda _pid: str(Path(sys.executable).resolve()))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(harness, "process_command", lambda _pid: expected_command)
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=43210, cwd=None, command=expected_command),
    )
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())

    result = harness.run_preflight(
        evidence_path=evidence_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8102,
    )

    assert result["status"] == "PASS"
    assert result["checks"]["cwd"]["status"] == "UNAVAILABLE"
    assert result["checks"]["cwd"]["observed"]["reasonCode"] == "cwd_unobservable"
    assert result["checks"]["ownedByHarness"]["status"] == "PASS"
    assert result["checks"]["processStartTime"]["status"] == "PASS"
    assert result["checks"]["commandIdentity"]["status"] == "PASS"
    assert result["checks"]["interpreterIdentity"]["status"] == "PASS"
    assert result["checks"]["buildIdentity"]["status"] == "PASS"
    assert result["checks"]["pidOwnsPort"]["status"] == "PASS"


def test_preflight_fails_closed_when_identity_evidence_is_missing(monkeypatch, tmp_path: Path) -> None:
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
                    "port": 8102,
                    "assetIdentity": {"mainJsAssetFilename": "index-CKPdXr8Q.js"},
                    "runLogPath": str(tmp_path / "run.log"),
                },
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "2026-07-05T00:00:00+00:00",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "process_executable", lambda _pid: str(Path(sys.executable).resolve()))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=43210, cwd=str(tmp_path.resolve()), command=None),
    )
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())

    result = harness.run_preflight(
        evidence_path=evidence_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8102,
    )

    assert result["status"] == "FAIL"
    assert result["checks"]["assetIdentity"]["status"] == "FAIL"
    assert result["checks"]["buildIdentity"]["status"] == "FAIL"
    assert result["checks"]["interpreterIdentity"]["status"] == "FAIL"


def test_preflight_windows_rejects_observable_cwd_mismatch(monkeypatch, tmp_path: Path) -> None:
    expected_command = "python main.py --serve-only --host 127.0.0.1 --port 8102"
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "contract": "wolfystock_uat_runtime_harness_v1",
                "status": "PASS",
                "source": {"gitSha": "45b6965d"},
                "run": {
                    "runId": "uat-run",
                    "pid": 43210,
                    "cwd": str(tmp_path.resolve()),
                    "startTime": "2026-07-05T00:00:00+00:00",
                    "port": 8102,
                    "assetIdentity": {"mainJsAssetFilename": "index-CKPdXr8Q.js"},
                    "evidencePath": str(evidence_path),
                    "runLogPath": str(tmp_path / "run.log"),
                },
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "2026-07-05T00:00:00+00:00",
                    "command": expected_command,
                    "listener": {"host": "127.0.0.1", "port": 8102},
                },
                "frontend": {"mainJsAssetFilename": "index-CKPdXr8Q.js"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "is_windows", lambda: True)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str((tmp_path / "other").resolve()))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(harness, "process_command", lambda _pid: expected_command)
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=43210, cwd=None, command=expected_command),
    )
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())

    result = harness.run_preflight(
        evidence_path=evidence_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8102,
    )

    assert result["status"] == "FAIL"
    assert result["checks"]["cwd"]["status"] == "FAIL"
    assert result["checks"]["cwd"]["observed"] == str((tmp_path / "other").resolve())


def test_preflight_posix_rejects_unobservable_cwd(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "contract": "wolfystock_uat_runtime_harness_v1",
                "status": "PASS",
                "source": {"gitSha": "45b6965d"},
                "run": {
                    "runId": "uat-run",
                    "pid": 43210,
                    "cwd": str(tmp_path.resolve()),
                    "startTime": "2026-07-05T00:00:00+00:00",
                    "port": 8102,
                    "assetIdentity": {"mainJsAssetFilename": "index-CKPdXr8Q.js"},
                    "evidencePath": str(evidence_path),
                    "runLogPath": str(tmp_path / "run.log"),
                },
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "Sun Jul  5 00:00:00 2026",
                    "listener": {"host": "127.0.0.1", "port": 8102},
                },
                "frontend": {"mainJsAssetFilename": "index-CKPdXr8Q.js"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "is_windows", lambda: False)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: None)
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "Sun Jul  5 00:00:00 2026")
    monkeypatch.setattr(harness, "process_command", lambda _pid: "python main.py --serve-only --port 8102")
    monkeypatch.setattr(
        harness,
        "find_port_owner",
        lambda _host, _port: harness.PortOwner(pid=43210, cwd=None, command="python main.py --serve-only"),
    )
    monkeypatch.setattr(harness, "DirectNoProxyHttpClient", lambda: _FakeClient())

    result = harness.run_preflight(
        evidence_path=evidence_path,
        expected_sha="45b6965d",
        host="127.0.0.1",
        port=8102,
    )

    assert result["status"] == "FAIL"
    assert result["checks"]["cwd"]["status"] == "FAIL"
    assert result["checks"]["cwd"]["observed"] is None


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
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
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
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
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
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="absent"))
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
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
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
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
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
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "Sun Jul  5 00:00:00 2026")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: str(tmp_path.resolve()))
    monkeypatch.setattr(harness, "find_port_owner", lambda _host, _port: None)
    monkeypatch.setattr(harness.os, "kill", lambda *_args, **_kwargs: pytest.fail("missing port owner must not be killed"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "pid_not_port_owner"


def test_safe_stop_windows_invalid_pid_returns_absent_without_raw_exception(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {"ownedByHarness": True, "processStartTime": "2026-07-05T00:00:00+00:00"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "is_windows", lambda: True)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="absent", windows_error=87))
    monkeypatch.setattr(harness, "_terminate_pid", lambda _pid: pytest.fail("invalid pid must not be terminated"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "absent"
    assert result["reasonCode"] == "runtime_already_absent"
    assert result["windowsError"] == 87
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["lifecycleEvents"][-1]["reasonCode"] == "runtime_already_absent"


def test_safe_stop_windows_access_denied_is_not_classified_as_absent(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {"ownedByHarness": True, "processStartTime": "2026-07-05T00:00:00+00:00"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "is_windows", lambda: True)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="access_denied", windows_error=5))
    monkeypatch.setattr(harness, "_terminate_pid", lambda _pid: pytest.fail("access denied process must not be terminated"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "access_denied"
    assert result["windowsError"] == 5
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["lifecycleEvents"][-1]["status"] == "rejected"
    assert payload["lifecycleEvents"][-1]["reasonCode"] == "access_denied"


def test_windows_port_owner_query_avoids_powershell_pid_collision(monkeypatch) -> None:
    scripts: list[str] = []

    def _run(script: str) -> subprocess.CompletedProcess[str]:
        scripts.append(script)
        return subprocess.CompletedProcess(
            ["powershell"],
            0,
            stdout='{"pid":43210,"command":"python main.py --serve-only"}',
            stderr="",
        )

    monkeypatch.setattr(harness, "_run_windows_powershell", _run)

    owner = harness._find_windows_port_owner(8102)

    assert owner == harness.PortOwner(pid=43210, cwd=None, command="python main.py --serve-only")
    assert "$pid" not in scripts[0].lower()
    assert "OwningProcess" in scripts[0]
    assert "Select-Object -First 1" in scripts[0]


def test_safe_stop_windows_rejects_reused_pid_when_command_identity_mismatches(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "2026-07-05T00:00:00+00:00",
                    "command": f'"{sys.executable}" "{tmp_path / "main.py"}" --serve-only --port 8000',
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "is_windows", lambda: True)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: None)
    monkeypatch.setattr(harness, "process_command", lambda _pid: '"C:\\Python\\python.exe" other.py --serve-only')
    monkeypatch.setattr(harness, "_terminate_pid", lambda _pid: pytest.fail("command mismatch process must not be terminated"))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "rejected"
    assert result["reasonCode"] == "pid_command_mismatch"


def test_safe_stop_windows_allows_matching_command_identity_and_terminates(monkeypatch, tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    expected_command = f'"{sys.executable}" "{tmp_path / "main.py"}" --serve-only --port 8000'
    evidence_path.write_text(
        json.dumps(
            {
                "run": {"pid": 43210, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                "runtime": {
                    "ownedByHarness": True,
                    "processStartTime": "2026-07-05T00:00:00+00:00",
                    "command": expected_command,
                },
            }
        ),
        encoding="utf-8",
    )
    terminated: list[int] = []
    monkeypatch.setattr(harness, "is_windows", lambda: True)
    monkeypatch.setattr(harness, "_probe_process", lambda _pid: harness.ProcessProbe(state="alive"))
    monkeypatch.setattr(harness, "process_start_time", lambda _pid: "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(harness, "process_cwd", lambda _pid: None)
    monkeypatch.setattr(harness, "process_command", lambda _pid: expected_command)
    monkeypatch.setattr(harness, "_terminate_pid", lambda pid: terminated.append(pid))

    result = harness.stop_runtime_from_evidence(evidence_path)

    assert result["status"] == "stopped"
    assert result["reasonCode"] == "task_owned_pid_terminated"
    assert terminated == [43210]


def test_stop_owned_runtime_reports_already_absent() -> None:
    process = _AlreadyAbsentProcess()

    result = harness.stop_owned_runtime(process)

    assert result["status"] == "absent"
    assert process.terminated is False
    assert process.killed is False


def test_start_runtime_uses_windows_venv_python_when_available(monkeypatch, tmp_path: Path) -> None:
    main_py = tmp_path / "main.py"
    main_py.write_text("print('ok')\n", encoding="utf-8")
    windows_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    windows_python.parent.mkdir(parents=True)
    windows_python.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def _popen(command, cwd, env, stdout, stderr, text):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        captured["text"] = text
        return _FakeProcess()

    monkeypatch.setattr(harness, "is_windows", lambda: True)
    monkeypatch.setattr(harness.subprocess, "Popen", _popen)

    process = harness.start_runtime(tmp_path, host="127.0.0.1", port=8125)

    assert process.pid == 43210
    assert captured["command"][0] == str(windows_python)
    assert captured["command"][1] == str(main_py)


def test_start_runtime_preserves_posix_venv_python_default(monkeypatch, tmp_path: Path) -> None:
    main_py = tmp_path / "main.py"
    main_py.write_text("print('ok')\n", encoding="utf-8")
    posix_python = tmp_path / ".venv" / "bin" / "python"
    posix_python.parent.mkdir(parents=True)
    posix_python.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def _popen(command, cwd, env, stdout, stderr, text):
        captured["command"] = command
        return _FakeProcess()

    monkeypatch.setattr(harness, "is_windows", lambda: False)
    monkeypatch.setattr(harness.subprocess, "Popen", _popen)

    harness.start_runtime(tmp_path, host="127.0.0.1", port=8125)

    assert captured["command"][0] == str(posix_python)


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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only integration proof")
def test_stop_from_evidence_windows_can_terminate_owned_child_with_recorded_identity(tmp_path: Path) -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path)
    try:
        process_start_time = harness.process_start_time(child.pid)
        process_command = harness.process_command(child.pid)
        assert process_start_time
        assert process_command

        evidence_path = tmp_path / "evidence.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "run": {"pid": child.pid, "cwd": str(tmp_path.resolve()), "runId": "uat-run"},
                    "runtime": {
                        "ownedByHarness": True,
                        "processStartTime": process_start_time,
                        "command": process_command,
                    },
                }
            ),
            encoding="utf-8",
        )

        result = harness.stop_runtime_from_evidence(evidence_path)

        assert result["status"] == "stopped"
        child.wait(timeout=10)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)


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
