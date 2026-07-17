from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ENVIRONMENT_SCHEMA_VERSION = "wolfystock_environment_v1"
BOOTSTRAP_IMPLEMENTATION_VERSION = "wolfystock_bootstrap_v5"
PYTHON_INPUTS = ("requirements.txt", "requirements-dev.txt")
WEB_INPUTS = ("apps/dsa-web/package.json", "apps/dsa-web/package-lock.json")


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ToolchainIdentity:
    os_name: str
    architecture: str
    python_implementation: str
    python_version: str
    node_version: str
    npm_version: str
    install_mode: str

    def as_payload(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentIdentity:
    python_input_fingerprint: str
    web_input_fingerprint: str
    combined_input_fingerprint: str
    manifest_hashes: dict[str, str]
    toolchain: ToolchainIdentity


def npm_command(*arguments: str) -> list[str]:
    if os.name == "nt":
        return ["cmd.exe", "/d", "/c", "npm.cmd", *arguments]
    return ["npm", *arguments]


def _tool_environment(config_root: Path) -> dict[str, str]:
    allowed = ("COMSPEC", "LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMROOT")
    environment = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    user_config = config_root / "user.npmrc"
    global_config = config_root / "global.npmrc"
    user_config.write_text("", encoding="utf-8")
    global_config.write_text("", encoding="utf-8")
    environment["npm_config_userconfig"] = str(user_config)
    environment["npm_config_globalconfig"] = str(global_config)
    return environment


def _tool_version(command: list[str], label: str) -> str:
    try:
        with tempfile.TemporaryDirectory(prefix="wolfystock-tool-config-") as temporary:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
                env=_tool_environment(Path(temporary)),
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"unable to determine {label} version") from exc
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError(f"unable to determine {label} version")
    return result.stdout.strip().lstrip("v")


def detect_toolchain() -> ToolchainIdentity:
    return ToolchainIdentity(
        os_name=platform.system(),
        architecture=platform.machine(),
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        node_version=_tool_version(["node", "--version"], "Node"),
        npm_version=_tool_version(npm_command("--version"), "npm"),
        install_mode="pip-requirements+npm-ci",
    )


def validate_bootstrap_interpreter() -> None:
    if platform.python_implementation() != "CPython" or sys.version_info[:2] != (3, 11):
        raise ValueError(
            "bootstrap interpreter must be CPython 3.11; set WOLFYSTOCK_BOOTSTRAP_PYTHON to an exact CPython 3.11 executable"
        )


def calculate_environment_identity(root: Path, toolchain: ToolchainIdentity) -> EnvironmentIdentity:
    root = root.resolve(strict=True)
    manifest_hashes: dict[str, str] = {}
    for relative in (*PYTHON_INPUTS, *WEB_INPUTS):
        path = root / relative
        if not path.is_file():
            raise ValueError(f"authoritative dependency input is missing: {relative}")
        manifest_hashes[relative] = file_hash(path)

    common = {
        "schemaVersion": ENVIRONMENT_SCHEMA_VERSION,
        "bootstrapImplementationVersion": BOOTSTRAP_IMPLEMENTATION_VERSION,
        "os": toolchain.os_name,
        "architecture": toolchain.architecture,
        "installMode": toolchain.install_mode,
    }
    python_payload = {
        **common,
        "pythonImplementation": toolchain.python_implementation,
        "pythonVersion": toolchain.python_version,
        "manifests": {name: manifest_hashes[name] for name in PYTHON_INPUTS},
    }
    web_payload = {
        **common,
        "nodeVersion": toolchain.node_version,
        "npmVersion": toolchain.npm_version,
        "manifests": {name: manifest_hashes[name] for name in WEB_INPUTS},
    }
    python_fingerprint = stable_hash(python_payload)
    web_fingerprint = stable_hash(web_payload)
    combined = stable_hash(
        {
            **common,
            "pythonInputFingerprint": python_fingerprint,
            "webInputFingerprint": web_fingerprint,
        }
    )
    return EnvironmentIdentity(
        python_input_fingerprint=python_fingerprint,
        web_input_fingerprint=web_fingerprint,
        combined_input_fingerprint=combined,
        manifest_hashes=manifest_hashes,
        toolchain=toolchain,
    )
