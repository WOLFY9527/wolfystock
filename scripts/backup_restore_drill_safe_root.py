#!/usr/bin/env python3
"""Validate the restore drill target against the current Wolfy managed run."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import NoReturn


ENVIRONMENT_EVIDENCE_SCHEMA = "wolfystock_environment_evidence_v1"
ENVIRONMENT_POLICY_VERSION = "wolfystock_test_environment_policy_v1"
RUN_ID_PATTERN = re.compile(r"^run-[0-9a-f]{16}$")
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def fail() -> NoReturn:
    print("[FAIL] Unsafe restore target refused", file=sys.stderr)
    print(
        "Target must be a non-existing path inside the exact current Wolfy managed test run temporary root.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def resolve_exact_existing_path(raw_path: str, *, directory: bool) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        fail()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        fail()
    if path != resolved:
        fail()
    if directory and not resolved.is_dir():
        fail()
    if not directory and not resolved.is_file():
        fail()
    return resolved


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_run_identity(environment: dict[str, str]) -> tuple[Path, Path]:
    run_id = environment.get("WOLFYSTOCK_TEST_RUN_ID", "")
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        fail()
    if environment.get("WOLFYSTOCK_ENV_POLICY_VERSION") != ENVIRONMENT_POLICY_VERSION:
        fail()
    if environment.get("WOLFYSTOCK_TEST_OFFLINE") != "1":
        fail()

    cache_root = resolve_exact_existing_path(
        environment.get("WOLFYSTOCK_ENV_CACHE", ""),
        directory=True,
    )
    run_root = resolve_exact_existing_path(
        str(cache_root / "runs" / "active" / run_id),
        directory=True,
    )
    temp_root = resolve_exact_existing_path(str(run_root / "tmp"), directory=True)
    home_root = resolve_exact_existing_path(str(run_root / "home"), directory=True)
    service_root = resolve_exact_existing_path(str(run_root / "services"), directory=True)

    for name in ("TMPDIR", "TEMP", "TMP"):
        if resolve_exact_existing_path(environment.get(name, ""), directory=True) != temp_root:
            fail()
    if resolve_exact_existing_path(environment.get("HOME", ""), directory=True) != home_root:
        fail()
    if (
        resolve_exact_existing_path(
            environment.get("WOLFYSTOCK_SERVICE_STATE_DIR", ""),
            directory=True,
        )
        != service_root
    ):
        fail()

    evidence_path = resolve_exact_existing_path(
        str(service_root / "environment-evidence.json"),
        directory=False,
    )
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        fail()
    if not isinstance(evidence, dict):
        fail()
    if evidence.get("schemaVersion") != ENVIRONMENT_EVIDENCE_SCHEMA:
        fail()
    if evidence.get("environmentPolicyVersion") != ENVIRONMENT_POLICY_VERSION:
        fail()
    evidence_fingerprint = evidence.get("environmentFingerprint")
    if not isinstance(evidence_fingerprint, str):
        fail()
    if FINGERPRINT_PATTERN.fullmatch(evidence_fingerprint) is None:
        fail()
    operational = evidence.get("operational")
    if not isinstance(operational, dict) or operational.get("runId") != run_id:
        fail()
    return run_root, temp_root


def validate_restore_target(target_value: str, repository_value: str) -> None:
    _, temp_root = validate_run_identity(dict(os.environ))
    repository_root = resolve_exact_existing_path(repository_value, directory=True)
    target_path = Path(target_value)
    if not target_path.is_absolute():
        fail()
    try:
        resolved_target = target_path.resolve(strict=False)
    except (OSError, RuntimeError):
        fail()
    if resolved_target == temp_root or not is_within(resolved_target, temp_root):
        fail()
    if is_within(resolved_target, repository_root):
        fail()


def main() -> int:
    if len(sys.argv) != 3:
        fail()
    validate_restore_target(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
