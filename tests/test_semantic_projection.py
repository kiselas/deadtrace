from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from deadtrace import semantic_report
from deadtrace.analysis import analyze
from deadtrace.config import Config
from deadtrace.core import Derivation, NodeId


@pytest.mark.parametrize("limit", [0, 3, 100])
def test_derivation_projection_converts_only_the_stable_shown_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: int
) -> None:
    (tmp_path / "main.py").write_text(
        "\n".join(f"def f_{index:02}():\n    return {index}\n" for index in range(50)),
        encoding="utf-8",
    )
    result = analyze(tmp_path, Config())
    node_map = result.model.graph.node_map()
    world = result.snapshot.worlds[0]
    smallest = min(
        world.derivations,
        key=lambda item: (
            item.world.key,
            node_map[item.target].display_name,
            item.reachability.value,
            item.kind.value,
        ),
    )
    # Equal sort keys with different details must preserve their input order.
    world = replace(
        world,
        derivations=(
            replace(smallest, detail="tie first"),
            replace(smallest, detail="tie second"),
            *reversed(world.derivations),
        ),
    )
    result = replace(result, snapshot=replace(result.snapshot, worlds=(world,)))
    original = semantic_report._derivation_dict
    expected = sorted(
        (original(item, node_map) for item in world.derivations),
        key=lambda item: (item["world"], item["target"], item["reachability"], item["kind"]),
    )[:limit]
    converted = 0

    def counted(derivation: Derivation, nodes: dict[NodeId, Any]) -> dict[str, str | None]:
        nonlocal converted
        converted += 1
        return original(derivation, nodes)

    monkeypatch.setattr(semantic_report, "_EXPLANATION_LIMIT", limit)
    monkeypatch.setattr(semantic_report, "_derivation_dict", counted)
    report = semantic_report.semantic_report_dict(result)
    explanations = report["explanations"]
    assert explanations["derivations"] == expected
    assert explanations["total"] == len(world.derivations)
    assert explanations["truncated"] is (limit < len(world.derivations))
    assert converted == min(limit, len(world.derivations))
