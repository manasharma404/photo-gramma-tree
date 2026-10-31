"""Extract USGS South Fork real frames + explicitly-labelled synthetic degradations for M1 (T13).

Once SEKI_SouthFork_AerialImages_F02-2.zip is downloaded in a browser into data/raw/:
    uv run python -m ml.prepare_m1_eval --zip data/raw/SEKI_SouthFork_AerialImages_F02-2.zip --out-dir data/iqa_eval

Outputs (under data/iqa_eval/, gitignored):
    - frames/ (36 real USGS frames + 24 SYNTHETIC_* degraded frames = 60 frames)
    - contact_sheet.jpg (visual inspection grid of all 60 frames)
    - labels.csv (columns: image,usable,synthetic,degradation,source_image)
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import zipfile

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _motion_blur(bgr: np.ndarray, ksize: int = 31) -> np.ndarray:
    kernel = np.zeros((ksize, ksize), dtype=np.float32)
    kernel[ksize // 2, :] = 1.0 / float(ksize)
    return cv2.filter2D(bgr, -1, kernel)


def prepare_eval_set(
    zip_or_dir: Path,
    out_dir: Path,
    n_real: int = 36,
    max_eval_dim: int = 1600,
) -> dict[str, Path]:
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    raw_entries: list[tuple[str, bytes]] = []
    if zip_or_dir.is_file() and zip_or_dir.suffix.lower() == ".zip":
        with zipfile.ZipFile(zip_or_dir, "r") as zf:
            img_members = sorted(
                n
                for n in zf.namelist()
                if Path(n).suffix.lower() in IMAGE_EXTS and not Path(n).name.startswith(".")
            )
            step = max(1, len(img_members) // max(n_real, 1))
            picked = img_members[::step][:n_real]
            for m in picked:
                raw_entries.append((Path(m).name, zf.read(m)))
    elif zip_or_dir.is_dir():
        imgs = sorted(p for p in zip_or_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
        step = max(1, len(imgs) // max(n_real, 1))
        for p in imgs[::step][:n_real]:
            raw_entries.append((p.name, p.read_bytes()))
    else:
        raise FileNotFoundError(f"USGS frame archive or folder not found: {zip_or_dir}")

    if len(raw_entries) < 26:
        raise ValueError(f"Expected >=26 real frames from {zip_or_dir}, found {len(raw_entries)}")

    rows: list[dict[str, str]] = []
    decoded_real: list[tuple[str, np.ndarray]] = []

    for fname, raw_bytes in raw_entries:
        bgr = cv2.imdecode(np.frombuffer(raw_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            continue
        h, w = bgr.shape[:2]
        if max(h, w) > max_eval_dim:
            sc = float(max_eval_dim) / float(max(h, w))
            bgr = cv2.resize(bgr, (int(round(w * sc)), int(round(h * sc))), interpolation=cv2.INTER_AREA)

        out_name = f"REAL_{Path(fname).stem}.jpg"
        cv2.imwrite(str(frames_dir / out_name), bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        decoded_real.append((out_name, bgr))
        rows.append(
            {
                "image": out_name,
                "usable": "yes",
                "synthetic": "false",
                "degradation": "none_real_usgs",
                "source_image": fname,
            }
        )

    # Create 24 explicitly-labelled SYNTHETIC degraded frames across 4 failure modes
    degradations = (
        [("defocus_blur", lambda im: cv2.GaussianBlur(im, (31, 31), 9.0))] * 8
        + [("motion_blur", lambda im: _motion_blur(im, 33))] * 8
        + [("dark_underexposed", lambda im: np.clip(im.astype(np.float32) * 0.14, 0, 255).astype(np.uint8))] * 4
        + [("bright_overexposed", lambda im: np.clip(im.astype(np.float32) * 2.6 + 130.0, 0, 255).astype(np.uint8))] * 4
    )

    thumbs: list[np.ndarray] = []
    for name, bgr in decoded_real:
        th = cv2.resize(bgr, (240, 160))
        cv2.putText(th, name[:22], (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 0), 1, cv2.LINE_AA)
        thumbs.append(th)

    for idx, (deg_kind, fn) in enumerate(degradations):
        src_name, src_bgr = decoded_real[idx % len(decoded_real)]
        bad_bgr = fn(src_bgr)
        syn_name = f"SYNTHETIC_{idx + 1:02d}_{deg_kind}_{src_name.replace('REAL_', '')}"
        cv2.imwrite(str(frames_dir / syn_name), bad_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        rows.append(
            {
                "image": syn_name,
                "usable": "no",
                "synthetic": "true",
                "degradation": f"synthetic:{deg_kind}",
                "source_image": src_name,
            }
        )
        th = cv2.resize(bad_bgr, (240, 160))
        cv2.putText(th, f"SYN:{deg_kind[:14]}", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 80, 255), 1, cv2.LINE_AA)
        thumbs.append(th)

    # Render visual contact sheet for manual verification
    cols = 6
    n_rows = (len(thumbs) + cols - 1) // cols
    sheet = np.zeros((n_rows * 160, cols * 240, 3), dtype=np.uint8)
    for i, th in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet[r * 160 : (r + 1) * 160, c * 240 : (c + 1) * 240] = th
    sheet_path = out_dir / "contact_sheet.jpg"
    cv2.imwrite(str(sheet_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])

    labels_path = out_dir / "labels.csv"
    with open(labels_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["image", "usable", "synthetic", "degradation", "source_image"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return {"frames_dir": frames_dir, "labels_csv": labels_path, "contact_sheet": sheet_path}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", type=Path, required=True, help="Path to USGS South Fork zip or folder")
    ap.add_argument("--out-dir", type=Path, default=Path("data/iqa_eval"))
    ap.add_argument("--n-real", type=int, default=36)
    args = ap.parse_args()

    out = prepare_eval_set(args.zip, args.out_dir, n_real=args.n_real)
    print(f"Prepared IQA evaluation set in {args.out_dir}: {out}")


if __name__ == "__main__":
    main()
