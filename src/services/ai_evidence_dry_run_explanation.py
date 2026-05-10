# -*- coding: utf-8 -*-
"""Deterministic display-only composer for AI evidence explanation previews."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from src.services.ai_evidence_packet import (
    AI_EVIDENCE_PACKET_VERSION,
    AiEvidenceDecisionStatus,
    AiEvidenceEngine,
    AiEvidenceFreshnessClass,
    AiEvidencePacket,
    coerce_ai_evidence_packet,
    evaluate_evidence_policy,
)
from src.services.ai_evidence_packet_validator import validate_ai_evidence_packet


_FORBIDDEN_USER_TERMS = (
    "raw",
    "debug",
    "schema",
    "trace",
    "prompt",
    "token",
    "cookie",
    "authorization",
    "stack trace",
    "provider_timeout",
    "marketcache",
    "local_db",
    "fixture",
    "mock",
    "synthetic",
    "generatedcandidates",
    "failedcandidates",
)
_KNOWN_ENGINES = {item.value for item in AiEvidenceEngine}
_USER_LABEL_DATA_BLOCKED = "数据不足，禁止判断"
_USER_LABEL_OBSERVE_ONLY = "仅供观察"
_USER_LABEL_REVIEW_REQUIRED = "需人工复核"
_USER_LABEL_STALE = "数据已过期"
_USER_LABEL_FALLBACK = "备用数据"
_USER_LABEL_REAL_FLOW_MISSING = "真实资金流暂缺"
_USER_LABEL_RESEARCH_ONLY = "研究级回测"
_USER_LABEL_RISK_OBSERVE_ONLY = "仅供风险观察"
_USER_LABEL_DEMO_DATA = "演示数据"
_USER_LABEL_LINEAGE_REVIEW = "持仓来源待核验"
_USER_LABEL_CASH_INCOMPLETE = "现金流水不完整"
_USER_LABEL_AUTHORITY_REVIEW = "依据需复核"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(target: list[str], value: Any) -> None:
    text = _text(value)
    if text and text not in target:
        target.append(text)


def _iter_strings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [text for item in value if (text := _text(item))]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _raw_packet(value: AiEvidencePacket | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, AiEvidencePacket):
        return value.to_dict()
    return _mapping(value)


def _source_packet_version(raw_packet: dict[str, Any], packet: AiEvidencePacket) -> str:
    return _text(raw_packet.get("evidence_version")) or packet.evidence_version


def _raw_engine(raw_packet: dict[str, Any], packet: AiEvidencePacket) -> str:
    return _text(raw_packet.get("engine")) or packet.engine.value


def _clean_user_text(value: Any) -> str:
    text = _text(value)
    lowered = text.lower()
    if not text:
        return ""
    if any(term in lowered for term in _FORBIDDEN_USER_TERMS):
        return ""
    if "dry-run" in lowered or "dry_run" in lowered:
        return ""
    return text


def _reason_codes(packet: AiEvidencePacket) -> list[str]:
    codes: list[str] = []
    for code in packet.confidence_cap.reason_codes:
        _append_unique(codes, code)
    for code in packet.quality_flags:
        _append_unique(codes, code)
    for item in [*packet.required_evidence, *packet.optional_evidence]:
        for code in item.reason_codes:
            _append_unique(codes, code)
    for key in (
        "fail_closed_reason_codes",
        "gate_issue_codes",
        "disabled_claims",
        "reason_codes",
        "risk_labels",
    ):
        for code in _iter_strings(packet.admin_diagnostics.get(key)):
            _append_unique(codes, code)
    required_status = _mapping(packet.admin_diagnostics.get("required_data_status"))
    for code in _iter_strings(required_status.get("missingReasonCodes")):
        _append_unique(codes, code)
    return codes


def _limit_confidence(value: int) -> int:
    return max(0, min(100, int(value)))


def _policy_adjusted_cap(packet: AiEvidencePacket) -> int:
    policy = evaluate_evidence_policy(packet)
    return _limit_confidence(min(packet.confidence_cap.value, policy.confidence_cap.value))


def _collect_disabled_claims(packet: AiEvidencePacket) -> list[str]:
    disabled_claims = _iter_strings(packet.admin_diagnostics.get("disabled_claims"))

    if packet.engine is AiEvidenceEngine.OPTIONS:
        _append_unique(disabled_claims, "options_recommendation")
        _append_unique(disabled_claims, "options_tradeability")
    if packet.engine is AiEvidenceEngine.BACKTEST and (
        "research_prototype_only" in packet.confidence_cap.reason_codes
        or not bool(packet.admin_diagnostics.get("professional_quant_ready", True))
    ):
        _append_unique(disabled_claims, "professional_backtest_claim")
    if packet.engine is AiEvidenceEngine.PORTFOLIO_RISK and (
        any(item.key == "fx.freshness" and item.status.value == "stale" for item in packet.required_evidence)
    ):
        _append_unique(disabled_claims, "strong_risk_conclusion")
    if packet.engine is AiEvidenceEngine.ROTATION and (
        packet.admin_diagnostics.get("flow_evidence_type") == "proxy_only"
        or packet.admin_diagnostics.get("flow_language_allowed") is False
    ):
        _append_unique(disabled_claims, "real_fund_flow_claim")

    return disabled_claims


def _collect_limitation_labels(packet: AiEvidencePacket, *, invalid: bool) -> list[str]:
    labels: list[str] = []
    codes = _reason_codes(packet)
    lower_codes = {code.lower() for code in codes}

    if invalid:
        _append_unique(labels, _USER_LABEL_REVIEW_REQUIRED)

    if packet.engine is AiEvidenceEngine.OPTIONS:
        _append_unique(labels, _USER_LABEL_DATA_BLOCKED)
    if packet.engine is AiEvidenceEngine.PORTFOLIO_RISK:
        _append_unique(labels, _USER_LABEL_RISK_OBSERVE_ONLY)

    if (
        packet.decision_status is AiEvidenceDecisionStatus.FORBIDDEN
        or "required_data_missing" in lower_codes
    ):
        _append_unique(labels, _USER_LABEL_DATA_BLOCKED)
    if packet.decision_status is AiEvidenceDecisionStatus.CAUTION:
        _append_unique(labels, _USER_LABEL_OBSERVE_ONLY)

    if "stale_required_data" in lower_codes:
        _append_unique(labels, _USER_LABEL_STALE)
    if "stale_fx" in lower_codes:
        _append_unique(labels, "FX 汇率已过期")
    if any(item.freshness_class is AiEvidenceFreshnessClass.FALLBACK for item in packet.required_evidence):
        _append_unique(labels, _USER_LABEL_FALLBACK)
    if any(source.source_class.value == "fallback" for source in packet.source_refs):
        _append_unique(labels, _USER_LABEL_FALLBACK)

    if (
        "rotation_proxy_only_flow_boundary" in lower_codes
        or "flow_proxy_only" in lower_codes
        or "real_flow_missing" in lower_codes
        or packet.admin_diagnostics.get("flow_evidence_type") == "proxy_only"
        or packet.admin_diagnostics.get("flow_language_allowed") is False
    ):
        _append_unique(labels, _USER_LABEL_REAL_FLOW_MISSING)

    if "research_prototype_only" in lower_codes or not bool(packet.admin_diagnostics.get("professional_quant_ready", True)):
        _append_unique(labels, _USER_LABEL_RESEARCH_ONLY)

    if "fixture_or_synthetic_required_evidence" in lower_codes:
        _append_unique(labels, _USER_LABEL_DEMO_DATA)

    for label in _iter_strings(packet.admin_diagnostics.get("limitation_labels")):
        cleaned = _clean_user_text(label)
        if cleaned:
            _append_unique(labels, cleaned)

    if packet.engine is AiEvidenceEngine.PORTFOLIO_RISK:
        for item in packet.required_evidence:
            if item.key == "holdings.lineage" and item.status.value != "available":
                _append_unique(labels, _USER_LABEL_LINEAGE_REVIEW)
            if item.key == "cash.ledger" and item.status.value != "available":
                _append_unique(labels, _USER_LABEL_CASH_INCOMPLETE)
            if item.key == "source.authority" and "mixed" in " ".join(item.reason_codes).lower():
                _append_unique(labels, _USER_LABEL_AUTHORITY_REVIEW)

    cleaned_labels = []
    for label in labels:
        cleaned = _clean_user_text(label)
        if cleaned:
            _append_unique(cleaned_labels, cleaned)
    return cleaned_labels


def _valid_posture(packet: AiEvidencePacket, *, cap: int, labels: list[str]) -> str:
    if packet.decision_status is AiEvidenceDecisionStatus.FORBIDDEN:
        return "blocked"
    if (
        packet.decision_status is AiEvidenceDecisionStatus.CAUTION
        or cap <= 75
        or _USER_LABEL_DATA_BLOCKED in labels
        or _USER_LABEL_OBSERVE_ONLY in labels
        or _USER_LABEL_RESEARCH_ONLY in labels
        or _USER_LABEL_RISK_OBSERVE_ONLY in labels
        or _USER_LABEL_REAL_FLOW_MISSING in labels
    ):
        return "observe_only"
    return "allowed_metadata_only"


def _invalid_posture(packet: AiEvidencePacket, issue_codes: set[str]) -> str:
    if _source_packet_version({}, packet) != AI_EVIDENCE_PACKET_VERSION:
        return "review_required"
    if "invalid_evidence_version" in issue_codes or "unsupported_engine" in issue_codes:
        return "review_required"
    policy = evaluate_evidence_policy(packet)
    if policy.decision_status is AiEvidenceDecisionStatus.FORBIDDEN:
        return "blocked"
    return "review_required"


def _invalid_summary(packet: AiEvidencePacket, posture: str) -> str:
    if packet.engine is AiEvidenceEngine.OPTIONS or posture == "blocked":
        return "证据校验未通过，当前仅可用于人工复核，禁止判断。"
    if packet.decision_status is AiEvidenceDecisionStatus.FORBIDDEN:
        return "证据校验未通过，当前仅可用于人工复核，禁止判断。"
    return "证据校验未通过，当前仅可用于人工复核，禁止判断。"


def _valid_summary(packet: AiEvidencePacket, posture: str, labels: list[str]) -> str:
    if packet.engine is AiEvidenceEngine.OPTIONS:
        return "当前期权证据不足，数据不足，禁止判断，仅保留观察与人工复核。"
    if packet.engine is AiEvidenceEngine.ROTATION and _USER_LABEL_REAL_FLOW_MISSING in labels:
        return "当前为轮动代理证据，真实资金流暂缺，仅供观察。"
    if packet.engine is AiEvidenceEngine.BACKTEST and _USER_LABEL_RESEARCH_ONLY in labels:
        return "当前仅为研究级回测证据，仅供观察，不构成机构级验证结论。"
    if packet.engine is AiEvidenceEngine.PORTFOLIO_RISK:
        if "FX 汇率已过期" in labels:
            return "当前组合风险证据存在 FX 汇率约束，仅供风险观察，不输出确定性风险结论。"
        if _USER_LABEL_LINEAGE_REVIEW in labels or _USER_LABEL_CASH_INCOMPLETE in labels:
            return "当前组合风险证据链不完整，仅供风险观察，不输出确定性风险结论。"
        return "当前组合风险证据仅供风险观察，不输出确定性风险结论。"
    if posture == "allowed_metadata_only":
        return "当前证据链已校验，可用于观察，不提升任何判断强度。"
    if _USER_LABEL_DATA_BLOCKED in labels:
        return "当前证据不足，禁止判断，仅保留观察与人工复核。"
    if _USER_LABEL_STALE in labels or _USER_LABEL_FALLBACK in labels:
        return "当前证据存在时效或来源约束，仅供观察。"
    return "当前证据仅供观察，不形成推荐性结论。"


@dataclass(slots=True)
class AiEvidenceDryRunExplanation:
    explanation_mode: str = "dry_run"
    source_packet_version: str = AI_EVIDENCE_PACKET_VERSION
    engine: str = AiEvidenceEngine.ANALYSIS.value
    posture: str = "review_required"
    confidence_cap: int = 0
    disabled_claims: list[str] = field(default_factory=list)
    safe_summary: str = ""
    limitation_labels: list[str] = field(default_factory=list)
    admin_reason_code_count: int = 0
    generated_at: str = field(default_factory=_now_iso)
    validation_state: str = "not_evaluated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "explanation_mode": self.explanation_mode,
            "source_packet_version": self.source_packet_version,
            "engine": self.engine,
            "posture": self.posture,
            "confidence_cap": self.confidence_cap,
            "disabled_claims": list(self.disabled_claims),
            "safe_summary": self.safe_summary,
            "limitation_labels": list(self.limitation_labels),
            "admin_reason_code_count": self.admin_reason_code_count,
            "generated_at": self.generated_at,
            "validation_state": self.validation_state,
        }


def compose_ai_evidence_dry_run_explanation(
    value: AiEvidencePacket | Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> AiEvidenceDryRunExplanation:
    raw_packet = _raw_packet(value)
    packet = coerce_ai_evidence_packet(value)
    validation = validate_ai_evidence_packet(raw_packet)
    validation_state = "valid" if validation.is_valid else "invalid"
    source_packet_version = _source_packet_version(raw_packet, packet)
    raw_engine = _raw_engine(raw_packet, packet)
    issue_codes = {issue.get("reasonCode", "") for issue in validation.issues}
    cap = _policy_adjusted_cap(packet)

    if source_packet_version != AI_EVIDENCE_PACKET_VERSION:
        validation_state = "invalid"
        issue_codes.add("invalid_evidence_version")
        cap = min(cap, 40)
    if raw_engine and raw_engine not in _KNOWN_ENGINES:
        validation_state = "invalid"
        issue_codes.add("unsupported_engine")
        cap = min(cap, 40)

    limitation_labels = _collect_limitation_labels(packet, invalid=validation_state == "invalid")
    disabled_claims = _collect_disabled_claims(packet)

    if validation_state == "invalid":
        posture = "review_required"
        if packet.decision_status is AiEvidenceDecisionStatus.FORBIDDEN or "required_data_missing" in issue_codes:
            posture = "blocked"
        safe_summary = _invalid_summary(packet, posture)
    else:
        posture = _valid_posture(packet, cap=cap, labels=limitation_labels)
        safe_summary = _valid_summary(packet, posture, limitation_labels)

    safe_summary = _clean_user_text(safe_summary) or "当前证据需人工复核。"
    limitation_labels = [label for label in limitation_labels if _clean_user_text(label)]

    return AiEvidenceDryRunExplanation(
        source_packet_version=source_packet_version,
        engine=raw_engine if raw_engine in _KNOWN_ENGINES else "unknown",
        posture=posture,
        confidence_cap=cap,
        disabled_claims=disabled_claims,
        safe_summary=safe_summary,
        limitation_labels=limitation_labels,
        admin_reason_code_count=len(_reason_codes(packet)),
        generated_at=generated_at or _now_iso(),
        validation_state=validation_state,
    )


__all__ = [
    "AiEvidenceDryRunExplanation",
    "compose_ai_evidence_dry_run_explanation",
]
