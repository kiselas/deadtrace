"""Independently unused definitions currently retained by an overly broad guard."""

from pathlib import Path

import pytest

from deadtrace.case_validator import unmet_targets

RECALL_GAPS = {"object_setattr_store": ("_tool.py:Stored.idle",)}


def test_every_recall_gap_is_pinned(project_root: Path) -> None:
    root = project_root / "fixtures" / "recall-gaps"
    assert {path.parent.name for path in root.glob("*/CASE.toml")} == set(RECALL_GAPS)


@pytest.mark.parametrize("case", sorted(RECALL_GAPS))
def test_exact_recall_gap(project_root: Path, case: str) -> None:
    assert unmet_targets(project_root / "fixtures" / "recall-gaps" / case) == RECALL_GAPS[case]
