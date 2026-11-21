"""Bake the landing page's dots: the South Fork slide before (USGS lidar, 2021-22) and after (our drone map, 2024).

    uv run python scripts/bake_slide_dots.py [--spacing 1.5] [--png out.png]

Offline: reads only files already on the laptop.
  after  = our bare-ground height model (ODM DTM, `data/active.json`), colours from our orthophoto
  before = USGS 3DEP 1 m lidar terrain, flown 3 Nov 2021 to 23 Sep 2022 (before the 9 Jan 2023 debris flow)

The two were measured differently (our map has no ground control: GPS-only, about +-6 m sideways and metres
vertically), so before comparing them we line the before terrain up with ours: we search the sideways shift
and fit a tilted plane that make the two agree best on ground that did not change (robust statistics, so the
debris itself barely votes). This is a visual alignment for the landing page, NOT a measurement: the page says
"rough height change". The leftover disagreement on stable ground (NMAD) is written into the file and shown.

Output `web/src/assets/slide_dots.bin` (bundled by Vite under /assets/):
  uint32 header length, JSON header (padded to 4 bytes), then for N points:
  int16 x[N], int16 y[N] (decimetres from the centre, x east, y north),
  uint16 z_before[N], uint16 z_after[N] (centimetres above the header's z0),
  uint8 rgb_after[3N] (our orthophoto), uint8 shade_before[N] (hillshade of the lidar terrain),
  uint16 photo[N] (already on a 2-byte boundary: 4 + header + 12 N bytes) (index of the first real drone photo covering the dot; 65535 = none)

Finding (21 Nov): after alignment, the biggest "change" (up to +15 m) sits on the dense forest beside the
channel: there our map's ground model is tree canopy, not ground. So the page does NOT colour height change
as debris; it uses the after terrain and the real photo order. The before terrain stays in the file for later.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from scipy.ndimage import map_coordinates

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "data/prefetch/usgs_1m/USGS_1M_11_x34y403_CA_SierraNevada_B22.tif"
LIVE_RUN = Path("data/live_runs/2026-11-21_153533_live_southfork_block")  # Test 7f, USGS block at flight speed
OUT = ROOT / "web/src/assets/slide_dots.bin"  # imported by web/src/story.js, bundled under /assets/


def warp(path: Path, crs, transform, width: int, height: int, bands, resampling) -> np.ndarray:
    with rasterio.open(path) as src, WarpedVRT(src, crs=crs, transform=transform, width=width, height=height,
                                               resampling=resampling) as vrt:
        return vrt.read(bands, masked=True)


MAP_RUN = Path("data/runs/2026-11-04_2243_southfork_f01_4_middle_middle")  # the measured map we quote (80.2 min)


def numbers(active: dict) -> dict:
    """the page's headline numbers, copied from the files the runs wrote (never typed in)."""
    run = json.loads((ROOT / MAP_RUN / "run.json").read_text())
    acc = json.loads((ROOT / MAP_RUN / "accuracy.json").read_text())
    vr = json.loads((ROOT / active["accuracy"]).read_text()).get("vertical_relative", {})
    return {
        "map": {"source": f"{MAP_RUN}/run.json, accuracy.json", "tier": run["tier"],
                "minutes": round(run["total_seconds"] / 60, 1), "area_ha": round(run["area_ha"], 2),
                "photos": run["inputs"]["count"], "used_gcps": acc["used_gcps"],
                "rmse_h_m": acc["horizontal"]["rmse_h_m"], "n_checkpoints": acc["n_checkpoints"],
                "checkpoint_method": acc.get("checkpoint_method")},
        "heights": {"source": active["accuracy"], "std_m": vr.get("std_m"), "n": vr.get("n")},
    }


def nmad(a: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(a - np.median(a))))


def plane_fit(x, y, dz):
    """robust tilted-plane fit dz ~ a + b x + c y, ignoring the 'changed' tail (debris, trees, edges)."""
    keep = np.ones(dz.size, bool)
    coef = np.zeros(3)
    for _ in range(4):
        A = np.c_[np.ones(keep.sum()), x[keep], y[keep]]
        coef, *_ = np.linalg.lstsq(A, dz[keep], rcond=None)
        r = dz - (coef[0] + coef[1] * x + coef[2] * y)
        s = max(nmad(r[keep]), 0.05)
        keep = np.abs(r) < 3 * s
    return coef, keep


def hillshade(z: np.ndarray, cell: float, az=315.0, alt=40.0) -> np.ndarray:
    gy, gx = np.gradient(z, cell)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, b = np.radians(az), np.radians(alt)
    hs = np.sin(b) * np.cos(slope) + np.cos(b) * np.sin(slope) * np.cos(a - aspect)
    return np.clip(hs, 0, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spacing", type=float, default=1.5, help="metres between dots")
    ap.add_argument("--png", help="optional diagnostic image of the height change")
    args = ap.parse_args()
    active = json.loads((ROOT / "data/active.json").read_text())
    dtm_path, ortho_path = ROOT / active["dtm"], ROOT / active["orthophoto"]

    with rasterio.open(dtm_path) as d:
        crs, b = d.crs, d.bounds
    g = args.spacing
    w, h = int((b.right - b.left) // g), int((b.top - b.bottom) // g)
    tr = from_origin(b.left, b.top, g, g)

    after = warp(dtm_path, crs, tr, w, h, 1, Resampling.average)
    rgb = warp(ortho_path, crs, tr, w, h, [1, 2, 3], Resampling.average)
    # the lidar on a finer 1 m grid with a margin, so the shift search can sample it anywhere
    m, fine = 20.0, 1.0
    ftr = from_origin(b.left - m, b.top + m, fine, fine)
    fw, fh = int((b.right - b.left + 2 * m) / fine), int((b.top - b.bottom + 2 * m) / fine)
    before_f = warp(BEFORE, crs, ftr, fw, fh, 1, Resampling.bilinear)
    before_f = before_f.filled(np.nan).astype(np.float64)

    rows, cols = np.mgrid[0:h, 0:w]
    X = b.left + (cols + 0.5) * g   # dot centres, metres in UTM 11N
    Y = b.top - (rows + 0.5) * g
    valid = ~np.ma.getmaskarray(after) & ~np.ma.getmaskarray(rgb).any(axis=0)
    za = np.asarray(after.filled(np.nan), np.float64)
    valid &= np.isfinite(za)

    def before_at(xs, ys):
        c = (xs - (b.left - m)) / fine - 0.5
        r = ((b.top + m) - ys) / fine - 0.5
        return map_coordinates(before_f, [r, c], order=1, mode="nearest", cval=np.nan)

    xv, yv, zav = X[valid], Y[valid], za[valid]
    xc, yc = xv - xv.mean(), yv - yv.mean()

    # 1) sideways shift: coarse then fine search for the shift that makes stable ground agree best
    def score(sx, sy):
        zb = before_at(xv + sx, yv + sy)
        dz = zav - zb
        ok = np.isfinite(dz)
        coef, keep = plane_fit(xc[ok], yc[ok], dz[ok])
        r = dz[ok] - (coef[0] + coef[1] * xc[ok] + coef[2] * yc[ok])
        return nmad(r[keep]), coef

    best = (np.inf, 0.0, 0.0, None)
    for step, rng, centre in ((2.0, 12.0, (0.0, 0.0)), (0.5, 2.0, None)):
        cx, cy = centre if centre else (best[1], best[2])
        for sx in np.arange(cx - rng, cx + rng + 1e-9, step):
            for sy in np.arange(cy - rng, cy + rng + 1e-9, step):
                s, coef = score(sx, sy)
                if s < best[0]:
                    best = (s, float(sx), float(sy), coef)
    s_nmad, sx, sy, coef = best
    zb = before_at(xv + sx, yv + sy) + coef[0] + coef[1] * xc + coef[2] * yc  # before, lined up with ours
    ok = np.isfinite(zb)
    dz = zav - zb
    stable = np.abs(dz - np.median(dz[ok])) < 3 * s_nmad

    # 2) shade for the before dots (the lidar has no colour)
    zb_grid = np.full((h, w), np.nan)
    zb_grid[valid] = zb
    filled = np.where(np.isfinite(zb_grid), zb_grid, np.nanmedian(zb))
    shade = hillshade(filled, g)[valid]

    keep = ok
    x_dm = np.round((xv - xv.mean()) * 10).astype(np.int16)[keep]
    y_dm = np.round((yv - yv.mean()) * 10).astype(np.int16)[keep]
    z0 = float(np.floor(min(np.nanmin(zav[keep]), np.nanmin(zb[keep]))))
    zb_cm = np.clip(np.round((zb[keep] - z0) * 100), 0, 65535).astype(np.uint16)
    za_cm = np.clip(np.round((zav[keep] - z0) * 100), 0, 65535).astype(np.uint16)
    col = np.stack([rgb[i].filled(0)[valid][keep] for i in range(3)], axis=1).astype(np.uint8)
    sh = np.round(shade[keep] * 255).astype(np.uint8)
    n = int(keep.sum())

    # 3) which real drone photo first covered each dot, in the order the drone took them (growing-map run, Test 7f)
    from matplotlib.path import Path as MPath
    run = json.loads((ROOT / LIVE_RUN / "result.json").read_text())
    photo = np.full(n, 65535, np.uint16)
    pts = np.c_[xv[keep], yv[keep]]
    for fp in sorted(run["footprints"], key=lambda f: f["idx"]):
        inside = MPath(np.asarray(fp["corners_xy"])).contains_points(pts) & (photo == 65535)
        photo[inside] = fp["idx"]
    d = dz[keep]
    header = {
        "n": n, "spacing_m": g, "z0": z0, "crs": f"EPSG:{crs.to_epsg()}",
        "centre_utm": [round(float(xv.mean()), 2), round(float(yv.mean()), 2)],
        "after": {"what": "our bare-ground height model (ODM DTM) and orthophoto", "flown": "2024-04-30",
                  "source": "USGS South Fork aerial images processed by us without ground control"},
        "before": {"what": "USGS 3DEP 1 m lidar terrain", "flown": "2021-11-03 to 2022-09-23",
                   "file": BEFORE.name},
        "event": "debris flow, 2023-01-09",
        "alignment": {"shift_east_m": sx, "shift_north_m": sy, "offset_m": round(float(coef[0]), 2),
                      "tilt_m_per_100m": [round(float(coef[1]) * 100, 3), round(float(coef[2]) * 100, 3)],
                      "stable_ground_nmad_m": round(s_nmad, 2),
                      "stable_share": round(float(stable[keep].mean()), 3),
                      "method": "shift search + robust tilted plane on ground that did not change; visual only"},
        "change_m": {"p5": round(float(np.percentile(d, 5)), 2), "p50": round(float(np.median(d)), 2),
                     "p95": round(float(np.percentile(d, 95)), 2)},
        "photos": {"run": LIVE_RUN.name, "total": int(run["photos_total"]), "placed": int(run["placed"]),
                   "arrival_to_map_s_typical": run.get("arrival_to_placed_s_recent"),
                   "arrival_to_map_s_worst": run.get("arrival_to_placed_s_max"),
                   "dots_covered": int((photo != 65535).sum())},
        "numbers": numbers(active),
        "made": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label": "Change is NOT shown on the page: on the forested side our map's ground model is tree canopy",
    }
    hb = json.dumps(header, separators=(",", ":")).encode()
    hb += b" " * (-len(hb) % 4)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(struct.pack("<I", len(hb)))
        f.write(hb)
        for arr in (x_dm, y_dm, zb_cm, za_cm):
            f.write(arr.astype(arr.dtype.newbyteorder("<")).tobytes())
        f.write(col.tobytes())
        f.write(sh.tobytes())
        f.write(photo.astype("<u2").tobytes())
    print(json.dumps(header, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f} MB, {n} dots)")

    if args.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        grid = np.full((h, w), np.nan)
        vi = np.flatnonzero(valid)[keep]
        grid.flat[vi] = d
        fig, ax = plt.subplots(1, 2, figsize=(12, 6))
        ax[0].imshow(np.dstack([rgb[i].filled(0) for i in range(3)]))
        ax[0].set_title("our orthophoto (after)")
        im = ax[1].imshow(grid, cmap="RdBu_r", vmin=-4, vmax=4)
        ax[1].set_title(f"after - before (m), stable NMAD {s_nmad:.2f} m")
        fig.colorbar(im, ax=ax[1], shrink=0.7)
        fig.savefig(args.png, dpi=90, bbox_inches="tight")
    return 0


if __name__ == "__main__":
    sys.exit(main())
