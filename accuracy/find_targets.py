"""Find survey targets in an orthophoto near their surveyed positions.

    python -m accuracy.find_targets --ortho <orthophoto.tif> --rtk <rtk.csv> --out <dir>

The USGS South Fork aerial targets are white squares of roughly 0.8 m with dark
"bowtie" triangles and a hand-written number. For each target that falls on the
map, we search a window around its surveyed position for small, bright,
low-saturation, roughly square blobs that contain some dark pixels, score them,
and save a crop sheet of the best candidates for a person to confirm.

The output (candidates.json) is a proposal, not a measurement: a candidate only
counts as a checkpoint after someone confirms it in confirmed.json.
"""
import argparse
import csv
import json
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

TARGET_CODES = ("AT", "CHLK")


def read_targets(rtk_csv):
    with open(rtk_csv, encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["code"] in TARGET_CODES]


def candidates_in(rgb, valid, px_m, side_m=(0.3, 1.2), top=5):
    """White-and-blue square blobs (the target's white square with bluish triangles).

    Sand, rocks and dry wood here are yellowish (red > blue), so requiring bluish
    pixels next to near-white ones rejects most of them. Returns (row, col, score, info).
    """
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    v, s = hsv[..., 2].astype(np.int32), hsv[..., 1].astype(np.int32)
    r, b = rgb[..., 0].astype(np.int32), rgb[..., 2].astype(np.int32)
    vv = v[valid]
    if vv.size == 0:
        return []
    white = (v >= max(180, np.percentile(vv, 98))) & (s <= 60) & (b >= r - 5) & valid
    bluish = (b - r >= 12) & (v >= 80) & valid
    blob = cv2.dilate((white | bluish).astype(np.uint8), np.ones((3, 3), np.uint8))
    n, _, stats, cents = cv2.connectedComponentsWithStats(blob, connectivity=8)
    lo, hi = (side_m[0] / px_m) ** 2, (side_m[1] / px_m) ** 2
    out = []
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        if not (lo <= w * h <= hi) or max(w, h) > 2.0 * min(w, h):
            continue
        white_frac = float(white[y:y + h, x:x + w].mean())
        blue_frac = float(bluish[y:y + h, x:x + w].mean())
        if white_frac < 0.1 or blue_frac < 0.05:
            continue
        ring = v[max(0, y - h):y + 2 * h, max(0, x - w):x + 2 * w]
        contrast = float(np.percentile(v[y:y + h, x:x + w], 90) - np.median(ring))
        score = min(white_frac, 0.5) + min(blue_frac, 0.4) + min(w, h) / max(w, h) + contrast / 255
        out.append((float(cents[i][1]), float(cents[i][0]), round(score, 3),
                    {"w_m": round(w * px_m, 2), "h_m": round(h * px_m, 2), "white_frac": round(white_frac, 2),
                     "blue_frac": round(blue_frac, 2), "contrast": round(contrast, 1)}))
    return sorted(out, key=lambda c: -c[2])[:top]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ortho", type=Path, required=True)
    ap.add_argument("--rtk", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--radius", type=float, default=30.0, help="search half-window in metres")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.ortho) as ds:
        to_map = Transformer.from_crs(4326, ds.crs, always_xy=True)
        px_m = abs(ds.transform.a)
        results = []
        for t in read_targets(args.rtk):
            x, y = to_map.transform(float(t["longitude"]), float(t["latitude"]))
            if not (ds.bounds.left < x < ds.bounds.right and ds.bounds.bottom < y < ds.bounds.top):
                continue
            win = from_bounds(x - args.radius, y - args.radius, x + args.radius, y + args.radius, ds.transform)
            arr = ds.read(window=win, boundless=True, fill_value=0)
            rgb = np.ascontiguousarray(np.moveaxis(arr[:3], 0, -1))
            valid = arr[3] > 0 if ds.count >= 4 else rgb.sum(axis=2) > 0
            if valid.mean() < 0.05:
                continue
            wt = ds.window_transform(win)
            cands = []
            for row, col, score, info in candidates_in(rgb, valid, px_m):
                cx, cy = wt * (col, row)
                cands.append({"x": round(cx, 3), "y": round(cy, 3), "score": score,
                              "offset_m": round(float(np.hypot(cx - x, cy - y)), 2), **info,
                              "_rc": (row, col)})
            results.append({"id": t["pid"], "code": t["code"], "surveyed_xy": [round(x, 3), round(y, 3)],
                            "window_valid_fraction": round(float(valid.mean()), 2), "candidates": cands})

            # crop sheet: overview with candidates numbered + 3 m zoom of each
            k = len(cands)
            fig, axs = plt.subplots(1, k + 1, figsize=(3 * (k + 1), 3.2))
            axs = np.atleast_1d(axs)
            axs[0].imshow(rgb)
            axs[0].plot(rgb.shape[1] / 2, rgb.shape[0] / 2, "r+", ms=14)
            for j, c in enumerate(cands, 1):
                r, cc = c["_rc"]
                axs[0].annotate(str(j), (cc, r), color="cyan", fontsize=10, weight="bold")
                z = int(1.5 / px_m)
                axs[j].imshow(rgb[max(0, int(r) - z):int(r) + z, max(0, int(cc) - z):int(cc) + z])
                axs[j].set_title(f"#{j} {c['offset_m']} m s={c['score']}", fontsize=8)
            axs[0].set_title(f"{t['pid']} ({t['code']}) ±{args.radius:.0f} m; + = surveyed", fontsize=8)
            for a in axs:
                a.axis("off")
            fig.tight_layout()
            fig.savefig(args.out / f"{t['pid']}_candidates.png", dpi=100)
            plt.close(fig)

    for r in results:
        for c in r["candidates"]:
            c.pop("_rc")
    meta = {"ortho": str(args.ortho).replace("\\", "/"), "crs": "map CRS of the orthophoto", "radius_m": args.radius,
            "px_m": px_m, "status": "PROPOSALS: confirm each in confirmed.json before computing errors",
            "targets": results}
    (args.out / "candidates.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    for r in results:
        best = r["candidates"][0] if r["candidates"] else None
        print(r["id"], r["code"], f"valid={r['window_valid_fraction']}",
              f"best: {best['offset_m']} m score {best['score']} {best['w_m']}x{best['h_m']} m" if best else "no candidate")


if __name__ == "__main__":
    main()
