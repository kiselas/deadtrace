"""Why findings of an earlier analysis are no longer reported (ADR-0122).

A finding disappears when its code is deleted, when a resolved path from a root now reaches it,
or when an unknown boundary now only keeps it possibly running; the count of findings falls the
same way in each case. The scan that no longer reports a finding still holds its graph, so it
records the cause; a comparison of saved reports reads the causes instead of re-running analysis.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from deadtrace.analysis import AnalysisResult
from deadtrace.comparison import cause_rank
from deadtrace.core import (
    Derivation,
    EdgeKind,
    NodeId,
    ReachabilityKind,
    SemanticNode,
    UnknownBoundary,
    WorldId,
    WorldResult,
    solve,
)
from deadtrace.findings import Finding
from deadtrace.semantic_report import first_boundaries

COUNTERFACTUAL_LIMIT = 8
"""Boundaries whose removal is re-solved to tell whether they alone keep a member running."""

_BOUNDARY_PREFIX = "unknown execution boundary: "


def explain_resolved(
    result: AnalysisResult, entries: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """The cause of each earlier finding, given by fingerprint, code and members, that this
    analysis no longer shows; entries it still shows are left out."""

    shown = {finding.fingerprint for finding in result.findings}
    pending = [
        entry
        for entry in entries
        if isinstance(entry.get("fingerprint"), str) and entry["fingerprint"] not in shown
    ]
    if not pending:
        return []
    context = _Context.of(result)
    explained = [context.explain(entry) for entry in pending]
    context.settle_counterfactuals()
    return sorted(explained, key=lambda item: str(item["fingerprint"]))


@dataclass(slots=True)
class _Context:
    result: AnalysisResult
    production: tuple[WorldResult, ...]
    tests: tuple[WorldResult, ...]
    complete: bool
    node_by_member: dict[tuple[str, str, str, int], NodeId]
    finding_of_node: dict[NodeId, Finding]
    blocked: dict[str, Finding]
    retained: frozenset[NodeId]
    reasons: dict[tuple[NodeId, str], str]
    node_map: dict[NodeId, SemanticNode]
    protected: list[tuple[dict[str, Any], NodeId, tuple[NodeId, str], bool]] = field(
        default_factory=list
    )
    """Each protected member's output, its node, the boundary that protects it, and whether a
    tests world reaching it also hides the finding."""
    _boundaries: dict[str, dict[NodeId, tuple[NodeId, str] | None]] = field(default_factory=dict)
    _resolved: dict[str, dict[NodeId, Derivation]] = field(default_factory=dict)
    _conservative: dict[str, dict[NodeId, Derivation]] = field(default_factory=dict)
    _crossed: dict[WorldId, tuple[UnknownBoundary, ...]] = field(default_factory=dict)
    _targets: dict[int, frozenset[NodeId]] = field(default_factory=dict)
    _module_of: dict[NodeId, NodeId] = field(default_factory=dict)

    @classmethod
    def of(cls, result: AnalysisResult) -> _Context:
        production = tuple(world for world in result.snapshot.worlds if world.id.profile != "tests")
        tests = tuple(world for world in result.snapshot.worlds if world.id.profile == "tests")
        node_by_member = {
            (symbol.path, symbol.qualified_name, symbol.kind.value, symbol.occurrence): symbol.id
            for symbol in result.program.symbols.values()
        }
        finding_of_node: dict[NodeId, Finding] = {}
        for finding in (*result.findings, *result.blocked_findings):
            for member in finding.members:
                key = (member.path, member.qualified_name, member.kind, member.occurrence)
                if (node := node_by_member.get(key)) is not None:
                    finding_of_node.setdefault(node, finding)
        reasons: dict[tuple[NodeId, str], str] = {}
        for boundary in (
            *result.snapshot.graph.boundaries,
            *(boundary for plan in result.model.plans for boundary in plan.boundaries),
        ):
            reasons.setdefault((boundary.source, boundary.domain), boundary.reason)
        return cls(
            result=result,
            production=production,
            tests=tests,
            complete=bool(production)
            and all(world.negative_findings_allowed for world in production),
            node_by_member=node_by_member,
            finding_of_node=finding_of_node,
            blocked={finding.fingerprint: finding for finding in result.blocked_findings},
            retained=frozenset().union(*(world.retained for world in production)),
            reasons=reasons,
            node_map=result.snapshot.graph.node_map(),
        )

    def explain(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        fingerprint = str(entry["fingerprint"])
        members = [
            member for member in entry.get("members", []) or [] if isinstance(member, Mapping)
        ]
        explained: dict[str, Any] = {"fingerprint": fingerprint, "code": entry.get("code")}
        if (blocked := self.blocked.get(fingerprint)) is not None:
            return {**explained, "cause": "blocked", "blocked": list(blocked.blocked)}
        if not self.complete:
            # Findings are emitted only when every production world is complete; a degraded
            # analysis cannot vouch for the absence of any finding.
            return {**explained, "cause": "incomplete"}
        # RCH001 leaves out what a tests world reaches; RCH004 is defined by such reach.
        member_causes = [
            self._member(member, with_tests=entry.get("code") == "RCH001") for member in members
        ]
        cause = min(
            (item["status"] for item in member_causes), key=cause_rank, default="unexplained"
        )
        return {**explained, "cause": cause, "members": member_causes}

    def settle_counterfactuals(self) -> None:
        """Record for each protected member whether its boundary alone keeps it hidden: without
        the boundary, no world whose reach hides the finding reaches the member at all.

        Resolved reach does not depend on unknown boundaries, so a member that another boundary
        crossed from resolved code targets directly stays possibly running: ``sole`` is false
        without solving. The rest are solved again boundary by boundary; removing a boundary can
        only shrink what a world reaches, so only the worlds that reach one of its members are
        solved. The solved worlds add up to at most the worlds of the analysis, about one more
        solve; past that budget or ``COUNTERFACTUAL_LIMIT`` boundaries, ``sole`` is null. The
        budget counts worlds, not seconds, so the report stays deterministic."""

        pending = []
        for item in self.protected:
            output, node, key, with_tests = item
            if self._covered_elsewhere(node, key, with_tests=with_tests):
                output["evidence"]["sole"] = False
            else:
                pending.append(item)
        budget = len(self.result.snapshot.worlds)
        keys = sorted({key for _, _, key, _ in pending})[:COUNTERFACTUAL_LIMIT]
        for key in keys:
            entries = [item for item in pending if item[2] == key]
            worlds = {
                world.id
                for _, node, _, with_tests in entries
                for world in (*self.production, *(self.tests if with_tests else ()))
                if node in world.resolved_may_run or node in world.conservative_may_run
            }
            if len(worlds) > budget:
                continue
            budget -= len(worlds)
            reached = self._reached_without(key, worlds)
            for output, node, _, with_tests in entries:
                hiding = {world.id for world in self.production}
                if with_tests:
                    hiding |= {world.id for world in self.tests}
                output["evidence"]["sole"] = not any(
                    node in nodes for world, nodes in reached.items() if world in hiding
                )
        for output, *_ in self.protected:
            output["evidence"].setdefault("sole", None)

    def _covered_elsewhere(
        self, node: NodeId, key: tuple[NodeId, str], *, with_tests: bool
    ) -> bool:
        """Whether a boundary other than ``key``, crossed from resolved code of a world that
        reaches ``node``, targets it with no gate that only conservative code could open."""

        if not self._module_of:
            modules = {
                item.path: item.id for item in self.node_map.values() if item.kind.value == "module"
            }
            self._module_of = {
                item.id: modules[item.path]
                for item in self.node_map.values()
                if item.path in modules
            }
        for world in (*self.production, *(self.tests if with_tests else ())):
            if node not in world.conservative_may_run:
                continue
            for boundary in self._crossed_in(world):
                if (boundary.source, boundary.domain) == key or boundary.opens_gates:
                    continue
                if boundary.targets and node not in self._target_set(boundary):
                    continue
                gate = dict(boundary.gates).get(node) or (
                    self._module_of.get(node) if boundary.needs_module else None
                )
                if gate is None or gate in world.resolved_may_run:
                    return True
        return False

    def _crossed_in(self, world: WorldResult) -> tuple[UnknownBoundary, ...]:
        if world.id not in self._crossed:
            plan = next(item for item in self.result.model.plans if item.id == world.id)
            self._crossed[world.id] = tuple(
                boundary
                for boundary in (*self.result.snapshot.graph.boundaries, *plan.boundaries)
                if boundary.source in world.resolved_may_run
            )
        return self._crossed[world.id]

    def _target_set(self, boundary: UnknownBoundary) -> frozenset[NodeId]:
        key = id(boundary.targets)
        if key not in self._targets:
            self._targets[key] = frozenset(boundary.targets)
        return self._targets[key]

    def _member(self, member: Mapping[str, Any], *, with_tests: bool) -> dict[str, Any]:
        identity = {
            "path": member.get("path"),
            "qualified_name": member.get("qualified_name"),
            "kind": member.get("kind"),
            "occurrence": member.get("occurrence"),
        }
        occurrence = member.get("occurrence")
        node = self.node_by_member.get(
            (
                str(member.get("path")),
                str(member.get("qualified_name")),
                str(member.get("kind")),
                occurrence if isinstance(occurrence, int) else -1,
            )
        )
        if node is None:
            return {**identity, "status": "deleted"}
        if (finding := self.finding_of_node.get(node)) is not None:
            evidence: dict[str, Any] = {"fingerprint": finding.fingerprint, "code": finding.code}
            if finding.blocked:
                evidence["blocked"] = list(finding.blocked)
            return {**identity, "status": "regrouped", "evidence": evidence}
        for world in self.production:
            if node in world.resolved_may_run:
                return {**identity, "status": "reached", "evidence": self._reached(world, node)}
        if self._is_retained(node):
            return {
                **identity,
                "status": "kept",
                "evidence": {"contract": "retained declaration"},
            }
        for world in self.production:
            if node in world.conservative_may_run:
                return self._protection(identity, world, node, with_tests=with_tests)
        for world in self.tests if with_tests else ():
            if node in world.resolved_may_run:
                return {**identity, "status": "reached", "evidence": self._reached(world, node)}
        for world in self.tests if with_tests else ():
            if node in world.conservative_may_run:
                return self._protection(identity, world, node, with_tests=with_tests)
        return {**identity, "status": "unexplained"}

    def _protection(
        self, identity: dict[str, Any], world: WorldResult, node: NodeId, *, with_tests: bool
    ) -> dict[str, Any]:
        cause = self._first_boundary(world).get(node)
        if cause is None:
            return {
                **identity,
                "status": "kept",
                "evidence": {"world": world.id.key, "contract": self._contract(world, node)},
            }
        origin, detail = cause
        domain = detail.removeprefix(_BOUNDARY_PREFIX)
        evidence: dict[str, Any] = {
            "world": world.id.key,
            "boundary": {
                **self._place(origin),
                "domain": domain,
                "reason": self.reasons.get((origin, domain), domain),
            },
        }
        # A caller that itself may run only through the boundary is a consumer the analysis
        # cannot vouch for; a member the boundary targets directly has none, and a class held
        # by its own method is ownership, not a consumer.
        derivation = self._derivations(world, ReachabilityKind.CONSERVATIVE).get(node)
        if (
            derivation is not None
            and derivation.source is not None
            and derivation.kind not in {EdgeKind.UNKNOWN, EdgeKind.MEMBER}
        ):
            evidence["edge"] = derivation.kind.value
            evidence["from"] = self._place(derivation.source)
        output = {**identity, "status": "protected", "evidence": evidence}
        self.protected.append((output, node, (origin, domain), with_tests))
        return output

    def _reached(self, world: WorldResult, node: NodeId) -> dict[str, Any]:
        derivation = self._derivations(world, ReachabilityKind.RESOLVED).get(node)
        if derivation is None or derivation.source is None:
            provenance = next((item for item in world.root_provenance if item.target == node), None)
            return {
                "world": world.id.key,
                "root": provenance.kind if provenance is not None else "root",
                "detail": provenance.detail if provenance is not None else "",
            }
        return {
            "world": world.id.key,
            "edge": derivation.kind.value,
            "from": self._place(derivation.source),
        }

    def _contract(self, world: WorldResult, node: NodeId) -> str:
        """The detail of the conservative root a node is derived from, such as a keep contract."""

        derivations = self._derivations(world, ReachabilityKind.CONSERVATIVE)
        seen: set[NodeId] = set()
        current: NodeId | None = node
        detail = "conservative root"
        while current is not None and current not in seen:
            seen.add(current)
            derivation = derivations.get(current)
            if derivation is None:
                break
            detail = derivation.detail
            current = derivation.source
        return detail

    def _is_retained(self, node: NodeId) -> bool:
        current: NodeId | None = node
        seen: set[NodeId] = set()
        while current is not None and current not in seen:
            if current in self.retained:
                return True
            seen.add(current)
            semantic = self.node_map.get(current)
            current = semantic.owner if semantic is not None else None
        return False

    def _reached_without(
        self, key: tuple[NodeId, str], worlds: set[WorldId]
    ) -> dict[WorldId, frozenset[NodeId]]:
        """What each of ``worlds`` reaches once the boundary ``key`` is gone."""

        graph = self.result.snapshot.graph
        without = replace(
            graph,
            boundaries=tuple(
                item for item in graph.boundaries if (item.source, item.domain) != key
            ),
        )
        plans = tuple(
            replace(
                plan,
                boundaries=tuple(
                    item for item in plan.boundaries if (item.source, item.domain) != key
                ),
            )
            for plan in self.result.model.plans
            if plan.id in worlds
        )
        snapshot = solve(without, plans)
        return {
            world.id: frozenset(world.resolved_may_run | world.conservative_may_run)
            for world in snapshot.worlds
        }

    def _first_boundary(self, world: WorldResult) -> dict[NodeId, tuple[NodeId, str] | None]:
        key = world.id.key
        if key not in self._boundaries:
            self._boundaries[key] = first_boundaries(world)
        return self._boundaries[key]

    def _derivations(
        self, world: WorldResult, reachability: ReachabilityKind
    ) -> dict[NodeId, Derivation]:
        cache = self._resolved if reachability is ReachabilityKind.RESOLVED else self._conservative
        key = world.id.key
        if key not in cache:
            found: dict[NodeId, Derivation] = {}
            for derivation in world.derivations:
                if derivation.reachability is reachability:
                    found.setdefault(derivation.target, derivation)
            cache[key] = found
        return cache[key]

    def _place(self, node_id: NodeId) -> dict[str, Any]:
        node = self.node_map.get(node_id)
        if node is None:
            return {"name": str(node_id)}
        return {"name": node.display_name, "path": node.path, "line": node.line}
