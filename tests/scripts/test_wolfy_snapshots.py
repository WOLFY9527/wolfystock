from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts.environment.errors import EnvironmentFailure, OfflineMaterialUnavailable
from scripts.environment.locking import SnapshotLock
from scripts.environment.snapshots import ensure_snapshot, sweep_interrupted_builds, verify_cached_snapshot


@dataclass
class FakeComponent:
    name: str = "python"
    input_fingerprint: str = "a" * 64
    build_count: int = 0
    fail: bool = False
    offline_available: bool = True
    network_builds: int = 0
    corrupt_on_promotion: bool = False
    build_started: threading.Event | None = None
    release_build: threading.Event | None = None

    def build(self, destination: Path, *, offline: bool) -> None:
        self.build_count += 1
        if self.build_started:
            self.build_started.set()
        if self.release_build:
            assert self.release_build.wait(timeout=5)
        if offline and not self.offline_available:
            raise OfflineMaterialUnavailable("offline_python_material_unavailable")
        if not offline:
            self.network_builds += 1
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "payload.txt").write_text("verified-content\n", encoding="utf-8")
        if self.fail:
            raise EnvironmentFailure("fixture_install_failed", "fixture install failed")

    def inspect(self, snapshot: Path) -> dict[str, object]:
        payload = snapshot / "payload.txt"
        if not payload.is_file():
            raise EnvironmentFailure("snapshot_payload_missing", "snapshot payload is missing")
        return {"payload": payload.read_text(encoding="utf-8")}

    def verify(self, snapshot: Path, manifest: dict[str, object]) -> None:
        if self.inspect(snapshot) != manifest.get("installed"):
            raise EnvironmentFailure("snapshot_payload_mismatch", "snapshot payload does not match")

    def prepare_promotion(self, temporary: Path, final: Path) -> None:
        if self.corrupt_on_promotion:
            (temporary / "payload.txt").write_text("corrupt-after-inspection\n", encoding="utf-8")


def test_corrupt_provenance_manifest_is_rejected_and_rebuilt(tmp_path: Path) -> None:
    component = FakeComponent()
    first = ensure_snapshot(tmp_path, component, offline=True)
    (first.path / "provenance.json").write_text("{broken", encoding="utf-8")

    second = ensure_snapshot(tmp_path, component, offline=True)

    assert component.build_count == 2
    assert second.path == first.path
    assert verify_cached_snapshot(second.path, component)["installedFingerprint"] == second.installed_fingerprint
    assert any((tmp_path / "quarantine").iterdir())


def test_failed_installation_never_creates_a_valid_final_snapshot(tmp_path: Path) -> None:
    component = FakeComponent(fail=True)

    with pytest.raises(EnvironmentFailure, match="fixture install failed"):
        ensure_snapshot(tmp_path, component, offline=True)

    final_root = tmp_path / "snapshots" / "python" / component.input_fingerprint
    assert not [path for path in final_root.glob("*") if not path.name.startswith(".build-")]


def test_failed_promotion_verification_never_exposes_final_snapshot(tmp_path: Path) -> None:
    component = FakeComponent(corrupt_on_promotion=True)

    with pytest.raises(EnvironmentFailure, match="snapshot payload does not match"):
        ensure_snapshot(tmp_path, component, offline=True)

    final_root = tmp_path / "snapshots" / "python" / component.input_fingerprint
    assert not [path for path in final_root.glob("*") if not path.name.startswith(".build-")]


@pytest.mark.skipif(os.name == "nt", reason="POSIX snapshot permissions")
def test_writable_cached_snapshot_is_not_accepted_as_immutable(tmp_path: Path) -> None:
    component = FakeComponent()
    component.immutable = True
    result = ensure_snapshot(tmp_path, component, offline=True)
    payload = result.path / "payload.txt"
    payload.chmod(0o600)

    with pytest.raises(EnvironmentFailure) as raised:
        verify_cached_snapshot(result.path, component)

    assert raised.value.code == "snapshot_immutability_invalid"


def test_interrupted_temporary_build_is_quarantined_and_ignored(tmp_path: Path) -> None:
    input_root = tmp_path / "snapshots" / "web" / ("b" * 64)
    interrupted = input_root / ".build-interrupted"
    interrupted.mkdir(parents=True)
    (interrupted / "partial").write_text("partial", encoding="utf-8")
    old = time.time() - 7200
    os.utime(interrupted, (old, old))

    swept = sweep_interrupted_builds(tmp_path, "web", "b" * 64, older_than_seconds=60)

    assert swept == 1
    assert not interrupted.exists()
    assert any((tmp_path / "quarantine").iterdir())


def test_two_concurrent_ensure_operations_converge_on_one_snapshot(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    component = FakeComponent(build_started=started, release_build=release)
    results = []
    errors = []

    def worker() -> None:
        try:
            results.append(ensure_snapshot(tmp_path, component, offline=True, lock_timeout=5))
        except Exception as exc:  # pragma: no cover - assertion reports unexpected thread errors
            errors.append(exc)

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    assert started.wait(timeout=2)
    second.start()
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not errors
    assert component.build_count == 1
    assert len(results) == 2
    assert results[0].path == results[1].path


def test_active_lock_is_not_stolen(tmp_path: Path) -> None:
    lock_path = tmp_path / "active.lock"
    first = SnapshotLock(lock_path, timeout=0.1, stale_after=0.0)
    first.acquire()
    try:
        with pytest.raises(EnvironmentFailure, match="lock_wait_timeout"):
            SnapshotLock(lock_path, timeout=0.05, stale_after=0.0).acquire()
        owner = json.loads((lock_path / "owner.json").read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert "hostname" not in owner
        assert len(owner["hostId"]) == 64
    finally:
        first.release()


def test_stale_dead_owner_lock_is_recovered(tmp_path: Path) -> None:
    lock_path = tmp_path / "stale.lock"
    lock_path.mkdir()
    contender = SnapshotLock(lock_path, hostname="fixture-host")
    (lock_path / "owner.json").write_text(
        json.dumps({"pid": 99999999, "hostId": contender.host_id, "token": "old", "createdEpoch": 1}),
        encoding="utf-8",
    )

    lock = SnapshotLock(
        lock_path,
        timeout=0.2,
        stale_after=1,
        hostname="fixture-host",
        clock=lambda: 1000.0,
        pid_alive=lambda _pid: False,
    )
    lock.acquire()
    try:
        owner = json.loads((lock_path / "owner.json").read_text(encoding="utf-8"))
        assert owner["token"] != "old"
    finally:
        lock.release()


def test_offline_ensure_never_uses_online_builder(tmp_path: Path) -> None:
    component = FakeComponent(offline_available=False)

    with pytest.raises(OfflineMaterialUnavailable, match="offline_python_material_unavailable"):
        ensure_snapshot(tmp_path, component, offline=True)

    assert component.network_builds == 0


def test_online_ensure_reports_network_use_only_after_offline_material_miss(tmp_path: Path) -> None:
    component = FakeComponent(offline_available=False)

    result = ensure_snapshot(tmp_path, component, offline=False)

    assert result.network_used is True
    assert component.network_builds == 1
    assert component.build_count == 2
