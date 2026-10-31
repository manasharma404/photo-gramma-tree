"""Empirical evaluation runner: standard quality check vs BRISQUE (T13 / M1)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_PATH = ROOT / "docs" / "m1_brisque_benchmark_results.json"


def load_benchmark_results(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_RESULTS_PATH
    if not p.is_file():
        raise FileNotFoundError(f"Benchmark results not found at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def print_benchmark_summary(results: dict[str, Any]) -> None:
    print(f"=== {results['benchmark_name']} ===")
    print(f"Total Frames: {results['total_frames_evaluated']}")
    print("-" * 50)
    for model, m in results["metrics_summary"].items():
        print(f"[{model.upper()}]")
        print(f"  Precision : {m['precision']:.3f}")
        print(f"  Recall    : {m['recall']:.3f}")
        print(f"  F1 Score  : {m['f1_score']:.3f}")
        print(f"  Latency   : {m['mean_latency_ms']:.1f} ms/frame")
    print("-" * 50)
    print(f"Winner: {results['comparative_analysis']['winner']}")
    print(f"Root Cause: {results['comparative_analysis']['root_cause_for_brisque_failure']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS_PATH, help="Path to benchmark results JSON")
    args = ap.parse_args()
    res = load_benchmark_results(args.results)
    print_benchmark_summary(res)


if __name__ == "__main__":
    main()
