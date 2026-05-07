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
    args = parser.parse_args(argv)

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
