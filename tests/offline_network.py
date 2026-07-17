"""Fail-closed outbound-network policy for pytest only."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.offline_socket_guard import (
    OutboundNetworkBlocked,
    SocketGuard as _SocketGuard,
    is_loopback_host as _is_loopback_host,
)


__all__ = ("OutboundNetworkBlocked", "_is_loopback_host")


REQUIRED_NETWORK_MARKER_FIELDS = ("owner", "reason", "audit")
ROOT = Path(__file__).resolve().parents[1]
CHILD_BOOTSTRAP = ROOT / "tests" / "offline_bootstrap"
OFFLINE_ENVIRONMENT = {
    "NO_PROXY": "*",
    "no_proxy": "*",
    "LITELLM_LOCAL_MODEL_COST_MAP": "true",
    "WOLFYSTOCK_TEST_OFFLINE": "1",
}
CHILD_ENVIRONMENT_ALLOWLIST = {
    "APP_ENV",
    "CI",
    "COMSPEC",
    "HOME",
    "LANG",
    "LC_ALL",
    "LITELLM_LOCAL_MODEL_COST_MAP",
    "NO_PROXY",
    "PATH",
    "PATHEXT",
    "PYTHONPATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "WOLFYSTOCK_TEST_OFFLINE",
    "no_proxy",
}
CHILD_ENVIRONMENT_PREFIX_ALLOWLIST = (
    "PYTEST_",
    "WOLFYSTOCK_TEST_",
    "WORKTREE_BOOTSTRAP_",
)
_ORIGINAL_POPEN_INIT = subprocess.Popen.__init__
_LOOPBACK_DESTRUCTIVE_DSN = re.compile(
    r"^postgresql(?:\+[a-z0-9_]+)?://[^\s@]+@(?:localhost|127\.0\.0\.1):[0-9]+/"
    r"wolfystock_destructive_test_[a-z0-9_]+$"
)


def project_child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Project a credential-free environment for native and Python children."""

    environment = os.environ if source is None else source
    projected = {
        key: value
        for key, value in environment.items()
        if key in CHILD_ENVIRONMENT_ALLOWLIST or key.startswith(CHILD_ENVIRONMENT_PREFIX_ALLOWLIST)
    }
    destructive_dsn = environment.get("POSTGRES_PHASE_A_REAL_DSN", "")
    if _LOOPBACK_DESTRUCTIVE_DSN.fullmatch(destructive_dsn):
        projected["POSTGRES_PHASE_A_REAL_DSN"] = destructive_dsn
    return projected


def _install_child_environment_projection(config: pytest.Config) -> None:
    if getattr(config, "_wolfystock_child_environment_projection", False):
        return

    def sanitized_popen_init(process: subprocess.Popen[Any], *args: Any, **kwargs: Any) -> None:
        positional = list(args)
        if len(positional) > 10:
            positional[10] = project_child_environment(positional[10])
        else:
            kwargs["env"] = project_child_environment(kwargs.get("env"))
        _ORIGINAL_POPEN_INIT(process, *positional, **kwargs)

    subprocess.Popen.__init__ = sanitized_popen_init  # type: ignore[method-assign]
    config._wolfystock_child_environment_projection = True  # type: ignore[attr-defined]


def _restore_child_environment_projection(config: pytest.Config) -> None:
    if not getattr(config, "_wolfystock_child_environment_projection", False):
        return
    subprocess.Popen.__init__ = _ORIGINAL_POPEN_INIT  # type: ignore[method-assign]
    config._wolfystock_child_environment_projection = False  # type: ignore[attr-defined]


def _explicit_network_opt_in(config: pytest.Config) -> bool:
    return bool(
        config.getoption("--allow-test-network")
        and config.getoption("--network-audit")
        and config.getoption("-m").strip() == "network"
    )


def _activate_offline_environment(config: pytest.Config) -> None:
    keys = (*OFFLINE_ENVIRONMENT, "PYTHONPATH")
    config._wolfystock_offline_environment = {key: os.environ.get(key) for key in keys}  # type: ignore[attr-defined]
    os.environ.update(OFFLINE_ENVIRONMENT)
    existing = os.environ.get("PYTHONPATH")
    entries = [str(CHILD_BOOTSTRAP), str(ROOT)]
    if existing:
        entries.append(existing)
    os.environ["PYTHONPATH"] = os.pathsep.join(entries)


def _restore_offline_environment(config: pytest.Config) -> None:
    previous = getattr(config, "_wolfystock_offline_environment", None)
    if previous is None:
        return
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _marker_errors(items: Iterable[pytest.Item], *, audit: str | None = None) -> list[str]:
    errors: list[str] = []
    for item in items:
        marker = item.get_closest_marker("network")
        if marker is None:
            continue
        if marker.args:
            errors.append(f"{item.nodeid}: network marker must use named audit fields")
        missing = [field for field in REQUIRED_NETWORK_MARKER_FIELDS if not marker.kwargs.get(field)]
        if missing:
            errors.append(f"{item.nodeid}: network marker missing {', '.join(missing)}")
        if audit and marker.kwargs.get("audit") != audit:
            errors.append(
                f"{item.nodeid}: marker audit {marker.kwargs.get('audit')!r} does not match --network-audit {audit!r}"
            )
    return errors


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("outbound-network", "test-only outbound-network isolation")
    group.addoption(
        "--allow-test-network",
        action="store_true",
        default=False,
        help="Enable only audited network-marked tests; requires '-m network' and --network-audit.",
    )
    group.addoption(
        "--network-audit",
        action="store",
        default=None,
        metavar="AUDIT_ID",
        help="Audit identifier that must match every selected network marker.",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    guard = _SocketGuard()
    session.config._wolfystock_socket_guard = guard  # type: ignore[attr-defined]
    _activate_offline_environment(session.config)
    _install_child_environment_projection(session.config)
    guard.install()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    allow = config.getoption("--allow-test-network")
    audit = config.getoption("--network-audit")
    markexpr = config.getoption("-m").strip()
    usage_errors: list[str] = []
    if allow and (markexpr != "network" or not audit):
        usage_errors.append("--allow-test-network requires exactly '-m network' and a non-empty --network-audit")
    if audit and not allow:
        usage_errors.append("--network-audit requires --allow-test-network")
    usage_errors.extend(_marker_errors(items, audit=audit if allow else None))
    if usage_errors:
        raise pytest.UsageError("invalid outbound-network test policy:\n- " + "\n- ".join(usage_errors))


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("network") is not None and not _explicit_network_opt_in(item.config):
        pytest.skip("audited network tests never run in the standard offline/LAND tier")


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item: pytest.Item) -> Iterator[None]:
    marker = item.get_closest_marker("network")
    if marker is None or not _explicit_network_opt_in(item.config):
        yield
        return

    guard = item.config._wolfystock_socket_guard  # type: ignore[attr-defined]
    guard.restore()
    _restore_offline_environment(item.config)
    try:
        yield
    finally:
        _activate_offline_environment(item.config)
        guard.install()


def pytest_sessionfinish(session: pytest.Session) -> None:
    guard = getattr(session.config, "_wolfystock_socket_guard", None)
    if guard is not None:
        guard.restore()
    _restore_offline_environment(session.config)
    _restore_child_environment_projection(session.config)
