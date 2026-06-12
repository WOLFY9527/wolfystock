# -*- coding: utf-8 -*-
"""Shared evidence safety helper tests."""

from __future__ import annotations

from pathlib import Path

from scripts.evidence_safety import (
    compact_key,
    finding,
    is_iso_timestamp,
    matches_marker,
    missing_fields,
    normalize_key,
    path_label,
    read_json_document,
    required_field_findings,
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


def test_path_label_redacts_broker_order_account_artifact_names() -> None:
    assert path_label(Path("/tmp/operator/brokerAccountRef-U1234567.json")) == "[redacted]"
    assert path_label(Path("/tmp/operator/order-id-fixture-must-not-leak.json")) == "[redacted]"
    assert path_label(Path("/tmp/operator/execution_id-fixture-must-not-leak.json")) == "[redacted]"


def test_read_json_document_returns_sanitized_failure(tmp_path: Path) -> None:
    invalid_value = "not-json-should-not-leak"
    artifact = tmp_path / "operator-secret-artifact.json"
    artifact.write_text(invalid_value, encoding="utf-8")

    value, findings = read_json_document(
        artifact,
        failure_reason_code="artifact_read_failed",
    )

    assert value is None
    assert findings == [{"field": "$", "reasonCode": "artifact_read_failed"}]
    assert invalid_value not in repr(findings)
    assert str(artifact) not in repr(findings)


def test_required_field_helpers_build_sanitized_paths() -> None:
    payload = {"present": True}

    assert missing_fields(payload, ("present", "missing")) == ["missing"]
    assert required_field_findings(payload, ("present", "missing"), parent="category") == [
        {"field": "category.missing", "reasonCode": "missing_required_field"}
    ]
    assert required_field_findings(
        payload,
        ("present", "missing"),
        parent="category",
        field_key="path",
        reason_code="required",
    ) == [{"path": "category.missing", "reasonCode": "required"}]


def test_is_iso_timestamp_accepts_z_and_offsets_without_accepting_non_strings() -> None:
    assert is_iso_timestamp("2026-06-12T10:20:30Z") is True
    assert is_iso_timestamp("2026-06-12T10:20:30+00:00") is True
    assert is_iso_timestamp("2026-06-12") is True
    assert is_iso_timestamp("not-a-timestamp") is False
    assert is_iso_timestamp(True) is False
    assert is_iso_timestamp("") is False


def test_matches_marker_preserves_label_marker_matching_modes() -> None:
    markers = ("api_key", "launch-approved", "account_ref")

    assert matches_marker("contains API Key", markers) is True
    assert matches_marker("launch-approved evidence", markers) is True
    assert matches_marker("brokerAccountRef-U1234567.json", markers) is True
    assert matches_marker("safe-artifact.json", markers) is False
