from __future__ import annotations

from pathlib import Path

import pytest

from deadtrace.analysis import analyze
from deadtrace.config import Config
from deadtrace.core import AssemblyState
from deadtrace.target_environment import read_target_environment


def test_uv_lock_versions_take_precedence_over_project_requirements(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "target"
version = "0.0.0"
dependencies = ["fastapi==0.100.0", "dishka>=1"]
""",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        """
version = 1
[[package]]
name = "fastapi"
version = "0.141.1"
[[package]]
name = "dishka"
version = "1.10.1"
""",
        encoding="utf-8",
    )

    environment = read_target_environment(tmp_path, {"fastapi", "dishka"})

    assert [(item.name, item.version, item.source) for item in environment.packages] == [
        ("dishka", "1.10.1", "uv.lock"),
        ("fastapi", "0.141.1", "uv.lock"),
    ]
    assert not environment.issues


@pytest.mark.parametrize(
    ("version", "code", "assembly", "reported"),
    [
        ("0.99.1", "DT4001", AssemblyState.PARTIAL, False),
        ("0.100.0", "DT4002", AssemblyState.COMPLETE, True),
    ],
)
def test_pinned_framework_versions_outside_the_supported_range_block_findings(
    tmp_path: Path, version: str, code: str, assembly: AssemblyState, reported: bool
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        f"""
[project]
name = "target"
version = "0.0.0"
dependencies = ["fastapi=={version}"]
""",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def endpoint() -> None:
    pass

def candidate() -> None:
    pass
""",
        encoding="utf-8",
    )

    result = analyze(tmp_path, Config())
    production = result.snapshot.worlds[0]

    assert production.assembly_state is assembly
    assert [item.code for item in result.target_environment.issues] == [code]
    assert any(item.code == code for item in production.limitations)
    assert bool(result.findings) is reported
    assert result.target_environment.packages[0].version == version


def test_unrelated_and_non_exact_dependencies_do_not_claim_versions(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "target"
version = "0.0.0"
dependencies = ["fastapi>=0.100", "other==1.0"]
""",
        encoding="utf-8",
    )

    environment = read_target_environment(tmp_path, {"fastapi"})

    assert not environment.packages
    assert not environment.issues


def test_malformed_or_oversized_metadata_is_ignored_as_unresolved(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("not = [", encoding="utf-8")
    (tmp_path / "uv.lock").write_bytes(b"x" * (16 * 1024 * 1024 + 1))

    environment = read_target_environment(tmp_path, {"fastapi"})

    assert not environment.packages
    assert not environment.issues
