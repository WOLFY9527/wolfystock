"""Deterministic AST collectors for architecture boundary debt."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence


SERVICE_API_SCHEMA_FAMILY = "serviceToApiSchemaEdges"
DIRECT_STORAGE_FAMILY = "directStorageConsumers"
PROVIDER_HEAVY_FAMILY = "providerHeavyConstructionPoints"
FAMILY_BASELINE_COUNTS = {
    DIRECT_STORAGE_FAMILY: 51,
    PROVIDER_HEAVY_FAMILY: 21,
    SERVICE_API_SCHEMA_FAMILY: 53,
}

PRODUCTION_ROOTS = ("api", "bot", "data_provider", "src")
PROVIDER_IMPORT_PREFIXES = (
    "data_provider",
    "src.services.market_cache",
    "yfinance",
)
# This module is the provider-owned cache implementation, not a consumer-domain
# construction point. The T457 inventory counts the remaining 21 service files.
PROVIDER_OWNED_SERVICE_PATHS = frozenset(
    {"src/services/market_cache_redis_backend.py"}
)


def _matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def _is_type_checking_guard(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "TYPE_CHECKING") or (
        isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING"
    )


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, prefixes: Sequence[str], *, include_type_checking: bool) -> None:
        self.prefixes = prefixes
        self.include_type_checking = include_type_checking
        self.modules: set[str] = set()

    def visit_If(self, node: ast.If) -> None:
        if not self.include_type_checking and _is_type_checking_guard(node.test):
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level != 0 or not node.module:
            return
        if any(_matches_prefix(node.module, prefix) for prefix in self.prefixes):
            self._record(node.module)
            return
        for alias in node.names:
            self._record(f"{node.module}.{alias.name}")

    def _record(self, module: str) -> None:
        if any(_matches_prefix(module, prefix) for prefix in self.prefixes):
            self.modules.add(module)


class _ProviderImportCollector(_ImportCollector):
    def __init__(self) -> None:
        super().__init__(PROVIDER_IMPORT_PREFIXES, include_type_checking=False)
        self.bindings: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if any(_matches_prefix(alias.name, prefix) for prefix in self.prefixes):
                self.modules.add(alias.name)
                self.bindings.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level != 0 or not node.module:
            return
        if any(_matches_prefix(node.module, prefix) for prefix in self.prefixes):
            self.modules.add(node.module)
            self.bindings.update(alias.asname or alias.name for alias in node.names)
            return
        for alias in node.names:
            candidate = f"{node.module}.{alias.name}"
            if any(_matches_prefix(candidate, prefix) for prefix in self.prefixes):
                self.modules.add(candidate)
                self.bindings.add(alias.asname or alias.name)


def _callable_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _callable_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


class _ProviderConstructionCollector(ast.NodeVisitor):
    def __init__(self, bindings: set[str]) -> None:
        self.bindings = bindings
        self.scope: list[str] = []
        self.calls: Counter[tuple[str, str]] = Counter()

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_guard(node.test):
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node.name, node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node.name, node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node.name, node)

    def _visit_scope(
        self,
        name: str,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self.scope.append(name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        callable_name = _callable_name(node.func)
        if callable_name and callable_name.split(".", 1)[0] in self.bindings:
            scope = ".".join(self.scope) if self.scope else "<module>"
            self.calls[(scope, callable_name)] += 1
        self.generic_visit(node)


def _imports_for_file(
    path: Path,
    prefixes: Sequence[str],
    *,
    include_type_checking: bool = True,
) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    collector = _ImportCollector(prefixes, include_type_checking=include_type_checking)
    collector.visit(tree)
    return collector.modules


def _python_files(root: Path, relative_root: str) -> Iterable[Path]:
    search_root = root / relative_root
    if search_root.is_dir():
        yield from sorted(search_root.rglob("*.py"))


def _collect_service_api_schema_edges(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in _python_files(root, "src/services"):
        source = path.relative_to(root).as_posix()
        targets = _imports_for_file(path, ("api.v1.schemas",))
        entries.extend({"source": source, "target": target} for target in sorted(targets))
    return sorted(entries, key=lambda entry: (entry["source"], entry["target"]))


def _collect_direct_storage_consumers(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative_root in PRODUCTION_ROOTS:
        for path in _python_files(root, relative_root):
            relative_path = path.relative_to(root)
            if relative_path.parts[:2] == ("src", "repositories"):
                continue
            if _imports_for_file(path, ("src.storage",)):
                entries.append({"path": relative_path.as_posix()})
    return sorted(entries, key=lambda entry: entry["path"])


def _collect_provider_heavy_construction_points(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in _python_files(root, "src/services"):
        relative_path = path.relative_to(root).as_posix()
        if relative_path in PROVIDER_OWNED_SERVICE_PATHS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        import_collector = _ProviderImportCollector()
        import_collector.visit(tree)
        imports = sorted(import_collector.modules)
        if not imports:
            continue
        construction_collector = _ProviderConstructionCollector(import_collector.bindings)
        construction_collector.visit(tree)
        constructions = [
            {"callable": callable_name, "count": count, "scope": scope}
            for (scope, callable_name), count in sorted(construction_collector.calls.items())
        ]
        entries.append(
            {
                "constructions": constructions,
                "imports": imports,
                "path": relative_path,
            }
        )
    return sorted(
        entries,
        key=lambda entry: (
            entry["path"],
            tuple(entry["imports"]),
            tuple(
                (item["scope"], item["callable"], item["count"])
                for item in entry["constructions"]
            ),
        ),
    )


_COLLECTORS = {
    DIRECT_STORAGE_FAMILY: _collect_direct_storage_consumers,
    PROVIDER_HEAVY_FAMILY: _collect_provider_heavy_construction_points,
    SERVICE_API_SCHEMA_FAMILY: _collect_service_api_schema_edges,
}


def collect_family(root: Path, family: str) -> list[dict[str, Any]]:
    """Collect one independently attributable debt family."""

    try:
        collector = _COLLECTORS[family]
    except KeyError as exc:
        raise ValueError(f"unknown debt family: {family}") from exc
    return collector(Path(root))
