"""Seal or verify CI distribution bytes without importing packaged code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import tomllib
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path


def describe(dist: Path, version: str) -> dict[str, dict[str, str | int]]:
    expected = {
        f"deadtrace-{version}-py3-none-any.whl",
        f"deadtrace-{version}.tar.gz",
    }
    files = {
        path.name
        for path in dist.iterdir()
        if path.name not in {"release-receipt.json", ".gitignore"}
    }
    if files != expected:
        raise ValueError(f"expected only wheel and sdist for {version}, got {sorted(files)}")
    result: dict[str, dict[str, str | int]] = {}
    for name in sorted(expected):
        path = dist / name
        if name.endswith(".whl"):
            with zipfile.ZipFile(path) as wheel:
                names = [item for item in wheel.namelist() if item.endswith(".dist-info/METADATA")]
                if len(names) != 1:
                    raise ValueError("wheel must have exactly one METADATA")
                raw = wheel.read(names[0])
        else:
            with tarfile.open(path, "r:gz") as sdist:
                members = [
                    item
                    for item in sdist.getmembers()
                    if item.isfile()
                    and item.name.endswith("/PKG-INFO")
                    and item.name.count("/") == 1
                ]
                if len(members) != 1:
                    raise ValueError("sdist must have exactly one top-level PKG-INFO")
                stream = sdist.extractfile(members[0])
                if stream is None:
                    raise ValueError("missing sdist metadata")
                raw = stream.read()
        metadata = BytesParser(policy=policy.compat32).parsebytes(raw)
        if metadata.get("Name") != "deadtrace" or metadata.get("Version") != version:
            raise ValueError(f"distribution identity mismatch: {name}")
        result[name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["seal", "verify"])
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.sha) is None:
        raise ValueError("expected a full lowercase commit SHA")
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project["name"] != "deadtrace":
        raise ValueError("unexpected project")
    receipt = {
        "schema": 1,
        "project": "deadtrace",
        "version": project["version"],
        "commit": args.sha,
        "artifacts": describe(args.dist, project["version"]),
    }
    receipt_path = args.dist / "release-receipt.json"
    if args.mode == "seal":
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif json.loads(receipt_path.read_text(encoding="utf-8")) != receipt:
        raise ValueError("release receipt does not match candidate or distribution bytes")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
