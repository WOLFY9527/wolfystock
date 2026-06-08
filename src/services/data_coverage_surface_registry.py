# -*- coding: utf-8 -*-
"""Inert surface registry for Data Coverage Matrix v1 adoption planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


DATA_COVERAGE_SURFACE_REGISTRY_VERSION: Final[str] = "data_coverage_surface_registry_v1"


class SurfaceAudience(str, Enum):
    CONSUMER = "consumer"
    ADMIN = "admin"
    SHARED = "shared"


class ConsumerVisibilityIntent(str, Enum):
    SAFE_PRODUCT_STATUS_ONLY = "safe_product_status_only"
    OBSERVATION_ONLY_SUMMARY = "observation_only_summary"


class AdminVisibilityIntent(str, Enum):
    NONE = "none"
    GATED_DIAGNOSTIC_METADATA_ALLOWED = "gated_diagnostic_metadata_allowed"


@dataclass(frozen=True, slots=True)
class SurfaceRegistryEntry:
    surface_id: str
    route_id: str
    audience: SurfaceAudience
    field_key: str
    evidence_family: str
    required_posture_notes: tuple[str, ...]
    consumer_visibility_intent: ConsumerVisibilityIntent
    admin_visibility_intent: AdminVisibilityIntent


DATA_COVERAGE_SURFACE_REGISTRY: Final[tuple[SurfaceRegistryEntry, ...]] = (
    SurfaceRegistryEntry(
        surface_id="market_overview",
        route_id="/zh/market-overview",
        audience=SurfaceAudience.CONSUMER,
        field_key="market_regime",
        evidence_family="market_regime",
        required_posture_notes=(
            "static_registry_only",
            "observation_only_until_separate_authority_review",
            "consumer_projection_must_hide_provider_diagnostics",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="liquidity",
        route_id="/zh/market/liquidity-monitor",
        audience=SurfaceAudience.CONSUMER,
        field_key="liquidity_score_status",
        evidence_family="liquidity_monitor",
        required_posture_notes=(
            "static_registry_only",
            "do_not_grant_score_authority_from_coverage_or_freshness",
            "consumer_projection_must_remain_product_state_only",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="rotation",
        route_id="/zh/market/rotation-radar",
        audience=SurfaceAudience.CONSUMER,
        field_key="rotation_score_status",
        evidence_family="rotation_signal",
        required_posture_notes=(
            "static_registry_only",
            "do_not_grant_rotation_stage_or_rank_authority_from_source_labels",
            "consumer_projection_must_hide_provider_and_reason_code_details",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="scanner",
        route_id="/zh/scanner",
        audience=SurfaceAudience.CONSUMER,
        field_key="candidate_score_status",
        evidence_family="scanner_candidate",
        required_posture_notes=(
            "static_registry_only",
            "do_not_change_scanner_ranking_selection_or_thresholds",
            "consumer_projection_must_stay_observation_only_when_authority_is_missing",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="single_stock",
        route_id="/zh",
        audience=SurfaceAudience.CONSUMER,
        field_key="single_stock_summary_status",
        evidence_family="single_stock_evidence",
        required_posture_notes=(
            "static_registry_only",
            "single_stock_analysis_must_remain_observation_only",
            "report_export_and_drawer_surfaces_must_hide_provider_diagnostics",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.OBSERVATION_ONLY_SUMMARY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="watchlist",
        route_id="/zh/watchlist",
        audience=SurfaceAudience.CONSUMER,
        field_key="watchlist_readiness_status",
        evidence_family="watchlist_candidate",
        required_posture_notes=(
            "static_registry_only",
            "do_not_change_watchlist_mutation_or_refresh_semantics",
            "consumer_projection_must_not_imply_trade_or_execution_authority",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="portfolio",
        route_id="/zh/portfolio",
        audience=SurfaceAudience.CONSUMER,
        field_key="portfolio_read_model_status",
        evidence_family="portfolio_research",
        required_posture_notes=(
            "static_registry_only",
            "do_not_change_portfolio_accounting_cash_holdings_or_pnl_semantics",
            "consumer_projection_must_hide_provider_and_ledger_diagnostics",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="backtest",
        route_id="/zh/backtest",
        audience=SurfaceAudience.CONSUMER,
        field_key="backtest_result_status",
        evidence_family="backtest_research",
        required_posture_notes=(
            "static_registry_only",
            "do_not_change_backtest_calculations_fills_costs_or_metrics",
            "consumer_projection_must_not_promote_decision_grade_without_review",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.SAFE_PRODUCT_STATUS_ONLY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
    SurfaceRegistryEntry(
        surface_id="options",
        route_id="/zh/options-lab",
        audience=SurfaceAudience.CONSUMER,
        field_key="options_setup_status",
        evidence_family="options_market_structure",
        required_posture_notes=(
            "static_registry_only",
            "do_not_grant_trade_recommendation_or_contract_selection_authority",
            "consumer_projection_must_preserve_no_advice_and_observation_only_posture",
        ),
        consumer_visibility_intent=ConsumerVisibilityIntent.OBSERVATION_ONLY_SUMMARY,
        admin_visibility_intent=AdminVisibilityIntent.GATED_DIAGNOSTIC_METADATA_ALLOWED,
    ),
)


DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD: Final[dict[tuple[str, str], SurfaceRegistryEntry]] = {
    (entry.surface_id, entry.field_key): entry
    for entry in DATA_COVERAGE_SURFACE_REGISTRY
}
