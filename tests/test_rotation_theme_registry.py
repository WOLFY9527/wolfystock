# -*- coding: utf-8 -*-
"""Static contracts for Rotation Theme Registry v2."""

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
            raise AssertionError(f"theme registry imported provider module {fullname}")
        if fullname.startswith("src.providers") or fullname.startswith("src.services.market_provider"):
            self.blocked.append(fullname)
            raise AssertionError(f"theme registry imported provider module {fullname}")
        return None


def test_rotation_theme_registry_import_is_static_metadata_only() -> None:
    sys.modules.pop("src.services.rotation_theme_registry", None)
    blocker = _ProviderImportBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        module = importlib.import_module("src.services.rotation_theme_registry")
    finally:
        sys.meta_path.remove(blocker)

    assert module.ROTATION_THEME_REGISTRY_VERSION == "rotation_theme_registry_v2"
    assert module.list_rotation_theme_definitions("US")
    assert blocker.blocked == []


def test_rotation_theme_registry_v2_has_required_theme_metadata() -> None:
    from src.services.rotation_theme_registry import list_rotation_theme_definitions

    themes = list_rotation_theme_definitions("US")
    ids = [theme.theme_id for theme in themes]

    assert len(ids) == len(set(ids))
    for required in (
        "ai_infrastructure",
        "ai_neocloud",
        "semiconductors",
        "semiconductor_equipment",
        "cloud_software",
        "cybersecurity",
        "crypto_exchanges_brokers",
        "bitcoin_treasury",
        "ethereum_treasury",
        "crypto_miners",
        "stablecoin_tokenization",
    ):
        assert required in ids

    for theme in themes:
        payload = theme.to_dict()
        for field in (
            "theme_id",
            "display_name",
            "definition",
            "category",
            "primary_symbols",
            "secondary_symbols",
            "related_symbols",
            "proxy_etfs",
            "proxy_indices",
            "benchmark_symbols",
            "inclusion_notes",
            "data_quality_notes",
        ):
            assert field in payload
        assert theme.theme_id
        assert theme.display_name
        assert theme.definition
        assert theme.category
        assert theme.primary_symbols
        assert theme.data_quality_notes


def test_orcl_is_included_with_explicit_ai_cloud_inclusion_note() -> None:
    from src.services.rotation_theme_registry import get_rotation_theme_definition

    neocloud = get_rotation_theme_definition("ai_neocloud")
    cloud = get_rotation_theme_definition("cloud_software")
    assert neocloud is not None
    assert cloud is not None

    assert "ORCL" in neocloud.all_constituent_symbols()
    assert "ORCL" in cloud.all_constituent_symbols()
    assert "ORCL" in neocloud.inclusion_notes
    assert "AI cloud" in neocloud.inclusion_notes["ORCL"]


def test_bmnr_is_included_with_explicit_ethereum_treasury_note() -> None:
    from src.services.rotation_theme_registry import get_rotation_theme_definition

    theme = get_rotation_theme_definition("ethereum_treasury")
    assert theme is not None

    assert "BMNR" in theme.all_constituent_symbols()
    assert "BMNR" in theme.inclusion_notes
    assert "Ethereum" in theme.inclusion_notes["BMNR"]
    assert "ETH beta" in theme.inclusion_notes["BMNR"]


def test_sox_is_index_concept_and_smh_soxx_are_semiconductor_etf_proxies() -> None:
    from src.services.rotation_theme_registry import get_rotation_theme_definition, list_rotation_theme_definitions

    semis = get_rotation_theme_definition("semiconductors")
    equipment = get_rotation_theme_definition("semiconductor_equipment")
    assert semis is not None
    assert equipment is not None

    assert {"SMH", "SOXX"}.issubset(set(semis.proxy_etfs))
    assert {"SMH", "SOXX"}.issubset(set(equipment.proxy_etfs))
    assert "SOX" in semis.proxy_indices
    assert "SOX" in equipment.proxy_indices
    assert all("SOX" not in theme.proxy_etfs for theme in list_rotation_theme_definitions("US"))


def test_igv_is_cloud_software_proxy_etf() -> None:
    from src.services.rotation_theme_registry import get_rotation_theme_definition

    theme = get_rotation_theme_definition("cloud_software")
    assert theme is not None

    assert "IGV" in theme.proxy_etfs
    assert "SOX" not in theme.proxy_etfs
