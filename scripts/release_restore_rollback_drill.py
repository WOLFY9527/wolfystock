#!/usr/bin/env python3
"""Validate offline drill packets or execute a bounded local restore qualification.

Offline mode accepts only sanitized operator labels and remains advisory. The
explicit local-isolated mode uses the managed test run root to exercise the
application's SQLite backup, restore, startup, and rollback path. Neither mode
approves a release or touches production storage, secrets, or networks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backup_restore_drill_safe_root import validate_run_identity


SCHEMA_VERSION = "wolfystock_release_restore_rollback_drill_v1"
INPUT_SCHEMA_VERSION = "wolfystock_release_restore_rollback_drill_input_v1"
MAX_ARTIFACT_BYTES = 32768
MAX_FINDINGS = 20
REQUIRED_FIELDS = (
    "backupLabel",
    "restoreDrillLabel",
    "rollbackOwnerLabel",
    "releaseCandidateLabel",
    "rpoRtoNotes",
    "frontendRollbackPlan",
    "backendRollbackPlan",
    "databaseRollbackRestorePlan",
    "adminAuthRecoveryNote",
)
RESTORE_FIELDS = {
    "backupLabel",
    "restoreDrillLabel",
    "rpoRtoNotes",
    "databaseRollbackRestorePlan",
    "adminAuthRecoveryNote",
}
ROLLBACK_FIELDS = {
    "rollbackOwnerLabel",
    "releaseCandidateLabel",
    "frontendRollbackPlan",
    "backendRollbackPlan",
    "databaseRollbackRestorePlan",
    "adminAuthRecoveryNote",
}
REQUIRED_FALSE_ASSERTIONS = (
    "productionDbConnected",
    "secretsRead",
    "migrationsRun",
    "databasesRestored",
    "filesDeleted",
    "notificationsSent",
    "networkCallsMade",
    "destructiveOperationsExecuted",
)
SAFE_TEXT_VALUES = {
    "",
    "***",
    "********",
    "[redacted]",
    "redacted",
    "<redacted>",
    "masked",
    "missing",
    "none",
    "not_applicable",
    "present",
    "sanitized",
}
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "dsn",
    "env",
    "password",
    "private_key",
    "raw_log",
    "raw_payload",
    "raw_response",
    "secret",
    "session",
    "token",
    "webhook",
)
SAFE_FIELD_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/@+-]{2,479}$")
ABSOLUTE_PATH_PATTERN = re.compile(r"(^|\s)(?:/[^/\s][^\s]*|~[/\\][^\s]*|[A-Za-z]:[\\/][^\s]*)")
SECRET_VALUE_PATTERNS = (
    re.compile(
        r"([?&](?:api[-_]?key|apikey|access_token|token|secret|password|cookie|session)=)"
        r"(?!\*{3}|redacted)[^&#\s]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:api[-_]?key|apikey|access_token|token|secret|password|cookie|session|dsn)\s*"
        r"[=:]\s*(?!\*{3}|redacted\b)[^\s,;&]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bAuthorization\s*:\s*Bearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+(?!\*{3}|redacted\b)[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\b(?:postgres|postgresql|mysql|redis)://[^:/@\s]+:[^@\s]+@", re.IGNORECASE),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
)
DESTRUCTIVE_TEXT_PATTERNS = (
    re.compile(r"\b(?:dropdb|createdb|pg_restore|psql)\b.*(?:prod|production|primary|live)", re.IGNORECASE),
    re.compile(r"\b(?:DROP|TRUNCATE)\s+(?:DATABASE|SCHEMA|TABLE)\b", re.IGNORECASE),
    re.compile(r"\b(?:rm\s+-rf|unlink|shred)\b", re.IGNORECASE),
    re.compile(r"\b(?:restore|promote|failover)\s+(?:prod|production|primary|live)\b", re.IGNORECASE),
)
NETWORK_TEXT_PATTERNS = (
    re.compile(r"\b(?:curl|wget|httpie|nc|telnet)\b", re.IGNORECASE),
    re.compile(r"\bhttps?://", re.IGNORECASE),
)
APPROVAL_CLAIM_PATTERNS = (
    re.compile(r"\blaunch[-_ ]?approved\b", re.IGNORECASE),
    re.compile(r"\blaunch[-_ ]?go\b", re.IGNORECASE),
    re.compile(r"\brelease[-_ ]?approved\b", re.IGNORECASE),
    re.compile(r"^\s*GO\s*$", re.IGNORECASE),
)
APPROVAL_KEYS = {"launchapproved", "releaseapproved", "launchgo", "go"}
LOCAL_DRILL_SCHEMA_VERSION = "wolfystock_t689_local_isolated_restore_drill_v1"
LOCAL_DRILL_PROFILE = "local_isolated_release_profile"
_CANDIDATE_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class LocalDrillError(RuntimeError):
    """Fail the executable local drill without exposing mutable local details."""


def _empty_artifact() -> dict[str, Any]:
    return {
        "schemaVersion": INPUT_SCHEMA_VERSION,
        "mode": "offline_empty",
    }


def _load_artifact(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact_too_large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("artifact_invalid_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("artifact_not_json_object")
    return payload


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _normalize_key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _safe_text(value: str) -> bool:
    return value.strip().lower() in SAFE_TEXT_VALUES


def _finding(path: str, reason: str) -> dict[str, str]:
    return {"path": path or "$", "reasonCode": reason}


def _find_unsafe_values(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = _path_join(path, key_text)
            normalized_key = _normalize_key(key_text)
            compact_key = _compact_key(key_text)
            if compact_key in APPROVAL_KEYS and nested is True:
                findings.append(_finding(nested_path, "release_or_launch_approval_claim_not_allowed"))
                continue
            if isinstance(nested, str) and any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                if not _safe_text(nested):
                    findings.append(_finding(nested_path, "sensitive_key_contains_value"))
                    continue
            findings.extend(_find_unsafe_values(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_unsafe_values(nested, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        if _safe_text(value):
            return findings
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "secret_like_value_detected"))
                return findings
        if ABSOLUTE_PATH_PATTERN.search(value):
            findings.append(_finding(path, "unsafe_path_like_value"))
            return findings
        for pattern in DESTRUCTIVE_TEXT_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "destructive_operation_text_not_allowed"))
                return findings
        for pattern in NETWORK_TEXT_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "network_call_text_not_allowed"))
                return findings
        for pattern in APPROVAL_CLAIM_PATTERNS:
            if pattern.search(value):
                findings.append(_finding(path, "release_or_launch_approval_claim_not_allowed"))
                return findings
    return findings


def _required_fields_check(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    invalid = [
        field
        for field in REQUIRED_FIELDS
        if field in payload and not (isinstance(payload[field], str) and SAFE_FIELD_PATTERN.fullmatch(payload[field]))
    ]
    schema_ok = payload.get("schemaVersion") in {None, INPUT_SCHEMA_VERSION}
    ok = not missing and not invalid and schema_ok
    return {
        "status": _status(ok),
        "requiredFieldCount": len(REQUIRED_FIELDS),
        "presentFieldCount": len([field for field in REQUIRED_FIELDS if field in payload]),
        "missingFields": missing,
        "invalidFields": invalid,
        "schemaVersionAccepted": schema_ok,
    }


def _operator_assertions_check(payload: dict[str, Any]) -> dict[str, Any]:
    assertions = payload.get("operatorAssertions")
    if assertions is None:
        assertions = {}
    if not isinstance(assertions, dict):
        return {
            "status": "fail",
            "requiredFalseFlags": list(REQUIRED_FALSE_ASSERTIONS),
            "unsafeTrueFlags": ["operatorAssertions"],
        }
    unsafe_true = [flag for flag in REQUIRED_FALSE_ASSERTIONS if assertions.get(flag) is True]
    return {
        "status": _status(not unsafe_true),
        "requiredFalseFlags": list(REQUIRED_FALSE_ASSERTIONS),
        "unsafeTrueFlags": unsafe_true,
    }


def _safety_check(payload: dict[str, Any], load_error: str | None = None) -> dict[str, Any]:
    findings = _find_unsafe_values(payload)
    if load_error:
        findings.insert(0, _finding("artifact", load_error))
    bounded_findings = findings[:MAX_FINDINGS]
    return {
        "status": _status(not findings),
        "unsafeFindingCount": len(findings),
        "findings": bounded_findings,
        "findingValuesIncluded": False,
        "maxFindingsEmitted": MAX_FINDINGS,
    }


def _build_report(payload: dict[str, Any], *, load_error: str | None = None) -> dict[str, Any]:
    required = _required_fields_check(payload)
    safety = _safety_check(payload, load_error=load_error)
    assertions = _operator_assertions_check(payload)
    field_ok = required["status"] == "pass"
    safety_ok = safety["status"] == "pass" and assertions["status"] == "pass"
    restore_ready = field_ok and safety_ok and all(field not in required["missingFields"] for field in RESTORE_FIELDS)
    rollback_ready = field_ok and safety_ok and all(field not in required["missingFields"] for field in ROLLBACK_FIELDS)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "inputSchemaVersion": payload.get("schemaVersion") or "unknown",
        "mode": "offline_operator_review",
        "drillStatus": "REVIEW-READY" if restore_ready and rollback_ready else "NO-GO",
        "restoreReady": restore_ready,
        "rollbackReady": rollback_ready,
        "destructiveOperationsExecuted": False,
        "networkCallsExecuted": False,
        "manualReviewRequired": True,
        "releaseApproved": False,
        "runtimeBehaviorChanged": False,
        "checks": {
            "requiredFields": required,
            "safety": safety,
            "operatorAssertions": assertions,
        },
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_revision(repository_root: Path, revision: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", revision],
        cwd=repository_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise LocalDrillError("candidate_identity_unavailable")
    value = result.stdout.strip()
    if not _CANDIDATE_SHA_PATTERN.fullmatch(value):
        raise LocalDrillError("candidate_identity_invalid")
    return value


def _sqlite_backup(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise LocalDrillError("backup_source_missing")
    if destination.exists() or destination.is_symlink():
        raise LocalDrillError("backup_target_not_clean")
    if source.resolve() == destination.resolve():
        raise LocalDrillError("backup_source_equals_target")

    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def _sqlite_schema_sha256(path: Path) -> str:
    if not path.is_file():
        raise LocalDrillError("schema_target_missing")
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY type, name, tbl_name"
        ).fetchall()
    return _sha256_json(
        {
            "engine": "sqlite",
            "userVersion": user_version,
            "objects": [[str(value or "") for value in row] for row in rows],
        }
    )


def _restore_environment(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@contextmanager
def _isolated_runtime_database(database_path: Path, environment_path: Path) -> Iterator[Any]:
    """Bind the app's normal Config and DatabaseManager owners to one disposable database."""
    from src.config import Config
    from src.storage import DatabaseManager

    previous = {
        key: os.environ.get(key)
        for key in (
            "ADMIN_AUTH_ENABLED",
            "CRYPTO_REALTIME_ENABLED",
            "DATABASE_PATH",
            "ENV_FILE",
            "WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS",
        )
    }
    environment_path.write_text(
        "\n".join(
            (
                "ADMIN_AUTH_ENABLED=false",
                "CRYPTO_REALTIME_ENABLED=false",
                f"DATABASE_PATH={database_path}",
                "WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS=true",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    os.environ["ENV_FILE"] = str(environment_path)
    os.environ["DATABASE_PATH"] = str(database_path)
    os.environ["ADMIN_AUTH_ENABLED"] = "false"
    os.environ["CRYPTO_REALTIME_ENABLED"] = "false"
    os.environ["WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS"] = "true"
    Config.reset_instance()
    DatabaseManager.reset_instance()
    try:
        yield DatabaseManager.get_instance()
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        _restore_environment(previous)


def _seed_isolated_persistent_state(database: Any) -> dict[str, int]:
    from src.services.portfolio_service import PortfolioService
    from src.services.watchlist_service import WatchlistService

    expires_at = datetime.now() + timedelta(hours=1)
    users = (
        ("restore-owner-alpha", "restore-alpha", "user"),
        ("restore-owner-beta", "restore-beta", "user"),
        ("restore-admin", "restore-admin", "admin"),
    )
    for user_id, username, role in users:
        database.create_or_update_app_user(
            user_id=user_id,
            username=username,
            display_name=username,
            role=role,
            password_hash=None,
            is_active=True,
        )
        database.create_app_user_session(
            session_id=f"restore-session-{user_id}",
            user_id=user_id,
            expires_at=expires_at,
        )

    alpha_account = PortfolioService(owner_id="restore-owner-alpha").create_account(
        name="Restore Alpha Account",
        broker=None,
        market="us",
        base_currency="USD",
    )
    beta_account = PortfolioService(owner_id="restore-owner-beta").create_account(
        name="Restore Beta Account",
        broker=None,
        market="cn",
        base_currency="CNY",
    )

    watchlist = WatchlistService(db_manager=database)
    alpha_item = watchlist.add_item(
        owner_id="restore-owner-alpha",
        symbol="AAPL",
        market="us",
        name="Restore Alpha Watchlist",
    )
    beta_item = watchlist.add_item(
        owner_id="restore-owner-beta",
        symbol="600519",
        market="cn",
        name="Restore Beta Watchlist",
    )
    return {
        "alphaAccountId": int(alpha_account["id"]),
        "betaAccountId": int(beta_account["id"]),
        "alphaWatchlistItemId": int(alpha_item["id"]),
        "betaWatchlistItemId": int(beta_item["id"]),
    }


def _verify_restored_state(database: Any, identifiers: dict[str, int]) -> None:
    from src.services.portfolio_service import PortfolioService
    from src.services.watchlist_service import WatchlistService

    alpha_user = database.get_app_user("restore-owner-alpha")
    beta_user = database.get_app_user("restore-owner-beta")
    admin_user = database.get_app_user("restore-admin")
    if (
        alpha_user is None
        or beta_user is None
        or admin_user is None
        or str(alpha_user.role) != "user"
        or str(beta_user.role) != "user"
        or str(admin_user.role) != "admin"
    ):
        raise LocalDrillError("restored_roles_invalid")

    alpha_session = database.get_app_user_session("restore-session-restore-owner-alpha")
    beta_session = database.get_app_user_session("restore-session-restore-owner-beta")
    if (
        alpha_session is None
        or beta_session is None
        or str(alpha_session.user_id) != "restore-owner-alpha"
        or str(beta_session.user_id) != "restore-owner-beta"
    ):
        raise LocalDrillError("restored_sessions_invalid")

    alpha_portfolio = PortfolioService(owner_id="restore-owner-alpha")
    beta_portfolio = PortfolioService(owner_id="restore-owner-beta")
    if alpha_portfolio.get_account(identifiers["alphaAccountId"]) is None:
        raise LocalDrillError("restored_alpha_portfolio_missing")
    if beta_portfolio.get_account(identifiers["betaAccountId"]) is None:
        raise LocalDrillError("restored_beta_portfolio_missing")
    if beta_portfolio.get_account(identifiers["alphaAccountId"]) is not None:
        raise LocalDrillError("portfolio_owner_isolation_failed")

    watchlist = WatchlistService(db_manager=database)
    if (
        watchlist.get_item_by_id(
            owner_id="restore-owner-alpha",
            item_id=identifiers["alphaWatchlistItemId"],
        )
        is None
    ):
        raise LocalDrillError("restored_alpha_watchlist_missing")
    if (
        watchlist.get_item_by_id(
            owner_id="restore-owner-beta",
            item_id=identifiers["betaWatchlistItemId"],
        )
        is None
    ):
        raise LocalDrillError("restored_beta_watchlist_missing")
    if (
        watchlist.get_item_by_id(
            owner_id="restore-owner-beta",
            item_id=identifiers["alphaWatchlistItemId"],
        )
        is not None
    ):
        raise LocalDrillError("watchlist_owner_isolation_failed")


def _start_restored_application(database_path: Path, environment_path: Path, identifiers: dict[str, int]) -> None:
    from fastapi.testclient import TestClient

    with _isolated_runtime_database(database_path, environment_path) as database:
        _verify_restored_state(database, identifiers)
        from api.app import create_app

        app = create_app(static_dir=environment_path.parent / "missing-static")
        with TestClient(app) as client:
            response = client.get("/api/health/ready")
        if response.status_code != 200 or response.json().get("ready") is not True:
            raise LocalDrillError("restored_application_not_ready")


def _seed_rollback_drift(database: Any) -> None:
    database.create_or_update_app_user(
        user_id="restore-rollback-drift",
        username="restore-rollback-drift",
        display_name="restore-rollback-drift",
        role="user",
        password_hash=None,
        is_active=True,
    )


def _managed_environment_fingerprint(run_root: Path) -> str:
    evidence_path = run_root / "services" / "environment-evidence.json"
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocalDrillError("managed_environment_evidence_unavailable") from exc
    fingerprint = str(payload.get("environmentFingerprint") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise LocalDrillError("managed_environment_fingerprint_invalid")
    return fingerprint


def _local_check(check_id: str, *, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "evidence": evidence or {}}


def _local_failure_report(failure_code: str) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "localDrillSchemaVersion": LOCAL_DRILL_SCHEMA_VERSION,
        "mode": "local_isolated_execution",
        "qualificationScope": LOCAL_DRILL_PROFILE,
        "drillStatus": "NO-GO",
        "restoreReady": False,
        "rollbackReady": False,
        "releaseApproved": False,
        "manualReviewRequired": True,
        "productionStorageTouched": False,
        "networkCallsExecuted": False,
        "productionDestructiveOperationsExecuted": False,
        "isolatedDatabaseActionsExecuted": False,
        "isolatedRollbackTargetReplacementExecuted": False,
        "failureCode": failure_code,
    }


def _run_local_isolated_drill(*, expected_sha: str) -> dict[str, Any]:
    if not _CANDIDATE_SHA_PATTERN.fullmatch(expected_sha):
        raise LocalDrillError("expected_candidate_sha_invalid")

    actual_sha = _git_revision(REPOSITORY_ROOT, "HEAD")
    if actual_sha != expected_sha:
        raise LocalDrillError("candidate_identity_mismatch")
    tree_sha = _git_revision(REPOSITORY_ROOT, "HEAD^{tree}")
    run_root, temp_root = validate_run_identity(dict(os.environ))
    environment_fingerprint = _managed_environment_fingerprint(run_root)
    started_at = time.monotonic()

    with tempfile.TemporaryDirectory(prefix="t689-release-restore-", dir=temp_root) as work_dir_value:
        work_dir = Path(work_dir_value)
        source_path = work_dir / "source.sqlite"
        backup_path = work_dir / "backup.sqlite"
        backup_metadata_path = work_dir / "backup-metadata.json"
        restore_path = work_dir / "restored.sqlite"
        rollback_target_path = work_dir / "rollback-target.sqlite"
        source_environment_path = work_dir / "source.env"
        restored_environment_path = work_dir / "restored.env"
        rollback_environment_path = work_dir / "rollback.env"

        with _isolated_runtime_database(source_path, source_environment_path) as source_database:
            identifiers = _seed_isolated_persistent_state(source_database)
        source_schema_sha256 = _sqlite_schema_sha256(source_path)
        source_sha256_before_backup = _sha256_file(source_path)
        database_target_sha256 = hashlib.sha256(str(restore_path.resolve()).encode("utf-8")).hexdigest()
        configuration_sha256 = _sha256_json(
            {
                "candidateSha": actual_sha,
                "candidateTree": tree_sha,
                "databaseEngine": "sqlite",
                "databaseTargetSha256": database_target_sha256,
                "environmentFingerprint": environment_fingerprint,
                "profile": LOCAL_DRILL_PROFILE,
            }
        )

        _sqlite_backup(source_path, backup_path)
        if _sha256_file(source_path) != source_sha256_before_backup:
            raise LocalDrillError("backup_mutated_source")
        backup_sha256 = _sha256_file(backup_path)
        backup_metadata = {
            "backupFormat": "sqlite-backup-api",
            "backupSha256": backup_sha256,
            "candidateSha": actual_sha,
            "candidateTree": tree_sha,
            "configurationSha256": configuration_sha256,
            "schemaSha256": source_schema_sha256,
        }
        backup_metadata_serialized = json.dumps(
            backup_metadata,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        backup_metadata_path.write_text(backup_metadata_serialized, encoding="utf-8")
        backup_metadata_sha256 = _sha256_file(backup_metadata_path)
        if backup_metadata_sha256 != _sha256_json(backup_metadata):
            raise LocalDrillError("backup_metadata_checksum_mismatch")
        if json.loads(backup_metadata_path.read_text(encoding="utf-8")) != backup_metadata:
            raise LocalDrillError("backup_metadata_readback_mismatch")

        _sqlite_backup(backup_path, restore_path)
        restore_sha256 = _sha256_file(restore_path)
        restored_schema_sha256 = _sqlite_schema_sha256(restore_path)
        if restored_schema_sha256 != source_schema_sha256:
            raise LocalDrillError("restore_schema_identity_mismatch")
        _start_restored_application(restore_path, restored_environment_path, identifiers)

        _sqlite_backup(restore_path, rollback_target_path)
        with _isolated_runtime_database(rollback_target_path, rollback_environment_path) as rollback_database:
            _seed_rollback_drift(rollback_database)
            if rollback_database.get_app_user("restore-rollback-drift") is None:
                raise LocalDrillError("rollback_drift_not_created")
        rollback_target_path.unlink()
        _sqlite_backup(backup_path, rollback_target_path)
        _start_restored_application(rollback_target_path, rollback_environment_path, identifiers)
        with _isolated_runtime_database(rollback_target_path, rollback_environment_path) as rollback_database:
            if rollback_database.get_app_user("restore-rollback-drift") is not None:
                raise LocalDrillError("rollback_drift_persisted")

        observed_rto_seconds = round(time.monotonic() - started_at, 6)
        checks = [
            _local_check(
                "managed_test_isolation",
                evidence={"environmentFingerprint": environment_fingerprint, "profile": LOCAL_DRILL_PROFILE},
            ),
            _local_check("candidate_identity", evidence={"sha": actual_sha, "tree": tree_sha}),
            _local_check(
                "backup_metadata_and_checksum",
                evidence={"backupMetadataSha256": backup_metadata_sha256, "backupSha256": backup_sha256},
            ),
            _local_check("restore_to_separate_clean_target", evidence={"restoreSha256": restore_sha256}),
            _local_check("restored_application_startup"),
            _local_check("user_session_role_and_owner_isolation"),
            _local_check("schema_identity", evidence={"schemaSha256": restored_schema_sha256}),
            _local_check("controlled_rollback"),
        ]
        return {
            "schemaVersion": SCHEMA_VERSION,
            "localDrillSchemaVersion": LOCAL_DRILL_SCHEMA_VERSION,
            "mode": "local_isolated_execution",
            "qualificationScope": LOCAL_DRILL_PROFILE,
            "drillStatus": "QUALIFIED_LOCAL_ISOLATED",
            "restoreReady": True,
            "rollbackReady": True,
            "releaseApproved": False,
            "manualReviewRequired": True,
            "productionStorageTouched": False,
            "networkCallsExecuted": False,
            "productionDestructiveOperationsExecuted": False,
            "isolatedDatabaseActionsExecuted": True,
            "isolatedRollbackTargetReplacementExecuted": True,
            "candidate": {"sha": actual_sha, "tree": tree_sha},
            "identities": {
                "configurationSha256": configuration_sha256,
                "backupMetadataSha256": backup_metadata_sha256,
                "backupSha256": backup_sha256,
                "restoreSha256": restore_sha256,
                "schemaSha256": restored_schema_sha256,
            },
            "observedRpoSeconds": 0,
            "observedRtoSeconds": observed_rto_seconds,
            "rollbackDecision": "executed_to_verified_backup",
            "checks": checks,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or execute a bounded release restore/rollback drill.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="Run offline advisory validation only.")
    mode.add_argument(
        "--local-isolated",
        action="store_true",
        help="Execute the managed-test-only SQLite backup, restore, startup, and rollback drill.",
    )
    parser.add_argument("--artifact", help="Path to sanitized operator-supplied drill JSON.")
    parser.add_argument("--expected-sha", help="Exact Git candidate SHA required by --local-isolated.")
    parser.add_argument("--allow-no-go", action="store_true", help="Return exit 0 even when the drill remains NO-GO.")
    args = parser.parse_args(argv)

    if args.local_isolated:
        if args.artifact:
            parser.error("--artifact is only valid with --offline")
        if args.allow_no_go:
            parser.error("--allow-no-go is only valid with --offline")
        if not args.expected_sha:
            parser.error("--expected-sha is required with --local-isolated")
        try:
            report = _run_local_isolated_drill(expected_sha=args.expected_sha)
        except LocalDrillError as exc:
            report = _local_failure_report(str(exc))
            exit_code = 1
        else:
            exit_code = 0
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return exit_code

    if args.expected_sha:
        parser.error("--expected-sha is only valid with --local-isolated")

    load_error: str | None = None
    payload = _empty_artifact()
    artifact_supplied = bool(args.artifact)
    if args.artifact:
        try:
            payload = _load_artifact(Path(args.artifact))
        except OSError:
            load_error = "artifact_not_readable"
            payload = _empty_artifact()
        except ValueError as exc:
            load_error = str(exc)
            payload = _empty_artifact()

    report = _build_report(payload, load_error=load_error)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if report["drillStatus"] != "REVIEW-READY" and artifact_supplied and not args.allow_no_go:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
