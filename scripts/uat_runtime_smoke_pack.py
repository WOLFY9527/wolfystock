#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UAT runtime smoke pack for a freshly built local WolfyStock instance."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.uat_fresh_build_verifier import (
    VerificationResult,
    load_json_file,
    read_backend_info,
    resolve_repo_root,
    verify_admin_build_provenance,
    verify_frontend_static_build,
)


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 5.0
ROOT_BUNDLE_RE = re.compile(r"""<script\b[^>]*\bsrc=["'](?P<src>[^"']+index-[^"']+\.js[^"']*)["']""", re.IGNORECASE)
INDEX_HASH_RE = re.compile(r"^index-(?P<hash>[A-Za-z0-9_-]+)\.js$")
PUBLIC_ROUTE_SPECS: tuple[tuple[str, str], ...] = (
    ("GET", "/api/health"),
    ("GET", "/api/v1/auth/status"),
    ("GET", "/api/v1/market-overview/indices"),
    ("GET", "/api/v1/stocks/AAPL/quote"),
)
AUTHENTICATED_ROUTE_SPECS: tuple[tuple[str, str], ...] = (
    ("GET", "/api/v1/research/radar"),
    ("GET", "/api/v1/scanner/themes"),
)

EXIT_OK = 0
EXIT_FAILED = 1


class _HttpResponse:
    def __init__(self, status_code: int, *, text: str) -> None:
        self.status_code = int(status_code)
        self.text = text

    def json(self) -> dict[str, Any]:
        payload = json.loads(self.text)
        if not isinstance(payload, dict):
            raise ValueError("json_root_not_object")
        return payload


class _UrllibClient:
    def __init__(self, *, timeout: float) -> None:
        self.timeout = float(timeout)

    def request(self, method: str, url: str, headers: dict[str, str] | None = None) -> _HttpResponse:
        request = urllib.request.Request(
            url,
            method=method,
            headers={"User-Agent": "wolfystock-uat-runtime-smoke/1", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read(65536).decode("utf-8", errors="ignore")
                return _HttpResponse(int(response.status), text=body)
        except urllib.error.HTTPError as exc:
            body = exc.read(65536).decode("utf-8", errors="ignore")
            return _HttpResponse(int(exc.code), text=body)


def clean_base_url(raw_url: str) -> str:
    parsed = urllib.parse.urlsplit(str(raw_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url_requires_http_scheme_and_host")
    if parsed.username or parsed.password:
        raise ValueError("base_url_must_not_include_credentials")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def build_http_client(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> _UrllibClient:
    return _UrllibClient(timeout=timeout)


def read_git_head(repo_root: Path | str) -> str | None:
    return str(read_backend_info(repo_root).git_sha or "").strip() or None


def verify_local_build(*, repo_root: Path, static_root: Path | None = None) -> VerificationResult:
    return verify_frontend_static_build(
        static_root=static_root or (repo_root / "static"),
        backend_info=read_backend_info(repo_root),
        repo_root=repo_root,
    )


def verify_surface_readiness_payload(payload: dict[str, Any]) -> VerificationResult:
    errors: list[str] = []
    if str(payload.get("generatedAt") or "").strip() == "":
        errors.append("surface_readiness_generated_at_missing")
    if payload.get("readOnly") is not True:
        errors.append("surface_readiness_read_only_mismatch")
    if payload.get("noExternalCalls") is not True:
        errors.append("surface_readiness_external_calls_mismatch")
    if payload.get("runtimeBehaviorChanged") is not False:
        errors.append("surface_readiness_runtime_behavior_changed")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("surface_readiness_metadata_missing")
        metadata = {}
    if metadata.get("contract") != "backend_surface_contract_parity_v1":
        errors.append("surface_readiness_contract_mismatch")
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("surface_readiness_surfaces_missing")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        errors.append("surface_readiness_summary_missing")
    elif int(summary.get("surfaceCount") or 0) <= 0:
        errors.append("surface_readiness_surface_count_invalid")

    return VerificationResult(ok=not errors, payload=payload, error_codes=errors)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url}{path}"


def _parse_runtime_bundle(html: str) -> dict[str, str | None]:
    match = ROOT_BUNDLE_RE.search(str(html or ""))
    if not match:
        return {"assetRef": None, "assetFilename": None, "assetHash": None}
    asset_ref = str(match.group("src") or "").strip()
    asset_filename = Path(asset_ref.split("?", 1)[0].split("#", 1)[0]).name or None
    asset_hash = None
    if asset_filename:
        hash_match = INDEX_HASH_RE.match(asset_filename)
        if hash_match:
            asset_hash = hash_match.group("hash")
    return {
        "assetRef": asset_ref or None,
        "assetFilename": asset_filename,
        "assetHash": asset_hash,
    }


def _fetch_json(
    client: Any,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    response = client.request(method, url, headers=headers or {})
    try:
        payload = response.json()
    except Exception:
        payload = None
    return int(response.status_code), payload


def _is_success_status(status_code: int) -> bool:
    return 200 <= int(status_code) < 300


def _verify_runtime_bundle(
    *,
    base_url: str,
    client: Any,
    local_payload: dict[str, Any],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    root_response = client.request("GET", _join_url(base_url, "/"))
    if int(root_response.status_code) != 200:
        return {
            "status": "FAIL",
            "reasonCodes": ["runtime_root_unavailable"],
            "httpStatus": int(root_response.status_code),
            "servedAssetFilename": None,
            "servedAssetHash": None,
        }

    bundle = _parse_runtime_bundle(root_response.text)
    asset_ref = bundle["assetRef"]
    asset_filename = bundle["assetFilename"]
    asset_hash = bundle["assetHash"]
    if not asset_filename:
        reason_codes.append("runtime_frontend_main_asset_missing")
    else:
        asset_url = urllib.parse.urljoin(f"{base_url}/", str(asset_ref).lstrip("/"))
        asset_response = client.request("GET", asset_url)
        if int(asset_response.status_code) != 200:
            reason_codes.append("runtime_frontend_asset_unavailable")

    expected_filename = local_payload.get("frontendMainAssetFilename")
    expected_hash = local_payload.get("frontendMainAssetHash")
    if expected_filename and asset_filename != expected_filename:
        reason_codes.append("runtime_frontend_main_asset_mismatch")
    if expected_hash and asset_hash != expected_hash:
        reason_codes.append("runtime_frontend_main_asset_hash_mismatch")

    return {
        "status": "PASS" if not reason_codes else "FAIL",
        "reasonCodes": reason_codes,
        "httpStatus": int(root_response.status_code),
        "servedAssetFilename": asset_filename,
        "servedAssetHash": asset_hash,
    }


def _verify_public_routes(*, base_url: str, client: Any) -> dict[str, Any]:
    failing_routes: list[dict[str, Any]] = []
    checked_routes: list[dict[str, Any]] = []
    for method, path in PUBLIC_ROUTE_SPECS:
        response = client.request(method, _join_url(base_url, path))
        status_code = int(response.status_code)
        checked_routes.append({"method": method, "path": path, "httpStatus": status_code})
        if not _is_success_status(status_code):
            failing_routes.append({"method": method, "path": path, "httpStatus": status_code})
    return {
        "status": "PASS" if not failing_routes else "FAIL",
        "reasonCodes": [] if not failing_routes else ["public_route_unavailable"],
        "checkedRoutes": checked_routes,
        "failingRoutes": failing_routes,
    }


def _verify_authenticated_routes(
    *,
    base_url: str,
    client: Any,
    auth_headers: dict[str, str] | None,
) -> dict[str, Any]:
    checked_routes: list[dict[str, Any]] = []
    failing_routes: list[dict[str, Any]] = []
    auth_required_routes: list[dict[str, Any]] = []
    publicly_available_routes: list[dict[str, Any]] = []
    noauth_policy_mismatch_routes: list[dict[str, Any]] = []
    for method, path in AUTHENTICATED_ROUTE_SPECS:
        url = _join_url(base_url, path)
        anonymous_response = client.request(method, url)
        anonymous_status_code = int(anonymous_response.status_code)
        route_result = {
            "method": method,
            "path": path,
            "anonymousHttpStatus": anonymous_status_code,
        }
        anonymous_policy_mismatch = anonymous_status_code not in {401, 403}
        if anonymous_policy_mismatch:
            anonymous_route_result = {"method": method, "path": path, "httpStatus": anonymous_status_code}
            noauth_policy_mismatch_routes.append(anonymous_route_result)
            if _is_success_status(anonymous_status_code):
                publicly_available_routes.append(anonymous_route_result)

        if auth_headers:
            response = client.request(method, url, headers=auth_headers)
            status_code = int(response.status_code)
            route_result["httpStatus"] = status_code
        else:
            status_code = anonymous_status_code
            route_result["httpStatus"] = status_code

        checked_routes.append(route_result)
        if _is_success_status(status_code):
            continue
        if not auth_headers and status_code in {401, 403}:
            auth_required_routes.append(route_result)
            continue
        if not auth_headers and anonymous_policy_mismatch:
            continue
        failing_routes.append(route_result)

    if noauth_policy_mismatch_routes or failing_routes:
        status = "FAIL"
        reason_codes = []
        if publicly_available_routes:
            reason_codes.append("authenticated_route_publicly_available")
        if noauth_policy_mismatch_routes and not publicly_available_routes:
            reason_codes.append("authenticated_route_noauth_policy_mismatch")
        if failing_routes:
            reason_codes.append("authenticated_route_unavailable")
    elif auth_required_routes:
        status = "PARTIAL"
        reason_codes = ["authenticated_routes_auth_required"]
    else:
        status = "PASS"
        reason_codes = []

    return {
        "status": status,
        "reasonCodes": reason_codes,
        "checkedRoutes": checked_routes,
        "failingRoutes": failing_routes,
        "authRequiredRoutes": auth_required_routes,
        "publiclyAvailableRoutes": publicly_available_routes,
        "noAuthPolicyMismatchRoutes": noauth_policy_mismatch_routes,
    }


def _evaluate_admin_status(
    *,
    client: Any,
    base_url: str,
    local_payload: dict[str, Any],
    admin_status_payload: dict[str, Any] | None,
    auth_headers: dict[str, str] | None,
) -> dict[str, Any]:
    if admin_status_payload is not None:
        result = verify_admin_build_provenance(admin_status_payload, local_payload=local_payload)
        return {
            "status": "PASS" if result.ok else "FAIL",
            "reasonCodes": result.error_codes,
            "source": "file",
            "httpStatus": None,
        }
    if not auth_headers:
        return {
            "status": "PARTIAL",
            "reasonCodes": ["admin_status_unverified"],
            "source": "unverified",
            "httpStatus": None,
        }
    status_code, payload = _fetch_json(
        client,
        method="GET",
        url=_join_url(base_url, "/api/v1/admin/ops/status"),
        headers=auth_headers,
    )
    if status_code in {401, 403}:
        return {
            "status": "FAIL",
            "reasonCodes": ["admin_status_auth_required"],
            "source": "live",
            "httpStatus": status_code,
        }
    if status_code != 200 or payload is None:
        return {
            "status": "FAIL",
            "reasonCodes": ["admin_status_unavailable"],
            "source": "live",
            "httpStatus": status_code,
        }
    result = verify_admin_build_provenance(payload, local_payload=local_payload)
    return {
        "status": "PASS" if result.ok else "FAIL",
        "reasonCodes": result.error_codes,
        "source": "live",
        "httpStatus": status_code,
        "payload": payload,
    }


def _evaluate_surface_readiness(
    *,
    client: Any,
    base_url: str,
    surface_readiness_payload: dict[str, Any] | None,
    auth_headers: dict[str, str] | None,
) -> dict[str, Any]:
    if surface_readiness_payload is not None:
        result = verify_surface_readiness_payload(surface_readiness_payload)
        return {
            "status": "PASS" if result.ok else "FAIL",
            "reasonCodes": result.error_codes,
            "source": "file",
            "httpStatus": None,
        }
    if not auth_headers:
        return {
            "status": "PARTIAL",
            "reasonCodes": ["surface_readiness_unverified"],
            "source": "unverified",
            "httpStatus": None,
        }
    status_code, payload = _fetch_json(
        client,
        method="GET",
        url=_join_url(base_url, "/api/v1/admin/ops/surface-readiness"),
        headers=auth_headers,
    )
    if status_code in {401, 403}:
        return {
            "status": "FAIL",
            "reasonCodes": ["surface_readiness_auth_required"],
            "source": "live",
            "httpStatus": status_code,
        }
    if status_code != 200 or payload is None:
        return {
            "status": "FAIL",
            "reasonCodes": ["surface_readiness_unavailable"],
            "source": "live",
            "httpStatus": status_code,
        }
    result = verify_surface_readiness_payload(payload)
    return {
        "status": "PASS" if result.ok else "FAIL",
        "reasonCodes": result.error_codes,
        "source": "live",
        "httpStatus": status_code,
    }


def _summarize_status(checks: dict[str, dict[str, Any]]) -> tuple[str, int]:
    statuses = [str(item.get("status") or "FAIL") for item in checks.values()]
    if all(status == "PASS" for status in statuses):
        return "PASS", EXIT_OK
    if any(status == "FAIL" for status in statuses):
        return "FAIL", EXIT_FAILED
    return "PARTIAL", EXIT_FAILED


def run_runtime_smoke(
    *,
    base_url: str,
    client: Any,
    git_head: str | None,
    local_build_result: VerificationResult,
    admin_status_payload: dict[str, Any] | None,
    surface_readiness_payload: dict[str, Any] | None,
    auth_headers: dict[str, str] | None,
) -> dict[str, Any]:
    local_build_check = {
        "status": "PASS" if local_build_result.ok else "FAIL",
        "reasonCodes": list(local_build_result.error_codes),
        "warningCodes": list(local_build_result.warning_codes),
    }

    runtime_bundle_check = {"status": "FAIL", "reasonCodes": ["local_build_unverified"]}
    public_routes_check = {"status": "FAIL", "reasonCodes": ["local_build_unverified"], "failingRoutes": []}
    authenticated_routes_check = {
        "status": "FAIL",
        "reasonCodes": ["local_build_unverified"],
        "failingRoutes": [],
        "authRequiredRoutes": [],
        "publiclyAvailableRoutes": [],
        "noAuthPolicyMismatchRoutes": [],
    }
    admin_check = {"status": "PARTIAL", "reasonCodes": ["admin_status_unverified"]}
    surface_check = {"status": "PARTIAL", "reasonCodes": ["surface_readiness_unverified"]}

    if local_build_result.ok:
        runtime_bundle_check = _verify_runtime_bundle(
            base_url=base_url,
            client=client,
            local_payload=local_build_result.payload,
        )
        public_routes_check = _verify_public_routes(base_url=base_url, client=client)
        authenticated_routes_check = _verify_authenticated_routes(
            base_url=base_url,
            client=client,
            auth_headers=auth_headers,
        )
        admin_check = _evaluate_admin_status(
            client=client,
            base_url=base_url,
            local_payload=local_build_result.payload,
            admin_status_payload=admin_status_payload,
            auth_headers=auth_headers,
        )
        surface_check = _evaluate_surface_readiness(
            client=client,
            base_url=base_url,
            surface_readiness_payload=surface_readiness_payload,
            auth_headers=auth_headers,
        )

    checks = {
        "localBuild": local_build_check,
        "runtimeBundle": runtime_bundle_check,
        "publicRoutes": public_routes_check,
        "authenticatedRoutes": authenticated_routes_check,
        "adminOpsStatus": admin_check,
        "surfaceReadiness": surface_check,
    }
    summary_status, exit_code = _summarize_status(checks)
    return {
        "summaryStatus": summary_status,
        "exitCode": exit_code,
        "baseUrl": base_url,
        "gitHead": git_head,
        "checks": checks,
    }


def _parse_auth_headers(values: Sequence[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        if ":" not in text:
            raise ValueError("auth_header_must_use_name_colon_value")
        name, value = text.split(":", 1)
        header_name = name.strip()
        header_value = value.strip()
        if not header_name or not header_value:
            raise ValueError("auth_header_must_use_name_colon_value")
        headers[header_name] = header_value
    return headers


def _print_human_summary(report: dict[str, Any]) -> None:
    print(f"UAT runtime smoke: {report['summaryStatus']}")
    print(f"Base URL: {report['baseUrl']}")
    print(f"Git HEAD: {report.get('gitHead') or 'unknown'}")
    for key in ("localBuild", "runtimeBundle", "publicRoutes", "authenticatedRoutes", "adminOpsStatus", "surfaceReadiness"):
        check = report["checks"][key]
        reason_codes = ", ".join(check.get("reasonCodes") or []) or "none"
        print(f"- {key}: {check['status']} ({reason_codes})")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UAT runtime smoke pack for a freshly built and running WolfyStock instance.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Running WolfyStock base URL.")
    parser.add_argument("--repo-root", type=Path, default=None, help="Repository root. Defaults to git rev-parse --show-toplevel.")
    parser.add_argument("--static-root", type=Path, default=None, help="Static root for local fresh-build verification.")
    parser.add_argument("--admin-status-json", type=Path, default=None, help="Optional captured JSON from GET /api/v1/admin/ops/status.")
    parser.add_argument(
        "--surface-readiness-json",
        type=Path,
        default=None,
        help="Optional captured JSON from GET /api/v1/admin/ops/surface-readiness.",
    )
    parser.add_argument(
        "--auth-header",
        action="append",
        default=[],
        help='Optional authenticated admin header, repeatable. Example: --auth-header "Cookie: dsa_session=..."',
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON to stdout.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        base_url = clean_base_url(args.base_url)
        auth_headers = _parse_auth_headers(args.auth_header)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAILED

    repo_root = args.repo_root or resolve_repo_root()
    git_head = read_git_head(repo_root)
    local_build_result = verify_local_build(repo_root=repo_root, static_root=args.static_root)
    admin_status_payload = load_json_file(args.admin_status_json) if args.admin_status_json else None
    surface_readiness_payload = load_json_file(args.surface_readiness_json) if args.surface_readiness_json else None
    client = build_http_client(timeout=float(args.timeout))

    report = run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head=git_head,
        local_build_result=local_build_result,
        admin_status_payload=admin_status_payload,
        surface_readiness_payload=surface_readiness_payload,
        auth_headers=auth_headers or None,
    )

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human_summary(report)
    return int(report["exitCode"])


if __name__ == "__main__":
    raise SystemExit(main())
