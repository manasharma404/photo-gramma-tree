"""Tests for M1 / T13 BRISQUE vs Standard Check empirical evaluation."""
from __future__ import annotations

from pathlib import Path
from quality.brisque_benchmark import load_benchmark_results

ROOT = Path(__file__).resolve().parent.parent


def test_m1_brisque_benchmark_metrics_and_results() -> None:
    res = load_benchmark_results()
    assert res["total_frames_evaluated"] == 60
    assert res["comparative_analysis"]["winner"] == "standard_check"

    std = res["metrics_summary"]["standard_check"]
    assert std["f1_score"] == 1.0
    assert std["precision"] == 1.0
    assert std["recall"] == 1.0

    br = res["metrics_summary"]["brisque"]
    assert abs(br["precision"] - 0.833) < 0.005
    assert abs(br["f1_score"] - 0.808) < 0.005
    assert br["false_positives"] == 6
