from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deadtrace import config
from deadtrace.analysis import analyze
from deadtrace.cli import app
from deadtrace.config import Config, ConfigurationError, load_config
from deadtrace.entry_points import read_project_entry_points
from deadtrace.scanner import scan
from deadtrace.target_environment import read_target_environment


@pytest.mark.parametrize("encoding", ["base64_codec", "hex_codec", "undefined"])
def test_non_text_source_encoding_is_an_input_issue(tmp_path: Path, encoding: str) -> None:
    (tmp_path / "bad.py").write_bytes(f"# coding: {encoding}\ndef bad(): pass\n".encode())
    (tmp_path / "good.py").write_text("def good(): pass\n", encoding="utf-8")

    report = scan(tmp_path, Config())

    assert [item.qualified_name for item in report.definitions] == ["good"]
    assert [(issue.path, issue.code) for issue in report.issues] == [("bad.py", "DT1001")]


@pytest.mark.parametrize("blocked_name", [".", "blocked"])
def test_directory_read_errors_cannot_produce_a_complete_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blocked_name: str
) -> None:
    blocked = tmp_path / blocked_name
    blocked.mkdir(exist_ok=True)
    (blocked / "hidden.py").write_text("def hidden(): pass\n", encoding="utf-8")
    (tmp_path / "main.py").write_text(
        "def candidate(): pass\nif __name__ == '__main__': pass\n", encoding="utf-8"
    )
    original_scandir = os.scandir

    def deny_directory(path: str | Path) -> AbstractContextManager[Iterator[os.DirEntry[str]]]:
        if Path(path) == blocked:
            raise PermissionError(13, "access denied", str(blocked))
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", deny_directory)

    report = scan(tmp_path, Config())
    result = analyze(tmp_path, Config())

    assert report.has_errors
    assert [(issue.path, issue.code) for issue in report.issues] == [(blocked_name, "DT1001")]
    assert not result.complete
    assert result.has_operational_errors
    assert result.findings == ()
    if blocked_name != ".":
        assert [item.qualified_name for item in report.definitions] == ["candidate"]
    cli = CliRunner().invoke(app, ["scan", str(tmp_path), "--inventory-only", "--format", "json"])
    assert cli.exit_code == 2
    assert "DT1001" in cli.stderr


def test_invalid_utf8_configuration_uses_a_configuration_error(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_bytes(b"[tool.deadtrace]\n# \xff\n")

    with pytest.raises(ConfigurationError, match="cannot read configuration"):
        load_config(path)
    result = CliRunner().invoke(app, ["scan", str(tmp_path), "--inventory-only"])
    assert result.exit_code == 2
    assert "configuration error" in result.stderr


def test_discovery_error_recovery_retries_the_whole_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "target.py").write_text("def target(): pass\n", encoding="utf-8")
    original_scandir = os.scandir
    failed = False

    def deny_once(path: str | Path) -> AbstractContextManager[Iterator[os.DirEntry[str]]]:
        nonlocal failed
        if Path(path) == tmp_path and not failed:
            failed = True
            raise PermissionError(13, "access denied", str(tmp_path))
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", deny_once)

    report = scan(tmp_path, Config())

    assert report.issues == ()
    assert report.files == ("target.py",)
    assert [item.qualified_name for item in report.definitions] == ["target"]


def test_configuration_read_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "MAX_ARTIFACT_BYTES", 32)
    path = tmp_path / "pyproject.toml"
    path.write_bytes(b"#" + b"x" * 32)

    with pytest.raises(ConfigurationError, match="limit is 32 bytes"):
        load_config(path)
    path.write_bytes(b"#" + b"x" * 31)
    assert load_config(path) == Config()


def test_invalid_utf8_metadata_uses_existing_malformed_input_policy(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_bytes(b"\xff")
    (tmp_path / "uv.lock").write_bytes(b"\xff")

    entries, issues = read_project_entry_points(tmp_path)
    environment = read_target_environment(tmp_path, {"fastapi"})

    assert entries == ()
    assert [issue.code for issue in issues] == ["DT4101"]
    assert environment.packages == ()


@pytest.mark.parametrize("metadata", ["uv.lock", "pyproject.toml"])
def test_invalid_framework_version_guards_findings(tmp_path: Path, metadata: str) -> None:
    content = (
        '[[package]]\nname="fastapi"\nversion="oops"\n'
        if metadata == "uv.lock"
        else '[project]\ndependencies=["fastapi===oops"]\n'
    )
    (tmp_path / metadata).write_text(content, encoding="utf-8")
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\ndef candidate(): pass\n", encoding="utf-8"
    )

    result = analyze(tmp_path, Config())

    assert not result.complete
    assert result.findings == ()
    assert [(issue.code, issue.version) for issue in result.target_environment.issues] == [
        ("DT4001", "oops")
    ]
    cli = CliRunner().invoke(app, ["scan", str(tmp_path), "--require-complete"])
    assert cli.exit_code == 2


def test_invalid_unmodeled_version_does_not_claim_framework_compatibility(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname="custom"\nversion="oops"\n', encoding="utf-8"
    )

    environment = read_target_environment(tmp_path, {"custom"})

    assert [(package.name, package.version) for package in environment.packages] == [
        ("custom", "oops")
    ]
    assert environment.issues == ()
