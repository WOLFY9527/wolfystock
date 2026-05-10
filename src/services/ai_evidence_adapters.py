# -*- coding: utf-8 -*-
"""Inert metadata-only adapters for cross-engine AI evidence packets."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from src.services.ai_evidence_packet import (
    AI_EVIDENCE_PACKET_VERSION,
    AiEvidenceConfidenceCap,
    AiEvidenceCriticality,
    AiEvidenceDecisionStatus,
    AiEvidenceEngine,
    AiEvidenceEntity,
    AiEvidenceFreshnessClass,
    AiEvidenceItem,
    AiEvidencePacket,
    AiEvidenceSourceClass,
    AiEvidenceSourceRef,
    AiEvidenceStatus,
    AiExplainableFact,
    coerce_ai_evidence_packet,
    evaluate_evidence_policy,
)
from src.services.rotation_state_evidence import ROTATION_STATE_EVIDENCE_SCHEMA_VERSION
from src.services.scanner_evidence_packet import SCANNER_EVIDENCE_VERSION


_FORBIDDEN_FIELD_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "header",
    "headers",
    "password",
    "payload",
    "prompt",
    "request",
    "response",
    "secret",
    "stack",
    "token",
    "trace",
)
_FORBIDDEN_VALUE_MARKERS = (
    "authorization:",
    "bearer ",
    "cookie=",
    "set-cookie",
    "raw prompt",
    "raw llm response",
    "stack trace",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple, set)) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(target: list[str], value: Any) -> None:
    text = _text(value)
    if text and text not in target:
        target.append(text)


def _normalized_key(value: Any) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


def _is_forbidden_key(value: Any) -> bool:
    normalized = _normalized_key(value)
    return any(marker in normalized for marker in _FORBIDDEN_FIELD_MARKERS)


def _is_forbidden_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in _FORBIDDEN_VALUE_MARKERS)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            if _is_forbidden_key(key):
                continue
            cleaned = _sanitize_value(child)
            if cleaned in ({}, [], None, ""):
                continue
            sanitized[str(key)] = cleaned
        return sanitized
    if isinstance(value, (list, tuple, set)):
        cleaned_items = []
        for child in value:
            cleaned = _sanitize_value(child)
            if cleaned in ({}, [], None, ""):
                continue
            cleaned_items.append(cleaned)
        return cleaned_items
    if _is_forbidden_value(value):
        return "[redacted]"
    return value


def _replace_rotation_flow_wording(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _replace_rotation_flow_wording(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_rotation_flow_wording(child) for child in value]
    if isinstance(value, str):
        return (
            value.replace("真实资金流暂缺", "资金依据未接入")
            .replace("真实资金流", "实盘资金依据")
            .replace("资金流入确认", "资金依据确认")
            .replace("主力资金确认", "主力依据确认")
            .replace("ETF 申赎确认", "ETF 依据确认")
        )
    return value


def _source_class(value: Any, *, default: AiEvidenceSourceClass) -> AiEvidenceSourceClass:
    text = _normalized_key(value)
    if text in {"live"}:
        return AiEvidenceSourceClass.LIVE
    if text in {"delayed", "delayed_usable"}:
        return AiEvidenceSourceClass.DELAYED
    if text in {"cache", "cached"}:
        return AiEvidenceSourceClass.CACHE
    if text in {"local", "manual"}:
        return AiEvidenceSourceClass.LOCAL
    if text in {"fixture", "dry_run"}:
        return AiEvidenceSourceClass.FIXTURE
    if text in {"synthetic", "mock"}:
        return AiEvidenceSourceClass.SYNTHETIC
    if text in {"fallback", "mixed"}:
        return AiEvidenceSourceClass.FALLBACK
    if text in {"local_historical", "historical"}:
        return AiEvidenceSourceClass.LOCAL_HISTORICAL
    if text in {"inferred", "proxy_only"}:
        return AiEvidenceSourceClass.INFERRED
    return default


def _freshness_class(value: Any, *, default: AiEvidenceFreshnessClass) -> AiEvidenceFreshnessClass:
    text = _normalized_key(value)
    if text in {"fresh", "complete", "ready", "available"}:
        return AiEvidenceFreshnessClass.FRESH
    if text in {"delayed", "delayed_usable"}:
        return AiEvidenceFreshnessClass.DELAYED_USABLE
    if text in {"stale", "fallback"}:
        return AiEvidenceFreshnessClass.STALE
    if text in {"missing", "unavailable", "blocked", "insufficient"}:
        return AiEvidenceFreshnessClass.MISSING
    if text in {"fixture", "dry_run"}:
        return AiEvidenceFreshnessClass.FIXTURE
    if text in {"synthetic", "mock"}:
        return AiEvidenceFreshnessClass.SYNTHETIC
    if text in {"local_historical", "historical"}:
        return AiEvidenceFreshnessClass.LOCAL_HISTORICAL
    if text in {"fallback_only"}:
        return AiEvidenceFreshnessClass.FALLBACK
    return default


def _required_status(value: Any, *, allow_partial: bool = True) -> AiEvidenceStatus:
    text = _normalized_key(value)
    if text in {"available", "complete", "ready", "clear", "usable", "strong"}:
        return AiEvidenceStatus.AVAILABLE
    if text in {"stale", "fallback"}:
        return AiEvidenceStatus.STALE
    if text in {"fixture", "dry_run"}:
        return AiEvidenceStatus.FIXTURE
    if text in {"synthetic", "mock"}:
        return AiEvidenceStatus.SYNTHETIC
    if text in {"conflicting"}:
        return AiEvidenceStatus.CONFLICTING
    if text in {"missing", "blocked", "unavailable", "unknown"}:
        return AiEvidenceStatus.MISSING
    if allow_partial:
        return AiEvidenceStatus.PARTIAL
    return AiEvidenceStatus.MISSING


def _safe_run_id(engine: AiEvidenceEngine, entity_id: str, *parts: Any) -> str:
    material = "|".join([engine.value, entity_id] + [_text(part) for part in parts if _text(part)])
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]
    return f"synthetic_{engine.value}_{digest}"


def _decision_rank(value: AiEvidenceDecisionStatus) -> int:
    return {
        AiEvidenceDecisionStatus.FORBIDDEN: 0,
        AiEvidenceDecisionStatus.CAUTION: 1,
        AiEvidenceDecisionStatus.ALLOWED: 2,
    }[value]


def _stricter_decision(left: AiEvidenceDecisionStatus, right: AiEvidenceDecisionStatus) -> AiEvidenceDecisionStatus:
    return left if _decision_rank(left) <= _decision_rank(right) else right


def _sanitize_source_refs(
    source_refs: list[Any],
    *,
    provider: str,
    category: str,
    source_class: AiEvidenceSourceClass,
    fallback_ref_id: str,
    sanitized_reason_code: str,
) -> list[AiEvidenceSourceRef]:
    sanitized: list[AiEvidenceSourceRef] = []
    for index, raw in enumerate(source_refs):
        payload = _mapping(raw)
        ref_id = _text(payload.get("source_ref_id")) or f"{fallback_ref_id}_{index + 1}"
        sanitized.append(
            AiEvidenceSourceRef(
                source_ref_id=ref_id,
                provider=_text(payload.get("provider")) or provider,
                category=_text(payload.get("category")) or category,
                source_class=_source_class(payload.get("source_class"), default=source_class),
                cache_hit=bool(payload["cache_hit"]) if payload.get("cache_hit") is not None else None,
                provider_usage_event_ids=[_text(item) for item in _items(payload.get("provider_usage_event_ids")) if _text(item)],
                sanitized_reason_code=_text(payload.get("sanitized_reason_code")) or sanitized_reason_code,
                raw_payload_stored=False,
            )
        )
    if sanitized:
        return sanitized
    return [
        AiEvidenceSourceRef(
            source_ref_id=fallback_ref_id,
            provider=provider,
            category=category,
            source_class=source_class,
            cache_hit=None,
            provider_usage_event_ids=[],
            sanitized_reason_code=sanitized_reason_code,
            raw_payload_stored=False,
        )
    ]


def _normalize_facts(
    facts: list[Any],
    *,
    fallback_statement: str,
    fallback_source_ref_id: str,
) -> list[AiExplainableFact]:
    normalized: list[AiExplainableFact] = []
    for index, raw in enumerate(facts):
        payload = _mapping(raw)
        source_ref_ids = [_text(item) for item in _items(payload.get("source_ref_ids")) if _text(item)]
        if not source_ref_ids:
            source_ref_ids = [fallback_source_ref_id]
        normalized.append(
            AiExplainableFact(
                fact_id=_text(payload.get("fact_id")) or f"fact_{index + 1}",
                statement=_text(payload.get("statement")) or fallback_statement,
                source_ref_ids=source_ref_ids,
                criticality=AiEvidenceCriticality(_text(payload.get("criticality")) or "important"),
                confidence_class=_text(payload.get("confidence_class")) or "medium",
                user_visible=bool(payload.get("user_visible", True)),
            )
        )
    if normalized:
        return normalized
    return [
        AiExplainableFact(
            fact_id="fact_1",
            statement=fallback_statement,
            source_ref_ids=[fallback_source_ref_id],
            criticality=AiEvidenceCriticality.IMPORTANT,
            confidence_class="medium",
            user_visible=True,
        )
    ]


def _finalize_packet(packet: AiEvidencePacket) -> AiEvidencePacket:
    policy = evaluate_evidence_policy(packet)
    reason_codes = list(packet.confidence_cap.reason_codes)
    for code in policy.confidence_cap.reason_codes:
        _append_unique(reason_codes, code)
    quality_flags = list(packet.quality_flags)
    for flag in policy.quality_flags:
        _append_unique(quality_flags, flag)
    return AiEvidencePacket(
        engine=packet.engine,
        entity=packet.entity,
        run_id=packet.run_id,
        evidence_version=AI_EVIDENCE_PACKET_VERSION,
        required_evidence=list(packet.required_evidence),
        optional_evidence=list(packet.optional_evidence),
        freshness=_mapping(_sanitize_value(packet.freshness)),
        quality_flags=quality_flags,
        decision_status=_stricter_decision(packet.decision_status, policy.decision_status),
        confidence_cap=AiEvidenceConfidenceCap(
            value=min(packet.confidence_cap.value, policy.confidence_cap.value),
            policy_version=packet.confidence_cap.policy_version,
            reason_codes=reason_codes,
        ),
        source_refs=list(packet.source_refs),
        explainable_facts=list(packet.explainable_facts),
        admin_diagnostics=_mapping(_sanitize_value(packet.admin_diagnostics)),
    )


def _item(
    *,
    key: str,
    status: AiEvidenceStatus,
    value_class: str,
    source_ref_ids: list[str],
    as_of: str | None,
    freshness_class: AiEvidenceFreshnessClass,
    reason_codes: list[str] | None = None,
    criticality: AiEvidenceCriticality = AiEvidenceCriticality.REQUIRED,
) -> AiEvidenceItem:
    return AiEvidenceItem(
        key=key,
        criticality=criticality,
        status=status,
        value_class=value_class,
        source_ref_ids=list(source_ref_ids),
        as_of=_text(as_of) or None,
        freshness_class=freshness_class,
        reason_codes=[_text(code) for code in (reason_codes or []) if _text(code)],
    )


def _apply_version_guard(
    packet: AiEvidencePacket,
    *,
    actual_version: Any,
    expected_version: str,
    quality_flag: str,
    reason_code: str,
) -> AiEvidencePacket:
    version_text = _text(actual_version)
    if not version_text or version_text == expected_version:
        return packet

    quality_flags = list(packet.quality_flags)
    _append_unique(quality_flags, quality_flag)
    reason_codes = list(packet.confidence_cap.reason_codes)
    _append_unique(reason_codes, reason_code)
    return AiEvidencePacket(
        engine=packet.engine,
        entity=packet.entity,
        run_id=packet.run_id,
        evidence_version=packet.evidence_version,
        required_evidence=list(packet.required_evidence),
        optional_evidence=list(packet.optional_evidence),
        freshness=packet.freshness,
        quality_flags=quality_flags,
        decision_status=_stricter_decision(packet.decision_status, AiEvidenceDecisionStatus.CAUTION),
        confidence_cap=AiEvidenceConfidenceCap(
            value=min(packet.confidence_cap.value, 60),
            policy_version=packet.confidence_cap.policy_version,
            reason_codes=reason_codes,
        ),
        source_refs=list(packet.source_refs),
        explainable_facts=list(packet.explainable_facts),
        admin_diagnostics=dict(packet.admin_diagnostics),
    )


def normalize_engine_evidence_to_ai_packet(value: Any) -> AiEvidencePacket:
    payload = value.to_dict() if isinstance(value, AiEvidencePacket) else _mapping(value)
    if not payload:
        raise ValueError("unsupported engine evidence payload")
    if payload.get("evidence_version") == AI_EVIDENCE_PACKET_VERSION:
        packet = coerce_ai_evidence_packet(payload)
        source_refs = _sanitize_source_refs(
            [item.to_dict() if hasattr(item, "to_dict") else item for item in packet.source_refs],
            provider="engine_adapter",
            category=packet.engine.value,
            source_class=AiEvidenceSourceClass.LOCAL,
            fallback_ref_id=f"{packet.engine.value}_source",
            sanitized_reason_code="sanitized_source_ref",
        )
        facts = _normalize_facts(
            [item.to_dict() if hasattr(item, "to_dict") else item for item in packet.explainable_facts],
            fallback_statement="Evidence packet metadata was normalized without changing engine behavior.",
            fallback_source_ref_id=source_refs[0].source_ref_id,
        )
        normalized = AiEvidencePacket(
            engine=packet.engine,
            entity=packet.entity,
            run_id=packet.run_id or _safe_run_id(packet.engine, packet.entity.id),
            evidence_version=AI_EVIDENCE_PACKET_VERSION,
            required_evidence=list(packet.required_evidence),
            optional_evidence=list(packet.optional_evidence),
            freshness=_mapping(_sanitize_value(packet.freshness)),
            quality_flags=list(packet.quality_flags),
            decision_status=packet.decision_status,
            confidence_cap=packet.confidence_cap,
            source_refs=source_refs,
            explainable_facts=facts,
            admin_diagnostics=_mapping(_sanitize_value(packet.admin_diagnostics)),
        )
        return _finalize_packet(normalized)
    if "portfolioRiskEvidence" in payload or "riskDiagnostics" in payload:
        return portfolio_risk_to_ai_packet(payload)
    if "rotationStateEvidence" in payload or "flowEvidenceType" in payload:
        return rotation_evidence_to_ai_packet(payload)
    if "dataQualityGates" in payload or "gateDecision" in payload:
        return options_gates_to_ai_packet(payload)
    if "professionalReadiness" in payload or "overall_state" in payload:
        return backtest_readiness_to_ai_packet(payload)
    diagnostics = _mapping(payload.get("diagnostics"))
    if "evidence_packet" in diagnostics or "evidenceVersion" in payload:
        return scanner_evidence_to_ai_packet(payload)
    raise ValueError("unsupported engine evidence payload")


def scanner_evidence_to_ai_packet(value: Any) -> AiEvidencePacket:
    payload = _mapping(value)
    raw = _mapping(_mapping(payload.get("diagnostics")).get("evidence_packet")) or payload
    symbol = _text(raw.get("symbol")) or "unknown"
    market = (_text(raw.get("market")) or _text(payload.get("market")) or "unknown").upper()
    entity = AiEvidenceEntity(
        type="symbol",
        id=f"scanner:{symbol}",
        symbol=symbol,
        market=market,
        display_name=_text(payload.get("name")) or None,
    )
    freshness_detail = _mapping(raw.get("freshnessDetail"))
    quote_state = _text(freshness_detail.get("quoteState")) or _text(raw.get("freshnessState"))
    history_state = _text(freshness_detail.get("historyState")) or _text(raw.get("freshnessState"))
    latest_trade_date = _text(freshness_detail.get("latestTradeDate")) or None
    rank = raw.get("rank")
    score = raw.get("score")
    reason_codes = [_text(code) for code in _items(raw.get("adminReasonCodes")) if _text(code)]
    warning_flags = [_text(code) for code in _items(raw.get("warningFlags")) if _text(code)]
    user_labels = [_text(code) for code in _items(raw.get("userFacingLabels")) if _text(code)]
    quote_ref_id = "scanner_quote"
    history_ref_id = "scanner_history"
    source_refs = [
        AiEvidenceSourceRef(
            source_ref_id=quote_ref_id,
            provider="scanner_evidence_adapter",
            category="quote",
            source_class=_source_class(quote_state, default=AiEvidenceSourceClass.FALLBACK),
            cache_hit=None,
            provider_usage_event_ids=[],
            sanitized_reason_code="scanner_quote_metadata_only",
            raw_payload_stored=False,
        ),
        AiEvidenceSourceRef(
            source_ref_id=history_ref_id,
            provider="scanner_evidence_adapter",
            category="ohlcv",
            source_class=_source_class(history_state, default=AiEvidenceSourceClass.LOCAL_HISTORICAL),
            cache_hit=None,
            provider_usage_event_ids=[],
            sanitized_reason_code="scanner_history_metadata_only",
            raw_payload_stored=False,
        ),
    ]
    quality_flags: list[str] = []
    decision_status = AiEvidenceDecisionStatus.ALLOWED
    cap_value = 90
    quote_status = _required_status(quote_state, allow_partial=False)
    quote_freshness = _freshness_class(quote_state, default=AiEvidenceFreshnessClass.UNKNOWN)
    history_status = _required_status(history_state, allow_partial=False)
    history_freshness = _freshness_class(history_state, default=AiEvidenceFreshnessClass.UNKNOWN)
    if quote_status is AiEvidenceStatus.STALE or history_status is AiEvidenceStatus.STALE:
        decision_status = AiEvidenceDecisionStatus.CAUTION
        cap_value = min(cap_value, 60 if quote_status is AiEvidenceStatus.STALE and not latest_trade_date else 75)
    if _text(raw.get("dataQualityState")) in {"partial", "missing", "insufficient"} or warning_flags:
        decision_status = AiEvidenceDecisionStatus.CAUTION
        cap_value = min(cap_value, 75)
    optional_evidence = []
    if "external_optional_unavailable" in reason_codes:
        _append_unique(quality_flags, "optional_enrichment_missing")
        optional_evidence.append(
            _item(
                key="news.context",
                status=AiEvidenceStatus.MISSING,
                value_class="document",
                source_ref_ids=[history_ref_id],
                as_of=None,
                freshness_class=AiEvidenceFreshnessClass.MISSING,
                reason_codes=["optional_news_missing"],
                criticality=AiEvidenceCriticality.OPTIONAL,
            )
        )
    packet = AiEvidencePacket(
        engine=AiEvidenceEngine.SCANNER,
        entity=entity,
        run_id=_text(raw.get("runId")) or _safe_run_id(AiEvidenceEngine.SCANNER, entity.id, raw.get("evidenceVersion")),
        evidence_version=AI_EVIDENCE_PACKET_VERSION,
        required_evidence=[
            _item(
                key="quote.price",
                status=quote_status,
                value_class="numeric",
                source_ref_ids=[quote_ref_id],
                as_of=latest_trade_date,
                freshness_class=quote_freshness,
                reason_codes=["provider_unavailable"] if quote_status is not AiEvidenceStatus.AVAILABLE else [],
            ),
            _item(
                key="ohlcv.window",
                status=history_status,
                value_class="timeseries",
                source_ref_ids=[history_ref_id],
                as_of=latest_trade_date,
                freshness_class=history_freshness,
                reason_codes=[code for code in reason_codes if code.startswith("history_")],
            ),
            _item(
                key="liquidity.amount",
                status=_required_status(_mapping(raw.get("liquidityEvidence")).get("state"), allow_partial=True),
                value_class="numeric",
                source_ref_ids=[history_ref_id],
                as_of=latest_trade_date,
                freshness_class=history_freshness,
                reason_codes=[],
            ),
            _item(
                key="score.component_inputs",
                status=AiEvidenceStatus.AVAILABLE,
                value_class="metadata",
                source_ref_ids=[history_ref_id],
                as_of=latest_trade_date,
                freshness_class=history_freshness,
                reason_codes=[],
            ),
            _item(
                key="run.id",
                status=AiEvidenceStatus.AVAILABLE,
                value_class="metadata",
                source_ref_ids=[history_ref_id],
                as_of=latest_trade_date,
                freshness_class=history_freshness,
                reason_codes=[],
            ),
        ],
        optional_evidence=optional_evidence,
        freshness={
            "quote": {"as_of": latest_trade_date, "freshness_class": quote_freshness.value},
            "history": {"as_of": latest_trade_date, "freshness_class": history_freshness.value},
        },
        quality_flags=quality_flags,
        decision_status=decision_status,
        confidence_cap=AiEvidenceConfidenceCap(
            value=cap_value,
            reason_codes=["scanner_evidence_metadata_only"],
        ),
        source_refs=source_refs,
        explainable_facts=[
            AiExplainableFact(
                fact_id="fact_1",
                statement="Scanner evidence metadata is advisory-only; rank and score remain audit context and never upgrade the decision posture.",
                source_ref_ids=[quote_ref_id, history_ref_id],
                criticality=AiEvidenceCriticality.IMPORTANT,
                confidence_class="medium",
                user_visible=True,
            )
        ],
        admin_diagnostics=_mapping(
            _sanitize_value(
                {
                    "source_packet_version": _text(raw.get("evidenceVersion")) or "scanner_evidence_v1",
                    "data_quality_state": _text(raw.get("dataQualityState")) or "unknown",
                    "freshness_state": _text(raw.get("freshnessState")) or "unknown",
                    "missing_evidence": [_text(item) for item in _items(raw.get("missingEvidence")) if _text(item)],
                    "warning_flags": warning_flags,
                    "user_facing_labels": user_labels,
                    "admin_reason_codes": reason_codes,
                    "scanner_rank_metadata": {
                        "rank": rank,
                        "score": score,
                        "advisory_only": True,
                    },
                }
            )
        ),
    )
    packet = _apply_version_guard(
        packet,
        actual_version=raw.get("evidenceVersion"),
        expected_version=SCANNER_EVIDENCE_VERSION,
        quality_flag="unknown_source_packet_version",
        reason_code="unsupported_source_packet_version",
    )
    return _finalize_packet(packet)


def rotation_evidence_to_ai_packet(value: Any) -> AiEvidencePacket:
    payload = _mapping(value)
    raw = _mapping(payload.get("rotationStateEvidence")) or payload
    theme_id = _text(raw.get("themeId")) or "unknown_theme"
    market = (_text(raw.get("market")) or "unknown").upper()
    flow_type = _normalized_key(raw.get("flowEvidenceType")) or "none"
    flow_language_allowed = bool(raw.get("flowLanguageAllowed"))
    confidence = raw.get("stateConfidence")
    try:
        state_confidence = float(confidence)
    except (TypeError, ValueError):
        state_confidence = 0.5
    required_data = _mapping(raw.get("requiredDataStatus"))
    as_of = _text(raw.get("asOf")) or None
    source_ref_id = "rotation_state"
    packet = AiEvidencePacket(
        engine=AiEvidenceEngine.ROTATION,
        entity=AiEvidenceEntity(
            type="sector",
            id=f"rotation:{theme_id}",
            market=market,
            display_name=theme_id,
        ),
        run_id=_text(raw.get("computedAt")) or _safe_run_id(AiEvidenceEngine.ROTATION, f"rotation:{theme_id}", as_of),
        evidence_version=AI_EVIDENCE_PACKET_VERSION,
        required_evidence=[
            _item(
                key="taxonomy.version",
                status=AiEvidenceStatus.AVAILABLE if _text(raw.get("taxonomyVersion")) else AiEvidenceStatus.MISSING,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=AiEvidenceFreshnessClass.FRESH if _text(raw.get("taxonomyVersion")) else AiEvidenceFreshnessClass.MISSING,
                reason_codes=[],
            ),
            _item(
                key="proxy.coverage",
                status=AiEvidenceStatus.AVAILABLE if required_data.get("hasSufficientEvidence") else AiEvidenceStatus.PARTIAL,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=AiEvidenceFreshnessClass.DELAYED_USABLE,
                reason_codes=[_text(code) for code in _items(required_data.get("missingReasonCodes")) if _text(code)],
            ),
            _item(
                key="benchmark_proxy.ohlcv",
                status=AiEvidenceStatus.AVAILABLE if as_of else AiEvidenceStatus.PARTIAL,
                value_class="timeseries",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=AiEvidenceFreshnessClass.DELAYED_USABLE if as_of else AiEvidenceFreshnessClass.UNKNOWN,
                reason_codes=[],
            ),
            _item(
                key="breadth.coverage",
                status=_required_status(_mapping(_mapping(raw.get("signals")).get("breadth")).get("status"), allow_partial=True),
                value_class="numeric",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=AiEvidenceFreshnessClass.DELAYED_USABLE,
                reason_codes=[],
            ),
            _item(
                key="volume.baseline",
                status=AiEvidenceStatus.AVAILABLE,
                value_class="numeric",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=AiEvidenceFreshnessClass.DELAYED_USABLE,
                reason_codes=[],
            ),
            _item(
                key="flow.evidence_boundary",
                status=AiEvidenceStatus.AVAILABLE,
                value_class="categorical",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=AiEvidenceFreshnessClass.UNKNOWN,
                reason_codes=[f"flow_{flow_type}"],
            ),
        ],
        optional_evidence=[
            _item(
                key="actual_flow.provider",
                status=AiEvidenceStatus.MISSING if flow_type in {"none", "proxy_only"} else AiEvidenceStatus.AVAILABLE,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=AiEvidenceFreshnessClass.MISSING if flow_type in {"none", "proxy_only"} else AiEvidenceFreshnessClass.FRESH,
                reason_codes=["real_flow_missing"] if flow_type in {"none", "proxy_only"} else [],
                criticality=AiEvidenceCriticality.OPTIONAL,
            )
        ],
        freshness={
            "rotation_state": {
                "as_of": as_of,
                "freshness_class": "delayed_usable" if as_of else "unknown",
            }
        },
        quality_flags=["optional_enrichment_missing"] if flow_type in {"none", "proxy_only"} else [],
        decision_status=AiEvidenceDecisionStatus.CAUTION if not flow_language_allowed or not required_data.get("hasSufficientEvidence") else AiEvidenceDecisionStatus.ALLOWED,
        confidence_cap=AiEvidenceConfidenceCap(
            value=min(60 if not flow_language_allowed else 80, max(30, int(round(state_confidence * 100)))),
            reason_codes=["rotation_proxy_only_flow_boundary"] if flow_type in {"none", "proxy_only"} else [],
        ),
        source_refs=[
            AiEvidenceSourceRef(
                source_ref_id=source_ref_id,
                provider="rotation_evidence_adapter",
                category="rotation",
                source_class=AiEvidenceSourceClass.INFERRED if flow_type in {"none", "proxy_only"} else AiEvidenceSourceClass.DELAYED,
                cache_hit=None,
                provider_usage_event_ids=[],
                sanitized_reason_code="rotation_state_metadata_only",
                raw_payload_stored=False,
            )
        ],
        explainable_facts=[
            AiExplainableFact(
                fact_id="fact_1",
                statement="当前仅有轮动代理证据，实盘资金依据未接入，因此只能保持观察级别表达。",
                source_ref_ids=[source_ref_id],
                criticality=AiEvidenceCriticality.REQUIRED,
                confidence_class="medium",
                user_visible=True,
            )
        ],
        admin_diagnostics=_mapping(
            _sanitize_value(
                _replace_rotation_flow_wording(
                    {
                    "engine_schema_version": _text(raw.get("schemaVersion")) or "rotation_state_evidence_v1",
                    "state": _text(raw.get("state")),
                    "state_confidence": state_confidence,
                    "flow_evidence_type": flow_type,
                    "flow_language_allowed": flow_language_allowed,
                    "required_data_status": required_data,
                    "risk_labels": [_text(item) for item in _items(raw.get("riskLabels")) if _text(item)],
                    "sanitized_inputs": _mapping(raw.get("adminDiagnostics")),
                    }
                )
            )
        ),
    )
    packet = _apply_version_guard(
        packet,
        actual_version=raw.get("schemaVersion"),
        expected_version=ROTATION_STATE_EVIDENCE_SCHEMA_VERSION,
        quality_flag="unknown_engine_schema_version",
        reason_code="unsupported_engine_schema_version",
    )
    return _finalize_packet(packet)


def options_gates_to_ai_packet(value: Any) -> AiEvidencePacket:
    payload = _mapping(value)
    symbol = _text(payload.get("symbol")) or _text(_mapping(payload.get("underlying")).get("symbol")) or "unknown"
    market = (_text(payload.get("market")) or _text(_mapping(payload.get("underlying")).get("market")) or "unknown").upper()
    strategy_key = _text(payload.get("strategyKey")) or "unknown_strategy"
    gate_decision = _text(payload.get("gateDecision"))
    reason_codes = [_text(code) for code in _items(payload.get("failClosedReasonCodes")) if _text(code)]
    issue_codes = [_text(_mapping(issue).get("code")) for issue in _items(payload.get("gateIssues")) if _text(_mapping(issue).get("code"))]
    all_codes = reason_codes + [code for code in issue_codes if code not in reason_codes]
    has_fixture = any(marker in code for code in all_codes for marker in ("fixture", "synthetic", "dry_run", "dry-run"))
    has_missing = any(marker in code for code in all_codes for marker in ("missing", "unknown"))
    has_stale = any(marker in code for code in all_codes for marker in ("stale", "fallback", "delayed"))
    as_of = _text(_mapping(payload.get("chain")).get("asOf")) or _text(_mapping(payload.get("underlying")).get("asOf")) or None
    source_ref_id = "options_gate"
    decision_status = AiEvidenceDecisionStatus.FORBIDDEN if gate_decision == "数据不足，禁止判断" else AiEvidenceDecisionStatus.CAUTION
    cap_value = 35 if has_fixture else 40 if decision_status is AiEvidenceDecisionStatus.FORBIDDEN else 60 if has_stale else 75
    provider_status = (
        AiEvidenceStatus.FIXTURE
        if has_fixture
        else AiEvidenceStatus.MISSING
        if has_missing
        else AiEvidenceStatus.STALE
        if has_stale
        else AiEvidenceStatus.AVAILABLE
    )
    provider_freshness = (
        AiEvidenceFreshnessClass.FIXTURE
        if has_fixture
        else AiEvidenceFreshnessClass.MISSING
        if has_missing
        else AiEvidenceFreshnessClass.STALE
        if has_stale
        else AiEvidenceFreshnessClass.FRESH
    )
    packet = AiEvidencePacket(
        engine=AiEvidenceEngine.OPTIONS,
        entity=AiEvidenceEntity(
            type="strategy",
            id=f"options:{symbol}:{strategy_key}",
            symbol=symbol,
            market=market,
            display_name=strategy_key,
        ),
        run_id=_safe_run_id(AiEvidenceEngine.OPTIONS, f"options:{symbol}:{strategy_key}", as_of),
        evidence_version=AI_EVIDENCE_PACKET_VERSION,
        required_evidence=[
            _item(
                key="underlying.quote",
                status=provider_status,
                value_class="numeric",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=[code for code in all_codes if any(marker in code for marker in ("freshness", "fixture", "synthetic", "unknown"))],
            ),
            _item(
                key="chain.snapshot",
                status=provider_status,
                value_class="timeseries",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=[code for code in all_codes if "source" in code or "freshness" in code],
            ),
            _item(
                key="contract.identity",
                status=AiEvidenceStatus.AVAILABLE,
                value_class="categorical",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=[],
            ),
            _item(
                key="quote.bid_ask_mid",
                status=AiEvidenceStatus.MISSING if any("bid_ask" in code or "bidask" in code for code in all_codes) else provider_status,
                value_class="numeric",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=[code for code in all_codes if "bid_ask" in code or "bidask" in code],
            ),
            _item(
                key="iv.greeks",
                status=AiEvidenceStatus.PARTIAL,
                value_class="numeric",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=[],
            ),
            _item(
                key="liquidity.oi_volume",
                status=_required_status(_mapping(payload.get("liquidityGates")).get("status"), allow_partial=True),
                value_class="numeric",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=[code for code in all_codes if "liquidity" in code or "bid_ask" in code],
            ),
            _item(
                key="event.calendar",
                status=AiEvidenceStatus.PARTIAL,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=[],
            ),
            _item(
                key="provider.freshness",
                status=provider_status,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=as_of,
                freshness_class=provider_freshness,
                reason_codes=all_codes,
            ),
        ],
        optional_evidence=[],
        freshness={"options_chain": {"as_of": as_of, "freshness_class": provider_freshness.value}},
        quality_flags=[],
        decision_status=decision_status,
        confidence_cap=AiEvidenceConfidenceCap(value=cap_value, reason_codes=["options_gate_metadata_only"]),
        source_refs=[
            AiEvidenceSourceRef(
                source_ref_id=source_ref_id,
                provider="options_gate_adapter",
                category="options",
                source_class=AiEvidenceSourceClass.FIXTURE if has_fixture else AiEvidenceSourceClass.FALLBACK if has_stale else AiEvidenceSourceClass.LOCAL,
                cache_hit=None,
                provider_usage_event_ids=[],
                sanitized_reason_code="options_gate_metadata_only",
                raw_payload_stored=False,
            )
        ],
        explainable_facts=[
            AiExplainableFact(
                fact_id="fact_1",
                statement="期权判断被现有数据质量闸门限制，适配器仅转写现有禁止判断姿态，不扩展策略集合或推荐语义。",
                source_ref_ids=[source_ref_id],
                criticality=AiEvidenceCriticality.REQUIRED,
                confidence_class="low",
                user_visible=True,
            )
        ],
        admin_diagnostics=_mapping(
            _sanitize_value(
                {
                    "strategy_key": strategy_key,
                    "gate_decision": gate_decision,
                    "decision_grade": bool(payload.get("decisionGrade")),
                    "fail_closed_reason_codes": reason_codes,
                    "data_quality_status": _text(_mapping(payload.get("dataQualityGates")).get("status")),
                    "liquidity_status": _text(_mapping(payload.get("liquidityGates")).get("status")),
                    "gate_issue_codes": issue_codes,
                }
            )
        ),
    )
    return _finalize_packet(packet)


def backtest_readiness_to_ai_packet(value: Any) -> AiEvidencePacket:
    payload = _mapping(value)
    raw = _mapping(payload.get("professionalReadiness")) or payload
    run_id = _text(payload.get("run_id")) or _safe_run_id(AiEvidenceEngine.BACKTEST, _text(payload.get("symbol")) or "backtest")
    symbol = _text(payload.get("symbol"))
    market = (_text(payload.get("market")) or "unknown").upper()
    source_ref_id = "backtest_readiness"
    overall_state = _text(raw.get("overall_state")) or "research_prototype"
    professional_quant_ready = bool(raw.get("professional_quant_ready"))
    packet = AiEvidencePacket(
        engine=AiEvidenceEngine.BACKTEST,
        entity=AiEvidenceEntity(
            type="job" if not symbol else "symbol",
            id=f"backtest:{symbol or run_id}",
            symbol=symbol or None,
            market=market,
            display_name=symbol or "backtest",
        ),
        run_id=run_id,
        evidence_version=AI_EVIDENCE_PACKET_VERSION,
        required_evidence=[
            _item(
                key="local_bars.coverage",
                status=AiEvidenceStatus.AVAILABLE,
                value_class="timeseries",
                source_ref_ids=[source_ref_id],
                as_of=None,
                freshness_class=AiEvidenceFreshnessClass.LOCAL_HISTORICAL,
                reason_codes=[],
            ),
            _item(
                key="adjusted_data.policy",
                status=AiEvidenceStatus.PARTIAL,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=None,
                freshness_class=AiEvidenceFreshnessClass.UNKNOWN,
                reason_codes=[_text(payload.get("adjustedDataState")) or _text(raw.get("adjusted_data_state"))],
            ),
            _item(
                key="corporate_actions.coverage",
                status=AiEvidenceStatus.PARTIAL,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=None,
                freshness_class=AiEvidenceFreshnessClass.UNKNOWN,
                reason_codes=[_text(payload.get("corporateActionState")) or _text(raw.get("corporate_action_state"))],
            ),
            _item(
                key="trading_calendar.policy",
                status=AiEvidenceStatus.PARTIAL,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=None,
                freshness_class=AiEvidenceFreshnessClass.UNKNOWN,
                reason_codes=[_text(payload.get("tradingCalendarState")) or _text(raw.get("trading_calendar_state"))],
            ),
            _item(
                key="cost_fill.model",
                status=AiEvidenceStatus.PARTIAL,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=None,
                freshness_class=AiEvidenceFreshnessClass.UNKNOWN,
                reason_codes=[_text(payload.get("fillModelState")) or _text(raw.get("fill_model"))],
            ),
            _item(
                key="rule_engine.dataset_version",
                status=AiEvidenceStatus.PARTIAL,
                value_class="metadata",
                source_ref_ids=[source_ref_id],
                as_of=None,
                freshness_class=AiEvidenceFreshnessClass.UNKNOWN,
                reason_codes=[_text(payload.get("reproducibilityState")) or _text(raw.get("reproducibility_state"))],
            ),
        ],
        optional_evidence=[],
        freshness={"backtest_readiness": {"as_of": None, "freshness_class": "local_historical"}},
        quality_flags=[],
        decision_status=AiEvidenceDecisionStatus.CAUTION if overall_state == "research_prototype" or not professional_quant_ready else AiEvidenceDecisionStatus.ALLOWED,
        confidence_cap=AiEvidenceConfidenceCap(
            value=55 if overall_state == "research_prototype" or not professional_quant_ready else 85,
            reason_codes=["research_prototype_only"] if overall_state == "research_prototype" or not professional_quant_ready else [],
        ),
        source_refs=[
            AiEvidenceSourceRef(
                source_ref_id=source_ref_id,
                provider="backtest_readiness_adapter",
                category="backtest",
                source_class=AiEvidenceSourceClass.LOCAL_HISTORICAL,
                cache_hit=True,
                provider_usage_event_ids=[],
                sanitized_reason_code="backtest_readiness_metadata_only",
                raw_payload_stored=False,
            )
        ],
        explainable_facts=[
            AiExplainableFact(
                fact_id="fact_1",
                statement="当前仅为研究级回测就绪度证据，不构成专业量化验证结论。",
                source_ref_ids=[source_ref_id],
                criticality=AiEvidenceCriticality.REQUIRED,
                confidence_class="medium",
                user_visible=True,
            )
        ],
        admin_diagnostics=_mapping(
            _sanitize_value(
                {
                    "overall_state": overall_state,
                    "professional_quant_ready": professional_quant_ready,
                    "adjusted_data_state": _text(raw.get("adjusted_data_state")) or _text(payload.get("adjustedDataState")),
                    "corporate_action_state": _text(raw.get("corporate_action_state")) or _text(payload.get("corporateActionState")),
                    "trading_calendar_state": _text(raw.get("trading_calendar_state")) or _text(payload.get("tradingCalendarState")),
                    "fill_model": _text(raw.get("fill_model")) or _text(payload.get("fillModelState")),
                    "cost_model_state": _text(raw.get("cost_model_state")) or _text(payload.get("costModelState")),
                    "reproducibility_state": _text(raw.get("reproducibility_state")) or _text(payload.get("reproducibilityState")),
                    "provider_calls": bool(raw.get("provider_calls")),
                    "categories": _mapping(raw.get("categories")),
                }
            )
        ),
    )
    return _finalize_packet(packet)


def portfolio_risk_to_ai_packet(value: Any) -> AiEvidencePacket:
    payload = _mapping(value)
    if payload.get("portfolioRiskEvidence"):
        packet = normalize_engine_evidence_to_ai_packet(payload.get("portfolioRiskEvidence"))
    else:
        portfolio_id = _text(payload.get("portfolioId")) or "unknown_portfolio"
        packet = AiEvidencePacket(
            engine=AiEvidenceEngine.PORTFOLIO_RISK,
            entity=AiEvidenceEntity(
                type="portfolio",
                id=f"portfolio:{portfolio_id}",
                market=(_text(payload.get("market")) or "unknown").upper(),
                display_name=portfolio_id,
            ),
            run_id=_safe_run_id(AiEvidenceEngine.PORTFOLIO_RISK, f"portfolio:{portfolio_id}"),
            evidence_version=AI_EVIDENCE_PACKET_VERSION,
            required_evidence=[],
            optional_evidence=[],
            freshness={},
            quality_flags=[],
            decision_status=AiEvidenceDecisionStatus.CAUTION,
            confidence_cap=AiEvidenceConfidenceCap(value=70, reason_codes=["portfolio_risk_metadata_only"]),
            source_refs=[
                AiEvidenceSourceRef(
                    source_ref_id="portfolio_risk",
                    provider="portfolio_risk_adapter",
                    category="portfolio",
                    source_class=AiEvidenceSourceClass.LOCAL,
                    cache_hit=True,
                    provider_usage_event_ids=[],
                    sanitized_reason_code="portfolio_risk_metadata_only",
                    raw_payload_stored=False,
                )
            ],
            explainable_facts=[
                AiExplainableFact(
                    fact_id="fact_1",
                    statement="Portfolio risk metadata was normalized from existing diagnostics only.",
                    source_ref_ids=["portfolio_risk"],
                    criticality=AiEvidenceCriticality.IMPORTANT,
                    confidence_class="medium",
                    user_visible=True,
                )
            ],
            admin_diagnostics={},
        )
    confidence = _mapping(_mapping(payload.get("riskDiagnostics")).get("confidenceCap")) or _mapping(payload.get("confidenceCap"))
    reason_codes = list(packet.confidence_cap.reason_codes)
    limitation_labels = [_text(item) for item in _items(confidence.get("limitation_labels")) if _text(item)]
    disabled_claims = [_text(item) for item in _items(confidence.get("disabled_claims")) if _text(item)]
    if "FX 汇率已过期" in limitation_labels:
        _append_unique(reason_codes, "stale_fx")
    for code in _items(confidence.get("reason_codes")):
        _append_unique(reason_codes, code)
    quality_flags = list(packet.quality_flags)
    if "FX 汇率已过期" in limitation_labels:
        _append_unique(quality_flags, "stale_required_data")
    decision = packet.decision_status
    if _text(confidence.get("decision_status")) == AiEvidenceDecisionStatus.FORBIDDEN.value:
        decision = AiEvidenceDecisionStatus.FORBIDDEN
    elif _text(confidence.get("decision_status")) == AiEvidenceDecisionStatus.CAUTION.value:
        decision = _stricter_decision(decision, AiEvidenceDecisionStatus.CAUTION)
    admin_diagnostics = _mapping(packet.admin_diagnostics)
    admin_diagnostics.update(
        _mapping(
            _sanitize_value(
                {
                    "confidence_cap": confidence,
                    "limitation_labels": limitation_labels,
                    "disabled_claims": disabled_claims,
                }
            )
        )
    )
    adjusted = AiEvidencePacket(
        engine=packet.engine,
        entity=packet.entity,
        run_id=packet.run_id or _safe_run_id(packet.engine, packet.entity.id),
        evidence_version=AI_EVIDENCE_PACKET_VERSION,
        required_evidence=list(packet.required_evidence),
        optional_evidence=list(packet.optional_evidence),
        freshness=packet.freshness,
        quality_flags=quality_flags,
        decision_status=decision,
        confidence_cap=AiEvidenceConfidenceCap(
            value=min(packet.confidence_cap.value, int(confidence.get("value") or packet.confidence_cap.value)),
            reason_codes=reason_codes,
        ),
        source_refs=list(packet.source_refs),
        explainable_facts=list(packet.explainable_facts),
        admin_diagnostics=admin_diagnostics,
    )
    return _finalize_packet(adjusted)


__all__ = [
    "backtest_readiness_to_ai_packet",
    "normalize_engine_evidence_to_ai_packet",
    "options_gates_to_ai_packet",
    "portfolio_risk_to_ai_packet",
    "rotation_evidence_to_ai_packet",
    "scanner_evidence_to_ai_packet",
]
