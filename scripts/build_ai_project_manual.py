#!/usr/bin/env python3
"""Generate documentation navigation and source identity from the canonical registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
GENERATOR_PATH = Path(__file__).resolve()
REGISTRY_PATH = ROOT / "docs" / "documentation-manifest.json"
DOCS_INDEX_PATH = ROOT / "docs" / "README.md"
MANUAL_PATH = ROOT / "docs" / "generated" / "AI_PROJECT_MANUAL.md"
MANIFEST_PATH = ROOT / "docs" / "generated" / "AI_PROJECT_MANUAL_SOURCES.json"
GENERATOR_VERSION = 7

@dataclass(frozen=True)
class GeneratedOutputs:
    docs_index: str
    manual: str
    manifest_text: str
    source_count: int
    discovery: dict[str, Any]


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_text(content: str) -> str:
    return _sha256_bytes(content.encode("utf-8"))


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _document_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / entry["path"]
    content = path.read_bytes()
    text = content.decode("utf-8")
    return {
        "id": entry["id"],
        "path": entry["path"],
        "title": _first_heading(text, entry["id"]),
        "kind": entry["kind"],
        "status": entry["status"],
        "editable": entry["editable"],
        "summary": entry["summary"],
        "bytes": len(content),
        "lineCount": len(text.splitlines()),
        "sha256": _sha256_bytes(content),
    }


def _discover_markdown() -> dict[str, Any]:
    paths: set[str] = set()
    for args in (("--cached",), ("--others", "--exclude-standard")):
        result = subprocess.run(
            ["git", "ls-files", "-z", *args],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        for item in result.stdout.split(b"\0"):
            if not item:
                continue
            relative_path = item.decode("utf-8")
            path = ROOT / relative_path
            if relative_path.lower().endswith(".md") and (path.exists() or path.is_symlink()):
                paths.add(relative_path)
    return {
        "markdownDiscovered": len(paths),
        "markdownPaths": sorted(paths),
        "scope": "tracked and non-ignored untracked Markdown present in the worktree",
    }


def _relative_href(target: str, output_path: str) -> str:
    output_dir = PurePosixPath(output_path).parent
    return os.path.relpath(target, start=output_dir.as_posix()).replace(os.sep, "/")


def _link(target: str, output_path: str, label: str | None = None) -> str:
    return f"[{label or target}]({_relative_href(target, output_path)})"


def _escape_table(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    header_list = list(headers)
    lines = [
        "| " + " | ".join(header_list) + " |",
        "| " + " | ".join("---" for _ in header_list) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_escape_table(value) for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def _render_mandatory(registry: dict[str, Any], output_path: str) -> str:
    lines = [
        "1. Read the current task and " + _link("AGENTS.md", output_path) + ".",
        "2. Use this task router to select only the applicable canonical documents.",
        "3. Read the closest source and tests; they remain the executable truth.",
    ]
    if output_path != "docs/README.md":
        lines[1] = "2. Use " + _link("docs/README.md", output_path) + " to select only the applicable canonical documents."
    return "\n".join(lines)


def _render_routes(registry: dict[str, Any], output_path: str) -> str:
    rows: list[list[str]] = []
    for route in registry["taskRoutes"]:
        links = "<br>".join(_link(path, output_path) for path in route["read"])
        rows.append([route["task"], links, route["note"]])
    return _table(("Task", "Read after the mandatory context", "Boundary"), rows)


def _render_authorities(registry: dict[str, Any], output_path: str) -> str:
    return _table(
        ("Authority", "Canonical source", "Scope"),
        (
            (
                authority["id"],
                _link(authority["source"], output_path),
                authority["scope"],
            )
            for authority in registry["authorities"]
        ),
    )


def _render_docs_index(registry: dict[str, Any]) -> str:
    output_path = "docs/README.md"
    return (
        "# WolfyStock Documentation\n\n"
        "> GENERATED NAVIGATION. DO NOT EDIT DIRECTLY.\n"
        "> Source: [`docs/documentation-manifest.json`](documentation-manifest.json). "
        "Generator: [`scripts/build_ai_project_manual.py`](../scripts/build_ai_project_manual.py).\n\n"
        "This is the model-independent documentation entrypoint. It keeps the mandatory "
        "context small, routes tasks to canonical owners, and separates generated, mirrored, "
        "historical, and temporary material.\n\n"
        "## Mandatory Context\n\n"
        + _render_mandatory(registry, output_path)
        + "\n\n"
        "The root [`README.md`](../README.md) is the human/product entrypoint. The generated "
        "[`AI project manual`](generated/AI_PROJECT_MANUAL.md) is a complete catalog, not a "
        "second policy or domain authority.\n\n"
        "## Task Routing\n\n"
        + _render_routes(registry, output_path)
        + "\n\n"
        "## Canonical Authority Map\n\n"
        + _render_authorities(registry, output_path)
        + "\n\n"
        "## Document Classes\n\n"
        "- `canonical`: directly editable owner for the stated scope.\n"
        "- `generated`: output of the registered generator; edit its source instead.\n"
        "- `tool_entry` / `tool_mirror`: required platform or AI compatibility surface that "
        "defers to a canonical owner.\n"
        "- `tool_workflow` / `platform_template`: local tool or repository-platform workflow "
        "asset, not project policy.\n"
        "- `temporary_evidence`: bounded audit evidence with an owner, retirement condition, "
        "and deletion action; never current policy.\n\n"
        "## Editing And Validation\n\n"
        "Edit canonical sources and [`docs/documentation-manifest.json`](documentation-manifest.json), "
        "then run:\n\n"
        "```bash\n"
        "python scripts/build_ai_project_manual.py\n"
        "python scripts/check_documentation.py\n"
        "python scripts/build_ai_project_manual.py --check\n"
        "python scripts/check_ai_assets.py\n"
        "```\n\n"
        "Generated output is not canonical source. Temporary evidence is not durable "
        "documentation. Document presence is not authority.\n"
    )


def _render_inventory(
    registry: dict[str, Any], source_meta: dict[str, dict[str, Any]], output_path: str
) -> str:
    rows: list[list[object]] = []
    for entry in registry["documents"]:
        meta = source_meta.get(entry["path"])
        sha = meta["sha256"][:12] if meta else "generated"
        rows.append(
            [
                _link(entry["path"], output_path),
                entry["kind"],
                entry["status"],
                "yes" if entry["editable"] else "no",
                entry["summary"],
                sha,
            ]
        )
    return _table(("Path", "Kind", "Status", "Direct edit", "Purpose", "SHA-256"), rows)


def _render_lifecycles(registry: dict[str, Any], output_path: str) -> str:
    rows: list[list[str]] = []
    for entry in registry["documents"]:
        if entry["kind"] != "temporary_evidence":
            continue
        lifecycle = entry["lifecycle"]
        machine = lifecycle.get("machineEvidence")
        rows.append(
            [
                _link(entry["path"], output_path),
                lifecycle["owner"],
                _link(machine, output_path) if machine else "none",
                lifecycle["retireWhen"],
                lifecycle["retirementAction"],
            ]
        )
    return _table(("Report", "Owner", "Machine evidence", "Retire when", "Action"), rows)


def _render_manual(
    registry: dict[str, Any], source_meta: dict[str, dict[str, Any]], discovery: dict[str, Any]
) -> str:
    output_path = "docs/generated/AI_PROJECT_MANUAL.md"
    kind_counts = Counter(entry["kind"] for entry in registry["documents"])
    count_summary = ", ".join(f"{kind}={count}" for kind, count in sorted(kind_counts.items()))
    return (
        "# WolfyStock AI Project Manual\n\n"
        "> GENERATED FILE. DO NOT EDIT DIRECTLY.\n"
        "> Canonical registry: [`docs/documentation-manifest.json`](../documentation-manifest.json). "
        "Generator: [`scripts/build_ai_project_manual.py`](../../scripts/build_ai_project_manual.py).\n\n"
        "This manual is a generated navigation and integrity catalog. It does not copy domain "
        "rules, authorize protected changes, approve release, or replace current source/test "
        "inspection.\n\n"
        "## Mandatory Context\n\n"
        + _render_mandatory(registry, output_path)
        + "\n\n"
        "## Task Routing\n\n"
        + _render_routes(registry, output_path)
        + "\n\n"
        "## Canonical Authority Map\n\n"
        + _render_authorities(registry, output_path)
        + "\n\n"
        "## Registered Markdown Inventory\n\n"
        + _render_inventory(registry, source_meta, output_path)
        + "\n\n"
        "Inventory summary: registered="
        + str(len(registry["documents"]))
        + ", discovered="
        + str(discovery["markdownDiscovered"])
        + "; "
        + count_summary
        + ".\n\n"
        "## Temporary Evidence Lifecycle\n\n"
        + _render_lifecycles(registry, output_path)
        + "\n\n"
        "Temporary reports are deleted when their registered condition is met. They are not moved "
        "to archive, history, completed-report, mirror, or compatibility paths.\n\n"
        "## Generated Model\n\n"
        "The generator reads the structured registry and registered source metadata. It renders "
        "navigation, classifications, lifecycle conditions, and hashes; domain prose remains in "
        "its canonical owner. The source identity file is "
        "[`docs/generated/AI_PROJECT_MANUAL_SOURCES.json`](AI_PROJECT_MANUAL_SOURCES.json).\n\n"
        "Run `python scripts/build_ai_project_manual.py --check` for freshness and "
        "`python scripts/check_documentation.py` for structure, links, paths, and lifecycle checks.\n"
    )


def _build_source_manifest(
    registry: dict[str, Any],
    source_meta: dict[str, dict[str, Any]],
    discovery: dict[str, Any],
    docs_index: str,
    manual: str,
) -> dict[str, Any]:
    registry_bytes = REGISTRY_PATH.read_bytes()
    return {
        "schemaVersion": 3,
        "generator": {
            "path": _display_path(GENERATOR_PATH),
            "version": GENERATOR_VERSION,
            "sha256": _sha256_bytes(GENERATOR_PATH.read_bytes()),
            "deterministic": True,
            "callsExternalServices": False,
            "requiresApiKeys": False,
            "readsProductionDataPaths": False,
        },
        "registry": {
            "path": _display_path(REGISTRY_PATH),
            "schemaVersion": registry["schemaVersion"],
            "sha256": _sha256_bytes(registry_bytes),
        },
        "outputs": {
            "docsIndex": _display_path(DOCS_INDEX_PATH),
            "docsIndexSha256": _sha256_text(docs_index),
            "manual": _display_path(MANUAL_PATH),
            "manualSha256": _sha256_text(manual),
            "sourceManifest": _display_path(MANIFEST_PATH),
        },
        "inventory": {
            "registeredMarkdown": len(registry["documents"]),
            "markdownDiscovered": discovery["markdownDiscovered"],
            "kindCounts": dict(
                sorted(Counter(entry["kind"] for entry in registry["documents"]).items())
            ),
            "statusCounts": dict(
                sorted(Counter(entry["status"] for entry in registry["documents"]).items())
            ),
        },
        "discovery": discovery,
        "authorities": registry["authorities"],
        "taskRoutes": registry["taskRoutes"],
        "sources": [source_meta[path] for path in sorted(source_meta)],
        "temporaryEvidence": [
            {
                "path": entry["path"],
                **entry["lifecycle"],
            }
            for entry in registry["documents"]
            if entry["kind"] == "temporary_evidence"
        ],
    }


def build_generated_outputs() -> GeneratedOutputs:
    registry = _load_registry()
    source_meta = {
        entry["path"]: _document_metadata(entry)
        for entry in registry["documents"]
        if entry["kind"] != "generated"
    }
    discovery = _discover_markdown()
    docs_index = _render_docs_index(registry)
    manual = _render_manual(registry, source_meta, discovery)
    source_manifest = _build_source_manifest(registry, source_meta, discovery, docs_index, manual)
    return GeneratedOutputs(
        docs_index=docs_index,
        manual=manual,
        manifest_text=json.dumps(source_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        source_count=len(source_meta),
        discovery=discovery,
    )


def _write_text_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def check_generated_outputs(outputs: GeneratedOutputs) -> int:
    expected = {
        DOCS_INDEX_PATH: outputs.docs_index,
        MANUAL_PATH: outputs.manual,
        MANIFEST_PATH: outputs.manifest_text,
    }
    stale_paths = [
        _display_path(path)
        for path, content in expected.items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    if stale_paths:
        print("[manual-generator] generated documentation is stale", file=sys.stderr)
        for path in stale_paths:
            print(f"[manual-generator] stale output: {path}", file=sys.stderr)
        print(f"[manual-generator] run: python {_display_path(GENERATOR_PATH)}", file=sys.stderr)
        return 1

    print("[manual-generator] generated documentation is fresh")
    print(
        f"registered_sources={outputs.source_count} "
        f"markdown_discovered={outputs.discovery['markdownDiscovered']}"
    )
    return 0


def write_generated_outputs(outputs: GeneratedOutputs) -> None:
    _write_text_if_changed(DOCS_INDEX_PATH, outputs.docs_index)
    _write_text_if_changed(MANUAL_PATH, outputs.manual)
    _write_text_if_changed(MANIFEST_PATH, outputs.manifest_text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail without writing when outputs are stale")
    args = parser.parse_args(argv)

    outputs = build_generated_outputs()
    if args.check:
        return check_generated_outputs(outputs)

    write_generated_outputs(outputs)
    print("[manual-generator] generated documentation updated")
    print(
        f"registered_sources={outputs.source_count} "
        f"markdown_discovered={outputs.discovery['markdownDiscovered']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
