"""Tests for split-question Jev calibration."""

from __future__ import annotations

import pytest
from scripts.analyze_t059_jev_split import (
    CandidateJudgment,
    calibrate_split_thresholds,
)


def test_split_calibration_uses_both_independent_thresholds() -> None:
    correct = ("d", 0, 1, 3, 7)
    incorrect = ("d", 3, 7, 0, 1)
    result = calibrate_split_thresholds(
        [
            CandidateJudgment(correct, 0.8, 0.9),
            CandidateJudgment(incorrect, 0.9, 0.6),
        ],
        {correct},
        grid=(0.5, 0.7, 0.9),
    )

    assert result.definition_threshold == 0.7
    assert result.orientation_threshold == 0.9
    assert result.f1 == 1.0
    assert result.precision == 1.0


def test_split_calibration_validates_inputs() -> None:
    with pytest.raises(ValueError, match="at least one"):
        calibrate_split_thresholds([], set())
    judgment = CandidateJudgment(None, 0.5, 0.5)
    with pytest.raises(ValueError, match="must not be empty"):
        calibrate_split_thresholds([judgment], set(), grid=())
    with pytest.raises(ValueError, match="between zero and one"):
        calibrate_split_thresholds([judgment], set(), grid=(1.1,))
