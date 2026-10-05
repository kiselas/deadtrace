"""Safe helpers for user-selected JSON artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, NoReturn

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
"""Largest project input, such as ``pyproject.toml`` or ``uv.lock``, that analysis reads."""
MAX_REPORT_BYTES = 256 * 1024 * 1024
"""Largest Deadtrace report or baseline read back; a 624k-line monorepo writes about 113 MB."""


class ArtifactError(ValueError):
    """Raised when a report-like artifact is missing, oversized, or malformed."""


class InputTooLargeError(ValueError):
    """An opened input exceeded its reader's byte limit."""


def read_bounded_bytes(path: Path, *, limit: int) -> bytes:
    """Read at most ``limit + 1`` bytes, even if file size metadata is stale.

    Small chunks avoid reserving the full report allowance for a small file. The extra byte
    distinguishes an input exactly at the limit from one that is too large.
    """

    if limit < 0:
        raise ValueError("byte limit must be nonnegative")
    chunks: list[bytes] = []
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(min(64 * 1024, limit + 1 - size)):
            size += len(chunk)
            if size > limit:
                raise InputTooLargeError(f"input {path} is too large; limit is {limit} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


def read_json_artifact(path: Path) -> dict[str, Any]:
    """Read a bounded JSON object without executing project code."""

    try:
        source = read_bounded_bytes(path, limit=MAX_REPORT_BYTES).decode("utf-8")
        payload = json.loads(
            source,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except ArtifactError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise ArtifactError(f"cannot read artifact {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ArtifactError(f"artifact {path} must contain a JSON object")
    if _depth_exceeds(payload, MAX_JSON_DEPTH):
        raise ArtifactError(f"cannot read artifact {path}: nesting deeper than {MAX_JSON_DEPTH}")
    return payload


MAX_JSON_DEPTH = 200
"""Deeper nesting is rejected on every interpreter; reports nest a few levels."""


def _depth_exceeds(value: Any, limit: int) -> bool:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if depth > limit:
            return True
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return False


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise ArtifactError(f"non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ArtifactError(f"non-finite JSON number: {value}")
    return number


def render_json_artifact(payload: dict[str, Any]) -> str:
    """Render deterministic UTF-8 JSON text."""

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
