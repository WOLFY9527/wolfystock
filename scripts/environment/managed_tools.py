from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .errors import EnvironmentFailure
from .identity import ToolchainIdentity, file_hash, stable_hash


MANAGED_RG_POLICY_VERSION = "wolfystock_managed_rg_v1"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
SourceResolver = Callable[[str], str | None]


def _run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, **kwargs)


def _platform_identity(toolchain: ToolchainIdentity) -> str:
    architecture = toolchain.architecture.lower()
    architecture = {"aarch64": "arm64", "amd64": "x86_64"}.get(
        architecture, architecture
    )
    return f"{toolchain.os_name.lower()}-{architecture}"


class ManagedRgComponent:
    name = "tool-rg"
    immutable = True

    def __init__(
        self,
        toolchain: ToolchainIdentity,
        *,
        source_resolver: SourceResolver = shutil.which,
        command_runner: CommandRunner = _run,
    ) -> None:
        self.platform = _platform_identity(toolchain)
        self.input_fingerprint = stable_hash(
            {
                "policyVersion": MANAGED_RG_POLICY_VERSION,
                "tool": "rg",
                "platform": self.platform,
            }
        )
        self.source_resolver = source_resolver
        self.command_runner = command_runner

    @property
    def executable_name(self) -> str:
        return "rg.exe" if os.name == "nt" else "rg"

    def build(self, destination: Path, *, offline: bool) -> None:
        source = self.source_resolver("rg")
        if not source:
            raise EnvironmentFailure(
                "managed_rg_source_missing",
                "reviewed rg source is unavailable for managed provisioning",
            )
        source_path = Path(source)
        if not source_path.is_file():
            raise EnvironmentFailure(
                "managed_rg_source_missing",
                "reviewed rg source is unavailable for managed provisioning",
            )
        destination.mkdir(parents=True, exist_ok=True)
        executable = destination / self.executable_name
        shutil.copy2(source_path, executable)
        if os.name != "nt":
            executable.chmod(executable.stat().st_mode | 0o500)

    def inspect(self, snapshot: Path) -> dict[str, object]:
        executable = snapshot / self.executable_name
        if not executable.is_file():
            raise EnvironmentFailure(
                "managed_rg_executable_missing", "managed rg executable is missing"
            )
        result = self.command_runner(
            [str(executable), "--version"],
            env={"PATH": os.pathsep.join((str(snapshot), "/usr/bin", "/bin"))},
        )
        first_line = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
        match = re.fullmatch(r"ripgrep ([0-9]+\.[0-9]+\.[0-9]+)", first_line.strip())
        if result.returncode != 0 or match is None:
            raise EnvironmentFailure(
                "managed_rg_probe_failed", "managed rg identity probe failed"
            )
        return {
            "executable": self.executable_name,
            "executableSha256": file_hash(executable),
            "platform": self.platform,
            "version": match.group(1),
        }

    def verify(self, snapshot: Path, manifest: dict[str, object]) -> None:
        if self.inspect(snapshot) != manifest.get("installed"):
            raise EnvironmentFailure(
                "managed_rg_identity_mismatch", "managed rg installed identity does not match"
            )

    def prepare_promotion(self, temporary: Path, final: Path) -> None:
        return None
