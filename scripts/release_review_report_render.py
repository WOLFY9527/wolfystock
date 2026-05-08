#!/usr/bin/env python3
"""Render an offline, sanitized release review report from summary JSON.

This helper consumes the bounded summary emitted by
operator_evidence_bundle_check.py and, when available, an optional manifest
summary. It renders Markdown for manual operator review only.

It does not call networks, read environment variables, inspect deployment
state, touch launch acceptance plumbing, emit raw artifact bodies, or approve a
launch decision.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


APPROVAL_FORBIDDEN_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
    "release-approved",
)
SENSITIVE_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "db_url",
    "password",
    "payload",
    "private_key",
    "request",
    "response",
    "secret",
    "session",
    "sk-",
    "stack trace",
    "stacktrace",
    "token",
    "traceback",
    "user_id",
    "userid",
)
SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.:/+ -]+")
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
BUNDLE_EXIT_OK = {"complete-review-required"}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable_to_read_json:{path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path.name}")
    return payload


def _looks_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in SENSITIVE_MARKERS + APPROVAL_FORBIDDEN_PHRASES)


def _sanitize_text(value: Any, *, default: str = "unknown", max_length: int = 96) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if _looks_sensitive(text):
        return "[redacted]"
    text = SAFE_TOKEN_RE.sub("_", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return default
    if len(text) > max_length:
        return f"{text[: max_length - 3]}..."
    return text


def _sanitize_filename_label(value: Any) -> str:
    text = _sanitize_text(Path(str(value or "")).name, default="unknown")
    if text == "[redacted]" or _looks_sensitive(text):
        return "[redacted]"
    return text


def _sanitize_status(value: Any) -> str:
    return _sanitize_text(value, default="unknown", max_length=48).lower()


def _reason_summary(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    reasons = [_sanitize_text(reason, max_length=80) for reason in value]
    safe_reasons = [reason for reason in reasons if reason]
    return ", ".join(safe_reasons) if safe_reasons else "none"


def _list_from(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _review_posture(bundle_status: str) -> str:
    if bundle_status == "complete-review-required":
        return "Current operator review posture: **manual review required**."
    if bundle_status == "incomplete-no-go":
        return "Current operator review posture: **NO-GO - incomplete evidence bundle**."
    if bundle_status == "rejected-no-go":
        return "Current operator review posture: **NO-GO - blocking evidence rejection present**."
    return "Current operator review posture: **NO-GO - unrecognized evidence status**."


def _blocking_summary(bundle: dict[str, Any]) -> list[str]:
    rows = []
    for item in _list_from(bundle.get("artifacts")) + _list_from(bundle.get("advisories")):
        status = _sanitize_status(item.get("status"))
        if status in {"accepted"}:
            continue
        category = _sanitize_text(item.get("category"), max_length=48)
        reasons = _reason_summary(item.get("blockingReasonSummaries"))
        rows.append(f"- `{category}`: `{status}`; reasons: {reasons}")
    return rows or ["- No blocking or needs-review category summaries were present in the supplied summary."]


def _render_category_table(bundle: dict[str, Any]) -> list[str]:
    lines = [
        "| Category | Status | Artifact label | Validator | Reason summaries |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in _list_from(bundle.get("artifacts")):
        category = _sanitize_text(item.get("category"), max_length=48)
        status = _sanitize_status(item.get("status"))
        path_label = _sanitize_filename_label(item.get("pathLabel"))
        validator = _sanitize_filename_label(item.get("validatorName"))
        reasons = _reason_summary(item.get("blockingReasonSummaries"))
        lines.append(f"| {category} | {status} | {path_label} | {validator} | {reasons} |")
    advisories = _list_from(bundle.get("advisories"))
    if advisories:
        lines.append("")
        lines.append("Advisories:")
        for advisory in advisories:
            category = _sanitize_text(advisory.get("category"), max_length=48)
            status = _sanitize_status(advisory.get("status"))
            reasons = _reason_summary(advisory.get("blockingReasonSummaries"))
            lines.append(f"- `{category}`: `{status}`; reasons: {reasons}")
    return lines


def _render_manifest(manifest: dict[str, Any] | None) -> list[str]:
    if manifest is None:
        return ["Manifest/checksum summary was not supplied."]

    status = _sanitize_status(
        manifest.get("manifestStatus")
        or manifest.get("status")
        or manifest.get("bundleStatus")
        or manifest.get("checksumStatus")
    )
    checksum_status = _sanitize_status(manifest.get("checksumStatus"))
    checksum_algorithm = _sanitize_text(manifest.get("checksumAlgorithm"), default="not-supplied", max_length=32)
    artifact_count = _sanitize_text(manifest.get("artifactCount"), default="not-supplied", max_length=24)
    reasons = _reason_summary(manifest.get("blockingReasonSummaries"))
    return [
        f"- Manifest status: `{status}`",
        f"- Artifact count: `{artifact_count}`",
        f"- Checksum algorithm: `{checksum_algorithm}`",
        f"- Checksum status: `{checksum_status}`",
        f"- Reason summaries: {reasons}",
    ]


def _assert_no_forbidden_phrases(markdown: str) -> None:
    lowered = markdown.lower()
    for phrase in APPROVAL_FORBIDDEN_PHRASES:
        if phrase in lowered:
            raise RuntimeError("renderer_generated_forbidden_approval_phrase")


def render_report(
    bundle: dict[str, Any],
    *,
    manifest: dict[str, Any] | None = None,
    release_candidate_label: str | None = None,
    release_candidate_sha: str | None = None,
) -> str:
    bundle_status = _sanitize_status(bundle.get("bundleStatus"))
    label = _sanitize_text(release_candidate_label, default="not supplied")
    sha = _sanitize_text(release_candidate_sha, default="not supplied", max_length=64)
    if sha != "not supplied" and not SHA_RE.match(sha):
        sha = "[redacted]"

    lines = [
        "# Offline Release Review Report",
        "",
        "## Release Candidate",
        f"- Label: `{label}`",
        f"- SHA: `{sha}`",
        "",
        "## Evidence Bundle Status",
        f"- Bundle status: **{bundle_status}**",
        f"- Generated at: `{_sanitize_text(bundle.get('generatedAt'), default='not supplied')}`",
        f"- Artifact directory label: `{_sanitize_filename_label(bundle.get('artifactDirectoryLabel'))}`",
        _review_posture(bundle_status),
        "",
        "## Category Status Table",
        *_render_category_table(bundle),
        "",
        "## Blocking / Needs-Review Summary",
        *_blocking_summary(bundle),
        "",
        "## Manifest / Checksum Summary",
        *_render_manifest(manifest),
        "",
        "## Manual Review Required",
        "Manual operator review is required before any release decision.",
        "",
        "## Non-Approval Statement",
        "This report is informational only and does not approve launch.",
    ]
    markdown = "\n".join(lines).rstrip() + "\n"
    _assert_no_forbidden_phrases(markdown)
    return markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_summary", help="Path to operator evidence bundle summary JSON.")
    parser.add_argument("--manifest", help="Optional manifest summary JSON path.")
    parser.add_argument("--release-candidate-label", help="Optional release candidate label.")
    parser.add_argument("--release-candidate-sha", help="Optional release candidate commit SHA.")
    args = parser.parse_args(argv)

    try:
        bundle = _load_json(Path(args.bundle_summary))
        manifest = _load_json(Path(args.manifest)) if args.manifest else None
        markdown = render_report(
            bundle,
            manifest=manifest,
            release_candidate_label=args.release_candidate_label,
            release_candidate_sha=args.release_candidate_sha,
        )
    except (RuntimeError, ValueError) as exc:
        print(_sanitize_text(exc, max_length=120), file=sys.stderr)
        return 2

    print(markdown, end="")
    bundle_status = _sanitize_status(bundle.get("bundleStatus"))
    return 0 if bundle_status in BUNDLE_EXIT_OK else 1


if __name__ == "__main__":
    sys.exit(main())
