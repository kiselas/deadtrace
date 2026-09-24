from __future__ import annotations

import socket
from pathlib import Path

import pytest

from deadtrace import scanner
from deadtrace.config import Config
from deadtrace.inventory import inventory_source
from deadtrace.scanner import collect_sources, scan


def test_nested_definitions_have_owner_and_occurrence() -> None:
    definitions = inventory_source(
        """
class Service:
    def run(self):
        def helper():
            return 1
        return helper()

def duplicate():
    return 1

def duplicate():
    return 2
""".lstrip(),
        path="app.py",
    )

    by_name = [(item.qualified_name, item.owner, item.occurrence) for item in definitions]
    assert by_name == [
        ("Service", None, 0),
        ("Service.run", "Service", 0),
        ("Service.run.helper", "Service.run", 0),
        ("duplicate", None, 0),
        ("duplicate", None, 1),
    ]


def test_unicode_and_crlf_have_stable_spans(tmp_path: Path) -> None:
    target = tmp_path / "unicode_target.py"
    target.write_bytes("# café\r\ndef привет():\r\n    return 'мир'\r\n".encode())

    report = scan(tmp_path, Config())

    assert report.issues == ()
    assert report.definitions[0].qualified_name == "привет"
    assert report.definitions[0].span.start_line == 2


def test_scan_is_deterministic_and_does_not_execute_or_write(tmp_path: Path) -> None:
    target = tmp_path / "dangerous.py"
    contents = b"raise RuntimeError('must not execute')\n\ndef declared():\n    return 1\n"
    target.write_bytes(contents)
    before = target.stat().st_mtime_ns

    first = scan(tmp_path, Config())
    second = scan(tmp_path, Config())

    assert first == second
    assert target.read_bytes() == contents
    assert target.stat().st_mtime_ns == before
    assert first.definitions[0].qualified_name == "declared"


def test_scan_does_not_open_network_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "target.py").write_text("def target():\n    pass\n", encoding="utf-8")

    def forbidden_socket(*args: object, **kwargs: object) -> socket.socket:
        del args, kwargs
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    report = scan(tmp_path, Config())
    assert not report.has_errors


def test_report_exclude_marks_but_does_not_remove_inventory(tmp_path: Path) -> None:
    (tmp_path / "visible.py").write_text("def visible():\n    pass\n", encoding="utf-8")
    (tmp_path / "hidden.py").write_text("def hidden():\n    pass\n", encoding="utf-8")

    unfiltered = scan(tmp_path, Config())
    filtered = scan(tmp_path, Config(report_exclude=("hidden.py",)))

    assert [item.identity() for item in unfiltered.definitions] == [
        item.identity() for item in filtered.definitions
    ]
    assert [item.report_excluded for item in filtered.definitions] == [True, False]


def test_syntax_error_is_reported_without_losing_valid_files(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "valid.py").write_text("def valid():\n    pass\n", encoding="utf-8")

    report = scan(tmp_path, Config())

    assert [item.qualified_name for item in report.definitions] == ["valid"]
    assert len(report.issues) == 1
    assert report.issues[0].code == "DT1001"
    assert report.issues[0].path == "broken.py"


@pytest.mark.parametrize("name", ["missing", "notes.txt"])
def test_invalid_scan_path_is_reported(tmp_path: Path, name: str) -> None:
    target = tmp_path / name
    if target.suffix:
        target.write_text("not Python", encoding="utf-8")

    report = scan(target, Config())

    assert report.definitions == ()
    assert report.issues[0].code == "DT1000"


def test_invalid_source_encoding_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "encoded.py"
    target.write_bytes(b"# coding: ascii\n# \xff\ndef item():\n    pass\n")

    report = scan(tmp_path, Config())

    assert report.definitions == ()
    assert report.issues[0].code == "DT1001"


def test_symlink_outside_root_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("def outside():\n    pass\n", encoding="utf-8")
    link = root / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    report = scan(root, Config())

    assert report.definitions == ()
    assert report.issues[0].code == "DT1002"


def test_source_snapshot_retries_as_a_whole_after_a_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.py"
    target.write_text("def original():\n    pass\n", encoding="utf-8")
    reads = iter(
        (
            ("def first():\n    pass\n", "first"),
            ("def second():\n    pass\n", "second"),
            ("def second():\n    pass\n", "second"),
            ("def second():\n    pass\n", "second"),
        )
    )
    monkeypatch.setattr(scanner, "_read_python_source", lambda path: next(reads))

    collection = collect_sources(tmp_path)

    assert [unit.digest for unit in collection.units] == ["second"]
    assert collection.issues == ()


def test_repeated_source_changes_return_no_mixed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.py"
    target.write_text("def original():\n    pass\n", encoding="utf-8")
    counter = 0

    def changing_read(path: Path) -> tuple[str, str]:
        nonlocal counter
        del path
        counter += 1
        return f"def version_{counter}():\n    pass\n", str(counter)

    monkeypatch.setattr(scanner, "_read_python_source", changing_read)

    collection = collect_sources(tmp_path)

    assert collection.units == ()
    assert any(issue.code == "DT1002" for issue in collection.issues)
