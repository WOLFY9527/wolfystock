# -*- coding: utf-8 -*-
"""Fixture tests for official macro transport helpers."""

from __future__ import annotations

import ast
import importlib.util
import json
import socket
import ssl
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from src.config import Config
from src.services.market_data_source_registry import project_source_provenance
import src.services.official_macro_transport as official_macro_transport
from src.services.official_macro_transport import (
    FRED_OBSERVATIONS_URL,
    NYFED_SOFR_UNSUPPORTED_REASON,
    TREASURY_DAILY_RATES_CSV_URL,
    OfficialMacroTransportError,
    build_fred_observations_request,
    build_supported_fred_requests,
    build_treasury_daily_rates_request,
    run_fed_liquidity_live_smoke,
    run_official_macro_live_smoke,
    run_usd_pressure_live_smoke,
    parse_fred_observation_points_payload,
    parse_fred_observations_payload,
    fetch_fred_observation_points,
    fetch_treasury_daily_rate_observation_points,
    parse_nyfed_sofr_payload,
    parse_treasury_daily_rate_observation_points_csv,
    parse_treasury_daily_rates_csv,
    parse_treasury_daily_rates_rows,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "official_macro"
MODULE_PATH = REPO_ROOT / "src" / "services" / "official_macro_transport.py"
OFFICIAL_MACRO_ACTIVATION_SCRIPT_PATH = REPO_ROOT / "scripts" / "diagnose_official_macro_activation.py"
OFFICIAL_MACRO_PREWARM_SCRIPT_PATH = REPO_ROOT / "scripts" / "official_macro_cache_prewarm.py"
FORBIDDEN_IMPORT_PREFIXES = ("requests", "httpx", "aiohttp", "urllib3", "yfinance")
OFFICIAL_MACRO_SMOKE_CORE_FIELDS = {
    "credentialsPresent",
    "providerConstructed",
    "probePassed",
    "freshnessValid",
    "sourceMetadataValid",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "fulfilledSeries",
    "missingSeries",
    "staleSeries",
    "reason",
}
OFFICIAL_MACRO_SMOKE_RETRY_FIELDS = {"attempts", "maxAttempts", "transientMissingSeries", "finalAttemptMissingSeries"}


def _load_json_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_text_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _macro_point(
    series_id: str,
    value: float,
    date_text: str,
    *,
    source_id: str | None = None,
    source_type: str = "official_public",
    freshness_hint: str = "daily_close",
) -> official_macro_transport.MacroObservation:
    return official_macro_transport.MacroObservation(
        symbol=series_id,
        value=value,
        date=date_text,
        as_of=date_text,
        source_id=source_id or f"fred:{series_id}",
        source_type=source_type,
        freshness_hint=freshness_hint,
    )


def _assert_smoke_summary_fields(summary: dict[str, object]) -> None:
    assert OFFICIAL_MACRO_SMOKE_CORE_FIELDS.issubset(summary.keys())
    assert OFFICIAL_MACRO_SMOKE_RETRY_FIELDS.issubset(summary.keys())


def _module_imports() -> set[str]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _load_official_macro_activation_script():
    spec = importlib.util.spec_from_file_location(
        "diagnose_official_macro_activation_for_test",
        OFFICIAL_MACRO_ACTIVATION_SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_official_macro_prewarm_script():
    spec = importlib.util.spec_from_file_location(
        "official_macro_cache_prewarm_for_test",
        OFFICIAL_MACRO_PREWARM_SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _isolate_fred_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "")
    Config.reset_instance()
    try:
        yield
    finally:
        Config.reset_instance()


def test_official_macro_transport_stays_stdlib_only() -> None:
    forbidden_imports = sorted(
        module
        for module in _module_imports()
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert forbidden_imports == []


def test_build_supported_fred_requests_covers_expected_series() -> None:
    requests = build_supported_fred_requests()

    assert [request.params["series_id"] for request in requests] == ["VIXCLS", "DGS2", "DGS10", "DGS30", "SOFR"]
    assert all(request.url == FRED_OBSERVATIONS_URL for request in requests)
    assert all(request.requires_api_key for request in requests)
    assert all(request.source_type == "official_public" for request in requests)


def test_build_fred_observations_request_omits_api_key_when_not_supplied() -> None:
    request = build_fred_observations_request("DGS10", limit=7, observation_start="2026-05-01")

    assert request.method == "GET"
    assert request.url == FRED_OBSERVATIONS_URL
    assert request.params["series_id"] == "DGS10"
    assert request.params["file_type"] == "json"
    assert request.params["sort_order"] == "desc"
    assert request.params["limit"] == "7"
    assert request.params["observation_start"] == "2026-05-01"
    assert "api_key" not in request.params
    assert request.source_id == "fred:DGS10"
    assert request.requires_api_key is True


def test_build_fred_observations_request_includes_explicit_dummy_api_key() -> None:
    request = build_fred_observations_request("DGS10", api_key="fred-explicit-test-key", limit=2)

    assert request.params["series_id"] == "DGS10"
    assert request.params["limit"] == "2"
    assert request.params["api_key"] == "fred-explicit-test-key"


def test_fetch_fred_observation_points_uses_runtime_configured_fred_api_key_without_exposing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests = []

    def _fake_fetch_transport_bytes(request, *, timeout):
        captured_requests.append(request)
        return json.dumps(
            {
                "observations": [
                    {"date": "2026-05-13", "value": "4.45"},
                    {"date": "2026-05-12", "value": "4.41"},
                ]
            }
        ).encode("utf-8")

    monkeypatch.setenv("FRED_API_KEY", "fred-secret-test-key")
    Config.reset_instance()
    try:
        with patch("src.services.official_macro_transport._fetch_transport_bytes", side_effect=_fake_fetch_transport_bytes):
            points = fetch_fred_observation_points("DGS10", limit=2)
    finally:
        Config.reset_instance()

    assert len(captured_requests) == 1
    assert captured_requests[0].params["api_key"] == "fred-secret-test-key"
    assert captured_requests[0].params["series_id"] == "DGS10"
    assert "fred-secret-test-key" not in json.dumps([point.to_dict() for point in points])


def test_fetch_fred_observation_points_reports_missing_api_key_without_network_call() -> None:
    with patch("src.services.official_macro_transport.urlopen", side_effect=AssertionError("network should not be called")):
        with pytest.raises(OfficialMacroTransportError) as exc_info:
            fetch_fred_observation_points("VIXCLS", limit=1)

    assert exc_info.value.reason == "missing_api_key"
    assert "api key" in str(exc_info.value).lower()
    diagnostics = exc_info.value.diagnostics
    assert diagnostics["providerName"] == "fred"
    assert diagnostics["endpointHost"] == "api.stlouisfed.org"
    assert diagnostics["requestedSeries"] == "VIXCLS"
    assert diagnostics["configPresent"] is True
    assert diagnostics["apiKeyPresent"] is False
    assert "api_key" not in json.dumps(diagnostics)


def test_fetch_fred_observation_points_reports_non_2xx_http_response() -> None:
    http_error = HTTPError(
        url=FRED_OBSERVATIONS_URL,
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )

    with patch("src.services.official_macro_transport.urlopen", side_effect=http_error):
        with pytest.raises(OfficialMacroTransportError) as exc_info:
            fetch_fred_observation_points("DGS10", api_key="fred-test-key", limit=1)

    assert exc_info.value.reason == "http_error"
    assert exc_info.value.status_code == 403


def test_fetch_fred_observation_points_reports_timeout() -> None:
    with patch("src.services.official_macro_transport.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(OfficialMacroTransportError) as exc_info:
            fetch_fred_observation_points("DGS30", api_key="fred-test-key", limit=1)

    assert exc_info.value.reason == "timeout"


def test_fetch_fred_observation_points_uses_certifi_ca_bundle_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    certifi_cafile = tmp_path / "certifi-cacert.pem"
    certifi_cafile.write_text("fixture", encoding="utf-8")
    ssl_context = object()
    created_contexts: list[str | None] = []
    urlopen_contexts: list[object | None] = []

    class Response:
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"observations":[{"date":"2026-05-13","value":"4.45"}]}'

    def fake_create_default_context(*, cafile: str | None = None) -> object:
        created_contexts.append(cafile)
        return ssl_context

    def fake_urlopen(request: object, *, timeout: float, context: object | None = None) -> Response:
        urlopen_contexts.append(context)
        return Response()

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.setattr(ssl, "create_default_context", fake_create_default_context)
    monkeypatch.setattr(official_macro_transport, "urlopen", fake_urlopen)
    with patch.dict(sys.modules, {"certifi": SimpleNamespace(where=lambda: str(certifi_cafile))}):
        points = fetch_fred_observation_points("DGS10", api_key="fred-test-key", limit=1)

    assert [point.value for point in points] == [4.45]
    assert created_contexts == [str(certifi_cafile)]
    assert urlopen_contexts == [ssl_context]


def test_fetch_fred_observation_points_falls_back_to_system_ca_when_certifi_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ssl_context = object()
    created_contexts: list[str | None] = []

    class Response:
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"observations":[{"date":"2026-05-13","value":"4.45"}]}'

    def fake_create_default_context(*, cafile: str | None = None) -> object:
        created_contexts.append(cafile)
        return ssl_context

    def fake_urlopen(request: object, *, timeout: float, context: object | None = None) -> Response:
        assert context is ssl_context
        return Response()

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.setattr(ssl, "create_default_context", fake_create_default_context)
    monkeypatch.setattr(official_macro_transport, "urlopen", fake_urlopen)
    with patch.dict(sys.modules, {"certifi": None}):
        points = fetch_fred_observation_points("DGS10", api_key="fred-test-key", limit=1)

    assert [point.value for point in points] == [4.45]
    assert created_contexts == [None]


def test_fetch_fred_observation_points_reports_ssl_failure_ca_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    certifi_cafile = tmp_path / "certifi-cacert.pem"
    certifi_cafile.write_text("fixture", encoding="utf-8")

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.setattr(ssl, "create_default_context", lambda *, cafile=None: object())
    monkeypatch.setattr(
        official_macro_transport,
        "urlopen",
        lambda *_, **__: (_ for _ in ()).throw(
            URLError(ssl.SSLCertVerificationError("certificate verify failed token=SECRET"))
        ),
    )

    with patch.dict(sys.modules, {"certifi": SimpleNamespace(where=lambda: str(certifi_cafile))}):
        with pytest.raises(OfficialMacroTransportError) as exc_info:
            fetch_fred_observation_points("DGS10", api_key="fred-test-key", limit=1, timeout=1.25)

    assert exc_info.value.reason == "transport_error"
    diagnostics = exc_info.value.diagnostics
    assert diagnostics["providerName"] == "fred"
    assert diagnostics["requestedSeries"] == "DGS10"
    assert diagnostics["apiKeyPresent"] is True
    assert diagnostics["caBundleSource"] == "certifi"
    assert diagnostics["exceptionClass"] == "SSLCertVerificationError"
    assert diagnostics["exceptionChain"] == ["URLError", "SSLCertVerificationError"]
    assert "SECRET" not in json.dumps(diagnostics)
    assert "fred-test-key" not in json.dumps(diagnostics)


def test_fetch_fred_observation_points_reports_urlerror_timeout_with_safe_diagnostics() -> None:
    with patch(
        "src.services.official_macro_transport.urlopen",
        side_effect=URLError(socket.timeout("timed out token=SECRET")),
    ):
        with pytest.raises(OfficialMacroTransportError) as exc_info:
            fetch_fred_observation_points("DGS10", api_key="fred-test-key", limit=1, timeout=1.25)

    assert exc_info.value.reason == "timeout"
    diagnostics = exc_info.value.diagnostics
    assert diagnostics["providerName"] == "fred"
    assert diagnostics["endpointHost"] == "api.stlouisfed.org"
    assert diagnostics["requestedSeries"] == "DGS10"
    assert diagnostics["apiKeyPresent"] is True
    assert diagnostics["timeoutSeconds"] == 1.25
    assert diagnostics["exceptionClass"] == "TimeoutError"
    assert "SECRET" not in json.dumps(diagnostics)
    assert "fred-test-key" not in json.dumps(diagnostics)


def test_fetch_fred_observation_points_reports_empty_transport_body() -> None:
    class EmptyResponse:
        status = 200

        def __enter__(self) -> "EmptyResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b""

    with patch("src.services.official_macro_transport.urlopen", return_value=EmptyResponse()):
        with pytest.raises(OfficialMacroTransportError) as exc_info:
            fetch_fred_observation_points("DGS10", api_key="fred-test-key", limit=1)

    assert exc_info.value.reason == "empty_response"


def test_build_fred_observations_request_supports_credit_stress_series_without_expanding_runtime_default_set() -> None:
    request = build_fred_observations_request("BAMLH0A0HYM2", limit=3)

    assert request.method == "GET"
    assert request.url == FRED_OBSERVATIONS_URL
    assert request.params["series_id"] == "BAMLH0A0HYM2"
    assert request.params["file_type"] == "json"
    assert request.params["sort_order"] == "desc"
    assert request.params["limit"] == "3"
    assert "api_key" not in request.params
    assert request.source_id == "fred:BAMLH0A0HYM2"
    assert request.source_type == "official_public"
    assert request.requires_api_key is True
    assert [item.params["series_id"] for item in build_supported_fred_requests()] == ["VIXCLS", "DGS2", "DGS10", "DGS30", "SOFR"]


@pytest.mark.parametrize(
    ("series_id", "limit"),
    [
        ("DFF", 2),
        ("CPIAUCSL", 13),
        ("PPIACO", 13),
        ("WALCL", 2),
        ("RRPONTSYD", 2),
        ("WTREGEN", 2),
        ("WRESBAL", 2),
        ("DTWEXBGS", 2),
    ],
)
def test_build_fred_observations_request_supports_additional_official_macro_series_without_expanding_runtime_default_set(
    series_id: str,
    limit: int,
) -> None:
    request = build_fred_observations_request(series_id, limit=limit)

    assert request.method == "GET"
    assert request.url == FRED_OBSERVATIONS_URL
    assert request.params["series_id"] == series_id
    assert request.params["limit"] == str(limit)
    assert request.source_id == f"fred:{series_id}"
    assert request.source_type == "official_public"
    assert request.requires_api_key is True
    assert [item.params["series_id"] for item in build_supported_fred_requests()] == ["VIXCLS", "DGS2", "DGS10", "DGS30", "SOFR"]


def test_build_fred_observations_request_rejects_unsupported_series() -> None:
    with pytest.raises(ValueError, match="unsupported FRED series"):
        build_fred_observations_request("DXY")


def test_fed_liquidity_live_smoke_reports_bounded_official_series_successfully() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    fred_requested: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        fred_requested.append(series_id)
        values = {
            "WALCL": 7485000.0,
            "RRPONTSYD": 432.2,
            "WTREGEN": 812000.0,
            "WRESBAL": 3260000.0,
        }
        return [_macro_point(series_id, values[series_id], "2026-05-13")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_fed_liquidity_live_smoke(now=now)

    assert fred_requested == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    _assert_smoke_summary_fields(summary)
    assert summary | {} == {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": True,
        "freshnessValid": True,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "fulfilledSeries": ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"],
        "missingSeries": [],
        "staleSeries": [],
        "reason": None,
        "attempts": 1,
        "maxAttempts": 3,
        "transientMissingSeries": [],
        "finalAttemptMissingSeries": [],
    }


def test_fed_liquidity_live_smoke_fails_closed_on_partial_or_stale_series() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    fred_requested: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        fred_requested.append(series_id)
        points = {
            "WALCL": [_macro_point("WALCL", 7485000.0, "2026-05-20")],
            "RRPONTSYD": [_macro_point("RRPONTSYD", 432.2, "2026-05-20")],
            "WTREGEN": [_macro_point("WTREGEN", 812000.0, "2026-05-01")],
            "WRESBAL": [],
        }
        return list(points[series_id])

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_fed_liquidity_live_smoke(now=now)

    assert fred_requested.count("WRESBAL") == 3
    assert set(fred_requested) == {"WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"}
    _assert_smoke_summary_fields(summary)
    assert summary["probePassed"] is False
    assert summary["sourceAuthorityAllowed"] is False
    assert summary["scoreContributionAllowed"] is False
    assert summary["fulfilledSeries"] == ["WALCL", "RRPONTSYD"]
    assert summary["missingSeries"] == ["WRESBAL"]
    assert summary["staleSeries"] == ["WTREGEN"]
    assert summary["reason"] == "stale_series"


def test_usd_pressure_live_smoke_reports_bounded_official_series_successfully() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    fred_requested: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        fred_requested.append(series_id)
        return [_macro_point(series_id, 128.42, "2026-05-15", freshness_hint="daily_trade_weighted_usd")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_usd_pressure_live_smoke(now=now)

    assert fred_requested == ["DTWEXBGS"]
    _assert_smoke_summary_fields(summary)
    assert summary | {} == {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": True,
        "freshnessValid": True,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "fulfilledSeries": ["DTWEXBGS"],
        "missingSeries": [],
        "staleSeries": [],
        "reason": None,
        "attempts": 1,
        "maxAttempts": 3,
        "transientMissingSeries": [],
        "finalAttemptMissingSeries": [],
        "latestObservationDate": "2026-05-15",
        "latestAsOf": "2026-05-15",
        "freshnessPolicy": "official_h10_weekly_batch_t_plus_7",
        "maxAcceptedLagDays": 10,
        "maxAcceptedBusinessLagDays": 7,
        "seriesLagDays": 7,
    }


def test_usd_pressure_live_smoke_fails_closed_on_missing_series() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    fred_requested: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        fred_requested.append(series_id)
        return []

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_usd_pressure_live_smoke(now=now)

    assert fred_requested == ["DTWEXBGS", "DTWEXBGS", "DTWEXBGS"]
    _assert_smoke_summary_fields(summary)
    assert summary["probePassed"] is False
    assert summary["freshnessValid"] is True
    assert summary["sourceMetadataValid"] is True
    assert summary["sourceAuthorityAllowed"] is False
    assert summary["scoreContributionAllowed"] is False
    assert summary["fulfilledSeries"] == []
    assert summary["missingSeries"] == ["DTWEXBGS"]
    assert summary["staleSeries"] == []
    assert summary["reason"] == "series_coverage"
    assert "latestObservationDate" not in summary
    assert "freshnessPolicy" not in summary


def test_usd_pressure_live_smoke_fails_closed_on_stale_series() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    fred_requested: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        fred_requested.append(series_id)
        return [_macro_point(series_id, 127.8, "2026-05-01", freshness_hint="daily_trade_weighted_usd")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_usd_pressure_live_smoke(now=now)

    assert fred_requested == ["DTWEXBGS", "DTWEXBGS", "DTWEXBGS"]
    _assert_smoke_summary_fields(summary)
    assert summary["probePassed"] is False
    assert summary["sourceAuthorityAllowed"] is False
    assert summary["scoreContributionAllowed"] is False
    assert summary["fulfilledSeries"] == []
    assert summary["missingSeries"] == []
    assert summary["staleSeries"] == ["DTWEXBGS"]
    assert summary["reason"] == "stale_series"
    assert summary["latestObservationDate"] == "2026-05-01"
    assert summary["latestAsOf"] == "2026-05-01"
    assert summary["freshnessPolicy"] == "official_h10_weekly_batch_t_plus_7"
    assert summary["maxAcceptedLagDays"] == 10
    assert summary["maxAcceptedBusinessLagDays"] == 7
    assert summary["seriesLagDays"] == 21


def test_usd_pressure_live_smoke_fails_closed_on_malformed_observation_date() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        return [_macro_point(series_id, 128.42, "not-a-date", freshness_hint="daily_trade_weighted_usd")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_usd_pressure_live_smoke(now=now)

    _assert_smoke_summary_fields(summary)
    assert summary["probePassed"] is False
    assert summary["freshnessValid"] is False
    assert summary["sourceMetadataValid"] is True
    assert summary["sourceAuthorityAllowed"] is False
    assert summary["scoreContributionAllowed"] is False
    assert summary["fulfilledSeries"] == []
    assert summary["missingSeries"] == []
    assert summary["staleSeries"] == ["DTWEXBGS"]
    assert summary["reason"] == "stale_series"
    assert "latestObservationDate" not in summary
    assert "latestAsOf" not in summary
    assert summary["freshnessPolicy"] == "official_h10_weekly_batch_t_plus_7"
    assert summary["maxAcceptedLagDays"] == 10
    assert summary["maxAcceptedBusinessLagDays"] == 7
    assert "seriesLagDays" not in summary


def test_usd_pressure_live_smoke_fails_closed_on_invalid_source_metadata() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        return [
            _macro_point(
                series_id,
                128.42,
                "2026-05-15",
                source_id="yfinance_proxy",
                source_type="unofficial_proxy",
                freshness_hint="daily_trade_weighted_usd",
            )
        ]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_usd_pressure_live_smoke(now=now)

    _assert_smoke_summary_fields(summary)
    assert summary["probePassed"] is False
    assert summary["freshnessValid"] is True
    assert summary["sourceMetadataValid"] is False
    assert summary["sourceAuthorityAllowed"] is False
    assert summary["scoreContributionAllowed"] is False
    assert summary["fulfilledSeries"] == []
    assert summary["missingSeries"] == ["DTWEXBGS"]
    assert summary["staleSeries"] == []
    assert summary["reason"] == "source_metadata_invalid"
    assert summary["latestObservationDate"] == "2026-05-15"
    assert summary["latestAsOf"] == "2026-05-15"
    assert "freshnessPolicy" not in summary


def test_official_macro_activation_cache_readiness_smoke_outputs_sanitized_required_series_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_official_macro_activation_script()

    monkeypatch.setattr(
        script,
        "run_usd_pressure_live_smoke",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledSeries": ["DTWEXBGS"],
            "missingSeries": [],
            "staleSeries": [],
            "reason": None,
            "rawProviderPayload": {"token": "SECRET"},
        },
    )
    monkeypatch.setattr(
        script,
        "run_fed_liquidity_live_smoke",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledSeries": ["WALCL", "WRESBAL"],
            "missingSeries": ["RRPONTSYD"],
            "staleSeries": ["WTREGEN"],
            "reason": "stale_series",
            "rawProviderPayload": {"token": "SECRET"},
        },
    )
    monkeypatch.setattr(
        script,
        "run_official_macro_live_smoke",
        lambda: (_ for _ in ()).throw(AssertionError("cache readiness mode must not run generic macro smoke")),
    )

    exit_code = script.main(["--cache-readiness"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["credentialsPresent"] is True
    assert payload["keyPresent"] is True
    assert payload["providerConstructed"] is True
    assert payload["probePassed"] is False
    assert payload["readiness"] == "blocked"
    assert payload["freshnessValid"] is False
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert payload["reason"] == "stale_series"
    assert payload["operatorNextGate"] == "remediate_required_series_before_prewarm"
    assert payload["requiredSeries"] == ["DTWEXBGS", "WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert payload["requiredSeriesStatus"] == {
        "DTWEXBGS": "fulfilled",
        "WALCL": "fulfilled",
        "RRPONTSYD": "missing",
        "WTREGEN": "stale",
        "WRESBAL": "fulfilled",
    }
    assert payload["seriesReadiness"] == [
        {
            "blocked": False,
            "blockedReason": None,
            "freshnessPolicy": "official_h10_weekly_batch_t_plus_7",
            "group": "usd_pressure",
            "series": "DTWEXBGS",
            "status": "fulfilled",
            "symbol": "USD_TWI",
        },
        {
            "blocked": False,
            "blockedReason": None,
            "freshnessPolicy": "official_weekly_fed_liquidity_t_plus_7",
            "group": "fed_liquidity",
            "series": "WALCL",
            "status": "fulfilled",
            "symbol": "FED_ASSETS",
        },
        {
            "blocked": True,
            "blockedReason": "stale_series",
            "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
            "group": "fed_liquidity",
            "series": "RRPONTSYD",
            "status": "missing",
            "symbol": "FED_RRP",
        },
        {
            "blocked": True,
            "blockedReason": "stale_series",
            "freshnessPolicy": "official_weekly_fed_liquidity_t_plus_7",
            "group": "fed_liquidity",
            "series": "WTREGEN",
            "status": "stale",
            "symbol": "TGA",
        },
        {
            "blocked": False,
            "blockedReason": None,
            "freshnessPolicy": "official_weekly_fed_liquidity_t_plus_7",
            "group": "fed_liquidity",
            "series": "WRESBAL",
            "status": "fulfilled",
            "symbol": "RESERVES",
        },
    ]
    assert payload["missingSeries"] == ["RRPONTSYD"]
    assert payload["staleSeries"] == ["WTREGEN"]
    assert payload["groups"]["usdPressure"]["requiredSeriesStatus"] == {"DTWEXBGS": "fulfilled"}
    assert payload["groups"]["fedLiquidity"]["requiredSeriesStatus"]["RRPONTSYD"] == "missing"
    assert "rawProviderPayload" not in output
    assert "SECRET" not in output


def test_official_macro_activation_cache_readiness_unexpected_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_official_macro_activation_script()

    monkeypatch.setattr(script, "run_usd_pressure_live_smoke", lambda: (_ for _ in ()).throw(RuntimeError("SECRET")))

    exit_code = script.main(["--cache-readiness"])

    assert exit_code == 1
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["credentialsPresent"] is False
    assert payload["keyPresent"] is False
    assert payload["providerConstructed"] is False
    assert payload["sourceAuthorityAllowed"] is False
    assert payload["scoreContributionAllowed"] is False
    assert payload["reason"] == "unexpected_error"
    assert payload["operatorNextGate"] == "remediate_required_series_before_prewarm"
    assert payload["requiredSeries"] == ["DTWEXBGS", "WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert payload["requiredSeriesStatus"] == {
        "DTWEXBGS": "missing",
        "WALCL": "missing",
        "RRPONTSYD": "missing",
        "WTREGEN": "missing",
        "WRESBAL": "missing",
    }
    assert all(item["blocked"] is True for item in payload["seriesReadiness"])
    assert all(item["blockedReason"] == "unexpected_error" for item in payload["seriesReadiness"])
    assert "SECRET" not in output


def test_official_macro_activation_help_includes_cache_readiness_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_official_macro_activation_script()

    with pytest.raises(SystemExit) as excinfo:
        script.main(["--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "cache-readiness" in output
    assert "official macro" in output.lower()


def test_official_macro_cache_prewarm_dry_run_reports_sanitized_write_plan() -> None:
    script = _load_official_macro_prewarm_script()

    def fail_factory() -> object:
        raise AssertionError("dry-run must not construct MarketOverviewService")

    result = script.run_prewarm(
        write=False,
        service_factory=fail_factory,
        readiness_probe=lambda: {
            "readiness": "blocked",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "requiredSeriesStatus": {
                "DTWEXBGS": "fulfilled",
                "WALCL": "missing",
                "RRPONTSYD": "fulfilled",
                "WTREGEN": "fulfilled",
                "WRESBAL": "fulfilled",
            },
            "missingSeries": ["WALCL"],
            "staleSeries": [],
            "reason": "series_coverage",
            "rawProviderPayload": {"token": "SECRET"},
        },
    )

    assert result["dryRun"] is True
    assert result["writeEnabled"] is False
    assert result["writeAttempted"] is False
    assert result["readiness"] == "blocked"
    assert result["requiredSeries"] == ["DTWEXBGS", "WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert result["fulfilledSeries"] == ["DTWEXBGS", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert result["missingSeries"] == ["WALCL"]
    assert result["staleSeries"] == []
    assert result["sourceAuthorityAllowed"] is False
    assert result["scoreContributionAllowed"] is False
    assert result["cacheRowsWouldWrite"] == 2
    assert result["cacheRowsWritten"] == 0
    assert result["writeEfficacy"] == "not_written"
    assert result["scoreGradeUsable"] is False
    assert result["degradedTargetCount"] == 0
    assert result["degradedTargetSymbols"] == []
    assert result["degradedTargetReasons"] == []
    assert result["writtenButNotScoreGradeReason"] == "write_not_attempted"
    assert result["reason"] == "series_coverage"
    assert "targetPanels" in result
    assert "rawProviderPayload" not in json.dumps(result)
    assert "SECRET" not in json.dumps(result)


def test_official_macro_cache_prewarm_write_reports_sanitized_coverage_summary() -> None:
    script = _load_official_macro_prewarm_script()

    class FakeService:
        def prewarm_official_macro_cache(self) -> dict[str, dict[str, object]]:
            return {
                "rates": {
                    "source": "mixed",
                    "freshness": "cached",
                    "items": [
                        {
                            "symbol": "US2Y",
                            "officialSeriesId": "DGS2",
                            "source": "fred",
                            "sourceType": "official_public",
                            "freshness": "cached",
                            "sourceAuthorityAllowed": True,
                            "scoreContributionAllowed": True,
                        },
                    ],
                    "rawProviderPayload": {"token": "SECRET"},
                },
                "macro": {
                    "source": "mixed",
                    "freshness": "cached",
                    "items": [
                        {
                            "symbol": "USD_TWI",
                            "officialSeriesId": "DTWEXBGS",
                            "source": "fred",
                            "sourceType": "official_public",
                            "freshness": "cached",
                            "sourceAuthorityAllowed": True,
                            "scoreContributionAllowed": True,
                        },
                        {
                            "symbol": "FED_ASSETS",
                            "officialSeriesId": "WALCL",
                            "source": "fred",
                            "sourceType": "official_public",
                            "freshness": "cached",
                            "sourceAuthorityAllowed": True,
                            "scoreContributionAllowed": True,
                        },
                    ],
                    "rawProviderPayload": {"token": "SECRET"},
                },
            }

    result = script.run_prewarm(
        write=True,
        service_factory=FakeService,
        readiness_probe=lambda: {
            "readiness": "ready",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "requiredSeriesStatus": {
                "DTWEXBGS": "fulfilled",
                "WALCL": "fulfilled",
                "RRPONTSYD": "fulfilled",
                "WTREGEN": "fulfilled",
                "WRESBAL": "fulfilled",
            },
            "missingSeries": [],
            "staleSeries": [],
            "reason": None,
        },
    )

    assert result["dryRun"] is False
    assert result["writeEnabled"] is True
    assert result["writeAttempted"] is True
    assert result["readiness"] == "ready"
    assert result["cacheRowsWouldWrite"] == 0
    assert result["cacheRowsWritten"] == 2
    assert result["writeEfficacy"] == "written_score_grade_usable"
    assert result["scoreGradeUsable"] is True
    assert result["degradedTargetCount"] == 0
    assert result["degradedTargetSymbols"] == []
    assert result["degradedTargetReasons"] == []
    assert result["writtenButNotScoreGradeReason"] is None
    assert result["fulfilledSeries"] == ["DTWEXBGS", "WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert result["missingSeries"] == []
    assert result["reason"] is None
    assert "rawProviderPayload" not in json.dumps(result)
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize(
    ("series_id", "fixture_name", "expected_value", "expected_date", "expected_hint"),
    [
        ("BAMLH0A0HYM2", "fred_bamlh0a0hym2.json", 3.31, "2026-05-13", "daily_credit_stress"),
        ("CPIAUCSL", "fred_cpiaucsl.json", 321.0, "2026-05-15", "monthly_inflation_index"),
        ("DFF", "fred_dff.json", 4.33, "2026-05-15", "daily_policy_rate"),
        ("VIXCLS", "fred_vixcls.json", 18.22, "2026-05-13", "daily_close"),
        ("DGS2", "fred_dgs2.json", 3.87, "2026-05-13", "daily_rate"),
        ("DGS10", "fred_dgs10.json", 4.45, "2026-05-12", "daily_rate"),
        ("DGS30", "fred_dgs30.json", 4.89, "2026-05-13", "daily_rate"),
        ("PPIACO", "fred_ppiaco.json", 282.0, "2026-05-15", "monthly_inflation_index"),
        ("SOFR", "fred_sofr.json", 5.31, "2026-05-13", "daily_fixing"),
        ("DTWEXBGS", "fred_dtwexbgs.json", 128.42, "2026-05-13", "daily_trade_weighted_usd"),
    ],
)
def test_parse_fred_observations_payload_from_fixtures(
    series_id: str,
    fixture_name: str,
    expected_value: float,
    expected_date: str,
    expected_hint: str,
) -> None:
    observation = parse_fred_observations_payload(series_id, _load_json_fixture(fixture_name))

    assert observation.symbol == series_id
    assert observation.value == expected_value
    assert observation.date == expected_date
    assert observation.as_of == expected_date
    assert observation.source_id == f"fred:{series_id}"
    assert observation.source_type == "official_public"
    assert observation.freshness_hint == expected_hint
    assert observation.unavailable_reason is None


def test_parse_fred_observations_payload_returns_unavailable_for_missing_values() -> None:
    payload = {
        "observations": [
            {"date": "2026-05-13", "value": "."},
            {"date": "2026-05-12", "value": "N/A"},
        ]
    }

    observation = parse_fred_observations_payload("DGS2", payload)

    assert observation.value is None
    assert observation.date is None
    assert observation.as_of is None
    assert observation.unavailable_reason == "fred_observation_value_unavailable"


def test_official_macro_transport_observations_remain_official_but_non_live() -> None:
    observation = parse_fred_observations_payload("DGS10", _load_json_fixture("fred_dgs10.json"))
    delayed = project_source_provenance(source_type=observation.source_type, freshness="delayed")
    stale = project_source_provenance(source_type=observation.source_type, freshness="stale", is_stale=True)

    assert delayed["sourceType"] == "official_public"
    assert delayed["freshnessLabel"] == "延迟"
    assert stale["sourceType"] == "official_public"
    assert stale["freshnessLabel"] == "过期"


def test_parse_fred_observation_points_payload_returns_latest_two_valid_points() -> None:
    points = parse_fred_observation_points_payload("VIXCLS", _load_json_fixture("fred_vixcls.json"), limit=2)

    assert [point.to_dict() for point in points] == [
        {
            "symbol": "VIXCLS",
            "value": 18.22,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "fred:VIXCLS",
            "source_type": "official_public",
            "freshness_hint": "daily_close",
            "unavailable_reason": None,
        },
        {
            "symbol": "VIXCLS",
            "value": 17.05,
            "date": "2026-05-12",
            "asOf": "2026-05-12",
            "source_id": "fred:VIXCLS",
            "source_type": "official_public",
            "freshness_hint": "daily_close",
            "unavailable_reason": None,
        },
    ]


def test_build_treasury_daily_rates_request_matches_official_csv_download() -> None:
    request = build_treasury_daily_rates_request()

    assert request.method == "GET"
    assert request.url == TREASURY_DAILY_RATES_CSV_URL
    assert request.params == {"_format": "csv", "type": "daily_treasury_yield_curve"}
    assert request.source_id == "treasury:daily_treasury_yield_curve"
    assert request.requires_api_key is False


def test_parse_treasury_daily_rates_csv_returns_latest_2y_10y_30y() -> None:
    observations = parse_treasury_daily_rates_csv(_load_text_fixture("treasury_daily_rates.csv"))

    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "DGS2",
            "value": 3.87,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS10",
            "value": 4.41,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS30",
            "value": 4.89,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
    ]


def test_parse_treasury_daily_rates_rows_handles_json_like_rows_and_missing_value() -> None:
    observations = parse_treasury_daily_rates_rows(
        [
            {"Date": "2026-05-12", "2 Yr": "3.91", "10 Yr": "4.45", "30 Yr": "4.92"},
            {"Date": "2026-05-13", "2 Year": "3.87", "10 Year": "4.41", "30 Year": "N/A"},
        ]
    )

    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "DGS2",
            "value": 3.87,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS10",
            "value": 4.41,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS30",
            "value": None,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": "treasury_rate_unavailable",
        },
    ]


def test_parse_treasury_daily_rate_observation_points_csv_returns_latest_two_rows_per_symbol() -> None:
    points = parse_treasury_daily_rate_observation_points_csv(_load_text_fixture("treasury_daily_rates.csv"), limit=2)

    assert [item.to_dict() for item in points["DGS2"]] == [
        {
            "symbol": "DGS2",
            "value": 3.87,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS2",
            "value": 3.91,
            "date": "2026-05-12",
            "asOf": "2026-05-12",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
    ]
    assert [item.to_dict() for item in points["DGS10"]] == [
        {
            "symbol": "DGS10",
            "value": 4.41,
            "date": "2026-05-13",
            "asOf": "2026-05-13",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
        {
            "symbol": "DGS10",
            "value": 4.45,
            "date": "2026-05-12",
            "asOf": "2026-05-12",
            "source_id": "treasury:daily_treasury_yield_curve",
            "source_type": "official_public",
            "freshness_hint": "daily_1530_et",
            "unavailable_reason": None,
        },
    ]


def test_fetch_treasury_daily_rate_observation_points_retries_once_within_bounded_timeout_budget() -> None:
    attempts: list[float] = []
    csv_bytes = _load_text_fixture("treasury_daily_rates.csv").encode("utf-8")

    def _fake_fetch_transport_bytes(request, *, timeout):
        attempts.append(timeout)
        if len(attempts) == 1:
            raise OfficialMacroTransportError(
                "timeout",
                "treasury timed out",
                diagnostics={"providerName": "treasury", "endpointHost": "home.treasury.gov"},
            )
        return csv_bytes

    with patch("src.services.official_macro_transport._fetch_transport_bytes", side_effect=_fake_fetch_transport_bytes):
        points = fetch_treasury_daily_rate_observation_points(limit=2, timeout=0.8)

    assert attempts == [pytest.approx(0.4, abs=0.01), pytest.approx(0.4, abs=0.01)]
    assert [item.value for item in points["DGS10"]] == [4.41, 4.45]


def test_parse_nyfed_sofr_payload_is_explicitly_unsupported_without_repo_shape() -> None:
    observation = parse_nyfed_sofr_payload({"unexpected": "shape"})

    assert observation.to_dict() == {
        "symbol": "SOFR",
        "value": None,
        "date": None,
        "asOf": None,
        "source_id": "nyfed:sofr",
        "source_type": "official_public",
        "freshness_hint": "unsupported_shape",
        "unavailable_reason": NYFED_SOFR_UNSUPPORTED_REASON,
    }


def test_official_macro_live_smoke_missing_fred_key_exits_cleanly_without_secret_output() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)

    treasury_points = {
        "DGS2": [_macro_point("DGS2", 3.87, "2026-05-13", source_id="treasury:daily_treasury_yield_curve", freshness_hint="daily_1530_et")],
        "DGS10": [_macro_point("DGS10", 4.41, "2026-05-13", source_id="treasury:daily_treasury_yield_curve", freshness_hint="daily_1530_et")],
        "DGS30": [_macro_point("DGS30", 4.89, "2026-05-13", source_id="treasury:daily_treasury_yield_curve", freshness_hint="daily_1530_et")],
    }

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=AssertionError("missing FRED key must not trigger FRED network calls"),
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        return_value=treasury_points,
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": False},
    ):
        summary = run_official_macro_live_smoke(now=now)

    _assert_smoke_summary_fields(summary)
    assert summary | {} == {
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "freshnessValid": True,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledSeries": ["DGS2", "DGS10", "DGS30"],
        "missingSeries": ["VIXCLS", "SOFR", "DFF", "BAMLH0A0HYM2"],
        "staleSeries": [],
        "reason": "credentials",
        "attempts": 1,
        "maxAttempts": 3,
        "transientMissingSeries": [],
        "finalAttemptMissingSeries": ["VIXCLS", "SOFR", "DFF", "BAMLH0A0HYM2"],
    }
    dumped = json.dumps(summary, ensure_ascii=False)
    assert "fred-secret-test-key" not in dumped
    assert "FRED_API_KEY" not in dumped


def test_official_macro_live_smoke_reports_bounded_official_series_successfully() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    fred_requested: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        fred_requested.append(series_id)
        values = {
            "VIXCLS": 18.22,
            "SOFR": 5.31,
            "DFF": 4.33,
            "DGS2": 3.87,
            "DGS10": 4.41,
            "DGS30": 4.89,
            "BAMLH0A0HYM2": 3.31,
        }
        return [_macro_point(series_id, values[series_id], "2026-05-13")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        side_effect=AssertionError("bounded FRED smoke should not fan out to Treasury when FRED is configured"),
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_official_macro_live_smoke(now=now)

    assert fred_requested == ["VIXCLS", "SOFR", "DFF", "DGS2", "DGS10", "DGS30", "BAMLH0A0HYM2"]
    _assert_smoke_summary_fields(summary)
    assert summary | {} == {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": True,
        "freshnessValid": True,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "fulfilledSeries": ["VIXCLS", "SOFR", "DFF", "DGS2", "DGS10", "DGS30", "BAMLH0A0HYM2"],
        "missingSeries": [],
        "staleSeries": [],
        "reason": None,
        "attempts": 1,
        "maxAttempts": 3,
        "transientMissingSeries": [],
        "finalAttemptMissingSeries": [],
    }


def test_official_macro_live_smoke_partial_dgs_coverage_fails_closed_without_treasury_fallback() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    fred_requested: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        fred_requested.append(series_id)
        points = {
            "VIXCLS": [_macro_point("VIXCLS", 18.22, "2026-05-13")],
            "SOFR": [_macro_point("SOFR", 5.31, "2026-05-13")],
            "DFF": [_macro_point("DFF", 4.33, "2026-05-13")],
            "DGS2": [_macro_point("DGS2", 3.87, "2026-05-13")],
            "DGS10": [_macro_point("DGS10", 4.41, "2026-05-13")],
            "DGS30": [],
            "BAMLH0A0HYM2": [_macro_point("BAMLH0A0HYM2", 3.31, "2026-05-13")],
        }
        return list(points[series_id])

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        side_effect=AssertionError("partial DGS coverage must not fall back to Treasury when FRED is configured"),
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_official_macro_live_smoke(now=now)

    assert fred_requested.count("DGS30") == 3
    assert set(fred_requested) == {"VIXCLS", "SOFR", "DFF", "DGS2", "DGS10", "DGS30", "BAMLH0A0HYM2"}
    for series_id in {"VIXCLS", "SOFR", "DFF", "DGS2", "DGS10", "BAMLH0A0HYM2"}:
        assert fred_requested.count(series_id) == 1
    _assert_smoke_summary_fields(summary)
    assert summary | {} == {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": False,
        "freshnessValid": True,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledSeries": ["VIXCLS", "SOFR", "DFF", "DGS2", "DGS10", "BAMLH0A0HYM2"],
        "missingSeries": ["DGS30"],
        "staleSeries": [],
        "reason": "series_coverage",
        "attempts": 3,
        "maxAttempts": 3,
        "transientMissingSeries": [],
        "finalAttemptMissingSeries": ["DGS30"],
    }


def test_official_macro_live_smoke_stale_dgs_yields_fail_closed_without_treasury_fallback() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        points = {
            "VIXCLS": [_macro_point("VIXCLS", 18.22, "2026-05-13")],
            "SOFR": [_macro_point("SOFR", 5.31, "2026-05-13")],
            "DFF": [_macro_point("DFF", 4.33, "2026-05-13")],
            "DGS2": [_macro_point("DGS2", 3.87, "2026-05-13")],
            "DGS10": [_macro_point("DGS10", 4.41, "2026-05-08")],
            "DGS30": [_macro_point("DGS30", 4.89, "2026-05-13")],
            "BAMLH0A0HYM2": [_macro_point("BAMLH0A0HYM2", 3.31, "2026-05-13")],
        }
        return list(points[series_id])

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        side_effect=AssertionError("stale DGS coverage must not fall back to Treasury when FRED is configured"),
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_official_macro_live_smoke(now=now)

    _assert_smoke_summary_fields(summary)
    assert summary | {} == {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledSeries": ["VIXCLS", "SOFR", "DFF", "DGS2", "DGS30", "BAMLH0A0HYM2"],
        "missingSeries": [],
        "staleSeries": ["DGS10"],
        "reason": "stale_series",
        "attempts": 3,
        "maxAttempts": 3,
        "transientMissingSeries": [],
        "finalAttemptMissingSeries": [],
    }


def test_official_macro_live_smoke_rejects_proxy_metadata_for_treasury_yield_series() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        if series_id == "DGS10":
            return [
                _macro_point(
                    "DGS10",
                    4.41,
                    "2026-05-13",
                    source_id="yfinance_proxy",
                    source_type="unofficial_proxy",
                )
            ]
        values = {
            "VIXCLS": 18.22,
            "SOFR": 5.31,
            "DFF": 4.33,
            "DGS2": 3.87,
            "DGS30": 4.89,
            "BAMLH0A0HYM2": 3.31,
        }
        return [_macro_point(series_id, values[series_id], "2026-05-13")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        side_effect=AssertionError("proxy Treasury yield metadata must not be masked by Treasury fallback when FRED is configured"),
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_official_macro_live_smoke(now=now)

    _assert_smoke_summary_fields(summary)
    assert summary | {} == {
        "credentialsPresent": True,
        "providerConstructed": True,
        "probePassed": False,
        "freshnessValid": True,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledSeries": ["VIXCLS", "SOFR", "DFF", "DGS2", "DGS30", "BAMLH0A0HYM2"],
        "missingSeries": ["DGS10"],
        "staleSeries": [],
        "reason": "source_metadata_invalid",
        "attempts": 3,
        "maxAttempts": 3,
        "transientMissingSeries": [],
        "finalAttemptMissingSeries": ["DGS10"],
    }


def test_official_macro_live_smoke_retries_transient_missing_series_and_passes() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    attempts_by_series: dict[str, int] = {}

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        attempts_by_series[series_id] = attempts_by_series.get(series_id, 0) + 1
        if series_id in {"SOFR", "BAMLH0A0HYM2"} and attempts_by_series[series_id] == 1:
            return []
        values = {
            "VIXCLS": 18.22,
            "SOFR": 5.31,
            "DFF": 4.33,
            "DGS2": 3.87,
            "DGS10": 4.41,
            "DGS30": 4.89,
            "BAMLH0A0HYM2": 3.31,
        }
        return [_macro_point(series_id, values[series_id], "2026-05-13")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        side_effect=AssertionError("retry hardening must stay within official FRED smoke path when credentials are configured"),
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_official_macro_live_smoke(now=now)

    assert summary["probePassed"] is True
    assert summary["attempts"] == 2
    assert summary["maxAttempts"] == 3
    assert summary["transientMissingSeries"] == ["SOFR", "BAMLH0A0HYM2"]
    assert summary["finalAttemptMissingSeries"] == []
    assert attempts_by_series == {
        "VIXCLS": 1,
        "SOFR": 2,
        "DFF": 1,
        "DGS2": 1,
        "DGS10": 1,
        "DGS30": 1,
        "BAMLH0A0HYM2": 2,
    }


def test_official_macro_live_smoke_stops_after_bounded_retry_for_persistent_missing_series() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    attempts_by_series: dict[str, int] = {}

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        attempts_by_series[series_id] = attempts_by_series.get(series_id, 0) + 1
        if series_id == "BAMLH0A0HYM2":
            return []
        values = {
            "VIXCLS": 18.22,
            "SOFR": 5.31,
            "DFF": 4.33,
            "DGS2": 3.87,
            "DGS10": 4.41,
            "DGS30": 4.89,
        }
        return [_macro_point(series_id, values[series_id], "2026-05-13")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        side_effect=AssertionError("persistent missing series must not trigger Treasury fallback when FRED is configured"),
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_official_macro_live_smoke(now=now)

    assert summary["probePassed"] is False
    assert summary["reason"] == "series_coverage"
    assert summary["attempts"] == 3
    assert summary["maxAttempts"] == 3
    assert summary["missingSeries"] == ["BAMLH0A0HYM2"]
    assert summary["finalAttemptMissingSeries"] == ["BAMLH0A0HYM2"]
    assert attempts_by_series["BAMLH0A0HYM2"] == 3
    assert set(attempts_by_series) == {
        "VIXCLS",
        "SOFR",
        "DFF",
        "DGS2",
        "DGS10",
        "DGS30",
        "BAMLH0A0HYM2",
    }


def test_official_macro_live_smoke_retries_only_bounded_series_without_broad_fanout() -> None:
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    requested_series: list[str] = []

    def _fake_fetch_fred(series_id: str, *, limit: int = 2, timeout: float = 0.0):
        requested_series.append(series_id)
        if series_id == "SOFR" and requested_series.count("SOFR") == 1:
            return []
        values = {
            "VIXCLS": 18.22,
            "SOFR": 5.31,
            "DFF": 4.33,
            "DGS2": 3.87,
            "DGS10": 4.41,
            "DGS30": 4.89,
            "BAMLH0A0HYM2": 3.31,
        }
        return [_macro_point(series_id, values[series_id], "2026-05-13")]

    with patch(
        "src.services.official_macro_transport.fetch_fred_observation_points",
        side_effect=_fake_fetch_fred,
    ), patch(
        "src.services.official_macro_transport.fetch_treasury_daily_rate_observation_points",
        side_effect=AssertionError("bounded series retry must not broaden provider fanout"),
    ), patch(
        "src.services.official_macro_transport.fred_runtime_config_probe",
        return_value={"configPresent": True, "apiKeyPresent": True},
    ):
        summary = run_official_macro_live_smoke(now=now)

    assert summary["probePassed"] is True
    assert set(requested_series) == {
        "VIXCLS",
        "SOFR",
        "DFF",
        "DGS2",
        "DGS10",
        "DGS30",
        "BAMLH0A0HYM2",
    }
    assert requested_series.count("SOFR") == 2
    for series_id in {"VIXCLS", "DFF", "DGS2", "DGS10", "DGS30", "BAMLH0A0HYM2"}:
        assert requested_series.count(series_id) == 1
