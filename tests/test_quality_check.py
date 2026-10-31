"""Tests for T12 image, EXIF GPS, exposure histogram, ORB overlap, and footprint coverage checker."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import jsonschema
import numpy as np
from PIL import Image

from pipeline import frame_quality
from quality import check as qcheck

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
IMAGE_QUALITY_SCHEMA = json.loads((CONTRACTS / "image_quality.schema.json").read_text(encoding="utf-8"))


def _make_gps_exif_bytes(lat: float, lon: float, alt_m: float = 60.0) -> bytes:
    """Create standard TIFF/EXIF bytes with GPSInfo IFD (0x8825) via Pillow."""
    def _deg_to_dms_rational(deg_abs: float):
        d = int(deg_abs)
        rem = (deg_abs - d) * 60.0
        m = int(rem)
        s = round((rem - m) * 60.0, 4)
        return (float(d), float(m), float(s))

    exif = Image.Exif()
    # FocalLengthIn35mmFilm = 24mm
    exif[41989] = 24
    exif[0x8825] = {
        1: "N" if lat >= 0 else "S",
        2: _deg_to_dms_rational(abs(lat)),
        3: "E" if lon >= 0 else "W",
        4: _deg_to_dms_rational(abs(lon)),
        5: 0,
        6: float(alt_m),
    }
    return exif.tobytes()


def _save_jpeg(path: Path, arr_u8: np.ndarray, gps: tuple[float, float] | None = None) -> None:
    im = Image.fromarray(arr_u8)
    if gps is not None:
        im.save(path, format="JPEG", quality=95, exif=_make_gps_exif_bytes(gps[0], gps[1]))
    else:
        im.save(path, format="JPEG", quality=95)


def _rich_textured_canvas(seed: int, h: int = 600, w: int = 800) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # Macro gradient + high-frequency grain + crisp geometric landmarks
    grad_x = np.linspace(60, 190, w, dtype=np.float32)[None, :]
    noise = rng.integers(-25, 26, size=(h, w), dtype=np.int16)
    canvas = np.clip(grad_x + noise, 20, 235).astype(np.uint8)
    for i in range(45):
        cx = int(rng.integers(30, w - 30))
        cy = int(rng.integers(30, h - 30))
        r = int(rng.integers(8, 28))
        val = int(rng.integers(35, 220))
        cv2.rectangle(canvas, (cx - r, cy - r), (cx + r, cy + r), val, 2)
        cv2.circle(canvas, (cx, cy), max(3, r // 2), 255 - val, -1)
    return canvas


def test_quality_check_imports_pipeline_frame_quality():
    assert qcheck.frame_quality is frame_quality


def test_image_directory_quality_orb_overlap_and_coverage_validates_contract(tmp_path: Path):
    survey_dir = tmp_path / "survey"
    survey_dir.mkdir()

    # Large textured terrain scene: img_01 and img_02 share ~85% overlap (shifted by 60 px out of 500 px)
    terrain_a = _rich_textured_canvas(seed=42, h=500, w=700)
    crop_1 = terrain_a[:, 0:500]
    crop_2 = terrain_a[:, 60:560]

    # Separate unrelated scene for img_03 -> low ORB overlap with img_02!
    terrain_b = _rich_textured_canvas(seed=999, h=500, w=500)

    # Bad frames: blurry, dark, overexposed, flat/no_texture, and missing GPS
    blurry = cv2.GaussianBlur(crop_1, (19, 19), 5.0)
    dark = np.clip(crop_1.astype(np.int16) - 170, 0, 25).astype(np.uint8)
    overexp = np.full((500, 500), 253, dtype=np.uint8)
    # Add high-frequency bright noise on half so it isn't only no_texture, testing overexposed histogram clipping
    overexp[:250, :250] = crop_1[:250, :250]
    overexp[100:, :] = 254
    flat_grey = np.full((500, 500), 128, dtype=np.uint8)

    _save_jpeg(survey_dir / "img_01.jpg", crop_1, gps=(11.4990, 76.1590))
    _save_jpeg(survey_dir / "img_02.jpg", crop_2, gps=(11.4992, 76.1592))
    _save_jpeg(survey_dir / "img_03.jpg", terrain_b, gps=(11.4994, 76.1594))
    _save_jpeg(survey_dir / "img_04_blur.jpg", blurry, gps=(11.4998, 76.1598))
    _save_jpeg(survey_dir / "img_05_dark.jpg", dark, gps=(11.5002, 76.1602))
    _save_jpeg(survey_dir / "img_06_overexp.jpg", overexp, gps=(11.5004, 76.1604))
    _save_jpeg(survey_dir / "img_07_flat.jpg", flat_grey, gps=(11.5006, 76.1606))
    _save_jpeg(survey_dir / "img_08_nogps.jpg", crop_1, gps=None)

    out_json = tmp_path / "image_quality.json"
    res = qcheck.check_source(survey_dir, out_path=out_json)

    jsonschema.validate(res, IMAGE_QUALITY_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert res["method"] == "standard_check"
    assert res["model"] is None

    by_name = {it["image"]: it for it in res["items"]}
    assert by_name["img_01.jpg"]["usable"] is True
    assert by_name["img_02.jpg"]["usable"] is True
    assert by_name["img_03.jpg"]["usable"] is True

    assert by_name["img_04_blur.jpg"]["usable"] is False
    assert "blur" in by_name["img_04_blur.jpg"]["reasons"]

    assert by_name["img_05_dark.jpg"]["usable"] is False
    assert "dark" in by_name["img_05_dark.jpg"]["reasons"]

    assert by_name["img_06_overexp.jpg"]["usable"] is False
    assert "overexposed" in by_name["img_06_overexp.jpg"]["reasons"]

    assert by_name["img_07_flat.jpg"]["usable"] is False
    assert "no_texture" in by_name["img_07_flat.jpg"]["reasons"]

    assert by_name["img_08_nogps.jpg"]["usable"] is False
    assert "other" in by_name["img_08_nogps.jpg"]["reasons"]

    # Coverage & ORB overlap checks:
    cov = res["coverage"]
    assert cov is not None
    assert ["img_01.jpg", "img_02.jpg"] not in cov["low_overlap_pairs"]
    assert ["img_02.jpg", "img_03.jpg"] in cov["low_overlap_pairs"]
    assert cov["target_area_m2"] > 0
    assert 0.0 < cov["coverage_fraction"] < 1.0
    assert cov["uncovered_geojson"] is not None
    assert Path(cov["uncovered_geojson"]).is_file()


def test_non_geotagged_folder_reports_null_footprint_metrics_never_zero(tmp_path: Path):
    folder = tmp_path / "frames_no_gps"
    folder.mkdir()
    scene = _rich_textured_canvas(seed=7, h=400, w=500)
    _save_jpeg(folder / "f001.jpg", scene[:, :400], gps=None)
    _save_jpeg(folder / "f002.jpg", scene[:, 40:440], gps=None)

    res = qcheck.check_source(folder)
    jsonschema.validate(res, IMAGE_QUALITY_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert res["coverage"]["target_area_m2"] is None
    assert res["coverage"]["covered_area_m2"] is None
    assert res["coverage"]["coverage_fraction"] is None
    assert res["coverage"]["low_overlap_pairs"] == []


def test_t13_ml_comparison_gate_requires_ml_to_beat_standard_check():
    from ml.benchmark_iqa import compare_predictions

    labels = {"f1.jpg": True, "f2.jpg": True, "f3.jpg": False, "f4.jpg": False}
    std_preds = {"f1.jpg": True, "f2.jpg": True, "f3.jpg": False, "f4.jpg": True}  # 3/4
    ml_worse = {"f1.jpg": True, "f2.jpg": False, "f3.jpg": False, "f4.jpg": True}  # 2/4
    ml_better = {"f1.jpg": True, "f2.jpg": True, "f3.jpg": False, "f4.jpg": False}  # 4/4

    rep_keep = compare_predictions(labels, std_preds, ml_worse)
    assert rep_keep["ml_beats_standard_check"] is False
    assert rep_keep["selected_method"] == "standard_check"
    assert rep_keep["model_metadata"]["model"] == "opencv-QualityBRISQUE-svr-live-r2"

    rep_win = compare_predictions(labels, std_preds, ml_better)
    assert rep_win["ml_beats_standard_check"] is True
    assert rep_win["selected_method"] == "ml_model"
