#!/usr/bin/env python3
"""Aggregate sanitized operator evidence validator summaries offline.

This helper reads a local directory of already-sanitized JSON artifacts and
runs the existing standalone operator evidence validators in process. It emits
only a bounded summary for human review: artifact category, filename label,
validator name, status, and reason-code summaries.

It does not call networks, read environment files, run restore commands, touch
databases, send notifications, mutate runtime configuration, or integrate with
launch acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from evidence_safety import path_label as _path_label
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import path_label as _path_label

from provider_operator_evidence_check import validate_provider_operator_evidence
from provider_sla_licensing_evidence_check import validate_provider_sla_licensing_evidence
from api_abuse_request_safety_evidence_check import validate_api_abuse_request_safety_evidence
from config_snapshot_evidence_check import validate_config_snapshot_evidence
from manual_release_approval_evidence_check import validate_manual_release_approval_evidence
from quota_operator_evidence_check import validate_artifact as validate_quota_operator_evidence
from restore_pitr_operator_evidence_check import _build_report as validate_restore_pitr_operator_evidence
from security_operator_acceptance_check import _build_summary as validate_security_operator_acceptance
from staging_ingress_operator_evidence_check import validate_staging_ingress_operator_evidence
from ws2_sse_operator_decision_check import validate_ws2_sse_operator_decision


SCHEMA_VERSION = "wolfystock_operator_evidence_bundle_summary_v1"
BUNDLE_STATUSES = {
    "complete": "complete-review-required",
    "incomplete": "incomplete-no-go",
    "rejected": "rejected-no-go",
}
REQUIRED_REASON_MISSING = "required_artifact_missing"
UNKNOWN_ARTIFACT_REASON = "unknown_artifact_not_validated"
ACCEPTED_OUTCOMES = {"accepted"}
REVIEW_OUTCOMES = {"needs-review"}
REJECTED_OUTCOMES = {"rejected"}


Validator = Callable[[Any], dict[str, Any]]


@dataclass(frozen=True)
class ArtifactSpec:
    category: str
    filename: str
    validator_name: str
    validate: Validator


ARTIFACT_SPECS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        category="api-abuse-request-safety",
        filename="api_abuse_safety_evidence.json",
        validator_name="api_abuse_request_safety_evidence_check.py",
        validate=validate_api_abuse_request_safety_evidence,
    ),
    ArtifactSpec(
        category="provider",
        filename="provider_operator_evidence.json",
        validator_name="provider_operator_evidence_check.py",
        validate=validate_provider_operator_evidence,
    ),
    ArtifactSpec(
        category="provider-sla-licensing",
        filename="provider_sla_licensing_evidence.json",
        validator_name="provider_sla_licensing_evidence_check.py",
        validate=validate_provider_sla_licensing_evidence,
    ),
    ArtifactSpec(
        category="restore-pitr",
        filename="restore_pitr_operator_evidence.json",
        validator_name="restore_pitr_operator_evidence_check.py",
        validate=validate_restore_pitr_operator_evidence,
    ),
    ArtifactSpec(
        category="security",
        filename="security_operator_acceptance.json",
        validator_name="security_operator_acceptance_check.py",
        validate=validate_security_operator_acceptance,
    ),
    ArtifactSpec(
        category="quota-budget",
        filename="quota_budget_operator_evidence.json",
        validator_name="quota_operator_evidence_check.py",
        validate=validate_quota_operator_evidence,
    ),
    ArtifactSpec(
        category="staging-ingress",
        filename="staging_ingress_operator_evidence.json",
        validator_name="staging_ingress_operator_evidence_check.py",
        validate=validate_staging_ingress_operator_evidence,
    ),
    ArtifactSpec(
        category="ws2-sse",
        filename="ws2_sse_operator_decision_evidence.json",
        validator_name="ws2_sse_operator_decision_check.py",
        validate=validate_ws2_sse_operator_decision,
    ),
    ArtifactSpec(
        category="config-snapshot",
        filename="config_snapshot_evidence.json",
        validator_name="config_snapshot_evidence_check.py",
        validate=validate_config_snapshot_evidence,
    ),
    ArtifactSpec(
        category="manual-release-approval",
        filename="manual_release_approval_review_record.json",
        validator_name="manual_release_approval_evidence_check.py",
        validate=validate_manual_release_approval_evidence,
    ),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, REQUIRED_REASON_MISSING
    except (OSError, json.JSONDecodeError):
        return None, "artifact_read_failed"


def _collect_outcomes(value: Any) -> set[str]:
    outcomes: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).strip().lower() == "outcome":
                outcome = str(nested or "").strip().lower()
                if outcome:
                    outcomes.add(outcome)
            outcomes.update(_collect_outcomes(nested))
    elif isinstance(value, list):
        for nested in value:
            outcomes.update(_collect_outcomes(nested))
    return outcomes


def _validator_passed(summary: dict[str, Any]) -> bool:
    if summary.get("status") in {"pass", "accepted"}:
        return True
    if summary.get("finalStatus") in {"EVIDENCE-READY", "ACCEPTED"}:
        return True
    if (
        summary.get("manualReviewStatus") in {"needs-review", "review-record-valid"}
        and summary.get("releaseApproved") is False
        and summary.get("launchApproved") is False
    ):
        return True
    return False


def _reason_summaries(summary: dict[str, Any]) -> list[str]:
    reasons: set[str] = set()
    findings = summary.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict):
                reason = str(finding.get("reasonCode") or "").strip()
                if reason:
                    reasons.add(reason)
    if reasons:
        return sorted(reasons)

    checks = summary.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            if check.get("status") == "pass":
                continue
            check_id = str(check.get("id") or "check").strip()
            status = str(check.get("status") or "fail").strip()
            reasons.add(f"{check_id}:{status}")
    elif isinstance(checks, dict):
        for key, value in checks.items():
            if value is False:
                reasons.add(f"{key}:false")

    if not reasons and not _validator_passed(summary):
        reasons.add("validator_rejected_artifact")
    return sorted(reasons)


def _artifact_status(*, payload: Any, validator_summary: dict[str, Any]) -> str:
    manual_review_status = str(validator_summary.get("manualReviewStatus") or "").strip()
    if manual_review_status:
        if (
            manual_review_status in {"needs-review", "review-record-valid"}
            and validator_summary.get("releaseApproved") is False
            and validator_summary.get("launchApproved") is False
        ):
            return "needs-review"
        return "rejected"

    outcomes = _collect_outcomes(payload)
    passed = _validator_passed(validator_summary)
    if passed:
        if outcomes and outcomes.issubset(ACCEPTED_OUTCOMES):
            return "accepted"
        if outcomes & REVIEW_OUTCOMES:
            return "needs-review"
        return "accepted"
    if outcomes & REJECTED_OUTCOMES:
        return "rejected"
    if outcomes and outcomes.issubset(REVIEW_OUTCOMES):
        return "needs-review"
    return "rejected"


def _summarize_artifact(artifact_dir: Path, spec: ArtifactSpec) -> dict[str, Any]:
    path = artifact_dir / spec.filename
    if not path.exists():
        return {
            "category": spec.category,
            "pathLabel": spec.filename,
            "status": "missing",
            "validatorName": spec.validator_name,
            "blockingReasonSummaries": [REQUIRED_REASON_MISSING],
        }

    payload, load_error = _load_json(path)
    if load_error:
        return {
            "category": spec.category,
            "pathLabel": _path_label(path),
            "status": "rejected",
            "validatorName": spec.validator_name,
            "blockingReasonSummaries": [load_error],
        }

    try:
        validator_summary = spec.validate(payload)
    except Exception:
        return {
            "category": spec.category,
            "pathLabel": _path_label(path),
            "status": "rejected",
            "validatorName": spec.validator_name,
            "blockingReasonSummaries": ["validator_execution_failed"],
        }

    return {
        "category": spec.category,
        "pathLabel": _path_label(path),
        "status": _artifact_status(payload=payload, validator_summary=validator_summary),
        "validatorName": spec.validator_name,
        "blockingReasonSummaries": _reason_summaries(validator_summary),
    }


def _summarize_unknown_artifacts(artifact_dir: Path) -> list[dict[str, Any]]:
    expected = {spec.filename for spec in ARTIFACT_SPECS}
    advisories: list[dict[str, Any]] = []
    for path in sorted(artifact_dir.glob("*.json")):
        if path.name in expected:
            continue
        advisories.append(
            {
                "category": "unknown-extra-artifact",
                "pathLabel": _path_label(path),
                "status": "needs-review",
                "validatorName": "operator_evidence_bundle_check.py",
                "blockingReasonSummaries": [UNKNOWN_ARTIFACT_REASON],
            }
        )
    return advisories


def build_bundle_summary(artifact_dir: Path) -> dict[str, Any]:
    artifacts = [_summarize_artifact(artifact_dir, spec) for spec in ARTIFACT_SPECS]
    missing = any(artifact["status"] == "missing" for artifact in artifacts)
    rejected = any(artifact["status"] == "rejected" for artifact in artifacts)
    if missing:
        bundle_status = BUNDLE_STATUSES["incomplete"]
    elif rejected:
        bundle_status = BUNDLE_STATUSES["rejected"]
    else:
        bundle_status = BUNDLE_STATUSES["complete"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": _now_iso(),
        "artifactDirectoryLabel": _path_label(artifact_dir),
        "bundleStatus": bundle_status,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "rawArtifactBodiesIncluded": False,
        "artifacts": artifacts,
        "advisories": _summarize_unknown_artifacts(artifact_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", help="Directory containing sanitized operator evidence JSON artifacts.")
    args = parser.parse_args(argv)

    artifact_dir = Path(args.artifact_dir)
    if not artifact_dir.is_dir():
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": _now_iso(),
            "artifactDirectoryLabel": _path_label(artifact_dir),
            "bundleStatus": BUNDLE_STATUSES["incomplete"],
            "runtimeBehaviorChanged": False,
            "networkCallsExecutedByValidator": False,
            "rawArtifactBodiesIncluded": False,
            "artifacts": [
                {
                    "category": spec.category,
                    "pathLabel": spec.filename,
                    "status": "missing",
                    "validatorName": spec.validator_name,
                    "blockingReasonSummaries": [REQUIRED_REASON_MISSING],
                }
                for spec in ARTIFACT_SPECS
            ],
            "advisories": [],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    summary = build_bundle_summary(artifact_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["bundleStatus"] == BUNDLE_STATUSES["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
