# -*- coding: utf-8 -*-
"""Offline contracts for research budget profiles."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from src.services.analysis_provider_planner import (
    DataCategory,
    apply_research_budget_profile,
    build_fast_decision_provider_plan,
)
from src.services.research_budget_profiles import (
    ResearchMode,
    describe_research_budget_profiles,
    get_research_budget_profile,
    normalize_research_mode,
)


def test_research_budget_profiles_define_expected_modes_and_budget_posture() -> None:
    quick = get_research_budget_profile("quick")
    standard = get_research_budget_profile(ResearchMode.STANDARD)
    deep = get_research_budget_profile("deep")

    assert quick.mode is ResearchMode.QUICK
    assert standard.mode is ResearchMode.STANDARD
    assert deep.mode is ResearchMode.DEEP
    assert quick.optional_deadline_seconds < standard.optional_deadline_seconds < deep.optional_deadline_seconds
    assert quick.max_external_provider_calls < standard.max_external_provider_calls <= deep.max_external_provider_calls
    assert quick.allow_deep_news is False
    assert quick.allow_social_sentiment is False
    assert quick.allow_expensive_fundamentals is False
    assert standard.cache_first_required is True
    assert deep.allow_expensive_fundamentals is True


def test_research_mode_normalization_is_sanitized_and_strict_errors_do_not_echo_raw_input() -> None:
    assert normalize_research_mode(" FAST ") is ResearchMode.QUICK
    assert normalize_research_mode("balanced") is ResearchMode.STANDARD
    assert normalize_research_mode("research") is ResearchMode.DEEP
    assert normalize_research_mode("not-a-mode token=SECRET") is ResearchMode.STANDARD

    with pytest.raises(ValueError) as exc:
        normalize_research_mode("not-a-mode token=SECRET", strict=True)

    assert "unsupported research mode" in str(exc.value)
    assert "SECRET" not in str(exc.value)
    assert "not-a-mode" not in str(exc.value)


def test_describe_research_budget_profiles_is_public_and_sanitized() -> None:
    description = describe_research_budget_profiles()

    assert set(description) == {"quick", "standard", "deep"}
    assert description["quick"]["researchMode"] == "quick"
    assert description["standard"]["cacheFirstRequired"] is True
    assert "operatorDescription" in description["deep"]
    assert "api_key" not in json.dumps(description).lower()
    assert "token" not in json.dumps(description).lower()
    assert "secret" not in json.dumps(description).lower()


def test_no_mode_fast_decision_plan_preserves_existing_behavior() -> None:
    plan = build_fast_decision_provider_plan(
        "ORCL",
        market="us",
        categories=[DataCategory.QUOTE, DataCategory.FUNDAMENTALS, DataCategory.NEWS],
    )

    budgeted, metadata = apply_research_budget_profile(
        plan,
        research_mode=None,
        required_categories={DataCategory.QUOTE},
    )

    assert budgeted == plan
    assert metadata == {}


def test_quick_mode_caps_optional_categories_without_skipping_required_quote() -> None:
    plan = build_fast_decision_provider_plan(
        "ORCL",
        market="us",
        categories=[
            DataCategory.QUOTE,
            DataCategory.FUNDAMENTALS,
            DataCategory.EARNINGS,
            DataCategory.NEWS,
            DataCategory.SENTIMENT,
        ],
    )

    budgeted, metadata = apply_research_budget_profile(
        plan,
        research_mode="quick",
        required_categories={DataCategory.QUOTE},
    )

    assert budgeted.categories[DataCategory.QUOTE] == plan.categories[DataCategory.QUOTE]
    assert budgeted.categories[DataCategory.FUNDAMENTALS].max_attempts == 1
    assert budgeted.categories[DataCategory.EARNINGS].max_attempts == 1
    assert DataCategory.NEWS not in budgeted.categories
    assert DataCategory.SENTIMENT not in budgeted.categories
    assert metadata["researchMode"] == "quick"
    assert metadata["optionalDeadlineSeconds"] == get_research_budget_profile("quick").optional_deadline_seconds
    assert {item["category"] for item in metadata["skippedByBudget"]} == {"news", "sentiment"}
    assert metadata["externalCallBudget"]["requiredCategoriesExcluded"] == ["quote"]
    assert "SECRET" not in json.dumps(metadata)


def test_standard_and_deep_profiles_keep_optional_enrichment_budgeted_but_distinct() -> None:
    plan = build_fast_decision_provider_plan(
        "ORCL",
        market="us",
        categories=[DataCategory.FUNDAMENTALS, DataCategory.NEWS, DataCategory.SENTIMENT],
    )

    standard_plan, standard_metadata = apply_research_budget_profile(plan, research_mode="standard")
    deep_plan, deep_metadata = apply_research_budget_profile(plan, research_mode="deep")

    assert DataCategory.NEWS in standard_plan.categories
    assert DataCategory.SENTIMENT in standard_plan.categories
    assert DataCategory.NEWS in deep_plan.categories
    assert DataCategory.SENTIMENT in deep_plan.categories
    assert standard_metadata["optionalDeadlineSeconds"] < deep_metadata["optionalDeadlineSeconds"]
    assert standard_metadata["researchMode"] == "standard"
    assert deep_metadata["researchMode"] == "deep"


def test_research_budget_profile_import_does_not_import_live_provider_clients() -> None:
    script = """
import json
import src.services.research_budget_profiles
blocked = [
    "data_provider.alpaca_fetcher",
    "data_provider.twelve_data_fetcher",
    "data_provider.alphavantage_provider",
    "data_provider.us_fundamentals_provider",
    "data_provider.yfinance_fetcher",
    "src.services.market_cache",
    "src.core.pipeline",
]
print(json.dumps({name: name in __import__("sys").modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
