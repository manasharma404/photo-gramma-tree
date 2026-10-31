"""CRASAR road-damage ML crop preparation and predict CLI -> ml_scores.json (C3 / T15 groundwork).

Model card reference:
  - Name: CRASAR/CRASAR-U-DROIDs-RDA_AAAI26_Simple_VanillaUNet
  - Architecture: 4-channel MaskedUNet (RGB + 40-pixel road corridor mask)
  - URL: https://huggingface.co/CRASAR/CRASAR-U-DROIDs-RDA_AAAI26_Simple_VanillaUNet
  - Licence: MIT (explicitly declared on Hugging Face model card)

Honesty & fusion rules:
  1. Never invents probabilities: if local CRASAR weights (.onnx / .pt / .ckpt) or PyTorch/MMCV
     runtime are unavailable offline, emits schema-compliant null scores (p_blocked=null,
     p_partial=null, p_clear=null) rather than heuristic or random numbers.
  2. When fused in advisor/assess.py, a model NEVER flips geometric 'blocked' to 'open', and
     any geometry/ML disagreement sets needs_verification=true.

Usage:
    uv run python -m ml.road_damage --crops-dir <dir> --out ml_scores.json
    uv run python -m ml.road_damage --segments segments.geojson --ortho ortho.tif --out ml_scores.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.windows import Window
from shapely.geometry import LineString, shape

CRASAR_MODEL_ID = "CRASAR/CRASAR-U-DROIDs-RDA_AAAI26_Simple_VanillaUNet"
CRASAR_MODEL_VERSION = "AAAI26-MaskedUNet-MIT"
CRASAR_MODEL_LICENCE = "MIT"
CRASAR_ROAD_WIDTH_PX = 40
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def prepare_masked_unet_crop(
    bgr_crop: np.ndarray,
    centerline_px: list[tuple[float, float]] | None = None,
    target_size: int = 256,
    road_width_px: int = CRASAR_ROAD_WIDTH_PX,
) -> np.ndarray:
    """Build normalized (4, H, W) float32 tensor [R, G, B, road_mask] matching CRASAR MaskedUNet."""
    if bgr_crop is None or bgr_crop.size == 0:
        raise ValueError("Empty image crop passed to prepare_masked_unet_crop")

    h0, w0 = bgr_crop.shape[:2]
    rgb = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2RGB)
    rgb_resized = cv2.resize(rgb, (target_size, target_size), interpolation=cv2.INTER_LINEAR)

    mask = np.zeros((target_size, target_size), dtype=np.uint8)
    scaled_width = max(4, int(round(road_width_px * (target_size / max(float(max(h0, w0)), 1.0)))))

    if centerline_px and len(centerline_px) >= 2:
        pts = np.array(
            [
                [
                    int(round(px * target_size / max(w0, 1))),
                    int(round(py * target_size / max(h0, 1))),
                ]
                for px, py in centerline_px
            ],
            dtype=np.int32,
        )
        cv2.polylines(mask, [pts], isClosed=False, color=255, thickness=scaled_width)
    else:
        # Default horizontal corridor across crop centre when pre-cropped per segment_id
        cy = target_size // 2
        cv2.line(mask, (0, cy), (target_size - 1, cy), color=255, thickness=scaled_width)

    rgb_f = rgb_resized.astype(np.float32) / 255.0
    mask_f = (mask.astype(np.float32) / 255.0)[..., None]
    chw = np.transpose(np.concatenate([rgb_f, mask_f], axis=-1), (2, 0, 1))
    return chw


def extract_segment_crops_from_orthophoto(
    segments_fc: dict[str, Any],
    ortho_path: Path,
    pad_px: int = 48,
) -> dict[str, tuple[np.ndarray, list[tuple[float, float]]]]:
    """Extract georeferenced BGR crops and pixel centerlines per segment_id from an orthophoto."""
    crops: dict[str, tuple[np.ndarray, list[tuple[float, float]]]] = {}
    with rasterio.open(ortho_path) as src:
        to_src = (
            Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            if src.crs and str(src.crs).upper() != "EPSG:4326"
            else None
        )
        for feat in segments_fc.get("features", []):
            props = feat.get("properties") or {}
            sid = str(props["segment_id"])
            geom = shape(feat["geometry"]) if feat.get("geometry") else None
            if not isinstance(geom, LineString) or geom.is_empty:
                continue

            pts_src = [
                to_src.transform(float(x), float(y)) if to_src else (float(x), float(y))
                for x, y in geom.coords
            ]
            rows_cols = [src.index(mx, my) for mx, my in pts_src]
            rs = [r for r, _ in rows_cols]
            cs = [c for _, c in rows_cols]
            r0 = max(0, min(rs) - pad_px)
            r1 = min(src.height, max(rs) + pad_px)
            c0 = max(0, min(cs) - pad_px)
            c1 = min(src.width, max(cs) + pad_px)
            if r1 - r0 < 8 or c1 - c0 < 8:
                continue

            win = Window(col_off=c0, row_off=r0, width=c1 - c0, height=r1 - r0)
            bands = [1, 2, 3] if src.count >= 3 else [1, 1, 1]
            arr = src.read(bands, window=win)
            rgb = np.transpose(np.clip(arr, 0, 255).astype(np.uint8), (1, 2, 0))
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            local_line = [(float(c - c0), float(r - r0)) for r, c in rows_cols]
            crops[sid] = (bgr, local_line)
    return crops


def _softmax_channel(logits_chw: np.ndarray) -> np.ndarray:
    shifted = logits_chw - np.max(logits_chw, axis=0, keepdims=True)
    exps = np.exp(shifted)
    return exps / np.maximum(np.sum(exps, axis=0, keepdims=True), 1e-8)


def _aggregate_corridor_probabilities(
    probs_chw: np.ndarray,
    road_mask_hw: np.ndarray,
) -> tuple[float, float, float]:
    """Aggregate 3-class [clear, partial, blocked] pixel probabilities inside the road mask."""
    active = road_mask_hw > 0.5
    if not np.any(active):
        active = np.ones_like(road_mask_hw, dtype=bool)

    if probs_chw.shape[0] >= 3:
        p_clear = float(np.mean(probs_chw[0][active]))
        p_partial = float(np.mean(probs_chw[1][active]))
        p_blocked = float(np.mean(probs_chw[2][active]))
    elif probs_chw.shape[0] == 2:
        p_clear = float(np.mean(probs_chw[0][active]))
        p_blocked = float(np.mean(probs_chw[1][active]))
        p_partial = 0.0
    else:
        p_blocked = float(np.clip(np.mean(probs_chw[0][active]), 0.0, 1.0))
        p_clear = 1.0 - p_blocked
        p_partial = 0.0

    total = max(p_clear + p_partial + p_blocked, 1e-8)
    return (
        round(p_blocked / total, 4),
        round(p_partial / total, 4),
        round(p_clear / total, 4),
    )


def load_offline_predictor(
    checkpoint_path: Path | None,
) -> tuple[Callable[[np.ndarray], np.ndarray] | None, str]:
    """Load an offline ONNX (OpenCV DNN) or TorchScript CRASAR checkpoint if available."""
    if checkpoint_path is None or not checkpoint_path.is_file():
        return None, "no_local_checkpoint"

    suffix = checkpoint_path.suffix.lower()
    if suffix == ".onnx":
        net = cv2.dnn.readNetFromONNX(str(checkpoint_path))

        def _run_onnx(chw: np.ndarray) -> np.ndarray:
            net.setInput(chw[None, ...].astype(np.float32))
            out = net.forward()
            return _softmax_channel(np.asarray(out[0], dtype=np.float32))

        return _run_onnx, "opencv_dnn_onnx"

    if suffix in {".pt", ".pth", ".ckpt"}:
        try:
            import torch  # type: ignore[import-not-found]
        except ImportError:
            return None, "torch_not_installed_offline"

        model = torch.jit.load(str(checkpoint_path), map_location="cpu")
        model.eval()

        def _run_torch(chw: np.ndarray) -> np.ndarray:
            with torch.no_grad():
                inp = torch.from_numpy(chw[None, ...].astype(np.float32))
                out = model(inp)
                if isinstance(out, (tuple, list)):
                    out = out[0]
                arr = out[0].detach().cpu().numpy()
                return _softmax_channel(arr)

        return _run_torch, "torchscript_cpu"

    return None, f"unsupported_checkpoint_format:{suffix}"


def predict_crops_to_ml_scores(
    crops_by_segment: dict[str, tuple[np.ndarray, list[tuple[float, float]] | None]],
    *,
    checkpoint_path: Path | None = None,
    predictor_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    target_size: int = 256,
    mock: bool = False,
) -> dict[str, Any]:
    """Run CRASAR MaskedUNet predictor on segment crops -> schema-valid ml_scores.json."""
    fn = predictor_fn
    runtime_status = "custom_predictor"
    if fn is None:
        fn, runtime_status = load_offline_predictor(checkpoint_path)

    scores: list[dict[str, Any]] = []
    for sid in sorted(crops_by_segment.keys()):
        bgr, line_px = crops_by_segment[sid]
        chw = prepare_masked_unet_crop(bgr, centerline_px=line_px, target_size=target_size)
        if fn is None:
            # Hard Rule 1: Never invent probabilities when weights/runtime are absent.
            scores.append(
                {
                    "segment_id": sid,
                    "p_blocked": None,
                    "p_partial": None,
                    "p_clear": None,
                    "model": CRASAR_MODEL_ID,
                    "version": f"{CRASAR_MODEL_VERSION} ({runtime_status})",
                }
            )
        else:
            probs = fn(chw)
            p_blk, p_prt, p_clr = _aggregate_corridor_probabilities(probs, chw[3])
            scores.append(
                {
                    "segment_id": sid,
                    "p_blocked": p_blk,
                    "p_partial": p_prt,
                    "p_clear": p_clr,
                    "model": CRASAR_MODEL_ID,
                    "version": CRASAR_MODEL_VERSION,
                }
            )

    return {
        "mock": bool(mock),
        "scores": scores,
    }


def load_crops_directory(
    crops_dir: Path,
) -> dict[str, tuple[np.ndarray, list[tuple[float, float]] | None]]:
    out: dict[str, tuple[np.ndarray, list[tuple[float, float]] | None]] = {}
    for p in sorted(crops_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            bgr = cv2.imdecode(np.frombuffer(p.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
            if bgr is not None:
                out[p.stem] = (bgr, None)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crops-dir", type=Path, default=None, help="Directory of <segment_id>.{jpg,png,tif} crops")
    ap.add_argument("--segments", type=Path, default=None, help="segments.geojson (when cropping from --ortho)")
    ap.add_argument("--ortho", type=Path, default=None, help="Orthophoto GeoTIFF path")
    ap.add_argument("--checkpoint", type=Path, default=None, help="Optional local CRASAR .onnx or .pt weights")
    ap.add_argument("--target-size", type=int, default=256, help="Crop tensor height/width")
    ap.add_argument("--mock", action="store_true", help="Mark output ml_scores.json as mock")
    ap.add_argument("--out", type=Path, required=True, help="Output ml_scores.json path")
    args = ap.parse_args()

    if args.crops_dir is not None:
        crops = load_crops_directory(args.crops_dir)
    elif args.segments is not None and args.ortho is not None:
        seg_fc = json.loads(args.segments.read_text(encoding="utf-8"))
        raw_crops = extract_segment_crops_from_orthophoto(seg_fc, args.ortho)
        crops = {k: (v[0], v[1]) for k, v in raw_crops.items()}
    else:
        raise SystemExit("Provide either --crops-dir or both --segments and --ortho.")

    payload = predict_crops_to_ml_scores(
        crops,
        checkpoint_path=args.checkpoint,
        target_size=args.target_size,
        mock=args.mock,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    scored_n = sum(1 for s in payload["scores"] if s["p_blocked"] is not None)
    print(
        f"Wrote {args.out}: {len(payload['scores'])} segments "
        f"({scored_n} scored with local weights, {len(payload['scores']) - scored_n} null without weights)"
    )


if __name__ == "__main__":
    main()
