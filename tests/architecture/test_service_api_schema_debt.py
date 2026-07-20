"""Architecture guard for service-to-API-schema reverse dependencies."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.architecture import boundary_debt


ROOT = Path(__file__).resolve().parents[2]
FAMILY = "serviceToApiSchemaEdges"


def test_service_to_api_schema_edges_match_the_debt_manifest() -> None:
    manifest = boundary_debt.load_manifest()

    boundary_debt.assert_family_matches(ROOT, manifest, FAMILY)

    assert len(boundary_debt.collect_source_graph(ROOT).family_entries(FAMILY)) == 46


def test_service_to_api_schema_guard_rejects_an_injected_reverse_edge(
    tmp_path: Path,
) -> None:
    manifest = boundary_debt.load_manifest()
    manifest["families"][FAMILY]["entries"] = []
    source = tmp_path / "src" / "services" / "forbidden.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from api.v1 import schemas\n"
        "from api.v1.schemas.forbidden import ForbiddenResponse\n",
        encoding="utf-8",
    )

    with pytest.raises(boundary_debt.DebtMismatchError, match="new debt entries") as error:
        boundary_debt.assert_family_matches(tmp_path, manifest, FAMILY)

    assert "src/services/forbidden.py -> api.v1.schemas.forbidden" in str(error.value)
    assert "- src/services/forbidden.py -> api.v1.schemas" in str(error.value).splitlines()
