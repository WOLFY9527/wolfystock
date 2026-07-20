"""Collect and validate frozen architecture boundary debt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.architecture.boundary_debt_collectors import (
    DIRECT_STORAGE_FAMILY,
    FAMILY_BASELINE_COUNTS,
    PROVIDER_HEAVY_FAMILY,
    PROVIDER_IMPORT_PREFIXES,
    PROVIDER_OWNED_SERVICE_PATHS,
    SERVICE_API_SCHEMA_FAMILY,
    collect_source_graph,
)


MANIFEST_PATH = ROOT / "docs" / "architecture" / "debt-manifest.json"
SCHEMA_VERSION = "t457-w1-boundary-debt-v1"
TASK_ID = "T457-W1-GUARD-008"
OWNER = "architecture_validation"

FAMILY_SPECS = {
    DIRECT_STORAGE_FAMILY: {
        "auditedBaselineCount": FAMILY_BASELINE_COUNTS[DIRECT_STORAGE_FAMILY],
        "entryFields": ("path",),
    },
    PROVIDER_HEAVY_FAMILY: {
        "auditedBaselineCount": FAMILY_BASELINE_COUNTS[PROVIDER_HEAVY_FAMILY],
        "entryFields": ("constructions", "imports", "path"),
    },
    SERVICE_API_SCHEMA_FAMILY: {
        "auditedBaselineCount": FAMILY_BASELINE_COUNTS[SERVICE_API_SCHEMA_FAMILY],
        "entryFields": ("source", "target"),
    },
}
_MODULE_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


class DebtManifestError(ValueError):
    """Raised when the debt manifest is malformed or non-canonical."""


class DebtMismatchError(AssertionError):
    """Raised when collected debt differs from the frozen manifest."""


def _matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Load and validate a boundary-debt manifest."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DebtManifestError(f"cannot load debt manifest {path}: {exc}") from exc
    validate_manifest(payload)
    return payload


def _normalized_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DebtManifestError(f"{label} must be a non-empty string")
    normalized = PurePosixPath(value)
    if (
        "\\" in value
        or value.startswith("./")
        or normalized.is_absolute()
        or ".." in normalized.parts
        or normalized.as_posix() != value
    ):
        raise DebtManifestError(
            f"{label} must be a normalized repository-relative POSIX path: {value!r}"
        )
    return value


def _module_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not _MODULE_RE.fullmatch(value):
        raise DebtManifestError(f"{label} must be a normalized Python module name")
    return value


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    if "source" in entry:
        return (entry["source"], entry["target"])
    if "imports" in entry:
        return (
            entry["path"],
            tuple(entry["imports"]),
            tuple(
                (item["scope"], item["callable"], item["count"])
                for item in entry["constructions"]
            ),
        )
    return (entry["path"],)


def _validate_entry(family: str, entry: object, index: int) -> dict[str, Any]:
    label = f"families.{family}.entries[{index}]"
    if not isinstance(entry, dict):
        raise DebtManifestError(f"{label} must be an object")
    expected_fields = FAMILY_SPECS[family]["entryFields"]
    if tuple(sorted(entry)) != expected_fields:
        raise DebtManifestError(f"{label} fields must be {list(expected_fields)}")

    if family == SERVICE_API_SCHEMA_FAMILY:
        source = _normalized_path(entry["source"], f"{label}.source")
        target = _module_name(entry["target"], f"{label}.target")
        if not source.startswith("src/services/") or not _matches_prefix(
            target, "api.v1.schemas"
        ):
            raise DebtManifestError(f"{label} is outside the service-to-schema boundary")
    elif family == DIRECT_STORAGE_FAMILY:
        path = _normalized_path(entry["path"], f"{label}.path")
        if path.startswith("src/repositories/"):
            raise DebtManifestError(f"{label} must exclude persistence-owner repositories")
    else:
        path = _normalized_path(entry["path"], f"{label}.path")
        imports = entry["imports"]
        constructions = entry["constructions"]
        if not path.startswith("src/services/"):
            raise DebtManifestError(f"{label}.path must identify a service file")
        if path in PROVIDER_OWNED_SERVICE_PATHS:
            raise DebtManifestError(f"{label}.path identifies provider-owned infrastructure")
        if not isinstance(imports, list) or not imports:
            raise DebtManifestError(f"{label}.imports must be a non-empty list")
        normalized_imports = [
            _module_name(module, f"{label}.imports") for module in imports
        ]
        if normalized_imports != sorted(set(normalized_imports)):
            raise DebtManifestError(f"{label} must contain sorted unique imports")
        if any(
            not any(_matches_prefix(module, prefix) for prefix in PROVIDER_IMPORT_PREFIXES)
            for module in normalized_imports
        ):
            raise DebtManifestError(f"{label}.imports contains a non-provider module")
        if not isinstance(constructions, list):
            raise DebtManifestError(f"{label}.constructions must be a list")
        construction_keys: list[tuple[str, str]] = []
        for construction_index, construction in enumerate(constructions):
            construction_label = f"{label}.constructions[{construction_index}]"
            if not isinstance(construction, dict) or set(construction) != {
                "callable",
                "count",
                "scope",
            }:
                raise DebtManifestError(f"{construction_label} has unsupported fields")
            callable_name = _module_name(
                construction["callable"], f"{construction_label}.callable"
            )
            scope = construction["scope"]
            if not isinstance(scope, str) or not scope or (
                scope != "<module>" and not _MODULE_RE.fullmatch(scope)
            ):
                raise DebtManifestError(f"{construction_label}.scope is not normalized")
            count = construction["count"]
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise DebtManifestError(f"{construction_label}.count must be a positive integer")
            construction_keys.append((scope, callable_name))
        if construction_keys != sorted(set(construction_keys)):
            raise DebtManifestError(
                f"{label} must contain sorted unique construction points"
            )
    return entry


def validate_manifest(manifest: object) -> None:
    """Validate schema, normalization, uniqueness, order, and monotonic caps."""

    if not isinstance(manifest, dict):
        raise DebtManifestError("debt manifest root must be an object")
    if set(manifest) != {"families", "schemaVersion"}:
        raise DebtManifestError("debt manifest fields must be families and schemaVersion")
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise DebtManifestError(f"schemaVersion must be {SCHEMA_VERSION}")
    families = manifest.get("families")
    if not isinstance(families, dict) or set(families) != set(FAMILY_SPECS):
        raise DebtManifestError(f"families must be {sorted(FAMILY_SPECS)}")

    for family, spec in FAMILY_SPECS.items():
        details = families[family]
        label = f"families.{family}"
        if not isinstance(details, dict) or set(details) != {
            "auditedBaselineCount",
            "entries",
            "owner",
            "taskId",
        }:
            raise DebtManifestError(f"{label} has unsupported fields")
        if details["auditedBaselineCount"] != spec["auditedBaselineCount"]:
            raise DebtManifestError(
                f"{label}.auditedBaselineCount must be {spec['auditedBaselineCount']}"
            )
        if details["owner"] != OWNER or details["taskId"] != TASK_ID:
            raise DebtManifestError(f"{label} must retain its architecture owner and task")
        entries = details["entries"]
        if not isinstance(entries, list):
            raise DebtManifestError(f"{label}.entries must be a list")
        if len(entries) > spec["auditedBaselineCount"]:
            raise DebtManifestError(f"{label}.entries may only shrink from the audited baseline")
        validated = [_validate_entry(family, entry, index) for index, entry in enumerate(entries)]
        keys = [_entry_sort_key(entry) for entry in validated]
        if len(keys) != len(set(keys)):
            raise DebtManifestError(f"{label} must contain unique entries")
        if keys != sorted(keys):
            raise DebtManifestError(f"{label} must contain sorted entries")


def render_manifest(manifest: dict[str, Any]) -> str:
    """Render canonical, platform-independent JSON."""

    validate_manifest(manifest)
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def reproduce_manifest(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the manifest with all entries deterministically recollected."""

    validate_manifest(manifest)
    reproduced = deepcopy(manifest)
    graph = collect_source_graph(root)
    for family in FAMILY_SPECS:
        reproduced["families"][family]["entries"] = graph.family_entries(family)
    validate_manifest(reproduced)
    return reproduced


def _display_entry(family: str, entry: Mapping[str, Any]) -> str:
    if family == SERVICE_API_SCHEMA_FAMILY:
        return f"{entry['source']} -> {entry['target']}"
    if family == PROVIDER_HEAVY_FAMILY:
        constructions = ", ".join(
            f"{item['scope']} -> {item['callable']} ({item['count']})"
            for item in entry["constructions"]
        ) or "none"
        return (
            f"{entry['path']} -> {', '.join(entry['imports'])}; "
            f"constructions: {constructions}"
        )
    return str(entry["path"])


def assert_family_matches(root: Path, manifest: dict[str, Any], family: str) -> None:
    """Fail on new debt or on reductions not removed from the manifest."""

    validate_manifest(manifest)
    if family not in FAMILY_SPECS:
        raise DebtManifestError(f"unknown debt family: {family}")
    expected = manifest["families"][family]["entries"]
    actual = collect_source_graph(root).family_entries(family)
    expected_by_key = {_entry_sort_key(entry): entry for entry in expected}
    actual_by_key = {_entry_sort_key(entry): entry for entry in actual}
    new_keys = sorted(set(actual_by_key) - set(expected_by_key))
    stale_keys = sorted(set(expected_by_key) - set(actual_by_key))
    if not new_keys and not stale_keys:
        return

    sections = [f"{family} differs from the frozen debt manifest"]
    if new_keys:
        sections.append(
            "new debt entries:\n"
            + "\n".join(f"- {_display_entry(family, actual_by_key[key])}" for key in new_keys)
        )
    if stale_keys:
        sections.append(
            "stale manifest entries:\n"
            + "\n".join(
                f"- {_display_entry(family, expected_by_key[key])}" for key in stale_keys
            )
        )
    raise DebtMismatchError("\n".join(sections))


def _check_manifest(root: Path, path: Path) -> None:
    manifest = load_manifest(path)
    source = path.read_text(encoding="utf-8")
    if source != render_manifest(manifest):
        raise DebtManifestError(f"{path} is not canonical JSON with a trailing newline")
    for family in FAMILY_SPECS:
        assert_family_matches(root, manifest, family)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.check:
            _check_manifest(args.root, args.manifest)
            print(json.dumps({"families": sorted(FAMILY_SPECS), "status": "ok"}))
        else:
            manifest = load_manifest(args.manifest)
            print(render_manifest(reproduce_manifest(args.root, manifest)), end="")
    except (DebtManifestError, DebtMismatchError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
