# -*- coding: utf-8 -*-
"""Offline validator for inert data-quality required-field contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from src.services.data_quality_contracts import (
    CONTRACT_VERSION,
    DataQualityClass,
    DataQualityContractField,
    EngineId,
    EngineRequiredFieldContract,
    EvidenceCriticality,
    coerce_engine_required_field_contract,
    evaluate_confidence_cap_effect,
    get_engine_required_field_contract,
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
SAFE_SOURCE_REF_FIELDS = {"source_ref_id", "source_class", "provider", "raw_payload_stored", "sanitized_reason_code"}


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _join_path(parent: str, key: str) -> str:
    if parent == "$":
        return key
    return f"{parent}.{key}"


@dataclass(slots=True)
class DataQualityValidationIssue:
    field: str
    reason_code: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reasonCode": self.reason_code}


@dataclass(slots=True)
class DataQualityValidationResult:
    is_valid: bool
    issues: list[dict[str, str]] = field(default_factory=list)


def _append_issue(
    issues: list[DataQualityValidationIssue],
    *,
    field: str,
    reason_code: str,
    limit: int,
) -> None:
    if len(issues) >= limit:
        return
    issue = DataQualityValidationIssue(field=field, reason_code=reason_code)
    if issue.to_dict() not in [item.to_dict() for item in issues]:
        issues.append(issue)


def _scan_source_ref_tree(
    value: Any,
    *,
    field: str,
    issues: list[DataQualityValidationIssue],
    limit: int,
) -> None:
    if len(issues) >= limit:
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_field = _join_path(field, key_text)
            normalized_key = _normalize_key(key_text)
            if normalized_key not in SAFE_SOURCE_REF_FIELDS and any(marker in normalized_key for marker in FORBIDDEN_SOURCE_REF_MARKERS):
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


def _enum_values(enum_cls: type[Any]) -> set[str]:
    return {item.value for item in enum_cls}


def validate_data_quality_contract(
    value: EngineRequiredFieldContract | Mapping[str, Any],
    *,
    strict: bool = False,
    issue_limit: int = 20,
) -> DataQualityValidationResult:
    limit = max(1, int(issue_limit or 20))
    issues: list[DataQualityValidationIssue] = []
    raw_contract = value.to_dict() if isinstance(value, EngineRequiredFieldContract) else _coerce_mapping(value)
    if not raw_contract:
        _append_issue(issues, field="$", reason_code="invalid_contract_shape", limit=limit)
        result = DataQualityValidationResult(is_valid=False, issues=[item.to_dict() for item in issues])
        if strict:
            raise ValueError("data quality contract validation failed: invalid_contract_shape")
        return result

    engine_value = str(raw_contract.get("engine") or "").strip()
    if engine_value not in _enum_values(EngineId):
        _append_issue(issues, field="engine", reason_code="invalid_engine_id", limit=limit)
        result = DataQualityValidationResult(is_valid=False, issues=[item.to_dict() for item in issues])
        if strict:
            raise ValueError("data quality contract validation failed: invalid_engine_id")
        return result

    if raw_contract.get("contract_version") != CONTRACT_VERSION:
        _append_issue(issues, field="contract_version", reason_code="invalid_contract_version", limit=limit)

    contract = coerce_engine_required_field_contract(raw_contract)
    registry_contract = get_engine_required_field_contract(contract.engine)
    required_field_keys = {field.field_key for field in registry_contract.required_fields}

    if not registry_contract.required_fields:
        _append_issue(issues, field="required_fields", reason_code="registry_required_fields_empty", limit=limit)
    if not contract.required_fields:
        _append_issue(issues, field="required_fields", reason_code="required_fields_empty", limit=limit)

    for index, raw_field in enumerate(raw_contract.get("required_fields") or []):
        if str(raw_field.get("criticality") or "").strip() != EvidenceCriticality.REQUIRED.value:
            _append_issue(
                issues,
                field=f"required_fields[{index}].criticality",
                reason_code="invalid_required_field_criticality",
                limit=limit,
            )
        if str(raw_field.get("data_quality_class") or "").strip() not in _enum_values(DataQualityClass):
            _append_issue(
                issues,
                field=f"required_fields[{index}].data_quality_class",
                reason_code="invalid_data_quality_class",
                limit=limit,
            )

    for group_name in ("important_fields", "optional_fields"):
        for index, raw_field in enumerate(raw_contract.get(group_name) or []):
            if str(raw_field.get("data_quality_class") or "").strip() not in _enum_values(DataQualityClass):
                _append_issue(
                    issues,
                    field=f"{group_name}[{index}].data_quality_class",
                    reason_code="invalid_data_quality_class",
                    limit=limit,
                )

    required_lookup = {field.field_key: field for field in contract.required_fields}
    for field_key in sorted(required_field_keys):
        if field_key not in required_lookup:
            _append_issue(
                issues,
                field=f"required_fields.{field_key}",
                reason_code="missing_required_field_entry",
                limit=limit,
            )
            continue

        field_item = required_lookup[field_key]
        if field_item.criticality is not EvidenceCriticality.REQUIRED:
            _append_issue(
                issues,
                field=f"required_fields.{field_key}.criticality",
                reason_code="invalid_required_field_criticality",
                limit=limit,
            )

        if field_item.data_quality_class is DataQualityClass.MISSING or str(field_item.status.value) == "missing":
            _append_issue(
                issues,
                field=f"required_fields.{field_key}",
                reason_code="required_field_missing",
                limit=limit,
            )

        effect = evaluate_confidence_cap_effect(field_item)
        if field_item.decision_grade and effect in {"block_decision_grade", "cap_or_block_pending_classification"}:
            _append_issue(
                issues,
                field=f"required_fields.{field_key}.decision_grade",
                reason_code="invalid_required_decision_grade",
                limit=limit,
            )

    for index, raw_source_ref in enumerate(raw_contract.get("source_ref_policies") or []):
        if bool(raw_source_ref.get("raw_payload_stored")):
            _append_issue(
                issues,
                field=f"source_ref_policies[{index}].raw_payload_stored",
                reason_code="raw_payload_storage_not_allowed",
                limit=limit,
            )
        _scan_source_ref_tree(raw_source_ref, field=f"source_ref_policies[{index}]", issues=issues, limit=limit)

    result = DataQualityValidationResult(
        is_valid=not issues,
        issues=[item.to_dict() for item in issues],
    )
    if strict and not result.is_valid:
        summary = ", ".join(issue["reasonCode"] for issue in result.issues[:5])
        raise ValueError(f"data quality contract validation failed: {summary}")
    return result


__all__ = [
    "DataQualityValidationIssue",
    "DataQualityValidationResult",
    "validate_data_quality_contract",
]
