from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
