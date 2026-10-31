"""Tests for spatial confidence layer (T14 / F5).

Asserts:
- Output is labelled strictly as "estimated quality indicator", never "accuracy".
- Output is a valid single-band float32 GeoTIFF.
- Raster pixel values are bounded within [0.0, 1.0].
"""
from __future__ import annotations

from pathlib import Path
import rasterio

from quality.spatial_confidence import (
    LABEL_ESTIMATED_QUALITY,
    METRIC_NAME,
    generate_spatial_confidence,
)

ROOT = Path(__file__).resolve().parent.parent


def test_t14_spatial_confidence_on_real_southfork_sample(tmp_path: Path) -> None:
    ortho_path = ROOT / "samples" / "southfork_f01_4" / "orthophoto_small.tif"
    if not ortho_path.is_file():
        return

    out_tif = tmp_path / "southfork_spatial_confidence.tif"
    summary = generate_spatial_confidence(ortho_path, out_tif)

    # 1. Honest naming requirement: must be "estimated quality indicator", never "accuracy"
    assert summary["label"] == LABEL_ESTIMATED_QUALITY
    assert "accuracy" not in summary["label"].lower()
    assert "accuracy" not in METRIC_NAME.lower()

    # 2. File exists and valid GeoTIFF
    assert out_tif.is_file()
    with rasterio.open(out_tif) as src:
        assert src.count == 1
        assert src.dtypes[0] == "float32"
        tags = src.tags()
        assert tags.get("label") == "estimated quality indicator"
        assert "accuracy" not in tags.get("label", "").lower()

        arr = src.read(1)
        valid = arr[arr > 0]
        assert len(valid) > 0
        assert (valid >= 0.0).all() and (valid <= 1.05).all()

        with rasterio.open(ortho_path) as orig:
            assert src.crs == orig.crs
            assert src.width == orig.width
            assert src.height == orig.height
