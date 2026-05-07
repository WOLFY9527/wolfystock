import shutil
import subprocess
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "backup_restore_drill_check.sh"


def _run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    (repo / "tests").mkdir()
    (repo / "tests" / "fixtures" / "ops").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT_SOURCE, repo / "scripts" / "backup_restore_drill_check.sh")
    (repo / "tests" / "test_backup_restore_drill_smoke.py").write_text(
        "# disposable restore smoke placeholder\n",
        encoding="utf-8",
    )
    (repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_artifact.marker").write_text(
        "synthetic backup artifact marker\n",
        encoding="utf-8",
    )
    (repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_metadata.json").write_text(
        json.dumps(
            {
                "backup_id": "synthetic-drill-001",
                "created_at": "2026-05-07T00:00:00Z",
                "artifact_path": "backup_restore_preflight_artifact.marker",
                "schema_version": "backup_restore_preflight_v1",
                "source_environment": "synthetic",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _run(["git", "init", "-b", "main"], repo, check=True)
    _run(["git", "config", "user.email", "codex@example.com"], repo, check=True)
    _run(["git", "config", "user.name", "Codex Test"], repo, check=True)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _run(["git", "add", "README.md", "scripts", "tests"], repo, check=True)
    _run(["git", "commit", "-m", "initial"], repo, check=True)
    return repo


def _drill_check(repo: Path, *args: str, **kwargs):
    return _run(["bash", "scripts/backup_restore_drill_check.sh", *args], repo, **kwargs)


def _write_metadata(repo: Path, artifact_path: Path, *, created_at: datetime | None = None, schema_version: str = "backup_restore_preflight_v1") -> Path:
    metadata_path = repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "backup_id": "synthetic-drill-001",
                "created_at": (created_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
                "artifact_path": str(artifact_path),
                "schema_version": schema_version,
                "source_environment": "synthetic",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return metadata_path


def test_backup_restore_drill_check_prints_production_like_preflight_evidence(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.sqlite"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "restore-target" / "restored.sqlite"),
    )

    assert result.returncode == 0
    assert "Production-like backup/restore drill preflight" in result.stdout
    assert "Mode: dry-run/simulated" in result.stdout
    assert "tests/test_backup_restore_drill_smoke.py: present" in result.stdout
    assert "Backup artifact: present" in result.stdout
    assert "Backup timestamp: fresh" in result.stdout
    assert "Schema compatibility: ok (backup_restore_preflight_v1)" in result.stdout
    assert "Restore target isolation: accepted" in result.stdout
    assert "Dry-run evidence: suitable for launch readiness review" in result.stdout
    assert "python3 -m pytest tests/test_backup_restore_drill_smoke.py -q" in result.stdout
    assert "bash -n scripts/backup_restore_drill_check.sh" in result.stdout
    assert "No production DB, migration, PostgreSQL, or backup infrastructure action is performed" in result.stdout


def test_backup_restore_drill_check_rejects_unsafe_db_path(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.sqlite"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        "/var/lib/postgresql/prod/wolfystock.sqlite",
    )

    assert result.returncode == 1
    assert "[FAIL] Unsafe restore target refused" in result.stderr
    assert "/var/lib/postgresql/prod/wolfystock.sqlite" in result.stderr


def test_backup_restore_drill_check_does_not_mutate_files(tmp_path):
    repo = _init_repo(tmp_path)
    metadata_path = repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_metadata.json"

    before = _run(["git", "status", "--short"], repo, check=True).stdout
    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.sqlite"),
    )
    after = _run(["git", "status", "--short"], repo, check=True).stdout

    assert result.returncode == 0
    assert before == ""
    assert after == ""


def test_backup_restore_drill_check_fails_without_metadata(tmp_path):
    repo = _init_repo(tmp_path)

    result = _drill_check(repo, "--restore-target", str(tmp_path / "scratch" / "restore.sqlite"))

    assert result.returncode == 1
    assert "[FAIL] Backup metadata is required" in result.stderr


def test_backup_restore_drill_check_fails_for_stale_metadata(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.sqlite"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(
        repo,
        artifact_path,
        created_at=datetime.now(timezone.utc) - timedelta(hours=73),
    )

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.sqlite"),
    )

    assert result.returncode == 1
    assert "[FAIL] Stale backup metadata" in result.stderr


def test_backup_restore_drill_check_fails_for_incompatible_schema(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.sqlite"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path, schema_version="legacy_backup_v0")

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.sqlite"),
    )

    assert result.returncode == 1
    assert "[FAIL] Incompatible backup metadata schema" in result.stderr


def test_backup_restore_drill_check_fails_when_restore_target_exists(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.sqlite"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)
    restore_target = tmp_path / "scratch" / "restored.sqlite"
    restore_target.parent.mkdir()
    restore_target.write_text("existing restore target\n", encoding="utf-8")

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(restore_target),
    )

    assert result.returncode == 1
    assert "[FAIL] Restore target already exists" in result.stderr
