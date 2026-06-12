#!/usr/bin/env python3
"""Neutral helpers for offline evidence validators.

This module intentionally owns only traversal and sanitized labels. Each
validator keeps its own marker vocabulary, reason codes, and schema rules.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


Finding = dict[str, str]
ScanCallback = Callable[[str, Any], list[Finding]]
EntryScanCallback = Callable[[str, Any, Any], list[Finding]]

UNSAFE_LABEL_MARKERS = (
    "../",
    "..\\",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "account_label",
    "account_name",
    "account_ref",
    "broker_account",
    "broker_url",
    "cookie",
    "credential",
    "database_url",
    "db_url",
    "dedup_hash",
    "debug_payload",
    "exec_id",
    "execution_id",
    "fingerprint",
    "import_fingerprint",
    "order_id",
    "order_ref",
    "password",
    "payload",
    "private_key",
    "raw",
    "request",
    "request_id",
    "response",
    "secret",
    "session",
    "set-cookie",
    "sk-",
    "stack trace",
    "stacktrace",
    "token",
    "traceback",
    "webhook",
)
FORBIDDEN_APPROVAL_LABEL_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
    "public launch go",
    "go for launch",
    "approved for launch",
    "release-approved",
)


def finding(field: str, reason_code: str, *, field_key: str = "field") -> Finding:
    return {field_key: field, "reasonCode": reason_code}


def normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def matches_marker(value: Any, markers: Sequence[str]) -> bool:
    normalized = normalize_key(value)
    compacted = compact_key(value)
    for marker in markers:
        marker_normalized = normalize_key(marker)
        marker_compacted = compact_key(marker)
        if marker_normalized and marker_normalized in normalized:
            return True
        if marker_compacted and marker_compacted in compacted:
            return True
    return False


def join_path(parent: str, key: str) -> str:
    if parent in {"", "$"}:
        return key
    return f"{parent}.{key}"


def path_label(path: Path) -> str:
    label = path.name
    lowered = label.lower()
    normalized = normalize_key(label)
    compacted = compact_key(label)
    if any(
        marker in lowered or marker in normalized or marker.replace("_", "") in compacted
        for marker in UNSAFE_LABEL_MARKERS + FORBIDDEN_APPROVAL_LABEL_PHRASES
    ):
        return "[redacted]"
    return label


def read_json_document(
    path: Path,
    *,
    failure_reason_code: str,
    field: str = "$",
    field_key: str = "field",
) -> tuple[Any | None, list[Finding]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, json.JSONDecodeError):
        return None, [finding(field, failure_reason_code, field_key=field_key)]


def is_iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def missing_fields(mapping: Mapping[str, Any], required_fields: Sequence[str]) -> list[str]:
    return [field for field in required_fields if field not in mapping]


def required_field_findings(
    mapping: Mapping[str, Any],
    required_fields: Sequence[str],
    *,
    parent: str = "",
    reason_code: str = "missing_required_field",
    field_key: str = "field",
) -> list[Finding]:
    return [
        finding(join_path(parent, field), reason_code, field_key=field_key)
        for field in missing_fields(mapping, required_fields)
    ]


def scan_json_tree(
    value: Any,
    *,
    field: str = "$",
    scan_key: ScanCallback | None = None,
    scan_entry: EntryScanCallback | None = None,
    scan_string: ScanCallback | None = None,
    recurse_on_key_findings: bool = True,
) -> list[Finding]:
    findings: list[Finding] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_field = join_path(field, key_text)
            key_findings = scan_key(child_field, key) if scan_key else []
            if scan_entry:
                key_findings.extend(scan_entry(child_field, key, child))
            findings.extend(key_findings)
            if key_findings and not recurse_on_key_findings:
                continue
            findings.extend(
                scan_json_tree(
                    child,
                    field=child_field,
                    scan_key=scan_key,
                    scan_entry=scan_entry,
                    scan_string=scan_string,
                    recurse_on_key_findings=recurse_on_key_findings,
                )
            )
        return findings
    if isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(
                scan_json_tree(
                    child,
                    field=f"{field}[{index}]",
                    scan_key=scan_key,
                    scan_entry=scan_entry,
                    scan_string=scan_string,
                    recurse_on_key_findings=recurse_on_key_findings,
                )
            )
        return findings
    if isinstance(value, str) and scan_string:
        findings.extend(scan_string(field, value))
    return findings
