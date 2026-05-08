#!/usr/bin/env python3
"""Run the offline operator evidence workflow in one safe local command.

The workflow orchestrates existing evidence helpers only. It reads local
sanitized JSON artifacts, writes bounded summaries, and renders a Markdown
review report for human review. It does not call networks, inspect environment
values, read deployment state, run probes, touch databases, send notifications,
or change runtime behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from operator_evidence_bundle_check import (
    BUNDLE_STATUSES,
    REQUIRED_REASON_MISSING,
    build_bundle_summary,
)
from operator_evidence_manifest_check import create_manifest, verify_manifest
from operator_evidence_template_pack import _build_templates, _write_templates
from release_review_report_render import _sanitize_status as _sanitize_report_status
from release_review_report_render import render_report


EXIT_OK = 0
EXIT_USAGE_OR_IO = 2
EXIT_MISSING_REQUIRED_ARTIFACT = 10
EXIT_VALIDATOR_REJECTION = 11
EXIT_MANIFEST_MISMATCH = 12
EXIT_UNSAFE_MARKER_DETECTED = 13

MANIFEST_OUTPUT = "evidence-manifest.json"
BUNDLE_SUMMARY_OUTPUT = "bundle-summary.json"
REPORT_OUTPUT = "release-review-report.md"
UNSAFE_MARKER_REASON = "unsafe_marker"
REPORT_OK_STATUSES = {BUNDLE_STATUSES["complete"]}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_root_not_object")
    return payload


def _artifact_findings(bundle: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for item in bundle.get("artifacts", []):
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "unknown")
        status = str(item.get("status") or "unknown")
        reasons = item.get("blockingReasonSummaries")
        if not isinstance(reasons, list):
            reasons = []
        for reason in reasons:
            reason_code = str(reason or "")
            if reason_code == UNSAFE_MARKER_REASON:
                findings.append({"category": category, "reasonCode": reason_code})
        if status == "missing":
            findings.append({"category": category, "reasonCode": REQUIRED_REASON_MISSING})
        if status == "rejected":
            if not reasons:
                findings.append({"category": category, "reasonCode": "validator_rejected_artifact"})
            for reason in reasons:
                reason_code = str(reason or "validator_rejected_artifact")
                findings.append({"category": category, "reasonCode": reason_code})
    return findings


def _manifest_summary_for_report(
    manifest: dict[str, Any],
    verification: dict[str, Any],
    create_findings: list[dict[str, str]],
) -> dict[str, Any]:
    verification_status = str(verification.get("verificationStatus") or "unknown")
    entries = manifest.get("entries")
    findings = verification.get("findings")
    reason_codes: list[str] = []
    for finding in create_findings + (findings if isinstance(findings, list) else []):
        if isinstance(finding, dict):
            reason = str(finding.get("reasonCode") or "").strip()
            if reason:
                reason_codes.append(reason)
    return {
        "schemaVersion": "wolfystock_operator_evidence_manifest_summary_v1",
        "manifestStatus": verification_status,
        "artifactCount": len(entries) if isinstance(entries, list) else 0,
        "checksumAlgorithm": "sha256",
        "checksumStatus": verification_status,
        "blockingReasonSummaries": sorted(set(reason_codes)),
    }


def _manifest_has_mismatch(verification: dict[str, Any]) -> bool:
    if verification.get("verificationStatus") == "pass":
        return False
    findings = verification.get("findings")
    if not isinstance(findings, list):
        return True
    missing_reasons = {"missing_file", "missing_manifest_entry", REQUIRED_REASON_MISSING}
    return any(
        isinstance(finding, dict) and str(finding.get("reasonCode") or "") not in missing_reasons
        for finding in findings
    )


def _workflow_exit(bundle: dict[str, Any], verification: dict[str, Any]) -> tuple[int, str]:
    artifact_findings = _artifact_findings(bundle)
    unsafe = [finding for finding in artifact_findings if finding["reasonCode"] == UNSAFE_MARKER_REASON]
    if unsafe:
        categories = ", ".join(sorted({finding["category"] for finding in unsafe}))
        return EXIT_UNSAFE_MARKER_DETECTED, f"[FAIL] unsafe marker detection: {categories}"

    missing = [finding for finding in artifact_findings if finding["reasonCode"] == REQUIRED_REASON_MISSING]
    if missing:
        categories = ", ".join(sorted({finding["category"] for finding in missing}))
        return (
            EXIT_MISSING_REQUIRED_ARTIFACT,
            f"[FAIL] missing required artifact: {categories}; reason: {REQUIRED_REASON_MISSING}",
        )

    if _manifest_has_mismatch(verification):
        reasons = []
        findings = verification.get("findings")
        if isinstance(findings, list):
            reasons = [
                str(finding.get("reasonCode"))
                for finding in findings
                if isinstance(finding, dict) and finding.get("reasonCode")
            ]
        reason_summary = ", ".join(sorted(set(reasons))) or "verification_failed"
        return EXIT_MANIFEST_MISMATCH, f"[FAIL] manifest mismatch: {reason_summary}"

    rejected = [finding for finding in artifact_findings if finding["reasonCode"] != REQUIRED_REASON_MISSING]
    if rejected:
        reasons = ", ".join(sorted({finding["reasonCode"] for finding in rejected}))
        return EXIT_VALIDATOR_REJECTION, f"[FAIL] validator rejection: {reasons}"

    bundle_status = str(bundle.get("bundleStatus") or "")
    if bundle_status not in REPORT_OK_STATUSES:
        safe_status = _sanitize_report_status(bundle_status)
        return EXIT_VALIDATOR_REJECTION, f"[FAIL] bundle status requires review blocker: {safe_status}"

    return EXIT_OK, "[OK] operator evidence workflow completed: review-required"


def _run_init(args: argparse.Namespace) -> int:
    try:
        templates = _build_templates("all")
        _write_templates(Path(args.output_dir), templates, force=False)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE_OR_IO
    print("[OK] sanitized operator evidence templates generated")
    return EXIT_OK


def _run_check(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.artifact_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest, create_findings = create_manifest(artifact_dir)
    manifest_path = output_dir / MANIFEST_OUTPUT
    _write_json(manifest_path, manifest)

    verification = verify_manifest(artifact_dir, manifest_path)
    bundle = build_bundle_summary(artifact_dir)
    _write_json(output_dir / BUNDLE_SUMMARY_OUTPUT, bundle)

    report = render_report(
        bundle,
        manifest=_manifest_summary_for_report(manifest, verification, create_findings),
    )
    (output_dir / REPORT_OUTPUT).write_text(report, encoding="utf-8")

    exit_code, message = _workflow_exit(bundle, verification)
    stream = sys.stdout if exit_code == EXIT_OK else sys.stderr
    print(message, file=stream)
    return exit_code


def _run_report(args: argparse.Namespace) -> int:
    try:
        bundle = _load_json_object(Path(args.bundle_summary))
        report = render_report(bundle)
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError):
        print("[FAIL] report render failed", file=sys.stderr)
        return EXIT_USAGE_OR_IO

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    bundle_status = str(bundle.get("bundleStatus") or "")
    if bundle_status in REPORT_OK_STATUSES:
        print("[OK] release review report rendered")
        return EXIT_OK
    safe_status = _sanitize_report_status(bundle_status)
    print(f"[FAIL] report rendered for non-passing bundle status: {safe_status}", file=sys.stderr)
    return EXIT_VALIDATOR_REJECTION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Generate sanitized local evidence templates.")
    init_parser.add_argument("--output-dir", required=True, help="Directory where template JSON files are written.")
    init_parser.set_defaults(func=_run_init)

    check_parser = subparsers.add_parser("check", help="Validate artifacts and render a review report.")
    check_parser.add_argument("--artifact-dir", required=True, help="Directory containing sanitized evidence artifacts.")
    check_parser.add_argument("--output-dir", required=True, help="Directory for workflow outputs.")
    check_parser.set_defaults(func=_run_check)

    report_parser = subparsers.add_parser("report", help="Render a Markdown report from a bundle summary.")
    report_parser.add_argument("--bundle-summary", required=True, help="Path to bundle-summary.json.")
    report_parser.add_argument("--output", required=True, help="Markdown report output path.")
    report_parser.set_defaults(func=_run_report)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
