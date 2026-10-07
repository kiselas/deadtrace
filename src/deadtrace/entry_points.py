"""Read project entry points as bounded data without loading them (PEP 621, Poetry, flit)."""

from __future__ import annotations

import configparser
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


@dataclass(frozen=True, slots=True)
class ProjectDistribution:
    """The distribution ``pyproject.toml`` declares and the import packages it may ship."""

    name: str
    packages: frozenset[str]


def read_project_distribution(root: Path) -> ProjectDistribution | None:
    """Return the declared ``[project].name`` and candidate import packages, without a build.

    Candidates are the normalized distribution name (``Flask-SocketIO`` gives ``flask_socketio``)
    plus packages that ``[tool.setuptools.packages]`` or ``[tool.hatch.build.targets.wheel]``
    list literally. A missing name or an unreadable file gives ``None``; the caller checks which
    candidates exist in the source (ADR-0052).
    """

    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        document = tomllib.loads(read_bounded_bytes(path, limit=MAX_ARTIFACT_BYTES).decode("utf-8"))
    except (OSError, UnicodeError, RecursionError, tomllib.TOMLDecodeError, InputTooLargeError):
        return None
    project = document.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("name"), str):
        return None
    name = project["name"]
    packages = {re.sub(r"[-.]+", "_", name).lower()}
    tool = document.get("tool")
    if isinstance(tool, dict):
        setuptools = tool.get("setuptools")
        if isinstance(setuptools, dict):
            listed = setuptools.get("packages")
            if isinstance(listed, list):
                packages.update(_top_level(item) for item in listed if isinstance(item, str))
        hatch = tool.get("hatch")
        if isinstance(hatch, dict):
            build = hatch.get("build")
            targets = build.get("targets") if isinstance(build, dict) else None
            wheel = targets.get("wheel") if isinstance(targets, dict) else None
            listed = wheel.get("packages") if isinstance(wheel, dict) else None
            if isinstance(listed, list):
                packages.update(
                    _top_level(item.rpartition("/")[2]) for item in listed if isinstance(item, str)
                )
    return ProjectDistribution(name, frozenset(packages))


def _top_level(dotted: str) -> str:
    return dotted.split(".")[0]


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
        return tuple(sorted(set(_read_setup_cfg(root / "setup.cfg")))), ()
    try:
        document = tomllib.loads(read_bounded_bytes(path, limit=MAX_ARTIFACT_BYTES).decode("utf-8"))
    except InputTooLargeError:
        return (), (
            EntryPointIssue("DT4101", "pyproject.toml is too large for entry-point discovery"),
        )
    except (OSError, UnicodeError, RecursionError, tomllib.TOMLDecodeError) as error:
        return (), (EntryPointIssue("DT4101", f"cannot read project entry points: {error}"),)
    entries: list[ProjectEntryPoint] = []
    issues: list[EntryPointIssue] = []
    _read_tool_entry_points(document, entries, issues)
    entries.extend(_read_setup_cfg(root / "setup.cfg"))
    project = document.get("project")
    if not isinstance(project, dict):
        return tuple(sorted(set(entries))), tuple(sorted(set(issues)))
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


def _read_tool_entry_points(
    document: dict[str, Any], entries: list[ProjectEntryPoint], issues: list[EntryPointIssue]
) -> None:
    """Poetry and flit declare entry points under ``[tool]`` instead of ``[project]`` (ADR-0063)."""

    tool = document.get("tool")
    if not isinstance(tool, dict):
        return
    poetry = tool.get("poetry")
    if isinstance(poetry, dict):
        _read_group(poetry.get("scripts"), "console_scripts", entries, issues, strict=False)
        plugins = poetry.get("plugins")
        if isinstance(plugins, dict):
            for group, values in sorted(plugins.items()):
                if isinstance(group, str):
                    _read_group(values, group, entries, issues, strict=False)
    flit = tool.get("flit")
    if isinstance(flit, dict):
        _read_group(flit.get("scripts"), "console_scripts", entries, issues, strict=False)
        groups = flit.get("entrypoints")
        if isinstance(groups, dict):
            for group, values in sorted(groups.items()):
                if isinstance(group, str):
                    _read_group(values, group, entries, issues, strict=False)


def _read_setup_cfg(path: Path) -> list[ProjectEntryPoint]:
    """``[options.entry_points]`` of ``setup.cfg``: one ``name = module:object`` per line."""

    if not path.is_file():
        return []
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(
            read_bounded_bytes(path, limit=MAX_ARTIFACT_BYTES).decode("utf-8"), source=str(path)
        )
    except (OSError, UnicodeError, InputTooLargeError, configparser.Error):
        return []
    section = "options.entry_points"
    if not parser.has_section(section):
        return []
    entries: list[ProjectEntryPoint] = []
    for group, text in parser.items(section):
        for line in text.splitlines():
            name, separator, reference = line.partition("=")
            match = _OBJECT_REFERENCE.fullmatch(reference) if separator else None
            if match is None or not name.strip():
                continue
            module = match.group("module")
            object_name = match.group("object")
            target = f"{module}:{object_name}" if object_name else module
            entries.append(ProjectEntryPoint(group.strip(), name.strip(), target))
    return entries


def _read_group(
    values: Any,
    group: str,
    entries: list[ProjectEntryPoint],
    issues: list[EntryPointIssue],
    *,
    strict: bool = True,
) -> None:
    if values is None:
        return
    if not isinstance(values, dict):
        if not strict:
            return
        issues.append(
            EntryPointIssue("DT4101", f"project entry-point group {group} must be a table")
        )
        return
    for name, value in sorted(values.items()):
        if not isinstance(name, str) or not isinstance(value, str):
            if not strict:
                continue
            issues.append(
                EntryPointIssue("DT4101", f"entry point in group {group} must map names to strings")
            )
            continue
        match = _OBJECT_REFERENCE.fullmatch(value)
        if match is None:
            if strict:
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
