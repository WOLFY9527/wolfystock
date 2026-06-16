#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local UAT frontend build and provenance verifier.

The script is intentionally local/read-only except for the optional frontend
build command, which follows the existing Vite convention and writes to
repo-local static/ output.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.build_provenance_service import BackendBuildInfo, build_build_provenance


DEFAULT_ADMIN_OPS_STATUS_URL = "http://127.0.0.1:8000/api/v1/admin/ops/status"
SUPPORTED_ADMIN_FRESHNESS_STATUSES = frozenset({"fresh", "stale", "unknown"})
PROVENANCE_COMPARE_FIELDS = (
    "backendGitSha",
    "frontendMainAssetFilename",
    "frontendMainAssetHash",
    "frontendStaticBuildTimestamp",
    "freshnessStatus",
    "stale",
)
PROVENANCE_COMPARE_ERROR_CODES = {
    "backendGitSha": "admin_backend_git_sha_mismatch",
    "frontendMainAssetFilename": "admin_frontend_main_asset_mismatch",
    "frontendMainAssetHash": "admin_frontend_main_asset_hash_mismatch",
    "frontendStaticBuildTimestamp": "admin_frontend_static_build_timestamp_mismatch",
    "freshnessStatus": "admin_freshness_status_mismatch",
    "stale": "admin_stale_flag_mismatch",
}
PROVENANCE_MISSING_ERROR_CODES = {
    "backendGitSha": "admin_backend_git_sha_missing",
    "frontendMainAssetFilename": "admin_frontend_main_asset_missing",
    "frontendMainAssetHash": "admin_frontend_main_asset_hash_missing",
    "frontendStaticBuildTimestamp": "admin_frontend_static_build_timestamp_missing",
    "freshnessStatus": "admin_freshness_status_missing",
    "stale": "admin_stale_flag_missing",
}
GENERATED_ARTIFACT_PATHS = (
    "static",
    "apps/dsa-web/node_modules",
    "apps/dsa-web/node_modules/.cache",
    ".cache",
)


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    payload: dict[str, Any]
    error_codes: list[str] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)


def verify_frontend_static_build(
    *,
    static_root: Path | str,
    backend_info: BackendBuildInfo,
    repo_root: Path | str,
    require_fresh: bool = True,
    allow_unknown_freshness: bool = False,
) -> VerificationResult:
    """Verify the static frontend bundle against backend HEAD provenance."""

    root = Path(static_root)
    repo = Path(repo_root)
    payload = build_build_provenance(static_root=root, backend_info=backend_info, repo_root=repo)
    errors: list[str] = []
    warnings: list[str] = []

    if payload["staticAssetMode"] != "static_dist":
        errors.append("frontend_static_dist_unavailable")
    if not payload["staticAssetRootExists"]:
        errors.append("static_root_missing")
    if not payload["staticIndexPresent"]:
        errors.append("index_html_missing")
    if not payload["frontendMainAssetFilename"]:
        errors.append("frontend_main_asset_unknown")
    if payload["frontendMainAssetFilename"] and not _main_asset_exists(root, payload["frontendMainAssetFilename"]):
        errors.append("frontend_main_asset_missing")
    if not payload["frontendMainAssetHash"]:
        errors.append("frontend_main_asset_hash_missing")

    freshness_status = str(payload.get("freshnessStatus") or "unknown")
    if require_fresh and freshness_status == "stale":
        errors.append("frontend_static_build_stale")
    elif require_fresh and freshness_status == "unknown":
        if allow_unknown_freshness:
            warnings.append("frontend_static_build_freshness_unknown")
        else:
            errors.append("frontend_static_build_freshness_unknown")
    elif freshness_status == "unavailable":
        errors.append("frontend_static_build_unavailable")

    return VerificationResult(
        ok=not errors,
        payload=payload,
        error_codes=_dedupe(errors),
        warning_codes=_dedupe(warnings),
    )


def verify_admin_build_provenance(
    admin_ops_payload: dict[str, Any],
    *,
    local_payload: dict[str, Any] | None = None,
) -> VerificationResult:
    """Validate and optionally compare an admin ops status buildProvenance payload."""

    build_provenance = admin_ops_payload.get("buildProvenance")
    if not isinstance(build_provenance, dict):
        build_provenance = admin_ops_payload
    if not isinstance(build_provenance, dict):
        return VerificationResult(
            ok=False,
            payload={},
            error_codes=["admin_build_provenance_missing"],
        )

    errors: list[str] = []
    if build_provenance.get("contract") != "admin_build_provenance_v1":
        errors.append("admin_build_provenance_contract_mismatch")

    freshness_status = str(build_provenance.get("freshnessStatus") or "unknown")
    if freshness_status not in SUPPORTED_ADMIN_FRESHNESS_STATUSES:
        errors.append("admin_build_provenance_freshness_status_unsupported")
    reason_codes = build_provenance.get("reasonCodes")
    if not isinstance(reason_codes, list) or not reason_codes:
        errors.append("admin_build_provenance_reason_codes_missing")

    if local_payload:
        for field_name in PROVENANCE_COMPARE_FIELDS:
            local_value = local_payload.get(field_name)
            admin_value = build_provenance.get(field_name)
            if local_value is not None and admin_value is None:
                errors.append(PROVENANCE_MISSING_ERROR_CODES[field_name])
            elif local_value is not None and admin_value != local_value:
                errors.append(PROVENANCE_COMPARE_ERROR_CODES[field_name])

    return VerificationResult(
        ok=not errors,
        payload=dict(build_provenance),
        error_codes=_dedupe(errors),
    )


def read_backend_info(repo_root: Path | str) -> BackendBuildInfo:
    repo = Path(repo_root)
    return BackendBuildInfo(
        git_sha=_git_output(repo, "rev-parse", "HEAD"),
        branch=_git_output(repo, "branch", "--show-current"),
        commit_timestamp=_git_output(repo, "show", "-s", "--format=%cI", "HEAD"),
    )


def resolve_repo_root(start: Path | None = None) -> Path:
    cwd = start or Path.cwd()
    output = _git_output(cwd, "rev-parse", "--show-toplevel")
    if output:
        return Path(output)
    return Path(__file__).resolve().parents[1]


def run_frontend_build(repo_root: Path) -> int:
    web_dir = repo_root / "apps" / "dsa-web"
    node_modules = web_dir / "node_modules"
    if not node_modules.exists():
        print(
            "ERROR: apps/dsa-web/node_modules is missing; run npm ci or create the documented worktree symlink first.",
            file=sys.stderr,
        )
        return 1

    command = ["npm", "--prefix", "apps/dsa-web", "run", "build"]
    print(f"Frontend build command: {' '.join(command)}")
    completed = subprocess.run(command, cwd=repo_root, check=False)
    if completed.returncode != 0:
        print("ERROR: frontend build failed; static assets were not accepted for UAT.", file=sys.stderr)
    return completed.returncode


def verify_git_preflight(repo_root: Path | str) -> list[str]:
    repo = Path(repo_root)
    errors: list[str] = []
    conflicts = _git_output(repo, "diff", "--name-only", "--diff-filter=U")
    if conflicts:
        errors.append("merge_conflicts_present")
    status = _git_output(repo, "status", "--short")
    if status:
        errors.append("worktree_dirty")
    return errors


def load_json_file(path: Path | str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("admin ops status JSON must be an object")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild or verify local frontend static assets and backend build provenance before UAT.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to git rev-parse --show-toplevel.",
    )
    parser.add_argument(
        "--static-root",
        type=Path,
        default=None,
        help="Static asset root. Defaults to <repo>/static.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip npm build and verify the current static asset root.",
    )
    parser.add_argument(
        "--admin-status-json",
        type=Path,
        default=None,
        help="Optional captured JSON from GET /api/v1/admin/ops/status for local comparison.",
    )
    parser.add_argument(
        "--admin-status-url",
        default=DEFAULT_ADMIN_OPS_STATUS_URL,
        help="Admin ops status URL to print in the post-build verification instruction.",
    )
    parser.add_argument(
        "--allow-unknown-freshness",
        action="store_true",
        help="Allow unknown local freshness only for manual diagnostics; default fails closed.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root or resolve_repo_root()
    static_root = args.static_root or repo_root / "static"
    backend_info = read_backend_info(repo_root)

    print(f"Git HEAD: {backend_info.git_sha or 'unknown'}")
    print(f"Git branch: {_safe_display_text(backend_info.branch) or 'unknown'}")
    print(f"Git commit timestamp: {backend_info.commit_timestamp or 'unknown'}")

    preflight_errors = verify_git_preflight(repo_root)
    if preflight_errors:
        for error in preflight_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    hygiene_errors = verify_generated_artifact_hygiene(repo_root)
    if hygiene_errors:
        for error in hygiene_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if not args.verify_only:
        build_status = run_frontend_build(repo_root)
        if build_status != 0:
            return build_status
    else:
        print("Frontend build command: skipped (--verify-only)")

    hygiene_errors = verify_generated_artifact_hygiene(repo_root)
    if hygiene_errors:
        for error in hygiene_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    local_result = verify_frontend_static_build(
        static_root=static_root,
        backend_info=backend_info,
        repo_root=repo_root,
        allow_unknown_freshness=bool(args.allow_unknown_freshness),
    )
    _print_local_result(local_result)
    if not local_result.ok:
        return 1

    if args.admin_status_json:
        try:
            admin_payload = load_json_file(args.admin_status_json)
        except Exception as exc:
            print(f"ERROR: failed to read admin ops status JSON: {exc}", file=sys.stderr)
            return 1
        admin_result = verify_admin_build_provenance(admin_payload, local_payload=local_result.payload)
        _print_admin_result(admin_result)
        if not admin_result.ok:
            return 1
    else:
        _print_admin_status_instruction(args.admin_status_url)

    return 0


def verify_generated_artifact_hygiene(repo_root: Path | str) -> list[str]:
    repo = Path(repo_root)
    tracked = _git_output(repo, "ls-files", *GENERATED_ARTIFACT_PATHS)
    if tracked:
        return ["generated_artifacts_tracked: static/node_modules/cache paths must not be committed"]
    return []


def _print_local_result(result: VerificationResult) -> None:
    payload = result.payload
    print(f"Frontend main asset: {payload.get('frontendMainAssetFilename') or 'unknown'}")
    print(f"Frontend main asset hash: {payload.get('frontendMainAssetHash') or 'unknown'}")
    print(f"Frontend static build timestamp: {payload.get('frontendStaticBuildTimestamp') or 'unknown'}")
    print(f"Build freshness status: {payload.get('freshnessStatus') or 'unknown'}")
    if result.warning_codes:
        print(f"Warnings: {', '.join(result.warning_codes)}")
    if result.error_codes:
        print(f"ERROR: {', '.join(result.error_codes)}", file=sys.stderr)


def _print_admin_result(result: VerificationResult) -> None:
    print(f"Admin buildProvenance freshness: {result.payload.get('freshnessStatus') or 'unknown'}")
    if result.error_codes:
        print(f"ERROR: {', '.join(result.error_codes)}", file=sys.stderr)


def _print_admin_status_instruction(url: str) -> None:
    print("Admin ops status comparison:")
    print(
        "  Capture GET /api/v1/admin/ops/status with an authenticated admin session, then rerun with "
        "--admin-status-json <captured-json>."
    )
    print(
        "  Mismatch-sensitive fields: buildProvenance.backendGitSha, frontendMainAssetFilename, "
        "frontendMainAssetHash, frontendStaticBuildTimestamp, freshnessStatus, stale."
    )
    print(
        "  Diagnostic fields checked: buildProvenance.contract, reasonCodes."
    )
    print(f"  URL: {_safe_url_for_instruction(url)}")
    print("  Do not paste cookies, tokens, credentials, or raw provider payloads into logs.")


def _main_asset_exists(static_root: Path, filename: str) -> bool:
    assets_dir = static_root / "assets"
    direct = assets_dir / filename
    if direct.is_file():
        return True
    if not assets_dir.is_dir():
        return False
    return any(path.is_file() and path.name == filename for path in assets_dir.rglob(filename))


def _git_output(repo_root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _safe_display_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in ("authorization", "bearer", "cookie", "password", "secret", "token")):
        return "redacted"
    if "://" in text or "?" in text:
        return "redacted"
    return text[:120]


def _safe_url_for_instruction(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_ADMIN_OPS_STATUS_URL
    try:
        from urllib.parse import urlsplit, urlunsplit

        parsed = urlsplit(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return DEFAULT_ADMIN_OPS_STATUS_URL
        hostname = parsed.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = f"{hostname}:{parsed.port}" if parsed.port else hostname
        return urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))
    except Exception:
        return DEFAULT_ADMIN_OPS_STATUS_URL


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
