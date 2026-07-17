from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import time
import uuid
from pathlib import Path
from typing import Callable

from .errors import EnvironmentFailure


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SnapshotLock:
    """Atomic directory lock that only recovers confirmed local dead owners."""

    def __init__(
        self,
        path: Path,
        *,
        timeout: float = 120.0,
        stale_after: float = 1800.0,
        hostname: str | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        pid_alive: Callable[[int], bool] = _pid_alive,
    ) -> None:
        self.path = path
        self.timeout = timeout
        self.stale_after = stale_after
        self.hostname = hostname or socket.gethostname()
        self.host_id = hashlib.sha256(self.hostname.encode("utf-8", errors="surrogateescape")).hexdigest()
        self.clock = clock
        self.sleeper = sleeper
        self.pid_alive = pid_alive
        self.token = uuid.uuid4().hex
        self.acquired = False

    def _owner(self) -> dict[str, object] | None:
        try:
            payload = json.loads((self.path / "owner.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _recover_if_stale(self) -> bool:
        owner = self._owner()
        if owner is None:
            return False
        try:
            created = float(owner["createdEpoch"])
            pid = int(owner["pid"])
            host_id = str(owner["hostId"])
            token = str(owner["token"])
        except (KeyError, TypeError, ValueError):
            return False
        if host_id != self.host_id or self.clock() - created <= self.stale_after or self.pid_alive(pid):
            return False
        current = self._owner()
        if current is None or current.get("token") != token:
            return False
        displaced = self.path.with_name(f"{self.path.name}.stale-{uuid.uuid4().hex}")
        try:
            self.path.rename(displaced)
        except OSError:
            return False
        shutil.rmtree(displaced, ignore_errors=True)
        return True

    def acquire(self) -> None:
        deadline = self.clock() + self.timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self.path.mkdir()
            except FileExistsError:
                if self._recover_if_stale():
                    continue
                if self.clock() >= deadline:
                    raise EnvironmentFailure("lock_wait_timeout", "lock_wait_timeout")
                self.sleeper(min(0.05, max(0.0, deadline - self.clock())))
                continue
            owner = {
                "createdEpoch": self.clock(),
                "hostId": self.host_id,
                "pid": os.getpid(),
                "token": self.token,
            }
            (self.path / "owner.json").write_text(
                json.dumps(owner, sort_keys=True, separators=(",", ":")), encoding="utf-8"
            )
            self.acquired = True
            return

    def release(self) -> None:
        if not self.acquired:
            return
        owner = self._owner()
        if owner is not None and owner.get("token") == self.token:
            shutil.rmtree(self.path, ignore_errors=False)
        self.acquired = False

    def __enter__(self) -> "SnapshotLock":
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()
