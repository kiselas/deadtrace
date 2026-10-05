from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deadtrace import (
    artifacts,
    case_validator,
    deployment,
    entry_points,
    pytest_semantics,
    target_environment,
)
from deadtrace.artifacts import (
    ArtifactError,
    InputTooLargeError,
    read_bounded_bytes,
    read_json_artifact,
)
from deadtrace.case_validator import CaseValidationError, validate_cases
from deadtrace.cli import app
from deadtrace.pytest_semantics import PytestCollection, read_pytest_collection


@pytest.mark.parametrize(
    "reader", ["json", "entrypoints", "versions", "deployment", "pytest_toml", "pytest_ini", "case"]
)
def test_read_limit_survives_stale_file_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reader: str
) -> None:
    contents = {
        "json": ("report.json", '{"padding":"' + "x" * 100 + '"}'),
        "entrypoints": ("pyproject.toml", '[project.scripts]\nrun="app:main"\n#' + "x" * 100),
        "versions": ("uv.lock", '[[package]]\nname="fastapi"\nversion="0.141.1"\n#' + "x" * 100),
        "deployment": ("Procfile", "web: python -m app\n#" + "x" * 100),
        "pytest_toml": (
            "pyproject.toml",
            '[tool.pytest.ini_options]\npython_files=["special.py"]\n#' + "x" * 100,
        ),
        "pytest_ini": ("pytest.ini", "[pytest]\npython_files=special.py\n#" + "x" * 100),
        "case": ("CASE.toml", 'schema_version=1\ncase_id="case"\ntargets=[]\n#' + "x" * 100),
    }
    name, source = contents[reader]
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    (tmp_path / "CASE.md").write_text("# Case\n", encoding="utf-8")
    original_stat = Path.stat

    def stale_stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        result = original_stat(self, follow_symlinks=follow_symlinks)
        if self == path:
            return os.stat_result((*result[:6], 1, *result[7:]))
        return result

    monkeypatch.setattr(Path, "stat", stale_stat)
    for module in (artifacts, entry_points, target_environment, pytest_semantics, case_validator):
        monkeypatch.setattr(module, "MAX_ARTIFACT_BYTES", 64)
    monkeypatch.setattr(artifacts, "MAX_REPORT_BYTES", 64)
    monkeypatch.setattr(deployment, "MAX_DEPLOYMENT_FILE_BYTES", 64)

    if reader == "json":
        with pytest.raises(ArtifactError, match="limit is 64 bytes"):
            read_json_artifact(path)
    elif reader == "entrypoints":
        entries, issues = entry_points.read_project_entry_points(tmp_path)
        assert entries == ()
        assert [issue.code for issue in issues] == ["DT4101"]
    elif reader == "versions":
        assert target_environment.read_target_environment(tmp_path, {"fastapi"}).packages == ()
    elif reader == "deployment":
        assert deployment.read_deployment_references(tmp_path) == ()
    elif reader.startswith("pytest"):
        assert read_pytest_collection(tmp_path) == PytestCollection()
    else:
        with pytest.raises(CaseValidationError, match="limit is 64 bytes"):
            validate_cases(tmp_path)


@pytest.mark.parametrize(
    "source",
    [
        '{"x":1,"x":2}',
        '{"nested":{"x":1,"x":2}}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        '{"x":1e999}',
        '{"x":' + "[" * 10000 + "0" + "]" * 10000 + "}",
        '{"x":' + "9" * 10000 + "}",
    ],
)
def test_ambiguous_or_unrepresentable_json_is_an_artifact_error(
    tmp_path: Path, source: str
) -> None:
    path = tmp_path / "report.json"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ArtifactError):
        read_json_artifact(path)
    result = CliRunner().invoke(
        app,
        [
            "baseline",
            "create",
            str(path),
            "--output",
            str(tmp_path / "baseline.json"),
            "--reason",
            "review",
        ],
    )
    assert result.exit_code == 2
    assert "baseline error" in result.stderr
    assert not (tmp_path / "baseline.json").exists()


@pytest.mark.parametrize("source", ["tool=1\n", 'tool="invalid"\n', "[tool]\npytest=1\n"])
def test_malformed_pytest_table_does_not_crash(tmp_path: Path, source: str) -> None:
    (tmp_path / "pyproject.toml").write_text(source, encoding="utf-8")

    assert read_pytest_collection(tmp_path) == PytestCollection()


@pytest.mark.parametrize("size", [0, 9, 10, 11])
def test_partial_reads_enforce_the_limit_and_close_the_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    requests: list[int] = []

    class ShortReads(BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            assert size is not None and size > 0
            requests.append(size)
            return super().read(min(size, 3))

    stream = ShortReads(b"x" * size)

    def open_stream(self: Path, mode: str) -> ShortReads:
        assert self == tmp_path / "input"
        assert mode == "rb"
        return stream

    monkeypatch.setattr(Path, "open", open_stream)
    if size > 10:
        with pytest.raises(InputTooLargeError, match="limit is 10 bytes"):
            read_bounded_bytes(tmp_path / "input", limit=10)
    else:
        assert read_bounded_bytes(tmp_path / "input", limit=10) == b"x" * size
    assert stream.closed
    assert all(request <= 11 for request in requests)


def test_json_limit_counts_bytes_and_accepts_distinct_nested_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "report.json"
    source = '{"é":1.5,"nested":{"é":2},"items":[true,null]}'
    path.write_bytes(source.encode("utf-8"))
    monkeypatch.setattr(artifacts, "MAX_REPORT_BYTES", len(source.encode("utf-8")))

    assert read_json_artifact(path) == {"é": 1.5, "nested": {"é": 2}, "items": [True, None]}
    monkeypatch.setattr(artifacts, "MAX_REPORT_BYTES", len(source))
    with pytest.raises(ArtifactError, match="too large"):
        read_json_artifact(path)


def test_invalid_utf8_manifest_is_a_validation_error(tmp_path: Path) -> None:
    (tmp_path / "CASE.md").write_text("# Case\n", encoding="utf-8")
    (tmp_path / "CASE.toml").write_bytes(b"\xff")

    with pytest.raises(CaseValidationError, match="cannot read"):
        validate_cases(tmp_path)


@pytest.mark.parametrize("reader", ["config", "entrypoints", "versions", "pytest", "case"])
def test_parser_recursion_exhaustion_is_a_reader_error(tmp_path: Path, reader: str) -> None:
    from deadtrace.config import ConfigurationError, load_config

    name = "CASE.toml" if reader == "case" else "pyproject.toml"
    path = tmp_path / name
    path.write_text("x=" + "[" * 10000 + "0" + "]" * 10000, encoding="utf-8")
    if reader == "config":
        with pytest.raises(ConfigurationError, match="cannot read"):
            load_config(path)
    elif reader == "entrypoints":
        entries, issues = entry_points.read_project_entry_points(tmp_path)
        assert entries == ()
        assert [issue.code for issue in issues] == ["DT4101"]
    elif reader == "versions":
        assert target_environment.read_target_environment(tmp_path, {"fastapi"}).packages == ()
    elif reader == "pytest":
        assert read_pytest_collection(tmp_path) == PytestCollection()
    else:
        (tmp_path / "CASE.md").write_text("# Case\n", encoding="utf-8")
        with pytest.raises(CaseValidationError, match="cannot read"):
            validate_cases(tmp_path)
