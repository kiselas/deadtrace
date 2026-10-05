from __future__ import annotations

from pathlib import Path

from deadtrace.analysis import analyze
from deadtrace.case_validator import validate_cases
from deadtrace.config import load_config


def test_reference_corpus_manifest_and_static_result(project_root: Path) -> None:
    case_root = project_root / "corpus" / "reference" / "fastapi_dishka_basic"
    result = validate_cases(project_root / "corpus")
    analysis = analyze(case_root, load_config(case_root / "pyproject.toml"))

    assert result.cases == 121
    assert result.targets == 422
    assert result.semantic_cases == 121
    assert analysis.complete
    assert [finding.code for finding in analysis.findings] == ["RCH003"]
    assert {member.qualified_name for member in analysis.findings[0].members} >= {
        "AppProvider.legacy",
        "LegacyService",
        "LegacyService.run",
    }
