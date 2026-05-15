# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.smoke_market_data_authenticated as smoke


RAW_KEY_MARKER = "raw-api-key-value"
RAW_URL_MARKER = "https://provider.example.test/v1/raw?api_key=raw-api-key-value"
RAW_COOKIE_MARKER = "raw-session-cookie"


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeClient:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def request(self, method: str, path: str, headers: dict[str, str] | None = None):
        self.calls.append((method, path, headers or {}))
        return self._responses[path]


def test_probe_routes_checks_expected_market_inventory_and_bounded_authenticated_summary() -> None:
    client = _FakeClient(
        {
            "/api/v1/market/rates": _FakeResponse(
                200,
                {
                    "source": "treasury",
                    "sourceType": "official_public",
                    "sourceLabel": RAW_URL_MARKER,
                    "freshness": "delayed",
                    "fallbackUsed": False,
                    "providerHealth": {"status": "cache", "provider": RAW_URL_MARKER},
                },
            ),
            "/api/v1/market/temperature": _FakeResponse(
                200,
                {
                    "source": "mixed",
                    "sourceType": "public_api",
                    "freshness": "live",
                    "fallbackUsed": True,
                    "providerHealth": {"status": "partial", "provider": RAW_KEY_MARKER},
                },
            ),
            "/api/v1/market/liquidity-monitor": _FakeResponse(
                200,
                {
                    "freshness": {"status": "delayed"},
                    "sourceMetadata": {
                        "externalProviderCalls": False,
                        "providerRuntimeChanged": False,
                        "marketCacheMutation": False,
                    },
                    "indicators": [{"status": "partial"}],
                },
            ),
            "/api/v1/market/fx-commodities": _FakeResponse(
                200,
                {
                    "source": "yfinance_proxy",
                    "sourceType": "unofficial_proxy",
                    "freshness": "delayed",
                    "fallbackUsed": False,
                    "providerHealth": {"status": "cache", "provider": RAW_COOKIE_MARKER},
                },
            ),
            "/api/v1/market-overview/macro": _FakeResponse(
                200,
                {
                    "source": "fallback",
                    "sourceType": "official_public",
                    "freshness": "fallback",
                    "fallbackUsed": True,
                },
            ),
        }
    )

    records = smoke.probe_routes(client, smoke.MARKET_ROUTES, mode="authenticated")

    assert {path for _, path, _ in client.calls} == set(smoke.MARKET_ROUTES)
    assert [item["route"] for item in records] == list(smoke.MARKET_ROUTES)

    rates = next(item for item in records if item["route"] == "/api/v1/market/rates")
    temperature = next(item for item in records if item["route"] == "/api/v1/market/temperature")
    liquidity = next(item for item in records if item["route"] == "/api/v1/market/liquidity-monitor")
    macro = next(item for item in records if item["route"] == "/api/v1/market-overview/macro")

    assert rates == {
        "mode": "authenticated",
        "route": "/api/v1/market/rates",
        "httpStatus": 200,
        "sourceClass": "official_public",
        "freshnessClass": "delayed",
        "fallback": False,
        "partial": False,
    }
    assert temperature["sourceClass"] == "mixed"
    assert temperature["partial"] is True
    assert liquidity["sourceClass"] == "aggregated_partial"
    assert liquidity["partial"] is True
    assert macro["sourceClass"] == "fallback"
    assert macro["fallback"] is True

    text = json.dumps(records, ensure_ascii=False, sort_keys=True)
    for marker in (RAW_KEY_MARKER, RAW_URL_MARKER, RAW_COOKIE_MARKER, "authorization", "traceback", "cookie"):
        assert marker.lower() not in text.lower()


def test_unauthenticated_summary_reports_401_not_429() -> None:
    client = _FakeClient({route: _FakeResponse(401, {"error": "unauthorized", "message": "Login required"}) for route in smoke.MARKET_ROUTES})

    records = smoke.probe_routes(
        client,
        smoke.MARKET_ROUTES,
        mode="unauthenticated",
        headers={"X-Forwarded-For": smoke.PRIME_IP},
    )

    assert all(item["httpStatus"] == 401 for item in records)
    assert all(item["sourceClass"] == "auth_guard_401" for item in records)
    assert all(item["freshnessClass"] == "not_applicable" for item in records)
    assert all(item["fallback"] is False and item["partial"] is False for item in records)


def test_main_writes_bounded_json_and_exit_code(monkeypatch, capsys) -> None:
    bounded_records = [
        {
            "mode": "unauthenticated",
            "route": "/api/v1/market/rates",
            "httpStatus": 401,
            "sourceClass": "auth_guard_401",
            "freshnessClass": "not_applicable",
            "fallback": False,
            "partial": False,
        },
        {
            "mode": "authenticated",
            "route": "/api/v1/market/rates",
            "httpStatus": 200,
            "sourceClass": "official_public",
            "freshnessClass": "delayed",
            "fallback": False,
            "partial": False,
        },
    ]
    monkeypatch.setattr(smoke, "run_smoke", lambda include_unauthenticated=False: bounded_records)

    exit_code = smoke.main(["--include-unauthenticated"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == bounded_records


def test_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/smoke_market_data_authenticated.py", "--help"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--include-unauthenticated" in result.stdout
