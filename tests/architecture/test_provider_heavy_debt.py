"""Architecture guard for provider-heavy service construction points."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.architecture import boundary_debt


ROOT = Path(__file__).resolve().parents[2]
FAMILY = "providerHeavyConstructionPoints"


def test_provider_heavy_construction_points_match_the_debt_manifest() -> None:
    manifest = boundary_debt.load_manifest()

    boundary_debt.assert_family_matches(ROOT, manifest, FAMILY)

    assert len(boundary_debt.collect_family(ROOT, FAMILY)) == 21


def test_provider_heavy_guard_rejects_an_injected_construction_point(
    tmp_path: Path,
) -> None:
    manifest = boundary_debt.load_manifest()
    manifest["families"][FAMILY]["entries"] = []
    provider_owned = tmp_path / "src" / "services" / "market_cache_redis_backend.py"
    provider_owned.parent.mkdir(parents=True)
    provider_owned.write_text(
        "from src.services.market_cache import MarketCache\n",
        encoding="utf-8",
    )
    consumer = tmp_path / "src" / "services" / "forbidden_provider.py"
    consumer.write_text(
        "from data_provider.base import DataFetcherManager\n"
        "\n"
        "def build_provider():\n"
        "    return DataFetcherManager()\n",
        encoding="utf-8",
    )
    parent_import = tmp_path / "src" / "services" / "forbidden_market_cache.py"
    parent_import.write_text(
        "from src.services import market_cache\n"
        "\n"
        "def read_cache():\n"
        "    return market_cache.get('fixture')\n",
        encoding="utf-8",
    )

    with pytest.raises(boundary_debt.DebtMismatchError, match="new debt entries") as error:
        boundary_debt.assert_family_matches(tmp_path, manifest, FAMILY)

    assert "src/services/forbidden_provider.py" in str(error.value)
    assert "src/services/forbidden_market_cache.py" in str(error.value)
    assert "market_cache_redis_backend.py" not in str(error.value)


def test_provider_heavy_guard_rejects_a_new_call_in_existing_debt(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "services" / "legacy_provider.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from data_provider.base import DataFetcherManager\n",
        encoding="utf-8",
    )
    manifest = boundary_debt.load_manifest()
    family = manifest["families"][FAMILY]
    family["entries"] = boundary_debt.collect_family(tmp_path, FAMILY)
    boundary_debt.assert_family_matches(tmp_path, manifest, FAMILY)

    source.write_text(
        "from data_provider.base import DataFetcherManager\n"
        "\n"
        "def build_provider():\n"
        "    return DataFetcherManager()\n",
        encoding="utf-8",
    )

    with pytest.raises(boundary_debt.DebtMismatchError, match="new debt entries") as error:
        boundary_debt.assert_family_matches(tmp_path, manifest, FAMILY)

    assert "build_provider -> DataFetcherManager (1)" in str(error.value)
