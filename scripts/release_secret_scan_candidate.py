#!/usr/bin/env python3
"""Fast full-tree scanner for release_secret_scan.sh candidate mode."""

from __future__ import annotations

import argparse
import io
import json
import re
import tarfile
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


SKIP_PARTS = {
    ".git",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    ".cache",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "build",
    "coverage",
    "htmlcov",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tgz", ".bz2", ".xz", ".7z", ".tar", ".db", ".sqlite", ".sqlite3", ".duckdb",
    ".parquet", ".pkl", ".pyc", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov",
}
DIRECT_PATTERNS = (
    (re.compile(r"BEGIN\s+(?:(?:RSA|DSA|EC|OPENSSH|PGP)\s+)?PRIVATE\s+KEY", re.I), "private key material"),
    (re.compile(r"(?<![A-Za-z0-9_])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9_])"), "AWS access key id"),
    (re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{24,}(?![A-Za-z0-9_])"), "OpenAI-style API key"),
    (re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9_]{24,}(?![A-Za-z0-9_])"), "GitHub token"),
    (re.compile(r"(?<![A-Za-z0-9_])xox[baprs]-[A-Za-z0-9-]{20,}(?![A-Za-z0-9_])"), "Slack token"),
    (re.compile(r"(?<![A-Za-z0-9_])AIza[0-9A-Za-z_-]{30,}(?![A-Za-z0-9_])"), "Google API key"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.I), "bearer token"),
)
ASSIGNMENT_RE = re.compile(
    r"(?:^|[^A-Za-z0-9_.-])"
    r"([A-Za-z0-9_.-]*(?:api[_-]?key|token|secret|password|passwd|credential|credentials|"
    r"client[_-]?secret|access[_-]?key|secret[_-]?key|private[_-]?key|session[_-]?token|bearer)"
    r"[A-Za-z0-9_.-]*)\s*[:=]\s*([^\s#][^#]*)",
    re.I,
)
PRIVATE_PATH_RE = re.compile(r"(?:/Users/[^/\s\"']+|/home/[^/\s\"']+|[A-Za-z]:\\Users\\[^\\\s\"']+)")
PRODUCTION_PREFIXES = (
    "api/", "src/", "data_provider/", "bot/", "apps/dsa-web/src/", "apps/dsa-desktop/src/",
    "docker/", ".github/workflows/",
)


def _skip_path(path: str) -> bool:
    value = PurePosixPath(path)
    return bool(SKIP_PARTS.intersection(value.parts)) or value.suffix.lower() in SKIP_SUFFIXES


def _is_test_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        path.startswith("validation/")
        or "tests" in parts
        or "__tests__" in parts
        or ".test." in path
        or ".spec." in path
    )


def _private_path_applies(path: str) -> bool:
    if _is_test_path(path):
        return False
    return path in {"main.py", "server.py"} or path.startswith(PRODUCTION_PREFIXES)


def _safe_placeholder(raw: str) -> bool:
    value = raw.split("#", 1)[0].strip().strip("\"'").rstrip(",;").strip()
    lower = value.lower()
    if "os.environ/" in lower or "(" in value or ")" in value or " + " in value:
        return True
    if not value or lower in {
        "none", "null", "nil", "true", "false", "changeme", "change_me", "change-me", "placeholder",
        "todo", "tbd", "example", "sample", "dummy", "mock", "fake", "x", "xx", "xxx",
    }:
        return True
    markers = ("your_", "your-", "your ", "example", "sample", "dummy", "mock", "fake", "unit-test", "test-only", "not-a-real", "redacted", "masked")
    return (
        any(marker in lower for marker in markers)
        or bool(
            re.fullmatch(
                r"\$\{\{\s*(?:github|secrets|inputs|needs|steps|env|vars)\."
                r"[A-Za-z_][A-Za-z0-9_.-]*\s*}}",
                value,
            )
        )
        or (value.startswith("<") and value.endswith(">"))
        or bool(re.fullmatch(r"\$\{?[A-Za-z_][A-Za-z0-9_]*}?", value))
        or bool(re.fullmatch(r"\$env:[A-Za-z_][A-Za-z0-9_]*", value, re.I))
    )


def _assignment_rule(path: str, line: str) -> str | None:
    if _is_test_path(path) or PurePosixPath(path).suffix.lower() in {
        ".md", ".rst", ".txt", ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sh", ".ps1",
    }:
        return None
    match = ASSIGNMENT_RE.search(line)
    if not match:
        return None
    key, value = match.groups()
    if _safe_placeholder(value):
        return None
    lower_key = key.lower()
    if "password" in lower_key or "passwd" in lower_key:
        return "non-empty password assignment"
    normalized = value.strip().strip("\"'")
    if len(normalized) >= 16 and re.search(r"[A-Za-z]", normalized) and re.search(r"[0-9+/=_.-]", normalized):
        return "secret-like credential assignment"
    return None


def _findings(path: str, text: str, *, strict_private_paths: bool = False) -> Iterable[tuple[int, str]]:
    test_fixture = _is_test_path(path)
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        seen: set[str] = set()
        if not test_fixture:
            for pattern, rule in DIRECT_PATTERNS:
                if pattern.search(line) and rule not in seen:
                    seen.add(rule)
                    yield line_number, rule
        if (strict_private_paths or _private_path_applies(path)) and PRIVATE_PATH_RE.search(line):
            yield line_number, "private absolute path"
        assignment_rule = _assignment_rule(path, line)
        if assignment_rule and assignment_rule not in seen:
            yield line_number, assignment_rule


def scan(root: Path, file_list: Path) -> tuple[list[str], int, int]:
    findings: list[str] = []
    scanned = 0
    private_findings = 0
    for relative in file_list.read_text(encoding="utf-8").splitlines():
        if not relative or _skip_path(relative):
            continue
        path = root / relative
        if not path.is_file():
            continue
        content = path.read_bytes()
        if not content or b"\0" in content[:8192]:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for line_number, rule in _findings(relative, text):
            if rule == "private absolute path":
                private_findings += 1
            findings.append(f"[FAIL] {relative}:{line_number} [candidate] {rule}")
    return sorted(set(findings)), scanned, private_findings


def _scan_content(
    *,
    label: str,
    content: bytes,
    strict_private_paths: bool,
) -> tuple[list[str], int]:
    if not content:
        return [], 0
    text = content.decode("utf-8", errors="ignore")
    findings: list[str] = []
    private_findings = 0
    for line_number, rule in _findings(label, text, strict_private_paths=strict_private_paths):
        private_findings += int(rule == "private absolute path")
        findings.append(f"[FAIL] {label}:{line_number} [evidence] {rule}")
    return findings, private_findings


def _scan_archive(
    *,
    label: str,
    content: bytes,
    strict_private_paths: bool,
    depth: int = 0,
) -> tuple[list[str], int, int]:
    if depth > 4:
        raise ValueError(f"archive_nesting_too_deep:{label}")
    try:
        archive = tarfile.open(fileobj=io.BytesIO(content), mode="r:*")
    except tarfile.ReadError:
        findings, private = _scan_content(
            label=label,
            content=content,
            strict_private_paths=strict_private_paths,
        )
        return findings, 1, private
    findings: list[str] = []
    scanned = 0
    private_findings = 0
    with archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"archive_member_unreadable:{label}!{member.name}")
            member_content = handle.read()
            member_label = f"{label}!{member.name}"
            nested_findings, nested_scanned, nested_private = _scan_archive(
                label=member_label,
                content=member_content,
                strict_private_paths=strict_private_paths,
                depth=depth + 1,
            )
            findings.extend(nested_findings)
            scanned += nested_scanned
            private_findings += nested_private
    return findings, scanned, private_findings


def scan_tree(root: Path) -> tuple[list[str], int, int]:
    if not root.is_dir():
        raise ValueError("evidence_root_missing")
    findings: list[str] = []
    scanned = 0
    private_findings = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        label = f"{root.name}/{relative}"
        strict = path.name != "source.tar.gz"
        nested_findings, nested_scanned, nested_private = _scan_archive(
            label=label,
            content=path.read_bytes(),
            strict_private_paths=strict,
        )
        findings.extend(nested_findings)
        scanned += nested_scanned
        private_findings += nested_private
    return sorted(set(findings)), scanned, private_findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--files", type=Path)
    source.add_argument("--scan-tree", action="store_true")
    parser.add_argument("--findings", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    findings, scanned, private_findings = (
        scan_tree(args.root) if args.scan_tree else scan(args.root, args.files)
    )
    args.findings.write_text("\n".join(findings) + ("\n" if findings else ""), encoding="utf-8")
    args.summary.write_text(
        json.dumps({"fileCount": scanned, "privatePathFindings": private_findings}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
