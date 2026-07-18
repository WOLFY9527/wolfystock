from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.environment.errors import EnvironmentFailure
from tests.scripts.test_wolfy_python_lock import write_lock_repository


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "docker" / "Dockerfile"


def test_dockerfile_installs_dependencies_through_reviewed_lock_helper() -> None:
    content = DOCKERFILE.read_text(encoding="utf-8")

    assert "pip install --no-cache-dir -r requirements.txt" not in content
    assert "FROM runtime-base AS python-dependencies" in content
    assert "ARG TARGETARCH" in content
    for lock_input in (
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-lock.json",
        "requirements-python311-runtime.lock",
        "requirements-python311-dev.lock",
        "requirements-python312-runtime.lock",
        "requirements-python312-dev.lock",
    ):
        assert lock_input in content
    assert "COPY scripts/environment/ ./scripts/environment/" in content
    assert "python -m scripts.environment.docker_python" in content
    assert "--target-arch \"${TARGETARCH}\"" in content
    assert "--destination /opt/wolfystock-python" in content
    assert "COPY --from=python-dependencies /opt/wolfystock-python /opt/wolfystock-python" in content
    assert "ENV PATH=/opt/wolfystock-python/bin:$PATH" in content
    assert content.index("python -m scripts.environment.docker_python") < content.index("COPY *.py ./")
    assert 'CMD ["python", "main.py", "--schedule"]' in content


@pytest.mark.parametrize(
    ("target_arch", "expected_projection", "expected_hash"),
    [
        (
            "amd64",
            "linux-x86_64-cpython311-runtime",
            "3cbe8e7f8865cbe0cbf138baeb17968111335fe08376484fc845e7d030fdadf7",
        ),
        (
            "x86_64",
            "linux-x86_64-cpython311-runtime",
            "3cbe8e7f8865cbe0cbf138baeb17968111335fe08376484fc845e7d030fdadf7",
        ),
        (
            "arm64",
            "linux-aarch64-cpython311-runtime",
            "7f77a9b32e210309cb3f26710f295d04cb9a21a72228d7e96a44ef1458885cff",
        ),
        (
            "aarch64",
            "linux-aarch64-cpython311-runtime",
            "7f77a9b32e210309cb3f26710f295d04cb9a21a72228d7e96a44ef1458885cff",
        ),
    ],
)
def test_docker_target_arch_selects_reviewed_runtime_projection(
    target_arch: str,
    expected_projection: str,
    expected_hash: str,
) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")

    contract = docker_python.select_docker_python_lock(
        ROOT,
        target_arch=target_arch,
        python_version="3.11.15",
    )

    assert contract.profile == "runtime"
    assert contract.projection == expected_projection
    assert contract.projection_hash == expected_hash


@pytest.mark.parametrize("target_arch", ["", "ppc64le"])
def test_docker_selection_rejects_unsupported_arch_before_install(
    target_arch: str,
) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")

    with pytest.raises(EnvironmentFailure) as raised:
        docker_python.select_docker_python_lock(
            ROOT,
            target_arch=target_arch,
            python_version="3.11.15",
        )

    assert raised.value.code == "python_lock_target_unsupported"


def test_docker_selection_rejects_linux_cpython312_and_development_projection() -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")

    with pytest.raises(EnvironmentFailure) as raised:
        docker_python.select_docker_python_lock(
            ROOT,
            target_arch="arm64",
            python_version="3.12.11",
        )

    assert raised.value.code == "python_lock_target_unsupported"
    source = Path(docker_python.__file__).read_text(encoding="utf-8")
    assert 'profile="runtime"' in source
    assert 'profile="development"' not in source


@pytest.mark.parametrize(
    ("target_arch", "distribution_count", "artifact_count", "source_build_count"),
    [("amd64", 141, 156, 7), ("arm64", 141, 156, 8)],
)
def test_docker_runtime_projection_has_reviewed_distribution_and_artifact_identity(
    target_arch: str,
    distribution_count: int,
    artifact_count: int,
    source_build_count: int,
) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")

    contract = docker_python.select_docker_python_lock(
        ROOT,
        target_arch=target_arch,
        python_version="3.11.15",
    )

    assert len(contract.distributions) == distribution_count
    assert contract.hash_count == artifact_count
    assert contract.source_build_count == source_build_count
    assert contract.distributions["litellm"] == frozenset({"1.91.3"})
    assert contract.distributions["pyarrow"] == frozenset({"25.0.0"})
    assert all(artifact.artifact_type == "wheel" for artifact in contract.artifacts["pyarrow"])
    assert contract.artifact_hashes["pyarrow"]
    assert set(contract.artifacts) == set(contract.distributions)
    assert all(contract.artifacts[name] for name in contract.distributions)
    assert all(contract.artifact_hashes[name] for name in contract.distributions)


def test_docker_lock_input_drift_fails_before_install(tmp_path: Path) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")
    write_lock_repository(tmp_path)
    (tmp_path / "requirements.txt").write_text("demo>=2\n", encoding="utf-8")

    with pytest.raises(EnvironmentFailure) as raised:
        docker_python.install_docker_python_environment(
            tmp_path,
            target_arch="arm64",
            python_version="3.11.15",
            destination=tmp_path / "python",
            artifact_cache_root=tmp_path / "artifacts",
            command_runner=lambda *_args, **_kwargs: pytest.fail(
                "pip ran before lock drift was rejected"
            ),
        )

    assert raised.value.code == "python_lock_input_drift"


def test_docker_helper_delegates_target_and_install_authority() -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")
    source = Path(docker_python.__file__).read_text(encoding="utf-8")

    assert "load_python_lock" in source
    assert "LockedPythonInstaller" in source
    assert "SUPPORTED_TARGETS" not in source
    assert "targetProjections" not in source
    assert "uv" not in source


def test_docker_install_uses_shared_hashed_runtime_installer_without_lock_mutation(
    tmp_path: Path,
) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")
    destination = tmp_path / "python"
    commands: list[list[str]] = []
    backend_material = ""
    lock_paths = sorted(ROOT.glob("requirements*.lock"))
    before = {path.name: path.read_bytes() for path in lock_paths}

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal backend_material
        commands.append(command)
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            (destination / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
        if "install" in command and "-r" in command:
            requirements = Path(command[command.index("-r") + 1])
            if requirements.name.endswith(".requirements.txt"):
                backend_material = requirements.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    evidence = docker_python.install_docker_python_environment(
        ROOT,
        target_arch="arm64",
        python_version="3.11.15",
        destination=destination,
        artifact_cache_root=tmp_path / "artifacts",
        command_runner=runner,
    )

    pip_commands = [
        command
        for command in commands
        if "-m" in command and command[command.index("-m") + 1] == "pip"
    ]
    download = next(command for command in pip_commands if "download" in command)
    installs = [command for command in pip_commands if "install" in command]
    runtime_install = next(
        command
        for command in installs
        if any(argument.endswith("requirements-python311-runtime.lock") for argument in command)
    )
    assert evidence["selectedProjection"] == "linux-aarch64-cpython311-runtime"
    assert evidence["selectedProfile"] == "runtime"
    assert "--no-deps" in download and "--require-hashes" in download
    assert all("--no-deps" in command and "--require-hashes" in command for command in installs)
    assert all("--no-build-isolation" in command for command in installs)
    assert "requirements-python311-runtime.lock" in " ".join(runtime_install)
    argument_names = {Path(argument).name for command in pip_commands for argument in command}
    assert "requirements.txt" not in argument_names
    assert "requirements-dev.txt" not in argument_names
    assert "requirements-python311-dev.lock" not in argument_names
    assert all("uv" not in command for command in pip_commands)
    assert "setuptools==82.0.1" in backend_material
    assert "--hash=sha256:" in backend_material
    assert "http://" not in backend_material and "https://" not in backend_material
    assert str(tmp_path) not in backend_material
    assert before == {path.name: path.read_bytes() for path in lock_paths}


def test_docker_download_failure_stops_before_install_without_fallback(
    tmp_path: Path,
) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")
    destination = tmp_path / "python"
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            return subprocess.CompletedProcess(command, 0, "", "")
        if "download" in command:
            return subprocess.CompletedProcess(command, 1, "", "artifact missing")
        return pytest.fail("install ran after locked artifact download failed")

    with pytest.raises(EnvironmentFailure) as raised:
        docker_python.install_docker_python_environment(
            ROOT,
            target_arch="arm64",
            python_version="3.11.15",
            destination=destination,
            artifact_cache_root=tmp_path / "artifacts",
            command_runner=runner,
        )

    assert raised.value.code == "python_locked_artifact_download_failed"
    assert all(Path(argument).name != "requirements.txt" for command in commands for argument in command)


def test_docker_missing_build_backend_fails_without_build_isolation_download(
    tmp_path: Path,
) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")
    destination = tmp_path / "python"
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            (destination / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
        if "install" in command and "-r" in command:
            requirements = Path(command[command.index("-r") + 1])
            if requirements.name.endswith(".requirements.txt"):
                return subprocess.CompletedProcess(command, 1, "", "backend missing")
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(EnvironmentFailure) as raised:
        docker_python.install_docker_python_environment(
            ROOT,
            target_arch="arm64",
            python_version="3.11.15",
            destination=destination,
            artifact_cache_root=tmp_path / "artifacts",
            command_runner=runner,
        )

    backend = next(command for command in commands if "install" in command)
    assert raised.value.code == "python_locked_build_backend_install_failed"
    assert "--no-deps" in backend
    assert "--require-hashes" in backend
    assert "--no-build-isolation" in backend
    assert not any(
        "requirements-python311-runtime.lock" in " ".join(command)
        for command in commands
        if "install" in command
    )


def test_docker_cli_rejects_unsupported_arch_before_install(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    docker_python = importlib.import_module("scripts.environment.docker_python")

    result = docker_python.main(
        [
            "--target-arch",
            "ppc64le",
            "--destination",
            str(tmp_path / "python"),
            "--artifact-cache",
            str(tmp_path / "artifacts"),
        ]
    )

    error = json.loads(capsys.readouterr().err)
    assert result == 1
    assert error == {"status": "error", "reasonCode": "python_lock_target_unsupported"}
