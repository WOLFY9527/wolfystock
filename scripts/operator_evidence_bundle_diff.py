#!/usr/bin/env python3
"""Compare sanitized operator evidence bundle summaries offline.

This helper consumes only the supplied sanitized bundle summaries and optional
checksum manifests. It renders a bounded Markdown review delta for manual
operator review and intentionally does not inspect artifact bodies, call
networks, change runtime behavior, or integrate with launch acceptance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APPROVAL_FORBIDDEN_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
    "public launch go",
    "release-approved",
)
SENSITIVE_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "db_url",
    "debug_payload",
    "dsn",
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
SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.:/+ -]+")
BLOCKING_STATUSES = {"missing", "needs-review", "rejected"}


@dataclass(frozen=True)
class EvidenceRecord:
    category: str
    status: str
    reasons: tuple[str, ...]


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


def _sanitize_status(value: Any) -> str:
    return _sanitize_text(value, default="unknown", max_length=48).lower()


def _sanitize_filename_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    label = Path(text).name
    sanitized = _sanitize_text(label, default="unknown", max_length=96)
    if sanitized == "[redacted]" or _looks_sensitive(sanitized):
        return "[redacted]"
    return sanitized


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable_to_read_json:{_sanitize_filename_label(path.name)}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{_sanitize_filename_label(path.name)}")
    return payload


def _list_from(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _reason_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    reasons = [_sanitize_text(reason, max_length=80) for reason in value]
    return tuple(reason for reason in reasons if reason)


def _collect_records(summary: dict[str, Any]) -> dict[str, EvidenceRecord]:
    records: dict[str, EvidenceRecord] = {}
    for item in _list_from(summary.get("artifacts")) + _list_from(summary.get("advisories")):
        category = _sanitize_text(item.get("category"), max_length=48)
        status = _sanitize_status(item.get("status"))
        reasons = _reason_list(item.get("blockingReasonSummaries"))
        records[category] = EvidenceRecord(category=category, status=status, reasons=reasons)
    return records


def _blocking_count(records: dict[str, EvidenceRecord]) -> int:
    return sum(1 for record in records.values() if record.status in BLOCKING_STATUSES or record.status != "accepted")


def _format_delta(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _format_category_list(categories: set[str]) -> str:
    if not categories:
        return "none"
    return ", ".join(f"`{category}`" for category in sorted(categories))


def _format_reasons(reasons: tuple[str, ...]) -> str:
    return ", ".join(reasons) if reasons else "none"


def _status_changes(before: dict[str, EvidenceRecord], after: dict[str, EvidenceRecord]) -> list[str]:
    rows: list[str] = []
    for category in sorted(set(before) & set(after)):
        before_status = before[category].status
        after_status = after[category].status
        if before_status != after_status:
            rows.append(f"- {category}: `{before_status}` -> `{after_status}`")
    return rows or ["- none"]


def _after_blockers(after: dict[str, EvidenceRecord]) -> list[str]:
    rows: list[str] = []
    for category in sorted(after):
        record = after[category]
        if record.status == "accepted":
            continue
        rows.append(f"- {category}: `{record.status}`; reasons: {_format_reasons(record.reasons)}")
    return rows or ["- none"]


def _manifest_entries(manifest: dict[str, Any] | None) -> dict[str, str]:
    if manifest is None:
        return {}
    entries: dict[str, str] = {}
    for entry in _list_from(manifest.get("entries")):
        label = _sanitize_filename_label(entry.get("fileLabel"))
        checksum = entry.get("sha256")
        entries[label] = checksum if isinstance(checksum, str) else ""
    return entries


def _checksum_changes(
    before_manifest: dict[str, Any] | None,
    after_manifest: dict[str, Any] | None,
) -> list[str]:
    if before_manifest is None or after_manifest is None:
        return ["- Manifest pair was not supplied; checksum delta not evaluated."]

    before = _manifest_entries(before_manifest)
    after = _manifest_entries(after_manifest)
    rows: list[str] = []
    for label in sorted(set(before) - set(after)):
        rows.append(f"- {label}: manifest entry removed")
    for label in sorted(set(after) - set(before)):
        rows.append(f"- {label}: manifest entry added")
    for label in sorted(set(before) & set(after)):
        if before[label] != after[label]:
            rows.append(f"- {label}: checksum changed")
    return rows or ["- none"]


def _assert_no_forbidden_phrases(markdown: str) -> None:
    lowered = markdown.lower()
    for phrase in APPROVAL_FORBIDDEN_PHRASES:
        if phrase in lowered:
            raise RuntimeError("diff_renderer_generated_forbidden_approval_phrase")


def render_diff(
    before_summary: dict[str, Any],
    after_summary: dict[str, Any],
    *,
    before_manifest: dict[str, Any] | None = None,
    after_manifest: dict[str, Any] | None = None,
) -> str:
    before_records = _collect_records(before_summary)
    after_records = _collect_records(after_summary)
    before_categories = set(before_records)
    after_categories = set(after_records)
    before_blocking = _blocking_count(before_records)
    after_blocking = _blocking_count(after_records)
    blocking_delta = after_blocking - before_blocking

    lines = [
        "# Offline Evidence Bundle Review Diff",
        "",
        "## Summary",
        f"- Before bundle status: `{_sanitize_status(before_summary.get('bundleStatus'))}`",
        f"- After bundle status: `{_sanitize_status(after_summary.get('bundleStatus'))}`",
        f"- Blocking count: `{before_blocking}` -> `{after_blocking}` (`{_format_delta(blocking_delta)}`)",
        "",
        "## Category Delta",
        f"- Added categories: {_format_category_list(after_categories - before_categories)}",
        f"- Removed categories: {_format_category_list(before_categories - after_categories)}",
        "",
        "## Status Changes",
        *_status_changes(before_records, after_records),
        "",
        "## Blocking / Needs-Review After",
        *_after_blockers(after_records),
        "",
        "## Manifest Checksum Delta",
        *_checksum_changes(before_manifest, after_manifest),
        "",
        "## Manual Review Required",
        "Manual operator review is required before any release decision.",
        "",
        "## Non-Approval Statement",
        "This diff is informational only and does not approve launch, deployment, or production operation.",
    ]
    markdown = "\n".join(lines).rstrip() + "\n"
    _assert_no_forbidden_phrases(markdown)
    return markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    diff_parser = subparsers.add_parser("diff", help="Compare two sanitized bundle summaries.")
    diff_parser.add_argument("--before", required=True, help="Earlier bundle summary JSON path.")
    diff_parser.add_argument("--after", required=True, help="Later bundle summary JSON path.")
    diff_parser.add_argument("--before-manifest", help="Optional earlier manifest JSON path.")
    diff_parser.add_argument("--after-manifest", help="Optional later manifest JSON path.")
    diff_parser.add_argument("--output", help="Optional Markdown output path.")

    args = parser.parse_args(argv)

    try:
        before_summary = _load_json(Path(args.before))
        after_summary = _load_json(Path(args.after))
        before_manifest = _load_json(Path(args.before_manifest)) if args.before_manifest else None
        after_manifest = _load_json(Path(args.after_manifest)) if args.after_manifest else None
        markdown = render_diff(
            before_summary,
            after_summary,
            before_manifest=before_manifest,
            after_manifest=after_manifest,
        )
        if args.output:
            Path(args.output).write_text(markdown, encoding="utf-8")
    except (RuntimeError, ValueError, OSError) as exc:
        print(_sanitize_text(exc, max_length=120), file=sys.stderr)
        return 2

    print(markdown, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
