# -*- coding: utf-8 -*-
"""Contract guards for public AI routing and cost facade boundaries."""

from __future__ import annotations

import ast
import json
import runpy
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from api.v1.endpoints.agent import AgentModelsResponse, AgentProviderHealthResponse
from api.v1.schemas.admin_cost import (
    DuplicateCostSummaryResponse,
    LlmLedgerSummaryResponse,
    QuotaDryRunResponse,
)
from api.v1.schemas.usage import UsageSummaryResponse
from src.config import Config
from src.services.agent_model_service import (
    list_agent_model_deployments,
    list_agent_provider_health,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "ai_routing_cost"
SCANNER_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "scanner"
BACKTEST_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "backtest"
PORTFOLIO_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "portfolio"
FORBIDDEN_PUBLIC_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "completion_text",
    "cookie",
    "headers",
    "input_text",
    "output_text",
    "password",
    "prompt",
    "prompt_content",
    "prompt_text",
    "provider_payload",
    "raw_payload",
    "raw_prompt",
    "raw_provider_payload",
    "raw_response",
    "refresh_token",
    "request_body",
    "response_body",
    "secret",
    "session_id",
    "set-cookie",
    "stack_trace",
    "traceback",
}
FORBIDDEN_PUBLIC_SUBSTRINGS = (
    "authorization:",
    "authorization=",
    "bearer ",
    "cookie=",
    "set-cookie",
    "api_key",
    "raw_prompt",
    "raw_response",
    "provider_payload",
    "traceback (most recent call last)",
)


def _build_config(**overrides: Any) -> Config:
    config = Config(
        litellm_model="gemini/gemini-2.5-flash",
        litellm_fallback_models=["openai/gpt-4o-mini"],
        llm_model_list=[],
        llm_channels=[],
        litellm_config_path=None,
        llm_models_source="legacy_env",
        openai_base_url=None,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fixture(name: str) -> dict[str, Any]:
    return _load_json(FIXTURE_ROOT / name)


def _iter_public_strings(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _iter_public_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_public_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_public_payload_is_sanitized(value: Any, *, in_redaction: bool = False) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            assert str(key).strip().lower() not in FORBIDDEN_PUBLIC_KEYS
            _assert_public_payload_is_sanitized(
                item,
                in_redaction=in_redaction or str(key).strip().lower() == "redaction",
            )
        return
    if isinstance(value, list):
        for item in value:
            _assert_public_payload_is_sanitized(item, in_redaction=in_redaction)
        return
    if isinstance(value, str) and not in_redaction:
        lowered = value.lower()
        for forbidden in FORBIDDEN_PUBLIC_SUBSTRINGS:
            assert forbidden not in lowered


def _assert_round_trip_matches_fixture(model_cls: Any, fixture_name: str, *, by_alias: bool) -> dict[str, Any]:
    payload = _load_fixture(fixture_name)
    actual = model_cls.model_validate(payload).model_dump(by_alias=by_alias)
    assert actual == payload
    _assert_public_payload_is_sanitized(actual)
    return actual


def _get_by_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        assert isinstance(current, Mapping), f"path is not a mapping at {part}: {path}"
        current = current[part]
    return current


def _load_backend_boundary_inventory() -> dict[str, Any]:
    return runpy.run_path(str(REPO_ROOT / "tests" / "test_backend_modular_import_boundaries.py"))


def _collect_imported_modules(relative_path: str) -> set[str]:
    source_path = REPO_ROOT / relative_path
    module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_agent_models_response_matches_sanitized_public_fixture() -> None:
    fixture = _load_fixture("agent_models_response.json")
    config = _build_config(
        llm_channels=[{"name": "primary"}, {"name": "fallback"}],
        llm_models_source="llm_channels",
        llm_model_list=[
            {
                "model_name": "openai/gpt-4o-mini",
                "litellm_params": {
                    "model": "openai/gpt-4o-mini",
                    "api_key": "secret-openai",
                    "api_base": "https://api.openai.example/v1",
                },
            },
            {
                "model_name": "gemini/gemini-2.5-flash",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "api_key": "secret-gemini",
                },
            },
        ],
    )

    actual = AgentModelsResponse(
        models=list_agent_model_deployments(config)
    ).model_dump()

    assert actual == fixture
    assert [item["model"] for item in actual["models"]] == [
        "gemini/gemini-2.5-flash",
        "openai/gpt-4o-mini",
    ]
    assert actual["models"][0]["is_primary"] is True
    assert actual["models"][1]["is_fallback"] is True
    _assert_public_payload_is_sanitized(actual)


def test_agent_provider_health_matches_sanitized_public_fixture() -> None:
    fixture = _load_fixture("agent_provider_health_response.json")
    config = _build_config(
        agent_mode=True,
        _agent_mode_explicit=True,
        litellm_model="deepseek/deepseek-chat",
        litellm_fallback_models=["openai/gpt-4o-mini"],
        deepseek_api_keys=["sk-deepseek-secret"],
        openai_api_keys=[],
        gemini_api_keys=[],
        llm_model_list=[
            {
                "model_name": "__legacy_deepseek__",
                "litellm_params": {
                    "model": "__legacy_deepseek__",
                    "api_key": "sk-deepseek-secret",
                },
            }
        ],
    )

    actual = AgentProviderHealthResponse(
        **list_agent_provider_health(config)
    ).model_dump(by_alias=True)

    assert actual == fixture
    assert actual["routingMode"] == "AUTO"
    assert actual["currentProvider"] == "DeepSeek"
    assert actual["providers"][0]["selected"] is True
    assert actual["providers"][0]["status"] == "available"
    _assert_public_payload_is_sanitized(actual)


def test_quota_dry_run_response_fixture_matches_public_contract() -> None:
    payload = _assert_round_trip_matches_fixture(
        QuotaDryRunResponse,
        "quota_dry_run_response.json",
        by_alias=True,
    )

    assert payload["allowed"] is True
    assert payload["wouldBlock"] is False
    assert payload["routeFamily"] == "analysis"
    assert payload["metadata"]["quotaDecisionMode"] == "advisory"
    assert payload["metadata"]["noExternalCalls"] is True
    assert payload["metadata"]["operatorReview"]["realOutboundNotification"] is False


def test_llm_ledger_summary_response_fixture_matches_public_contract() -> None:
    payload = _assert_round_trip_matches_fixture(
        LlmLedgerSummaryResponse,
        "llm_ledger_summary_response.json",
        by_alias=True,
    )

    assert payload["total"]["totalTokens"] == 2800
    assert payload["metadata"]["readOnly"] is True
    assert payload["metadata"]["noExternalCalls"] is True
    assert payload["byProviderModel"][0]["dimensions"] == {
        "provider": "openai",
        "model": "gpt-4o-mini",
    }


def test_usage_summary_response_fixture_matches_public_contract() -> None:
    payload = _assert_round_trip_matches_fixture(
        UsageSummaryResponse,
        "usage_summary_response.json",
        by_alias=False,
    )

    assert payload["period"] == "month"
    assert payload["total_calls"] == 7
    assert payload["by_call_type"][0]["call_type"] == "analysis"
    assert payload["by_model"][0]["model"] == "openai/gpt-4o-mini"


def test_duplicate_cost_summary_response_fixture_matches_public_contract() -> None:
    payload = _assert_round_trip_matches_fixture(
        DuplicateCostSummaryResponse,
        "duplicate_cost_summary_response.json",
        by_alias=True,
    )

    assert payload["metadata"]["readOnly"] is True
    assert payload["metadata"]["noExternalCalls"] is True
    assert payload["summary"]["scannerAiCompleted"] == 1
    assert payload["scannerAi"]["skips"][0]["eventCounts"]["skipped_by_budget"] == 1
    assert payload["providers"]["cacheEfficiency"][0]["hitRate"] == 0.6667


def test_optional_ai_enrichment_stays_additive_across_domains() -> None:
    boundary = _load_fixture("optional_enrichment_boundary.json")
    scanner_candidate = _load_json(SCANNER_FIXTURE_ROOT / "scanner_candidate_dto.json")
    scanner_run = _load_json(SCANNER_FIXTURE_ROOT / "scanner_run_summary_dto.json")
    backtest_summary = _load_json(BACKTEST_FIXTURE_ROOT / "rule_backtest_result_summary_dto.json")
    portfolio_snapshot = _load_json(PORTFOLIO_FIXTURE_ROOT / "portfolio_snapshot_read_model_dto.json")

    for field_name in boundary["scanner"]["authoritativeFields"]:
        assert field_name in scanner_candidate
    scanner_ai_payload = _get_by_path(scanner_candidate, boundary["scanner"]["additiveAiPath"])
    assert scanner_ai_payload["available"] is True
    assert scanner_ai_payload["status"] == "generated"
    for field_name in boundary["scanner"]["forbiddenAiAuthorityFields"]:
        assert field_name not in scanner_ai_payload
    assert "AI interpretation is additive" in scanner_run["scoring_notes"][1]

    for field_name in boundary["backtest"]["authoritativeFields"]:
        assert field_name in backtest_summary
    for field_name in boundary["backtest"]["forbiddenAiAuthorityFields"]:
        assert field_name not in backtest_summary

    for field_name in boundary["portfolio"]["authoritativeFields"]:
        assert field_name in portfolio_snapshot
    for field_name in boundary["portfolio"]["forbiddenAiAuthorityFields"]:
        assert field_name not in portfolio_snapshot


def test_ai_routing_cost_domain_inventory_remains_explicit() -> None:
    inventory = _load_backend_boundary_inventory()
    ai_domain = inventory["ARCHITECTURE_DOMAIN_CLASSIFICATIONS"]["AI routing / cost"]

    assert {
        "src.services.agent_model_service",
        "src.services.duplicate_cost_summary_service",
        "src.services.llm_cost_ledger_service",
        "src.services.litellm_runtime",
        "src.services.llm_instrumentation",
        "src.services.research_budget_profiles",
    }.issubset(ai_domain)

    runtime_heavy = inventory["EXPECTED_RUNTIME_HEAVY_DOMAIN_CLASSIFICATIONS"]
    assert runtime_heavy["src.services.litellm_runtime"] == "AI routing / cost"
    assert runtime_heavy["src.services.llm_cost_ledger_service"] == "AI routing / cost"
    assert runtime_heavy["src.services.llm_instrumentation"] == "AI routing / cost"

    helper_modules = {
        case["module_name"]
        for case in inventory["LLM_HELPER_IMPORT_GUARD_CASES"]
    }
    assert helper_modules == {
        "src.services.llm_instrumentation",
        "src.services.litellm_runtime",
    }


def test_public_ai_cost_endpoints_avoid_runtime_internal_imports() -> None:
    boundary = _load_fixture("optional_enrichment_boundary.json")["facadeDiscipline"]
    forbidden_prefixes = tuple(boundary["forbiddenInternalRuntimeImports"])

    for relative_path in boundary["endpointFiles"]:
        imported_modules = _collect_imported_modules(relative_path)
        for forbidden_prefix in forbidden_prefixes:
            assert not any(
                name == forbidden_prefix or name.startswith(forbidden_prefix + ".")
                for name in imported_modules
            ), f"{relative_path} imports forbidden runtime internal {forbidden_prefix}"

    agent_imports = _collect_imported_modules("api/v1/endpoints/agent.py")
    admin_cost_imports = _collect_imported_modules("api/v1/endpoints/admin_cost.py")
    usage_imports = _collect_imported_modules("api/v1/endpoints/usage.py")

    assert "src.services.agent_model_service" in agent_imports
    assert "src.services.llm_cost_ledger_service" in admin_cost_imports
    assert "src.services.quota_policy_service" in admin_cost_imports
    assert "src.services.litellm_runtime" not in usage_imports


def test_ai_routing_cost_fixtures_are_sanitized() -> None:
    fixture_paths = sorted(FIXTURE_ROOT.glob("*.json"))

    assert {path.name for path in fixture_paths} == {
        "agent_models_response.json",
        "agent_provider_health_response.json",
        "duplicate_cost_summary_response.json",
        "llm_ledger_summary_response.json",
        "optional_enrichment_boundary.json",
        "quota_dry_run_response.json",
        "usage_summary_response.json",
    }
    for path in fixture_paths:
        _assert_public_payload_is_sanitized(_load_json(path))
