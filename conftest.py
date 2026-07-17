"""Repository-wide pytest policy plugins."""

pytest_plugins = (
    "tests.domain_topology_plugin",
    "tests.destructive_postgres",
    "tests.offline_network",
)
