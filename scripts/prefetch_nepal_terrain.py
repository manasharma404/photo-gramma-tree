"""Offline terrain for the Nepal corridor (Trishuli-Prithvi, the 26 Aug 2026 case study).

Run once while online (downloads 4 tiles, about 170 MB), then everything works with Wi-Fi off:
    uv run python scripts/prefetch_nepal_terrain.py
Rebuild from tiles already on disk:
    uv run python scripts/prefetch_nepal_terrain.py --offline

Source: Copernicus DEM GLO-30 Public (30 m), free public copy on AWS open data
(https://copernicus-dem-30m.s3.amazonaws.com/readme.html). It is a SURFACE model: heights include trees and
buildings, not bare ground. It shows the terrain BEFORE the flood only in the sense that it predates it
(the data were collected 2011-2015); it is far coarser than a drone height model, so it is context, not evidence.

Writes (gitignored):
  data/prefetch/copernicus_nepal/*.tif              the 4 source tiles, untouched
  data/projects/nepal/terrain/dem_utm45n_30m.tif    corridor heights, UTM zone 45N (EPSG:32645), 30 m cells
  data/projects/nepal/terrain/relief_utm45n_30m.tif shaded relief (grey, light from the north-west), RGB
  data/projects/nepal/tiles/relief/{z}/{x}/{y}.png  web-map tiles of the relief, zoom 8-13 (pipeline.tiles)
  data/projects/nepal/tiles/terrain/                height grid + texture for the 3D view (pipeline.terrain)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "prefetch" / "copernicus_nepal"
OUT = ROOT / "data" / "projects" / "nepal" / "terrain"
BBOX = {"south": 27.720, "north": 28.320, "west": 84.800, "east": 85.450}  # same box as scripts/prefetch_nepal.py
MARGIN = 0.02  # degrees, so the edges of the road box are not cut off by the reprojection
TILES = ["N27_00_E084_00", "N27_00_E085_00", "N28_00_E084_00", "N28_00_E085_00"]
URL = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"
UTM = "EPSG:32645"


def fetch(offline: bool) -> list[Path]:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in TILES:
        n = f"Copernicus_DSM_COG_10_{t}_DEM"
        p = SRC_DIR / f"{n}.tif"
        if not p.exists():
            if offline:
                sys.exit(f"missing {p} (run once without --offline while online)")
            print("downloading", n)
            urllib.request.urlretrieve(URL.format(n=n), p)
        paths.append(p)
    return paths


def hillshade(z: np.ndarray, cell: float, az: float = 315.0, alt: float = 45.0) -> np.ndarray:
    gy, gx = np.gradient(z, cell)  # rows run north->south, so gy is minus the northward slope
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gy, gx)
    a, e = np.radians(360.0 - az + 90.0), np.radians(alt)
    s = np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect)
    return np.clip(s, 0, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="use tiles already on disk; never download")
    args = ap.parse_args()
    paths = fetch(args.offline)
    OUT.mkdir(parents=True, exist_ok=True)

    srcs = [rasterio.open(p) for p in paths]
    box = (BBOX["west"] - MARGIN, BBOX["south"] - MARGIN, BBOX["east"] + MARGIN, BBOX["north"] + MARGIN)
    # the tiles declare no nodata value; use NaN so the reprojection's edges are "no data", not blended with 0 m
    mosaic, tr = merge(srcs, bounds=box, nodata=np.nan, dtype="float32")
    crs, nodata = srcs[0].crs, np.nan
    for s in srcs:
        s.close()

    dst_tr, w, h = calculate_default_transform(crs, UTM, mosaic.shape[2], mosaic.shape[1], *box, resolution=30)
    dem = np.full((h, w), np.nan, np.float32)
    reproject(mosaic[0].astype(np.float32), dem, src_transform=tr, src_crs=crs, src_nodata=nodata,
              dst_transform=dst_tr, dst_crs=UTM, dst_nodata=np.nan, resampling=Resampling.bilinear)
    prof = dict(driver="GTiff", width=w, height=h, crs=UTM, transform=dst_tr, tiled=True, compress="deflate")
    dem_path = OUT / "dem_utm45n_30m.tif"
    with rasterio.open(dem_path, "w", count=1, dtype="float32", nodata=np.nan, **prof) as d:
        d.write(dem, 1)

    valid = np.isfinite(dem)
    shade = hillshade(np.where(valid, dem, np.nanmedian(dem)), 30.0)
    grey = (40 + 215 * shade).astype(np.uint8)
    grey[~valid] = 0
    rel_path = OUT / "relief_utm45n_30m.tif"
    # RGBA: pipeline.tiles and pipeline.terrain read "where is there data" from the alpha band; without one,
    # pipeline.terrain would read band 1 and drop every dark (shaded) slope as missing.
    with rasterio.open(rel_path, "w", count=4, dtype="uint8", **prof) as d:
        for b in (1, 2, 3):
            d.write(grey, b)
        d.write((valid * 255).astype(np.uint8), 4)

    wsen = transform_bounds(UTM, "EPSG:4326", *rasterio.open(dem_path).bounds)
    print(f"DEM {w}x{h} cells at 30 m, heights {np.nanmin(dem):.0f}-{np.nanmax(dem):.0f} m, "
          f"{100 * valid.mean():.1f}% filled, WGS84 bounds {[round(v, 3) for v in wsen]}")

    py = sys.executable
    subprocess.run([py, "-m", "pipeline.tiles", "--ortho", str(rel_path), "--project", "nepal",
                    "--layer", "relief", "--min-zoom", "8", "--max-zoom", "13"], cwd=ROOT, check=True)
    subprocess.run([py, "-m", "pipeline.terrain", "--dsm", str(dem_path), "--ortho", str(rel_path),
                    "--project", "nepal"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
