"""Deterministic AST collectors for architecture boundary debt."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


SERVICE_API_SCHEMA_FAMILY = "serviceToApiSchemaEdges"
DIRECT_STORAGE_FAMILY = "directStorageConsumers"
PROVIDER_HEAVY_FAMILY = "providerHeavyConstructionPoints"
FAMILY_NAMES = frozenset(
    {
        DIRECT_STORAGE_FAMILY,
        PROVIDER_HEAVY_FAMILY,
        SERVICE_API_SCHEMA_FAMILY,
    }
)
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
COLLECTOR_VERSION = "t635-source-graph-v1"


@dataclass(frozen=True, slots=True)
class ProviderConstruction:
    callable: str
    count: int
    scope: str


@dataclass(frozen=True, slots=True)
class SourceFileGraph:
    path: str
    storage_imports: tuple[str, ...]
    provider_imports: tuple[str, ...]
    provider_constructions: tuple[ProviderConstruction, ...]
    service_schema_imports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceGraph:
    root: str
    input_digest: str
    content_digest: str
    files: tuple[SourceFileGraph, ...]

    def family_entries(self, family: str) -> list[dict[str, Any]]:
        return _family_entries(self, family)


_SOURCE_GRAPH_CACHE: dict[tuple[str, str, str, str], SourceGraph] = {}


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


def _imports_for_tree(
    tree: ast.AST,
    prefixes: Sequence[str],
    *,
    include_type_checking: bool = True,
) -> set[str]:
    collector = _ImportCollector(prefixes, include_type_checking=include_type_checking)
    collector.visit(tree)
    return collector.modules


def _python_files(root: Path, relative_root: str) -> Iterable[Path]:
    search_root = root / relative_root
    if search_root.is_dir():
        yield from sorted(search_root.rglob("*.py"))


def _source_files(root: Path) -> tuple[tuple[str, Path], ...]:
    files: dict[str, Path] = {}
    for relative_root in PRODUCTION_ROOTS:
        for path in _python_files(root, relative_root):
            relative_path = path.relative_to(root)
            if relative_path.parts[:2] == ("src", "repositories"):
                continue
            files[relative_path.as_posix()] = path
    return tuple(sorted(files.items()))


def _snapshot_source_inputs(
    root: Path,
) -> tuple[tuple[tuple[str, bytes], ...], str]:
    digest = hashlib.sha256()
    inputs: list[tuple[str, bytes]] = []
    for relative_path, path in _source_files(root):
        content = path.read_bytes()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
        inputs.append((relative_path, content))
    return tuple(inputs), digest.hexdigest()


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_GRAPH_CONFIG_DIGEST = _canonical_digest(
    {
        "productionRoots": PRODUCTION_ROOTS,
        "providerImportPrefixes": PROVIDER_IMPORT_PREFIXES,
        "providerOwnedServicePaths": sorted(PROVIDER_OWNED_SERVICE_PATHS),
        "serviceSchemaPrefix": "api.v1.schemas",
        "storagePrefix": "src.storage",
    }
)


def _build_source_graph(
    root: Path,
    source_inputs: tuple[tuple[str, bytes], ...],
    input_digest: str,
) -> SourceGraph:
    files: list[SourceFileGraph] = []
    for relative_path, content in source_inputs:
        source = content.decode("utf-8")
        path = root / relative_path
        tree = ast.parse(source, filename=str(path))
        storage_imports = tuple(sorted(_imports_for_tree(tree, ("src.storage",))))
        provider_imports: tuple[str, ...] = ()
        provider_constructions: tuple[ProviderConstruction, ...] = ()
        service_schema_imports: tuple[str, ...] = ()
        if relative_path.startswith("src/services/"):
            service_schema_imports = tuple(
                sorted(_imports_for_tree(tree, ("api.v1.schemas",)))
            )
            import_collector = _ProviderImportCollector()
            import_collector.visit(tree)
            provider_imports = tuple(sorted(import_collector.modules))
            construction_collector = _ProviderConstructionCollector(
                import_collector.bindings
            )
            construction_collector.visit(tree)
            provider_constructions = tuple(
                ProviderConstruction(
                    callable=callable_name,
                    count=count,
                    scope=scope,
                )
                for (scope, callable_name), count in sorted(
                    construction_collector.calls.items()
                )
            )
        files.append(
            SourceFileGraph(
                path=relative_path,
                storage_imports=storage_imports,
                provider_imports=provider_imports,
                provider_constructions=provider_constructions,
                service_schema_imports=service_schema_imports,
            )
        )
    ordered_files = tuple(files)
    content_digest = _canonical_digest(
        [
            {
                "path": file.path,
                "providerConstructions": [
                    {
                        "callable": item.callable,
                        "count": item.count,
                        "scope": item.scope,
                    }
                    for item in file.provider_constructions
                ],
                "providerImports": file.provider_imports,
                "serviceSchemaImports": file.service_schema_imports,
                "storageImports": file.storage_imports,
            }
            for file in ordered_files
        ]
    )
    return SourceGraph(
        root=root.as_posix(),
        input_digest=input_digest,
        content_digest=content_digest,
        files=ordered_files,
    )


def collect_source_graph(root: Path) -> SourceGraph:
    """Collect one immutable, deterministic source graph per exact input identity."""

    resolved_root = Path(root).resolve()
    source_inputs, input_digest = _snapshot_source_inputs(resolved_root)
    cache_key = (
        resolved_root.as_posix(),
        COLLECTOR_VERSION,
        _GRAPH_CONFIG_DIGEST,
        input_digest,
    )
    if cache_key not in _SOURCE_GRAPH_CACHE:
        _SOURCE_GRAPH_CACHE[cache_key] = _build_source_graph(
            resolved_root,
            source_inputs,
            input_digest,
        )
    return _SOURCE_GRAPH_CACHE[cache_key]


def _family_entries(graph: SourceGraph, family: str) -> list[dict[str, Any]]:
    if family not in FAMILY_NAMES:
        raise ValueError(f"unknown debt family: {family}")
    if family == DIRECT_STORAGE_FAMILY:
        return [
            {"path": file.path}
            for file in graph.files
            if file.storage_imports
        ]
    if family == PROVIDER_HEAVY_FAMILY:
        return [
            {
                "constructions": [
                    {
                        "callable": item.callable,
                        "count": item.count,
                        "scope": item.scope,
                    }
                    for item in file.provider_constructions
                ],
                "imports": list(file.provider_imports),
                "path": file.path,
            }
            for file in graph.files
            if file.path.startswith("src/services/")
            and file.path not in PROVIDER_OWNED_SERVICE_PATHS
            and file.provider_imports
        ]
    return [
        {"source": file.path, "target": target}
        for file in graph.files
        for target in file.service_schema_imports
    ]
