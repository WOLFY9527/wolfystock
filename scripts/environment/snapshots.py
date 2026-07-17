from __future__ import annotations

import json
import os
import shutil
import stat
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .errors import EnvironmentFailure, OfflineMaterialUnavailable
from .identity import stable_hash
from .locking import SnapshotLock


SNAPSHOT_SCHEMA = "wolfystock_dependency_snapshot_v1"


class SnapshotComponent(Protocol):
    name: str
    input_fingerprint: str

    def build(self, destination: Path, *, offline: bool) -> None:
        ...

    def inspect(self, snapshot: Path) -> dict[str, object]:
        ...

    def verify(self, snapshot: Path, manifest: dict[str, object]) -> None:
        ...

    def prepare_promotion(self, temporary: Path, final: Path) -> None:
        ...


@dataclass(frozen=True)
class SnapshotResult:
    component: str
    path: Path
    input_fingerprint: str
    installed_fingerprint: str
    network_used: bool
    reused: bool


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _quarantine(cache_root: Path, path: Path, label: str) -> Path:
    quarantine = cache_root / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    target = quarantine / f"{label}-{int(time.time())}-{uuid.uuid4().hex}"
    path.rename(target)
    retained = sorted(quarantine.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
    for expired in retained[8:]:
        if expired.is_dir() and not expired.is_symlink():
            shutil.rmtree(expired, onerror=_remove_readonly)
        else:
            expired.unlink(missing_ok=True)
    return target


def _remove_readonly(function: Any, path: str, _error: object) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    function(path)


def verify_cached_snapshot(snapshot: Path, component: SnapshotComponent) -> dict[str, Any]:
    manifest_path = snapshot / "provenance.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentFailure("snapshot_provenance_invalid", "snapshot provenance manifest is invalid") from exc
    if not isinstance(manifest, dict):
        raise EnvironmentFailure("snapshot_provenance_invalid", "snapshot provenance manifest is invalid")
    if (
        manifest.get("schemaVersion") != SNAPSHOT_SCHEMA
        or manifest.get("component") != component.name
        or manifest.get("inputFingerprint") != component.input_fingerprint
        or not isinstance(manifest.get("installed"), dict)
    ):
        raise EnvironmentFailure("snapshot_provenance_mismatch", "snapshot provenance manifest does not match")
    installed_fingerprint = stable_hash(manifest["installed"])
    if manifest.get("installedFingerprint") != installed_fingerprint or snapshot.name != installed_fingerprint:
        raise EnvironmentFailure("snapshot_provenance_mismatch", "snapshot installed fingerprint does not match")
    component.verify(snapshot, manifest)
    if bool(getattr(component, "immutable", False)) and os.name != "nt":
        for item in (snapshot, *snapshot.rglob("*")):
            if item.is_symlink():
                continue
            try:
                writable = item.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            except OSError as exc:
                raise EnvironmentFailure("snapshot_immutability_invalid", "snapshot immutability check failed") from exc
            if writable:
                raise EnvironmentFailure("snapshot_immutability_invalid", "dependency snapshot is writable")
    return manifest


def sweep_interrupted_builds(
    cache_root: Path,
    component_name: str,
    input_fingerprint: str,
    *,
    older_than_seconds: float = 1800.0,
) -> int:
    input_root = cache_root / "snapshots" / component_name / input_fingerprint
    if not input_root.is_dir():
        return 0
    now = time.time()
    swept = 0
    for path in input_root.glob(".build-*"):
        try:
            old = now - path.stat().st_mtime > older_than_seconds
        except OSError as exc:
            raise EnvironmentFailure("snapshot_sealing_failed", "unable to seal dependency snapshot") from exc
        if old:
            try:
                _quarantine(cache_root, path, f"interrupted-{component_name}")
            except FileNotFoundError:
                continue
            swept += 1
    return swept


def _valid_existing(cache_root: Path, input_root: Path, component: SnapshotComponent) -> SnapshotResult | None:
    for candidate in sorted(input_root.iterdir() if input_root.is_dir() else ()):
        if not candidate.is_dir() or candidate.name.startswith(".") or len(candidate.name) != 64:
            continue
        try:
            manifest = verify_cached_snapshot(candidate, component)
        except EnvironmentFailure:
            _quarantine(cache_root, candidate, f"corrupt-{component.name}")
            continue
        return SnapshotResult(
            component=component.name,
            path=candidate,
            input_fingerprint=component.input_fingerprint,
            installed_fingerprint=str(manifest["installedFingerprint"]),
            network_used=False,
            reused=True,
        )
    return None


def _build_once(
    cache_root: Path,
    input_root: Path,
    component: SnapshotComponent,
    *,
    offline: bool,
) -> tuple[Path, dict[str, object]]:
    temporary = input_root / f".build-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        component.build(temporary, offline=offline)
        installed = component.inspect(temporary)
        installed_fingerprint = stable_hash(installed)
        manifest: dict[str, object] = {
            "schemaVersion": SNAPSHOT_SCHEMA,
            "component": component.name,
            "inputFingerprint": component.input_fingerprint,
            "installedFingerprint": installed_fingerprint,
            "installed": installed,
        }
        _write_json(temporary / "provenance.json", manifest)
        component.verify(temporary, manifest)
        return temporary, manifest
    except Exception:
        if temporary.exists():
            _quarantine(cache_root, temporary, f"failed-{component.name}")
        raise


def _seal_snapshot(path: Path) -> None:
    for item in sorted(path.rglob("*"), reverse=True):
        try:
            if item.is_symlink():
                continue
            mode = item.stat().st_mode
            if item.is_dir():
                item.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            else:
                item.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
        except OSError:
            continue
    try:
        path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    except OSError as exc:
        raise EnvironmentFailure("snapshot_sealing_failed", "unable to seal dependency snapshot") from exc


def ensure_snapshot(
    cache_root: Path,
    component: SnapshotComponent,
    *,
    offline: bool,
    lock_timeout: float = 120.0,
) -> SnapshotResult:
    input_root = cache_root / "snapshots" / component.name / component.input_fingerprint
    input_root.mkdir(parents=True, exist_ok=True)
    sweep_interrupted_builds(cache_root, component.name, component.input_fingerprint)
    lock = SnapshotLock(
        cache_root / "locks" / f"{component.name}-{component.input_fingerprint}.lock",
        timeout=lock_timeout,
    )
    with lock:
        existing = _valid_existing(cache_root, input_root, component)
        if existing:
            return existing
        network_used = False
        if offline:
            temporary, manifest = _build_once(cache_root, input_root, component, offline=True)
        else:
            try:
                temporary, manifest = _build_once(cache_root, input_root, component, offline=True)
            except OfflineMaterialUnavailable:
                temporary, manifest = _build_once(cache_root, input_root, component, offline=False)
                network_used = True
        installed_fingerprint = str(manifest["installedFingerprint"])
        final = input_root / installed_fingerprint
        try:
            component.prepare_promotion(temporary, final)
            component.verify(temporary, manifest)
            if bool(getattr(component, "immutable", False)):
                _seal_snapshot(temporary)
            if final.exists():
                _quarantine(cache_root, temporary, f"duplicate-{component.name}")
            else:
                temporary.rename(final)
            verify_cached_snapshot(final, component)
        except Exception:
            if temporary.exists():
                _quarantine(cache_root, temporary, f"failed-promotion-{component.name}")
            if final.exists():
                _quarantine(cache_root, final, f"failed-final-{component.name}")
            raise
        return SnapshotResult(
            component=component.name,
            path=final,
            input_fingerprint=component.input_fingerprint,
            installed_fingerprint=installed_fingerprint,
            network_used=network_used,
            reused=False,
        )
