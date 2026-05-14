# -*- coding: utf-8 -*-
"""Golden fixture contract tests for admin observability read models and boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from api.v1.schemas.admin_activity import AdminActivityResponse
from api.v1.schemas.admin_cost import DuplicateCostSummaryResponse, LlmLedgerSummaryResponse
from api.v1.schemas.admin_logs import (
    AdminLogStorageSummaryModel,
    BusinessEventDetailModel,
    ExecutionLogSessionDetailModel,
)
from api.v1.schemas.admin_portfolio import (
    AdminPortfolioAccountDetailResponse,
    AdminPortfolioSummaryResponse,
)
from api.v1.schemas.admin_provider_circuits import (
    ProviderCircuitStatesResponse,
    ProviderSlaReadinessResponse,
)
from api.v1.schemas.admin_users import AdminUserDetailResponse, AdminUserListResponse
from api.v1.schemas.market_provider_operations import MarketProviderOperationsResponse


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "admin_observability"
FORBIDDEN_SENSITIVE_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session token",
    "session-token",
    "access_token",
    "refresh_token",
    "api_key",
    "password_hash",
    "passwordhash",
    "request_body",
    "response_body",
    "request headers",
    "response headers",
    "stack_trace",
    "traceback",
    "raw_provider_payload",
    "provider_payload",
    "raw request body",
    "raw response body",
)
FORBIDDEN_OWNERSHIP_TERMS = (
    "scanner scoring",
    "backtest math",
    "portfolio accounting authority",
    "provider fallback owner",
    "auth enforcement owner",
    "ai routing owner",
)


@dataclass(frozen=True)
class _ProviderHealthExamples:
    readiness: ProviderSlaReadinessResponse
    operations: MarketProviderOperationsResponse


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_no_sensitive_terms(value: Any) -> None:
    serialized = "\n".join(_iter_strings(value)).lower()
    for term in FORBIDDEN_SENSITIVE_TERMS:
        assert term not in serialized


def _build_provider_health_examples() -> _ProviderHealthExamples:
    return _ProviderHealthExamples(
        readiness=ProviderSlaReadinessResponse(
            **{
                "generatedAt": "2026-05-14T09:00:00Z",
                "items": [
                    {
                        "provider": "fixture_configured",
                        "providerCategory": "market_data",
                        "routeFamily": "analysis",
                        "observedSince": "2026-05-14T08:00:00Z",
                        "readinessState": "ready",
                        "reasonCode": "configured_runtime_reference",
                        "credentialState": "configured",
                        "credentialContract": {"state": "present", "source": "runtime_facade"},
                        "liveProvidersEnabled": False,
                        "providerEnabled": True,
                        "credentialsPresent": True,
                        "dryRunEnabled": True,
                        "liveHttpCallsEnabled": False,
                        "brokerOrderPathEnabled": False,
                        "portfolioMutationPathEnabled": False,
                        "tradeableData": False,
                        "latencyBucketMs": 120,
                        "latencyState": "healthy",
                        "errorRate": 0.0,
                        "errorState": "healthy",
                        "freshnessSeconds": 25,
                        "freshnessState": "fresh",
                        "recentErrors": [],
                        "trendSummary": {"latestObservationAt": "2026-05-14T08:59:00Z"},
                        "circuitAdvisoryState": "healthy",
                        "circuitStateCandidate": "closed",
                        "liveEnforcement": False,
                        "wouldBlockCall": False,
                        "wouldBlockIfEnforced": False,
                        "enforcementBlockReasonCode": None,
                        "wouldChangeProviderOrder": False,
                        "wouldChangeFallbackBehavior": False,
                        "noExternalCalls": True,
                        "providerBehaviorChanged": False,
                        "marketCacheBehaviorChanged": False,
                    },
                    {
                        "provider": "fixture_missing",
                        "providerCategory": "options",
                        "routeFamily": "options_lab",
                        "observedSince": "2026-05-14T08:00:00Z",
                        "readinessState": "missing_credentials",
                        "reasonCode": "options_provider_credentials_missing",
                        "credentialState": "missing_credentials",
                        "credentialContract": {"state": "missing", "requiredCredentialCount": 1, "configuredCredentialCount": 0},
                        "liveProvidersEnabled": True,
                        "providerEnabled": True,
                        "credentialsPresent": False,
                        "dryRunEnabled": False,
                        "liveHttpCallsEnabled": False,
                        "brokerOrderPathEnabled": False,
                        "portfolioMutationPathEnabled": False,
                        "tradeableData": False,
                        "latencyBucketMs": None,
                        "latencyState": "unknown",
                        "errorRate": None,
                        "errorState": "unknown",
                        "freshnessSeconds": None,
                        "freshnessState": "unknown",
                        "recentErrors": [],
                        "trendSummary": {"latestObservationAt": None},
                        "circuitAdvisoryState": "healthy",
                        "circuitStateCandidate": "closed",
                        "liveEnforcement": False,
                        "wouldBlockCall": False,
                        "wouldBlockIfEnforced": False,
                        "enforcementBlockReasonCode": None,
                        "wouldChangeProviderOrder": False,
                        "wouldChangeFallbackBehavior": False,
                        "noExternalCalls": True,
                        "providerBehaviorChanged": False,
                        "marketCacheBehaviorChanged": False,
                    },
                    {
                        "provider": "fixture_permission_denied",
                        "providerCategory": "market_data",
                        "routeFamily": "analysis",
                        "observedSince": "2026-05-14T08:00:00Z",
                        "readinessState": "sanitized_provider_error",
                        "reasonCode": "provider_403",
                        "credentialState": "configured",
                        "credentialContract": {"state": "present", "configuredCredentialCount": 1},
                        "liveProvidersEnabled": True,
                        "providerEnabled": True,
                        "credentialsPresent": True,
                        "dryRunEnabled": False,
                        "liveHttpCallsEnabled": False,
                        "brokerOrderPathEnabled": False,
                        "portfolioMutationPathEnabled": False,
                        "tradeableData": False,
                        "latencyBucketMs": 180,
                        "latencyState": "healthy",
                        "errorRate": 1.0,
                        "errorState": "failing",
                        "freshnessSeconds": 120,
                        "freshnessState": "stale",
                        "recentErrors": [{"reasonBucket": "provider_403", "countBucket": "1", "latestAt": "2026-05-14T08:58:00Z"}],
                        "trendSummary": {"provider403CountBucket": "1", "latestObservationAt": "2026-05-14T08:58:00Z"},
                        "circuitAdvisoryState": "degraded",
                        "circuitStateCandidate": "disabled_by_operator",
                        "liveEnforcement": False,
                        "wouldBlockCall": False,
                        "wouldBlockIfEnforced": True,
                        "enforcementBlockReasonCode": "provider_403",
                        "wouldChangeProviderOrder": False,
                        "wouldChangeFallbackBehavior": False,
                        "noExternalCalls": True,
                        "providerBehaviorChanged": False,
                        "marketCacheBehaviorChanged": False,
                    },
                    {
                        "provider": "fixture_timeout",
                        "providerCategory": "market_data",
                        "routeFamily": "guest_preview",
                        "observedSince": "2026-05-14T08:00:00Z",
                        "readinessState": "sanitized_provider_error",
                        "reasonCode": "timeout",
                        "credentialState": "configured",
                        "credentialContract": {"state": "present", "configuredCredentialCount": 1},
                        "liveProvidersEnabled": True,
                        "providerEnabled": True,
                        "credentialsPresent": True,
                        "dryRunEnabled": False,
                        "liveHttpCallsEnabled": False,
                        "brokerOrderPathEnabled": False,
                        "portfolioMutationPathEnabled": False,
                        "tradeableData": False,
                        "latencyBucketMs": 2200,
                        "latencyState": "slow",
                        "errorRate": 1.0,
                        "errorState": "failing",
                        "freshnessSeconds": 240,
                        "freshnessState": "stale",
                        "recentErrors": [{"reasonBucket": "timeout", "countBucket": "1", "latestAt": "2026-05-14T08:57:00Z"}],
                        "trendSummary": {"timeoutCountBucket": "1", "latestObservationAt": "2026-05-14T08:57:00Z"},
                        "circuitAdvisoryState": "open_candidate",
                        "circuitStateCandidate": "open",
                        "liveEnforcement": False,
                        "wouldBlockCall": False,
                        "wouldBlockIfEnforced": True,
                        "enforcementBlockReasonCode": "timeout",
                        "wouldChangeProviderOrder": False,
                        "wouldChangeFallbackBehavior": False,
                        "noExternalCalls": True,
                        "providerBehaviorChanged": False,
                        "marketCacheBehaviorChanged": False,
                    },
                ],
                "metadata": {
                    "readOnly": True,
                    "noExternalCalls": True,
                    "liveEnforcement": False,
                    "providerBehaviorChanged": False,
                    "marketCacheBehaviorChanged": False,
                    "dataSources": ["provider_sla_readiness"],
                    "limit": 100,
                    "redaction": ["credential_values_omitted", "payload_content_removed"],
                    "filters": {"routeFamily": "all"},
                },
            }
        ),
        operations=MarketProviderOperationsResponse(
            **{
                "generatedAt": "2026-05-14T09:00:00Z",
                "window": {"key": "24h", "since": "24h"},
                "summary": {
                    "totalItems": 2,
                    "liveCount": 0,
                    "cacheCount": 0,
                    "staleCount": 1,
                    "fallbackCount": 1,
                    "partialCount": 0,
                    "unavailableCount": 0,
                    "errorCount": 0,
                    "refreshingCount": 0,
                    "eventCount": 2,
                    "failureCount": 0,
                    "fallbackEventCount": 1,
                    "staleEventCount": 1,
                    "slowEventCount": 0,
                },
                "items": [
                    {
                        "provider": "fixture_fallback",
                        "sourceLabel": "Cache snapshot",
                        "sourceType": "cache",
                        "domain": "sentiment",
                        "endpoint": "/api/v1/market/sentiment",
                        "card": "MarketSentimentCard",
                        "cacheKey": "sentiment",
                        "status": "fallback",
                        "freshness": "fallback",
                        "asOf": "2026-05-14T08:58:00Z",
                        "updatedAt": "2026-05-14T08:58:00Z",
                        "lastSuccessfulAt": "2026-05-14T08:50:00Z",
                        "lastKnownGoodAgeMinutes": 10,
                        "latencyMs": 1800.0,
                        "isFallback": True,
                        "isStale": False,
                        "isRefreshing": False,
                        "isFromSnapshot": False,
                        "fallbackUsed": True,
                        "warning": "Fallback served within bounded timeout policy.",
                        "errorSummary": "timeout",
                        "adminLogDrillThrough": {
                            "label": "查看 Admin Logs",
                            "route": "/zh/admin/logs",
                            "query": {"since": "24h", "provider": "fixture_fallback", "query": "/api/v1/market/sentiment"},
                            "eventId": "evt-fallback-1",
                        },
                    },
                    {
                        "provider": "fixture_stale_cache",
                        "sourceLabel": "Cache snapshot",
                        "sourceType": "cache",
                        "domain": "quote",
                        "endpoint": "/api/v1/market/quote",
                        "card": "QuoteCard",
                        "cacheKey": "quote",
                        "status": "stale",
                        "freshness": "stale",
                        "asOf": "2026-05-14T08:40:00Z",
                        "updatedAt": "2026-05-14T08:40:00Z",
                        "lastSuccessfulAt": "2026-05-14T08:40:00Z",
                        "lastKnownGoodAgeMinutes": 20,
                        "latencyMs": 40.0,
                        "isFallback": False,
                        "isStale": True,
                        "isRefreshing": False,
                        "isFromSnapshot": True,
                        "fallbackUsed": False,
                        "warning": "Stale cache served within tolerated window.",
                        "errorSummary": None,
                        "adminLogDrillThrough": {
                            "label": "查看 Admin Logs",
                            "route": "/zh/admin/logs",
                            "query": {"since": "24h", "provider": "fixture_stale_cache", "query": "/api/v1/market/quote"},
                            "eventId": "evt-stale-1",
                        },
                    },
                ],
                "eventRollups": [],
                "cacheStates": [
                    {
                        "cacheKey": "sentiment",
                        "ttlSeconds": 60,
                        "fetchedAt": "2026-05-14T08:58:00Z",
                        "expiresAt": "2026-05-14T08:59:00Z",
                        "isFresh": False,
                        "isRefreshing": False,
                        "lastError": "timeout",
                        "persistentSnapshotAvailable": False,
                        "persistentSnapshotAgeMinutes": None,
                        "status": "stale",
                    },
                    {
                        "cacheKey": "quote",
                        "ttlSeconds": 60,
                        "fetchedAt": "2026-05-14T08:40:00Z",
                        "expiresAt": "2026-05-14T08:41:00Z",
                        "isFresh": False,
                        "isRefreshing": False,
                        "lastError": None,
                        "persistentSnapshotAvailable": True,
                        "persistentSnapshotAgeMinutes": 20,
                        "status": "stale",
                    },
                ],
                "limitations": ["bounded_diagnostic_details_only"],
                "adminLogDrillThrough": {
                    "label": "查看 Admin Logs",
                    "route": "/zh/admin/logs",
                    "query": {"since": "24h", "query": "market provider"},
                    "eventId": None,
                },
                "metadata": {
                    "source": "market_cache_and_admin_logs",
                    "readOnly": True,
                    "externalProviderCalls": False,
                    "cacheMutation": False,
                    "providerDiagnostics": {
                        "tickflowCnBreadth": {
                            "provider": "tickflow",
                            "market": "CN_Equity_A",
                            "diagnosticTarget": "cn_breadth",
                            "status": "permission_denied",
                            "credentialState": "configured",
                            "credentialConfigured": True,
                            "reachabilityState": "reachable",
                            "tickflowReachable": True,
                            "breadthEntitlementState": "permission_denied",
                            "breadthEntitlementUsable": False,
                            "reasonCode": "tickflow_permission_unavailable",
                            "observedSource": "fallback",
                            "sourceType": "cache",
                            "summary": "TickFlow key 已配置，但 CN_Equity_A breadth entitlement 当前不可用。",
                        }
                    },
                    "summaryCache": {
                        "enabled": True,
                        "ttlSeconds": 10,
                        "key": "GET:/api/v1/admin/market-providers/operations:v1:24h",
                        "hit": False,
                        "asOf": "2026-05-14T09:00:00Z",
                        "cacheAgeMs": 0,
                    },
                },
            }
        ),
    )


def _provider_health_class(item: Any) -> str:
    credential_state = getattr(item, "credential_state", None)
    if credential_state is not None:
        reason_code = str(getattr(item, "reason_code", "") or "").lower()
        recent_buckets = {str(error.reason_bucket or "").lower() for error in getattr(item, "recent_errors", [])}
        if credential_state == "missing_credentials" or "credentials_missing" in reason_code:
            return "missing credential"
        if "provider_403" in recent_buckets or reason_code == "provider_403":
            return "permission denied"
        if "timeout" in recent_buckets or reason_code == "timeout":
            return "timeout"
        if bool(getattr(item, "credentials_present", False)) and bool(getattr(item, "provider_enabled", False)):
            return "configured"
    if str(getattr(item, "status", "") or "").lower() == "fallback" and bool(getattr(item, "fallbackUsed", False)):
        return "fallback"
    if str(getattr(item, "status", "") or "").lower() == "stale" and (
        bool(getattr(item, "isStale", False)) or bool(getattr(item, "isFromSnapshot", False))
    ):
        return "stale cache"
    raise AssertionError(f"Unclassified provider health item: {item!r}")


def test_admin_logs_read_models_match_public_diagnostic_contracts() -> None:
    payload = _load_fixture("logs_read_models.json")

    AdminLogStorageSummaryModel(**payload["storage_summary"])
    ExecutionLogSessionDetailModel(**payload["session_detail"])
    BusinessEventDetailModel(**payload["event_detail"])

    assert payload["fixture_meta"]["surface"] == "admin_logs"
    assert payload["fixture_meta"]["read_only"] is True
    assert payload["fixture_meta"]["capability_label"] == "ops:logs:read"


def test_admin_cost_read_models_match_public_observability_contracts() -> None:
    payload = _load_fixture("cost_read_models.json")

    DuplicateCostSummaryResponse(**payload["duplicate_summary"])
    LlmLedgerSummaryResponse(**payload["llm_ledger_summary"])

    assert payload["fixture_meta"]["surface"] == "admin_cost_observability"
    assert payload["fixture_meta"]["read_only"] is True
    assert payload["fixture_meta"]["capability_label"] == "cost:observability:read"


def test_admin_provider_observability_read_models_match_public_contracts() -> None:
    payload = _load_fixture("provider_read_models.json")

    ProviderCircuitStatesResponse(**payload["provider_circuit_states"])
    ProviderSlaReadinessResponse(**payload["provider_sla_readiness"])
    MarketProviderOperationsResponse(**payload["market_provider_operations"])

    assert payload["fixture_meta"]["surface"] == "admin_provider_observability"
    assert payload["fixture_meta"]["read_only"] is True


def test_admin_user_activity_and_portfolio_read_models_match_public_contracts() -> None:
    payload = _load_fixture("user_activity_portfolio_read_models.json")

    AdminUserListResponse(**payload["user_list"])
    AdminUserDetailResponse(**payload["user_detail"])
    AdminActivityResponse(**payload["activity"])
    AdminPortfolioSummaryResponse(**payload["portfolio_summary"])
    AdminPortfolioAccountDetailResponse(**payload["portfolio_account_detail"])

    assert payload["fixture_meta"]["surface"] == "admin_user_observability"
    assert payload["fixture_meta"]["read_only"] is True


def test_admin_observability_boundary_fixture_keeps_read_only_and_mutation_ownership_explicit() -> None:
    payload = _load_fixture("mutation_boundary_inventory.json")

    assert {item["surface"] for item in payload["read_only_surfaces"]} >= {
        "admin_logs",
        "admin_cost_observability",
        "admin_provider_observability",
        "admin_user_observability",
        "admin_portfolio_observability",
    }
    assert {item["surface"] for item in payload["mutation_surfaces"]} >= {
        "admin_logs_cleanup",
        "admin_user_security",
        "system_provider_tests",
    }
    assert payload["ownership_boundary"]["admin_observability_role"] == "consumes_domain_contracts_only"


def test_admin_observability_fixtures_stay_sanitized_and_do_not_claim_other_domain_ownership() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert {path.name for path in fixture_paths} == {
        "cost_read_models.json",
        "logs_read_models.json",
        "mutation_boundary_inventory.json",
        "provider_read_models.json",
        "user_activity_portfolio_read_models.json",
    }
    for path in fixture_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        _assert_no_sensitive_terms(payload)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
        for term in FORBIDDEN_OWNERSHIP_TERMS:
            assert term not in serialized


def test_provider_health_public_models_distinguish_required_operator_classes() -> None:
    response = _build_provider_health_examples()

    assert {
        _provider_health_class(item) for item in response.readiness.items
    } == {
        "configured",
        "missing credential",
        "permission denied",
        "timeout",
    }
    assert {
        _provider_health_class(item) for item in response.operations.items
    } == {
        "fallback",
        "stale cache",
    }


def test_market_provider_operations_contract_can_carry_tickflow_entitlement_projection() -> None:
    response = _build_provider_health_examples()

    projection = response.operations.metadata["providerDiagnostics"]["tickflowCnBreadth"]

    assert projection["credentialState"] == "configured"
    assert projection["status"] == "permission_denied"
    assert projection["reachabilityState"] == "reachable"
    assert projection["breadthEntitlementState"] == "permission_denied"
    assert projection["breadthEntitlementUsable"] is False


def test_provider_health_public_models_remain_read_only_sanitized_and_query_only() -> None:
    response = _build_provider_health_examples()
    readiness_payload = response.readiness.model_dump(by_alias=True)
    operations_payload = response.operations.model_dump()

    assert response.readiness.metadata.read_only is True
    assert response.readiness.metadata.no_external_calls is True
    assert response.readiness.metadata.provider_behavior_changed is False
    assert response.readiness.metadata.market_cache_behavior_changed is False
    assert operations_payload["metadata"]["readOnly"] is True
    assert operations_payload["metadata"]["externalProviderCalls"] is False
    assert operations_payload["metadata"]["cacheMutation"] is False

    _assert_no_sensitive_terms(readiness_payload)
    _assert_no_sensitive_terms(operations_payload)
    for drill in [operations_payload["adminLogDrillThrough"], *(item["adminLogDrillThrough"] for item in operations_payload["items"])]:
        assert drill["route"] == "/zh/admin/logs"
        assert set(drill["query"]).issubset({"since", "category", "provider", "query"})
        assert "mode" not in drill["query"]
        assert "dryRun" not in drill["query"]
        assert "cleanup" not in str(drill).lower()
