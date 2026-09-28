"""Safe helpers for user-selected JSON artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
"""Largest project input, such as ``pyproject.toml`` or ``uv.lock``, that analysis reads."""
MAX_REPORT_BYTES = 256 * 1024 * 1024
"""Largest Deadtrace report or baseline read back; a 624k-line monorepo writes about 113 MB."""


class ArtifactError(ValueError):
    """Raised when a report-like artifact is missing, oversized, or malformed."""


def read_json_artifact(path: Path) -> dict[str, Any]:
    """Read a bounded JSON object without executing project code."""

    try:
        size = path.stat().st_size
        if size > MAX_REPORT_BYTES:
            raise ArtifactError(
                f"artifact {path} is {size} bytes; limit is {MAX_REPORT_BYTES} bytes"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ArtifactError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArtifactError(f"cannot read artifact {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ArtifactError(f"artifact {path} must contain a JSON object")
    return payload


def render_json_artifact(payload: dict[str, Any]) -> str:
    """Render deterministic UTF-8 JSON text."""

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
