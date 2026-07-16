# -*- coding: utf-8 -*-
"""Local-only market data readiness diagnostics.

This module must remain inert. It inspects environment variables, filesystem
presence, and optional dependency importability without calling providers,
opening network connections, or reading parquet contents.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from src.services.official_macro_liquidity_cache_contracts import (
    OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
    OFFICIAL_US_RATES_REQUIRED_SERIES,
    build_official_fed_liquidity_cache_bundle,
    build_official_us_rates_cache_bundle,
    normalize_official_series_aliases,
)
from src.services.historical_ohlcv_cache_preflight import build_historical_ohlcv_cache_preflight
from src.services.akshare_cn_ohlcv_cache import build_akshare_cn_ohlcv_runtime_status
from src.services.cross_asset_driver_readiness import (
    build_cross_asset_driver_readiness,
    cross_asset_driver_cache_symbols,
)
from src.services.provider_affected_surface_mapping import (
    canonical_product_affected_surfaces,
)
from src.services.vix_metadata import is_vix_symbol, normalize_vix_quote_metadata


CONSUMER_EVIDENCE_READINESS_MATRIX_VERSION = "consumer_evidence_readiness_matrix_v1"
_LOCAL_US_PARQUET_ENV_KEYS = ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR")
_TUSHARE_TOKEN_ENV_KEYS = ("TUSHARE_TOKEN",)
_PARQUET_ENGINES = ("pyarrow", "fastparquet")
_OPTIONAL_PROVIDER_MODULES = ("tushare", "pytdx", "akshare", "efinance")
_MARKET_INTELLIGENCE_SURFACES = ("market_overview", "liquidity_monitor")
_LOCAL_US_SURFACES = ("stock_history",)
_OFFICIAL_RISK_READINESS_VERSION = "official_risk_source_readiness_v1"
_OFFICIAL_RISK_READY_FRESHNESS = frozenset({"live", "fresh", "cached", "delayed"})
_VIX_SERIES_ID = "VIXCLS"


SpecFinder = Callable[[str], object | None]


@dataclass(frozen=True, slots=True)
class MarketDataReadinessCheck:
    id: str
    status: str
    severity: str
    user_facing_message: str
    remediation_hint: Optional[str]
    affects_surfaces: tuple[str, ...]
    product_affected_surfaces: tuple[str, ...] = ()
    secret_configured: Optional[bool] = None
    details: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "severity": self.severity,
            "userFacingMessage": self.user_facing_message,
            "remediationHint": self.remediation_hint,
            "affectsSurfaces": list(self.affects_surfaces),
            "productAffectedSurfaces": list(
                self.product_affected_surfaces
                or canonical_product_affected_surfaces(self.affects_surfaces)
            ),
        }
        if self.secret_configured is not None:
            payload["secretConfigured"] = self.secret_configured
        if self.details:
            payload["details"] = dict(self.details)
        return payload


@dataclass(frozen=True, slots=True)
class ConsumerEvidenceReadinessSpec:
    surface: str
    evidence_family: str
    required_inputs: tuple[str, ...]
    fulfilled_inputs: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    stale_inputs: tuple[str, ...] = ()
    blocked_inputs: tuple[str, ...] = ()
    observation_only_inputs: tuple[str, ...] = ()
    score_grade_inputs: tuple[str, ...] = ()
    readiness_state: str = "unavailable"
    confidence_cap_reason: str = ""
    source_authority_reason: str = ""
    freshness_reason: str = ""
    next_diagnostic: str = ""
    consumer_safe_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "evidenceFamily": self.evidence_family,
            "requiredInputs": list(self.required_inputs),
            "fulfilledInputs": list(self.fulfilled_inputs),
            "missingInputs": list(self.missing_inputs),
            "staleInputs": list(self.stale_inputs),
            "blockedInputs": list(self.blocked_inputs),
            "observationOnlyInputs": list(self.observation_only_inputs),
            "scoreGradeInputs": list(self.score_grade_inputs),
            "readinessState": self.readiness_state,
            "confidenceCapReason": self.confidence_cap_reason,
            "sourceAuthorityReason": self.source_authority_reason,
            "freshnessReason": self.freshness_reason,
            "nextDiagnostic": self.next_diagnostic,
            "consumerSafeSummary": self.consumer_safe_summary,
        }


@dataclass(frozen=True, slots=True)
class MarketDataReadinessDiagnostics:
    readiness_status: str
    checks: tuple[MarketDataReadinessCheck, ...]
    consumer_evidence_readiness_matrix: tuple[ConsumerEvidenceReadinessSpec, ...]
    official_risk_source_readiness: Mapping[str, Any]
    historical_ohlcv_cache_preflight: Mapping[str, Any]
    cross_asset_driver_readiness: Mapping[str, Any]
    representative_symbols: tuple[str, ...] = ()
    diagnostic_only: bool = True
    provider_runtime_called: bool = False
    network_calls_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "readinessStatus": self.readiness_status,
            "diagnosticOnly": self.diagnostic_only,
            "providerRuntimeCalled": self.provider_runtime_called,
            "networkCallsEnabled": self.network_calls_enabled,
            "representativeSymbols": list(self.representative_symbols),
            "historicalOhlcvCachePreflight": dict(self.historical_ohlcv_cache_preflight),
            "crossAssetDriverReadiness": dict(self.cross_asset_driver_readiness),
            "checks": [check.to_dict() for check in self.checks],
            "consumerEvidenceReadinessMatrix": {
                "contractVersion": CONSUMER_EVIDENCE_READINESS_MATRIX_VERSION,
                "diagnosticOnly": True,
                "networkCallsEnabled": False,
                "mutationEnabled": False,
                "items": [
                    row.to_dict()
                    for row in self.consumer_evidence_readiness_matrix
                ],
            },
            "officialRiskSourceReadiness": dict(self.official_risk_source_readiness),
        }


def build_market_data_readiness_diagnostics(
    *,
    representative_symbols: Optional[Sequence[str]] = None,
    env: Optional[Mapping[str, str]] = None,
    spec_finder: SpecFinder = importlib.util.find_spec,
    official_vix_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    official_rates_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    official_fed_liquidity_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> MarketDataReadinessDiagnostics:
    """Return an additive readiness snapshot using local-only signals."""

    resolved_env = env if env is not None else os.environ
    normalized_symbols = _normalize_symbols(representative_symbols)
    checks: list[MarketDataReadinessCheck] = []

    parquet_dir_key, parquet_dir_value = _resolve_first_nonempty_env(_LOCAL_US_PARQUET_ENV_KEYS, resolved_env)
    parquet_dir = Path(parquet_dir_value) if parquet_dir_value else None

    checks.append(_build_local_us_parquet_dir_check(parquet_dir_key=parquet_dir_key, parquet_dir=parquet_dir))
    checks.append(_build_parquet_engine_check(parquet_dir=parquet_dir, spec_finder=spec_finder))
    checks.append(_build_representative_parquet_file_check(parquet_dir=parquet_dir, symbols=normalized_symbols))
    checks.append(_build_tushare_token_check(env=resolved_env))
    checks.append(_build_optional_dependency_check(spec_finder=spec_finder))
    checks.append(_build_akshare_cn_ohlcv_runtime_check(env=resolved_env, spec_finder=spec_finder))

    historical_ohlcv_cache_preflight = build_historical_ohlcv_cache_preflight(
        env=resolved_env,
        spec_finder=spec_finder,
        symbols_by_market={"us": normalized_symbols},
        dry_run=True,
    )
    cross_asset_ohlcv_cache_preflight = build_historical_ohlcv_cache_preflight(
        env=resolved_env,
        spec_finder=spec_finder,
        symbols_by_market={"us": cross_asset_driver_cache_symbols()},
        dry_run=True,
    )

    return MarketDataReadinessDiagnostics(
        readiness_status=_resolve_readiness_status(checks),
        checks=tuple(checks),
        consumer_evidence_readiness_matrix=_build_consumer_evidence_readiness_matrix(),
        official_risk_source_readiness=build_official_risk_source_readiness(
            vix_rows=official_vix_rows,
            rates_rows=official_rates_rows,
            fed_liquidity_rows=official_fed_liquidity_rows,
        ),
        historical_ohlcv_cache_preflight=historical_ohlcv_cache_preflight,
        cross_asset_driver_readiness=build_cross_asset_driver_readiness(
            historical_ohlcv_cache_preflight=cross_asset_ohlcv_cache_preflight,
        ).to_dict(),
        representative_symbols=normalized_symbols,
    )


def build_official_risk_source_readiness(
    *,
    vix_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    rates_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    fed_liquidity_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    """Project official VIX/rates/Fed-liquidity row readiness without side effects."""

    vix = _build_vix_readiness(vix_rows)
    rates_bundle = build_official_us_rates_cache_bundle(rates_rows)
    fed_bundle = build_official_fed_liquidity_cache_bundle(fed_liquidity_rows)
    rates = _build_bundle_family_readiness(
        rates_bundle,
        rows=rates_rows,
        series=",".join(OFFICIAL_US_RATES_REQUIRED_SERIES),
        missing_blocker="missing_official_rates_series",
        stale_blocker="stale_official_rates_series",
        malformed_blocker="malformed_official_rates_row",
        fallback_blocker="non_official_rates_row",
        unavailable_blocker="unavailable_official_rates_rows",
        policy_blocker="official_rates_freshness_policy_not_met",
        budget_blocker="official_rates_refresh_budget_blocked",
        include_covered_series_count=True,
    )
    fed_liquidity = _build_bundle_family_readiness(
        fed_bundle,
        rows=fed_liquidity_rows,
        series=",".join(OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES),
        missing_blocker="missing_official_fed_liquidity_rows",
        stale_blocker="stale_official_fed_liquidity_rows",
        malformed_blocker="malformed_official_fed_liquidity_rows",
        fallback_blocker="non_official_fed_liquidity_rows",
        unavailable_blocker="unavailable_official_fed_liquidity_rows",
        policy_blocker="official_fed_liquidity_freshness_policy_not_met",
        budget_blocker="official_fed_liquidity_refresh_budget_blocked",
        include_covered_series_count=False,
    )
    bundle_state = _derive_official_risk_bundle_state((vix["state"], rates["state"], fed_liquidity["state"]))

    return {
        "contractVersion": _OFFICIAL_RISK_READINESS_VERSION,
        "diagnosticOnly": True,
        "networkCallsEnabled": False,
        "externalProviderCalls": False,
        "mutationEnabled": False,
        "vix": vix,
        "rates": rates,
        "fedLiquidity": fed_liquidity,
        "bundleState": bundle_state,
        "consumerSummary": _official_risk_consumer_summary(
            bundle_state=bundle_state,
            vix_state=str(vix["state"]),
            rates_state=str(rates["state"]),
            fed_liquidity_state=str(fed_liquidity["state"]),
        ),
        "nextDataAction": _official_risk_next_data_action(vix=vix, rates=rates, fed_liquidity=fed_liquidity),
    }


def _build_vix_readiness(rows: Optional[Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    candidates = [
        row
        for row in rows or ()
        if isinstance(row, Mapping)
        and (_row_series_id(row) == _VIX_SERIES_ID or is_vix_symbol(row.get("symbol") or row.get("key")))
    ]
    if not candidates:
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            blocker="missing_official_vix_row",
        )

    row = _latest_row(candidates)
    authority_snapshot = normalize_vix_quote_metadata(row).get("volatilityAuthoritySnapshot")
    if isinstance(authority_snapshot, Mapping) and (
        authority_snapshot.get("authorityState") == "blocked"
        or authority_snapshot.get("coverageState") == "rejected"
        or authority_snapshot.get("instrumentIdentity", {}).get("identityState") == "identity_mismatch"
    ):
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            latest_date=_row_latest_date(row),
            as_of=_row_as_of(row),
            freshness=_row_freshness(row),
            blocker=str(authority_snapshot.get("scoreEligibility", {}).get("reason") or "identity_mismatch"),
            volatility_authority_snapshot=authority_snapshot,
        )
    freshness = _row_freshness(row)
    if _row_is_flagged(row, "isFallback") or freshness in {"fallback", "mock", "synthetic"}:
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            latest_date=_row_latest_date(row),
            as_of=_row_as_of(row),
            freshness=freshness,
            blocker="non_official_vix_row",
            volatility_authority_snapshot=authority_snapshot,
        )
    if _row_is_flagged(row, "isUnavailable") or freshness in {"unavailable", "error"}:
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            latest_date=_row_latest_date(row),
            as_of=_row_as_of(row),
            freshness=freshness,
            blocker="unavailable_official_vix_row",
            volatility_authority_snapshot=authority_snapshot,
        )
    if _row_is_flagged(row, "isStale") or freshness == "stale":
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            latest_date=_row_latest_date(row),
            as_of=_row_as_of(row),
            freshness=freshness,
            blocker="stale_official_vix_row",
            volatility_authority_snapshot=authority_snapshot,
        )
    if not _row_is_official_public(row) or not _row_numeric_value(row):
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            latest_date=_row_latest_date(row),
            as_of=_row_as_of(row),
            freshness=freshness,
            blocker="invalid_official_vix_row",
            volatility_authority_snapshot=authority_snapshot,
        )
    if row.get("sourceAuthorityAllowed") is not True:
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            latest_date=_row_latest_date(row),
            as_of=_row_as_of(row),
            freshness=freshness,
            blocker="official_vix_authority_not_ready",
            volatility_authority_snapshot=authority_snapshot,
        )
    if freshness not in _OFFICIAL_RISK_READY_FRESHNESS:
        return _family_readiness(
            state="blocked",
            series=_VIX_SERIES_ID,
            source="official_public",
            latest_date=_row_latest_date(row),
            as_of=_row_as_of(row),
            freshness=freshness,
            blocker="official_vix_freshness_not_ready",
            volatility_authority_snapshot=authority_snapshot,
        )
    return _family_readiness(
        state="ready",
        series=_VIX_SERIES_ID,
        source="official_public",
        latest_date=_row_latest_date(row),
        as_of=_row_as_of(row),
        freshness=freshness,
        blocker=None,
        volatility_authority_snapshot=authority_snapshot,
    )


def _build_bundle_family_readiness(
    bundle: Mapping[str, Any],
    *,
    rows: Optional[Sequence[Mapping[str, Any]]],
    series: str,
    missing_blocker: str,
    stale_blocker: str,
    malformed_blocker: str,
    fallback_blocker: str,
    unavailable_blocker: str,
    policy_blocker: str,
    budget_blocker: str,
    include_covered_series_count: bool,
) -> dict[str, Any]:
    coverage_count = _int(bundle.get("coverageCount"))
    if bundle.get("readinessEligible") is True:
        state = "ready"
        blocker = None
    elif bundle.get("budgetBlockedSeries"):
        state = "partial" if coverage_count else "blocked"
        blocker = budget_blocker
    elif bundle.get("malformedSeries"):
        state = "partial" if coverage_count else "blocked"
        blocker = malformed_blocker
    elif bundle.get("fallbackOrProxySeries"):
        state = "partial" if coverage_count else "blocked"
        blocker = fallback_blocker
    elif bundle.get("policyRejectedSeries"):
        state = "partial" if coverage_count else "blocked"
        blocker = policy_blocker
    elif bundle.get("staleSeries"):
        state = "partial" if coverage_count else "blocked"
        blocker = stale_blocker
    elif bundle.get("missingSeries"):
        state = "partial" if coverage_count else "blocked"
        blocker = missing_blocker
    elif bundle.get("unavailableSeries"):
        state = "partial" if coverage_count else "blocked"
        blocker = unavailable_blocker
    elif bundle.get("isPartial"):
        state = "partial"
        blocker = missing_blocker
    else:
        state = "blocked"
        blocker = unavailable_blocker

    return _family_readiness(
        state=state,
        series=series,
        source="official_public",
        latest_date=_latest_from_rows(rows, "date") or _latest_from_bundle(bundle, "date"),
        as_of=_latest_from_rows(rows, "asOf") or _latest_from_bundle(bundle, "asOf"),
        freshness=_safe_text(bundle.get("freshness")) or "unavailable",
        blocker=blocker,
        covered_series_count=coverage_count if include_covered_series_count else None,
    )


def _build_consumer_evidence_readiness_matrix() -> tuple[ConsumerEvidenceReadinessSpec, ...]:
    """Return static, consumer-safe readiness posture for market evidence surfaces."""

    return (
        ConsumerEvidenceReadinessSpec(
            surface="market_overview",
            evidence_family="market_regime",
            required_inputs=(
                "macro context",
                "liquidity context",
                "rotation context",
                "market breadth context",
            ),
            fulfilled_inputs=("market overview read model",),
            missing_inputs=("market breadth context",),
            blocked_inputs=("macro context",),
            observation_only_inputs=("liquidity context", "rotation context"),
            score_grade_inputs=("market overview read model",),
            readiness_state="score_grade",
            confidence_cap_reason=(
                "Only the overview read model is score-grade; supporting families still cap confidence."
            ),
            source_authority_reason="Supporting families need stronger display authority before they can lift the cap.",
            freshness_reason="Freshness is measured by each existing market surface before this matrix is shown.",
            next_diagnostic="Compare overview evidence families against current safe surface snapshots.",
            consumer_safe_summary=(
                "Market overview has one score-grade input, while supporting evidence remains capped or observational."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="market_overview",
            evidence_family="official_vix_volatility",
            required_inputs=("VIXCLS official volatility close",),
            missing_inputs=("VIXCLS official volatility close",),
            blocked_inputs=("source authority gate", "freshness gate"),
            score_grade_inputs=(),
            readiness_state="missing",
            confidence_cap_reason=(
                "Official VIX volatility has no score-grade input until authority and freshness both pass."
            ),
            source_authority_reason="The VIXCLS source authority gate must pass before market overview scoring.",
            freshness_reason="The VIXCLS freshness gate must pass before the row can leave missing state.",
            next_diagnostic="Inspect the existing safe market overview volatility evidence snapshot.",
            consumer_safe_summary=(
                "Official VIX volatility is visible only as a readiness boundary until authority and freshness pass."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="market_overview",
            evidence_family="official_macro_rates_liquidity_bundle",
            required_inputs=(
                "Treasury daily rates",
                "policy-rate daily rows",
                "credit and USD pressure rows",
                "Fed liquidity weekly rows",
            ),
            missing_inputs=(
                "Treasury daily rates",
                "policy-rate daily rows",
                "credit and USD pressure rows",
                "Fed liquidity weekly rows",
            ),
            blocked_inputs=("coverage gate", "freshness gate", "source authority gate"),
            score_grade_inputs=(),
            readiness_state="missing",
            confidence_cap_reason=(
                "Macro, rates, and Fed liquidity stay capped until every required official family passes."
            ),
            source_authority_reason=(
                "Partial, proxy, fallback, missing, or stale rows cannot grant market overview score authority."
            ),
            freshness_reason=(
                "Treasury and policy-rate rows need the daily policy; Fed liquidity rows need the weekly policy."
            ),
            next_diagnostic="Inspect existing safe macro, rates, and liquidity evidence snapshots.",
            consumer_safe_summary=(
                "Market overview cannot promote the macro, rates, and Fed liquidity bundle until source authority, freshness, and coverage all pass."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="liquidity_monitor",
            evidence_family="liquidity",
            required_inputs=(
                "rates pressure",
                "credit stress",
                "volatility stress",
                "fund flow context",
                "breadth confirmation",
            ),
            fulfilled_inputs=(),
            missing_inputs=("rates pressure", "credit stress"),
            stale_inputs=("volatility stress",),
            blocked_inputs=("fund flow context",),
            observation_only_inputs=("breadth confirmation",),
            readiness_state="observation_only",
            confidence_cap_reason="Reliable score-grade coverage is below the consumer conclusion minimum.",
            source_authority_reason="Visible liquidity context is useful for observation but not conclusion authority.",
            freshness_reason="At least one liquidity family is delayed or not refreshed enough for a stronger state.",
            next_diagnostic="Review liquidity family coverage and freshness with the existing safe diagnostics.",
            consumer_safe_summary=(
                "Liquidity context is available for observation only and does not support a score-grade conclusion."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="liquidity_monitor",
            evidence_family="vix_pressure",
            required_inputs=("VIXCLS official volatility close",),
            missing_inputs=("VIXCLS official volatility close",),
            blocked_inputs=("source authority gate", "freshness gate"),
            observation_only_inputs=("proxy volatility context",),
            score_grade_inputs=(),
            readiness_state="observation_only",
            confidence_cap_reason=(
                "VIX pressure remains capped until official source authority and freshness both pass."
            ),
            source_authority_reason="Proxy volatility context cannot satisfy the VIXCLS source authority gate.",
            freshness_reason="The VIXCLS freshness gate is required before liquidity scoring can use this family.",
            next_diagnostic="Inspect existing safe liquidity volatility evidence before enabling scoring.",
            consumer_safe_summary=(
                "Liquidity VIX pressure stays observational until official authority and freshness pass."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="liquidity_monitor",
            evidence_family="macro_rates_fed_liquidity_bundle",
            required_inputs=(
                "Treasury daily rates",
                "policy-rate daily rows",
                "credit and USD pressure rows",
                "Fed liquidity weekly rows",
            ),
            missing_inputs=(
                "Treasury daily rates",
                "policy-rate daily rows",
                "credit and USD pressure rows",
                "Fed liquidity weekly rows",
            ),
            blocked_inputs=("coverage gate", "freshness gate", "source authority gate"),
            observation_only_inputs=("proxy macro and rates context",),
            score_grade_inputs=(),
            readiness_state="observation_only",
            confidence_cap_reason=(
                "Liquidity score contribution requires full official coverage plus the correct daily and weekly freshness checks."
            ),
            source_authority_reason=(
                "Proxy, fallback, partial, missing, or stale macro rows remain observation-only."
            ),
            freshness_reason=(
                "Daily rates and weekly Fed liquidity freshness must both pass before score-grade use."
            ),
            next_diagnostic="Review liquidity family coverage diagnostics before enabling macro score contribution.",
            consumer_safe_summary=(
                "Liquidity monitor keeps macro, rates, and Fed liquidity observational until authority, freshness, and coverage are complete."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="rotation_radar",
            evidence_family="rotation",
            required_inputs=(
                "theme coverage",
                "theme flow",
                "constituent coverage",
                "breadth confirmation",
            ),
            fulfilled_inputs=("taxonomy map",),
            missing_inputs=("theme flow",),
            blocked_inputs=("constituent coverage",),
            observation_only_inputs=("taxonomy map", "breadth confirmation"),
            readiness_state="blocked",
            confidence_cap_reason=(
                "Headline rotation ranking remains capped until theme coverage and flow evidence are stronger."
            ),
            source_authority_reason="Current consumer-safe rotation context cannot grant headline authority.",
            freshness_reason="Theme-flow freshness is not sufficient for a stronger state.",
            next_diagnostic="Inspect rotation consumer evidence counts and headline-lane exclusion reasons.",
            consumer_safe_summary="Rotation radar can show observations, but headline ranking evidence is blocked.",
        ),
        ConsumerEvidenceReadinessSpec(
            surface="decision_cockpit",
            evidence_family="decision_context",
            required_inputs=(
                "market overview",
                "research radar",
                "liquidity monitor",
                "rotation radar",
                "options observation",
            ),
            fulfilled_inputs=("market overview",),
            missing_inputs=("research radar", "options observation"),
            blocked_inputs=("liquidity monitor", "rotation radar"),
            observation_only_inputs=("market overview",),
            readiness_state="missing",
            confidence_cap_reason="Cross-surface decision context is incomplete.",
            source_authority_reason=(
                "Downstream surfaces cannot be promoted while required evidence is missing or blocked."
            ),
            freshness_reason="Freshness remains unresolved until all required families are present.",
            next_diagnostic="Build a cockpit driver table from existing market and research read models.",
            consumer_safe_summary=(
                "Decision cockpit is missing required cross-surface evidence and cannot make a strong market judgment."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="home_briefing",
            evidence_family="home_market_briefing",
            required_inputs=(
                "market overview",
                "liquidity context",
                "rotation context",
            ),
            missing_inputs=("liquidity context", "rotation context"),
            stale_inputs=("market overview",),
            readiness_state="unavailable",
            confidence_cap_reason=(
                "Home briefing depends on upstream market context and cannot strengthen unavailable evidence."
            ),
            source_authority_reason="The public briefing shell is safe but does not grant source authority.",
            freshness_reason="Upstream freshness is not ready enough for score-grade wording.",
            next_diagnostic="Recheck Home after market overview, liquidity, and rotation evidence improve.",
            consumer_safe_summary=(
                "Home briefing is unavailable for score-grade conclusion until upstream evidence is ready."
            ),
        ),
        ConsumerEvidenceReadinessSpec(
            surface="research_radar",
            evidence_family="research_prerequisites",
            required_inputs=(
                "completed scanner evidence",
                "watchlist research context",
                "candidate evidence quality",
            ),
            fulfilled_inputs=("consumer-safe research projection",),
            missing_inputs=("completed scanner evidence", "watchlist research context"),
            observation_only_inputs=("consumer-safe research projection",),
            readiness_state="observation_only",
            confidence_cap_reason="Research radar is bounded to observation while prerequisite evidence is incomplete.",
            source_authority_reason=(
                "Research context stays consumer-safe and does not grant market conclusion authority."
            ),
            freshness_reason="Candidate freshness is resolved by the research read model when evidence exists.",
            next_diagnostic="Check scanner and watchlist prerequisites before expecting research evidence.",
            consumer_safe_summary=(
                "Research radar can explain available observations but prerequisite evidence is incomplete."
            ),
        ),
    )


def _build_local_us_parquet_dir_check(
    *,
    parquet_dir_key: Optional[str],
    parquet_dir: Optional[Path],
) -> MarketDataReadinessCheck:
    if parquet_dir is None:
        return MarketDataReadinessCheck(
            id="local_us_parquet_dir",
            status="missing",
            severity="warning",
            user_facing_message="Local US parquet directory is not configured.",
            remediation_hint="Set LOCAL_US_PARQUET_DIR or US_STOCK_PARQUET_DIR to a normalized US parquet root.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details={
                "envKeys": list(_LOCAL_US_PARQUET_ENV_KEYS),
                "pathConfigured": False,
                "storageKind": "local_filesystem",
            },
        )

    try:
        exists = parquet_dir.exists()
        is_dir = parquet_dir.is_dir()
    except OSError as exc:
        return MarketDataReadinessCheck(
            id="local_us_parquet_dir",
            status="misconfigured",
            severity="error",
            user_facing_message="Local US parquet directory could not be inspected.",
            remediation_hint="Verify the configured parquet root is readable by the current process.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details=_build_path_details(
                env_key=parquet_dir_key,
                parquet_dir=parquet_dir,
                reason="path_inspection_failed",
                error=exc,
            ),
        )

    if not exists:
        return MarketDataReadinessCheck(
            id="local_us_parquet_dir",
            status="misconfigured",
            severity="error",
            user_facing_message="Configured local US parquet directory does not exist.",
            remediation_hint="Fix LOCAL_US_PARQUET_DIR/US_STOCK_PARQUET_DIR or sync the parquet dataset to the configured path.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details=_build_path_details(env_key=parquet_dir_key, parquet_dir=parquet_dir),
        )
    if not is_dir:
        return MarketDataReadinessCheck(
            id="local_us_parquet_dir",
            status="misconfigured",
            severity="error",
            user_facing_message="Configured local US parquet path is not a directory.",
            remediation_hint="Point LOCAL_US_PARQUET_DIR/US_STOCK_PARQUET_DIR at the parquet directory, not a single file.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details=_build_path_details(env_key=parquet_dir_key, parquet_dir=parquet_dir),
        )

    return MarketDataReadinessCheck(
        id="local_us_parquet_dir",
        status="ready",
        severity="info",
        user_facing_message="Local US parquet directory is configured and reachable.",
        remediation_hint=None,
        affects_surfaces=_LOCAL_US_SURFACES,
        details=_build_path_details(env_key=parquet_dir_key, parquet_dir=parquet_dir),
    )


def _build_path_details(
    *,
    env_key: Optional[str],
    parquet_dir: Path,
    reason: Optional[str] = None,
    error: Optional[OSError] = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "envKey": env_key,
        "pathConfigured": True,
        "pathBasename": parquet_dir.name or None,
        "storageKind": "local_filesystem",
    }
    if reason:
        details["reason"] = reason
    if error is not None:
        details["errorType"] = type(error).__name__
        if error.errno is not None:
            details["errorCode"] = error.errno
    return details


def _build_parquet_engine_check(
    *,
    parquet_dir: Optional[Path],
    spec_finder: SpecFinder,
) -> MarketDataReadinessCheck:
    available_engines = [engine for engine in _PARQUET_ENGINES if _module_available(engine, spec_finder)]
    if available_engines:
        return MarketDataReadinessCheck(
            id="parquet_engine",
            status="ready",
            severity="info",
            user_facing_message="A parquet engine is importable for local US parquet reads.",
            remediation_hint=None,
            affects_surfaces=_LOCAL_US_SURFACES,
            details={"availableModules": available_engines},
        )

    status = "misconfigured" if parquet_dir is not None else "missing"
    severity = "error" if parquet_dir is not None else "warning"
    return MarketDataReadinessCheck(
        id="parquet_engine",
        status=status,
        severity=severity,
        user_facing_message="No parquet engine is importable for local US parquet reads.",
        remediation_hint="Install pyarrow or fastparquet in the local runtime before relying on LOCAL_US_PARQUET_DIR.",
        affects_surfaces=_LOCAL_US_SURFACES,
        details={"checkedModules": list(_PARQUET_ENGINES)},
    )


def _build_representative_parquet_file_check(
    *,
    parquet_dir: Optional[Path],
    symbols: Sequence[str],
) -> MarketDataReadinessCheck:
    if not symbols:
        return MarketDataReadinessCheck(
            id="local_us_parquet_representative_files",
            status="missing",
            severity="warning",
            user_facing_message="Representative US parquet file presence was not evaluated because no symbol list was provided.",
            remediation_hint="Provide representative symbols when you want the diagnostic to verify file coverage.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details={
                "representativeSymbols": [],
                "checkedCount": 0,
                "availableCount": 0,
                "missingCount": 0,
                "reason": "representative_symbols_not_configured",
            },
        )
    if parquet_dir is None:
        return MarketDataReadinessCheck(
            id="local_us_parquet_representative_files",
            status="missing",
            severity="warning",
            user_facing_message="Representative US parquet file presence was not evaluated because no parquet root is configured.",
            remediation_hint="Configure LOCAL_US_PARQUET_DIR or US_STOCK_PARQUET_DIR before checking representative parquet files.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details={
                "representativeSymbols": list(symbols),
                "checkedCount": 0,
                "availableCount": 0,
                "missingCount": 0,
                "unavailableCount": len(symbols),
                "reason": "parquet_root_not_configured",
            },
        )

    missing_symbols = [symbol for symbol in symbols if not (parquet_dir / f"{symbol}.parquet").exists()]
    missing_count = len(missing_symbols)
    available_count = len(symbols) - missing_count
    if not missing_symbols:
        return MarketDataReadinessCheck(
            id="local_us_parquet_representative_files",
            status="ready",
            severity="info",
            user_facing_message="Representative US parquet files are present.",
            remediation_hint=None,
            affects_surfaces=_LOCAL_US_SURFACES,
            details={
                "representativeSymbols": list(symbols),
                "checkedCount": len(symbols),
                "availableCount": available_count,
                "missingCount": missing_count,
            },
        )

    status = "missing" if available_count == 0 else "partial"
    return MarketDataReadinessCheck(
        id="local_us_parquet_representative_files",
        status=status,
        severity="warning",
        user_facing_message="Representative US parquet files are missing for part of the requested symbol set.",
        remediation_hint="Sync the missing parquet files or reduce the representative symbol list to locally available coverage.",
        affects_surfaces=_LOCAL_US_SURFACES,
        details={
            "representativeSymbols": list(symbols),
            "missingSymbols": missing_symbols,
            "existingCount": available_count,
            "checkedCount": len(symbols),
            "availableCount": available_count,
            "missingCount": missing_count,
        },
    )


def _build_tushare_token_check(*, env: Mapping[str, str]) -> MarketDataReadinessCheck:
    env_key, env_value = _resolve_first_nonempty_env(_TUSHARE_TOKEN_ENV_KEYS, env)
    secret_configured = bool(env_value)
    if secret_configured:
        return MarketDataReadinessCheck(
            id="tushare_token",
            status="ready",
            severity="info",
            user_facing_message="Tushare token is configured for local runtime checks.",
            remediation_hint=None,
            affects_surfaces=_MARKET_INTELLIGENCE_SURFACES,
            secret_configured=True,
            details={"envKey": env_key},
        )

    return MarketDataReadinessCheck(
        id="tushare_token",
        status="missing",
        severity="warning",
        user_facing_message="Tushare token is not configured.",
        remediation_hint="Set TUSHARE_TOKEN when local operators need Tushare-backed CN/HK market intelligence inputs.",
        affects_surfaces=_MARKET_INTELLIGENCE_SURFACES,
        secret_configured=False,
        details={"envKeys": list(_TUSHARE_TOKEN_ENV_KEYS)},
    )


def _build_optional_dependency_check(*, spec_finder: SpecFinder) -> MarketDataReadinessCheck:
    available = [name for name in _OPTIONAL_PROVIDER_MODULES if _module_available(name, spec_finder)]
    missing = [name for name in _OPTIONAL_PROVIDER_MODULES if name not in available]
    if not missing:
        return MarketDataReadinessCheck(
            id="optional_provider_dependencies",
            status="ready",
            severity="info",
            user_facing_message="Optional local provider dependencies are importable.",
            remediation_hint=None,
            affects_surfaces=_MARKET_INTELLIGENCE_SURFACES,
            details={"availableModules": available},
        )

    status = "missing" if not available else "partial"
    return MarketDataReadinessCheck(
        id="optional_provider_dependencies",
        status=status,
        severity="warning",
        user_facing_message="Some optional local provider dependencies are not importable.",
        remediation_hint="Install the missing local provider SDKs only when those market-intelligence inputs are required in this environment.",
        affects_surfaces=_MARKET_INTELLIGENCE_SURFACES,
        details={"availableModules": available, "missingModules": missing},
    )


def _build_akshare_cn_ohlcv_runtime_check(*, env: Mapping[str, str], spec_finder: SpecFinder) -> MarketDataReadinessCheck:
    status = build_akshare_cn_ohlcv_runtime_status(
        env=env,
        dependency_checker=lambda: _module_available("akshare", spec_finder),
    )
    runtime_status = _safe_text(status.get("runtimeStatus")) or "runtime_unavailable"
    if runtime_status == "available":
        return MarketDataReadinessCheck(
            id="akshare_cn_ohlcv_runtime",
            status="available",
            severity="info",
            user_facing_message="CN daily OHLCV runtime is explicitly enabled and locally importable.",
            remediation_hint=None,
            affects_surfaces=("stock_history", "scanner", "backtest"),
            details=status,
        )
    if runtime_status == "disabled":
        return MarketDataReadinessCheck(
            id="akshare_cn_ohlcv_runtime",
            status="disabled",
            severity="info",
            user_facing_message="CN daily OHLCV runtime is disabled by configuration.",
            remediation_hint=f"Set the runtime enablement flag only in environments approved for local CN daily history refreshes.",
            affects_surfaces=("stock_history", "scanner", "backtest"),
            details=status,
        )
    if runtime_status == "dependency_missing":
        return MarketDataReadinessCheck(
            id="akshare_cn_ohlcv_runtime",
            status="dependency_missing",
            severity="warning",
            user_facing_message="CN daily OHLCV runtime is enabled but its optional dependency is unavailable.",
            remediation_hint="Install the declared optional dependency before enabling local CN daily history refreshes.",
            affects_surfaces=("stock_history", "scanner", "backtest"),
            details=status,
        )
    return MarketDataReadinessCheck(
        id="akshare_cn_ohlcv_runtime",
        status="runtime_unavailable",
        severity="warning",
        user_facing_message="CN daily OHLCV runtime status could not be evaluated safely.",
        remediation_hint="Review local runtime configuration before enabling CN daily history refreshes.",
        affects_surfaces=("stock_history", "scanner", "backtest"),
        details=status,
    )


def _resolve_first_nonempty_env(keys: Sequence[str], env: Mapping[str, str]) -> tuple[Optional[str], str]:
    for key in keys:
        value = str(env.get(key, "") or "").strip()
        if value:
            return key, value
    return None, ""


def _module_available(module_name: str, spec_finder: SpecFinder) -> bool:
    try:
        return spec_finder(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _normalize_symbols(symbols: Optional[Sequence[str]]) -> tuple[str, ...]:
    if not symbols:
        return ()
    normalized = []
    for symbol in symbols:
        candidate = str(symbol or "").strip().upper()
        if candidate:
            normalized.append(candidate)
    return tuple(dict.fromkeys(normalized))


def _resolve_readiness_status(checks: Sequence[MarketDataReadinessCheck]) -> str:
    significant = [check for check in checks if check.severity != "info"]
    if any(check.status == "misconfigured" for check in significant):
        return "misconfigured"
    if not significant:
        return "ready"
    if all(check.status in {"missing", "dependency_missing"} for check in significant):
        return "missing"
    if any(check.status in {"missing", "partial", "dependency_missing", "runtime_unavailable"} for check in significant):
        return "partial"
    return "ready"


def _family_readiness(
    *,
    state: str,
    series: str,
    source: str,
    latest_date: str | None = None,
    as_of: str | None = None,
    freshness: str = "unavailable",
    blocker: str | None = None,
    covered_series_count: int | None = None,
    volatility_authority_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "state": state,
        "series": series,
        "source": source,
        "latestDate": latest_date,
        "asOf": as_of,
        "freshness": freshness,
        "blocker": blocker,
    }
    if covered_series_count is not None:
        payload["coveredSeriesCount"] = covered_series_count
    if volatility_authority_snapshot is not None:
        payload["volatilityAuthoritySnapshot"] = dict(volatility_authority_snapshot)
    return payload


def _derive_official_risk_bundle_state(states: Sequence[str]) -> str:
    normalized = [_safe_text(state) for state in states if _safe_text(state)]
    if not normalized:
        return "unknown"
    if all(state == "ready" for state in normalized):
        return "ready"
    if any(state in {"ready", "partial"} for state in normalized):
        return "partial"
    if all(state == "blocked" for state in normalized):
        return "blocked"
    return "unknown"


def _official_risk_consumer_summary(
    *,
    bundle_state: str,
    vix_state: str,
    rates_state: str,
    fed_liquidity_state: str,
) -> str:
    if bundle_state == "ready":
        return "Official VIX, rates, and Fed liquidity are ready for market risk-source checks."
    if "ready" in {vix_state, rates_state, fed_liquidity_state} or "partial" in {
        vix_state,
        rates_state,
        fed_liquidity_state,
    }:
        return "Official risk-source coverage is partly ready; incomplete families remain excluded from stronger market interpretation."
    if bundle_state == "blocked":
        return "Official risk-source coverage is not ready; market panels should wait for official rows before relying on the bundle."
    return "Official risk-source readiness is unknown until official rows are checked."


def _official_risk_next_data_action(
    *,
    vix: Mapping[str, Any],
    rates: Mapping[str, Any],
    fed_liquidity: Mapping[str, Any],
) -> str:
    if vix.get("state") != "ready":
        return "Refresh the official VIX row before relying on risk-source readiness."
    if rates.get("state") != "ready":
        return "Complete the official rates coverage before relying on the bundle."
    if fed_liquidity.get("state") != "ready":
        return "Complete the official Fed liquidity coverage before relying on the bundle."
    return "Keep the official risk-source refresh bundle warm before market panels rely on it."


def _latest_row(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return max(rows, key=lambda row: (_row_as_of(row) or "", _row_latest_date(row) or ""))


def _latest_from_bundle(bundle: Mapping[str, Any], key: str) -> str | None:
    evidence = bundle.get("sourceFreshnessEvidence")
    values: list[str] = []
    for source in (bundle, evidence if isinstance(evidence, Mapping) else {}):
        for value_key in (key, _camel_to_snake(key), key.lower()):
            value = _safe_text(source.get(value_key))
            if value:
                values.append(value)
        for nested_key in ("fulfilledRows", "rows", "items", "inputs"):
            nested = source.get(nested_key)
            if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes, bytearray)):
                for item in nested:
                    if isinstance(item, Mapping):
                        nested_value = _safe_text(
                            item.get(key) or item.get(_camel_to_snake(key)) or item.get(key.lower())
                        )
                        if nested_value:
                            values.append(nested_value)
    return max(values) if values else None


def _latest_from_rows(rows: Optional[Sequence[Mapping[str, Any]]], key: str) -> str | None:
    values: list[str] = []
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        if key == "date":
            value = _row_latest_date(row)
        elif key == "asOf":
            value = _row_as_of(row)
        else:
            value = _safe_text(row.get(key))
        if value:
            values.append(value)
    return max(values) if values else None


def _row_series_id(row: Mapping[str, Any]) -> str:
    aliases = normalize_official_series_aliases(row)
    return aliases[0] if aliases else ""


def _row_freshness(row: Mapping[str, Any]) -> str:
    evidence = row.get("sourceFreshnessEvidence")
    if isinstance(evidence, Mapping):
        evidence_freshness = _safe_text(evidence.get("freshness")).lower()
    else:
        evidence_freshness = ""
    return (_safe_text(row.get("freshness")).lower() or evidence_freshness or "unavailable")


def _row_latest_date(row: Mapping[str, Any]) -> str | None:
    return _first_nonempty_text(row, ("latestDate", "date", "officialObservationDate", "observationDate", "updatedAt"))


def _row_as_of(row: Mapping[str, Any]) -> str | None:
    return _first_nonempty_text(row, ("asOf", "as_of", "officialAsOf", "updatedAt"))


def _row_is_official_public(row: Mapping[str, Any]) -> bool:
    source_type = _safe_text(row.get("sourceType") or row.get("source_type")).lower()
    source_tier = _safe_text(row.get("sourceTier") or row.get("source_tier")).lower()
    source_id = _safe_text(row.get("sourceId") or row.get("source_id")).lower()
    source = _safe_text(row.get("source")).lower()
    return bool(
        (source_type == "official_public" or source_tier == "official_public")
        and (source in {"fred", "treasury", "nyfed"} or source_id.startswith(("fred:", "treasury:", "nyfed:")))
    )


def _row_numeric_value(row: Mapping[str, Any]) -> bool:
    value = row.get("value") if row.get("value") is not None else row.get("price")
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _row_is_flagged(row: Mapping[str, Any], key: str) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    return bool(row.get(key) or (isinstance(evidence, Mapping) and evidence.get(key)))


def _first_nonempty_text(row: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = _safe_text(row.get(key))
        if value:
            return value
    evidence = row.get("sourceFreshnessEvidence")
    if isinstance(evidence, Mapping):
        for key in keys:
            value = _safe_text(evidence.get(key))
            if value:
                return value
    return None


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _camel_to_snake(value: str) -> str:
    chars: list[str] = []
    for character in value:
        if character.isupper() and chars:
            chars.append("_")
        chars.append(character.lower())
    return "".join(chars)


__all__ = [
    "MarketDataReadinessCheck",
    "MarketDataReadinessDiagnostics",
    "build_official_risk_source_readiness",
    "build_market_data_readiness_diagnostics",
]
