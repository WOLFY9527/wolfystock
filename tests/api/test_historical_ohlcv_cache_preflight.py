from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market_provider_operations


def _provider_read_admin() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


def _provider_write_admin() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read", "ops:providers:write"),
    )


def _admin_without_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("users:read",),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


class _FakePreflightService:
    def __init__(self) -> None:
        self.preflight_calls: list[dict] = []
        self.seed_calls: list[dict] = []

    def preflight(self, *, symbols_by_market=None, required_bars=60, require_adjusted=True, dry_run=True):
        self.preflight_calls.append(
            {
                "symbols_by_market": symbols_by_market,
                "required_bars": required_bars,
                "require_adjusted": require_adjusted,
                "dry_run": dry_run,
            }
        )
        return {
            "contractVersion": "historical_ohlcv_cache_preflight_v1",
            "dryRun": True,
            "networkCallsEnabled": False,
            "mutationEnabled": False,
            "activationChecklist": {
                "contractVersion": "historical_ohlcv_data_activation_checklist_v1",
                "operatorOnly": True,
                "readOnly": True,
                "noExternalCalls": True,
                "consumerVisible": False,
                "supportedStates": [
                    "disabled_by_config",
                    "dependency_missing",
                    "ready_to_seed",
                    "seeded/cache_hit",
                    "failed_safely",
                ],
                "starterSymbolSets": {
                    "us": {"label": "US first cache activation set", "symbols": ["SPY", "QQQ", "AAPL", "MSFT"], "supported": True},
                    "cnIfSupported": {"label": "CN first cache activation set if the local CN runtime is supported", "symbols": ["600519", "000001", "601398"], "supported": True},
                },
                "workflowUnlocks": ["Stock", "Scanner", "Backtest", "Technical Indicators", "Market Regime"],
                "items": [],
            },
            "markets": {},
        }

    def seed(self, *, symbols_by_market=None, required_bars=60, require_adjusted=True, dry_run=True):
        self.seed_calls.append(
            {
                "symbols_by_market": symbols_by_market,
                "required_bars": required_bars,
                "require_adjusted": require_adjusted,
                "dry_run": dry_run,
            }
        )
        return {
            "contractVersion": "historical_ohlcv_cache_preflight_v1",
            "dryRun": dry_run,
            "networkCallsEnabled": not dry_run,
            "mutationEnabled": not dry_run,
            "activationChecklist": {
                "contractVersion": "historical_ohlcv_data_activation_checklist_v1",
                "operatorOnly": True,
                "readOnly": True,
                "noExternalCalls": True,
                "consumerVisible": False,
                "supportedStates": [
                    "disabled_by_config",
                    "dependency_missing",
                    "ready_to_seed",
                    "seeded/cache_hit",
                    "failed_safely",
                ],
                "starterSymbolSets": {
                    "us": {"label": "US first cache activation set", "symbols": ["SPY", "QQQ", "AAPL", "MSFT"], "supported": True},
                    "cnIfSupported": {"label": "CN first cache activation set if the local CN runtime is supported", "symbols": ["600519", "000001", "601398"], "supported": True},
                },
                "workflowUnlocks": ["Stock", "Scanner", "Backtest", "Technical Indicators", "Market Regime"],
                "items": [],
            },
            "markets": {},
        }


def _client_for(user_factory, service: _FakePreflightService) -> TestClient:
    app = FastAPI()
    app.include_router(market_provider_operations.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_current_user] = user_factory
    app.dependency_overrides[market_provider_operations.get_historical_ohlcv_cache_preflight_service] = lambda: service
    return TestClient(app)


def test_preflight_endpoint_requires_provider_read_capability() -> None:
    service = _FakePreflightService()

    assert _client_for(_regular_user, service).get("/api/v1/admin/historical-ohlcv/cache-preflight").status_code == 403
    no_capability = _client_for(_admin_without_provider_read, service).get("/api/v1/admin/historical-ohlcv/cache-preflight")
    assert no_capability.status_code == 403
    assert no_capability.json()["detail"]["error"] == "admin_capability_required"


def test_preflight_endpoint_returns_dry_run_payload_and_parses_symbols() -> None:
    service = _FakePreflightService()
    client = _client_for(_provider_read_admin, service)

    response = client.get(
        "/api/v1/admin/historical-ohlcv/cache-preflight",
        params={"cn_symbols": "600519,000001", "us_symbols": "spy,qqq,aapl,msft", "required_bars": "30"},
    )

    assert response.status_code == 200
    assert response.json()["dryRun"] is True
    assert response.json()["activationChecklist"] == {
        "contractVersion": "historical_ohlcv_data_activation_checklist_v1",
        "operatorOnly": True,
        "readOnly": True,
        "noExternalCalls": True,
        "consumerVisible": False,
        "supportedStates": [
            "disabled_by_config",
            "dependency_missing",
            "ready_to_seed",
            "seeded/cache_hit",
            "failed_safely",
        ],
        "starterSymbolSets": {
            "us": {"label": "US first cache activation set", "symbols": ["SPY", "QQQ", "AAPL", "MSFT"], "supported": True},
            "cnIfSupported": {"label": "CN first cache activation set if the local CN runtime is supported", "symbols": ["600519", "000001", "601398"], "supported": True},
        },
        "workflowUnlocks": ["Stock", "Scanner", "Backtest", "Technical Indicators", "Market Regime"],
        "items": [],
    }
    assert service.preflight_calls == [
        {
            "symbols_by_market": {"cn": ["600519", "000001"], "us": ["SPY", "QQQ", "AAPL", "MSFT"]},
            "required_bars": 30,
            "require_adjusted": True,
            "dry_run": True,
        }
    ]


def test_preflight_endpoint_uses_default_symbols_when_query_symbols_are_omitted() -> None:
    service = _FakePreflightService()
    client = _client_for(_provider_read_admin, service)

    response = client.get("/api/v1/admin/historical-ohlcv/cache-preflight")

    assert response.status_code == 200
    assert service.preflight_calls == [
        {
            "symbols_by_market": None,
            "required_bars": 60,
            "require_adjusted": True,
            "dry_run": True,
        }
    ]


def test_preflight_endpoint_preserves_explicit_us_only_query_scope() -> None:
    service = _FakePreflightService()
    client = _client_for(_provider_read_admin, service)

    response = client.get("/api/v1/admin/historical-ohlcv/cache-preflight", params={"us_symbols": "spy"})

    assert response.status_code == 200
    assert service.preflight_calls == [
        {
            "symbols_by_market": {"cn": [], "us": ["SPY"]},
            "required_bars": 60,
            "require_adjusted": True,
            "dry_run": True,
        }
    ]


def test_seed_endpoint_defaults_to_dry_run_and_requires_write_for_execute() -> None:
    service = _FakePreflightService()
    read_client = _client_for(_provider_read_admin, service)
    dry = read_client.post(
        "/api/v1/admin/historical-ohlcv/cache-preflight/seed",
        json={"usSymbols": ["AAPL"], "dryRun": True},
    )
    assert dry.status_code == 200
    assert service.seed_calls[-1]["dry_run"] is True

    blocked = read_client.post(
        "/api/v1/admin/historical-ohlcv/cache-preflight/seed",
        json={"usSymbols": ["AAPL"], "dryRun": False},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"] == "admin_capability_required"

    write_client = _client_for(_provider_write_admin, service)
    execute = write_client.post(
        "/api/v1/admin/historical-ohlcv/cache-preflight/seed",
        json={"usSymbols": ["AAPL"], "dryRun": False, "requiredBars": 10},
    )
    assert execute.status_code == 200
    assert service.seed_calls[-1] == {
        "symbols_by_market": {"cn": [], "us": ["AAPL"]},
        "required_bars": 10,
        "require_adjusted": True,
        "dry_run": False,
    }


def test_non_admin_route_failures_do_not_leak_activation_checklist_internals() -> None:
    service = _FakePreflightService()
    regular_text = _client_for(_regular_user, service).get("/api/v1/admin/historical-ohlcv/cache-preflight").text.lower()
    missing_capability_text = _client_for(_admin_without_provider_read, service).get(
        "/api/v1/admin/historical-ohlcv/cache-preflight"
    ).text.lower()

    for payload_text in (regular_text, missing_capability_text):
        assert "orcl" not in payload_text
        assert "nvda" not in payload_text
        assert "market regime" not in payload_text
        assert "wolfystock_" not in payload_text
