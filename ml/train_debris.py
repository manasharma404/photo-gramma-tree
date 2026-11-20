"""Train lightweight U-Net with ResNet-18 encoder for landslide debris segmentation on CAS Landslide UAV data.

T1 requirements:
- Data: CAS Landslide Dataset (Zenodo record 10294997) UAV subsets
- Train/Val: Moxi town (0.2m GSD, 1635 images), split 80% train / 20% val
- Held-out test: Moxitaidi (0.6m GSD, 984 images)
- Small model for RTX 4050 (6 GB VRAM) / CPU
- Metrics: IoU (debris), Precision, Recall
- Export: ONNX weights outside git, timing on CPU & GPU, SHA-256 logged
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import zipfile

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
import torchvision.models as models

ROOT = Path(__file__).resolve().parent.parent
CAS_ZIP_DIR = ROOT / "data" / "cas" / "zips"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class CASZipDataset(Dataset):
    """Reads 512x512 RGB images and binary debris masks directly from Zenodo zip archives."""

    def __init__(self, zip_path: Path, image_indices: list[int] | None = None, is_train: bool = False):
        self.zip_path = zip_path
        self.is_train = is_train
        with zipfile.ZipFile(zip_path, "r") as zf:
            all_imgs = sorted([n for n in zf.namelist() if n.startswith("img/") and n.endswith(".tif")])
            all_masks = sorted([n for n in zf.namelist() if n.startswith("mask/") and n.endswith(".tif")])

        assert len(all_imgs) == len(all_masks), f"Mismatch: {len(all_imgs)} imgs vs {len(all_masks)} masks"

        if image_indices is not None:
            self.img_names = [all_imgs[i] for i in image_indices]
            self.mask_names = [all_masks[i] for i in image_indices]
        else:
            self.img_names = all_imgs
            self.mask_names = all_masks

    def __len__(self) -> int:
        return len(self.img_names)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            img_bytes = zf.read(self.img_names[idx])
            mask_bytes = zf.read(self.mask_names[idx])

        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)  # H, W, BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # H, W, RGB
        mask = cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), cv2.IMREAD_UNCHANGED)  # H, W

        # Ensure 512x512
        if img.shape[0] != 512 or img.shape[1] != 512:
            img = cv2.resize(img, (512, 512), interpolation=cv2.INTER_LINEAR)
            mask = cv2.resize(mask, (512, 512), interpolation=cv2.INTER_NEAREST)

        # Binary debris mask: threshold > 0
        mask = (mask > 0).astype(np.float32)

        # Simple data augmentation for training
        if self.is_train:
            if np.random.rand() > 0.5:
                img = np.fliplr(img).copy()
                mask = np.fliplr(mask).copy()
            if np.random.rand() > 0.5:
                img = np.flipud(img).copy()
                mask = np.flipud(mask).copy()

        # Normalize ImageNet mean/std
        img = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std

        # Transpose to (C, H, W)
        img_t = torch.from_numpy(img.transpose(2, 0, 1))
        mask_t = torch.from_numpy(mask).unsqueeze(0)  # (1, H, W)
        return img_t, mask_t


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
    """Lightweight U-Net with ResNet-18 encoder. Total parameters: ~14.3M."""

    def __init__(self, in_channels: int = 3, num_classes: int = 1):
        super().__init__()
        base = models.resnet18(weights=None)
        self.in_block = nn.Sequential(base.conv1, base.bn1, base.relu)  # 64, 256x256
        self.maxpool = base.maxpool  # 64, 128x128
        self.layer1 = base.layer1  # 64, 128x128
        self.layer2 = base.layer2  # 128, 64x64
        self.layer3 = base.layer3  # 256, 32x32
        self.layer4 = base.layer4  # 512, 16x16

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
        # Encoder
        x0 = self.in_block(x)       # 64, 256x256
        x1 = self.layer1(self.maxpool(x0))  # 64, 128x128
        x2 = self.layer2(x1)        # 128, 64x64
        x3 = self.layer3(x2)        # 256, 32x32
        x4 = self.layer4(x3)        # 512, 16x16

        # Decoder
        d4 = self.dec4(torch.cat([self.up4(x4), x3], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), x2], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), x1], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), x0], dim=1))
        out = self.final_conv(self.final_up(d1))
        return out


def bce_dice_loss(pred_logits: torch.Tensor, target: torch.Tensor, smooth: float = 1.0) -> torch.Tensor:
    bce = F.binary_cross_entropy_with_logits(pred_logits, target)
    probs = torch.sigmoid(pred_logits)
    intersection = (probs * target).sum(dim=(2, 3))
    union = probs.sum(dim=(2, 3)) + target.sum(dim=(2, 3))
    dice = 1.0 - (2.0 * intersection + smooth) / (union + smooth)
    return bce + dice.mean()


def evaluate_dataset(model: nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    total_inter = 0.0
    total_union = 0.0
    total_tp = 0.0
    total_fp = 0.0
    total_fn = 0.0

    with torch.no_grad():
        for imgs, masks in loader:
            imgs = imgs.to(device)
            masks = masks.to(device)
            logits = model(imgs)
            preds = (torch.sigmoid(logits) > 0.5).float()

            inter = (preds * masks).sum().item()
            union = (preds + masks).clamp(0, 1).sum().item()
            tp = inter
            fp = (preds * (1.0 - masks)).sum().item()
            fn = ((1.0 - preds) * masks).sum().item()

            total_inter += inter
            total_union += union
            total_tp += tp
            total_fp += fp
            total_fn += fn

    iou = total_inter / max(total_union, 1e-6)
    precision = total_tp / max(total_tp + total_fp, 1e-6)
    recall = total_tp / max(total_tp + total_fn, 1e-6)
    f1 = 2 * precision * recall / max(precision + recall, 1e-6)

    return {
        "iou": round(iou, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Train Landslide Debris Segmentation Model")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    args = parser.parse_args()

    train_zip = CAS_ZIP_DIR / "cas_train_val_0.2m.zip"
    test_zip = CAS_ZIP_DIR / "cas_held_out_test_0.6m.zip"

    assert train_zip.exists(), f"Train zip missing: {train_zip}"
    assert test_zip.exists(), f"Test zip missing: {test_zip}"

    # Setup device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    # Train / Val Split (Moxi town 0.2m, 1,635 images: 1,308 train, 327 val)
    np.random.seed(42)
    n_total = 1635
    indices = np.random.permutation(n_total)
    n_train = int(0.80 * n_total)
    train_idx = indices[:n_train].tolist()
    val_idx = indices[n_train:].tolist()

    print(f"CAS Dataset Split: Train={len(train_idx)}, Val={len(val_idx)}, Held-out Test=984")
    train_ds = CASZipDataset(train_zip, train_idx, is_train=True)
    val_ds = CASZipDataset(train_zip, val_idx, is_train=False)
    test_ds = CASZipDataset(test_zip, is_train=False)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = ResNet18UNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    print(f"\nStarting training for {args.epochs} epochs on {device}...")
    t_start = time.time()

    best_val_iou = 0.0
    best_weights_path = MODELS_DIR / "typhon_debris_resnet18.pt"

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        n_batches = 0
        ep_t0 = time.time()

        for step, (imgs, masks) in enumerate(train_loader):
            imgs = imgs.to(device)
            masks = masks.to(device)
            optimizer.zero_grad()
            logits = model(imgs)
            loss = bce_dice_loss(logits, masks)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            n_batches += 1
            if (step + 1) % 20 == 0 or (step + 1) == len(train_loader):
                print(f"\r  Epoch [{epoch}/{args.epochs}] Step [{step+1}/{len(train_loader)}] Loss: {loss.item():.4f}", end="", flush=True)

        scheduler.step()
        ep_time = time.time() - ep_t0
        avg_loss = running_loss / max(n_batches, 1)

        val_metrics = evaluate_dataset(model, val_loader, device)
        print(f"\n  Epoch {epoch} finished in {ep_time:.1f}s | Train Loss: {avg_loss:.4f} | Val IoU: {val_metrics['iou']:.4f} | Val F1: {val_metrics['f1']:.4f} | Precision: {val_metrics['precision']:.4f} | Recall: {val_metrics['recall']:.4f}")

        if val_metrics["iou"] > best_val_iou:
            best_val_iou = val_metrics["iou"]
            torch.save(model.state_dict(), best_weights_path)
            print(f"  --> Saved new best weights to {best_weights_path.name} (Val IoU: {best_val_iou:.4f})")

    total_train_time = time.time() - t_start
    print(f"\nTraining completed in {total_train_time:.1f}s ({total_train_time/60:.2f} min).")

    # Load best weights for final held-out evaluation
    model.load_state_dict(torch.load(best_weights_path, map_location=device))
    print("\n--- Final Evaluation on Held-Out Test Region (Moxitaidi UAV-0.6m, 984 images) ---")
    test_metrics = evaluate_dataset(model, test_loader, device)
    print(f"Held-out Test IoU (Debris):  {test_metrics['iou']:.4f} ({test_metrics['iou']*100:.2f}%)")
    print(f"Held-out Test Precision:     {test_metrics['precision']:.4f} ({test_metrics['precision']*100:.2f}%)")
    print(f"Held-out Test Recall:        {test_metrics['recall']:.4f} ({test_metrics['recall']*100:.2f}%)")
    print(f"Held-out Test F1-Score:      {test_metrics['f1']:.4f}")

    # Compute SHA-256 of saved weights
    h_sha = hashlib.sha256(best_weights_path.read_bytes()).hexdigest()
    weights_size_mb = best_weights_path.stat().st_size / (1024 * 1024)
    print(f"\nWeights file: {best_weights_path}")
    print(f"Size: {weights_size_mb:.2f} MB")
    print(f"SHA-256: {h_sha}")

    # Export to ONNX
    onnx_path = MODELS_DIR / "typhon_debris_resnet18.onnx"
    dummy_input = torch.randn(1, 3, 512, 512, device=device)
    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        input_names=["input"],
        output_names=["debris_logits"],
        dynamic_axes={"input": {0: "batch"}, "debris_logits": {0: "batch"}},
        opset_version=17,
    )
    onnx_sha = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    print(f"Exported ONNX: {onnx_path} ({onnx_path.stat().st_size / 1e6:.2f} MB)")
    print(f"ONNX SHA-256: {onnx_sha}")

    # Measure inference latency on GPU & CPU
    print("\n--- Benchmark Inference Latency (512x512 tile) ---")
    # GPU timing
    if torch.cuda.is_available():
        model.to("cuda").eval()
        x_gpu = torch.randn(1, 3, 512, 512, device="cuda")
        # warmup
        for _ in range(10):
            _ = model(x_gpu)
        torch.cuda.synchronize()
        t0 = time.time()
        n_iters = 50
        with torch.no_grad():
            for _ in range(n_iters):
                _ = model(x_gpu)
            torch.cuda.synchronize()
        gpu_latency_ms = (time.time() - t0) / n_iters * 1000.0
        print(f"GPU Latency (RTX 4050 6 GB): {gpu_latency_ms:.2f} ms / 512x512 tile ({1000.0/gpu_latency_ms:.1f} FPS)")
    else:
        gpu_latency_ms = None

    # CPU timing
    model.to("cpu").eval()
    x_cpu = torch.randn(1, 3, 512, 512, device="cpu")
    for _ in range(3):
        _ = model(x_cpu)
    t0 = time.time()
    n_cpu_iters = 10
    with torch.no_grad():
        for _ in range(n_cpu_iters):
            _ = model(x_cpu)
    cpu_latency_ms = (time.time() - t0) / n_cpu_iters * 1000.0
    print(f"CPU Latency: {cpu_latency_ms:.2f} ms / 512x512 tile ({1000.0/cpu_latency_ms:.1f} FPS)")

    # Save summary results JSON
    results = {
        "model": "ResNet18UNet",
        "parameters": sum(p.numel() for p in model.parameters()),
        "training_subset": "Moxi town (UAV-0.2m)",
        "training_resolution_gsd_m": 0.20,
        "training_images": len(train_idx),
        "validation_images": len(val_idx),
        "held_out_test_subset": "Moxitaidi (UAV-0.6m)",
        "held_out_test_images": len(test_ds),
        "held_out_metrics": test_metrics,
        "weights_path": str(best_weights_path),
        "weights_sha256": h_sha,
        "onnx_path": str(onnx_path),
        "onnx_sha256": onnx_sha,
        "latency_gpu_ms": round(gpu_latency_ms, 2) if gpu_latency_ms else None,
        "latency_cpu_ms": round(cpu_latency_ms, 2),
    }
    (MODELS_DIR / "training_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved metrics summary to {MODELS_DIR / 'training_summary.json'}")


if __name__ == "__main__":
    main()
