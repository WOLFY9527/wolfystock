from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .components import _bootstrap_environment
from .errors import EnvironmentFailure, OfflineMaterialUnavailable
from .identity import ToolchainIdentity, file_hash, stable_hash


BROWSER_POLICY_VERSION = "wolfystock_managed_browser_v1"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, **kwargs)


def _platform_identity(toolchain: ToolchainIdentity) -> str:
    architecture = toolchain.architecture.lower()
    architecture = {"aarch64": "arm64", "amd64": "x86_64"}.get(
        architecture, architecture
    )
    return f"{toolchain.os_name.lower()}-{architecture}"


@dataclass(frozen=True)
class BrowserContract:
    family: str
    revision: str
    browser_version: str
    playwright_version: str
    platform: str
    input_fingerprint: str


def _load_json(path: Path, code: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentFailure(code, "reviewed Playwright browser metadata is invalid") from exc
    if not isinstance(payload, dict):
        raise EnvironmentFailure(code, "reviewed Playwright browser metadata is invalid")
    return payload


def load_browser_contract(
    web_snapshot: Path,
    web_input_fingerprint: str,
    toolchain: ToolchainIdentity,
) -> BrowserContract:
    core = web_snapshot / "node_modules" / "playwright-core"
    package = _load_json(core / "package.json", "browser_dependency_graph_invalid")
    metadata = _load_json(core / "browsers.json", "browser_dependency_graph_invalid")
    playwright_version = package.get("version")
    browsers = metadata.get("browsers")
    if not isinstance(playwright_version, str) or not isinstance(browsers, list):
        raise EnvironmentFailure(
            "browser_dependency_graph_invalid", "reviewed Playwright browser metadata is invalid"
        )
    chromium = next(
        (
            item
            for item in browsers
            if isinstance(item, dict)
            and item.get("name") == "chromium"
            and item.get("installByDefault") is True
        ),
        None,
    )
    if not isinstance(chromium, dict):
        raise EnvironmentFailure(
            "browser_dependency_graph_invalid", "reviewed Chromium metadata is missing"
        )
    revision = chromium.get("revision")
    browser_version = chromium.get("browserVersion")
    if (
        not isinstance(revision, str)
        or re.fullmatch(r"[1-9][0-9]*", revision) is None
        or not isinstance(browser_version, str)
        or not browser_version
    ):
        raise EnvironmentFailure(
            "browser_dependency_graph_invalid", "reviewed Chromium identity is invalid"
        )
    platform_identity = _platform_identity(toolchain)
    payload = {
        "policyVersion": BROWSER_POLICY_VERSION,
        "family": "chromium",
        "revision": revision,
        "browserVersion": browser_version,
        "playwrightVersion": playwright_version,
        "platform": platform_identity,
        "webInputFingerprint": web_input_fingerprint,
    }
    return BrowserContract(
        family="chromium",
        revision=revision,
        browser_version=browser_version,
        playwright_version=playwright_version,
        platform=platform_identity,
        input_fingerprint=stable_hash(payload),
    )


class BrowserComponent:
    name = "browser"
    immutable = True

    def __init__(
        self,
        web_snapshot: Path,
        web_input_fingerprint: str,
        toolchain: ToolchainIdentity,
        *,
        node_executable: Path | None = None,
        command_runner: CommandRunner = _run,
    ) -> None:
        self.web_snapshot = web_snapshot
        self.contract = load_browser_contract(
            web_snapshot, web_input_fingerprint, toolchain
        )
        self.input_fingerprint = self.contract.input_fingerprint
        resolved_node = node_executable
        if resolved_node is None:
            resolved_node_value = shutil.which("node")
            if resolved_node_value is None:
                raise EnvironmentFailure("managed_node_missing", "Node executable is unavailable")
            resolved_node = Path(resolved_node_value)
        if not resolved_node.is_file():
            raise EnvironmentFailure("managed_node_missing", "Node executable is unavailable")
        self.node_executable = resolved_node
        self.command_runner = command_runner

    @property
    def playwright_cli(self) -> Path:
        path = self.web_snapshot / "node_modules" / "playwright-core" / "cli.js"
        if not path.is_file():
            raise EnvironmentFailure(
                "browser_dependency_graph_invalid", "reviewed Playwright CLI is missing"
            )
        return path

    @property
    def playwright_module(self) -> Path:
        path = self.web_snapshot / "node_modules" / "playwright"
        if not path.is_dir():
            raise EnvironmentFailure(
                "browser_dependency_graph_invalid", "reviewed Playwright module is missing"
            )
        return path

    def build(self, destination: Path, *, offline: bool) -> None:
        if offline:
            raise OfflineMaterialUnavailable(
                "offline_browser_snapshot_missing",
                "managed Chromium snapshot is missing; run online ./wolfy bootstrap --ensure",
            )
        destination.mkdir(parents=True, exist_ok=True)
        with _bootstrap_environment(offline=False) as environment:
            environment.update(
                {
                    "PLAYWRIGHT_BROWSERS_PATH": str(destination),
                    "PLAYWRIGHT_SKIP_BROWSER_GC": "1",
                }
            )
            result = self.command_runner(
                [
                    str(self.node_executable),
                    str(self.playwright_cli),
                    "install",
                    self.contract.family,
                ],
                cwd=self.web_snapshot,
                env=environment,
            )
        if result.returncode != 0:
            raise EnvironmentFailure(
                "browser_download_failed", "reviewed Chromium artifact download failed"
            )

    def _launch_probe(self, snapshot: Path) -> dict[str, object]:
        source = (
            "const {chromium}=require(process.argv[1]);"
            "(async()=>{const executablePath=chromium.executablePath();"
            "const browser=await chromium.launch({headless:true,executablePath});"
            "const browserVersion=browser.version();await browser.close();"
            "console.log(JSON.stringify({browserVersion,executablePath,launchVerified:true}));"
            "})().catch(error=>{console.error(error&&error.message||String(error));process.exit(1)});"
        )
        with tempfile.TemporaryDirectory(prefix="wolfystock-browser-probe-") as temporary:
            environment = {
                key: os.environ[key]
                for key in ("COMSPEC", "LANG", "LC_ALL", "PATHEXT", "SYSTEMROOT")
                if os.environ.get(key)
            }
            environment.update(
                {
                    "HOME": temporary,
                    "NO_PROXY": "*",
                    "PATH": os.pathsep.join(
                        (str(self.node_executable.parent), "/usr/bin", "/bin")
                    ),
                    "PLAYWRIGHT_BROWSERS_PATH": str(snapshot),
                    "TEMP": temporary,
                    "TMP": temporary,
                    "TMPDIR": temporary,
                    "no_proxy": "*",
                }
            )
            result = self.command_runner(
                [
                    str(self.node_executable),
                    "-e",
                    source,
                    str(self.playwright_module),
                ],
                cwd=self.web_snapshot,
                env=environment,
            )
        try:
            payload = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise EnvironmentFailure(
                "browser_launch_failed", "managed Chromium launch probe failed"
            ) from exc
        if result.returncode != 0 or not isinstance(payload, dict):
            raise EnvironmentFailure(
                "browser_launch_failed", "managed Chromium launch probe failed"
            )
        return payload

    def inspect(self, snapshot: Path) -> dict[str, object]:
        expected_directory = f"{self.contract.family}-{self.contract.revision}"
        wrong_revisions = sorted(
            path.name
            for path in snapshot.glob(f"{self.contract.family}-*")
            if path.is_dir() and path.name != expected_directory
        )
        if wrong_revisions:
            raise EnvironmentFailure(
                "browser_revision_mismatch", "managed Chromium revision does not match"
            )
        probe = self._launch_probe(snapshot)
        executable_value = probe.get("executablePath")
        if not isinstance(executable_value, str):
            raise EnvironmentFailure(
                "browser_executable_missing", "managed Chromium executable is missing"
            )
        try:
            executable = Path(executable_value).resolve(strict=True)
            relative = executable.relative_to(snapshot.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise EnvironmentFailure(
                "browser_executable_outside_cache",
                "managed Chromium executable is outside its snapshot",
            ) from exc
        if relative.parts[:1] != (expected_directory,):
            raise EnvironmentFailure(
                "browser_revision_mismatch", "managed Chromium revision does not match"
            )
        if (
            not executable.is_file()
            or probe.get("launchVerified") is not True
            or probe.get("browserVersion") != self.contract.browser_version
        ):
            raise EnvironmentFailure(
                "browser_launch_failed", "managed Chromium launch identity does not match"
            )
        return {
            "browserVersion": self.contract.browser_version,
            "executable": relative.as_posix(),
            "executableSha256": file_hash(executable),
            "family": self.contract.family,
            "launchVerified": True,
            "platform": self.contract.platform,
            "playwrightVersion": self.contract.playwright_version,
            "revision": self.contract.revision,
        }

    def verify(self, snapshot: Path, manifest: dict[str, object]) -> None:
        if self.inspect(snapshot) != manifest.get("installed"):
            raise EnvironmentFailure(
                "browser_installed_identity_mismatch",
                "managed Chromium installed identity does not match",
            )

    def prepare_promotion(self, temporary: Path, final: Path) -> None:
        return None


def browser_executable_path(snapshot: Path) -> Path:
    try:
        manifest = json.loads((snapshot / "provenance.json").read_text(encoding="utf-8"))
        executable = manifest["installed"]["executable"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise EnvironmentFailure(
            "browser_executable_missing", "managed Chromium executable identity is missing"
        ) from exc
    candidate = snapshot / str(executable)
    try:
        candidate.resolve(strict=True).relative_to(snapshot.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise EnvironmentFailure(
            "browser_executable_outside_cache",
            "managed Chromium executable is outside its snapshot",
        ) from exc
    return candidate
