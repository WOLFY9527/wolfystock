from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.uat_runtime_smoke_pack as smoke


class _FakeResponse:
    def __init__(self, status_code: int, *, text: str = "", payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> dict[str, object]:
        if self._payload is None:
            raise ValueError("json unavailable")
        return self._payload


class _FakeClient:
    def __init__(self, responses: dict[tuple[str, ...], _FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def request(self, method: str, url: str, headers: dict[str, str] | None = None) -> _FakeResponse:
        request_headers = dict(headers or {})
        self.calls.append((method, url, request_headers))
        auth_key = (method, url, "auth" if request_headers else "anonymous")
        if auth_key in self._responses:
            return self._responses[auth_key]
        key = (method, url)
        if key not in self._responses:
            raise AssertionError(f"unexpected request: {key}")
        return self._responses[key]


def _local_provenance() -> dict[str, object]:
    return {
        "backendGitSha": "e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        "frontendMainAssetFilename": "index-CKPdXr8Q.js",
        "frontendMainAssetHash": "CKPdXr8Q",
        "frontendStaticBuildTimestamp": "2026-06-16T12:05:00+00:00",
        "freshnessStatus": "fresh",
        "stale": False,
    }


def _auth_status_payload(*, auth_enabled: bool, logged_in: bool = False) -> dict[str, object]:
    return {
        "authEnabled": auth_enabled,
        "loggedIn": logged_in,
    }


def _admin_status_payload() -> dict[str, object]:
    return {
        "buildProvenance": {
            **_local_provenance(),
            "contract": "admin_build_provenance_v1",
            "reasonCodes": ["frontend_build_not_older_than_backend_commit"],
        }
    }


def _surface_readiness_payload() -> dict[str, object]:
    return {
        "generatedAt": "2026-06-17T09:00:00+00:00",
        "readOnly": True,
        "noExternalCalls": True,
        "liveEnforcement": False,
        "runtimeBehaviorChanged": False,
        "consumerVisible": False,
        "surfaces": [
            {
                "surfaceKey": "market_decision_cockpit",
                "label": "Market Decision Cockpit",
                "status": "degraded_contract",
                "routeStatus": "present",
                "primaryRoute": {
                    "method": "GET",
                    "path": "/api/v1/market/decision-cockpit",
                    "exists": True,
                    "responseModel": "dict",
                    "typedContract": False,
                },
                "relatedRoutes": [],
                "authRequirement": {"status": "known", "label": "optional_user"},
                "schemaVersionStatus": "present",
                "observationBoundaryStatus": "present",
                "degradedStateShapeStatus": "present",
                "consumerSafeIssueLabelsStatus": "raw_internal_codes_detected",
                "implementationStatus": "implemented",
                "gaps": [],
                "notes": [],
            }
        ],
        "summary": {"surfaceCount": 10, "statusCounts": {"ready": 1}},
        "metadata": {
            "contract": "backend_surface_contract_parity_v1",
            "projection": "route_registry_contract_signals_only",
            "providerCallsAttempted": False,
            "cacheMutation": False,
            "authBehaviorChanged": False,
        },
    }


def _route_responses(
    base_url: str,
    *,
    auth_enabled: bool,
    logged_in: bool = False,
) -> dict[tuple[str, ...], _FakeResponse]:
    return {
        ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
        (
            "GET",
            f"{base_url}/api/v1/auth/status",
        ): _FakeResponse(200, payload=_auth_status_payload(auth_enabled=auth_enabled, logged_in=logged_in)),
        ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
        ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
        ("GET", f"{base_url}/api/v1/stocks/AAPL/evidence"): _FakeResponse(200, payload={"items": []}),
        (
            "GET",
            f"{base_url}/api/v1/stocks/AAPL/structure-decision",
        ): _FakeResponse(200, payload={"schemaVersion": "stock_structure_decision_v1"}),
        ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(401, payload={"error": "unauthorized"}),
        ("GET", f"{base_url}/api/v1/research/radar", "auth"): _FakeResponse(200, payload={"items": []}),
        ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(401, payload={"error": "unauthorized"}),
        ("GET", f"{base_url}/api/v1/scanner/themes", "auth"): _FakeResponse(200, payload={"themes": []}),
    }


def test_public_route_specs_only_include_quote_baseline_for_stocks() -> None:
    assert ("GET", "/api/v1/stocks/AAPL/quote") in smoke.PUBLIC_ROUTE_SPECS
    assert ("GET", "/api/v1/stocks/AAPL/evidence") not in smoke.PUBLIC_ROUTE_SPECS
    assert ("GET", "/api/v1/stocks/AAPL/structure-decision") not in smoke.PUBLIC_ROUTE_SPECS


def test_probe_runtime_bundle_accepts_matching_root_asset_and_public_routes() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            **_route_responses(base_url, auth_enabled=True, logged_in=True),
            ("GET", f"{base_url}/api/v1/admin/ops/status"): _FakeResponse(200, payload=_admin_status_payload()),
            ("GET", f"{base_url}/api/v1/admin/ops/surface-readiness"): _FakeResponse(200, payload=_surface_readiness_payload()),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=None,
        surface_readiness_payload=None,
        auth_headers={"Cookie": "opaque-admin-session"},
    )

    assert report["summaryStatus"] == "PASS"
    assert report["exitCode"] == 0
    assert report["checks"]["adminOpsStatus"]["status"] == "PASS"
    assert report["checks"]["surfaceReadiness"]["status"] == "PASS"
    assert report["checks"]["runtimeBundle"]["status"] == "PASS"
    assert report["checks"]["publicRoutes"]["status"] == "PASS"
    assert report["checks"]["publicRoutes"]["failingRoutes"] == []
    assert report["checks"]["runtimeAuthMode"]["mode"] == "auth_enabled"
    assert report["checks"]["authenticatedRoutes"]["status"] == "PASS"
    assert report["checks"]["authenticatedRoutes"]["expectationMode"] == "authenticated_success_expected"
    assert report["checks"]["authenticatedRoutes"]["failingRoutes"] == []
    assert report["checks"]["authenticatedRoutes"]["authenticatedSessionRoutes"] == [
        {
            "method": "GET",
            "path": "/api/v1/research/radar",
            "anonymousHttpStatus": 401,
            "httpStatus": 200,
        },
        {
            "method": "GET",
            "path": "/api/v1/scanner/themes",
            "anonymousHttpStatus": 401,
            "httpStatus": 200,
        },
    ]
    assert report["checks"]["authenticatedRoutes"]["publiclyAvailableRoutes"] == []
    assert report["checks"]["authenticatedRoutes"]["noAuthPolicyMismatchRoutes"] == []
    output = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert "opaque-admin-session" not in output


def test_runtime_bundle_fails_when_served_asset_does_not_match_expected_bundle() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-Stale999.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-Stale999.js"): _FakeResponse(200, text="console.log('stale');"),
            **_route_responses(base_url, auth_enabled=True),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["exitCode"] == 1
    assert "runtime_frontend_main_asset_mismatch" in report["checks"]["runtimeBundle"]["reasonCodes"]


def test_partial_when_admin_status_json_is_present_but_surface_readiness_is_unverified() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            **_route_responses(base_url, auth_enabled=True),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=None,
        auth_headers=None,
    )

    assert report["summaryStatus"] == "PARTIAL"
    assert report["exitCode"] == 1
    assert report["checks"]["adminOpsStatus"]["status"] == "PASS"
    assert report["checks"]["surfaceReadiness"]["status"] == "PARTIAL"
    assert report["checks"]["surfaceReadiness"]["reasonCodes"] == ["surface_readiness_unverified"]


def test_fail_when_live_admin_status_returns_unauthorized() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            **_route_responses(base_url, auth_enabled=True, logged_in=True),
            ("GET", f"{base_url}/api/v1/admin/ops/status"): _FakeResponse(401, payload={"error": "unauthorized"}),
            ("GET", f"{base_url}/api/v1/admin/ops/surface-readiness"): _FakeResponse(
                401,
                payload={"error": "unauthorized"},
            ),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=None,
        surface_readiness_payload=None,
        auth_headers={"Authorization": "Bearer opaque"},
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["checks"]["adminOpsStatus"]["status"] == "FAIL"
    assert report["checks"]["adminOpsStatus"]["reasonCodes"] == ["admin_status_auth_required"]


def test_unauthenticated_authenticated_routes_are_partial_not_fail() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(
                200,
                payload=_auth_status_payload(auth_enabled=True, logged_in=False),
            ),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/evidence"): _FakeResponse(200, payload={"items": []}),
            (
                "GET",
                f"{base_url}/api/v1/stocks/AAPL/structure-decision",
            ): _FakeResponse(200, payload={"schemaVersion": "stock_structure_decision_v1"}),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "PARTIAL"
    assert report["exitCode"] == 1
    assert report["checks"]["publicRoutes"]["status"] == "PASS"
    assert report["checks"]["runtimeAuthMode"]["mode"] == "auth_enabled"
    assert report["checks"]["authenticatedRoutes"]["status"] == "PARTIAL"
    assert report["checks"]["authenticatedRoutes"]["expectationMode"] == "unauthenticated_rejection_expected"
    assert report["checks"]["authenticatedRoutes"]["reasonCodes"] == ["authenticated_routes_auth_required"]
    assert report["checks"]["authenticatedRoutes"]["failingRoutes"] == []
    assert report["checks"]["authenticatedRoutes"]["authRequiredRoutes"] == [
        {
            "method": "GET",
            "path": "/api/v1/research/radar",
            "anonymousHttpStatus": 401,
            "httpStatus": 401,
        },
        {
            "method": "GET",
            "path": "/api/v1/scanner/themes",
            "anonymousHttpStatus": 401,
            "httpStatus": 401,
        },
    ]
    assert report["checks"]["authenticatedRoutes"]["publiclyAvailableRoutes"] == []
    assert report["checks"]["authenticatedRoutes"]["noAuthPolicyMismatchRoutes"] == []


def test_auth_disabled_runtime_treats_open_protected_routes_as_expected() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(
                200,
                payload=_auth_status_payload(auth_enabled=False, logged_in=False),
            ),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(200, payload={"themes": []}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "PASS"
    assert report["checks"]["runtimeAuthMode"]["mode"] == "auth_disabled"
    assert report["checks"]["runtimeAuthMode"]["authEnabled"] is False
    assert report["checks"]["authenticatedRoutes"]["status"] == "PASS"
    assert report["checks"]["authenticatedRoutes"]["expectationMode"] == "auth_disabled_open"
    assert report["checks"]["authenticatedRoutes"]["authDisabledOpenRoutes"] == [
        {
            "method": "GET",
            "path": "/api/v1/research/radar",
            "anonymousHttpStatus": 200,
            "httpStatus": 200,
        },
        {
            "method": "GET",
            "path": "/api/v1/scanner/themes",
            "anonymousHttpStatus": 200,
            "httpStatus": 200,
        },
    ]
    assert report["checks"]["authenticatedRoutes"]["failingRoutes"] == []


def test_auth_disabled_runtime_still_fails_when_protected_route_rejects() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(
                200,
                payload=_auth_status_payload(auth_enabled=False, logged_in=False),
            ),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(200, payload={"themes": []}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["checks"]["runtimeAuthMode"]["mode"] == "auth_disabled"
    assert report["checks"]["authenticatedRoutes"]["status"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["reasonCodes"] == [
        "auth_disabled_route_rejected",
        "auth_disabled_route_unavailable",
    ]
    assert report["checks"]["authenticatedRoutes"]["failingRoutes"] == [
        {
            "method": "GET",
            "path": "/api/v1/research/radar",
            "anonymousHttpStatus": 401,
            "httpStatus": 401,
        }
    ]


def test_true_public_route_failure_still_fails_smoke() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(503, payload={"status": "down"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(
                200,
                payload=_auth_status_payload(auth_enabled=True, logged_in=False),
            ),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/evidence"): _FakeResponse(200, payload={"items": []}),
            (
                "GET",
                f"{base_url}/api/v1/stocks/AAPL/structure-decision",
            ): _FakeResponse(200, payload={"schemaVersion": "stock_structure_decision_v1"}),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["checks"]["publicRoutes"]["status"] == "FAIL"
    assert report["checks"]["publicRoutes"]["failingRoutes"] == [
        {"method": "GET", "path": "/api/health", "httpStatus": 503}
    ]
    assert report["checks"]["authenticatedRoutes"]["status"] == "PARTIAL"


def test_authenticated_routes_pass_with_supplied_auth_headers() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(
                200,
                payload=_auth_status_payload(auth_enabled=True, logged_in=True),
            ),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/evidence"): _FakeResponse(200, payload={"items": []}),
            (
                "GET",
                f"{base_url}/api/v1/stocks/AAPL/structure-decision",
            ): _FakeResponse(200, payload={"schemaVersion": "stock_structure_decision_v1"}),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
            ("GET", f"{base_url}/api/v1/research/radar", "auth"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
            ("GET", f"{base_url}/api/v1/scanner/themes", "auth"): _FakeResponse(200, payload={"themes": []}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers={"Cookie": "opaque-admin-session"},
    )

    assert report["summaryStatus"] == "PASS"
    assert report["checks"]["authenticatedRoutes"]["status"] == "PASS"
    assert report["checks"]["authenticatedRoutes"]["expectationMode"] == "authenticated_success_expected"
    assert report["checks"]["authenticatedRoutes"]["checkedRoutes"] == [
        {
            "method": "GET",
            "path": "/api/v1/research/radar",
            "anonymousHttpStatus": 401,
            "httpStatus": 200,
        },
        {
            "method": "GET",
            "path": "/api/v1/scanner/themes",
            "anonymousHttpStatus": 401,
            "httpStatus": 200,
        },
    ]


def test_authenticated_routes_fail_when_auth_supplied_but_route_unavailable() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(
                200,
                payload=_auth_status_payload(auth_enabled=True, logged_in=True),
            ),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/evidence"): _FakeResponse(200, payload={"items": []}),
            (
                "GET",
                f"{base_url}/api/v1/stocks/AAPL/structure-decision",
            ): _FakeResponse(200, payload={"schemaVersion": "stock_structure_decision_v1"}),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
            ("GET", f"{base_url}/api/v1/research/radar", "auth"): _FakeResponse(503, payload={"detail": "Unavailable"}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(401, payload={"detail": "Unauthorized"}),
            ("GET", f"{base_url}/api/v1/scanner/themes", "auth"): _FakeResponse(200, payload={"themes": []}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers={"Authorization": "Bearer opaque"},
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["status"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["failingRoutes"] == [
        {
            "method": "GET",
            "path": "/api/v1/research/radar",
            "anonymousHttpStatus": 401,
            "httpStatus": 503,
        }
    ]


def test_authenticated_routes_fail_when_noauth_request_is_publicly_available() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            **_route_responses(base_url, auth_enabled=True),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(200, payload={"items": []}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["status"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["reasonCodes"] == ["authenticated_route_publicly_available"]
    assert report["checks"]["authenticatedRoutes"]["publiclyAvailableRoutes"] == [
        {"method": "GET", "path": "/api/v1/research/radar", "httpStatus": 200}
    ]
    assert report["checks"]["authenticatedRoutes"]["noAuthPolicyMismatchRoutes"] == [
        {"method": "GET", "path": "/api/v1/research/radar", "httpStatus": 200}
    ]


def test_authenticated_routes_fail_when_noauth_request_is_rate_limited() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            **_route_responses(base_url, auth_enabled=True),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(429, payload={"error": "rate_limited"}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["status"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["reasonCodes"] == [
        "authenticated_route_noauth_policy_mismatch"
    ]
    assert report["checks"]["authenticatedRoutes"]["publiclyAvailableRoutes"] == []
    assert report["checks"]["authenticatedRoutes"]["noAuthPolicyMismatchRoutes"] == [
        {"method": "GET", "path": "/api/v1/research/radar", "httpStatus": 429}
    ]


def test_verify_surface_readiness_payload_accepts_bounded_contract() -> None:
    result = smoke.verify_surface_readiness_payload(_surface_readiness_payload())

    assert result.ok is True
    assert result.error_codes == []
    assert result.payload["metadata"]["contract"] == "backend_surface_contract_parity_v1"


def test_runtime_auth_mode_fails_closed_when_auth_status_payload_is_ambiguous() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(200, payload={"loggedIn": False}),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/stocks/AAPL/quote"): _FakeResponse(200, payload={"stockCode": "AAPL"}),
            ("GET", f"{base_url}/api/v1/research/radar"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(200, payload={"themes": []}),
        }
    )

    report = smoke.run_runtime_smoke(
        base_url=base_url,
        client=client,
        git_head="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        local_build_result=smoke.VerificationResult(ok=True, payload=_local_provenance()),
        admin_status_payload=_admin_status_payload(),
        surface_readiness_payload=_surface_readiness_payload(),
        auth_headers=None,
    )

    assert report["summaryStatus"] == "FAIL"
    assert report["checks"]["runtimeAuthMode"]["status"] == "FAIL"
    assert report["checks"]["runtimeAuthMode"]["reasonCodes"] == ["runtime_auth_mode_missing"]
    assert report["checks"]["authenticatedRoutes"]["status"] == "FAIL"
    assert report["checks"]["authenticatedRoutes"]["reasonCodes"] == ["runtime_auth_mode_unverified"]


def test_main_supports_json_stdout_with_admin_status_file(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    status_path = tmp_path / "admin-status.json"
    status_path.write_text(json.dumps(_admin_status_payload()), encoding="utf-8")

    monkeypatch.setattr(smoke, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(smoke, "read_git_head", lambda _repo_root: "e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590")
    monkeypatch.setattr(
        smoke,
        "verify_local_build",
        lambda **_kwargs: smoke.VerificationResult(ok=True, payload=_local_provenance()),
    )
    monkeypatch.setattr(
        smoke,
        "build_http_client",
        lambda timeout=5.0: _FakeClient(
            {
                ("GET", "http://127.0.0.1:8000/"): _FakeResponse(
                    200,
                    text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
                ),
                ("GET", "http://127.0.0.1:8000/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="ok"),
                **_route_responses("http://127.0.0.1:8000", auth_enabled=True),
            }
        ),
    )

    exit_code = smoke.main(["--admin-status-json", str(status_path), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summaryStatus"] == "PARTIAL"
    assert payload["checks"]["adminOpsStatus"]["status"] == "PASS"
    assert payload["checks"]["runtimeAuthMode"]["mode"] == "auth_enabled"
    assert payload["checks"]["authenticatedRoutes"]["status"] == "PARTIAL"


def test_parse_auth_headers_keeps_values_but_report_does_not_echo_them() -> None:
    headers = smoke._parse_auth_headers(
        [
            "Authorization: Bearer opaque-token",
            "Cookie: session=opaque-cookie",
            "X-Admin-Password: secret-password",
        ]
    )

    assert headers == {
        "Authorization": "Bearer opaque-token",
        "Cookie": "session=opaque-cookie",
        "X-Admin-Password": "secret-password",
    }

    report = {
        "checks": {
            "authenticatedRoutes": {
                "status": "PARTIAL",
                "reasonCodes": ["authenticated_routes_auth_required"],
            }
        }
    }
    output = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert "opaque-token" not in output
    assert "opaque-cookie" not in output
    assert "secret-password" not in output


def test_base_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="base_url_must_not_include_credentials"):
        smoke.clean_base_url("http://user:secret@127.0.0.1:8000")


def test_direct_script_help_entrypoint_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/uat_runtime_smoke_pack.py", "--help"],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "UAT runtime smoke pack" in result.stdout
