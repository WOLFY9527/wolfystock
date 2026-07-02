from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market_provider_operations
from src.services.us_ohlcv_cache_refresh import UsOhlcvCacheRefreshService


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
                    "us": {"label": "US first cache activation set", "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"], "supported": True},
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
                    "us": {"label": "US first cache activation set", "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"], "supported": True},
                    "cnIfSupported": {"label": "CN first cache activation set if the local CN runtime is supported", "symbols": ["600519", "000001", "601398"], "supported": True},
                },
                "workflowUnlocks": ["Stock", "Scanner", "Backtest", "Technical Indicators", "Market Regime"],
                "items": [],
            },
            "markets": {},
        }


class _FakeUsRefreshService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def refresh(
        self,
        *,
        symbols=None,
        tier="starter",
        execute=False,
        max_symbols=5,
        required_bars=60,
        require_adjusted=True,
    ):
        self.calls.append(
            {
                "symbols": symbols,
                "tier": tier,
                "execute": execute,
                "max_symbols": max_symbols,
                "required_bars": required_bars,
                "require_adjusted": require_adjusted,
            }
        )
        refresh_count = min(max_symbols, len(symbols or []))
        return {
            "contractVersion": "us_ohlcv_cache_refresh_v1",
            "dryRun": not execute,
            "execute": execute,
            "target": {"market": "us", "tier": tier, "source": "test", "configured": False},
            "requestedSymbols": list(symbols or []),
            "normalizedSymbols": list(symbols or []),
            "alreadyAvailableSymbols": [],
            "missingOrStaleSymbols": list(symbols or []),
            "skippedSymbols": [],
            "estimatedMaxProviderCalls": refresh_count,
            "plannedProviderCalls": refresh_count,
            "actualProviderCallsMade": 0,
            "plannedCacheWrites": refresh_count,
            "plannedSymbolsToWrite": list(symbols or [])[:refresh_count],
            "plannedRowsUnknown": refresh_count > 0,
            "actualSymbolsWritten": 0,
            "actualRowsWritten": 0,
            "writeTarget": "local_us_parquet_cache",
            "refreshPolicy": {
                "explicitExecutionRequired": True,
                "dryRunDefault": True,
                "boundedByMaxSymbols": True,
                "consumerSafe": True,
            },
            "providerPolicy": {
                "liveProviderCallsAllowed": execute,
                "plannedProviderCalls": refresh_count,
                "actualProviderCallsMade": 0,
                "providerCallsMade": 0,
                "providerCallBoundary": "missing_or_stale_symbols_only",
                "consumerSafe": True,
            },
            "writePolicy": {
                "cacheWritesAllowed": execute,
                "databaseWritesAllowed": False,
                "writeTarget": "local_us_parquet_cache",
                "plannedCacheWrites": refresh_count,
                "plannedSymbolsToWrite": list(symbols or [])[:refresh_count],
                "plannedRowsUnknown": refresh_count > 0,
                "symbolsWritten": [],
                "rowsWritten": 0,
                "actualSymbolsWritten": 0,
                "actualRowsWritten": 0,
                "consumerSafe": True,
            },
            "plan": {
                "symbols": [],
                "alreadyAvailableCount": 0,
                "refreshCandidateCount": refresh_count,
                "plannedProviderCalls": refresh_count,
                "plannedCacheWrites": refresh_count,
                "plannedSymbolsToWrite": list(symbols or [])[:refresh_count],
                "writePlanSemantics": "would_write_if_execute_true",
                "skippedCount": 0,
            },
            "results": [],
            "summary": {},
            "consumerSafe": True,
        }


class _CountingUsCache:
    def __init__(self) -> None:
        self.load_calls: list[tuple[str, int | None]] = []
        self.save_calls: list[str] = []

    def load_result(self, symbol: str, **kwargs: Any) -> SimpleNamespace:
        self.load_calls.append((str(symbol).upper(), kwargs.get("days")))
        return SimpleNamespace(status="missing", dataframe=None)

    def save(self, symbol: str, *_: Any) -> int:
        self.save_calls.append(str(symbol).upper())
        raise AssertionError("dry-run cache write called")


class _ProviderShouldNotRun:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_daily_data(self, *, stock_code: str, **_: Any) -> Any:
        self.calls.append(str(stock_code).upper())
        raise AssertionError("dry-run provider called")


def _client_for(user_factory, service: _FakePreflightService) -> TestClient:
    app = FastAPI()
    app.include_router(market_provider_operations.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_current_user] = user_factory
    app.dependency_overrides[market_provider_operations.get_historical_ohlcv_cache_preflight_service] = lambda: service
    return TestClient(app)


def _refresh_client_for(user_factory, service: _FakeUsRefreshService) -> TestClient:
    app = FastAPI()
    app.include_router(market_provider_operations.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_current_user] = user_factory
    app.dependency_overrides[market_provider_operations.get_us_ohlcv_cache_refresh_service] = lambda: service
    return TestClient(app)


def test_us_ohlcv_refresh_route_is_registered_with_operator_friendly_schema() -> None:
    app = FastAPI()
    app.include_router(market_provider_operations.router, prefix="/api/v1/admin")

    schema = app.openapi()
    route = schema["paths"]["/api/v1/admin/historical-ohlcv/us-cache-refresh"]["post"]
    request_schema_ref = route["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_schema_name = request_schema_ref.rsplit("/", 1)[-1]
    response_schema_ref = route["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_schema_name = response_schema_ref.rsplit("/", 1)[-1]
    properties = schema["components"]["schemas"][request_schema_name]["properties"]
    response_properties = schema["components"]["schemas"][response_schema_name]["properties"]

    assert route["summary"] == "Plan or explicitly execute bounded US OHLCV cache refresh"
    assert request_schema_name == "UsOhlcvCacheRefreshRequest"
    for field_name in ("symbols", "target", "universe", "execute", "dryRun", "maxSymbols"):
        assert field_name in properties
    for field_name in (
        "estimatedMaxProviderCalls",
        "plannedProviderCalls",
        "actualProviderCallsMade",
        "plannedCacheWrites",
        "plannedSymbolsToWrite",
        "plannedRowsUnknown",
        "actualSymbolsWritten",
        "actualRowsWritten",
    ):
        assert field_name in response_properties


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
            "us": {"label": "US first cache activation set", "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"], "supported": True},
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


def test_us_ohlcv_refresh_endpoint_defaults_to_dry_run_with_provider_read_capability() -> None:
    service = _FakeUsRefreshService()
    client = _refresh_client_for(_provider_read_admin, service)

    response = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["spy", "aapl"], "maxSymbols": 2, "requiredBars": 30},
    )

    assert response.status_code == 200
    assert response.json()["dryRun"] is True
    assert service.calls == [
        {
            "symbols": ["spy", "aapl"],
            "tier": "starter",
            "execute": False,
            "max_symbols": 2,
            "required_bars": 30,
            "require_adjusted": True,
        }
    ]


def test_us_ohlcv_refresh_endpoint_accepts_explicit_symbols_dry_run_contract() -> None:
    service = _FakeUsRefreshService()
    client = _refresh_client_for(_provider_read_admin, service)

    response = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["TSLA", "NVDA"], "execute": False, "dryRun": True, "maxSymbols": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dryRun"] is True
    assert payload["execute"] is False
    assert payload["providerPolicy"]["liveProviderCallsAllowed"] is False
    assert payload["writePolicy"]["cacheWritesAllowed"] is False
    assert payload["writePolicy"]["databaseWritesAllowed"] is False
    assert service.calls[-1] == {
        "symbols": ["TSLA", "NVDA"],
        "tier": "starter",
        "execute": False,
        "max_symbols": 2,
        "required_bars": 60,
        "require_adjusted": True,
    }


def test_us_ohlcv_refresh_endpoint_accepts_target_symbols_dry_run_contract() -> None:
    service = _FakeUsRefreshService()
    client = _refresh_client_for(_provider_read_admin, service)

    response = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={
            "target": "symbols",
            "symbols": ["TSLA", "NVDA"],
            "execute": False,
            "dryRun": True,
            "maxSymbols": 2,
        },
    )

    assert response.status_code == 200
    assert service.calls[-1]["symbols"] == ["TSLA", "NVDA"]
    assert service.calls[-1]["tier"] == "starter"
    assert service.calls[-1]["execute"] is False


def test_us_ohlcv_refresh_endpoint_accepts_starter_and_tier1_dry_run_contracts() -> None:
    service = _FakeUsRefreshService()
    client = _refresh_client_for(_provider_read_admin, service)

    starter = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"universe": "starter", "execute": False, "dryRun": True, "maxSymbols": 2},
    )
    tier1 = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"target": "tier1", "execute": False, "dryRun": True, "maxSymbols": 2},
    )

    assert starter.status_code == 200
    assert tier1.status_code == 200
    assert service.calls[-2]["symbols"] == []
    assert service.calls[-2]["tier"] == "starter"
    assert service.calls[-1]["symbols"] == []
    assert service.calls[-1]["tier"] == "tier1"


def test_us_ohlcv_refresh_endpoint_accepts_snake_case_equivalents() -> None:
    service = _FakeUsRefreshService()
    client = _refresh_client_for(_provider_read_admin, service)

    response = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["TSLA"], "execute": False, "dry_run": True, "max_symbols": 1},
    )

    assert response.status_code == 200
    assert service.calls[-1]["max_symbols"] == 1


def test_us_ohlcv_refresh_endpoint_dry_run_does_not_call_provider_or_write_cache() -> None:
    cache = _CountingUsCache()
    provider = _ProviderShouldNotRun()
    service = UsOhlcvCacheRefreshService(cache=cache, fetcher=provider, today=date(2026, 1, 10))
    client = _refresh_client_for(_provider_read_admin, service)

    response = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["TSLA", "NVDA"], "execute": False, "dryRun": True, "maxSymbols": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dryRun"] is True
    assert payload["estimatedMaxProviderCalls"] == 2
    assert payload["plannedProviderCalls"] == 2
    assert payload["actualProviderCallsMade"] == 0
    assert payload["providerPolicy"]["plannedProviderCalls"] == 2
    assert payload["providerPolicy"]["providerCallsMade"] == 0
    assert payload["providerPolicy"]["actualProviderCallsMade"] == 0
    planned_provider_symbol_count = len(
        [item for item in payload["plan"]["symbols"] if item["providerCallPlanned"]]
    )
    planned_write_symbol_count = len([item for item in payload["plan"]["symbols"] if item["writePlanned"]])
    assert planned_provider_symbol_count == payload["plannedProviderCalls"]
    assert planned_write_symbol_count == payload["plannedCacheWrites"]
    assert payload["plannedCacheWrites"] == 2
    assert payload["plannedSymbolsToWrite"] == ["TSLA", "NVDA"]
    assert payload["writePolicy"]["plannedCacheWrites"] == 2
    assert payload["writePolicy"]["plannedSymbolsToWrite"] == ["TSLA", "NVDA"]
    assert payload["writePolicy"]["cacheWritesAllowed"] is False
    assert payload["writePolicy"]["databaseWritesAllowed"] is False
    assert payload["writePolicy"]["actualRowsWritten"] == 0
    assert payload["writePolicy"]["rowsWritten"] == 0
    assert payload["actualSymbolsWritten"] == 0
    assert payload["actualRowsWritten"] == 0
    assert provider.calls == []
    assert cache.save_calls == []
    assert cache.load_calls == [("TSLA", 60), ("NVDA", 60)]


def test_us_ohlcv_refresh_endpoint_requires_provider_write_for_execute() -> None:
    service = _FakeUsRefreshService()
    read_client = _refresh_client_for(_provider_read_admin, service)

    blocked = read_client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["AAPL"], "execute": True},
    )

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"] == "admin_capability_required"
    assert service.calls == []

    write_client = _refresh_client_for(_provider_write_admin, service)
    executed = write_client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["AAPL"], "execute": True, "maxSymbols": 1},
    )

    assert executed.status_code == 200
    assert executed.json()["execute"] is True
    assert service.calls[-1]["execute"] is True
    assert service.calls[-1]["max_symbols"] == 1


def test_us_ohlcv_refresh_endpoint_rejects_ambiguous_execution_contract_with_field_detail() -> None:
    service = _FakeUsRefreshService()
    client = _refresh_client_for(_provider_read_admin, service)

    response = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["TSLA"], "execute": True, "dryRun": True},
    )

    assert response.status_code == 422
    payload_text = str(response.json()).lower()
    assert "dryrun" in payload_text or "dry_run" in payload_text
    assert "execute" in payload_text
    assert service.calls == []


def test_us_ohlcv_refresh_endpoint_rejects_dry_run_false_without_execute() -> None:
    service = _FakeUsRefreshService()
    client = _refresh_client_for(_provider_read_admin, service)

    response = client.post(
        "/api/v1/admin/historical-ohlcv/us-cache-refresh",
        json={"symbols": ["TSLA"], "execute": False, "dryRun": False},
    )

    assert response.status_code == 422
    payload_text = str(response.json()).lower()
    assert "dryrun" in payload_text or "dry_run" in payload_text
    assert "execute" in payload_text
    assert service.calls == []
