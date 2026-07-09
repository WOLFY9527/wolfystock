#!/usr/bin/env python3
"""Sanitize one offline operator evidence JSON artifact for manual review.

The sanitizer reads only the operator-provided JSON path, writes a redacted copy
unless --in-place is explicitly supplied, and emits bounded findings. It does
not call networks, read environment state, inspect credentials, mutate runtime
configuration, or integrate with launch acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from evidence_safety import compact_key
    from evidence_safety import join_path
    from evidence_safety import normalize_key
    from evidence_safety import path_label
    from evidence_safety import scan_json_tree
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import compact_key
    from scripts.evidence_safety import join_path
    from scripts.evidence_safety import normalize_key
    from scripts.evidence_safety import path_label
    from scripts.evidence_safety import scan_json_tree


SCHEMA_VERSION = "wolfystock_evidence_artifact_sanitizer_v1"
REDACTED = "<redacted>"

SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "database_url",
    "db_url",
    "dsn",
    "password",
    "passwd",
    "private_key",
    "secret",
    "session",
    "set_cookie",
    "token",
    "webhook",
)
SAFE_STRUCTURAL_KEYS = {
    "credentialbearingurlsincluded",
    "credentialpresence",
    "credentialpresenceonly",
    "credentialvaluesredacted",
    "productionsecretsread",
    "rawartifactbodiesincluded",
    "rawlogsincluded",
    "secretpresencesummary",
}
RAW_KEY_MARKERS = (
    "broker_order_payload",
    "brokerorderpayload",
    "broker_payload",
    "brokerpayload",
    "debug_payload",
    "debug_trace",
    "execution_payload",
    "executionpayload",
    "log_dump",
    "order_payload",
    "orderpayload",
    "provider_payload",
    "raw_log",
    "raw_payload",
    "raw_request",
    "raw_request_body",
    "raw_response",
    "raw_response_body",
    "request_body",
    "response_body",
    "stack_trace",
    "stacktrace",
    "traceback",
)
BROKER_ORDER_IDENTITY_KEY_MARKERS = (
    "account_id",
    "account_ref",
    "account_number",
    "accountid",
    "accountnumber",
    "accountref",
    "broker_account_id",
    "broker_account_ref",
    "broker_account_number",
    "broker_order_id",
    "broker_position_ref",
    "brokeraccountid",
    "brokeraccountnumber",
    "brokeraccountref",
    "brokerorderid",
    "brokerpositionref",
    "exec_id",
    "execid",
    "execution_id",
    "executionid",
    "order_id",
    "order_ref",
    "orderid",
    "orderref",
    "perm_id",
    "permid",
    "request_id",
    "requestid",
    "trade_id",
    "trade_uid",
    "tradeid",
    "tradeuid",
)
ACCOUNT_METADATA_KEY_MARKERS = (
    "account_alias",
    "account_label",
    "account_metadata",
    "account_name",
    "account_profile",
    "accountalias",
    "accountlabel",
    "accountmetadata",
    "accountname",
    "accountprofile",
    "broker_account_metadata",
    "brokeraccountmetadata",
)
ENDPOINT_URL_KEY_MARKERS = (
    "api_base_url",
    "api_url",
    "apibaseurl",
    "apiurl",
    "base_url",
    "baseurl",
    "broker_api_url",
    "brokerapiurl",
    "broker_url",
    "brokerurl",
    "callback_url",
    "callbackurl",
    "endpoint_url",
    "endpointurl",
    "request_url",
    "requesturl",
)
APPROVAL_BOOLEAN_KEYS = {
    "approvalboolean",
    "approvedforlaunch",
    "automaticgo",
    "go",
    "goforlaunch",
    "launchapproved",
    "publiclaunchgo",
    "releaseapproved",
}

SECRET_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*-----END [A-Z ]*PRIVATE KEY-----", re.IGNORECASE | re.DOTALL),
    ),
    (
        "secret_marker",
        re.compile(
            r"\b(?:api[-_\s]?key|apikey|authorization|bearer|cookie|password|passwd|"
            r"secret|session|set-cookie|token)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_marker",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    ),
    (
        "secret_marker",
        re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b"),
    ),
)
RAW_VALUE_PATTERN = re.compile(
    r"\b(?:raw[-_\s]?(?:request|response|payload|log)|raw[-_\s]?request[-_\s]?body|"
    r"raw[-_\s]?response[-_\s]?body|debug[-_\s]?(?:payload|trace)|provider[-_\s]?payload|"
    r"stack trace|stacktrace|traceback|db dump|database dump)\b",
    re.IGNORECASE,
)
BROKER_ORDER_IDENTITY_VALUE_PATTERN = re.compile(
    r"\b(?:broker[-_\s]?account[-_\s]?(?:ref|id|number|label)|"
    r"account[-_\s]?(?:ref|number|label)|order[-_\s]?(?:id|ref)|"
    r"request[-_\s]?id|execution[-_\s]?id|exec[-_\s]?id|perm[-_\s]?id|trade[-_\s]?uid)\b"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)
CREDENTIAL_URL_PATTERNS = (
    re.compile(r"\bhttps?://[^/\s:@]+:[^@\s]+@[^/\s]+", re.IGNORECASE),
    re.compile(r"\bhttps?://[^\s?#]+[?][^\s]*(?:api[_-]?key|token|secret|password|session|cookie)=", re.IGNORECASE),
)
ENDPOINT_URL_PATTERN = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)
PATH_TRAVERSAL_PATTERN = re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)|\.\.[\\/]")
SENSITIVE_ABSOLUTE_PATH_PATTERN = re.compile(r"^/(?:etc|home|private|root|Users|var)/(?:\S+)")
APPROVAL_WORDING_PATTERN = re.compile(
    r"\b(?:launch[-_\s]?approved|production[-_\s]?ready|automatic[-_\s]?go|"
    r"public\s+launch\s+go|go\s+for\s+launch|launch\s+go|approved\s+for\s+launch|"
    r"release[-_\s]?approved)\b",
    re.IGNORECASE,
)
UNSAFE_PATH_MARKERS = (
    tuple(SECRET_KEY_MARKERS)
    + tuple(RAW_KEY_MARKERS)
    + tuple(BROKER_ORDER_IDENTITY_KEY_MARKERS)
    + tuple(ACCOUNT_METADATA_KEY_MARKERS)
    + tuple(ENDPOINT_URL_KEY_MARKERS)
    + ("../", "..\\")
)


@dataclass(frozen=True)
class UnsafeMatch:
    category: str
    reason_code: str


@dataclass(frozen=True)
class UnsafeFinding:
    field: str
    category: str
    reason_code: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _matches_marker(key: Any, markers: tuple[str, ...]) -> bool:
    normalized = normalize_key(key)
    compacted = compact_key(key)
    for marker in markers:
        marker_normalized = normalize_key(marker)
        marker_compacted = compact_key(marker)
        if marker_normalized and marker_normalized in normalized:
            return True
        if marker_compacted and marker_compacted in compacted:
            return True
    return False


def _key_matches(key: Any) -> list[UnsafeMatch]:
    normalized = normalize_key(key)
    if normalized in SAFE_STRUCTURAL_KEYS or compact_key(key) in SAFE_STRUCTURAL_KEYS:
        return []
    if _matches_marker(key, RAW_KEY_MARKERS):
        return [UnsafeMatch("raw_body_or_log", "raw_or_debug_key")]
    if _matches_marker(key, SECRET_KEY_MARKERS):
        return [UnsafeMatch("secret_marker", "secret_key_marker")]
    if _matches_marker(key, BROKER_ORDER_IDENTITY_KEY_MARKERS):
        return [UnsafeMatch("broker_order_identity", "broker_order_identity_key")]
    if _matches_marker(key, ACCOUNT_METADATA_KEY_MARKERS):
        return [UnsafeMatch("account_metadata", "account_metadata_key")]
    if _matches_marker(key, ENDPOINT_URL_KEY_MARKERS):
        return [UnsafeMatch("endpoint_url", "endpoint_url_key")]
    return []


def _entry_matches(key: Any, child: Any) -> list[UnsafeMatch]:
    if child is True and compact_key(key) in APPROVAL_BOOLEAN_KEYS:
        return [UnsafeMatch("approval_wording", "approval_boolean_forbidden")]
    return []


def _string_matches(value: str) -> list[UnsafeMatch]:
    matches: list[UnsafeMatch] = []
    for category, pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            matches.append(UnsafeMatch(category, "secret_value_marker"))
            break
    if RAW_VALUE_PATTERN.search(value):
        matches.append(UnsafeMatch("raw_body_or_log", "raw_or_debug_value"))
    if BROKER_ORDER_IDENTITY_VALUE_PATTERN.search(value):
        matches.append(UnsafeMatch("broker_order_identity", "broker_order_identity_value"))
    if any(pattern.search(value) for pattern in CREDENTIAL_URL_PATTERNS):
        matches.append(UnsafeMatch("credential_url", "credential_url_value"))
    elif ENDPOINT_URL_PATTERN.search(value):
        matches.append(UnsafeMatch("endpoint_url", "endpoint_url_value"))
    if PATH_TRAVERSAL_PATTERN.search(value) or SENSITIVE_ABSOLUTE_PATH_PATTERN.search(value):
        matches.append(UnsafeMatch("path_traversal", "unsafe_path_value"))
    if APPROVAL_WORDING_PATTERN.search(value):
        matches.append(UnsafeMatch("approval_wording", "approval_wording_forbidden"))
    return matches


def _scan_key(field: str, key: Any) -> list[dict[str, str]]:
    return [
        {"field": field, "category": match.category, "reasonCode": match.reason_code}
        for match in _key_matches(key)
    ]


def _scan_entry(field: str, key: Any, child: Any) -> list[dict[str, str]]:
    return [
        {"field": field, "category": match.category, "reasonCode": match.reason_code}
        for match in _entry_matches(key, child)
    ]


def _scan_string(field: str, value: Any) -> list[dict[str, str]]:
    return [
        {"field": field, "category": match.category, "reasonCode": match.reason_code}
        for match in _string_matches(value)
    ]


def _collect_findings(value: Any) -> list[UnsafeFinding]:
    raw_findings = scan_json_tree(
        value,
        scan_key=_scan_key,
        scan_entry=_scan_entry,
        scan_string=_scan_string,
        recurse_on_key_findings=False,
    )
    deduped: dict[tuple[str, str, str], UnsafeFinding] = {}
    for item in raw_findings:
        finding = UnsafeFinding(
            field=str(item["field"]),
            category=str(item["category"]),
            reason_code=str(item["reasonCode"]),
        )
        deduped[(finding.field, finding.category, finding.reason_code)] = finding
    return sorted(deduped.values(), key=lambda finding: (finding.field, finding.category, finding.reason_code))


def _contains_unsafe_path_marker(field: str) -> bool:
    lowered = field.lower()
    normalized = normalize_key(field)
    return any(marker in lowered or marker in normalized for marker in UNSAFE_PATH_MARKERS)


def _safe_finding_field(field: str, index: int) -> str:
    if _contains_unsafe_path_marker(field) or Path(field).is_absolute():
        return f"field_{index:04d}"
    return field or f"field_{index:04d}"


def _sanitize_findings(findings: list[UnsafeFinding]) -> list[dict[str, str]]:
    return [
        {
            "field": _safe_finding_field(finding.field, index),
            "category": finding.category,
            "reasonCode": finding.reason_code,
        }
        for index, finding in enumerate(findings, start=1)
    ]


def _summary_counts(findings: list[UnsafeFinding]) -> dict[str, Any]:
    counts = Counter(finding.category for finding in findings)
    return {
        "totalFindings": len(findings),
        "countsByCategory": dict(sorted(counts.items())),
    }


def _sanitize_value(value: Any, *, field: str = "$", force_redact: bool = False) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            child_field = join_path(field, key_text)
            child_force = force_redact or bool(_key_matches(key_text)) or bool(_entry_matches(key_text, child))
            sanitized[key_text] = _sanitize_value(child, field=child_field, force_redact=child_force)
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize_value(child, field=f"{field}[{index}]", force_redact=force_redact)
            for index, child in enumerate(value)
        ]
    if force_redact:
        return REDACTED
    if isinstance(value, str) and _string_matches(value):
        return REDACTED
    return value


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] input file not found: {path_label(path)}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise SystemExit(f"[FAIL] input file is not readable JSON: {path_label(path)}")


def _default_output_path(input_path: Path) -> Path:
    suffix = input_path.suffix
    if suffix:
        return input_path.with_name(f"{input_path.stem}.sanitized{suffix}")
    return input_path.with_name(f"{input_path.name}.sanitized")


def _canonical_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _paths_alias(left: Path, right: Path) -> bool:
    try:
        if left.exists() and right.exists() and left.samefile(right):
            return True
    except OSError:
        pass
    return _canonical_path(left) == _canonical_path(right)


def _destination_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _in_place_write_path(input_path: Path) -> Path:
    if not input_path.is_symlink():
        return input_path
    try:
        return input_path.resolve(strict=True)
    except OSError as exc:
        raise SystemExit(f"[FAIL] input file not found: {path_label(input_path)}") from exc


def _serialized_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _fsync_parent_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise SystemExit(f"[FAIL] write failed: {path_label(path)}") from exc

    try:
        os.replace(temp_path, path)
        temp_path = None
        _fsync_parent_directory(path)
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise SystemExit(f"[FAIL] replacement failed: {path_label(path)}") from exc


def _write_json_atomic(path: Path, payload: Any) -> None:
    _write_text_atomic(path, _serialized_json(payload))


def _build_report(
    *,
    mode: str,
    input_path: Path,
    output_path: Path | None,
    findings: list[UnsafeFinding],
    source_artifact_mutated: bool,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": _now_iso(),
        "mode": mode,
        "sanitizerStatus": "needs-review",
        "inputLabel": path_label(input_path),
        "outputLabel": path_label(output_path) if output_path else None,
        "runtimeBehaviorChanged": False,
        "networkCallsExecuted": False,
        "rawArtifactBodiesIncluded": False,
        "sourceArtifactMutated": source_artifact_mutated,
        "reviewOnly": True,
        "findings": _sanitize_findings(findings),
        "summary": _summary_counts(findings),
    }


def _print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _sanitize_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = input_path if args.in_place else Path(args.output) if args.output else _default_output_path(input_path)

    if args.in_place and args.output:
        raise SystemExit("[FAIL] --in-place cannot be combined with --output")
    if args.in_place and args.overwrite:
        raise SystemExit("[FAIL] --overwrite cannot be combined with --in-place")
    if not args.in_place and _paths_alias(input_path, output_path):
        raise SystemExit("[FAIL] input/output alias rejected; use --in-place for explicit source mutation")
    if not args.in_place and _destination_exists(output_path) and not args.overwrite:
        raise SystemExit("[FAIL] output already exists; pass --overwrite to replace it")

    payload = _load_json(input_path)
    findings = _collect_findings(payload)
    write_path = _in_place_write_path(input_path) if args.in_place else output_path
    _write_json_atomic(write_path, _sanitize_value(payload))
    report = _build_report(
        mode="sanitize",
        input_path=input_path,
        output_path=output_path,
        findings=findings,
        source_artifact_mutated=args.in_place,
    )
    _print_report(report)
    return 1 if args.fail_on_findings and findings else 0


def _scan_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    payload = _load_json(input_path)
    findings = _collect_findings(payload)
    report = _build_report(
        mode="scan",
        input_path=input_path,
        output_path=None,
        findings=findings,
        source_artifact_mutated=False,
    )
    _print_report(report)
    return 1 if args.fail_on_findings and findings else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sanitize = subparsers.add_parser("sanitize", help="write a redacted JSON copy and print bounded findings")
    sanitize.add_argument("--input", required=True, help="Operator-provided JSON artifact path.")
    sanitize.add_argument("--output", help="Separate sanitized JSON output path. Defaults to a sibling *.sanitized* path.")
    sanitize.add_argument("--in-place", action="store_true", help="Overwrite the input artifact with the sanitized copy.")
    sanitize.add_argument("--overwrite", action="store_true", help="Explicitly replace an existing non-in-place output path.")
    sanitize.add_argument("--fail-on-findings", action="store_true", help="Exit non-zero when unsafe markers were found.")
    sanitize.set_defaults(func=_sanitize_command)

    scan = subparsers.add_parser("scan", help="print sanitized findings only")
    scan.add_argument("--input", required=True, help="Operator-provided JSON artifact path.")
    scan.add_argument("--fail-on-findings", action="store_true", help="Exit non-zero when unsafe markers were found.")
    scan.set_defaults(func=_scan_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
