from __future__ import annotations

from pathlib import Path

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


def test_explicit_untested_framework_version_blocks_negative_findings(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "target"
version = "0.0.0"
dependencies = ["fastapi==0.100.0"]
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

    assert production.assembly_state is AssemblyState.PARTIAL
    assert any(item.code == "DT4001" for item in production.limitations)
    assert not result.findings
    assert result.target_environment.packages[0].version == "0.100.0"


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
