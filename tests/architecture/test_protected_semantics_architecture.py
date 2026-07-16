"""Architecture checks for the T457 W1 protected-semantics matrix."""

from __future__ import annotations

from pathlib import Path

from scripts.architecture import protected_semantics
from scripts import domain_test_topology


ROOT = Path(__file__).resolve().parents[2]


def test_protected_semantics_matrix_is_complete_and_canonical() -> None:
    matrix = protected_semantics.load_matrix()
    case_ids = tuple(case["id"] for case in matrix["cases"])

    assert matrix["schemaVersion"] == "t457-w1-protected-semantics-v1"
    assert case_ids == protected_semantics.REQUIRED_CASE_IDS
    assert all(case["ownerNodes"] for case in matrix["cases"])
    source = protected_semantics.MATRIX_PATH.read_text(encoding="utf-8")
    assert source.endswith("\n")
    assert "\r" not in source


def test_protected_semantics_reuse_collected_owner_nodes() -> None:
    matrix = protected_semantics.load_matrix()
    topology = domain_test_topology.load_manifest(ROOT / "validation" / "domain_test_topology.json")
    collected = {entry["id"] for entry in topology["backend"]["tests"]}
    owners = {node for case in matrix["cases"] for node in case["ownerNodes"]}

    assert owners <= collected
