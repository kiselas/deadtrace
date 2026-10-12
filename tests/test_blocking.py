"""Findings of forms that reviews showed to be mostly false are held back (ADR-0071)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from deadtrace.analysis import analyze
from deadtrace.cli import app
from deadtrace.config import Config

runner = CliRunner()

TOOL = 'def main() -> None:\n    print("tool")\n\n\nif __name__ == "__main__":\n    main()\n'


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _blocked(root: Path) -> dict[str, tuple[str, ...]]:
    result = analyze(root, Config())
    return {
        member.qualified_name: finding.blocked
        for finding in result.blocked_findings
        for member in finding.members
    }


def _shown(root: Path) -> set[str]:
    result = analyze(root, Config())
    return {member.qualified_name for finding in result.findings for member in finding.members}


def test_code_under_examples_is_blocked(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "_tool.py": TOOL + "\n\ndef unused() -> None:\n    pass\n",
            "examples/_demo.py": "def helper() -> None:\n    pass\n",
        },
    )

    assert _blocked(tmp_path) == {"helper": ("non_production_area",)}
    assert _shown(tmp_path) == {"unused"}


def test_method_of_class_with_external_base_is_blocked(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "_tool.py": TOOL
            + "\n\nfrom django.views.generic import ListView\n\n\n"
            + "class BookList(ListView):\n    def get_ordering(self):\n        return ['title']\n",
        },
    )

    blocked = _blocked(tmp_path)

    assert "external_base_hooks" in blocked["BookList.get_ordering"]


def test_name_in_a_configuration_file_is_blocked(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "_tool.py": TOOL + "\n\ndef rotate_logs() -> None:\n    pass\n",
            "deploy/cron.yml": "jobs:\n  - call: _tool.rotate_logs\n",
        },
    )

    assert _blocked(tmp_path) == {"rotate_logs": ("mentioned_in_config",)}


def test_deadtrace_report_does_not_block_its_own_findings(tmp_path: Path) -> None:
    _write(tmp_path, {"_tool.py": TOOL + "\n\ndef rotate_logs() -> None:\n    pass\n"})
    report = tmp_path / "deadtrace-report.yml"
    report.write_text(
        "tool: deadtrace\nmodel_revision: x\nfingerprint: rotate_logs\n", encoding="utf-8"
    )

    assert _shown(tmp_path) == {"rotate_logs"}


def test_exported_public_name_of_a_package_is_blocked(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "_tool.py": TOOL,
            "shop/__init__.py": "",
            "shop/cart.py": '__all__ = ["total"]\n\n\ndef total(items):\n    return sum(items)\n',
            "shop/app.py": (
                "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
                '@app.get("/")\ndef index() -> dict[str, int]:\n    return {}\n'
            ),
        },
    )

    assert _blocked(tmp_path).get("total") == ("public_api",)


def test_exit_codes_ignore_blocked_findings_and_json_lists_them(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "_tool.py": TOOL,
            "examples/_demo.py": "def helper() -> None:\n    pass\n",
        },
    )

    failed = runner.invoke(app, ["scan", str(tmp_path), "--fail-on-findings"])
    payload = runner.invoke(app, ["scan", str(tmp_path), "--format", "json"])
    shown = runner.invoke(app, ["scan", str(tmp_path), "--show-blocked"])

    assert failed.exit_code == 0
    assert "Blocked: 1 findings held back (non_production_area 1)." in failed.stdout
    report = json.loads(payload.stdout)
    assert report["findings"] == []
    assert report["summary"]["blocked_finding_count"] == 1
    assert report["blocked_findings"][0]["blocked"] == ["non_production_area"]
    assert "[blocked: non_production_area]" in shown.stdout
    assert "examples/_demo.py:1  helper" in shown.stdout


def test_method_of_mixin_mixed_into_class_with_external_base_is_blocked(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "_tool.py": TOOL
            + "\n\nfrom django.test import TestCase\n\n\n"
            + "class DataMixin:\n    @classmethod\n    def setUpTestData(cls):\n        pass\n\n\n"
            + "class FormTest(DataMixin, TestCase):\n    pass\n",
        },
    )

    assert "external_base_hooks" in _blocked(tmp_path)["DataMixin.setUpTestData"]


def test_private_helper_of_a_mixin_is_not_blocked_as_a_hook(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "_tool.py": TOOL
            + "\n\nfrom django.test import TestCase\n\n\n"
            + "class AdminMixin:\n    def _check_operator(self):\n        pass\n\n\n"
            + "class AdminTest(AdminMixin, TestCase):\n    pass\n",
        },
    )

    assert "AdminMixin._check_operator" not in _blocked(tmp_path)


def test_overridden_stub_method_is_an_interface_declaration(tmp_path: Path) -> None:
    """A base stub that subclasses override declares their interface (ADR-0101)."""

    _write(
        tmp_path,
        {
            "_tool.py": TOOL
            + "\n\nclass _Base:\n"
            + "    def _validate(self, path):\n        raise NotImplementedError\n\n"
            + "    def _never(self):\n        raise NotImplementedError\n\n\n"
            + "class _Csv(_Base):\n"
            + "    def run(self, path):\n        self._validate(path)\n\n"
            + "    def _validate(self, path):\n        return path\n\n\n"
            + "def _use():\n    _Csv().run('x')\n\n\n_use()\n",
        },
    )

    assert _blocked(tmp_path) == {"_Base._validate": ("interface_declaration",)}
    assert "_Base._never" in _shown(tmp_path)
