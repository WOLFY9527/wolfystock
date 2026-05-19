# -*- coding: utf-8 -*-
"""Fixture tests for official macro transport helpers."""

from __future__ import annotations

import ast
import json
import socket
import ssl
import sys
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
    parse_fred_observation_points_payload,
    parse_fred_observations_payload,
    fetch_fred_observation_points,
    parse_nyfed_sofr_payload,
    parse_treasury_daily_rate_observation_points_csv,
    parse_treasury_daily_rates_csv,
    parse_treasury_daily_rates_rows,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "official_macro"
MODULE_PATH = REPO_ROOT / "src" / "services" / "official_macro_transport.py"
FORBIDDEN_IMPORT_PREFIXES = ("requests", "httpx", "aiohttp", "urllib3", "yfinance")


def _load_json_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_text_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _module_imports() -> set[str]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


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
