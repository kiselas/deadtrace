from __future__ import annotations

import pytest

from deadtrace.core import (
    AssemblyState,
    EdgeKind,
    ExecutionEdge,
    NodeId,
    NodeKind,
    ReachabilityKind,
    Requirement,
    SemanticGraph,
    SemanticNode,
    UnknownBoundary,
    WorldId,
    WorldPlan,
    solve,
)


def _node(name: str, *, owner: NodeId | None = None) -> SemanticNode:
    return SemanticNode(
        id=NodeId(name),
        display_name=name,
        kind=NodeKind.FUNCTION,
        path="case.py",
        line=1,
        owner=owner,
    )


def test_direct_chain_and_unreachable_islands() -> None:
    nodes = tuple(_node(name) for name in ("root", "live", "cycle_a", "cycle_b", "island"))
    graph = SemanticGraph(
        nodes=nodes,
        edges=(
            ExecutionEdge(NodeId("root"), NodeId("live"), EdgeKind.CALL, "root calls live"),
            ExecutionEdge(NodeId("cycle_a"), NodeId("cycle_b"), EdgeKind.CALL, "unreachable cycle"),
            ExecutionEdge(NodeId("cycle_b"), NodeId("cycle_a"), EdgeKind.CALL, "unreachable cycle"),
        ),
    )
    world = WorldId("production", "web")

    result = solve(graph, (WorldPlan(world, (NodeId("root"),)),)).world(world)

    assert result.resolved_may_run == {NodeId("root"), NodeId("live")}
    assert result.state_of(NodeId("cycle_a")) is None
    assert result.state_of(NodeId("island")) is None
    assert result.negative_findings_allowed


def test_shared_helper_reached_from_live_path() -> None:
    graph = SemanticGraph(
        nodes=tuple(_node(name) for name in ("root", "active", "legacy", "helper")),
        edges=(
            ExecutionEdge(NodeId("root"), NodeId("active"), EdgeKind.CALL, "active path"),
            ExecutionEdge(NodeId("active"), NodeId("helper"), EdgeKind.CALL, "shared helper"),
            ExecutionEdge(NodeId("legacy"), NodeId("helper"), EdgeKind.CALL, "shared helper"),
        ),
    )
    world = WorldId("production", "web")

    result = solve(graph, (WorldPlan(world, (NodeId("root"),)),)).world(world)

    assert result.state_of(NodeId("helper")) is not None
    assert result.state_of(NodeId("legacy")) is None


def test_callback_guard_propagates_to_helper() -> None:
    graph = SemanticGraph(
        nodes=tuple(_node(name) for name in ("root", "callback", "helper", "unrelated")),
        edges=(
            ExecutionEdge(NodeId("callback"), NodeId("helper"), EdgeKind.CALL, "callback helper"),
        ),
        boundaries=(
            UnknownBoundary(
                source=NodeId("root"),
                domain="callback",
                reason="external callback timing is unknown",
                targets=(NodeId("callback"),),
            ),
        ),
    )
    world = WorldId("production", "web")

    result = solve(graph, (WorldPlan(world, (NodeId("root"),)),)).world(world)

    assert NodeId("callback") in result.conservative_may_run
    assert NodeId("helper") in result.conservative_may_run
    assert result.state_of(NodeId("unrelated")) is None


def test_worlds_do_not_share_roots_or_requirements() -> None:
    graph = SemanticGraph(
        nodes=tuple(_node(name) for name in ("prod", "test", "prod_impl", "test_impl")),
        edges=(
            ExecutionEdge(NodeId("prod"), NodeId("prod_impl"), EdgeKind.CALL, "production"),
            ExecutionEdge(NodeId("test"), NodeId("test_impl"), EdgeKind.CALL, "tests"),
        ),
        requirements=(
            Requirement(NodeId("test"), NodeId("test_impl"), EdgeKind.KEEP, "test fixture"),
        ),
    )
    production = WorldId("production", "web")
    tests = WorldId("tests", "pytest")

    snapshot = solve(
        graph,
        (
            WorldPlan(production, (NodeId("prod"),)),
            WorldPlan(tests, (NodeId("test"),)),
        ),
    )

    assert snapshot.world(production).resolved_may_run == {NodeId("prod"), NodeId("prod_impl")}
    assert snapshot.world(production).retained == set()
    assert snapshot.world(tests).resolved_may_run == {NodeId("test"), NodeId("test_impl")}
    assert snapshot.world(tests).retained == {NodeId("test_impl")}


def test_invalid_or_rootless_world_blocks_negative_findings() -> None:
    graph = SemanticGraph(nodes=(_node("candidate"),))
    rootless = WorldId("production", "rootless")
    invalid = WorldId("production", "invalid")

    snapshot = solve(
        graph,
        (
            WorldPlan(rootless, ()),
            WorldPlan(
                invalid,
                (NodeId("candidate"),),
                assembly_state=AssemblyState.INVALID,
            ),
        ),
    )

    assert not snapshot.world(rootless).negative_findings_allowed
    assert not snapshot.world(invalid).negative_findings_allowed


def test_budget_exhaustion_widens_instead_of_dropping_targets() -> None:
    graph = SemanticGraph(
        nodes=tuple(_node(name) for name in ("root", "next", "otherwise_dead")),
        edges=(ExecutionEdge(NodeId("root"), NodeId("next"), EdgeKind.CALL, "next"),),
    )
    world = WorldId("production", "web")

    result = solve(graph, (WorldPlan(world, (NodeId("root"),)),), max_steps=1).world(world)

    assert result.exhausted_budget
    assert result.state_of(NodeId("otherwise_dead")) is not None
    assert not result.negative_findings_allowed


def test_conservative_root_propagates_without_becoming_resolved() -> None:
    world = WorldId("production", "external")
    graph = SemanticGraph(
        nodes=(_node("hook"), _node("helper")),
        edges=(ExecutionEdge(NodeId("hook"), NodeId("helper"), EdgeKind.CALL, "helper"),),
    )

    result = solve(
        graph,
        (
            WorldPlan(
                world,
                (),
                retained_roots=(NodeId("hook"),),
                conservative_roots=(NodeId("hook"),),
            ),
        ),
    ).world(world)

    assert result.conservative_may_run == {NodeId("hook"), NodeId("helper")}
    assert not result.resolved_may_run
    assert NodeId("hook") in result.retained


def test_graph_rejects_unknown_nodes_and_invalid_budget() -> None:
    graph = SemanticGraph(nodes=(_node("root"),))
    world = WorldId("production", "web")

    with pytest.raises(ValueError, match="positive"):
        solve(graph, (WorldPlan(world, (NodeId("root"),)),), max_steps=0)
    with pytest.raises(ValueError, match="world root"):
        solve(graph, (WorldPlan(world, (NodeId("missing"),)),))
    with pytest.raises(KeyError):
        solve(graph, (WorldPlan(world, (NodeId("root"),)),)).world(WorldId("other", "world"))


def test_refined_snapshot_does_not_keep_stale_conservative_state() -> None:
    nodes = tuple(_node(name) for name in ("root", "known", "unrelated"))
    world = WorldId("production", "web")
    guarded = SemanticGraph(
        nodes=nodes,
        boundaries=(UnknownBoundary(NodeId("root"), "pending", "temporary unresolved dispatch"),),
    )
    refined = SemanticGraph(
        nodes=nodes,
        edges=(ExecutionEdge(NodeId("root"), NodeId("known"), EdgeKind.CALL, "resolved"),),
    )

    guarded_result = solve(guarded, (WorldPlan(world, (NodeId("root"),)),)).world(world)
    refined_result = solve(refined, (WorldPlan(world, (NodeId("root"),)),)).world(world)

    assert guarded_result.state_of(NodeId("unrelated")) is ReachabilityKind.CONSERVATIVE
    assert refined_result.state_of(NodeId("known")) is ReachabilityKind.RESOLVED
    assert refined_result.state_of(NodeId("unrelated")) is None


def test_solver_result_is_independent_of_fact_order() -> None:
    nodes = tuple(_node(name) for name in ("root", "first", "second"))
    edges = (
        ExecutionEdge(NodeId("root"), NodeId("first"), EdgeKind.CALL, "first"),
        ExecutionEdge(NodeId("first"), NodeId("second"), EdgeKind.CALL, "second"),
    )
    world = WorldId("production", "web")

    forward = solve(
        SemanticGraph(nodes=nodes, edges=edges),
        (WorldPlan(world, (NodeId("root"),)),),
    ).world(world)
    reversed_result = solve(
        SemanticGraph(nodes=tuple(reversed(nodes)), edges=tuple(reversed(edges))),
        (WorldPlan(world, (NodeId("root"),)),),
    ).world(world)

    assert forward.resolved_may_run == reversed_result.resolved_may_run
    assert forward.conservative_may_run == reversed_result.conservative_may_run
    assert forward.retained == reversed_result.retained
    assert forward.limitations == reversed_result.limitations
