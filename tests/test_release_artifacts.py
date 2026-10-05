"""Publication rejects identity drift and modified distribution bytes."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

SHA = "a" * 40
VERSION = "0.1.0a1"


def candidate(root: Path, *, metadata_version: str = VERSION) -> Path:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "deadtrace"\nversion = "{VERSION}"\n', encoding="utf-8"
    )
    dist = root / "dist"
    dist.mkdir()
    (dist / ".gitignore").write_text("*\n", encoding="utf-8")
    metadata = f"Metadata-Version: 2.4\nName: deadtrace\nVersion: {metadata_version}\n".encode()
    with zipfile.ZipFile(dist / f"deadtrace-{VERSION}-py3-none-any.whl", "w") as archive:
        archive.writestr(f"deadtrace-{VERSION}.dist-info/METADATA", metadata)
    with tarfile.open(dist / f"deadtrace-{VERSION}.tar.gz", "w:gz") as archive:
        item = tarfile.TarInfo(f"deadtrace-{VERSION}/PKG-INFO")
        item.size = len(metadata)
        archive.addfile(item, io.BytesIO(metadata))
    return dist


def run(root: Path, script: Path, mode: str, sha: str = SHA) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), mode, "--sha", sha],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def test_receipt_binds_candidate_and_exact_bytes(tmp_path: Path, project_root: Path) -> None:
    dist = candidate(tmp_path)
    script = project_root / "scripts" / "release_artifacts.py"
    assert run(tmp_path, script, "seal").returncode == 0
    assert run(tmp_path, script, "verify").returncode == 0
    receipt = json.loads((dist / "release-receipt.json").read_text())
    assert receipt["commit"] == SHA and len(receipt["artifacts"]) == 2
    assert run(tmp_path, script, "verify", "b" * 40).returncode != 0
    wheel = dist / f"deadtrace-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("deadtrace/changed.py", "raise RuntimeError('never execute')\n")
    failed = run(tmp_path, script, "verify")
    assert failed.returncode != 0 and "does not match" in failed.stderr


@pytest.mark.parametrize("problem", ["version", "missing", "extra", "sha"])
def test_rejects_invalid_publish_inputs(tmp_path: Path, project_root: Path, problem: str) -> None:
    dist = candidate(tmp_path, metadata_version="0.1.0a0" if problem == "version" else VERSION)
    if problem == "missing":
        (dist / f"deadtrace-{VERSION}.tar.gz").unlink()
    elif problem == "extra":
        (dist / "unexpected.whl").write_bytes(b"unexpected")
    result = run(
        tmp_path,
        project_root / "scripts" / "release_artifacts.py",
        "seal",
        "invalid" if problem == "sha" else SHA,
    )
    assert result.returncode != 0
    assert not (dist / "release-receipt.json").exists()
