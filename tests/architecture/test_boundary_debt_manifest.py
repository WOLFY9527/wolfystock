"""Contract tests for the versioned architecture boundary-debt manifest."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from scripts.architecture import boundary_debt
from scripts.architecture import boundary_debt_collectors


ROOT = Path(__file__).resolve().parents[2]


def _assert_source_graph_reuses_an_immutable_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "src" / "services" / "graph.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from api.v1.schemas.graph import GraphResponse\n",
        encoding="utf-8",
    )
    build_calls = 0
    original_build = boundary_debt_collectors._build_source_graph

    def counted_build(*args: object, **kwargs: object):
        nonlocal build_calls
        build_calls += 1
        return original_build(*args, **kwargs)

    monkeypatch.setattr(boundary_debt_collectors, "_build_source_graph", counted_build)

    first = boundary_debt_collectors.collect_source_graph(tmp_path)
    second = boundary_debt_collectors.collect_source_graph(tmp_path)

    assert first is second
    assert first.content_digest == second.content_digest
    assert build_calls == 1
    with pytest.raises(FrozenInstanceError):
        first.files = ()


def _assert_source_graph_cache_invalidates_after_source_mutation(tmp_path: Path) -> None:
    source = tmp_path / "src" / "services" / "graph.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from api.v1.schemas.before import BeforeResponse\n",
        encoding="utf-8",
    )

    before = boundary_debt_collectors.collect_source_graph(tmp_path)
    source.write_text(
        "from api.v1.schemas.after import AfterResponse\n",
        encoding="utf-8",
    )
    after = boundary_debt_collectors.collect_source_graph(tmp_path)

    assert before is not after
    assert before.input_digest != after.input_digest
    assert before.family_entries("serviceToApiSchemaEdges") != after.family_entries(
        "serviceToApiSchemaEdges"
    )


def _assert_source_graph_digest_is_deterministic(tmp_path: Path) -> None:
    contents = "from api.v1.schemas.graph import GraphResponse\n"
    roots = [tmp_path / "first", tmp_path / "second"]
    for root in roots:
        source = root / "src" / "services" / "graph.py"
        source.parent.mkdir(parents=True)
        source.write_text(contents, encoding="utf-8")

    first = boundary_debt_collectors.collect_source_graph(roots[0])
    second = boundary_debt_collectors.collect_source_graph(roots[1])

    assert first.content_digest == second.content_digest
    assert first.files == second.files


def _assert_source_graph_read_failure_is_not_cached_as_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "src" / "services" / "read_error.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from api.v1.schemas.read_error import ReadErrorResponse\n",
        encoding="utf-8",
    )
    original_read_bytes = Path.read_bytes

    def failed_read_bytes(path: Path) -> bytes:
        if path == source:
            raise OSError("injected source read failure")
        return original_read_bytes(path)

    with monkeypatch.context() as context:
        context.setattr(Path, "read_bytes", failed_read_bytes)
        with pytest.raises(OSError, match="injected source read failure"):
            boundary_debt_collectors.collect_source_graph(tmp_path)

    graph = boundary_debt_collectors.collect_source_graph(tmp_path)
    assert graph.family_entries("serviceToApiSchemaEdges") == [
        {
            "source": "src/services/read_error.py",
            "target": "api.v1.schemas.read_error",
        }
    ]


def _assert_source_graph_parse_failure_is_not_cached_as_empty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "services" / "broken.py"
    source.parent.mkdir(parents=True)
    source.write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(SyntaxError):
        boundary_debt_collectors.collect_source_graph(tmp_path)

    source.write_text(
        "from api.v1.schemas.fixed import FixedResponse\n",
        encoding="utf-8",
    )
    graph = boundary_debt_collectors.collect_source_graph(tmp_path)

    assert graph.files
    assert graph.family_entries("serviceToApiSchemaEdges") == [
        {"source": "src/services/broken.py", "target": "api.v1.schemas.fixed"}
    ]


def test_boundary_debt_manifest_is_canonical_and_reproduces_current_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
    _assert_source_graph_reuses_an_immutable_result(monkeypatch, tmp_path / "reuse")
    _assert_source_graph_cache_invalidates_after_source_mutation(tmp_path / "mutation")
    _assert_source_graph_digest_is_deterministic(tmp_path / "digest")
    _assert_source_graph_read_failure_is_not_cached_as_empty(
        monkeypatch, tmp_path / "read"
    )
    _assert_source_graph_parse_failure_is_not_cached_as_empty(tmp_path / "parse")


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
    family["entries"] = boundary_debt_collectors.collect_source_graph(
        tmp_path
    ).family_entries(
        "serviceToApiSchemaEdges"
    )

    boundary_debt.assert_family_matches(tmp_path, manifest, "serviceToApiSchemaEdges")

    source.unlink()
    with pytest.raises(boundary_debt.DebtMismatchError, match="stale manifest entries"):
        boundary_debt.assert_family_matches(tmp_path, manifest, "serviceToApiSchemaEdges")

    family["entries"] = []
    boundary_debt.assert_family_matches(tmp_path, manifest, "serviceToApiSchemaEdges")
