"""Score road segments for landslide debris from drone orthophoto (F3 Part 1).

Measures debris coverage inside each segment's corridor polygon using typhon_debris_resnet18.pt,
applies the documented corridor_debris_fraction rule, saves one visual evidence crop per segment,
and writes schema-valid ml_scores.json (contracts/ml_scores.schema.json).

Usage:
    python ml/score_segments.py
    python ml/score_segments.py --project southfork_f01_4
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import cv2
import jsonschema
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
import shapely
from shapely.geometry import box, shape
import torch
import torch.nn as nn
import torchvision.models as models

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHTS = ROOT / "models" / "typhon_debris_resnet18.pt"
SCHEMA_PATH = ROOT / "contracts" / "ml_scores.schema.json"


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class ResNet18UNet(nn.Module):
    """Lightweight U-Net with ResNet-18 encoder for debris segmentation."""

    def __init__(self, in_channels: int = 3, num_classes: int = 1):
        super().__init__()
        base = models.resnet18(weights=None)
        self.in_block = nn.Sequential(base.conv1, base.bn1, base.relu)
        self.maxpool = base.maxpool
        self.layer1 = base.layer1
        self.layer2 = base.layer2
        self.layer3 = base.layer3
        self.layer4 = base.layer4

        self.up4 = nn.ConvTranspose2d(512, 256, 2, stride=2)
        self.dec4 = ConvBlock(256 + 256, 256)

        self.up3 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.dec3 = ConvBlock(128 + 128, 128)

        self.up2 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec2 = ConvBlock(64 + 64, 64)

        self.up1 = nn.ConvTranspose2d(64, 64, 2, stride=2)
        self.dec1 = ConvBlock(64 + 64, 64)

        self.final_up = nn.ConvTranspose2d(64, 32, 2, stride=2)
        self.final_conv = nn.Sequential(
            ConvBlock(32, 32),
            nn.Conv2d(32, num_classes, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.in_block(x)
        x1 = self.layer1(self.maxpool(x0))
        x2 = self.layer2(x1)
        x3 = self.layer3(x2)
        x4 = self.layer4(x3)

        d4 = self.dec4(torch.cat([self.up4(x4), x3], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), x2], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), x1], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), x0], dim=1))
        return self.final_conv(self.final_up(d1))


def load_model(weights_path: Path, device: torch.device) -> nn.Module:
    model = ResNet18UNet(in_channels=3, num_classes=1)
    state = torch.load(weights_path, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device)
    model.eval()
    return model


def pad_to_multiple_of_32(img: np.ndarray) -> tuple[np.ndarray, int, int]:
    h, w = img.shape[:2]
    pad_h = (32 - (h % 32)) % 32
    pad_w = (32 - (w % 32)) % 32
    if pad_h > 0 or pad_w > 0:
        if img.ndim == 3:
            padded = np.pad(img, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
        else:
            padded = np.pad(img, ((0, pad_h), (0, pad_w)), mode="reflect")
        return padded, pad_h, pad_w
    return img, 0, 0


def score_corridor_debris(
    model: nn.Module,
    rgb_crop: np.ndarray,
    corridor_mask: np.ndarray,
    gsd_m: float,
    device: torch.device,
) -> tuple[float, np.ndarray]:
    """Score debris fraction in corridor and return (fraction, full_res_debris_mask)."""
    h, w = rgb_crop.shape[:2]
    # Resize to training resolution 0.20 m/px
    scale = gsd_m / 0.20
    target_w = max(32, round(w * scale))
    target_h = max(32, round(h * scale))
    scaled_rgb = cv2.resize(rgb_crop, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    # Pad to multiple of 32
    padded_rgb, pad_h, pad_w = pad_to_multiple_of_32(scaled_rgb)

    # Normalize ImageNet
    img_f = padded_rgb.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img_norm = (img_f - mean) / std

    tensor = torch.from_numpy(img_norm.transpose(2, 0, 1)).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits).squeeze().cpu().numpy()

    # Unpad
    if pad_h > 0 or pad_w > 0:
        probs = probs[:target_h, :target_w]

    # Resize probabilities back to full resolution of the crop
    probs_orig = cv2.resize(probs, (w, h), interpolation=cv2.INTER_LINEAR)
    debris_binary = (probs_orig > 0.5)

    corridor_pixels = np.sum(corridor_mask)
    if corridor_pixels < 5:
        return 0.0, debris_binary

    debris_in_corridor = np.sum(debris_binary & corridor_mask)
    fraction = float(debris_in_corridor / corridor_pixels)
    return fraction, debris_binary


def make_evidence_crop(
    rgb_crop: np.ndarray,
    corridor_mask: np.ndarray,
    debris_mask: np.ndarray,
    segment_id: str,
    fraction: float,
    status: str,
    out_path: Path,
) -> None:
    """Save an evidence JPEG showing corridor boundary, model debris mask, and metrics overlay."""
    vis = rgb_crop.copy()

    # Highlight debris in orange/red (BGR: 0, 80, 255)
    overlay = vis.copy()
    overlay[debris_mask] = (0.3 * overlay[debris_mask] + 0.7 * np.array([0, 80, 255])).astype(np.uint8)
    vis = cv2.addWeighted(overlay, 0.7, vis, 0.3, 0)

    # Find corridor contours and draw in cyan
    contours, _ = cv2.findContours(corridor_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vis, contours, -1, (255, 255, 0), 2)  # Cyan corridor boundary

    # Draw status badge on top
    h, w = vis.shape[:2]
    header = np.zeros((45, w, 3), dtype=np.uint8)
    color_map = {
        "clear": (40, 180, 40),
        "partial": (0, 165, 255),
        "blocked": (30, 30, 220),
    }
    badge_color = color_map.get(status, (200, 200, 200))
    cv2.rectangle(header, (0, 0), (w, 45), (30, 30, 30), -1)
    label_text = f"{segment_id} | Debris: {fraction*100:.1f}% | {status.upper()}"
    cv2.putText(header, label_text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, badge_color, 2, cv2.LINE_AA)

    combined = np.vstack([header, vis])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), cv2.cvtColor(combined, cv2.COLOR_RGB2BGR))


def score_project(
    project_dir: Path,
    ortho_path: Path,
    weights_path: Path,
    out_scores_path: Path,
    evidence_dir: Path,
) -> dict:
    t0 = time.time()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"--- Scoring Road Segments for Project: {project_dir.name} ---")
    print(f"Device: {device} | Weights: {weights_path}")
    print(f"Orthophoto: {ortho_path}")

    model = load_model(weights_path, device)

    # Load segments
    segs_path = project_dir / "roads" / "segments.geojson"
    if not segs_path.exists():
        segs_path = project_dir / "segments.geojson"
    if not segs_path.exists():
        raise FileNotFoundError(f"Segments GeoJSON not found in {project_dir}")

    with open(segs_path, "r", encoding="utf-8") as f:
        segs_data = json.load(f)

    features = segs_data.get("features", [])
    print(f"Total road segments to evaluate: {len(features)}")

    # Open orthophoto
    ds = rasterio.open(ortho_path)
    bounds_poly = box(*ds.bounds)
    gsd_m = float(ds.res[0])
    to_utm = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True)

    scores = []
    covered_count = 0
    evidence_paths = []

    for idx, feat in enumerate(features):
        props = feat.get("properties", {})
        seg_id = props.get("segment_id", f"seg_{idx+1:04d}")
        width_m = float(props.get("corridor_width_m") or 5.0)

        # Reproject geometry to orthophoto CRS
        geom_wgs = shape(feat["geometry"])
        geom_utm = shapely.transform(geom_wgs, lambda c: np.column_stack(to_utm.transform(c[:, 0], c[:, 1])))

        # Check if intersects orthophoto footprint
        if not geom_utm.intersects(bounds_poly):
            scores.append({
                "segment_id": seg_id,
                "p_blocked": None,
                "p_partial": None,
                "p_clear": None,
                "model": "typhon_debris_resnet18",
                "version": "1.0.0",
            })
            continue

        corridor_poly = geom_utm.buffer(width_m / 2.0)
        poly_intersection = corridor_poly.intersection(bounds_poly)
        if poly_intersection.is_empty or poly_intersection.area < 2.0:
            scores.append({
                "segment_id": seg_id,
                "p_blocked": None,
                "p_partial": None,
                "p_clear": None,
                "model": "typhon_debris_resnet18",
                "version": "1.0.0",
            })
            continue

        # Extract window around corridor
        minx, miny, maxx, maxy = corridor_poly.bounds
        margin_m = 6.0
        win = from_bounds(minx - margin_m, miny - margin_m, maxx + margin_m, maxy + margin_m, ds.transform)
        # Clamp window to raster extents
        win = win.intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
        win_w, win_h = int(round(win.width)), int(round(win.height))
        if win_w < 5 or win_h < 5:
            scores.append({
                "segment_id": seg_id,
                "p_blocked": None,
                "p_partial": None,
                "p_clear": None,
                "model": "typhon_debris_resnet18",
                "version": "1.0.0",
            })
            continue

        # Read RGB and Alpha
        raw = ds.read([1, 2, 3, 4], window=win)
        rgb = np.transpose(raw[:3], (1, 2, 0)).astype(np.uint8)
        alpha = raw[3]

        win_transform = rasterio.windows.transform(win, ds.transform)
        # Rasterize corridor polygon into window
        geom_mask = rasterize([(corridor_poly, 1)], out_shape=(win_h, win_w), transform=win_transform, fill=0, default_value=1)
        valid_corridor_mask = (geom_mask == 1) & (alpha > 50)

        if np.sum(valid_corridor_mask) < 20:
            scores.append({
                "segment_id": seg_id,
                "p_blocked": None,
                "p_partial": None,
                "p_clear": None,
                "model": "typhon_debris_resnet18",
                "version": "1.0.0",
            })
            continue

        # Score debris inside corridor
        fraction, debris_mask = score_corridor_debris(model, rgb, valid_corridor_mask, gsd_m, device)
        covered_count += 1

        # Map to probabilities per documented rule
        if fraction < 0.15:
            status = "clear"
            p_clear = round(float(1.0 - fraction), 3)
            p_blocked = 0.0
            p_partial = round(float(fraction), 3)
        elif fraction < 0.60:
            status = "partial"
            p_partial = round(float(fraction), 3)
            p_blocked = round(float(fraction * 0.5), 3)
            p_clear = round(float(max(0.0, 1.0 - (p_partial + p_blocked))), 3)
        else:
            status = "blocked"
            p_blocked = round(float(min(1.0, 0.70 + 0.30 * fraction)), 3)
            p_partial = round(float(max(0.0, 1.0 - p_blocked)), 3)
            p_clear = 0.0

        scores.append({
            "segment_id": seg_id,
            "p_blocked": p_blocked,
            "p_partial": p_partial,
            "p_clear": p_clear,
            "model": "typhon_debris_resnet18",
            "version": "1.0.0",
        })

        # Save evidence crop
        ev_file = evidence_dir / f"{seg_id}.jpg"
        make_evidence_crop(rgb, valid_corridor_mask, debris_mask, seg_id, fraction, status, ev_file)
        evidence_paths.append(str(ev_file))
        print(f"  {seg_id}: debris {fraction*100:4.1f}% -> {status:7s} (p_b={p_blocked:.3f}, p_p={p_partial:.3f}, p_c={p_clear:.3f}) | saved {ev_file.name}")

    ds.close()

    duration_s = time.time() - t0
    payload = {
        "mock": False,
        "scores": scores,
    }

    # Validate schema
    if SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=payload, schema=schema)
        print(f"Successfully validated against {SCHEMA_PATH.name}!")

    out_scores_path.parent.mkdir(parents=True, exist_ok=True)
    out_scores_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nSummary:")
    print(f"  Total segments: {len(scores)}")
    print(f"  Covered & scored inside flight footprint: {covered_count}")
    print(f"  Uncovered / outside footprint (unknown/null): {len(scores) - covered_count}")
    print(f"  Saved evidence crops: {len(evidence_paths)} to {evidence_dir}")
    print(f"  Scores written to: {out_scores_path}")
    print(f"  Total run time: {duration_s:.2f} s")

    return {
        "total_segments": len(scores),
        "covered": covered_count,
        "duration_s": duration_s,
        "evidence_paths": evidence_paths,
        "out_scores_path": str(out_scores_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Score South Fork road segments for landslide debris")
    parser.add_argument("--project", default="southfork_f01_4")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    args = parser.parse_args()

    project_dir = ROOT / "data" / "projects" / args.project
    ortho_path = project_dir / "odm_orthophoto" / "odm_orthophoto.tif"
    out_scores = project_dir / "ml_scores.json"
    evidence_dir = project_dir / "evidence"

    res = score_project(
        project_dir=project_dir,
        ortho_path=ortho_path,
        weights_path=args.weights,
        out_scores_path=out_scores,
        evidence_dir=evidence_dir,
    )
    print("\nF3 Part 1 Complete.")


if __name__ == "__main__":
    main()
