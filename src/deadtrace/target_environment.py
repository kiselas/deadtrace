"""Read target dependency versions as data without importing the target."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from deadtrace.artifacts import MAX_ARTIFACT_BYTES, InputTooLargeError, read_bounded_bytes

_SUPPORTED_EXACT = {
    "fastapi": frozenset({Version("0.141.1")}),
    "dishka": frozenset({Version("1.10.1")}),
}
"""Versions the runtime oracle executes the reference application with."""
_SUPPORTED_RANGES = {
    "fastapi": SpecifierSet(">=0.100,<1"),
    "dishka": SpecifierSet(">=1.0,<2"),
}
"""Versions whose behavior for the modeled subset is the oracle-tested one (ADR-0018): FastAPI
applications, routers, ``include_router``, ``Depends``, lifespan, and background tasks since
Pydantic 2 support; Dishka 1 providers, ``FromDishka``, ``@inject``, and ``setup_dishka``. A
version outside the range weakens the analysis; an untested one inside it is only reported."""
UNTESTED_VERSION = "DT4002"


@dataclass(frozen=True, slots=True)
class TargetPackage:
    name: str
    version: str
    source: str


@dataclass(frozen=True, slots=True)
class CompatibilityIssue:
    code: str
    package: str
    version: str
    message: str


@dataclass(frozen=True, slots=True)
class TargetEnvironment:
    packages: tuple[TargetPackage, ...]
    issues: tuple[CompatibilityIssue, ...]
    digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "packages": [
                {"name": item.name, "version": item.version, "source": item.source}
                for item in self.packages
            ],
            "issues": [
                {
                    "code": item.code,
                    "package": item.package,
                    "version": item.version,
                    "message": item.message,
                }
                for item in self.issues
            ],
            "digest": self.digest,
        }


def read_target_environment(root: Path, imported_packages: set[str]) -> TargetEnvironment:
    """Read exact versions from uv.lock, then exact project requirements."""

    versions = _versions_from_uv_lock(root / "uv.lock")
    for name, version in _versions_from_pyproject(root / "pyproject.toml").items():
        versions.setdefault(name, version)
    packages = tuple(
        TargetPackage(name, str(version), source)
        for name, (version, source) in sorted(versions.items())
        if name in imported_packages
    )
    issues = tuple(
        issue
        for package in packages
        if package.name in _SUPPORTED_EXACT
        if (issue := _compatibility_issue(package)) is not None
    )
    canonical = "\n".join(f"{item.name}=={item.version}@{item.source}" for item in packages)
    return TargetEnvironment(packages, issues, sha256(canonical.encode()).hexdigest())


def _compatibility_issue(package: TargetPackage) -> CompatibilityIssue | None:
    try:
        version = Version(package.version)
    except InvalidVersion:
        return CompatibilityIssue(
            code="DT4001",
            package=package.name,
            version=package.version,
            message=f"cannot interpret {package.name} version {package.version!r}; "
            "dependency compatibility is unknown",
        )
    if version in _SUPPORTED_EXACT[package.name]:
        return None
    tested = ", ".join(str(item) for item in sorted(_SUPPORTED_EXACT[package.name]))
    supported = _SUPPORTED_RANGES[package.name]
    if version in supported:
        return CompatibilityIssue(
            code=UNTESTED_VERSION,
            package=package.name,
            version=package.version,
            message=(
                f"{package.name} {package.version} is in the supported range {supported} but "
                f"not in the oracle-tested set: {tested}"
            ),
        )
    return CompatibilityIssue(
        code="DT4001",
        package=package.name,
        version=package.version,
        message=(
            f"{package.name} {package.version} is outside the supported range {supported}; "
            f"the oracle-tested set is {tested}"
        ),
    )


def _versions_from_uv_lock(path: Path) -> dict[str, tuple[str, str]]:
    document = _read_toml(path)
    if document is None:
        return {}
    packages = document.get("package", [])
    if not isinstance(packages, list):
        return {}
    result: dict[str, tuple[str, str]] = {}
    for package in packages:
        if not isinstance(package, dict):
            continue
        name = package.get("name")
        version = package.get("version")
        if isinstance(name, str) and isinstance(version, str):
            result[_canonical_name(name)] = (_normalized_version(version), "uv.lock")
    return result


def _versions_from_pyproject(path: Path) -> dict[str, tuple[str, str]]:
    document = _read_toml(path)
    if document is None:
        return {}
    project = document.get("project", {})
    if not isinstance(project, dict):
        return {}
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list):
        return {}
    result: dict[str, tuple[str, str]] = {}
    for dependency in dependencies:
        if not isinstance(dependency, str):
            continue
        try:
            requirement = Requirement(dependency)
        except InvalidRequirement:
            continue
        exact = [item.version for item in requirement.specifier if item.operator in {"==", "==="}]
        if len(exact) == 1 and "*" not in exact[0]:
            result[_canonical_name(requirement.name)] = (
                _normalized_version(exact[0]),
                "pyproject.toml",
            )
    return result


def _normalized_version(value: str) -> str:
    try:
        return str(Version(value))
    except InvalidVersion:
        return value


def _read_toml(path: Path) -> dict[str, object] | None:
    try:
        if not path.is_file():
            return None
        document = tomllib.loads(read_bounded_bytes(path, limit=MAX_ARTIFACT_BYTES).decode("utf-8"))
    except (OSError, UnicodeError, InputTooLargeError, RecursionError, tomllib.TOMLDecodeError):
        return None
    return document


def _canonical_name(name: str) -> str:
    return name.lower().replace("_", "-")
