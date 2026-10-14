"""Manifest-selected roots are local, bounded and narrower than a module export."""

from __future__ import annotations

import json
import posixpath
from pathlib import Path

import pytest

from deadtrace import frameworks
from deadtrace.config import Config
from deadtrace.core import WorldPlan
from deadtrace.deployment import (
    MAX_DEPLOYMENT_FILE_BYTES,
    DeploymentReference,
    read_deployment_references,
)
from deadtrace.frameworks import COMMANDS_WORLD, build_framework_model
from deadtrace.python_frontend import PythonProgram, build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def _write(root: Path, path: str, text: str) -> None:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")


def _plan(
    sources: dict[str, str], target: str, manifest: str = "templates/a/cookiecutter.json"
) -> tuple[PythonProgram, WorldPlan | None]:
    root = Path("/project")
    collection = SourceCollection(
        root=root,
        files=tuple(sorted(sources)),
        units=tuple(
            SourceUnit(path, root / path, source, "owned-" + path)
            for path, source in sorted(sources.items())
        ),
        issues=(),
    )
    program = build_python_program(collection)
    model = build_framework_model(
        program, Config(), deployment=(DeploymentReference("local_object", target, manifest),)
    )
    return program, next((plan for plan in model.plans if plan.id == COMMANDS_WORLD), None)


def test_only_named_extensions_in_the_exact_manifest_are_read(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "templates/a/cookiecutter.json",
        json.dumps(
            {
                "_extensions": [
                    "filters.chosen",
                    "plugins:Extension",
                    "filters.chosen",
                    1,
                    None,
                    "../filters.chosen",
                    "filters:Class.method",
                    "plain",
                    "a:b:c",
                ],
                "example": "other.unused",
            }
        ),
    )
    _write(tmp_path, "data.json", '{"_extensions": ["other.unused"]}')
    assert read_deployment_references(tmp_path) == (
        DeploymentReference("local_object", "filters:chosen", "templates/a/cookiecutter.json"),
        DeploymentReference("local_object", "plugins:Extension", "templates/a/cookiecutter.json"),
    )
    assert read_deployment_references(tmp_path, ("templates/**",)) == ()


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "[]",
        "null",
        '{"extensions": ["filters.chosen"]}',
        '{"_extensions": "filters.chosen"}',
        '{"_extensions": null}',
        '{"_extensions": {"filters.chosen": true}}',
        pytest.param("[" * 20000 + "]" * 20000, id="too-deep"),
    ],
)
def test_invalid_or_non_list_manifest_adds_no_roots(tmp_path: Path, text: str) -> None:
    _write(tmp_path, "cookiecutter.json", text)
    assert read_deployment_references(tmp_path) == ()


def test_oversized_manifest_is_not_parsed(tmp_path: Path) -> None:
    _write(tmp_path, "cookiecutter.json", " " * MAX_DEPLOYMENT_FILE_BYTES + "{}")
    assert read_deployment_references(tmp_path) == ()


def test_symlinked_manifest_is_not_read(tmp_path: Path) -> None:
    _write(tmp_path, "payload.txt", '{"_extensions": ["filters.chosen"]}')
    try:
        (tmp_path / "cookiecutter.json").symlink_to(tmp_path / "payload.txt")
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")
    assert read_deployment_references(tmp_path) == ()


def test_template_directory_wins_without_exposing_other_definitions() -> None:
    source = "def chosen():\n    return 1\ndef unused():\n    return 2\n"
    program, plan = _plan(
        {
            "templates/a/__init__.py": "",
            "templates/a/filters.py": source,
            "templates/b/filters.py": source,
            "filters.py": source,
        },
        "filters:chosen",
    )
    assert plan is not None
    chosen = program.resolve_symbol("templates.a.filters.chosen")
    assert chosen is not None and chosen.id in plan.retained_roots
    for name in ("templates.a.filters.unused", "templates.b.filters.chosen", "filters.chosen"):
        other = program.resolve_symbol(name)
        assert other is not None and other.id not in plan.retained_roots
    assert {item.detail for item in plan.root_provenance} == {
        "templates/a/cookiecutter.json: filters:chosen"
    }


def test_regular_package_reexport_and_src_path_keep_local_roots() -> None:
    program, plan = _plan(
        {
            "src/tool/templates/extensions/__init__.py": "from .filters import chosen\n",
            "src/tool/templates/extensions/filters.py": "def chosen():\n    return 1\n",
            "src/tool/templates/extensions.py": "def chosen():\n    return 2\n",
        },
        "extensions:chosen",
        "src/tool/templates/cookiecutter.json",
    )
    assert plan is not None
    package = next(
        module for module in program.modules.values() if module.path.endswith("__init__.py")
    )
    selected = program.resolve_symbol(f"{package.name}.filters.chosen")
    assert selected is not None and selected.id in plan.retained_roots
    assert package.node_id in plan.roots
    assert all(
        module.node_id not in plan.roots
        for module in program.modules.values()
        if module.path.endswith("extensions.py")
    )


def test_package_initializers_are_roots_but_a_plain_module_blocks_descendants() -> None:
    program, plan = _plan(
        {
            "templates/a/plugins/__init__.py": "marker = 1\n",
            "templates/a/plugins/sub.py": "def chosen():\n    return 1\n",
        },
        "plugins.sub:chosen",
    )
    assert plan is not None
    assert {
        program.modules[name].node_id for name in ("templates.a.plugins", "templates.a.plugins.sub")
    } <= set(plan.roots)

    program, plan = _plan(
        {
            "templates/a/plugins.py": "marker = 1\n",
            "templates/a/plugins/sub.py": "def chosen():\n    return 1\n",
        },
        "plugins.sub:chosen",
    )
    assert plan is not None
    assert program.modules["templates.a.plugins"].node_id in plan.roots
    selected = program.resolve_symbol("templates.a.plugins.sub.chosen")
    assert selected is not None and selected.id not in plan.retained_roots


def test_missing_local_extension_does_not_fall_back_to_another_directory() -> None:
    _, plan = _plan({"templates/b/filters.py": "def chosen():\n    return 1\n"}, "filters:chosen")
    assert plan is None


def test_missing_namespace_bounds_long_extension_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    original = posixpath.join
    joins = 0

    def counted(path: str, *parts: str) -> str:
        nonlocal joins
        joins += 1
        return original(path, *parts)

    monkeypatch.setattr(posixpath, "join", counted)
    reference = DeploymentReference(
        "local_object", "missing." * 1000 + "filters:chosen", "cookiecutter.json"
    )
    assert frameworks._local_extension_modules({}, reference) == []
    assert joins <= 1


def test_selected_package_class_does_not_expose_shadowed_file_methods() -> None:
    program, plan = _plan(
        {
            "templates/a/extensions.py": (
                "class Extension:\n    def shadowed(self):\n        return 1\n"
            ),
            "templates/a/extensions/__init__.py": (
                "class Extension:\n    def active(self):\n        return 2\n"
            ),
        },
        "extensions:Extension",
    )
    assert plan is not None
    active = program.resolve_symbol("templates.a.extensions.Extension.active")
    shadowed = program.resolve_symbol("templates.a.extensions.Extension.shadowed")
    assert active is not None and active.id in plan.retained_roots
    assert shadowed is not None and shadowed.id not in plan.retained_roots
