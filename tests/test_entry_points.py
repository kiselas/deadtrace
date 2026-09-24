from __future__ import annotations

from pathlib import Path

from deadtrace.analysis import analyze
from deadtrace.config import Config, WorldConfig
from deadtrace.core import AssemblyState
from deadtrace.entry_points import read_project_entry_points
from deadtrace.semantic_report import semantic_report_dict


def test_pep621_script_becomes_a_provenanced_execution_world(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "entry-project"
version = "0.0.0"

[project.scripts]
entry-project = "acme.cli:main"
""",
        encoding="utf-8",
    )
    source = tmp_path / "src" / "acme" / "cli.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
def helper() -> None:
    pass

def main() -> None:
    helper()

def candidate() -> None:
    pass
""",
        encoding="utf-8",
    )

    result = analyze(tmp_path, Config())
    report = semantic_report_dict(result)

    assert result.complete
    assert [world.id.key for world in result.snapshot.worlds] == [
        "production:entrypoint:console_scripts:entry-project"
    ]
    assert [finding.code for finding in result.findings] == ["RCH001"]
    assert result.findings[0].members[0].qualified_name == "candidate"
    provenance = report["worlds"][0]["root_provenance"]
    assert provenance
    assert {item["kind"] for item in provenance} == {"project_entry_point"}
    assert {item["detail"] for item in provenance} == {
        "pyproject.toml console_scripts:entry-project"
    }


def test_static_entry_point_reader_supports_groups_and_ignores_legacy_extras(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "plugins"
version = "0.0.0"

[project.gui-scripts]
desktop = "acme.ui:start [gui]"

[project.entry-points."acme.plugins"]
worker = "acme.worker"
broken = 42
""",
        encoding="utf-8",
    )

    entries, issues = read_project_entry_points(tmp_path)

    assert [(item.group, item.name, item.target) for item in entries] == [
        ("acme.plugins", "worker", "acme.worker"),
        ("gui_scripts", "desktop", "acme.ui:start"),
    ]
    assert [issue.code for issue in issues] == ["DT4101"]


def test_dynamic_entry_points_limit_auto_discovery_but_explicit_world_wins(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "dynamic-project"
version = "0.0.0"
dynamic = ["scripts"]
dependencies = ["fastapi==0.141.1"]
""",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI
app = FastAPI()

def candidate() -> None:
    pass
""",
        encoding="utf-8",
    )

    automatic = analyze(tmp_path, Config())
    explicit = analyze(
        tmp_path,
        Config(
            worlds=(
                WorldConfig(
                    "production",
                    "web",
                    ("main:app",),
                    ("python", "fastapi"),
                ),
            )
        ),
    )

    assert automatic.snapshot.worlds[0].assembly_state is AssemblyState.PARTIAL
    assert any(
        limitation.code == "DT4102" for limitation in automatic.snapshot.worlds[0].limitations
    )
    assert not automatic.findings
    assert explicit.snapshot.worlds[0].assembly_state is AssemblyState.COMPLETE
    assert [finding.code for finding in explicit.findings] == ["RCH001"]
