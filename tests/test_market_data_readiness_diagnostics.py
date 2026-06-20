# -*- coding: utf-8 -*-
"""Tests for local-only market data readiness diagnostics."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
import requests

from src.services.market_data_readiness_diagnostics import (
    build_market_data_readiness_diagnostics,
    build_official_risk_source_readiness,
)


ALL_OPTIONAL_MODULES = {"pyarrow", "fastparquet", "tushare", "pytdx", "akshare", "efinance"}
EXPECTED_CONSUMER_MATRIX_FIELDS = {
    "surface",
    "evidenceFamily",
    "requiredInputs",
    "fulfilledInputs",
    "missingInputs",
    "staleInputs",
    "blockedInputs",
    "observationOnlyInputs",
    "scoreGradeInputs",
    "readinessState",
    "confidenceCapReason",
    "sourceAuthorityReason",
    "freshnessReason",
    "nextDiagnostic",
    "consumerSafeSummary",
}
EXPECTED_CONSUMER_SURFACES = {
    "market_overview",
    "liquidity_monitor",
    "rotation_radar",
    "decision_cockpit",
    "home_briefing",
    "research_radar",
}
EXPECTED_VIX_READINESS_ROWS = {
    ("market_overview", "official_vix_volatility"),
    ("liquidity_monitor", "vix_pressure"),
}
EXPECTED_OFFICIAL_MACRO_BUNDLE_READINESS_ROWS = {
    ("market_overview", "official_macro_rates_liquidity_bundle"),
    ("liquidity_monitor", "macro_rates_fed_liquidity_bundle"),
}
EXPECTED_READINESS_STATES = {
    "score_grade",
    "observation_only",
    "blocked",
    "missing",
    "unavailable",
}
FORBIDDEN_CONSUMER_MATRIX_FRAGMENTS = {
    "provider",
    "cache",
    "runtime",
    "raw",
    "debug",
    "requestid",
    "traceid",
    "schema",
    "marketcache",
    "fred",
    "yfinance",
    "providerclass",
    "officialoverlay",
    "cache_miss",
    "stale_official_row",
    "token",
    "cookie",
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "position sizing",
    "买入",
    "卖出",
    "持有",
    "投资建议",
    "交易建议",
    "目标价",
    "止损",
    "仓位建议",
}
FORBIDDEN_OFFICIAL_RISK_CONSUMER_FRAGMENTS = {
    "api_key",
    "token",
    "cookie",
    "secret",
    "credential",
    "provider",
    "runtime",
    "raw",
    "debug",
    "trace",
    "requestid",
    "marketcache",
    "sourceauthorityallowed",
    "scorecontributionallowed",
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "position sizing",
    "买入",
    "卖出",
    "持有",
    "投资建议",
    "交易建议",
    "目标价",
    "止损",
    "仓位建议",
}


def _spec_finder_with(available_modules: set[str], seen: list[str] | None = None):
    def _finder(module_name: str):
        if seen is not None:
            seen.append(module_name)
        return object() if module_name in available_modules else None

    return _finder


def _find_check(payload: dict, check_id: str) -> dict:
    return next(check for check in payload["checks"] if check["id"] == check_id)


def _matrix_rows(payload: dict) -> list[dict]:
    return list(payload["consumerEvidenceReadinessMatrix"]["items"])


def _official_row(
    series_id: str,
    *,
    symbol: str | None = None,
    value: float = 1.0,
    source: str = "fred",
    source_id: str | None = None,
    freshness: str = "delayed",
    date: str = "2026-06-19",
    as_of: str = "2026-06-20T08:00:00+08:00",
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    freshness_policy: str = "official_daily_us_weekday_t_plus_1",
) -> dict:
    source_id = source_id or f"{source}:{series_id}"
    return {
        "symbol": symbol or series_id,
        "value": value,
        "date": date,
        "asOf": as_of,
        "source": source,
        "sourceId": source_id,
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "officialSeriesId": series_id,
        "freshness": freshness,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "sourceFreshnessEvidence": {
            "freshness": freshness,
            "freshnessPolicy": freshness_policy,
            "cacheOnly": True,
            "externalProviderCalls": False,
            "isFallback": False,
            "isUnavailable": False,
            "isStale": freshness == "stale",
        },
    }


def _rates_rows() -> list[dict]:
    return [
        _official_row("DGS2", symbol="US2Y", value=3.8, source="treasury", source_id="treasury:DGS2"),
        _official_row("DGS10", symbol="US10Y", value=4.2, source="treasury", source_id="treasury:DGS10"),
        _official_row("DGS30", symbol="US30Y", value=4.4, source="treasury", source_id="treasury:DGS30"),
    ]


def _fed_liquidity_rows() -> list[dict]:
    return [
        _official_row(
            "WALCL",
            symbol="FED_ASSETS",
            value=7_200_000.0,
            freshness="cached",
            freshness_policy="official_weekly_fed_liquidity_t_plus_7",
        ),
        _official_row("RRPONTSYD", symbol="FED_RRP", value=330_000.0),
        _official_row(
            "WTREGEN",
            symbol="TGA",
            value=780_000.0,
            freshness="cached",
            freshness_policy="official_weekly_fed_liquidity_t_plus_7",
        ),
        _official_row(
            "WRESBAL",
            symbol="RESERVES",
            value=3_100_000.0,
            freshness="cached",
            freshness_policy="official_weekly_fed_liquidity_t_plus_7",
        ),
    ]


def _assert_path_not_disclosed(payload: dict, path: Path) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)

    assert str(path) not in serialized
    assert str(path.parent) not in serialized


def test_parquet_dir_missing_reports_misconfigured(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing-us-parquet"

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(missing_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with(ALL_OPTIONAL_MODULES),
    ).to_dict()

    parquet_check = _find_check(payload, "local_us_parquet_dir")

    assert payload["readinessStatus"] == "misconfigured"
    assert parquet_check["status"] == "misconfigured"
    assert parquet_check["details"]["envKey"] == "LOCAL_US_PARQUET_DIR"
    assert parquet_check["details"]["pathConfigured"] is True
    assert parquet_check["details"]["pathBasename"] == "missing-us-parquet"
    assert parquet_check["details"]["storageKind"] == "local_filesystem"
    _assert_path_not_disclosed(payload, missing_dir)


def test_parquet_dir_inspection_error_redacts_configured_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parquet_dir = tmp_path / "private-us-parquet"

    def _raise_os_error(self):
        raise OSError(f"permission denied: {self}")

    monkeypatch.setattr(Path, "exists", _raise_os_error)

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with(ALL_OPTIONAL_MODULES),
    ).to_dict()

    parquet_check = _find_check(payload, "local_us_parquet_dir")

    assert payload["readinessStatus"] == "misconfigured"
    assert parquet_check["status"] == "misconfigured"
    assert parquet_check["details"]["reason"] == "path_inspection_failed"
    assert parquet_check["details"]["errorType"] == "OSError"
    assert parquet_check["details"]["pathConfigured"] is True
    assert parquet_check["details"]["pathBasename"] == "private-us-parquet"
    _assert_path_not_disclosed(payload, parquet_dir)


def test_parquet_dir_set_but_engine_missing_reports_misconfigured(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    engine_check = _find_check(payload, "parquet_engine")

    assert payload["readinessStatus"] == "misconfigured"
    assert engine_check["status"] == "misconfigured"
    assert engine_check["details"]["checkedModules"] == ["pyarrow", "fastparquet"]


def test_parquet_engine_available_reports_ready(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    engine_check = _find_check(payload, "parquet_engine")

    assert payload["readinessStatus"] == "ready"
    assert engine_check["status"] == "ready"
    assert engine_check["details"]["availableModules"] == ["pyarrow"]


def test_tushare_token_missing_reports_boolean_only(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()

    payload = build_market_data_readiness_diagnostics(
        env={"LOCAL_US_PARQUET_DIR": str(parquet_dir)},
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    token_check = _find_check(payload, "tushare_token")

    assert token_check["status"] == "missing"
    assert token_check["secretConfigured"] is False
    assert token_check["productAffectedSurfaces"] == ["market_overview", "liquidity_monitor"]
    assert "envKey" not in token_check.get("details", {})


def test_tushare_token_present_is_redacted_from_payload(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    secret = "super-secret-token"

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": secret,
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    token_check = _find_check(payload, "tushare_token")
    serialized = json.dumps(payload, ensure_ascii=False)

    assert token_check["status"] == "ready"
    assert token_check["secretConfigured"] is True
    assert secret not in serialized


def test_representative_file_missing_reports_partial(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    (parquet_dir / "AAPL.parquet").touch()

    payload = build_market_data_readiness_diagnostics(
        representative_symbols=["AAPL", "MSFT"],
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}),
    ).to_dict()

    file_check = _find_check(payload, "local_us_parquet_representative_files")

    assert payload["readinessStatus"] == "partial"
    assert file_check["status"] == "partial"
    assert file_check["productAffectedSurfaces"] == ["provider_ops"]
    assert file_check["details"]["missingSymbols"] == ["MSFT"]
    assert file_check["details"]["existingCount"] == 1


def test_diagnostics_stay_inert_without_network_or_provider_runtime_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    (parquet_dir / "AAPL.parquet").touch()
    seen_modules: list[str] = []

    def _fail_socket(*args, **kwargs):
        raise AssertionError("network call attempted")

    def _fail_request(*args, **kwargs):
        raise AssertionError("http request attempted")

    monkeypatch.setattr(socket, "create_connection", _fail_socket)
    monkeypatch.setattr(requests.sessions.Session, "request", _fail_request)

    payload = build_market_data_readiness_diagnostics(
        representative_symbols=["AAPL"],
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with({"pyarrow", "tushare", "pytdx", "akshare", "efinance"}, seen_modules),
    ).to_dict()

    assert payload["diagnosticOnly"] is True
    assert payload["providerRuntimeCalled"] is False
    assert payload["networkCallsEnabled"] is False
    assert payload["officialRiskSourceReadiness"]["externalProviderCalls"] is False
    assert payload["officialRiskSourceReadiness"]["mutationEnabled"] is False
    assert seen_modules == ["pyarrow", "fastparquet", "tushare", "pytdx", "akshare", "efinance"]


def test_official_risk_source_readiness_reports_ready_bundle_from_fresh_official_rows() -> None:
    payload = build_official_risk_source_readiness(
        vix_rows=[_official_row("VIXCLS", symbol="VIX", value=16.2, source_id="fred:VIXCLS")],
        rates_rows=_rates_rows(),
        fed_liquidity_rows=_fed_liquidity_rows(),
    )

    assert payload["contractVersion"] == "official_risk_source_readiness_v1"
    assert payload["diagnosticOnly"] is True
    assert payload["externalProviderCalls"] is False
    assert payload["mutationEnabled"] is False
    assert payload["bundleState"] == "ready"
    assert payload["vix"] == {
        "state": "ready",
        "series": "VIXCLS",
        "source": "official_public",
        "latestDate": "2026-06-19",
        "asOf": "2026-06-20T08:00:00+08:00",
        "freshness": "delayed",
        "blocker": None,
    }
    assert payload["rates"]["state"] == "ready"
    assert payload["rates"]["coveredSeriesCount"] == 3
    assert payload["rates"]["latestDate"] == "2026-06-19"
    assert payload["rates"]["freshness"] == "delayed"
    assert payload["rates"]["blocker"] is None
    assert payload["fedLiquidity"]["state"] == "ready"
    assert payload["fedLiquidity"]["latestDate"] == "2026-06-19"
    assert payload["fedLiquidity"]["freshness"] == "delayed"
    assert payload["fedLiquidity"]["blocker"] is None
    assert "Official VIX, rates, and Fed liquidity" in payload["consumerSummary"]
    assert payload["nextDataAction"] == "Keep the official risk-source refresh bundle warm before market panels rely on it."


def test_official_risk_source_readiness_fails_closed_when_vix_is_missing_or_stale() -> None:
    missing = build_official_risk_source_readiness(
        rates_rows=_rates_rows(),
        fed_liquidity_rows=_fed_liquidity_rows(),
    )
    stale = build_official_risk_source_readiness(
        vix_rows=[_official_row("VIXCLS", symbol="VIX", freshness="stale")],
        rates_rows=_rates_rows(),
        fed_liquidity_rows=_fed_liquidity_rows(),
    )

    assert missing["bundleState"] == "partial"
    assert missing["vix"]["state"] == "blocked"
    assert missing["vix"]["blocker"] == "missing_official_vix_row"
    assert missing["nextDataAction"] == "Refresh the official VIX row before relying on risk-source readiness."
    assert stale["bundleState"] == "partial"
    assert stale["vix"]["state"] == "blocked"
    assert stale["vix"]["freshness"] == "stale"
    assert stale["vix"]["blocker"] == "stale_official_vix_row"

    all_missing = build_official_risk_source_readiness()
    assert all_missing["bundleState"] == "blocked"
    assert all_missing["vix"]["state"] == "blocked"
    assert all_missing["rates"]["state"] == "blocked"
    assert all_missing["fedLiquidity"]["state"] == "blocked"


def test_official_risk_source_readiness_reports_partial_rates_and_unavailable_fed_liquidity() -> None:
    payload = build_official_risk_source_readiness(
        vix_rows=[_official_row("VIXCLS", symbol="VIX")],
        rates_rows=_rates_rows()[:2],
        fed_liquidity_rows=[],
    )

    assert payload["bundleState"] == "partial"
    assert payload["vix"]["state"] == "ready"
    assert payload["rates"]["state"] == "partial"
    assert payload["rates"]["coveredSeriesCount"] == 2
    assert payload["rates"]["blocker"] == "missing_official_rates_series"
    assert payload["fedLiquidity"]["state"] == "blocked"
    assert payload["fedLiquidity"]["blocker"] == "missing_official_fed_liquidity_rows"
    assert payload["nextDataAction"] == "Complete the official rates coverage before relying on the bundle."

    missing_rates = build_official_risk_source_readiness(
        vix_rows=[_official_row("VIXCLS", symbol="VIX")],
        rates_rows=[],
        fed_liquidity_rows=_fed_liquidity_rows(),
    )
    assert missing_rates["bundleState"] == "partial"
    assert missing_rates["rates"]["state"] == "blocked"
    assert missing_rates["rates"]["coveredSeriesCount"] == 0
    assert missing_rates["rates"]["blocker"] == "missing_official_rates_series"


def test_official_risk_source_readiness_consumer_fields_redact_raw_runtime_and_advice_terms() -> None:
    payload = build_official_risk_source_readiness(
        vix_rows=[
            {
                **_official_row("VIXCLS", symbol="VIX"),
                "sourceAuthorityReason": "provider_runtime token buy target price raw debug trace",
            }
        ],
        rates_rows=[],
        fed_liquidity_rows=[],
    )
    consumer_values = {
        "consumerSummary": payload["consumerSummary"],
        "nextDataAction": payload["nextDataAction"],
    }
    serialized = json.dumps(consumer_values, ensure_ascii=False).lower()

    for fragment in FORBIDDEN_OFFICIAL_RISK_CONSUMER_FRAGMENTS:
        assert fragment not in serialized


def test_consumer_evidence_readiness_matrix_is_provider_free_and_covers_core_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()
    seen_modules: list[str] = []

    def _fail_socket(*args, **kwargs):
        raise AssertionError("network call attempted")

    def _fail_request(*args, **kwargs):
        raise AssertionError("http request attempted")

    monkeypatch.setattr(socket, "create_connection", _fail_socket)
    monkeypatch.setattr(requests.sessions.Session, "request", _fail_request)

    payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with(ALL_OPTIONAL_MODULES, seen_modules),
    ).to_dict()

    matrix = payload["consumerEvidenceReadinessMatrix"]
    rows = matrix["items"]

    assert matrix["contractVersion"] == "consumer_evidence_readiness_matrix_v1"
    assert matrix["diagnosticOnly"] is True
    assert matrix["networkCallsEnabled"] is False
    assert matrix["mutationEnabled"] is False
    assert all(set(row) == EXPECTED_CONSUMER_MATRIX_FIELDS for row in rows)
    assert EXPECTED_CONSUMER_SURFACES <= {row["surface"] for row in rows}
    assert EXPECTED_VIX_READINESS_ROWS <= {
        (row["surface"], row["evidenceFamily"])
        for row in rows
    }
    assert EXPECTED_OFFICIAL_MACRO_BUNDLE_READINESS_ROWS <= {
        (row["surface"], row["evidenceFamily"])
        for row in rows
    }
    assert EXPECTED_READINESS_STATES <= {row["readinessState"] for row in rows}
    assert seen_modules == ["pyarrow", "fastparquet", "tushare", "pytdx", "akshare", "efinance"]


def test_official_vix_readiness_rows_fail_closed_without_runtime_checks() -> None:
    payload = build_market_data_readiness_diagnostics(
        env={},
        spec_finder=_spec_finder_with(set()),
    ).to_dict()

    rows = {
        (row["surface"], row["evidenceFamily"]): row
        for row in _matrix_rows(payload)
    }
    overview_vix = rows[("market_overview", "official_vix_volatility")]
    liquidity_vix = rows[("liquidity_monitor", "vix_pressure")]

    assert payload["diagnosticOnly"] is True
    assert payload["providerRuntimeCalled"] is False
    assert payload["networkCallsEnabled"] is False
    assert overview_vix["requiredInputs"] == ["VIXCLS official volatility close"]
    assert overview_vix["fulfilledInputs"] == []
    assert overview_vix["scoreGradeInputs"] == []
    assert overview_vix["readinessState"] == "missing"
    assert "source authority" in overview_vix["sourceAuthorityReason"].lower()
    assert "freshness" in overview_vix["freshnessReason"].lower()
    assert liquidity_vix["requiredInputs"] == ["VIXCLS official volatility close"]
    assert liquidity_vix["observationOnlyInputs"] == ["proxy volatility context"]
    assert liquidity_vix["scoreGradeInputs"] == []
    assert liquidity_vix["readinessState"] == "observation_only"


def test_official_macro_rates_fed_liquidity_readiness_rows_fail_closed_without_runtime_checks() -> None:
    payload = build_market_data_readiness_diagnostics(
        env={},
        spec_finder=_spec_finder_with(set()),
    ).to_dict()

    rows = {
        (row["surface"], row["evidenceFamily"]): row
        for row in _matrix_rows(payload)
    }
    overview_bundle = rows[("market_overview", "official_macro_rates_liquidity_bundle")]
    liquidity_bundle = rows[("liquidity_monitor", "macro_rates_fed_liquidity_bundle")]
    expected_inputs = [
        "Treasury daily rates",
        "policy-rate daily rows",
        "credit and USD pressure rows",
        "Fed liquidity weekly rows",
    ]

    assert payload["diagnosticOnly"] is True
    assert payload["providerRuntimeCalled"] is False
    assert payload["networkCallsEnabled"] is False
    assert overview_bundle["requiredInputs"] == expected_inputs
    assert overview_bundle["missingInputs"] == expected_inputs
    assert overview_bundle["scoreGradeInputs"] == []
    assert overview_bundle["readinessState"] == "missing"
    assert "partial" in overview_bundle["sourceAuthorityReason"].lower()
    assert "daily policy" in overview_bundle["freshnessReason"].lower()
    assert "weekly policy" in overview_bundle["freshnessReason"].lower()
    assert liquidity_bundle["requiredInputs"] == expected_inputs
    assert liquidity_bundle["missingInputs"] == expected_inputs
    assert liquidity_bundle["observationOnlyInputs"] == ["proxy macro and rates context"]
    assert liquidity_bundle["scoreGradeInputs"] == []
    assert liquidity_bundle["readinessState"] == "observation_only"


def test_consumer_evidence_readiness_matrix_redacts_internal_diagnostics_and_advice_terms() -> None:
    payload = build_market_data_readiness_diagnostics(
        env={},
        spec_finder=_spec_finder_with(set()),
    ).to_dict()

    matrix = payload["consumerEvidenceReadinessMatrix"]
    serialized = json.dumps(matrix, ensure_ascii=False).lower()

    for fragment in FORBIDDEN_CONSUMER_MATRIX_FRAGMENTS:
        assert fragment not in serialized


def test_consumer_evidence_readiness_matrix_states_are_deterministic_across_local_env(
    tmp_path: Path,
) -> None:
    parquet_dir = tmp_path / "us-parquet"
    parquet_dir.mkdir()

    ready_env_payload = build_market_data_readiness_diagnostics(
        env={
            "LOCAL_US_PARQUET_DIR": str(parquet_dir),
            "TUSHARE_TOKEN": "configured",
        },
        spec_finder=_spec_finder_with(ALL_OPTIONAL_MODULES),
    ).to_dict()
    missing_env_payload = build_market_data_readiness_diagnostics(
        env={},
        spec_finder=_spec_finder_with(set()),
    ).to_dict()

    def _states(payload: dict) -> list[tuple[str, str, str]]:
        return [
            (row["surface"], row["evidenceFamily"], row["readinessState"])
            for row in payload["consumerEvidenceReadinessMatrix"]["items"]
        ]

    assert _states(ready_env_payload) == _states(missing_env_payload)


def test_unavailable_consumer_evidence_does_not_produce_score_grade_judgment() -> None:
    payload = build_market_data_readiness_diagnostics(
        env={},
        spec_finder=_spec_finder_with(set()),
    ).to_dict()

    unavailable_rows = [
        row for row in payload["consumerEvidenceReadinessMatrix"]["items"]
        if row["readinessState"] == "unavailable"
    ]

    assert unavailable_rows
    for row in unavailable_rows:
        assert row["scoreGradeInputs"] == []
        assert row["fulfilledInputs"] == []
        assert "score-grade conclusion" in row["consumerSafeSummary"]
