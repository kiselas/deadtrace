from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

from deadtrace import semantic_report
from deadtrace.analysis import analyze
from deadtrace.config import Config
from deadtrace.semantic_report import (
    doctor_text,
    explain_fingerprint,
    render_semantic_json,
    render_semantic_text,
    semantic_report_dict,
)


def test_complete_fastapi_analysis_emits_review_candidate(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def live() -> str:
    return "live"

def candidate() -> str:
    return "candidate"
""",
        encoding="utf-8",
    )

    result = analyze(tmp_path, Config())
    report = json.loads(render_semantic_json(result))

    assert result.complete
    assert report["analysis_state"] == "complete"
    assert report["validation"] == "not_performed"
    finding = next(item for item in report["findings"] if item["code"] == "RCH001")
    assert [member["qualified_name"] for member in finding["members"]] == ["candidate"]
    assert finding["action"] == "review"
    assert "py:" not in render_semantic_json(result)


def test_source_and_config_digests_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )

    first = analyze(tmp_path, Config())
    second = analyze(tmp_path, Config())

    assert first.source_digest == second.source_digest
    assert first.config_digest == second.config_digest
    assert first.findings == second.findings
    assert render_semantic_json(first) == render_semantic_json(second)


def test_new_snapshot_drops_edges_removed_from_source(tmp_path: Path) -> None:
    source = tmp_path / "main.py"
    source.write_text(
        """
from fastapi import FastAPI
app = FastAPI()

def helper() -> str:
    return "used"

@app.get("/")
def endpoint() -> str:
    return helper()
""",
        encoding="utf-8",
    )
    first = analyze(tmp_path, Config())
    source.write_text(
        """
from fastapi import FastAPI
app = FastAPI()

def helper() -> str:
    return "unused"

@app.get("/")
def endpoint() -> str:
    return "direct"
""",
        encoding="utf-8",
    )
    second = analyze(tmp_path, Config())

    assert not any(
        member.qualified_name == "helper"
        for finding in first.findings
        for member in finding.members
    )
    assert any(
        member.qualified_name == "helper"
        for finding in second.findings
        for member in finding.members
    )


def test_explanation_truncation_never_changes_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def endpoint() -> str:
    return "live"

def candidate() -> str:
    return "candidate"
""",
        encoding="utf-8",
    )
    result = analyze(tmp_path, Config())
    fingerprints = [finding.fingerprint for finding in result.findings]
    monkeypatch.setattr(semantic_report, "_EXPLANATION_LIMIT", 0)

    report = semantic_report_dict(result)

    assert [item["fingerprint"] for item in report["findings"]] == fingerprints
    assert report["explanations"]["truncated"]
    assert report["explanations"]["derivations"] == []


def test_unreadable_or_invalid_source_blocks_strong_findings(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    result = analyze(tmp_path, Config())

    assert not result.complete
    assert not any(finding.code in {"RCH001", "RCH003"} for finding in result.findings)


def test_text_doctor_and_saved_explanation(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def live() -> None:
    pass

def candidate() -> None:
    pass
""",
        encoding="utf-8",
    )
    result = analyze(tmp_path, Config())
    payload = semantic_report_dict(result)
    finding = result.findings[0]

    text = render_semantic_text(result)
    doctor = doctor_text(result)
    explanation = explain_fingerprint(payload, finding.fingerprint)

    assert "RCH001" in text
    assert "not a claim that deletion is safe" in text
    assert "fastapi.routes@2" in doctor
    assert finding.fingerprint in explanation


def test_saved_explanation_rejects_invalid_or_missing_findings() -> None:
    with pytest.raises(ValueError, match="findings array"):
        explain_fingerprint({}, "missing")

    with pytest.raises(KeyError) as error:
        explain_fingerprint({"findings": []}, "missing")
    assert error.value.args == ("missing",)


def test_unrequested_dishka_binding_is_grouped_with_its_component(tmp_path: Path) -> None:
    (tmp_path / "domain.py").write_text(
        """
def shared() -> None:
    pass

class Live:
    def run(self) -> None:
        shared()

class Legacy:
    def run(self) -> None:
        shared()
""",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from domain import Legacy, Live

class AppProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def live(self) -> Live:
        return Live()

    @provide(scope=Scope.REQUEST)
    def legacy(self) -> Legacy:
        return Legacy()

app = FastAPI()

@app.get("/")
@inject
def endpoint(service: FromDishka[Live]) -> None:
    service.run()

container = make_async_container(AppProvider())
setup_dishka(container, app)
""",
        encoding="utf-8",
    )

    result = analyze(tmp_path, Config())

    binding = next(finding for finding in result.findings if finding.code == "RCH003")
    names = {member.qualified_name for member in binding.members}
    assert {"AppProvider.legacy", "Legacy", "Legacy.run"} <= names
    assert not any(
        finding.code == "RCH001"
        and any(member.qualified_name == "Legacy" for member in finding.members)
        for finding in result.findings
    )
    explanation = json.loads(explain_fingerprint(semantic_report_dict(result), binding.fingerprint))
    assert explanation["finding"]["fingerprint"] == binding.fingerprint
    assert explanation["world_states"][0]["negative_findings_allowed"]
    assert any(edge["target"].endswith("shared") for edge in explanation["live_boundaries"])


def test_unpublished_router_is_separate_observation(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        """
from fastapi import APIRouter, FastAPI

app = FastAPI()
hidden = APIRouter()

@app.get("/")
def live() -> None:
    pass

@hidden.get("/hidden")
def hidden_endpoint() -> None:
    pass
""",
        encoding="utf-8",
    )

    result = analyze(tmp_path, Config())

    finding = next(item for item in result.findings if item.code == "RCH002")
    assert finding.members[0].qualified_name == "hidden_endpoint"


def test_semantic_scan_does_not_execute_target_import_hooks_or_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "executed.txt"
    (tmp_path / "main.py").write_text(
        f"""
from pathlib import Path
from fastapi import FastAPI

Path({str(marker)!r}).write_text("executed")
app = FastAPI()
""",
        encoding="utf-8",
    )
    (tmp_path / "malicious.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('pth')\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("SECRET=must-not-load\n", encoding="utf-8")

    def forbidden_connection(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("semantic scan must not use the network")

    monkeypatch.setattr(socket, "create_connection", forbidden_connection)
    path_before = list(sys.path)

    result = analyze(tmp_path, Config())

    assert result.complete
    assert not marker.exists()
    assert sys.path == path_before
