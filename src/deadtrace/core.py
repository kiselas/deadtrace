"""Deterministic world-local reachability and uncertainty closure.

The core has no Python, FastAPI, or Dishka knowledge. Frontends and semantic
capabilities contribute nodes, edges, roots, requirements, and boundaries.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import NewType

NodeId = NewType("NodeId", str)


class NodeKind(StrEnum):
    MODULE = "module"
    FUNCTION = "function"
    CLASS = "class"


class ReachabilityKind(StrEnum):
    RESOLVED = "resolved_may_run"
    CONSERVATIVE = "conservative_may_run"


class AssemblyState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INVALID = "invalid"


class EdgeKind(StrEnum):
    ROOT = "root"
    IMPORT = "import"
    CALL = "call"
    CONSTRUCT = "construct"
    FIELD_LOAD = "field_load"
    RETURN = "return"
    CALLBACK = "callback"
    FRAMEWORK = "framework"
    DEPENDENCY = "dependency"
    LIFECYCLE = "lifecycle"
    MEMBER = "member"
    INHERIT = "inherit"
    ANNOTATION = "annotation"
    KEEP = "keep"
    UNKNOWN = "unknown"


@dataclass(frozen=True, order=True, slots=True)
class WorldId:
    profile: str
    scenario: str

    @property
    def key(self) -> str:
        return f"{self.profile}:{self.scenario}"


@dataclass(frozen=True, slots=True)
class SemanticNode:
    id: NodeId
    display_name: str
    kind: NodeKind
    path: str
    line: int
    owner: NodeId | None = None
    report_excluded: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionEdge:
    source: NodeId
    target: NodeId
    kind: EdgeKind
    detail: str


@dataclass(frozen=True, slots=True)
class Requirement:
    """A declaration/object that must be retained independently of body execution."""

    source: NodeId
    target: NodeId
    kind: EdgeKind
    detail: str


@dataclass(frozen=True, slots=True)
class UnknownBoundary:
    """Possible execution introduced by one reached operation.

    An empty target tuple means the boundary cannot be localized and therefore
    protects every execution node in the graph.
    """

    source: NodeId
    domain: str
    reason: str
    targets: tuple[NodeId, ...] = ()


@dataclass(frozen=True, slots=True)
class Limitation:
    code: str
    message: str
    origin: NodeId | None = None
    world: WorldId | None = None


@dataclass(frozen=True, slots=True)
class Derivation:
    world: WorldId
    target: NodeId
    reachability: ReachabilityKind
    kind: EdgeKind
    source: NodeId | None
    detail: str


@dataclass(frozen=True, slots=True)
class RootProvenance:
    """Why a node is an execution root in one world."""

    target: NodeId
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class SemanticGraph:
    nodes: tuple[SemanticNode, ...]
    edges: tuple[ExecutionEdge, ...] = ()
    requirements: tuple[Requirement, ...] = ()
    boundaries: tuple[UnknownBoundary, ...] = ()

    def node_map(self) -> dict[NodeId, SemanticNode]:
        return {node.id: node for node in self.nodes}


@dataclass(frozen=True, slots=True)
class WorldPlan:
    id: WorldId
    roots: tuple[NodeId, ...]
    retained_roots: tuple[NodeId, ...] = ()
    conservative_roots: tuple[NodeId, ...] = ()
    assembly_state: AssemblyState = AssemblyState.COMPLETE
    limitations: tuple[Limitation, ...] = ()
    root_provenance: tuple[RootProvenance, ...] = ()
    edges: tuple[ExecutionEdge, ...] = ()
    """Execution facts that hold only in this world, such as pytest resolving a fixture."""
    boundaries: tuple[UnknownBoundary, ...] = ()
    """Unknown boundaries that exist only in this world (ADR-0016)."""


@dataclass(frozen=True, slots=True)
class WorldResult:
    id: WorldId
    assembly_state: AssemblyState
    roots: tuple[NodeId, ...]
    retained_roots: tuple[NodeId, ...]
    conservative_roots: tuple[NodeId, ...]
    root_provenance: tuple[RootProvenance, ...]
    resolved_may_run: frozenset[NodeId]
    conservative_may_run: frozenset[NodeId]
    retained: frozenset[NodeId]
    derivations: tuple[Derivation, ...]
    limitations: tuple[Limitation, ...]
    exhausted_budget: bool = False

    def state_of(self, node_id: NodeId) -> ReachabilityKind | None:
        if node_id in self.resolved_may_run:
            return ReachabilityKind.RESOLVED
        if node_id in self.conservative_may_run:
            return ReachabilityKind.CONSERVATIVE
        return None

    @property
    def negative_findings_allowed(self) -> bool:
        return (
            bool(self.resolved_may_run)
            and self.assembly_state is AssemblyState.COMPLETE
            and not self.exhausted_budget
        )


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    graph: SemanticGraph
    worlds: tuple[WorldResult, ...]

    def world(self, world_id: WorldId) -> WorldResult:
        for result in self.worlds:
            if result.id == world_id:
                return result
        raise KeyError(world_id)


@dataclass(slots=True)
class _MutableWorld:
    plan: WorldPlan
    resolved: set[NodeId] = field(default_factory=set)
    conservative: set[NodeId] = field(default_factory=set)
    retained: set[NodeId] = field(default_factory=set)
    derivations: list[Derivation] = field(default_factory=list)
    limitations: list[Limitation] = field(default_factory=list)
    exhausted_budget: bool = False


def solve(
    graph: SemanticGraph,
    plans: tuple[WorldPlan, ...],
    *,
    max_steps: int | None = None,
) -> AnalysisSnapshot:
    """Compute deterministic closure for each world without cross-world state.

    A node enters a world's queue at most once per reachability kind, so the default budget of
    twice the node count is never exhausted; an explicit ``max_steps`` caps the work instead.
    """

    if max_steps is not None and max_steps < 1:
        raise ValueError("max_steps must be positive")
    node_map = graph.node_map()
    if max_steps is None:
        max_steps = max(1, 2 * len(node_map))
    adjacency: defaultdict[NodeId, list[ExecutionEdge]] = defaultdict(list)
    requirements: defaultdict[NodeId, list[Requirement]] = defaultdict(list)
    boundaries: defaultdict[NodeId, list[UnknownBoundary]] = defaultdict(list)
    for edge in graph.edges:
        _require_known_node(node_map, edge.source, "edge source")
        _require_known_node(node_map, edge.target, "edge target")
        adjacency[edge.source].append(edge)
    for requirement in graph.requirements:
        _require_known_node(node_map, requirement.source, "requirement source")
        _require_known_node(node_map, requirement.target, "requirement target")
        requirements[requirement.source].append(requirement)
    for boundary in graph.boundaries:
        _require_known_node(node_map, boundary.source, "boundary source")
        for target in boundary.targets:
            _require_known_node(node_map, target, "boundary target")
        boundaries[boundary.source].append(boundary)

    for edge_values in adjacency.values():
        edge_values.sort(key=_fact_sort_key)
    for requirement_values in requirements.values():
        requirement_values.sort(key=_fact_sort_key)
    for boundary_values in boundaries.values():
        boundary_values.sort(key=_fact_sort_key)

    all_nodes = tuple(sorted(node_map))
    results = tuple(
        _solve_world(
            graph,
            plan,
            node_map=node_map,
            all_nodes=all_nodes,
            adjacency=adjacency,
            requirements=requirements,
            boundaries=boundaries,
            max_steps=max_steps,
        )
        for plan in sorted(plans, key=lambda item: item.id)
    )
    return AnalysisSnapshot(graph=graph, worlds=results)


def _solve_world(
    graph: SemanticGraph,
    plan: WorldPlan,
    *,
    node_map: dict[NodeId, SemanticNode],
    all_nodes: tuple[NodeId, ...],
    adjacency: dict[NodeId, list[ExecutionEdge]],
    requirements: dict[NodeId, list[Requirement]],
    boundaries: dict[NodeId, list[UnknownBoundary]],
    max_steps: int,
) -> WorldResult:
    state = _MutableWorld(plan=plan, limitations=list(plan.limitations))
    local_adjacency: defaultdict[NodeId, list[ExecutionEdge]] = defaultdict(list)
    local_boundaries: defaultdict[NodeId, list[UnknownBoundary]] = defaultdict(list)
    for edge in plan.edges:
        _require_known_node(node_map, edge.source, "world edge source")
        _require_known_node(node_map, edge.target, "world edge target")
        local_adjacency[edge.source].append(edge)
    for boundary in plan.boundaries:
        _require_known_node(node_map, boundary.source, "world boundary source")
        for target in boundary.targets:
            _require_known_node(node_map, target, "world boundary target")
        local_boundaries[boundary.source].append(boundary)
    for edge_values in local_adjacency.values():
        edge_values.sort(key=_fact_sort_key)
    for boundary_values in local_boundaries.values():
        boundary_values.sort(key=_fact_sort_key)
    for retained in plan.retained_roots:
        _require_known_node(node_map, retained, "retained root")
        state.retained.add(retained)
    queue: deque[tuple[NodeId, ReachabilityKind]] = deque()
    for root in sorted(set(plan.conservative_roots)):
        _require_known_node(node_map, root, "conservative root")
        _mark(
            state,
            queue,
            target=root,
            reachability=ReachabilityKind.CONSERVATIVE,
            kind=EdgeKind.ROOT,
            source=None,
            detail=f"external execution contract for {plan.id.key}",
        )
    for root in sorted(set(plan.roots)):
        _require_known_node(node_map, root, "world root")
        _mark(
            state,
            queue,
            target=root,
            reachability=ReachabilityKind.RESOLVED,
            kind=EdgeKind.ROOT,
            source=None,
            detail=f"configured or discovered root for {plan.id.key}",
        )

    crossed: dict[tuple[NodeId, UnknownBoundary], None] = {}
    steps = 0
    while queue:
        source, source_state = queue.popleft()
        steps += 1
        if steps > max_steps:
            state.exhausted_budget = True
            state.limitations.append(
                Limitation(
                    code="DT2001",
                    message=(
                        f"analysis step budget {max_steps} exhausted; remaining domain protected"
                    ),
                    origin=source,
                    world=plan.id,
                )
            )
            for node_id in all_nodes:
                _mark(
                    state,
                    queue,
                    target=node_id,
                    reachability=ReachabilityKind.CONSERVATIVE,
                    kind=EdgeKind.UNKNOWN,
                    source=source,
                    detail="budget exhaustion widens possible execution",
                )
            queue.clear()
            break

        for requirement in requirements.get(source, ()):  # declaration retention, not execution
            state.retained.add(requirement.target)

        for edge in (*adjacency.get(source, ()), *local_adjacency.get(source, ())):
            _mark(
                state,
                queue,
                target=edge.target,
                reachability=source_state,
                kind=edge.kind,
                source=source,
                detail=edge.detail,
            )

        for boundary in (*boundaries.get(source, ()), *local_boundaries.get(source, ())):
            targets = boundary.targets or all_nodes
            crossed[(source, boundary)] = None
            for target in targets:
                _mark(
                    state,
                    queue,
                    target=target,
                    reachability=ReachabilityKind.CONSERVATIVE,
                    kind=EdgeKind.UNKNOWN,
                    source=source,
                    detail=f"unknown execution boundary: {boundary.domain}",
                )

    for source, boundary in crossed:
        if not boundary.targets or any(
            target in state.conservative and target not in state.resolved
            for target in boundary.targets
        ):
            state.limitations.append(
                Limitation(code="DT2002", message=boundary.reason, origin=source, world=plan.id)
            )

    return WorldResult(
        id=plan.id,
        assembly_state=plan.assembly_state,
        roots=tuple(sorted(set(plan.roots))),
        retained_roots=tuple(sorted(set(plan.retained_roots))),
        conservative_roots=tuple(sorted(set(plan.conservative_roots))),
        root_provenance=tuple(
            sorted(
                plan.root_provenance, key=lambda item: (str(item.target), item.kind, item.detail)
            )
        ),
        resolved_may_run=frozenset(state.resolved),
        conservative_may_run=frozenset(state.conservative - state.resolved),
        retained=frozenset(state.retained),
        derivations=tuple(sorted(state.derivations, key=_derivation_sort_key)),
        limitations=tuple(sorted(set(state.limitations), key=_limitation_sort_key)),
        exhausted_budget=state.exhausted_budget,
    )


def _mark(
    state: _MutableWorld,
    queue: deque[tuple[NodeId, ReachabilityKind]],
    *,
    target: NodeId,
    reachability: ReachabilityKind,
    kind: EdgeKind,
    source: NodeId | None,
    detail: str,
) -> None:
    collection = state.resolved if reachability is ReachabilityKind.RESOLVED else state.conservative
    if target in collection:
        return
    collection.add(target)
    state.derivations.append(
        Derivation(
            world=state.plan.id,
            target=target,
            reachability=reachability,
            kind=kind,
            source=source,
            detail=detail,
        )
    )
    queue.append((target, reachability))


def _require_known_node(node_map: dict[NodeId, SemanticNode], node_id: NodeId, label: str) -> None:
    if node_id not in node_map:
        raise ValueError(f"{label} {node_id!r} is not present in the semantic graph")


def _fact_sort_key(value: object) -> tuple[str, ...]:
    if isinstance(value, ExecutionEdge):
        return (str(value.target), value.kind.value, value.detail)
    if isinstance(value, Requirement):
        return (str(value.target), value.kind.value, value.detail)
    if isinstance(value, UnknownBoundary):
        return (value.domain, value.reason, *(str(target) for target in value.targets))
    raise TypeError(type(value))


def _derivation_sort_key(value: Derivation) -> tuple[str, ...]:
    return (
        value.world.key,
        str(value.target),
        value.reachability.value,
        value.kind.value,
        str(value.source or ""),
        value.detail,
    )


def _limitation_sort_key(value: Limitation) -> tuple[str, ...]:
    return (
        value.world.key if value.world else "",
        value.code,
        str(value.origin or ""),
        value.message,
    )
