# -*- coding: utf-8 -*-
"""Future-facing data-quality validator boundary delegating to existing services."""

from src.services.data_quality_contract_validator import (
    DataQualityValidationIssue,
    DataQualityValidationResult,
    validate_data_quality_contract,
)

__all__ = [
    "DataQualityValidationIssue",
    "DataQualityValidationResult",
    "validate_data_quality_contract",
]
