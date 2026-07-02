from __future__ import annotations

import json

from scripts import check_market_regime_projection_runtime as verifier


FORBIDDEN_OUTPUT_TOKENS = (
    "traceback",
    "filenotfounderror",
    "rawpayload",
    "/private/",
    "/var/folders/",
    ".parquet",
    ".sqlite",
    ".duckdb",
    "buy",
    "sell",
    "hold",
    "recommendation",
    "target price",
    "stop loss",
)


def test_fixture_temp_mode_verifies_ready_blocked_and_failed_closed(capsys) -> None:
    exit_code = verifier.main(["--fixture-temp", "--json"])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "ok"
    assert summary["contractVersion"] == "market_regime_projection_runtime_verifier_v1"
    assert set(summary["scenarios"]) == {"ready", "blocked", "failed_closed"}

    ready = summary["scenarios"]["ready"]
    assert ready["status"] == "ok"
    assert ready["standaloneEvidencePack"]["status"] == "ready"
    assert ready["marketOverviewProjection"]["status"] == "ready"
    assert ready["decisionCockpitProjection"]["status"] == "ready"
    assert ready["consistency"]["consistent"] is True
    assert ready["safety"] == {
        "providerCallsEnabled": False,
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "externalCallsEnabled": False,
    }

    blocked = summary["scenarios"]["blocked"]
    assert blocked["status"] == "ok"
    assert blocked["standaloneEvidencePack"]["status"] == "blocked"
    assert blocked["decisionCockpitProjection"]["status"] == "blocked"
    assert blocked["marketOverviewProjection"]["label"] == "insufficient_data"
    assert blocked["decisionCockpitProjection"]["evidencePreview"]["dataCoverage"]["skippedSymbols"] == [
        {"reason": "missing", "symbol": "AAPL"}
    ]

    failed = summary["scenarios"]["failed_closed"]
    assert failed["status"] == "ok"
    assert failed["standaloneEvidencePack"]["status"] == "failed_closed"
    assert failed["marketOverviewProjection"]["label"] == "insufficient_data"
    assert failed["marketOverviewProjection"]["confidence"] == 0.0
    assert failed["decisionCockpitProjection"]["evidencePreview"]["indexTrend"]["return20d"] is None


def test_compare_projection_to_evidence_detects_label_mismatch() -> None:
    evidence = {
        "contractVersion": "market_regime_evidence_pack_v1",
        "status": "ready",
        "readiness": "ready",
        "regimeSummary": {"label": "risk_on", "status": "ready", "confidence": 0.75},
        "evidence": {"dataCoverage": {"usedSymbols": ["SPY"], "skippedSymbols": []}},
    }
    projection = {
        "contractVersion": "market_regime_evidence_projection_v1",
        "sourceContractVersion": "market_regime_evidence_pack_v1",
        "status": "ready",
        "readiness": "ready",
        "label": "risk_off",
        "confidence": 0.75,
        "evidencePreview": {"dataCoverage": {"usedSymbolCount": 1, "skippedSymbolCount": 0}},
        "providerCallsEnabled": False,
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "readOnlyBoundary": {
            "externalCallsEnabled": False,
            "networkCallsEnabled": False,
            "mutationEnabled": False,
        },
    }

    mismatches = verifier.compare_projection_to_evidence(
        evidence=evidence,
        projection=projection,
        surface="market_overview",
    )

    assert any(item["field"] == "label" for item in mismatches)


def test_fixture_temp_output_redacts_paths_tracebacks_and_unsafe_terms(capsys) -> None:
    exit_code = verifier.main(["--fixture-temp", "--json"])

    assert exit_code == 0
    output = capsys.readouterr().out.lower()
    for forbidden in FORBIDDEN_OUTPUT_TOKENS:
        assert forbidden not in output


def test_fixture_temp_mode_reports_no_generated_artifacts_committed(capsys) -> None:
    exit_code = verifier.main(["--fixture-temp", "--json"])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["artifactCheck"] == {
        "fixtureWritesConfinedToTemp": True,
        "repoGeneratedArtifactsCreated": False,
    }
