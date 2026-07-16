"""Collect the deterministic T457 W1 protected-semantics characterization."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MATRIX_PATH = ROOT / "tests" / "golden" / "protected_semantics.v1.json"
REQUIRED_CASE_IDS = (
    "absence-vs-observed-zero",
    "operational-vs-observation-time",
    "broker-currency-and-fx-evidence",
    "startup-failure-vs-static-degradation",
    "frontend-contract-vs-placeholder",
    "stored-json-corruption-vs-empty-object",
    "retryable-vs-terminal-failure",
)


def load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("protected semantics matrix must be an object")
    return payload


def _absence_vs_observed_zero() -> dict[str, Any]:
    from api.v1.endpoints.portfolio import _portfolio_count_observation
    from data_provider.realtime_types import safe_float

    def count(value: Any, data_status: str, count_kind: str) -> dict[str, Any]:
        observed, state = _portfolio_count_observation(
            value,
            data_status=data_status,
            count_kind=count_kind,
        )
        return {"value": observed, "state": state}

    return {
        "missingReady": count(None, "ready", "position"),
        "missingUnavailable": count(None, "provider_unavailable", "position"),
        "unprovenZero": count(0, "ready", "position"),
        "observedZero": count(0, "no_positions", "position"),
        "observedPositive": count(2, "ready", "position"),
        "numeric": {
            "missing": safe_float(None),
            "empty": safe_float(""),
            "zero": safe_float(0),
            "neutral": safe_float("0"),
        },
    }


def _operational_vs_observation_time() -> dict[str, Any]:
    from data_provider.realtime_types import market_index_metadata
    from src.providers.types import ProviderReason, ProviderResult
    from src.services.history_service import HistoryService
    from src.services.market_persistence_snapshot_store import normalize_persistence_snapshot

    attempted_at = datetime(2026, 7, 16, 1, 29, tzinfo=timezone.utc)
    generated_at = "2026-07-16T01:30:00+00:00"
    observed_at = "2026-07-16T01:28:00+00:00"
    as_of = "2026-07-16T01:27:00+00:00"
    cached_at = "2026-07-16T01:31:00+00:00"
    persisted_at = "2026-07-16T01:32:00+00:00"

    attempt = ProviderResult.failed(
        "fixture-provider",
        "quote",
        ProviderReason.TIMEOUT,
        startedAt=attempted_at,
    ).to_dict()
    time_contract = HistoryService._extract_time_contract(
        {
            "enhanced_context": {
                "market_timestamp": observed_at,
                "report_generated_at": generated_at,
                "session_type": "intraday_snapshot",
            }
        }
    )
    persistence = normalize_persistence_snapshot(
        {
            "surface": "market_overview",
            "metricKey": "fixture_metric",
            "source": "fixture_cache",
            "sourceType": "cache_snapshot",
            "sourceTier": "cache_snapshot",
            "freshness": "cached",
            "asOf": as_of,
            "updatedAt": cached_at,
            "snapshotCreatedAt": persisted_at,
        }
    )
    observation = market_index_metadata(
        {
            "source": "fixture-provider",
            "observedAt": observed_at,
            "asOf": as_of,
        }
    )
    return {
        "attemptedAt": attempt["startedAt"],
        "generatedAt": time_contract["report_generated_at"],
        "cachedAt": persistence.updated_at,
        "persistedAt": persistence.snapshot_created_at,
        "observedAt": observation["observed_at"],
        "asOf": observation["as_of"],
        "effectiveTimestamp": persistence.effective_timestamp.isoformat(),
        "createdTimestamp": persistence.created_timestamp.isoformat(),
    }


def _broker_currency_and_fx_evidence() -> dict[str, Any]:
    import pandas as pd

    from api.v1.schemas.portfolio import PortfolioLiveFxRateResponse
    from src.services.portfolio_import_service import PortfolioImportService

    parser = SimpleNamespace(column_hints={})
    base_row = {
        "成交日期": "2026-07-16",
        "证券代码": "AAPL",
        "买卖方向": "buy",
        "成交数量": "1",
        "成交价格": "200",
    }
    service = PortfolioImportService.__new__(PortfolioImportService)
    unknown = service._normalize_trade_row(row=pd.Series(base_row), parser_spec=parser)
    explicit_usd = service._normalize_trade_row(
        row=pd.Series({**base_row, "币种": "USD"}),
        parser_spec=parser,
    )
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "portfolio" / "portfolio_cash_fx_dto.json").read_text(
            encoding="utf-8"
        )
    )
    fx = PortfolioLiveFxRateResponse(**fixture["live_fx_rate"]).model_dump()
    return {
        "unknownBrokerCurrency": unknown["currency"],
        "explicitBrokerCurrency": explicit_usd["currency"],
        "fxEvidence": {
            "baseCurrency": fx["base_currency"],
            "quoteCurrency": fx["quote_currency"],
            "rate": fx["rate"],
            "provider": fx["provider"],
            "fetchedAt": fx["fetched_at"],
            "cacheHit": fx["cache_hit"],
            "stale": fx["stale"],
            "error": fx["error"],
        },
    }


def _startup_failure_vs_static_degradation() -> dict[str, Any]:
    from api.app import create_app

    missing_static = ROOT / "tests" / "golden" / "missing-static-fixture"
    with patch.dict(
        os.environ,
        {"APP_ENV": "development", "CORS_ALLOW_ALL": "false", "CORS_ORIGINS": ""},
        clear=False,
    ):
        degraded_app = create_app(static_dir=missing_static)

    failure_type = None
    failure_message = None
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "CORS_ALLOW_ALL": "true",
            "CORS_ORIGINS": "https://public.example.test",
        },
        clear=False,
    ):
        try:
            create_app(static_dir=missing_static)
        except RuntimeError as exc:
            failure_type = type(exc).__name__
            failure_message = str(exc)

    return {
        "staticAssetDegradation": {
            "appCreated": degraded_app is not None,
            "frontendStaticMode": degraded_app.state.frontend_static_mode,
        },
        "startupFailure": {
            "type": failure_type,
            "message": failure_message,
        },
    }


def _frontend_contract_vs_placeholder() -> dict[str, Any]:
    from src.services.admin_surface_contract_readiness_service import (
        AdminSurfaceContractReadinessService,
        RouteSnapshot,
    )
    from src.services.homepage_uat_readiness_service import HomepageUatReadinessService

    missing_route = RouteSnapshot("GET", "/missing", False, None, False, "unknown")
    ready_route = RouteSnapshot("GET", "/ready", True, "ReadyResponse", True, "public")
    status = AdminSurfaceContractReadinessService._surface_status
    checklist = HomepageUatReadinessService().build_checklist(as_of="2026-07-16T01:30:00Z")
    placeholder = next(item for item in checklist["cockpitModules"] if item["key"] == "event_impact_map")
    return {
        "missingContract": status(
            primary=missing_route,
            route_status="missing",
            gaps=("primary_route_missing",),
            implementation_status="missing",
        ),
        "readyContract": status(
            primary=ready_route,
            route_status="all_present",
            gaps=(),
            implementation_status="implemented",
        ),
        "plannedPlaceholder": {
            "overallStatus": checklist["status"],
            "evidenceBoundary": placeholder["evidenceBoundary"],
            "serializationReadiness": placeholder["serializationReadiness"],
            "publicDisplayReadiness": placeholder["publicDisplayReadiness"],
            "dataIntegrationReadiness": placeholder["dataIntegrationReadiness"],
        },
    }


def _stored_json_corruption_vs_empty_object() -> dict[str, Any]:
    from src.repositories.quote_ohlcv_snapshot_repository import _json_mapping

    empty = _json_mapping("{}")
    error_type = None
    error_message = None
    try:
        _json_mapping("not-json")
    except ValueError as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
    return {
        "authoritativeEmptyObject": empty,
        "invalidStoredJson": {"type": error_type, "message": error_message},
    }


def _retryable_vs_terminal_failure() -> dict[str, Any]:
    from src.providers.errors import (
        ProviderInvalidPayload,
        ProviderRateLimited,
        ProviderTimeout,
        ProviderUnauthorized,
        normalize_provider_exception,
    )
    from src.providers.types import ProviderReason

    cases = {
        "transient": ProviderTimeout("timed out"),
        "auth": ProviderUnauthorized("unauthorized"),
        "quota": ProviderRateLimited("rate limited"),
        "invalidInput": ProviderInvalidPayload("invalid payload"),
    }
    retryable_reasons = {ProviderReason.TIMEOUT, ProviderReason.PROVIDER_UNHEALTHY}
    return {
        key: {
            "reason": (reason := normalize_provider_exception(exc)).value,
            "retryable": reason in retryable_reasons,
        }
        for key, exc in cases.items()
    }


_COLLECTORS: dict[str, Callable[[], dict[str, Any]]] = {
    "absence-vs-observed-zero": _absence_vs_observed_zero,
    "operational-vs-observation-time": _operational_vs_observation_time,
    "broker-currency-and-fx-evidence": _broker_currency_and_fx_evidence,
    "startup-failure-vs-static-degradation": _startup_failure_vs_static_degradation,
    "frontend-contract-vs-placeholder": _frontend_contract_vs_placeholder,
    "stored-json-corruption-vs-empty-object": _stored_json_corruption_vs_empty_object,
    "retryable-vs-terminal-failure": _retryable_vs_terminal_failure,
}


def collect_case(case_id: str) -> dict[str, Any]:
    try:
        collector = _COLLECTORS[case_id]
    except KeyError as exc:
        raise ValueError(f"unknown protected semantics case: {case_id}") from exc
    return collector()


def collect_matrix() -> dict[str, Any]:
    return {case_id: collect_case(case_id) for case_id in REQUIRED_CASE_IDS}


def main() -> int:
    matrix = load_matrix()
    expected = {case["id"]: case["expected"] for case in matrix["cases"]}
    actual = collect_matrix()
    result = {
        "schemaVersion": matrix.get("schemaVersion"),
        "matchesGolden": actual == expected,
        "cases": actual,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["matchesGolden"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
