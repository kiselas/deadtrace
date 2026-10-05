"""Convert semantic state into review-oriented, non-destructive findings."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from deadtrace.core import AnalysisSnapshot, EdgeKind, NodeId, NodeKind, WorldResult
from deadtrace.frameworks import (
    FrameworkModel,
    FrameworkObjectKind,
    RouteRegistration,
)
from deadtrace.python_frontend import PythonProgram, conftest_directories, is_test_path


@dataclass(frozen=True, slots=True)
class FindingMember:
    path: str
    qualified_name: str
    kind: str
    occurrence: int
    line: int

    def identity(self) -> str:
        return f"python:{self.path}:{self.qualified_name}:{self.kind}:{self.occurrence}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "occurrence": self.occurrence,
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    category: str
    title: str
    reason: str
    worlds: tuple[str, ...]
    members: tuple[FindingMember, ...]
    fingerprint: str
    action: str = "review"
    validation: str = "not_performed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "title": self.title,
            "reason": self.reason,
            "worlds": list(self.worlds),
            "members": [member.to_dict() for member in self.members],
            "fingerprint": self.fingerprint,
            "action": self.action,
            "validation": self.validation,
        }


def build_findings(
    program: PythonProgram,
    model: FrameworkModel,
    snapshot: AnalysisSnapshot,
) -> tuple[Finding, ...]:
    """Emit findings only when every relevant application world passes its gate."""

    production_worlds = tuple(world for world in snapshot.worlds if world.id.profile != "tests")
    findings: list[Finding] = []
    findings.extend(_unpublished_router_findings(program, model, production_worlds))
    if not production_worlds or not all(
        world.negative_findings_allowed for world in production_worlds
    ):
        return tuple(sorted(findings, key=_finding_sort_key))

    reached = set().union(
        *(world.resolved_may_run | world.conservative_may_run for world in production_worlds)
    )
    retained = _retained_with_members(
        program, model, set().union(*(world.retained for world in production_worlds))
    )
    test_worlds = tuple(world for world in snapshot.worlds if world.id.profile == "tests")
    test_reached = (
        set().union(*(world.resolved_may_run | world.conservative_may_run for world in test_worlds))
        if test_worlds
        else set()
    )
    adjacency = _ownership_and_edge_adjacency(model)
    framework_nodes = _framework_specific_nodes(model, program, adjacency, reached)
    findings.extend(
        _unrequested_binding_findings(
            program, model, adjacency, reached, retained, production_worlds
        )
    )
    if test_worlds and all(world.negative_findings_allowed for world in test_worlds):
        resolved_in_tests = set().union(*(world.resolved_may_run for world in test_worlds))
        node_map = model.graph.node_map()
        test_trees = conftest_directories(program)
        test_only = {
            node_id
            for node_id in resolved_in_tests - reached - retained - framework_nodes
            if not is_test_path(node_map[node_id].path, test_trees)
            and node_map[node_id].kind is not NodeKind.MODULE
            and not node_map[node_id].report_excluded
        }
        for component in _candidate_components(model, test_only):
            members = _members(program, component)
            if members:
                findings.append(
                    _finding(
                        code="RCH004",
                        category="test_only_use",
                        title=(
                            "Production code is reached only from tests: "
                            f"{members[0].qualified_name}"
                        ),
                        reason=(
                            "The component is reached in the tests world but not in "
                            "production worlds."
                        ),
                        worlds=tuple(world.id.key for world in test_worlds),
                        members=members,
                    )
                )
    candidate_ids = {
        node.id
        for node in model.graph.nodes
        if node.kind is not NodeKind.MODULE
        and node.id not in reached
        and node.id not in retained
        and node.id not in test_reached
        and node.id not in framework_nodes
        and not node.report_excluded
    }
    for component in _candidate_components(model, candidate_ids):
        members = _members(program, component)
        if not members:
            continue
        findings.append(
            _finding(
                code="RCH001",
                category="unreached_component",
                title=f"Unreached component: {members[0].qualified_name}",
                reason="No execution path was found in any complete production world.",
                worlds=tuple(world.id.key for world in production_worlds),
                members=members,
            )
        )
    return tuple(sorted(findings, key=_finding_sort_key))


def _unpublished_router_findings(
    program: PythonProgram,
    model: FrameworkModel,
    production_worlds: tuple[WorldResult, ...],
) -> list[Finding]:
    del production_worlds
    apps = {
        key for key, obj in model.objects.items() if obj.kind is FrameworkObjectKind.FASTAPI_APP
    }
    if not apps:
        return []
    published = set(apps)
    queue = deque(sorted(apps))
    while queue:
        owner = queue.popleft()
        for include in model.includes:
            if include.owner == owner and include.router not in published:
                published.add(include.router)
                queue.append(include.router)
    may_be_published = model.escaping_routers if model.unknown_includes else frozenset()
    by_router: defaultdict[str, list[RouteRegistration]] = defaultdict(list)
    for route in model.routes:
        if route.owner not in published and route.owner not in may_be_published:
            by_router[route.owner].append(route)
    findings: list[Finding] = []
    for router, routes in sorted(by_router.items()):
        members = _members(program, {route.endpoint for route in routes})
        if members:
            findings.append(
                _finding(
                    code="RCH002",
                    category="unpublished_router",
                    title=f"Router is not included: {router.replace(':', '.')}",
                    reason=(
                        "Routes are registered on a router that is not included "
                        "by a discovered app."
                    ),
                    worlds=(),
                    members=members,
                )
            )
    return findings


def _unrequested_binding_findings(
    program: PythonProgram,
    model: FrameworkModel,
    adjacency: defaultdict[NodeId, set[NodeId]],
    reached: set[NodeId],
    retained: set[NodeId],
    worlds: tuple[WorldResult, ...],
) -> list[Finding]:
    findings: list[Finding] = []
    for binding in model.bindings:
        if binding.factory in reached or binding.factory not in retained:
            continue
        binding_component = _descendants(adjacency, binding.factory) - reached
        members = _members(program, binding_component)
        if not members:
            continue
        findings.append(
            _finding(
                code="RCH003",
                category="unrequested_binding",
                title=f"Registered binding is not requested: {binding.provides}",
                reason="The provider is registered, but no demand reaches this binding.",
                worlds=tuple(world.id.key for world in worlds),
                members=members,
            )
        )
    return findings


def _framework_specific_nodes(
    model: FrameworkModel,
    program: PythonProgram,
    adjacency: defaultdict[NodeId, set[NodeId]],
    reached: set[NodeId],
) -> set[NodeId]:
    """Nodes another finding accounts for, so ``RCH001`` leaves them out.

    What hangs below a binding's factory is reported with that binding when nothing requests it
    (``RCH003``). Below a factory that is reached, an unreached member is dead code like any
    other (ADR-0027).
    """

    nodes = {route.endpoint for route in model.routes}
    for binding in model.bindings:
        if binding.factory not in reached:
            nodes.update(_descendants(adjacency, binding.factory))
        nodes.add(binding.provider_class)
        provider = program.symbols.get(binding.provider_class)
        if provider is not None:
            nodes.update(symbol.id for symbol in program.index.members(provider.id))
    return nodes


def _retained_with_members(
    program: PythonProgram, model: FrameworkModel, retained: set[NodeId]
) -> set[NodeId]:
    """Retained declarations with what is defined inside them, except the methods of a class that
    a binding registers: the binding retains the class as a factory, and its methods are used or
    unused like those of any other class (ADR-0027)."""

    factories = {
        binding.factory
        for binding in model.bindings
        if (symbol := program.symbols.get(binding.factory)) is not None
        and symbol.kind is NodeKind.CLASS
    }
    return _with_members(model, retained - factories) | (retained & factories)


def _with_members(model: FrameworkModel, retained: set[NodeId]) -> set[NodeId]:
    """Retained declarations with everything defined inside them: a closure of a retained
    fixture is retained with it rather than reported on its own."""

    owned: defaultdict[NodeId, list[NodeId]] = defaultdict(list)
    for node in model.graph.nodes:
        if node.owner is not None:
            owned[node.owner].append(node.id)
    result = set(retained)
    stack = list(retained)
    while stack:
        for member in owned.get(stack.pop(), ()):
            if member not in result:
                result.add(member)
                stack.append(member)
    return result


def _ownership_and_edge_adjacency(model: FrameworkModel) -> defaultdict[NodeId, set[NodeId]]:
    """Owner-to-member and edge successors of every node, built once per ``build_findings``."""

    adjacency: defaultdict[NodeId, set[NodeId]] = defaultdict(set)
    for node in model.graph.nodes:
        if node.owner is not None:
            adjacency[node.owner].add(node.id)
    for edge in model.graph.edges:
        if edge.kind is not EdgeKind.MEMBER:
            adjacency[edge.source].add(edge.target)
    return adjacency


def _descendants(adjacency: defaultdict[NodeId, set[NodeId]], source: NodeId) -> set[NodeId]:
    visited: set[NodeId] = set()
    queue = deque([source])
    while queue:
        node_id = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        queue.extend(sorted(adjacency[node_id] - visited))
    return visited


def _candidate_components(
    model: FrameworkModel, candidates: set[NodeId]
) -> tuple[set[NodeId], ...]:
    adjacency: defaultdict[NodeId, set[NodeId]] = defaultdict(set)
    node_map = model.graph.node_map()
    for node_id in candidates:
        owner = node_map[node_id].owner
        if owner in candidates:
            adjacency[node_id].add(owner)
            adjacency[owner].add(node_id)
    for edge in model.graph.edges:
        if edge.source in candidates and edge.target in candidates:
            adjacency[edge.source].add(edge.target)
            adjacency[edge.target].add(edge.source)
    remaining = set(candidates)
    components: list[set[NodeId]] = []
    while remaining:
        seed = min(remaining)
        component: set[NodeId] = set()
        queue = deque([seed])
        while queue:
            node_id = queue.popleft()
            if node_id in component:
                continue
            component.add(node_id)
            queue.extend(sorted(adjacency[node_id] - component))
        remaining.difference_update(component)
        components.append(component)
    return tuple(sorted(components, key=lambda item: min(item)))


def _members(program: PythonProgram, node_ids: set[NodeId]) -> tuple[FindingMember, ...]:
    members = [
        FindingMember(
            path=symbol.path,
            qualified_name=symbol.qualified_name,
            kind=symbol.kind.value,
            occurrence=symbol.occurrence,
            line=symbol.line,
        )
        for node_id in node_ids
        for symbol in [program.symbols.get(node_id)]
        if symbol is not None
    ]
    return tuple(
        sorted(
            members,
            key=lambda item: (
                item.path,
                item.line,
                item.qualified_name,
                item.kind,
                item.occurrence,
            ),
        )
    )


def _finding(
    *,
    code: str,
    category: str,
    title: str,
    reason: str,
    worlds: tuple[str, ...],
    members: tuple[FindingMember, ...],
) -> Finding:
    # Worlds stay out: a new application or test world must not renew every fingerprint.
    canonical = "\n".join((code, *(member.identity() for member in members)))
    fingerprint = f"{code.lower()}-{sha256(canonical.encode()).hexdigest()[:16]}"
    return Finding(code, category, title, reason, worlds, members, fingerprint)


def _finding_sort_key(finding: Finding) -> tuple[str, str, str]:
    first = finding.members[0].identity() if finding.members else ""
    return (finding.code, first, finding.fingerprint)
