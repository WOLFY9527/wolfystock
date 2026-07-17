from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from tests.offline_network import OutboundNetworkBlocked, _is_loopback_host


ROOT = Path(__file__).resolve().parents[1]


def test_standard_pytest_process_denies_external_dns_and_socket_connection() -> None:
    with pytest.raises(OutboundNetworkBlocked, match="outbound network is disabled"):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(OutboundNetworkBlocked, match="outbound network is disabled"):
        socket.create_connection(("203.0.113.1", 443), timeout=0.01)


def test_standard_pytest_process_denies_http_client_proxy_tunneling() -> None:
    with pytest.raises(OutboundNetworkBlocked, match="outbound network is disabled"):
        httpx.get("https://example.com", timeout=0.01)


def test_python_subprocess_inherits_offline_socket_guard() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket; socket.create_connection(('203.0.113.1', 443), timeout=0.01)",
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode != 0
    assert "OutboundNetworkBlocked" in result.stderr


def test_child_environment_projection_removes_credentials_and_production_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.offline_network import project_child_environment

    monkeypatch.setenv("ALPACA_API_KEY", "provider-secret")
    monkeypatch.setenv("POSTGRES_PHASE_A_REAL_DSN", "postgresql://user:secret@db.example/production")
    monkeypatch.setenv("UNRELATED_PRIVATE_VALUE", "private")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WOLFYSTOCK_TEST_RUN_ID", "fixture-run")

    projected = project_child_environment()

    assert "ALPACA_API_KEY" not in projected
    assert "POSTGRES_PHASE_A_REAL_DSN" not in projected
    assert "UNRELATED_PRIVATE_VALUE" not in projected
    assert projected["APP_ENV"] == "production"
    assert projected["WOLFYSTOCK_TEST_RUN_ID"] == "fixture-run"
    assert projected["WOLFYSTOCK_TEST_OFFLINE"] == "1"

    child = subprocess.run(
        [sys.executable, "-c", "import json, os; print(json.dumps(dict(os.environ)))"],
        text=True,
        capture_output=True,
        check=False,
    )
    child_environment = json.loads(child.stdout)

    assert child.returncode == 0, child.stderr
    assert "ALPACA_API_KEY" not in child_environment
    assert "POSTGRES_PHASE_A_REAL_DSN" not in child_environment
    assert "UNRELATED_PRIVATE_VALUE" not in child_environment
    assert child_environment["APP_ENV"] == "production"
    assert child_environment["WOLFYSTOCK_TEST_RUN_ID"] == "fixture-run"


@pytest.mark.parametrize(
    ("host", "expected"),
    [("localhost", True), ("127.0.0.1", True), ("::1", True), ("0.0.0.0", True), ("example.com", False)],
)
def test_network_guard_classifies_only_loopback_destinations_as_local(host: str, expected: bool) -> None:
    assert _is_loopback_host(host) is expected


def _run_isolated_pytest(tmp_path: Path, source: str, *args: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_network_sample.py").write_text(source, encoding="utf-8")
    env = os.environ.copy()
    env["WOLFYSTOCK_TEST_OFFLINE"] = "0"
    for key in ("NO_PROXY", "no_proxy", "LITELLM_LOCAL_MODEL_COST_MAP"):
        env.pop(key, None)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT), env.get("PYTHONPATH"))))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "tests.offline_network",
            "test_network_sample.py",
            *args,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def test_audited_network_marker_requires_double_explicit_opt_in(tmp_path: Path) -> None:
    source = """
import pytest
import socket

try:
    socket.getaddrinfo("example.com", 443)
except RuntimeError:
    COLLECTION_NETWORK_WAS_BLOCKED = True
else:
    COLLECTION_NETWORK_WAS_BLOCKED = False

@pytest.mark.network(owner="validation", reason="contract proof", audit="T446")
def test_explicit_network_case():
    import os

    assert os.environ.get("WOLFYSTOCK_TEST_OFFLINE") != "1"
    assert os.environ.get("NO_PROXY") != "*"
    assert COLLECTION_NETWORK_WAS_BLOCKED
    assert True
"""
    standard = _run_isolated_pytest(tmp_path, source)
    missing_audit = _run_isolated_pytest(tmp_path, source, "-m", "network", "--allow-test-network")
    wrong_audit = _run_isolated_pytest(
        tmp_path, source, "-m", "network", "--allow-test-network", "--network-audit", "T999"
    )
    explicit = _run_isolated_pytest(
        tmp_path, source, "-m", "network", "--allow-test-network", "--network-audit", "T446"
    )

    assert standard.returncode == 0
    assert "1 skipped" in standard.stdout
    assert missing_audit.returncode != 0
    assert "requires exactly '-m network' and a non-empty --network-audit" in (missing_audit.stdout + missing_audit.stderr)
    assert wrong_audit.returncode != 0
    assert "does not match --network-audit 'T999'" in (wrong_audit.stdout + wrong_audit.stderr)
    assert explicit.returncode == 0
    assert "1 passed" in explicit.stdout


def test_network_marker_without_audit_metadata_fails_collection(tmp_path: Path) -> None:
    result = _run_isolated_pytest(
        tmp_path,
        """
import pytest

@pytest.mark.network
def test_unowned_network_case():
    assert True
""",
    )

    assert result.returncode != 0
    assert "network marker missing owner, reason, audit" in (result.stdout + result.stderr)
