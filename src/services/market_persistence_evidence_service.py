# -*- coding: utf-8 -*-
"""Pure historical persistence evidence from caller-supplied snapshots.

This module is intentionally inert: it does not import provider clients, read
configuration, call networks, mutate caches, or wire the result into runtime
Market Intelligence surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


MARKET_PERSISTENCE_EVIDENCE_VERSION = "market_persistence_evidence_v1"

PERSISTENCE_WINDOWS: tuple[str, ...] = ("latest", "1d", "5d", "20d")
PERSISTENCE_STATUSES: tuple[str, ...] = (
    "persistent",
    "emerging",
    "fading",
    "volatile",
    "insufficient_history",
    "data_insufficient",
)

_WINDOW_TARGET_DAYS = {
    "latest": 0.0,
    "1d": 1.0,
    "5d": 5.0,
    "20d": 20.0,
}

_SOURCE_TIER_WEIGHTS = {
    "official_public": 1.0,
    "exchange_public": 1.0,
    "exchange": 1.0,
    "broker_authorized": 0.95,
    "authorized": 0.95,
    "official_or_authorized": 0.9,
    "authorized_licensed_feed": 0.9,
    "tier_1_configured": 0.9,
    "cache_snapshot": 0.76,
    "snapshot": 0.74,
    "local_snapshot": 0.74,
    "public_proxy": 0.62,
    "unofficial_public_api": 0.52,
    "unofficial_proxy": 0.48,
    "third_party_free_api": 0.46,
    "static_fallback": 0.24,
    "fallback_static": 0.24,
    "public_web_fallback": 0.24,
    "synthetic": 0.15,
    "synthetic_fixture": 0.15,
    "unavailable": 0.0,
    "missing": 0.0,
}

_TRUST_WEIGHTS = {
    "high": 1.0,
    "active": 1.0,
    "reliable": 1.0,
    "verified": 1.0,
    "score_grade_when_configured": 0.92,
    "usable": 0.82,
    "usable_with_caution": 0.72,
    "medium": 0.68,
    "partial": 0.52,
    "degraded": 0.44,
    "weak": 0.3,
    "unavailable": 0.0,
    "rejected": 0.0,
    "unknown": 0.55,
}

_FRESHNESS_WEIGHTS = {
    "live": 1.0,
    "fresh": 1.0,
    "cached": 0.84,
    "delayed": 0.74,
    "partial": 0.58,
    "stale": 0.34,
    "fallback": 0.24,
    "mock": 0.15,
    "synthetic": 0.15,
    "unavailable": 0.0,
    "error": 0.0,
    "unknown": 0.55,
}

_REJECTED_REASON_MARKERS = (
    "source_authority_router_rejected",
    "authority_rejected",
    "provider_unavailable",
    "unavailable",
    "missing",
    "malformed",
    "rejected",
)


@dataclass(frozen=True, slots=True)
class MarketPersistenceEvidenceSnapshot:
    key: str
    surface: str
    metric: str
    value: float | str | None = None
    score: float | None = None
    regime_label: str | None = None
    state_label: str | None = None
    signal_label: str | None = None
    as_of: str | None = None
    updated_at: str | None = None
    source: str = ""
    source_tier: str = ""
    trust_level: str = "unknown"
    freshness: str = "unknown"
    observation_only: bool = False
    score_contribution_allowed: bool = True
    degradation_reason: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MarketPersistenceEvidenceSnapshot":
        return cls(
            key=_text(_get(value, "key")),
            surface=_text(_get(value, "surface")) or "generic",
            metric=_text(_get(value, "metric")),
            value=_get(value, "value"),
            score=_optional_float(_get(value, "score")),
            regime_label=_optional_text(_get(value, "regime_label", "regimeLabel", "regime")),
            state_label=_optional_text(_get(value, "state_label", "stateLabel", "state")),
            signal_label=_optional_text(_get(value, "signal_label", "signalLabel", "signal")),
            as_of=_optional_text(_get(value, "as_of", "asOf")),
            updated_at=_optional_text(_get(value, "updated_at", "updatedAt")),
            source=_text(_get(value, "source")),
            source_tier=_text(_get(value, "source_tier", "sourceTier")),
            trust_level=_text(_get(value, "trust_level", "trustLevel")) or "unknown",
            freshness=_text(_get(value, "freshness")) or "unknown",
            observation_only=_bool(_get(value, "observation_only", "observationOnly")),
            score_contribution_allowed=_bool(
                _get(value, "score_contribution_allowed", "scoreContributionAllowed", default=True)
            ),
            degradation_reason=_optional_text(_get(value, "degradation_reason", "degradationReason")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "surface": self.surface,
            "metric": self.metric,
            "value": self.value,
            "score": self.score,
            "regimeLabel": self.regime_label,
            "stateLabel": self.state_label,
            "signalLabel": self.signal_label,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "source": self.source,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshness": self.freshness,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "degradationReason": self.degradation_reason,
        }


@dataclass(frozen=True, slots=True)
class MarketPersistenceEvidenceResult:
    persistence_status: str
    windows: tuple[str, ...]
    evidence_items: tuple[dict[str, Any], ...]
    trend_direction: str
    acceleration: str
    consistency_score: float
    confidence: float
    confidence_label: str
    data_gaps: tuple[dict[str, Any], ...]
    counter_evidence: tuple[dict[str, Any], ...]
    narrative_bullets: tuple[str, ...]
    evidence_quality: dict[str, Any]
    not_investment_advice: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "persistenceStatus": self.persistence_status,
            "windows": list(self.windows),
            "evidenceItems": [dict(item) for item in self.evidence_items],
            "trendDirection": self.trend_direction,
            "acceleration": self.acceleration,
            "consistencyScore": self.consistency_score,
            "confidence": self.confidence,
            "confidenceLabel": self.confidence_label,
            "dataGaps": [dict(item) for item in self.data_gaps],
            "counterEvidence": [dict(item) for item in self.counter_evidence],
            "narrativeBullets": list(self.narrative_bullets),
            "evidenceQuality": dict(self.evidence_quality),
            "notInvestmentAdvice": self.not_investment_advice,
        }


@dataclass(frozen=True, slots=True)
class _ScoredSnapshot:
    item: MarketPersistenceEvidenceSnapshot
    score: float
    weight: float
    window: str | None
    timestamp: datetime | None
    discount_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _WindowEvidence:
    window: str
    score: float
    weight: float
    label: str | None
    items: tuple[_ScoredSnapshot, ...]


class MarketPersistenceEvidenceService:
    """Deterministic persistence classifier for injected historical snapshots."""

    min_history_windows = 2
    min_scoring_weight = 0.2

    def synthesize(
        self,
        snapshots: Iterable[MarketPersistenceEvidenceSnapshot | Mapping[str, Any]],
    ) -> MarketPersistenceEvidenceResult:
        evidence = tuple(_coerce_snapshot(item) for item in snapshots)
        scored, data_gaps = self._score_snapshots(evidence)
        windows = self._window_evidence(scored)
        window_names = tuple(window.window for window in windows)
        evidence_items = self._evidence_items(windows)
        trend_direction = _trend_direction(windows)
        acceleration = _acceleration(windows)
        consistency_score = _consistency_score(windows)
        counter_evidence = self._counter_evidence(windows)
        evidence_quality = self._evidence_quality(evidence, scored, windows, data_gaps)
        persistence_status = self._persistence_status(
            windows,
            trend_direction,
            acceleration,
            consistency_score,
            evidence_quality,
            data_gaps,
        )
        if persistence_status == "insufficient_history":
            data_gaps.append(
                {
                    "key": "history",
                    "label": "Need at least two score-eligible historical windows",
                    "reason": "insufficient_history",
                    "availableWindows": list(window_names),
                }
            )

        confidence = _confidence(persistence_status, consistency_score, evidence_quality, counter_evidence)
        confidence_label = _confidence_label(confidence, persistence_status)
        narrative_bullets = _narrative_bullets(
            persistence_status,
            window_names,
            trend_direction,
            acceleration,
            consistency_score,
            confidence_label,
            data_gaps,
            counter_evidence,
        )

        return MarketPersistenceEvidenceResult(
            persistence_status=persistence_status,
            windows=window_names,
            evidence_items=evidence_items,
            trend_direction=trend_direction,
            acceleration=acceleration,
            consistency_score=round(consistency_score, 3),
            confidence=round(confidence, 3),
            confidence_label=confidence_label,
            data_gaps=tuple(data_gaps),
            counter_evidence=counter_evidence,
            narrative_bullets=narrative_bullets,
            evidence_quality=evidence_quality,
        )

    def _score_snapshots(
        self,
        evidence: Sequence[MarketPersistenceEvidenceSnapshot],
    ) -> tuple[tuple[_ScoredSnapshot, ...], list[dict[str, Any]]]:
        scored: list[_ScoredSnapshot] = []
        data_gaps: list[dict[str, Any]] = []
        timestamps = tuple(_timestamp(item) for item in evidence)
        latest_timestamp = max((item for item in timestamps if item is not None), default=None)

        for item, timestamp in zip(evidence, timestamps):
            score = _score_value(item)
            if score is None:
                data_gaps.append(_data_gap(item, "missing_score_or_value"))
                continue

            weight, discount_reasons = _quality_weight(item)
            if weight <= 0.0:
                data_gaps.append(_data_gap(item, discount_reasons[0] if discount_reasons else "unscorable"))
                continue

            scored.append(
                _ScoredSnapshot(
                    item=item,
                    score=score,
                    weight=weight,
                    window=_window_name(timestamp, latest_timestamp),
                    timestamp=timestamp,
                    discount_reasons=discount_reasons,
                )
            )

        return tuple(scored), data_gaps

    @staticmethod
    def _window_evidence(scored: Sequence[_ScoredSnapshot]) -> tuple[_WindowEvidence, ...]:
        result: list[_WindowEvidence] = []
        for window in PERSISTENCE_WINDOWS:
            candidates = tuple(item for item in scored if item.window == window)
            if not candidates:
                continue
            total_weight = sum(item.weight for item in candidates)
            if total_weight <= 0.0:
                continue
            score = sum(item.score * item.weight for item in candidates) / total_weight
            result.append(
                _WindowEvidence(
                    window=window,
                    score=_clamp(score, -1.0, 1.0),
                    weight=total_weight,
                    label=_dominant_label(candidates),
                    items=candidates,
                )
            )
        return tuple(result)

    @staticmethod
    def _evidence_items(windows: Sequence[_WindowEvidence]) -> tuple[dict[str, Any], ...]:
        items: list[dict[str, Any]] = []
        for window in windows:
            for scored in window.items:
                payload = scored.item.to_dict()
                payload.update(
                    {
                        "window": window.window,
                        "normalizedScore": round(scored.score, 3),
                        "qualityWeight": round(scored.weight, 3),
                        "discountReasons": list(scored.discount_reasons),
                    }
                )
                items.append(payload)
        return tuple(items)

    @staticmethod
    def _counter_evidence(windows: Sequence[_WindowEvidence]) -> tuple[dict[str, Any], ...]:
        if len(windows) < 2:
            return ()
        latest = windows[0]
        latest_sign = _sign_bucket(latest.score)
        counters: list[dict[str, Any]] = []
        prior_scores = [window.score for window in windows[1:]]
        prior_average = sum(prior_scores) / len(prior_scores)
        prior_sign = _sign_bucket(prior_average)
        if latest_sign and prior_sign and latest_sign != prior_sign:
            counters.append(
                {
                    "window": "prior",
                    "reason": "latest_conflicts_with_prior_average",
                    "latestScore": round(latest.score, 3),
                    "priorAverageScore": round(prior_average, 3),
                }
            )
        if abs(latest.score) + 0.25 < abs(prior_average):
            counters.append(
                {
                    "window": "prior",
                    "reason": "latest_weaker_than_prior_average",
                    "latestScore": round(latest.score, 3),
                    "priorAverageScore": round(prior_average, 3),
                }
            )
        for window in windows[1:]:
            sign = _sign_bucket(window.score)
            if latest_sign and sign and sign != latest_sign:
                counters.append(
                    {
                        "window": window.window,
                        "reason": "window_direction_conflict",
                        "latestScore": round(latest.score, 3),
                        "windowScore": round(window.score, 3),
                    }
                )
        labels = {window.label for window in windows if window.label and window.label != "neutral"}
        if len(labels) > 1:
            counters.append(
                {
                    "window": "multi_window",
                    "reason": "state_label_conflict",
                    "labels": sorted(labels),
                }
            )
        return tuple(counters)

    @staticmethod
    def _evidence_quality(
        evidence: Sequence[MarketPersistenceEvidenceSnapshot],
        scored: Sequence[_ScoredSnapshot],
        windows: Sequence[_WindowEvidence],
        data_gaps: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        total_weight = sum(item.weight for item in scored)
        average_weight = total_weight / len(scored) if scored else 0.0
        return {
            "version": MARKET_PERSISTENCE_EVIDENCE_VERSION,
            "inputCount": len(evidence),
            "scoringEvidenceCount": len(scored),
            "availableWindowCount": len(windows),
            "availableWindows": [window.window for window in windows],
            "scoreContributingWeight": round(total_weight, 3),
            "averageEvidenceWeight": round(average_weight, 3),
            "discountedEvidenceCount": sum(1 for item in scored if item.discount_reasons),
            "observationOnlyEvidenceCount": sum(1 for item in evidence if item.observation_only),
            "scoreBlockedEvidenceCount": sum(1 for item in evidence if not item.score_contribution_allowed),
            "dataGapCount": len(data_gaps),
        }

    def _persistence_status(
        self,
        windows: Sequence[_WindowEvidence],
        trend_direction: str,
        acceleration: str,
        consistency_score: float,
        evidence_quality: Mapping[str, Any],
        data_gaps: Sequence[Mapping[str, Any]],
    ) -> str:
        if not windows or float(evidence_quality["scoreContributingWeight"]) < self.min_scoring_weight:
            return "data_insufficient"
        if len(windows) < self.min_history_windows:
            return "insufficient_history"
        if all(gap.get("reason") == "score_contribution_not_allowed" for gap in data_gaps) and data_gaps:
            return "data_insufficient"

        scores = [window.score for window in windows]
        latest = scores[0]
        prior = scores[1:]
        prior_average = sum(prior) / len(prior)
        sign_changes = _sign_changes(scores)

        if abs(latest) >= 0.45 and abs(prior_average) < 0.28 and trend_direction == "strengthening":
            return "emerging"
        if abs(latest) <= 0.32 and abs(prior_average) >= 0.5 and trend_direction == "weakening":
            return "fading"
        if sign_changes >= 2 or consistency_score < 0.38:
            return "volatile"
        if acceleration == "decelerating" and abs(latest) + 0.25 < abs(prior_average):
            return "fading"
        if consistency_score >= 0.68 and abs(latest) >= 0.35:
            return "persistent"
        if trend_direction == "strengthening" and abs(latest) >= 0.4:
            return "emerging"
        if trend_direction == "weakening":
            return "fading"
        return "volatile"


def synthesize_market_persistence(
    snapshots: Iterable[MarketPersistenceEvidenceSnapshot | Mapping[str, Any]],
) -> MarketPersistenceEvidenceResult:
    return MarketPersistenceEvidenceService().synthesize(snapshots)


def _coerce_snapshot(value: MarketPersistenceEvidenceSnapshot | Mapping[str, Any]) -> MarketPersistenceEvidenceSnapshot:
    if isinstance(value, MarketPersistenceEvidenceSnapshot):
        return value
    return MarketPersistenceEvidenceSnapshot.from_dict(value)


def _quality_weight(item: MarketPersistenceEvidenceSnapshot) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []
    if not item.score_contribution_allowed:
        return 0.0, ("score_contribution_not_allowed",)

    degradation = (item.degradation_reason or "").lower()
    if any(marker in degradation for marker in _REJECTED_REASON_MARKERS):
        return 0.0, ("unavailable_or_rejected",)

    source_tier = (item.source_tier or "unknown").lower()
    trust_level = (item.trust_level or "unknown").lower()
    freshness = (item.freshness or "unknown").lower()
    source_weight = _lookup_weight(_SOURCE_TIER_WEIGHTS, source_tier, default=0.55)
    trust_weight = _lookup_weight(_TRUST_WEIGHTS, trust_level, default=0.55)
    freshness_weight = _lookup_weight(_FRESHNESS_WEIGHTS, freshness, default=0.55)
    if source_weight <= 0.0 or trust_weight <= 0.0 or freshness_weight <= 0.0:
        return 0.0, ("unavailable_or_rejected",)

    weight = source_weight * trust_weight * freshness_weight
    if item.observation_only:
        weight *= 0.58
        reasons.append("observation_only_discount")
    if source_weight < 0.7:
        reasons.append("source_tier_discount")
    if trust_weight < 0.75:
        reasons.append("trust_discount")
    if freshness_weight < 0.8:
        reasons.append("freshness_discount")
    return _clamp(weight, 0.0, 1.0), tuple(reasons)


def _score_value(item: MarketPersistenceEvidenceSnapshot) -> float | None:
    number = _optional_float(item.score)
    if number is None:
        number = _optional_float(item.value)
    if number is None:
        return None
    if abs(number) > 1.0:
        number = number / 100.0
    return _clamp(number, -1.0, 1.0)


def _timestamp(item: MarketPersistenceEvidenceSnapshot) -> datetime | None:
    for value in (item.as_of, item.updated_at):
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _window_name(timestamp: datetime | None, latest_timestamp: datetime | None) -> str | None:
    if timestamp is None or latest_timestamp is None:
        return None
    age_days = abs((latest_timestamp - timestamp).total_seconds()) / 86400.0
    closest = min(PERSISTENCE_WINDOWS, key=lambda name: abs(age_days - _WINDOW_TARGET_DAYS[name]))
    tolerance = 0.35 if closest in {"latest", "1d"} else 1.25
    if abs(age_days - _WINDOW_TARGET_DAYS[closest]) <= tolerance:
        return closest
    return None


def _dominant_label(candidates: Sequence[_ScoredSnapshot]) -> str | None:
    weighted: dict[str, float] = {}
    for item in candidates:
        label = item.item.signal_label or item.item.state_label or item.item.regime_label
        if not label:
            continue
        weighted[label] = weighted.get(label, 0.0) + item.weight
    if not weighted:
        return None
    return max(weighted.items(), key=lambda value: value[1])[0]


def _trend_direction(windows: Sequence[_WindowEvidence]) -> str:
    if len(windows) < 2:
        return "unknown"
    latest = windows[0].score
    prior_average = sum(window.score for window in windows[1:]) / (len(windows) - 1)
    if _has_mixed_signs(window.score for window in windows):
        return "mixed"
    delta = abs(latest) - abs(prior_average)
    if delta > 0.12:
        return "strengthening"
    if delta < -0.12:
        return "weakening"
    return "stable"


def _acceleration(windows: Sequence[_WindowEvidence]) -> str:
    if len(windows) < 3:
        return "unknown"
    scores = [abs(window.score) for window in windows]
    near_delta = scores[0] - scores[1]
    far_delta = scores[1] - scores[-1]
    signed_scores = [window.score for window in windows]
    if _has_mixed_signs(signed_scores):
        return "mixed"
    if near_delta - far_delta > 0.12:
        return "accelerating"
    if near_delta - far_delta < -0.12:
        return "decelerating"
    return "stable"


def _consistency_score(windows: Sequence[_WindowEvidence]) -> float:
    if not windows:
        return 0.0
    scores = [window.score for window in windows]
    signs = [_sign_bucket(score) for score in scores if _sign_bucket(score)]
    sign_consistency = max((signs.count(sign) for sign in set(signs)), default=0) / len(scores)
    label_counts: dict[str, int] = {}
    for window in windows:
        if window.label and window.label != "neutral":
            label_counts[window.label] = label_counts.get(window.label, 0) + 1
    label_consistency = max(label_counts.values(), default=0) / len(windows) if label_counts else sign_consistency
    spread = max(scores) - min(scores)
    magnitude_stability = _clamp(1.0 - (spread / 2.0), 0.0, 1.0)
    sign_change_penalty = min(_sign_changes(scores) * 0.05, 0.2)
    return _clamp(
        (sign_consistency * 0.45) + (label_consistency * 0.35) + (magnitude_stability * 0.2) - sign_change_penalty,
        0.0,
        1.0,
    )


def _confidence(
    status: str,
    consistency_score: float,
    evidence_quality: Mapping[str, Any],
    counter_evidence: Sequence[Mapping[str, Any]],
) -> float:
    if status in {"data_insufficient", "insufficient_history"}:
        return 0.0
    coverage = min(float(evidence_quality["availableWindowCount"]) / len(PERSISTENCE_WINDOWS), 1.0)
    quality = float(evidence_quality["averageEvidenceWeight"])
    confidence = (consistency_score * 0.38) + (coverage * 0.28) + (quality * 0.34)
    confidence -= min(len(counter_evidence) * 0.08, 0.24)
    if status == "volatile":
        confidence *= 0.78
    return _clamp(confidence, 0.0, 1.0)


def _confidence_label(confidence: float, status: str) -> str:
    if status in {"data_insufficient", "insufficient_history"} or confidence < 0.2:
        return "insufficient"
    if confidence >= 0.72:
        return "high"
    if confidence >= 0.48:
        return "medium"
    return "low"


def _narrative_bullets(
    status: str,
    windows: Sequence[str],
    trend_direction: str,
    acceleration: str,
    consistency_score: float,
    confidence_label: str,
    data_gaps: Sequence[Mapping[str, Any]],
    counter_evidence: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    bullets = [
        (
            f"Persistence status is {status} across "
            f"{', '.join(windows) if windows else 'no score-eligible windows'}."
        ),
        f"Trend is {trend_direction}; acceleration is {acceleration}.",
        f"Consistency score is {round(consistency_score, 2)} with {confidence_label} confidence.",
    ]
    if data_gaps:
        bullets.append(f"{len(data_gaps)} data gap(s) kept explicit instead of filling missing history.")
    if counter_evidence:
        bullets.append(f"{len(counter_evidence)} counter-evidence item(s) show conflicting windows or labels.")
    return tuple(bullets)


def _data_gap(item: MarketPersistenceEvidenceSnapshot, reason: str) -> dict[str, Any]:
    return {
        "key": item.key,
        "surface": item.surface,
        "metric": item.metric,
        "reason": reason,
        "source": item.source,
        "sourceTier": item.source_tier,
        "trustLevel": item.trust_level,
        "freshness": item.freshness,
        "observationOnly": item.observation_only,
        "scoreContributionAllowed": item.score_contribution_allowed,
        "degradationReason": item.degradation_reason,
        "asOf": item.as_of,
        "updatedAt": item.updated_at,
    }


def _sign_changes(scores: Sequence[float]) -> int:
    signs = [_sign_bucket(score) for score in scores]
    return sum(1 for left, right in zip(signs, signs[1:]) if left and right and left != right)


def _has_mixed_signs(scores: Iterable[float]) -> bool:
    signs = {_sign_bucket(score) for score in scores}
    signs.discard("")
    return len(signs) > 1


def _sign_bucket(score: float) -> str:
    if score >= 0.25:
        return "positive"
    if score <= -0.25:
        return "negative"
    return ""


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _get(value: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return default


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lookup_weight(weights: Mapping[str, float], key: str, *, default: float) -> float:
    if key in weights:
        return weights[key]
    for marker, weight in weights.items():
        if marker and marker in key:
            return weight
    return default


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
