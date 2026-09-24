from __future__ import annotations

from pathlib import Path

from deadtrace.config import Config
from deadtrace.python_frontend import build_python_program
from deadtrace.scanner import collect_sources, inventory_collection, parse_collection
from deadtrace.timing import StageTimings

MAIN = (
    "import os\n"
    "from helper import helper as run\n"
    "\n"
    "VALUE = run()\n"
    "\n"
    "class Service:\n"
    "    def call(self) -> int:\n"
    "        return run()\n"
)
HELPER = "def helper() -> int:\n    return 1\n"
BROKEN = "def broken(:\n"


def _project(root: Path) -> Path:
    for name, source in (("main.py", MAIN), ("helper.py", HELPER), ("broken.py", BROKEN)):
        (root / name).write_text(source, encoding="utf-8", newline="\n")
    return root


def test_shared_parse_matches_on_demand_parse(tmp_path: Path) -> None:
    collection = collect_sources(_project(tmp_path))
    parsed = parse_collection(collection)

    assert isinstance(parsed["broken.py"], SyntaxError)
    assert inventory_collection(collection, Config(), parsed=parsed) == inventory_collection(
        collection, Config()
    )
    shared = build_python_program(collection, parsed=parsed)
    on_demand = build_python_program(collection)
    assert shared.graph == on_demand.graph
    assert shared.limitations == on_demand.limitations
    assert {
        name: (module.imports, sorted(module.statement_lines.values()))
        for name, module in shared.modules.items()
    } == {
        name: (module.imports, sorted(module.statement_lines.values()))
        for name, module in on_demand.modules.items()
    }


def test_shared_tree_is_the_one_symbols_point_into(tmp_path: Path) -> None:
    collection = collect_sources(_project(tmp_path))
    parsed = parse_collection(collection)
    program = build_python_program(collection, parsed=parsed)

    entry = parsed["main.py"]
    assert not isinstance(entry, SyntaxError)
    module = program.modules["main"]
    assert module.tree is entry.tree
    class_node = next(s.node for s in module.symbols if s.name == "Service")
    assert class_node in entry.tree.body
    assert sorted(module.statement_lines.values()) == [1, 2, 4]


def test_frontend_does_not_parse_again_when_given_a_shared_parse(tmp_path: Path) -> None:
    collection = collect_sources(_project(tmp_path))
    timings = StageTimings()
    parsed = parse_collection(collection, timings=timings)
    build_python_program(collection, parsed=parsed, timings=timings)

    assert timings.seconds["collect.parse"] > 0.0
    assert timings.seconds["frontend.parse"] == 0.0
    assert timings.counts["frontend.modules"] == 2
    assert timings.counts["frontend.parse_failures"] == 1
