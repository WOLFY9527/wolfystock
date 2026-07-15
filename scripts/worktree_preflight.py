#!/usr/bin/env python3
"""Immutable, cross-platform preflight for linked-worktree dependencies.

This module is deliberately the only implementation behind the shell and
PowerShell bootstrap entrypoints.  Its stdout/stderr contract is one JSON
object per invocation so automation can consume failures without scraping
human-oriented output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable


SCHEMA_VERSION = 1
MUTABLE_LOCAL_PATHS = (
    "dist",
    "apps/dsa-web/dist",
    ".pytest_cache",
    ".cache",
    "coverage",
    "data",
    "logs",
)


class PreflightError(RuntimeError):
    """An actionable, fail-closed bootstrap error."""


def detect_shell_flavor(
    *,
    executable: str | None = None,
    environ: dict[str, str] | None = None,
    platform_name: str | None = None,
) -> str:
    """Return ``wsl``, ``msys`` or ``posix`` using explicit capabilities.

    ``bash`` is not sufficient to distinguish these environments. WSL exports
    WSL_* markers (and its Windows launcher has a distinct path), while
    Git Bash/MSYS exports MSYSTEM/OSTYPE markers or lives below Git/MSYS.
    """
    env = environ or os.environ
    executable_text = (executable or "").replace("\\", "/").lower()
    system = (platform_name or platform.system()).lower()
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP") or "/windowsapps/" in executable_text and executable_text.endswith("/bash.exe"):
        return "wsl"
    if env.get("MSYSTEM") or env.get("MSYS2_PATH_TYPE") or env.get("OSTYPE", "").lower() in {"msys", "cygwin"}:
        return "msys"
    if "/git/" in executable_text or "/msys" in executable_text or executable_text.endswith("/usr/bin/bash") and system == "windows":
        return "msys"
    return "posix"


def windows_to_posix_path(value: str, *, shell_flavor: str) -> str:
    """Translate a Windows absolute path for one known POSIX shell flavor."""
    if shell_flavor == "posix":
        return value
    windows = PureWindowsPath(value)
    if not windows.is_absolute():
        raise ValueError(f"expected an absolute Windows path: {value}")
    drive = windows.drive.rstrip(":").lower()
    suffix = "/".join(windows.parts[1:])
    if shell_flavor == "msys":
        return f"/{drive}/{suffix}"
    if shell_flavor == "wsl":
        return f"/mnt/{drive}/{suffix}"
    raise ValueError(f"unsupported shell flavor: {shell_flavor}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_hash(value: object) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def emit(payload: dict[str, Any], *, error: bool = False) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), file=sys.stderr if error else sys.stdout)


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    except OSError as exc:
        raise PreflightError(f"unable to run {command[0]}: {exc}") from exc


def is_windows_absolute(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"))


def normalized_git_path_text(value: str, *, host: str | None = None, wsl_mount: str = "/mnt") -> str:
    """Normalize Git's absolute path spellings without interpreting .git files.

    Git Bash can report ``/c/repo``, native Git reports ``C:/repo``, and WSL
    may be handed a native drive path.  The conversion is lexical and is
    covered by tests; callers still require the resolved path to exist.
    """

    candidate = value.strip()
    if not candidate or candidate.startswith("gitdir:"):
        raise PreflightError("Git returned an empty path.")
    system = (host or platform.system()).lower()
    if system == "windows":
        if re.match(r"^/[A-Za-z]/", candidate):
            candidate = f"{candidate[1].upper()}:/{candidate[3:]}"
        if not is_windows_absolute(candidate):
            raise PreflightError("Git returned a non-absolute Windows path.")
        return candidate
    if system == "linux" and os.environ.get("WSL_DISTRO_NAME") and is_windows_absolute(candidate):
        windows = PureWindowsPath(candidate)
        drive = windows.drive.rstrip(":").lower()
        return str(Path(wsl_mount, drive, *windows.parts[1:]))
    if not candidate.startswith("/"):
        raise PreflightError("Git returned a non-absolute POSIX path.")
    return candidate


def normalize_git_path(value: str, *, host: str | None = None, wsl_mount: str = "/mnt") -> Path:
    return Path(normalized_git_path_text(value, host=host, wsl_mount=wsl_mount)).resolve(strict=False)


def require_existing(path: Path, message: str) -> Path:
    if not path.exists():
        raise PreflightError(message)
    return path.resolve(strict=True)


def git_output(root: Path, *args: str) -> str:
    result = run([*git_command(), "-C", git_argument_path(root), *args])
    if result.returncode != 0:
        raise PreflightError(f"Git path resolution failed: {result.stderr.strip() or 'unknown Git error'}")
    return result.stdout.strip()


def git_argument_path(path: Path) -> str:
    if os.environ.get("WSL_DISTRO_NAME"):
        parts = path.resolve(strict=False).parts
        if len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1:
            return f"{parts[2].upper()}:/{'/'.join(parts[3:])}"
    return str(path)


def git_command() -> list[str]:
    # A Windows-created linked worktree has a native ``gitdir: C:/...``
    # pointer.  WSL Git treats that pointer as a child of the mounted path,
    # while Git for Windows resolves it correctly.  Prefer the latter when
    # WSL is operating on a mounted Windows drive.
    if os.environ.get("WSL_DISTRO_NAME"):
        native = shutil.which("git.exe")
        if native:
            return [native]
        candidate = Path("/mnt/c/Program Files/Git/cmd/git.exe")
        if candidate.is_file():
            return [str(candidate)]
    native = shutil.which("git")
    if native:
        return [native]
    raise PreflightError("unable to locate Git; add it to PATH")


def resolve_git_layout(root: Path) -> tuple[Path, Path]:
    current = require_existing(
        normalize_git_path(git_output(root, "rev-parse", "--show-toplevel")),
        "Git reported a missing worktree root.",
    )
    common = require_existing(
        normalize_git_path(git_output(current, "rev-parse", "--path-format=absolute", "--git-common-dir")),
        "Git reported a missing common directory.",
    )
    porcelain = git_output(current, "worktree", "list", "--porcelain")
    canonical_line = next((line[9:] for line in porcelain.splitlines() if line.startswith("worktree ")), "")
    canonical = require_existing(normalize_git_path(canonical_line), "Git reported a missing canonical worktree.")
    return current, canonical


def manifest_hashes(root: Path) -> dict[str, str]:
    paths = ("requirements.txt", "apps/dsa-web/package.json", "apps/dsa-web/package-lock.json")
    hashes: dict[str, str] = {}
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise PreflightError(f"required dependency manifest is missing: {relative}")
        hashes[relative] = sha256_file(path)
    return hashes


def venv_python_version(venv: Path) -> str:
    config = venv / "pyvenv.cfg"
    if not config.is_file():
        raise PreflightError("canonical .venv is missing pyvenv.cfg; recreate it with the supported Python runtime")
    match = re.search(r"^version\s*=\s*([0-9]+\.[0-9]+)", config.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    if not match:
        raise PreflightError("canonical .venv has no Python major/minor version in pyvenv.cfg")
    return match.group(1)


def python_distribution_manifest(venv: Path) -> dict[str, str]:
    distributions: dict[str, str] = {}
    for metadata in sorted(venv.glob("**/site-packages/*.dist-info/METADATA")):
        distributions[str(metadata.relative_to(venv)).replace("\\", "/")] = sha256_file(metadata)
    if not distributions:
        raise PreflightError("canonical .venv has no installed distribution metadata; install dependencies in the canonical worktree")
    return distributions


def package_lock(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / "apps/dsa-web/package-lock.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PreflightError(f"web package-lock.json is invalid: {exc.msg}") from exc
    if not isinstance(payload.get("packages"), dict):
        raise PreflightError("web package-lock.json has no lockfile v2/v3 package map")
    return payload


def tool_command(name: str) -> list[str]:
    found = shutil.which(name)
    if found:
        return [found]
    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
    windows_candidate = Path(program_files) / "nodejs" / (f"{name}.cmd" if name == "npm" else f"{name}.exe")
    if windows_candidate.is_file():
        return [str(windows_candidate)]
    wsl_candidate = Path("/mnt/c/Program Files/nodejs") / (f"{name}.cmd" if name == "npm" else f"{name}.exe")
    if wsl_candidate.is_file():
        return [str(wsl_candidate)]
    raise PreflightError(f"unable to locate {name}; add it to PATH")


def installed_npm_manifest(root: Path) -> dict[str, Any]:
    web = root / "apps/dsa-web"
    modules = web / "node_modules"
    if not modules.is_dir():
        raise PreflightError("canonical apps/dsa-web/node_modules is missing; run npm ci in the canonical worktree")
    lock = package_lock(root)
    package_entries = lock["packages"]
    installed: dict[str, str] = {}
    integrity: dict[str, str] = {}
    for lock_path, entry in sorted(package_entries.items()):
        if not lock_path.startswith("node_modules/") or not isinstance(entry, dict):
            continue
        package_json = web / lock_path / "package.json"
        if not package_json.is_file():
            raise PreflightError(f"installed npm package is missing: {lock_path}; run npm ci in the canonical worktree")
        try:
            installed_version = json.loads(package_json.read_text(encoding="utf-8"))["version"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise PreflightError(f"installed npm package metadata is invalid: {lock_path}") from exc
        expected_version = entry.get("version")
        if expected_version and installed_version != expected_version:
            raise PreflightError(
                f"installed npm package version mismatch for {lock_path}: lockfile requires {expected_version}, installed {installed_version}; run npm ci in the canonical worktree"
            )
        installed[lock_path] = str(installed_version)
        if entry.get("integrity"):
            integrity[lock_path] = str(entry["integrity"])
    if not installed:
        raise PreflightError("canonical node_modules has no lockfile-backed installed packages; run npm ci in the canonical worktree")
    npm = run([*tool_command("npm"), "--prefix", git_argument_path(web), "ls", "--all", "--json", "--omit=optional"])
    if npm.returncode != 0:
        raise PreflightError(f"npm ls reports an incompatible installed tree; run npm ci in the canonical worktree: {npm.stderr.strip() or npm.stdout.strip()}")
    try:
        npm_payload = json.loads(npm.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightError("npm ls did not return JSON; verify the npm installation") from exc
    return {"packages": installed, "integrity": integrity, "npm_ls": stable_hash(npm_payload)}


def tool_version(command: list[str], label: str) -> str:
    result = run(command)
    if result.returncode != 0:
        raise PreflightError(f"unable to determine {label}: {result.stderr.strip() or 'command failed'}")
    return result.stdout.strip()


def platform_fingerprint() -> dict[str, Any]:
    encoding = locale.getpreferredencoding(False)
    return {
        "os": platform.system(),
        "architecture": platform.machine(),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "node_major": tool_version([*tool_command("node"), "--version"], "Node version").lstrip("v").split(".", 1)[0],
        "npm": tool_version([*tool_command("npm"), "--version"], "npm version"),
        "locale": locale.setlocale(locale.LC_CTYPE, None),
        "utf8": encoding.lower().replace("-", "") in {"utf8", "utf"},
        "git": tool_version(["git", "--version"], "Git version"),
        "link_capabilities": symlink_capabilities(),
    }


def symlink_capabilities() -> dict[str, bool]:
    # This is intentionally a non-mutating capability declaration. Actual
    # link creation is still attempted only in --apply and reports the
    # Windows privilege limitation precisely instead of guessing from this.
    return {"symlink_api": hasattr(os, "symlink"), "junction_fallback": os.name == "nt"}


def dependency_fingerprint(root: Path, configuration: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve(strict=True)
    venv = require_existing(root / ".venv", "canonical .venv is missing; create it in the canonical worktree")
    if not venv.is_dir():
        raise PreflightError("canonical .venv is not a directory")
    return {
        "schema": SCHEMA_VERSION,
        "platform": platform_fingerprint(),
        "manifests": manifest_hashes(root),
        "python": {
            "venv_python": venv_python_version(venv),
            "distributions": python_distribution_manifest(venv),
        },
        "web": installed_npm_manifest(root),
        "bootstrap": configuration,
    }


@dataclass(frozen=True)
class Link:
    label: str
    destination: Path
    source: Path
    kind: str


def same_target(destination: Path, source: Path) -> bool:
    try:
        return destination.resolve(strict=True) == source.resolve(strict=True)
    except OSError:
        return False


def create_link(link: Link) -> str:
    if os.environ.get("WSL_DISTRO_NAME") and link.kind == "directory":
        destination = git_argument_path(link.destination)
        source = git_argument_path(link.source)
        result = create_windows_junction(destination, source)
        if result.returncode != 0:
            raise PreflightError(
                f"cannot create {link.label} Windows junction from WSL: {result.stderr.strip() or result.stdout.strip()}"
            )
        return "junction"
    try:
        os.symlink(link.source, link.destination, target_is_directory=link.kind == "directory")
        return "symlink"
    except OSError as exc:
        if os.name != "nt" or link.kind != "directory":
            raise PreflightError(
                f"cannot create {link.label} symlink ({exc}); Windows Developer Mode or symlink privilege is required for file links"
            ) from exc
        result = create_windows_junction(str(link.destination), str(link.source))
        if result.returncode != 0:
            raise PreflightError(
                f"cannot create {link.label} link; Windows symlink/junction capability is unavailable: {result.stderr.strip() or result.stdout.strip()}"
            )
        return "junction"


def create_windows_junction(destination: str, source: str) -> subprocess.CompletedProcess[str]:
    executable = "powershell.exe"
    if os.environ.get("WSL_DISTRO_NAME"):
        candidate = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
        if candidate.is_file():
            executable = str(candidate)
    quote = lambda value: value.replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop'; "
        f"New-Item -ItemType Junction -Path '{quote(destination)}' -Target '{quote(source)}' | Out-Null"
    )
    return run([executable, "-NoProfile", "-NonInteractive", "-Command", command])


def external_env_link(root: Path, canonical: Path) -> Link | None:
    value = os.environ.get("WORKTREE_BOOTSTRAP_ENV_FILE")
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute() or not candidate.is_file():
        raise PreflightError("WORKTREE_BOOTSTRAP_ENV_FILE must be an existing absolute repo-external file path")
    source = candidate.resolve(strict=True)
    if source.is_relative_to(root) or source.is_relative_to(canonical):
        raise PreflightError("WORKTREE_BOOTSTRAP_ENV_FILE must point outside both repository worktrees")
    return Link(".env", root / ".env", source, "file")


def bootstrap(mode: str) -> dict[str, Any]:
    if os.environ.get("WORKTREE_BOOTSTRAP_ISOLATED") == "1":
        return {"status": "ok", "mode": mode, "isolated": True, "actions": ["shared dependency reuse skipped"]}
    root, canonical = resolve_git_layout(Path.cwd())
    if root == canonical:
        raise PreflightError("run this bootstrap from a linked worktree, not the canonical main worktree")
    config = {
        "isolated": False,
        "env_file_opt_in": bool(os.environ.get("WORKTREE_BOOTSTRAP_ENV_FILE")),
        "mutable_local_paths": MUTABLE_LOCAL_PATHS,
    }
    fingerprints = dependency_fingerprint(canonical, config)
    linked_manifests = manifest_hashes(root)
    if linked_manifests != fingerprints["manifests"]:
        raise PreflightError("dependency manifests differ from the canonical dependency fingerprint; use WORKTREE_BOOTSTRAP_ISOLATED=1 and install dependencies locally")
    links = [
        Link(".venv", root / ".venv", canonical / ".venv", "directory"),
        Link("apps/dsa-web/node_modules", root / "apps/dsa-web/node_modules", canonical / "apps/dsa-web/node_modules", "directory"),
    ]
    env_link = external_env_link(root, canonical)
    if env_link:
        links.append(env_link)
    actions: list[str] = []
    for link in links:
        if link.destination.exists() or link.destination.is_symlink():
            if not same_target(link.destination, link.source):
                raise PreflightError(f"refusing to replace {link.label}: destination is not the qualified canonical dependency link")
            actions.append(f"{link.label} already linked")
        elif mode == "--check":
            actions.append(f"would link {link.label}")
        else:
            if not link.destination.parent.is_dir():
                raise PreflightError(f"parent directory is missing for {link.label}; refusing to create non-link paths")
            actions.append(f"linked {link.label} ({create_link(link)})")
    return {
        "status": "ok",
        "mode": mode.removeprefix("--"),
        "root": str(root),
        "canonical_root": str(canonical),
        "fingerprint": stable_hash(fingerprints),
        "components": {"python": stable_hash(fingerprints["python"]), "web": stable_hash(fingerprints["web"])},
        "actions": actions,
        "mutable_local_paths": MUTABLE_LOCAL_PATHS,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bootstrap_parser = subparsers.add_parser("bootstrap")
    mode = bootstrap_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    fingerprint_parser = subparsers.add_parser("fingerprint")
    fingerprint_parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv or sys.argv[1:])
        if args.command == "bootstrap":
            emit(bootstrap("--check" if args.check else "--apply"))
        else:
            root = args.root.resolve(strict=True)
            config = {"isolated": False, "env_file_opt_in": False, "mutable_local_paths": MUTABLE_LOCAL_PATHS}
            fingerprint = dependency_fingerprint(root, config)
            emit({"status": "ok", "fingerprint": stable_hash(fingerprint), "payload": fingerprint})
        return 0
    except (PreflightError, OSError, ValueError) as exc:
        emit({"status": "error", "reason": str(exc), "remediation": "Run WORKTREE_BOOTSTRAP_ISOLATED=1 and install dependencies locally, or repair the canonical dependency tree."}, error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
