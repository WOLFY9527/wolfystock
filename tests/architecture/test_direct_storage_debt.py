"""Architecture guard for direct consumers of the storage god module."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.architecture import boundary_debt


ROOT = Path(__file__).resolve().parents[2]
FAMILY = "directStorageConsumers"


def test_direct_storage_consumers_match_the_debt_manifest() -> None:
    manifest = boundary_debt.load_manifest()

    boundary_debt.assert_family_matches(ROOT, manifest, FAMILY)

    assert len(boundary_debt.collect_family(ROOT, FAMILY)) == 51


def test_direct_storage_guard_rejects_an_injected_consumer(tmp_path: Path) -> None:
    manifest = boundary_debt.load_manifest()
    manifest["families"][FAMILY]["entries"] = []
    repository = tmp_path / "src" / "repositories" / "allowed_repo.py"
    repository.parent.mkdir(parents=True)
    repository.write_text("from src.storage import DatabaseManager\n", encoding="utf-8")
    consumer = tmp_path / "src" / "services" / "forbidden_storage.py"
    consumer.parent.mkdir(parents=True)
    consumer.write_text("from src.storage import DatabaseManager\n", encoding="utf-8")
    parent_import = tmp_path / "src" / "services" / "parent_import_storage.py"
    parent_import.write_text("from src import storage\n", encoding="utf-8")

    with pytest.raises(boundary_debt.DebtMismatchError, match="new debt entries") as error:
        boundary_debt.assert_family_matches(tmp_path, manifest, FAMILY)

    assert "src/services/forbidden_storage.py" in str(error.value)
    assert "src/services/parent_import_storage.py" in str(error.value)
    assert "src/repositories/allowed_repo.py" not in str(error.value)
