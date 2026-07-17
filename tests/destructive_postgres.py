"""Fail-closed pytest policy for destructive real PostgreSQL tests."""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


DESTRUCTIVE_MARKER = "destructive_postgres"
DSN_ENV_VAR = "POSTGRES_PHASE_A_REAL_DSN"
_DISPOSABLE_DATABASE = re.compile(r"^wolfystock_destructive_test_[a-z0-9_]+$")
_PRODUCTION_LIKE_TOKENS = {"default", "main", "primary", "prod", "production", "shared", "staging"}
_AUDIT_ID = re.compile(r"^T[0-9]+(?:-[A-Za-z0-9_-]+)?$")
_ACTIVE_TARGET: DestructivePostgresTarget | None = None


class DestructivePostgresPolicyError(RuntimeError):
    """Raised before any connection when a destructive target is unsafe."""


@dataclass(frozen=True)
class DestructivePostgresTarget:
    identity: str
    schema: str
    audit_id: str
    maintenance_url: URL
    scoped_url: URL

    @property
    def scoped_dsn(self) -> str:
        return self.scoped_url.render_as_string(hide_password=False)

    def audit_record(self) -> str:
        return json.dumps(
            {
                "auditId": self.audit_id,
                "databaseTarget": self.identity,
                "runSchema": self.schema,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def _parse_allowed_target(value: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"(localhost|127\.0\.0\.1):([0-9]{1,5})/([a-z0-9_]+)", value)
    if not match:
        raise DestructivePostgresPolicyError(
            "destructive PostgreSQL exact target identity must be HOST:PORT/DATABASE on loopback"
        )
    port = int(match.group(2))
    if not 1 <= port <= 65535:
        raise DestructivePostgresPolicyError("destructive PostgreSQL target port is invalid")
    return match.group(1), port, match.group(3)


def qualify_target(*, dsn: str, allowed_target: str, audit_id: str) -> DestructivePostgresTarget:
    """Validate an exact disposable identity without connecting to PostgreSQL."""

    if not _AUDIT_ID.fullmatch(audit_id):
        raise DestructivePostgresPolicyError("destructive PostgreSQL opt-in requires an audited task identifier")
    if not dsn:
        raise DestructivePostgresPolicyError(f"{DSN_ENV_VAR} is required after explicit destructive opt-in")
    try:
        url = make_url(dsn)
    except Exception as exc:
        raise DestructivePostgresPolicyError("destructive PostgreSQL DSN is invalid") from exc
    if not url.drivername.startswith("postgresql"):
        raise DestructivePostgresPolicyError("destructive PostgreSQL DSN must use a PostgreSQL driver")
    if "options" in url.query:
        raise DestructivePostgresPolicyError("destructive PostgreSQL DSN may not override schema options")
    host, port, database = _parse_allowed_target(allowed_target)
    actual = (str(url.host or ""), int(url.port or 0), str(url.database or ""))
    if actual != (host, port, database):
        raise DestructivePostgresPolicyError("destructive PostgreSQL DSN does not match the exact target identity")
    if not _DISPOSABLE_DATABASE.fullmatch(database) or _PRODUCTION_LIKE_TOKENS.intersection(database.split("_")):
        raise DestructivePostgresPolicyError(
            "destructive PostgreSQL requires an unambiguous disposable database identity"
        )

    schema = f"wolfystock_run_{secrets.token_hex(8)}"
    scoped_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    return DestructivePostgresTarget(
        identity=allowed_target,
        schema=schema,
        audit_id=audit_id,
        maintenance_url=url,
        scoped_url=scoped_url,
    )


def current_target() -> DestructivePostgresTarget:
    if _ACTIVE_TARGET is None:
        raise DestructivePostgresPolicyError("destructive PostgreSQL target is not active")
    return _ACTIVE_TARGET


def _activate_target(target: DestructivePostgresTarget) -> None:
    global _ACTIVE_TARGET
    engine = create_engine(target.maintenance_url, echo=False, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'create schema "{target.schema}"'))
    except Exception as exc:
        raise DestructivePostgresPolicyError(
            f"unable to create run-scoped PostgreSQL schema for {target.identity}"
        ) from exc
    finally:
        engine.dispose()
    _ACTIVE_TARGET = target


def _deactivate_target() -> None:
    global _ACTIVE_TARGET
    target = _ACTIVE_TARGET
    _ACTIVE_TARGET = None
    if target is None:
        return
    engine = create_engine(target.maintenance_url, echo=False, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'drop schema "{target.schema}" cascade'))
    finally:
        engine.dispose()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("destructive-postgres", "isolated destructive PostgreSQL validation")
    group.addoption("--allow-destructive-postgres", action="store_true", default=False)
    group.addoption("--destructive-postgres-audit", default=None, metavar="AUDIT_ID")
    group.addoption("--destructive-postgres-target", default=None, metavar="HOST:PORT/DATABASE")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "destructive_postgres: destructive real-PostgreSQL test requiring explicit disposable-target qualification",
    )
    allow = config.getoption("--allow-destructive-postgres")
    audit_id = config.getoption("--destructive-postgres-audit")
    allowed_target = config.getoption("--destructive-postgres-target")
    markexpr = config.getoption("-m").strip()
    if not allow and not audit_id and not allowed_target:
        config._wolfystock_destructive_postgres_target = None  # type: ignore[attr-defined]
        return
    if not allow or not audit_id or not allowed_target:
        raise pytest.UsageError(
            "destructive PostgreSQL requires --allow-destructive-postgres, "
            "--destructive-postgres-audit and --destructive-postgres-target together"
        )
    if markexpr != DESTRUCTIVE_MARKER:
        raise pytest.UsageError(
            "--allow-destructive-postgres requires exactly '-m destructive_postgres'"
        )
    try:
        target = qualify_target(
            dsn=str(os.environ.get(DSN_ENV_VAR) or "").strip(),
            allowed_target=allowed_target,
            audit_id=audit_id,
        )
    except DestructivePostgresPolicyError as exc:
        raise pytest.UsageError(str(exc)) from exc
    config._wolfystock_destructive_postgres_target = target  # type: ignore[attr-defined]


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--allow-destructive-postgres"):
        return
    reason = "destructive PostgreSQL tests require explicit audited disposable-target opt-in"
    for item in items:
        if item.get_closest_marker(DESTRUCTIVE_MARKER) is not None:
            item.add_marker(pytest.mark.skip(reason=reason))


def pytest_collection_finish(session: pytest.Session) -> None:
    target = getattr(session.config, "_wolfystock_destructive_postgres_target", None)
    if target is None:
        return
    nodes = [item for item in session.items if item.get_closest_marker(DESTRUCTIVE_MARKER) is not None]
    if not nodes:
        raise pytest.UsageError("destructive PostgreSQL qualification selected zero destructive PostgreSQL nodes")
    try:
        _activate_target(target)
    except DestructivePostgresPolicyError as exc:
        raise pytest.UsageError(str(exc)) from exc
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(f"destructive-postgres-target: {target.audit_record()}")


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    try:
        _deactivate_target()
    except Exception:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
