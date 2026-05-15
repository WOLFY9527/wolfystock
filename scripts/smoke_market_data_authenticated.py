#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local authenticated market data smoke using an in-process FastAPI TestClient.

The script never requires a real password, cookie copy/paste, or external curl
session handling. It uses a temporary isolated database path, a mock current
user for authenticated route probes, and bounded JSON output that excludes
provider payloads, headers, cookies, secrets, and stack traces.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.auth as auth
from api.deps import CurrentUser, get_current_user, get_optional_current_user
from api.middlewares.auth import add_auth_middleware
from api.v1 import api_v1_router
from src.config import Config
from src.storage import DatabaseManager

EXIT_OK = 0
EXIT_FAILED = 1
SMOKE_VERSION = "auth-market-smoke-v1"
PRIME_IP = "198.51.100.10"

MARKET_ROUTES: tuple[str, ...] = (
    "/api/v1/market/rates",
    "/api/v1/market/temperature",
    "/api/v1/market/liquidity-monitor",
    "/api/v1/market/fx-commodities",
    "/api/v1/market-overview/macro",
)

FALLBACK_SOURCES = {"fallback", "mock", "unavailable", "error"}
FRESHNESS_CLASSES = {"live", "cached", "delayed", "stale", "fallback", "mock", "error", "unavailable"}


class _NoOpExecutionLogService:
    def record_market_overview_fetch(self, **_: Any) -> str:
        return "market-smoke-noop"


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


def _reset_runtime_singletons() -> None:
    Config.reset_instance()
    DatabaseManager.reset_instance()
    _reset_auth_globals()


def _mock_user() -> CurrentUser:
    return CurrentUser(
        user_id="smoke-user",
        username="smoke-user",
        display_name="Smoke User",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="smoke-session",
    )


def _safe_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_freshness(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in FRESHNESS_CLASSES:
        return normalized
    return "unknown"


def _payload_freshness(payload: dict[str, Any]) -> str:
    freshness = payload.get("freshness")
    if isinstance(freshness, dict):
        return _normalize_freshness(freshness.get("status"))
    return _normalize_freshness(freshness)


def _payload_fallback(payload: dict[str, Any], freshness_class: str) -> bool:
    source = str(payload.get("source") or "").strip().lower()
    return bool(
        payload.get("isFallback")
        or payload.get("fallbackUsed")
        or freshness_class in {"fallback", "mock", "error", "unavailable"}
        or source in FALLBACK_SOURCES
    )


def _liquidity_partial(payload: dict[str, Any]) -> bool:
    indicators = payload.get("indicators")
    if not isinstance(indicators, list):
        return False
    return any(str(item.get("status") or "").strip().lower() == "partial" for item in indicators if isinstance(item, dict))


def _payload_partial(payload: dict[str, Any], is_fallback: bool) -> bool:
    source = str(payload.get("source") or "").strip().lower()
    provider_health = payload.get("providerHealth")
    provider_status = ""
    if isinstance(provider_health, dict):
        provider_status = str(provider_health.get("status") or "").strip().lower()
    if source == "mixed" or provider_status == "partial":
        return True
    if is_fallback:
        return False
    return bool(payload.get("fallbackUsed"))


def _source_class_from_payload(route: str, payload: dict[str, Any], freshness_class: str, is_fallback: bool) -> str:
    if route == "/api/v1/market/liquidity-monitor":
        metadata = payload.get("sourceMetadata")
        external_calls = bool(metadata.get("externalProviderCalls")) if isinstance(metadata, dict) else False
        if is_fallback:
            return "fallback"
        if _liquidity_partial(payload):
            return "aggregated_partial"
        return "aggregated_external" if external_calls else "aggregated_cached"

    source = str(payload.get("source") or "").strip().lower()
    source_type = str(payload.get("sourceType") or "").strip().lower()
    provider_health = payload.get("providerHealth")
    provider_status = ""
    if isinstance(provider_health, dict):
        provider_status = str(provider_health.get("status") or "").strip().lower()

    if source == "mixed" or provider_status == "partial":
        return "mixed"
    if is_fallback:
        return "fallback"
    if source_type in {"official_public", "unofficial_proxy", "public_api", "computed", "computed_from_fallback"}:
        return source_type
    if source == "computed":
        return "computed"
    if source in {"cached", "snapshot"}:
        return "cached_snapshot"
    if "proxy" in source or "proxy" in source_type:
        return "unofficial_proxy"
    return "other"


def summarize_route_result(route: str, mode: str, status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    if mode == "unauthenticated":
        source_class = {
            401: "auth_guard_401",
            403: "auth_guard_403",
            429: "rate_limited_429",
        }.get(int(status_code), "http_error")
        return {
            "mode": mode,
            "route": route,
            "httpStatus": int(status_code),
            "sourceClass": source_class,
            "freshnessClass": "not_applicable",
            "fallback": False,
            "partial": False,
        }

    freshness_class = _payload_freshness(payload)
    is_fallback = _payload_fallback(payload, freshness_class)
    return {
        "mode": mode,
        "route": route,
        "httpStatus": int(status_code),
        "sourceClass": _source_class_from_payload(route, payload, freshness_class, is_fallback),
        "freshnessClass": freshness_class,
        "fallback": is_fallback,
        "partial": _liquidity_partial(payload) if route == "/api/v1/market/liquidity-monitor" else _payload_partial(payload, is_fallback),
    }


def probe_routes(client: Any, routes: tuple[str, ...], *, mode: str, headers: dict[str, str] | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for route in routes:
        response = client.request("GET", route, headers=headers or {})
        records.append(summarize_route_result(route, mode, int(response.status_code), _safe_json(response)))
    return records


def _prime_public_failure_bucket(client: TestClient) -> None:
    client.post(
        "/api/v1/options/decision/evaluate",
        content='{"symbol":"TEM"',
        headers={
            "content-type": "application/json",
            "X-Forwarded-For": PRIME_IP,
        },
    )


@contextmanager
def _smoke_client() -> Iterator[TestClient]:
    _reset_runtime_singletons()
    with tempfile.TemporaryDirectory(prefix="auth-market-smoke-") as temp_dir:
        root = Path(temp_dir)
        env_path = root / ".env"
        db_path = root / "auth-market-smoke.sqlite"
        env_path.write_text(
            "\n".join(
                (
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={db_path}",
                    "TRUST_X_FORWARDED_FOR=true",
                    "PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES=1",
                    "PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS=300",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        env_overrides = {
            "ENV_FILE": str(env_path),
            "DATABASE_PATH": str(db_path),
            "ADMIN_AUTH_ENABLED": "true",
            "TRUST_X_FORWARDED_FOR": "true",
            "PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES": "1",
            "PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS": "300",
        }
        with patch.dict(os.environ, env_overrides, clear=False):
            _reset_runtime_singletons()
            app = FastAPI()
            add_auth_middleware(app)
            app.include_router(api_v1_router)
            with TestClient(app, raise_server_exceptions=False) as client:
                yield client
            _reset_runtime_singletons()


def run_smoke(*, include_unauthenticated: bool = False) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    mock_user = _mock_user()
    with _smoke_client() as client:
        if include_unauthenticated:
            _prime_public_failure_bucket(client)
            records.extend(
                probe_routes(
                    client,
                    MARKET_ROUTES,
                    mode="unauthenticated",
                    headers={"X-Forwarded-For": PRIME_IP},
                )
            )

        with patch("api.middlewares.auth.resolve_current_user", lambda _request: mock_user), patch(
            "src.services.market_overview_service.ExecutionLogService",
            _NoOpExecutionLogService,
        ):
            client.app.dependency_overrides[get_optional_current_user] = lambda: mock_user
            client.app.dependency_overrides[get_current_user] = lambda: mock_user
            records.extend(probe_routes(client, MARKET_ROUTES, mode="authenticated"))
            client.app.dependency_overrides.clear()
    return records


def _all_checks_pass(records: list[dict[str, Any]]) -> bool:
    for item in records:
        mode = str(item.get("mode") or "")
        status_code = int(item.get("httpStatus") or 0)
        if mode == "authenticated" and status_code != 200:
            return False
        if mode == "unauthenticated" and status_code != 401:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke authenticated market data routes without real cookies or secret output.")
    parser.add_argument(
        "--include-unauthenticated",
        action="store_true",
        help="Also verify the same routes fail closed with 401 instead of 429 under a hot public-abuse bucket.",
    )
    args = parser.parse_args(argv)

    records = run_smoke(include_unauthenticated=bool(args.include_unauthenticated))
    json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return EXIT_OK if _all_checks_pass(records) else EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
