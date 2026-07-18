#!/usr/bin/env python3
"""Synthetic staging ingress smoke preflight.

The script is safe by default: without WOLFYSTOCK_STAGING_INGRESS_SMOKE=1 it
does not open sockets and emits dry-run evidence for launch review.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OPT_IN_ENV = "WOLFYSTOCK_STAGING_INGRESS_SMOKE"
BASE_URLS_ENV = "WOLFYSTOCK_STAGING_INGRESS_BASE_URLS"
TIMEOUT_ENV = "WOLFYSTOCK_STAGING_INGRESS_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_BODY_BYTES = 64_000
OPERATOR_EVIDENCE_SCHEMA_VERSION = "wolfystock_staging_ingress_operator_evidence_v1"
TARGET_ENV_EVIDENCE_MODE = "target-environment-https-ingress"
SAFE_PLACEHOLDERS = {"", "[redacted]", "redacted", "<redacted>", "***", "sanitized", "none"}
SAFE_FALSE_MARKER_KEYS = {
    "rawResponseBodiesIncluded",
    "tokensIncluded",
    "cookiesIncluded",
    "secretsIncluded",
    "dsnsIncluded",
    "apiKeysIncluded",
    "providerPayloadsIncluded",
    "debugTracesIncluded",
    "credentialBearingUrlsIncluded",
    "backendPort8000Public",
    "customerDataUsed",
    "releaseApproved",
    "publicLaunchReady",
}
PRIVATE_HOST_OR_IP_PATTERN = re.compile(
    r"\b(?:localhost|(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:local|internal|lan|private))\b",
    re.IGNORECASE,
)

SENSITIVE_BODY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("api_key", re.compile(r"(?i)[\"']?\bapi[_\s-]?key\b[\"']?\s*[:=]")),
    ("secret", re.compile(r"(?i)[\"']?\bsecret\b[\"']?\s*[:=]")),
    ("password", re.compile(r"(?i)[\"']?\bpass(?:word|wd)?\b[\"']?\s*[:=]")),
    (
        "token",
        re.compile(
            r"(?i)(?:[\"']?\b(?:token|session[_\s-]?id)\b[\"']?\s*[:=]\s*[\"']?|"
            r"\bbearer\s+)[a-z0-9._~+/=-]{12,}"
        ),
    ),
    ("openai_key", re.compile(r"(?i)\bsk-[a-z0-9_-]{24,}\b")),
    ("github_token", re.compile(r"(?i)\bgh[pousr]_[a-z0-9_]{24,}\b")),
    ("slack_token", re.compile(r"(?i)\bxox[baprs]-[a-z0-9-]{20,}\b")),
    (
        "debug_payload",
        re.compile(
            r"(?i)\b(?:raw|debug|provider)[_\s-]+(?:payload|response)\b|"
            r"debug_payload|provider_payload|raw_payload|stack trace|traceback"
        ),
    ),
    ("credential_bearing_url", re.compile(r"(?i)\bhttps?://[^\s?#]+[?][^\s]+")),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_timeout(raw_value: str | None) -> float:
    if raw_value is None or raw_value == "":
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw_value)
    except ValueError:
        raise SystemExit(f"[FAIL] Invalid timeout value for {TIMEOUT_ENV}: expected seconds")
    if timeout <= 0 or timeout > 30:
        raise SystemExit(f"[FAIL] Invalid timeout value for {TIMEOUT_ENV}: expected 0 < seconds <= 30")
    return timeout


def _split_base_urls(values: list[str], env_value: str | None) -> list[str]:
    collected: list[str] = []
    for value in values:
        collected.extend(part.strip() for part in value.split(","))
    if env_value:
        collected.extend(part.strip() for part in env_value.split(","))
    return [value for value in collected if value]


def _clean_base_url(raw_url: str) -> str:
    parsed = urllib.parse.urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must include http(s) scheme and host")
    if parsed.username or parsed.password:
        raise ValueError("base URL must not include credentials")
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _display_url(raw_url: str) -> str:
    try:
        return _clean_base_url(raw_url)
    except ValueError:
        parsed = urllib.parse.urlsplit(raw_url)
        if parsed.scheme and parsed.netloc:
            return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        return "<invalid-url>"


def _join_url(base_url: str, path: str) -> str:
    clean_base = _clean_base_url(base_url)
    return f"{clean_base}{path}"


def _find_sensitive_pattern(body: str) -> str | None:
    for reason_code, pattern in SENSITIVE_BODY_PATTERNS:
        if pattern.search(body):
            return reason_code
    return None


def _load_json_payload(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] Evidence file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] Evidence file is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("[FAIL] Evidence file must contain a JSON object")
    return payload


def _safe_placeholder(value: Any) -> bool:
    return str(value).strip().lower() in SAFE_PLACEHOLDERS


def _safe_host_label(value: Any) -> bool:
    label = str(value or "").strip()
    if not label or any(marker in label for marker in ("://", "/", "?", "#", "@", ":")):
        return False
    if ".." in label:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,252}", label))


def _safe_reason_code(value: Any) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_.:-]+", str(value or "")))


def _public_ports_are_80_443(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    ports = value.get("publicPorts")
    return isinstance(ports, list) and set(ports) == {80, 443} and value.get("onlyPublicPorts80And443") is True


def _manual_review_ready(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return value.get("reviewRequired") is True and str(value.get("state") or "").strip() in {
        "ready-for-manual-review",
        "accepted-for-manual-review",
    }


def _find_sensitive_value(value: Any, *, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = f"{path}.{key_text}" if path else key_text
            normalized_key = key_text.lower().replace("-", "_")
            if key_text in SAFE_FALSE_MARKER_KEYS and nested is False:
                continue
            if isinstance(nested, str) and any(marker in normalized_key for marker in ("token", "secret", "password", "cookie", "session", "dsn", "private_key", "response_body", "provider_payload", "raw_payload", "debug_trace", "stack_trace")):
                if not _safe_placeholder(nested):
                    findings.append({"path": nested_path, "reasonCode": "sensitive_key_contains_value"})
                    continue
            findings.extend(_find_sensitive_value(nested, path=nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_find_sensitive_value(nested, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        if _safe_placeholder(value):
            return findings
        if PRIVATE_HOST_OR_IP_PATTERN.search(value):
            findings.append({"path": path or "$", "reasonCode": "private_host_or_ip"})
            return findings
        if re.search(r"(?i)\bhttps?://[^\s?#]+[?][^\s]+", value):
            findings.append({"path": path or "$", "reasonCode": "credential_bearing_url"})
            return findings
        if re.search(r"(?i)\bhttps?://[^\s\"']+", value):
            findings.append({"path": path or "$", "reasonCode": "raw_url"})
            return findings
        for reason_code, pattern in SENSITIVE_BODY_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path or "$", "reasonCode": reason_code})
                break
    return findings


def _operator_result_from_summary(payload: dict[str, Any], name: str) -> dict[str, Any]:
    summary = payload.get("resultSummary") if isinstance(payload.get("resultSummary"), dict) else {}
    result = summary.get(name) if isinstance(summary.get(name), dict) else {}
    status = str(result.get("status") or "missing")
    reason_code = str(result.get("reasonCode") or "missing")
    status_code = result.get("statusCode")
    evidence: dict[str, Any] = {
        "status": status,
        "reasonCode": reason_code,
    }
    if isinstance(status_code, int):
        evidence["statusCode"] = status_code
    return evidence


def _operator_evidence_checks(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    findings = _find_sensitive_value(payload)
    host_label = payload.get("baseUrlHostLabel")
    timeout = payload.get("timeoutSeconds")
    timestamp = payload.get("timestamp") or payload.get("generatedAt")
    reason_codes = payload.get("reasonCodes") if isinstance(payload.get("reasonCodes"), list) else []
    sanitization = payload.get("sanitization") if isinstance(payload.get("sanitization"), dict) else {}
    https_ingress = payload.get("httpsIngress") if isinstance(payload.get("httpsIngress"), dict) else {}
    synthetic_posture = (
        payload.get("syntheticDataPosture") if isinstance(payload.get("syntheticDataPosture"), dict) else {}
    )
    manual_review = payload.get("manualReview") if isinstance(payload.get("manualReview"), dict) else {}

    ready = _operator_result_from_summary(payload, "health_ready")
    alias = _operator_result_from_summary(payload, "health_alias")
    live = _operator_result_from_summary(payload, "health_live")
    admin = _operator_result_from_summary(payload, "admin_fail_closed")

    checks = [
        {
            "id": "operator_evidence_contains_no_unsafe_values",
            "status": "pass" if not findings else "fail",
            "evidence": {
                "unsafeFindingCount": len(findings),
                "findings": findings[:20],
            },
        },
        {
            "id": "operator_evidence_has_host_label_only",
            "status": "pass" if _safe_host_label(host_label) else "fail",
            "evidence": {
                "baseUrlHostLabel": host_label if _safe_host_label(host_label) else "<invalid>",
                "valuesIncluded": False,
            },
        },
        {
            "id": "operator_evidence_records_real_smoke_opt_in",
            "status": "pass" if payload.get("networkCallsEnabled") is True and payload.get("liveOptInRecorded") is True else "fail",
            "evidence": {
                "networkCallsEnabled": payload.get("networkCallsEnabled") is True,
                "liveOptInRecorded": payload.get("liveOptInRecorded") is True,
            },
        },
        {
            "id": "operator_evidence_has_timestamp",
            "status": "pass" if isinstance(timestamp, str) and timestamp.strip() else "fail",
            "evidence": {
                "timestamp": timestamp if isinstance(timestamp, str) and timestamp.strip() else "<missing>",
            },
        },
        {
            "id": "operator_evidence_has_bounded_timeout",
            "status": "pass" if isinstance(timeout, (int, float)) and 0 < float(timeout) <= 30 else "fail",
            "evidence": {
                "timeoutSeconds": timeout,
                "maxTimeoutSeconds": 30,
            },
        },
        {
            "id": "operator_evidence_has_required_result_summary",
            "status": "pass"
            if all(item.get("status") == "pass" for item in (ready, alias, live))
            and ready.get("statusCode") == 200
            and alias.get("statusCode") == 200
            and live.get("statusCode") == 200
            else "fail",
            "evidence": {
                "health_ready": ready,
                "health_alias": alias,
                "health_live": live,
            },
        },
        {
            "id": "operator_evidence_records_admin_fail_closed",
            "status": "pass"
            if admin.get("status") == "pass" and admin.get("statusCode") in {401, 403}
            else "fail",
            "evidence": {
                "admin_fail_closed": admin,
            },
        },
        {
            "id": "operator_evidence_has_sanitized_reason_codes",
            "status": "pass"
            if reason_codes and all(_safe_reason_code(reason_code) for reason_code in reason_codes)
            else "fail",
            "evidence": {
                "reasonCodes": [str(reason_code) for reason_code in reason_codes if _safe_reason_code(reason_code)],
                "reasonCodeCount": len(reason_codes),
            },
        },
        {
            "id": "operator_evidence_declares_required_sanitization",
            "status": "pass"
            if isinstance(sanitization, dict)
            and all(
                sanitization.get(key) is False
                for key in (
                    "rawResponseBodiesIncluded",
                    "tokensIncluded",
                    "cookiesIncluded",
                    "secretsIncluded",
                    "dsnsIncluded",
                    "apiKeysIncluded",
                    "providerPayloadsIncluded",
                    "debugTracesIncluded",
                    "credentialBearingUrlsIncluded",
                )
            )
            else "fail",
            "evidence": {
                "sanitization": {
                    key: sanitization.get(key) is False
                    for key in (
                        "rawResponseBodiesIncluded",
                        "tokensIncluded",
                        "cookiesIncluded",
                        "secretsIncluded",
                        "dsnsIncluded",
                        "apiKeysIncluded",
                        "providerPayloadsIncluded",
                        "debugTracesIncluded",
                        "credentialBearingUrlsIncluded",
                    )
                },
            },
        },
        {
            "id": "operator_evidence_records_target_https_ingress",
            "status": "pass"
            if payload.get("evidenceMode") == TARGET_ENV_EVIDENCE_MODE
            and https_ingress.get("reverseProxyTlsObserved") is True
            and _public_ports_are_80_443(https_ingress)
            and https_ingress.get("backendPort8000Public") is False
            and https_ingress.get("httpRedirectsToHttps") is True
            and synthetic_posture.get("syntheticUsersOnly") is True
            and synthetic_posture.get("customerDataUsed") is False
            and _manual_review_ready(manual_review)
            else "fail",
            "evidence": {
                "evidenceMode": str(payload.get("evidenceMode") or "<missing>"),
                "reverseProxyTlsObserved": https_ingress.get("reverseProxyTlsObserved") is True,
                "onlyPublicPorts80And443": _public_ports_are_80_443(https_ingress),
                "backendPort8000Public": https_ingress.get("backendPort8000Public") is True,
                "httpRedirectsToHttps": https_ingress.get("httpRedirectsToHttps") is True,
                "syntheticUsersOnly": synthetic_posture.get("syntheticUsersOnly") is True,
                "customerDataUsed": synthetic_posture.get("customerDataUsed") is True,
                "manualReviewReady": _manual_review_ready(manual_review),
            },
        },
        {
            "id": "operator_evidence_preserves_launch_no_go",
            "status": "pass"
            if payload.get("releaseApproved") is False and payload.get("publicLaunchReady") is False
            else "fail",
            "evidence": {
                "releaseApproved": payload.get("releaseApproved") is True,
                "publicLaunchReady": payload.get("publicLaunchReady") is True,
            },
        },
    ]

    normalized = {
        "schemaVersion": str(payload.get("schemaVersion") or OPERATOR_EVIDENCE_SCHEMA_VERSION),
        "mode": str(payload.get("mode") or "operator_sanitized"),
        "evidenceMode": str(payload.get("evidenceMode") or "<missing>"),
        "baseUrlHostLabel": host_label if _safe_host_label(host_label) else "<invalid>",
        "networkCallsEnabled": payload.get("networkCallsEnabled") is True,
        "liveOptInRecorded": payload.get("liveOptInRecorded") is True,
        "timeoutSeconds": timeout,
        "timestamp": timestamp if isinstance(timestamp, str) else "<missing>",
        "reasonCodes": [str(reason_code) for reason_code in reason_codes if _safe_reason_code(reason_code)],
        "sanitization": {
            key: sanitization.get(key) is False
            for key in (
                "rawResponseBodiesIncluded",
                "tokensIncluded",
                "cookiesIncluded",
                "secretsIncluded",
                "dsnsIncluded",
                "apiKeysIncluded",
                "providerPayloadsIncluded",
                "debugTracesIncluded",
                "credentialBearingUrlsIncluded",
            )
        },
        "resultSummary": {
            "health_ready": ready,
            "health_alias": alias,
            "health_live": live,
            "admin_fail_closed": admin,
        },
        "httpsIngress": {
            "reverseProxyTlsObserved": https_ingress.get("reverseProxyTlsObserved") is True,
            "onlyPublicPorts80And443": _public_ports_are_80_443(https_ingress),
            "backendPort8000Public": https_ingress.get("backendPort8000Public") is True,
            "httpRedirectsToHttps": https_ingress.get("httpRedirectsToHttps") is True,
        },
        "syntheticDataPosture": {
            "syntheticUsersOnly": synthetic_posture.get("syntheticUsersOnly") is True,
            "customerDataUsed": synthetic_posture.get("customerDataUsed") is True,
        },
        "manualReviewReady": _manual_review_ready(manual_review),
        "releaseApproved": payload.get("releaseApproved") is True,
        "publicLaunchReady": payload.get("publicLaunchReady") is True,
    }
    return checks, normalized


def _build_operator_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    checks, normalized = _operator_evidence_checks(payload)
    failed = sum(1 for check in checks if check["status"] == "fail")
    evidence: dict[str, Any] = {
        "tool": "staging_ingress_smoke",
        "generatedAt": _now_iso(),
        "mode": "operator_evidence",
        "networkCallsEnabled": False,
        "checkerNetworkCallsEnabled": False,
        "operatorEvidence": normalized,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": sum(1 for check in checks if check["status"] == "pass"),
            "failed": failed,
            "durationMs": int((time.monotonic() - started) * 1000),
        },
        "verdict": "pass" if failed == 0 else "fail",
    }
    return evidence


def _fetch_json(url: str, timeout: float) -> tuple[int, str, dict[str, Any] | None]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "wolfystock-staging-ingress-smoke/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = int(response.status)
            raw_body = response.read(MAX_BODY_BYTES + 1)
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        raw_body = exc.read(MAX_BODY_BYTES + 1)
        content_type = exc.headers.get("Content-Type", "")
    body = raw_body[:MAX_BODY_BYTES].decode("utf-8", errors="replace")
    if "json" not in content_type.lower():
        return status_code, body, None
    try:
        parsed_body = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed_body = None
    return status_code, body, parsed_body


def _safe_failure(
    *,
    name: str,
    base_url: str,
    path: str,
    reason_code: str,
    action: str,
    status_code: int | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    scenario: dict[str, Any] = {
        "name": name,
        "status": "fail",
        "baseUrl": _display_url(base_url),
        "url": f"{_display_url(base_url)}{path}",
        "path": path,
        "reasonCode": reason_code,
        "action": action,
    }
    if status_code is not None:
        scenario["statusCode"] = status_code
    if detail:
        scenario["detail"] = detail
    return scenario


def _pass(
    *,
    name: str,
    base_url: str,
    path: str,
    status_code: int,
    body_bytes: int,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass",
        "baseUrl": _display_url(base_url),
        "url": f"{_display_url(base_url)}{path}",
        "path": path,
        "statusCode": status_code,
        "bodyBytes": body_bytes,
    }


def _check_public_endpoint(name: str, base_url: str, path: str, timeout: float) -> dict[str, Any]:
    try:
        status_code, body, parsed_body = _fetch_json(_join_url(base_url, path), timeout)
    except (TimeoutError, socket.timeout):
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            reason_code="request_timeout",
            action="Check ingress routing, upstream health, and timeout budget.",
        )
    except urllib.error.URLError:
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            reason_code="request_failed",
            action="Check DNS, TLS, ingress routing, and upstream availability.",
        )

    sensitive_reason = _find_sensitive_pattern(body)
    if sensitive_reason:
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            status_code=status_code,
            reason_code="sensitive_payload_pattern",
            action=f"Remove or redact {sensitive_reason} fields from public health responses.",
        )
    if status_code != 200:
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            status_code=status_code,
            reason_code="unexpected_status",
            action="Verify ingress forwards this public health endpoint to the API service.",
        )
    if not isinstance(parsed_body, dict):
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            status_code=status_code,
            reason_code="invalid_json",
            action="Return a bounded JSON health payload through ingress.",
        )
    if parsed_body.get("status") not in {"ok", "ready"}:
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            status_code=status_code,
            reason_code="unexpected_health_status",
            action="Confirm the health handler reports ok readiness before launch.",
        )
    return _pass(name=name, base_url=base_url, path=path, status_code=status_code, body_bytes=len(body.encode("utf-8")))


def _check_admin_fail_closed(name: str, base_url: str, path: str, timeout: float) -> dict[str, Any]:
    try:
        status_code, body, _parsed_body = _fetch_json(_join_url(base_url, path), timeout)
    except (TimeoutError, socket.timeout):
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            reason_code="request_timeout",
            action="Check ingress routing, upstream health, and timeout budget.",
        )
    except urllib.error.URLError:
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            reason_code="request_failed",
            action="Check DNS, TLS, ingress routing, and upstream availability.",
        )

    sensitive_reason = _find_sensitive_pattern(body)
    if sensitive_reason:
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            status_code=status_code,
            reason_code="sensitive_payload_pattern",
            action=f"Remove or redact {sensitive_reason} fields from unauthenticated admin responses.",
        )
    if status_code not in {401, 403}:
        return _safe_failure(
            name=name,
            base_url=base_url,
            path=path,
            status_code=status_code,
            reason_code="admin_route_not_fail_closed",
            action="Require unauthenticated or forbidden status for protected admin routes.",
        )
    return _pass(name=name, base_url=base_url, path=path, status_code=status_code, body_bytes=len(body.encode("utf-8")))


def _dry_run_scenarios(base_urls: list[str]) -> list[dict[str, Any]]:
    checks = [
        ("health_ready", "/api/health/ready"),
        ("health_alias", "/api/health"),
        ("health_live", "/api/health/live"),
        ("admin_fail_closed", "/api/v1/admin/users"),
    ]
    return [
        {
            "name": name,
            "status": "skipped",
            "baseUrl": _display_url(base_url),
            "url": f"{_display_url(base_url)}{path}",
            "path": path,
            "reasonCode": "dry_run_no_network",
        }
        for base_url in base_urls
        for name, path in checks
    ]


def _live_scenarios(base_urls: list[str], timeout: float) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for base_url in base_urls:
        scenarios.append(_check_public_endpoint("health_ready", base_url, "/api/health/ready", timeout))
        scenarios.append(_check_public_endpoint("health_alias", base_url, "/api/health", timeout))
        scenarios.append(_check_public_endpoint("health_live", base_url, "/api/health/live", timeout))
        scenarios.append(_check_admin_fail_closed("admin_fail_closed", base_url, "/api/v1/admin/users", timeout))
    return scenarios


def _build_evidence(base_urls: list[str], timeout: float, live: bool) -> dict[str, Any]:
    started = time.monotonic()
    scenarios = _live_scenarios(base_urls, timeout) if live else _dry_run_scenarios(base_urls)
    failed = sum(1 for scenario in scenarios if scenario["status"] == "fail")
    evidence: dict[str, Any] = {
        "tool": "staging_ingress_smoke",
        "generatedAt": _now_iso(),
        "mode": "live" if live else "dry_run",
        "networkCallsEnabled": live,
        "manualReviewRequired": True,
        "releaseApproved": False,
        "publicLaunchReady": False,
        "timeoutSeconds": timeout,
        "baseUrls": [{"displayUrl": _display_url(base_url)} for base_url in base_urls],
        "scenarios": scenarios,
        "summary": {
            "total": len(scenarios),
            "passed": sum(1 for scenario in scenarios if scenario["status"] == "pass"),
            "failed": failed,
            "skipped": sum(1 for scenario in scenarios if scenario["status"] == "skipped"),
            "durationMs": int((time.monotonic() - started) * 1000),
        },
    }
    if live:
        evidence["verdict"] = "pass" if failed == 0 else "fail"
    else:
        evidence["verdict"] = "dry_run"
        evidence["nextStep"] = (
            f"Set {OPT_IN_ENV}=1 and {BASE_URLS_ENV}=https://staging.example.com "
            "to run live staging ingress smoke."
        )
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run safe staging ingress smoke evidence checks.")
    parser.add_argument("--base-url", action="append", default=[], help="Ingress-style base URL. Can be repeated.")
    parser.add_argument("--timeout", default=os.getenv(TIMEOUT_ENV), help="Per-request timeout in seconds.")
    parser.add_argument("--evidence-file", help="Optional path to write JSON evidence.")
    parser.add_argument(
        "--operator-evidence",
        help="Optional sanitized operator evidence JSON to validate offline without network calls.",
    )
    args = parser.parse_args(argv)

    if args.operator_evidence:
        if args.base_url:
            print("[FAIL] --operator-evidence is exclusive with --base-url", file=sys.stderr)
            return 2
        payload = _load_json_payload(args.operator_evidence)
        evidence = _build_operator_evidence(payload)
    else:
        timeout = _parse_timeout(args.timeout)
        base_urls = _split_base_urls(args.base_url, os.getenv(BASE_URLS_ENV))
        if not base_urls:
            base_urls = ["https://staging.example.invalid"]
        try:
            for base_url in base_urls:
                _clean_base_url(base_url)
        except ValueError as exc:
            print(f"[FAIL] Invalid base URL: {exc}", file=sys.stderr)
            return 2

        live = os.getenv(OPT_IN_ENV) == "1"
        evidence = _build_evidence(base_urls, timeout, live)
    output = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    if args.evidence_file:
        evidence_path = Path(args.evidence_file)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 1 if evidence["verdict"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
