# -*- coding: utf-8 -*-
"""Provider activation verifier contract tests."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market_provider_operations
from src.services.provider_activation_verifier import ProviderActivationVerifierService


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TEXT_MARKERS = (
    "apiKey",
    "api_key",
    "token",
    "credential",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "stack trace",
    "RuntimeError",
    "FMP_SECRET",
)


def _admin_user() -> CurrentUser:
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


def _admin_without_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id="admin-2",
        username="admin2",
        display_name="Admin 2",
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


def _client_for(user_factory) -> TestClient:
    app = FastAPI()
    app.include_router(market_provider_operations.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_current_user] = user_factory
    return TestClient(app)


def _row(payload: dict, capability_id: str) -> dict:
    return next(item for item in payload["capabilities"] if item["capabilityId"] == capability_id)


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class _InstalledSpec:
    pass


def _installed_spec_finder(name: str):
    if name in {"akshare", "baostock", "yfinance"}:
        return _InstalledSpec()
    return None


def test_activation_verifier_fails_closed_when_dependencies_and_config_are_absent(tmp_path: Path) -> None:
    service = ProviderActivationVerifierService(
        env={"SCANNER_LOCAL_UNIVERSE_PATH": str(tmp_path / "missing-universe.csv")},
        spec_finder=lambda _name: None,
        today=date(2026, 6, 27),
    )

    payload = service.verify()

    assert payload["contractVersion"] == "provider_activation_verifier_v1"
    assert payload["operatorOnly"] is True
    assert payload["readOnly"] is True
    assert payload["externalProviderCalls"] is False
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert payload["summary"]["availableCount"] == 0
    assert payload["summary"]["missingCount"] >= 3
    assert payload["summary"]["notConfiguredCount"] >= 2
    assert [item["capabilityId"] for item in payload["capabilities"]] == [
        "akshare.cn_hk_market_data",
        "baostock.cn_ohlcv",
        "fmp.fundamentals_earnings",
        "yfinance.market_data",
        "historical_ohlcv.runtime",
        "earnings_fundamentals.readiness",
        "scanner.universe",
    ]

    assert _row(payload, "akshare.cn_hk_market_data")["status"] == "missing"
    assert _row(payload, "baostock.cn_ohlcv")["status"] == "missing"
    assert _row(payload, "fmp.fundamentals_earnings")["status"] == "not_configured"
    assert _row(payload, "yfinance.market_data")["status"] == "missing"
    assert _row(payload, "historical_ohlcv.runtime")["status"] == "not_configured"
    assert _row(payload, "scanner.universe")["status"] == "missing"

    scanner = _row(payload, "scanner.universe")
    assert "Scanner" in scanner["blockedProductSurfaces"]
    assert scanner["adminNextAction"]
    assert scanner["operatorAction"] == scanner["adminNextAction"]
    assert scanner["reason"] == "scanner_universe_missing"
    assert scanner["consumerSafeMessage"] == "扫描标的池缺失，暂时无法生成候选。"
    assert scanner["minimumValidationCheck"]

    text = _json_text(payload)
    for marker in FORBIDDEN_TEXT_MARKERS:
        assert marker.lower() not in text.lower()


def test_activation_verifier_does_not_treat_importable_sdks_or_credentials_as_available(
    tmp_path: Path,
) -> None:
    service = ProviderActivationVerifierService(
        env={
            "FMP_API_KEY": "FMP_SECRET_VALUE",
            "SCANNER_LOCAL_UNIVERSE_PATH": str(tmp_path / "missing-universe.csv"),
        },
        spec_finder=_installed_spec_finder,
        today=date(2026, 6, 27),
    )

    payload = service.verify()

    assert _row(payload, "akshare.cn_hk_market_data")["status"] == "unavailable"
    assert _row(payload, "baostock.cn_ohlcv")["status"] == "unavailable"
    assert _row(payload, "yfinance.market_data")["status"] == "unavailable"
    assert _row(payload, "fmp.fundamentals_earnings")["status"] == "insufficient_permissions"
    assert "FMP_SECRET_VALUE" not in _json_text(payload)


def test_activation_verifier_requires_configuration_even_with_successful_probe_evidence(
    tmp_path: Path,
) -> None:
    service = ProviderActivationVerifierService(
        env={"SCANNER_LOCAL_UNIVERSE_PATH": str(tmp_path / "missing-universe.csv")},
        spec_finder=_installed_spec_finder,
        today=date(2026, 6, 27),
        local_checks={"fmp_provider_available": True},
    )

    payload = service.verify()

    assert _row(payload, "fmp.fundamentals_earnings")["status"] == "not_configured"


def test_activation_verifier_accepts_explicit_successful_runtime_and_probe_evidence(
    tmp_path: Path,
) -> None:
    service = ProviderActivationVerifierService(
        env={
            "FMP_API_KEY": "FMP_SECRET_VALUE",
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "true",
            "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": "true",
            "SCANNER_LOCAL_UNIVERSE_PATH": str(tmp_path / "missing-universe.csv"),
        },
        spec_finder=_installed_spec_finder,
        today=date(2026, 6, 27),
        local_checks={
            "akshare_provider_available": True,
            "baostock_provider_available": True,
            "fmp_provider_available": True,
            "yfinance_provider_available": True,
            "historical_ohlcv_latest_date": "2026-06-27",
        },
    )

    payload = service.verify()

    assert _row(payload, "akshare.cn_hk_market_data")["status"] == "available"
    assert _row(payload, "baostock.cn_ohlcv")["status"] == "available"
    assert _row(payload, "fmp.fundamentals_earnings")["status"] == "available"
    assert _row(payload, "yfinance.market_data")["status"] == "available"
    assert _row(payload, "historical_ohlcv.runtime")["status"] == "available"
    assert "FMP_SECRET_VALUE" not in _json_text(payload)


def test_activation_verifier_fails_closed_on_failed_and_unknown_probe_evidence(
    tmp_path: Path,
) -> None:
    service = ProviderActivationVerifierService(
        env={
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "true",
            "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": "true",
            "SCANNER_LOCAL_UNIVERSE_PATH": str(tmp_path / "missing-universe.csv"),
        },
        spec_finder=_installed_spec_finder,
        today=date(2026, 6, 27),
        local_checks={
            "akshare_provider_available": False,
            "baostock_provider_available": "unknown",
            "yfinance_provider_available": None,
        },
    )

    payload = service.verify()

    assert _row(payload, "akshare.cn_hk_market_data")["status"] == "unavailable"
    assert _row(payload, "baostock.cn_ohlcv")["status"] == "unavailable"
    assert _row(payload, "yfinance.market_data")["status"] == "unavailable"
    assert _row(payload, "historical_ohlcv.runtime")["status"] == "unavailable"


def test_activation_verifier_classifies_permission_sample_and_stale_states(tmp_path: Path) -> None:
    stale_universe = tmp_path / "scanner.csv"
    stale_universe.write_text("symbol,name\nORCL,Oracle\n", encoding="utf-8")
    old_mtime = date(2026, 6, 20)
    stale_timestamp = old_mtime.toordinal()

    service = ProviderActivationVerifierService(
        env={
            "FMP_API_KEY": "FMP_SECRET_VALUE",
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "true",
            "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": "true",
            "SCANNER_LOCAL_UNIVERSE_PATH": str(stale_universe),
        },
        spec_finder=_installed_spec_finder,
        today=date(2026, 6, 27),
        file_mtime=lambda path: stale_timestamp if Path(path) == stale_universe else None,
        local_checks={
            "akshare_provider_available": True,
            "baostock_provider_available": True,
            "yfinance_provider_available": True,
            "historical_ohlcv_latest_date": date(2026, 6, 12).isoformat(),
            "earnings_sample_only": True,
        },
    )

    payload = service.verify()

    assert _row(payload, "akshare.cn_hk_market_data")["status"] == "available"
    assert _row(payload, "baostock.cn_ohlcv")["status"] == "available"
    assert _row(payload, "yfinance.market_data")["status"] == "available"
    assert _row(payload, "fmp.fundamentals_earnings")["status"] == "insufficient_permissions"
    assert _row(payload, "historical_ohlcv.runtime")["status"] == "stale"
    historical = _row(payload, "historical_ohlcv.runtime")
    assert historical["reason"] == "historical_ohlcv_stale"
    assert historical["operatorAction"] == historical["adminNextAction"]
    assert historical["consumerSafeMessage"] == "历史行情缓存已过期，需要刷新后再使用相关研究流程。"
    assert _row(payload, "earnings_fundamentals.readiness")["status"] == "sample_only"
    assert _row(payload, "scanner.universe")["status"] == "stale"

    fmp = _row(payload, "fmp.fundamentals_earnings")
    assert "Stock Fundamentals" in fmp["blockedProductSurfaces"]
    assert "Earnings" in fmp["blockedProductSurfaces"]
    assert "permission" in fmp["adminNextAction"].lower()
    assert "FMP_SECRET_VALUE" not in _json_text(payload)


def test_activation_verifier_keeps_provider_failures_isolated(tmp_path: Path) -> None:
    class _Spec:
        pass

    def _spec_finder(name: str):
        if name == "akshare":
            raise RuntimeError("akshare import failed with SECRET_TOKEN")
        if name in {"baostock", "yfinance"}:
            return _Spec()
        return None

    service = ProviderActivationVerifierService(
        env={
            "SCANNER_LOCAL_UNIVERSE_PATH": str(tmp_path / "missing-universe.csv"),
        },
        spec_finder=_spec_finder,
        today=date(2026, 6, 27),
        local_checks={
            "baostock_provider_available": True,
            "yfinance_provider_available": True,
        },
    )

    payload = service.verify()

    assert _row(payload, "akshare.cn_hk_market_data")["status"] == "unavailable"
    assert _row(payload, "baostock.cn_ohlcv")["status"] == "available"
    assert _row(payload, "yfinance.market_data")["status"] == "available"
    assert "SECRET_TOKEN" not in _json_text(payload)


def test_admin_activation_endpoint_requires_provider_read_capability() -> None:
    user_client = _client_for(_regular_user)
    user_response = user_client.get("/api/v1/admin/provider-activation-verifier")
    assert user_response.status_code == 403
    assert user_response.json()["detail"]["error"] == "admin_required"

    no_capability_client = _client_for(_admin_without_provider_read)
    no_capability_response = no_capability_client.get("/api/v1/admin/provider-activation-verifier")
    assert no_capability_response.status_code == 403
    assert no_capability_response.json()["detail"]["error"] == "admin_capability_required"
    assert "ops:providers:read" not in no_capability_response.text

    admin_client = _client_for(_admin_user)
    admin_response = admin_client.get("/api/v1/admin/provider-activation-verifier")
    assert admin_response.status_code == 200
    payload = admin_response.json()
    assert payload["metadata"]["readOnly"] is True
    assert payload["capabilities"]
    for marker in FORBIDDEN_TEXT_MARKERS:
        assert marker.lower() not in admin_response.text.lower()


def test_admin_activation_endpoint_uses_canonical_verifier_path() -> None:
    admin_client = _client_for(_admin_user)
    expected_payload = {
        "contractVersion": "provider_activation_verifier_v1",
        "metadata": {"readOnly": True},
        "capabilities": [],
    }

    with patch.object(
        ProviderActivationVerifierService,
        "verify",
        return_value=expected_payload,
    ) as verify:
        response = admin_client.get("/api/v1/admin/provider-activation-verifier")

    assert response.status_code == 200
    assert response.json() == expected_payload
    assert verify.call_count == 1


def test_provider_activation_verifier_cli_outputs_safe_json() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/provider_activation_verifier.py", "--format", "json"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["contractVersion"] == "provider_activation_verifier_v1"
    assert payload["metadata"]["readOnly"] is True
    assert payload["capabilities"]
    assert completed.stderr == ""
    for marker in FORBIDDEN_TEXT_MARKERS:
        assert marker.lower() not in completed.stdout.lower()
