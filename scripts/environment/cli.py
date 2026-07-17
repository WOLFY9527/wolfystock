from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from .errors import EnvironmentFailure
from .manager import EnvironmentManager, managed_python_path, require_managed_python
from .python_lock import check_python_lock, update_python_lock
from .qualification import compare_findings, normalize_findings
from .runtime import cleanup_run, create_run_context, project_test_environment, write_run_json


FINDINGS_SCHEMA = "wolfystock_qualification_findings_v1"


def _emit(payload: dict[str, Any], *, error: bool = False) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=sys.stderr if error else sys.stdout,
    )


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wolfy", description="Hermetic WolfyStock environment authority")
    subparsers = parser.add_subparsers(dest="command", required=True)
    bootstrap = subparsers.add_parser("bootstrap", help="ensure verified dependency snapshots")
    bootstrap.add_argument("--ensure", action="store_true", required=True)
    bootstrap.add_argument("--offline", action="store_true")
    environment = subparsers.add_parser("env", help="inspect the managed environment")
    environment_subparsers = environment.add_subparsers(dest="env_command", required=True)
    environment_subparsers.add_parser("verify", help="verify snapshots and worktree links")
    execute = subparsers.add_parser("exec", help="run a command with a hermetic environment projection")
    execute.add_argument("--profile", required=True, choices=("test",))
    execute.add_argument("child_command", nargs=argparse.REMAINDER)
    qualify = subparsers.add_parser("qualify-env", help="emit environment evidence or compare baseline findings")
    qualify.add_argument("--findings", type=Path)
    qualify.add_argument("--baseline-commit")
    qualify.add_argument("--baseline-evidence", type=Path)
    qualify.add_argument("--output", type=Path)
    development = subparsers.add_parser("dev", help="start isolated frontend and backend services")
    development.add_argument("--json", action="store_true", required=True)
    development.add_argument("--stop", metavar="RUN_ID")
    lock = subparsers.add_parser("lock", help="inspect or explicitly update reviewed dependency locks")
    lock_families = lock.add_subparsers(dest="lock_family", required=True)
    python_lock = lock_families.add_parser("python", help="manage the authoritative Python lock family")
    lock_actions = python_lock.add_mutually_exclusive_group(required=True)
    lock_actions.add_argument("--check", dest="lock_action", action="store_const", const="check")
    lock_actions.add_argument("--update", dest="lock_action", action="store_const", const="update")
    return parser


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentFailure("evidence_unreadable", "structured evidence is unreadable") from exc


def _validate_baseline(args: argparse.Namespace) -> dict[str, Any] | None:
    values = (args.baseline_commit, args.baseline_evidence)
    if not any(values):
        return None
    if not all(values) or args.findings is None:
        raise EnvironmentFailure(
            "baseline_identity_incomplete",
            "baseline comparison requires --baseline-commit, --baseline-evidence and --findings",
        )
    if re.fullmatch(r"[0-9a-f]{40}", str(args.baseline_commit)) is None:
        raise EnvironmentFailure("baseline_commit_invalid", "baseline commit must be a full lowercase SHA")
    baseline = _load_json(args.baseline_evidence)
    if not isinstance(baseline, dict) or baseline.get("schemaVersion") != FINDINGS_SCHEMA:
        raise EnvironmentFailure("baseline_evidence_invalid", "baseline evidence schema is invalid")
    if baseline.get("commit") != args.baseline_commit:
        raise EnvironmentFailure("baseline_commit_mismatch", "baseline evidence commit does not match")
    if baseline.get("checkoutClean") is not True:
        raise EnvironmentFailure("baseline_checkout_not_clean", "baseline checkout must be explicitly clean")
    return baseline


def _managed_reexec(root: Path, argv: Sequence[str]) -> None:
    expected = managed_python_path(root)
    if Path(sys.executable).resolve(strict=False) == expected.resolve(strict=True):
        return
    environment = os.environ.copy()
    os.execve(
        str(expected),
        [str(expected), "-E", "-s", "-B", str(root / "scripts" / "wolfy.py"), *argv],
        environment,
    )


def _git_identity(root: Path) -> tuple[str, bool]:
    sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=False
    )
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], text=True, capture_output=True, check=False
    )
    if sha.returncode != 0 or status.returncode != 0:
        raise EnvironmentFailure("git_identity_unavailable", "Git checkout identity is unavailable")
    return sha.stdout.strip(), not bool(status.stdout.strip())


def _findings(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    values = payload.get("findings") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
        raise EnvironmentFailure("findings_invalid", "findings must be a JSON list of objects")
    return values


def _write_or_emit(payload: dict[str, Any], output: Path | None) -> None:
    if output is None:
        _emit(payload)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _emit({"status": payload.get("status", "ok"), "output": output.name})


def _execute(root: Path, manager: EnvironmentManager, args: argparse.Namespace) -> int:
    command = list(args.child_command)
    if command[:1] == ["--"]:
        command.pop(0)
    if not command:
        raise EnvironmentFailure("child_command_missing", "exec requires '-- <command...>'")
    run_id = "run-" + secrets.token_hex(8)
    context = create_run_context(manager.cache_root, run_id=run_id)
    success = False
    try:
        verified = manager.verify(run_id=run_id)
        write_run_json(context, "environment-evidence.json", verified.evidence)
        node = shutil.which("node")
        if not node:
            raise EnvironmentFailure("managed_node_missing", "Node executable is unavailable")
        environment = project_test_environment(
            dict(os.environ),
            context,
            managed_python=managed_python_path(root),
            node_bin=Path(node).parent,
            command=command,
        )
        environment["WOLFYSTOCK_ENV_FINGERPRINT"] = verified.combined_fingerprint
        environment["WOLFYSTOCK_ENV_CACHE"] = str(manager.cache_root)
        result = subprocess.run(command, cwd=root, env=environment, check=False)
        success = result.returncode == 0
        return result.returncode
    finally:
        cleanup_run(context, success=success)


def _qualify(root: Path, manager: EnvironmentManager, args: argparse.Namespace, baseline: dict[str, Any] | None) -> int:
    run_id = "qualify-" + secrets.token_hex(8)
    context = create_run_context(manager.cache_root, run_id=run_id)
    success = False
    try:
        verified = manager.verify(run_id=run_id)
        write_run_json(context, "environment-evidence.json", verified.evidence)
        if args.findings is None:
            payload = {"status": "PASS", "environmentEvidence": verified.evidence}
            _write_or_emit(payload, args.output)
            success = True
            return 0
        current_findings = normalize_findings(_findings(args.findings))
        if baseline is None:
            commit, clean = _git_identity(root)
            payload = {
                "schemaVersion": FINDINGS_SCHEMA,
                "commit": commit,
                "checkoutClean": clean,
                "environmentFingerprint": verified.combined_fingerprint,
                "findings": current_findings,
            }
            write_run_json(context, "qualification.json", payload)
            _write_or_emit(payload, args.output)
            success = True
            return 0
        if baseline.get("environmentFingerprint") != verified.combined_fingerprint:
            raise EnvironmentFailure("baseline_environment_mismatch", "baseline environment fingerprint does not match")
        result = compare_findings(
            baseline=baseline.get("findings", []),
            current=current_findings,
            baseline_commit=args.baseline_commit,
            evidence_fingerprint=verified.combined_fingerprint,
        )
        write_run_json(context, "qualification.json", result)
        _write_or_emit(result, args.output)
        success = result["status"] == "PASS"
        return 0 if success else 1
    finally:
        cleanup_run(context, success=success)


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(argv if argv is not None else sys.argv[1:])
    parser = _parser()
    try:
        args = parser.parse_args(raw)
        root = _root()
        if args.command == "lock":
            payload = (
                check_python_lock(root)
                if args.lock_action == "check"
                else update_python_lock(root)
            )
            _emit(payload)
            return 0
        baseline = _validate_baseline(args) if args.command == "qualify-env" else None
        if args.command != "bootstrap":
            _managed_reexec(root, raw)
            require_managed_python(root)
        manager = EnvironmentManager(root)
        if args.command == "bootstrap":
            verified = manager.ensure(offline=args.offline, run_id="bootstrap-" + secrets.token_hex(8))
            _emit({"status": "ok", "environmentEvidence": verified.evidence})
            return 0
        if args.command == "env":
            verified = manager.verify(run_id="verify-" + secrets.token_hex(8))
            _emit({"status": "ok", "environmentEvidence": verified.evidence})
            return 0
        if args.command == "exec":
            return _execute(root, manager, args)
        if args.command == "qualify-env":
            return _qualify(root, manager, args, baseline)
        from .services import run_development_services, stop_development_services

        payload = (
            stop_development_services(manager.cache_root, args.stop)
            if args.stop
            else run_development_services(root, manager)
        )
        _emit(payload)
        return 0 if payload.get("status") in {"ready", "stopped", "already_stopped"} else 1
    except EnvironmentFailure as exc:
        _emit({"status": "error", "reasonCode": exc.code, "message": exc.detail}, error=True)
        return 1
    except ValueError as exc:
        _emit({"status": "error", "reasonCode": "environment_input_invalid", "message": str(exc)}, error=True)
        return 1
