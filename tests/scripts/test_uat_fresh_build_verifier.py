from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import scripts.uat_fresh_build_verifier as verifier
from src.services.build_provenance_service import BackendBuildInfo


def _write_vite_static_dist(static_root: Path, *, asset_name: str = "index-CKPdXr8Q.js") -> Path:
    assets_dir = static_root / "assets"
    assets_dir.mkdir(parents=True)
    (static_root / "index.html").write_text(
        f'<html><head><script type="module" crossorigin src="/assets/{asset_name}"></script></head></html>',
        encoding="utf-8",
    )
    asset_path = assets_dir / asset_name
    asset_path.write_text("console.log('wolfystock build');\n", encoding="utf-8")
    return asset_path


def _set_mtime(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))


def _backend_info(commit_timestamp: datetime) -> BackendBuildInfo:
    return BackendBuildInfo(
        git_sha="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        branch="main",
        commit_timestamp=commit_timestamp,
    )


def test_verify_frontend_static_build_accepts_fresh_main_asset(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    asset_path = _write_vite_static_dist(static_root)
    backend_commit_at = datetime(2026, 6, 16, 11, 47, tzinfo=timezone.utc)
    frontend_built_at = datetime(2026, 6, 16, 12, 5, tzinfo=timezone.utc)
    _set_mtime(static_root / "index.html", frontend_built_at)
    _set_mtime(asset_path, frontend_built_at)

    result = verifier.verify_frontend_static_build(
        static_root=static_root,
        backend_info=_backend_info(backend_commit_at),
        repo_root=tmp_path,
    )

    assert result.ok is True
    assert result.error_codes == []
    assert result.payload["frontendMainAssetFilename"] == "index-CKPdXr8Q.js"
    assert result.payload["frontendMainAssetHash"] == "CKPdXr8Q"
    assert result.payload["frontendStaticBuildTimestamp"] == "2026-06-16T12:05:00+00:00"
    assert result.payload["freshnessStatus"] == "fresh"
    assert result.payload["stale"] is False


def test_verify_frontend_static_build_fails_closed_when_asset_is_stale(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    asset_path = _write_vite_static_dist(static_root)
    backend_commit_at = datetime(2026, 6, 16, 11, 47, tzinfo=timezone.utc)
    frontend_built_at = datetime(2026, 6, 16, 3, 35, tzinfo=timezone.utc)
    _set_mtime(static_root / "index.html", frontend_built_at)
    _set_mtime(asset_path, frontend_built_at)

    result = verifier.verify_frontend_static_build(
        static_root=static_root,
        backend_info=_backend_info(backend_commit_at),
        repo_root=tmp_path,
    )

    assert result.ok is False
    assert "frontend_static_build_stale" in result.error_codes
    assert result.payload["freshnessStatus"] == "stale"
    assert result.payload["stale"] is True
    assert "frontend_build_older_than_backend_commit" in result.payload["reasonCodes"]


def test_verify_frontend_static_build_fails_closed_when_main_asset_is_missing(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    assets_dir = static_root / "assets"
    assets_dir.mkdir(parents=True)
    (static_root / "index.html").write_text(
        '<html><head><script type="module" src="/assets/index-Missing123.js"></script></head></html>',
        encoding="utf-8",
    )

    result = verifier.verify_frontend_static_build(
        static_root=static_root,
        backend_info=_backend_info(datetime(2026, 6, 16, 11, 47, tzinfo=timezone.utc)),
        repo_root=tmp_path,
    )

    assert result.ok is False
    assert "frontend_main_asset_missing" in result.error_codes
    assert result.payload["frontendMainAssetFilename"] == "index-Missing123.js"
    assert result.payload["freshnessStatus"] == "unknown"


def test_verify_frontend_static_build_fails_closed_when_freshness_is_unknown(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    asset_path = _write_vite_static_dist(static_root)
    frontend_built_at = datetime(2026, 6, 16, 12, 5, tzinfo=timezone.utc)
    _set_mtime(static_root / "index.html", frontend_built_at)
    _set_mtime(asset_path, frontend_built_at)

    result = verifier.verify_frontend_static_build(
        static_root=static_root,
        backend_info=verifier.BackendBuildInfo(
            git_sha="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
            branch="main",
            commit_timestamp=None,
        ),
        repo_root=tmp_path,
    )

    assert result.ok is False
    assert "frontend_static_build_freshness_unknown" in result.error_codes


def test_verify_frontend_static_build_can_allow_unknown_freshness_for_manual_diagnostics(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    asset_path = _write_vite_static_dist(static_root)
    frontend_built_at = datetime(2026, 6, 16, 12, 5, tzinfo=timezone.utc)
    _set_mtime(static_root / "index.html", frontend_built_at)
    _set_mtime(asset_path, frontend_built_at)

    result = verifier.verify_frontend_static_build(
        static_root=static_root,
        backend_info=verifier.BackendBuildInfo(
            git_sha="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
            branch="main",
            commit_timestamp=None,
        ),
        repo_root=tmp_path,
        allow_unknown_freshness=True,
    )

    assert result.ok is True
    assert "frontend_static_build_freshness_unknown" in result.warning_codes


def test_verify_admin_build_provenance_accepts_fresh_stale_and_unknown_statuses() -> None:
    local_payload = {
        "backendGitSha": "e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        "frontendMainAssetFilename": "index-CKPdXr8Q.js",
        "frontendMainAssetHash": "CKPdXr8Q",
    }

    for freshness_status in ("fresh", "stale", "unknown"):
        admin_payload = {
            "buildProvenance": {
                **local_payload,
                "contract": "admin_build_provenance_v1",
                "freshnessStatus": freshness_status,
                "reasonCodes": ["provenance_observed"],
            }
        }

        result = verifier.verify_admin_build_provenance(admin_payload, local_payload=local_payload)

        assert result.ok is True
        assert result.error_codes == []
        assert result.payload["freshnessStatus"] == freshness_status


def test_verify_admin_build_provenance_rejects_mismatched_static_bundle() -> None:
    local_payload = {
        "backendGitSha": "e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        "frontendMainAssetFilename": "index-CKPdXr8Q.js",
        "frontendMainAssetHash": "CKPdXr8Q",
    }
    admin_payload = {
        "buildProvenance": {
            **local_payload,
            "contract": "admin_build_provenance_v1",
            "freshnessStatus": "fresh",
            "frontendMainAssetFilename": "index-Stale999.js",
            "frontendMainAssetHash": "Stale999",
        }
    }

    result = verifier.verify_admin_build_provenance(admin_payload, local_payload=local_payload)

    assert result.ok is False
    assert "admin_frontend_main_asset_mismatch" in result.error_codes


def test_verify_admin_build_provenance_rejects_stale_admin_provenance_mismatch() -> None:
    local_payload = {
        "backendGitSha": "e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        "frontendMainAssetFilename": "index-CKPdXr8Q.js",
        "frontendMainAssetHash": "CKPdXr8Q",
        "frontendStaticBuildTimestamp": "2026-06-16T12:05:00+00:00",
        "freshnessStatus": "fresh",
        "stale": False,
    }
    admin_payload = {
        "buildProvenance": {
            **local_payload,
            "contract": "admin_build_provenance_v1",
            "frontendStaticBuildTimestamp": "2026-06-16T03:35:00+00:00",
            "freshnessStatus": "stale",
            "stale": True,
            "reasonCodes": ["frontend_build_older_than_backend_commit"],
        }
    }

    result = verifier.verify_admin_build_provenance(admin_payload, local_payload=local_payload)

    assert result.ok is False
    assert "admin_frontend_static_build_timestamp_mismatch" in result.error_codes
    assert "admin_freshness_status_mismatch" in result.error_codes
    assert "admin_stale_flag_mismatch" in result.error_codes


def test_verify_admin_build_provenance_requires_reason_codes() -> None:
    result = verifier.verify_admin_build_provenance(
        {
            "buildProvenance": {
                "contract": "admin_build_provenance_v1",
                "freshnessStatus": "fresh",
            }
        }
    )

    assert result.ok is False
    assert "admin_build_provenance_reason_codes_missing" in result.error_codes


def test_verify_admin_build_provenance_rejects_missing_comparable_fields() -> None:
    local_payload = {
        "backendGitSha": "e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        "frontendMainAssetFilename": "index-CKPdXr8Q.js",
        "frontendMainAssetHash": "CKPdXr8Q",
        "frontendStaticBuildTimestamp": "2026-06-16T12:05:00+00:00",
        "freshnessStatus": "fresh",
        "stale": False,
    }
    admin_payload = {
        "buildProvenance": {
            "contract": "admin_build_provenance_v1",
            "freshnessStatus": "fresh",
            "reasonCodes": ["frontend_build_not_older_than_backend_commit"],
        }
    }

    result = verifier.verify_admin_build_provenance(admin_payload, local_payload=local_payload)

    assert result.ok is False
    assert "admin_backend_git_sha_missing" in result.error_codes
    assert "admin_frontend_main_asset_missing" in result.error_codes
    assert "admin_frontend_main_asset_hash_missing" in result.error_codes
    assert "admin_frontend_static_build_timestamp_missing" in result.error_codes
    assert "admin_stale_flag_missing" in result.error_codes


def test_git_preflight_fails_on_dirty_or_conflicted_tree(monkeypatch) -> None:
    def _git_output(_repo_root: Path, *args: str) -> str | None:
        if args == ("diff", "--name-only", "--diff-filter=U"):
            return "api/app.py"
        if args == ("status", "--short"):
            return " M api/app.py"
        return None

    monkeypatch.setattr(verifier, "_git_output", _git_output)

    errors = verifier.verify_git_preflight(Path("/repo"))

    assert "merge_conflicts_present" in errors
    assert "worktree_dirty" in errors


def test_main_runs_hygiene_before_frontend_build(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(verifier, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        verifier,
        "read_backend_info",
        lambda _repo_root: _backend_info(datetime(2026, 6, 16, 11, 47, tzinfo=timezone.utc)),
    )
    monkeypatch.setattr(verifier, "verify_git_preflight", lambda _repo_root: [])

    def _hygiene(_repo_root: Path) -> list[str]:
        calls.append("hygiene")
        return ["generated_artifacts_tracked: static/node_modules/cache paths must not be committed"]

    def _build(_repo_root: Path) -> int:
        calls.append("build")
        return 0

    monkeypatch.setattr(verifier, "verify_generated_artifact_hygiene", _hygiene)
    monkeypatch.setattr(verifier, "run_frontend_build", _build)

    result = verifier.main([])

    assert result == 1
    assert calls == ["hygiene"]


def test_run_frontend_build_bootstraps_dependencies_when_node_modules_missing(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    web_dir = tmp_path / "apps" / "dsa-web"
    web_dir.mkdir(parents=True)
    (web_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    monkeypatch.setattr(verifier.shutil, "which", lambda name: "/usr/local/bin/npm" if name == "npm" else None)

    def _run(command, cwd, check):
        commands.append(tuple(command))
        assert cwd == tmp_path
        assert check is False
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(verifier.subprocess, "run", _run)

    result = verifier.run_frontend_build(tmp_path)

    assert result == 0
    assert commands == [
        ("/usr/local/bin/npm", "--prefix", "apps/dsa-web", "ci"),
        ("/usr/local/bin/npm", "--prefix", "apps/dsa-web", "run", "build"),
    ]
    assert "Frontend bootstrap command: npm --prefix apps/dsa-web ci && npm --prefix apps/dsa-web run build" in capsys.readouterr().out


def test_run_frontend_build_fails_closed_when_npm_is_missing(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(verifier.shutil, "which", lambda _name: None)

    result = verifier.run_frontend_build(tmp_path)

    assert result == 1
    assert "npm is unavailable" in capsys.readouterr().err


def test_direct_script_help_entrypoint_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/uat_fresh_build_verifier.py", "--help"],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "Rebuild or verify local frontend static assets" in result.stdout


def test_admin_status_url_instruction_sanitizes_secrets_but_preserves_port() -> None:
    url = verifier._safe_url_for_instruction(
        "http://user:secret@127.0.0.1:8000/api/v1/admin/ops/status?token=raw"
    )

    assert url == "http://127.0.0.1:8000/api/v1/admin/ops/status"
    assert "secret" not in url
    assert "token" not in url
