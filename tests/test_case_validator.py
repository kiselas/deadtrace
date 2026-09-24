from __future__ import annotations

from pathlib import Path

import pytest

from deadtrace.case_validator import CaseValidationError, unmet_targets, validate_cases


def test_seed_cases_have_valid_lexical_targets(project_root: Path) -> None:
    result = validate_cases(project_root / "fixtures" / "cases")

    assert result.cases == 6
    assert result.targets == 12


def _write_case(
    root: Path,
    name: str,
    *,
    case_id: str = "case",
    targets: str = "",
    markdown: bool = True,
) -> Path:
    case = root / name
    case.mkdir()
    if markdown:
        (case / "CASE.md").write_text("# Case\n", encoding="utf-8")
    (case / "target.py").write_text("def present():\n    pass\n", encoding="utf-8")
    default_target = """
[[targets]]
path = "target.py"
kind = "function"
qualified_name = "present"
expectation = "live"
"""
    (case / "CASE.toml").write_text(
        f'schema_version = 1\ncase_id = "{case_id}"\n{targets or default_target}',
        encoding="utf-8",
    )
    return case


def test_case_markdown_is_required(tmp_path: Path) -> None:
    _write_case(tmp_path, "one", markdown=False)

    with pytest.raises(CaseValidationError, match=r"missing CASE\.md"):
        validate_cases(tmp_path)


def test_case_ids_are_unique(tmp_path: Path) -> None:
    _write_case(tmp_path, "one", case_id="duplicate")
    _write_case(tmp_path, "two", case_id="duplicate")

    with pytest.raises(CaseValidationError, match="duplicate case_id"):
        validate_cases(tmp_path)


@pytest.mark.parametrize(
    ("targets", "message"),
    [
        ("targets = []\n", "targets must be a non-empty"),
        ('targets = ["bad"]\n', "each target must be a table"),
        (
            """
[[targets]]
path = "target.py"
kind = "function"
qualified_name = "present"
expectation = "impossible"
""",
            "unsupported expectation",
        ),
        (
            """
[[targets]]
path = "target.py"
kind = "function"
qualified_name = "absent"
expectation = "candidate"
""",
            "lexical target not found",
        ),
    ],
)
def test_invalid_case_targets_are_rejected(tmp_path: Path, targets: str, message: str) -> None:
    _write_case(tmp_path, "one", targets=targets)

    with pytest.raises(CaseValidationError, match=message):
        validate_cases(tmp_path)


def test_invalid_case_schema_and_toml_are_rejected(tmp_path: Path) -> None:
    case = _write_case(tmp_path, "one")
    manifest = case / "CASE.toml"
    manifest.write_text("schema_version = 2\ncase_id = 'case'\n", encoding="utf-8")
    with pytest.raises(CaseValidationError, match="schema_version"):
        validate_cases(tmp_path)

    manifest.write_text("schema_version = [\n", encoding="utf-8")
    with pytest.raises(CaseValidationError, match="cannot read"):
        validate_cases(tmp_path)


def _write_semantic_case(root: Path, expectations: dict[str, str]) -> Path:
    case = root / "semantic"
    case.mkdir()
    (case / "CASE.md").write_text("# Case\n", encoding="utf-8", newline="\n")
    (case / "main.py").write_text(
        "def unused() -> None:\n    pass\n\n\ndef main() -> None:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    (case / "pyproject.toml").write_text(
        "[[tool.deadtrace.worlds]]\n"
        'profile = "production"\n'
        'scenario = "script"\n'
        'roots = ["main:main"]\n'
        'frameworks = ["python"]\n',
        encoding="utf-8",
        newline="\n",
    )
    targets = "".join(
        f'\n[[targets]]\npath = "main.py"\nkind = "function"\n'
        f'qualified_name = "{name}"\nexpectation = "{expectation}"\n'
        for name, expectation in expectations.items()
    )
    (case / "CASE.toml").write_text(
        f'schema_version = 1\ncase_id = "semantic"\n{targets}', encoding="utf-8", newline="\n"
    )
    return case


def test_not_candidate_is_met_by_reached_code_and_unmet_by_a_finding(tmp_path: Path) -> None:
    case = _write_semantic_case(tmp_path, {"main": "not_candidate", "unused": "not_candidate"})

    assert unmet_targets(case) == ("main.py:unused",)


def test_unmet_targets_lists_every_unmet_target_not_only_the_first(tmp_path: Path) -> None:
    case = _write_semantic_case(tmp_path, {"main": "candidate", "unused": "live"})

    assert unmet_targets(case) == ("main.py:main", "main.py:unused")


def test_unmet_targets_is_empty_when_every_expectation_holds(tmp_path: Path) -> None:
    case = _write_semantic_case(tmp_path, {"main": "live", "unused": "candidate"})

    assert unmet_targets(case) == ()


def test_required_case_strings_are_non_empty(tmp_path: Path) -> None:
    _write_case(tmp_path, "one", case_id="")

    with pytest.raises(CaseValidationError, match="case_id must be"):
        validate_cases(tmp_path)
