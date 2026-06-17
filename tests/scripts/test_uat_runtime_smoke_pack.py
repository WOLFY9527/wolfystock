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
    def __init__(self, responses: dict[tuple[str, str], _FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def request(self, method: str, url: str, headers: dict[str, str] | None = None) -> _FakeResponse:
        self.calls.append((method, url, dict(headers or {})))
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


def test_probe_runtime_bundle_accepts_matching_root_asset_and_public_routes() -> None:
    base_url = "http://127.0.0.1:8000"
    client = _FakeClient(
        {
            ("GET", f"{base_url}/"): _FakeResponse(
                200,
                text='<html><head><script type="module" crossorigin src="/assets/index-CKPdXr8Q.js"></script></head></html>',
            ),
            ("GET", f"{base_url}/assets/index-CKPdXr8Q.js"): _FakeResponse(200, text="console.log('ok');"),
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(200, payload={"authenticated": False}),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(200, payload={"themes": []}),
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
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(200, payload={"authenticated": False}),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
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
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(200, payload={"authenticated": False}),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(200, payload={"themes": []}),
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
            ("GET", f"{base_url}/api/health"): _FakeResponse(200, payload={"status": "ok"}),
            ("GET", f"{base_url}/api/v1/auth/status"): _FakeResponse(200, payload={"authenticated": False}),
            ("GET", f"{base_url}/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
            ("GET", f"{base_url}/api/v1/scanner/themes"): _FakeResponse(200, payload={"themes": []}),
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


def test_verify_surface_readiness_payload_accepts_bounded_contract() -> None:
    result = smoke.verify_surface_readiness_payload(_surface_readiness_payload())

    assert result.ok is True
    assert result.error_codes == []
    assert result.payload["metadata"]["contract"] == "backend_surface_contract_parity_v1"


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
                ("GET", "http://127.0.0.1:8000/api/health"): _FakeResponse(200, payload={"status": "ok"}),
                ("GET", "http://127.0.0.1:8000/api/v1/auth/status"): _FakeResponse(200, payload={"authenticated": False}),
                ("GET", "http://127.0.0.1:8000/api/v1/market-overview/indices"): _FakeResponse(200, payload={"items": []}),
                ("GET", "http://127.0.0.1:8000/api/v1/scanner/themes"): _FakeResponse(200, payload={"themes": []}),
            }
        ),
    )

    exit_code = smoke.main(["--admin-status-json", str(status_path), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summaryStatus"] == "PARTIAL"
    assert payload["checks"]["adminOpsStatus"]["status"] == "PASS"


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
