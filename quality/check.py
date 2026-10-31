"""Per-image and dataset-level photogrammetric quality & coverage checker (T12).

Imports blur (Laplacian variance) and brightness (mean luminance) directly from
pipeline/frame_quality.py without re-implementing them, and adds:
  - Batch GPS & camera EXIF validation via exiftool (with Pillow EXIF fallback)
  - 256-bin exposure histogram clipping checks (overexposed / crushed dark / no_texture)
  - Sequential/spatial neighbour overlap via OpenCV ORB + RANSAC homography
  - Metric ground footprint coverage & optional uncovered_geojson polygon export

Usage:
    uv run python -m quality.check <image_dir_or_mp4> --out image_quality.json
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from PIL import Image
from pyproj import CRS, Transformer
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import unary_union

from pipeline import frame_quality

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_THRESHOLDS_PATH = Path(__file__).resolve().parent / "thresholds.yaml"
EXIFTOOL_FALLBACK = Path.home() / "AppData/Local/Programs/ExifTool/ExifTool.exe"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_THRESHOLDS_PATH
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def _find_exiftool() -> str | None:
    exe = shutil.which("exiftool")
    if exe:
        return exe
    if EXIFTOOL_FALLBACK.exists():
        return str(EXIFTOOL_FALLBACK)
    return None


def _dms_to_deg(val: Any, ref: str | None) -> float | None:
    try:
        if isinstance(val, (int, float)):
            deg = float(val)
        elif isinstance(val, (tuple, list)) and len(val) == 3:
            def _to_f(x: Any) -> float:
                if hasattr(x, "numerator") and hasattr(x, "denominator"):
                    return float(x.numerator) / float(x.denominator) if x.denominator else 0.0
                if isinstance(x, (tuple, list)) and len(x) == 2:
                    return float(x[0]) / float(x[1]) if x[1] else 0.0
                return float(x)

            d, m, s = _to_f(val[0]), _to_f(val[1]), _to_f(val[2])
            deg = d + m / 60.0 + s / 3600.0
        else:
            return None
        if ref and str(ref).upper().startswith(("S", "W")):
            deg = -abs(deg)
        return deg
    except Exception:
        return None


def _pillow_exif_metadata(img_path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "lat": None,
        "lon": None,
        "rel_alt_m": None,
        "focal_35mm": None,
        "metadata_source": "pillow_exif",
    }
    try:
        with Image.open(img_path) as im:
            exif = im.getexif()
            if not exif:
                return meta
            # FocalLengthIn35mmFilm = 41989
            if 41989 in exif and exif[41989]:
                meta["focal_35mm"] = float(exif[41989])
            gps_ifd = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else {}
            if gps_ifd:
                lat = _dms_to_deg(gps_ifd.get(2), gps_ifd.get(1))
                lon = _dms_to_deg(gps_ifd.get(4), gps_ifd.get(3))
                if lat is not None and lon is not None and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    meta["lat"] = lat
                    meta["lon"] = lon
                alt_raw = gps_ifd.get(6)
                if alt_raw is not None:
                    try:
                        alt_val = float(alt_raw)
                        if gps_ifd.get(5) in (1, b"\x01"):
                            alt_val = -abs(alt_val)
                        if 1.0 <= alt_val <= 500.0:
                            meta["rel_alt_m"] = alt_val
                    except Exception:
                        pass
    except Exception:
        pass
    return meta


def extract_batch_metadata(image_paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Extract GPS & camera optics metadata per image via exiftool (fallback: Pillow EXIF)."""
    if not image_paths:
        return {}

    exe = _find_exiftool()
    out_map: dict[str, dict[str, Any]] = {}
    if exe is not None:
        try:
            proc = subprocess.run(
                [
                    exe,
                    "-j",
                    "-n",
                    "-GPSLatitude",
                    "-GPSLongitude",
                    "-RelativeAltitude",
                    "-GPSAltitude",
                    "-FocalLengthIn35mmFormat",
                    "-FOV",
                    *[str(p) for p in image_paths],
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                rows = json.loads(proc.stdout)
                for row in rows:
                    name = Path(row.get("SourceFile", "")).name
                    lat = row.get("GPSLatitude")
                    lon = row.get("GPSLongitude")
                    rel_alt = row.get("RelativeAltitude")
                    if rel_alt is not None:
                        try:
                            rel_alt = abs(float(str(rel_alt).lstrip("+")))
                        except ValueError:
                            rel_alt = None
                    out_map[name] = {
                        "lat": float(lat) if isinstance(lat, (int, float)) else None,
                        "lon": float(lon) if isinstance(lon, (int, float)) else None,
                        "rel_alt_m": rel_alt if isinstance(rel_alt, (int, float)) and rel_alt > 0 else None,
                        "focal_35mm": float(row["FocalLengthIn35mmFormat"])
                        if isinstance(row.get("FocalLengthIn35mmFormat"), (int, float))
                        else None,
                        "fov_deg": float(row["FOV"])
                        if isinstance(row.get("FOV"), (int, float))
                        else None,
                        "metadata_source": "exiftool",
                    }
        except Exception:
            out_map = {}

    for p in image_paths:
        if p.name not in out_map or out_map[p.name].get("lat") is None:
            fb = _pillow_exif_metadata(p)
            if p.name not in out_map or fb.get("lat") is not None:
                out_map[p.name] = fb
    return out_map


def exposure_histogram_metrics(gray: np.ndarray, exp_cfg: dict[str, Any]) -> dict[str, float]:
    """Compute 256-bin grayscale histogram clipping fractions and contrast std-dev."""
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    total = float(max(gray.size, 1))
    hi_bin = int(exp_cfg.get("highlight_clip_luma", 250))
    lo_bin = int(exp_cfg.get("shadow_clip_luma", 5))
    over_frac = float(hist[hi_bin:].sum() / total)
    under_frac = float(hist[: lo_bin + 1].sum() / total)
    luma_std = float(gray.std())
    return {
        "overexposed_fraction": over_frac,
        "shadow_clip_fraction": under_frac,
        "luma_std": luma_std,
    }


def evaluate_gray_frame(
    name: str,
    gray: np.ndarray,
    thresholds: dict[str, Any],
    missing_expected_gps: bool = False,
) -> dict[str, Any]:
    """Score a single grayscale image using pipeline.frame_quality.measure + exposure histogram."""
    # Import blur and mean brightness from pipeline/frame_quality.py (no re-implementation).
    base = frame_quality.measure(gray)
    mean_luma = float(base["mean_luma"])
    lap_var = float(base["laplacian_var"])

    sharp_cfg = thresholds["sharpness"]
    exp_cfg = thresholds["exposure"]
    hist_m = exposure_histogram_metrics(gray, exp_cfg)

    reasons: list[str] = []

    if (
        lap_var < float(sharp_cfg["no_texture_laplacian_var_below"])
        and hist_m["luma_std"] < float(sharp_cfg["no_texture_luma_std_below"])
    ):
        reasons.append("no_texture")
    elif lap_var < float(sharp_cfg["blurry_laplacian_var_below"]):
        reasons.append("blur")

    if (
        mean_luma < float(exp_cfg["dark_mean_luma_below"])
        or hist_m["shadow_clip_fraction"] > float(exp_cfg["max_shadow_clip_fraction"])
    ):
        reasons.append("dark")

    if (
        mean_luma > float(exp_cfg["overexposed_mean_luma_above"])
        or hist_m["overexposed_fraction"] > float(exp_cfg["max_overexposed_fraction"])
    ):
        reasons.append("overexposed")

    if missing_expected_gps:
        reasons.append("other")

    # Continuous quality score in [0, 1] combining sharpness and well-centered exposure.
    sharp_score = min(1.0, lap_var / max(float(sharp_cfg["reference_good_laplacian_var"]), 1.0))
    luma_penalty = abs(mean_luma - 128.0) / 128.0
    clip_penalty = min(1.0, hist_m["overexposed_fraction"] * 2.0 + hist_m["shadow_clip_fraction"])
    exp_score = max(0.0, 1.0 - 0.5 * luma_penalty - 0.5 * clip_penalty)
    score = round(float(max(0.0, min(1.0, 0.65 * sharp_score + 0.35 * exp_score))), 4)
    if reasons:
        score = round(min(score, 0.45), 4)

    return {
        "image": name,
        "score": score,
        "usable": len(reasons) == 0,
        "reasons": reasons,
    }


def _downscale_for_orb(gray: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = gray.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return gray
    scale = max_dim / float(longest)
    return cv2.resize(gray, (max(16, int(w * scale)), max(16, int(h * scale))), interpolation=cv2.INTER_AREA)


def estimate_orb_overlap_fraction(
    gray_a: np.ndarray,
    gray_b: np.ndarray,
    orb_cfg: dict[str, Any],
) -> float:
    """Estimate fractional overlap [0, 1] between two neighbour frames via ORB + RANSAC homography."""
    max_dim = int(orb_cfg.get("orb_max_dim_px", 800))
    im1 = _downscale_for_orb(gray_a, max_dim)
    im2 = _downscale_for_orb(gray_b, max_dim)

    orb = cv2.ORB_create(nfeatures=int(orb_cfg.get("orb_nfeatures", 1200)))
    kp1, des1 = orb.detectAndCompute(im1, None)
    kp2, des2 = orb.detectAndCompute(im2, None)
    if des1 is None or des2 is None or len(kp1) < 8 or len(kp2) < 8:
        return 0.0

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    knn = matcher.knnMatch(des1, des2, k=2)
    ratio = float(orb_cfg.get("lowe_ratio", 0.75))
    good = [m for pair in knn if len(pair) == 2 for m, n in [pair] if m.distance < ratio * n.distance]
    min_inliers = int(orb_cfg.get("min_inlier_matches", 10))
    if len(good) < min_inliers:
        return 0.0

    pts1 = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(pts1, pts2, cv2.RANSAC, 5.0)
    if H is None or mask is None or int(mask.sum()) < min_inliers:
        return 0.0

    h1, w1 = im1.shape[:2]
    h2, w2 = im2.shape[:2]
    corners1 = np.float32([[0, 0], [w1, 0], [w1, h1], [0, h1]]).reshape(-1, 1, 2)
    warped = cv2.perspectiveTransform(corners1, H).reshape(-1, 2)
    if not np.all(np.isfinite(warped)):
        return 0.0

    poly_warped = Polygon(warped)
    if not poly_warped.is_valid:
        poly_warped = poly_warped.buffer(0)
    frame2 = box(0.0, 0.0, float(w2), float(h2))
    if poly_warped.is_empty or frame2.area <= 0:
        return 0.0
    inter_area = poly_warped.intersection(frame2).area
    return float(max(0.0, min(1.0, inter_area / frame2.area)))


def _compute_footprint_coverage(
    items: list[dict[str, Any]],
    meta_by_name: dict[str, dict[str, Any]],
    dims_by_name: dict[str, tuple[int, int]],
    thresholds: dict[str, Any],
    low_overlap_pairs: list[list[str]],
    target_geojson_path: Path | None = None,
    uncovered_out_path: Path | None = None,
) -> dict[str, Any]:
    fp_cfg = thresholds["footprint"]
    default_agl = float(fp_cfg.get("default_agl_m", 60.0))
    default_hfov = float(fp_cfg.get("default_hfov_deg", 73.7))

    geotagged = [
        it["image"]
        for it in items
        if meta_by_name.get(it["image"], {}).get("lat") is not None
        and meta_by_name.get(it["image"], {}).get("lon") is not None
    ]
    if not geotagged:
        return {
            "target_area_m2": None,
            "covered_area_m2": None,
            "coverage_fraction": None,
            "low_overlap_pairs": low_overlap_pairs,
            "uncovered_geojson": None,
            "method": "orb_sequential_overlap_only (no embedded EXIF GPS for metric ground footprints)",
        }

    lat0 = float(np.mean([meta_by_name[n]["lat"] for n in geotagged]))
    lon0 = float(np.mean([meta_by_name[n]["lon"] for n in geotagged]))
    local_crs = CRS.from_proj4(f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +datum=WGS84 +units=m +no_defs")
    to_m = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
    to_wgs = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True)

    usable_by_name = {it["image"]: bool(it["usable"]) for it in items}
    all_boxes: list[Polygon] = []
    usable_boxes: list[Polygon] = []

    for name in geotagged:
        m = meta_by_name[name]
        cx, cy = to_m.transform(float(m["lon"]), float(m["lat"]))
        agl = float(m.get("rel_alt_m") or default_agl)
        if m.get("fov_deg"):
            hfov_rad = math.radians(float(m["fov_deg"]))
        elif m.get("focal_35mm"):
            hfov_rad = 2.0 * math.atan(18.0 / max(float(m["focal_35mm"]), 1.0))
        else:
            hfov_rad = math.radians(default_hfov)
        w_px, h_px = dims_by_name.get(name, (4000, 3000))
        aspect = float(h_px) / max(float(w_px), 1.0)
        ground_w = max(2.0 * agl * math.tan(hfov_rad / 2.0), 2.0)
        ground_h = max(ground_w * aspect, 2.0)
        fp = box(cx - ground_w / 2.0, cy - ground_h / 2.0, cx + ground_w / 2.0, cy + ground_h / 2.0)
        all_boxes.append(fp)
        if usable_by_name.get(name, False):
            usable_boxes.append(fp)

    covered_geom = unary_union(usable_boxes) if usable_boxes else Polygon()

    if target_geojson_path is not None and target_geojson_path.exists():
        raw_gj = json.loads(target_geojson_path.read_text(encoding="utf-8"))
        geoms_wgs = (
            [shape(f["geometry"]) for f in raw_gj["features"]]
            if raw_gj.get("type") == "FeatureCollection"
            else [shape(raw_gj["geometry"] if "geometry" in raw_gj else raw_gj)]
        )
        proj_polys: list[Polygon] = []
        for g in geoms_wgs:
            if isinstance(g, Polygon):
                ext = [to_m.transform(x, y) for x, y in g.exterior.coords]
                proj_polys.append(Polygon(ext))
        target_geom = unary_union(proj_polys)
        method_desc = "exif_nadir_footprints_vs_target_aoi + orb_homography_overlap (PLACEHOLDER AGL/FOV where missing)"
    else:
        # Envelope across all planned/flown camera footprints (so dropped frames expose real coverage gaps).
        target_geom = unary_union(all_boxes).convex_hull if len(all_boxes) >= 2 else unary_union(all_boxes)
        method_desc = "exif_nadir_footprints_vs_flight_hull + orb_homography_overlap (PLACEHOLDER AGL/FOV where missing)"

    target_area = float(target_geom.area)
    covered_in_target = covered_geom.intersection(target_geom) if not covered_geom.is_empty else Polygon()
    covered_area = float(covered_in_target.area)
    cov_frac = round(max(0.0, min(1.0, covered_area / target_area)), 4) if target_area > 0 else None

    uncovered_str: str | None = None
    if uncovered_out_path is not None and target_area > 0:
        diff_geom = target_geom.difference(covered_geom)
        if not diff_geom.is_empty and diff_geom.area > 0.01:
            polys = [diff_geom] if isinstance(diff_geom, Polygon) else (
                list(diff_geom.geoms) if isinstance(diff_geom, MultiPolygon) else []
            )
            wgs_polys = []
            for p in polys:
                ext_wgs = [to_wgs.transform(x, y) for x, y in p.exterior.coords]
                holes_wgs = [[to_wgs.transform(x, y) for x, y in ring.coords] for ring in p.interiors]
                wgs_polys.append(Polygon(ext_wgs, holes_wgs))
            if wgs_polys:
                fc = {
                    "type": "FeatureCollection",
                    "features": [
                        {"type": "Feature", "properties": {}, "geometry": mapping(wp)}
                        for wp in wgs_polys
                    ],
                }
                uncovered_out_path.parent.mkdir(parents=True, exist_ok=True)
                uncovered_out_path.write_text(json.dumps(fc, indent=2), encoding="utf-8")
                uncovered_str = str(uncovered_out_path)

    return {
        "target_area_m2": round(target_area, 2),
        "covered_area_m2": round(covered_area, 2),
        "coverage_fraction": cov_frac,
        "low_overlap_pairs": low_overlap_pairs,
        "uncovered_geojson": uncovered_str,
        "method": method_desc,
    }


def check_image_directory(
    folder: Path,
    thresholds: dict[str, Any] | None = None,
    target_geojson_path: Path | None = None,
    uncovered_out_path: Path | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Run T12 image + metadata + exposure + ORB overlap + footprint coverage check on an image folder."""
    cfg = thresholds or load_thresholds()
    img_paths = sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS],
        key=lambda p: p.name,
    )
    meta_by_name = extract_batch_metadata(img_paths)
    any_gps = any(m.get("lat") is not None and m.get("lon") is not None for m in meta_by_name.values())

    items: list[dict[str, Any]] = []
    grays_by_name: dict[str, np.ndarray] = {}
    dims_by_name: dict[str, tuple[int, int]] = {}

    for p in img_paths:
        # Read via numpy buffer so Unicode Windows paths work reliably in OpenCV
        raw_bytes = np.frombuffer(p.read_bytes(), dtype=np.uint8)
        gray = cv2.imdecode(raw_bytes, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            items.append(
                {
                    "image": p.name,
                    "score": 0.0,
                    "usable": False,
                    "reasons": ["other"],
                }
            )
            continue

        h, w = gray.shape[:2]
        dims_by_name[p.name] = (w, h)
        grays_by_name[p.name] = gray
        has_gps = (
            meta_by_name.get(p.name, {}).get("lat") is not None
            and meta_by_name.get(p.name, {}).get("lon") is not None
        )
        items.append(
            evaluate_gray_frame(
                name=p.name,
                gray=gray,
                thresholds=cfg,
                missing_expected_gps=(any_gps and not has_gps),
            )
        )

    # Check ORB overlap across sequential usable neighbours
    usable_names = [it["image"] for it in items if it["usable"] and it["image"] in grays_by_name]
    low_overlap_pairs: list[list[str]] = []
    min_ov = float(cfg["overlap_orb"]["min_overlap_fraction"])
    for idx in range(len(usable_names) - 1):
        na, nb = usable_names[idx], usable_names[idx + 1]
        ov = estimate_orb_overlap_fraction(grays_by_name[na], grays_by_name[nb], cfg["overlap_orb"])
        if ov < min_ov:
            low_overlap_pairs.append([na, nb])

    coverage = _compute_footprint_coverage(
        items=items,
        meta_by_name=meta_by_name,
        dims_by_name=dims_by_name,
        thresholds=cfg,
        low_overlap_pairs=low_overlap_pairs,
        target_geojson_path=target_geojson_path,
        uncovered_out_path=uncovered_out_path,
    )

    return {
        "mock": mock,
        "method": "standard_check",
        "model": None,
        "version": "0.1.0",
        "source": str(folder),
        "coverage": coverage,
        "items": items,
    }


def check_video_file(
    video_path: Path,
    n_frames: int = 24,
    thresholds: dict[str, Any] | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Run T12 frame quality & ORB sequential overlap check on an MP4 drone clip via pipeline/frame_quality.py."""
    cfg = thresholds or load_thresholds()
    probe_raw = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        check=True,
    ).stdout
    info = json.loads(probe_raw)
    v_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    width, height = int(v_stream["width"]), int(v_stream["height"])
    num, den = (int(x) for x in v_stream["r_frame_rate"].split("/"))
    fps = num / max(den, 1)
    duration_s = float(info["format"]["duration"])

    items: list[dict[str, Any]] = []
    grays: dict[str, np.ndarray] = {}

    for k in range(n_frames):
        t_s = (k + 0.5) * duration_s / max(n_frames, 1)
        frame_idx = int(round(t_s * fps))
        label = f"video:{frame_idx}"
        gray = frame_quality.video_frame_gray(video_path, t_s, width, height)
        grays[label] = gray
        items.append(evaluate_gray_frame(name=label, gray=gray, thresholds=cfg))

    usable_labels = [it["image"] for it in items if it["usable"] and it["image"] in grays]
    low_overlap_pairs: list[list[str]] = []
    min_ov = float(cfg["overlap_orb"]["min_overlap_fraction"])
    for idx in range(len(usable_labels) - 1):
        la, lb = usable_labels[idx], usable_labels[idx + 1]
        ov = estimate_orb_overlap_fraction(grays[la], grays[lb], cfg["overlap_orb"])
        if ov < min_ov:
            low_overlap_pairs.append([la, lb])

    return {
        "mock": mock,
        "method": "standard_check",
        "model": None,
        "version": "0.1.0",
        "source": str(video_path),
        "coverage": {
            "target_area_m2": None,
            "covered_area_m2": None,
            "coverage_fraction": None,
            "low_overlap_pairs": low_overlap_pairs,
            "uncovered_geojson": None,
            "method": "orb_sequential_video_frame_overlap",
        },
        "items": items,
    }


def check_source(
    source: Path,
    out_path: Path | None = None,
    target_geojson_path: Path | None = None,
    frames: int = 24,
    thresholds: dict[str, Any] | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    uncov_path = out_path.with_name(f"{out_path.stem}_uncovered.geojson") if out_path else None
    if source.is_dir():
        res = check_image_directory(
            folder=source,
            thresholds=thresholds,
            target_geojson_path=target_geojson_path,
            uncovered_out_path=uncov_path,
            mock=mock,
        )
    elif source.is_file() and source.suffix.lower() in {".mp4", ".mov", ".mkv"}:
        res = check_video_file(video_path=source, n_frames=frames, thresholds=thresholds, mock=mock)
    else:
        raise ValueError(f"Unsupported quality check source: {source}")

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="Folder of survey images or path to MP4 clip")
    ap.add_argument("--out", type=Path, required=True, help="Output image_quality.json path")
    ap.add_argument("--target-geojson", type=Path, default=None, help="Optional target AOI polygon GeoJSON")
    ap.add_argument("--frames", type=int, default=24, help="Sampled frames when source is an MP4")
    ap.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS_PATH)
    args = ap.parse_args()

    cfg = load_thresholds(args.thresholds)
    res = check_source(
        source=args.source,
        out_path=args.out,
        target_geojson_path=args.target_geojson,
        frames=args.frames,
        thresholds=cfg,
    )
    usable_n = sum(1 for it in res["items"] if it["usable"])
    print(
        f"wrote {args.out}: {usable_n}/{len(res['items'])} usable, "
        f"coverage_fraction={res['coverage']['coverage_fraction']}, "
        f"low_overlap_pairs={len(res['coverage']['low_overlap_pairs'])}"
    )


if __name__ == "__main__":
    main()
