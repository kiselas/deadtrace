"""Generate a deterministic, non-executable 50k-LOC benchmark project."""

from __future__ import annotations

import argparse
from pathlib import Path


def generate(root: Path, target_lines: int = 50_000) -> int:
    if target_lines < 1_000:
        raise ValueError("target_lines must be at least 1000")
    root.mkdir(parents=True, exist_ok=True)
    main = (
        "from fastapi import FastAPI\n"
        "\n"
        "app = FastAPI()\n"
        "\n"
        "@app.get('/')\n"
        "def live() -> str:\n"
        "    return 'live'\n"
    )
    (root / "main.py").write_text(main, encoding="utf-8", newline="\n")
    lines = len(main.splitlines())
    module_index = 0
    while lines < target_lines:
        remaining = target_lines - lines
        module_lines = min(200, remaining)
        if module_lines < 2:
            padding = "\n" * module_lines
            (root / f"padding_{module_index:04d}.py").write_text(
                padding, encoding="utf-8", newline="\n"
            )
            lines += module_lines
            continue
        body = [f"def candidate_{module_index:04d}() -> int:", "    value = 0"]
        body.extend(f"    value += {index % 7}" for index in range(module_lines - 3))
        body.append("    return value")
        contents = "\n".join(body) + "\n"
        (root / f"module_{module_index:04d}.py").write_text(
            contents, encoding="utf-8", newline="\n"
        )
        lines += len(body)
        module_index += 1
    (root / "pyproject.toml").write_text(
        """[project]
name = "deadtrace-scale-fixture"
version = "0.0.0"
dependencies = ["fastapi==0.141.1"]
""",
        encoding="utf-8",
        newline="\n",
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--lines", type=int, default=50_000)
    arguments = parser.parse_args()
    generated = generate(arguments.output, arguments.lines)
    print(f"Generated {generated} Python LOC in {arguments.output}")


if __name__ == "__main__":
    main()
