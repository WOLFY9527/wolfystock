import shutil
import subprocess
import json
import os
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
    (repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_wal_archive.marker").write_text(
        "synthetic WAL archive marker\n",
        encoding="utf-8",
    )
    (repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_metadata.json").write_text(
        json.dumps(
            {
                "backup_id": "synthetic-drill-001",
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "artifact_path": "backup_restore_preflight_artifact.marker",
                "schema_version": "backup_restore_preflight_v1",
                "application_schema_version": "wolfystock_ops_readiness_v1",
                "database_engine": "postgresql",
                "source_environment": "synthetic",
                "pitr": {
                    "target_time": "2026-05-07T00:10:00Z",
                    "window_start": "2026-05-07T00:00:00Z",
                    "window_end": "2026-05-07T00:20:00Z",
                    "wal_archive_path": "backup_restore_preflight_wal_archive.marker",
                    "restore_point_label": "synthetic-pitr-readiness",
                },
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


def _write_metadata(
    repo: Path,
    artifact_path: Path,
    *,
    created_at: datetime | None = None,
    schema_version: str = "backup_restore_preflight_v1",
    application_schema_version: str = "wolfystock_ops_readiness_v1",
    pitr: dict | None = None,
) -> Path:
    metadata_path = repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_metadata.json"
    wal_archive_path = repo / "tests" / "fixtures" / "ops" / "backup_restore_preflight_wal_archive.marker"
    metadata_path.write_text(
        json.dumps(
            {
                "backup_id": "synthetic-drill-001",
                "created_at": (created_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
                "artifact_path": str(artifact_path),
                "schema_version": schema_version,
                "application_schema_version": application_schema_version,
                "database_engine": "postgresql",
                "source_environment": "synthetic",
                "pitr": pitr
                if pitr is not None
                else {
                    "target_time": "2026-05-07T00:10:00Z",
                    "window_start": "2026-05-07T00:00:00Z",
                    "window_end": "2026-05-07T00:20:00Z",
                    "wal_archive_path": str(wal_archive_path),
                    "restore_point_label": "synthetic-pitr-readiness",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return metadata_path


def _write_real_restore_evidence(repo: Path, *, overrides: dict | None = None) -> Path:
    evidence_path = repo / "tests" / "fixtures" / "ops" / "real_restore_drill_evidence.json"
    payload = {
        "schema_version": "wolfystock_restore_drill_evidence_v1",
        "drill_id": "isolated-restore-2026-05-07",
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "database_engine": "postgresql",
        "source_environment": "staging",
        "restore_target": {
            "isolated": True,
            "target_type": "isolated_postgresql",
            "target_label": "staging-restore-drill",
            "production_target": False,
        },
        "execution": {
            "execution_opt_in": True,
            "restore_executed": True,
            "restore_status": "pass",
            "pitr_executed": True,
            "pitr_status": "pass",
            "network_calls_performed_by_checker": False,
        },
        "rpo_minutes_observed": 10,
        "rto_minutes_observed": 42,
        "post_restore_checks": {
            "app_boot": "pass",
            "storage_readiness": "pass",
            "auth_login": "pass",
            "owner_isolation": "pass",
            "durable_task_poll": "pass",
            "admin_logs_sanitized": "pass",
            "cost_observability": "pass",
            "provider_diagnostics_sanitized": "pass",
            "scanner_artifact_read": "pass",
            "backtest_artifact_read": "pass",
            "portfolio_replay": "pass",
            "batch_a_indexes": "pass",
        },
        "sanitization": {
            "evidence_redacted": True,
            "secrets_printed": False,
            "raw_dsn_present": False,
            "raw_tokens_present": False,
            "raw_passwords_present": False,
        },
        "blockers": [],
    }
    if overrides:
        payload.update(overrides)
    evidence_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return evidence_path


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
    assert "Application schema compatibility: ok (wolfystock_ops_readiness_v1)" in result.stdout
    assert "PITR metadata: validated" in result.stdout
    assert "WAL/archive metadata: present" in result.stdout
    assert "Restore target isolation: accepted" in result.stdout
    assert "Restore execution: disabled by default" in result.stdout
    assert "Dry-run evidence: suitable for launch readiness review" in result.stdout
    assert "Real restore/PITR execution: pending (no real evidence artifact supplied)" in result.stdout
    assert "python3 -m pytest tests/test_backup_restore_drill_smoke.py -q" in result.stdout
    assert "bash -n scripts/backup_restore_drill_check.sh" in result.stdout
    assert "No production DB, migration, PostgreSQL restore, network, or backup infrastructure action is performed" in result.stdout


def test_backup_restore_drill_check_accepts_real_restore_evidence_artifact(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)
    evidence_path = _write_real_restore_evidence(repo)

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
        "--real-restore-evidence",
        str(evidence_path),
    )

    assert result.returncode == 0
    assert "Real restore/PITR evidence: accepted" in result.stdout
    assert "Real restore execution: externally supplied evidence only; checker did not execute restore" in result.stdout
    assert "Restore execution status: pass" in result.stdout
    assert "PITR execution status: pass" in result.stdout
    assert "Post-restore checks: 12 passed" in result.stdout
    assert "Real restore/PITR execution: pending" not in result.stdout


def test_backup_restore_drill_check_rejects_real_evidence_with_unredacted_dsn(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)
    unsafe_dsn = "postgresql://restore_user:super-secret-password@localhost:5432/wolfystock_restore"
    evidence_path = _write_real_restore_evidence(
        repo,
        overrides={
            "restore_target": {
                "isolated": True,
                "target_type": "isolated_postgresql",
                "target_label": "staging-restore-drill",
                "production_target": False,
                "restore_dsn": unsafe_dsn,
            },
        },
    )

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
        "--real-restore-evidence",
        str(evidence_path),
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "[FAIL] Real restore evidence contains unredacted sensitive value" in result.stderr
    assert unsafe_dsn not in combined_output
    assert "super-secret-password" not in combined_output
    assert "wolfystock_restore" not in combined_output


def test_backup_restore_drill_check_rejects_incomplete_real_restore_evidence(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)
    evidence_path = _write_real_restore_evidence(
        repo,
        overrides={
            "execution": {
                "execution_opt_in": True,
                "restore_executed": True,
                "restore_status": "pass",
                "pitr_executed": False,
                "pitr_status": "pending",
                "network_calls_performed_by_checker": False,
            },
        },
    )

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
        "--real-restore-evidence",
        str(evidence_path),
    )

    assert result.returncode == 1
    assert "[FAIL] Real restore evidence PITR execution must be pass" in result.stderr


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
    assert "/var/lib/postgresql/prod/wolfystock.sqlite" not in result.stderr


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


def test_backup_restore_drill_check_fails_for_incompatible_application_schema(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(
        repo,
        artifact_path,
        application_schema_version="wolfystock_legacy_schema_v0",
    )

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
    )

    assert result.returncode == 1
    assert "[FAIL] Incompatible application schema metadata" in result.stderr


def test_backup_restore_drill_check_fails_without_pitr_metadata(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path, pitr={})

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
    )

    assert result.returncode == 1
    assert "[FAIL] PITR metadata missing fields" in result.stderr


def test_backup_restore_drill_check_fails_for_pitr_target_outside_window(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    wal_archive_path = tmp_path / "backup-artifacts" / "synthetic-wal.marker"
    wal_archive_path.write_text("synthetic WAL placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(
        repo,
        artifact_path,
        pitr={
            "target_time": "2026-05-07T01:00:00Z",
            "window_start": "2026-05-07T00:00:00Z",
            "window_end": "2026-05-07T00:20:00Z",
            "wal_archive_path": str(wal_archive_path),
            "restore_point_label": "synthetic-pitr-readiness",
        },
    )

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
    )

    assert result.returncode == 1
    assert "[FAIL] PITR target_time is outside the available restore window" in result.stderr


def test_backup_restore_drill_check_rejects_production_dsn_without_leaking_value(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)
    unsafe_dsn = "postgresql://app_user:super-secret-password@prod.db.example.com:5432/wolfystock_prod"

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
        "--restore-dsn",
        unsafe_dsn,
    )

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "[FAIL] Restore DSN refused" in result.stderr
    assert unsafe_dsn not in combined_output
    assert "super-secret-password" not in combined_output
    assert "prod.db.example.com" not in combined_output


def test_backup_restore_drill_check_accepts_explicit_local_safe_test_dsn_without_leaking_value(tmp_path):
    repo = _init_repo(tmp_path)
    artifact_path = tmp_path / "backup-artifacts" / "synthetic-backup.dump"
    artifact_path.parent.mkdir()
    artifact_path.write_text("synthetic backup placeholder\n", encoding="utf-8")
    metadata_path = _write_metadata(repo, artifact_path)
    safe_dsn = "postgresql://test_user:test-password@localhost:5432/wolfystock_restore_synthetic"

    result = _drill_check(
        repo,
        "--metadata",
        str(metadata_path),
        "--restore-target",
        str(tmp_path / "scratch" / "restore.pg"),
        "--restore-dsn",
        safe_dsn,
        env={
            **os.environ,
            "WOLFYSTOCK_RESTORE_PREFLIGHT_SAFE_TEST_DSN": "1",
        },
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "Restore DSN: accepted (local synthetic/test target, value redacted)" in result.stdout
    assert safe_dsn not in combined_output
    assert "test-password" not in combined_output
    assert "wolfystock_restore_synthetic" not in combined_output


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
