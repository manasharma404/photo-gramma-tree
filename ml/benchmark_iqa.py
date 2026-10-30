"""Head-to-head evaluation gate for T13: ML IQA (OpenCV BRISQUE SVR) vs T12 standard_check.

Per docs/teammate_prompt.md Step 11:
  - ML image-quality replaces standard_check ONLY if it beats standard_check on
    human-labelled frames from the survey dataset.
  - Model metadata recorded explicitly:
      * Model name: OpenCV QualityBRISQUE (Mittal et al., IEEE TIP 2012)
      * Version: opencv-contrib-python 5.0.0 (brisque_model_live.yml + brisque_range_live.yml)
      * Licence: Apache-2.0 (OpenCV) / BSD-2-Clause (LIVE IQA SVR weights)
      * Training data: LIVE Image Quality Assessment Database Release 2 (779 distorted images across 29 reference scenes; natural ground photos, NOT nadir drone footage)

Usage (once lead provides Neo 2 / USGS frame paths and labels.csv with columns image,usable):
    uv run python -m ml.benchmark_iqa --images <dir> --labels <labels.csv> --brisque-model <yml> --brisque-range <yml>
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from quality.check import evaluate_gray_frame, load_thresholds

MODEL_METADATA = {
    "model": "opencv-QualityBRISQUE-svr-live-r2",
    "version": "opencv-contrib-python==5.0.0",
    "licence": "Apache-2.0 (OpenCV) / BSD-2-Clause (UT Austin LIVE BRISQUE weights)",
    "training_data": "LIVE Image Quality Assessment Database Release 2 (29 reference images, 779 distorted images)",
}


def binary_classification_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if (not t) and (not p))
    fp = sum(1 for t, p in zip(y_true, y_pred) if (not t) and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and (not p))
    n = max(len(y_true), 1)
    acc = (tp + tn) / n
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2.0 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return {
        "n": len(y_true),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
    }


def compare_predictions(
    labels_by_image: dict[str, bool],
    standard_usable_by_image: dict[str, bool],
    ml_usable_by_image: dict[str, bool],
) -> dict[str, Any]:
    """Compare standard_check vs ML usable predictions on identical labelled frames."""
    common = sorted(
        set(labels_by_image.keys())
        & set(standard_usable_by_image.keys())
        & set(ml_usable_by_image.keys())
    )
    if not common:
        raise ValueError("No overlapping labelled images between ground truth, standard_check, and ML.")

    y_true = [bool(labels_by_image[k]) for k in common]
    y_std = [bool(standard_usable_by_image[k]) for k in common]
    y_ml = [bool(ml_usable_by_image[k]) for k in common]

    std_m = binary_classification_metrics(y_true, y_std)
    ml_m = binary_classification_metrics(y_true, y_ml)
    ml_wins = (ml_m["f1"], ml_m["accuracy"]) > (std_m["f1"], std_m["accuracy"])

    return {
        "evaluated_frames": len(common),
        "model_metadata": MODEL_METADATA,
        "standard_check": std_m,
        "ml_model": ml_m,
        "ml_beats_standard_check": ml_wins,
        "selected_method": "ml_model" if ml_wins else "standard_check",
    }


def score_brisque_directory(
    image_dir: Path,
    model_yml: Path,
    range_yml: Path,
    max_brisque_usable: float = 45.0,
) -> dict[str, tuple[float, bool]]:
    """Compute BRISQUE distortion score (0=best, 100=worst) and usability per image."""
    brisque = cv2.quality.QualityBRISQUE_create(str(model_yml), str(range_yml))
    results: dict[str, tuple[float, bool]] = {}
    for p in sorted(image_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
            arr = np.frombuffer(p.read_bytes(), dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None:
                continue
            raw_score = float(brisque.compute(bgr)[0])
            # Convert 0..100 distortion (lower is better) into 0..1 quality (higher is better)
            q_score = round(max(0.0, min(1.0, 1.0 - raw_score / 100.0)), 4)
            results[p.name] = (q_score, raw_score <= max_brisque_usable)
    return results


def load_labels_csv(csv_path: Path) -> dict[str, bool]:
    out: dict[str, bool] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            img = row["image"].strip()
            val = row["usable"].strip().lower() in ("1", "true", "yes", "usable")
            out[img] = val
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", type=Path, required=True, help="Directory of frames to evaluate")
    ap.add_argument("--labels", type=Path, required=True, help="CSV with columns: image,usable")
    ap.add_argument("--brisque-model", type=Path, required=True, help="Path to brisque_model_live.yml")
    ap.add_argument("--brisque-range", type=Path, required=True, help="Path to brisque_range_live.yml")
    ap.add_argument("--max-brisque", type=float, default=45.0, help="PLACEHOLDER BRISQUE distortion cutoff")
    ap.add_argument("--out", type=Path, default=None, help="Optional JSON comparison output")
    args = ap.parse_args()

    labels = load_labels_csv(args.labels)
    cfg = load_thresholds()
    std_usable: dict[str, bool] = {}
    for name in labels:
        p = args.images / name
        if p.is_file():
            gray = cv2.imdecode(np.frombuffer(p.read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if gray is not None:
                std_usable[name] = bool(evaluate_gray_frame(name, gray, cfg)["usable"])

    ml_scores = score_brisque_directory(args.images, args.brisque_model, args.brisque_range, args.max_brisque)
    ml_usable = {k: v[1] for k, v in ml_scores.items()}

    report = compare_predictions(labels, std_usable, ml_usable)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
