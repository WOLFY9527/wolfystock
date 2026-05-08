#!/usr/bin/env python3
"""Package sanitized operator evidence workflow outputs for manual review.

The packager copies only bounded workflow outputs and writes an index containing
file labels, byte sizes, checksums, and review posture metadata. It does not
read environment variables, inspect deployment state, call networks, read source
artifact bodies into the index, or integrate with launch acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXIT_OK = 0
EXIT_USAGE_OR_IO = 2
EXIT_SAFETY_REJECTION = 13

INDEX_SCHEMA_VERSION = "wolfystock_operator_evidence_archive_index_v1"
INDEX_OUTPUT = "archive-index.json"
BUNDLE_SUMMARY_OUTPUT = "bundle-summary.json"
MANIFEST_OUTPUT = "evidence-manifest.json"
REPORT_OUTPUT = "release-review-report.md"
REVIEW_DIFF_OUTPUT = "review-diff.md"

KNOWN_WORKFLOW_OUTPUTS = {
    BUNDLE_SUMMARY_OUTPUT,
    MANIFEST_OUTPUT,
    REPORT_OUTPUT,
    REVIEW_DIFF_OUTPUT,
}
SOURCE_ARTIFACT_FILENAMES = {
    "config_snapshot_evidence.json",
    "manual_release_approval_review_record.json",
    "provider_operator_evidence.json",
    "quota_budget_operator_evidence.json",
    "restore_pitr_operator_evidence.json",
    "security_operator_acceptance.json",
    "staging_ingress_operator_evidence.json",
    "ws2_sse_operator_decision_evidence.json",
}
SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SAFE_STATUS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
UNSAFE_MARKERS = (
    "../",
    "..\\",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "database_url",
    "db_url",
    "debug_payload",
    "password",
    "payload",
    "private_key",
    "raw",
    "request",
    "response",
    "secret",
    "session",
    "set-cookie",
    "sk-",
    "stack trace",
    "stacktrace",
    "token",
    "traceback",
)
FORBIDDEN_APPROVAL_PHRASES = (
    "launch-" + "approved",
    "production-" + "ready",
    "automatic-" + "go",
    "automatic " + "go",
    "public launch " + "go",
    "release-" + "approved",
)


class ArchivePackError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_unsafe(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in UNSAFE_MARKERS + FORBIDDEN_APPROVAL_PHRASES)


def _safe_label(value: Any, *, default: str) -> str:
    text = str(value or "").strip() or default
    if (
        not SAFE_LABEL_RE.fullmatch(text)
        or _looks_unsafe(text)
        or Path(text).is_absolute()
        or Path(text).name != text
    ):
        raise ArchivePackError("unsafe_label")
    return text


def _safe_status(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not SAFE_STATUS_RE.fullmatch(text) or _looks_unsafe(text) or Path(text).is_absolute():
        return None
    return text


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchivePackError("workflow_output_json_read_failed") from exc
    if not isinstance(payload, dict):
        raise ArchivePackError("workflow_output_json_root_not_object")
    return payload


def _resolve_dir(path: Path, *, reason: str, must_exist: bool) -> Path:
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise ArchivePackError(reason) from exc
    if must_exist and not resolved.is_dir():
        raise ArchivePackError(reason)
    return resolved


def _reject_unsafe_source_shape(workflow_output_dir: Path) -> None:
    names = {path.name for path in workflow_output_dir.iterdir() if path.is_file()}
    if names & SOURCE_ARTIFACT_FILENAMES:
        raise ArchivePackError("source_artifact_dir_rejected")
    unknown_json = sorted(path.name for path in workflow_output_dir.glob("*.json") if path.name not in KNOWN_WORKFLOW_OUTPUTS)
    if unknown_json:
        raise ArchivePackError("unknown_json_output_rejected")


def _selected_outputs(args: argparse.Namespace) -> list[str]:
    names = [BUNDLE_SUMMARY_OUTPUT]
    if args.include_manifest:
        names.append(MANIFEST_OUTPUT)
    if args.include_report:
        names.append(REPORT_OUTPUT)
    return names


def _copy_output(source_dir: Path, output_dir: Path, file_label: str) -> dict[str, Any]:
    source = source_dir / file_label
    if not source.is_file():
        raise ArchivePackError(f"required_output_missing:{file_label}")
    target = output_dir / file_label
    shutil.copyfile(source, target)
    return {
        "fileLabel": file_label,
        "byteSize": target.stat().st_size,
        "sha256": _sha256_file(target),
    }


def _discover_review_status(workflow_output_dir: Path) -> str | None:
    bundle_path = workflow_output_dir / BUNDLE_SUMMARY_OUTPUT
    if not bundle_path.is_file():
        return None
    bundle = _load_json_object(bundle_path)
    return _safe_status(bundle.get("bundleStatus"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_no_forbidden_phrases(value: Any) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    if any(phrase in rendered for phrase in FORBIDDEN_APPROVAL_PHRASES):
        raise ArchivePackError("archive_index_forbidden_approval_phrase")


def _run_pack(args: argparse.Namespace) -> int:
    workflow_output_dir = _resolve_dir(Path(args.workflow_output_dir), reason="workflow_output_dir_invalid", must_exist=True)
    output_dir = _resolve_dir(Path(args.output_dir), reason="output_dir_invalid", must_exist=False)
    if workflow_output_dir == output_dir:
        raise ArchivePackError("output_dir_must_be_distinct")

    archive_label = _safe_label(args.label, default=output_dir.name or "operator-evidence-archive")
    _reject_unsafe_source_shape(workflow_output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    included_files = [_copy_output(workflow_output_dir, output_dir, name) for name in _selected_outputs(args)]
    review_diff = workflow_output_dir / REVIEW_DIFF_OUTPUT
    if review_diff.is_file():
        included_files.append(_copy_output(workflow_output_dir, output_dir, REVIEW_DIFF_OUTPUT))

    index: dict[str, Any] = {
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "archiveLabel": archive_label,
        "generatedAt": _now_iso(),
        "includedFiles": included_files,
        "manualReviewRequired": True,
        "releaseApproved": False,
    }
    review_status = _discover_review_status(workflow_output_dir)
    if review_status:
        index["reviewStatus"] = review_status
    _assert_no_forbidden_phrases(index)
    _write_json(output_dir / INDEX_OUTPUT, index)
    print("[OK] operator evidence archive packaged: manual-review-required")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack", help="Package sanitized workflow outputs into a review directory.")
    pack_parser.add_argument("--workflow-output-dir", required=True, help="Directory produced by the evidence workflow.")
    pack_parser.add_argument("--output-dir", required=True, help="Directory where archive files are written.")
    pack_parser.add_argument("--label", help="Sanitized archive label for archive-index.json.")
    pack_parser.add_argument("--include-manifest", action="store_true", help="Copy evidence-manifest.json into the archive.")
    pack_parser.add_argument("--include-report", action="store_true", help="Copy release-review-report.md into the archive.")
    pack_parser.set_defaults(func=_run_pack)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ArchivePackError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return EXIT_SAFETY_REJECTION if "rejected" in str(exc) or "unsafe" in str(exc) else EXIT_USAGE_OR_IO
    except OSError:
        print("[FAIL] archive_pack_io_failed", file=sys.stderr)
        return EXIT_USAGE_OR_IO


if __name__ == "__main__":
    sys.exit(main())
