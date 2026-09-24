"""Copy the Python sources of installed packages into separate benchmark projects.

The packages come from the locked development environment, so their versions are fixed by
``uv.lock``. Files are copied as bytes; nothing is imported or executed. Each package becomes its
own scan root, ``OUTPUT/<package>/<package>/...``, and the versions are printed for the results
note:

    uv run python benchmarks/stage_installed_sources.py .benchmark-work/real

Real third-party code has no configured application roots, so these scans measure collection and
the Python frontend on realistic code, not findings.
"""

from __future__ import annotations

import argparse
import shutil
import sysconfig
from importlib.metadata import packages_distributions, version
from pathlib import Path

DEFAULT_PACKAGES = ("rich", "_pytest", "pydantic", "pygments", "mypy")


def stage(output: Path, packages: tuple[str, ...]) -> dict[str, tuple[str, int, int]]:
    """Return ``package -> (distribution version, files, lines)`` for every staged package."""

    site_packages = Path(sysconfig.get_paths()["purelib"])
    distributions = packages_distributions()
    staged: dict[str, tuple[str, int, int]] = {}
    for package in packages:
        source_root = site_packages / package
        if not source_root.is_dir():
            raise SystemExit(f"package directory not found: {package}")
        target_root = output / package / package
        if target_root.exists():
            shutil.rmtree(target_root)
        files = lines = 0
        for source in sorted(source_root.rglob("*.py")):
            if "__pycache__" in source.parts:
                continue
            target = target_root / source.relative_to(source_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            target.write_bytes(data)
            files += 1
            lines += data.count(b"\n")
        distribution = distributions.get(package, [package])[0]
        staged[package] = (f"{distribution} {version(distribution)}", files, lines)
    return staged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("packages", nargs="*", default=list(DEFAULT_PACKAGES))
    arguments = parser.parse_args()
    for package, (release, files, lines) in stage(
        arguments.output, tuple(arguments.packages)
    ).items():
        print(f"{package}: {release}, {files} files, {lines} lines")


if __name__ == "__main__":
    main()
