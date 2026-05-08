# -*- coding: utf-8 -*-
"""Shared evidence safety helper tests."""

from __future__ import annotations

from pathlib import Path

from scripts.evidence_safety import (
    compact_key,
    finding,
    normalize_key,
    path_label,
    scan_json_tree,
)


def test_scan_json_tree_reports_sanitized_paths_without_raw_values() -> None:
    secret_value = "raw-secret-value-should-not-leak"
    findings = scan_json_tree(
        {"outer": [{"api-key": secret_value}, {"note": "launch-approved"}]},
        scan_key=lambda field, key: [finding(field, "secret_key")] if normalize_key(key) == "api_key" else [],
        scan_string=lambda field, value: [finding(field, "launch_claim")] if "launch-approved" in value else [],
    )

    assert findings == [
        {"field": "outer[0].api-key", "reasonCode": "secret_key"},
        {"field": "outer[1].note", "reasonCode": "launch_claim"},
    ]
    assert secret_value not in repr(findings)


def test_key_and_path_helpers_normalize_without_exposing_directories() -> None:
    assert normalize_key("Raw Request-Body") == "raw_request_body"
    assert compact_key("Launch Approved!") == "launchapproved"
    assert path_label(Path("/tmp/operator/unsafe-artifact.json")) == "unsafe-artifact.json"
