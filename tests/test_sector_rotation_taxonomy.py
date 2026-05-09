# -*- coding: utf-8 -*-
"""Static taxonomy contracts for the rotation radar."""

from __future__ import annotations

import importlib
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec


class _ProviderImportBlocker(MetaPathFinder):
    def __init__(self) -> None:
        self.blocked: list[str] = []

    def find_spec(self, fullname: str, path: object | None, target: object | None = None) -> ModuleSpec | None:
        if fullname == "data_provider" or fullname.startswith("data_provider."):
            self.blocked.append(fullname)
            raise AssertionError(f"taxonomy module imported provider module {fullname}")
        if fullname.startswith("src.providers") or fullname.startswith("src.services.market_provider"):
            self.blocked.append(fullname)
            raise AssertionError(f"taxonomy module imported provider module {fullname}")
        return None


def test_taxonomy_import_does_not_touch_provider_modules() -> None:
    sys.modules.pop("src.services.sector_rotation_taxonomy", None)
    blocker = _ProviderImportBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        module = importlib.import_module("src.services.sector_rotation_taxonomy")
    finally:
        sys.meta_path.remove(blocker)

    assert module.get_rotation_taxonomy_by_market("US")
    assert blocker.blocked == []


def test_taxonomy_registry_has_required_market_counts_and_unique_ids() -> None:
    from src.services.sector_rotation_taxonomy import get_rotation_taxonomy_by_market, list_rotation_taxonomy_entries

    entries = list_rotation_taxonomy_entries()
    ids = [entry.id for entry in entries]

    assert len(ids) == len(set(ids))
    assert len(get_rotation_taxonomy_by_market("US")) >= 18
    assert len(get_rotation_taxonomy_by_market("CN")) >= 25
    assert len(get_rotation_taxonomy_by_market("HK")) >= 8
    assert len(get_rotation_taxonomy_by_market("CRYPTO")) >= 8


def test_non_us_taxonomy_entries_are_honest_static_observation_entries() -> None:
    from src.services.sector_rotation_taxonomy import get_rotation_taxonomy_by_market

    for market in ("CN", "HK", "CRYPTO"):
        entries = get_rotation_taxonomy_by_market(market)
        assert entries
        assert all(entry.userVisible for entry in entries)
        assert all(entry.enabledByDefault for entry in entries)
        assert all(entry.dataCoverage in {"taxonomy_only", "local_only", "proxy_backed"} for entry in entries)
        assert any(entry.dataCoverage == "taxonomy_only" for entry in entries)
