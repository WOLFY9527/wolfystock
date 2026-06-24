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
        params={"cn_symbols": "600519,000001", "us_symbols": "orcl,aapl,nvda,msft", "required_bars": "30"},
    )

    assert response.status_code == 200
    assert response.json()["dryRun"] is True
    assert service.preflight_calls == [
        {
            "symbols_by_market": {"cn": ["600519", "000001"], "us": ["ORCL", "AAPL", "NVDA", "MSFT"]},
            "required_bars": 30,
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
