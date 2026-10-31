"""Export a light terrain for the three.js view: heightmap + draped texture.

    python -m pipeline.terrain --dsm <dsm.tif> --ortho <orthophoto.tif> --project <p> [--grid 1024]

Writes data/projects/<p>/tiles/terrain/:
  height.f32    little-endian float32, row-major, north row first; NaN = no data
  texture.jpg   orthophoto resampled to the same bounds
  meta.json     size, bounds (map CRS and WGS84), cell size, height range, CRS
Served by api/main.py at /tiles/<p>/terrain/... . Heights are the DSM's own (absolute
heights carry the vertical error in accuracy.json; the 3D view shows them relative).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject, transform_bounds

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsm", type=Path, required=True)
    ap.add_argument("--ortho", type=Path, required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--grid", type=int, default=1024, help="max cells along the longer side")
    ap.add_argument("--texture", type=int, default=4096, help="max texture pixels along the longer side")
    args = ap.parse_args()
    out = ROOT / "data" / "projects" / args.project / "tiles" / "terrain"
    out.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.dsm) as dsm:
        b = dsm.bounds
        span_x, span_y = b.right - b.left, b.top - b.bottom
        scale = args.grid / max(span_x, span_y)
        w, h = max(2, int(span_x * scale)), max(2, int(span_y * scale))
        z = dsm.read(1, out_shape=(h, w), masked=True, resampling=Resampling.average).astype("float32")
        z = np.where(np.ma.getmaskarray(z), np.nan, np.ma.getdata(z)).astype("<f4")
        if dsm.nodata is not None:
            z[z == dsm.nodata] = np.nan
        crs = dsm.crs
    # Keep only cells we actually photographed: ODM interpolates heights across gaps, the orthophoto doesn't.
    with rasterio.open(args.ortho) as ortho:
        seen = np.zeros((h, w), np.uint8)
        alpha_band = ortho.count if ortho.count >= 4 else 1
        reproject(source=rasterio.band(ortho, alpha_band), destination=seen,
                  dst_transform=from_bounds(b.left, b.bottom, b.right, b.top, w, h), dst_crs=crs,
                  resampling=Resampling.min, dst_nodata=0)
    # GDAL nudges valid 0s to 1 when 0 is the output nodata, so "transparent" is < 128, not == 0
    z[seen < 128] = np.nan
    z.tofile(out / "height.f32")

    tscale = args.texture / max(span_x, span_y)
    tw, th = int(span_x * tscale), int(span_y * tscale)
    with rasterio.open(args.ortho) as ortho:
        rgb = np.zeros((3, th, tw), np.uint8)
        reproject(source=rasterio.band(ortho, [1, 2, 3]), destination=rgb,
                  dst_transform=from_bounds(b.left, b.bottom, b.right, b.top, tw, th), dst_crs=crs,
                  resampling=Resampling.bilinear, dst_nodata=0)
    Image.fromarray(np.moveaxis(rgb, 0, -1)).save(out / "texture.jpg", quality=85)

    # Small transparent thumbnail for UI cards: alpha from the orthophoto, cropped to the photographed area.
    with rasterio.open(args.ortho) as ortho:
        alpha = np.zeros((th, tw), np.uint8)
        reproject(source=rasterio.band(ortho, ortho.count if ortho.count >= 4 else 1), destination=alpha,
                  dst_transform=from_bounds(b.left, b.bottom, b.right, b.top, tw, th), dst_crs=crs,
                  resampling=Resampling.nearest, dst_nodata=0)
    alpha = np.where(alpha >= 128, 255, 0).astype(np.uint8)  # GDAL nudges valid 0s to 1 (see above)
    rows, cols = np.nonzero(alpha)
    if rows.size:
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        rgba = np.dstack([np.moveaxis(rgb, 0, -1), alpha])[r0:r1, c0:c1]
        thumb = Image.fromarray(rgba, "RGBA")
        thumb.thumbnail((640, 640))
        thumb.save(out / "thumb.png")

    finite = z[np.isfinite(z)]
    meta = {
        "width": w, "height": h, "cell_m": [round(span_x / w, 4), round(span_y / h, 4)],
        "bounds_map": [b.left, b.bottom, b.right, b.top], "crs": str(crs),
        "bounds_wsen": [round(v, 7) for v in transform_bounds(crs, "EPSG:4326", *b)],
        "z_min": round(float(finite.min()), 2), "z_max": round(float(finite.max()), 2),
        "no_data_fraction": round(float(1 - finite.size / z.size), 3),
        "texture": {"file": "texture.jpg", "width": tw, "height": th},
        "thumb": "thumb.png" if (out / "thumb.png").exists() else None,
        "height_file": "height.f32", "dtype": "float32-le", "row_order": "north_first",
        "source": {"dsm": str(args.dsm).replace("\\", "/"), "ortho": str(args.ortho).replace("\\", "/")},
        "url": f"/tiles/{args.project}/terrain/",
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
