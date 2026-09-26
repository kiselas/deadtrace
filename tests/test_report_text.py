"""Text reports count identical limitations once and summarize many conservative guards."""

from __future__ import annotations

from pathlib import Path

from deadtrace.analysis import AnalysisResult, analyze
from deadtrace.config import Config
from deadtrace.core import Limitation
from deadtrace.semantic_report import limitation_lines, render_semantic_text, widest_guards


def _guard(message: str) -> Limitation:
    return Limitation(code="DT2002", message=message)


def test_identical_limitations_are_counted_and_other_codes_always_listed() -> None:
    limitations = [
        Limitation(code="DT3001", message="configured root cannot be resolved: a"),
        _guard("registered by decorator app.task"),
        _guard("registered by decorator app.task"),
        Limitation(code="DT3001", message="configured root cannot be resolved: a"),
    ]

    assert limitation_lines(limitations, indent="  ", label="limitation ") == [
        "  limitation DT3001: configured root cannot be resolved: a (x2)",
        "  limitation DT2002: registered by decorator app.task (x2)",
    ]


def test_many_kinds_of_guard_collapse_into_a_summary() -> None:
    limitations = [
        Limitation(code="DT4001", message="version mismatch"),
        *(_guard(f"guard {index}") for index in range(8)),
        *(_guard("common guard") for _ in range(3)),
        *(_guard("frequent guard") for _ in range(2)),
    ]

    assert limitation_lines(limitations, indent="", label="") == [
        "DT4001: version mismatch",
        "DT2002: 13 conservative guards of 10 kinds protect code that may run; the most common:",
        "    common guard (x3)",
        "    frequent guard (x2)",
        "    guard 0",
        "    and 7 more kinds; the JSON report lists every guard",
    ]


def test_few_kinds_of_guard_are_listed_by_count() -> None:
    limitations = [_guard("b"), _guard("a"), _guard("b")]

    assert limitation_lines(limitations, indent="", label="") == ["DT2002: b (x2)", "DT2002: a"]


def _analyze(tmp_path: Path, files: dict[str, str]) -> AnalysisResult:
    for name, source in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return analyze(tmp_path, Config())


def test_a_limitation_every_world_has_is_printed_once(tmp_path: Path) -> None:
    result = _analyze(
        tmp_path,
        {
            "tool.py": "def main() -> None:\n    pass\n\nif __name__ == '__main__':\n    main()\n",
            "other.py": "if __name__ == '__main__':\n    pass\n",
            "broken.py": "def (:\n",
            "test_tool.py": "def test_main() -> None:\n    pass\n",
        },
    )
    text = render_semantic_text(result)

    assert len(result.snapshot.worlds) > 1
    assert text.count("broken.py: syntax error") == 1
    assert "Every world:" in text


def test_widest_guards_explain_why_little_is_reported(tmp_path: Path) -> None:
    result = _analyze(
        tmp_path,
        {
            "_runner.py": (
                "import importlib\nimport sys\n\n"
                "def main() -> None:\n"
                "    importlib.import_module(sys.argv[1])\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
            **{
                f"_plugin_{index}.py": (
                    "import atexit\n\n@atexit.register\ndef hook() -> None:\n    pass\n"
                )
                for index in range(4)
            },
        },
    )
    text = render_semantic_text(result)
    guards = widest_guards(result, 3)

    assert guards and guards[0][2] == "_runner.py:4"
    assert "may run only through unknown boundaries" in text
    assert "_runner.py:4  any project module may be imported by name" in text
