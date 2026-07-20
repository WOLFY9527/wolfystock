#!/usr/bin/env python3
"""Validate canonical module ownership and dependency contracts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.architecture import boundary_debt


MANIFEST_PATH = ROOT / "docs" / "architecture" / "module-contracts.json"
SCHEMA_VERSION = "t645-module-contracts-v1"
REFERENCE_PATHS = {
    "boundaryDebt": "docs/architecture/debt-manifest.json",
    "documentation": "docs/documentation-manifest.json",
    "protectedSemantics": "docs/contracts/data-trust.md",
    "testTopology": "validation/domain_test_topology.json",
    "validationOwners": "validation/validation_owners.json",
}
MODULE_KINDS = {"backend-domain", "backend-platform", "client", "integration"}
OWNERSHIP_FIELDS = (
    "pathPrefixes",
    "pythonModulePrefixes",
    "pythonModules",
    "pythonPackages",
)
PUBLIC_BOUNDARY_FIELDS = ("pathPrefixes", "pythonModules", "pythonPackages")
MODULE_FIELDS = {
    "allowedDependencies",
    "backendClassification",
    "doesNotOwn",
    "documentationAuthorities",
    "id",
    "kind",
    "ownership",
    "protectedSemantics",
    "publicBoundary",
    "responsibility",
    "topologyDomains",
    "validationOwners",
}
MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
PYTHON_MODULE_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
PYTHON_PREFIX_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*[._]$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ModuleContractError(ValueError):
    """Raised when the canonical module contract is malformed."""


class DependencyViolationError(AssertionError):
    """Raised when source imports an unapproved module dependency."""


class DependencyDriftError(AssertionError):
    """Raised when reviewed dependency debt changes without contract review."""


@dataclass(frozen=True, order=True)
class DependencyEdge:
    """One unique internal Python import across module owners."""

    source: str
    target: str
    source_owner: str
    target_owner: str


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModuleContractError(f"cannot load {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ModuleContractError(f"{label} root must be an object")
    return payload


def _normalized_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ModuleContractError(f"{label} must be a non-empty string")
    normalized = PurePosixPath(value)
    if (
        "\\" in value
        or value.startswith("./")
        or normalized.is_absolute()
        or ".." in normalized.parts
        or normalized.as_posix() != value
    ):
        raise ModuleContractError(
            f"{label} must be a normalized repository-relative POSIX path"
        )
    return value


def _string_list(
    value: object,
    label: str,
    *,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ModuleContractError(f"{label} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ModuleContractError(f"{label} must not be empty")
    if value != sorted(set(value)):
        raise ModuleContractError(f"{label} must be sorted and unique")
    return value


def _selector_lists(
    value: object,
    label: str,
    fields: Sequence[str],
) -> dict[str, list[str]]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ModuleContractError(f"{label} fields must be {sorted(fields)}")
    selectors = {
        field: _string_list(value[field], f"{label}.{field}") for field in fields
    }
    for path in selectors.get("pathPrefixes", []):
        _normalized_path(path, f"{label}.pathPrefixes")
    for module_name in (
        *selectors.get("pythonModules", []),
        *selectors.get("pythonPackages", []),
    ):
        if not PYTHON_MODULE_RE.fullmatch(module_name):
            raise ModuleContractError(f"{label} contains an invalid Python module")
    for prefix in selectors.get("pythonModulePrefixes", []):
        if not PYTHON_PREFIX_RE.fullmatch(prefix):
            raise ModuleContractError(
                f"{label}.pythonModulePrefixes contains an invalid raw module prefix"
            )
    return selectors


def _module_map(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {module["id"]: module for module in manifest["modules"]}


def _python_selector_candidates(
    manifest: Mapping[str, Any], module_name: str
) -> list[tuple[int, int, str]]:
    candidates: list[tuple[int, int, str]] = []
    for module in manifest["modules"]:
        ownership = module["ownership"]
        for selector in ownership["pythonModules"]:
            if module_name == selector:
                candidates.append((len(selector), 3, module["id"]))
        for selector in ownership["pythonPackages"]:
            if module_name == selector or module_name.startswith(f"{selector}."):
                candidates.append((len(selector), 2, module["id"]))
        for selector in ownership["pythonModulePrefixes"]:
            if module_name.startswith(selector):
                candidates.append((len(selector), 1, module["id"]))
    return candidates


def module_for_python_name(
    manifest: Mapping[str, Any], module_name: str
) -> str | None:
    """Resolve explicit ownership; the longest selector is authoritative."""

    candidates = _python_selector_candidates(manifest, module_name)
    if not candidates:
        return None
    best_rank = max((length, kind) for length, kind, _owner in candidates)
    owners = {
        owner
        for length, kind, owner in candidates
        if (length, kind) == best_rank
    }
    if len(owners) != 1:
        raise ModuleContractError(
            f"Python module {module_name!r} has ambiguous owners: {sorted(owners)}"
        )
    return next(iter(owners))


def module_for_path(manifest: Mapping[str, Any], path: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    for module in manifest["modules"]:
        for selector in module["ownership"]["pathPrefixes"]:
            if path == selector or path.startswith(f"{selector}/"):
                candidates.append((len(selector), module["id"]))
    if not candidates:
        return None
    best_length = max(length for length, _owner in candidates)
    owners = {owner for length, owner in candidates if length == best_length}
    if len(owners) != 1:
        raise ModuleContractError(
            f"repository path {path!r} has ambiguous owners: {sorted(owners)}"
        )
    return next(iter(owners))


def classify_backend_module(
    manifest: Mapping[str, Any], module_name: str
) -> str | None:
    owner = module_for_python_name(manifest, module_name)
    if owner is None:
        return None
    classification = _module_map(manifest)[owner]["backendClassification"]
    return classification or None


def backend_domain_classifications(
    manifest: Mapping[str, Any] | None = None,
    *,
    root: Path = ROOT,
) -> dict[str, set[str]]:
    """Expose the canonical classifications used by focused legacy guards."""

    payload = manifest or load_manifest()
    classifications: dict[str, set[str]] = {}
    for module_name in discover_python_modules(Path(root), payload):
        owner = module_for_python_name(payload, module_name)
        if owner is None:
            continue
        label = _module_map(payload)[owner]["backendClassification"]
        if label:
            classifications.setdefault(label, set()).add(module_name)
    return classifications


def _validate_selector_claims(manifest: Mapping[str, Any]) -> None:
    claims: dict[tuple[str, str], str] = {}
    for module in manifest["modules"]:
        module_id = module["id"]
        for field in OWNERSHIP_FIELDS:
            namespace = "path" if field == "pathPrefixes" else "python"
            for selector in module["ownership"][field]:
                key = (namespace, selector)
                previous = claims.get(key)
                if previous is not None and previous != module_id:
                    raise ModuleContractError(
                        f"ownership selector {selector!r} is claimed by both "
                        f"{previous} and {module_id}"
                    )
                claims[key] = module_id


def _validate_public_boundaries(
    manifest: Mapping[str, Any],
    root: Path,
    python_modules: Mapping[str, Path],
) -> None:
    for module in manifest["modules"]:
        module_id = module["id"]
        public = module["publicBoundary"]
        for module_name in public["pythonModules"]:
            if module_name not in python_modules:
                raise ModuleContractError(
                    f"{module_id} public boundary module is missing: {module_name}"
                )
            if module_for_python_name(manifest, module_name) != module_id:
                raise ModuleContractError(
                    f"{module_id} public boundary is owned by another module: {module_name}"
                )
        for package in public["pythonPackages"]:
            matches = [
                name
                for name in python_modules
                if name == package or name.startswith(f"{package}.")
            ]
            if not matches:
                raise ModuleContractError(
                    f"{module_id} public boundary package is missing: {package}"
                )
            if any(
                module_for_python_name(manifest, name) != module_id for name in matches
            ):
                raise ModuleContractError(
                    f"{module_id} public boundary package crosses module ownership: {package}"
                )
        for path in public["pathPrefixes"]:
            if not (root / path).exists():
                raise ModuleContractError(
                    f"{module_id} public boundary path is missing: {path}"
                )
            if module_for_path(manifest, path) != module_id:
                raise ModuleContractError(
                    f"{module_id} public boundary path is owned by another module: {path}"
                )


def validate_manifest(manifest: object, *, root: Path = ROOT) -> None:
    """Validate schema, authority references, ownership, and public boundaries."""

    if not isinstance(manifest, dict):
        raise ModuleContractError("module contract root must be an object")
    if set(manifest) != {
        "dependencyDebt",
        "modules",
        "privateImportDebt",
        "references",
        "schemaVersion",
        "semanticTags",
        "sourceSets",
    }:
        raise ModuleContractError("module contract contains unsupported root fields")
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ModuleContractError(f"schemaVersion must be {SCHEMA_VERSION}")
    if manifest.get("references") != REFERENCE_PATHS:
        raise ModuleContractError("references must reuse the canonical architecture authorities")
    for label, path in REFERENCE_PATHS.items():
        if not (root / path).is_file():
            raise ModuleContractError(f"referenced {label} authority is missing: {path}")

    source_sets = manifest.get("sourceSets")
    if not isinstance(source_sets, dict) or set(source_sets) != {
        "pathRoots",
        "pythonRoots",
        "residualPythonOwners",
    }:
        raise ModuleContractError(
            "sourceSets fields must be pathRoots, pythonRoots, and residualPythonOwners"
        )
    for field in ("pathRoots", "pythonRoots"):
        paths = _string_list(source_sets[field], f"sourceSets.{field}", allow_empty=False)
        for path in paths:
            _normalized_path(path, f"sourceSets.{field}")
            if not (root / path).exists():
                raise ModuleContractError(f"source root is missing: {path}")

    documentation = _read_json(root / REFERENCE_PATHS["documentation"], "documentation manifest")
    documentation_authorities = {
        entry.get("id"): entry for entry in documentation.get("authorities", [])
    }
    documentation_ids = set(documentation_authorities)
    architecture_authority = documentation_authorities.get("system-architecture", {})
    if architecture_authority.get("source") != "docs/architecture/overview.md":
        raise ModuleContractError(
            "documentation authority system-architecture must point to the canonical overview"
        )
    validation = _read_json(root / REFERENCE_PATHS["validationOwners"], "validation owner manifest")
    validation_ids = set(validation.get("owners", {}))
    topology = _read_json(root / REFERENCE_PATHS["testTopology"], "test topology")
    topology_ids = set(topology.get("backend", {}).get("domains", {}))

    tags = manifest.get("semanticTags")
    if not isinstance(tags, list) or not tags:
        raise ModuleContractError("semanticTags must be a non-empty list")
    tag_ids: list[str] = []
    for index, tag in enumerate(tags):
        label = f"semanticTags[{index}]"
        if not isinstance(tag, dict) or set(tag) != {"authorities", "id"}:
            raise ModuleContractError(f"{label} has unsupported fields")
        tag_id = tag.get("id")
        if not isinstance(tag_id, str) or not MODULE_ID_RE.fullmatch(tag_id):
            raise ModuleContractError(f"{label}.id must be a normalized identifier")
        tag_ids.append(tag_id)
        authorities = _string_list(
            tag.get("authorities"), f"{label}.authorities", allow_empty=False
        )
        unknown = sorted(set(authorities) - documentation_ids)
        if unknown:
            raise ModuleContractError(f"{label} has unknown authorities: {unknown}")
    if tag_ids != sorted(set(tag_ids)):
        raise ModuleContractError("semanticTags must have sorted unique ids")

    modules = manifest.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ModuleContractError("modules must be a non-empty list")
    module_ids: list[str] = []
    classification_labels: list[str] = []
    for index, module in enumerate(modules):
        label = f"modules[{index}]"
        if not isinstance(module, dict) or set(module) != MODULE_FIELDS:
            raise ModuleContractError(f"{label} has unsupported fields")
        module_id = module.get("id")
        if not isinstance(module_id, str) or not MODULE_ID_RE.fullmatch(module_id):
            raise ModuleContractError(f"{label}.id must be a normalized identifier")
        module_ids.append(module_id)
        if module.get("kind") not in MODULE_KINDS:
            raise ModuleContractError(f"{label}.kind is unsupported")
        if not isinstance(module.get("responsibility"), str) or not module["responsibility"]:
            raise ModuleContractError(f"{label}.responsibility is required")
        _string_list(module.get("doesNotOwn"), f"{label}.doesNotOwn", allow_empty=False)
        ownership = _selector_lists(module.get("ownership"), f"{label}.ownership", OWNERSHIP_FIELDS)
        if not any(ownership.values()):
            raise ModuleContractError(f"{label}.ownership must declare at least one selector")
        public = _selector_lists(
            module.get("publicBoundary"),
            f"{label}.publicBoundary",
            PUBLIC_BOUNDARY_FIELDS,
        )
        if not any(public.values()):
            raise ModuleContractError(f"{label}.publicBoundary must not be empty")
        classification = module.get("backendClassification")
        if classification is not None:
            if not isinstance(classification, str) or not classification:
                raise ModuleContractError(f"{label}.backendClassification is invalid")
            classification_labels.append(classification)
        for field in (
            "allowedDependencies",
            "documentationAuthorities",
            "protectedSemantics",
            "topologyDomains",
            "validationOwners",
        ):
            _string_list(module.get(field), f"{label}.{field}")
    if module_ids != sorted(set(module_ids)):
        raise ModuleContractError("modules must have sorted unique ids")
    if len(classification_labels) != len(set(classification_labels)):
        raise ModuleContractError("backendClassification labels must be unique")

    module_ids_set = set(module_ids)
    tag_ids_set = set(tag_ids)
    residual_owners = _string_list(
        source_sets["residualPythonOwners"],
        "sourceSets.residualPythonOwners",
        allow_empty=False,
    )
    unknown_residual_owners = sorted(set(residual_owners) - module_ids_set)
    if unknown_residual_owners:
        raise ModuleContractError(
            "sourceSets has unknown residual Python owners: "
            f"{unknown_residual_owners}"
        )
    for module in modules:
        module_id = module["id"]
        dependencies = set(module["allowedDependencies"])
        unknown_dependencies = sorted(dependencies - module_ids_set)
        if unknown_dependencies:
            raise ModuleContractError(
                f"{module_id} has unknown allowed dependency: {unknown_dependencies}"
            )
        if module_id in dependencies:
            raise ModuleContractError(f"{module_id} may not depend on itself explicitly")
        unknown_docs = sorted(set(module["documentationAuthorities"]) - documentation_ids)
        if unknown_docs:
            raise ModuleContractError(
                f"{module_id} has unknown documentation authority: {unknown_docs}"
            )
        unknown_owners = sorted(set(module["validationOwners"]) - validation_ids)
        if unknown_owners:
            raise ModuleContractError(
                f"{module_id} has unknown validation owner: {unknown_owners}"
            )
        unknown_domains = sorted(set(module["topologyDomains"]) - topology_ids)
        if unknown_domains:
            raise ModuleContractError(
                f"{module_id} has unknown topology domain: {unknown_domains}"
            )
        unknown_tags = sorted(set(module["protectedSemantics"]) - tag_ids_set)
        if unknown_tags:
            raise ModuleContractError(
                f"{module_id} has unknown protected semantic: {unknown_tags}"
            )

    _validate_selector_claims(manifest)
    python_modules = discover_python_modules(root, manifest)
    _validate_ownership_selectors(manifest, root, python_modules)
    for module_name in python_modules:
        if module_for_python_name(manifest, module_name) is None:
            raise ModuleContractError(f"Python source has no module owner: {module_name}")
    for path in source_sets["pathRoots"]:
        if module_for_path(manifest, path) is None:
            raise ModuleContractError(f"path source root has no module owner: {path}")
    _validate_public_boundaries(manifest, root, python_modules)

    debt = manifest.get("dependencyDebt")
    if not isinstance(debt, list):
        raise ModuleContractError("dependencyDebt must be a list")
    debt_keys: list[tuple[str, str]] = []
    for index, entry in enumerate(debt):
        label = f"dependencyDebt[{index}]"
        if not isinstance(entry, dict) or set(entry) != {
            "edgeCount",
            "from",
            "reason",
            "retireWhen",
            "reviewOwner",
            "sha256",
            "to",
            "validationOwners",
        }:
            raise ModuleContractError(f"{label} has unsupported fields")
        source_owner = entry.get("from")
        target_owner = entry.get("to")
        if source_owner not in module_ids_set or target_owner not in module_ids_set:
            raise ModuleContractError(f"{label} references an unknown module")
        if source_owner == target_owner:
            raise ModuleContractError(f"{label} must cross module owners")
        debt_keys.append((source_owner, target_owner))
        if target_owner in _module_map(manifest)[source_owner]["allowedDependencies"]:
            raise ModuleContractError(f"{label} overlaps an allowed dependency")
        if (
            not isinstance(entry.get("edgeCount"), int)
            or isinstance(entry["edgeCount"], bool)
            or entry["edgeCount"] < 1
        ):
            raise ModuleContractError(f"{label}.edgeCount must be a positive integer")
        if not isinstance(entry.get("sha256"), str) or not SHA256_RE.fullmatch(entry["sha256"]):
            raise ModuleContractError(f"{label}.sha256 must be a lowercase SHA-256")
        for field in ("reason", "retireWhen", "reviewOwner"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise ModuleContractError(f"{label}.{field} is required")
        owners = _string_list(
            entry.get("validationOwners"),
            f"{label}.validationOwners",
            allow_empty=False,
        )
        unknown = sorted(set(owners) - validation_ids)
        if unknown:
            raise ModuleContractError(f"{label} has unknown validation owner: {unknown}")
    if debt_keys != sorted(set(debt_keys)):
        raise ModuleContractError("dependencyDebt must have sorted unique module pairs")

    private_debt = manifest.get("privateImportDebt")
    if not isinstance(private_debt, dict) or set(private_debt) != {
        "edgeCount",
        "reason",
        "retireWhen",
        "reviewOwner",
        "sha256",
        "validationOwners",
    }:
        raise ModuleContractError("privateImportDebt has unsupported fields")
    if (
        not isinstance(private_debt.get("edgeCount"), int)
        or isinstance(private_debt["edgeCount"], bool)
        or private_debt["edgeCount"] < 1
    ):
        raise ModuleContractError("privateImportDebt.edgeCount must be a positive integer")
    if not isinstance(private_debt.get("sha256"), str) or not SHA256_RE.fullmatch(
        private_debt["sha256"]
    ):
        raise ModuleContractError("privateImportDebt.sha256 must be a lowercase SHA-256")
    for field in ("reason", "retireWhen", "reviewOwner"):
        if not isinstance(private_debt.get(field), str) or not private_debt[field]:
            raise ModuleContractError(f"privateImportDebt.{field} is required")
    private_debt_owners = _string_list(
        private_debt.get("validationOwners"),
        "privateImportDebt.validationOwners",
        allow_empty=False,
    )
    unknown_private_debt_owners = sorted(set(private_debt_owners) - validation_ids)
    if unknown_private_debt_owners:
        raise ModuleContractError(
            "privateImportDebt has unknown validation owner: "
            f"{unknown_private_debt_owners}"
        )


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    payload = _read_json(Path(path), "module contract")
    validate_manifest(payload, root=ROOT)
    return payload


def render_manifest(manifest: Mapping[str, Any], *, root: Path = ROOT) -> str:
    validate_manifest(manifest, root=root)
    return json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def _module_name(path: Path, root: Path) -> str:
    parts = path.relative_to(root).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def discover_python_modules(
    root: Path, manifest: Mapping[str, Any]
) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for relative_root in manifest["sourceSets"]["pythonRoots"]:
        source_root = Path(root) / relative_root
        paths = [source_root] if source_root.is_file() else sorted(source_root.rglob("*.py"))
        for path in paths:
            if path.suffix != ".py" or "__pycache__" in path.parts:
                continue
            module_name = _module_name(path, Path(root))
            if not module_name:
                raise ModuleContractError(f"cannot derive Python module for {path}")
            previous = modules.get(module_name)
            if previous is not None and previous != path:
                raise ModuleContractError(f"duplicate Python module {module_name}")
            modules[module_name] = path
    return dict(sorted(modules.items()))


def _validate_ownership_selectors(
    manifest: Mapping[str, Any],
    root: Path,
    python_modules: Mapping[str, Path],
) -> None:
    """Reject ownership claims that no longer resolve to repository sources."""

    for module in manifest["modules"]:
        module_id = module["id"]
        ownership = module["ownership"]
        for path in ownership["pathPrefixes"]:
            if not (root / path).exists():
                raise ModuleContractError(
                    f"{module_id} ownership path is missing: {path}"
                )
        for module_name in ownership["pythonModules"]:
            if module_name not in python_modules:
                raise ModuleContractError(
                    f"{module_id} ownership module is missing: {module_name}"
                )
        for package in ownership["pythonPackages"]:
            if not any(
                name == package or name.startswith(f"{package}.")
                for name in python_modules
            ):
                raise ModuleContractError(
                    f"{module_id} ownership package is missing: {package}"
                )
        for prefix in ownership["pythonModulePrefixes"]:
            if not any(name.startswith(prefix) for name in python_modules):
                raise ModuleContractError(
                    f"{module_id} ownership prefix is missing: {prefix}"
                )


def _source_package(module_name: str, path: Path) -> str:
    if path.name == "__init__.py":
        return module_name
    return module_name.rpartition(".")[0]


def _nearest_module(candidate: str, modules: Mapping[str, Path]) -> str | None:
    current = candidate
    while current:
        if current in modules:
            return current
        current = current.rpartition(".")[0]
    return None


def _import_targets(
    node: ast.Import | ast.ImportFrom,
    *,
    source_module: str,
    source_path: Path,
    modules: Mapping[str, Path],
) -> set[str]:
    if isinstance(node, ast.Import):
        return {
            target
            for alias in node.names
            if (target := _nearest_module(alias.name, modules)) is not None
        }

    base = node.module or ""
    if node.level:
        package = _source_package(source_module, source_path)
        if not package:
            return set()
        try:
            base = importlib.util.resolve_name(f"{'.' * node.level}{base}", package)
        except (ImportError, ValueError):
            return set()
    if not base:
        return set()

    targets: set[str] = set()
    for alias in node.names:
        candidate = f"{base}.{alias.name}" if alias.name != "*" else base
        target = _nearest_module(candidate, modules)
        if target is not None:
            targets.add(target)
    return targets


def collect_dependency_edges(
    root: Path, manifest: Mapping[str, Any]
) -> tuple[DependencyEdge, ...]:
    modules = discover_python_modules(Path(root), manifest)
    edges: set[DependencyEdge] = set()
    for source_module, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            raise ModuleContractError(f"cannot parse Python source {path}: {exc}") from exc
        source_owner = module_for_python_name(manifest, source_module)
        if source_owner is None:
            raise ModuleContractError(f"Python source has no module owner: {source_module}")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            try:
                targets = _import_targets(
                    node,
                    source_module=source_module,
                    source_path=path,
                    modules=modules,
                )
            except Exception as exc:
                raise ModuleContractError(
                    f"cannot analyze Python dependencies for {path}: {exc}"
                ) from exc
            for target in targets:
                target_owner = module_for_python_name(manifest, target)
                if target_owner is None or target_owner == source_owner:
                    continue
                edges.add(
                    DependencyEdge(
                        source=source_module,
                        target=target,
                        source_owner=source_owner,
                        target_owner=target_owner,
                    )
                )
    return tuple(sorted(edges))


def _debt_pairs(manifest: Mapping[str, Any]) -> set[tuple[str, str]]:
    return {(entry["from"], entry["to"]) for entry in manifest["dependencyDebt"]}


def _dependency_violations(
    edges: Iterable[DependencyEdge], manifest: Mapping[str, Any]
) -> tuple[DependencyEdge, ...]:
    modules = _module_map(manifest)
    debt_pairs = _debt_pairs(manifest)
    return tuple(
        edge
        for edge in edges
        if edge.target_owner not in modules[edge.source_owner]["allowedDependencies"]
        and (edge.source_owner, edge.target_owner) not in debt_pairs
    )


def find_dependency_violations(
    root: Path, manifest: Mapping[str, Any]
) -> tuple[DependencyEdge, ...]:
    return _dependency_violations(collect_dependency_edges(root, manifest), manifest)


def dependency_inventory_hash(edges: Iterable[DependencyEdge]) -> str:
    lines = [
        f"{edge.source}\t{edge.target}\t{edge.source_owner}\t{edge.target_owner}"
        for edge in sorted(set(edges))
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _is_public_python_target(
    manifest: Mapping[str, Any], owner: str, target: str
) -> bool:
    public = _module_map(manifest)[owner]["publicBoundary"]
    if target in public["pythonModules"]:
        return True
    return any(
        target == package or target.startswith(f"{package}.")
        for package in public["pythonPackages"]
    )


def _private_import_edges(
    edges: Iterable[DependencyEdge], manifest: Mapping[str, Any]
) -> tuple[DependencyEdge, ...]:
    debt_pairs = _debt_pairs(manifest)
    return tuple(
        edge
        for edge in edges
        if (edge.source_owner, edge.target_owner) not in debt_pairs
        and not _is_public_python_target(manifest, edge.target_owner, edge.target)
    )


def _format_edges(edges: Sequence[DependencyEdge], limit: int = 20) -> str:
    rendered = [f"{edge.source} -> {edge.target}" for edge in edges[:limit]]
    if len(edges) > limit:
        rendered.append(f"... {len(edges) - limit} more")
    return "\n".join(rendered)


def assert_repository_matches(
    root: Path, manifest: Mapping[str, Any]
) -> dict[str, int]:
    """Check references, ownership, approved dependencies, and frozen debt."""

    root = Path(root)
    validate_manifest(manifest, root=root)
    edges = collect_dependency_edges(root, manifest)
    violations = _dependency_violations(edges, manifest)
    if violations:
        raise DependencyViolationError(
            "unapproved module dependencies:\n" + _format_edges(violations)
        )

    for entry in manifest["dependencyDebt"]:
        pair_edges = tuple(
            edge
            for edge in edges
            if edge.source_owner == entry["from"] and edge.target_owner == entry["to"]
        )
        actual_hash = dependency_inventory_hash(pair_edges)
        if len(pair_edges) != entry["edgeCount"] or actual_hash != entry["sha256"]:
            raise DependencyDriftError(
                "reviewed dependency debt changed for "
                f"{entry['from']} -> {entry['to']}: "
                f"expected count/hash {entry['edgeCount']}/{entry['sha256']}, "
                f"found {len(pair_edges)}/{actual_hash}\n"
                + _format_edges(pair_edges)
            )

    private_edges = _private_import_edges(edges, manifest)
    private_debt = manifest["privateImportDebt"]
    private_hash = dependency_inventory_hash(private_edges)
    if (
        len(private_edges) != private_debt["edgeCount"]
        or private_hash != private_debt["sha256"]
    ):
        raise DependencyDriftError(
            "reviewed private import debt changed: "
            f"expected count/hash {private_debt['edgeCount']}/{private_debt['sha256']}, "
            f"found {len(private_edges)}/{private_hash}\n"
            + _format_edges(private_edges)
        )

    debt_manifest = boundary_debt.load_manifest(root / manifest["references"]["boundaryDebt"])
    for family in boundary_debt.FAMILY_SPECS:
        boundary_debt.assert_family_matches(root, debt_manifest, family)

    python_modules = discover_python_modules(root, manifest)
    approved_edges = tuple(
        edge
        for edge in edges
        if edge.target_owner in _module_map(manifest)[edge.source_owner]["allowedDependencies"]
    )
    selector_count = sum(
        len(module["ownership"][field])
        for module in manifest["modules"]
        for field in OWNERSHIP_FIELDS
    )
    residual_owners = set(manifest["sourceSets"]["residualPythonOwners"])
    residual_sources = sum(
        module_for_python_name(manifest, module_name) in residual_owners
        for module_name in python_modules
    )
    return {
        "approvedDependencyEdges": len(approved_edges),
        "dependencyEdges": len(edges),
        "dependencyGroups": len(manifest["dependencyDebt"]),
        "modules": len(manifest["modules"]),
        "multiplyOwnedPythonModules": 0,
        "newDisallowedEdges": len(violations),
        "ownedPythonModules": len(python_modules),
        "privateImportEdges": len(private_edges),
        "pythonModules": len(python_modules),
        "residualPythonModules": residual_sources,
        "reviewedDebtPairs": len(manifest["dependencyDebt"]),
        "selectorCount": selector_count,
        "unownedPythonModules": 0,
    }


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the repository contract")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if not args.check:
        parser.error("--check is required")
    root = args.root.resolve()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    try:
        manifest = _read_json(manifest_path, "module contract")
        evidence = assert_repository_matches(root, manifest)
        if manifest_path.read_text(encoding="utf-8") != render_manifest(
            manifest, root=root
        ):
            raise ModuleContractError("module contract JSON is not canonical")
        try:
            manifest_display = manifest_path.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ModuleContractError("module contract must be inside the repository root") from exc
    except (ModuleContractError, DependencyViolationError, DependencyDriftError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "manifest": manifest_display,
                "status": "ok",
                **evidence,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
