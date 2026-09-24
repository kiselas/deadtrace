"""Small immutable data objects shared by the inventory pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DefinitionKind(StrEnum):
    """Kinds recognized by the first, lexical-only frontend."""

    FUNCTION = "function"
    CLASS = "class"


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """A half-open source range. Lines are 1-based; columns are 0-based."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def to_dict(self) -> dict[str, int]:
        return {
            "start_line": self.start_line,
            "start_column": self.start_column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }


@dataclass(frozen=True, slots=True)
class Definition:
    """A lexical function or class declaration."""

    path: str
    qualified_name: str
    name: str
    kind: DefinitionKind
    owner: str | None
    occurrence: int
    span: SourceSpan
    report_excluded: bool

    def identity(self) -> tuple[str, str, str, int]:
        return (self.path, self.qualified_name, self.kind.value, self.occurrence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "qualified_name": self.qualified_name,
            "name": self.name,
            "kind": self.kind.value,
            "owner": self.owner,
            "occurrence": self.occurrence,
            "span": self.span.to_dict(),
            "report_excluded": self.report_excluded,
        }


@dataclass(frozen=True, slots=True)
class ScanIssue:
    """A non-silent problem encountered while building the source universe."""

    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True, slots=True)
class InventoryReport:
    """Experimental report schema 0."""

    root: str
    files: tuple[str, ...]
    definitions: tuple[Definition, ...]
    issues: tuple[ScanIssue, ...]

    @property
    def has_errors(self) -> bool:
        return bool(self.issues)
