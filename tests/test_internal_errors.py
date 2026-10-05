from __future__ import annotations

from pathlib import Path

import pytest

import deadtrace.cli as cli


def _explode(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("secret-looking message must not be printed")


def _run(monkeypatch: pytest.MonkeyPatch, *argv: str) -> None:
    monkeypatch.setattr("sys.argv", ["deadtrace", *argv])
    monkeypatch.delenv("DEADTRACE_DEBUG", raising=False)
    cli.run()


def test_internal_error_is_one_line_with_exit_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(cli, "analyze", _explode)

    with pytest.raises(SystemExit) as raised:
        _run(monkeypatch, "scan", str(tmp_path))

    err = capsys.readouterr().err
    assert raised.value.code == 2
    assert "DT0001" in err
    assert "RuntimeError" in err
    assert "Traceback" not in err
    assert "secret-looking" not in err
    assert len(err.strip().splitlines()) == 1


def test_debug_flag_shows_the_traceback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(cli, "analyze", _explode)

    with pytest.raises(RuntimeError):
        _run(monkeypatch, "--debug", "scan", str(tmp_path))


def test_debug_environment_variable_shows_the_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(cli, "analyze", _explode)
    monkeypatch.setattr("sys.argv", ["deadtrace", "scan", str(tmp_path)])
    monkeypatch.setenv("DEADTRACE_DEBUG", "1")

    with pytest.raises(RuntimeError):
        cli.run()


def test_operational_errors_keep_their_own_exit_codes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(SystemExit) as raised:
        _run(monkeypatch, "scan", str(tmp_path / "missing"))

    assert raised.value.code == 2


def test_help_documents_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(cli.app, ["--help"])

    assert "DT0001" in result.stdout
