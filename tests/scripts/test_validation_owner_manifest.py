from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts import validation_changed_files as planner


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "validation" / "validation_owners.json"


def load_manifest() -> tuple[dict, str]:
    return planner.load_owner_manifest(MANIFEST_PATH, root=ROOT)


def test_owner_manifest_is_shadow_only_and_all_named_test_owners_are_listable() -> None:
    manifest, manifest_hash = load_manifest()

    result = planner.validate_owner_manifest(manifest, root=ROOT, manifest_hash=manifest_hash)

    assert result["status"] == "valid"
    assert result["manifestHash"] == manifest_hash
    assert tuple(manifest["tierOrder"]) == planner.SHADOW_TIERS
    test_owners = {
        owner_id: targets
        for owner_id, targets in result["resolvedTargets"].items()
        if manifest["owners"][owner_id].get("targets")
    }
    assert test_owners
    assert all(targets for targets in test_owners.values())


def test_nonexistent_owner_reference_is_rejected() -> None:
    manifest, _ = load_manifest()
    broken = deepcopy(manifest)
    broken["rules"][0]["owners"]["direct_owner"].append("direct.does.not.exist")

    with pytest.raises(planner.OwnerManifestError, match="nonexistent owner"):
        planner.validate_owner_manifest(broken, root=ROOT)


def test_exhaustive_tracked_path_inventory_has_no_mapping_gap() -> None:
    manifest, manifest_hash = load_manifest()
    planner.validate_owner_manifest(manifest, root=ROOT, manifest_hash=manifest_hash)

    inventory = planner.tracked_path_inventory(manifest, root=ROOT, manifest_hash=manifest_hash)

    assert inventory["trackedValidationRelevantPathCount"] > 2_000
    assert inventory["explicitRulePathCount"] + inventory["unknownEscalationPathCount"] == inventory[
        "trackedValidationRelevantPathCount"
    ]
    assert inventory["unknownEscalationPaths"] == []
    assert inventory["silentlyUnmappedPaths"] == []
    assert inventory["inventoryHash"] == planner.stable_hash(
        {key: value for key, value in inventory.items() if key != "inventoryHash"}
    )


def test_every_protected_rule_fails_closed_to_baseline_milestone_and_release() -> None:
    manifest, _ = load_manifest()

    protected_rules = [rule for rule in manifest["rules"] if rule.get("protected")]

    assert protected_rules
    for rule in protected_rules:
        assert rule["reason"]
        assert rule["owners"]["protected_baseline_comparison"]
        assert rule["owners"]["milestone"]
        assert rule["owners"]["release"]


def test_shadow_owners_never_downgrade_any_tracked_legacy_escalation() -> None:
    manifest, _ = load_manifest()
    tracked_paths = planner.decode_z_paths(planner.run_git_bytes(["ls-files", "-z"], root=ROOT))

    for path in tracked_paths:
        legacy = planner.classify([path], root=ROOT)
        if not (legacy["hasProtectedDomain"] or legacy["hasFullGateRisk"] or legacy["hasUnknown"]):
            continue
        rules = planner.matching_rules(path, manifest)
        owner_ids = set(planner.owner_ids_for_rules(rules)) if rules else set(manifest["unknownEscalation"]["owners"])
        assert "protected.baseline.current_gate" in owner_ids, path
        assert "release.full.validation" in owner_ids, path
