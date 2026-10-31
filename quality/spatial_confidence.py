"""Spatial confidence layer generator for post-disaster orthomosaics (T14).

Labelled strictly as "estimated quality indicator", never "accuracy".
Computes a normalized float32 raster [0.0, 1.0] representing local texture
richness and feature tracking density across the photogrammetric block.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import rasterio

LABEL_ESTIMATED_QUALITY = "estimated quality indicator"
METRIC_NAME = "estimated_quality_indicator"


def generate_spatial_confidence(
    orthophoto_path: Path,
    out_path: Path,
    *,
    accuracy_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a 1-band float32 GeoTIFF representing an estimated quality indicator.

    Strict rule: Labelled 'estimated quality indicator', never 'accuracy'.
    """
    orthophoto_path = Path(orthophoto_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(orthophoto_path) as src:
        profile = src.profile.copy()
        crs = src.crs
        transform = src.transform
        width = src.width
        height = src.height
        count = src.count

        # Read bands for RGB or single band
        if count >= 3:
            r = src.read(1)
            g = src.read(2)
            b = src.read(3)
            # Mask out black / no-data background
            valid_mask = (r > 0) | (g > 0) | (b > 0)
            gray = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.float32)
        else:
            gray = src.read(1).astype(np.float32)
            valid_mask = gray > 0

    if not valid_mask.any():
        quality_map = np.zeros((height, width), dtype=np.float32)
    else:
        # Local structural contrast / edge density using cv2.Sobel
        dx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        dy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad = np.sqrt(dx * dx + dy * dy)

        # Smooth local density
        k_size = max(5, min(31, int(min(width, height) * 0.02) | 1))
        blurred = cv2.GaussianBlur(grad, (k_size, k_size), 0)

        # Normalize across valid pixels into [0.1, 1.0]
        v_min = float(np.percentile(blurred[valid_mask], 2))
        v_max = float(np.percentile(blurred[valid_mask], 98))
        span = max(v_max - v_min, 1e-5)

        norm_grad = np.clip((blurred - v_min) / span, 0.0, 1.0)
        quality_map = np.where(valid_mask, 0.15 + 0.85 * norm_grad, 0.0).astype(np.float32)

    # Update profile for single-band float32 GeoTIFF
    profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=0.0,
        compress="lzw",
    )

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(quality_map, 1)
        dst.update_tags(
            label=LABEL_ESTIMATED_QUALITY,
            metric=METRIC_NAME,
            disclaimer="Estimated quality indicator only; never to be construed as surveyed positional accuracy.",
        )

    valid_vals = quality_map[valid_mask] if valid_mask.any() else np.array([0.0])
    summary = {
        "out_path": str(out_path),
        "label": LABEL_ESTIMATED_QUALITY,
        "crs": str(crs),
        "width": width,
        "height": height,
        "valid_pixels": int(np.sum(valid_mask)),
        "min": float(np.min(valid_vals)),
        "max": float(np.max(valid_vals)),
        "mean": float(np.mean(valid_vals)),
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--orthophoto", type=Path, required=True, help="Input orthophoto GeoTIFF")
    ap.add_argument("--out", type=Path, required=True, help="Output spatial confidence GeoTIFF")
    ap.add_argument("--accuracy", type=Path, default=None, help="Optional accuracy.json path")
    args = ap.parse_args()

    summary = generate_spatial_confidence(args.orthophoto, args.out, accuracy_path=args.accuracy)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

