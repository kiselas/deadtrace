"""Standard-library ``ast`` frontend that emits lexical facts and never imports target code."""

from __future__ import annotations

import ast
import re
import warnings
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase

from deadtrace.model import Definition, DefinitionKind, SourceSpan
from deadtrace.timing import StageTimings

type DefinitionNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef

DEFINITION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class SourceText:
    """Source text of one module with line lookup and character columns.

    ``ast`` reports columns as UTF-8 byte offsets, while reports use character columns. Line starts
    are computed only when a caller needs a line, which for columns means non-ASCII text.
    """

    __slots__ = ("_line_starts", "ascii", "text")

    def __init__(self, text: str) -> None:
        self.text = text
        self.ascii = text.isascii()
        self._line_starts: list[int] | None = None

    def line(self, number: int) -> str:
        """Line ``number`` (1-based) without its line break."""

        starts = self._starts()
        start = starts[number - 1]
        end = starts[number] if number < len(starts) else len(self.text)
        return _LINE_BREAK.sub("", self.text[start:end])

    def column(self, line: int, byte_offset: int) -> int:
        """Character column of a UTF-8 byte offset on ``line``."""

        if self.ascii:
            return byte_offset
        text = self.line(line)
        if text.isascii():
            return byte_offset
        return len(text.encode("utf-8")[:byte_offset].decode("utf-8"))

    def segment(self, node: ast.expr) -> str:
        """The source text of ``node``, with line breaks written as ``\\n``."""

        assert node.end_lineno is not None and node.end_col_offset is not None
        lines = [
            self.line(number).encode("utf-8") for number in range(node.lineno, node.end_lineno + 1)
        ]
        lines[-1] = lines[-1][: node.end_col_offset]
        lines[0] = lines[0][node.col_offset :]
        return "\n".join(line.decode("utf-8") for line in lines)

    def _starts(self) -> list[int]:
        if self._line_starts is None:
            self._line_starts = [0, *(match.end() for match in _LINE_BREAK.finditer(self.text))]
        return self._line_starts


@dataclass(frozen=True, slots=True)
class ParsedSource:
    """One parse of one source file, shared by every pass that reads it. No pass may mutate it."""

    tree: ast.Module
    text: SourceText


def parse_source(source: str) -> ParsedSource:
    """Parse once with the running interpreter's grammar. Raises ``SyntaxError``.

    Warnings the compiler emits while parsing, such as invalid escape sequences, describe the target
    program; they are suppressed so they never reach Deadtrace's own output.
    """

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        tree = ast.parse(source)
    return ParsedSource(tree, SourceText(source))


def child_statements(statement: ast.stmt) -> list[ast.stmt]:
    """Statements nested directly in ``statement``, in source order."""

    if isinstance(statement, (ast.Try, ast.TryStar)):
        return [
            *statement.body,
            *(child for handler in statement.handlers for child in handler.body),
            *statement.orelse,
            *statement.finalbody,
        ]
    if isinstance(statement, ast.Match):
        return [child for case in statement.cases for child in case.body]
    return [
        *getattr(statement, "body", ()),
        *getattr(statement, "orelse", ()),
    ]


def iter_definitions(
    statements: Sequence[ast.stmt],
) -> Iterator[tuple[DefinitionNode, tuple[DefinitionNode, ...]]]:
    """Yield every function and class definition with its enclosing definitions, in source order.

    Definitions are statements, so only nested statement lists are searched.
    """

    stack: list[tuple[ast.stmt, tuple[DefinitionNode, ...]]] = [
        (statement, ()) for statement in reversed(statements)
    ]
    while stack:
        statement, owners = stack.pop()
        inner_owners = owners
        if isinstance(statement, DEFINITION_TYPES):
            yield statement, owners
            inner_owners = (*owners, statement)
        stack.extend((child, inner_owners) for child in reversed(child_statements(statement)))


def inventory_source(
    source: str,
    *,
    path: str,
    report_exclude: Sequence[str] = (),
    timings: StageTimings | None = None,
    parsed: ParsedSource | None = None,
) -> tuple[Definition, ...]:
    """Return deterministic lexical definitions, parsing ``source`` unless already parsed."""

    timings = timings if timings is not None else StageTimings()
    if parsed is None:
        with timings.stage("collect.parse"):
            parsed = parse_source(source)
    report_excluded = _matches_any(path, report_exclude)
    occurrences: defaultdict[tuple[str, DefinitionKind], int] = defaultdict(int)
    definitions: list[Definition] = []
    with timings.stage("collect.inventory_visit"):
        text = parsed.text
        for node, owners in iter_definitions(parsed.tree.body):
            kind = (
                DefinitionKind.CLASS if isinstance(node, ast.ClassDef) else DefinitionKind.FUNCTION
            )
            owner = ".".join(item.name for item in owners) or None
            qualified_name = f"{owner}.{node.name}" if owner else node.name
            occurrence = occurrences[(qualified_name, kind)]
            occurrences[(qualified_name, kind)] += 1
            assert node.end_lineno is not None and node.end_col_offset is not None
            definitions.append(
                Definition(
                    path=path,
                    qualified_name=qualified_name,
                    name=node.name,
                    kind=kind,
                    owner=owner,
                    occurrence=occurrence,
                    span=SourceSpan(
                        start_line=node.lineno,
                        start_column=text.column(node.lineno, node.col_offset),
                        end_line=node.end_lineno,
                        end_column=text.column(node.end_lineno, node.end_col_offset),
                    ),
                    report_excluded=report_excluded,
                )
            )
    return tuple(definitions)


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatchcase(normalized, pattern.replace("\\", "/")) for pattern in patterns)
