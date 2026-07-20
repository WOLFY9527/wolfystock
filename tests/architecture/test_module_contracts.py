"""Contract tests for canonical module ownership and dependency boundaries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.architecture import module_contracts


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MODULE_IDS = {
    "admin-observability",
    "ai-routing",
    "api-transport",
    "application-runtime",
    "auth-security",
    "backtest",
    "desktop-shell",
    "notification-integrations",
    "persistence",
    "portfolio",
    "provider-runtime",
    "research-services",
    "scanner",
    "shared-contracts",
    "web-client",
}


def _module(manifest: dict[str, object], module_id: str) -> dict[str, object]:
    return next(
        module
        for module in manifest["modules"]
        if module["id"] == module_id
    )


def test_module_contract_manifest_is_canonical_and_matches_the_repository() -> None:
    manifest = module_contracts.load_manifest()

    module_contracts.validate_manifest(manifest, root=ROOT)
    evidence = module_contracts.assert_repository_matches(ROOT, manifest)

    assert manifest["schemaVersion"] == "t645-module-contracts-v1"
    assert {module["id"] for module in manifest["modules"]} == EXPECTED_MODULE_IDS
    assert module_contracts.render_manifest(manifest) == (
        module_contracts.MANIFEST_PATH.read_text(encoding="utf-8")
    )
    assert evidence["pythonModules"] > 0
    assert evidence["dependencyEdges"] > 0
    assert evidence["privateImportEdges"] == manifest["privateImportDebt"]["edgeCount"]
    assert evidence["reviewedDebtPairs"] == len(manifest["dependencyDebt"])


def test_module_contract_reuses_existing_authority_inventories() -> None:
    manifest = module_contracts.load_manifest()
    classifications = module_contracts.backend_domain_classifications(manifest)

    assert manifest["references"] == {
        "boundaryDebt": "docs/architecture/debt-manifest.json",
        "documentation": "docs/documentation-manifest.json",
        "protectedSemantics": "docs/contracts/data-trust.md",
        "testTopology": "validation/domain_test_topology.json",
        "validationOwners": "validation/validation_owners.json",
    }
    assert module_contracts.module_for_python_name(
        manifest, "data_provider.yfinance_fetcher"
    ) == "provider-runtime"
    assert module_contracts.module_for_python_name(
        manifest, "api.v1.endpoints.backtest"
    ) == "backtest"
    assert module_contracts.module_for_python_name(
        manifest, "api.v1.schemas.backtest"
    ) == "shared-contracts"
    assert module_contracts.classify_backend_module(
        manifest, "src.services.portfolio_service"
    ) == "portfolio"
    assert "src.services.agent_model_service" in classifications["AI routing / cost"]
    assert "src.services.agent_" not in classifications["AI routing / cost"]


def test_module_contract_rejects_ambiguous_or_unknown_relationships() -> None:
    manifest = module_contracts.load_manifest()
    invalid_cases: list[tuple[str, dict[str, object]]] = []

    ambiguous = deepcopy(manifest)
    _module(ambiguous, "research-services")["ownership"]["pythonPackages"].append(
        "data_provider"
    )
    _module(ambiguous, "research-services")["ownership"]["pythonPackages"].sort()
    invalid_cases.append(("claimed by both", ambiguous))

    unknown_dependency = deepcopy(manifest)
    _module(unknown_dependency, "scanner")["allowedDependencies"].append(
        "unknown-module"
    )
    _module(unknown_dependency, "scanner")["allowedDependencies"].sort()
    invalid_cases.append(("unknown allowed dependency", unknown_dependency))

    unknown_documentation = deepcopy(manifest)
    _module(unknown_documentation, "scanner")["documentationAuthorities"].append(
        "unknown-authority"
    )
    _module(unknown_documentation, "scanner")["documentationAuthorities"].sort()
    invalid_cases.append(("unknown documentation authority", unknown_documentation))

    unknown_validation_owner = deepcopy(manifest)
    _module(unknown_validation_owner, "scanner")["validationOwners"].append(
        "unknown.owner"
    )
    _module(unknown_validation_owner, "scanner")["validationOwners"].sort()
    invalid_cases.append(("unknown validation owner", unknown_validation_owner))

    unknown_topology_domain = deepcopy(manifest)
    _module(unknown_topology_domain, "scanner")["topologyDomains"].append(
        "unknown_domain"
    )
    _module(unknown_topology_domain, "scanner")["topologyDomains"].sort()
    invalid_cases.append(("unknown topology domain", unknown_topology_domain))

    missing_path = deepcopy(manifest)
    _module(missing_path, "desktop-shell")["ownership"]["pathPrefixes"].append(
        "apps/removed-desktop"
    )
    _module(missing_path, "desktop-shell")["ownership"]["pathPrefixes"].sort()
    invalid_cases.append(("ownership path is missing", missing_path))

    missing_module = deepcopy(manifest)
    _module(missing_module, "scanner")["ownership"]["pythonModules"].append(
        "src.services.removed_scanner_module"
    )
    _module(missing_module, "scanner")["ownership"]["pythonModules"].sort()
    invalid_cases.append(("ownership module is missing", missing_module))

    missing_package = deepcopy(manifest)
    _module(missing_package, "research-services")["ownership"]["pythonPackages"].append(
        "src.removed_package"
    )
    _module(missing_package, "research-services")["ownership"]["pythonPackages"].sort()
    invalid_cases.append(("ownership package is missing", missing_package))

    missing_prefix = deepcopy(manifest)
    _module(missing_prefix, "scanner")["ownership"]["pythonModulePrefixes"].append(
        "src.services.removed_scanner_"
    )
    _module(missing_prefix, "scanner")["ownership"]["pythonModulePrefixes"].sort()
    invalid_cases.append(("ownership prefix is missing", missing_prefix))

    for expected_message, payload in invalid_cases:
        with pytest.raises(module_contracts.ModuleContractError, match=expected_message):
            module_contracts.validate_manifest(payload, root=ROOT)


def test_public_boundaries_must_be_owned_by_the_declaring_module() -> None:
    manifest = module_contracts.load_manifest()
    invalid = deepcopy(manifest)
    _module(invalid, "research-services")["publicBoundary"]["pythonPackages"].append(
        "src.repositories"
    )
    _module(invalid, "research-services")["publicBoundary"]["pythonPackages"].sort()

    with pytest.raises(module_contracts.ModuleContractError, match="public boundary"):
        module_contracts.validate_manifest(invalid, root=ROOT)


def test_dependency_guard_rejects_an_injected_unauthorized_edge(
    tmp_path: Path,
) -> None:
    manifest = module_contracts.load_manifest()
    source = tmp_path / "src" / "feature.py"
    target = tmp_path / "data_provider" / "base.py"
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    source.write_text("from data_provider.base import BaseDataFetcher\n", encoding="utf-8")
    target.write_text("class BaseDataFetcher:\n    pass\n", encoding="utf-8")

    restricted = deepcopy(manifest)
    research = _module(restricted, "research-services")
    research["allowedDependencies"].remove("provider-runtime")
    restricted["dependencyDebt"] = [
        entry
        for entry in restricted["dependencyDebt"]
        if not (
            entry["from"] == "research-services"
            and entry["to"] == "provider-runtime"
        )
    ]

    violations = module_contracts.find_dependency_violations(tmp_path, restricted)

    assert len(violations) == 1
    assert violations[0].source == "src.feature"
    assert violations[0].target == "data_provider.base"
    assert violations[0].source_owner == "research-services"
    assert violations[0].target_owner == "provider-runtime"


def test_reviewed_dependency_debt_is_frozen_to_exact_ast_edges() -> None:
    manifest = module_contracts.load_manifest()
    invalid = deepcopy(manifest)
    invalid["dependencyDebt"][0]["sha256"] = "0" * 64

    with pytest.raises(module_contracts.DependencyDriftError, match="reviewed dependency debt"):
        module_contracts.assert_repository_matches(ROOT, invalid)

    private_invalid = deepcopy(manifest)
    private_invalid["privateImportDebt"]["sha256"] = "0" * 64

    with pytest.raises(module_contracts.DependencyDriftError, match="private import debt"):
        module_contracts.assert_repository_matches(ROOT, private_invalid)


def test_module_contract_rejects_missing_unreadable_and_malformed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(module_contracts.ModuleContractError, match="cannot load module contract"):
        module_contracts.load_manifest(missing)

    unreadable = tmp_path / "unreadable.json"
    unreadable.write_text("{}", encoding="utf-8")
    original_read_text = Path.read_text

    def fail_contract_read(path: Path, *args: object, **kwargs: object) -> str:
        if path == unreadable:
            raise OSError("denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_contract_read)
    with pytest.raises(module_contracts.ModuleContractError, match="cannot load module contract"):
        module_contracts._read_json(unreadable, "module contract")

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(module_contracts.ModuleContractError, match="cannot load module contract"):
        module_contracts._read_json(malformed, "module contract")


def test_module_contract_rejects_duplicate_or_missing_ownership_selectors() -> None:
    manifest = module_contracts.load_manifest()

    duplicate = deepcopy(manifest)
    duplicate["modules"].append(deepcopy(duplicate["modules"][0]))
    with pytest.raises(module_contracts.ModuleContractError, match="sorted unique ids"):
        module_contracts.validate_manifest(duplicate, root=ROOT)

    missing_selector = deepcopy(manifest)
    _module(missing_selector, "scanner")["ownership"] = {
        "pathPrefixes": [],
        "pythonModulePrefixes": [],
        "pythonModules": [],
        "pythonPackages": [],
    }
    with pytest.raises(module_contracts.ModuleContractError, match="must declare at least one selector"):
        module_contracts.validate_manifest(missing_selector, root=ROOT)

    no_match = deepcopy(manifest)
    _module(no_match, "scanner")["ownership"]["pythonModulePrefixes"].append(
        "src.services.removed_scanner_"
    )
    _module(no_match, "scanner")["ownership"]["pythonModulePrefixes"].sort()
    with pytest.raises(module_contracts.ModuleContractError, match="ownership prefix is missing"):
        module_contracts.validate_manifest(no_match, root=ROOT)


def test_specific_selectors_win_over_residual_umbrella_selectors() -> None:
    manifest = {
        "modules": [
            {
                "id": "api-transport",
                "ownership": {
                    "pathPrefixes": [],
                    "pythonModulePrefixes": [],
                    "pythonModules": [],
                    "pythonPackages": ["api"],
                },
            },
            {
                "id": "research-services",
                "ownership": {
                    "pathPrefixes": [],
                    "pythonModulePrefixes": [],
                    "pythonModules": [],
                    "pythonPackages": ["src"],
                },
            },
            {
                "id": "scanner",
                "ownership": {
                    "pathPrefixes": [],
                    "pythonModulePrefixes": ["src.services.scanner_"],
                    "pythonModules": [],
                    "pythonPackages": [],
                },
            },
        ]
    }

    assert module_contracts.module_for_python_name(manifest, "src.services.scanner_ai") == "scanner"
    assert module_contracts.module_for_python_name(manifest, "src.services.history_service") == "research-services"
    assert module_contracts.module_for_python_name(manifest, "api.v1.endpoints.market") == "api-transport"


def test_selector_resolution_rejects_equal_rank_ambiguous_owner_results() -> None:
    manifest = {
        "modules": [
            {
                "id": "alpha",
                "ownership": {
                    "pathPrefixes": [],
                    "pythonModulePrefixes": ["src.services.item_"],
                    "pythonModules": [],
                    "pythonPackages": [],
                },
            },
            {
                "id": "beta",
                "ownership": {
                    "pathPrefixes": [],
                    "pythonModulePrefixes": ["src.services.item_"],
                    "pythonModules": [],
                    "pythonPackages": [],
                },
            },
        ]
    }

    with pytest.raises(module_contracts.ModuleContractError, match="ambiguous owners"):
        module_contracts.module_for_python_name(manifest, "src.services.item_owner")


def test_module_contract_rejects_unowned_and_multiply_owned_sources() -> None:
    manifest = module_contracts.load_manifest()

    unowned = deepcopy(manifest)
    _module(unowned, "research-services")["ownership"]["pythonPackages"].remove("src")
    _module(unowned, "research-services")["ownership"]["pythonModulePrefixes"].append(
        "src.services.history_"
    )
    _module(unowned, "research-services")["ownership"]["pythonModulePrefixes"].sort()
    with pytest.raises(module_contracts.ModuleContractError, match="Python source has no module owner"):
        module_contracts.validate_manifest(unowned, root=ROOT)

    multiply_owned = deepcopy(manifest)
    _module(multiply_owned, "research-services")["ownership"]["pythonPackages"].append("data_provider")
    _module(multiply_owned, "research-services")["ownership"]["pythonPackages"].sort()
    with pytest.raises(module_contracts.ModuleContractError, match="claimed by both"):
        module_contracts.validate_manifest(multiply_owned, root=ROOT)


def test_dependency_contract_distinguishes_existing_imports_from_approval() -> None:
    manifest = module_contracts.load_manifest()
    edges = module_contracts.collect_dependency_edges(ROOT, manifest)
    debt_pairs = {(entry["from"], entry["to"]) for entry in manifest["dependencyDebt"]}
    approved = next(
        edge
        for edge in edges
        if edge.target_owner in _module(manifest, edge.source_owner)["allowedDependencies"]
        and (edge.source_owner, edge.target_owner) not in debt_pairs
    )
    restricted = deepcopy(manifest)
    _module(restricted, approved.source_owner)["allowedDependencies"].remove(approved.target_owner)

    assert approved in module_contracts.find_dependency_violations(ROOT, restricted)


def test_dependency_analysis_fails_closed_on_source_read_parse_and_analysis_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = module_contracts.load_manifest()
    sources = module_contracts.discover_python_modules(ROOT, manifest)
    source_path = next(iter(sources.values()))
    original_read_text = Path.read_text

    def fail_source_read(path: Path, *args: object, **kwargs: object) -> str:
        if path == source_path:
            raise OSError("read denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_source_read)
    with pytest.raises(module_contracts.ModuleContractError, match="cannot parse Python source"):
        module_contracts.collect_dependency_edges(ROOT, manifest)

    monkeypatch.undo()
    monkeypatch.setattr(module_contracts.ast, "parse", lambda *args, **kwargs: (_ for _ in ()).throw(SyntaxError("bad source")))
    with pytest.raises(module_contracts.ModuleContractError, match="cannot parse Python source"):
        module_contracts.collect_dependency_edges(ROOT, manifest)

    monkeypatch.undo()
    monkeypatch.setattr(module_contracts, "_import_targets", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("analysis failed")))
    with pytest.raises(module_contracts.ModuleContractError, match="cannot analyze Python dependencies"):
        module_contracts.collect_dependency_edges(ROOT, manifest)


def test_frozen_debt_rejects_missing_duplicate_malformed_and_owner_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = module_contracts.load_manifest()

    missing = deepcopy(manifest)
    missing["dependencyDebt"][0]["edgeCount"] += 1
    with pytest.raises(module_contracts.DependencyDriftError, match="reviewed dependency debt"):
        module_contracts.assert_repository_matches(ROOT, missing)

    duplicate = deepcopy(manifest)
    duplicate["dependencyDebt"].append(deepcopy(duplicate["dependencyDebt"][0]))
    with pytest.raises(module_contracts.ModuleContractError, match="sorted unique module pairs"):
        module_contracts.validate_manifest(duplicate, root=ROOT)

    malformed = deepcopy(manifest)
    malformed["dependencyDebt"][0]["edgeCount"] = True
    with pytest.raises(module_contracts.ModuleContractError, match="positive integer"):
        module_contracts.validate_manifest(malformed, root=ROOT)

    edges = module_contracts.collect_dependency_edges(ROOT, manifest)
    drifted_source = replace(edges[0], source_owner="research-services")
    drifted_target = replace(edges[0], target_owner="api-transport")
    assert module_contracts.dependency_inventory_hash([edges[0]]) != module_contracts.dependency_inventory_hash([drifted_source])
    assert module_contracts.dependency_inventory_hash([edges[0]]) != module_contracts.dependency_inventory_hash([drifted_target])

    monkeypatch.setattr(module_contracts, "collect_dependency_edges", lambda *args, **kwargs: (drifted_source,))
    monkeypatch.setattr(module_contracts, "_dependency_violations", lambda *args, **kwargs: ())
    with pytest.raises(module_contracts.DependencyDriftError, match="reviewed dependency debt"):
        module_contracts.assert_repository_matches(ROOT, manifest)

    monkeypatch.setattr(module_contracts, "collect_dependency_edges", lambda *args, **kwargs: (drifted_target,))
    with pytest.raises(module_contracts.DependencyDriftError, match="reviewed dependency debt"):
        module_contracts.assert_repository_matches(ROOT, manifest)


def test_private_import_debt_is_measured_and_residual_ownership_is_reported() -> None:
    manifest = module_contracts.load_manifest()
    evidence = module_contracts.assert_repository_matches(ROOT, manifest)

    assert evidence["privateImportEdges"] == manifest["privateImportDebt"]["edgeCount"]
    assert evidence["residualPythonModules"] > 0
    assert evidence["ownedPythonModules"] == evidence["pythonModules"]
