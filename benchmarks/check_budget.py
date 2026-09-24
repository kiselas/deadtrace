"""Fail when a benchmark artifact exceeds the performance budget (roadmap PERF-04).

    python benchmarks/check_budget.py ARTIFACT... [--max-seconds 30] [--max-rss-mib 1024]

The defaults are the preliminary alpha budget of the roadmap: a cold scan of 50,000 lines in less
than 30 seconds, with process peak RSS below 1 GiB. The median ``total_seconds`` of each artifact is
compared, so one slow run on a shared runner does not fail the check. An artifact without a peak
RSS fails, because the budget cannot be verified.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

MIB = 2**20


def check(artifact: dict[str, Any], *, max_seconds: float, max_rss_bytes: int) -> list[str]:
    """What an artifact violates; empty when it is within the budget."""

    if artifact.get("kind") != "deadtrace-benchmark" or artifact.get("schema_version") != 4:
        return ["not a schema-4 deadtrace benchmark artifact"]
    problems: list[str] = []
    median = float(artifact["summary"]["total_seconds"]["median"])
    if median >= max_seconds:
        problems.append(f"median total {median:.2f} s is not below {max_seconds:g} s")
    rss = artifact.get("process_peak_rss_bytes")
    if rss is None:
        problems.append("peak RSS was not reported")
    elif rss >= max_rss_bytes:
        problems.append(f"peak RSS {rss / MIB:.0f} MiB is not below {max_rss_bytes / MIB:.0f} MiB")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check benchmark artifacts against the budget.")
    parser.add_argument("artifacts", nargs="+", type=Path)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument("--max-rss-mib", type=float, default=1024.0)
    args = parser.parse_args(argv)
    failed = False
    for path in args.artifacts:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        problems = check(
            artifact,
            max_seconds=args.max_seconds,
            max_rss_bytes=int(args.max_rss_mib * MIB),
        )
        failed = failed or bool(problems)
        counters = artifact.get("counters", {})
        summary = artifact.get("summary", {}).get("total_seconds", {})
        rss = artifact.get("process_peak_rss_bytes")
        print(
            f"{path.name}: {counters.get('lines', '?')} lines, "
            f"median {summary.get('median', float('nan')):.2f} s over {artifact.get('runs', '?')} "
            f"runs, peak RSS {rss / MIB if rss is not None else float('nan'):.0f} MiB: "
            + ("; ".join(problems) if problems else "within budget")
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
