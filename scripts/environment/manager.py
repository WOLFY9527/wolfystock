from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .cache import environment_cache_root
from .components import PythonComponent, WebComponent
from .errors import EnvironmentFailure
from .identity import (
    BOOTSTRAP_IMPLEMENTATION_VERSION,
    ENVIRONMENT_SCHEMA_VERSION,
    EnvironmentIdentity,
    ToolchainIdentity,
    calculate_environment_identity,
    detect_toolchain,
    stable_hash,
)
from .runtime import ENVIRONMENT_POLICY_VERSION
from .python_lock import (
    PythonLockContract,
    bootstrap_profile_for_target,
    load_python_lock,
)
from .snapshots import SnapshotResult, ensure_snapshot, verify_cached_snapshot


EVIDENCE_SCHEMA = "wolfystock_environment_evidence_v1"
POINTER_SCHEMA = "wolfystock_worktree_environment_pointer_v1"


@dataclass(frozen=True)
class VerifiedEnvironment:
    identity: EnvironmentIdentity
    python: SnapshotResult
    web: SnapshotResult
    combined_fingerprint: str
    evidence: dict[str, Any]


def _cache_relative(cache_root: Path, path: Path) -> str:
    try:
        relative = path.resolve(strict=True).relative_to(cache_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise EnvironmentFailure("snapshot_outside_cache", "dependency snapshot is outside the environment cache") from exc
    return "$CACHE/" + relative.as_posix()


def _legacy_backup(cache_root: Path, destination: Path, label: str) -> Path:
    legacy = cache_root / "legacy"
    legacy.mkdir(parents=True, exist_ok=True)
    backup = legacy / f"{label}-{int(time.time())}-{uuid.uuid4().hex}"
    destination.rename(backup)
    siblings = sorted(legacy.glob(f"{label}-*"), key=lambda item: item.stat().st_mtime, reverse=True)
    for expired in siblings[2:]:
        if expired.is_dir() and not expired.is_symlink():
            shutil.rmtree(expired, ignore_errors=True)
        else:
            expired.unlink(missing_ok=True)
    return backup


def _replace_with_link(destination: Path, target: Path, cache_root: Path, label: str) -> None:
    if destination.is_symlink() and destination.resolve(strict=False) == target.resolve(strict=True):
        return
    if destination.exists() and not destination.is_symlink() and destination.resolve(strict=False) == target.resolve(strict=True):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_name(f".{destination.name}.wolfy-{uuid.uuid4().hex}")
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(staged), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0 or not staged.is_dir():
                raise OSError("directory junction creation failed")
        else:
            staged.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        raise EnvironmentFailure("dependency_link_creation_failed", f"unable to create {label} dependency link") from exc
    backup: Path | None = None
    try:
        if destination.exists() and not destination.is_symlink():
            backup = _legacy_backup(cache_root, destination, label)
        os.replace(staged, destination)
    except OSError as exc:
        staged.unlink(missing_ok=True)
        if backup is not None and not destination.exists():
            backup.rename(destination)
        raise EnvironmentFailure("dependency_link_promotion_failed", f"unable to promote {label} dependency link") from exc


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def combined_environment_fingerprint(
    identity: EnvironmentIdentity, python: SnapshotResult, web: SnapshotResult
) -> str:
    return stable_hash(
        {
            "schemaVersion": EVIDENCE_SCHEMA,
            "combinedInputFingerprint": identity.combined_input_fingerprint,
            "pythonInstalledFingerprint": python.installed_fingerprint,
            "webInstalledFingerprint": web.installed_fingerprint,
            "environmentPolicyVersion": ENVIRONMENT_POLICY_VERSION,
        }
    )


def link_worktree_environment(
    root: Path,
    cache_root: Path,
    python: SnapshotResult,
    web: SnapshotResult,
    *,
    combined_fingerprint: str,
) -> Path:
    root = root.resolve(strict=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    for result in (python, web):
        if not result.path.is_dir() or not (result.path / "provenance.json").is_file():
            raise EnvironmentFailure("replacement_snapshot_missing", "replacement_snapshot_missing")
        _cache_relative(cache_root, result.path)
    if not (web.path / "node_modules").is_dir():
        raise EnvironmentFailure("replacement_snapshot_missing", "replacement_snapshot_missing")
    _replace_with_link(root / ".venv", python.path, cache_root, "python")
    _replace_with_link(
        root / "apps" / "dsa-web" / "node_modules", web.path / "node_modules", cache_root, "web"
    )
    pointer = root / ".wolfy" / "environment.json"
    _write_json_atomic(
        pointer,
        {
            "schemaVersion": POINTER_SCHEMA,
            "combinedFingerprint": combined_fingerprint,
            "components": {
                "python": {
                    "inputFingerprint": python.input_fingerprint,
                    "installedFingerprint": python.installed_fingerprint,
                    "snapshot": _cache_relative(cache_root, python.path),
                },
                "web": {
                    "inputFingerprint": web.input_fingerprint,
                    "installedFingerprint": web.installed_fingerprint,
                    "snapshot": _cache_relative(cache_root, web.path),
                },
            },
        },
    )
    return pointer


def managed_python_path(root: Path) -> Path:
    candidates = (root / ".venv" / "bin" / "python", root / ".venv" / "Scripts" / "python.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise EnvironmentFailure("managed_python_missing", "managed Python is missing; run ./wolfy bootstrap --ensure")


def require_managed_python(root: Path, *, executable: Path | None = None) -> Path:
    expected = managed_python_path(root).resolve(strict=True)
    actual = (executable or Path(sys.executable)).resolve(strict=False)
    if actual != expected:
        raise EnvironmentFailure("wrong_managed_interpreter", "wrong_managed_interpreter")
    return expected


def _toolchain_evidence(toolchain: Mapping[str, Any]) -> dict[str, Any]:
    aliases = {
        "os_name": "os",
        "architecture": "architecture",
        "python_implementation": "pythonImplementation",
        "python_version": "pythonVersion",
        "node_version": "nodeVersion",
        "npm_version": "npmVersion",
        "install_mode": "installMode",
    }
    allowed = set(aliases.values())
    projected: dict[str, Any] = {}
    for key, value in toolchain.items():
        name = aliases.get(key, key)
        if name in allowed and isinstance(value, str):
            projected[name] = value
    return dict(sorted(projected.items()))


def build_environment_evidence(
    *,
    combined_fingerprint: str,
    python: SnapshotResult,
    web: SnapshotResult,
    manifest_hashes: dict[str, str],
    python_lock_evidence: dict[str, Any],
    toolchain: Mapping[str, Any],
    run_id: str | None,
    network_used: bool,
    verified_at: str,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    root = cache_root or python.path.parents[3]
    return {
        "schemaVersion": EVIDENCE_SCHEMA,
        "environmentIdentity": {
            "schemaVersion": ENVIRONMENT_SCHEMA_VERSION,
            "bootstrapImplementationVersion": BOOTSTRAP_IMPLEMENTATION_VERSION,
        },
        "environmentFingerprint": combined_fingerprint,
        "componentFingerprints": {
            "python": {
                "input": python.input_fingerprint,
                "installed": python.installed_fingerprint,
            },
            "web": {"input": web.input_fingerprint, "installed": web.installed_fingerprint},
        },
        "manifestHashes": dict(sorted(manifest_hashes.items())),
        "pythonLock": python_lock_evidence,
        "toolchain": _toolchain_evidence(toolchain),
        "snapshots": {
            "python": _cache_relative(root, python.path),
            "web": _cache_relative(root, web.path),
        },
        "environmentPolicyVersion": ENVIRONMENT_POLICY_VERSION,
        "operational": {
            "bootstrapNetworkUsed": network_used,
            "runId": run_id,
            "verifiedAt": verified_at,
        },
    }


class EnvironmentManager:
    def __init__(
        self,
        root: Path,
        *,
        cache_root: Path | None = None,
        toolchain: ToolchainIdentity | None = None,
    ) -> None:
        self.root = root.resolve(strict=True)
        self.cache_root = (cache_root or environment_cache_root()).resolve(strict=False)
        self.cache_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            try:
                self.cache_root.chmod(0o700)
            except OSError as exc:
                raise EnvironmentFailure(
                    "environment_cache_permissions_invalid", "unable to restrict environment cache permissions"
                ) from exc
        self.toolchain = toolchain or detect_toolchain()
        python_profile = bootstrap_profile_for_target(
            os_name=self.toolchain.os_name,
            architecture=self.toolchain.architecture,
            python_version=self.toolchain.python_version,
            python_implementation=self.toolchain.python_implementation,
        )
        self.python_lock: PythonLockContract = load_python_lock(
            self.root,
            os_name=self.toolchain.os_name,
            architecture=self.toolchain.architecture,
            python_version=self.toolchain.python_version,
            python_implementation=self.toolchain.python_implementation,
            profile=python_profile,
        )
        self.identity = calculate_environment_identity(self.root, self.toolchain)

    def _components(self) -> tuple[PythonComponent, WebComponent]:
        return (
            PythonComponent(
                self.root,
                self.identity.python_input_fingerprint,
                self.toolchain,
                lock_contract=self.python_lock,
                artifact_cache_root=self.cache_root / "artifacts" / "python",
            ),
            WebComponent(self.root, self.identity.web_input_fingerprint, self.toolchain),
        )

    def _verified(
        self,
        python: SnapshotResult,
        web: SnapshotResult,
        *,
        network_used: bool,
        run_id: str | None = None,
    ) -> VerifiedEnvironment:
        combined = combined_environment_fingerprint(self.identity, python, web)
        evidence = build_environment_evidence(
            combined_fingerprint=combined,
            python=python,
            web=web,
            manifest_hashes=self.identity.manifest_hashes,
            python_lock_evidence=self.python_lock.evidence(),
            toolchain=asdict(self.toolchain),
            run_id=run_id,
            network_used=network_used,
            verified_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            cache_root=self.cache_root,
        )
        return VerifiedEnvironment(self.identity, python, web, combined, evidence)

    def ensure(self, *, offline: bool, run_id: str | None = None) -> VerifiedEnvironment:
        python_component, web_component = self._components()
        python = ensure_snapshot(self.cache_root, python_component, offline=offline)
        web = ensure_snapshot(self.cache_root, web_component, offline=offline)
        verified = self._verified(
            python,
            web,
            network_used=python.network_used or web.network_used,
            run_id=run_id,
        )
        link_worktree_environment(
            self.root,
            self.cache_root,
            python,
            web,
            combined_fingerprint=verified.combined_fingerprint,
        )
        return self.verify(
            network_used=verified.evidence["operational"]["bootstrapNetworkUsed"],
            run_id=run_id,
        )

    def verify(self, *, network_used: bool = False, run_id: str | None = None) -> VerifiedEnvironment:
        pointer_path = self.root / ".wolfy" / "environment.json"
        try:
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EnvironmentFailure("worktree_pointer_invalid", "worktree environment pointer is missing or invalid") from exc
        if pointer.get("schemaVersion") != POINTER_SCHEMA or not isinstance(pointer.get("components"), dict):
            raise EnvironmentFailure("worktree_pointer_invalid", "worktree environment pointer is invalid")
        python_component, web_component = self._components()
        results: list[SnapshotResult] = []
        for name, destination, component in (
            ("python", self.root / ".venv", python_component),
            ("web", self.root / "apps" / "dsa-web" / "node_modules", web_component),
        ):
            details = pointer["components"].get(name)
            if not isinstance(details, dict) or details.get("inputFingerprint") != component.input_fingerprint:
                raise EnvironmentFailure("worktree_pointer_mismatch", f"{name} pointer input fingerprint does not match")
            try:
                resolved_target = destination.resolve(strict=True)
            except OSError as exc:
                raise EnvironmentFailure("worktree_dependency_link_broken", f"{name} dependency link is broken") from exc
            snapshot = resolved_target.parent if name == "web" else resolved_target
            if name == "web" and resolved_target.name != "node_modules":
                raise EnvironmentFailure("worktree_pointer_mismatch", "Web dependency link target is invalid")
            _cache_relative(self.cache_root, snapshot)
            manifest = verify_cached_snapshot(snapshot, component)
            if (
                details.get("snapshot") != _cache_relative(self.cache_root, snapshot)
                or details.get("installedFingerprint") != manifest.get("installedFingerprint")
            ):
                raise EnvironmentFailure(
                    "worktree_pointer_mismatch", f"{name} pointer snapshot identity does not match"
                )
            results.append(
                SnapshotResult(
                    name,
                    snapshot,
                    component.input_fingerprint,
                    str(manifest["installedFingerprint"]),
                    False,
                    True,
                )
            )
        verified = self._verified(results[0], results[1], network_used=network_used, run_id=run_id)
        if pointer.get("combinedFingerprint") != verified.combined_fingerprint:
            raise EnvironmentFailure("worktree_pointer_mismatch", "combined environment fingerprint does not match")
        return verified
