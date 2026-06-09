#!/usr/bin/env python3
"""Collect changed files for conservative validation tiers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_REF = (
    os.environ.get("VALIDATION_BASE_REF")
    or os.environ.get("CI_GATE_BASE_REF")
    or os.environ.get("RELEASE_SECRET_SCAN_BASE_REF")
    or "origin/main"
)
DEFAULT_DIFF_FILTER = "ACMRTUXB"

BINARY_SUFFIXES = {
    ".7z",
    ".avif",
    ".bz2",
    ".db",
    ".duckdb",
    ".eot",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".otf",
    ".parquet",
    ".pdf",
    ".pkl",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".xz",
    ".zip",
}

SKIPPED_PARTS = {
    ".cache",
    ".electron-builder-cache",
    ".git",
    ".next",
    ".pytest_cache",
    ".turbo",
    ".vite",
    ".venv",
    "__pycache__",
    "blob-report",
    "build",
    "coverage",
    "dist",
    "generated",
    "htmlcov",
    "node_modules",
    "playwright-report",
    "static",
    "test-results",
    "tmp",
    "vendor",
    "venv",
}

FRONTEND_LINT_SUFFIXES = {".cjs", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
FRONTEND_RELATED_SUFFIXES = {".cjs", ".css", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
DESIGN_SUFFIXES = {".css", ".ts", ".tsx"}
DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".json", ".yml", ".yaml"}

PROTECTED_PREFIXES = (
    "api/",
    "data_provider/",
    "src/",
)
PROTECTED_PARTS = {
    "migrations",
}
PROTECTED_FRONTEND_PREFIXES = (
    "apps/dsa-web/src/api/",
    "apps/dsa-web/src/services/auth",
    "apps/dsa-web/src/stores/auth",
)
FULL_GATE_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}


def run_git(args: list[str], *, root: Path = ROOT, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=check,
    )


def git_lines(args: list[str], *, root: Path = ROOT) -> list[str]:
    result = run_git(args, root=root)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def base_ref_available(base_ref: str) -> bool:
    return run_git(["rev-parse", "--verify", base_ref]).returncode == 0


def normalize_path(value: str, *, root: Path = ROOT) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        try:
            raw = path.resolve().relative_to(root).as_posix()
        except ValueError:
            return None
    raw = raw.replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    if raw in {"", "."} or raw.startswith("../") or "/../" in raw:
        return None
    return raw


def unique_sorted(paths: Iterable[str]) -> list[str]:
    return sorted({path for path in paths if path})


def has_skipped_part(path: str) -> bool:
    parts = set(path.split("/"))
    return bool(parts & SKIPPED_PARTS)


def is_generated_static_binary_or_cache(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in BINARY_SUFFIXES or has_skipped_part(path)


def path_exists(path: str, *, root: Path = ROOT) -> bool:
    return (root / path).is_file()


def is_frontend_path(path: str) -> bool:
    return path.startswith("apps/dsa-web/")


def is_python_path(path: str) -> bool:
    return path.endswith(".py")


def is_doc_path(path: str) -> bool:
    return path.startswith("docs/") or Path(path).suffix.lower() in DOC_SUFFIXES


def scope_allows(path: str, scope: str) -> bool:
    if is_generated_static_binary_or_cache(path):
        return False
    suffix = Path(path).suffix.lower()
    if scope in {"all", "secret"}:
        return True
    if scope == "frontend":
        return is_frontend_path(path)
    if scope == "frontend-lint":
        return is_frontend_path(path) and suffix in FRONTEND_LINT_SUFFIXES
    if scope == "frontend-related":
        return is_frontend_path(path) and suffix in FRONTEND_RELATED_SUFFIXES
    if scope == "design":
        return path.startswith("apps/dsa-web/src/") and suffix in DESIGN_SUFFIXES
    if scope == "python":
        return is_python_path(path)
    if scope == "docs":
        return is_doc_path(path)
    raise ValueError(f"unknown scope: {scope}")


def read_files_from(path: str, *, root: Path = ROOT) -> list[str]:
    if path == "-":
        return [line for line in sys.stdin.read().splitlines() if line.strip()]
    content_path = Path(path)
    if not content_path.is_absolute():
        content_path = root / content_path
    return content_path.read_text(encoding="utf-8").splitlines()


def collect_raw(mode: str, base_ref: str, diff_filter: str) -> dict[str, list[str] | bool]:
    branch: list[str] = []
    local_staged: list[str] = []
    local_worktree: list[str] = []
    local_untracked: list[str] = []
    base_available = base_ref_available(base_ref)

    if mode in {"all", "active", "branch", "branch-release"}:
        if base_available:
            separator = ".." if mode == "branch-release" else "..."
            branch = git_lines(["diff", "--name-only", f"--diff-filter={diff_filter}", f"{base_ref}{separator}HEAD"])
        else:
            print(f"[WARN] base ref not available: {base_ref}", file=sys.stderr)

    if mode in {"all", "active", "local", "staged"}:
        local_staged = git_lines(["diff", "--cached", "--name-only", f"--diff-filter={diff_filter}"])
    if mode in {"all", "active", "local", "worktree"}:
        local_worktree = git_lines(["diff", "--name-only", f"--diff-filter={diff_filter}"])
    if mode in {"all", "active", "local", "untracked"}:
        local_untracked = git_lines(["ls-files", "--others", "--exclude-standard"])

    local = unique_sorted([*local_staged, *local_worktree, *local_untracked])
    if mode == "active":
        selected = local if local else branch
    elif mode == "local":
        selected = local
    elif mode == "staged":
        selected = local_staged
    elif mode == "worktree":
        selected = local_worktree
    elif mode == "untracked":
        selected = local_untracked
    elif mode in {"branch", "branch-release"}:
        selected = branch
    else:
        selected = [*branch, *local]

    return {
        "baseRefAvailable": base_available,
        "branchFiles": unique_sorted(normalize_path(path) or "" for path in branch),
        "stagedFiles": unique_sorted(normalize_path(path) or "" for path in local_staged),
        "worktreeFiles": unique_sorted(normalize_path(path) or "" for path in local_worktree),
        "untrackedFiles": unique_sorted(normalize_path(path) or "" for path in local_untracked),
        "localFiles": unique_sorted(normalize_path(path) or "" for path in local),
        "selectedFiles": unique_sorted(normalize_path(path) or "" for path in selected),
    }


def is_protected_domain(path: str) -> bool:
    parts = set(path.split("/"))
    if parts & PROTECTED_PARTS:
        return True
    return path.startswith(PROTECTED_PREFIXES) or path.startswith(PROTECTED_FRONTEND_PREFIXES)


def needs_full_gate(path: str) -> bool:
    if path in FULL_GATE_FILES or Path(path).name in FULL_GATE_FILES:
        return True
    if path.startswith(".github/workflows/"):
        return True
    if path.endswith("-lock.json") or path.endswith(".lock"):
        return True
    return False


def is_known_validation_path(path: str) -> bool:
    if is_doc_path(path):
        return True
    if path.startswith("scripts/"):
        return True
    if path.startswith("tests/"):
        return True
    if path.startswith("apps/dsa-web/"):
        return True
    if path in {"AGENTS.md", "CLAUDE.md"}:
        return True
    return False


def classify(files: list[str], *, root: Path = ROOT) -> dict[str, object]:
    protected_files = [path for path in files if is_protected_domain(path)]
    full_gate_files = [path for path in files if needs_full_gate(path)]
    unknown_files = [path for path in files if not is_known_validation_path(path)]
    frontend_files = [path for path in files if is_frontend_path(path)]
    frontend_shared = [
        path
        for path in frontend_files
        if path.startswith(
            (
                "apps/dsa-web/src/components/",
                "apps/dsa-web/src/hooks/",
                "apps/dsa-web/src/lib/",
                "apps/dsa-web/src/styles/",
                "apps/dsa-web/src/utils/",
            )
        )
    ]
    backend_report_files = [
        path
        for path in files
        if path.startswith(("src/services/report", "src/schemas/report", "tests/"))
        and ("report" in path.lower() or "renderer" in path.lower())
    ]

    if protected_files:
        tier = "protected-domain"
    elif full_gate_files or unknown_files:
        tier = "full-gate"
    elif backend_report_files:
        tier = "backend-report"
    elif frontend_shared:
        tier = "frontend-shared"
    elif frontend_files:
        tier = "frontend-component"
    elif all(is_doc_path(path) for path in files) if files else False:
        tier = "copy-only"
    else:
        tier = "script-doc"

    return {
        "tier": tier,
        "hasFrontend": bool(frontend_files),
        "hasFrontendShared": bool(frontend_shared),
        "hasPython": any(is_python_path(path) for path in files),
        "hasDocs": any(is_doc_path(path) for path in files),
        "hasProtectedDomain": bool(protected_files),
        "hasFullGateRisk": bool(full_gate_files),
        "hasUnknown": bool(unknown_files),
        "protectedFiles": protected_files,
        "fullGateFiles": full_gate_files,
        "unknownFiles": unknown_files,
        "frontendFiles": frontend_files,
        "frontendSharedFiles": frontend_shared,
        "backendReportFiles": backend_report_files,
    }


def resolve_output_path(path: str, relative_to: str | None, *, root: Path = ROOT) -> str | None:
    if not relative_to:
        return path
    base = root / relative_to
    absolute = root / path
    try:
        return absolute.relative_to(base).as_posix()
    except ValueError:
        return None


def selected_files(args: argparse.Namespace) -> tuple[dict[str, object], list[str], list[str]]:
    if args.files is not None or args.files_from:
        provided: list[str] = []
        for path in args.files or []:
            provided.append(path)
        for file_list in args.files_from or []:
            provided.extend(read_files_from(file_list, root=args.root))
        raw = {
            "baseRefAvailable": base_ref_available(args.base_ref),
            "branchFiles": [],
            "stagedFiles": [],
            "worktreeFiles": [],
            "untrackedFiles": [],
            "localFiles": [],
            "selectedFiles": unique_sorted(normalize_path(path, root=args.root) or "" for path in provided),
        }
    else:
        raw = collect_raw(args.mode, args.base_ref, args.diff_filter)

    normalized = raw["selectedFiles"]
    assert isinstance(normalized, list)
    skipped = [path for path in normalized if is_generated_static_binary_or_cache(path)]
    filtered = [path for path in normalized if scope_allows(path, args.scope)]
    if args.existing:
        filtered = [path for path in filtered if path_exists(path, root=args.root)]

    output_files: list[str] = []
    for path in filtered:
        rendered = resolve_output_path(path, args.relative_to, root=args.root)
        if rendered is not None:
            output_files.append(rendered)
    return raw, unique_sorted(output_files), unique_sorted(skipped)


def print_files(files: list[str], output_format: str) -> None:
    if output_format == "lines":
        for path in files:
            print(path)
        return
    if output_format == "nul":
        sys.stdout.buffer.write(b"".join(path.encode("utf-8") + b"\0" for path in files))
        return
    if output_format == "shell":
        print(" ".join(shlex.quote(path) for path in files))
        return
    raise ValueError(f"unsupported file output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect changed files for local validation tiers without writing repo cache files.",
        epilog=(
            "Examples:\n"
            "  python3 scripts/validation_changed_files.py --mode active --scope frontend-lint\n"
            "  python3 scripts/validation_changed_files.py --files-from /tmp/files.txt --scope secret\n"
            "  python3 scripts/validation_changed_files.py --scope frontend-lint --relative-to apps/dsa-web --exec eslint"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF, help=f"base ref for branch diffs (default: {DEFAULT_BASE_REF})")
    parser.add_argument(
        "--mode",
        choices=("active", "all", "branch", "branch-release", "local", "staged", "worktree", "untracked"),
        default="active",
        help="changed-file source; active uses local files when present, otherwise branch files",
    )
    parser.add_argument(
        "--scope",
        choices=("all", "secret", "frontend", "frontend-lint", "frontend-related", "design", "python", "docs"),
        default="all",
        help="filter files to a validation domain",
    )
    parser.add_argument("--format", choices=("lines", "nul", "shell", "json"), default="lines", help="output format")
    parser.add_argument("--diff-filter", default=DEFAULT_DIFF_FILTER, help=f"git diff-filter letters (default: {DEFAULT_DIFF_FILTER})")
    parser.add_argument("--files", nargs="*", help="explicit file paths to filter instead of collecting git changes")
    parser.add_argument("--files-from", action="append", help="read explicit file paths from a newline-delimited file, or '-' for stdin")
    parser.add_argument("--existing", action="store_true", help="only return files that exist in the working tree")
    parser.add_argument("--relative-to", help="render output paths relative to this repo-local directory")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--skip-message", default="[SKIP] no changed files matched the requested validation scope")
    parser.add_argument("--exec", nargs=argparse.REMAINDER, help="run the command after -- with selected files appended")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.root = args.root.resolve()

    raw, files, skipped = selected_files(args)
    classification = classify(raw["selectedFiles"])  # type: ignore[arg-type]

    if args.exec is not None:
        command = list(args.exec)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("--exec requires a command after --")
        if not files:
            print(args.skip_message)
            return 0
        return subprocess.call([*command, *files])

    if args.format == "json":
        payload = {
            "root": str(args.root),
            "baseRef": args.base_ref,
            "mode": args.mode,
            "scope": args.scope,
            "baseRefAvailable": raw["baseRefAvailable"],
            "branchFiles": raw["branchFiles"],
            "stagedFiles": raw["stagedFiles"],
            "worktreeFiles": raw["worktreeFiles"],
            "untrackedFiles": raw["untrackedFiles"],
            "localFiles": raw["localFiles"],
            "selectedFiles": raw["selectedFiles"],
            "files": files,
            "skippedGeneratedStaticBinaryOrCache": skipped,
            "classification": classification,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print_files(files, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
