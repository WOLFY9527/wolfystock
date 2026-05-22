from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "diagnose_market_intelligence_runtime.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("diagnose_market_intelligence_runtime", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_diagnostic_no_base_url_stays_local_only(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "run_official_macro_live_smoke",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledSeries": ["VIXCLS", "SOFR"],
            "missingSeries": [],
            "staleSeries": [],
            "reason": None,
        },
    )
    monkeypatch.setattr(
        module,
        "run_rotation_radar_alpaca_live_smoke",
        lambda: {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledWindows": [],
            "missingWindows": ["5m", "15m", "60m", "1d"],
            "staleWindows": [],
            "reason": "credentials",
        },
    )
    monkeypatch.setattr(
        module,
        "run_polygon_us_breadth_activation",
        lambda: {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "observationDate": None,
            "freshnessValid": False,
            "coverageCount": 0,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": [
                "ADVANCERS",
                "DECLINERS",
                "UNCHANGED",
                "ADVANCE_DECLINE_RATIO",
                "NEW_HIGHS",
                "NEW_LOWS",
                "HIGH_LOW_RATIO",
            ],
            "reasonCodes": ["authorized_us_market_breadth_feed_not_configured"],
        },
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )

    payload = module.collect_diagnostic_bundle()

    assert payload == {
        "officialMacroDiagnostic": {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledSeries": ["VIXCLS", "SOFR"],
            "missingSeries": [],
            "staleSeries": [],
            "reason": None,
        },
        "alpacaRotationDiagnostic": {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledWindows": [],
            "missingWindows": ["5m", "15m", "60m", "1d"],
            "staleWindows": [],
            "reason": "credentials",
        },
        "polygonUsBreadthDiagnostic": {
            "credentialsPresent": False,
            "probePassed": False,
            "observationDate": None,
            "freshnessValid": False,
            "coverageCount": 0,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": [
                "ADVANCERS",
                "DECLINERS",
                "UNCHANGED",
                "ADVANCE_DECLINE_RATIO",
                "NEW_HIGHS",
                "NEW_LOWS",
                "HIGH_LOW_RATIO",
            ],
            "reasonCodes": ["authorized_us_market_breadth_feed_not_configured"],
        },
        "usBreadthAuthorityDiagnostic": {
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": [
                "ADVANCERS",
                "DECLINERS",
                "UNCHANGED",
                "ADVANCE_DECLINE_RATIO",
                "NEW_HIGHS",
                "NEW_LOWS",
                "HIGH_LOW_RATIO",
            ],
            "staleMetrics": [],
            "reason": "authorized_us_market_breadth_feed_not_configured",
            "sourceLabel": "Official or Authorized US Market Breadth",
            "sourceTier": "official_or_authorized_licensed_feed",
            "trustLevel": "score_grade_when_configured",
        },
        "discrepancies": [],
    }


def test_runtime_diagnostic_sanitizes_endpoint_and_provider_output(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "run_official_macro_live_smoke",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledSeries": ["VIXCLS", "SOFR", "DFF"],
            "missingSeries": [],
            "staleSeries": [],
            "reason": "token=fred-secret",
            "Authorization": "Bearer fred-secret",
            "headers": {"X-Api-Key": "fred-secret"},
        },
    )
    monkeypatch.setattr(
        module,
        "run_rotation_radar_alpaca_live_smoke",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledWindows": ["5m", "15m", "60m", "1d"],
            "missingWindows": [],
            "staleWindows": [],
            "reason": "header=alpaca-secret",
            "apiKey": "alpaca-secret",
        },
    )
    monkeypatch.setattr(
        module,
        "run_polygon_us_breadth_activation",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": False,
            "observationDate": "2026-05-21",
            "freshnessValid": False,
            "coverageCount": 0,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": ["ADVANCERS"],
            "reasonCodes": ["api_key=polygon-secret", "polygon_eod_stale"],
            "requestUrl": "https://api.polygon.io/raw?apiKey=polygon-secret",
        },
        raising=False,
    )

    endpoint_payloads = {
        "/api/v1/market-overview/macro": {
            "freshness": "fallback",
            "providerHealth": {"status": "unavailable", "errorSummary": "token=macro-secret"},
            "items": [
                {"symbol": "VIX", "value": None, "isUnavailable": True, "rawHeaders": {"Authorization": "secret"}},
                {"symbol": "SOFR", "value": None, "isUnavailable": True},
            ],
            "headers": {"Cookie": "session=secret"},
        },
        "/api/v1/market/liquidity-monitor": {
            "score": {"regime": "unavailable", "includedIndicatorCount": 0},
            "freshness": {"status": "fallback"},
            "indicators": [
                {
                    "key": "vix_pressure",
                    "includedInScore": False,
                    "evidence": {"isUnavailable": True},
                    "coverageDiagnostics": {"scoreContributionAllowed": False},
                }
            ],
            "rawPayload": "X" * 5000,
        },
        "/api/v1/market/rotation-radar?market=US": {
            "freshness": "fallback",
            "metadata": {
                "quoteProvider": {
                    "present": False,
                    "status": "absent",
                    "asOf": "2026-05-22T10:00:00+08:00",
                    "headers": {"Authorization": "secret"},
                }
            },
            "summary": {
                "headlineEligibleThemeCount": 0,
                "observationThemeCount": 12,
                "noHeadlineReason": "fallback/static",
            },
            "themes": [{"sourceAuthorityAllowed": False, "scoreContributionAllowed": False}],
        },
        "/api/v1/market/temperature": {
            "temperatureAvailable": False,
            "disabledReason": "insufficient_reliable_inputs",
            "providerHealth": {"status": "partial"},
            "headers": {"Authorization": "secret"},
        },
        "/api/v1/market/data-readiness": {
            "readinessStatus": "misconfigured",
            "checks": [
                {"id": "local_us_parquet_dir", "status": "misconfigured"},
                {"id": "tushare_token", "status": "missing", "secretConfigured": False},
            ],
            "path": "/private/path/should/not/appear",
        },
        "/api/v1/market/us-breadth": {
            "source": "yfinance_proxy",
            "sourceType": "unofficial_proxy",
            "freshness": "delayed",
            "breadthClaimType": "representative_sample_breadth",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "sourceAuthorityReason": "representative_sample_not_full_market_breadth",
            "items": [
                {"symbol": "SECTORS_UP", "value": 6, "source": "yfinance_proxy"},
                {"symbol": "RSP_SPY", "value": -0.4, "source": "yfinance_proxy"},
            ],
            "providerHealth": {"status": "cache"},
        },
    }

    def fake_fetch_json(base_url: str, path: str, timeout_seconds: float):
        assert base_url == "http://127.0.0.1:8000?token=top-secret"
        return 200, endpoint_payloads[path]

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)

    payload = module.collect_diagnostic_bundle(base_url="http://127.0.0.1:8000?token=top-secret")
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["endpointReachability"]["baseUrl"] == "http://127.0.0.1:8000"
    assert payload["runtimeReadiness"]["marketOverviewMacro"]["available"] is False
    assert payload["runtimeReadiness"]["usBreadth"]["available"] is False
    assert payload["runtimeReadiness"]["usBreadth"]["breadthClaimType"] == "representative_sample_breadth"
    assert payload["runtimeReadiness"]["usBreadth"]["sourceAuthorityAllowed"] is False
    assert payload["runtimeReadiness"]["usBreadth"]["scoreContributionAllowed"] is False
    assert payload["runtimeReadiness"]["rotationRadar"]["available"] is False
    assert payload["runtimeReadiness"]["marketTemperature"]["temperatureAvailable"] is False
    assert payload["runtimeReadiness"]["dataReadiness"]["readinessStatus"] == "misconfigured"
    assert payload["polygonUsBreadthDiagnostic"]["reasonCodes"] == ["redacted", "polygon_eod_stale"]
    assert {"code": "diagnostic_pass_runtime_unavailable", "diagnostic": "officialMacroDiagnostic", "runtimeSurface": "marketOverviewMacro"} in payload["discrepancies"]
    assert {"code": "diagnostic_pass_runtime_unavailable", "diagnostic": "alpacaRotationDiagnostic", "runtimeSurface": "rotationRadar"} in payload["discrepancies"]

    for blocked in (
        "top-secret",
        "fred-secret",
        "alpaca-secret",
        "polygon-secret",
        "Authorization",
        "Cookie",
        "X-Api-Key",
        "requestUrl",
        "/private/path/should/not/appear",
        "rawPayload",
        "rawHeaders",
    ):
        assert blocked not in serialized


def test_runtime_diagnostic_keeps_polygon_breadth_probe_failure_fail_closed(monkeypatch) -> None:
    module = _load_script_module()
    monkeypatch.setenv("POLYGON_API_KEY", "polygon-test-key")

    monkeypatch.setattr(
        module,
        "run_official_macro_live_smoke",
        lambda: {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledSeries": [],
            "missingSeries": ["VIXCLS"],
            "staleSeries": [],
            "reason": "credentials",
        },
    )
    monkeypatch.setattr(
        module,
        "run_rotation_radar_alpaca_live_smoke",
        lambda: {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledWindows": [],
            "missingWindows": ["5m", "15m", "60m", "1d"],
            "staleWindows": [],
            "reason": "credentials",
        },
    )
    monkeypatch.setattr(
        module,
        "run_polygon_us_breadth_activation",
        lambda: (_ for _ in ()).throw(RuntimeError("polygon api_key=raw-secret")),
    )

    payload = module.collect_diagnostic_bundle()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "officialMacroDiagnostic" in payload
    assert "alpacaRotationDiagnostic" in payload
    assert payload["polygonUsBreadthDiagnostic"] == {
        "credentialsPresent": True,
        "probePassed": False,
        "observationDate": None,
        "freshnessValid": False,
        "coverageCount": 0,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledMetrics": [],
        "missingMetrics": [
            "ADVANCERS",
            "DECLINERS",
            "UNCHANGED",
            "ADVANCE_DECLINE_RATIO",
            "NEW_HIGHS",
            "NEW_LOWS",
            "HIGH_LOW_RATIO",
        ],
        "reasonCodes": ["unexpected_error"],
    }
    assert payload["discrepancies"] == []
    for reason_code in payload["polygonUsBreadthDiagnostic"]["reasonCodes"]:
        lowered = reason_code.lower()
        assert "http://" not in lowered
        assert "https://" not in lowered
        assert "api_key" not in lowered
        assert "apikey" not in lowered
        assert "secret" not in lowered
    assert "raw-secret" not in serialized
    assert "polygon-test-key" not in serialized
    assert "api_key" not in serialized
