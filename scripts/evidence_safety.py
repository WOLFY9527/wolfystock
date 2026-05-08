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
    return path.name


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
