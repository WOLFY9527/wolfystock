# -*- coding: utf-8 -*-
"""Pure market decision semantics foundation.

This module derives observational-only market posture semantics from already
computed Market Regime, Liquidity, and optional Rotation summary payloads. It
does not fetch providers, call networks, mutate caches, read environment
configuration, or wire results into endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


MARKET_DECISION_SEMANTICS_VERSION = "market_decision_semantics_v1"
MARKET_DIRECTION_READINESS_VERSION = "market_direction_readiness_v1"

_OFFENSIVE_REGIMES = {
    "risk_on_liquidity_expansion": 1.0,
    "goldilocks_soft_landing": 0.85,
}

_DEFENSIVE_REGIMES = {
    "risk_off_deleveraging": -1.0,
    "rates_shock_duration_pressure": -0.85,
    "dollar_squeeze": -0.85,
    "credit_or_funding_stress": -1.0,
    "term_premium_or_inflation_scare": -0.7,
    "nacho_mega_cap_defensive_rotation": -0.55,
}

_OFFENSIVE_LIQUIDITY = {
    "expanding_liquidity": 1.0,
}

_DEFENSIVE_LIQUIDITY = {
    "contracting_liquidity": -1.0,
}

_NON_SCORE_GRADE_SOURCE_TIERS = {
    "public_proxy",
    "unofficial_proxy",
    "unofficial_public_api",
    "third_party_free_api",
    "static_fallback",
    "fallback_static",
    "public_web_fallback",
    "synthetic",
    "synthetic_fixture",
    "unavailable",
    "missing",
    "malformed_fixture",
    "disabled_live_stub",
}

_NON_SCORE_GRADE_FRESHNESS = {"fallback", "unavailable", "error"}
_NON_SCORE_GRADE_ROTATION_QUALITY = {"degraded_proxy", "taxonomy_only", "proxy_only", "fallback_only"}
_READINESS_BLOCKED_FRESHNESS = {"stale", "partial", "fallback", "unavailable", "error", "mock", "synthetic"}
_READINESS_BLOCKED_TRUST = {"weak", "degraded", "unavailable", "rejected"}
_READINESS_REQUIRED_PILLARS = {
    "official_macro_rates_volatility": "Official macro/rates/volatility",
    "liquidity_conditions": "Liquidity/conditions",
    "rotation_or_risk_participation": "Rotation/risk participation",
}
_OFFICIAL_MACRO_PILLARS = {"rates_pressure", "volatility_stress", "dollar_pressure"}
_RISK_PARTICIPATION_PILLARS = {
    "risk_appetite",
    "breadth_health",
    "china_risk_appetite",
    "crypto_risk_beta",
    "rotation_leadership",
    "risk_asset_demand",
    "breadth_confirmation",
    "crypto_liquidity_beta",
}
_OFFICIAL_SOURCE_TIERS = {"official_public", "official_api"}
_OFFICIAL_SOURCES = {"fred", "treasury", "official_macro"}
_READINESS_PROXY_SOURCE_MARKERS = (
    "proxy",
    "yfinance",
    "yahoo",
    "fallback",
    "static",
    "synthetic",
    "unavailable",
    "missing",
)
_READINESS_DEGRADATION_MARKERS = (
    "proxy",
    "fallback",
    "static",
    "synthetic",
    "unavailable",
    "missing",
    "rejected",
)
_READINESS_MAX_ITEMS = 6


@dataclass(frozen=True, slots=True)
class DirectionReadinessBucket:
    count: int
    items: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "items": [dict(item) for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class MarketDirectionReadiness:
    status: str
    confidence_label: str
    score_grade_pillars: DirectionReadinessBucket
    observation_only_pillars: DirectionReadinessBucket
    missing_pillars: DirectionReadinessBucket
    blocking_reasons: tuple[str, ...]
    claim_boundaries: tuple[dict[str, Any], ...]
    not_investment_advice: bool = True
    version: str = MARKET_DIRECTION_READINESS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "confidenceLabel": self.confidence_label,
            "scoreGradePillars": self.score_grade_pillars.to_dict(),
            "observationOnlyPillars": self.observation_only_pillars.to_dict(),
            "missingPillars": self.missing_pillars.to_dict(),
            "blockingReasons": list(self.blocking_reasons),
            "claimBoundaries": [dict(item) for item in self.claim_boundaries],
            "notInvestmentAdvice": self.not_investment_advice,
        }


@dataclass(frozen=True, slots=True)
class PostureConfidence:
    value: int
    label: str
    cap_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "label": self.label,
            "capReasons": list(self.cap_reasons),
        }


@dataclass(frozen=True, slots=True)
class MarketDecisionSemanticsResult:
    posture: str
    posture_confidence: PostureConfidence
    exposure_bias: str
    style_tilts: tuple[dict[str, Any], ...]
    confirmation_signals: tuple[dict[str, Any], ...]
    invalidation_triggers: tuple[dict[str, Any], ...]
    counter_evidence: tuple[dict[str, Any], ...]
    data_gaps: tuple[dict[str, Any], ...]
    direction_readiness: MarketDirectionReadiness
    claim_boundaries: tuple[dict[str, Any], ...]
    not_investment_advice: bool = True
    version: str = MARKET_DECISION_SEMANTICS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "posture": self.posture,
            "postureConfidence": self.posture_confidence.to_dict(),
            "exposureBias": self.exposure_bias,
            "styleTilts": [dict(item) for item in self.style_tilts],
            "confirmationSignals": [dict(item) for item in self.confirmation_signals],
            "invalidationTriggers": [dict(item) for item in self.invalidation_triggers],
            "counterEvidence": [dict(item) for item in self.counter_evidence],
            "dataGaps": [dict(item) for item in self.data_gaps],
            "directionReadiness": self.direction_readiness.to_dict(),
            "claimBoundaries": [dict(item) for item in self.claim_boundaries],
            "notInvestmentAdvice": self.not_investment_advice,
        }


class MarketDecisionSemanticsService:
    """Derive watch-only posture semantics from existing synthesis DTOs."""

    min_scoring_pillars = 3

    def derive(
        self,
        market_regime_synthesis: Mapping[str, Any] | Any,
        liquidity_impulse_synthesis: Mapping[str, Any] | Any,
        rotation_summary_evidence: Mapping[str, Any] | Any | None = None,
    ) -> MarketDecisionSemanticsResult:
        regime = _coerce_payload(market_regime_synthesis)
        liquidity = _coerce_payload(liquidity_impulse_synthesis)
        rotation = _coerce_payload(rotation_summary_evidence) if rotation_summary_evidence is not None else {}

        data_gaps = _merge_surface_items(
            ("market_regime_synthesis", _sequence(regime.get("dataGaps"))),
            ("liquidity_impulse_synthesis", _sequence(liquidity.get("dataGaps"))),
            ("rotation_summary", _sequence(rotation.get("dataGaps"))),
        )
        counter_evidence = _merge_surface_items(
            ("market_regime_synthesis", _sequence(regime.get("counterEvidence"))),
            ("liquidity_impulse_synthesis", _sequence(liquidity.get("counterEvidence"))),
        )

        cap_reasons: list[str] = []
        regime_sign = _regime_sign(regime)
        liquidity_sign = _liquidity_sign(liquidity)
        score_grade_ready = self._score_grade_ready(regime, liquidity, cap_reasons)

        if regime_sign * liquidity_sign < 0:
            _append_unique(cap_reasons, "conflicting_primary_pillars")
            counter_evidence = counter_evidence + (
                {
                    "surface": "combined",
                    "key": "combined:regime_liquidity_mismatch",
                    "label": "Regime/liquidity mismatch",
                    "detail": "Market regime and liquidity impulse point in different directions.",
                },
            )

        if counter_evidence:
            _append_unique(cap_reasons, "counter_evidence_present")

        if _float(_mapping(regime.get("evidenceQuality")).get("conflictPenalty")) >= 0.25 or _float(
            _mapping(liquidity.get("evidenceQuality")).get("conflictPenalty")
        ) >= 0.25:
            _append_unique(cap_reasons, "elevated_conflict_penalty")

        rotation_style_allowed = _rotation_style_allowed(rotation)
        if rotation and not rotation_style_allowed:
            _append_unique(cap_reasons, "rotation_non_scoring_or_taxonomy_only")

        if not score_grade_ready:
            posture = "data_insufficient"
        else:
            posture = _posture_from_signs(regime_sign, liquidity_sign)

        confidence_value = self._confidence_value(posture, regime, liquidity, cap_reasons)
        confidence_label = _confidence_label(confidence_value, posture)
        if posture != "data_insufficient" and confidence_label == "low":
            _append_unique(cap_reasons, "tentative_bias_only")

        posture_confidence = PostureConfidence(
            value=confidence_value,
            label=confidence_label,
            cap_reasons=tuple(cap_reasons),
        )
        exposure_bias = _exposure_bias(posture)
        style_tilts = self._style_tilts(posture, confidence_label, regime, liquidity, rotation, rotation_style_allowed)
        confirmation_signals = self._confirmation_signals(
            posture,
            confidence_label,
            regime,
            liquidity,
            rotation,
            rotation_style_allowed,
        )
        invalidation_triggers = self._invalidation_triggers(
            posture,
            regime,
            liquidity,
            rotation,
            rotation_style_allowed,
        )
        direction_readiness = _derive_direction_readiness(
            regime,
            liquidity,
            rotation,
            posture,
            posture_confidence,
        )
        claim_boundaries = _claim_boundaries(posture, posture_confidence, bool(style_tilts))

        return MarketDecisionSemanticsResult(
            posture=posture,
            posture_confidence=posture_confidence,
            exposure_bias=exposure_bias,
            style_tilts=style_tilts,
            confirmation_signals=confirmation_signals,
            invalidation_triggers=invalidation_triggers,
            counter_evidence=counter_evidence,
            data_gaps=data_gaps,
            direction_readiness=direction_readiness,
            claim_boundaries=claim_boundaries,
        )

    def _score_grade_ready(
        self,
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        cap_reasons: list[str],
    ) -> bool:
        regime_quality = _mapping(regime.get("evidenceQuality"))
        liquidity_quality = _mapping(liquidity.get("evidenceQuality"))
        proxy_or_observation_gap = (
            int(_float(regime_quality.get("observationOnlyEvidenceCount"))) > 0
            or int(_float(regime_quality.get("scoreBlockedEvidenceCount"))) > 0
            or int(_float(liquidity_quality.get("observationOnlyEvidenceCount"))) > 0
            or int(_float(liquidity_quality.get("proxyOnlyScoringCount"))) > 0
            or int(_float(liquidity_quality.get("scoreBlockedEvidenceCount"))) > 0
        )
        if proxy_or_observation_gap:
            _append_unique(cap_reasons, "proxy_or_observation_only_evidence")

        if _text(regime.get("primaryRegime")) == "data_insufficient" or _text(liquidity.get("liquidityImpulse")) == "data_insufficient":
            _append_unique(cap_reasons, "missing_scoring_pillars")
            return False

        if int(_float(regime_quality.get("scoringPillarCount"))) < self.min_scoring_pillars:
            _append_unique(cap_reasons, "missing_scoring_pillars")
            return False
        if int(_float(liquidity_quality.get("scoringPillarCount"))) < self.min_scoring_pillars:
            _append_unique(cap_reasons, "missing_scoring_pillars")
            return False

        if int(_float(liquidity_quality.get("realScoringEvidenceCount"))) == 0 and int(
            _float(liquidity_quality.get("scoringEvidenceCount"))
        ) > 0:
            _append_unique(cap_reasons, "proxy_or_observation_only_evidence")
            return False

        if _score_grade_driver_count(_sequence(regime.get("topDrivers"))) < 2:
            _append_unique(cap_reasons, "proxy_or_observation_only_evidence")
            return False

        if _score_grade_driver_count(_sequence(liquidity.get("dominantDrivers"))) < 2:
            _append_unique(cap_reasons, "proxy_or_observation_only_evidence")
            return False

        return True

    @staticmethod
    def _confidence_value(
        posture: str,
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        cap_reasons: Sequence[str],
    ) -> int:
        if posture == "data_insufficient":
            return 18

        baseline = round(((_float(regime.get("confidence")) + _float(liquidity.get("confidence"))) / 2.0) * 100)
        penalties = 0
        if "counter_evidence_present" in cap_reasons:
            penalties += 10
        if "elevated_conflict_penalty" in cap_reasons:
            penalties += 8
        if "conflicting_primary_pillars" in cap_reasons:
            penalties += 16
        if "rotation_non_scoring_or_taxonomy_only" in cap_reasons:
            penalties += 4
        return _clamp_int(baseline - penalties, 20, 95)

    @staticmethod
    def _style_tilts(
        posture: str,
        confidence_label: str,
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        rotation: Mapping[str, Any],
        rotation_style_allowed: bool,
    ) -> tuple[dict[str, Any], ...]:
        if posture == "data_insufficient" or confidence_label not in {"medium", "high"}:
            return ()

        tilts: list[dict[str, Any]] = []
        if posture == "offensive":
            tilts.append(
                {
                    "tilt": "liquidity_beta_watch",
                    "label": "Liquidity beta watch",
                    "detail": "Risk-on regime and expanding liquidity align, but the output remains a watch-only observation.",
                }
            )
            if rotation_style_allowed and _float(rotation.get("rotationScore")) >= 70 and _float(rotation.get("changePercent")) > 0:
                tilts.append(
                    {
                        "tilt": "rotation_leadership_watch",
                        "label": "Rotation leadership watch",
                        "detail": "Score-grade rotation leadership is confirming the broader risk-on watch.",
                    }
                )
        elif posture == "defensive":
            tilts.append(
                {
                    "tilt": "quality_defense_watch",
                    "label": "Quality defense watch",
                    "detail": "Contracting liquidity and defensive regime semantics favor a risk-control watch posture only.",
                }
            )
            if rotation_style_allowed and _float(rotation.get("changePercent")) < 0:
                tilts.append(
                    {
                        "tilt": "defensive_leadership_watch",
                        "label": "Defensive leadership watch",
                        "detail": "Rotation evidence suggests leadership is narrowing rather than broadening.",
                    }
                )
        elif (
            posture == "neutral"
            and _text(liquidity.get("liquidityImpulse")) == "mixed_or_transition"
            and _text(regime.get("primaryRegime")) != "data_insufficient"
        ):
            tilts.append(
                {
                    "tilt": "transition_watch",
                    "label": "Transition watch",
                    "detail": "Signals are mixed enough that only a balanced watch is supportable.",
                }
            )
        return tuple(tilts)

    @staticmethod
    def _confirmation_signals(
        posture: str,
        confidence_label: str,
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        rotation: Mapping[str, Any],
        rotation_style_allowed: bool,
    ) -> tuple[dict[str, Any], ...]:
        if posture == "data_insufficient":
            return ()

        signals: list[dict[str, Any]] = []
        if posture == "offensive":
            signals.extend(
                [
                    {
                        "signal": "regime_alignment",
                        "detail": "Primary regime should remain in a risk-on or soft-landing watch state with score-grade support.",
                    },
                    {
                        "signal": "liquidity_alignment",
                        "detail": "Liquidity impulse should remain expanding rather than mixed or contracting.",
                    },
                ]
            )
        elif posture == "defensive":
            signals.extend(
                [
                    {
                        "signal": "regime_alignment",
                        "detail": "Primary regime should remain in a defensive or pressure-driven watch state with score-grade support.",
                    },
                    {
                        "signal": "liquidity_alignment",
                        "detail": "Liquidity impulse should remain contracting rather than expanding.",
                    },
                ]
            )
        else:
            signals.append(
                {
                    "signal": "alignment_resolution",
                    "detail": "Need regime and liquidity to realign in the same direction before a stronger watch bias is supportable.",
                }
            )

        if rotation_style_allowed and _float(rotation.get("rotationScore")) >= 70:
            signals.append(
                {
                    "signal": "rotation_confirmation",
                    "detail": "Rotation leadership should remain score-grade and source-authorized before using it as style confirmation.",
                }
            )
        if confidence_label == "low":
            signals.append(
                {
                    "signal": "tentative_bias_confirmation",
                    "detail": "Tentative bias needs follow-through from the same score-grade pillars before confidence can improve.",
                }
            )
        return tuple(signals)

    @staticmethod
    def _invalidation_triggers(
        posture: str,
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        rotation: Mapping[str, Any],
        rotation_style_allowed: bool,
    ) -> tuple[dict[str, Any], ...]:
        if posture == "data_insufficient":
            return ()

        triggers: list[dict[str, Any]] = []
        if posture == "offensive":
            triggers.extend(
                [
                    {
                        "trigger": "regime_turns_defensive_or_insufficient",
                        "detail": "Invalidate the risk-on watch if the regime flips defensive or loses score-grade coverage.",
                    },
                    {
                        "trigger": "liquidity_stops_expanding",
                        "detail": "Invalidate the risk-on watch if liquidity turns mixed or contracting.",
                    },
                ]
            )
        elif posture == "defensive":
            triggers.extend(
                [
                    {
                        "trigger": "regime_relaxes_risk_pressure",
                        "detail": "Invalidate the risk-control watch if the regime rotates back toward a risk-on or soft-landing read.",
                    },
                    {
                        "trigger": "liquidity_re-expands",
                        "detail": "Invalidate the risk-control watch if liquidity turns sustainably expanding.",
                    },
                ]
            )
        else:
            triggers.append(
                {
                    "trigger": "directional_realignment",
                    "detail": "Invalidate the balanced watch if regime and liquidity realign decisively in either direction.",
                }
            )

        if rotation and rotation_style_allowed:
            triggers.append(
                {
                    "trigger": "rotation_loses_score_grade_authority",
                    "detail": "Any style confirmation should be removed if rotation evidence becomes proxy-only, taxonomy-only, or non-scoring.",
                }
            )
        return tuple(triggers)


def derive_market_decision_semantics(
    market_regime_synthesis: Mapping[str, Any] | Any,
    liquidity_impulse_synthesis: Mapping[str, Any] | Any,
    rotation_summary_evidence: Mapping[str, Any] | Any | None = None,
) -> MarketDecisionSemanticsResult:
    return MarketDecisionSemanticsService().derive(
        market_regime_synthesis,
        liquidity_impulse_synthesis,
        rotation_summary_evidence,
    )


def _coerce_payload(value: Mapping[str, Any] | Any | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    raise TypeError(f"Unsupported payload type for market decision semantics: {type(value)!r}")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    return ()


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = _text(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return default


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _clamp_int(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _confidence_label(value: int, posture: str) -> str:
    if posture == "data_insufficient":
        return "insufficient"
    if value >= 75:
        return "high"
    if value >= 55:
        return "medium"
    return "low"


def _regime_sign(regime: Mapping[str, Any]) -> float:
    primary = _text(regime.get("primaryRegime"))
    if primary in _OFFENSIVE_REGIMES:
        return _OFFENSIVE_REGIMES[primary]
    if primary in _DEFENSIVE_REGIMES:
        return _DEFENSIVE_REGIMES[primary]
    return 0.0


def _liquidity_sign(liquidity: Mapping[str, Any]) -> float:
    impulse = _text(liquidity.get("liquidityImpulse"))
    if impulse in _OFFENSIVE_LIQUIDITY:
        return _OFFENSIVE_LIQUIDITY[impulse]
    if impulse in _DEFENSIVE_LIQUIDITY:
        return _DEFENSIVE_LIQUIDITY[impulse]
    return 0.0


def _posture_from_signs(regime_sign: float, liquidity_sign: float) -> str:
    total = regime_sign + liquidity_sign
    if regime_sign * liquidity_sign < 0:
        return "neutral"
    if total >= 1.25:
        return "offensive"
    if total <= -1.25:
        return "defensive"
    return "neutral"


def _exposure_bias(posture: str) -> str:
    if posture == "offensive":
        return "risk_on_watch"
    if posture == "defensive":
        return "risk_control_watch"
    if posture == "neutral":
        return "balanced_watch"
    return "no_bias_data_insufficient"


def _merge_surface_items(*surfaces: tuple[str, Sequence[Any]]) -> tuple[dict[str, Any], ...]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for surface_name, items in surfaces:
        for raw_item in items:
            item = _mapping(raw_item)
            if not item:
                continue
            key = (_text(item.get("key")), _text(item.get("label")), surface_name)
            if key in seen:
                continue
            seen.add(key)
            merged.append({"surface": surface_name, **item})
    return tuple(merged)


def _score_grade_driver_count(drivers: Sequence[Any]) -> int:
    count = 0
    for raw_item in drivers:
        item = _mapping(raw_item)
        if not item:
            continue
        if _bool(item.get("observationOnly")):
            continue
        if not _bool(item.get("scoreContributionAllowed"), default=True):
            continue
        if "includedInScore" in item and not _bool(item.get("includedInScore"), default=True):
            continue
        if _bool(item.get("proxyOnly")):
            continue
        if _text(item.get("sourceTier")).lower() in _NON_SCORE_GRADE_SOURCE_TIERS:
            continue
        if _text(item.get("freshness")).lower() in _NON_SCORE_GRADE_FRESHNESS:
            continue
        if _text(item.get("trustLevel")).lower() in {"unavailable", "rejected"}:
            continue
        count += 1
    return count


def _rotation_style_allowed(rotation: Mapping[str, Any]) -> bool:
    if not rotation:
        return False
    if not _bool(rotation.get("sourceAuthorityAllowed")):
        return False
    if not _bool(rotation.get("scoreContributionAllowed"), default=True):
        return False
    if _text(rotation.get("evidenceQuality")).lower() in _NON_SCORE_GRADE_ROTATION_QUALITY:
        return False
    if _text(rotation.get("sourceTier")).lower() in _NON_SCORE_GRADE_SOURCE_TIERS:
        return False
    return True


def _derive_direction_readiness(
    regime: Mapping[str, Any],
    liquidity: Mapping[str, Any],
    rotation: Mapping[str, Any],
    posture: str,
    posture_confidence: PostureConfidence,
) -> MarketDirectionReadiness:
    score_grade: list[dict[str, Any]] = []
    observation_only: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for classification in (
        _classify_official_macro_readiness(regime, liquidity),
        _classify_liquidity_readiness(liquidity),
        _classify_rotation_or_risk_participation_readiness(regime, liquidity, rotation),
    ):
        if classification["status"] == "score_grade":
            score_grade.append(classification["item"])
        elif classification["status"] == "observation_only":
            observation_only.append(classification["item"])
        else:
            missing.append(classification["item"])

    blocking_reasons: list[str] = []
    for item in observation_only + missing:
        _append_unique(blocking_reasons, f"required_{item['pillar']}_not_score_grade")

    fallback_proxy_present = bool(_readiness_non_score_evidence_count(regime, liquidity) or observation_only)
    if fallback_proxy_present:
        _append_unique(blocking_reasons, "fallback_proxy_or_observation_only_evidence_present")
    if posture == "data_insufficient":
        _append_unique(blocking_reasons, "market_decision_semantics_data_insufficient")

    score_grade_count = len(score_grade)
    non_score_dominant = fallback_proxy_present and score_grade_count <= 1
    if score_grade_count == len(_READINESS_REQUIRED_PILLARS) and posture != "data_insufficient":
        status = "direction_ready"
        blocking_reasons = []
    elif score_grade_count == 0 or non_score_dominant:
        status = "data_insufficient"
        _append_unique(blocking_reasons, "no_meaningful_score_grade_pillars")
    else:
        status = "partial_context_only"

    return MarketDirectionReadiness(
        status=status,
        confidence_label=_direction_readiness_confidence_label(status, posture_confidence),
        score_grade_pillars=_readiness_bucket(score_grade),
        observation_only_pillars=_readiness_bucket(observation_only),
        missing_pillars=_readiness_bucket(missing),
        blocking_reasons=tuple(blocking_reasons),
        claim_boundaries=_direction_readiness_claim_boundaries(status),
    )


def _classify_official_macro_readiness(
    regime: Mapping[str, Any],
    liquidity: Mapping[str, Any],
) -> dict[str, Any]:
    pillar = "official_macro_rates_volatility"
    evidence = [
        item
        for item in _readiness_surface_items(regime, "market_regime_synthesis", ("topDrivers", "dataGaps"))
        + _readiness_surface_items(liquidity, "liquidity_impulse_synthesis", ("dominantDrivers", "dataGaps"))
        if _text(item.get("pillar")) in _OFFICIAL_MACRO_PILLARS
    ]
    score_grade = [
        item
        for item in evidence
        if _readiness_item_score_grade(item) and _readiness_item_official(item)
    ]
    return _readiness_classification(pillar, evidence, score_grade)


def _classify_liquidity_readiness(liquidity: Mapping[str, Any]) -> dict[str, Any]:
    pillar = "liquidity_conditions"
    quality = _mapping(liquidity.get("evidenceQuality"))
    drivers = _sequence(liquidity.get("dominantDrivers"))
    evidence = _readiness_surface_items(liquidity, "liquidity_impulse_synthesis", ("dominantDrivers", "dataGaps"))
    score_grade_driver_count = _readiness_score_grade_driver_count(drivers)
    liquidity_score_grade = (
        _text(liquidity.get("liquidityImpulse")) != "data_insufficient"
        and int(_float(quality.get("scoringPillarCount"))) >= 3
        and int(_float(quality.get("realScoringEvidenceCount"))) > 0
        and score_grade_driver_count >= 2
    )
    score_grade = [
        item
        for item in evidence
        if _text(item.get("sourceList")) == "dominantDrivers" and _readiness_item_score_grade(item)
    ]
    if liquidity_score_grade and not score_grade:
        score_grade = [
            {
                "surface": "liquidity_impulse_synthesis",
                "sourceList": "evidenceQuality",
                "key": "liquidity_impulse_synthesis:evidence_quality",
                "label": "Liquidity impulse synthesis",
                "reasonCode": "score_grade_evidence",
            }
        ]
    return _readiness_classification(pillar, evidence, score_grade)


def _classify_rotation_or_risk_participation_readiness(
    regime: Mapping[str, Any],
    liquidity: Mapping[str, Any],
    rotation: Mapping[str, Any],
) -> dict[str, Any]:
    pillar = "rotation_or_risk_participation"
    evidence = [
        item
        for item in _readiness_surface_items(regime, "market_regime_synthesis", ("topDrivers", "dataGaps"))
        + _readiness_surface_items(liquidity, "liquidity_impulse_synthesis", ("dominantDrivers", "dataGaps"))
        if _text(item.get("pillar")) in _RISK_PARTICIPATION_PILLARS
    ]
    if rotation:
        evidence.append({"surface": "rotation_summary", "sourceList": "summary", **dict(rotation)})

    score_grade = [
        item
        for item in evidence
        if (
            (item.get("surface") == "rotation_summary" and _rotation_readiness_allowed(item))
            or (
                item.get("surface") != "rotation_summary"
                and _readiness_item_score_grade(item)
            )
        )
    ]
    if not any(item.get("surface") == "rotation_summary" for item in score_grade):
        risk_participation_count = sum(1 for item in score_grade if item.get("surface") != "rotation_summary")
        if risk_participation_count < 2:
            score_grade = [item for item in score_grade if item.get("surface") == "rotation_summary"]
    return _readiness_classification(pillar, evidence, score_grade)


def _readiness_classification(
    pillar: str,
    evidence: Sequence[Mapping[str, Any]],
    score_grade: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if score_grade:
        return {
            "status": "score_grade",
            "item": _readiness_pillar_item(
                pillar,
                "score_grade_evidence",
                score_grade,
            ),
        }
    if evidence and not _readiness_evidence_only_missing_gaps(evidence):
        return {
            "status": "observation_only",
            "item": _readiness_pillar_item(
                pillar,
                _readiness_reason_code(evidence),
                evidence,
            ),
        }
    return {
        "status": "missing",
        "item": _readiness_pillar_item(
            pillar,
            "missing_scoring_evidence",
            (),
        ),
    }


def _readiness_evidence_only_missing_gaps(evidence: Sequence[Mapping[str, Any]]) -> bool:
    return bool(evidence) and all(
        _text(item.get("sourceList")) == "dataGaps"
        and _text(item.get("reason")) == "missing_scoring_evidence"
        for item in evidence
    )


def _readiness_pillar_item(
    pillar: str,
    reason_code: str,
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    refs = []
    for item in evidence[:3]:
        key = _text(item.get("key") or item.get("symbol") or item.get("id") or item.get("label"))
        label = _text(item.get("label") or item.get("name") or item.get("symbol") or key)
        if not key and not label:
            continue
        refs.append(
            {
                "key": key or label,
                "label": label or key,
                "surface": _text(item.get("surface")),
            }
        )
    return {
        "pillar": pillar,
        "label": _READINESS_REQUIRED_PILLARS[pillar],
        "reasonCode": reason_code,
        "evidenceRefs": refs,
    }


def _readiness_bucket(items: Sequence[Mapping[str, Any]]) -> DirectionReadinessBucket:
    return DirectionReadinessBucket(
        count=len(items),
        items=tuple(dict(item) for item in items[:_READINESS_MAX_ITEMS]),
    )


def _readiness_surface_items(
    payload: Mapping[str, Any],
    surface: str,
    keys: Sequence[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in keys:
        for raw_item in _sequence(payload.get(key)):
            item = _mapping(raw_item)
            if not item:
                continue
            items.append({"surface": surface, "sourceList": key, **item})
    return items


def _readiness_item_score_grade(item: Mapping[str, Any]) -> bool:
    if _text(item.get("sourceList")) == "dataGaps":
        return False
    if _bool(item.get("observationOnly")):
        return False
    if _bool(item.get("isFallback")) or _bool(item.get("isUnavailable")) or _bool(item.get("isPartial")):
        return False
    if not _bool(item.get("scoreContributionAllowed"), default=True):
        return False
    if "includedInScore" in item and not _bool(item.get("includedInScore"), default=True):
        return False
    if "sourceAuthorityAllowed" in item and not _bool(item.get("sourceAuthorityAllowed")):
        return False
    if _bool(item.get("proxyOnly")):
        return False

    source_tier = _text(item.get("sourceTier") or item.get("sourceType") or item.get("source")).lower()
    source = _text(item.get("source")).lower()
    freshness = _text(item.get("freshness")).lower()
    trust_level = _text(item.get("trustLevel")).lower()
    degradation_reason = _text(item.get("degradationReason") or item.get("sourceAuthorityReason")).lower()

    if source_tier in _NON_SCORE_GRADE_SOURCE_TIERS:
        return False
    if any(marker in source_tier or marker in source for marker in _READINESS_PROXY_SOURCE_MARKERS):
        return False
    if freshness in _READINESS_BLOCKED_FRESHNESS:
        return False
    if trust_level in _READINESS_BLOCKED_TRUST:
        return False
    if any(marker in degradation_reason for marker in _READINESS_DEGRADATION_MARKERS):
        return False
    return True


def _readiness_item_official(item: Mapping[str, Any]) -> bool:
    source_tier = _text(item.get("sourceTier") or item.get("sourceType")).lower()
    source = _text(item.get("source")).lower()
    return source_tier in _OFFICIAL_SOURCE_TIERS or source in _OFFICIAL_SOURCES


def _rotation_readiness_allowed(rotation: Mapping[str, Any]) -> bool:
    return _rotation_style_allowed(rotation) and _readiness_item_score_grade(rotation)


def _readiness_score_grade_driver_count(drivers: Sequence[Any]) -> int:
    return sum(1 for raw_item in drivers if _readiness_item_score_grade(_mapping(raw_item)))


def _readiness_non_score_evidence_count(
    regime: Mapping[str, Any],
    liquidity: Mapping[str, Any],
) -> int:
    regime_quality = _mapping(regime.get("evidenceQuality"))
    liquidity_quality = _mapping(liquidity.get("evidenceQuality"))
    return (
        int(_float(regime_quality.get("observationOnlyEvidenceCount")))
        + int(_float(regime_quality.get("scoreBlockedEvidenceCount")))
        + int(_float(liquidity_quality.get("observationOnlyEvidenceCount")))
        + int(_float(liquidity_quality.get("scoreBlockedEvidenceCount")))
        + int(_float(liquidity_quality.get("proxyOnlyScoringCount")))
    )


def _readiness_reason_code(evidence: Sequence[Mapping[str, Any]]) -> str:
    for item in evidence:
        if _bool(item.get("observationOnly")):
            return "observation_only_evidence"
        if not _bool(item.get("scoreContributionAllowed"), default=True):
            return "score_contribution_not_allowed"
        if "includedInScore" in item and not _bool(item.get("includedInScore"), default=True):
            return "score_contribution_not_allowed"
        if "sourceAuthorityAllowed" in item and not _bool(item.get("sourceAuthorityAllowed")):
            return "source_authority_not_allowed"
        if _bool(item.get("proxyOnly")):
            return "fallback_or_proxy_evidence"
        if _bool(item.get("isFallback")):
            return "fallback_or_proxy_evidence"
        if _bool(item.get("isUnavailable")):
            return "unavailable_evidence"
        if _bool(item.get("isPartial")):
            return "partial_evidence"
        freshness = _text(item.get("freshness")).lower()
        if freshness in _READINESS_BLOCKED_FRESHNESS:
            return "freshness_not_ready"
        source_tier = _text(item.get("sourceTier") or item.get("sourceType") or item.get("source")).lower()
        source = _text(item.get("source")).lower()
        if source_tier in _NON_SCORE_GRADE_SOURCE_TIERS or any(
            marker in source_tier or marker in source for marker in _READINESS_PROXY_SOURCE_MARKERS
        ):
            return "fallback_or_proxy_evidence"
    return "not_score_grade_evidence"


def _direction_readiness_confidence_label(
    status: str,
    posture_confidence: PostureConfidence,
) -> str:
    if status == "data_insufficient":
        return "insufficient"
    if status == "partial_context_only":
        return "low"
    if posture_confidence.label == "high":
        return "high"
    return "medium"


def _direction_readiness_claim_boundaries(status: str) -> tuple[dict[str, Any], ...]:
    return (
        {
            "claim": "market_direction_readiness_context",
            "allowed": status != "data_insufficient",
            "reasonCode": status,
            "detail": "Readiness describes evidence coverage and source quality only.",
        },
        {
            "claim": "trade_instruction",
            "allowed": False,
            "reasonCode": "not_investment_advice",
            "detail": "Readiness is not an execution instruction.",
        },
        {
            "claim": "allocation_or_suitability_guidance",
            "allowed": False,
            "reasonCode": "not_investment_advice",
            "detail": "Readiness does not provide allocation or suitability guidance.",
        },
    )


def _claim_boundaries(
    posture: str,
    posture_confidence: PostureConfidence,
    has_style_tilts: bool,
) -> tuple[dict[str, Any], ...]:
    boundaries: list[dict[str, Any]] = []

    if posture == "data_insufficient":
        boundaries.append(
            {
                "claim": "observational_posture_watch",
                "allowed": False,
                "reasonCode": "insufficient_score_grade_evidence",
                "detail": "No posture watch is supportable without score-grade regime and liquidity evidence.",
            }
        )
        boundaries.append(
            {
                "claim": "style_tilt_watch",
                "allowed": False,
                "reasonCode": "insufficient_score_grade_evidence",
                "detail": "Style tilt watch language is blocked until score-grade evidence improves.",
            }
        )
    else:
        boundaries.append(
            {
                "claim": "observational_posture_watch",
                "allowed": True,
                "reasonCode": "watch_only_language",
                "detail": "Only observational posture watch language is allowed; this is not a trading instruction.",
            }
        )
        if has_style_tilts:
            boundaries.append(
                {
                    "claim": "style_tilt_watch",
                    "allowed": True,
                    "reasonCode": "watch_only_language",
                    "detail": "Style tilts remain observational and do not imply position sizing or execution advice.",
                }
            )
        else:
            boundaries.append(
                {
                    "claim": "style_tilt_watch",
                    "allowed": False,
                    "reasonCode": "tentative_bias_only" if posture_confidence.label == "low" else "no_style_tilt_supported",
                    "detail": "Style tilt language is capped because the current signal quality is still tentative.",
                }
            )

    for claim in ("direct_trade_action", "position_size_guidance", "personalized_suitability"):
        boundaries.append(
            {
                "claim": claim,
                "allowed": False,
                "reasonCode": "not_investment_advice",
                "detail": "This DTO never outputs buy, sell, add, reduce, or sizing advice.",
            }
        )
    return tuple(boundaries)
