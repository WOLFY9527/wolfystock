from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .errors import EnvironmentFailure, OfflineMaterialUnavailable
from .identity import ToolchainIdentity, file_hash, npm_command, stable_hash


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=kwargs.pop("timeout", 900),
            **kwargs,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnvironmentFailure("package_manager_unavailable", "package manager invocation failed") from exc


@contextmanager
def _bootstrap_environment(*, offline: bool) -> Iterator[dict[str, str]]:
    allowed = (
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "PIP_CACHE_DIR",
        "npm_config_cache",
    )
    if not offline:
        allowed += ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "all_proxy", "http_proxy", "https_proxy", "no_proxy")
    projected = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    projected["PYTHONDONTWRITEBYTECODE"] = "1"
    projected["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    projected["PIP_CONFIG_FILE"] = os.devnull
    if offline:
        projected.update(
            {
                "PIP_NO_INDEX": "1",
                "npm_config_offline": "true",
                "NO_PROXY": "*",
                "no_proxy": "*",
            }
        )
    with tempfile.TemporaryDirectory(prefix="wolfystock-package-config-") as temporary:
        config_root = Path(temporary)
        user_config = config_root / "user.npmrc"
        global_config = config_root / "global.npmrc"
        user_config.write_text("", encoding="utf-8")
        global_config.write_text("", encoding="utf-8")
        projected["npm_config_userconfig"] = str(user_config)
        projected["npm_config_globalconfig"] = str(global_config)
        yield projected


def _metadata_hashes(snapshot: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for pattern in ("**/*.dist-info/METADATA", "**/*.dist-info/RECORD"):
        for path in sorted(snapshot.glob(pattern)):
            hashes[path.relative_to(snapshot).as_posix()] = file_hash(path)
    if not hashes:
        raise EnvironmentFailure("python_distribution_metadata_missing", "Python distribution metadata is missing")
    return hashes


def _update_digest(digest: Any, *values: str) -> None:
    for value in values:
        encoded = value.encode("utf-8", errors="surrogateescape")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)


def _content_tree_identity(snapshot: Path, roots: tuple[Path, ...]) -> dict[str, object]:
    digest = hashlib.sha256()
    file_count = 0
    symlink_count = 0
    total_bytes = 0
    entries: list[Path] = []
    for root in roots:
        if not root.is_dir():
            raise EnvironmentFailure("installed_content_tree_missing", "installed content tree is missing")
        entries.extend(root.rglob("*"))
    for path in sorted(entries, key=lambda item: item.relative_to(snapshot).as_posix()):
        relative = path.relative_to(snapshot).as_posix()
        if path.is_symlink():
            target = os.readlink(path)
            _update_digest(digest, relative, "symlink", target)
            symlink_count += 1
            continue
        if path.is_dir():
            _update_digest(digest, relative, "directory")
            continue
        if not path.is_file():
            raise EnvironmentFailure(
                "installed_content_entry_invalid", f"unsupported installed content entry: {relative}"
            )
        size = path.stat().st_size
        _update_digest(digest, relative, "file", str(size), file_hash(path))
        file_count += 1
        total_bytes += size
    return {
        "sha256": digest.hexdigest(),
        "fileCount": file_count,
        "symlinkCount": symlink_count,
        "totalBytes": total_bytes,
    }


def _python_site_packages(snapshot: Path) -> tuple[Path, ...]:
    candidates = sorted(
        {
            *snapshot.glob("lib/python*/site-packages"),
            *snapshot.glob("lib64/python*/site-packages"),
            snapshot / "Lib" / "site-packages",
        }
    )
    roots = tuple(path for path in candidates if path.is_dir())
    if not roots:
        raise EnvironmentFailure("python_site_packages_missing", "Python site-packages is missing")
    return roots


def _remove_python_bytecode(snapshot: Path) -> None:
    for bytecode in snapshot.rglob("*.pyc"):
        bytecode.unlink(missing_ok=True)
    for cache in sorted(snapshot.rglob("__pycache__"), reverse=True):
        try:
            cache.rmdir()
        except OSError:
            continue


def _normalize_distribution_records(snapshot: Path) -> None:
    for root in _python_site_packages(snapshot):
        for record in sorted(root.glob("*.dist-info/RECORD")):
            with record.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            normalized: list[list[str]] = []
            for row in rows:
                if not row:
                    continue
                padded = (row + ["", ""])[:3]
                if padded[0].startswith("../"):
                    padded[1:] = ["", ""]
                normalized.append(padded)
            with record.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows(normalized)


class PythonComponent:
    name = "python"
    immutable = True
    critical_imports = ("fastapi", "pytest", "sqlalchemy")

    def __init__(
        self,
        root: Path,
        input_fingerprint: str,
        toolchain: ToolchainIdentity,
        *,
        command_runner: CommandRunner = _run,
    ) -> None:
        self.root = root
        self.input_fingerprint = input_fingerprint
        self.toolchain = toolchain
        self.command_runner = command_runner

    @staticmethod
    def python_path(snapshot: Path) -> Path:
        candidates = (snapshot / "bin" / "python", snapshot / "Scripts" / "python.exe")
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise EnvironmentFailure("managed_python_missing", "managed Python interpreter is missing")

    def _offline_wheel_arguments(self, destination: Path) -> list[str]:
        with _bootstrap_environment(offline=True) as environment:
            cache_result = self.command_runner(
                [sys.executable, "-m", "pip", "cache", "dir"], env=environment
            )
        if cache_result.returncode != 0:
            return []
        cache = Path(cache_result.stdout.strip()) / "wheels"
        wheels = sorted(cache.glob("**/*.whl")) if cache.is_dir() else []
        if not wheels:
            return []
        links = destination / ".offline-wheels"
        links.mkdir()
        index = links / "index.html"
        anchors = [
            f'<a href="{html.escape(wheel.resolve(strict=True).as_uri())}">{html.escape(wheel.name)}</a>'
            for wheel in wheels
        ]
        index.write_text("\n".join(anchors) + "\n", encoding="utf-8")
        return ["--find-links", index.as_uri()]

    def build(self, destination: Path, *, offline: bool) -> None:
        with _bootstrap_environment(offline=offline) as environment:
            create = self.command_runner(
                [sys.executable, "-m", "venv", str(destination)], env=environment
            )
        if create.returncode != 0:
            raise EnvironmentFailure("python_environment_creation_failed", "managed Python environment creation failed")
        python = self.python_path(destination)
        offline_args = self._offline_wheel_arguments(destination) if offline else []
        command = [
            str(python),
            "-I",
            "-m",
            "pip",
            "install",
            "--no-input",
            *offline_args,
            "-r",
            str(self.root / "requirements-dev.txt"),
        ]
        with _bootstrap_environment(offline=offline) as environment:
            install = self.command_runner(command, cwd=self.root, env=environment)
        shutil.rmtree(destination / ".offline-wheels", ignore_errors=True)
        if install.returncode != 0:
            if offline:
                raise OfflineMaterialUnavailable(
                    "offline_python_material_unavailable", "offline_python_material_unavailable"
                )
            raise EnvironmentFailure("python_dependency_install_failed", "Python dependency installation failed")
        _remove_python_bytecode(destination)
        _normalize_distribution_records(destination)

    def _probe(self, snapshot: Path) -> dict[str, Any]:
        python = self.python_path(snapshot)
        source = (
            "import importlib,json,platform,sys; names=json.loads(sys.argv[1]); imports={};"
            "\nfor name in names:\n"
            " try: importlib.import_module(name); imports[name]=True\n"
            " except Exception: imports[name]=False\n"
            "print(json.dumps({'implementation':platform.python_implementation(),'version':platform.python_version(),"
            "'prefix':sys.prefix,'basePrefix':sys.base_prefix,'imports':imports},sort_keys=True))"
        )
        result = self.command_runner(
            [str(python), "-I", "-B", "-c", source, json.dumps(self.critical_imports)],
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise EnvironmentFailure("managed_python_probe_failed", "managed Python probe failed") from exc
        if result.returncode != 0 or not isinstance(payload, dict):
            raise EnvironmentFailure("managed_python_probe_failed", "managed Python probe failed")
        if Path(str(payload.get("prefix"))).resolve(strict=False) != snapshot.resolve(strict=False):
            raise EnvironmentFailure("managed_python_prefix_mismatch", "managed Python prefix does not match snapshot")
        if payload.get("basePrefix") == payload.get("prefix"):
            raise EnvironmentFailure("managed_python_prefix_mismatch", "managed Python is not isolated")
        if (
            payload.get("implementation") != self.toolchain.python_implementation
            or payload.get("version") != self.toolchain.python_version
        ):
            raise EnvironmentFailure("managed_python_identity_mismatch", "managed Python identity does not match")
        imports = payload.get("imports") if isinstance(payload.get("imports"), dict) else {}
        missing = sorted(name for name in self.critical_imports if imports.get(name) is not True)
        if missing:
            raise EnvironmentFailure("python_critical_import_failed", "python_critical_import_failed:" + ",".join(missing))
        return payload

    def inspect(self, snapshot: Path) -> dict[str, object]:
        probe = self._probe(snapshot)
        python = self.python_path(snapshot)
        check = self.command_runner(
            [str(python), "-I", "-B", "-m", "pip", "check"], env={"PYTHONDONTWRITEBYTECODE": "1"}
        )
        if check.returncode != 0:
            raise EnvironmentFailure("python_dependency_metadata_inconsistent", "pip check rejected dependency metadata")
        return {
            "implementation": probe["implementation"],
            "version": probe["version"],
            "interpreterSha256": file_hash(python.resolve(strict=True)),
            "distributionMetadata": _metadata_hashes(snapshot),
            "contentTree": _content_tree_identity(snapshot, _python_site_packages(snapshot)),
            "criticalImports": list(self.critical_imports),
        }

    def verify(self, snapshot: Path, manifest: dict[str, object]) -> None:
        if self.inspect(snapshot) != manifest.get("installed"):
            raise EnvironmentFailure("python_installed_identity_mismatch", "python_installed_identity_mismatch")

    def prepare_promotion(self, temporary: Path, final: Path) -> None:
        scripts = temporary / ("Scripts" if os.name == "nt" else "bin")
        old = str(temporary).encode()
        new = str(final).encode()
        old_name = temporary.name.encode()
        new_name = final.name.encode()
        candidates = list(scripts.iterdir()) if scripts.is_dir() else []
        candidates.append(temporary / "pyvenv.cfg")
        for path in candidates:
            if not path.is_file() or path.is_symlink():
                continue
            try:
                content = path.read_bytes()
            except OSError:
                continue
            rewritten = content.replace(old, new).replace(old_name, new_name)
            if rewritten != content:
                path.write_bytes(rewritten)


def _platform_allows(entry: dict[str, Any]) -> bool:
    current_os = platform.system().lower()
    current_cpu = platform.machine().lower()
    for field, current in (("os", current_os), ("cpu", current_cpu)):
        values = entry.get(field)
        if values is None:
            continue
        if not isinstance(values, list):
            return False
        included = {str(value).lower() for value in values if not str(value).startswith("!")}
        excluded = {str(value)[1:].lower() for value in values if str(value).startswith("!")}
        if current in excluded or included and current not in included:
            return False
    return True


def _normalize_npm_tree(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_npm_tree(item)
            for key, item in sorted(value.items())
            if key not in {"path", "resolved", "_id"}
        }
    if isinstance(value, list):
        return [_normalize_npm_tree(item) for item in value]
    return value


class WebComponent:
    name = "web"
    immutable = True

    def __init__(
        self,
        root: Path,
        input_fingerprint: str,
        toolchain: ToolchainIdentity,
        *,
        command_runner: CommandRunner = _run,
    ) -> None:
        self.root = root
        self.input_fingerprint = input_fingerprint
        self.toolchain = toolchain
        self.command_runner = command_runner

    @property
    def web_root(self) -> Path:
        return self.root / "apps" / "dsa-web"

    def build(self, destination: Path, *, offline: bool) -> None:
        shutil.copy2(self.web_root / "package.json", destination / "package.json")
        shutil.copy2(self.web_root / "package-lock.json", destination / "package-lock.json")
        command = npm_command("--prefix", str(destination), "ci", "--no-audit", "--no-fund")
        if offline:
            command.append("--offline")
        with _bootstrap_environment(offline=offline) as environment:
            install = self.command_runner(command, env=environment)
        modules = destination / "node_modules"
        if install.returncode != 0 or not modules.is_dir():
            if offline:
                raise OfflineMaterialUnavailable("offline_web_material_unavailable", "offline_web_material_unavailable")
            raise EnvironmentFailure("web_dependency_install_failed", "Web dependency installation failed")

    def _lock_packages(self) -> dict[str, Any]:
        try:
            payload = json.loads((self.web_root / "package-lock.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EnvironmentFailure("web_lockfile_invalid", "Web lockfile is invalid") from exc
        packages = payload.get("packages")
        if not isinstance(packages, dict):
            raise EnvironmentFailure("web_lockfile_invalid", "Web lockfile package map is invalid")
        return packages

    def _npm_tree(self, snapshot: Path) -> object:
        with _bootstrap_environment(offline=True) as environment:
            result = self.command_runner(
                npm_command("--prefix", str(snapshot), "ls", "--all", "--json", "--omit=optional"),
                env=environment,
            )
        if result.returncode != 0:
            raise EnvironmentFailure("web_dependency_tree_invalid", "web_dependency_tree_invalid")
        try:
            return _normalize_npm_tree(json.loads(result.stdout))
        except json.JSONDecodeError as exc:
            raise EnvironmentFailure("web_dependency_tree_invalid", "web_dependency_tree_invalid") from exc

    def inspect(self, snapshot: Path) -> dict[str, object]:
        modules = snapshot / "node_modules"
        if not modules.is_dir():
            raise EnvironmentFailure("web_dependency_tree_missing", "Web node_modules tree is missing")
        snapshot_lock = snapshot / "package-lock.json"
        if not snapshot_lock.is_file() or file_hash(snapshot_lock) != file_hash(self.web_root / "package-lock.json"):
            raise EnvironmentFailure("web_lock_identity_mismatch", "Web snapshot lockfile does not match")
        installed: dict[str, dict[str, str]] = {}
        for lock_path, entry in sorted(self._lock_packages().items()):
            if not lock_path.startswith("node_modules/") or not isinstance(entry, dict):
                continue
            expected = entry.get("version")
            optional = entry.get("optional") is True
            if not isinstance(expected, str):
                raise EnvironmentFailure("web_lockfile_invalid", f"web_lockfile_invalid:{lock_path}")
            package_json = modules / lock_path.removeprefix("node_modules/") / "package.json"
            if not package_json.is_file():
                if optional or not _platform_allows(entry):
                    continue
                raise EnvironmentFailure("web_dependency_missing", f"web_dependency_missing:{lock_path}")
            try:
                package = json.loads(package_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise EnvironmentFailure("web_dependency_metadata_invalid", f"web_dependency_metadata_invalid:{lock_path}") from exc
            if package.get("version") != expected:
                raise EnvironmentFailure("web_dependency_version_mismatch", f"web_dependency_version_mismatch:{lock_path}")
            installed[lock_path] = {"version": expected, "metadataSha256": file_hash(package_json)}
        if not installed:
            raise EnvironmentFailure("web_dependency_metadata_missing", "Web dependency metadata is missing")
        return {
            "nodeVersion": self.toolchain.node_version,
            "npmVersion": self.toolchain.npm_version,
            "packageLockSha256": file_hash(snapshot_lock),
            "packages": installed,
            "npmTreeFingerprint": stable_hash(self._npm_tree(snapshot)),
            "contentTree": _content_tree_identity(snapshot, (modules,)),
        }

    def verify(self, snapshot: Path, manifest: dict[str, object]) -> None:
        if self.inspect(snapshot) != manifest.get("installed"):
            raise EnvironmentFailure("web_installed_identity_mismatch", "web_installed_identity_mismatch")

    def prepare_promotion(self, temporary: Path, final: Path) -> None:
        return None
