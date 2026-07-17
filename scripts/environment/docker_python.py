from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Sequence

from .components import CommandRunner, LockedPythonInstaller, _run
from .errors import EnvironmentFailure
from .python_lock import PythonLockContract, load_python_lock


def select_docker_python_lock(
    root: Path,
    *,
    target_arch: str,
    python_version: str,
) -> PythonLockContract:
    return load_python_lock(
        root,
        os_name="Linux",
        architecture=target_arch,
        python_version=python_version,
        python_implementation="CPython",
        profile="runtime",
    )


def install_docker_python_environment(
    root: Path,
    *,
    target_arch: str,
    python_version: str,
    destination: Path,
    artifact_cache_root: Path,
    command_runner: CommandRunner = _run,
) -> dict[str, object]:
    contract = select_docker_python_lock(
        root,
        target_arch=target_arch,
        python_version=python_version,
    )
    installer = LockedPythonInstaller(
        root,
        lock_contract=contract,
        artifact_cache_root=artifact_cache_root,
        command_runner=command_runner,
    )
    installer.build(destination, offline=False)
    return contract.evidence()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install a reviewed Python runtime lock for a Docker target"
    )
    parser.add_argument("--target-arch", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--artifact-cache", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evidence = install_docker_python_environment(
            Path.cwd(),
            target_arch=args.target_arch,
            python_version=platform.python_version(),
            destination=args.destination,
            artifact_cache_root=args.artifact_cache,
        )
    except EnvironmentFailure as exc:
        print(json.dumps({"status": "error", "reasonCode": exc.code}), file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "pythonLock": evidence}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
