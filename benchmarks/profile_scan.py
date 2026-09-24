"""Run one analysis so an external profiler can observe it.

This script is for profiling only and is never part of a timed benchmark run:

    uv run python -m cProfile -o profile.prof benchmarks/profile_scan.py PATH

Strip user-specific path prefixes from any profile excerpt before committing it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from deadtrace.analysis import analyze
from deadtrace.config import discover_config, load_config


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: profile_scan.py PATH", file=sys.stderr)
        return 2
    path = Path(argv[1])
    result = analyze(path, load_config(discover_config(path, None)))
    metrics = result.metrics
    print(
        f"files={metrics.files} lines={metrics.lines} "
        f"nodes={metrics.nodes} edges={metrics.edges} worlds={metrics.worlds}"
    )
    print(
        f"collect={metrics.collect_seconds:.3f}s frontend={metrics.frontend_seconds:.3f}s "
        f"solve={metrics.solve_seconds:.3f}s total={metrics.total_seconds:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
