from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import tomllib
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Callable, Iterable

from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.specifiers import InvalidSpecifier, SpecifierSet
from pip._vendor.packaging.tags import (
    Tag,
    compatible_tags,
    cpython_tags,
    mac_platforms,
)
from pip._vendor.packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from pip._vendor.packaging.version import Version

from .errors import EnvironmentFailure


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ArtifactCandidate:
    filename: str
    sha256: str
    url: str = ""
    requires_python: str | None = None


@dataclass(frozen=True)
class LockedArtifact:
    filename: str
    sha256: str
    artifact_type: str


@dataclass(frozen=True)
class ProjectionValidation:
    artifacts: dict[str, tuple[LockedArtifact, ...]]
    build_requirements: dict[str, str]
    hash_count: int
    projection_hash: str
    source_build_count: int


ArtifactIndex = Callable[[str, str], Iterable[ArtifactCandidate]]
ArtifactReader = Callable[[ArtifactCandidate], bytes]


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def pypi_artifact_index(name: str, version: str) -> tuple[ArtifactCandidate, ...]:
    request = urllib.request.Request(
        f"https://pypi.org/pypi/{name}/{version}/json",
        headers={"Accept": "application/json", "User-Agent": "WolfyStock-lock-review"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (OSError, ValueError) as exc:
        raise EnvironmentFailure(
            "python_lock_artifact_index_unavailable",
            f"artifact index unavailable for {name}=={version}",
        ) from exc
    candidates: list[ArtifactCandidate] = []
    for item in payload.get("urls", []):
        digest = item.get("digests", {}).get("sha256")
        filename = item.get("filename")
        url = item.get("url")
        if (
            item.get("yanked")
            or item.get("packagetype") not in {"bdist_wheel", "sdist"}
            or not isinstance(filename, str)
            or not isinstance(digest, str)
            or not isinstance(url, str)
        ):
            continue
        requires_python = item.get("requires_python")
        if requires_python is not None and not isinstance(requires_python, str):
            continue
        candidates.append(ArtifactCandidate(filename, digest, url, requires_python))
    return tuple(sorted(candidates, key=lambda candidate: candidate.filename))


def read_artifact(candidate: ArtifactCandidate) -> bytes:
    if not candidate.url.startswith("https://files.pythonhosted.org/"):
        raise EnvironmentFailure(
            "python_lock_artifact_source_invalid", "artifact source is not reviewed PyPI storage"
        )
    request = urllib.request.Request(
        candidate.url, headers={"User-Agent": "WolfyStock-lock-review"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
    except OSError as exc:
        raise EnvironmentFailure(
            "python_lock_artifact_source_unavailable", "source artifact is unavailable"
        ) from exc
    if hashlib.sha256(content).hexdigest() != candidate.sha256:
        raise EnvironmentFailure(
            "python_lock_artifact_hash_mismatch", "source artifact hash does not match index"
        )
    return content


def _linux_platforms(platform_name: str, architecture: str) -> list[str]:
    match = re.fullmatch(r"manylinux_2_(\d+)_(x86_64|aarch64)", platform_name)
    if match is None or match.group(2) != architecture:
        raise EnvironmentFailure(
            "python_lock_target_invalid", "Linux artifact platform is invalid"
        )
    maximum = int(match.group(1))
    minimum = 5 if architecture == "x86_64" else 17
    platforms = [
        f"manylinux_2_{minor}_{architecture}"
        for minor in range(maximum, minimum - 1, -1)
    ]
    if maximum >= 17:
        platforms.append(f"manylinux2014_{architecture}")
    if architecture == "x86_64" and maximum >= 12:
        platforms.append("manylinux2010_x86_64")
    if architecture == "x86_64" and maximum >= 5:
        platforms.append("manylinux1_x86_64")
    platforms.append(f"linux_{architecture}")
    return platforms


def supported_tags(target: dict[str, str]) -> frozenset[Tag]:
    version = tuple(int(part) for part in target["pythonVersion"].split("."))
    interpreter = "cp" + target["pythonVersion"].replace(".", "")
    if target["implementation"] != "CPython" or target["abi"] != interpreter:
        raise EnvironmentFailure(
            "python_lock_target_invalid", "Python implementation or ABI is invalid"
        )
    if target["os"] == "Linux":
        platforms = _linux_platforms(target["platform"], target["architecture"])
    elif target["os"] == "Darwin":
        match = re.fullmatch(r"macosx_(\d+)_(\d+)_(arm64|x86_64)", target["platform"])
        if match is None or match.group(3) != target["architecture"]:
            raise EnvironmentFailure(
                "python_lock_target_invalid", "macOS artifact platform is invalid"
            )
        platforms = list(
            mac_platforms((int(match.group(1)), int(match.group(2))), target["architecture"])
        )
    elif target["os"] == "Windows" and target["platform"] == "win_amd64":
        platforms = ["win_amd64"]
    else:
        raise EnvironmentFailure(
            "python_lock_target_invalid", "artifact platform is unsupported"
        )
    tags = set(cpython_tags(version, abis=[target["abi"]], platforms=platforms))
    tags.update(compatible_tags(version, interpreter=interpreter, platforms=platforms))
    return frozenset(tags)


def wheel_is_compatible(filename: str, target: dict[str, str]) -> bool:
    try:
        _, _, _, wheel_tags = parse_wheel_filename(filename)
    except ValueError:
        return False
    return bool(wheel_tags & supported_tags(target))


def _artifact_supports_python(
    candidate: ArtifactCandidate, target: dict[str, str]
) -> bool:
    if candidate.requires_python is None:
        return True
    try:
        specifier = SpecifierSet(candidate.requires_python)
    except InvalidSpecifier as exc:
        raise EnvironmentFailure(
            "python_lock_artifact_invalid", "artifact Requires-Python is invalid"
        ) from exc
    return specifier.contains(Version(target["pythonVersion"] + ".0"), prereleases=True)


def _validate_filename(filename: str) -> None:
    if PurePosixPath(filename).name != filename or "\\" in filename:
        raise EnvironmentFailure(
            "python_lock_artifact_invalid", "artifact filename is invalid"
        )


def _artifact_identity(filename: str) -> tuple[str, str, str]:
    _validate_filename(filename)
    if filename.endswith(".whl"):
        try:
            name, version, _, _ = parse_wheel_filename(filename)
        except ValueError as exc:
            raise EnvironmentFailure(
                "python_lock_artifact_invalid", "wheel filename is invalid"
            ) from exc
        return canonicalize_name(name), str(version), "wheel"
    try:
        name, version = parse_sdist_filename(filename)
    except ValueError as exc:
        raise EnvironmentFailure(
            "python_lock_artifact_invalid", "source distribution filename is invalid"
        ) from exc
    return canonicalize_name(name), str(version), "sdist"


def _pyproject_from_archive(filename: str, content: bytes) -> bytes | None:
    entries: list[tuple[str, bytes]] = []
    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                for name in archive.namelist():
                    path = PurePosixPath(name)
                    if path.name == "pyproject.toml" and ".." not in path.parts:
                        entries.append((name, archive.read(name)))
        else:
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
                for member in archive.getmembers():
                    path = PurePosixPath(member.name)
                    if (
                        member.isfile()
                        and path.name == "pyproject.toml"
                        and not path.is_absolute()
                        and ".." not in path.parts
                    ):
                        handle = archive.extractfile(member)
                        if handle is not None:
                            entries.append((member.name, handle.read()))
    except (tarfile.TarError, zipfile.BadZipFile, OSError) as exc:
        raise EnvironmentFailure(
            "python_lock_source_build_invalid", "source distribution cannot be inspected"
        ) from exc
    if not entries:
        return None
    entries.sort(key=lambda item: (len(PurePosixPath(item[0]).parts), item[0]))
    return entries[0][1]


def _marker_environment(target: dict[str, str]) -> dict[str, str]:
    version = target["pythonVersion"]
    return {
        "implementation_name": "cpython",
        "implementation_version": version + ".0",
        "os_name": "nt" if target["os"] == "Windows" else "posix",
        "platform_machine": target["architecture"],
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": target["os"],
        "platform_version": "",
        "python_full_version": version + ".0",
        "python_version": version,
        "sys_platform": {"Darwin": "darwin", "Linux": "linux", "Windows": "win32"}[
            target["os"]
        ],
    }


def review_source_build(
    candidate: ArtifactCandidate,
    content: bytes,
    target: dict[str, str],
    distributions: dict[str, frozenset[str]],
) -> dict[str, object]:
    pyproject = _pyproject_from_archive(candidate.filename, content)
    if pyproject is None:
        backend = "setuptools.build_meta:__legacy__"
        requirements = ["setuptools>=40.8.0"]
    else:
        try:
            payload = tomllib.loads(pyproject.decode("utf-8"))
            build_system = payload["build-system"]
            backend = build_system["build-backend"]
            requirements = build_system["requires"]
        except (KeyError, TypeError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise EnvironmentFailure(
                "python_lock_source_build_invalid", "source build system is invalid"
            ) from exc
        if build_system.get("backend-path") is not None:
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked", "in-tree source build backend is not locked"
            )
    if not isinstance(backend, str) or not backend or not isinstance(requirements, list):
        raise EnvironmentFailure(
            "python_lock_source_build_invalid", "source build system is invalid"
        )
    locked: list[dict[str, str]] = []
    for raw in requirements:
        if not isinstance(raw, str):
            raise EnvironmentFailure(
                "python_lock_source_build_invalid", "source build requirement is invalid"
            )
        try:
            requirement = Requirement(raw)
        except ValueError as exc:
            raise EnvironmentFailure(
                "python_lock_source_build_invalid", "source build requirement is invalid"
            ) from exc
        if requirement.marker is not None and not requirement.marker.evaluate(
            _marker_environment(target)
        ):
            continue
        name = canonicalize_name(requirement.name)
        versions = distributions.get(name, frozenset())
        if len(versions) != 1:
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked",
                f"source build requirement is not locked: {name}",
            )
        version = next(iter(versions))
        if requirement.specifier and not requirement.specifier.contains(
            Version(version), prereleases=True
        ):
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked",
                f"locked source build requirement is incompatible: {name}",
            )
        locked.append({"name": name, "requirement": raw, "version": version})
    if not locked:
        raise EnvironmentFailure(
            "python_lock_source_build_unlocked", "source build backend has no locked requirements"
        )
    return {"backend": backend, "requires": sorted(locked, key=lambda item: item["name"])}


def _record_hashes(records: Iterable[Any]) -> dict[str, set[str]]:
    hashes: dict[str, set[str]] = {}
    for record in records:
        hashes.setdefault(record.name, set()).update(record.hashes)
    return hashes


def build_projection(
    *,
    profile: str,
    target: dict[str, str],
    records: Iterable[Any],
    distributions: dict[str, frozenset[str]],
    artifact_index: ArtifactIndex,
    artifact_reader: ArtifactReader,
) -> dict[str, object]:
    allowed_hashes = _record_hashes(records)
    projection_records: list[dict[str, object]] = []
    for name, versions in sorted(distributions.items()):
        version = next(iter(versions))
        candidates = sorted(
            artifact_index(name, version), key=lambda candidate: candidate.filename
        )
        compatible_wheels: list[dict[str, str]] = []
        sources: list[ArtifactCandidate] = []
        for candidate in candidates:
            if not _artifact_supports_python(candidate, target):
                continue
            artifact_name, artifact_version, artifact_type = _artifact_identity(
                candidate.filename
            )
            if artifact_name != name or artifact_version != version:
                continue
            if not _HASH_RE.fullmatch(candidate.sha256):
                continue
            if candidate.sha256 not in allowed_hashes.get(name, set()):
                continue
            if artifact_type == "wheel" and wheel_is_compatible(candidate.filename, target):
                compatible_wheels.append(
                    {
                        "filename": candidate.filename,
                        "sha256": candidate.sha256,
                        "type": "wheel",
                    }
                )
            elif artifact_type == "sdist":
                sources.append(candidate)
        record: dict[str, object] = {"name": name, "version": version}
        if compatible_wheels:
            record["artifacts"] = compatible_wheels
        elif sources:
            source = sources[0]
            record["artifacts"] = [
                {"filename": source.filename, "sha256": source.sha256, "type": "sdist"}
            ]
            try:
                record["buildSystem"] = review_source_build(
                    source, artifact_reader(source), target, distributions
                )
            except EnvironmentFailure as exc:
                raise EnvironmentFailure(
                    exc.code,
                    f"{name}=={version} for {_projection_label(target, profile)}: {exc}",
                ) from exc
        else:
            raise EnvironmentFailure(
                "python_lock_artifact_missing",
                f"no reviewed artifact for {name}=={version}",
            )
        projection_records.append(record)
    payload = {"profile": profile, "records": projection_records, "target": target}
    return {**payload, "projectionHash": canonical_hash(payload)}


def _projection_label(target: dict[str, str], profile: str) -> str:
    return (
        f"{target['os']}/{target['architecture']}/"
        f"{target['implementation']}-{target['pythonVersion']}/{profile}"
    )


def _validate_build_system(
    build_system: object,
    distributions: dict[str, frozenset[str]],
) -> dict[str, str]:
    if not isinstance(build_system, dict) or set(build_system) != {"backend", "requires"}:
        raise EnvironmentFailure(
            "python_lock_source_build_unlocked", "source build backend is not locked"
        )
    backend = build_system.get("backend")
    requires = build_system.get("requires")
    if not isinstance(backend, str) or not backend or not isinstance(requires, list) or not requires:
        raise EnvironmentFailure(
            "python_lock_source_build_unlocked", "source build backend is not locked"
        )
    locked: dict[str, str] = {}
    for item in requires:
        if not isinstance(item, dict) or set(item) != {"name", "requirement", "version"}:
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked", "source build requirement is not locked"
            )
        name = item.get("name")
        version = item.get("version")
        raw = item.get("requirement")
        if not all(isinstance(value, str) for value in (name, version, raw)):
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked", "source build requirement is not locked"
            )
        try:
            requirement = Requirement(raw)
        except ValueError as exc:
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked", "source build requirement is invalid"
            ) from exc
        if canonicalize_name(requirement.name) != name or distributions.get(name) != frozenset(
            {version}
        ):
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked", "source build requirement is not selected"
            )
        if requirement.specifier and not requirement.specifier.contains(
            Version(version), prereleases=True
        ):
            raise EnvironmentFailure(
                "python_lock_source_build_unlocked", "source build requirement is incompatible"
            )
        locked[name] = version
    return locked


def validate_projection(
    projection: object,
    *,
    profile: str,
    target: dict[str, str],
    records: Iterable[Any],
    distributions: dict[str, frozenset[str]],
) -> ProjectionValidation:
    if not isinstance(projection, dict) or set(projection) != {
        "profile",
        "projectionHash",
        "records",
        "target",
    }:
        raise EnvironmentFailure(
            "python_lock_projection_invalid", "target artifact projection is invalid"
        )
    payload = {key: value for key, value in projection.items() if key != "projectionHash"}
    if projection.get("projectionHash") != canonical_hash(payload):
        raise EnvironmentFailure(
            "python_lock_projection_drift", "target artifact projection identity drifted"
        )
    if projection.get("profile") != profile or projection.get("target") != target:
        raise EnvironmentFailure(
            "python_lock_projection_drift", "target artifact projection selection drifted"
        )
    projection_records = projection.get("records")
    if not isinstance(projection_records, list):
        raise EnvironmentFailure(
            "python_lock_projection_invalid", "target artifact projection records are invalid"
        )
    allowed_hashes = _record_hashes(records)
    artifacts: dict[str, tuple[LockedArtifact, ...]] = {}
    build_requirements: dict[str, str] = {}
    source_build_count = 0
    previous_name = ""
    for item in projection_records:
        if not isinstance(item, dict) or not {"name", "version", "artifacts"}.issubset(item):
            raise EnvironmentFailure(
                "python_lock_projection_invalid", "target artifact projection record is invalid"
            )
        if set(item) not in (
            {"name", "version", "artifacts"},
            {"name", "version", "artifacts", "buildSystem"},
        ):
            raise EnvironmentFailure(
                "python_lock_projection_invalid", "target artifact projection fields are invalid"
            )
        name = item.get("name")
        version = item.get("version")
        artifact_items = item.get("artifacts")
        if (
            not isinstance(name, str)
            or name <= previous_name
            or not isinstance(version, str)
            or distributions.get(name) != frozenset({version})
            or not isinstance(artifact_items, list)
            or not artifact_items
        ):
            code = "python_lock_artifact_missing" if artifact_items == [] else "python_lock_projection_invalid"
            raise EnvironmentFailure(code, "target artifact projection record is invalid")
        previous_name = name
        locked_artifacts: list[LockedArtifact] = []
        previous_filename = ""
        includes_source = False
        for artifact in artifact_items:
            if not isinstance(artifact, dict) or set(artifact) != {
                "filename",
                "sha256",
                "type",
            }:
                raise EnvironmentFailure(
                    "python_lock_artifact_invalid", "target artifact is invalid"
                )
            filename = artifact.get("filename")
            digest = artifact.get("sha256")
            artifact_type = artifact.get("type")
            if (
                not isinstance(filename, str)
                or filename <= previous_filename
                or not isinstance(digest, str)
                or not _HASH_RE.fullmatch(digest)
                or digest not in allowed_hashes.get(name, set())
            ):
                raise EnvironmentFailure(
                    "python_lock_artifact_hash_unreviewed", "target artifact hash is not reviewed"
                )
            artifact_name, artifact_version, parsed_type = _artifact_identity(filename)
            if (
                artifact_name != name
                or artifact_version != version
                or artifact_type != parsed_type
            ):
                raise EnvironmentFailure(
                    "python_lock_artifact_invalid", "target artifact identity is invalid"
                )
            if artifact_type == "wheel" and not wheel_is_compatible(filename, target):
                raise EnvironmentFailure(
                    "python_lock_artifact_incompatible", "wheel is incompatible with target"
                )
            includes_source = includes_source or artifact_type == "sdist"
            locked_artifacts.append(LockedArtifact(filename, digest, artifact_type))
            previous_filename = filename
        if includes_source:
            source_build_count += 1
            build_requirements.update(
                _validate_build_system(item.get("buildSystem"), distributions)
            )
        elif "buildSystem" in item:
            raise EnvironmentFailure(
                "python_lock_projection_invalid", "wheel projection has a source build system"
            )
        artifacts[name] = tuple(locked_artifacts)
    if set(artifacts) != set(distributions):
        raise EnvironmentFailure(
            "python_lock_artifact_missing", "target projection omits selected distributions"
        )
    return ProjectionValidation(
        artifacts=artifacts,
        build_requirements=build_requirements,
        hash_count=sum(len(items) for items in artifacts.values()),
        projection_hash=str(projection["projectionHash"]),
        source_build_count=source_build_count,
    )
