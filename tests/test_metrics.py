"""Tests for deadman_switch.metrics -- heartbeat regularity analysis."""

from __future__ import annotations

import pytest

from deadman_switch.metrics import (
    MetricsError, basic_stats, heartbeat_report, intervals, largest_gap,
    punctuality,
)


def test_intervals_basic():
    assert intervals([0, 10, 30]) == [10, 20]


def test_intervals_sorts_input():
    assert intervals([30, 0, 10]) == [10, 20]


def test_intervals_too_few():
    with pytest.raises(MetricsError):
        intervals([5])


def test_basic_stats_steady():
    beats = [0, 10, 20, 30]
    stats = basic_stats(beats)
    assert stats["count"] == 4
    assert stats["mean"] == 10
    assert stats["jitter"] == 0
    assert stats["min"] == 10 and stats["max"] == 10


def test_basic_stats_jittery():
    beats = [0, 5, 25, 30]  # gaps 5, 20, 5
    stats = basic_stats(beats)
    assert stats["mean"] == 10
    assert stats["jitter"] > 0
    assert stats["min"] == 5 and stats["max"] == 20


def test_largest_gap():
    beats = [0, 10, 50, 60]
    gap = largest_gap(beats)
    assert gap["duration"] == 40
    assert gap["from"] == 10 and gap["to"] == 50


def test_punctuality_perfect():
    beats = [0, 30, 60, 90]
    result = punctuality(beats, expected_interval=30)
    assert result["score"] == 1.0
    assert result["on_time"] == 3


def test_punctuality_with_tolerance():
    beats = [0, 32, 60]  # gaps 32, 28; expected 30, tolerance 0.25
    result = punctuality(beats, expected_interval=30, tolerance=0.25)
    assert result["score"] == 1.0


def test_punctuality_off_cadence():
    beats = [0, 100, 200]  # way off a 30s cadence
    result = punctuality(beats, expected_interval=30, tolerance=0.25)
    assert result["score"] == 0.0


def test_punctuality_validation():
    with pytest.raises(MetricsError):
        punctuality([0, 10], expected_interval=0)
    with pytest.raises(MetricsError):
        punctuality([0, 10], expected_interval=10, tolerance=2)


def test_heartbeat_report_shape():
    beats = [0, 30, 60, 90]
    report = heartbeat_report(beats, expected_interval=30)
    assert "stats" in report
    assert "largest_gap" in report
    assert "punctuality" in report
    assert report["punctuality"]["score"] == 1.0


def test_heartbeat_report_without_expected():
    beats = [0, 30, 60]
    report = heartbeat_report(beats)
    assert "punctuality" not in report


def test_heartbeat_report_too_few():
    with pytest.raises(MetricsError):
        heartbeat_report([0])
