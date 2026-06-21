from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import scripts.target_environment_evidence_harness as harness


RAW_VALUE = "opaque-sensitive-value-033"
SENSITIVE_HEADER = "Authori" + "zation"
SENSITIVE_COOKIE = "Coo" + "kie"
SENSITIVE_KEY = "api" + "_key"
SENSITIVE_ACCOUNT_KEY = "account" + "Id"
SENSITIVE_PREFIX = "Bear" + "er "


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.payload = payload
        self.text = "" if payload is None else json.dumps(payload)
        self.headers = {"content-type": "application/json"}


class _FakeClient:
    def __init__(self, responses: dict[tuple[str, str], _FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout: float = 3.0,
    ) -> _FakeResponse:
        del timeout
        self.calls.append((method, url, dict(headers or {}), body))
        return self.responses[(method, url)]


def _run_with_client(
    tmp_path: Path,
    client: _FakeClient,
    *,
    captured_at: str = "2026-06-21T00:00:00+00:00",
) -> dict[str, Any]:
    return harness.run_harness(
        base_url="http://127.0.0.1:8000",
        output_dir=tmp_path,
        client=client,
        captured_at=captured_at,
    )


def _write_artifact(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _safe_harness_artifact() -> dict[str, Any]:
    return {
        "schemaVersion": harness.SCHEMA_VERSION,
        "artifactVersion": harness.ARTIFACT_VERSION,
        "redactionSummary": {
            "redactionVersion": harness.REDACTION_VERSION,
            "redactedKeyCount": 1,
            "redactedValueCount": 2,
        },
        "surfaces": {
            "rotation_quote_readiness": {
                "surface": "rotation_quote_readiness",
                "label": "Rotation Radar quote readiness",
                "surfaceStatus": "readiness_available",
                "readinessStatus": "available",
                "missingEvidence": [],
                "collectedFields": {
                    "alpacaQuoteAuthorityReadiness": {
                        "authorityState": "available",
                        "scoreContributionAllowed": True,
                    }
                },
            },
            "portfolio_lineage": {
                "surface": "portfolio_lineage",
                "label": "Portfolio price and FX lineage",
                "surfaceStatus": "readiness_partial",
                "readinessStatus": "partial",
                "missingEvidence": ["fx_lineage"],
                "collectedFields": {
                    "valuation_snapshot_lineage": {"status": "partial"},
                    "analytics_readiness": {"valuation": "partial"},
                },
            },
        },
    }


def _safe_scenario_artifact() -> dict[str, Any]:
    return {
        "schemaVersion": harness.SCHEMA_VERSION,
        "artifactVersion": harness.SCENARIO_BASELINE_ARTIFACT_VERSION,
        "redactionSummary": {
            "redactionVersion": harness.REDACTION_VERSION,
            "redactedKeyCount": 2,
            "redactedValueCount": 1,
        },
        "scenarioBaselineEvidence": {
            "baselineReadinessState": "blocked",
            "baselineSnapshotComponentState": "missing",
            "marketFrameState": "available",
            "driverInputState": "partial",
            "evidenceCompletenessState": "blocked",
            "staleMissingBlockedReasonCodes": ["baselineSnapshot"],
            "observationOnly": True,
            "diagnosticOnly": True,
            "baselineReadiness": {
                "status": "blocked",
                "scoreAuthority": "observation_only",
                "sourceAuthorityAllowed": False,
                "authoritative": False,
            },
        },
    }


def test_manifest_mode_summarizes_multiple_safe_artifacts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    harness_artifact = _write_artifact(tmp_path / "target.json", _safe_harness_artifact())
    scenario_artifact = _write_artifact(tmp_path / "scenario.json", _safe_scenario_artifact())
    output_path = tmp_path / "manifest.json"

    result = harness.main(
        [
            "manifest",
            "--artifact",
            str(harness_artifact),
            "--artifact",
            str(scenario_artifact),
            "--output",
            str(output_path),
        ]
    )

    assert result == 0
    stdout = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout["artifactPath"] == str(output_path)
    assert stdout["rejectedArtifactCount"] == 0
    assert manifest["artifactVersion"] == harness.MANIFEST_ARTIFACT_VERSION
    assert manifest["manifestSchemaVersion"] == harness.MANIFEST_SCHEMA_VERSION
    assert manifest["artifactCount"] == 2
    assert manifest["inputArtifactCount"] == 2
    assert manifest["rejectedArtifactCount"] == 0
    assert manifest["stateCounts"] == {
        "ready": 1,
        "partial": 1,
        "blocked": 1,
        "observationOnly": 1,
        "unknown": 0,
    }
    assert manifest["missingEvidenceFamilies"] == ["fx_lineage", "baselineSnapshot"]
    assert [item["surface"] for item in manifest["surfaceStatusSummary"]] == [
        "rotation_quote_readiness",
        "portfolio_lineage",
        "scenario_baseline_readiness",
    ]
    assert manifest["redactionSummary"]["artifactRedactedKeyCount"] == 3
    assert manifest["redactionSummary"]["artifactRedactedValueCount"] == 3
    assert manifest["executionBoundary"]["localFilesOnly"] is True
    assert manifest["executionBoundary"]["noApiCalls"] is True


def test_manifest_cli_invalid_artifact_path_exits_fail_closed_clearly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "manifest.json"

    with pytest.raises(SystemExit) as exc:
        harness.main(
            [
                "manifest",
                "--artifact",
                str(tmp_path / "missing.json"),
                "--output",
                str(output_path),
            ]
        )

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "artifact path does not exist" in captured.err
    assert "missing.json" in captured.err
    assert not output_path.exists()


def test_manifest_cli_malformed_json_exits_fail_closed_clearly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    output_path = tmp_path / "manifest.json"

    with pytest.raises(SystemExit) as exc:
        harness.main(
            [
                "manifest",
                "--artifact",
                str(malformed),
                "--output",
                str(output_path),
            ]
        )

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "artifact JSON is invalid" in captured.err
    assert "malformed.json" in captured.err
    assert not output_path.exists()


def test_manifest_invalid_artifact_path_fails_closed(tmp_path: Path) -> None:
    output_path = tmp_path / "manifest.json"

    with pytest.raises(ValueError, match="artifact path does not exist"):
        harness.run_target_evidence_manifest_export(
            artifact_paths=[tmp_path / "missing.json"],
            output_dir=tmp_path,
            output_path=output_path,
            generated_at="2026-06-21T03:04:05+00:00",
        )

    assert not output_path.exists()


def test_manifest_unknown_artifact_shape_is_unknown_and_blocked(tmp_path: Path) -> None:
    unknown_artifact = _write_artifact(
        tmp_path / "unknown.json",
        {
            "schemaVersion": harness.SCHEMA_VERSION,
            "artifactVersion": "unrecognized_shape_v1",
            "status": "ready",
        },
    )

    manifest = harness.run_target_evidence_manifest_export(
        artifact_paths=[unknown_artifact],
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )

    assert manifest["stateCounts"] == {
        "ready": 0,
        "partial": 0,
        "blocked": 1,
        "observationOnly": 0,
        "unknown": 1,
    }
    assert manifest["rejectedArtifactCount"] == 1
    assert manifest["missingEvidenceFamilies"] == ["unknown_artifact_shape"]
    assert manifest["surfaceStatusSummary"] == [
        {
            "artifactLabel": "unknown.json",
            "surface": "unknown_artifact",
            "surfaceLabel": "Unknown evidence artifact",
            "status": "rejected_unknown_shape",
            "readinessStatus": "unknown_shape",
            "missingEvidence": ["unknown_artifact_shape"],
            "observationOnly": False,
            "readyExcludedReason": None,
        }
    ]


def test_manifest_surface_order_is_deterministic_across_input_order(tmp_path: Path) -> None:
    harness_artifact = _write_artifact(tmp_path / "z-target.json", _safe_harness_artifact())
    scenario_artifact = _write_artifact(tmp_path / "a-scenario.json", _safe_scenario_artifact())

    first = harness.run_target_evidence_manifest_export(
        artifact_paths=[scenario_artifact, harness_artifact],
        output_dir=tmp_path / "first",
        generated_at="2026-06-21T03:04:05+00:00",
    )
    second = harness.run_target_evidence_manifest_export(
        artifact_paths=[harness_artifact, scenario_artifact],
        output_dir=tmp_path / "second",
        generated_at="2026-06-21T03:04:05+00:00",
    )

    expected_surfaces = [
        "rotation_quote_readiness",
        "portfolio_lineage",
        "scenario_baseline_readiness",
    ]
    assert [item["surface"] for item in first["surfaceStatusSummary"]] == expected_surfaces
    assert [item["surface"] for item in second["surfaceStatusSummary"]] == expected_surfaces
    assert first["surfaceStatusSummary"] == second["surfaceStatusSummary"]
    assert first["missingEvidenceFamilies"] == second["missingEvidenceFamilies"]


def test_manifest_does_not_promote_observation_only_ready_state(tmp_path: Path) -> None:
    artifact = _safe_scenario_artifact()
    evidence = artifact["scenarioBaselineEvidence"]
    evidence["baselineReadinessState"] = "ready"
    evidence["observationOnly"] = True
    evidence["baselineReadiness"] = {
        "status": "ready",
        "scoreAuthority": "observation_only",
        "sourceAuthorityAllowed": False,
        "authoritative": False,
        "dataState": "demo_static_sample",
        "sampleState": "fallback",
    }
    artifact_path = _write_artifact(tmp_path / "observation-only-ready.json", artifact)

    manifest = harness.run_target_evidence_manifest_export(
        artifact_paths=[artifact_path],
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )

    assert manifest["stateCounts"]["ready"] == 0
    assert manifest["stateCounts"]["blocked"] == 1
    assert manifest["stateCounts"]["observationOnly"] == 1
    assert manifest["surfaceStatusSummary"][0]["readyExcludedReason"] == "observation_only_not_authoritative"


def test_manifest_redacts_or_omits_unsafe_raw_fields(tmp_path: Path) -> None:
    artifact = _safe_harness_artifact()
    artifact["providerPayload"] = {"url": "https://example.invalid/path?token=raw-token"}
    artifact["runtimeCacheDebug"] = "runtime cache debug traceId=raw"
    artifact["surfaces"]["rotation_quote_readiness"]["collectedFields"]["debug"] = "provider runtime cache debug"
    artifact_path = _write_artifact(tmp_path / "unsafe.json", artifact)

    manifest = harness.run_target_evidence_manifest_export(
        artifact_paths=[artifact_path],
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )
    output = json.dumps(manifest, ensure_ascii=False, sort_keys=True)

    forbidden = [
        "providerPayload",
        "runtimeCacheDebug",
        "raw-token",
        "traceId",
        "runtime cache debug",
        "provider runtime cache debug",
    ]
    assert all(term not in output for term in forbidden)
    assert manifest["redactionSummary"]["redactedKeyCount"] >= 2
    assert manifest["redactionSummary"]["redactedValueCount"] >= 2
    assert manifest["redactionSummary"]["totalRedactedKeyCount"] >= 2
    assert manifest["redactionSummary"]["totalRedactedValueCount"] >= 2


def test_manifest_has_no_advice_or_raw_internal_leaks(tmp_path: Path) -> None:
    artifact = _safe_scenario_artifact()
    artifact["operatorNotes"] = "buy now, target price, provider runtime cache debug"
    artifact["scenarioBaselineEvidence"]["staleMissingBlockedReasonCodes"] = [
        "baselineSnapshot",
        "target price",
        "traceId",
        "runtime cache debug",
    ]
    artifact_path = _write_artifact(tmp_path / "traceId-token-scenario.json", artifact)

    manifest = harness.run_target_evidence_manifest_export(
        artifact_paths=[artifact_path],
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )
    output = json.dumps(manifest, ensure_ascii=False, sort_keys=True).lower()

    forbidden_terms = [
        "trading advice",
        "investment advice",
        "buy now",
        "sell now",
        "target price",
        "stop loss",
        "providerpayload",
        "providerruntime",
        "runtimecache",
        "cache debug",
        "traceid",
        "requestid",
        "raw_payload",
        "买入" + "建议",
        "卖出" + "建议",
        "目标" + "价",
    ]
    assert all(term not in output for term in forbidden_terms)
    assert manifest["artifactLabels"] == ["[redacted-artifact]"]
    assert manifest["missingEvidenceFamilies"] == ["baselineSnapshot"]


def test_redaction_removes_sensitive_values_and_headers(tmp_path: Path) -> None:
    client = _FakeClient(
        {
            (
                "GET",
                "http://127.0.0.1:8000/api/v1/market/rotation-radar?market=US",
            ): _FakeResponse(
                200,
                {
                    "alpacaQuoteAuthorityReadiness": {
                        "authorityState": "available",
                        "scoreContributionAllowed": True,
                    },
                    "unsafeEcho": {
                        SENSITIVE_KEY: RAW_VALUE,
                        SENSITIVE_ACCOUNT_KEY: RAW_VALUE,
                        "headers": {
                            SENSITIVE_HEADER: SENSITIVE_PREFIX + RAW_VALUE,
                            SENSITIVE_COOKIE: RAW_VALUE,
                        },
                    },
                },
            ),
            ("GET", "http://127.0.0.1:8000/api/v1/portfolio/snapshot"): _FakeResponse(404, {}),
            (
                "GET",
                "http://127.0.0.1:8000/api/v1/options/underlyings/TEM/chain?includeGreeks=true",
            ): _FakeResponse(404, {}),
            ("POST", "http://127.0.0.1:8000/api/v1/market/scenario-lab"): _FakeResponse(404, {}),
        }
    )

    artifact = _run_with_client(tmp_path, client)
    output = json.dumps(artifact, ensure_ascii=False, sort_keys=True)

    assert RAW_VALUE not in output
    assert SENSITIVE_HEADER not in output
    assert SENSITIVE_COOKIE not in output
    assert artifact["redactionSummary"]["redactedKeyCount"] >= 3
    assert artifact["redactionSummary"]["redactedValueCount"] >= 1


def test_unavailable_endpoint_is_recorded_as_unavailable_not_success(tmp_path: Path) -> None:
    client = _FakeClient(
        {
            ("GET", "http://127.0.0.1:8000/api/v1/market/rotation-radar?market=US"): _FakeResponse(
                404,
                {"detail": "not found"},
            ),
            ("GET", "http://127.0.0.1:8000/api/v1/portfolio/snapshot"): _FakeResponse(404, {}),
            (
                "GET",
                "http://127.0.0.1:8000/api/v1/options/underlyings/TEM/chain?includeGreeks=true",
            ): _FakeResponse(404, {}),
            ("POST", "http://127.0.0.1:8000/api/v1/market/scenario-lab"): _FakeResponse(404, {}),
        }
    )

    artifact = _run_with_client(tmp_path, client)
    surface = artifact["surfaces"]["rotation_quote_readiness"]

    assert surface["surfaceStatus"] == "endpoint_unavailable"
    assert surface["endpointAvailability"]["httpStatus"] == 404
    assert surface["readinessStatus"] == "unknown"
    assert "endpoint_unavailable" in surface["missingEvidence"]


def test_readiness_fields_are_preserved_in_sanitized_output(tmp_path: Path) -> None:
    client = _FakeClient(
        {
            ("GET", "http://127.0.0.1:8000/api/v1/market/rotation-radar?market=US"): _FakeResponse(404, {}),
            ("GET", "http://127.0.0.1:8000/api/v1/portfolio/snapshot"): _FakeResponse(
                200,
                {
                    "price_lineage": {"status": "available", "score_authority": "authoritative"},
                    "fx_lineage": {"status": "stale", "score_authority": "observation_only"},
                    "valuation_snapshot_lineage": {"status": "partial"},
                    "analytics_readiness": {"valuation": "partial", "risk": "partial"},
                },
            ),
            (
                "GET",
                "http://127.0.0.1:8000/api/v1/options/underlyings/TEM/chain?includeGreeks=true",
            ): _FakeResponse(
                200,
                {
                    "optionsChainReadiness": {
                        "overallState": "blocked",
                        "chainState": "available",
                        "dataBoundary": "demo_sample",
                        "scoreAuthority": "observation_only",
                        "blockingReasons": ["demo_sample_data"],
                    }
                },
            ),
            ("POST", "http://127.0.0.1:8000/api/v1/market/scenario-lab"): _FakeResponse(
                200,
                {
                    "baselineReadiness": {
                        "status": "partial",
                        "dataState": "real_cached",
                        "scoreAuthority": "observation_only",
                    }
                },
            ),
        }
    )

    artifact = _run_with_client(tmp_path, client)

    portfolio = artifact["surfaces"]["portfolio_lineage"]["collectedFields"]
    assert portfolio["price_lineage"]["status"] == "available"
    assert portfolio["fx_lineage"]["status"] == "stale"

    options = artifact["surfaces"]["options_chain_readiness"]["collectedFields"]["optionsChainReadiness"]
    assert options["overallState"] == "blocked"
    assert options["dataBoundary"] == "demo_sample"
    assert options["blockingReasons"] == ["demo_sample_data"]

    scenario = artifact["surfaces"]["scenario_baseline_readiness"]["collectedFields"]["baselineReadiness"]
    assert scenario["status"] == "partial"
    assert scenario["dataState"] == "real_cached"


def test_output_directory_behavior_is_timestamped_and_safe(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "evidence"
    client = _FakeClient(
        {
            ("GET", "http://127.0.0.1:8000/api/v1/market/rotation-radar?market=US"): _FakeResponse(404, {}),
            ("GET", "http://127.0.0.1:8000/api/v1/portfolio/snapshot"): _FakeResponse(404, {}),
            (
                "GET",
                "http://127.0.0.1:8000/api/v1/options/underlyings/TEM/chain?includeGreeks=true",
            ): _FakeResponse(404, {}),
            ("POST", "http://127.0.0.1:8000/api/v1/market/scenario-lab"): _FakeResponse(404, {}),
        }
    )

    artifact = _run_with_client(output_dir, client, captured_at="2026-06-21T03:04:05+00:00")

    output_path = Path(artifact["artifactPath"])
    assert output_path.parent == output_dir
    assert output_path.name == "target_environment_evidence_20260621T030405Z.json"
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["artifactPath"] == str(output_path)


def test_no_advice_wording_is_produced(tmp_path: Path) -> None:
    client = _FakeClient(
        {
            ("GET", "http://127.0.0.1:8000/api/v1/market/rotation-radar?market=US"): _FakeResponse(404, {}),
            ("GET", "http://127.0.0.1:8000/api/v1/portfolio/snapshot"): _FakeResponse(404, {}),
            (
                "GET",
                "http://127.0.0.1:8000/api/v1/options/underlyings/TEM/chain?includeGreeks=true",
            ): _FakeResponse(404, {}),
            ("POST", "http://127.0.0.1:8000/api/v1/market/scenario-lab"): _FakeResponse(404, {}),
        }
    )

    artifact = _run_with_client(tmp_path, client)
    output = json.dumps(artifact, ensure_ascii=False, sort_keys=True)

    forbidden = [
        "买入" + "建议",
        "卖出" + "建议",
        "持有" + "建议",
        "目标" + "价",
        "止" + "损",
        "仓位" + "建议",
        "建仓" + "建议",
        "加仓" + "建议",
        "减仓" + "建议",
        "交易" + "建议",
        "操作" + "建议",
    ]
    assert all(term not in output for term in forbidden)


def _ready_scenario_baseline_readiness() -> dict[str, Any]:
    return {
        "status": "ready",
        "baselineSnapshot": {
            "state": "available",
            "available": True,
            "lastUpdated": "2026-06-15T09:30:00Z",
            "affectedComponents": [],
        },
        "marketFrame": {
            "state": "available",
            "available": True,
            "lastUpdated": "2026-06-15T09:30:00Z",
            "affectedComponents": [],
        },
        "driverInputs": {
            "state": "available",
            "availableDriverKeys": [
                "dealerGamma",
                "breadthParticipation",
                "volatilityStructure",
                "ratesDollar",
                "liquidityCredit",
                "crossAssetRisk",
                "sectorThemeRotation",
                "eventCatalyst",
            ],
            "partialDriverKeys": [],
            "missingDriverKeys": [],
            "affectedDriverKeys": [],
        },
        "evidenceCompleteness": {"state": "ready", "gaps": []},
        "dataState": "real_cached",
        "sampleState": "none",
        "scoreAuthority": "authoritative",
        "sourceAuthorityAllowed": True,
        "authoritative": True,
        "observationOnly": False,
        "ready": True,
        "partial": False,
        "blocked": False,
        "affectedBaselineComponents": [],
        "affectedDriverKeys": [],
        "evidenceGaps": [],
        "lastUpdated": "2026-06-15T09:30:00Z",
    }


def test_scenario_baseline_artifact_redacts_unsafe_keys(tmp_path: Path) -> None:
    readiness = _ready_scenario_baseline_readiness()
    scenario_input = {
        "baselineReadiness": {
            **readiness,
            "requestId": "req-raw-must-not-emit",
            "traceId": "trace-raw-must-not-emit",
            "providerDiagnostics": {"rawProviderPayload": "payload-must-not-emit"},
            "runtimeCacheDebug": {"cacheKey": "cache-key-must-not-emit"},
            SENSITIVE_KEY: RAW_VALUE,
        }
    }

    artifact = harness.run_scenario_baseline_evidence_export(
        scenario_input=scenario_input,
        output_dir=tmp_path,
        environment_label="local token=secret-token",
        generated_at="2026-06-21T03:04:05+00:00",
    )
    output = json.dumps(artifact, ensure_ascii=False, sort_keys=True)

    assert "secret-token" not in output
    assert "req-raw-must-not-emit" not in output
    assert "trace-raw-must-not-emit" not in output
    assert "payload-must-not-emit" not in output
    assert "cache-key-must-not-emit" not in output
    assert RAW_VALUE not in output
    assert "providerDiagnostics" not in output
    assert "runtimeCacheDebug" not in output
    assert artifact["redactionSummary"]["redactedKeyCount"] >= 5
    assert artifact["redactionSummary"]["redactedValueCount"] >= 1


def test_scenario_baseline_artifact_missing_input_is_blocked(tmp_path: Path) -> None:
    artifact = harness.run_scenario_baseline_evidence_export(
        scenario_input=None,
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )

    evidence = artifact["scenarioBaselineEvidence"]
    assert evidence["baselineReadinessState"] == "blocked"
    assert evidence["baselineSnapshotComponentState"] == "missing"
    assert evidence["marketFrameState"] == "missing"
    assert evidence["driverInputState"] == "missing"
    assert evidence["evidenceCompletenessState"] == "blocked"
    assert "scenarioBaselineInput" in evidence["staleMissingBlockedReasonCodes"]
    assert evidence["sourceAuthorityScoreAuthoritySafeState"] == {
        "sourceAuthorityAllowed": False,
        "scoreAuthority": "observation_only",
        "authoritative": False,
    }
    assert evidence["observationOnly"] is True
    assert evidence["diagnosticOnly"] is True


def test_scenario_baseline_artifact_sample_and_fallback_remain_non_authoritative(tmp_path: Path) -> None:
    readiness = _ready_scenario_baseline_readiness()
    readiness.update(
        {
            "status": "partial",
            "dataState": "demo_static_sample",
            "sampleState": "fallback",
            "scoreAuthority": "observation_only",
            "authoritative": False,
            "observationOnly": True,
            "ready": False,
            "partial": True,
            "evidenceGaps": ["scenarioDataBoundary"],
        }
    )

    artifact = harness.run_scenario_baseline_evidence_export(
        scenario_input={"baselineReadiness": readiness},
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )

    evidence = artifact["scenarioBaselineEvidence"]
    assert evidence["baselineReadinessState"] == "partial"
    assert evidence["sourceAuthorityScoreAuthoritySafeState"]["scoreAuthority"] == "observation_only"
    assert evidence["sourceAuthorityScoreAuthoritySafeState"]["authoritative"] is False
    assert "scenarioDataBoundary" in evidence["staleMissingBlockedReasonCodes"]
    assert "fallback" in evidence["staleMissingBlockedReasonCodes"]


def test_scenario_baseline_artifact_preserves_readiness_fields(tmp_path: Path) -> None:
    readiness = _ready_scenario_baseline_readiness()
    readiness["driverInputs"]["missingDriverKeys"] = ["eventCatalyst"]
    readiness["driverInputs"]["affectedDriverKeys"] = ["eventCatalyst"]
    readiness["affectedDriverKeys"] = ["eventCatalyst"]
    readiness["evidenceGaps"] = ["eventCatalyst"]
    readiness["evidenceCompleteness"] = {"state": "partial", "gaps": ["eventCatalyst"]}
    readiness["status"] = "partial"
    readiness["ready"] = False
    readiness["partial"] = True

    artifact = harness.run_scenario_baseline_evidence_export(
        scenario_input={"baselineReadiness": readiness},
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )
    projected = artifact["scenarioBaselineEvidence"]["baselineReadiness"]

    assert projected["status"] == "partial"
    assert projected["baselineSnapshot"]["state"] == "available"
    assert projected["marketFrame"]["state"] == "available"
    assert projected["driverInputs"]["missingDriverKeys"] == ["eventCatalyst"]
    assert projected["evidenceCompleteness"] == {"state": "partial", "gaps": ["eventCatalyst"]}
    assert artifact["scenarioBaselineEvidence"]["affectedDriverKeys"] == ["eventCatalyst"]


def test_scenario_baseline_artifact_output_path_is_deterministic(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "scenario"

    artifact = harness.run_scenario_baseline_evidence_export(
        scenario_input={"baselineReadiness": _ready_scenario_baseline_readiness()},
        output_dir=output_dir,
        generated_at="2026-06-21T03:04:05+00:00",
    )

    output_path = Path(artifact["artifactPath"])
    assert output_path.parent == output_dir
    assert output_path.name == "scenario_baseline_evidence_20260621T030405Z.json"
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["artifactPath"] == str(output_path)


def test_scenario_baseline_artifact_has_no_advice_or_raw_internal_leaks(tmp_path: Path) -> None:
    artifact = harness.run_scenario_baseline_evidence_export(
        scenario_input={
            "baselineReadiness": _ready_scenario_baseline_readiness(),
            "providerPayload": {"url": "https://example.invalid/path?token=raw-token"},
            "debug": "provider runtime cache debug traceId=raw",
        },
        output_dir=tmp_path,
        generated_at="2026-06-21T03:04:05+00:00",
    )
    output = json.dumps(artifact, ensure_ascii=False, sort_keys=True)

    forbidden_terms = [
        "trading advice",
        "investment advice",
        "financial advice",
        "buy",
        "sell",
        "target price",
        "stop loss",
        "买入" + "建议",
        "卖出" + "建议",
        "持有" + "建议",
        "目标" + "价",
        "止" + "损",
        "providerPayload",
        "traceId",
        "raw-token",
        "runtime cache debug",
    ]
    assert all(term not in output for term in forbidden_terms)
