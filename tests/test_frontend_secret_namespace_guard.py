# -*- coding: utf-8 -*-
"""Static guards for frontend provider-secret namespace boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = REPO_ROOT / "apps" / "dsa-web"
FRONTEND_SCAN_ROOTS = (
    FRONTEND_ROOT / "src",
    FRONTEND_ROOT / "e2e",
    FRONTEND_ROOT / "scripts",
)
FRONTEND_SCAN_FILES = (FRONTEND_ROOT / "package.json",)
FRONTEND_SCAN_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json"}
FRONTEND_SKIP_DIRS = {
    "node_modules",
    "dist",
    "coverage",
    "playwright-report",
    "test-results",
    ".vite",
}

BACKEND_ONLY_PROVIDER_SECRET_NAMES = ("POLYGON_API_KEY",)
FRONTEND_VITE_POLYGON_ENV_RE = re.compile(r"\bVITE_[A-Z0-9_]*POLYGON[A-Z0-9_]*\b")


@dataclass(frozen=True)
class FrontendSecretNamespaceViolation:
    path: Path
    line_number: int
    env_name: str
    reason: str


def _is_frontend_path(path: Path) -> bool:
    try:
        relative = path.relative_to(FRONTEND_ROOT)
    except ValueError:
        return False
    return not any(part in FRONTEND_SKIP_DIRS for part in relative.parts)


def _iter_frontend_source_files() -> list[Path]:
    files: list[Path] = []
    for root in FRONTEND_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() or path.suffix not in FRONTEND_SCAN_SUFFIXES:
                continue
            if _is_frontend_path(path):
                files.append(path)
    for path in FRONTEND_SCAN_FILES:
        if path.exists():
            files.append(path)
    return sorted(files)


def _format_violation(violation: FrontendSecretNamespaceViolation) -> str:
    path = violation.path
    try:
        path = path.relative_to(REPO_ROOT)
    except ValueError:
        pass
    return f"{path}:{violation.line_number}: {violation.env_name} ({violation.reason})"


def collect_frontend_provider_secret_namespace_violations(
    sources: Mapping[Path, str] | None = None,
) -> list[FrontendSecretNamespaceViolation]:
    if sources is None:
        sources = {path: path.read_text(encoding="utf-8") for path in _iter_frontend_source_files()}

    violations: list[FrontendSecretNamespaceViolation] = []
    backend_only_patterns = {
        env_name: re.compile(rf"\b{re.escape(env_name)}\b")
        for env_name in BACKEND_ONLY_PROVIDER_SECRET_NAMES
    }

    for path, text in sources.items():
        if not _is_frontend_path(path):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in FRONTEND_VITE_POLYGON_ENV_RE.finditer(line):
                violations.append(
                    FrontendSecretNamespaceViolation(
                        path=path,
                        line_number=line_number,
                        env_name=match.group(0),
                        reason=(
                            "frontend VITE namespace must not expose "
                            "backend-only Polygon provider secrets"
                        ),
                    )
                )
            for env_name, pattern in backend_only_patterns.items():
                if pattern.search(line):
                    violations.append(
                        FrontendSecretNamespaceViolation(
                            path=path,
                            line_number=line_number,
                            env_name=env_name,
                            reason="backend-only provider secret name referenced from frontend",
                        )
                    )

    return violations


def test_frontend_provider_secret_namespace_guard_rejects_polygon_vite_env_names() -> None:
    violations = collect_frontend_provider_secret_namespace_violations(
        {
            REPO_ROOT / "apps/dsa-web/src/demo.ts": (
                "const key = import.meta.env.VITE_POLYGON_API_KEY;\n"
                "const name = 'VITE_PUBLIC_POLYGON_TOKEN';\n"
            )
        }
    )

    assert {violation.env_name for violation in violations} == {
        "VITE_POLYGON_API_KEY",
        "VITE_PUBLIC_POLYGON_TOKEN",
    }


def test_frontend_provider_secret_namespace_guard_rejects_backend_only_provider_secret_names() -> None:
    violations = collect_frontend_provider_secret_namespace_violations(
        {
            REPO_ROOT / "apps/dsa-web/src/settings.tsx": (
                "const forbidden = 'POLYGON_API_KEY';\n"
            )
        }
    )

    assert {violation.env_name for violation in violations} == {"POLYGON_API_KEY"}


def test_frontend_provider_secret_namespace_guard_allows_backend_only_polygon_usage() -> None:
    violations = collect_frontend_provider_secret_namespace_violations(
        {
            REPO_ROOT / "src/services/polygon_us_breadth_provider.py": (
                "credential = os.getenv('POLYGON_API_KEY')\n"
            )
        }
    )

    assert violations == []


def test_frontend_tree_does_not_reference_backend_only_provider_secret_names() -> None:
    violations = collect_frontend_provider_secret_namespace_violations()

    assert violations == [], "\n".join(_format_violation(violation) for violation in violations)
