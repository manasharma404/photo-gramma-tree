"""Make the landing page's small images from OUR data (USGS public survey processed by us), plus site facts.

    uv run python web/scripts/landing_thumbs.py --ortho <orthophoto.tif> --terrain-thumb <thumb.png> \
        --dashboard <screenshot.png> --rtk <rtk.csv>

Writes web/public/landing/{ortho,terrain,dashboard}.jpg and prints the site centre and median ground
height (orthometric, from the RTK ground points inside the map) for the landing page's coordinate labels.
"""
import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling

OUT = Path(__file__).resolve().parent.parent / "public" / "landing"


def square(img, size=360):
    w, h = img.size
    s = min(w, h)
    return img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((size, size), Image.LANCZOS)


def hillshade(dsm_path, window_m=140, size=360):
    """Grey shaded relief of our height model (light from the north-west), centred on the data."""
    with rasterio.open(dsm_path) as ds:
        # centre on the densest real data (a median can land in a gap ODM filled in, which shows as streaks)
        m = (ds.dataset_mask(out_shape=(ds.height // 16, ds.width // 16)) > 0).astype(float)
        k = max(3, int(window_m / abs(ds.transform.a) / 16))
        from scipy.ndimage import uniform_filter
        r, c = np.unravel_index(np.argmax(uniform_filter(m, size=k)), m.shape)
        x, y = ds.xy(int(r) * 16, int(c) * 16)
        h = window_m / 2
        win = rasterio.windows.from_bounds(x - h, y - h, x + h, y + h, ds.transform)
        z = ds.read(1, window=win, out_shape=(size, size), resampling=Resampling.average, boundless=True, masked=True)
    zf = np.ma.filled(z.astype(float), np.nan)
    zf = np.where(np.isfinite(zf), zf, np.nanmedian(zf))
    cell = window_m / size
    gy, gx = np.gradient(zf, cell)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    img = (np.clip(shade, 0, 1) * 200 + 40).astype(np.uint8)
    img[np.ma.getmaskarray(z)] = 236
    return Image.fromarray(img).convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ortho", type=Path, required=True)
    ap.add_argument("--terrain-thumb", type=Path, default=None)
    ap.add_argument("--dsm", type=Path, default=None, help="use a hillshade of this DSM for the terrain thumbnail")
    ap.add_argument("--dashboard", type=Path, required=True)
    ap.add_argument("--rtk", type=Path, required=True)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.ortho) as ds:
        # a 60 m window at the centre of the valid area, read at ~0.17 m/px
        mask = ds.dataset_mask(out_shape=(ds.height // 20, ds.width // 20))
        rows, cols = np.nonzero(mask)
        r, c = int(np.median(rows)) * 20, int(np.median(cols)) * 20
        x, y = ds.xy(r, c)
        half = 30
        win = rasterio.windows.from_bounds(x - half, y - half, x + half, y + half, ds.transform)
        rgb = ds.read([1, 2, 3], window=win, out_shape=(3, 360, 360), resampling=Resampling.average, boundless=True)
        Image.fromarray(np.moveaxis(rgb, 0, -1)).save(OUT / "ortho.jpg", quality=86)
        to_wgs = Transformer.from_crs(ds.crs, 4326, always_xy=True)
        lon, lat = to_wgs.transform(x, y)
        b = ds.bounds
        to_map = Transformer.from_crs(4326, ds.crs, always_xy=True)

    if args.dsm:
        hillshade(args.dsm).save(OUT / "terrain.jpg", quality=86)
    else:
        t = Image.open(args.terrain_thumb).convert("RGBA")
        bg = Image.new("RGBA", t.size, (230, 225, 214, 255))
        square(Image.alpha_composite(bg, t).convert("RGB")).save(OUT / "terrain.jpg", quality=86)

    d = Image.open(args.dashboard).convert("RGB")
    w, h = d.size
    square(d.crop((int(w * 0.31), int(h * 0.07), int(w * 0.86), int(h * 0.78)))).save(OUT / "dashboard.jpg", quality=86)

    with open(args.rtk, encoding="utf-8-sig") as f:
        hts = []
        for row in csv.DictReader(f):
            if row["code"] != "TOPO":
                continue
            px, py = to_map.transform(float(row["longitude"]), float(row["latitude"]))
            if b.left <= px <= b.right and b.bottom <= py <= b.top:
                hts.append(float(row["orthometric_ht_m"]))
    print(f"site centre: {lat:.4f} N, {abs(lon):.4f} {'W' if lon < 0 else 'E'}")
    print(f"median ground height (orthometric, {len(hts)} RTK points): {np.median(hts):.0f} m" if hts else "no RTK points in map")
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
