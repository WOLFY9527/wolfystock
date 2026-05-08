#!/usr/bin/env python3
"""Create and verify sanitized operator evidence checksum manifests offline.

This helper reads local sanitized evidence artifacts only to compute file
checksums and discover bounded metadata. It emits filename labels, categories,
hashes, byte sizes, validator names, and redaction versions. It never prints raw
artifact bodies, calls networks, reads environment files, or changes runtime
behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from operator_evidence_bundle_check import ARTIFACT_SPECS


MANIFEST_SCHEMA_VERSION = "wolfystock_operator_evidence_manifest_v1"
VERIFY_SCHEMA_VERSION = "wolfystock_operator_evidence_manifest_verification_v1"
ENTRY_FIELDS = {
    "category",
    "fileLabel",
    "sha256",
    "byteSize",
    "generatedAt",
    "validatorName",
    "redactionVersion",
}
TOP_LEVEL_FIELDS = {"schemaVersion", "generatedAt", "artifactDirectoryLabel", "entries"}
SAFE_SUMMARY_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
UNSAFE_SUMMARY_MARKERS = (
    "../",
    "..\\",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "debug_payload",
    "password",
    "private_key",
    "raw",
    "release-approved",
    "secret",
    "session",
    "set-cookie",
    "stack trace",
    "token",
    "traceback",
)


@dataclass(frozen=True)
class ManifestSpec:
    category: str
    filename: str
    validator_name: str


MANIFEST_SPECS: tuple[ManifestSpec, ...] = tuple(
    ManifestSpec(spec.category, spec.filename, spec.validator_name) for spec in ARTIFACT_SPECS
)
SPEC_BY_FILE_LABEL = {spec.filename: spec for spec in MANIFEST_SPECS}
SPEC_BY_CATEGORY_AND_FILE = {(spec.category, spec.filename): spec for spec in MANIFEST_SPECS}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_safe_file_label(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    label = value.strip()
    if not label or label in {".", ".."}:
        return False
    path = Path(label)
    return path.name == label and not path.is_absolute() and "/" not in label and "\\" not in label


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_for_metadata(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _collect_redaction_versions(value: Any) -> list[str]:
    versions: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in {"evidenceredactionversion", "redactionversion"} and isinstance(nested, str):
                version = nested.strip()
                if version:
                    versions.add(version)
            versions.update(_collect_redaction_versions(nested))
    elif isinstance(value, list):
        for nested in value:
            versions.update(_collect_redaction_versions(nested))
    return sorted(versions)


def _redaction_version(path: Path) -> str | None:
    metadata = _read_json_for_metadata(path)
    versions = _collect_redaction_versions(metadata)
    if not versions:
        return None
    return ",".join(versions)


def _manifest_entry(artifact_dir: Path, spec: ManifestSpec, generated_at: str) -> dict[str, Any]:
    path = artifact_dir / spec.filename
    entry: dict[str, Any] = {
        "category": spec.category,
        "fileLabel": spec.filename,
        "sha256": _sha256_file(path),
        "byteSize": path.stat().st_size,
        "generatedAt": generated_at,
        "validatorName": spec.validator_name,
    }
    redaction_version = _redaction_version(path)
    if redaction_version:
        entry["redactionVersion"] = redaction_version
    return entry


def create_manifest(artifact_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    generated_at = _now_iso()
    entries: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    for spec in MANIFEST_SPECS:
        path = artifact_dir / spec.filename
        if not path.is_file():
            findings.append(
                {
                    "category": spec.category,
                    "fileLabel": spec.filename,
                    "reasonCode": "missing_file",
                }
            )
            continue
        entries.append(_manifest_entry(artifact_dir, spec, generated_at))

    manifest = {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "artifactDirectoryLabel": artifact_dir.name,
        "entries": entries,
    }
    return manifest, findings


def _safe_summary_token(value: Any, *, default: str, unsafe_default: str | None = None) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if not text:
        return default
    if (
        not SAFE_SUMMARY_TOKEN_RE.fullmatch(text)
        or any(marker in lowered for marker in UNSAFE_SUMMARY_MARKERS)
        or Path(text).is_absolute()
    ):
        return unsafe_default or default
    return text


def _finding(category: Any, file_label: Any, reason_code: str) -> dict[str, str]:
    safe_category = _safe_summary_token(category, default="manifest", unsafe_default="[redacted]")
    safe_label = _safe_summary_token(file_label, default="manifest.json", unsafe_default="[redacted]")
    return {"category": safe_category, "fileLabel": safe_label, "reasonCode": reason_code}


def _safe_manifest_label(path: Path) -> str:
    return path.name if _is_safe_file_label(path.name) else "manifest.json"


def _verification_summary(artifact_dir: Path, manifest_path: Path, findings: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schemaVersion": VERIFY_SCHEMA_VERSION,
        "generatedAt": _now_iso(),
        "artifactDirectoryLabel": artifact_dir.name,
        "manifestLabel": _safe_manifest_label(manifest_path),
        "verificationStatus": "pass" if not findings else "fail",
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "rawArtifactBodiesIncluded": False,
        "findings": findings,
    }


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [_finding("manifest", path.name, "manifest_missing")]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, [_finding("manifest", path.name, "manifest_read_failed")]
    if not isinstance(payload, dict):
        return None, [_finding("manifest", path.name, "manifest_must_be_json_object")]
    return payload, []


def _validate_manifest_shape(manifest: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if any(field not in TOP_LEVEL_FIELDS for field in manifest):
        findings.append(_finding("manifest", "manifest.json", "unsafe_manifest_field"))
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA_VERSION:
        findings.append(_finding("manifest", "manifest.json", "invalid_schema_version"))
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        findings.append(_finding("manifest", "manifest.json", "entries_must_be_array"))
        return findings
    for entry in entries:
        if not isinstance(entry, dict):
            findings.append(_finding("manifest", "manifest.json", "entry_must_be_json_object"))
            continue
        category = entry.get("category")
        file_label = entry.get("fileLabel")
        if any(field not in ENTRY_FIELDS for field in entry):
            findings.append(_finding(category, file_label, "unsafe_manifest_field"))
        if not _is_safe_file_label(file_label):
            findings.append(_finding(category, file_label, "path_traversal_rejected"))
            continue
        if (category, file_label) not in SPEC_BY_CATEGORY_AND_FILE:
            findings.append(_finding(category, file_label, "unknown_required_artifact"))
        if not isinstance(entry.get("sha256"), str) or len(entry.get("sha256", "")) != 64:
            findings.append(_finding(category, file_label, "invalid_checksum"))
        if not isinstance(entry.get("byteSize"), int) or entry.get("byteSize") < 0:
            findings.append(_finding(category, file_label, "invalid_byte_size"))
    return findings


def verify_manifest(artifact_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest, findings = _load_manifest(manifest_path)
    if manifest is None:
        return _verification_summary(artifact_dir, manifest_path, findings)

    findings.extend(_validate_manifest_shape(manifest))
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return _verification_summary(artifact_dir, manifest_path, findings)

    seen_expected: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        category = entry.get("category")
        file_label = entry.get("fileLabel")
        if not _is_safe_file_label(file_label):
            continue
        spec = SPEC_BY_CATEGORY_AND_FILE.get((category, file_label))
        if not spec:
            continue
        seen_expected.add((spec.category, spec.filename))
        path = artifact_dir / spec.filename
        if not path.is_file():
            findings.append(_finding(spec.category, spec.filename, "missing_file"))
            continue
        if path.stat().st_size != entry.get("byteSize"):
            findings.append(_finding(spec.category, spec.filename, "byte_size_changed"))
        if _sha256_file(path) != entry.get("sha256"):
            findings.append(_finding(spec.category, spec.filename, "checksum_changed"))

    for spec in MANIFEST_SPECS:
        if (spec.category, spec.filename) not in seen_expected:
            findings.append(_finding(spec.category, spec.filename, "missing_manifest_entry"))

    return _verification_summary(artifact_dir, manifest_path, findings)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a sanitized checksum manifest.")
    create_parser.add_argument("--artifact-dir", required=True, help="Directory containing sanitized evidence artifacts.")
    create_parser.add_argument("--output", required=True, help="Manifest JSON output path.")

    verify_parser = subparsers.add_parser("verify", help="Verify a sanitized checksum manifest.")
    verify_parser.add_argument("--artifact-dir", required=True, help="Directory containing sanitized evidence artifacts.")
    verify_parser.add_argument("--manifest", required=True, help="Manifest JSON path.")

    args = parser.parse_args(argv)
    artifact_dir = Path(args.artifact_dir)

    if args.command == "create":
        manifest, findings = create_manifest(artifact_dir)
        output_path = Path(args.output)
        _write_json(output_path, manifest)
        summary = _verification_summary(artifact_dir, output_path, findings)
        _print_json(summary)
        return 0 if not findings else 1

    summary = verify_manifest(artifact_dir, Path(args.manifest))
    _print_json(summary)
    return 0 if summary["verificationStatus"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
