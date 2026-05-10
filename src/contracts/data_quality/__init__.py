# -*- coding: utf-8 -*-
"""Future-facing data-quality contract boundary delegating to existing implementations."""

from src.contracts.data_quality.contracts import (
    CONTRACT_VERSION,
    DataQualityClass,
    DataQualityContractField,
    DataQualityStatus,
    EngineId,
    EngineRequiredFieldContract,
    EvidenceCriticality,
    SourceRefPolicy,
    coerce_engine_required_field_contract,
    evaluate_confidence_cap_effect,
    get_engine_required_field_contract,
)
from src.contracts.data_quality.validator import (
    DataQualityValidationIssue,
    DataQualityValidationResult,
    validate_data_quality_contract,
)

__all__ = [
    "CONTRACT_VERSION",
    "DataQualityClass",
    "DataQualityContractField",
    "DataQualityStatus",
    "EngineId",
    "EngineRequiredFieldContract",
    "EvidenceCriticality",
    "SourceRefPolicy",
    "coerce_engine_required_field_contract",
    "evaluate_confidence_cap_effect",
    "get_engine_required_field_contract",
    "DataQualityValidationIssue",
    "DataQualityValidationResult",
    "validate_data_quality_contract",
]
