from __future__ import annotations

from pathlib import Path

import pytest

from deadtrace.analysis import analyze
from deadtrace.config import (
    KNOWN_FRAMEWORKS,
    Config,
    ConfigurationError,
    discover_config,
    load_config,
)
from deadtrace.frameworks import APPLICATION_CONSTRUCTORS
from deadtrace.semantic_report import render_semantic_text


def test_no_config_uses_defaults() -> None:
    assert load_config(None).report_exclude == ()


def test_unknown_config_key_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.deadtrace]\nfuture-option = true\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="future-option"):
        load_config(config)


def test_report_exclude_requires_strings(tmp_path: Path) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text("[tool.deadtrace]\nreport-exclude = [1]\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="array of strings"):
        load_config(config)


def test_config_discovery_is_limited_to_scan_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    expected = project / "pyproject.toml"
    expected.write_text("[tool.deadtrace]\n", encoding="utf-8")

    assert discover_config(project, None) == expected
    assert discover_config(project / "missing.py", None) == expected


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("[tool.deadtrace\n", "cannot read configuration"),
        ("tool = 1\n", "[tool] must be a table"),
        ("[tool]\ndeadtrace = 1\n", "[tool.deadtrace] must be a table"),
    ],
)
def test_malformed_configuration_is_rejected(tmp_path: Path, contents: str, message: str) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message.replace("[", r"\[")):
        load_config(config)


def test_explicit_config_wins(tmp_path: Path) -> None:
    explicit = tmp_path / "custom.toml"
    assert discover_config(tmp_path, explicit) == explicit


def test_world_and_keep_configuration(tmp_path: Path) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.deadtrace]
max-steps = 42
require-complete = true
report-exclude = ["generated/**"]

[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = ["app.main:app"]
frameworks = ["python", "fastapi", "dishka", "pydantic"]

[[tool.deadtrace.keep]]
target = "app.hooks:external_hook"
reason = "loaded by a deployment platform"
profiles = ["production"]
""",
        encoding="utf-8",
    )

    loaded = load_config(config)

    assert loaded.max_steps == 42
    assert loaded.require_complete
    assert loaded.report_exclude == ("generated/**",)
    assert loaded.worlds[0].roots == ("app.main:app",)
    assert loaded.keep[0].reason == "loaded by a deployment platform"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("max-steps = 0", "max-steps"),
        ("max-steps = true", "max-steps"),
        ('max-steps = "many"', "max-steps"),
        ('require-complete = "yes"', "require-complete"),
        ('worlds = "bad"', "worlds"),
        ('keep = "bad"', "keep"),
    ],
)
def test_invalid_top_level_semantic_configuration(tmp_path: Path, body: str, message: str) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(f"[tool.deadtrace]\n{body}\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message):
        load_config(config)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = ["main:app"]
surprise = true
""",
            "unknown world option",
        ),
        (
            """
[[tool.deadtrace.worlds]]
profile = ""
scenario = "web"
roots = ["main:app"]
""",
            "world.profile",
        ),
        (
            """
[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = []
""",
            "world.roots",
        ),
        (
            """
[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = ["main:app"]
frameworks = "fastapi"
""",
            "world.frameworks",
        ),
        (
            """
[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = ["main:app"]
frameworks = ["quantum-web"]
""",
            "unknown framework capability",
        ),
        (
            """
[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = ["main:app"]

[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = ["main:other"]
""",
            "duplicate world",
        ),
        (
            """
[[tool.deadtrace.worlds]]
profile = "production"
scenario = "migrations"
roots = ["main:app"]
""",
            "reserved",
        ),
    ],
)
def test_invalid_world_configuration(tmp_path: Path, body: str, message: str) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(body, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message.replace(".", r"\.")):
        load_config(config)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
[[tool.deadtrace.keep]]
target = "main:hook"
reason = "external"
profiles = ["production"]
extra = true
""",
            "unknown keep option",
        ),
        (
            """
[[tool.deadtrace.keep]]
target = ""
reason = "external"
profiles = ["production"]
""",
            "keep.target",
        ),
        (
            """
[[tool.deadtrace.keep]]
target = "main:hook"
reason = "external"
profiles = []
""",
            "keep.profiles",
        ),
    ],
)
def test_invalid_keep_configuration(tmp_path: Path, body: str, message: str) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(body, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message.replace(".", r"\.")):
        load_config(config)


def test_every_modeled_framework_can_be_listed_by_a_world(tmp_path: Path) -> None:
    names = sorted({"django", "python", *APPLICATION_CONSTRUCTORS.values()})
    listed = ", ".join(f'"{name}"' for name in names)
    path = tmp_path / "pyproject.toml"
    path.write_text(
        "[[tool.deadtrace.worlds]]\n"
        'profile = "production"\n'
        'scenario = "all"\n'
        'roots = ["main:app"]\n'
        f"frameworks = [{listed}]\n",
        encoding="utf-8",
    )

    assert load_config(path).worlds[0].frameworks == tuple(names)
    assert set(names) <= KNOWN_FRAMEWORKS


def test_exclude_removes_data_directories_from_the_source_universe(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.deadtrace]\nexclude = ["corpus/**", "*.generated.py"]\n', encoding="utf-8"
    )
    for name in ("app.py", "corpus/case/main.py", "schema.generated.py"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("def f() -> None:\n    pass\n", encoding="utf-8")

    config = load_config(discover_config(tmp_path, None))
    result = analyze(tmp_path, config)

    assert config.exclude == ("corpus/**", "*.generated.py")
    assert result.collection.files == ("app.py",)
    assert result.collection.excluded_files == ("corpus/case/main.py", "schema.generated.py")
    assert "Excluded by configuration: 2 files" in render_semantic_text(result)


def test_an_unused_exclude_keeps_the_configuration_digest(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")

    assert (
        analyze(tmp_path, Config()).config_digest
        == analyze(tmp_path, Config(exclude=())).config_digest
    )
    assert (
        analyze(tmp_path, Config()).config_digest
        != analyze(tmp_path, Config(exclude=("x/**",))).config_digest
    )
