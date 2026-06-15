# -*- coding: utf-8 -*-
"""Deterministic market decision cockpit aggregate service.

This service only composes already-normalized market regime, research radar,
and options observation payloads. It does not fetch providers, mutate caches,
rank scanners, or change any protected-domain semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from src.services.market_overview_service import MarketOverviewService
from src.services.market_regime_decision_engine import build_market_regime_decision
from src.services.options_market_structure_observation import build_options_market_structure_observation
from src.services.research_radar_candidate_engine import build_research_radar_candidate_queue


SCHEMA_VERSION = "market_decision_cockpit.v1"
NO_ADVICE_DISCLOSURE = "Decision support only; not investment advice or trading instruction."
_RESEARCH_EMPTY_REASON = "research_candidates_unavailable"
_OPTION_CHAIN_EMPTY_REASON = "option_chain_unavailable"
_MARKET_REGIME_LOW_CONFIDENCE_REASON = "market_regime_low_confidence"


class MarketDecisionCockpitService:
    """Compose market regime, research preview, and options observation."""

    def __init__(
        self,
        *,
        market_overview_service: MarketOverviewService | None = None,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self._market_overview_service = market_overview_service or MarketOverviewService()
        self._now_provider = now_provider or self._default_now_provider

    def get_decision_cockpit(
        self,
        *,
        actor: Mapping[str, Any] | None = None,
        market_inputs: Mapping[str, Any] | None = None,
        market_regime_decision: Mapping[str, Any] | None = None,
        research_candidates: Sequence[Mapping[str, Any]] | None = None,
        option_contracts: Sequence[Any] | None = None,
        option_spot: float | int | str | None = None,
    ) -> dict[str, Any]:
        generated_at = self._now_provider()
        decision = self._build_market_regime_decision(
            actor=actor,
            market_inputs=market_inputs,
            market_regime_decision=market_regime_decision,
        )
        research_preview = self._build_research_queue_preview(
            decision,
            research_candidates=research_candidates,
        )
        options_status = self._build_options_structure_status(
            option_contracts=option_contracts,
            option_spot=option_spot,
        )

        return {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": generated_at,
            "marketRegimeDecision": decision,
            "researchQueuePreview": research_preview,
            "optionsStructureStatus": options_status,
            "cockpitSummary": self._build_cockpit_summary(decision, research_preview, options_status),
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "dataQuality": self._build_data_quality(decision, research_preview, options_status),
        }

    @staticmethod
    def _default_now_provider() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _build_market_regime_decision(
        self,
        *,
        actor: Mapping[str, Any] | None,
        market_inputs: Mapping[str, Any] | None,
        market_regime_decision: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(market_regime_decision, Mapping):
            payload = dict(market_regime_decision)
        elif isinstance(market_inputs, Mapping):
            payload = build_market_regime_decision(market_inputs)
        else:
            payload = self._market_overview_decision(actor=actor)

        payload.setdefault("invalidationConditions", _invalidation_conditions(payload))
        return payload

    def _market_overview_decision(self, *, actor: Mapping[str, Any] | None) -> dict[str, Any]:
        try:
            payload = self._market_overview_service.get_market_regime_decision(
                actor=dict(actor) if isinstance(actor, Mapping) else None
            )
            if isinstance(payload, Mapping):
                return dict(payload)
        except Exception:
            pass

        fallback = build_market_regime_decision({})
        fallback["inputSource"] = "market_decision_cockpit_fallback_inputs"
        fallback["updatedAt"] = self._default_now_provider()
        fallback["invalidationConditions"] = _invalidation_conditions(fallback)
        return fallback

    def _build_research_queue_preview(
        self,
        market_regime_decision: Mapping[str, Any],
        *,
        research_candidates: Sequence[Mapping[str, Any]] | None,
    ) -> dict[str, Any]:
        candidates = list(research_candidates or [])
        queue = build_research_radar_candidate_queue(
            candidates,
            market_regime_context=market_regime_decision,
        )
        research_queue = list(queue.get("researchQueue") or [])
        summary = queue.get("summary") if isinstance(queue.get("summary"), Mapping) else {}
        preview: dict[str, Any] = {
            "topCandidates": research_queue[:3],
            "queueQuality": summary.get("queueQuality", "thin"),
            "evidenceGaps": list(summary.get("evidenceGaps") or []),
            "previewOnly": True,
        }
        if not candidates or not research_queue:
            preview["degradedState"] = {
                "status": "empty",
                "reasonCodes": [_RESEARCH_EMPTY_REASON],
            }
        return preview

    def _build_options_structure_status(
        self,
        *,
        option_contracts: Sequence[Any] | None,
        option_spot: float | int | str | None,
    ) -> dict[str, Any]:
        contracts = list(option_contracts or [])
        prerequisites_met = bool(contracts) and option_spot is not None
        observation = build_options_market_structure_observation(
            contracts,
            spot=option_spot,
            methodology_approved=prerequisites_met,
            coverage_thresholds_defined=prerequisites_met,
            provider_authority_verified=prerequisites_met,
            redistribution_rights_verified=prerequisites_met,
            decision_use_rights_verified=prerequisites_met,
            deliverable_handling_reviewed=prerequisites_met,
        )

        observation_state = str(observation.get("observationState") or "blocked")
        if observation_state == "ready":
            gamma_status = "ready_observation"
        elif observation_state == "degraded":
            gamma_status = "degraded"
        else:
            gamma_status = "unavailable"

        blocked_reason_codes = list(observation.get("blockedReasonCodes") or [])
        if gamma_status == "unavailable" and _OPTION_CHAIN_EMPTY_REASON not in blocked_reason_codes:
            blocked_reason_codes.insert(0, _OPTION_CHAIN_EMPTY_REASON)

        return {
            "gammaEvidenceStatus": gamma_status,
            "observationOnly": bool(observation.get("observationOnly", True)),
            "decisionGrade": False,
            "missingEvidence": list(observation.get("missingEvidence") or []),
            "blockedReasonCodes": blocked_reason_codes,
        }

    def _build_cockpit_summary(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime = str(market_regime_decision.get("regime") or "lowConfidence")
        confidence = str(market_regime_decision.get("confidence") or "low")
        priorities = _mapping(market_regime_decision.get("researchPriorities"))
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        evidence_gaps = list(research_preview.get("evidenceGaps") or [])
        blocked_reasons = list(options_status.get("blockedReasonCodes") or [])

        what_to_watch = list(priorities.get("watchToday") or [])
        what_to_watch.extend(priorities.get("investigateNext") or [])
        if not what_to_watch:
            what_to_watch.append("Await stronger market evidence before tightening the read.")

        confidence_limits = list(regime_quality.get("confidenceCapReasons") or [])
        confidence_limits.extend(evidence_gaps)
        confidence_limits.extend(blocked_reasons)

        return {
            "whatChanged": [
                f"Regime resolved to {regime} with {confidence} confidence.",
                f"Research preview quality is {research_preview.get('queueQuality', 'thin')}.",
            ],
            "whyItMatters": [
                "This cockpit keeps regime, research triage, and options observation in one read-only view.",
            ],
            "whatToWatch": what_to_watch,
            "confidenceLimits": _dedupe(confidence_limits),
        }

    def _build_data_quality(
        self,
        market_regime_decision: Mapping[str, Any],
        research_preview: Mapping[str, Any],
        options_status: Mapping[str, Any],
    ) -> dict[str, Any]:
        regime_quality = _mapping(market_regime_decision.get("dataQuality"))
        reason_codes = list(market_regime_decision.get("missingEvidence") or [])
        if str(market_regime_decision.get("confidence") or "").lower() == "low":
            reason_codes.append(_MARKET_REGIME_LOW_CONFIDENCE_REASON)
        if not research_preview.get("topCandidates"):
            reason_codes.append(_RESEARCH_EMPTY_REASON)
        if options_status.get("gammaEvidenceStatus") == "unavailable":
            reason_codes.append(_OPTION_CHAIN_EMPTY_REASON)
        reason_codes.append("options_observation_only")

        available_driver_count = int(regime_quality.get("availableDriverCount") or 0)
        status = "blocked" if (
            available_driver_count == 0
            and not research_preview.get("topCandidates")
            and options_status.get("gammaEvidenceStatus") == "unavailable"
        ) else "degraded"

        return {
            "status": status,
            "reasonCodes": _dedupe(reason_codes),
            "regimeEvidenceGrade": regime_quality.get("evidenceGrade"),
            "availableDriverCount": available_driver_count,
            "proxyEvidenceCount": int(regime_quality.get("proxyEvidenceCount") or 0),
        }


def build_market_decision_cockpit(
    *,
    actor: Mapping[str, Any] | None = None,
    market_inputs: Mapping[str, Any] | None = None,
    market_regime_decision: Mapping[str, Any] | None = None,
    research_candidates: Sequence[Mapping[str, Any]] | None = None,
    option_contracts: Sequence[Any] | None = None,
    option_spot: float | int | str | None = None,
    market_overview_service: MarketOverviewService | None = None,
    now_provider: Callable[[], str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the v1 market decision cockpit payload."""

    now = (lambda: generated_at) if generated_at is not None else now_provider
    return MarketDecisionCockpitService(
        market_overview_service=market_overview_service,
        now_provider=now,
    ).get_decision_cockpit(
        actor=actor,
        market_inputs=market_inputs,
        market_regime_decision=market_regime_decision,
        research_candidates=research_candidates,
        option_contracts=option_contracts,
        option_spot=option_spot,
    )


def _invalidation_conditions(payload: Mapping[str, Any]) -> list[str]:
    explanation = payload.get("explanation")
    if not isinstance(explanation, Mapping):
        return []
    return list(explanation.get("whatInvalidatesIt") or [])


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _dedupe(items: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


__all__ = [
    "MarketDecisionCockpitService",
    "NO_ADVICE_DISCLOSURE",
    "SCHEMA_VERSION",
    "build_market_decision_cockpit",
]
