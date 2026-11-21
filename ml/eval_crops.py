"""Evaluate trained debris model on 50 South Fork road/trail crops (Step 1 of Finale Plan).

Evaluates typhon_debris_resnet18.pt against human labels in data/eval/southfork_crops/labels.csv.
Decision rule T is fixed from CAS validation sweep BEFORE looking at these results:
    T = 0.005 (0.5% debris area fraction) [Primary F1-optimal threshold from CAS val]
    T = 0.050 (5.0% debris area fraction) [Conservative high-precision threshold]

Usage:
    python ml/eval_crops.py
    python ml/eval_crops.py --threshold 0.005
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import cv2
import numpy as np
import torch
import torchvision.models as models
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHTS = ROOT / "models" / "typhon_debris_resnet18.pt"
DEFAULT_CROPS_DIR = ROOT / "data" / "eval" / "southfork_crops"
DEFAULT_LABELS_CSV = DEFAULT_CROPS_DIR / "labels.csv"


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
    """Lightweight U-Net with ResNet-18 encoder."""

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


def normalize_crop_id(raw_id: str) -> str:
    cleaned = raw_id.strip().lower()
    if cleaned.endswith(".png") or cleaned.endswith(".jpg"):
        cleaned = cleaned.rsplit(".", 1)[0]
    if cleaned.startswith("c"):
        try:
            num = int(cleaned[1:])
            return f"c{num:02d}"
        except ValueError:
            pass
    elif cleaned.isdigit():
        return f"c{int(cleaned):02d}"
    return cleaned


def parse_labels_csv(csv_path: Path) -> tuple[list[dict], list[dict]]:
    """Parse labels.csv, splitting into valid evaluation rows and excluded rows."""
    valid_rows = []
    excluded_rows = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            crop_id = normalize_crop_id(row.get("crop_id") or row.get("id") or "")
            label_str = (row.get("label") or "").strip().lower()
            notes = (row.get("notes") or "").strip()

            if not crop_id:
                continue

            # Check if blank or unsure / can't tell
            if not label_str or label_str in ("blank", "c07") or crop_id == "c07":
                excluded_rows.append({"crop_id": crop_id, "label": label_str, "notes": notes, "reason": "blank"})
                continue
            if label_str in ("unsure", "can't tell", "cant tell", "unknown", "?"):
                excluded_rows.append({"crop_id": crop_id, "label": label_str, "notes": notes, "reason": "unsure/can't tell"})
                continue

            # Binary ground truth
            if label_str in ("debris", "1", "yes", "true", "landslide"):
                gt = 1
            elif label_str in ("no debris", "clear", "0", "no", "false", "clean"):
                gt = 0
            else:
                excluded_rows.append({"crop_id": crop_id, "label": label_str, "notes": notes, "reason": f"unrecognized label '{label_str}'"})
                continue

            is_broken_trees = "tree" in notes.lower() or "wood" in notes.lower() or "timber" in notes.lower()
            valid_rows.append({
                "crop_id": crop_id,
                "gt": gt,
                "label_str": label_str,
                "notes": notes,
                "is_broken_trees": is_broken_trees,
            })

    return valid_rows, excluded_rows


def predict_crop(model: nn.Module, img_path: Path, device: torch.device) -> float:
    """Load crop (0.05m GSD, 512x512), resize to 0.20m GSD (128x128), predict debris share."""
    img_bgr = cv2.imread(str(img_path))
    if img_bgr is None:
        raise FileNotFoundError(f"Crop image not found or unreadable: {img_path}")

    # Resize from 0.05 m/px to 0.20 m/px (factor of 4: 512 -> 128)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    target_size = (max(32, round(w / 4)), max(32, round(h / 4)))  # 128x128
    img_resized = cv2.resize(img_rgb, target_size, interpolation=cv2.INTER_AREA)

    # Normalize ImageNet mean/std
    img_f = img_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img_norm = (img_f - mean) / std

    tensor = torch.from_numpy(img_norm.transpose(2, 0, 1)).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits).squeeze().cpu().numpy()

    debris_fraction = float(np.mean(probs > 0.5))
    return debris_fraction


def compute_metrics(records: list[dict], threshold: float) -> dict[str, float]:
    tp = sum(1 for r in records if r["gt"] == 1 and r["pred_fraction"] >= threshold)
    fp = sum(1 for r in records if r["gt"] == 0 and r["pred_fraction"] >= threshold)
    fn = sum(1 for r in records if r["gt"] == 1 and r["pred_fraction"] < threshold)
    tn = sum(1 for r in records if r["gt"] == 0 and r["pred_fraction"] < threshold)

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "total": len(records),
    }


def evaluate(
    crops_dir: Path,
    labels_csv: Path,
    weights_path: Path,
    threshold: float = 0.005,
    alt_threshold: float = 0.050,
) -> int:
    print(f"=== South Fork 50 Road/Trail Crops Evaluation ===")
    print(f"Decision Rule T (fixed beforehand from CAS val set): T = {threshold:.3f} ({threshold*100:.1f}%)")
    print(f"Conservative Rule T (high-precision check):           T = {alt_threshold:.3f} ({alt_threshold*100:.1f}%)")

    if not labels_csv.exists():
        print(f"\n[INFO] labels.csv not found at: {labels_csv}")
        print("To evaluate crops:")
        print(f"  1. Place 'labels.csv' and crop PNGs (c01.png ... c50.png) in {crops_dir}")
        print("  2. Re-run: python ml/eval_crops.py")
        return 1

    if not weights_path.exists():
        print(f"\n[ERROR] Model weights not found at: {weights_path}")
        return 1

    valid_rows, excluded_rows = parse_labels_csv(labels_csv)
    print(f"\nLabels summary: {len(valid_rows)} valid evaluation crops, {len(excluded_rows)} excluded crops.")
    for exc in excluded_rows:
        print(f"  - Excluded {exc['crop_id']}: label='{exc['label']}', reason={exc['reason']}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading weights from {weights_path} onto {device}...")
    model = load_model(weights_path, device)

    # Run predictions
    scored_records = []
    missing_imgs = []
    for r in valid_rows:
        cid = r["crop_id"]
        img_path = crops_dir / f"{cid}.png"
        if not img_path.exists():
            img_path = crops_dir / f"{cid}.jpg"
        if not img_path.exists():
            missing_imgs.append(cid)
            continue

        frac = predict_crop(model, img_path, device)
        r_scored = dict(r)
        r_scored["pred_fraction"] = frac
        scored_records.append(r_scored)

    if missing_imgs:
        print(f"[WARNING] {len(missing_imgs)} crop images not found in {crops_dir}: {missing_imgs}")
        if not scored_records:
            print("No crop images found to score. Please ensure c01.png ... c50.png are present.")
            return 1

    print(f"\n--- Results on All Valid Evaluated Crops (N={len(scored_records)}) ---")
    m_prim = compute_metrics(scored_records, threshold)
    print(f"Primary T={threshold:.3f} ({threshold*100:.1f}%):")
    print(f"  Precision: {m_prim['precision']:.4f} ({m_prim['tp']}/{m_prim['tp']+m_prim['fp']})")
    print(f"  Recall:    {m_prim['recall']:.4f} ({m_prim['tp']}/{m_prim['tp']+m_prim['fn']})")
    print(f"  F1 Score:  {m_prim['f1']:.4f}")
    print(f"  Confusion: TP={m_prim['tp']}, FP={m_prim['fp']}, FN={m_prim['fn']}, TN={m_prim['tn']}")

    m_alt = compute_metrics(scored_records, alt_threshold)
    print(f"Conservative T={alt_threshold:.3f} ({alt_threshold*100:.1f}%):")
    print(f"  Precision: {m_alt['precision']:.4f} ({m_alt['tp']}/{m_alt['tp']+m_alt['fp']})")
    print(f"  Recall:    {m_alt['recall']:.4f} ({m_alt['tp']}/{m_alt['tp']+m_alt['fn']})")
    print(f"  F1 Score:  {m_alt['f1']:.4f}")
    print(f"  Confusion: TP={m_alt['tp']}, FP={m_alt['fp']}, FN={m_alt['fn']}, TN={m_alt['tn']}")

    # Subgroup analysis: "Broken trees" vs Rest
    trees_records = [r for r in scored_records if r["gt"] == 1 and r["is_broken_trees"]]
    rock_soil_records = [r for r in scored_records if r["gt"] == 1 and not r["is_broken_trees"]]

    print(f"\n--- Subgroup Breakdown for Debris Positives ---")
    print(f"1. 'Broken trees mainly' debris crops (N={len(trees_records)}):")
    if trees_records:
        rec_trees_prim = sum(1 for r in trees_records if r["pred_fraction"] >= threshold) / len(trees_records)
        rec_trees_alt = sum(1 for r in trees_records if r["pred_fraction"] >= alt_threshold) / len(trees_records)
        print(f"   Recall at T={threshold:.3f}: {rec_trees_prim:.4f} ({sum(1 for r in trees_records if r['pred_fraction'] >= threshold)}/{len(trees_records)})")
        print(f"   Recall at T={alt_threshold:.3f}: {rec_trees_alt:.4f} ({sum(1 for r in trees_records if r['pred_fraction'] >= alt_threshold)}/{len(trees_records)})")

    print(f"2. Mud, rock and scar debris crops (N={len(rock_soil_records)}):")
    if rock_soil_records:
        rec_rock_prim = sum(1 for r in rock_soil_records if r["pred_fraction"] >= threshold) / len(rock_soil_records)
        rec_rock_alt = sum(1 for r in rock_soil_records if r["pred_fraction"] >= alt_threshold) / len(rock_soil_records)
        print(f"   Recall at T={threshold:.3f}: {rec_rock_prim:.4f} ({sum(1 for r in rock_soil_records if r['pred_fraction'] >= threshold)}/{len(rock_soil_records)})")
        print(f"   Recall at T={alt_threshold:.3f}: {rec_rock_alt:.4f} ({sum(1 for r in rock_soil_records if r['pred_fraction'] >= alt_threshold)}/{len(rock_soil_records)})")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Evaluate debris model on 50 South Fork crops")
    parser.add_argument("--crops-dir", type=Path, default=DEFAULT_CROPS_DIR, help="Path to crops folder")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_CSV, help="Path to labels.csv")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS, help="Path to model weights .pt")
    parser.add_argument("--threshold", type=float, default=0.005, help="Primary threshold T (default 0.005)")
    parser.add_argument("--alt-threshold", type=float, default=0.050, help="Alternative threshold T (default 0.050)")
    args = parser.parse_args()

    ret = evaluate(
        crops_dir=args.crops_dir,
        labels_csv=args.labels,
        weights_path=args.weights,
        threshold=args.threshold,
        alt_threshold=args.alt_threshold,
    )
    sys.exit(ret)


if __name__ == "__main__":
    main()
