from __future__ import annotations

import pytest

from deadtrace.timing import COUNTERS, STAGES, StageTimings


def test_key_sets_are_fixed_and_start_at_zero() -> None:
    timings = StageTimings()

    assert tuple(timings.seconds) == STAGES
    assert tuple(timings.counts) == COUNTERS
    assert all(value == 0.0 for value in timings.seconds.values())
    assert all(value == 0 for value in timings.counts.values())


def test_stage_accumulates_and_counters_add() -> None:
    timings = StageTimings()

    with timings.stage("frontend.parse"):
        pass
    with timings.stage("frontend.parse"):
        pass
    timings.count("frontend.modules")
    timings.count("frontend.modules", 4)

    assert timings.seconds["frontend.parse"] >= 0.0
    assert timings.counts["frontend.modules"] == 5


def test_stage_records_time_when_the_block_raises() -> None:
    timings = StageTimings()

    with pytest.raises(ValueError, match="boom"), timings.stage("solve.reachability"):
        raise ValueError("boom")

    assert timings.seconds["solve.reachability"] >= 0.0


def test_unknown_names_are_rejected() -> None:
    timings = StageTimings()

    with pytest.raises(KeyError, match="unknown stage"), timings.stage("frontend.typo"):
        pass
    with pytest.raises(KeyError, match="unknown counter"):
        timings.count("frontend.typo")


def test_frozen_views_are_read_only_copies() -> None:
    timings = StageTimings()
    seconds = timings.frozen_seconds()
    counts = timings.frozen_counts()
    timings.count("findings")

    assert counts["findings"] == 0
    with pytest.raises(TypeError):
        seconds["frontend.parse"] = 1.0  # type: ignore[index]
    with pytest.raises(TypeError):
        counts["findings"] = 1  # type: ignore[index]
