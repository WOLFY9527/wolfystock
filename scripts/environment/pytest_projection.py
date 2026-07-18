from __future__ import annotations

from .runtime import TEST_CONFIG_OVERRIDE_KEYS


def pytest_configure() -> None:
    from tests import offline_network

    offline_network.CHILD_ENVIRONMENT_ALLOWLIST.update(TEST_CONFIG_OVERRIDE_KEYS)
