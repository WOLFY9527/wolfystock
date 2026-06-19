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

from src.services.provider_affected_surface_mapping import (
    canonical_product_affected_surfaces,
)


CONSUMER_EVIDENCE_READINESS_MATRIX_VERSION = "consumer_evidence_readiness_matrix_v1"
_LOCAL_US_PARQUET_ENV_KEYS = ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR")
_TUSHARE_TOKEN_ENV_KEYS = ("TUSHARE_TOKEN",)
_PARQUET_ENGINES = ("pyarrow", "fastparquet")
_OPTIONAL_PROVIDER_MODULES = ("tushare", "pytdx", "akshare", "efinance")
_MARKET_INTELLIGENCE_SURFACES = ("market_overview", "liquidity_monitor")
_LOCAL_US_SURFACES = ("stock_history",)


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
        }


def build_market_data_readiness_diagnostics(
    *,
    representative_symbols: Optional[Sequence[str]] = None,
    env: Optional[Mapping[str, str]] = None,
    spec_finder: SpecFinder = importlib.util.find_spec,
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

    return MarketDataReadinessDiagnostics(
        readiness_status=_resolve_readiness_status(checks),
        checks=tuple(checks),
        consumer_evidence_readiness_matrix=_build_consumer_evidence_readiness_matrix(),
        representative_symbols=normalized_symbols,
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
            status="ready",
            severity="info",
            user_facing_message="Representative US parquet file presence was not evaluated because no symbol list was provided.",
            remediation_hint="Provide representative symbols when you want the diagnostic to verify file coverage.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details={"representativeSymbols": []},
        )
    if parquet_dir is None:
        return MarketDataReadinessCheck(
            id="local_us_parquet_representative_files",
            status="missing",
            severity="warning",
            user_facing_message="Representative US parquet file presence was not evaluated because no parquet root is configured.",
            remediation_hint="Configure LOCAL_US_PARQUET_DIR or US_STOCK_PARQUET_DIR before checking representative parquet files.",
            affects_surfaces=_LOCAL_US_SURFACES,
            details={"representativeSymbols": list(symbols)},
        )

    missing_symbols = [symbol for symbol in symbols if not (parquet_dir / f"{symbol}.parquet").exists()]
    if not missing_symbols:
        return MarketDataReadinessCheck(
            id="local_us_parquet_representative_files",
            status="ready",
            severity="info",
            user_facing_message="Representative US parquet files are present.",
            remediation_hint=None,
            affects_surfaces=_LOCAL_US_SURFACES,
            details={"representativeSymbols": list(symbols)},
        )

    existing_count = len(symbols) - len(missing_symbols)
    status = "missing" if existing_count == 0 else "partial"
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
            "existingCount": existing_count,
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
    if all(check.status == "missing" for check in significant):
        return "missing"
    if any(check.status in {"missing", "partial"} for check in significant):
        return "partial"
    return "ready"


__all__ = [
    "MarketDataReadinessCheck",
    "MarketDataReadinessDiagnostics",
    "build_market_data_readiness_diagnostics",
]
