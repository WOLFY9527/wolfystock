#!/usr/bin/env python3
"""Plan and reconcile explicit resumable backend validation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESUME_SCHEMA = "wolfystock.validation-resume.v1"
RESUME_SOURCE_KIND = "backend-shard-resume-source"
RESUME_PLAN_KIND = "backend-shard-resume-plan"


class ResumeError(ValueError):
    """Raised when explicit resume evidence cannot be trusted."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResumeError(f"{label} is missing or malformed: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ResumeError(f"{label} must be an object")
    return payload


def _relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResumeError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ResumeError(f"{label} must be a contained relative path")
    return path.as_posix()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ResumeError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _plan_hash(plan: dict[str, Any], label: str) -> str:
    value = plan.get("planHash")
    _digest(value, f"{label}.planHash")
    if value != canonical_hash({key: item for key, item in plan.items() if key != "planHash"}):
        raise ResumeError(f"{label} hash mismatch")
    return value


def _stage_ids(shard: dict[str, Any], stage_plan: dict[str, Any]) -> list[str]:
    shard_ids = set(shard["nodeIds"])
    return [
        stage["id"]
        for stage in stage_plan["stages"]
        if stage["required"] and shard_ids.intersection(stage["nodeIds"])
    ]


def build_resume_context(
    risk_plan: dict[str, Any],
    stage_plan: dict[str, Any],
    shard_plan: dict[str, Any],
) -> dict[str, Any]:
    """Bind T631, T637, and T633 plans without creating another selector."""

    from scripts import validation_changed_files as planner
    from tests import conftest as shard_authority

    planner._validate_plan(risk_plan)
    planner.validate_backend_stage_plan(stage_plan)
    shard_authority._validate_backend_shard_plan(shard_plan)
    risk_hash = _plan_hash(risk_plan, "risk plan")
    stage_hash = _plan_hash(stage_plan, "stage plan")
    shard_hash = _plan_hash(shard_plan, "shard plan")
    if stage_plan["riskPlanHash"] != risk_hash or shard_plan["riskPlanHash"] != risk_hash:
        raise ResumeError("risk plan identity does not match stage or shard plan")
    if shard_plan.get("validationStages", {}).get("planHash") != stage_hash:
        raise ResumeError("stage plan identity does not match shard plan")
    if shard_plan.get("candidate") != risk_plan["identity"]["candidate"]:
        raise ResumeError("candidate identity does not match shard plan")
    if shard_plan.get("topology") != stage_plan["topology"]:
        raise ResumeError("topology identity does not match shard plan")

    shards = []
    for shard in sorted(shard_plan["shards"], key=lambda item: item["id"]):
        stages = _stage_ids(shard, stage_plan)
        if not stages:
            raise ResumeError(f"shard has no selected stage ownership: {shard['id']}")
        shards.append({"id": shard["id"], "selection": shard["selection"], "stageIds": stages})
    return {
        "tier": stage_plan["tier"],
        "riskPlanHash": risk_hash,
        "stagePlanHash": stage_hash,
        "shardPlanHash": shard_hash,
        "candidate": risk_plan["identity"]["candidate"],
        "topology": stage_plan["topology"],
        "shards": shards,
        "_shardPlan": shard_plan,
    }


def _public_context(context: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in context.items() if not key.startswith("_")}


def build_resume_source(context: dict[str, Any]) -> dict[str, Any]:
    """Create the explicit, relative-path-only input for a later resume."""

    public = _public_context(context)
    shards = [
        {
            **shard,
            "directory": f"sharded/{shard['id']}",
        }
        for shard in public["shards"]
    ]
    source = {
        "schemaVersion": RESUME_SCHEMA,
        "kind": RESUME_SOURCE_KIND,
        "state": "prepared",
        **{key: value for key, value in public.items() if key != "shards"},
        "shards": shards,
    }
    source["sourceHash"] = canonical_hash(source)
    return source


def _identity_mismatches(current: dict[str, Any], source: dict[str, Any]) -> list[str]:
    fields = ("tier", "riskPlanHash", "stagePlanHash", "shardPlanHash", "candidate", "topology")
    return [field for field in fields if source.get(field) != current.get(field)]


def _validated_source(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("schemaVersion") != RESUME_SCHEMA or source.get("kind") != RESUME_SOURCE_KIND:
        raise ResumeError("resume evidence schema or kind is invalid")
    if source.get("state") != "prepared":
        raise ResumeError("resume evidence state is invalid")
    if source.get("sourceHash") != canonical_hash({key: value for key, value in source.items() if key != "sourceHash"}):
        raise ResumeError("resume evidence hash mismatch")
    for field in ("riskPlanHash", "stagePlanHash", "shardPlanHash"):
        _digest(source.get(field), field)
    shards = source.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ResumeError("resume evidence shards are missing")
    ids = []
    for shard in shards:
        if not isinstance(shard, dict) or not isinstance(shard.get("id"), str):
            raise ResumeError("resume evidence shard is malformed")
        ids.append(shard["id"])
        _relative_path(shard.get("directory"), f"resume evidence shard directory: {shard['id']}")
        if not isinstance(shard.get("stageIds"), list) or not shard["stageIds"]:
            raise ResumeError("resume evidence shard stage ownership is malformed")
    if len(ids) != len(set(ids)):
        raise ResumeError("resume evidence contains duplicate shard records")
    return source


def _validated_resume_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schemaVersion") != RESUME_SCHEMA or plan.get("kind") != RESUME_PLAN_KIND:
        raise ResumeError("resume plan schema or kind is invalid")
    if plan.get("planHash") != canonical_hash({key: value for key, value in plan.items() if key != "planHash"}):
        raise ResumeError("resume plan hash mismatch")
    reusable = plan.get("reusableShards")
    remaining = plan.get("remainingShards")
    accepted = plan.get("acceptedPriorResultIdentities")
    if not all(isinstance(value, list) for value in (reusable, remaining, accepted)):
        raise ResumeError("resume plan shard lists are malformed")
    if reusable != sorted(set(reusable)) or remaining != sorted(set(remaining)) or set(reusable) & set(remaining):
        raise ResumeError("resume plan shard scheduling is malformed")
    accepted_by_id = {item.get("shardId"): item for item in accepted if isinstance(item, dict)}
    if set(accepted_by_id) != set(reusable) or len(accepted_by_id) != len(accepted):
        raise ResumeError("resume plan accepted evidence does not cover reusable shards")
    for shard_id, identity in accepted_by_id.items():
        _digest(identity.get("attemptSha256"), f"resume plan attempt hash: {shard_id}")
    return plan


def build_resume_plan(current: dict[str, Any], prior: dict[str, Any] | None) -> dict[str, Any]:
    """Return a deterministic fail-closed shard reuse decision without executing work."""

    all_shards = sorted(shard["id"] for shard in current["shards"])
    rejection_reasons: list[str] = []
    candidate_shards: list[str] = []
    if prior is not None:
        try:
            source = _validated_source(prior)
        except ResumeError as exc:
            rejection_reasons.append(str(exc))
        else:
            mismatches = _identity_mismatches(current, source)
            if mismatches:
                rejection_reasons.extend(f"identity mismatch: {field}" for field in mismatches)
            elif [shard["id"] for shard in sorted(source["shards"], key=lambda item: item["id"])] != all_shards:
                rejection_reasons.append("resume evidence shard inventory mismatch")
            else:
                source_by_id = {shard["id"]: shard for shard in source["shards"]}
                differing_shards = [
                    shard["id"]
                    for shard in current["shards"]
                    if {
                        "selection": source_by_id[shard["id"]].get("selection"),
                        "stageIds": source_by_id[shard["id"]].get("stageIds"),
                    }
                    != {"selection": shard.get("selection"), "stageIds": shard.get("stageIds")}
                ]
                if differing_shards:
                    rejection_reasons.extend(
                        f"resume evidence shard identity mismatch: {shard_id}" for shard_id in differing_shards
                    )
                else:
                    candidate_shards = all_shards
    plan = {
        "schemaVersion": RESUME_SCHEMA,
        "kind": RESUME_PLAN_KIND,
        "tier": current["tier"],
        "acceptedPriorResultIdentities": [],
        "candidateShards": candidate_shards,
        "reusableShards": [],
        "remainingShards": all_shards,
        "rejectionReasons": sorted(rejection_reasons),
    }
    plan["planHash"] = canonical_hash(plan)
    return plan


def successful_terminal_result(attempt: dict[str, Any]) -> None:
    """Reject every terminal state except a completed, first-attempt success."""

    if attempt.get("state") != "completed":
        raise ResumeError("structured result is incomplete")
    if attempt.get("status") != "passed" or attempt.get("exitCode") != 0:
        raise ResumeError(f"terminal outcome is not successful: {attempt.get('status')}")
    if attempt.get("attempt") != {"index": 0, "kind": "first"}:
        raise ResumeError("structured result is not a first attempt")


def _current_result_identity(context: dict[str, Any], shard_id: str) -> dict[str, Any]:
    from scripts import domain_test_topology as topology

    shard = next(item for item in context["_shardPlan"]["shards"] if item["id"] == shard_id)
    manifest = topology.load_manifest()
    return topology.build_test_result_identity(
        manifest,
        command=context["_shardPlan"]["commandIdentity"]["selected"]["argv"],
        selected_ids=shard["nodeIds"],
    )


def plan_from_evidence(context: dict[str, Any], evidence_path: Path | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if evidence_path is None:
        return build_resume_plan(context, None), None
    source = _load_object(evidence_path, "resume evidence")
    preliminary = build_resume_plan(context, source)
    if preliminary["rejectionReasons"]:
        return preliminary, source

    from scripts import domain_test_topology as topology
    from tests import conftest as shard_authority

    evidence_root = evidence_path.parent
    accepted: list[str] = []
    accepted_identities: list[dict[str, Any]] = []
    rejections: list[str] = []
    for shard in sorted(source["shards"], key=lambda item: item["id"]):
        directory = evidence_root / _relative_path(shard["directory"], f"resume evidence shard directory: {shard['id']}")
        try:
            attempt, _ = shard_authority._load_backend_shard_attempt(
                directory,
                plan=context["_shardPlan"],
                shard=next(item for item in context["_shardPlan"]["shards"] if item["id"] == shard["id"]),
                manifest=topology.load_manifest(),
            )
            successful_terminal_result(attempt)
            if attempt["identity"] != _current_result_identity(context, shard["id"]):
                raise ResumeError("environment, dependency-lock, or command identity mismatch")
        except (OSError, ValueError, ResumeError) as exc:
            rejections.append(f"{shard['id']}: {exc}")
        else:
            accepted.append(shard["id"])
            accepted_identities.append(
                {
                    "shardId": shard["id"],
                    "stageIds": shard["stageIds"],
                    "candidate": attempt["identity"]["candidate"],
                    "environment": attempt["identity"]["environment"],
                    "dependencyLock": attempt["identity"]["dependencyLock"],
                    "command": attempt["identity"]["command"],
                    "selection": attempt["identity"]["selection"],
                    "topology": attempt["identity"]["topology"],
                    "attemptSha256": hashlib.sha256((directory / "attempt-0.json").read_bytes()).hexdigest(),
                }
            )
    plan = {
        "schemaVersion": RESUME_SCHEMA,
        "kind": RESUME_PLAN_KIND,
        "tier": context["tier"],
        "acceptedPriorResultIdentities": accepted_identities,
        "candidateShards": sorted(item["id"] for item in context["shards"]),
        "reusableShards": accepted,
        "remainingShards": [item["id"] for item in context["shards"] if item["id"] not in accepted],
        "rejectionReasons": rejections,
    }
    plan["planHash"] = canonical_hash(plan)
    return plan, source


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(payload) + b"\n")


def _context_from_paths(risk_path: Path, stage_path: Path, shard_path: Path) -> dict[str, Any]:
    return build_resume_context(
        _load_object(risk_path, "risk plan"),
        _load_object(stage_path, "stage plan"),
        _load_object(shard_path, "shard plan"),
    )


def materialize_reused_shards(plan: dict[str, Any], source: dict[str, Any], *, source_root: Path, output_dir: Path) -> None:
    _validated_resume_plan(plan)
    by_id = {item["id"]: item for item in source["shards"]}
    accepted_by_id = {item["shardId"]: item for item in plan["acceptedPriorResultIdentities"]}
    for shard_id in plan["reusableShards"]:
        source_directory = source_root / _relative_path(by_id[shard_id]["directory"], f"resume source directory: {shard_id}")
        attempt_path = source_directory / "attempt-0.json"
        if not attempt_path.is_file() or hashlib.sha256(attempt_path.read_bytes()).hexdigest() != accepted_by_id[shard_id]["attemptSha256"]:
            raise ResumeError(f"resume source artifact changed after planning: {shard_id}")
        destination = output_dir / shard_id
        if destination.exists():
            raise ResumeError(f"resume destination already exists: {shard_id}")
        shutil.copytree(source_directory, destination)


def reconcile_shards(shard_plan_path: Path, output_dir: Path) -> dict[str, Any]:
    from scripts import domain_test_topology as topology
    from tests import conftest as shard_authority

    plan = shard_authority._load_backend_shard_plan(shard_plan_path)
    workers = []
    duration_seconds = 0.0
    for shard in sorted(plan["shards"], key=lambda item: item["id"]):
        attempt, _ = shard_authority._load_backend_shard_attempt(
            output_dir / shard["id"],
            plan=plan,
            shard=shard,
            manifest=topology.load_manifest(),
        )
        workers.append(
            {
                "shardId": shard["id"],
                "returnCode": attempt["exitCode"],
                "timedOut": False,
                "source": "reused_or_executed_structured_result",
            }
        )
        duration_seconds += float(attempt["timing"]["wallSeconds"])
    worker_manifest = {
        "schemaVersion": "wolfystock.backend-shard-suite.v1",
        "planHash": plan["planHash"],
        "launchOrder": [item["shardId"] for item in workers],
        "timeoutSeconds": 0.0,
        "durationSeconds": duration_seconds,
        "workers": workers,
    }
    _write(output_dir / "workers.json", worker_manifest)
    return shard_authority.validate_backend_shard_suite(shard_plan_path, output_dir)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T638 deterministic resumable validation planner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("create-source", "plan"):
        command = subparsers.add_parser(name)
        command.add_argument("--risk-plan", required=True, type=Path)
        command.add_argument("--stage-plan", required=True, type=Path)
        command.add_argument("--shard-plan", required=True, type=Path)
        if name == "create-source":
            command.add_argument("--output", required=True, type=Path)
        else:
            command.add_argument("--resume-evidence", type=Path)
            command.add_argument("--output", required=True, type=Path)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--resume-plan", required=True, type=Path)
    materialize.add_argument("--resume-evidence", required=True, type=Path)
    materialize.add_argument("--output-dir", required=True, type=Path)
    remaining = subparsers.add_parser("remaining-shards")
    remaining.add_argument("--resume-plan", required=True, type=Path)
    reusable = subparsers.add_parser("reusable-shards")
    reusable.add_argument("--resume-plan", required=True, type=Path)
    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--shard-plan", required=True, type=Path)
    reconcile.add_argument("--output-dir", required=True, type=Path)
    reconcile.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command in {"create-source", "plan"}:
        context = _context_from_paths(args.risk_plan, args.stage_plan, args.shard_plan)
        if args.command == "create-source":
            payload = build_resume_source(context)
        else:
            payload, _ = plan_from_evidence(context, args.resume_evidence)
        _write(args.output, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "materialize":
        plan = _load_object(args.resume_plan, "resume plan")
        source = _validated_source(_load_object(args.resume_evidence, "resume evidence"))
        materialize_reused_shards(plan, source, source_root=args.resume_evidence.parent, output_dir=args.output_dir)
        return 0
    if args.command in {"remaining-shards", "reusable-shards"}:
        plan = _validated_resume_plan(_load_object(args.resume_plan, "resume plan"))
        field = "remainingShards" if args.command == "remaining-shards" else "reusableShards"
        if plan.get("kind") != RESUME_PLAN_KIND or not isinstance(plan.get(field), list):
            raise ResumeError(f"resume plan {field} is invalid")
        print("\n".join(plan[field]))
        return 0
    result = reconcile_shards(args.shard_plan, args.output_dir)
    _write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ResumeError, ValueError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
