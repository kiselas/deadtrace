"""Python-specific fact extraction built on the standard-library ``ast`` module.

This module turns source text into the generic execution graph consumed by
``deadtrace.core``. Syntax-tree objects stay inside this frontend boundary.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from functools import lru_cache
from typing import Any, NamedTuple

from deadtrace.core import (
    EdgeKind,
    ExecutionEdge,
    NodeId,
    NodeKind,
    SemanticGraph,
    SemanticNode,
    UnknownBoundary,
)
from deadtrace.inventory import (
    DEFINITION_TYPES,
    DefinitionNode,
    ParsedSource,
    SourceText,
    child_statements,
    iter_definitions,
    parse_source,
)
from deadtrace.nominal_types import NOMINAL_FAMILIES, ROOT_BASES, may_supply_nominal_value
from deadtrace.receiver_flow import (
    EXTERNAL_RECEIVER,
    UNKNOWN_RECEIVER,
    ReceiverState,
    ReceiverValue,
    StringValue,
)
from deadtrace.scanner import ParsedCollection, SourceCollection, SourceUnit
from deadtrace.timing import StageTimings

type FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

_INSIGNIFICANT_TOKENS = frozenset(
    {tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.COMMENT, tokenize.INDENT}
)

TRANSPARENT_DECORATORS = frozenset(
    {
        "abc.abstractmethod",
        "classmethod",
        "contextlib.asynccontextmanager",
        "contextlib.contextmanager",
        "dataclasses.dataclass",
        "enum.unique",
        "functools.cache",
        "functools.cached_property",
        "functools.lru_cache",
        "functools.total_ordering",
        "functools.wraps",
        "property",
        "staticmethod",
        "typing.final",
        "typing.no_type_check",
        "typing.overload",
        "typing.override",
        "typing.runtime_checkable",
        "typing_extensions.final",
        "typing_extensions.overload",
        "typing_extensions.override",
        "typing_extensions.runtime_checkable",
    }
)
"""Decorators that return the function or a wrapper reached through its name, never a registry."""

HOOK_FREE_BASES = frozenset(
    {
        "abc.ABC",
        "bytearray",
        "bytes",
        "complex",
        "dict",
        "dishka.Provider",
        "float",
        "frozenset",
        "int",
        "list",
        "object",
        "pydantic.BaseModel",
        "pydantic.main.BaseModel",
        "set",
        "str",
        "tuple",
        "typing.Generic",
        "typing.NamedTuple",
        "typing.Protocol",
        "typing.TypedDict",
        "typing_extensions.NamedTuple",
        "typing_extensions.Protocol",
        "typing_extensions.TypedDict",
    }
)
"""External bases that call no methods of their subclasses beyond special methods and hooks that
a capability models. Builtin exception classes are treated the same way."""

ENUM_BASES = frozenset(
    {"enum.Enum", "enum.Flag", "enum.IntEnum", "enum.IntFlag", "enum.ReprEnum", "enum.StrEnum"}
)
ENUM_HOOKS = frozenset({"_generate_next_value_", "_missing_"})
PYTEST_REGISTRATIONS = frozenset({"pytest.fixture", "pytest_asyncio.fixture"})


def is_fixture_decorator(name: str) -> bool:
    """Whether an expanded decorator name registers a pytest fixture, sync or asyncio."""

    return name.endswith("pytest.fixture") or name.endswith("pytest_asyncio.fixture")


CONFIGURATION_CLASS_NAMES = frozenset({"Config", "Meta"})
"""Nested classes that bases outside the project read as options even when they call no methods:
Pydantic's ``Config`` and the ``Meta`` of model and serializer libraries."""
DYNAMIC_IMPORTS = frozenset(
    {"__import__", "importlib.__import__", "importlib.import_module", "runpy.run_module"}
)
PATH_IMPORTS = frozenset(
    {
        "importlib.machinery.SourceFileLoader",
        "importlib.util.spec_from_file_location",
        "runpy.run_path",
    }
)
"""Calls that load a module from a file path, which may be any project file (ADR-0017)."""
LOADED_MODULE_NAMES = frozenset({"__module__", "__name__", "__package__"})
DESERIALIZERS = frozenset(
    {
        "_pickle.load",
        "_pickle.loads",
        "cloudpickle.load",
        "cloudpickle.loads",
        "dill.load",
        "dill.loads",
        "joblib.load",
        "jsonpickle.decode",
        "jsonpickle.loads",
        "numpy.load",
        "pandas.read_pickle",
        "pickle.Unpickler",
        "pickle.load",
        "pickle.loads",
        "shelve.open",
        "torch.load",
        "yaml.full_load",
        "yaml.load",
        "yaml.load_all",
        "yaml.unsafe_load",
        "yaml.unsafe_load_all",
    }
)
"""Calls that may build instances of any project class from data (ADR-0022)."""
BUILTIN_MANAGERS = frozenset({"open", "memoryview"})
"""Builtins whose results used as context managers are objects from outside the project."""
"""Names of modules that are loaded already when code can read them (ADR-0018)."""
OVERLOAD_DECORATORS = frozenset({"typing.overload", "typing_extensions.overload"})
INSPECTING_CONSUMERS = frozenset({"isinstance", "issubclass"})
"""Consumers that inspect a class they receive without calling anything on it."""
UNITTEST_RUNNERS = frozenset({"unittest.main", "unittest.TestProgram"})
"""Calls that run the ``TestCase`` classes of the module they are in."""
CONTAINER_TYPES = frozenset(
    {"list", "dict", "set", "deque", "defaultdict", "OrderedDict", "List", "Dict", "Set", "Deque"}
)
"""Builtin and typing containers: what a value stored in one is later called through is judged at
the call that reads it back."""
CONTAINER_STORES = frozenset(
    {"append", "appendleft", "add", "extend", "extendleft", "insert", "setdefault", "update"}
)
"""Methods of a container that only keep the values they receive."""

_COMPOUND_STATEMENTS = (
    *DEFINITION_TYPES,
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
    ast.Match,
)


@dataclass(frozen=True, slots=True)
class ImportBinding:
    local_name: str
    target: str
    is_module: bool
    line: int
    conditional: bool = False
    """Whether the import sits in a nested block, such as ``try`` or ``if``, of its scope."""


@dataclass(frozen=True, slots=True)
class ParameterInfo:
    name: str
    annotation: ast.expr | None
    default: ast.expr | None


@dataclass(slots=True)
class PythonSymbol:
    id: NodeId
    module: str
    qualified_name: str
    name: str
    kind: NodeKind
    path: str
    line: int
    occurrence: int
    owner: NodeId | None
    owner_qualified_name: str | None
    node: DefinitionNode
    parameters: tuple[ParameterInfo, ...] = ()
    return_annotation: ast.expr | None = None
    decorators: tuple[ast.expr, ...] = ()
    bases: tuple[ast.expr, ...] = ()


@dataclass(slots=True)
class PythonModule:
    name: str
    path: str
    node_id: NodeId
    unit: SourceUnit
    tree: ast.Module
    statement_lines: Mapping[ast.stmt, int]
    """Start line of every top-level simple statement."""
    text: SourceText
    imports: dict[str, ImportBinding] = field(default_factory=dict)
    """Names the module's imports bind at its top level, nested blocks included; the last wins."""
    symbols: list[PythonSymbol] = field(default_factory=list)
    star_imports: tuple[str, ...] = ()
    """Project modules whose names ``from module import *`` binds at the top level."""
    import_alternatives: dict[str, tuple[ImportBinding, ...]] = field(default_factory=dict)
    """Top-level names that several imports bind, one in a nested block, with every binding."""


@dataclass(frozen=True, slots=True)
class PythonLimitation:
    code: str
    path: str
    line: int
    message: str
    origin: NodeId | None = None


class CallArgument(NamedTuple):
    """One argument of a call: ``star`` is ``""``, ``"*"``, or ``"**"``."""

    value: ast.expr
    keyword: str | None
    star: str


class SymbolIndex:
    """Lookups over a finished symbol table, built once instead of scanning it per query.

    Every answer lists symbols in symbol-table order, so ties resolve exactly as a scan over the
    table would. The table must not change after the index is built.
    """

    __slots__ = ("_by_full_name", "_members", "_sorted_full_names")

    def __init__(self, symbols: Iterable[PythonSymbol]) -> None:
        by_full_name: dict[str, list[PythonSymbol]] = {}
        members: dict[NodeId, list[PythonSymbol]] = {}
        for symbol in symbols:
            by_full_name.setdefault(f"{symbol.module}.{symbol.qualified_name}", []).append(symbol)
            if symbol.owner is not None:
                members.setdefault(symbol.owner, []).append(symbol)
        self._by_full_name = {name: tuple(items) for name, items in by_full_name.items()}
        self._members = {owner: tuple(items) for owner, items in members.items()}
        self._sorted_full_names = sorted(self._by_full_name)

    def named(self, full_name: str) -> tuple[PythonSymbol, ...]:
        """Symbols whose ``module.qualified_name`` is exactly ``full_name``."""

        return self._by_full_name.get(full_name, ())

    def resolve(self, full_name: str) -> PythonSymbol | None:
        """The last occurrence named ``full_name``, the first of equals on a tie."""

        matches = self._by_full_name.get(full_name)
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        return max(matches, key=lambda item: item.occurrence)

    def members(self, owner: NodeId) -> tuple[PythonSymbol, ...]:
        """Symbols defined directly inside ``owner``."""

        return self._members.get(owner, ())

    def under(self, prefix: str) -> Iterator[PythonSymbol]:
        """Symbols whose full name starts with ``prefix``, in full-name order."""

        names = self._sorted_full_names
        position = bisect_left(names, prefix)
        while position < len(names) and names[position].startswith(prefix):
            yield from self._by_full_name[names[position]]
            position += 1


@dataclass(slots=True)
class PythonProgram:
    graph: SemanticGraph
    modules: dict[str, PythonModule]
    symbols: dict[NodeId, PythonSymbol]
    limitations: tuple[PythonLimitation, ...]
    index: SymbolIndex = field(repr=False, compare=False)
    """Index over ``symbols``, which is complete and never changes once the program is built."""
    _through_imports: dict[str, PythonSymbol | None] = field(
        default_factory=dict, repr=False, compare=False
    )

    def resolve_symbol(self, target: str) -> PythonSymbol | None:
        """Resolve ``module:qualname`` or a fully-qualified name, following re-exports."""

        full_name = target.replace(":", ".", 1) if ":" in target else target
        return self.index.resolve(full_name) or resolve_through_imports(
            self.modules, self.index, full_name, self._through_imports
        )


def build_python_program(
    collection: SourceCollection,
    *,
    report_exclude: Sequence[str] = (),
    timings: StageTimings | None = None,
    parsed: ParsedCollection | None = None,
) -> PythonProgram:
    """Extract a deterministic project graph from a stable source collection.

    ``parsed`` supplies each unit's shared parse; units missing from it are parsed here.
    """

    timings = timings if timings is not None else StageTimings()
    modules: dict[str, PythonModule] = {}
    symbols: dict[NodeId, PythonSymbol] = {}
    limitations: list[PythonLimitation] = []
    nodes: list[SemanticNode] = []

    entries: list[tuple[SourceUnit, ParsedSource]] = []
    for unit in collection.units:
        entry = parsed.get(unit.path) if parsed is not None else None
        if entry is None:
            try:
                with timings.stage("frontend.parse"):
                    entry = parse_source(unit.source)
            except SyntaxError as error:
                entry = error
        if isinstance(entry, SyntaxError):
            timings.count("frontend.parse_failures")
            continue
        entries.append((unit, entry))
    keep_src = _imports_src_package(entries)

    for unit, entry in entries:
        timings.count("frontend.modules")
        module_name = module_name_from_path(unit.path, keep_src=keep_src)
        module_node = NodeId(f"py-module:{module_name}")
        module = PythonModule(
            module_name,
            unit.path,
            module_node,
            unit,
            entry.tree,
            _statement_lines(entry.tree),
            entry.text,
        )
        with timings.stage("frontend.symbols"):
            module_symbols = _collect_symbols(module)
        module.symbols.extend(module_symbols)
        timings.count("frontend.symbols", len(module_symbols))
        modules[module_name] = module
        nodes.append(
            SemanticNode(
                id=module_node,
                display_name=module_name,
                kind=NodeKind.MODULE,
                path=unit.path,
                line=1,
                report_excluded=_matches_any(unit.path, report_exclude),
            )
        )
        for symbol in module_symbols:
            symbols[symbol.id] = symbol
            nodes.append(
                SemanticNode(
                    id=symbol.id,
                    display_name=f"{symbol.module}.{symbol.qualified_name}",
                    kind=symbol.kind,
                    path=symbol.path,
                    line=symbol.line,
                    owner=symbol.owner,
                    report_excluded=_matches_any(symbol.path, report_exclude),
                )
            )

    with timings.stage("frontend.imports"):
        import_roots = ImportRoots(modules)
        for module in modules.values():
            scope_imports = _collect_imports(module, modules, module.tree.body, import_roots)
            module.imports.update(scope_imports.bindings)
            module.star_imports = scope_imports.star
            module.import_alternatives = scope_imports.alternatives
    timings.count(
        "frontend.import_bindings", sum(len(module.imports) for module in modules.values())
    )

    index = SymbolIndex(symbols.values())
    resolver = _Resolver(modules, symbols, index)
    edges: list[ExecutionEdge] = []
    boundaries: list[UnknownBoundary] = []
    with timings.stage("frontend.class_fields"):
        resolver.prepare()
        edges.extend(_structural_edges(modules, symbols, resolver))
    for module in modules.values():
        package = _enclosing_package(module.name, modules)
        if package is not None:
            edges.append(
                ExecutionEdge(
                    module.node_id,
                    modules[package].node_id,
                    EdgeKind.IMPORT,
                    f"runs after its package {package}",
                )
            )

        declaration_visitor = _ExecutionVisitor(
            module=module,
            current=None,
            resolver=resolver,
            class_field_types={},
        )
        with timings.stage("frontend.declaration_flow"):
            _visit_module_declaration_effects(module.tree, declaration_visitor)
            declaration_visitor.finish()
        edges.extend(declaration_visitor.edges)
        boundaries.extend(declaration_visitor.boundaries)
        limitations.extend(declaration_visitor.limitations)

    with timings.stage("frontend.class_fields"):
        class_fields = _infer_all_class_fields(modules, resolver)
        boundaries.extend(_unsupported_python_hook_boundaries(modules, symbols, resolver))
    with timings.stage("frontend.symbol_flow"):
        for module in modules.values():
            for symbol in module.symbols:
                visitor = _ExecutionVisitor(
                    module=module,
                    current=symbol,
                    resolver=resolver,
                    class_field_types=class_fields,
                )
                if isinstance(symbol.node, ast.ClassDef):
                    _visit_class_execution_effects(symbol.node, visitor)
                else:
                    visitor.visit_statements(symbol.node.body)
                visitor.finish()
                edges.extend(visitor.edges)
                boundaries.extend(visitor.boundaries)
                limitations.extend(visitor.limitations)

    with timings.stage("frontend.graph"):
        graph = SemanticGraph(
            nodes=tuple(sorted(nodes, key=lambda item: str(item.id))),
            edges=tuple(sorted(set(edges), key=_edge_sort_key)),
            boundaries=tuple(sorted(set(boundaries), key=_boundary_sort_key)),
        )
        program = PythonProgram(
            graph=graph,
            modules=modules,
            symbols=symbols,
            limitations=tuple(sorted(set(limitations), key=_limitation_sort_key)),
            index=index,
        )
    timings.count("frontend.edges", len(graph.edges))
    timings.count("frontend.boundaries", len(graph.boundaries))
    return program


def _collect_symbols(module: PythonModule) -> list[PythonSymbol]:
    symbols: list[PythonSymbol] = []
    by_node: dict[int, PythonSymbol] = {}
    occurrences: defaultdict[tuple[str, NodeKind], int] = defaultdict(int)
    for node, owners in iter_definitions(module.tree.body):
        owner = by_node[id(owners[-1])] if owners else None
        kind = NodeKind.CLASS if isinstance(node, ast.ClassDef) else NodeKind.FUNCTION
        owner_qname = owner.qualified_name if owner is not None else None
        qualified_name = f"{owner_qname}.{node.name}" if owner_qname else node.name
        occurrence = occurrences[(qualified_name, kind)]
        occurrences[(qualified_name, kind)] += 1
        symbol = PythonSymbol(
            id=NodeId(f"py:{module.name}:{qualified_name}:{kind.value}:{occurrence}"),
            module=module.name,
            qualified_name=qualified_name,
            name=node.name,
            kind=kind,
            path=module.path,
            line=node.lineno,
            occurrence=occurrence,
            owner=owner.id if owner is not None else None,
            owner_qualified_name=owner_qname,
            node=node,
            parameters=() if isinstance(node, ast.ClassDef) else _parameters(node),
            return_annotation=None if isinstance(node, ast.ClassDef) else node.returns,
            decorators=tuple(node.decorator_list),
            bases=(
                tuple(_unstarred(base) for base in node.bases)
                if isinstance(node, ast.ClassDef)
                else ()
            ),
        )
        by_node[id(node)] = symbol
        symbols.append(symbol)
    return symbols


class _Resolver:
    def __init__(
        self,
        modules: dict[str, PythonModule],
        symbols: dict[NodeId, PythonSymbol],
        index: SymbolIndex,
    ) -> None:
        self.modules = modules
        self.symbols = symbols
        self.index = index
        self._called_parameters: dict[NodeId, frozenset[str]] = {}
        self.by_node: dict[int, PythonSymbol] = {id(item.node): item for item in symbols.values()}
        methods: dict[str, list[NodeId]] = {}
        for item in symbols.values():
            owner = symbols.get(item.owner) if item.owner is not None else None
            if (
                item.kind is NodeKind.FUNCTION
                and owner is not None
                and owner.kind is NodeKind.CLASS
            ):
                methods.setdefault(item.name, []).append(item.id)
        self._methods = {name: tuple(sorted(ids)) for name, ids in methods.items()}
        self._bases: dict[NodeId, tuple[PythonSymbol, ...]] = {}
        self._external_bases: dict[NodeId, tuple[str, ...]] = {}
        self._subclasses: dict[NodeId, list[PythonSymbol]] = {}
        self._mro: dict[NodeId, tuple[PythonSymbol, ...]] = {}
        self._project_roots = frozenset(name.split(".")[0] for name in modules)
        self.import_roots = ImportRoots(modules)
        self._top_level: dict[str, tuple[NodeId, ...]] | None = None
        self._stand_ins: dict[str, tuple[NodeId, ...]] | None = None
        self._through_imports: dict[str, PythonSymbol | None] = {}
        self._scope_imports: dict[NodeId, dict[str, ImportBinding]] = {}
        self._locals_by_scope: dict[NodeId, tuple[frozenset[str], bool]] = {}
        self._exposed_methods: dict[NodeId, tuple[NodeId, ...]] = {}
        self._top_level_bindings: dict[str, frozenset[str]] = {}
        self._nominal_rebindings = {
            module.name: frozenset(
                name
                for part in ast.walk(module.tree)
                if isinstance(part, (ast.Name, ast.Attribute)) and isinstance(part.ctx, ast.Store)
                if (name := _dotted_name(part)) is not None
            )
            for module in modules.values()
        }
        direct: set[int] = set()
        for module in modules.values():
            direct.update(
                id(item) for item in module.tree.body if isinstance(item, DEFINITION_TYPES)
            )
        for item in symbols.values():
            direct.update(
                id(child) for child in item.node.body if isinstance(child, DEFINITION_TYPES)
            )
        self.redefined: frozenset[NodeId] = frozenset(
            item.id
            for item in symbols.values()
            if len(matches := index.named(f"{item.module}.{item.qualified_name}")) > 1
            and any(id(match.node) not in direct for match in matches)
        )
        """Symbols sharing their name with another definition, one of them made conditionally."""
        self._name_alternatives: dict[str, dict[str, tuple[str, ...]]] = {}
        for name, module in modules.items():
            alternatives = {
                local: tuple(binding.target for binding in bindings)
                for local, bindings in module.import_alternatives.items()
            }
            for local, binding in module.imports.items():
                definitions = index.named(f"{name}.{local}")
                if (
                    local not in alternatives
                    and definitions
                    and (
                        binding.conditional
                        or any(id(item.node) not in direct for item in definitions)
                    )
                ):
                    alternatives[local] = (binding.target, f"{name}.{local}")
            if alternatives:
                self._name_alternatives[name] = alternatives
        self.module_types: dict[str, dict[str, str]] = {}
        """Per module, top-level names bound once to an instance of a project class."""
        self.module_externals: dict[str, frozenset[str]] = {}
        """Per module, top-level names bound to the result of a call into another package."""
        self.names: dict[str, frozenset[str]] = {
            name: frozenset(
                {
                    *(part for item in module.symbols for part in item.qualified_name.split(".")),
                    *module.imports,
                }
            )
            for name, module in modules.items()
        }
        """Per module, every name that can start a reference to a project symbol."""
        for _round in range(2):
            for name, module in modules.items():
                if module.star_imports:
                    self.names[name] = self.names[name].union(
                        *(self.names.get(base, frozenset()) for base in module.star_imports)
                    )

    def prepare(self) -> None:
        """Resolve class bases and top-level values once every module's imports are known."""

        for item in self.symbols.values():
            if item.kind is not NodeKind.CLASS:
                continue
            module = self.modules[item.module]
            bases: list[PythonSymbol] = []
            external: list[str] = []
            for base in item.bases:
                target = self.resolve_expression(
                    base,
                    module=module,
                    current=self.enclosing_scope(item),
                    local_types={},
                    class_field_types={},
                )
                if target is not None and target.kind is NodeKind.CLASS and target.id != item.id:
                    bases.append(target)
                else:
                    external.append(_base_name(self, base, module))
            self._bases[item.id] = tuple(bases)
            self._external_bases[item.id] = tuple(external)
            for base_symbol in bases:
                self._subclasses.setdefault(base_symbol.id, []).append(item)
        for module in self.modules.values():
            types: dict[str, str] = {}
            externals: set[str] = set()
            for statement in module.tree.body:
                if not isinstance(statement, ast.Assign) or not isinstance(
                    statement.value, ast.Call
                ):
                    continue
                names = [target.id for target in statement.targets if isinstance(target, ast.Name)]
                callee = self.resolve_expression(
                    statement.value.func,
                    module=module,
                    current=None,
                    local_types={},
                    class_field_types={},
                )
                if callee is not None and callee.kind is NodeKind.CLASS:
                    types.update(
                        (name, f"{callee.module}.{callee.qualified_name}") for name in names
                    )
                elif callee is None and self.is_external(statement.value.func, module):
                    externals.update(names)
            self.module_types[module.name] = types
            self.module_externals[module.name] = frozenset(externals)

    def bases(self, class_symbol: PythonSymbol) -> tuple[PythonSymbol, ...]:
        return self._bases.get(class_symbol.id, ())

    def external_bases(self, class_symbol: PythonSymbol) -> tuple[str, ...]:
        """Names of the bases, anywhere in the project hierarchy, that are not project classes."""

        names: list[str] = []
        for item in self.mro(class_symbol):
            names.extend(self._external_bases.get(item.id, ()))
        return tuple(dict.fromkeys(names))

    def mro(self, class_symbol: PythonSymbol) -> tuple[PythonSymbol, ...]:
        """Method resolution order over project classes; bases outside the project are skipped.

        C3 linearization, falling back to depth-first order for inconsistent hierarchies.
        """

        cached = self._mro.get(class_symbol.id)
        if cached is not None:
            return cached
        self._mro[class_symbol.id] = (class_symbol,)
        bases = self.bases(class_symbol)
        sequences = [list(self.mro(base)) for base in bases] + [list(bases)]
        result = [class_symbol]
        while True:
            sequences = [sequence for sequence in sequences if sequence]
            if not sequences:
                break
            head = next(
                (
                    sequence[0]
                    for sequence in sequences
                    if not any(
                        sequence[0].id in (item.id for item in other[1:]) for other in sequences
                    )
                ),
                None,
            )
            if head is None:
                seen = {item.id for item in result}
                for sequence in sequences:
                    for item in sequence:
                        if item.id not in seen:
                            seen.add(item.id)
                            result.append(item)
                break
            result.append(head)
            sequences = [
                sequence[1:] if sequence[0].id == head.id else sequence for sequence in sequences
            ]
        self._mro[class_symbol.id] = tuple(result)
        return self._mro[class_symbol.id]

    def lookup_member(
        self, class_symbol: PythonSymbol, name: str, *, skip_self: bool = False
    ) -> PythonSymbol | None:
        """The member ``name`` that attribute lookup on ``class_symbol`` finds first."""

        order = self.mro(class_symbol)
        for candidate in order[1:] if skip_self else order:
            member = self.resolve_full_name(f"{candidate.module}.{candidate.qualified_name}.{name}")
            if member is not None:
                return member
        return None

    def overrides(self, class_symbol: PythonSymbol, name: str) -> tuple[PythonSymbol, ...]:
        """Members named ``name`` defined by project subclasses of ``class_symbol``."""

        found: dict[NodeId, PythonSymbol] = {}
        queue = list(self._subclasses.get(class_symbol.id, ()))
        seen = {class_symbol.id}
        while queue:
            subclass = queue.pop()
            if subclass.id in seen:
                continue
            seen.add(subclass.id)
            member = self.resolve_full_name(f"{subclass.module}.{subclass.qualified_name}.{name}")
            if member is not None:
                found[member.id] = member
            queue.extend(self._subclasses.get(subclass.id, ()))
        # An annotation does not bind the receiver: a Protocol is met by any class with the
        # method, and tests pass hand-written stand-ins that derive from nothing (ADR-0017).
        structural = any(
            base in {"typing.Protocol", "typing_extensions.Protocol"}
            for base in self.external_bases(class_symbol)
        )
        candidates = self.methods_named(name) if structural else self.stand_in_methods_named(name)
        for method_id in candidates:
            method = self.symbols[method_id]
            if method_id not in found and method.owner != class_symbol.id:
                found[method_id] = method
        return tuple(found[key] for key in sorted(found))

    def subclasses_of(self, class_symbol: PythonSymbol) -> tuple[PythonSymbol, ...]:
        """Every project class deriving from ``class_symbol``, directly or not."""

        found: dict[NodeId, PythonSymbol] = {}
        queue = list(self._subclasses.get(class_symbol.id, ()))
        while queue:
            item = queue.pop()
            if item.id not in found:
                found[item.id] = item
                queue.extend(self._subclasses.get(item.id, ()))
        return tuple(found[key] for key in sorted(found))

    def methods_named(self, name: str) -> tuple[NodeId, ...]:
        return self._methods.get(name, ())

    def stand_in_methods_named(self, name: str) -> tuple[NodeId, ...]:
        """Methods named ``name`` of classes in test code (ADR-0018)."""

        if self._stand_ins is None:
            found: dict[str, list[NodeId]] = {}
            for symbol in self.symbols.values():
                owner = self.symbols.get(symbol.owner) if symbol.owner is not None else None
                if (
                    owner is not None
                    and owner.kind is NodeKind.CLASS
                    and is_function(symbol)
                    and is_test_path(symbol.path)
                ):
                    found.setdefault(symbol.name, []).append(symbol.id)
            self._stand_ins = {key: tuple(sorted(value)) for key, value in found.items()}
        return self._stand_ins.get(name, ())

    def top_level_named(self, name: str) -> tuple[NodeId, ...]:
        """Functions and classes of every module defined at its top level under ``name``."""

        if self._top_level is None:
            found: dict[str, list[NodeId]] = {}
            for symbol in self.symbols.values():
                if symbol.owner is None:
                    found.setdefault(symbol.name, []).append(symbol.id)
            self._top_level = {key: tuple(sorted(value)) for key, value in found.items()}
        return self._top_level.get(name, ())

    def named_by_string(self, value: str) -> NodeId | None:
        """The module or symbol that a string such as ``"pkg.mod"`` or ``"pkg.mod:name"`` names."""

        module = self.modules.get(value)
        if module is not None:
            return module.node_id
        full_name = value.replace(":", ".", 1)
        symbol = self.resolve_full_name(full_name)
        if symbol is not None:
            return symbol.id
        owner_name, _, attribute = full_name.rpartition(".")
        owner = self.modules.get(owner_name)
        if owner is not None and attribute in self.top_level_bindings(owner):
            return owner.node_id
        return None

    def top_level_bindings(self, module: PythonModule) -> frozenset[str]:
        """Names a module binds at its top level: definitions, imports, and assignments."""

        cached = self._top_level_bindings.get(module.name)
        if cached is None:
            names = set(module.imports)
            names.update(item.name for item in module.symbols if item.owner is None)
            for statement in module.tree.body:
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        _bound_names(target, names)
                elif isinstance(statement, ast.AnnAssign | ast.AugAssign):
                    _bound_names(statement.target, names)
            cached = self._top_level_bindings[module.name] = frozenset(names)
        return cached

    def class_named(self, full_name: str) -> PythonSymbol | None:
        symbol = self.resolve_full_name(full_name)
        return symbol if symbol is not None and symbol.kind is NodeKind.CLASS else None

    def in_project(self, dotted: str) -> bool:
        """Whether a dotted import target starts with a top-level name of the project."""

        return dotted.split(".")[0] in self._project_roots

    def is_external(self, expression: ast.expr, module: PythonModule) -> bool:
        """Whether ``expression`` evaluates to an object from outside the project."""

        if isinstance(expression, (ast.Constant, ast.JoinedStr, ast.List, ast.Dict, ast.Set)):
            return True
        if isinstance(expression, (ast.Tuple, ast.ListComp, ast.DictComp, ast.SetComp)):
            return True
        if isinstance(expression, (ast.Attribute, ast.Subscript)):
            return self.is_external(expression.value, module)
        if isinstance(expression, ast.Call):
            return self.resolve_expression(
                expression.func, module=module, current=None, local_types={}, class_field_types={}
            ) is None and self.is_external(expression.func, module)
        if isinstance(expression, ast.Name):
            if expression.id in self.module_externals.get(module.name, frozenset()):
                return True
            binding = module.imports.get(expression.id)
            if binding is None:
                return False
            return binding.target.split(".")[0] not in self._project_roots
        return False

    def annotation_classes(
        self, annotation: ast.expr, module: PythonModule, scope: str | None = None
    ) -> tuple[PythonSymbol, ...]:
        """Project classes an evaluated annotation names; string annotations name none.

        ``scope`` is the class whose body evaluates the annotation: a field of the body or a
        signature of one of its methods, where a bare name is a member of the class first. An
        attribute chain that reaches no definition, as ``Meta.Models.Alias``, uses the classes
        it goes through (ADR-0027, class attributes).
        """

        found: dict[NodeId, PythonSymbol] = {}
        for name in _annotation_names(annotation, module.text, generics=True):
            symbol = self._annotation_symbol(name, module, scope)
            while symbol is None and "." in name:
                name = name.rpartition(".")[0]
                symbol = self._annotation_symbol(name, module, scope)
            while symbol is not None and symbol.kind is NodeKind.CLASS:
                found[symbol.id] = symbol
                owner = symbol.owner_qualified_name
                symbol = (
                    self.index.resolve(f"{symbol.module}.{owner}") if owner is not None else None
                )
        return tuple(found[key] for key in sorted(found))

    def annotation_is_external(self, annotation: ast.expr, module: PythonModule) -> bool:
        """Whether an annotation names only types from outside the project."""

        names = _annotation_names(annotation, module.text)
        return bool(names) and all(
            self._annotation_symbol(name, module) is None
            and (binding := module.imports.get(name.split(".", 1)[0])) is not None
            and binding.target.split(".")[0] not in self._project_roots
            for name in names
        )

    def _annotation_symbol(
        self, name: str, module: PythonModule, scope: str | None = None
    ) -> PythonSymbol | None:
        first, _, rest = name.partition(".")
        binding = module.imports.get(first)
        if binding is not None:
            return self.resolve_full_name(f"{binding.target}.{rest}" if rest else binding.target)
        if scope is not None:
            in_scope = self.resolve_full_name(f"{module.name}.{scope}.{name}")
            if in_scope is not None:
                return in_scope
        return self.resolve_full_name(f"{module.name}.{name}")

    def resolve_full_name(self, full_name: str) -> PythonSymbol | None:
        """The symbol a full name reaches, directly or through re-exporting imports."""

        return self.index.resolve(full_name) or resolve_through_imports(
            self.modules, self.index, full_name, self._through_imports
        )

    def resolve_binding(self, binding: ImportBinding, rest: Sequence[str]) -> PythonSymbol | None:
        """The symbol ``name.rest`` reaches when an import binds ``name``."""

        symbol = self.resolve_full_name(".".join((binding.target, *rest)))
        if symbol is None and rest:
            owner = self.resolve_full_name(".".join((binding.target, *rest[:-1])))
            if owner is not None and owner.kind is NodeKind.CLASS:
                return self.lookup_member(owner, rest[-1], skip_self=True)
        return symbol

    def imported_modules(
        self, node: ast.Import | ast.ImportFrom, module: PythonModule
    ) -> list[str]:
        """Project modules an import statement runs, each package before its submodules."""

        names: list[str] = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.extend(_package_path(self.import_roots.absolute(module, alias.name)))
        else:
            base = _import_from_base(module, node)
            if base is None:
                return []
            if not node.level:
                base = self.import_roots.absolute(
                    module, base, tuple(alias.name for alias in node.names)
                )
            if base:
                names.extend(_package_path(base))
            names.extend(
                f"{base}.{alias.name}" if base else alias.name
                for alias in node.names
                if alias.name != "*"
            )
        return [
            name for name in dict.fromkeys(names) if name in self.modules and name != module.name
        ]

    def scope_imports(self, scope: PythonSymbol | None) -> dict[str, ImportBinding]:
        """Imports a function's body binds, with those of enclosing functions it can see."""

        if scope is None or scope.kind is not NodeKind.FUNCTION:
            return {}
        cached = self._scope_imports.get(scope.id)
        if cached is not None:
            return cached
        module = self.modules[scope.module]
        assert not isinstance(scope.node, ast.ClassDef)
        shadowed, has_imports = self._scope_locals(scope)
        own = (
            _collect_imports(module, self.modules, scope.node.body, self.import_roots).bindings
            if has_imports
            else {}
        )
        owner = self.symbols.get(scope.owner) if scope.owner is not None else None
        enclosing = self.scope_imports(owner)
        if enclosing:
            merged = {name: item for name, item in enclosing.items() if name not in shadowed}
            merged.update(own)
            own = merged
        self._scope_imports[scope.id] = own
        return own

    def alternatives(self, symbol: PythonSymbol) -> tuple[PythonSymbol, ...]:
        """Other definitions of a name when one of its definitions is conditional."""

        if symbol.id not in self.redefined:
            return ()
        return tuple(
            item
            for item in self.index.named(f"{symbol.module}.{symbol.qualified_name}")
            if item.id != symbol.id
        )

    def name_alternatives(self, module: PythonModule) -> dict[str, tuple[str, ...]]:
        """Per top-level name that several statements bind, the full names it may be bound to."""

        return self._name_alternatives.get(module.name, {})

    def local_names(self, scope: PythonSymbol) -> frozenset[str]:
        return self._scope_locals(scope)[0]

    def _scope_locals(self, scope: PythonSymbol) -> tuple[frozenset[str], bool]:
        """``_local_names`` of a scope, and whether its body has an import statement."""

        facts = self._locals_by_scope.get(scope.id)
        if facts is None:
            facts = self._locals_by_scope[scope.id] = _local_names(scope)
        return facts

    def exposed_methods(self, class_symbol: PythonSymbol) -> tuple[NodeId, ...]:
        """Methods of a class and its project bases, which code holding the class may call."""

        cached = self._exposed_methods.get(class_symbol.id)
        if cached is None:
            cached = self._exposed_methods[class_symbol.id] = tuple(
                sorted(
                    member.id
                    for item in self.mro(class_symbol)
                    for member in self.index.members(item.id)
                    if member.kind is NodeKind.FUNCTION
                )
            )
        return cached

    def with_exposed_methods(self, targets: Iterable[NodeId]) -> set[NodeId]:
        """``targets`` and the methods that every class among them exposes."""

        expanded = set(targets)
        for target in tuple(expanded):
            symbol = self.symbols.get(target)
            if symbol is not None and symbol.kind is NodeKind.CLASS:
                expanded.update(self.exposed_methods(symbol))
        return expanded

    def is_project_name(self, dotted: str) -> bool:
        return dotted.split(".", 1)[0] in self._project_roots

    def called_parameter_names(self, symbol: PythonSymbol) -> frozenset[str]:
        """``_called_parameter_names`` computed once per function; its syntax never changes."""

        names = self._called_parameters.get(symbol.id)
        if names is None:
            names = self._called_parameters[symbol.id] = _called_parameter_names(symbol)
        return names

    def resolve_expression(
        self,
        expression: ast.expr,
        *,
        module: PythonModule,
        current: PythonSymbol | None,
        local_types: dict[str, str],
        class_field_types: dict[tuple[str, str], str],
    ) -> PythonSymbol | None:
        dotted = _dotted_name(expression)
        if dotted is None:
            return None
        return self.resolve_dotted(
            dotted,
            module=module,
            current=current,
            local_types=local_types,
            class_field_types=class_field_types,
        )

    def resolve_dotted(
        self,
        dotted: str,
        *,
        module: PythonModule,
        current: PythonSymbol | None,
        local_types: dict[str, str],
        class_field_types: dict[tuple[str, str], str],
    ) -> PythonSymbol | None:
        if dotted.startswith("self.") and current is not None:
            parts = dotted.split(".")
            owner_name = _containing_class_qname(current)
            if owner_name is None:
                return None
            if len(parts) == 2:
                direct = self.resolve_full_name(f"{module.name}.{owner_name}.{parts[1]}")
                if direct is not None:
                    return direct
                owner = self.class_named(f"{module.name}.{owner_name}")
                return self.lookup_member(owner, parts[1]) if owner is not None else None
            if len(parts) >= 3:
                field_type = class_field_types.get((f"{module.name}.{owner_name}", parts[1]))
                if field_type is not None:
                    return self.typed_member(field_type, parts[2:])
        first, *rest = dotted.split(".")
        local_type = local_types.get(first)
        if local_type is None and first not in local_types:
            local_type = self.module_types.get(module.name, {}).get(first)
        if local_type is not None and rest:
            return self.typed_member(local_type, rest)
        for scope in self._scopes(current):
            scoped = self.index.resolve(f"{module.name}.{scope.qualified_name}.{dotted}")
            if scoped is not None:
                return scoped
        local_symbol = self.index.resolve(f"{module.name}.{dotted}")
        binding = module.imports.get(first)
        if binding is not None:
            suffix = ".".join(rest)
            target = f"{binding.target}.{suffix}" if suffix else binding.target
            imported_symbol = self.resolve_full_name(target)
            if local_symbol is None or binding.line > local_symbol.line:
                if imported_symbol is None and rest:
                    return self._inherited(
                        dotted,
                        module=module,
                        current=current,
                        local_types=local_types,
                        class_field_types=class_field_types,
                    )
                return imported_symbol
        if local_symbol is None and binding is None and module.star_imports:
            for base in reversed(module.star_imports):
                star_symbol = self.resolve_full_name(f"{base}.{dotted}")
                if star_symbol is not None:
                    return star_symbol
        if local_symbol is None and rest:
            return self._inherited(
                dotted,
                module=module,
                current=current,
                local_types=local_types,
                class_field_types=class_field_types,
            )
        return local_symbol

    def _scopes(self, current: PythonSymbol | None) -> Iterator[PythonSymbol]:
        """Scopes whose definitions a name in ``current`` can see, innermost first.

        A function sees its own nested definitions and those of enclosing functions; a class body
        sees its own definitions. Class scopes are never visible from the functions inside them.
        """

        scope = current
        first = True
        while scope is not None:
            if scope.kind is NodeKind.FUNCTION or first:
                yield scope
            first = False
            scope = self.symbols.get(scope.owner) if scope.owner is not None else None

    def enclosing_scope(self, symbol: PythonSymbol) -> PythonSymbol | None:
        """The scope a definition's header is evaluated in: its owner, or the module."""

        return self.symbols.get(symbol.owner) if symbol.owner is not None else None

    def typed_member(self, type_name: str, parts: Sequence[str]) -> PythonSymbol | None:
        direct = self.resolve_full_name(f"{type_name}.{'.'.join(parts)}")
        if direct is not None or len(parts) != 1:
            return direct
        owner = self.class_named(type_name)
        return self.lookup_member(owner, parts[0]) if owner is not None else None

    def _inherited(
        self,
        dotted: str,
        *,
        module: PythonModule,
        current: PythonSymbol | None,
        local_types: dict[str, str],
        class_field_types: dict[tuple[str, str], str],
    ) -> PythonSymbol | None:
        """``Class.member`` where ``member`` is inherited from a project base of ``Class``."""

        prefix, _, name = dotted.rpartition(".")
        owner = self.resolve_dotted(
            prefix,
            module=module,
            current=current,
            local_types=local_types,
            class_field_types=class_field_types,
        )
        if owner is None or owner.kind is not NodeKind.CLASS:
            return None
        return self.lookup_member(owner, name, skip_self=True)

    def external_name(self, expression: ast.expr, module: PythonModule) -> str | None:
        dotted = _dotted_name(expression)
        if dotted is None:
            return None
        first, *rest = dotted.split(".")
        binding = module.imports.get(first)
        if binding is None:
            return dotted
        suffix = ".".join(rest)
        full = f"{binding.target}.{suffix}" if suffix else binding.target
        # ``from .util import TestCase`` where ``util`` says ``TestCase = unittest.TestCase``.
        resolved = follow_module_alias(self.modules, full)
        return resolved if not self.is_project_name(resolved) else full


class _ExecutionVisitor:
    """Execution facts of one scope: a module's top level, a class body, or a function body."""

    def __init__(
        self,
        *,
        module: PythonModule,
        current: PythonSymbol | None,
        resolver: _Resolver,
        class_field_types: dict[tuple[str, str], str],
    ) -> None:
        self.module = module
        self.current = current
        self.resolver = resolver
        self.class_field_types = class_field_types
        self.source = current.id if current is not None else module.node_id
        self.edges: list[ExecutionEdge] = []
        self.boundaries: list[UnknownBoundary] = []
        self.limitations: list[PythonLimitation] = []
        self.external_locals: set[str] = set()
        self._local_imports = resolver.scope_imports(current)
        self.external_locals.update(
            name
            for name, binding in self._local_imports.items()
            if not resolver.is_project_name(binding.target)
        )
        self.local_types = self._initial_local_types()
        self._receiver_values = {
            name: ReceiverValue(frozenset({type_name}))
            for name, type_name in self.local_types.items()
        }
        self._receiver_values.update((name, EXTERNAL_RECEIVER) for name in self.external_locals)
        if current is not None:
            for parameter in current.parameters:
                annotation = parameter.annotation
                if (
                    annotation is not None
                    and parameter.name in self.external_locals
                    and (origin := self._external_value_annotation_origin(annotation)) is not None
                ):
                    self._receiver_values[parameter.name] = ReceiverValue(
                        external=True, external_annotation=True, external_nominal=origin
                    )
        self._container_locals: set[str] = set()
        self._string_values: dict[str, StringValue] = {}
        # These constructs need expression/closure scope modeling before strong string updates.
        self._track_strings = (
            current is not None
            and isinstance(current.node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not any(
                isinstance(node, (ast.NamedExpr, ast.Global, ast.Nonlocal, ast.comprehension))
                for node in ast.walk(current.node)
            )
        )
        self._container_attributes = _container_attributes(resolver, current)
        self._handled: set[int] = set()
        self._escaped: set[NodeId] = set()
        self._named_classes: set[NodeId] = set()
        self._dispatched: set[str] = set()
        self._dynamic_modules: set[str] = set()
        self._flow_pass_budget = 256
        self._stand_ins: set[str] = set()
        """Methods called on values from outside the project, which tests may replace."""
        """Locals bound to a module imported by a computed name."""
        self._names = resolver.names.get(module.name, frozenset())
        self._locals = resolver.local_names(current) if current is not None else frozenset()
        self._name_alternatives = resolver.name_alternatives(module)
        self._redefined = resolver.redefined
        self._evaluates_annotations = current is None or current.kind is NodeKind.CLASS

    def visit_statements(self, statements: Iterable[ast.stmt]) -> None:
        for statement in statements:
            if isinstance(statement, ast.Assign):
                self.visit_expression(statement.value)
                self._visit_assign(statement)
                for target in statement.targets:
                    self.visit_expression(target)
            elif isinstance(statement, ast.AnnAssign):
                if statement.value is not None:
                    self.visit_expression(statement.value)
                self._visit_ann_assign(statement)
            elif isinstance(statement, (ast.AugAssign, ast.Delete)):
                self._visit_nodes(flow_nodes((statement,)))
                targets = (
                    statement.targets if isinstance(statement, ast.Delete) else [statement.target]
                )
                for target in targets:
                    for child in ast.walk(target):
                        if isinstance(child, ast.Name):
                            self._set_receiver(child.id, UNKNOWN_RECEIVER)
                            self._container_locals.discard(child.id)
            elif isinstance(statement, ast.If):
                self._visit_if(statement)
                self.visit_expression(statement.test)
                entry = self._receiver_state()
                self.visit_statements(statement.body)
                left = self._receiver_state()
                self._restore_receiver_state(entry)
                self.visit_statements(statement.orelse)
                self._restore_receiver_state(left.join(self._receiver_state()))
            elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                self._visit_receiver_loop(statement)
            elif isinstance(statement, (ast.Try, ast.TryStar)):
                self._visit_receiver_try(statement)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                for item in statement.items:
                    self.visit_expression(item.context_expr)
                self._visit_with(statement)
                self.visit_statements(statement.body)
            elif isinstance(statement, ast.Match):
                self.visit_expression(statement.subject)
                entry = self._receiver_state()
                merged = entry
                for case in statement.cases:
                    self._restore_receiver_state(entry)
                    self._visit_nodes(ast.walk(case.pattern))
                    for node in ast.walk(case.pattern):
                        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                            self._set_receiver(node.name, UNKNOWN_RECEIVER)
                        elif isinstance(node, ast.MatchMapping) and node.rest:
                            self._set_receiver(node.rest, UNKNOWN_RECEIVER)
                    if case.guard is not None:
                        self.visit_expression(case.guard)
                    self.visit_statements(case.body)
                    merged = merged.join(self._receiver_state())
                self._restore_receiver_state(merged)
            else:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    for alias in statement.names:
                        name = alias.asname or alias.name.split(".")[0]
                        self._string_values.pop(name, None)
                        self._forget_external_annotation(name)
                elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self._string_values.pop(statement.name, None)
                    self._forget_external_annotation(statement.name)
                self._visit_nodes(flow_nodes((statement,)))

    def _receiver_state(self) -> ReceiverState:
        return ReceiverState(
            dict(self._receiver_values),
            set(self._container_locals),
            set(self._dynamic_modules),
            dict(self._string_values),
        )

    def _restore_receiver_state(self, state: ReceiverState) -> None:
        self._receiver_values = dict(state.values)
        self.local_types = {
            name: min(value.types) for name, value in state.values.items() if value.project_only
        }
        self.external_locals = {
            name
            for name, value in state.values.items()
            if value.external and not (value.types or value.unknown)
        }
        self._container_locals = set(state.containers)
        self._dynamic_modules = set(state.dynamic_modules)
        self._string_values = dict(state.strings)

    def _set_receiver(self, name: str, value: ReceiverValue) -> None:
        self._string_values.pop(name, None)
        self._receiver_values[name] = value
        self.local_types.pop(name, None)
        self.external_locals.discard(name)
        if value.project_only:
            self.local_types[name] = min(value.types)
        elif value.external and not (value.types or value.unknown):
            self.external_locals.add(name)

    def _forget_external_annotation(self, name: str) -> None:
        value = self._receiver_values.get(name)
        if value is not None and value.external_annotation:
            self._receiver_values[name] = ReceiverValue(value.types, value.unknown, value.external)

    def _revisit(self, statements: Iterable[ast.stmt]) -> None:
        # Expression references handled during an earlier loop pass must be evaluated again.
        statements = tuple(statements)
        self._handled.difference_update(
            id(node) for statement in statements for node in ast.walk(statement)
        )
        self.visit_statements(statements)

    def _visit_receiver_loop(self, node: ast.For | ast.AsyncFor | ast.While) -> None:
        entry = self._receiver_state()
        head = entry
        converged = False
        for _ in range(32):
            if self._flow_pass_budget <= 0:
                break
            self._flow_pass_budget -= 1
            self._restore_receiver_state(head)
            if isinstance(node, ast.While):
                self.visit_expression(node.test)
            else:
                self.visit_expression(node.iter)
                for target in ast.walk(node.target):
                    if isinstance(target, ast.Name):
                        self._set_receiver(target.id, UNKNOWN_RECEIVER)
                        self._container_locals.discard(target.id)
            self._revisit(node.body)
            joined = head.join(entry).join(self._receiver_state())
            if joined == head:
                converged = True
                break
            head = joined
        if not converged:
            # Widen to unknown; a convergence budget must never discard possible receivers.
            head = ReceiverState(
                {name: value.join(UNKNOWN_RECEIVER) for name, value in head.values.items()},
                dynamic_modules=head.dynamic_modules,
            )
            self._restore_receiver_state(head)
            self._revisit(node.body)
            head = head.join(self._receiver_state())
        self._restore_receiver_state(head)
        self.visit_statements(node.orelse)
        # A break may skip the else; return/continue paths are conservatively included too.
        self._restore_receiver_state(head.join(self._receiver_state()))

    def _visit_receiver_try(self, node: ast.Try | ast.TryStar) -> None:
        entry = self._receiver_state()
        exceptional = entry
        for statement in node.body:
            self.visit_statements((statement,))
            exceptional = exceptional.join(self._receiver_state())
        # A nested statement can raise between two writes not visible in its final state.
        # Keep such locals explicitly unknown at exception/finally entries.
        for part in flow_nodes(node.body):
            if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store):
                exceptional.values[part.id] = exceptional.values.get(
                    part.id, UNKNOWN_RECEIVER
                ).join(UNKNOWN_RECEIVER)
                exceptional.strings.pop(part.id, None)
        self.visit_statements(node.orelse)
        merged = self._receiver_state()
        for handler in node.handlers:
            self._restore_receiver_state(exceptional)
            if handler.type is not None:
                self.visit_expression(handler.type)
            if handler.name is not None:
                self._set_receiver(handler.name, UNKNOWN_RECEIVER)
            self.visit_statements(handler.body)
            merged = merged.join(self._receiver_state())
        # Finally also runs on an exception/return before the final statement of the try.
        self._restore_receiver_state(merged.join(exceptional))
        self.visit_statements(node.finalbody)

    def visit_expression(self, expression: ast.expr) -> None:
        self._visit_nodes(ast.walk(expression))

    def finish(self) -> None:
        """Record references that escaped from this scope as one boundary."""

        self._escaped = self.resolver.with_exposed_methods(self._escaped) | self._named_classes
        self._named_classes = set()
        self._escaped -= {edge.target for edge in self.edges if edge.source == self.source}
        if self._escaped:
            self.boundaries.append(
                UnknownBoundary(
                    source=self.source,
                    domain="escaped_reference",
                    reason="project callable or class is used as a value by an unknown consumer",
                    targets=tuple(sorted(self._escaped)),
                )
            )
            self._escaped = set()
        if self._dispatched:
            names = sorted(self._dispatched)
            shown = ", ".join(names[:5]) + (
                f", and {len(names) - 5} more" if len(names) > 5 else ""
            )
            self.boundaries.append(
                UnknownBoundary(
                    source=self.source,
                    domain="unresolved_method_dispatch",
                    reason=f"methods named {shown} may run on values of unknown type",
                    targets=tuple(
                        sorted(
                            {
                                target
                                for name in names
                                for target in self.resolver.methods_named(name)
                            }
                        )
                    ),
                    needs_module=True,
                )
            )
            self._dispatched = set()
        if self._stand_ins:
            names = sorted(self._stand_ins)
            self.boundaries.append(
                UnknownBoundary(
                    source=self.source,
                    domain="test_stand_in_dispatch",
                    reason=(
                        "test stand-ins may replace values from outside the project for methods "
                        + ", ".join(names[:5])
                        + (f", and {len(names) - 5} more" if len(names) > 5 else "")
                    ),
                    targets=tuple(
                        sorted(
                            {
                                target
                                for name in names
                                for target in self.resolver.stand_in_methods_named(name)
                            }
                        )
                    ),
                )
            )
            self._stand_ins = set()

    def _receiver_is_project(self, receiver: ast.expr) -> bool:
        """Whether a receiver's type is a project class, so its methods are already resolved."""

        dotted = _dotted_name(receiver)
        if dotted is None:
            return False
        first = dotted.split(".")[0]
        value = self._receiver_values.get(first)
        if value is not None:
            return value.project_only
        return first in self.local_types or first in {"self", "cls"}

    def visit_definition_header(self, node: DefinitionNode) -> None:
        """Effects of executing a ``def`` or ``class`` statement: decorators and defaults."""

        decorated = self.resolver.by_node.get(id(node))
        for decorator in node.decorator_list:
            self._apply_decorator(decorator, decorated)
        if not isinstance(node, ast.ClassDef):
            for parameter in _parameters(node):
                if parameter.default is not None:
                    self.visit_expression(parameter.default)
                if parameter.annotation is not None:
                    self._visit_annotation_calls(parameter.annotation)
            if node.returns is not None:
                self._visit_annotation_calls(node.returns)

    def _visit_annotation_calls(self, annotation: ast.expr) -> None:
        """Run the calls an annotation makes, such as ``Annotated`` metadata (ADR-0017).

        ``Annotated[bool, typer.Option(callback=check)]`` and ``AfterValidator(normalize)``
        build objects whose callables a framework calls later. Python evaluates a parameter
        annotation when the ``def`` runs; under ``from __future__ import annotations`` the
        framework that reads the signature evaluates it instead, so both are treated alike.
        Names an annotation only mentions as types are not references.
        """

        for call in _outermost_calls(annotation):
            self.visit_expression(call)

    def mark_references(self, expression: ast.expr) -> None:
        """Treat the name chain of ``expression`` as already accounted for."""

        node: ast.expr = expression
        while isinstance(node, ast.Attribute):
            self._handled.add(id(node))
            node = node.value
        if isinstance(node, ast.Name):
            self._handled.add(id(node))

    def _visit_nodes(self, nodes: Iterable[ast.AST]) -> None:
        handlers: dict[type[ast.AST], Callable[[Any], None]] = {
            ast.Call: self._visit_call,
            ast.Name: self._visit_name_or_attribute,
            ast.Attribute: self._visit_name_or_attribute,
            ast.Subscript: self._visit_subscript,
            ast.Assign: self._visit_assign,
            ast.AnnAssign: self._visit_ann_assign,
            ast.FunctionDef: self.visit_definition_header,
            ast.AsyncFunctionDef: self.visit_definition_header,
            ast.ClassDef: self.visit_definition_header,
            ast.Constant: self._visit_constant,
            ast.Import: self._visit_import,
            ast.ImportFrom: self._visit_import,
            ast.If: self._visit_if,
            ast.With: self._visit_with,
            ast.AsyncWith: self._visit_with,
            ast.NamedExpr: self._visit_named_expression,
        }
        handled = self._handled
        for node in nodes:
            handler = handlers.get(type(node))
            if handler is not None and id(node) not in handled:
                handler(node)

    def _visit_subscript(self, node: ast.Subscript) -> None:
        if self._is_globals_call(node.value):
            self._record_globals_lookup(node.slice)

    def _is_globals_call(self, expression: ast.expr) -> bool:
        return (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "globals"
            and not expression.args
            and "globals" not in self._locals
        )

    def _record_globals_lookup(self, key: ast.expr | None) -> None:
        """``globals()["_render_%s_type" % name]`` reads a top-level definition by its name.

        A constant name is a reference; a computed one may name any top-level definition of the
        module that has its constant start and end (ADR-0025).
        """

        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            symbol = self.resolver.resolve_full_name(f"{self.module.name}.{key.value}")
            if symbol is not None:
                self._escaped.add(symbol.id)
            return
        prefix, suffix = _constant_affixes(key)
        targets = tuple(
            sorted(
                symbol.id
                for symbol in self.module.symbols
                if symbol.owner is None
                and symbol.name.startswith(prefix)
                and symbol.name.endswith(suffix)
                and len(symbol.name) >= len(prefix) + len(suffix)
            )
        )
        if targets:
            self.boundaries.append(
                UnknownBoundary(
                    source=self.source,
                    domain="dynamic_attribute_dispatch",
                    reason="globals() lookup by a computed name may name a top-level definition",
                    targets=targets,
                )
            )

    def _visit_import(self, node: ast.Import | ast.ImportFrom) -> None:
        """Running an import statement runs the project modules it names."""

        for name in self.resolver.imported_modules(node, self.module):
            self.edges.append(
                ExecutionEdge(
                    self.source,
                    self.resolver.modules[name].node_id,
                    EdgeKind.IMPORT,
                    f"imports local module {name}",
                )
            )

    def _visit_if(self, node: ast.If) -> None:
        """Imports under ``if TYPE_CHECKING:`` bind names for annotations but never run."""

        test = node.test
        name = test.id if isinstance(test, ast.Name) else getattr(test, "attr", None)
        if name != "TYPE_CHECKING":
            return
        stack = list(node.body)
        while stack:
            statement = stack.pop()
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                self._handled.add(id(statement))
            elif not isinstance(statement, DEFINITION_TYPES):
                stack.extend(child_statements(statement))

    def _external_name(self, expression: ast.expr) -> str | None:
        head: ast.expr = expression
        while isinstance(head, ast.Attribute):
            head = head.value
        if isinstance(head, ast.Name) and head.id in self._local_imports:
            dotted = _dotted_name(expression)
            if dotted is not None:
                binding = self._local_imports[head.id]
                _first, _, suffix = dotted.partition(".")
                return f"{binding.target}.{suffix}" if suffix else binding.target
        return self.resolver.external_name(expression, self.module)

    def _alternative_targets(
        self, expression: ast.expr, target: PythonSymbol | None
    ) -> list[PythonSymbol]:
        """Definitions an expression may name besides ``target``, when bindings are alternatives."""

        found: dict[NodeId, PythonSymbol] = {}
        dotted = _dotted_name(expression)
        if dotted is not None:
            first, *rest = dotted.split(".")
            value = self._receiver_values.get(first)
            if value is not None and rest:
                for type_name in value.types:
                    member = self.resolver.typed_member(type_name, rest)
                    if member is not None:
                        found[member.id] = member
        redefined = target is not None and target.id in self._redefined
        if target is not None and redefined:
            found.update((item.id, item) for item in self.resolver.alternatives(target))
        head: ast.expr = expression
        while isinstance(head, ast.Attribute):
            head = head.value
        if (
            isinstance(head, ast.Name)
            and head.id not in self._locals
            and head.id not in self._local_imports
        ):
            bases = self._name_alternatives.get(head.id, ())
            dotted = _dotted_name(expression) if bases else None
            if dotted is not None:
                rest = dotted.split(".")[1:]
                for base in bases:
                    symbol = self.resolver.resolve_full_name(".".join((base, *rest)))
                    if symbol is not None:
                        found[symbol.id] = symbol
                        found.update((item.id, item) for item in self.resolver.alternatives(symbol))
        if target is not None:
            found.pop(target.id, None)
        return [found[key] for key in sorted(found)]

    def _visit_constant(self, node: ast.Constant) -> None:
        """A string that names a project module or symbol exactly is a reference to it."""

        value = node.value
        if type(value) is not str or len(value) > 200 or not ("." in value or ":" in value):
            return
        if value.endswith(".py") and _SCRIPT_FILE.fullmatch(value):
            # ``subprocess.run([sys.executable, "fail_script.py"])`` runs the module by its file
            # name (ADR-0028).
            suffix = "/" + value.removeprefix("./")
            matches = [
                module
                for module in self.resolver.modules.values()
                if ("/" + module.path).endswith(suffix)
            ]
            if 0 < len(matches) <= 3:
                self._escaped.update(module.node_id for module in matches)
            return
        if value.startswith(".") and value.strip("."):
            # ``"._process.cmdexec:cmdexec"`` in a package's lazy export table (ADR-0028).
            module_part, colon, attribute = value.partition(":")
            is_package = self.module.path.rpartition("/")[2] == "__init__.py"
            package = self.module.name if is_package else self.module.name.rpartition(".")[0]
            absolute = _relative_import_name(module_part, package or None)
            if absolute is None:
                return
            value = absolute + colon + attribute
        target = self.resolver.named_by_string(value)
        if target is not None:
            self._escaped.add(target)
            symbol = self.resolver.symbols.get(target)
            if symbol is not None:
                self._escaped.update(item.id for item in self.resolver.alternatives(symbol))

    def _record_dynamic_import(self, call: ast.Call) -> None:
        arguments = positional_arguments(call)
        name = arguments[0] if arguments else keyword_argument(call, "name")
        if (isinstance(name, ast.Attribute) and name.attr in LOADED_MODULE_NAMES) or (
            isinstance(name, ast.Name) and name.id in LOADED_MODULE_NAMES
        ):
            return  # ``obj.__module__`` names a module already loaded; importing it runs nothing
        modules = self.resolver.modules
        package = self._import_package(call, arguments)
        if isinstance(name, ast.Constant) and isinstance(name.value, str):
            absolute = _relative_import_name(name.value, package)
            module = modules.get(absolute) if absolute is not None else None
            if module is not None:
                self._escaped.add(module.node_id)
                return
            if absolute is not None:
                return
            name = None  # a relative name without a known package may name any module
        loaded_suffix = _loaded_module_suffix(name)
        if loaded_suffix:
            # ``f"{obj.__module__}.tables"`` names a submodule of a module already loaded; one
            # whose prefix is a directory without ``__init__.py`` has no module to wait for.
            matching = sorted(
                (key, module) for key, module in modules.items() if key.endswith(loaded_suffix)
            )
            if matching:
                self.boundaries.append(
                    UnknownBoundary(
                        source=self.source,
                        domain="dynamic_import",
                        reason=(
                            f"modules ending with {loaded_suffix!r} may be imported beside "
                            "loaded modules"
                        ),
                        targets=tuple(module.node_id for _, module in matching),
                        gates=tuple(
                            (module.node_id, modules[key[: -len(loaded_suffix)]].node_id)
                            for key, module in matching
                            if key[: -len(loaded_suffix)] in modules
                        ),
                    )
                )
            return
        prefix, suffix = _constant_affixes(name)
        if prefix.startswith("."):
            base = _relative_import_name(prefix, package)
            # ``f".{name}"`` continues after the package: ``pkg.`` rather than ``pkg``.
            prefix = "" if base is None else base + ("." if prefix.endswith(".") else "")
        named = {
            key
            for key in modules
            if key.startswith(prefix) and key.endswith(suffix) and len(key) >= len(prefix + suffix)
        }
        # Importing ``a.b.tables`` runs the packages ``a`` and ``a.b`` first.
        imported = {
            package for key in named for package in _package_path(key) if package in modules
        }
        targets = tuple(sorted(modules[key].node_id for key in imported))
        if targets:
            shown = " and ".join(
                part
                for part in (
                    f"starting with {prefix!r}" if prefix else "",
                    f"ending with {suffix!r}" if suffix else "",
                )
                if part
            )
            self.boundaries.append(
                UnknownBoundary(
                    source=self.source,
                    domain="dynamic_import",
                    reason=(
                        f"modules {shown} may be imported by name"
                        if shown
                        else "any project module may be imported by name"
                    ),
                    targets=targets,
                )
            )

    def _import_package(self, call: ast.Call, arguments: Sequence[ast.expr]) -> str | None:
        """The ``package`` a relative ``import_module`` name is resolved against, if known."""

        value = arguments[1] if len(arguments) > 1 else keyword_argument(call, "package")
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.Name) and value.id in {"__name__", "__package__"}:
            is_package = self.module.path.rpartition("/")[2] == "__init__.py"
            if value.id == "__name__" or is_package:
                return self.module.name
            return self.module.name.rpartition(".")[0]
        return None

    def _visit_name_or_attribute(self, node: ast.Name | ast.Attribute) -> None:
        if type(node.ctx) is ast.Load:
            self._visit_reference(node)
        else:
            self.mark_references(node)

    def _resolve(self, expression: ast.expr) -> PythonSymbol | None:
        head: ast.expr = expression
        while isinstance(head, ast.Attribute):
            head = head.value
        if isinstance(head, ast.Name):
            value = self._receiver_values.get(head.id)
            if value is not None and (
                not value.project_only or not isinstance(expression, ast.Attribute)
            ):
                return self._nested_definition(expression)
            binding = self._local_imports.get(head.id)
            if binding is not None:
                dotted = _dotted_name(expression)
                if dotted is None:
                    return None
                # ``def cpu_count`` in one branch and ``from os import cpu_count`` in another
                # bind the name alike; an import from outside the project leaves the definition.
                return self.resolver.resolve_binding(
                    binding, dotted.split(".")[1:]
                ) or self._nested_definition(expression)
            if head.id in self._locals and head.id not in self.local_types:
                return self._nested_definition(expression)
        return self.resolver.resolve_expression(
            expression,
            module=self.module,
            current=self.current,
            local_types=self.local_types,
            class_field_types=self.class_field_types,
        )

    def _nested_definition(self, expression: ast.expr) -> PythonSymbol | None:
        """A definition nested in this function under a name the function also binds otherwise.

        ``def write`` in one branch and ``write = print`` in another both bind ``write``; either
        may be what runs, so the nested definition is a possible target.
        """

        dotted = _dotted_name(expression)
        if dotted is None or self.current is None:
            return None
        return self.resolver.index.resolve(
            f"{self.module.name}.{self.current.qualified_name}.{dotted}"
        )

    def _containing_class(self) -> PythonSymbol | None:
        owner_name = _containing_class_qname(self.current) if self.current is not None else None
        if owner_name is None:
            return None
        return self.resolver.class_named(f"{self.module.name}.{owner_name}")

    def _super_member(self, attribute: ast.Attribute) -> PythonSymbol | None:
        receiver = attribute.value
        if not (
            isinstance(receiver, ast.Call)
            and isinstance(receiver.func, ast.Name)
            and receiver.func.id == "super"
        ):
            return None
        self._handled.add(id(receiver))
        self._handled.add(id(receiver.func))
        owner = self._containing_class()
        if owner is None:
            return None
        return self.resolver.lookup_member(owner, attribute.attr, skip_self=True)

    def _is_super(self, attribute: ast.Attribute) -> bool:
        receiver = attribute.value
        return (
            isinstance(receiver, ast.Call)
            and isinstance(receiver.func, ast.Name)
            and receiver.func.id == "super"
        )

    def _through_instance(self, attribute: ast.Attribute) -> bool:
        """Whether ``attribute`` is looked up on an instance, where a subclass may override it."""

        if self._is_super(attribute):
            return False
        receiver = self._resolve(attribute.value)
        return receiver is None

    def _dispatch_edges(self, target: PythonSymbol, detail_prefix: str) -> None:
        owner = self.resolver.symbols.get(target.owner) if target.owner is not None else None
        if owner is None or owner.kind is not NodeKind.CLASS:
            return
        for override in self.resolver.overrides(owner, target.name):
            self.edges.append(
                ExecutionEdge(
                    self.source,
                    override.id,
                    EdgeKind.CALL,
                    f"{detail_prefix} {override.module}.{override.qualified_name}",
                )
            )

    def _visit_call(self, node: ast.Call) -> None:
        func = node.func
        self.mark_references(func)
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and self._is_globals_call(func.value)
        ):
            self._record_globals_lookup(node.args[0] if node.args else None)
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"getfixturevalue", "getfuncargvalue"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            # ``request.getfixturevalue("name")`` requests the fixture ``name`` from a body.
            self._escaped.update(self.resolver.top_level_named(node.args[0].value))
        if (
            isinstance(func, ast.Name)
            and func.id in {"locals", "vars"}
            and not node.args
            and func.id not in self._locals
            and self.current is not None
        ):
            # ``return locals()`` hands the function's nested definitions on, as
            # ``property(**prop())`` receives ``fget`` and ``fset`` (ADR-0026).
            self._escaped.update(
                member.id for member in self.resolver.index.members(self.current.id)
            )
        if self._external_name(func) in UNITTEST_RUNNERS:
            # ``unittest.main()`` collects the test cases of ``__main__``, this module (ADR-0028).
            self._escaped.update(
                symbol.id
                for symbol in self.module.symbols
                if symbol.owner is None
                and symbol.kind is NodeKind.CLASS
                and any(
                    name.endswith(("unittest.TestCase", "unittest.IsolatedAsyncioTestCase"))
                    for name in self.resolver.external_bases(symbol)
                )
            )
        if _dotted_name(func) == "getattr" and "getattr" not in self._locals:
            self._record_getattr_value(node)
        if isinstance(func, ast.Attribute) and self._is_super(func):
            target = self._super_member(func)
            through_instance = False
        else:
            target = self._resolve(func)
            through_instance = isinstance(func, ast.Attribute) and self._through_instance(func)
            if target is None and isinstance(func, ast.Attribute):
                target = self._inferred_member(func)
                through_instance = target is not None
        for alternative in self._alternative_targets(func, target):
            self._call_edges(
                node,
                alternative,
                through_instance=isinstance(func, ast.Attribute) and self._through_instance(func),
            )
        if target is not None:
            self._call_edges(node, target, through_instance=through_instance)
            self._inherited_through_class(func, target)
        elif _is_getattr_call(func):
            assert isinstance(func, ast.Call)
            self._record_dynamic_getattr(func)
        else:
            if self._external_name(func) in DESERIALIZERS:
                self.boundaries.append(
                    UnknownBoundary(
                        source=self.source,
                        domain="deserialization",
                        reason="deserialized objects may be instances of any project class",
                        targets=(self.source,),
                        opens_gates=True,
                    )
                )
            if self._external_name(func) in DYNAMIC_IMPORTS:
                self._record_dynamic_import(node)
            elif self._external_name(func) in PATH_IMPORTS:
                self.boundaries.append(
                    UnknownBoundary(
                        source=self.source,
                        domain="dynamic_import",
                        reason="any project module may be loaded from a file path",
                        targets=tuple(
                            sorted(module.node_id for module in self.resolver.modules.values())
                        ),
                    )
                )
            self._record_escaped_project_callables(node)
            if isinstance(func, ast.Attribute):
                self._reference_receiver(func)

    def _inherited_through_class(self, func: ast.expr, target: PythonSymbol) -> None:
        """``Sub.create()`` with ``create`` inherited uses ``Sub``, which ``cls`` then is.

        The member runs with the subclass as its class, so the subclass is used: its own
        hooks and the members that bases outside the project call are reached with it
        (ADR-0020).
        """

        if not isinstance(func, ast.Attribute) or target.owner is None:
            return
        receiver = self._resolve(func.value) if _dotted_name(func.value) is not None else None
        if receiver is None or receiver.kind is not NodeKind.CLASS or receiver.id == target.owner:
            return
        self.edges.append(
            ExecutionEdge(
                self.source,
                receiver.id,
                EdgeKind.FIELD_LOAD,
                f"calls an inherited member through {receiver.module}.{receiver.qualified_name}",
            )
        )

    def _call_edges(self, node: ast.Call, target: PythonSymbol, *, through_instance: bool) -> None:
        """Edges of calling ``target``: the call, its initializer, and possible overrides."""

        kind = EdgeKind.CONSTRUCT if target.kind is NodeKind.CLASS else EdgeKind.CALL
        self.edges.append(
            ExecutionEdge(
                self.source, target.id, kind, f"calls {target.module}.{target.qualified_name}"
            )
        )
        if target.kind is NodeKind.CLASS:
            initializer = self.resolver.lookup_member(target, "__init__")
            if initializer is not None:
                self.edges.append(
                    ExecutionEdge(
                        self.source,
                        initializer.id,
                        EdgeKind.CONSTRUCT,
                        f"constructs {target.module}.{target.qualified_name}",
                    )
                )
        elif through_instance:
            self._dispatch_edges(target, "may dispatch to override")
        if is_function(target):
            self._link_callable_arguments(node, target)

    def _visit_reference(self, node: ast.Name | ast.Attribute) -> None:
        """A name or attribute used as a value: the referenced callable or class escapes."""

        self.mark_references(node)
        if isinstance(node, ast.Name):
            if (
                node.id not in self._names
                and node.id not in self.local_types
                and node.id not in self._local_imports
            ):
                return
            target = self._resolve(node)
        elif isinstance(node.value, ast.Name) and node.value.id in self._dynamic_modules:
            # ``module.check`` of ``module = import_module(name)`` may be the ``check`` of any
            # module the import may reach (ADR-0017).
            self._escaped.update(self.resolver.top_level_named(node.attr))
            return
        elif self._unknown_local_head(node):
            if self.resolver.methods_named(node.attr):
                self._dispatched.add(node.attr)
            return
        elif self._is_super(node):
            target = self._super_member(node)
        else:
            target = self._resolve(node) or self._inferred_member(node)
        self._escaped.update(item.id for item in self._alternative_targets(node, target))
        if target is not None:
            self._escaped.add(target.id)
            self._inherited_through_class(node, target)
            if isinstance(node, ast.Attribute) and self._through_instance(node):
                owner = self.resolver.symbols.get(target.owner) if target.owner else None
                if owner is not None and owner.kind is NodeKind.CLASS:
                    self._escaped.update(
                        item.id for item in self.resolver.overrides(owner, target.name)
                    )
            return
        if isinstance(node, ast.Attribute):
            self._reference_receiver(node)

    def _members_provided_by_subclasses(self, attribute: ast.Attribute) -> list[PythonSymbol]:
        """Members ``self.name`` reaches when the class has none: a subclass's or its other bases'.

        A mixin calls ``self._build_header()`` that the concrete subclass, or another base of that
        subclass, defines (ADR-0026). A class with a base outside the project may get the name
        from there, so it is left to that rule.
        """

        receiver = attribute.value
        if not (isinstance(receiver, ast.Name) and receiver.id in {"self", "cls"}):
            return []
        owner = self._containing_class()
        if owner is None or receiver.id in self._locals - {"self", "cls"}:
            return []
        if self.resolver.lookup_member(owner, attribute.attr) is not None:
            return []
        if self.resolver.external_bases(owner):
            return []
        found: dict[NodeId, PythonSymbol] = {}
        for subclass in self.resolver.subclasses_of(owner):
            for base in self.resolver.mro(subclass):
                member = self.resolver.resolve_full_name(
                    f"{base.module}.{base.qualified_name}.{attribute.attr}"
                )
                if member is not None:
                    found[member.id] = member
        return [found[key] for key in sorted(found)]

    def _use(self, symbol: PythonSymbol) -> None:
        """A definition whose attribute the code reads, and that nothing resolved to a member.

        A class is needed for its attribute, a field or a member of a base outside the project. The
        attribute is not one of its methods, for a method would have resolved, so the methods do
        not run with it (ADR-0027).
        """

        if symbol.kind is NodeKind.CLASS:
            self._named_classes.add(symbol.id)
        else:
            self._escaped.add(symbol.id)

    def _reference_receiver(self, attribute: ast.Attribute) -> None:
        """An attribute that did not resolve: its receiver escapes or its type is unknown."""

        receiver = attribute.value
        if self._is_super(attribute):
            return
        provided = self._members_provided_by_subclasses(attribute)
        if provided:
            self._escaped.update(member.id for member in provided)
            return
        if isinstance(receiver, ast.Name) and receiver.id in self._dynamic_modules:
            self._escaped.update(self.resolver.top_level_named(attribute.attr))
            return
        if self._unknown_local_head(attribute):
            if self.resolver.methods_named(attribute.attr):
                self._dispatched.add(attribute.attr)
            return
        # ``gateways.mikrotik()`` on a ``Gateways`` whose base supplies ``mikrotik``: no member is
        # found, and what a subclass, or a stand-in in a test, defines under the name may run.
        type_name = self._infer_expression_type(receiver)
        receiver_class = self.resolver.class_named(type_name) if type_name is not None else None
        if (
            receiver_class is not None
            and not (isinstance(receiver, ast.Name) and receiver.id in {"self", "cls"})
            and self.resolver.lookup_member(receiver_class, attribute.attr) is None
        ):
            self._escaped.update(
                member.id for member in self.resolver.overrides(receiver_class, attribute.attr)
            )
        symbol = self._resolve(receiver) if _dotted_name(receiver) is not None else None
        if symbol is not None:
            self._use(symbol)
            return
        # ``Status.ACTIVE.value``: ``Status.ACTIVE`` is no project symbol, but ``Status`` is, and
        # evaluating the chain uses it (ADR-0017).
        prefix = receiver.value if isinstance(receiver, ast.Attribute) else None
        while isinstance(prefix, (ast.Attribute, ast.Name)):
            found = self._resolve(prefix)
            if found is not None:
                self._use(found)
                break
            prefix = prefix.value if isinstance(prefix, ast.Attribute) else None
        if self._known_receiver(receiver):
            if self.resolver.stand_in_methods_named(attribute.attr) and not (
                self._infer_expression_type(receiver) or self._receiver_is_project(receiver)
            ):
                self._stand_ins.add(attribute.attr)
            return
        if self.resolver.methods_named(attribute.attr):
            self._dispatched.add(attribute.attr)

    def _unknown_local_head(self, attribute: ast.Attribute) -> bool:
        """``name.attr`` where ``name`` is a plain local value of unknown type.

        Such a head cannot resolve to a project symbol, so only method-name dispatch applies.
        """

        head = attribute.value
        if not isinstance(head, ast.Name):
            return False
        name = head.id
        value = self._receiver_values.get(name)
        if value is not None:
            return value.unknown or (bool(value.types) and value.external)
        return (
            name in self._locals
            and name not in self.local_types
            and name not in self.external_locals
            and name not in self._local_imports
            and name not in {"self", "cls"}
        )

    def _inferred_member(self, attribute: ast.Attribute) -> PythonSymbol | None:
        """The member an attribute names on a value whose project type is inferred."""

        if isinstance(attribute.value, (ast.Name, ast.Attribute)):
            return None
        type_name = self._infer_expression_type(attribute.value)
        if type_name is None:
            return None
        return self.resolver.typed_member(type_name, [attribute.attr])

    def _known_receiver(self, receiver: ast.expr) -> bool:
        """Whether the type of ``receiver`` is a project class or lies outside the project."""

        if not isinstance(receiver, (ast.Name, ast.Attribute)) and (
            self._infer_expression_type(receiver) is not None
        ):
            return True

        dotted = _dotted_name(receiver)
        if dotted is not None:
            first, *rest = dotted.split(".")
            value = self._receiver_values.get(first)
            if value is not None and not rest:
                return not value.unknown and bool(value.types or value.external)
            if first in self.external_locals:
                return True
            if not rest and (first in self.local_types or first in {"self", "cls"}):
                return first in self.local_types
            if (
                first == "self"
                and len(rest) == 1
                and self.current is not None
                and (
                    f"{self.module.name}.{_containing_class_qname(self.current)}",
                    rest[0],
                )
                in self.class_field_types
            ):
                return True
            if not rest and first in self.resolver.module_types.get(self.module.name, {}):
                return True
        return self.resolver.is_external(receiver, self.module)

    def _apply_decorator(self, decorator: ast.expr, decorated: PythonSymbol | None) -> None:
        if isinstance(decorator, ast.Call):
            self.visit_expression(decorator)
            factory = self._resolve(decorator.func)
            name = self._external_name(decorator.func) or "a decorator call"
            if factory is None and _is_transparent_decorator(name):
                return
            reason = (
                f"decorated with the result of {factory.module}.{factory.qualified_name}(...)"
                if factory is not None
                else f"registered by decorator {name}"
            )
            self._escape_decorated(decorated, reason)
            return
        self.mark_references(decorator)
        applied = self._resolve(decorator)
        if applied is None:
            if isinstance(decorator, ast.Attribute):
                self._reference_receiver(decorator)
            name = self._external_name(decorator) or "a decorator"
            if not _is_transparent_decorator(name):
                self._escape_decorated(decorated, f"registered by decorator {name}")
            return
        kind = EdgeKind.CONSTRUCT if applied.kind is NodeKind.CLASS else EdgeKind.CALL
        self.edges.append(
            ExecutionEdge(
                self.source,
                applied.id,
                kind,
                f"applies decorator {applied.module}.{applied.qualified_name}",
            )
        )
        if applied.kind is NodeKind.CLASS:
            initializer = self.resolver.lookup_member(applied, "__init__")
            if initializer is not None:
                self.edges.append(
                    ExecutionEdge(
                        self.source,
                        initializer.id,
                        EdgeKind.CONSTRUCT,
                        f"constructs decorator {applied.module}.{applied.qualified_name}",
                    )
                )
        first = applied.parameters[0].name if applied.parameters else None
        if (
            decorated is not None
            and is_function(applied)
            and first is not None
            and first in self.resolver.called_parameter_names(applied)
        ):
            self.edges.append(
                ExecutionEdge(
                    applied.id,
                    decorated.id,
                    EdgeKind.CALLBACK,
                    f"decorator calls the decorated {decorated.qualified_name}",
                )
            )
            return
        self._escape_decorated(decorated, f"decorated by {applied.module}.{applied.qualified_name}")

    def _escape_decorated(self, decorated: PythonSymbol | None, reason: str) -> None:
        if decorated is None:
            return
        self.boundaries.append(
            UnknownBoundary(
                source=self.source,
                domain="decorator_registration",
                reason=reason,
                targets=(decorated.id,),
            )
        )

    def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
        """``with open(path) as stream``: a manager from outside the project yields its value.

        The value is what the manager's ``__enter__`` returns, which a manager outside the
        project takes from outside it too, so methods called on it are not project methods of
        the same name (ADR-0018).
        """

        for item in node.items:
            target = item.optional_vars
            if not isinstance(target, ast.Name):
                continue
            self._set_receiver(target.id, UNKNOWN_RECEIVER)
            self._container_locals.discard(target.id)
            manager = item.context_expr
            if not isinstance(manager, ast.Call) or self._resolve(manager.func) is not None:
                continue
            function = manager.func
            builtin = (
                isinstance(function, ast.Name)
                and function.id not in self._names
                and function.id not in self._locals
                and function.id not in self._local_imports
                and function.id in BUILTIN_MANAGERS
            )
            if builtin or self.resolver.is_external(function, self.module):
                self._set_receiver(target.id, EXTERNAL_RECEIVER)

    def _visit_assign(self, node: ast.Assign) -> None:
        string_value = self._string_value(node.value)
        if (
            isinstance(node.value, ast.Call)
            and self._external_name(node.value.func) in DYNAMIC_IMPORTS
        ):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            self._dynamic_modules.update(names)
            for name in names:
                self._set_receiver(name, UNKNOWN_RECEIVER)
            return
        value = self._receiver_value(node.value)
        container = _is_container_value(node.value)
        for target in node.targets:
            if not isinstance(target, ast.Name):
                for child in ast.walk(target):
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                        self._set_receiver(child.id, UNKNOWN_RECEIVER)
                        self._container_locals.discard(child.id)
                continue
            if container:
                self._container_locals.add(target.id)
            else:
                self._container_locals.discard(target.id)
            self._set_receiver(target.id, value)
            if self._track_strings:
                self._string_values[target.id] = string_value
            self._dynamic_modules.discard(target.id)

    def _visit_named_expression(self, node: ast.NamedExpr) -> None:
        self.visit_expression(node.value)
        self._set_receiver(node.target.id, self._receiver_value(node.value))
        self._container_locals.discard(node.target.id)

    def _visit_ann_assign(self, node: ast.AnnAssign) -> None:
        string_value = self._string_value(node.value) if node.value is not None else StringValue()
        calls = _outermost_calls(node.annotation) if self._evaluates_annotations else []
        inside_calls = {id(part) for call in calls for part in ast.walk(call)}
        for part in ast.walk(node.annotation):
            if id(part) not in inside_calls:
                self._handled.add(id(part))
        for call in calls:
            self._visit_annotation_calls(call)
        if self._evaluates_annotations:
            scope = self.current.qualified_name if self.current is not None else None
            for class_symbol in self.resolver.annotation_classes(
                node.annotation, self.module, scope
            ):
                self.edges.append(
                    ExecutionEdge(
                        self.source,
                        class_symbol.id,
                        EdgeKind.ANNOTATION,
                        f"annotation uses {class_symbol.module}.{class_symbol.qualified_name}",
                    )
                )
        if isinstance(node.target, ast.Name):
            if _is_container_annotation(node.annotation) or (
                node.value is not None and _is_container_value(node.value)
            ):
                self._container_locals.add(node.target.id)
            else:
                self._container_locals.discard(node.target.id)
            inferred = self._resolve_annotation(node.annotation)
            value = self._receiver_value(node.value) if node.value is not None else UNKNOWN_RECEIVER
            if node.value is not None:
                self._set_receiver(node.target.id, value)
            elif inferred is not None:
                self._set_receiver(node.target.id, ReceiverValue(frozenset({inferred})))
            else:
                self._set_receiver(node.target.id, value)
            if self._track_strings and node.value is not None:
                self._string_values[node.target.id] = string_value

    def _string_value(self, expression: ast.expr) -> StringValue:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return StringValue(frozenset({expression.value}), unknown=False)
        if not self._track_strings:
            return StringValue()
        if isinstance(expression, ast.Name):
            return self._string_values.get(expression.id, StringValue())
        if isinstance(expression, ast.IfExp):
            return self._string_value(expression.body).join(self._string_value(expression.orelse))
        return StringValue()

    def _initial_local_types(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if self.current is None:
            return result
        containing_class = _containing_class_qname(self.current)
        if containing_class is not None:
            result["self"] = f"{self.module.name}.{containing_class}"
            parameters = self.current.parameters
            if parameters and parameters[0].name == "cls":
                result["cls"] = result["self"]
        for parameter in self.current.parameters:
            if parameter.annotation is None:
                continue
            resolved = self._resolve_annotation(parameter.annotation)
            if resolved is not None:
                result[parameter.name] = resolved
            elif self.resolver.annotation_is_external(parameter.annotation, self.module):
                self.external_locals.add(parameter.name)
        return result

    def _external_value_annotation_origin(self, annotation: ast.expr) -> str | None:
        """A simple imported external value type, under the existing annotation contract.

        Generic, structural/opaque typing annotations, unions and module types cannot justify
        restricting reflection to instance members. Alternative bindings must agree.
        """
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            parsed = _parsed_annotation(annotation.value)
            if parsed is None:
                return None
            annotation = parsed
        if not isinstance(annotation, (ast.Name, ast.Attribute)):
            return None
        if not self.resolver.annotation_is_external(annotation, self.module):
            return None
        dotted = _dotted_name(annotation)
        assert dotted is not None
        head, _, rest = dotted.partition(".")
        binding = self.module.imports[head]
        bindings = self.module.import_alternatives.get(head, (binding,))
        origins = {f"{item.target}.{rest}" if rest else item.target for item in bindings}
        accepted = len(origins) == 1 and all(
            not origin.startswith(("typing.", "typing_extensions."))
            and origin != "types.ModuleType"
            and not self.resolver.in_project(origin)
            for origin in origins
        )
        return next(iter(origins)) if accepted else None

    def _external_reflection_targets(self, receiver: ast.expr) -> tuple[NodeId, ...] | None:
        """All project class members remain possible, including subclasses and stand-ins.

        An external base may itself inherit another unscanned external base. Without dependency
        source, matching its spelling to the parameter annotation is insufficient. Recognized
        standard nominal families refine ancestry; opaque bases retain protection. Escaped
        callable values retain their own guards. Method-name filtering is not applied here.
        """
        value = self._receiver_values.get(receiver.id) if isinstance(receiver, ast.Name) else None
        if (
            not self._track_strings
            or value is None
            or not value.external_annotation
            or value.unknown
            or value.types
        ):
            return None
        owners: set[NodeId] | None = None
        if value.external_nominal in NOMINAL_FAMILIES:
            owners = set()
            for symbol in self.resolver.symbols.values():
                if symbol.kind is not NodeKind.CLASS:
                    continue
                possible = is_test_path(symbol.path)
                for ancestor in self.resolver.mro(symbol):
                    assert isinstance(ancestor.node, ast.ClassDef)
                    module = self.resolver.modules[ancestor.module]
                    for base in ancestor.node.bases:
                        resolved = self.resolver.resolve_expression(
                            base,
                            module=module,
                            current=self.resolver.enclosing_scope(ancestor),
                            local_types={},
                            class_field_types={},
                        )
                        if resolved is not None and resolved.kind is NodeKind.CLASS:
                            continue
                        name = _base_name(self.resolver, base, module)
                        # Bare builtin spellings can be rebound; never treat them as metadata
                        # when their head is bound by source or by an enclosing local scope.
                        head = _dotted_name(base.value if isinstance(base, ast.Subscript) else base)
                        scope = self.resolver.enclosing_scope(ancestor)
                        head_name = head.split(".")[0] if head is not None else ""
                        shadowed = (
                            (scope is not None and head_name in self.resolver.local_names(scope))
                            or head_name in module.import_alternatives
                            or (
                                name in ROOT_BASES
                                and name in self.resolver.top_level_bindings(module)
                            )
                            or head_name in self.resolver._nominal_rebindings[module.name]
                            or head in self.resolver._nominal_rebindings[module.name]
                        )
                        if (
                            resolved is not None
                            or shadowed
                            or head is None
                            or may_supply_nominal_value(name, value.external_nominal)
                        ):
                            possible = True
                if possible:
                    owners.update(item.id for item in self.resolver.mro(symbol))
        return tuple(
            sorted(
                symbol.id
                for symbol in self.resolver.symbols.values()
                if symbol.owner is not None
                and self.resolver.symbols[symbol.owner].kind is NodeKind.CLASS
                and (owners is None or symbol.owner in owners)
            )
        )

    def _resolve_annotation(self, annotation: ast.expr) -> str | None:
        """The one project class an annotation names; ``A | B`` names no single class (ADR-0022)."""

        found: set[str] = set()
        for name in _annotation_names(annotation, self.module.text):
            binding = self.module.imports.get(name.split(".", 1)[0])
            if binding is not None:
                rest = name.split(".", 1)
                candidate = binding.target if len(rest) == 1 else f"{binding.target}.{rest[1]}"
            else:
                candidate = f"{self.module.name}.{name}"
            symbol = self.resolver.resolve_full_name(candidate)
            if symbol is not None and symbol.kind is NodeKind.CLASS:
                found.add(f"{symbol.module}.{symbol.qualified_name}")
        return next(iter(found)) if len(found) == 1 else None

    def _infer_expression_type(self, expression: ast.expr) -> str | None:
        if isinstance(expression, ast.Name):
            value = self._receiver_values.get(expression.id)
            if value is not None:
                return (
                    next(iter(value.types))
                    if value.project_only and len(value.types) == 1
                    else None
                )
            return self.local_types.get(expression.id)
        if isinstance(expression, ast.Attribute) and expression.attr == "__class__":
            return self._infer_expression_type(expression.value)
        if (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "type"
            and "type" not in self._locals
            and len(expression.args) == 1
        ):
            return self._infer_expression_type(expression.args[0])
        if isinstance(expression, ast.Call):
            target = self._resolve(expression.func)
            if target is not None and target.kind is NodeKind.CLASS:
                return f"{target.module}.{target.qualified_name}"
            if target is not None and target.return_annotation is not None:
                return self._resolve_annotation(target.return_annotation)
        return None

    def _receiver_value(self, expression: ast.expr) -> ReceiverValue:
        if isinstance(expression, ast.Name) and expression.id in self._receiver_values:
            return self._receiver_values[expression.id]
        if isinstance(expression, ast.IfExp):
            return self._receiver_value(expression.body).join(
                self._receiver_value(expression.orelse)
            )
        if isinstance(expression, ast.Call):
            target = self._resolve(expression.func)
            alternatives = self._alternative_targets(expression.func, target)
            if alternatives:
                result = ReceiverValue()
                type_name: str | None
                for possible in ([target] if target is not None else []) + alternatives:
                    if possible.kind is NodeKind.CLASS:
                        type_name = f"{possible.module}.{possible.qualified_name}"
                    else:
                        type_name = (
                            self._resolve_annotation(possible.return_annotation)
                            if possible.return_annotation is not None
                            else None
                        )
                    result = result.join(
                        ReceiverValue(frozenset({type_name}))
                        if type_name is not None
                        else UNKNOWN_RECEIVER
                    )
                if target is None:
                    result = result.join(UNKNOWN_RECEIVER)
                return result
        inferred = self._infer_expression_type(expression)
        if inferred is not None:
            return ReceiverValue(frozenset({inferred}))
        if (
            isinstance(expression, ast.Call)
            and self._resolve(expression.func) is None
            and (self.resolver.is_external(expression.func, self.module))
        ):
            return EXTERNAL_RECEIVER
        return UNKNOWN_RECEIVER

    def _is_external_module(self, receiver: ast.expr) -> bool:
        """``pkg`` or ``pkg.sub`` where ``pkg`` is imported from outside the project.

        ``getattr(pyautogui, action)`` returns an attribute of a third-party module, which calls
        no project code unless it is passed some, so it is no unknown boundary (ADR-0017).
        """

        head = receiver
        while isinstance(head, ast.Attribute):
            head = head.value
        if not isinstance(head, ast.Name):
            return False
        binding = self._local_imports.get(head.id)
        if binding is None and head.id not in self._locals:
            binding = self.module.imports.get(head.id)
        return binding is not None and not self.resolver.in_project(binding.target)

    def _receiver_methods(self, receiver: ast.expr) -> tuple[NodeId, ...] | None:
        """Methods, inherited ones too, that an attribute of ``receiver`` of known type may be."""

        value = self._receiver_values.get(receiver.id) if isinstance(receiver, ast.Name) else None
        if value is not None:
            if not value.project_only:
                return None
            receiver_types = value.types
        else:
            receiver_type = self._infer_expression_type(receiver)
            if receiver_type is None:
                return None
            receiver_types = frozenset({receiver_type})
        # The value may be an instance of a project subclass, as ``getattr(self, ...)`` in a
        # base class of a visitor: its methods count as well.
        owners: list[str] = []
        for receiver_type in sorted(receiver_types):
            class_symbol = self.resolver.class_named(receiver_type)
            if class_symbol is None:
                owners.append(receiver_type)
            else:
                owners.extend(
                    f"{item.module}.{item.qualified_name}"
                    for item in (
                        *self.resolver.mro(class_symbol),
                        *self.resolver.subclasses_of(class_symbol),
                    )
                )
        return tuple(
            sorted(
                {
                    symbol.id
                    for owner in owners
                    for symbol in self.resolver.index.under(f"{owner}.")
                    if symbol.kind is NodeKind.FUNCTION
                }
            )
        )

    def _module_members(self, receiver: ast.expr, name: ast.expr) -> tuple[NodeId, ...]:
        """Selected definitions and imported callable aliases of a project module.

        Select names in each exporting namespace before traversing its import bindings;
        an exported ``run`` can name a definition called ``work`` in another module.
        """

        if not isinstance(receiver, ast.Name):
            return ()
        binding = self._local_imports.get(receiver.id) or self.module.imports.get(receiver.id)
        module = self.resolver.modules.get(binding.target) if binding is not None else None
        if module is None:
            return ()
        value = self._string_value(name)
        selection = None if value.unknown else value.names
        pending: list[tuple[str, frozenset[str] | None]] = [(module.name, selection)]
        seen: set[tuple[str, frozenset[str] | None]] = set()
        targets: set[NodeId] = set()
        while pending:
            module_name, selected = pending.pop()
            key = (module_name, selected)
            if key in seen:
                continue
            seen.add(key)
            owner = self.resolver.modules.get(module_name)
            if owner is None:
                continue
            direct = tuple(
                symbol.id
                for symbol in owner.symbols
                if symbol.owner is None and (selected is None or symbol.name in selected)
            )
            if owner is module and selected is None:
                direct = self._named_like(direct, name)
            targets.update(direct)
            for local, imported in owner.imports.items():
                if selected is not None and local not in selected:
                    continue
                for alternative in owner.import_alternatives.get(local, (imported,)):
                    full_name = alternative.target
                    targets.update(symbol.id for symbol in self.resolver.index.named(full_name))
                    parent, _, attribute = full_name.rpartition(".")
                    if parent in self.resolver.modules:
                        pending.append((parent, frozenset({attribute})))
            pending.extend((base, selected) for base in owner.star_imports)
        return tuple(sorted(targets))

    def _record_getattr_value(self, call: ast.Call) -> None:
        """``getattr(core, name)`` may return a callable that is invoked later.

        The value may be called anywhere later, as a ``message_generator`` argument, so its
        methods may run. Only receivers of a known project type are localized here; a call of
        the value itself is handled with the call (ADR-0022).
        """

        arguments = call_arguments(call)
        if len(arguments) < 2:
            return
        receiver = arguments[0].value
        if self._is_external_module(receiver):
            return
        external_targets = self._external_reflection_targets(receiver)
        if external_targets is not None:
            targets = external_targets
        else:
            targets = self._receiver_methods(receiver) or ()
            if targets:
                targets = self._named_like(targets, arguments[1].value)
            else:
                targets = self._module_members(receiver, arguments[1].value)
        if targets:
            self.boundaries.append(
                UnknownBoundary(
                    source=self.source,
                    domain="dynamic_attribute_dispatch",
                    reason="dynamic getattr call target cannot be resolved statically",
                    targets=targets,
                )
            )

    def _named_like(self, targets: tuple[NodeId, ...], name: ast.expr) -> tuple[NodeId, ...]:
        """The targets whose names fit the constant start and end of a computed attribute name.

        ``getattr(self, "save_" + kind)`` reads a method that starts with ``save_``. The name may be
        a local that one assignment gave such a value (ADR-0028).
        """

        if not targets:
            return targets
        value = self._string_value(name)
        if not value.unknown:
            return tuple(
                target
                for target in targets
                if (symbol := self.resolver.symbols.get(target)) is not None
                and symbol.name in value.names
            )
        prefix, suffix = _constant_affixes(name)
        if not (prefix or suffix) and isinstance(name, ast.Name) and self.current is not None:
            values = [
                node.value
                for node in ast.walk(self.current.node)
                if isinstance(node, ast.Assign)
                and any(isinstance(item, ast.Name) and item.id == name.id for item in node.targets)
            ]
            if len(values) == 1:
                prefix, suffix = _constant_affixes(values[0])
        if not (prefix or suffix):
            return targets
        return tuple(
            target
            for target in targets
            if (symbol := self.resolver.symbols.get(target)) is not None
            and symbol.name.startswith(prefix)
            and symbol.name.endswith(suffix)
        )

    def _record_dynamic_getattr(self, function: ast.Call) -> None:
        targets: tuple[NodeId, ...] = ()
        arguments = call_arguments(function)
        if arguments:
            receiver = arguments[0].value
            if self._is_external_module(receiver):
                return  # an attribute of a module outside the project is not project code
            external_targets = self._external_reflection_targets(receiver)
            if external_targets is not None:
                if external_targets:
                    self.boundaries.append(
                        UnknownBoundary(
                            source=self.source,
                            domain="dynamic_attribute_dispatch",
                            reason="external value may supply a project subclass or stand-in",
                            targets=external_targets,
                        )
                    )
                return
            targets = self._receiver_methods(receiver) or ()
            if len(arguments) > 1:
                names = self._string_value(arguments[1].value)
                if not names.unknown and targets:
                    targets = self._named_like(targets, arguments[1].value)
                    if not targets:
                        return  # Empty finite selection must not become a whole-graph guard.
                targets = self._named_like(targets, arguments[1].value)
        self.boundaries.append(
            UnknownBoundary(
                source=self.source,
                domain="dynamic_attribute_dispatch",
                reason="dynamic getattr call target cannot be resolved statically",
                targets=targets,
            )
        )

    def _record_escaped_project_callables(self, call: ast.Call) -> None:
        escaped: set[NodeId] = set()
        consumer = self._external_name(call.func)
        if (
            isinstance(call.func, ast.Name)
            and call.func.id in self._locals
            and call.func.id not in self._local_imports
        ):
            consumer = None  # an unresolved local callable is not a builtin of that name
        for argument in call_arguments(call):
            if _consumer_calls_instance_methods(consumer) and not (
                self._stores_in_container(call.func)
            ):
                value = self._receiver_value(argument.value)
                for possible_type in value.types:
                    instance_class = self.resolver.class_named(possible_type)
                    if instance_class is not None:
                        escaped.add(instance_class.id)
            # ``add_task(Core(user).cleanup)`` passes a method of an instance built in place.
            target = self._resolve(argument.value) or (
                self._inferred_member(argument.value)
                if isinstance(argument.value, ast.Attribute)
                else None
            )
            self.mark_references(argument.value)
            if (
                target is None
                and isinstance(argument.value, (ast.Call, ast.Name))
                and _consumer_calls_instance_methods(self._external_name(call.func))
                and not self._stores_in_container(call.func)
            ):
                # ``Controller(Handler(port))``: the consumer calls the methods of an instance of a
                # project class, as a protocol such as a handler's ``handle_DATA`` (ADR-0022).
                type_name = self._infer_expression_type(argument.value)
                instance_class = (
                    self.resolver.class_named(type_name) if type_name is not None else None
                )
                if instance_class is not None:
                    escaped.add(instance_class.id)
                    continue
            if target is not None:
                escaped.add(target.id)
                escaped.update(self._overrides_of_reference(argument.value, target))
                escaped.update(
                    item.id for item in self._alternative_targets(argument.value, target)
                )
            elif isinstance(argument.value, ast.Attribute):
                self._reference_receiver(argument.value)
        if escaped:
            external = self._external_name(call.func) or "unknown consumer"
            self.boundaries.append(
                UnknownBoundary(
                    source=self.source,
                    domain="escaped_callable",
                    reason=f"project callable escapes to unresolved consumer {external}",
                    targets=tuple(sorted(escaped)),
                )
            )
            if external not in INSPECTING_CONSUMERS:
                self._expose_classes(escaped, external)

    def _stores_in_container(self, function: ast.expr) -> bool:
        """``items.append(Handler())`` on a builtin container keeps the instance, calls nothing.

        The methods run where the value is read back, and a call there is resolved by the type of
        the value or guarded by the name it calls (ADR-0027).
        """

        if not isinstance(function, ast.Attribute) or function.attr not in CONTAINER_STORES:
            return False
        receiver = function.value
        if isinstance(receiver, ast.Name):
            return receiver.id in self._container_locals
        return (
            isinstance(receiver, ast.Attribute)
            and isinstance(receiver.value, ast.Name)
            and receiver.value.id == "self"
            and receiver.attr in self._container_attributes
        )

    def _overrides_of_reference(
        self, expression: ast.expr, target: PythonSymbol
    ) -> tuple[NodeId, ...]:
        """Overrides in project subclasses of a method referenced as ``self.method``.

        A method passed as a value is called on the same instance, which may be of a subclass, as
        a call of it would be.
        """

        if not isinstance(expression, ast.Attribute) or not self._through_instance(expression):
            return ()
        owner = self.resolver.symbols.get(target.owner) if target.owner is not None else None
        if owner is None or owner.kind is not NodeKind.CLASS:
            return ()
        # ``self`` is an instance of the class the method is in or of a subclass of it, so a
        # sibling class that derives from the base beside it never receives the call.
        receiver = (
            self._containing_class()
            if isinstance(expression.value, ast.Name) and expression.value.id in {"self", "cls"}
            else None
        )
        return tuple(item.id for item in self.resolver.overrides(receiver or owner, target.name))

    def _expose_classes(self, escaped: set[NodeId], external: str) -> None:
        """A consumer that receives a class may call its methods: one boundary per class.

        The class is among the targets, so a capability that models the consumer can recognize the
        boundary by the class it names.
        """

        for target in sorted(escaped):
            symbol = self.resolver.symbols.get(target)
            if symbol is None or symbol.kind is not NodeKind.CLASS:
                continue
            methods = self.resolver.exposed_methods(symbol)
            if methods:
                self.boundaries.append(
                    UnknownBoundary(
                        source=self.source,
                        domain="escaped_class",
                        reason=(
                            f"methods of {symbol.module}.{symbol.qualified_name} may be called by"
                            f" unresolved consumer {external}"
                        ),
                        targets=tuple(sorted({target, *methods})),
                    )
                )

    def _link_callable_arguments(self, call: ast.Call, target: PythonSymbol) -> None:
        called_parameters = self.resolver.called_parameter_names(target)
        if not called_parameters:
            return
        parameters = list(target.parameters)
        if target.owner_qualified_name is not None and isinstance(call.func, ast.Attribute):
            parameters = parameters[1:]
        position = 0
        for argument in call_arguments(call):
            if argument.star:
                continue
            if argument.keyword is not None:
                parameter_name = argument.keyword
            elif position < len(parameters):
                parameter_name = parameters[position].name
                position += 1
            else:
                continue
            if parameter_name not in called_parameters:
                continue
            callback = self._resolve(argument.value)
            if callback is not None:
                self.mark_references(argument.value)
                for reached in (
                    callback.id,
                    *self._overrides_of_reference(argument.value, callback),
                    *(item.id for item in self._alternative_targets(argument.value, callback)),
                ):
                    self.edges.append(
                        ExecutionEdge(
                            target.id,
                            reached,
                            EdgeKind.CALLBACK,
                            f"invokes callable argument {parameter_name}",
                        )
                    )


def _local_names(scope: PythonSymbol) -> tuple[frozenset[str], bool]:
    """Names a function binds locally, which shadow project symbols of the same name, and whether
    its body has an import statement.

    Only statements bind names that outlive them, so the search stays at statement level: targets
    of assignments, loops, ``with``, ``except``, imports, and ``match`` captures, plus parameters.
    Nested definitions are not included: they are symbols themselves and resolve as such.
    Assignment expressions (``:=``) are not seen; a name bound only that way does not shadow.
    """

    if isinstance(scope.node, ast.ClassDef):
        return frozenset(), False
    names = {parameter.name for parameter in scope.parameters}
    declared: set[str] = set()
    has_imports = False
    stack: list[ast.stmt] = list(scope.node.body)
    while stack:
        statement = stack.pop()
        if isinstance(statement, DEFINITION_TYPES):
            continue
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                _bound_names(target, names)
        elif isinstance(statement, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor)):
            _bound_names(statement.target, names)
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                if item.optional_vars is not None:
                    _bound_names(item.optional_vars, names)
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            has_imports = True
            names.update(
                alias.asname or alias.name.split(".")[0]
                for alias in statement.names
                if alias.name != "*"
            )
        elif isinstance(statement, (ast.Global, ast.Nonlocal)):
            declared.update(statement.names)
        elif isinstance(statement, (ast.Try, ast.TryStar)):
            names.update(handler.name for handler in statement.handlers if handler.name)
        elif isinstance(statement, ast.Match):
            for case in statement.cases:
                for node in ast.walk(case.pattern):
                    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                        names.add(node.name)
                    elif isinstance(node, ast.MatchMapping) and node.rest:
                        names.add(node.rest)
        stack.extend(child_statements(statement))
    return frozenset(names - declared), has_imports


def _bound_names(target: ast.expr, names: set[str]) -> None:
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            _bound_names(element, names)
    elif isinstance(target, ast.Starred):
        _bound_names(target.value, names)


def _structural_edges(
    modules: dict[str, PythonModule],
    symbols: dict[NodeId, PythonSymbol],
    resolver: _Resolver,
) -> list[ExecutionEdge]:
    """Edges that hold whenever a symbol is used: its owner, its bases, and annotation classes."""

    edges: list[ExecutionEdge] = []
    for symbol in symbols.values():
        owner = symbols.get(symbol.owner) if symbol.owner is not None else None
        if owner is not None:
            edges.append(
                ExecutionEdge(
                    symbol.id,
                    owner.id,
                    EdgeKind.MEMBER,
                    f"defined in {owner.module}.{owner.qualified_name}",
                )
            )
        if symbol.kind is NodeKind.CLASS:
            for base in resolver.bases(symbol):
                # A base defined in both branches of a condition is whichever one ran.
                for candidate in (base, *resolver.alternatives(base)):
                    edges.append(
                        ExecutionEdge(
                            symbol.id,
                            candidate.id,
                            EdgeKind.INHERIT,
                            f"inherits from {candidate.module}.{candidate.qualified_name}",
                        )
                    )
            continue
        module = modules[symbol.module]
        implementation = _overload_implementation(symbol, module, resolver)
        if implementation is not None:
            edges.append(
                ExecutionEdge(
                    implementation.id,
                    symbol.id,
                    EdgeKind.ANNOTATION,
                    f"overload signature of {symbol.module}.{symbol.qualified_name}",
                )
            )
        annotations = [parameter.annotation for parameter in symbol.parameters]
        annotations.append(symbol.return_annotation)
        # A method's signature is evaluated in the body of its class.
        scope = symbol.owner_qualified_name
        for annotation in annotations:
            if annotation is None:
                continue
            for class_symbol in resolver.annotation_classes(annotation, module, scope):
                edges.append(
                    ExecutionEdge(
                        symbol.id,
                        class_symbol.id,
                        EdgeKind.ANNOTATION,
                        f"annotation uses {class_symbol.module}.{class_symbol.qualified_name}",
                    )
                )
    return edges


def _overload_implementation(
    symbol: PythonSymbol, module: PythonModule, resolver: _Resolver
) -> PythonSymbol | None:
    """The definition an ``@overload`` signature describes: the next one of its name without it."""

    if not symbol.decorators or not any(
        resolver.external_name(decorator, module) in OVERLOAD_DECORATORS
        for decorator in symbol.decorators
    ):
        return None
    for candidate in resolver.index.named(f"{symbol.module}.{symbol.qualified_name}"):
        if candidate.occurrence > symbol.occurrence and not any(
            resolver.external_name(decorator, module) in OVERLOAD_DECORATORS
            for decorator in candidate.decorators
        ):
            return candidate
    return None


def flow_nodes(statements: Iterable[ast.stmt]) -> Iterator[ast.AST]:
    """Nodes of ``statements`` in order, without entering nested function or class definitions.

    Statements come in source order, and each one comes before the expressions it contains and the
    statements nested in it, so an assignment is seen before the calls that follow it. A nested
    definition is yielded itself, so a consumer can evaluate its header, but nothing inside it is.
    The order among the expression nodes of one statement is not significant to any consumer.
    """

    for statement in statements:
        yield statement
        if not isinstance(statement, DEFINITION_TYPES):
            yield from _flow_parts(statement)


def _flow_parts(node: ast.AST) -> Iterator[ast.AST]:
    for name in node._fields:
        value = getattr(node, name, None)
        if isinstance(value, list):
            if value and isinstance(value[0], ast.stmt):
                yield from flow_nodes(value)
                continue
            for item in value:
                if isinstance(item, (ast.excepthandler, ast.match_case)):
                    yield item
                    yield from _flow_parts(item)
                elif isinstance(item, ast.AST):
                    yield from ast.walk(item)
        elif isinstance(value, ast.AST):
            yield from ast.walk(value)


def call_arguments(call: ast.Call) -> tuple[CallArgument, ...]:
    """Every argument of ``call`` in source order, starred and keyword arguments included."""

    positional = [
        CallArgument(argument.value, None, "*")
        if isinstance(argument, ast.Starred)
        else CallArgument(argument, None, "")
        for argument in call.args
    ]
    keywords = [
        CallArgument(keyword.value, keyword.arg, "" if keyword.arg is not None else "**")
        for keyword in call.keywords
    ]
    if not keywords or not any(argument.star for argument in positional):
        return (*positional, *keywords)
    located = [
        *(
            ((node.lineno, node.col_offset), argument)
            for node, argument in zip(call.args, positional, strict=True)
        ),
        *(
            ((node.lineno, node.col_offset), argument)
            for node, argument in zip(call.keywords, keywords, strict=True)
        ),
    ]
    return tuple(argument for _position, argument in sorted(located, key=lambda item: item[0]))


def keyword_argument(call: ast.Call, name: str) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def positional_arguments(call: ast.Call) -> list[ast.expr]:
    """Values of the arguments without a keyword, ``*`` and ``**`` unpacking included."""

    return [argument.value for argument in call_arguments(call) if argument.keyword is None]


def subscript_items(subscript: ast.Subscript, text: SourceText) -> tuple[ast.expr, ...]:
    """Items of ``subscript`` as written: ``x[a, b]`` has two and ``x[(a, b)]`` has one."""

    index = subscript.slice
    if isinstance(index, ast.Tuple) and not _parenthesized(index, text):
        return tuple(index.elts)
    return (index,)


def subscript_elements(subscript: ast.Subscript, text: SourceText) -> tuple[ast.expr, ...]:
    """Items of ``subscript`` that are index expressions rather than slices."""

    return tuple(
        item for item in subscript_items(subscript, text) if not isinstance(item, ast.Slice)
    )


def _parenthesized(node: ast.Tuple, text: SourceText) -> bool:
    if not node.elts:
        return True
    first = node.elts[0]
    if (first.lineno, first.col_offset) == (node.lineno, node.col_offset):
        return False
    tokens = _tokens(text.segment(node))
    if tokens is None or not tokens or tokens[0].string != "(":
        return tokens is None
    depth = 0
    for position, token in enumerate(tokens):
        if token.type == tokenize.OP and token.string in "([{":
            depth += 1
        elif token.type == tokenize.OP and token.string in ")]}":
            depth -= 1
            if depth == 0:
                return position == len(tokens) - 1
    return False  # pragma: no cover - a segment starting with "(" always closes it


def single_string_literal(expression: ast.expr | None, text: SourceText) -> str | None:
    """The value of one plain string literal, not a concatenation, f-string, or bytes."""

    if not isinstance(expression, ast.Constant) or not isinstance(expression.value, str):
        return None
    tokens = _tokens(text.segment(expression))
    if tokens is None:  # pragma: no cover - the segment of a parsed literal always tokenizes
        return None
    return expression.value if len(tokens) == 1 and tokens[0].type == tokenize.STRING else None


def _tokens(segment: str) -> list[tokenize.TokenInfo] | None:
    """Significant tokens of an expression's source, parenthesized so line breaks are free."""

    try:
        tokens = [
            token
            for token in tokenize.generate_tokens(io.StringIO(f"({segment})").readline)
            if token.type not in _INSIGNIFICANT_TOKENS
        ]
    except (tokenize.TokenError, SyntaxError):  # pragma: no cover - the segment is valid syntax
        return None
    return tokens[1:-1]


def simple_block_statements(module: PythonModule, node: DefinitionNode) -> tuple[ast.stmt, ...]:
    """Simple statements of an indented block body; none for a body on the header line."""

    first = node.body[0]
    if module.text.line(first.lineno).encode("utf-8")[: first.col_offset].strip():
        return ()
    return tuple(
        statement for statement in node.body if not isinstance(statement, _COMPOUND_STATEMENTS)
    )


def has_main_guard(module: PythonModule) -> bool:
    """Whether the module runs code under ``if __name__ == "__main__":`` at its top level."""

    for statement in module.tree.body:
        if not isinstance(statement, ast.If) or not isinstance(statement.test, ast.Compare):
            continue
        test = statement.test
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            continue
        sides = (test.left, test.comparators[0])
        names = {side.id for side in sides if isinstance(side, ast.Name)}
        values = {
            side.value
            for side in sides
            if isinstance(side, ast.Constant) and isinstance(side.value, str)
        }
        if names == {"__name__"} and values == {"__main__"}:
            return True
    return False


def declared_exports(module: PythonModule) -> frozenset[str] | None:
    """The names a top-level ``__all__`` lists, or ``None`` when it is absent or not literal.

    ``__all__`` may be assigned, extended with ``+=``, ``append``, or ``extend``, all with string
    literals. Any other top-level use as an assignment target makes the list unknown.
    """

    exports: set[str] | None = None
    for statement in module.tree.body:
        if isinstance(statement, ast.Assign) and any(
            _is_all_name(target) for target in statement.targets
        ):
            names = _string_items(statement.value)
            if names is None or len(statement.targets) != 1:
                return None
            exports = set(names)
        elif isinstance(statement, ast.AugAssign | ast.AnnAssign) and _is_all_name(
            statement.target
        ):
            names = _string_items(statement.value) if statement.value is not None else None
            if names is None or (isinstance(statement, ast.AugAssign) and exports is None):
                return None
            if isinstance(statement, ast.AugAssign) and not isinstance(statement.op, ast.Add):
                return None
            exports = set(names) if exports is None else exports | set(names)
        elif (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Attribute)
            and _is_all_name(statement.value.func.value)
        ):
            call = statement.value
            method = call.func.attr if isinstance(call.func, ast.Attribute) else ""
            if exports is None or call.keywords or len(call.args) != 1:
                return None
            argument = call.args[0]
            if method == "append" and isinstance(argument, ast.Constant):
                names = (argument.value,) if isinstance(argument.value, str) else None
            else:
                names = _string_items(argument) if method == "extend" else None
            if names is None:
                return None
            exports |= set(names)
    return frozenset(exports) if exports is not None else None


def _is_all_name(expression: ast.expr) -> bool:
    return isinstance(expression, ast.Name) and expression.id == "__all__"


def _string_items(expression: ast.expr) -> tuple[str, ...] | None:
    if not isinstance(expression, ast.List | ast.Tuple):
        return None
    names = tuple(
        item.value
        for item in expression.elts
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    )
    return names if len(names) == len(expression.elts) else None


def is_function(symbol: PythonSymbol) -> bool:
    return isinstance(symbol.node, (ast.FunctionDef, ast.AsyncFunctionDef))


def _unstarred(expression: ast.expr) -> ast.expr:
    return expression.value if isinstance(expression, ast.Starred) else expression


@dataclass(frozen=True, slots=True)
class _ScopeImports:
    bindings: dict[str, ImportBinding]
    """The binding each name ends up with; the last import of a name wins."""
    alternatives: dict[str, tuple[ImportBinding, ...]]
    """Every binding of the names that more than one import binds, one of them conditionally."""
    star: tuple[str, ...]
    """Project modules imported with ``*``."""


class ImportRoots:
    """How an absolute import names a project module (ADR-0017).

    A name whose first part is a top-level project module or package names it. Otherwise it may
    name a module beside the importer: Python puts a script's own directory on the path, and
    pytest's default import mode puts the directory of a test module that is not in a package
    there. So the directories that hold the importer and are no regular package are tried,
    innermost first. A match only adds modules that may run; an import of an installed
    distribution that shares a sibling's name is taken for the sibling.

    When the first part is only a directory without ``__init__.py`` at the root, as ``shop`` in
    a monorepo's ``shop/shop/main.py``, and the name does not exist under it, the name is looked
    up beside the importer too: the service directory is on the path, and namespace portions of
    one name merge. A name found nowhere else may name a package that a directory of its name
    holds as a distribution, as ``libs/common/common`` for ``common`` installed in editable mode,
    when exactly one such package has that name (ADR-0022).
    """

    def __init__(self, modules: Mapping[str, PythonModule]) -> None:
        self.modules = modules
        self.roots = frozenset(name.split(".")[0] for name in modules)
        self.namespaces = frozenset(prefix for name in modules for prefix in _package_path(name))
        # A distribution keeps its package in a directory of the package's name, as
        # ``libs/common/common``; the package may lack ``__init__.py``.
        found: defaultdict[str, list[str]] = defaultdict(list)
        for name in self.namespaces:
            parent, _, last = name.rpartition(".")
            if parent.rpartition(".")[2] == last and parent not in modules:
                found[last].append(name)
        self.distributions = {last: names[0] for last, names in found.items() if len(names) == 1}

    def absolute(self, importer: PythonModule, name: str, members: Sequence[str] = ()) -> str:
        """The project name ``name`` imports; ``members`` are what ``from name import`` takes."""

        first = name.split(".")[0]
        if not name or first in self.modules or name in self.namespaces:
            return name
        is_package = importer.path.rpartition("/")[2] == "__init__.py"
        directory = importer.name if is_package else importer.name.rpartition(".")[0]
        while directory:
            if directory not in self.modules:
                candidate = f"{directory}.{name}"
                # ``celery.py`` importing ``celery`` means the installed package, not itself, and
                # a directory without ``__init__.py`` such as ``alembic/`` beside ``env.py``
                # shadows an installed package only when it holds the module imported from it.
                if (
                    candidate in self.namespaces
                    and not (importer.name == candidate and not is_package)
                    and (
                        candidate in self.modules
                        or any(f"{candidate}.{member}" in self.namespaces for member in members)
                        or f"{directory}.{first}" in self.modules
                        or first in self.roots
                    )
                ):
                    return candidate
            directory = directory.rpartition(".")[0]
        distribution = self.distributions.get(first)
        if distribution is not None and first not in self.roots:
            candidate = distribution + name[len(first) :]
            if candidate in self.namespaces and candidate != importer.name:
                return candidate
        return name


def _collect_imports(
    module: PythonModule,
    modules: Mapping[str, PythonModule],
    statements: Iterable[ast.stmt],
    roots: ImportRoots | None = None,
) -> _ScopeImports:
    """Names the imports of one scope bind, in nested blocks too but not in nested definitions."""

    roots = roots if roots is not None else ImportRoots(modules)

    bindings: dict[str, ImportBinding] = {}
    every: dict[str, list[ImportBinding]] = {}
    star: list[str] = []
    stack = [(statement, False) for statement in reversed(list(statements))]
    while stack:
        statement, nested = stack.pop()
        found: list[ImportBinding] = []
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                target = alias.name
                local = alias.asname or target.split(".")[0]
                bound_target = roots.absolute(
                    module,
                    target if alias.asname else target.split(".")[0],
                    () if alias.asname else tuple(target.split(".")[1:2]),
                )
                found.append(ImportBinding(local, bound_target, True, statement.lineno, nested))
        elif isinstance(statement, ast.ImportFrom):
            base = _import_from_base(module, statement)
            if base is None:
                continue
            if not statement.level:
                base = roots.absolute(module, base, tuple(alias.name for alias in statement.names))
            for alias in statement.names:
                imported = alias.name
                if imported == "*":
                    if base in modules:
                        star.append(base)
                    continue
                local = alias.asname or imported
                candidate = f"{base}.{imported}" if base else imported
                found.append(
                    ImportBinding(local, candidate, candidate in modules, statement.lineno, nested)
                )
        elif not isinstance(statement, DEFINITION_TYPES):
            stack.extend((child, True) for child in reversed(child_statements(statement)))
        for binding in found:
            bindings[binding.local_name] = binding
            every.setdefault(binding.local_name, []).append(binding)
    return _ScopeImports(
        bindings,
        {
            name: tuple(items)
            for name, items in every.items()
            if len(items) > 1 and any(item.conditional for item in items)
        },
        tuple(dict.fromkeys(star)),
    )


def resolve_through_imports(
    modules: Mapping[str, PythonModule],
    index: SymbolIndex,
    full_name: str,
    memo: dict[str, PythonSymbol | None],
) -> PythonSymbol | None:
    """The symbol a full name reaches through the imports of the module it starts in.

    ``pkg.helper`` names ``pkg._impl.helper`` when ``pkg`` runs ``from pkg._impl import helper``
    or ``from pkg._impl import *``. Chains are followed; an import cycle reaches nothing.
    """

    if full_name in memo:
        return memo[full_name]
    memo[full_name] = None
    parts = full_name.split(".")
    result: PythonSymbol | None = None
    for cut in range(len(parts) - 1, 0, -1):
        module = modules.get(".".join(parts[:cut]))
        if module is None:
            continue
        first, rest = parts[cut], parts[cut + 1 :]
        binding = module.imports.get(first)
        # A name imported in both branches of a condition, one of them from another package,
        # is the project's whichever branch ran.
        bindings = module.import_alternatives.get(first) or ((binding,) if binding else ())
        targets = (
            [".".join((item.target, *rest)) for item in bindings]
            if bindings
            else [".".join((base, first, *rest)) for base in reversed(module.star_imports)]
        )
        for target in targets:
            result = index.resolve(target) or resolve_through_imports(modules, index, target, memo)
            if result is not None:
                break
        break
    memo[full_name] = result
    return result


MODELED_CONSUMER_PACKAGES = ("dishka.", "fastapi.")
"""Packages whose calls the framework model interprets, so instances passed to them are not
handed to an unknown consumer."""


def follow_module_alias(modules: Mapping[str, PythonModule], full: str, depth: int = 0) -> str:
    """``pkg.util.TestCase`` as ``unittest.TestCase`` when ``pkg.util`` binds it to that once."""

    owner, _, attribute = full.rpartition(".")
    source = modules.get(owner)
    alias = _module_alias(source, attribute) if source is not None and depth < 4 else None
    dotted = _dotted_name(alias) if alias is not None else None
    if source is None or dotted is None:
        return full
    first, *rest = dotted.split(".")
    binding = source.imports.get(first)
    if binding is None:
        return full
    expanded = ".".join((binding.target, *rest))
    return follow_module_alias(modules, expanded, depth + 1)


def _module_alias(module: PythonModule, name: str) -> ast.expr | None:
    """The dotted expression a module binds ``name`` to once: ``TestCase = unittest.TestCase``."""

    found: ast.expr | None = None
    for statement in module.tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in statement.targets
        ):
            if found is not None or _dotted_name(statement.value) is None:
                return None
            found = statement.value
    return found


def _is_container_value(value: ast.expr) -> bool:
    """A display, a comprehension, or a call of a builtin container type."""

    if isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in CONTAINER_TYPES
    )


def _is_container_annotation(annotation: ast.expr) -> bool:
    head = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    return isinstance(head, ast.Name) and head.id in CONTAINER_TYPES


@lru_cache(maxsize=256)
def _class_container_attributes(node: ast.ClassDef) -> frozenset[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        value: ast.expr | None
        annotation: ast.expr | None
        if isinstance(child, ast.Assign):
            targets, value, annotation = child.targets, child.value, None
        elif isinstance(child, ast.AnnAssign):
            targets, value, annotation = [child.target], child.value, child.annotation
        else:
            continue
        if not (
            (value is not None and _is_container_value(value))
            or (annotation is not None and _is_container_annotation(annotation))
        ):
            continue
        for target in targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                if target.value.id == "self":
                    names.add(target.attr)
            elif isinstance(target, ast.Name) and child in node.body:
                names.add(target.id)
    return frozenset(names)


def _container_attributes(resolver: _Resolver, current: PythonSymbol | None) -> frozenset[str]:
    """``self`` attributes that a class binds to builtin containers anywhere in its body."""

    if current is None:
        return frozenset()
    owner = _containing_class_qname(current)
    if owner is None:
        return frozenset()
    symbol = resolver.class_named(f"{current.module}.{owner}")
    if symbol is None or not isinstance(symbol.node, ast.ClassDef):
        return frozenset()
    return _class_container_attributes(symbol.node)


def _consumer_calls_instance_methods(consumer: str | None) -> bool:
    """Whether an external consumer may call methods of an instance it receives.

    Builtins such as ``print`` or ``len`` use only special methods, which the hook guards cover;
    modeled frameworks are interpreted by their capability. Any other consumer may call any
    method, as an SMTP controller calls its handler's ``handle_DATA``.
    """

    if consumer is None:
        return True
    return "." in consumer and not consumer.startswith(MODELED_CONSUMER_PACKAGES)


def _relative_import_name(name: str, package: str | None) -> str | None:
    """``importlib.import_module``'s absolute name for ``name``, or None when it is unknown."""

    if not name.startswith("."):
        return name
    if package is None:
        return None
    level = len(name) - len(name.lstrip("."))
    parts = package.split(".")
    if level - 1 > len(parts):
        return None
    base = ".".join(parts[: len(parts) - (level - 1)])
    rest = name[level:]
    return f"{base}.{rest}" if base and rest else base or rest


def _loaded_module_suffix(expression: ast.expr | None) -> str:
    """``.tables`` for ``f"{obj.__module__}.tables"`` or ``obj.__module__ + ".tables"``."""

    parts: list[ast.expr]
    if isinstance(expression, ast.JoinedStr):
        parts = [
            part.value if isinstance(part, ast.FormattedValue) else part
            for part in expression.values
        ]
    elif isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        parts = [expression.left, expression.right]
    else:
        return ""
    if len(parts) != 2:
        return ""
    head, tail = parts
    loaded = (isinstance(head, ast.Attribute) and head.attr in LOADED_MODULE_NAMES) or (
        isinstance(head, ast.Name) and head.id in LOADED_MODULE_NAMES
    )
    if (
        loaded
        and isinstance(tail, ast.Constant)
        and isinstance(tail.value, str)
        and tail.value.startswith(".")
    ):
        return tail.value
    return ""


def _constant_affixes(expression: ast.expr | None) -> tuple[str, str]:
    """The constant start and end of a computed string: ``f"{pkg}.tables"`` ends in ``.tables``."""

    template = _format_template(expression)
    if template is not None:
        return template
    parts: list[ast.expr]
    if isinstance(expression, ast.JoinedStr):
        parts = list(expression.values)
    elif isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        parts = [expression.left, expression.right]
    else:
        return "", ""
    if not parts:
        return "", ""

    def constant(part: ast.expr) -> str:
        return part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else ""

    prefix = constant(parts[0])
    suffix = constant(parts[-1]) if len(parts) > 1 else ""
    return prefix, suffix


_SCRIPT_FILE = re.compile(r"[\w][\w./-]*\.py")
"""A string that is one relative file name of a Python module."""
_PERCENT_FIELD = re.compile(r"%[-#0 +]*\d*(?:\.\d+)?[sdriouxXeEfFgGc]")
_BRACE_FIELD = re.compile(r"\{[^{}]*\}")


def _format_template(expression: ast.expr | None) -> tuple[str, str] | None:
    """The literal start and end of ``"a_%s_b" % x`` and ``"a_{}_b".format(x)``, else ``None``."""

    template: str | None = None
    field = _PERCENT_FIELD
    if (
        isinstance(expression, ast.BinOp)
        and isinstance(expression.op, ast.Mod)
        and isinstance(expression.left, ast.Constant)
        and isinstance(expression.left.value, str)
    ):
        template = expression.left.value
    elif (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Attribute)
        and expression.func.attr == "format"
        and isinstance(expression.func.value, ast.Constant)
        and isinstance(expression.func.value.value, str)
    ):
        template = expression.func.value.value
        field = _BRACE_FIELD
    if template is None:
        return None
    fields = list(field.finditer(template))
    if not fields:
        return None
    return template[: fields[0].start()], template[fields[-1].end() :]


def _package_path(name: str) -> list[str]:
    """``a``, ``a.b``, and ``a.b.c`` for ``a.b.c``: the modules importing it runs, in order."""

    parts = name.split(".")
    return [".".join(parts[: length + 1]) for length in range(len(parts))]


def _enclosing_package(name: str, modules: Mapping[str, PythonModule]) -> str | None:
    """The nearest project package that Python runs before the module ``name``."""

    package = name.rpartition(".")[0]
    while package:
        if package in modules:
            return package
        package = package.rpartition(".")[0]
    return None


def _statement_lines(tree: ast.Module) -> dict[ast.stmt, int]:
    return {
        statement: statement.lineno
        for statement in tree.body
        if not isinstance(statement, _COMPOUND_STATEMENTS)
    }


def _import_from_base(module: PythonModule, node: ast.ImportFrom) -> str | None:
    imported_module = node.module or ""
    level = node.level
    if level == 0:
        return imported_module
    package = (
        module.name if module.path.endswith("/__init__.py") else module.name.rpartition(".")[0]
    )
    parts = package.split(".") if package else []
    drops = level - 1
    if drops > len(parts):
        return None
    prefix = ".".join(parts[: len(parts) - drops])
    if prefix and imported_module:
        return f"{prefix}.{imported_module}"
    return prefix or imported_module


UNKNOWN_FIELD_TYPE = "<unknown>"
"""A field value whose class is not known, which gives the field no single type."""


def _infer_all_class_fields(
    modules: dict[str, PythonModule], resolver: _Resolver
) -> dict[tuple[str, str], str]:
    """Types of ``self`` fields that every assignment of the field agrees on (ADR-0022).

    A field has a type only when every assignment to it, in the methods of its class and of the
    class's project subclasses, is an instance of one class, or of ``None``. An assignment whose
    class is not known, a tuple or loop target, ``setattr(self, ...)``, and an assignment to the
    attribute of that name on any other object leave it without a type, so calls on it stay
    unresolved instead of reaching one class only. A field annotated ``self.name: T`` has the
    type ``T`` unless an assignment is known to be of a class that is no subclass of ``T``.
    """

    provisional: dict[tuple[str, str], str] = {}
    declared: dict[tuple[str, str], str] = {}
    assigned: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    poisoned_classes: set[str] = set()
    foreign_fields: set[str] = set()
    for module in modules.values():
        for node in ast.walk(module.tree):
            for target in _assignment_targets(node):
                if isinstance(target, ast.Attribute) and not (
                    isinstance(target.value, ast.Name) and target.value.id == "self"
                ):
                    foreign_fields.add(target.attr)
        for symbol in module.symbols:
            if not (
                is_function(symbol)
                and symbol.owner_qualified_name is not None
                and symbol.parameters
                and symbol.parameters[0].name == "self"
            ):
                continue
            assert not isinstance(symbol.node, ast.ClassDef)
            owner = f"{module.name}.{symbol.owner_qualified_name}"
            annotations = _self_field_annotations(symbol.node.body)
            assignments, opaque, computed = _self_field_writes(symbol.node.body)
            if computed:
                poisoned_classes.add(owner)
            for field_name in opaque:
                assigned[(owner, field_name)].add(UNKNOWN_FIELD_TYPE)
            if not (annotations or assignments):
                continue
            parameter_types: dict[str, str] = {}
            helper = _ExecutionVisitor(
                module=module,
                current=symbol,
                resolver=resolver,
                class_field_types=provisional,
            )
            for parameter in symbol.parameters:
                if parameter.annotation is not None:
                    resolved = helper._resolve_annotation(parameter.annotation)
                    if resolved is not None:
                        parameter_types[parameter.name] = resolved
            for field_name, annotation in annotations:
                resolved = helper._resolve_annotation(annotation)
                if resolved is not None:
                    declared.setdefault((owner, field_name), resolved)
            for field_name, value in assignments:
                types = _value_classes(
                    value, module, symbol, resolver, parameter_types, provisional
                )
                assigned[(owner, field_name)].update(types)
                if len(types) == 1 and UNKNOWN_FIELD_TYPE not in types:
                    provisional.setdefault((owner, field_name), next(iter(types)))

    def subclasses_of(owner: str) -> list[str]:
        symbol = resolver.class_named(owner)
        found: list[str] = []
        queue = list(resolver._subclasses.get(symbol.id, ())) if symbol is not None else []
        seen: set[NodeId] = set()
        while queue:
            item = queue.pop()
            if item.id in seen:
                continue
            seen.add(item.id)
            found.append(f"{item.module}.{item.qualified_name}")
            queue.extend(resolver._subclasses.get(item.id, ()))
        return found

    def is_subclass(name: str, base: str) -> bool:
        symbol = resolver.class_named(name)
        base_symbol = resolver.class_named(base)
        return (
            symbol is not None
            and base_symbol is not None
            and any(item.id == base_symbol.id for item in resolver.mro(symbol))
        )

    result: dict[tuple[str, str], str] = {}
    for owner, field_name in {*assigned, *declared}:
        if field_name in foreign_fields:
            continue
        family = [owner, *subclasses_of(owner)]
        if any(item in poisoned_classes for item in family):
            continue
        types = set().union(*(assigned.get((item, field_name), set()) for item in family))
        declared_type = declared.get((owner, field_name))
        if declared_type is not None:
            if all(
                item == UNKNOWN_FIELD_TYPE or is_subclass(item, declared_type) for item in types
            ):
                result[(owner, field_name)] = declared_type
        elif len(types) == 1 and UNKNOWN_FIELD_TYPE not in types:
            result[(owner, field_name)] = next(iter(types))
    return result


def _assignment_targets(node: ast.AST) -> list[ast.expr]:
    """The targets a statement binds, with tuple and list targets flattened."""

    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
    else:
        return []
    flat: list[ast.expr] = []
    while targets:
        target = targets.pop()
        if isinstance(target, (ast.Tuple, ast.List)):
            targets.extend(target.elts)
        elif isinstance(target, ast.Starred):
            targets.append(target.value)
        else:
            flat.append(target)
    return flat


def _value_classes(
    value: ast.expr,
    module: PythonModule,
    symbol: PythonSymbol,
    resolver: _Resolver,
    parameter_types: dict[str, str],
    field_types: dict[tuple[str, str], str],
) -> set[str]:
    """The classes a value may be an instance of; ``None`` adds none, unknown adds a marker."""

    if isinstance(value, ast.Constant) and value.value is None:
        return set()
    if isinstance(value, ast.IfExp):
        return _value_classes(
            value.body, module, symbol, resolver, parameter_types, field_types
        ) | _value_classes(value.orelse, module, symbol, resolver, parameter_types, field_types)
    if isinstance(value, ast.BoolOp):
        return set().union(
            *(
                _value_classes(item, module, symbol, resolver, parameter_types, field_types)
                for item in value.values
            )
        )
    if isinstance(value, ast.Name) and value.id in parameter_types:
        return {parameter_types[value.id]}
    if isinstance(value, ast.Call):
        target = resolver.resolve_expression(
            value.func,
            module=module,
            current=symbol,
            local_types=parameter_types,
            class_field_types=field_types,
        )
        if target is not None and target.kind is NodeKind.CLASS:
            return {f"{target.module}.{target.qualified_name}"}
    return {UNKNOWN_FIELD_TYPE}


def _unsupported_python_hook_boundaries(
    modules: dict[str, PythonModule],
    symbols: dict[NodeId, PythonSymbol],
    resolver: _Resolver,
) -> tuple[UnknownBoundary, ...]:
    """Guard project hooks whose implicit dispatch is outside the modeled subset."""

    owned_methods: defaultdict[NodeId, list[PythonSymbol]] = defaultdict(list)
    owned_classes: defaultdict[NodeId, list[PythonSymbol]] = defaultdict(list)
    for symbol in symbols.values():
        if symbol.owner is not None and symbol.kind is NodeKind.FUNCTION:
            owned_methods[symbol.owner].append(symbol)
        elif symbol.owner is not None and symbol.kind is NodeKind.CLASS:
            owned_classes[symbol.owner].append(symbol)

    boundaries: list[UnknownBoundary] = []
    for class_symbol in symbols.values():
        if class_symbol.kind is not NodeKind.CLASS:
            continue
        hook_targets = {
            method.id
            for method in owned_methods[class_symbol.id]
            if _is_special_method(method.name) or _is_descriptor_hook(method)
        }
        if hook_targets:
            boundaries.append(
                UnknownBoundary(
                    source=class_symbol.id,
                    domain="implicit_python_dispatch",
                    reason=(
                        "property, descriptor, or protocol hook may execute through "
                        "unsupported implicit Python dispatch"
                    ),
                    targets=tuple(sorted(hook_targets)),
                )
            )

        # A concrete class must implement the abstract methods of its bases, or it cannot be
        # created; removing an implementation that no call reaches breaks the class (ADR-0027).
        abstract_names = {
            method.name
            for base in resolver.mro(class_symbol)[1:]
            for method in owned_methods[base.id]
            if _is_abstract(method)
        }
        required = {
            method.id for method in owned_methods[class_symbol.id] if method.name in abstract_names
        }
        if required:
            boundaries.append(
                UnknownBoundary(
                    source=class_symbol.id,
                    domain="abstract_implementation",
                    reason="methods implement abstract methods that the class must define",
                    targets=tuple(sorted(required)),
                )
            )

        external = resolver.external_bases(class_symbol)
        hooking = [name for name in external if not _hook_free(name)]
        methods = owned_methods[class_symbol.id]
        if any(name not in ENUM_BASES for name in hooking):
            external_targets = {method.id for method in methods}
        else:
            external_targets = {method.id for method in methods if method.name in ENUM_HOOKS}
        if not hooking:
            external_targets = set()
        # A metaclass or base outside the project reads nested classes as options: Django's and
        # Django REST framework's ``Meta``, Pydantic's ``Config`` (ADR-0017).
        external_targets.update(
            nested.id
            for nested in owned_classes[class_symbol.id]
            if hooking or (external and nested.name in CONFIGURATION_CLASS_NAMES)
        )
        if external_targets:
            hooking = hooking or list(external)
            boundaries.append(
                UnknownBoundary(
                    source=class_symbol.id,
                    domain="external_base_hooks",
                    reason=(
                        "methods may be called by external base classes "
                        + ", ".join(sorted(set(hooking)))
                    ),
                    targets=tuple(sorted(external_targets)),
                )
            )

        assert isinstance(class_symbol.node, ast.ClassDef)
        module = modules[class_symbol.module]
        # The class statement runs a project metaclass, its own or a base's, and the
        # ``__init_subclass__`` of its project bases where it stands, so the class is created
        # for those effects, as a registry or a test checking a metaclass relies on (ADR-0022).
        hooks: set[NodeId] = set()
        mro = resolver.mro(class_symbol)
        for index, item in enumerate(mro):
            assert isinstance(item.node, ast.ClassDef)
            for keyword in item.node.keywords:
                if keyword.arg != "metaclass":
                    continue
                metaclass = resolver.resolve_expression(
                    keyword.value,
                    module=modules[item.module],
                    current=resolver.enclosing_scope(item),
                    local_types={},
                    class_field_types={},
                )
                if metaclass is not None and metaclass.kind is NodeKind.CLASS:
                    hooks.add(metaclass.id)
                    hooks.update(method.id for method in owned_methods[metaclass.id])
            if index:
                hooks.update(
                    method.id
                    for method in owned_methods[item.id]
                    if method.name == "__init_subclass__"
                )
        scope = resolver.enclosing_scope(class_symbol)
        while scope is not None and scope.kind is NodeKind.CLASS:
            scope = resolver.enclosing_scope(scope)
        if hooks or _base_is_computed(class_symbol, module, scope, resolver, modules):
            boundaries.append(
                UnknownBoundary(
                    source=scope.id if scope is not None else module.node_id,
                    domain="metaclass_execution",
                    reason="a project metaclass or __init_subclass__ runs at class creation",
                    targets=tuple(sorted({class_symbol.id, *hooks})),
                )
            )
    # PEP 562: attribute access on a module calls its ``__getattr__`` for a missing name and
    # ``dir(module)`` its ``__dir__``, from code that imports the module (ADR-0025).
    for module in modules.values():
        module_hooks = tuple(
            sorted(
                symbol.id
                for symbol in module.symbols
                if symbol.owner is None
                and (
                    (symbol.kind is NodeKind.FUNCTION and symbol.name in MODULE_HOOKS)
                    or (
                        symbol.kind in {NodeKind.FUNCTION, NodeKind.CLASS}
                        and _is_reserved_name(symbol.name)
                    )
                )
            )
        )
        if module_hooks:
            boundaries.append(
                UnknownBoundary(
                    source=module.node_id,
                    domain="implicit_python_dispatch",
                    reason=(
                        "module __getattr__ or __dir__ may execute when the module is accessed,"
                        " and a function or class named __like_this__ may be looked up by a host"
                    ),
                    targets=module_hooks,
                )
            )
    return tuple(boundaries)


MODULE_HOOKS = frozenset({"__getattr__", "__dir__"})
"""Module-level functions that Python calls for missing attributes and ``dir()`` (PEP 562)."""


def _is_reserved_name(name: str) -> bool:
    """``__ExtensionFactory__``: Python reserves such names, and a host that loads the module
    looks them up by name (ADR-0028)."""

    return len(name) > 4 and name.startswith("__") and name.endswith("__")


def _base_is_computed(
    class_symbol: PythonSymbol,
    module: PythonModule,
    scope: PythonSymbol | None,
    resolver: _Resolver,
    modules: dict[str, PythonModule],
) -> bool:
    """Whether a base is a class value only running code tells: its statement may run hooks.

    ``class Boom(cls)`` derives from a parameter, and ``class Sub(validators.Draft7)`` from a
    module variable that a project function built with ``Draft7 = create(...)``; the base's
    ``__init_subclass__`` or metaclass runs when the statement does, which tests rely on
    (ADR-0025).
    """

    local = _local_names(scope)[0] if scope is not None and scope.kind is NodeKind.FUNCTION else ()
    for base in class_symbol.bases:
        expression = _unstarred(base.value if isinstance(base, ast.Subscript) else base)
        if isinstance(expression, ast.Call):
            callee = resolver.resolve_expression(
                expression.func,
                module=module,
                current=scope,
                local_types={},
                class_field_types={},
            )
            if callee is not None and callee.kind is NodeKind.FUNCTION:
                return True  # ``class Sub(create(schema))``: a project function makes the base
            continue
        dotted = _dotted_name(expression)
        if dotted is None:
            continue
        if dotted.split(".")[0] in local:
            return True
        module_name, _, attribute = (resolver.external_name(expression, module) or "").rpartition(
            "."
        )
        owner = modules.get(module_name)
        if owner is not None and _is_factory_value(owner, attribute, resolver):
            return True
    return False


def _is_factory_value(module: PythonModule, name: str, resolver: _Resolver) -> bool:
    """Whether ``name = project_function(...)`` is a top-level assignment of ``module``."""

    for statement in module.tree.body:
        if not (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name for target in statement.targets
            )
            and isinstance(statement.value, ast.Call)
        ):
            continue
        callee = resolver.resolve_expression(
            statement.value.func,
            module=module,
            current=None,
            local_types={},
            class_field_types={},
        )
        if callee is not None and callee.kind is NodeKind.FUNCTION:
            return True
    return False


def _is_special_method(name: str) -> bool:
    """``__name__`` and ``_name_`` methods, which protocols and libraries call implicitly.

    Python reserves double-underscore names for its protocols; single-underscore names such as
    ``_missing_`` in ``enum`` and ``_repr_html_`` in IPython are the convention for library ones.
    """

    if len(name) > 4 and name.startswith("__") and name.endswith("__"):
        return True
    return (
        len(name) > 2
        and name.startswith("_")
        and name.endswith("_")
        and name[1] != "_"
        and name[-2] != "_"
    )


def _hook_free(name: str) -> bool:
    if name in HOOK_FREE_BASES:
        return True
    return "." not in name and name.endswith(("Error", "Exception", "Warning", "Exit", "Interrupt"))


def _base_name(resolver: _Resolver, base: ast.expr, module: PythonModule) -> str:
    """How a base that is not a project class is named, for hook decisions and messages."""

    expression = base.value if isinstance(base, ast.Subscript) else base
    return resolver.external_name(_unstarred(expression), module) or "a computed base"


def _is_abstract(symbol: PythonSymbol) -> bool:
    return any(
        (name := _dotted_name(decorator)) is not None
        and name.rsplit(".", 1)[-1]
        in {"abstractmethod", "abstractproperty", "abstractclassmethod", "abstractstaticmethod"}
        for decorator in symbol.decorators
    )


def _is_descriptor_hook(symbol: PythonSymbol) -> bool:
    for decorator in symbol.decorators:
        name = _dotted_name(decorator)
        if name == "property" or (
            name is not None and name.endswith((".getter", ".setter", ".deleter"))
        ):
            return True
    return False


def _self_field_annotations(
    body: Sequence[ast.stmt],
) -> tuple[tuple[str, ast.expr], ...]:
    """Fields a method declares as ``self.name: T``, with or without a value."""

    found: list[tuple[str, ast.expr]] = []
    for node in flow_nodes(body):
        if isinstance(node, ast.AnnAssign):
            dotted = _dotted_name(node.target)
            if dotted is not None and dotted.startswith("self.") and dotted.count(".") == 1:
                found.append((dotted.split(".")[1], node.annotation))
    return tuple(found)


def _self_field_writes(
    body: Sequence[ast.stmt],
) -> tuple[tuple[tuple[str, ast.expr], ...], frozenset[str], bool]:
    """``self.name = value`` writes; fields written with no single value; any computed write.

    A field bound as a tuple, loop, or ``with`` target, or by ``setattr(self, "name", value)``,
    has no value to infer from; ``setattr(self, name, value)`` with a computed name may write any
    field. Augmented assignments keep the field's value.
    """

    values = _self_field_assignments(body)
    opaque: set[str] = set()
    computed = False
    for node in flow_nodes(body):
        simple = isinstance(node, ast.Assign) and all(
            not isinstance(target, (ast.Tuple, ast.List)) for target in node.targets
        )
        if not simple and not isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            for target in _assignment_targets(node):
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    opaque.add(target.attr)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "self"
        ):
            name = node.args[1] if len(node.args) > 1 else None
            if isinstance(name, ast.Constant) and isinstance(name.value, str):
                opaque.add(name.value)
            else:
                computed = True
    return values, frozenset(opaque), computed


def _self_field_assignments(
    body: Sequence[ast.stmt],
) -> tuple[tuple[str, ast.expr], ...]:
    found: list[tuple[str, ast.expr]] = []
    for node in flow_nodes(body):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                dotted = _dotted_name(target)
                if dotted is not None and dotted.startswith("self.") and dotted.count(".") == 1:
                    found.append((dotted.split(".")[1], node.value))
        elif isinstance(node, ast.AnnAssign):
            dotted = _dotted_name(node.target)
            if (
                dotted is not None
                and dotted.startswith("self.")
                and dotted.count(".") == 1
                and node.value is not None
            ):
                found.append((dotted.split(".")[1], node.value))
    return tuple(found)


def _is_transparent_decorator(name: str) -> bool:
    """Decorators that return the function they receive and register it with nothing.

    pytest marks and fixtures register functions only with pytest's collection, which the tests
    world models itself, so outside it they call nothing (ADR-0017).
    """

    return (
        name in TRANSPARENT_DECORATORS
        or name in PYTEST_REGISTRATIONS
        or name.startswith("pytest.mark.")
    )


def _outermost_calls(expression: ast.expr) -> list[ast.Call]:
    """The calls in ``expression`` that no other call in it contains, in source order."""

    calls: list[ast.Call] = []
    stack: list[ast.AST] = [expression]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Call):
            calls.append(node)
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))
    return calls


def _visit_module_declaration_effects(module: ast.Module, visitor: _ExecutionVisitor) -> None:
    visitor.visit_statements(module.body)


def _visit_class_execution_effects(node: ast.ClassDef, visitor: _ExecutionVisitor) -> None:
    for base in node.bases:
        visitor.mark_references(_unstarred(base))
        visitor.visit_expression(base)
    for decorator in node.decorator_list:
        visitor.mark_references(decorator.func if isinstance(decorator, ast.Call) else decorator)
        visitor.visit_expression(decorator)
    visitor.visit_statements(node.body)


def _parameters(node: FunctionNode) -> tuple[ParameterInfo, ...]:
    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(arguments.defaults))
    defaults.extend(arguments.defaults)
    values: list[tuple[ast.arg, ast.expr | None]] = list(zip(positional, defaults, strict=True))
    values.extend(zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True))
    if arguments.vararg is not None:
        values.append((arguments.vararg, None))
    if arguments.kwarg is not None:
        values.append((arguments.kwarg, None))
    return tuple(
        ParameterInfo(name=argument.arg, annotation=argument.annotation, default=default)
        for argument, default in values
    )


@lru_cache(maxsize=8192)
def _parsed_annotation(value: str) -> ast.expr | None:
    """A quoted annotation as an expression, or ``None`` when it is no annotation."""

    stripped = value.strip()
    if not stripped or len(stripped) > 200:
        return None
    try:
        return ast.parse(stripped, mode="eval").body
    except (SyntaxError, ValueError):
        return None


def _annotation_names(
    expression: ast.expr, text: SourceText, *, generics: bool = False
) -> tuple[str, ...]:
    """Dotted names an annotation mentions; ``generics`` also gives the subscripted class.

    ``Box[int]`` needs ``Box`` for the class to be live, but it does not give a variable the type
    ``Box`` in the other uses of these names, so the subscripted name is opt-in.
    """

    if isinstance(expression, (ast.Name, ast.Attribute)) or _is_name_constant(expression):
        dotted = _dotted_name(expression)
        return (dotted,) if dotted is not None else ()
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        # ``-> "Behaviour"`` names its class as ``-> Behaviour`` does (ADR-0026).
        parsed = _parsed_annotation(expression.value)
        if parsed is None:
            return ()
        return _annotation_names(parsed, SourceText(expression.value.strip()), generics=generics)
    if isinstance(expression, ast.Subscript):
        base = _dotted_name(expression.value)
        if base in {"Literal", "typing.Literal", "typing_extensions.Literal"}:
            return ()  # the strings of a Literal are values, not types
        elements = subscript_elements(expression, text)
        if base in {"Annotated", "typing.Annotated", "FromDishka"}:
            return _annotation_names(elements[0], text, generics=generics) if elements else ()
        result: list[str] = [base] if generics and base is not None else []
        for element in elements:
            result.extend(_annotation_names(element, text, generics=generics))
        return tuple(result)
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.BitOr):
        return (
            *_annotation_names(expression.left, text, generics=generics),
            *_annotation_names(expression.right, text, generics=generics),
        )
    return ()


def _called_parameter_names(symbol: PythonSymbol) -> frozenset[str]:
    if isinstance(symbol.node, ast.ClassDef):
        return frozenset()
    parameter_names = {parameter.name for parameter in symbol.parameters}
    return frozenset(
        node.func.id
        for node in flow_nodes(symbol.node.body)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in parameter_names
    )


def _is_name_constant(expression: ast.AST | None) -> bool:
    """``True``, ``False``, and ``None``, which facts spell as names (ADR-0007)."""

    return isinstance(expression, ast.Constant) and (
        expression.value is None or isinstance(expression.value, bool)
    )


def _dotted_name(expression: ast.AST | None) -> str | None:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        base = _dotted_name(expression.value)
        return f"{base}.{expression.attr}" if base is not None else None
    if _is_name_constant(expression):
        assert isinstance(expression, ast.Constant)
        return str(expression.value)
    return None


def _is_getattr_call(expression: ast.expr) -> bool:
    return isinstance(expression, ast.Call) and _dotted_name(expression.func) == "getattr"


def _containing_class_qname(symbol: PythonSymbol) -> str | None:
    if symbol.owner_qualified_name is None:
        return None
    return symbol.owner_qualified_name.split(".")[0]


def _imports_src_package(entries: Sequence[tuple[SourceUnit, ParsedSource]]) -> bool:
    """Whether project code imports a top-level ``src`` package, as in ``from src.app import x``.

    A ``src`` directory is usually a source root whose packages are imported by their own names,
    so its name is left out of module names. Some projects instead put the project root on the
    path and import ``src`` itself; then ``src`` is part of every module name below it (ADR-0015).
    """

    if not any(unit.path.startswith("src/") for unit, _entry in entries):
        return False
    for unit, entry in entries:
        if "src" not in unit.source:
            continue
        for node in ast.walk(entry.tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            if any(name == "src" or name.startswith("src.") for name in names):
                return True
    return False


def is_test_directory(name: str) -> bool:
    """``test``, ``tests``, ``testing``, and names such as ``unit_tests`` or ``tests_api``."""

    return (
        name in {"test", "tests", "testing"}
        or name.endswith(("_test", "_tests"))
        or (name.startswith(("test_", "tests_")))
    )


def conftest_directories(program: PythonProgram) -> frozenset[str]:
    """Directories below the root that hold a ``conftest.py``: pytest test trees.

    A ``conftest.py`` at the root configures the whole checkout and marks nothing as test code.
    """

    return frozenset(
        directory
        for module in program.modules.values()
        for directory, _, name in [module.path.rpartition("/")]
        if name == "conftest.py" and directory
    )


def is_test_path(path: str, test_trees: frozenset[str] = frozenset()) -> bool:
    """Whether a source file is test code by pytest's conventions (ADR-0017)."""

    *directories, name = path.replace("\\", "/").split("/")
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    if any(is_test_directory(directory) for directory in directories):
        return True
    return any(path.startswith(f"{tree}/") for tree in test_trees)


def module_name_from_path(path: str, *, keep_src: bool = False) -> str:
    normalized = path.replace("\\", "/")
    without_suffix = normalized[:-3] if normalized.endswith(".py") else normalized
    parts = without_suffix.split("/")
    if len(parts) > 1 and parts[0] == "src" and not keep_src:
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or "__root__"


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatchcase(normalized, pattern.replace("\\", "/")) for pattern in patterns)


def _edge_sort_key(edge: ExecutionEdge) -> tuple[str, ...]:
    return (str(edge.source), str(edge.target), edge.kind.value, edge.detail)


def _boundary_sort_key(boundary: UnknownBoundary) -> tuple[str, ...]:
    return (
        str(boundary.source),
        boundary.domain,
        boundary.reason,
        *(str(target) for target in boundary.targets),
    )


def _limitation_sort_key(limitation: PythonLimitation) -> tuple[str, int, str, str, str]:
    return (
        limitation.path,
        limitation.line,
        limitation.code,
        limitation.message,
        str(limitation.origin or ""),
    )
