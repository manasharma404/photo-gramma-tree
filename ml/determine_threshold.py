import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import zipfile
import cv2
import numpy as np
import torch
from ml.train_debris import ResNet18UNet, CASZipDataset

CAS_ZIP = ROOT / "data/cas/zips/cas_train_val_0.2m.zip"
WEIGHTS_PATH = ROOT / "models/typhon_debris_resnet18.pt"

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading weights from {WEIGHTS_PATH} on {device}...")
    model = ResNet18UNet(in_channels=3, num_classes=1)
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=device))
    model.to(device).eval()

    with zipfile.ZipFile(CAS_ZIP, "r") as zf:
        all_imgs = sorted([n for n in zf.namelist() if n.startswith("img/") and n.endswith(".tif")])

    np.random.seed(42)
    n = len(all_imgs)
    indices = np.random.permutation(n)
    val_idx = indices[int(0.8 * n):].tolist()
    print(f"Evaluating on {len(val_idx)} CAS validation tiles...")

    val_dataset = CASZipDataset(CAS_ZIP, image_indices=val_idx, is_train=False)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=16, shuffle=False, num_workers=0)

    gt_shares = []
    pred_shares = []

    with torch.no_grad():
        for imgs, masks in val_loader:
            imgs = imgs.to(device)
            logits = model(imgs)
            probs = torch.sigmoid(logits)
            preds = (probs >= 0.5).float()

            # Batch mean per tile
            gt_shares.extend(masks.mean(dim=[1, 2, 3]).cpu().numpy().tolist())
            pred_shares.extend(preds.mean(dim=[1, 2, 3]).cpu().numpy().tolist())

    gt_shares = np.array(gt_shares, dtype=np.float32)
    pred_shares = np.array(pred_shares, dtype=np.float32)
    gt_is_debris = gt_shares >= 0.01

    print(f"\nTotal validation tiles: {len(gt_shares)}")
    print(f"Ground truth debris tiles (GT >= 1%): {gt_is_debris.sum()} ({gt_is_debris.mean()*100:.1f}%)")
    print(f"Ground truth clear tiles (GT < 1%): {(~gt_is_debris).sum()} ({(~gt_is_debris).mean()*100:.1f}%)")

    print("\n--- Sweeping Threshold T on CAS Validation Set ---")
    best_t = 0.05
    best_f1 = -1.0
    best_p, best_r = 0.0, 0.0

    thresholds = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25]
    for t in thresholds:
        pred_label = pred_shares >= t
        tp = int((pred_label & gt_is_debris).sum())
        fp = int((pred_label & ~gt_is_debris).sum())
        fn = int((~pred_label & gt_is_debris).sum())
        tn = int((~pred_label & ~gt_is_debris).sum())

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        print(f"T = {t*100:4.1f}% ({t:.3f}): Prec = {prec:.4f}, Rec = {rec:.4f}, F1 = {f1:.4f} (TP={tp:3d}, FP={fp:3d}, FN={fn:3d}, TN={tn:3d})")
        if f1 > best_f1:
            best_f1 = f1
            best_t = t
            best_p = prec
            best_r = rec

    print(f"\n=======================================================")
    print(f"Optimal Threshold on CAS Validation Set: T = {best_t*100:.1f}% (T = {best_t})")
    print(f"CAS Val Performance at T={best_t}: Precision={best_p:.4f}, Recall={best_r:.4f}, F1={best_f1:.4f}")
    print(f"=======================================================")

if __name__ == "__main__":
    main()
