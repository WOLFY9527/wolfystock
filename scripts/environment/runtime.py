from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import EnvironmentFailure


ENVIRONMENT_POLICY_VERSION = "wolfystock_test_environment_policy_v1"
_SAFE_DSN = re.compile(
    r"^postgresql(?:\+[a-z0-9_]+)?://[^\s@]+@(?:localhost|127\.0\.0\.1):[0-9]+/"
    r"wolfystock_destructive_test_[a-z0-9_]+$"
)
_RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")


def _boolean_override(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"false", "true"}:
        raise ValueError
    return normalized


def _market_cache_backend_override(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"disabled", "redis"}:
        raise ValueError
    return normalized


def _market_cache_url_override(value: str) -> str:
    if not value:
        return value
    if len(value) > 2048 or urlparse(value).scheme not in {"redis", "rediss"}:
        raise ValueError
    return value


def _bounded_float_override(value: str) -> str:
    parsed = float(value)
    if not 0.001 <= parsed <= 5.0:
        raise ValueError
    return value


def _bounded_integer_override(value: str) -> str:
    parsed = int(value)
    if not 1 <= parsed <= 100_000:
        raise ValueError
    return value


TEST_CONFIG_OVERRIDE_VALIDATORS: Mapping[str, Callable[[str], str]] = {
    "MARKET_CACHE_REMOTE_BACKEND": _market_cache_backend_override,
    "MARKET_CACHE_REMOTE_QUEUE_SIZE": _bounded_integer_override,
    "MARKET_CACHE_REMOTE_TIMEOUT_SECONDS": _bounded_float_override,
    "MARKET_CACHE_REMOTE_URL": _market_cache_url_override,
    "WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED": _boolean_override,
    "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": _boolean_override,
    "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": _boolean_override,
}
TEST_CONFIG_OVERRIDE_KEYS = frozenset(TEST_CONFIG_OVERRIDE_VALIDATORS)


def parse_test_config_overrides(values: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in values:
        name, separator, value = item.partition("=")
        validator = TEST_CONFIG_OVERRIDE_VALIDATORS.get(name)
        if not separator or validator is None or name in overrides:
            raise EnvironmentFailure(
                "test_config_override_invalid",
                "test configuration override must use one reviewed KEY=VALUE identity",
            )
        try:
            overrides[name] = validator(value)
        except (TypeError, ValueError) as exc:
            raise EnvironmentFailure(
                "test_config_override_invalid",
                f"test configuration override value is invalid for {name}",
            ) from exc
    return overrides


@dataclass(frozen=True)
class RunContext:
    run_id: str
    root: Path
    database_path: Path
    duckdb_path: Path
    cache_dir: Path
    logs_dir: Path
    uploads_dir: Path
    temp_dir: Path
    coverage_dir: Path
    pytest_cache_dir: Path
    frontend_dir: Path
    service_dir: Path

    @property
    def mutable_paths(self) -> tuple[Path, ...]:
        return (
            self.database_path,
            self.duckdb_path,
            self.cache_dir,
            self.logs_dir,
            self.uploads_dir,
            self.temp_dir,
            self.coverage_dir,
            self.pytest_cache_dir,
            self.frontend_dir,
            self.service_dir,
        )


def create_run_context(cache_root: Path, *, run_id: str) -> RunContext:
    root = cache_root / "runs" / "active" / run_id
    paths = {
        "database_path": root / "data" / "test.sqlite3",
        "duckdb_path": root / "data" / "test.duckdb",
        "cache_dir": root / "cache",
        "logs_dir": root / "logs",
        "uploads_dir": root / "uploads",
        "temp_dir": root / "tmp",
        "coverage_dir": root / "coverage",
        "pytest_cache_dir": root / "pytest-cache",
        "frontend_dir": root / "frontend",
        "service_dir": root / "services",
    }
    for path in paths.values():
        (path.parent if path.suffix else path).mkdir(parents=True, exist_ok=True)
    return RunContext(run_id=run_id, root=root, **paths)


def write_run_json(context: RunContext, name: str, payload: dict[str, object]) -> Path:
    if Path(name).name != name or not name.endswith(".json"):
        raise ValueError("run evidence name must be a plain JSON filename")
    destination = context.service_dir / name
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def _remove_run_tree(path: Path) -> None:
    if not path.exists():
        return
    try:
        for current, directories, files in os.walk(path, topdown=False, followlinks=False):
            current_path = Path(current)
            for name in files:
                item = current_path / name
                if not item.is_symlink():
                    item.chmod(0o600)
            for name in directories:
                item = current_path / name
                if not item.is_symlink():
                    item.chmod(0o700)
            current_path.chmod(0o700)
        shutil.rmtree(path)
    except OSError as exc:
        raise EnvironmentFailure("run_cleanup_failed", "run-scoped state could not be removed") from exc
    if path.exists():
        raise EnvironmentFailure("run_cleanup_failed", "run-scoped state could not be removed")


def _destructive_postgres_authorized(command: list[str], source: dict[str, str]) -> bool:
    required = {
        "--allow-destructive-postgres",
        "--destructive-postgres-audit",
        "--destructive-postgres-target",
    }
    dsn = source.get("POSTGRES_PHASE_A_REAL_DSN", "")
    return (
        _SAFE_DSN.fullmatch(dsn) is not None
        and required.issubset(command)
        and "-m" in command
        and command[command.index("-m") + 1 : command.index("-m") + 2] == ["destructive_postgres"]
    )


def project_test_environment(
    source: dict[str, str],
    context: RunContext,
    *,
    managed_python: Path,
    node_bin: Path,
    managed_rg_dir: Path,
    browser_path: Path,
    browser_executable: Path,
    command: list[str],
    config_overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    overrides = dict(config_overrides or {})
    if set(overrides).difference(TEST_CONFIG_OVERRIDE_KEYS):
        raise EnvironmentFailure(
            "test_config_override_invalid", "test configuration override key is not reviewed"
        )
    release_controlled = bool(
        source.get("WOLFYSTOCK_RELEASE_CANDIDATE_SHA")
        or source.get("DSA_WEB_PLAYWRIGHT_EXTERNAL_SERVER")
        or source.get("APP_ENV", "").strip().lower() in {"production", "release"}
    )
    if overrides and release_controlled:
        raise EnvironmentFailure(
            "test_config_override_forbidden",
            "test configuration overrides are forbidden for production and release execution",
        )
    preserved = {
        key: source[key]
        for key in ("CI", "COLORTERM", "LANG", "LC_ALL", "TERM", "TZ")
        if source.get(key)
    }
    if source.get("APP_ENV"):
        preserved["APP_ENV"] = source["APP_ENV"]
    release_sha = source.get("WOLFYSTOCK_RELEASE_CANDIDATE_SHA")
    if release_sha:
        if _RELEASE_SHA.fullmatch(release_sha) is None:
            raise EnvironmentFailure("release_control_invalid", "release candidate SHA must be a full lowercase SHA")
        preserved["WOLFYSTOCK_RELEASE_CANDIDATE_SHA"] = release_sha
    external_server = source.get("DSA_WEB_PLAYWRIGHT_EXTERNAL_SERVER")
    if external_server:
        if external_server != "1":
            raise EnvironmentFailure("release_control_invalid", "external Playwright server mode must equal 1")
        preserved["DSA_WEB_PLAYWRIGHT_EXTERNAL_SERVER"] = external_server
    for name in ("PLAYWRIGHT_JSON_OUTPUT_NAME", "PLAYWRIGHT_OUTPUT_DIR"):
        value = source.get(name)
        if not value:
            continue
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise EnvironmentFailure("release_control_invalid", f"{name} must be a repository-relative path")
        preserved[name] = value
    preserved.update(
        {
            "PATH": os.pathsep.join(
                (
                    str(managed_python.parent),
                    str(node_bin),
                    str(managed_rg_dir),
                    "/usr/bin",
                    "/bin",
                )
            ),
            "DATABASE_PATH": str(context.database_path),
            "DUCKDB_DATABASE_PATH": str(context.duckdb_path),
            "ENV_FILE": str(context.root / "empty.env"),
            "LOG_DIR": str(context.logs_dir),
            "HOME": str(context.root / "home"),
            "TMPDIR": str(context.temp_dir),
            "TEMP": str(context.temp_dir),
            "TMP": str(context.temp_dir),
            "XDG_CACHE_HOME": str(context.cache_dir),
            "COVERAGE_FILE": str(context.coverage_dir / ".coverage"),
            "PYTEST_ADDOPTS": f"-o cache_dir={context.pytest_cache_dir}",
            "PYTEST_PLUGINS": "scripts.environment.pytest_projection",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "NO_PROXY": "*",
            "no_proxy": "*",
            "WOLFYSTOCK_TEST_OFFLINE": "1",
            "WOLFYSTOCK_TEST_RUN_ID": context.run_id,
            "WOLFYSTOCK_TEST_UPLOAD_DIR": str(context.uploads_dir),
            "WOLFYSTOCK_FRONTEND_OUTPUT_DIR": str(context.frontend_dir),
            "WOLFYSTOCK_SERVICE_STATE_DIR": str(context.service_dir),
            "WOLFYSTOCK_ENV_POLICY_VERSION": ENVIRONMENT_POLICY_VERSION,
            "LITELLM_LOCAL_MODEL_COST_MAP": "true",
            "CRYPTO_REALTIME_ENABLED": "false",
            "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
            "WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true",
            "PORTFOLIO_FX_UPDATE_ENABLED": "false",
            "PLAYWRIGHT_BROWSERS_PATH": str(browser_path),
            "WOLFYSTOCK_MANAGED_CHROMIUM_EXECUTABLE": str(browser_executable),
        }
    )
    preserved.update(overrides)
    (context.root / "home").mkdir(parents=True, exist_ok=True)
    if _destructive_postgres_authorized(command, source):
        preserved["POSTGRES_PHASE_A_REAL_DSN"] = source["POSTGRES_PHASE_A_REAL_DSN"]
    return preserved


def cleanup_run(context: RunContext, *, success: bool, retain_failures: int = 3) -> None:
    if not context.root.exists():
        return
    if success:
        _remove_run_tree(context.root)
        return
    failed_root = context.root.parents[1] / "failed"
    failed_root.mkdir(parents=True, exist_ok=True)
    destination = failed_root / context.run_id
    if destination.exists():
        _remove_run_tree(destination)
    context.root.rename(destination)
    retained = sorted(failed_root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
    for expired in retained[max(0, retain_failures) :]:
        _remove_run_tree(expired)
