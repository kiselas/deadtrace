"""Deadtrace public package metadata."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("deadtrace")
except PackageNotFoundError:  # pragma: no cover - source-tree fallback
    __version__ = "0.1.0a2"

__all__ = ["__version__"]
