"""Import-graph rules: package layers, package cycles, and late imports.

The graph is built over every Python file in the packages named by ``PACKAGE_LAYERS``. Tests,
scripts, website code, and leaf root modules are out of scope. Base and head are built the same
way; existing edges are grandfathered by the base revision, so the first run does not fail on
current debt.

A layer violation is an import whose target package is not in the source package's allowed set.
A cycle is a strongly connected component with more than one package. A late import is any
cross-package import inside a function, which hides an edge the module-level graph should show.

Same-package late imports are kept as baseline credit but never reported: moving a module out
of a package must not turn its existing late imports into new cross-package debt.
"""

from __future__ import annotations

import ast
import warnings
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from scripts.code_health.config import (
    ALL_PACKAGES,
    MOVED_MODULES,
    PACKAGE_LAYERS,
    ROOT_PACKAGE,
    in_scope,
)
from scripts.code_health.gitio import Change, read_files, tracked_files
from scripts.code_health.model import MODULE_SCOPE, Finding


@dataclass(frozen=True)
class ImportRef:
    path: str
    line: int
    source_pkg: str
    target_module: str
    target_pkg: str
    late: bool


@dataclass
class PackageGraph:
    refs: list[ImportRef]
    edges: dict[str, set[str]]
    cycle_edges: dict[tuple[str, ...], int]


def package_of(path: str) -> str | None:
    """The top-level package a measured Python file belongs to, or None.

    A root module is the special ``ROOT_PACKAGE`` node: the graph keeps its late imports as
    baseline credit so a module that moves into a package does not look like new debt.
    """
    if not path.endswith(".py"):
        return None
    if "/" not in path:
        return ROOT_PACKAGE
    first = path.split("/", 1)[0]
    return first if first in PACKAGE_LAYERS else None


def graph_relevant(paths: Iterable[str]) -> bool:
    return any(package_of(path) for path in paths)


def _package_parts(path: str) -> list[str]:
    """The package containing ``path``: ``agent/sub/foo.py`` and ``agent/sub/__init__.py``
    both resolve to ``["agent", "sub"]``."""
    return path[:-3].split("/")[:-1]


def _is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _imports(path: str, text: str) -> list[tuple[int, str, bool]]:
    """(line, module, late) for every import in one file.

    ``late`` is true inside a function, the signal that the module-level graph is missing an
    edge. Imports under ``if TYPE_CHECKING:`` are type-only and never create a runtime edge.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except SyntaxError:
        return []
    package = _package_parts(path)
    found: list[tuple[int, str, bool]] = []

    def add(module: str, line: int, late: bool) -> None:
        if module:
            found.append((line, module, late))

    def walk(node: ast.AST, late: bool) -> None:
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            for child in node.orelse:
                walk(child, late)
            return
        for child in ast.iter_child_nodes(node):
            child_late = late or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            if isinstance(child, ast.Import):
                for alias in child.names:
                    add(alias.name, child.lineno, child_late)
            elif isinstance(child, ast.ImportFrom):
                if child.level == 0:
                    if child.module:
                        add(child.module, child.lineno, child_late)
                else:
                    base = package[:max(0, len(package) - (child.level - 1))]
                    if base:
                        prefix = ".".join(base)
                        add(f"{prefix}.{child.module}" if child.module else prefix,
                            child.lineno, child_late)
                    elif child.module:
                        add(child.module, child.lineno, child_late)
            walk(child, child_late)

    walk(tree, False)
    return found


def _target_package(module: str, root_modules: set[str]) -> str | None:
    first = module.split(".", 1)[0]
    if first in PACKAGE_LAYERS and first != ROOT_PACKAGE:
        return first
    return ROOT_PACKAGE if first in root_modules else None


def build_graph(paths: list[str], contents: dict[str, str]) -> PackageGraph:
    root_modules = {path[:-3] for path in paths if "/" not in path and path.endswith(".py")}
    refs: list[ImportRef] = []
    for path in paths:
        source = package_of(path)
        text = contents.get(path)
        if source is None or text is None:
            continue
        for line, module, late in _imports(path, text):
            target = _target_package(module, root_modules)
            if target is None:
                continue
            if target == source:
                # Same-package late imports are credit only: they let a module move out of a
                # package without its existing late imports reading as new debt.
                if late:
                    refs.append(ImportRef(path, line, source, module, target, late))
                continue
            refs.append(ImportRef(path, line, source, module, target, late))
    edges: dict[str, set[str]] = defaultdict(set)
    for ref in refs:
        if ref.target_pkg != ref.source_pkg and ROOT_PACKAGE not in (ref.source_pkg, ref.target_pkg):
            edges[ref.source_pkg].add(ref.target_pkg)
    return PackageGraph(refs, dict(edges), _cycle_edges(edges))


def _sccs(edges: dict[str, set[str]]) -> list[set[str]]:
    """Tarjan's strongly connected components over the package graph."""
    nodes: set[str] = set(edges)
    for targets in edges.values():
        nodes.update(targets)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    out: list[set[str]] = []
    counter = 0

    def visit(node: str) -> None:
        nonlocal counter
        index[node] = low[node] = counter
        counter += 1
        stack.append(node)
        on_stack.add(node)
        for child in edges.get(node, ()):
            if child not in index:
                visit(child)
                low[node] = min(low[node], low[child])
            elif child in on_stack:
                low[node] = min(low[node], index[child])
        if low[node] == index[node]:
            component: set[str] = set()
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.add(item)
                if item == node:
                    break
            out.append(component)

    for node in sorted(nodes):
        if node not in index:
            visit(node)
    return out


def _cycle_edges(edges: dict[str, set[str]]) -> dict[tuple[str, ...], int]:
    """Frozen per-component edge counts. A cycle may lose edges, never gain one."""
    counts: dict[tuple[str, ...], int] = {}
    for component in _sccs(edges):
        if len(component) < 2:
            continue
        key = tuple(sorted(component))
        counts[key] = sum(
            1
            for source in component
            for target in edges.get(source, ())
            if target in component and target != source
        )
    return counts


def _layer_violation(ref: ImportRef) -> bool:
    if ref.target_pkg == ref.source_pkg:
        return False
    allowed = PACKAGE_LAYERS.get(ref.source_pkg)
    return bool(allowed) and ALL_PACKAGES not in allowed and ref.target_pkg not in allowed


def _new_refs(base: PackageGraph, head: PackageGraph, renamed: dict[str, str],
              changed: set[str], keep: Callable[[ImportRef], bool]) -> list[ImportRef]:
    """Head refs that exceed the base count for their (stable path, target module) key.

    Changed files are considered first, so a finding points at the line a reviewer can see.
    """
    base_counts = Counter(
        (ref.path, MOVED_MODULES.get(ref.target_module, ref.target_module))
        for ref in base.refs if keep(ref)
    )
    ordered = sorted(
        (ref for ref in head.refs if keep(ref)),
        key=lambda ref: (0 if ref.path in changed else 1, ref.path, ref.line),
    )
    fresh: list[ImportRef] = []
    for ref in ordered:
        key = (renamed.get(ref.path, ref.path), ref.target_module)
        if base_counts[key] > 0:
            base_counts[key] -= 1
            continue
        fresh.append(ref)
    return fresh


def _layer_findings(base: PackageGraph, head: PackageGraph, renamed: dict[str, str],
                    changed: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for ref in _new_refs(base, head, renamed, changed, _layer_violation):
        allowed = ", ".join(sorted(PACKAGE_LAYERS[ref.source_pkg])) or "nothing"
        findings.append(Finding(
            ref.path, "LAYER_VIOLATION", MODULE_SCOPE, ref.line,
            f"`{ref.source_pkg}` imports `{ref.target_module}`; `{ref.target_pkg}` is not "
            f"in its layer (allowed: {allowed})",
        ))
    return findings


def _late_findings(base: PackageGraph, head: PackageGraph, renamed: dict[str, str],
                   changed: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for ref in _new_refs(base, head, renamed, changed, lambda ref: ref.late):
        if ref.target_pkg == ref.source_pkg:
            continue
        # Root modules are the temporary compatibility layer: PACKAGE_LAYERS lets them import
        # anything and ROOT_MODULE stops new ones, so a late import out of the root is migration
        # scaffolding, not hidden package debt. Package -> root still counts: callers must migrate.
        if ref.source_pkg == ROOT_PACKAGE:
            continue
        findings.append(Finding(
            ref.path, "LATE_IMPORT", MODULE_SCOPE, ref.line,
            f"`{ref.source_pkg}` imports `{ref.target_module}` inside a function; "
            "the import graph should see this edge at module scope",
        ))
    return findings


def _cycle_findings(base: PackageGraph, head: PackageGraph,
                    changed: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for key, count in sorted(head.cycle_edges.items()):
        was = base.cycle_edges.get(key, 0)
        if count <= was:
            continue
        component = set(key)
        refs = [
            ref for ref in head.refs
            if ref.source_pkg in component and ref.target_pkg in component
            and ref.path in changed
        ]
        if not refs:
            refs = [
                ref for ref in head.refs
                if ref.source_pkg in component and ref.target_pkg in component
            ]
        if not refs:
            continue
        ref = min(refs, key=lambda item: (item.path, item.line))
        verb = "new dependency cycle" if was == 0 else "dependency cycle grew"
        findings.append(Finding(
            ref.path, "IMPORT_CYCLE", MODULE_SCOPE, ref.line,
            f"{verb} among: {', '.join(key)} "
            f"(internal package edges {was} -> {count})",
        ))
    return findings


def _is_root_py(path: str) -> bool:
    return path.endswith(".py") and "/" not in path


def _root_module_findings(repo: Path, base: str, head: str | None,
                          changes: list[Change]) -> list[Finding]:
    """A new file at the repository root is new layout debt, not a finding about its contents."""
    base_root = {path for path in tracked_files(repo, base) if _is_root_py(path)}
    head_paths = {path for path in tracked_files(repo, head) if _is_root_py(path)}
    if head is None:
        head_paths.update(change.new for change in changes if change.new and _is_root_py(change.new))
    return [
        Finding(
            path, "ROOT_MODULE", MODULE_SCOPE, 1,
            "new top-level Python module; move it into the owning package, or make it an "
            "explicit compatibility shim",
        )
        for path in sorted(head_paths - base_root)
    ]


def _graph_paths(repo: Path, tree: str | None,
                 changes: list[Change] | None = None) -> list[str]:
    paths = {
        path for path in tracked_files(repo, tree)
        if package_of(path) and in_scope(path) == "py"
    }
    if changes is not None:
        paths.update(change.new for change in changes if change.new and package_of(change.new))
    return sorted(paths)


def compare_imports(repo: Path, base: str, head: str | None,
                    changes: list[Change]) -> list[Finding]:
    """The import-graph verdict for ``head`` against ``base``."""
    base_paths = _graph_paths(repo, base)
    head_paths = _graph_paths(repo, head, changes)
    base_graph = build_graph(base_paths, read_files(repo, base, base_paths))
    head_graph = build_graph(head_paths, read_files(repo, head, head_paths))
    renamed = {change.new: change.old for change in changes if change.new and change.old}
    changed = {change.new for change in changes if change.new}
    return (
        _layer_findings(base_graph, head_graph, renamed, changed)
        + _late_findings(base_graph, head_graph, renamed, changed)
        + _cycle_findings(base_graph, head_graph, changed)
        + _root_module_findings(repo, base, head, changes)
    )
