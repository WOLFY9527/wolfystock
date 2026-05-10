# -*- coding: utf-8 -*-
"""Tests for the inert future-facing contracts namespace."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.services import ai_evidence_packet as service_evidence_packet
from src.services import ai_evidence_packet_validator as service_evidence_validator
from src.services import data_quality_contracts as service_data_quality_contracts
from src.services import data_quality_contract_validator as service_data_quality_validator


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_NAMESPACE_MODULES = (
    "src.contracts",
    "src.contracts.evidence",
    "src.contracts.data_quality",
)
ALLOWED_IMPLEMENTATION_MODULES = {
    "src.services.ai_evidence_packet",
    "src.services.ai_evidence_packet_validator",
    "src.services.data_quality_contracts",
    "src.services.data_quality_contract_validator",
}
FORBIDDEN_RUNTIME_PREFIXES = (
    "data_provider",
    "openai",
    "litellm",
    "src.agent",
    "src.core.pipeline",
    "api.v1.endpoints",
    "src.services.litellm_runtime",
    "src.services.market_cache",
    "src.services.market_scanner_service",
    "src.services.market_rotation_radar_service",
    "src.services.options_lab_service",
    "src.services.rule_backtest_service",
    "src.services.portfolio_service",
    "src.services.portfolio_risk_diagnostics",
)
EXCLUDED_ADAPTER_MODULES = (
    "src.services.ai_evidence_adapters",
    "src.services.scanner_evidence_packet",
    "src.services.rotation_state_evidence",
)
SUBPROCESS_TRACKED_PREFIXES = ("src.", "api.", "data_provider")

EXPECTED_EVIDENCE_EXPORTS = {
    "AI_EVIDENCE_PACKET_VERSION",
    "AI_EVIDENCE_CONFIDENCE_POLICY_VERSION",
    "AiEvidenceConfidenceCap",
    "AiEvidenceCriticality",
    "AiEvidenceDecisionStatus",
    "AiEvidenceEngine",
    "AiEvidenceEntity",
    "AiEvidenceFreshnessClass",
    "AiEvidenceItem",
    "AiEvidencePacket",
    "AiEvidencePolicyResult",
    "AiEvidenceSourceClass",
    "AiEvidenceSourceRef",
    "AiEvidenceStatus",
    "AiExplainableFact",
    "coerce_ai_evidence_packet",
    "evaluate_evidence_policy",
    "AiEvidenceValidationIssue",
    "AiEvidenceValidationResult",
    "validate_ai_evidence_packet",
}

EXPECTED_DATA_QUALITY_EXPORTS = {
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
}


def _import_contract_namespaces_in_subprocess() -> set[str]:
    script = f"""
import importlib
import json
import sys

for module_name in {list(CONTRACT_NAMESPACE_MODULES)!r}:
    importlib.import_module(module_name)

loaded_modules = sorted(
    name
    for name in sys.modules
    if name.startswith({SUBPROCESS_TRACKED_PREFIXES!r}) or name in {{"openai", "litellm"}}
)
print(json.dumps({{"loaded_modules": loaded_modules}}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    return set(payload["loaded_modules"])


def _has_loaded_prefix(loaded_modules: set[str], prefix: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for name in loaded_modules)


def test_evidence_namespace_imports_and_exposes_expected_contract_surface() -> None:
    from src.contracts import evidence

    assert EXPECTED_EVIDENCE_EXPORTS == set(evidence.__all__)
    assert evidence.AiEvidencePacket is service_evidence_packet.AiEvidencePacket
    assert evidence.AiEvidenceValidationResult is service_evidence_validator.AiEvidenceValidationResult
    assert not hasattr(evidence, "build_scanner_evidence_packet")
    assert not hasattr(evidence, "scanner_evidence_to_ai_packet")


def test_data_quality_namespace_imports_and_exposes_expected_contract_surface() -> None:
    from src.contracts import data_quality

    assert EXPECTED_DATA_QUALITY_EXPORTS == set(data_quality.__all__)
    assert data_quality.EngineRequiredFieldContract is service_data_quality_contracts.EngineRequiredFieldContract
    assert data_quality.DataQualityValidationResult is service_data_quality_validator.DataQualityValidationResult


def test_contract_submodules_delegate_to_existing_implementations() -> None:
    from src.contracts.data_quality import contracts as data_quality_contracts
    from src.contracts.data_quality import validator as data_quality_validator
    from src.contracts.evidence import packet as evidence_packet
    from src.contracts.evidence import validator as evidence_validator

    assert evidence_packet.AiEvidencePacket is service_evidence_packet.AiEvidencePacket
    assert evidence_validator.validate_ai_evidence_packet is service_evidence_validator.validate_ai_evidence_packet
    assert data_quality_contracts.get_engine_required_field_contract is service_data_quality_contracts.get_engine_required_field_contract
    assert data_quality_validator.validate_data_quality_contract is service_data_quality_validator.validate_data_quality_contract


def test_contract_namespaces_are_inert_and_avoid_runtime_domain_imports() -> None:
    loaded_modules = _import_contract_namespaces_in_subprocess()

    assert set(CONTRACT_NAMESPACE_MODULES).issubset(loaded_modules)
    assert ALLOWED_IMPLEMENTATION_MODULES.issubset(loaded_modules)

    for forbidden_prefix in FORBIDDEN_RUNTIME_PREFIXES:
        assert not _has_loaded_prefix(
            loaded_modules,
            forbidden_prefix,
        ), f"unexpected runtime import side effect: {forbidden_prefix}"


def test_contract_namespaces_exclude_adapter_modules() -> None:
    loaded_modules = _import_contract_namespaces_in_subprocess()

    for module_name in EXCLUDED_ADAPTER_MODULES:
        assert module_name not in loaded_modules, f"unexpected adapter import: {module_name}"
