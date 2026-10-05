"""Read PEP 621 project entry points as bounded data without loading them."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deadtrace.artifacts import MAX_ARTIFACT_BYTES, InputTooLargeError, read_bounded_bytes

_OBJECT_REFERENCE = re.compile(
    r"^\s*(?P<module>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"
    r"(?::(?P<object>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*))?"
    r"(?:\s*\[[^\]]+\])?\s*$"
)


@dataclass(frozen=True, order=True, slots=True)
class ProjectEntryPoint:
    group: str
    name: str
    target: str

    @property
    def scenario(self) -> str:
        return f"entrypoint:{self.group}:{self.name}"


@dataclass(frozen=True, order=True, slots=True)
class EntryPointIssue:
    code: str
    message: str


def read_project_entry_points(
    root: Path,
) -> tuple[tuple[ProjectEntryPoint, ...], tuple[EntryPointIssue, ...]]:
    """Return static PEP 621 entry points and limitations; never invoke a build backend."""

    path = root / "pyproject.toml"
    if not path.is_file():
        return (), ()
    try:
        document = tomllib.loads(read_bounded_bytes(path, limit=MAX_ARTIFACT_BYTES).decode("utf-8"))
    except InputTooLargeError:
        return (), (
            EntryPointIssue("DT4101", "pyproject.toml is too large for entry-point discovery"),
        )
    except (OSError, UnicodeError, RecursionError, tomllib.TOMLDecodeError) as error:
        return (), (EntryPointIssue("DT4101", f"cannot read project entry points: {error}"),)
    project = document.get("project")
    if not isinstance(project, dict):
        return (), ()

    entries: list[ProjectEntryPoint] = []
    issues: list[EntryPointIssue] = []
    dynamic = project.get("dynamic", [])
    if isinstance(dynamic, list):
        dynamic_names = {item for item in dynamic if isinstance(item, str)}
        dynamic_entry_fields = dynamic_names.intersection(
            {"scripts", "gui-scripts", "entry-points"}
        )
        if dynamic_entry_fields:
            issues.append(
                EntryPointIssue(
                    "DT4102",
                    "dynamic project entry points require executing a build backend and "
                    "were not loaded",
                )
            )

    _read_group(project.get("scripts"), "console_scripts", entries, issues)
    _read_group(project.get("gui-scripts"), "gui_scripts", entries, issues)
    groups = project.get("entry-points")
    if groups is not None:
        if not isinstance(groups, dict):
            issues.append(EntryPointIssue("DT4101", "project.entry-points must be a table"))
        else:
            for group, values in sorted(groups.items()):
                if not isinstance(group, str) or not isinstance(values, dict):
                    issues.append(
                        EntryPointIssue(
                            "DT4101", "project.entry-points groups must be one-level tables"
                        )
                    )
                    continue
                _read_group(values, group, entries, issues)
    return tuple(sorted(set(entries))), tuple(sorted(set(issues)))


def _read_group(
    values: Any,
    group: str,
    entries: list[ProjectEntryPoint],
    issues: list[EntryPointIssue],
) -> None:
    if values is None:
        return
    if not isinstance(values, dict):
        issues.append(
            EntryPointIssue("DT4101", f"project entry-point group {group} must be a table")
        )
        return
    for name, value in sorted(values.items()):
        if not isinstance(name, str) or not isinstance(value, str):
            issues.append(
                EntryPointIssue("DT4101", f"entry point in group {group} must map names to strings")
            )
            continue
        match = _OBJECT_REFERENCE.fullmatch(value)
        if match is None:
            issues.append(
                EntryPointIssue(
                    "DT4101", f"entry point {group}:{name} has an invalid object reference"
                )
            )
            continue
        module = match.group("module")
        object_name = match.group("object")
        target = f"{module}:{object_name}" if object_name else module
        entries.append(ProjectEntryPoint(group, name, target))
