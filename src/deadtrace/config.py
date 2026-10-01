"""Strict configuration loading for ``[tool.deadtrace]``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deadtrace.artifacts import MAX_ARTIFACT_BYTES


class ConfigurationError(ValueError):
    """Raised when Deadtrace configuration is invalid or ambiguous."""


@dataclass(frozen=True, slots=True)
class WorldConfig:
    profile: str
    scenario: str
    roots: tuple[str, ...]
    frameworks: tuple[str, ...] = ("python", "fastapi", "dishka")


@dataclass(frozen=True, slots=True)
class KeepConfig:
    target: str
    reason: str
    profiles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Config:
    report_exclude: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    """Glob patterns of files that are not source: data the project never runs."""
    worlds: tuple[WorldConfig, ...] = ()
    keep: tuple[KeepConfig, ...] = ()
    max_steps: int | None = None
    """Solver step budget per world; ``None`` sizes it from the graph."""
    require_complete: bool = False


_KNOWN_KEYS = frozenset(
    {"exclude", "report-exclude", "worlds", "keep", "max-steps", "require-complete"}
)
KNOWN_FRAMEWORKS = frozenset(
    {
        "aiohttp",
        "arq",
        "bottle",
        "celery",
        "django",
        "dishka",
        "falcon",
        "fastapi",
        "faststream",
        "flask",
        "litestar",
        "pydantic",
        "pytest",
        "python",
        "quart",
        "sanic",
        "starlette",
        "taskiq",
        "typer",
    }
)
"""Names a world may list in ``frameworks``. The list is declarative (ADR-0014): every capability
applies to every world, because switching one off could only remove protection. Unknown names are
rejected so that a typo does not pass silently."""


def discover_config(scan_path: Path, explicit: Path | None) -> Path | None:
    """Return an explicit config or the pyproject at the scan root, if present."""

    if explicit is not None:
        return explicit
    base = scan_path if scan_path.is_dir() else scan_path.parent
    candidate = base / "pyproject.toml"
    return candidate if candidate.is_file() else None


def load_config(path: Path | None) -> Config:
    """Load config without accepting misspelled or future-only options."""

    if path is None:
        return Config()
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_ARTIFACT_BYTES + 1)
        if len(data) > MAX_ARTIFACT_BYTES:
            raise ConfigurationError(
                f"configuration {path} is too large; limit is {MAX_ARTIFACT_BYTES} bytes"
            )
        document = tomllib.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(f"cannot read configuration {path}: {error}") from error

    section = _deadtrace_section(document, path)
    unknown = sorted(set(section) - _KNOWN_KEYS)
    if unknown:
        names = ", ".join(unknown)
        raise ConfigurationError(f"unknown [tool.deadtrace] option(s): {names}")

    raw_excludes = _string_array(section, "report-exclude")
    source_excludes = _string_array(section, "exclude")
    worlds = _worlds(section.get("worlds", []))
    keeps = _keeps(section.get("keep", []))
    max_steps = section.get("max-steps")
    if max_steps is not None and (
        not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 1
    ):
        raise ConfigurationError("[tool.deadtrace].max-steps must be a positive integer")
    require_complete = section.get("require-complete", False)
    if not isinstance(require_complete, bool):
        raise ConfigurationError("[tool.deadtrace].require-complete must be a boolean")
    return Config(
        report_exclude=raw_excludes,
        exclude=source_excludes,
        worlds=worlds,
        keep=keeps,
        max_steps=max_steps,
        require_complete=require_complete,
    )


def _deadtrace_section(document: dict[str, Any], path: Path) -> dict[str, Any]:
    tool = document.get("tool", {})
    if not isinstance(tool, dict):
        raise ConfigurationError(f"[tool] must be a table in {path}")
    section = tool.get("deadtrace", {})
    if not isinstance(section, dict):
        raise ConfigurationError(f"[tool.deadtrace] must be a table in {path}")
    return section


def _string_array(section: dict[str, Any], key: str) -> tuple[str, ...]:
    value = section.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigurationError(f"[tool.deadtrace].{key} must be an array of strings")
    return tuple(value)


def _worlds(value: object) -> tuple[WorldConfig, ...]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ConfigurationError("[tool.deadtrace].worlds must be an array of tables")
    worlds: list[WorldConfig] = []
    identities: set[tuple[str, str]] = set()
    for raw in value:
        assert isinstance(raw, dict)
        unknown = sorted(set(raw) - {"profile", "scenario", "roots", "frameworks"})
        if unknown:
            raise ConfigurationError(f"unknown world option(s): {', '.join(unknown)}")
        profile = _non_empty_string(raw, "profile", "world")
        scenario = _non_empty_string(raw, "scenario", "world")
        roots = _required_string_array(raw, "roots", "world")
        raw_frameworks = raw.get("frameworks", ["python", "fastapi", "dishka"])
        if (
            not isinstance(raw_frameworks, list)
            or not raw_frameworks
            or not all(isinstance(item, str) for item in raw_frameworks)
        ):
            raise ConfigurationError("world.frameworks must be a non-empty array of strings")
        frameworks = tuple(raw_frameworks)
        unsupported = sorted(set(frameworks) - KNOWN_FRAMEWORKS)
        if unsupported:
            raise ConfigurationError(f"unknown framework capability: {', '.join(unsupported)}")
        identity = (profile, scenario)
        if identity == ("production", "migrations"):
            raise ConfigurationError(
                "world production:migrations is reserved for the migrations of the project"
            )
        if identity in identities:
            raise ConfigurationError(f"duplicate world {profile}:{scenario}")
        identities.add(identity)
        worlds.append(WorldConfig(profile, scenario, roots, frameworks))
    return tuple(worlds)


def _keeps(value: object) -> tuple[KeepConfig, ...]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ConfigurationError("[tool.deadtrace].keep must be an array of tables")
    keeps: list[KeepConfig] = []
    for raw in value:
        assert isinstance(raw, dict)
        unknown = sorted(set(raw) - {"target", "reason", "profiles"})
        if unknown:
            raise ConfigurationError(f"unknown keep option(s): {', '.join(unknown)}")
        target = _non_empty_string(raw, "target", "keep")
        reason = _non_empty_string(raw, "reason", "keep")
        profiles = _required_string_array(raw, "profiles", "keep")
        keeps.append(KeepConfig(target, reason, profiles))
    return tuple(keeps)


def _non_empty_string(value: dict[str, Any], key: str, context: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ConfigurationError(f"{context}.{key} must be a non-empty string")
    return item


def _required_string_array(value: dict[str, Any], key: str, context: str) -> tuple[str, ...]:
    item = value.get(key)
    if not isinstance(item, list) or not item or not all(isinstance(part, str) for part in item):
        raise ConfigurationError(f"{context}.{key} must be a non-empty array of strings")
    return tuple(item)
