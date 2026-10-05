"""Read-only source discovery and inventory orchestration."""

from __future__ import annotations

import os
import tokenize
from collections.abc import Mapping
from dataclasses import dataclass
from fnmatch import fnmatchcase
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from deadtrace.config import Config
from deadtrace.inventory import ParsedSource, inventory_source, parse_source
from deadtrace.model import Definition, InventoryReport, ScanIssue
from deadtrace.timing import StageTimings

_UNIMPORTABLE_DIRECTORIES = frozenset({"__pycache__", "__pypackages__", "node_modules"})
"""Directories whose contents belong to tools or other ecosystems, never to the project."""
_ENVIRONMENT_MARKERS = ("pyvenv.cfg", "conda-meta")
"""Files or directories that mark a Python environment: a virtual environment or a conda one."""


@dataclass(frozen=True, slots=True)
class SourceUnit:
    path: str
    absolute_path: Path
    source: str
    digest: str


@dataclass(frozen=True, slots=True)
class SourceCollection:
    root: Path
    files: tuple[str, ...]
    units: tuple[SourceUnit, ...]
    issues: tuple[ScanIssue, ...]
    skipped_directories: tuple[str, ...] = ()
    """Environments and tool directories left out of the source universe (ADR-0015)."""
    excluded_files: tuple[str, ...] = ()
    """Python files that configured ``exclude`` patterns leave out (ADR-0018)."""


def collect_sources(
    scan_path: Path,
    *,
    timings: StageTimings | None = None,
    exclude: tuple[str, ...] = (),
) -> SourceCollection:
    """Read a stable source snapshot without importing or executing target code."""

    timings = timings if timings is not None else StageTimings()
    absolute_input = scan_path.absolute()
    root = absolute_input if absolute_input.is_dir() else absolute_input.parent
    canonical_root = root.resolve()
    last_files: tuple[str, ...] = ()
    last_issues: tuple[ScanIssue, ...] = ()
    last_skipped: tuple[str, ...] = ()
    last_excluded: tuple[str, ...] = ()
    for _attempt in range(2):
        timings.count("collect.attempts")
        collection, stable = _collect_source_attempt(
            absolute_input, root, canonical_root, timings, exclude
        )
        if stable:
            return collection
        last_files = collection.files
        last_issues = collection.issues
        last_skipped = collection.skipped_directories
        last_excluded = collection.excluded_files

    issue = ScanIssue(
        code="DT1002",
        path=".",
        message="source tree changed during scan; no mixed semantic snapshot was retained",
    )
    return SourceCollection(
        root=canonical_root,
        files=last_files,
        units=(),
        issues=tuple(
            sorted({*last_issues, issue}, key=lambda item: (item.path, item.code, item.message))
        ),
        skipped_directories=last_skipped,
        excluded_files=last_excluded,
    )


def _collect_source_attempt(
    absolute_input: Path,
    root: Path,
    canonical_root: Path,
    timings: StageTimings,
    exclude: tuple[str, ...] = (),
) -> tuple[SourceCollection, bool]:
    with timings.stage("collect.discover"):
        found, discovery_issues, skipped = _discover_python_files(absolute_input, canonical_root)
    files, excluded = _apply_exclude(found, root, exclude)
    issues = list(discovery_issues)
    inventory_files: list[str] = []
    units: list[SourceUnit] = []
    signatures: dict[Path, str] = {}

    with timings.stage("collect.read"):
        for file_path in files:
            relative = file_path.relative_to(root).as_posix()
            inventory_files.append(relative)
            timings.count("collect.files_read")
            try:
                source, digest = _read_python_source(file_path)
                units.append(SourceUnit(relative, file_path, source, digest))
                signatures[file_path] = f"ok:{digest}"
                timings.count("collect.characters", len(source))
            except (OSError, UnicodeError, SyntaxError, LookupError) as error:
                message = _single_line(error)
                issues.append(ScanIssue(code="DT1001", path=relative, message=message))
                signatures[file_path] = f"error:{type(error).__name__}:{message}"
                timings.count("collect.read_errors")

    collection = SourceCollection(
        root=canonical_root,
        files=tuple(sorted(inventory_files)),
        units=tuple(sorted(units, key=lambda item: item.path)),
        issues=tuple(sorted(issues, key=lambda item: (item.path, item.code, item.message))),
        skipped_directories=skipped,
        excluded_files=excluded,
    )
    with timings.stage("collect.verify_discover"):
        verified_files, verified_discovery_issues, verified_skipped = _discover_python_files(
            absolute_input, canonical_root
        )
    stable = (
        found == verified_files
        and discovery_issues == verified_discovery_issues
        and skipped == verified_skipped
    )
    if stable:
        with timings.stage("collect.verify_read"):
            for file_path in files:
                try:
                    _source, digest = _read_python_source(file_path)
                    signature = f"ok:{digest}"
                except (OSError, UnicodeError, SyntaxError, LookupError) as error:
                    message = _single_line(error)
                    signature = f"error:{type(error).__name__}:{message}"
                if signatures[file_path] != signature:
                    stable = False
                    break
    return collection, stable


type ParsedCollection = Mapping[str, ParsedSource | SyntaxError]
"""Each source unit's single parse, or the syntax error that prevented it, keyed by path."""


def parse_collection(
    collection: SourceCollection, *, timings: StageTimings | None = None
) -> ParsedCollection:
    """Parse every unit once so inventory, frontend, and frameworks share one tree each."""

    timings = timings if timings is not None else StageTimings()
    parsed: dict[str, ParsedSource | SyntaxError] = {}
    with timings.stage("collect.parse"):
        for unit in collection.units:
            try:
                parsed[unit.path] = parse_source(unit.source)
            except SyntaxError as error:
                parsed[unit.path] = error
            except RecursionError:
                parsed[unit.path] = SyntaxError("expression nesting exceeds the parser's limit")
    return parsed


def scan(scan_path: Path, config: Config) -> InventoryReport:
    """Build schema-0 inventory from a file or directory without executing it."""

    collection = collect_sources(scan_path, exclude=config.exclude)
    return inventory_collection(collection, config)


def inventory_collection(
    collection: SourceCollection,
    config: Config,
    *,
    timings: StageTimings | None = None,
    parsed: ParsedCollection | None = None,
) -> InventoryReport:
    """Build inventory from an already captured source snapshot."""

    timings = timings if timings is not None else StageTimings()
    definitions: list[Definition] = []
    issues = list(collection.issues)
    for unit in collection.units:
        entry = parsed.get(unit.path) if parsed is not None else None
        try:
            if isinstance(entry, SyntaxError):
                raise entry
            definitions.extend(
                inventory_source(
                    unit.source,
                    path=unit.path,
                    report_exclude=config.report_exclude,
                    timings=timings,
                    parsed=entry,
                )
            )
        except SyntaxError as error:
            issues.append(ScanIssue(code="DT1001", path=unit.path, message=_syntax_message(error)))

    ordered_definitions = tuple(
        sorted(
            definitions,
            key=lambda item: (
                item.path,
                item.span.start_line,
                item.span.start_column,
                item.kind.value,
                item.qualified_name,
                item.occurrence,
            ),
        )
    )
    ordered_issues = tuple(sorted(issues, key=lambda item: (item.path, item.code, item.message)))
    return InventoryReport(
        root=str(collection.root),
        files=collection.files,
        definitions=ordered_definitions,
        issues=ordered_issues,
    )


def _discover_python_files(
    scan_path: Path, canonical_root: Path
) -> tuple[tuple[Path, ...], tuple[ScanIssue, ...], tuple[str, ...]]:
    if not scan_path.exists():
        issue = ScanIssue(code="DT1000", path=str(scan_path), message="scan path does not exist")
        return (), (issue,), ()
    if scan_path.is_file():
        if scan_path.suffix != ".py":
            issue = ScanIssue(code="DT1000", path=scan_path.name, message="scan file is not Python")
            return (), (issue,), ()
        accepted, issues = _accept_paths((scan_path,), scan_path.parent, canonical_root)
        return accepted, issues, ()

    candidates: list[Path] = []
    skipped: list[str] = []
    discovery_issues: list[ScanIssue] = []

    def record_walk_error(error: OSError) -> None:
        failed_path = Path(error.filename) if error.filename is not None else scan_path
        discovery_issues.append(
            ScanIssue(
                code="DT1001",
                path=failed_path.relative_to(scan_path).as_posix(),
                message=f"cannot read directory: {_single_line(error)}",
            )
        )

    for current, directory_names, file_names in os.walk(
        scan_path, followlinks=False, onerror=record_walk_error
    ):
        current_path = Path(current)
        kept: list[str] = []
        for name in sorted(directory_names):
            if is_skipped_directory(current_path, name):
                skipped.append((current_path / name).relative_to(scan_path).as_posix())
            else:
                kept.append(name)
        directory_names[:] = kept
        candidates.extend(
            current_path / name for name in sorted(file_names) if name.endswith(".py")
        )
    accepted, issues = _accept_paths(tuple(candidates), scan_path, canonical_root)
    return (
        accepted,
        tuple(
            sorted(
                (*discovery_issues, *issues), key=lambda item: (item.path, item.code, item.message)
            )
        ),
        tuple(sorted(skipped)),
    )


def _apply_exclude(
    files: tuple[Path, ...], root: Path, patterns: tuple[str, ...]
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Split discovered files into source and those an ``exclude`` pattern names.

    A pattern is a glob over the path relative to the scan root, with ``/`` separators, as in
    ``report-exclude``; ``corpus/**`` names everything below ``corpus``.
    """

    if not patterns:
        return files, ()
    kept: list[Path] = []
    excluded: list[str] = []
    for file_path in files:
        relative = file_path.relative_to(root).as_posix()
        if any(fnmatchcase(relative, pattern) for pattern in patterns):
            excluded.append(relative)
        else:
            kept.append(file_path)
    return tuple(kept), tuple(sorted(excluded))


def is_skipped_directory(parent: Path, name: str) -> bool:
    """Whether a directory below the scan path holds no project source (ADR-0015).

    A name that starts with a dot cannot be a package, so nothing in it is importable as project
    code; such directories hold tool state, caches, and virtual environments. ``site-packages``,
    ``node_modules``, ``__pycache__``, and ``__pypackages__`` belong to installers and other
    tools, and a directory marked as a Python environment holds installed distributions whatever
    its name. Other unimportable names stay in the universe: their scripts still run when invoked
    by path.
    """

    if name.startswith(".") or name in _UNIMPORTABLE_DIRECTORIES or name == "site-packages":
        return True
    directory = parent / name
    if name == "build" and _is_setuptools_build(directory):
        return True
    return any((directory / marker).exists() for marker in _ENVIRONMENT_MARKERS)


def _is_setuptools_build(directory: Path) -> bool:
    """A ``build`` directory that holds setuptools copies of packages (``lib``, ``bdist.*``)."""

    try:
        children = [entry.name for entry in directory.iterdir() if entry.is_dir()]
    except OSError:
        return False
    return any(child == "lib" or child.startswith(("lib.", "bdist.")) for child in children)


def _accept_paths(
    candidates: tuple[Path, ...], display_root: Path, canonical_root: Path
) -> tuple[tuple[Path, ...], tuple[ScanIssue, ...]]:
    accepted: list[Path] = []
    issues: list[ScanIssue] = []
    for candidate in candidates:
        try:
            candidate.resolve().relative_to(canonical_root)
        except (OSError, ValueError):
            issues.append(
                ScanIssue(
                    code="DT1002",
                    path=candidate.relative_to(display_root).as_posix(),
                    message="symbolic link resolves outside the scan root",
                )
            )
            continue
        accepted.append(candidate)
    return tuple(accepted), tuple(issues)


def _read_python_source(path: Path) -> tuple[str, str]:
    """Read one stable file, retrying once if its metadata changes mid-read."""

    for attempt in range(2):
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        stable = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
        if stable:
            encoding, _ = tokenize.detect_encoding(BytesIO(data).readline)
            return data.decode(encoding), sha256(data).hexdigest()
        if attempt == 1:
            raise OSError("source changed while it was being read")
    raise AssertionError("unreachable")


def _single_line(error: BaseException) -> str:
    return " ".join(str(error).splitlines())


def _syntax_message(error: SyntaxError) -> str:
    location = f" at line {error.lineno}, column {error.offset}" if error.lineno else ""
    hint = " (syntax newer than the interpreter running deadtrace is reported the same way)"
    return f"syntax error{location}: {_single_line(Exception(error.msg))}{hint}"
