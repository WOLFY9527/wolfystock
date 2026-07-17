from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from .errors import EnvironmentFailure


ENVIRONMENT_POLICY_VERSION = "wolfystock_test_environment_policy_v1"
_SAFE_DSN = re.compile(
    r"^postgresql(?:\+[a-z0-9_]+)?://[^\s@]+@(?:localhost|127\.0\.0\.1):[0-9]+/"
    r"wolfystock_destructive_test_[a-z0-9_]+$"
)


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
    command: list[str],
) -> dict[str, str]:
    preserved = {
        key: source[key]
        for key in ("CI", "COLORTERM", "LANG", "LC_ALL", "TERM", "TZ")
        if source.get(key)
    }
    if source.get("APP_ENV"):
        preserved["APP_ENV"] = source["APP_ENV"]
    preserved.update(
        {
            "PATH": os.pathsep.join((str(managed_python.parent), str(node_bin), "/usr/bin", "/bin")),
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
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "false",
            "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED": "false",
            "PORTFOLIO_FX_UPDATE_ENABLED": "false",
        }
    )
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
