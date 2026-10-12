"""Hold back findings of forms that reviews showed to be mostly false (ADR-0071).

A blocked finding is not a claim that the code is dead. The analysis is unchanged: the finding
keeps its code, members, and fingerprint, and the JSON report lists it under
``blocked_findings`` with the reasons. Text output, exit codes, baselines, and comparisons see
only the findings that are not blocked.

Reasons, each measured on reviewed findings of public projects:

- ``external_base_hooks``: a method of a class whose base the project does not define; frameworks
  call such methods by name (``get_queryset``, ``allow_migrate``, ``__get_validators__``).
- ``non_production_area``: code under ``examples``, ``docs``, ``scripts``, ``tools`` and similar
  directories, which people run by hand.
- ``public_api``: a public name of a public package module, when the project documents its API
  (Sphinx autodoc, mkdocstrings, mkapi) or the module or its package lists the name in
  ``__all__``.
- ``mentioned_in_config``: the name appears in a configuration or template file of the project
  (YAML, TOML, INI, templates, Makefiles, Dockerfiles; not JSON, text, or deadtrace's own
  artifacts), where it is usually loaded by name.

Files are read as bounded text; nothing is imported or executed.
"""

from __future__ import annotations

import ast
import os
import re
from collections.abc import Iterable
from dataclasses import replace
from fnmatch import fnmatchcase
from pathlib import Path

from deadtrace.artifacts import InputTooLargeError, read_bounded_bytes
from deadtrace.findings import Finding, FindingMember
from deadtrace.python_frontend import (
    PythonModule,
    PythonProgram,
    PythonSymbol,
    _dotted_name,
    _unstarred,
    declared_exports,
)
from deadtrace.scanner import is_skipped_directory

BLOCKING_REASONS = (
    "external_base_hooks",
    "non_production_area",
    "public_api",
    "mentioned_in_config",
)
BLOCKABLE_CODES = frozenset({"RCH001", "RCH004"})
"""Reachability findings; RCH002 and RCH003 come from a framework model and are never blocked."""
NON_PRODUCTION_DIRECTORIES = frozenset(
    {
        "bench",
        "benchmark",
        "benchmarks",
        "demo",
        "demos",
        "doc",
        "docs",
        "docs_src",
        "example",
        "examples",
        "playground",
        "sample",
        "samples",
        "scripts",
        "tools",
    }
)
_TEST_DIRECTORIES = frozenset({"test", "tests", "testing"})
_NEUTRAL_BASES = frozenset({"object", "Protocol", "Generic", "ABC", "ABCMeta"})
CONFIGURATION_SUFFIXES = (
    ".cfg",
    ".conf",
    ".env",
    ".html",
    ".ini",
    ".j2",
    ".jinja",
    ".jinja2",
    ".toml",
    ".xml",
    ".yaml",
    ".yml",
)
_CONFIGURATION_NAMES = frozenset({"makefile", "dockerfile", "procfile", "justfile"})
_DOCUMENTATION_SUFFIXES = (".md", ".rst")
_API_DOCUMENTATION = re.compile(
    r"auto(?:module|class|function|method)::|^:::\s*[\w.]+|!\[mkapi\]", re.MULTILINE
)
MAX_TEXT_FILE_BYTES = 1024 * 1024
MAX_TEXT_FILES = 5000
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_MIN_MENTIONED_NAME = 4


class ProjectText:
    """Words of the project's configuration files, and whether it documents an API."""

    def __init__(self, root: Path, exclude: tuple[str, ...] = ()) -> None:
        self.configuration_words: frozenset[str] = frozenset()
        self.documents_api = False
        if not root.is_dir():
            return
        words: set[str] = set()
        read = 0
        for current, directory_names, file_names in os.walk(root, followlinks=False):
            current_path = Path(current)
            directory_names[:] = sorted(
                name for name in directory_names if not is_skipped_directory(current_path, name)
            )
            for name in sorted(file_names):
                if read >= MAX_TEXT_FILES:
                    break
                path = current_path / name
                relative = path.relative_to(root).as_posix()
                if any(fnmatchcase(relative, pattern) for pattern in exclude):
                    continue
                lowered = name.lower()
                configuration = lowered.endswith(CONFIGURATION_SUFFIXES) or (
                    lowered in _CONFIGURATION_NAMES
                )
                documentation = lowered.endswith(_DOCUMENTATION_SUFFIXES)
                if lowered == "mkdocs.yml" or lowered == "mkdocs.yaml":
                    documentation = True
                if not configuration and not documentation:
                    continue
                text = _read_text(path)
                read += 1
                if text is None:
                    continue
                if configuration and not _is_own_artifact(text):
                    words.update(_WORD.findall(text))
                if documentation and not self.documents_api:
                    self.documents_api = bool(_API_DOCUMENTATION.search(text)) or (
                        lowered.startswith("mkdocs") and "mkdocstrings" in text
                    )
        self.configuration_words = frozenset(words)


def apply_blocking(
    program: PythonProgram, findings: Iterable[Finding], text: ProjectText
) -> tuple[tuple[Finding, ...], tuple[Finding, ...]]:
    """Split findings into those shown and those blocked, the latter with their reasons."""

    shown: list[Finding] = []
    blocked: list[Finding] = []
    symbols = {
        (symbol.path, symbol.qualified_name, symbol.occurrence): symbol
        for symbol in program.symbols.values()
    }
    modules = {module.path: module for module in program.modules.values()}
    hierarchy = _ClassHierarchy(program)
    for finding in findings:
        if finding.code not in BLOCKABLE_CODES:
            shown.append(finding)
            continue
        reasons = sorted(
            {
                reason
                for member in finding.members
                for reason in _reasons(program, member, text, symbols, modules, hierarchy)
            }
        )
        if reasons:
            blocked.append(replace(finding, blocked=tuple(reasons)))
        else:
            shown.append(finding)
    return tuple(shown), tuple(blocked)


def _reasons(
    program: PythonProgram,
    member: FindingMember,
    text: ProjectText,
    symbols: dict[tuple[str, str, int], PythonSymbol],
    modules: dict[str, PythonModule],
    hierarchy: _ClassHierarchy,
) -> set[str]:
    reasons: set[str] = set()
    parts = member.path.replace("\\", "/").split("/")
    directories = parts[:-1]
    if any(part in NON_PRODUCTION_DIRECTORIES for part in directories):
        reasons.add("non_production_area")
    symbol = symbols.get((member.path, member.qualified_name, member.occurrence))
    if symbol is not None and symbol.owner is not None:
        owner = program.symbols.get(symbol.owner)
        if (
            owner is not None
            and isinstance(owner.node, ast.ClassDef)
            and hierarchy.meets_external_base(owner)
        ):
            reasons.add("external_base_hooks")
    if _is_public_package_member(member, directories) and (
        text.documents_api or _exported(program, member, modules)
    ):
        reasons.add("public_api")
    name = member.qualified_name.rpartition(".")[2]
    if (
        len(name) >= _MIN_MENTIONED_NAME
        and not name.startswith("__")
        and name in text.configuration_words
    ):
        reasons.add("mentioned_in_config")
    return reasons


class _ClassHierarchy:
    """Project classes with their project bases, subclasses, and external bases."""

    def __init__(self, program: PythonProgram) -> None:
        self.program = program
        self.bases: dict[str, list[PythonSymbol]] = {}
        self.subclasses: dict[str, list[PythonSymbol]] = {}
        self.external: set[str] = set()
        for symbol in program.symbols.values():
            if not isinstance(symbol.node, ast.ClassDef):
                continue
            external, bases = _classify_bases(program, symbol)
            if external:
                self.external.add(str(symbol.id))
            self.bases[str(symbol.id)] = bases
            for base in bases:
                self.subclasses.setdefault(str(base.id), []).append(symbol)

    def meets_external_base(self, class_symbol: PythonSymbol) -> bool:
        """Whether the class, a project ancestor, or a project subclass has an external base.

        A mixin without bases becomes part of every subclass, so a framework that calls hooks
        on such a subclass (``setUpTestData``, ``render_to_response``) may call the mixin's.
        """

        seen: set[str] = set()
        queue = [class_symbol]
        while queue:
            current = queue.pop()
            key = str(current.id)
            if key in seen:
                continue
            seen.add(key)
            if key in self.external:
                return True
            queue.extend(self.bases.get(key, ()))
        seen_down: set[str] = set()
        queue = [class_symbol]
        while queue:
            current = queue.pop()
            key = str(current.id)
            if key in seen_down:
                continue
            seen_down.add(key)
            if key in self.external:
                return True
            queue.extend(self.subclasses.get(key, ()))
        return False


def _classify_bases(
    program: PythonProgram, class_symbol: PythonSymbol
) -> tuple[bool, list[PythonSymbol]]:
    """Whether a base is external (neither project nor neutral), and the project bases."""

    module = program.modules.get(class_symbol.module)
    if module is None:
        return False, []
    external = False
    project: list[PythonSymbol] = []
    for base in class_symbol.bases:
        dotted = _dotted_name(_unstarred(base))
        if dotted is None and isinstance(base, ast.Subscript):
            dotted = _dotted_name(base.value)
        if dotted is None:
            continue
        if dotted.rpartition(".")[2] in _NEUTRAL_BASES:
            continue
        first, _, rest = dotted.partition(".")
        binding = module.imports.get(first)
        if binding is not None:
            full = f"{binding.target}.{rest}" if rest else binding.target
        else:
            full = f"{module.name}.{dotted}"
        resolved = program.resolve_symbol(full)
        if resolved is None:
            external = True
        elif isinstance(resolved.node, ast.ClassDef):
            project.append(resolved)
    return external, project


def _is_public_package_member(member: FindingMember, directories: list[str]) -> bool:
    path_parts = member.path.replace("\\", "/").split("/")
    if path_parts and path_parts[0] == "src":
        path_parts = path_parts[1:]
    if len(path_parts) < 2:
        return False
    if any(part in _TEST_DIRECTORIES for part in directories):
        return False
    if any(part.startswith("_") and part != "__init__.py" for part in path_parts):
        return False
    return not any(part.startswith("_") for part in member.qualified_name.split("."))


def _exported(
    program: PythonProgram, member: FindingMember, modules: dict[str, PythonModule]
) -> bool:
    """Whether the module, or the package that holds it, lists the name in ``__all__``."""

    top = member.qualified_name.split(".")[0]
    module = modules.get(member.path)
    if module is None:
        return False
    if top in (declared_exports(module) or frozenset()):
        return True
    package = program.modules.get(module.name.rpartition(".")[0])
    return package is not None and top in (declared_exports(package) or frozenset())


def _is_own_artifact(text: str) -> bool:
    """A report, baseline, or support bundle of deadtrace names every finding it holds."""

    head = text[:4096]
    return "deadtrace" in head and ("model_revision" in head or "fingerprint" in head)


def _read_text(path: Path) -> str | None:
    try:
        if path.is_symlink():
            return None
        return read_bounded_bytes(path, limit=MAX_TEXT_FILE_BYTES).decode("utf-8", errors="replace")
    except (OSError, InputTooLargeError):
        return None
