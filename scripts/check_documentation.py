#!/usr/bin/env python3
"""Validate the repository documentation registry, links, paths, and lifecycles."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "docs" / "documentation-manifest.json"

ALLOWED_KINDS = {
    "canonical",
    "generated",
    "platform_template",
    "temporary_evidence",
    "tool_entry",
    "tool_mirror",
    "tool_workflow",
}
ALLOWED_STATUSES = {"active", "generated", "mirror", "temporary"}
TEXT_SUFFIXES = {
    ".cjs",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
REFERENCE_EXEMPTIONS = {
    "tests/scripts/test_validation_owner_planner.py": {"docs/" + "guide.md"},
}
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
DOC_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])(?P<path>docs/[A-Za-z0-9_.\-/]+\.md)"
    r"(?:#(?P<anchor>[A-Za-z0-9_.\-/]+))?"
)
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
PRIVATE_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])/(?:Users|private/var|var/folders|tmp)/[^\s`\"']+")
SECRET_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|"
    r"(?:AKIA|ASIA)[0-9A-Z]{16})(?![A-Za-z0-9_])"
)


def _relative(path: Path, root: Path = ROOT) -> str:
    return path.relative_to(root).as_posix()


def _load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_paths(root: Path, *args: str) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", *args],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return {
        item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    }


def discover_repository_paths(root: Path = ROOT) -> set[str]:
    tracked = _git_paths(root, "--cached")
    untracked = _git_paths(root, "--others", "--exclude-standard")
    return {
        path
        for path in tracked | untracked
        if (root / path).exists() or (root / path).is_symlink()
    }


def discover_markdown_paths(root: Path = ROOT) -> set[str]:
    return {path for path in discover_repository_paths(root) if path.lower().endswith(".md")}


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def validate_registry(
    registry: dict[str, Any], markdown_paths: set[str], root: Path = ROOT
) -> list[str]:
    errors: list[str] = []
    documents = registry.get("documents", [])
    if registry.get("schemaVersion") != 1:
        errors.append("registry schemaVersion must be 1")
    if not isinstance(documents, list) or not documents:
        return errors + ["registry documents must be a non-empty list"]

    ids = [str(entry.get("id", "")) for entry in documents]
    paths = [str(entry.get("path", "")) for entry in documents]
    for value in _duplicates(ids):
        errors.append(f"duplicate document id: {value}")
    for value in _duplicates(paths):
        errors.append(f"duplicate document path: {value}")

    registered = set(paths)
    missing_registration = sorted(markdown_paths - registered)
    stale_registration = sorted(registered - markdown_paths)
    for path in missing_registration:
        errors.append(f"unregistered Markdown: {path}")
    for path in stale_registration:
        errors.append(f"registered Markdown is missing or untracked: {path}")

    generated_output_by_path = {
        entry["path"]: entry for entry in registry.get("generatedOutputs", [])
    }
    authority_by_id = {
        entry["id"]: entry for entry in registry.get("authorities", [])
    }
    if len(authority_by_id) != len(registry.get("authorities", [])):
        errors.append("authority ids must be unique")

    claimed_authorities: dict[str, str] = {}
    for entry in documents:
        path = str(entry.get("path", ""))
        kind = entry.get("kind")
        status = entry.get("status")
        editable = entry.get("editable")
        if kind not in ALLOWED_KINDS:
            errors.append(f"{path}: invalid kind {kind!r}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{path}: invalid status {status!r}")
        if not isinstance(editable, bool):
            errors.append(f"{path}: editable must be boolean")
        if not entry.get("summary"):
            errors.append(f"{path}: summary is required")
        if not path.endswith(".md"):
            errors.append(f"{path}: registered document must be Markdown")

        if kind == "generated":
            if editable is not False or status != "generated":
                errors.append(f"{path}: generated documents must be non-editable/generated")
            output = generated_output_by_path.get(path)
            if output is None:
                errors.append(f"{path}: generated document is not a declared output")
            elif output.get("generator") != entry.get("generator"):
                errors.append(f"{path}: generated output and document generator disagree")

        if kind == "temporary_evidence":
            lifecycle = entry.get("lifecycle")
            if status != "temporary" or not isinstance(lifecycle, dict):
                errors.append(f"{path}: temporary evidence requires temporary status and lifecycle")
            else:
                for field in ("owner", "retireWhen", "retirementAction"):
                    if not lifecycle.get(field):
                        errors.append(f"{path}: lifecycle.{field} is required")
                if lifecycle.get("archiveCopyAllowed") is not False:
                    errors.append(f"{path}: archiveCopyAllowed must be false")
                machine = lifecycle.get("machineEvidence")
                if machine and not (root / machine).is_file():
                    errors.append(f"{path}: machine evidence is missing: {machine}")

        if kind in {"tool_entry", "tool_mirror"}:
            canonical = entry.get("canonical")
            if not canonical or not (root / canonical).exists():
                errors.append(f"{path}: mirror canonical target is missing")

        symlink_target = entry.get("symlinkTarget")
        if symlink_target:
            full_path = root / path
            if not full_path.is_symlink():
                errors.append(f"{path}: expected symlink")
            elif full_path.readlink().as_posix() != symlink_target:
                errors.append(f"{path}: symlink target must be {symlink_target}")

        for authority_id in entry.get("authorityIds", []):
            if authority_id in claimed_authorities:
                errors.append(
                    f"authority {authority_id} claimed by both {claimed_authorities[authority_id]} and {path}"
                )
            claimed_authorities[authority_id] = path
            authority = authority_by_id.get(authority_id)
            if authority is None:
                errors.append(f"{path}: unknown authority id {authority_id}")
            elif authority.get("source") != path:
                errors.append(f"{path}: authority {authority_id} points to {authority.get('source')}")

    for authority_id, authority in authority_by_id.items():
        source = authority.get("source", "")
        if not source or not (root / source).is_file():
            errors.append(f"authority {authority_id}: source is missing: {source}")
        if source.endswith(".md") and claimed_authorities.get(authority_id) != source:
            errors.append(f"authority {authority_id}: canonical Markdown does not claim the authority")
        if not authority.get("scope"):
            errors.append(f"authority {authority_id}: scope is required")

    root_paths = {
        path for path in markdown_paths if PurePosixPath(path).parent == PurePosixPath(".")
    }
    declared_root_paths = {entry.get("path") for entry in registry.get("rootDocuments", [])}
    if root_paths != declared_root_paths:
        errors.append(
            "root Markdown inventory differs: "
            f"actual={sorted(root_paths)} declared={sorted(declared_root_paths)}"
        )
    for entry in registry.get("rootDocuments", []):
        if not entry.get("reason"):
            errors.append(f"root document {entry.get('path')}: placement reason is required")

    mandatory = registry.get("mandatoryRead", [])
    if mandatory != ["AGENTS.md", "docs/README.md"]:
        errors.append("mandatoryRead must remain the small AGENTS.md -> docs/README.md path")

    route_ids = [route.get("id", "") for route in registry.get("taskRoutes", [])]
    for value in _duplicates(route_ids):
        errors.append(f"duplicate task route id: {value}")
    routed_paths: set[str] = set(mandatory)
    for route in registry.get("taskRoutes", []):
        if not route.get("task") or not route.get("note"):
            errors.append(f"task route {route.get('id')}: task and note are required")
        for path in route.get("read", []):
            routed_paths.add(path)
            if not (root / path).is_file():
                errors.append(f"task route {route.get('id')}: missing target {path}")
            document = next((item for item in documents if item["path"] == path), None)
            if document and document["kind"] == "generated":
                errors.append(f"task route {route.get('id')}: generated document cannot be a canonical target")

    authority_sources = {entry["source"] for entry in registry.get("authorities", [])}
    for entry in documents:
        if entry["kind"] != "canonical":
            continue
        if entry["path"] not in routed_paths | authority_sources:
            errors.append(f"orphan canonical document: {entry['path']}")

    for path in registry.get("retiredPaths", []):
        if (root / path).exists() or (root / path).is_symlink():
            errors.append(f"retired path still exists: {path}")

    return errors


def _without_fenced_blocks(text: str) -> str:
    output: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = FENCE_PATTERN.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            output.append("")
            continue
        output.append(line if fence is None else "")
    return "\n".join(output)


def _github_slug(text: str) -> str:
    text = HTML_TAG_PATTERN.sub("", text).strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def _heading_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in _without_fenced_blocks(path.read_text(encoding="utf-8")).splitlines():
        match = HEADING_PATTERN.match(line)
        if not match:
            continue
        base = _github_slug(match.group(1))
        count = counts.get(base, 0)
        counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")
    return anchors


def validate_markdown_links(markdown_paths: set[str], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    for relative_path in sorted(markdown_paths):
        source = root / relative_path
        text = _without_fenced_blocks(source.read_text(encoding="utf-8"))
        for raw_target in MARKDOWN_LINK_PATTERN.findall(text):
            target = raw_target.strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            target = target.split(" ", 1)[0]
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            path_part, separator, anchor = target.partition("#")
            decoded_path = unquote(path_part)
            resolved = source if not decoded_path else (source.parent / decoded_path).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{relative_path}: link escapes repository: {raw_target}")
                continue
            if not resolved.exists():
                errors.append(f"{relative_path}: broken relative link: {raw_target}")
                continue
            if separator and anchor and resolved.suffix.lower() == ".md":
                anchors = anchor_cache.setdefault(resolved, _heading_anchors(resolved))
                normalized = _github_slug(unquote(anchor))
                if normalized not in anchors:
                    errors.append(f"{relative_path}: missing Markdown anchor: {raw_target}")
    return errors


def _reference_scan_exclusions(registry: dict[str, Any]) -> set[str]:
    excluded = {"docs/documentation-manifest.json"}
    for entry in registry["documents"]:
        if entry["kind"] != "temporary_evidence":
            continue
        excluded.add(entry["path"])
        machine = entry.get("lifecycle", {}).get("machineEvidence")
        if machine:
            excluded.add(machine)
    return excluded


def validate_current_doc_references(
    registry: dict[str, Any], repository_paths: set[str], root: Path = ROOT
) -> list[str]:
    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    excluded = _reference_scan_exclusions(registry)
    retired_paths = registry.get("retiredPaths", [])
    for relative_path in sorted(repository_paths - excluded):
        path = root / relative_path
        if path.suffix.lower() not in TEXT_SUFFIXES or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        exemptions = REFERENCE_EXEMPTIONS.get(relative_path, set())
        references = {
            (match.group("path"), match.group("anchor"))
            for match in DOC_PATH_PATTERN.finditer(text)
        }
        for doc_path, anchor in sorted(references, key=lambda item: (item[0], item[1] or "")):
            if doc_path in exemptions:
                continue
            target = root / doc_path
            if not target.is_file():
                errors.append(f"{relative_path}: stale Markdown path reference: {doc_path}")
                continue
            if anchor:
                anchors = anchor_cache.setdefault(target, _heading_anchors(target))
                normalized = _github_slug(anchor)
                if normalized not in anchors:
                    errors.append(
                        f"{relative_path}: stale Markdown anchor reference: {doc_path}#{anchor}"
                    )
        for retired_path in retired_paths:
            if retired_path in text:
                errors.append(f"{relative_path}: retired path reference: {retired_path}")
    return errors


def validate_durable_doc_safety(registry: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for entry in registry["documents"]:
        if entry["kind"] == "temporary_evidence":
            continue
        path = root / entry["path"]
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if PRIVATE_PATH_PATTERN.search(line):
                errors.append(f"{entry['path']}:{line_number}: private absolute path")
            if SECRET_PATTERN.search(line):
                errors.append(f"{entry['path']}:{line_number}: secret-shaped value")
        if entry["kind"] == "generated":
            first_lines = "\n".join(text.splitlines()[:8]).lower()
            if "generated" not in first_lines or "do not edit" not in first_lines:
                errors.append(f"{entry['path']}: generated marker is missing")
    return errors


def collect_errors(root: Path = ROOT) -> tuple[list[str], dict[str, int]]:
    registry_path = root / "docs" / "documentation-manifest.json"
    registry = _load_registry(registry_path)
    repository_paths = discover_repository_paths(root)
    markdown_paths = {path for path in repository_paths if path.lower().endswith(".md")}
    errors = []
    errors.extend(validate_registry(registry, markdown_paths, root))
    errors.extend(validate_markdown_links(markdown_paths, root))
    errors.extend(validate_current_doc_references(registry, repository_paths, root))
    errors.extend(validate_durable_doc_safety(registry, root))
    counts = {
        "markdown": len(markdown_paths),
        "canonical": sum(entry["kind"] == "canonical" for entry in registry["documents"]),
        "generated": sum(entry["kind"] == "generated" for entry in registry["documents"]),
        "temporary": sum(
            entry["kind"] == "temporary_evidence" for entry in registry["documents"]
        ),
    }
    return sorted(set(errors)), counts


def main() -> int:
    errors, counts = collect_errors()
    if errors:
        for error in errors:
            print(f"[documentation] ERROR: {error}", file=sys.stderr)
        print(f"[documentation] FAILED: {len(errors)} finding(s)", file=sys.stderr)
        return 1
    print(
        "[documentation] OK "
        f"markdown={counts['markdown']} canonical={counts['canonical']} "
        f"generated={counts['generated']} temporary={counts['temporary']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
