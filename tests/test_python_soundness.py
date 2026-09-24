"""The Python-core rules (ADR-0008, ADR-0009, ADR-0010) keep what may run and nothing more.

The positive cases live in ``corpus/python``. These tests check that each rule stays local: dead
code that merely looks like live code is still unreached.
"""

from __future__ import annotations

from pathlib import Path

from deadtrace.core import ReachabilityKind, WorldId, WorldPlan, WorldResult, solve
from deadtrace.python_frontend import PythonProgram, build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def _program(**sources: str) -> PythonProgram:
    collection = SourceCollection(
        root=Path("/project"),
        files=tuple(sorted(sources)),
        units=tuple(
            SourceUnit(path, Path("/project") / path, source, f"digest-{path}")
            for path, source in sorted(sources.items())
        ),
        issues=(),
    )
    return build_python_program(collection)


def _world(program: PythonProgram, root: str) -> WorldResult:
    world = WorldId("production", "script")
    symbol = program.resolve_symbol(root)
    assert symbol is not None, root
    roots = (symbol.id, program.modules[symbol.module].node_id)
    return solve(program.graph, (WorldPlan(world, roots),)).world(world)


def _state(program: PythonProgram, world: WorldResult, target: str) -> ReachabilityKind | None:
    symbol = program.resolve_symbol(target)
    assert symbol is not None, target
    return world.state_of(symbol.id)


def test_a_reference_in_an_unreached_function_protects_nothing() -> None:
    program = _program(
        **{
            "main.py": """
def helper() -> int:
    return 1

def dead() -> object:
    return helper

def main() -> None:
    pass
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:dead") is None
    assert _state(program, world, "main:helper") is None


def test_unknown_receiver_protects_only_methods_with_that_name() -> None:
    program = _program(
        **{
            "main.py": """
class Repository:
    def fetch(self) -> int:
        return 1

    def purge(self) -> int:
        return 2

def main(repository) -> None:
    repository.fetch()
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:Repository.fetch") is ReachabilityKind.CONSERVATIVE
    assert _state(program, world, "main:Repository.purge") is None


def test_transparent_decorators_do_not_register_the_function() -> None:
    program = _program(
        **{
            "main.py": """
import functools

@functools.lru_cache(maxsize=None)
def cached() -> int:
    return 1

class Tools:
    @staticmethod
    def helper() -> int:
        return 2

def main() -> None:
    pass
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:cached") is None
    assert _state(program, world, "main:Tools") is None
    assert _state(program, world, "main:Tools.helper") is None


def test_an_external_decorator_in_an_unreached_module_protects_nothing() -> None:
    program = _program(
        **{
            "main.py": "def main() -> None:\n    pass\n",
            "tasks.py": """
from celery import Celery

app = Celery("jobs")

@app.task
def job() -> None:
    pass
""",
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "tasks:job") is None


def test_overrides_in_an_unrelated_hierarchy_are_not_dispatched_to() -> None:
    program = _program(
        **{
            "main.py": """
class Notifier:
    def send(self) -> str:
        return "base"

class EmailNotifier(Notifier):
    def send(self) -> str:
        return "email"

class Printer:
    def send(self) -> str:
        return "printer"

def main(notifier: Notifier) -> None:
    notifier.send()
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:Notifier.send") is ReachabilityKind.RESOLVED
    assert _state(program, world, "main:EmailNotifier.send") is ReachabilityKind.RESOLVED
    assert _state(program, world, "main:Printer.send") is None


def test_local_names_shadow_project_functions_of_the_same_name() -> None:
    program = _program(
        **{
            "main.py": """
def callback() -> int:
    return 1

def run(callback) -> int:
    return callback()

def main() -> None:
    run(lambda: 0)
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:run") is ReachabilityKind.RESOLVED
    assert _state(program, world, "main:callback") is None


def test_a_method_body_does_not_see_its_class_scope() -> None:
    program = _program(
        **{
            "main.py": """
def helper() -> int:
    return 1

class Service:
    def helper(self) -> int:
        return 2

    def run(self) -> int:
        return helper()

def main() -> None:
    Service().run()
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:helper") is ReachabilityKind.RESOLVED
    assert _state(program, world, "main:Service.helper") is None


def test_a_class_used_only_in_a_dead_function_annotation_stays_unreached() -> None:
    program = _program(
        **{
            "main.py": """
class Settings:
    pass

def dead(settings: Settings) -> None:
    del settings

def main() -> None:
    pass
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:dead") is None
    assert _state(program, world, "main:Settings") is None


def test_hook_free_external_bases_do_not_protect_ordinary_methods() -> None:
    program = _program(
        **{
            "main.py": """
import enum
import pydantic

class Payload(pydantic.BaseModel):
    name: str

    def unused_helper(self) -> str:
        return self.name

class AppError(Exception):
    def unused_detail(self) -> str:
        return "detail"

class Color(enum.Enum):
    RED = 1

    @classmethod
    def _missing_(cls, value: object) -> "Color":
        return cls.RED

    def unused_label(self) -> str:
        return "red"

def main() -> None:
    print(Payload(name="x"), AppError(), Color(1))
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:Payload.unused_helper") is None
    assert _state(program, world, "main:AppError.unused_detail") is None
    assert _state(program, world, "main:Color.unused_label") is None
    assert _state(program, world, "main:Color._missing_") is ReachabilityKind.CONSERVATIVE


def test_external_base_hooks_apply_only_to_classes_in_use() -> None:
    program = _program(
        **{
            "main.py": """
import threading

class Unused(threading.Thread):
    def run(self) -> None:
        pass

def main() -> None:
    pass
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:Unused.run") is None


def test_strings_protect_only_exact_names_in_code_that_runs() -> None:
    program = _program(
        **{
            "main.py": """
def dead() -> str:
    return "plugins.alpha"

def main() -> None:
    print("plugins.alpha.setup extra", "plugins")
""",
            "plugins/__init__.py": "",
            "plugins/alpha.py": "def setup() -> None:\n    pass\n",
        }
    )
    world = _world(program, "main:main")

    assert world.state_of(program.modules["plugins.alpha"].node_id) is None
    assert _state(program, world, "plugins.alpha:setup") is None


def test_type_checking_imports_and_imports_in_dead_functions_run_nothing() -> None:
    program = _program(
        **{
            "main.py": """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing_only

def dead() -> None:
    import lazy

def main() -> None:
    pass
""",
            "typing_only.py": "def setup() -> None:\n    pass\n\nsetup()\n",
            "lazy.py": "def setup() -> None:\n    pass\n\nsetup()\n",
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "typing_only:setup") is None
    assert _state(program, world, "lazy:setup") is None


def test_sequential_redefinitions_and_unconditional_rebinding_stay_precise() -> None:
    program = _program(
        **{
            "main.py": """
from first import helper
from second import helper

def render() -> None:
    pass

def render() -> None:
    pass

def main() -> None:
    helper()
    render()
""",
            "first.py": "def helper() -> None:\n    pass\n",
            "second.py": "def helper() -> None:\n    pass\n",
        }
    )
    world = _world(program, "main:main")
    renders = program.index.named("main.render")

    assert _state(program, world, "first:helper") is None
    assert _state(program, world, "second:helper") is ReachabilityKind.RESOLVED
    assert [world.state_of(item.id) for item in renders] == [None, ReachabilityKind.RESOLVED]


def test_a_local_name_shadows_an_import_of_the_enclosing_function() -> None:
    program = _program(
        **{
            "main.py": """
def main() -> None:
    from tasks import run

    def inner() -> None:
        run = print
        run()

    inner()
""",
            "tasks.py": "def run() -> None:\n    pass\n",
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "tasks:run") is None


def test_star_imports_and_reexport_cycles_bind_only_what_is_used() -> None:
    program = _program(
        **{
            "main.py": """
from helpers import *
from loop_a import missing

def main() -> None:
    greet()
    missing()
""",
            "helpers.py": "def greet() -> None:\n    pass\n\ndef unused() -> None:\n    pass\n",
            "loop_a.py": "from loop_b import missing\n",
            "loop_b.py": "from loop_a import missing\n",
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "helpers:greet") is ReachabilityKind.RESOLVED
    assert _state(program, world, "helpers:unused") is None


def test_classes_given_to_inspecting_or_dead_code_expose_no_methods() -> None:
    program = _program(
        **{
            "main.py": """
class Checked:
    def convert(self) -> None:
        pass

class Registered:
    def convert(self) -> None:
        pass

def dead() -> None:
    handlers = [Registered]

def main(value: object) -> bool:
    return isinstance(value, Checked)
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:Checked.convert") is None
    assert _state(program, world, "main:Registered.convert") is None


def test_single_underscore_names_that_are_not_hooks_stay_unreached() -> None:
    program = _program(
        **{
            "main.py": """
class Table:
    def _render(self) -> None:
        pass

    def __private(self) -> None:
        pass

    def _(self) -> None:
        pass

def main() -> Table:
    return Table()
"""
        }
    )
    world = _world(program, "main:main")

    for name in ("_render", "__private", "_"):
        assert _state(program, world, f"main:Table.{name}") is None


def test_an_overload_without_a_later_implementation_is_not_linked() -> None:
    program = _program(
        **{
            "main.py": """
from typing import overload

@overload
def first(value: int) -> int: ...

def first(value: int) -> int:
    return value

@overload
def orphan(value: int) -> int: ...

def main() -> None:
    first(1)
"""
        }
    )
    world = _world(program, "main:main")
    firsts = program.index.named("main.first")

    assert [world.state_of(item.id) for item in firsts] == [ReachabilityKind.RESOLVED] * 2
    assert _state(program, world, "main:orphan") is None


def test_a_nested_definition_is_reached_only_where_its_name_is_used() -> None:
    program = _program(
        **{
            "main.py": """
def main() -> None:
    write = print

    def write() -> None:
        pass

    def other() -> None:
        pass

    other = print
"""
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:main.write") is None
    assert _state(program, world, "main:main.other") is None
