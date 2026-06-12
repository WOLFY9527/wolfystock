#!/usr/bin/env python3
"""Neutral helpers for offline evidence validators.

This module intentionally owns only traversal and sanitized labels. Each
validator keeps its own marker vocabulary, reason codes, and schema rules.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable


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
