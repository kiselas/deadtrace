"""Known violations of independent case expectations, pinned exactly.

Every case under ``fixtures/known-violations`` states its safe outcome in CASE.md and CASE.toml
without consulting Deadtrace's output. The analysis does not meet some of those expectations yet;
``KNOWN_VIOLATIONS`` lists which. A fix removes a target from the list and a regression adds one,
and either way the list changes in the same commit. A case whose list becomes empty moves to
``corpus/`` together with the ``[analysis]`` table of the model revision that fixed it.

The lists are a ratchet over current behavior, not expectations: the expectations are the
manifests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deadtrace.case_validator import unmet_targets

KNOWN_VIOLATIONS: dict[str, tuple[str, ...]] = {}
"""Empty: imported alias reflection moved to corpus after the model-28 fix."""


def _cases_root(project_root: Path) -> Path:
    return project_root / "fixtures" / "known-violations"


def test_every_known_violation_case_is_pinned(project_root: Path) -> None:
    cases = {path.parent.name for path in _cases_root(project_root).glob("*/CASE.toml")}

    assert cases == set(KNOWN_VIOLATIONS)


@pytest.mark.parametrize("case", sorted(KNOWN_VIOLATIONS))
def test_unmet_expectations_are_exactly_the_known_violations(project_root: Path, case: str) -> None:
    expected = KNOWN_VIOLATIONS[case]
    assert expected, f"{case} meets every expectation; move it to corpus/"

    assert unmet_targets(_cases_root(project_root) / case) == expected
