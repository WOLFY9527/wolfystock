# -*- coding: utf-8 -*-
"""Coverage consistency guard for the homepage cockpit section layout contract."""

from __future__ import annotations

from src.services.homepage_section_layout_service import HomepageSectionLayoutService
from tests.test_homepage_cockpit_uat_readiness import EXPECTED_MODULES


EXPECTED_CANONICAL_MODULE_KEYS = {module_key for _, module_key in EXPECTED_MODULES}


def test_homepage_cockpit_section_layout_covers_canonical_modules_once() -> None:
    payload = HomepageSectionLayoutService().build_layout(as_of="2026-06-15T09:30:00Z")
    flattened_module_keys = [
        module["key"]
        for section in payload["sections"]
        for module in section["modules"]
    ]

    assert set(flattened_module_keys) == EXPECTED_CANONICAL_MODULE_KEYS
    assert flattened_module_keys.count("driver_chain") == 1
