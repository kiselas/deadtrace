"""The GitHub Action and pre-commit hooks are consumed from the repository root."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_action_default_version_matches_the_package() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    action = (ROOT / "action.yml").read_text(encoding="utf-8")

    assert f'default: "{project["version"]}"' in action
    assert "using: composite" in action


def test_pre_commit_hooks_run_the_cli_without_file_arguments() -> None:
    hooks = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    lines = hooks.splitlines()

    assert "- id: deadtrace" in lines
    assert "- id: deadtrace-report" in lines
    assert hooks.count("pass_filenames: false") == 2
    assert "entry: deadtrace scan . --baseline deadtrace-baseline.json --fail-on-new" in hooks
