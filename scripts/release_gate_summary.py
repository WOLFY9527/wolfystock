#!/usr/bin/env python3
"""Record, aggregate, and verify authoritative release qualification evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from release_candidate import canonical_digest, load_manifest, verify_artifacts, verify_environment, write_json


EVIDENCE_SCHEMA = "wolfystock_release_gate_evidence_v2"
QUALIFICATION_SCHEMA = "wolfystock_release_qualification_v2"
REQUIRED_GATES = (
    "backend-canonical",
    "authoritative-topology",
    "full-vitest",
    "frontend-lint",
    "frontend-typecheck",
    "production-build",
    "playwright-real-runtime",
    "runtime-uat",
    "auth-rbac",
    "operator-evidence",
    "secret-private-path-scan",
    "artifact-provenance",
)
UAT_CHECKS = (
    "localBuild",
    "runtimeBundle",
    "publicRoutes",
    "runtimeAuthMode",
    "authenticatedRoutes",
    "adminOpsStatus",
    "surfaceReadiness",
)
BROWSER_CASES = (
    "production startup readiness and static assets",
    "login logout and revoked session",
    "member admin boundary and portfolio read",
    "rollback error preserves portfolio state and exposes unavailable data",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _details_from_assignments(values: Sequence[str]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("detail_must_use_name_equals_value")
        name, value = raw.split("=", 1)
        name = name.strip()
        if not name or name in details:
            raise ValueError("detail_name_invalid_or_duplicate")
        details[name] = _parse_value(value.strip())
    return details


def _walk_specs(node: Any):
    if not isinstance(node, dict):
        return
    for spec in node.get("specs", []):
        if isinstance(spec, dict):
            yield spec
    for suite in node.get("suites", []):
        yield from _walk_specs(suite)


def _browser_details(report: Any, browser_spec: Path | None) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return {}, ["browser_report_not_object"]
    if browser_spec is None or not browser_spec.is_file():
        errors.append("browser_spec_missing")
    else:
        source = browser_spec.read_text(encoding="utf-8")
        if ".route(" in source:
            errors.append("browser_release_spec_contains_mocked_routes")

    outcomes: dict[str, str] = {}
    retries_observed = 0
    skipped = 0
    failed = 0
    for spec in _walk_specs(report):
        title = str(spec.get("title") or "")
        for test in spec.get("tests", []):
            if not isinstance(test, dict) or test.get("projectName") != "release-real-runtime":
                continue
            results = test.get("results") if isinstance(test.get("results"), list) else []
            first = next((result for result in results if isinstance(result, dict) and result.get("retry", 0) == 0), None)
            status = str(first.get("status") if isinstance(first, dict) else test.get("status") or "missing")
            outcomes[title] = status
            retries_observed += sum(
                1 for result in results if isinstance(result, dict) and int(result.get("retry") or 0) > 0
            )
            if status == "skipped" or str(test.get("status") or "") == "skipped":
                skipped += 1
            elif status != "passed":
                failed += 1
    missing = sorted(set(BROWSER_CASES) - set(outcomes))
    unexpected = sorted(set(outcomes) - set(BROWSER_CASES))
    if missing:
        errors.append("browser_required_cases_missing:" + ",".join(missing))
    if unexpected:
        errors.append("browser_unexpected_cases:" + ",".join(unexpected))
    if skipped:
        errors.append("browser_required_case_skipped")
    if retries_observed:
        errors.append("browser_retry_observed")
    if failed:
        errors.append("browser_first_attempt_failed")
    details = {
        "project": "release-real-runtime",
        "mockedRouteSuites": 0 if "browser_release_spec_contains_mocked_routes" not in errors else 1,
        "retriesObserved": retries_observed,
        "requiredCases": list(BROWSER_CASES),
        "firstAttempt": {
            "total": len(outcomes),
            "passed": sum(status == "passed" for status in outcomes.values()),
            "failed": failed,
            "skipped": skipped,
        },
    }
    return details, errors


def _uat_details(report: Any, candidate: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(report, dict):
        return {}, ["uat_report_not_object"]
    smoke = report.get("smokeReport")
    if not isinstance(smoke, dict):
        return {}, ["uat_smoke_report_missing"]
    checks = smoke.get("checks") if isinstance(smoke.get("checks"), dict) else {}
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    web_artifact = report.get("webArtifact") if isinstance(report.get("webArtifact"), dict) else {}
    web_payload = web_artifact.get("payload") if isinstance(web_artifact.get("payload"), dict) else {}
    statuses: dict[str, str] = {}
    for name in UAT_CHECKS:
        check = checks.get(name)
        statuses[name] = str(check.get("status") or "MISSING") if isinstance(check, dict) else "MISSING"
    errors: list[str] = []
    if report.get("contract") != "wolfystock_uat_runtime_harness_v1":
        errors.append("uat_contract_mismatch")
    if source.get("gitSha") != candidate["commitSha"] or run.get("sha") != candidate["commitSha"]:
        errors.append("uat_candidate_sha_mismatch")
    if report.get("status") != "PASS":
        errors.append("uat_harness_not_pass")
    if report.get("environmentFingerprint") != candidate["environment"]["fingerprint"]:
        errors.append("uat_environment_fingerprint_mismatch")
    if run.get("cwd") != "$WORKTREE":
        errors.append("uat_runtime_cwd_not_sanitized")
    if web_payload.get("fingerprint") != candidate["web"]["artifactFingerprint"]:
        errors.append("uat_web_artifact_fingerprint_mismatch")
    if smoke.get("summaryStatus") != "PASS" or smoke.get("exitCode") != 0:
        errors.append("uat_aggregate_not_pass")
    errors.extend(f"uat_{name}_not_pass" for name, status in statuses.items() if status != "PASS")
    return {
        "contract": report.get("contract"),
        "candidateSha": source.get("gitSha"),
        "environmentFingerprint": report.get("environmentFingerprint"),
        "runtimeCwd": run.get("cwd"),
        "assetFingerprint": web_payload.get("fingerprint"),
        "summaryStatus": smoke.get("summaryStatus"),
        "exitCode": smoke.get("exitCode"),
        "requiredChecks": statuses,
    }, errors


def _operator_details(
    report: Any,
    operator_evidence_dir: Path | None,
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(report, dict) or report.get("bundleStatus") != "complete-review-required":
        return {}, ["operator_evidence_not_complete"]
    details = {
        "bundleSchema": report.get("schemaVersion"),
        "bundleStatus": report["bundleStatus"],
    }
    errors: list[str] = []
    if report.get("schemaVersion") != "wolfystock_operator_evidence_bundle_summary_v1":
        errors.append("operator_evidence_schema_mismatch")
    if operator_evidence_dir is None or not operator_evidence_dir.is_dir():
        return details, [*errors, "operator_evidence_directory_missing"]
    try:
        manual_review = _load_json(operator_evidence_dir / "manual_release_approval_review_record.json")
    except (OSError, json.JSONDecodeError):
        return details, [*errors, "operator_manual_review_unreadable"]
    release_candidate_sha = manual_review.get("releaseCandidateSha") if isinstance(manual_review, dict) else None
    details["releaseCandidateSha"] = release_candidate_sha
    if release_candidate_sha != candidate["commitSha"]:
        errors.append("operator_evidence_candidate_sha_mismatch")
    return details, errors


def _production_build_details(report: Any, candidate: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(report, dict):
        return {}, ["production_build_report_not_object"]
    manifest = report.get("manifest") if isinstance(report.get("manifest"), dict) else {}
    build_candidate = manifest.get("candidate") if isinstance(manifest.get("candidate"), dict) else {}
    fingerprint = manifest.get("fingerprint")
    assets = manifest.get("assets")
    valid = (
        report.get("ok") is True
        and report.get("errorCodes") == []
        and manifest.get("contract") == "wolfystock_web_build_artifact_v1"
        and build_candidate.get("commit") == candidate["commitSha"]
        and build_candidate.get("dirty") is False
        and isinstance(fingerprint, str)
        and len(fingerprint) == 64
        and all(character in "0123456789abcdef" for character in fingerprint)
        and isinstance(assets, list)
        and bool(assets)
    )
    details = {
        "artifactContract": manifest.get("contract"),
        "artifactCandidateSha": build_candidate.get("commit"),
        "artifactFingerprint": fingerprint,
        "assetCount": len(assets) if isinstance(assets, list) else 0,
    }
    return details, [] if valid else ["production_build_report_not_pass"]


def _auth_rbac_details(report: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(report, dict):
        return {}, ["auth_rbac_audit_not_pass"]
    surfaces = report.get("surfacesChecked")
    risky_findings = report.get("riskyFindings")
    valid = (
        report.get("auditStatus") == "manual_review_required"
        and isinstance(surfaces, list)
        and bool(surfaces)
        and all(isinstance(surface, dict) and surface.get("status") == "pass" for surface in surfaces)
        and risky_findings == []
        and report.get("manualReviewRequired") is True
        and report.get("networkCallsExecuted") is False
    )
    details = {
        "auditStatus": report.get("auditStatus"),
        "surfaceCount": len(surfaces) if isinstance(surfaces, list) else 0,
        "riskyFindingCount": len(risky_findings) if isinstance(risky_findings, list) else None,
        "manualReviewRequired": report.get("manualReviewRequired"),
        "networkCallsExecuted": report.get("networkCallsExecuted"),
    }
    return details, [] if valid else ["auth_rbac_audit_not_pass"]


def _source_details(
    gate_id: str,
    report: Any,
    browser_spec: Path | None,
    operator_evidence_dir: Path | None,
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if gate_id == "playwright-real-runtime":
        return _browser_details(report, browser_spec)
    if gate_id == "runtime-uat":
        return _uat_details(report, candidate)
    if gate_id == "secret-private-path-scan":
        if not isinstance(report, dict):
            return {}, ["secret_scan_report_not_object"]
        details = {
            "scanSchema": report.get("schemaVersion"),
            "scanMode": report.get("mode"),
            "scannedCommit": report.get("scannedCommit"),
            "fileCount": report.get("fileCount"),
            "privatePathScan": report.get("privatePathScan"),
        }
        errors: list[str] = []
        if report.get("schemaVersion") != "wolfystock_release_secret_scan_v1" or report.get("mode") != "candidate":
            errors.append("secret_scan_contract_mismatch")
        if report.get("status") != "PASS":
            errors.append("secret_scan_not_pass")
        return details, errors
    if gate_id == "operator-evidence":
        return _operator_details(report, operator_evidence_dir, candidate)
    if gate_id == "auth-rbac":
        return _auth_rbac_details(report)
    if gate_id == "production-build":
        return _production_build_details(report, candidate)
    if isinstance(report, dict) and report.get("ok") is False:
        return {}, ["source_report_not_pass"]
    return {"sourceReportValidated": True}, []


def _artifact_digest_map(candidate: dict[str, Any]) -> dict[str, str]:
    return {str(item["name"]): str(item["sha256"]) for item in candidate["artifacts"]}


def _candidate_identity(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidateSha": candidate["commitSha"],
        "candidateDigest": candidate["candidateDigest"],
        "environmentFingerprint": candidate["environment"]["fingerprint"],
        "pythonLockContentHash": candidate["pythonLock"]["contentHash"],
        "imageIndexDigest": candidate["images"]["indexDigest"],
        "imagePlatformDigests": {
            platform: details["digest"] for platform, details in candidate["images"]["platforms"].items()
        },
    }


def _validate_gate_details(gate_id: str, details: Any, candidate: dict[str, Any]) -> list[str]:
    if not isinstance(details, dict):
        return ["gate_details_invalid"]
    errors: list[str] = []
    if gate_id in {
        "backend-canonical",
        "authoritative-topology",
        "full-vitest",
        "frontend-lint",
        "frontend-typecheck",
    }:
        if details.get("commandExitCode") != 0:
            errors.append("gate_command_not_pass")
    elif gate_id == "production-build":
        if details.get("artifactContract") != "wolfystock_web_build_artifact_v1":
            errors.append("production_build_contract_mismatch")
        if details.get("artifactCandidateSha") != candidate["commitSha"]:
            errors.append("production_build_candidate_sha_mismatch")
        if not re.fullmatch(r"[0-9a-f]{64}", str(details.get("artifactFingerprint") or "")):
            errors.append("production_build_fingerprint_invalid")
        if type(details.get("assetCount")) is not int or details["assetCount"] <= 0:
            errors.append("production_build_assets_missing")
    elif gate_id == "playwright-real-runtime":
        first = details.get("firstAttempt") if isinstance(details.get("firstAttempt"), dict) else {}
        if details.get("project") != "release-real-runtime" or details.get("mockedRouteSuites") != 0:
            errors.append("browser_project_or_mode_invalid")
        if details.get("retriesObserved") != 0:
            errors.append("browser_retry_observed")
        if details.get("requiredCases") != list(BROWSER_CASES):
            errors.append("browser_required_cases_invalid")
        if first != {"total": len(BROWSER_CASES), "passed": len(BROWSER_CASES), "failed": 0, "skipped": 0}:
            errors.append("browser_first_attempt_not_pass")
    elif gate_id == "runtime-uat":
        if details.get("contract") != "wolfystock_uat_runtime_harness_v1":
            errors.append("uat_contract_mismatch")
        if details.get("candidateSha") != candidate["commitSha"]:
            errors.append("uat_candidate_sha_mismatch")
        if details.get("environmentFingerprint") != candidate["environment"]["fingerprint"]:
            errors.append("uat_environment_fingerprint_mismatch")
        if details.get("runtimeCwd") != "$WORKTREE":
            errors.append("uat_runtime_cwd_invalid")
        if details.get("assetFingerprint") != candidate["web"]["artifactFingerprint"]:
            errors.append("uat_asset_fingerprint_mismatch")
        if details.get("summaryStatus") != "PASS" or details.get("exitCode") != 0:
            errors.append("uat_aggregate_not_pass")
        checks = details.get("requiredChecks") if isinstance(details.get("requiredChecks"), dict) else {}
        errors.extend(f"uat_{name}_not_pass" for name in UAT_CHECKS if checks.get(name) != "PASS")
    elif gate_id == "secret-private-path-scan":
        if details.get("scanSchema") != "wolfystock_release_secret_scan_v1" or details.get("scanMode") != "candidate":
            errors.append("secret_scan_contract_mismatch")
        if details.get("scannedCommit") != candidate["commitSha"]:
            errors.append("secret_scan_sha_mismatch")
        if type(details.get("fileCount")) is not int or details["fileCount"] <= 0:
            errors.append("secret_scan_zero_files")
        if details.get("privatePathScan") != "PASS":
            errors.append("private_path_scan_not_pass")
    elif gate_id == "auth-rbac":
        if details.get("auditStatus") != "manual_review_required":
            errors.append("auth_rbac_audit_status_invalid")
        if type(details.get("surfaceCount")) is not int or details["surfaceCount"] <= 0:
            errors.append("auth_rbac_surface_count_invalid")
        if details.get("riskyFindingCount") != 0:
            errors.append("auth_rbac_risky_findings_present")
        if details.get("manualReviewRequired") is not True or details.get("networkCallsExecuted") is not False:
            errors.append("auth_rbac_audit_mode_invalid")
    elif gate_id == "operator-evidence":
        if details.get("bundleSchema") != "wolfystock_operator_evidence_bundle_summary_v1":
            errors.append("operator_evidence_schema_mismatch")
        if details.get("bundleStatus") != "complete-review-required":
            errors.append("operator_evidence_not_complete")
        if details.get("releaseCandidateSha") != candidate["commitSha"]:
            errors.append("operator_evidence_candidate_sha_mismatch")
        if details.get("environment") != "release-approval":
            errors.append("operator_evidence_environment_invalid")
    elif gate_id == "artifact-provenance":
        if details.get("provenanceAttested") is not True:
            errors.append("provenance_attestation_missing")
        if details.get("artifactDigests") != _artifact_digest_map(candidate):
            errors.append("provenance_artifact_digests_mismatch")
        if details.get("imageIndexDigest") != candidate["images"]["indexDigest"]:
            errors.append("provenance_image_index_digest_mismatch")
        if details.get("imagePlatformDigests") != _candidate_identity(candidate)["imagePlatformDigests"]:
            errors.append("provenance_image_platform_digests_mismatch")
    return errors


def _validate_evidence(payload: Any, gate_id: str, candidate: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["evidence_not_object"]
    errors: list[str] = []
    if payload.get("schemaVersion") != EVIDENCE_SCHEMA:
        errors.append("evidence_schema_mismatch")
    if payload.get("gateId") != gate_id:
        errors.append("evidence_gate_id_mismatch")
    if payload.get("status") != "PASS":
        errors.append("evidence_status_not_pass")
    for field, expected in _candidate_identity(candidate).items():
        if payload.get(field) != expected:
            errors.append(f"evidence_{field}_mismatch")
    errors.extend(_validate_gate_details(gate_id, payload.get("details"), candidate))
    return sorted(set(errors))


def record_evidence(args: argparse.Namespace) -> int:
    candidate = load_manifest(args.candidate)
    details = _details_from_assignments(args.detail)
    if args.status == "FAIL":
        write_json(
            args.output,
            {
                "schemaVersion": EVIDENCE_SCHEMA,
                "gateId": args.gate_id,
                "status": "FAIL",
                **_candidate_identity(candidate),
                "details": details or {"reasonCode": "gate_not_completed"},
            },
        )
        return 0
    errors: list[str] = []
    if args.source_report:
        source_details, source_errors = _source_details(
            args.gate_id,
            _load_json(args.source_report),
            args.browser_spec,
            args.operator_evidence_dir,
            candidate,
        )
        details.update(source_details)
        errors.extend(source_errors)
    if args.gate_id == "artifact-provenance":
        details["artifactDigests"] = _artifact_digest_map(candidate)
        details["imageIndexDigest"] = candidate["images"]["indexDigest"]
        details["imagePlatformDigests"] = _candidate_identity(candidate)["imagePlatformDigests"]
    probe = {
        "schemaVersion": EVIDENCE_SCHEMA,
        "gateId": args.gate_id,
        "status": "PASS",
        **_candidate_identity(candidate),
        "details": details,
    }
    errors.extend(_validate_evidence(probe, args.gate_id, candidate))
    if errors:
        print("[NO-GO] " + ";".join(sorted(set(errors))), file=sys.stderr)
        return 1
    write_json(args.output, probe)
    return 0


def qualify(args: argparse.Namespace) -> int:
    candidate = load_manifest(args.candidate)
    environment_errors = verify_environment(
        candidate,
        _load_json(args.environment_evidence),
        _load_json(args.python_lock_report),
    )
    if environment_errors:
        raise ValueError(";".join(sorted(set(environment_errors))))
    gates: list[dict[str, Any]] = []
    for gate_id in REQUIRED_GATES:
        path = args.evidence_dir / f"{gate_id}.json"
        if not path.is_file():
            gates.append(
                {
                    "gateId": gate_id,
                    "status": "MISSING",
                    "reasonCodes": ["required_evidence_missing"],
                    "evidenceDigest": None,
                }
            )
            continue
        try:
            payload = _load_json(path)
        except (OSError, json.JSONDecodeError):
            gates.append(
                {
                    "gateId": gate_id,
                    "status": "MALFORMED",
                    "reasonCodes": ["evidence_unreadable"],
                    "evidenceDigest": None,
                }
            )
            continue
        errors = _validate_evidence(payload, gate_id, candidate)
        gates.append(
            {
                "gateId": gate_id,
                "status": "PASS" if not errors else "FAIL",
                "reasonCodes": errors,
                "evidenceDigest": canonical_digest(payload),
            }
        )
    go = all(gate["status"] == "PASS" for gate in gates)
    summary: dict[str, Any] = {
        "schemaVersion": QUALIFICATION_SCHEMA,
        **_candidate_identity(candidate),
        "environmentEvidenceDigest": candidate["environment"]["evidenceDigest"],
        "finalStatus": "GO" if go else "NO-GO",
        "releaseApproved": go,
        "gates": gates,
    }
    summary["qualificationDigest"] = canonical_digest(summary)
    write_json(args.output, summary)
    print(json.dumps({"candidateDigest": candidate["candidateDigest"], "finalStatus": summary["finalStatus"]}))
    return 0 if go else 1


def verify_promotion(args: argparse.Namespace) -> int:
    candidate = load_manifest(args.candidate)
    errors = verify_artifacts(candidate, args.artifact_dir)
    if args.expected_sha and candidate["commitSha"] != args.expected_sha.strip().lower():
        errors.append("candidate_sha_mismatch")
    try:
        qualification = _load_json(args.qualification)
    except (OSError, json.JSONDecodeError):
        qualification = {}
        errors.append("qualification_unreadable")
    if qualification.get("schemaVersion") != QUALIFICATION_SCHEMA:
        errors.append("qualification_schema_mismatch")
    digest_payload = dict(qualification)
    observed_digest = digest_payload.pop("qualificationDigest", None)
    if observed_digest != canonical_digest(digest_payload):
        errors.append("qualification_digest_mismatch")
    if qualification.get("finalStatus") != "GO" or qualification.get("releaseApproved") is not True:
        errors.append("qualification_not_go")
    for field, expected in _candidate_identity(candidate).items():
        if qualification.get(field) != expected:
            errors.append(f"qualification_{field}_mismatch")
    if qualification.get("environmentEvidenceDigest") != candidate["environment"]["evidenceDigest"]:
        errors.append("qualification_environment_evidence_digest_mismatch")
    gates = qualification.get("gates") if isinstance(qualification.get("gates"), list) else []
    if (
        len(gates) != len(REQUIRED_GATES)
        or [gate.get("gateId") for gate in gates] != list(REQUIRED_GATES)
        or any(
            gate.get("status") != "PASS"
            or gate.get("reasonCodes") != []
            or not re.fullmatch(r"[0-9a-f]{64}", str(gate.get("evidenceDigest") or ""))
            for gate in gates
        )
    ):
        errors.append("qualification_required_gates_not_pass")
    if errors:
        print("[NO-GO] " + ";".join(sorted(set(errors))), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "candidateDigest": candidate["candidateDigest"],
                "qualificationDigest": qualification.get("qualificationDigest"),
                "imageIndexDigest": candidate["images"]["indexDigest"],
                "finalStatus": "GO",
            }
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record")
    record.add_argument("--candidate", type=Path, required=True)
    record.add_argument("--gate-id", choices=REQUIRED_GATES, required=True)
    record.add_argument("--status", choices=("PASS", "FAIL"), default="PASS")
    record.add_argument("--source-report", type=Path)
    record.add_argument("--browser-spec", type=Path)
    record.add_argument("--operator-evidence-dir", type=Path)
    record.add_argument("--detail", action="append", default=[])
    record.add_argument("--output", type=Path, required=True)
    aggregate = subparsers.add_parser("qualify")
    aggregate.add_argument("--candidate", type=Path, required=True)
    aggregate.add_argument("--evidence-dir", type=Path, required=True)
    aggregate.add_argument("--environment-evidence", type=Path, required=True)
    aggregate.add_argument("--python-lock-report", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify-promotion")
    verify.add_argument("--candidate", type=Path, required=True)
    verify.add_argument("--qualification", type=Path, required=True)
    verify.add_argument("--artifact-dir", type=Path, required=True)
    verify.add_argument("--expected-sha", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.command == "record":
            return record_evidence(args)
        if args.command == "qualify":
            return qualify(args)
        return verify_promotion(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[NO-GO] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
