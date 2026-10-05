"""Exercise an installed wheel from a temporary directory outside the checkout."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    checkout = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="deadtrace-wheel-smoke-") as directory:
        work = Path(directory)

        def command(*arguments: str, expected: int = 0) -> str:
            result = subprocess.run(
                [sys.executable, "-m", "deadtrace", *arguments],
                cwd=work,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=60,
            )
            if result.returncode != expected:
                raise RuntimeError(
                    f"{arguments}: expected exit {expected}, got {result.returncode}\n"
                    f"{result.stdout}\n{result.stderr}"
                )
            return result.stdout

        location = subprocess.run(
            [sys.executable, "-c", "import deadtrace; print(deadtrace.__file__)"],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        if Path(location.stdout.strip()).resolve().is_relative_to(checkout):
            raise RuntimeError("wheel smoke imported Deadtrace from the checkout")
        expected_version = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["version"]
        assert command("--version").strip() == f"deadtrace {expected_version}"
        assert "scan" in command("--help")

        target = work / "target"
        target.mkdir()
        source = target / "main.py"
        contents = (
            "from pathlib import Path\n"
            "Path('executed.txt').write_text('target executed')\n"
            "raise RuntimeError('must never execute')\n"
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.get('/')\n"
            "def endpoint(): return 'ok'\n"
            "def candidate(): return 'unused'\n"
        )
        source.write_text(contents, encoding="utf-8")
        timestamp = source.stat().st_mtime_ns
        inventory = json.loads(command("scan", str(target), "--inventory-only", "--format", "json"))
        assert inventory["schema_version"] == 0
        assert inventory["summary"]["definition_count"] == 2
        assert inventory["issues"] == []

        first = command("scan", str(target), "--format", "json", "--require-complete")
        assert first == command("scan", str(target), "--format", "json", "--require-complete")
        report = json.loads(first)
        assert report["tool"]["version"] == expected_version
        assert report["schema_version"] == 1
        assert report["analysis_state"] == "complete"
        finding = next(item for item in report["findings"] if item["code"] == "RCH001")
        assert [member["qualified_name"] for member in finding["members"]] == ["candidate"]

        saved_report = work / "report.json"
        saved_report.write_text(first, encoding="utf-8")
        assert finding["fingerprint"] in command(
            "explain", finding["fingerprint"], "--report", str(saved_report)
        )
        baseline = work / "baseline.json"
        command(
            "baseline",
            "create",
            str(saved_report),
            "--output",
            str(baseline),
            "--reason",
            "wheel smoke",
        )
        command("scan", str(target), "--baseline", str(baseline), "--fail-on-new")
        command(
            "compare", str(saved_report), str(saved_report), "--require-comparable", "--fail-on-new"
        )

        (target / "bad.py").write_bytes(b"# coding: base64_codec\ndef bad(): pass\n")
        failed = json.loads(
            command("scan", str(target), "--inventory-only", "--format", "json", expected=2)
        )
        assert [issue["code"] for issue in failed["issues"]] == ["DT1001"]
        assert source.read_text(encoding="utf-8") == contents
        assert source.stat().st_mtime_ns == timestamp
        assert not (work / "executed.txt").exists()
        assert not (target / "executed.txt").exists()
    print(
        "Wheel smoke passed: inventory, analysis, determinism, artifacts, input errors, "
        "no target execution."
    )


if __name__ == "__main__":
    main()
