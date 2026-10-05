"""Hostile project inputs end in a report or a diagnostic, never an unhandled exception."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deadtrace.cli import app

runner = CliRunner()
Build = Callable[[Path], Path]


def _file(name: str, data: bytes) -> Build:
    def build(root: Path) -> Path:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
        return root

    return build


def _single_file(root: Path) -> Path:
    target = root / "only.py"
    target.write_text("def f():\n    pass\n", encoding="utf-8")
    return target


CASES: dict[str, Build] = {
    "deep-nesting": _file("deep.py", b"x = " + b"(" * 5000 + b"1" + b")" * 5000 + b"\n"),
    "deep-binary-chain": _file("chain.py", b"x = " + b" + ".join([b"1"] * 20000) + b"\n"),
    "deep-but-parseable-chain": _file("c2.py", b"x = " + b" + ".join([b"1"] * 900) + b"\n"),
    "deep-but-parseable-calls": _file("c3.py", b"x = " + b"f(" * 90 + b"1" + b")" * 90 + b"\n"),
    "deep-attribute-chain": _file("c4.py", b"x = a" + b".b" * 3000 + b"\n"),
    "deep-if-elif": _file(
        "c5.py", b"if a:\n    pass\n" + b"".join(b"elif a%d:\n    pass\n" % i for i in range(900))
    ),
    "very-long-line": _file("long.py", b"x = '" + b"a" * 2_000_000 + b"'\n"),
    "bom": _file("bom.py", b"\xef\xbb\xbfdef f():\n    pass\n"),
    "nul-byte": _file("nul.py", b"def f():\n    pass\n\x00\n"),
    "invalid-utf8": _file("bad.py", b"def f():\n    x = '\xff\xfe'\n"),
    "unknown-cookie": _file("cookie.py", b"# -*- coding: nonesuch -*-\nx = 1\n"),
    "empty-project": lambda root: root,
    "empty-file": _file("empty.py", b""),
    "only-comments": _file("c.py", b"# nothing\n"),
    "broken-pyproject": _file("pyproject.toml", b"[tool.deadtrace\nx ="),
    "pyproject-wrong-types": _file("pyproject.toml", b"[project]\nname = 1\ndependencies = 5\n"),
    "bad-uv-lock": _file("uv.lock", b"version = 1\n[[package]]\nname = 1\nversion = []\n"),
    "bad-poetry-lock": _file("poetry.lock", b"[[package]]\nname = 'fastapi'\nversion = 'x.y'\n"),
    "bad-requirements": _file("requirements.txt", b"fastapi===oops\n-r\n\x00\n"),
    "bad-pipfile-lock": _file("Pipfile.lock", b"{not json"),
    "binary-compose": _file("docker-compose.yml", b"\x00\x01\x02"),
    "binary-dockerfile": _file("Dockerfile", b"\xff\xfe\x00"),
    "bad-procfile": _file("Procfile", b"web:\n: :\n"),
    "huge-shell-script": _file("run.sh", b"python " + b"a" * 1_000_000 + b"\n"),
    "bad-setup-cfg": _file("setup.cfg", b"[options.entry_points\nx"),
    "bad-pytest-ini": _file("pytest.ini", b"[pytest\naddopts = -p"),
    "directory-named-py": lambda root: _directory_named_py(root),
    "nonascii-path": _file("модуль/файл.py", b"def f():\n    pass\n"),
    "star-import-cycle": lambda root: _cycle(root),
}


def _directory_named_py(root: Path) -> Path:
    (root / "pkg.py").mkdir()
    return root


def _cycle(root: Path) -> Path:
    (root / "a.py").write_text("from b import *\n", encoding="utf-8")
    (root / "b.py").write_text("from a import *\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("name", sorted(CASES))
def test_scan_never_raises(name: str, tmp_path: Path) -> None:
    target = CASES[name](tmp_path)

    result = runner.invoke(app, ["scan", str(target)])

    assert result.exit_code in (0, 1, 2), result.output
    assert not isinstance(result.exception, Exception) or isinstance(
        result.exception, SystemExit
    ), repr(result.exception)


@pytest.mark.parametrize("command", ["doctor", "support-bundle"])
@pytest.mark.parametrize("name", ["deep-nesting", "nul-byte", "broken-pyproject", "bad-uv-lock"])
def test_other_commands_never_raise(name: str, command: str, tmp_path: Path) -> None:
    target = CASES[name](tmp_path)

    result = runner.invoke(app, [command, str(target)])

    assert result.exit_code in (0, 1, 2), result.output
    assert not isinstance(result.exception, Exception) or isinstance(result.exception, SystemExit)


def test_scan_of_a_single_file_does_not_raise(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(_single_file(tmp_path))])

    assert result.exit_code in (0, 1, 2)
    assert not isinstance(result.exception, Exception) or isinstance(result.exception, SystemExit)


def test_missing_path_is_an_operational_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(tmp_path / "absent")])

    assert result.exit_code == 2


def test_source_file_over_the_input_limit_is_skipped_with_dt1001(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("def f():\n    pass\n", encoding="utf-8")
    with (tmp_path / "huge.py").open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)

    result = runner.invoke(app, ["scan", str(tmp_path), "--format", "json"])

    assert result.exit_code == 2
    assert "huge.py" in result.stderr
    assert "DT1001" in result.stderr
    assert "too large" in result.stderr
