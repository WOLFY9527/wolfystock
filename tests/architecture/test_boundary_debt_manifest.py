"""Contract tests for the versioned architecture boundary-debt manifest."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.architecture import boundary_debt


ROOT = Path(__file__).resolve().parents[2]


def test_boundary_debt_manifest_is_canonical_and_reproduces_current_main() -> None:
    manifest = boundary_debt.load_manifest()

    boundary_debt.validate_manifest(manifest)

    assert manifest["schemaVersion"] == "t457-w1-boundary-debt-v1"
    assert {
        family: len(details["entries"])
        for family, details in manifest["families"].items()
    } == {
        "directStorageConsumers": 51,
        "providerHeavyConstructionPoints": 21,
        "serviceToApiSchemaEdges": 46,
    }
    assert boundary_debt.render_manifest(manifest) == boundary_debt.MANIFEST_PATH.read_text(
        encoding="utf-8"
    )
    assert boundary_debt.reproduce_manifest(ROOT, manifest) == manifest
    assert boundary_debt.reproduce_manifest(ROOT, manifest) == boundary_debt.reproduce_manifest(
        ROOT, manifest
    )


def test_boundary_debt_manifest_validation_rejects_noncanonical_payloads() -> None:
    manifest = boundary_debt.load_manifest()
    invalid_cases: list[tuple[str, dict[str, object]]] = []

    wrong_version = deepcopy(manifest)
    wrong_version["schemaVersion"] = "t457-w1-boundary-debt-v2"
    invalid_cases.append(("schemaVersion", wrong_version))

    non_normalized_path = deepcopy(manifest)
    non_normalized_path["families"]["directStorageConsumers"]["entries"][0]["path"] = (
        "./api/app.py"
    )
    invalid_cases.append(("normalized repository-relative POSIX path", non_normalized_path))

    duplicate_entry = deepcopy(manifest)
    schema_entries = duplicate_entry["families"]["serviceToApiSchemaEdges"]["entries"]
    schema_entries[-1] = deepcopy(schema_entries[0])
    invalid_cases.append(("unique entries", duplicate_entry))

    unordered_entries = deepcopy(manifest)
    storage_entries = unordered_entries["families"]["directStorageConsumers"]["entries"]
    storage_entries[0], storage_entries[1] = storage_entries[1], storage_entries[0]
    invalid_cases.append(("sorted entries", unordered_entries))

    unordered_imports = deepcopy(manifest)
    provider_entry = next(
        entry
        for entry in unordered_imports["families"]["providerHeavyConstructionPoints"]["entries"]
        if len(entry["imports"]) > 1
    )
    provider_entry["imports"] = list(reversed(provider_entry["imports"]))
    invalid_cases.append(("sorted unique imports", unordered_imports))

    unordered_constructions = deepcopy(manifest)
    provider_entry = next(
        entry
        for entry in unordered_constructions["families"]["providerHeavyConstructionPoints"][
            "entries"
        ]
        if len(entry["constructions"]) > 1
    )
    provider_entry["constructions"] = list(reversed(provider_entry["constructions"]))
    invalid_cases.append(("sorted unique construction points", unordered_constructions))

    for expected_message, payload in invalid_cases:
        with pytest.raises(boundary_debt.DebtManifestError, match=expected_message):
            boundary_debt.validate_manifest(payload)


def test_boundary_debt_reduction_requires_removing_the_manifest_entry(tmp_path: Path) -> None:
    source = tmp_path / "src" / "services" / "legacy.py"
    source.parent.mkdir(parents=True)
    source.write_text("from api.v1.schemas.legacy import LegacyResponse\n", encoding="utf-8")
    manifest = boundary_debt.load_manifest()
    family = manifest["families"]["serviceToApiSchemaEdges"]
    family["entries"] = boundary_debt.collect_family(
        tmp_path, "serviceToApiSchemaEdges"
    )

    boundary_debt.assert_family_matches(tmp_path, manifest, "serviceToApiSchemaEdges")

    source.unlink()
    with pytest.raises(boundary_debt.DebtMismatchError, match="stale manifest entries"):
        boundary_debt.assert_family_matches(tmp_path, manifest, "serviceToApiSchemaEdges")

    family["entries"] = []
    boundary_debt.assert_family_matches(tmp_path, manifest, "serviceToApiSchemaEdges")
