# -*- coding: utf-8 -*-
"""Offline validator for additive AI evidence packets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from src.services.ai_evidence_packet import (
    AI_EVIDENCE_PACKET_VERSION,
    AiEvidenceDecisionStatus,
    AiEvidencePacket,
    coerce_ai_evidence_packet,
    evaluate_evidence_policy,
)


TOP_LEVEL_REQUIRED_FIELDS = (
    "engine",
    "entity",
    "run_id",
    "evidence_version",
    "required_evidence",
    "optional_evidence",
    "freshness",
    "quality_flags",
    "decision_status",
    "confidence_cap",
    "source_refs",
    "explainable_facts",
    "admin_diagnostics",
)
FORBIDDEN_SOURCE_REF_MARKERS = (
    "raw",
    "payload",
    "request",
    "response",
    "header",
    "headers",
    "token",
    "cookie",
    "authorization",
    "prompt",
)
FORBIDDEN_SOURCE_REF_VALUE_MARKERS = (
    "authorization:",
    "bearer ",
    "set-cookie",
    "cookie=",
    "raw prompt",
    "raw_payload",
)
SAFE_SOURCE_REF_FIELDS = {"raw_payload_stored"}


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(slots=True)
class AiEvidenceValidationIssue:
    field: str
    reason_code: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reasonCode": self.reason_code}


@dataclass(slots=True)
class AiEvidenceValidationResult:
    is_valid: bool
    issues: list[dict[str, str]] = field(default_factory=list)


def _append_issue(
    issues: list[AiEvidenceValidationIssue],
    *,
    field: str,
    reason_code: str,
    limit: int,
) -> None:
    if len(issues) >= limit:
        return
    issue = AiEvidenceValidationIssue(field=field, reason_code=reason_code)
    if issue.to_dict() not in [item.to_dict() for item in issues]:
        issues.append(issue)


def _join_path(parent: str, key: str) -> str:
    if parent == "$":
        return key
    return f"{parent}.{key}"


def _scan_source_ref_tree(
    value: Any,
    *,
    field: str,
    issues: list[AiEvidenceValidationIssue],
    limit: int,
) -> None:
    if len(issues) >= limit:
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_field = _join_path(field, key_text)
            normalized_key = _normalize_key(key_text)
            if normalized_key not in SAFE_SOURCE_REF_FIELDS and any(
                marker in normalized_key for marker in FORBIDDEN_SOURCE_REF_MARKERS
            ):
                _append_issue(
                    issues,
                    field=child_field,
                    reason_code="unsafe_source_ref_field",
                    limit=limit,
                )
            _scan_source_ref_tree(child, field=child_field, issues=issues, limit=limit)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_source_ref_tree(child, field=f"{field}[{index}]", issues=issues, limit=limit)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in FORBIDDEN_SOURCE_REF_VALUE_MARKERS):
            _append_issue(
                issues,
                field=field,
                reason_code="unsafe_source_ref_value",
                limit=limit,
            )


def validate_ai_evidence_packet(
    value: AiEvidencePacket | Mapping[str, Any],
    *,
    strict: bool = False,
    issue_limit: int = 20,
) -> AiEvidenceValidationResult:
    limit = max(1, int(issue_limit or 20))
    issues: list[AiEvidenceValidationIssue] = []
    raw_packet = value.to_dict() if isinstance(value, AiEvidencePacket) else _coerce_mapping(value)
    if not raw_packet:
        _append_issue(issues, field="$", reason_code="invalid_packet_shape", limit=limit)
        result = AiEvidenceValidationResult(is_valid=False, issues=[item.to_dict() for item in issues])
        if strict:
            raise ValueError("ai evidence packet validation failed: invalid_packet_shape")
        return result

    for field in TOP_LEVEL_REQUIRED_FIELDS:
        if field not in raw_packet:
            _append_issue(issues, field=field, reason_code="missing_required_field", limit=limit)

    if raw_packet.get("evidence_version") not in {AI_EVIDENCE_PACKET_VERSION}:
        _append_issue(issues, field="evidence_version", reason_code="invalid_evidence_version", limit=limit)

    packet = coerce_ai_evidence_packet(value)
    source_ref_ids = {source.source_ref_id for source in packet.source_refs if source.source_ref_id}

    for index, fact in enumerate(packet.explainable_facts):
        if fact.user_visible and not fact.source_ref_ids:
            _append_issue(
                issues,
                field=f"explainable_facts[{index}].source_ref_ids",
                reason_code="user_visible_fact_missing_source_ref",
                limit=limit,
            )
        for source_ref_id in fact.source_ref_ids:
            if source_ref_id not in source_ref_ids:
                _append_issue(
                    issues,
                    field=f"explainable_facts[{index}].source_ref_ids",
                    reason_code="unknown_source_ref",
                    limit=limit,
                )

    for index, source_ref in enumerate(raw_packet.get("source_refs") or []):
        _scan_source_ref_tree(source_ref, field=f"source_refs[{index}]", issues=issues, limit=limit)

    policy = evaluate_evidence_policy(packet)
    if packet.confidence_cap.value > policy.confidence_cap.value:
        _append_issue(
            issues,
            field="confidence_cap.value",
            reason_code="confidence_cap_exceeds_policy",
            limit=limit,
        )
    if packet.decision_status is AiEvidenceDecisionStatus.ALLOWED and policy.decision_status is not AiEvidenceDecisionStatus.ALLOWED:
        _append_issue(
            issues,
            field="decision_status",
            reason_code="decision_status_exceeds_policy",
            limit=limit,
        )
    if packet.decision_status is AiEvidenceDecisionStatus.CAUTION and policy.decision_status is AiEvidenceDecisionStatus.FORBIDDEN:
        _append_issue(
            issues,
            field="decision_status",
            reason_code="decision_status_exceeds_policy",
            limit=limit,
        )
    if (
        packet.decision_status is AiEvidenceDecisionStatus.ALLOWED
        and "fixture_or_synthetic_required_evidence" in policy.confidence_cap.reason_codes
    ):
        _append_issue(
            issues,
            field="decision_status",
            reason_code="fixture_required_evidence_forbidden",
            limit=limit,
        )

    result = AiEvidenceValidationResult(
        is_valid=not issues,
        issues=[item.to_dict() for item in issues],
    )
    if strict and not result.is_valid:
        summary = ", ".join(issue["reasonCode"] for issue in result.issues[:5])
        raise ValueError(f"ai evidence packet validation failed: {summary}")
    return result


__all__ = [
    "AiEvidenceValidationIssue",
    "AiEvidenceValidationResult",
    "validate_ai_evidence_packet",
]
