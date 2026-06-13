#!/usr/bin/env python3
"""Offline auth/RBAC release audit summary.

The script reads repository source files only. It does not import application
runtime modules, read environment values, open sockets, touch databases, or
approve launch.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SurfaceSpec:
    label: str
    source_path: str
    markers: tuple[str, ...]
    review_note: str


SURFACES: tuple[SurfaceSpec, ...] = (
    SurfaceSpec(
        label="private_api_auth_middleware",
        source_path="api/middlewares/auth.py",
        markers=("Login required", "path.startswith(\"/api/v1/\")", "csrf_origin_forbidden"),
        review_note="private API middleware fail-closed and CSRF guard",
    ),
    SurfaceSpec(
        label="admin_users",
        source_path="api/v1/endpoints/admin_users.py",
        markers=(
            'require_admin_capability("users:read")',
            'require_admin_capability("users:activity:read")',
            "/users/onboard",
            "/users",
        ),
        review_note="admin user directory and activity routes remain capability-gated",
    ),
    SurfaceSpec(
        label="admin_logs",
        source_path="api/v1/endpoints/admin_logs.py",
        markers=("require_admin_capability(\"ops:logs:read\")", "/storage/summary"),
        review_note="admin log read access remains capability-gated",
    ),
    SurfaceSpec(
        label="cost_observability",
        source_path="api/v1/endpoints/admin_cost.py",
        markers=("require_admin_capability(\"cost:observability:read\")", "/cost/llm-ledger-summary"),
        review_note="cost observability remains capability-gated",
    ),
    SurfaceSpec(
        label="provider_circuits",
        source_path="api/v1/endpoints/admin_provider_circuits.py",
        markers=("require_admin_capability(\"ops:providers:read\")", "/providers/circuits"),
        review_note="provider circuit diagnostics remain capability-gated",
    ),
    SurfaceSpec(
        label="market_provider_operations",
        source_path="api/v1/endpoints/market_provider_operations.py",
        markers=('require_admin_capability("ops:providers:read")', "/market-providers/operations"),
        review_note="market provider operations remain capability-gated",
    ),
    SurfaceSpec(
        label="public_error_limiter",
        source_path="api/middlewares/public_abuse_limiter.py",
        markers=("rate_limited", "identityRedaction", "client_identity_not_exposed"),
        review_note="public abuse limiter exposes bounded error metadata",
    ),
    SurfaceSpec(
        label="operator_evidence_workflow",
        source_path="scripts/operator_evidence_workflow_run.py",
        markers=("offline operator evidence workflow", "review-required"),
        review_note="operator evidence workflow remains offline and review-required",
    ),
    SurfaceSpec(
        label="manual_release_review_doc",
        source_path="docs/audits/auth-rbac-release-security-guide.md",
        markers=("Manual review is required before launch", "does not approve launch"),
        review_note="release guide requires human security review",
    ),
)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _check_surface(spec: SurfaceSpec) -> tuple[dict[str, object], list[dict[str, str]]]:
    path = REPO_ROOT / spec.source_path
    text = _read_text(path)
    findings: list[dict[str, str]] = []
    if text is None:
        findings.append({"surface": spec.label, "reasonCode": "source_file_missing"})
    else:
        missing_count = sum(1 for marker in spec.markers if marker not in text)
        if missing_count:
            findings.append({"surface": spec.label, "reasonCode": "expected_release_guard_marker_missing"})

    surface = {
        "label": spec.label,
        "sourcePath": spec.source_path,
        "status": "pass" if not findings else "review_required",
        "reviewNote": spec.review_note,
    }
    return surface, findings


def build_audit() -> dict[str, object]:
    surfaces: list[dict[str, object]] = []
    findings: list[dict[str, str]] = []
    for spec in SURFACES:
        surface, surface_findings = _check_surface(spec)
        surfaces.append(surface)
        findings.extend(surface_findings)

    return {
        "auditStatus": "manual_review_required",
        "surfacesChecked": surfaces,
        "riskyFindings": findings,
        "manualReviewRequired": True,
        "networkCallsExecuted": False,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit offline auth/RBAC release audit JSON.")
    parser.add_argument("--offline", action="store_true", help="Required; confirms no live checks or network calls.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.offline:
        print("[FAIL] --offline is required; live audit mode is not implemented.", file=sys.stderr)
        return 2
    print(json.dumps(build_audit(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
