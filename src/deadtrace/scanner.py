"""Read-only source discovery and inventory orchestration."""

from __future__ import annotations

import os
import tokenize
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from deadtrace.config import Config
from deadtrace.inventory import ParsedSource, inventory_source, parse_source
from deadtrace.model import Definition, InventoryReport, ScanIssue
from deadtrace.timing import StageTimings

_SKIPPED_DIRECTORIES = frozenset(
    {".git", ".hg", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".venv", "__pycache__"}
)


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


def collect_sources(scan_path: Path, *, timings: StageTimings | None = None) -> SourceCollection:
    """Read a stable source snapshot without importing or executing target code."""

    timings = timings if timings is not None else StageTimings()
    absolute_input = scan_path.absolute()
    root = absolute_input if absolute_input.is_dir() else absolute_input.parent
    canonical_root = root.resolve()
    last_files: tuple[str, ...] = ()
    last_issues: tuple[ScanIssue, ...] = ()
    for _attempt in range(2):
        timings.count("collect.attempts")
        collection, stable = _collect_source_attempt(absolute_input, root, canonical_root, timings)
        if stable:
            return collection
        last_files = collection.files
        last_issues = collection.issues

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
    )


def _collect_source_attempt(
    absolute_input: Path,
    root: Path,
    canonical_root: Path,
    timings: StageTimings,
) -> tuple[SourceCollection, bool]:
    with timings.stage("collect.discover"):
        files, discovery_issues = _discover_python_files(absolute_input, canonical_root)
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
            except (OSError, UnicodeError, SyntaxError) as error:
                message = _single_line(error)
                issues.append(ScanIssue(code="DT1001", path=relative, message=message))
                signatures[file_path] = f"error:{type(error).__name__}:{message}"
                timings.count("collect.read_errors")

    collection = SourceCollection(
        root=canonical_root,
        files=tuple(sorted(inventory_files)),
        units=tuple(sorted(units, key=lambda item: item.path)),
        issues=tuple(sorted(issues, key=lambda item: (item.path, item.code, item.message))),
    )
    with timings.stage("collect.verify_discover"):
        verified_files, verified_discovery_issues = _discover_python_files(
            absolute_input, canonical_root
        )
    stable = files == verified_files and discovery_issues == verified_discovery_issues
    if stable:
        with timings.stage("collect.verify_read"):
            for file_path in files:
                try:
                    _source, digest = _read_python_source(file_path)
                    signature = f"ok:{digest}"
                except (OSError, UnicodeError, SyntaxError) as error:
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
    return parsed


def scan(scan_path: Path, config: Config) -> InventoryReport:
    """Build schema-0 inventory from a file or directory without executing it."""

    collection = collect_sources(scan_path)
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
) -> tuple[tuple[Path, ...], tuple[ScanIssue, ...]]:
    if not scan_path.exists():
        issue = ScanIssue(code="DT1000", path=str(scan_path), message="scan path does not exist")
        return (), (issue,)
    if scan_path.is_file():
        if scan_path.suffix != ".py":
            issue = ScanIssue(code="DT1000", path=scan_path.name, message="scan file is not Python")
            return (), (issue,)
        return _accept_paths((scan_path,), scan_path.parent, canonical_root)

    candidates: list[Path] = []
    for current, directory_names, file_names in os.walk(scan_path, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if name not in _SKIPPED_DIRECTORIES
        )
        current_path = Path(current)
        candidates.extend(
            current_path / name for name in sorted(file_names) if name.endswith(".py")
        )
    return _accept_paths(tuple(candidates), scan_path, canonical_root)


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
    return f"syntax error{location}: {_single_line(Exception(error.msg))}"
