# -*- coding: utf-8 -*-
"""Golden fixture contract tests for admin observability read models and boundaries."""

from __future__ import annotations

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
