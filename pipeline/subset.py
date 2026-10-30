"""Choose an image subset for ODM by where the photos are, relative to known targets.

    python -m pipeline.subset --images data/public/usgs_southfork/images \
        --rtk data/public/usgs_southfork/SEKI_SouthFork_DebrisFlow_2024_RTK_GNSS.csv --max 150

Reads each image's EXIF GPS (exiftool), estimates its ground footprint from the
camera's stated GSD, counts how many images see each target, and keeps the images
that see the most targets (ties: closest to the target cluster). Writes
subset.txt (one path per line), subset.json (the numbers behind the choice) and
subset.png (image centres vs targets).
"""
import argparse
import csv
import io
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pyproj import Transformer

EXIFTOOL_FALLBACK = Path.home() / "AppData/Local/Programs/ExifTool/ExifTool.exe"
TARGET_CODES = ("AT", "CHLK")  # aerial targets and chalk targets (23 in the USGS file)


def exiftool():
    exe = shutil.which("exiftool") or (str(EXIFTOOL_FALLBACK) if EXIFTOOL_FALLBACK.exists() else None)
    if exe is None:
        raise SystemExit("exiftool not found")
    return exe


def read_image_gps(folder):
    out = subprocess.run(
        [exiftool(), "-r", "-n", "-csv", "-ext", "jpg", "-GPSLatitude", "-GPSLongitude", "-GPSAltitude",
         "-ImageWidth", "-ImageHeight", "-Model", str(folder)],
        capture_output=True, text=True, check=True).stdout
    rows = list(csv.DictReader(io.StringIO(out)))
    return [r for r in rows if r.get("GPSLatitude")]


def read_targets(rtk_csv):
    with open(rtk_csv, encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["code"] in TARGET_CODES]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--rtk", type=Path, required=True)
    ap.add_argument("--max", type=int, default=150)
    ap.add_argument("--gsd-cm", type=float, default=2.9, help="nominal GSD stated by the data provider")
    ap.add_argument("--epsg", type=int, default=32611, help="metric CRS for footprints (UTM 11N for South Fork)")
    ap.add_argument("--out-dir", type=Path, default=None, help="where subset.* go (default: next to the RTK file)")
    args = ap.parse_args()

    to_utm = Transformer.from_crs(4326, args.epsg, always_xy=True)
    images = read_image_gps(args.images)
    targets = read_targets(args.rtk)
    ix, iy = to_utm.transform([float(r["GPSLongitude"]) for r in images], [float(r["GPSLatitude"]) for r in images])
    tx, ty = to_utm.transform([float(t["longitude"]) for t in targets], [float(t["latitude"]) for t in targets])
    ix, iy, tx, ty = map(np.asarray, (ix, iy, tx, ty))

    # Footprint as an axis-aligned box of half-size (width, height) * GSD / 2. Heading is unknown,
    # so use the shorter side for both axes: a conservative "this image surely sees it" test.
    w, h = int(images[0]["ImageWidth"]), int(images[0]["ImageHeight"])
    half = min(w, h) * args.gsd_cm / 100 / 2
    sees = (np.abs(ix[:, None] - tx[None, :]) <= half) & (np.abs(iy[:, None] - ty[None, :]) <= half)

    cx, cy = tx.mean(), ty.mean()
    dist = np.hypot(ix - cx, iy - cy)
    order = sorted(range(len(images)), key=lambda i: (-sees[i].sum(), dist[i]))
    keep = sorted(order[: args.max])

    root = args.out_dir or args.rtk.parent
    paths = [str(Path(images[i]["SourceFile"]).resolve().relative_to(Path.cwd().resolve())).replace("\\", "/")
             for i in keep]
    (root / "subset.txt").write_text("\n".join(paths) + "\n", encoding="utf-8")

    per_target_all = sees.sum(axis=0)
    per_target_kept = sees[keep].sum(axis=0)
    summary = {
        "method": "EXIF GPS image centres; footprint = square of half-side min(w,h)*GSD/2 (heading unknown, conservative)",
        "gsd_cm_stated": args.gsd_cm,
        "footprint_half_side_m": round(half, 1),
        "images_total": len(images),
        "images_kept": len(keep),
        "camera_models": sorted({r.get("Model", "") for r in images}),
        "image_size_px": [w, h],
        "image_alt_m_ellipsoid": {"min": min(float(r["GPSAltitude"]) for r in images),
                                  "max": max(float(r["GPSAltitude"]) for r in images)},
        "targets_total": len(targets),
        "targets_seen_by_any_image": int((per_target_all > 0).sum()),
        "targets_seen_by_kept_images": int((per_target_kept > 0).sum()),
        "targets_seen_by_3plus_kept_images": int((per_target_kept >= 3).sum()),
        "per_target": [{"id": t["pid"], "code": t["code"], "images_all": int(a), "images_kept": int(k)}
                       for t, a, k in zip(targets, per_target_all, per_target_kept)],
    }
    (root / "subset.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8, 8))
    dropped = [i for i in range(len(images)) if i not in set(keep)]
    ax.scatter(ix[dropped], iy[dropped], s=8, c="#bbbbbb", label=f"image centre, not kept ({len(dropped)})")
    ax.scatter(ix[keep], iy[keep], s=8, c="#1f77b4", label=f"image centre, kept ({len(keep)})")
    colours = ["#2ca02c" if k >= 3 else "#ff7f0e" if k > 0 else "#d62728" for k in per_target_kept]
    ax.scatter(tx, ty, s=60, marker="x", c=colours, label="target (green ≥3 images, orange 1–2, red 0)")
    for t, x, y in zip(targets, tx, ty):
        ax.annotate(t["pid"], (x, y), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_aspect("equal")
    ax.set_xlabel(f"Easting (m, EPSG:{args.epsg})")
    ax.set_ylabel("Northing (m)")
    ax.set_title("USGS South Fork: image centres (EXIF GPS) vs RTK targets")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(root / "subset.png", dpi=120)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_target"}, indent=2))


if __name__ == "__main__":
    main()
