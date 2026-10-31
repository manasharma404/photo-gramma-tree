"""Cut an orthophoto into web-map tiles (XYZ, EPSG:3857, 256 px PNG) for offline MapLibre.

    python -m pipeline.tiles --ortho <orthophoto.tif> --project <p> [--min-zoom 14] [--max-zoom 20]

Writes data/projects/<p>/tiles/ortho/{z}/{x}/{y}.png and tiles/ortho/meta.json
(bounds, zooms, tile count). api/main.py serves them at /tiles/<p>/ortho/{z}/{x}/{y}.png.
Fully transparent tiles are skipped.
"""
import argparse
import io
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject, transform_bounds

ROOT = Path(__file__).resolve().parent.parent
HALF = 20037508.342789244  # half the width of the Web Mercator world in metres
TILE = 256


def tile_bounds(z, x, y):
    size = 2 * HALF / 2 ** z
    return (-HALF + x * size, HALF - (y + 1) * size, -HALF + (x + 1) * size, HALF - y * size)


def tiles_for(bounds_3857, z):
    size = 2 * HALF / 2 ** z
    x0 = int(math.floor((bounds_3857[0] + HALF) / size))
    x1 = int(math.floor((bounds_3857[2] + HALF) / size))
    y0 = int(math.floor((HALF - bounds_3857[3]) / size))
    y1 = int(math.floor((HALF - bounds_3857[1]) / size))
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def render(src, z, x, y):
    """Warp one tile straight from the source (handles tiles that hang over the map's edge)."""
    b = tile_bounds(z, x, y)
    bands = min(src.count, 4)
    arr = np.zeros((bands, TILE, TILE), np.uint8)
    reproject(source=rasterio.band(src, list(range(1, bands + 1))), destination=arr,
              dst_transform=from_bounds(*b, TILE, TILE), dst_crs="EPSG:3857",
              resampling=Resampling.bilinear, dst_nodata=0)
    if bands == 3:
        alpha = (arr.sum(axis=0) > 0).astype(np.uint8) * 255
        arr = np.concatenate([arr, alpha[None]], axis=0)
    if not arr[3].any():
        return None
    return Image.fromarray(np.moveaxis(arr.astype(np.uint8), 0, -1), "RGBA")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ortho", type=Path, required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--min-zoom", type=int, default=14)
    ap.add_argument("--max-zoom", type=int, default=20)
    args = ap.parse_args()
    out = ROOT / "data" / "projects" / args.project / "tiles" / "ortho"
    out.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.ortho) as src:
        b3857 = transform_bounds(src.crs, "EPSG:3857", *src.bounds)
        written = 0
        for z in range(args.min_zoom, args.max_zoom + 1):
            n = 0
            for x, y in tiles_for(b3857, z):
                img = render(src, z, x, y)
                if img is None:
                    continue
                p = out / str(z) / str(x)
                p.mkdir(parents=True, exist_ok=True)
                img.save(p / f"{y}.png", optimize=False)
                n += 1
            written += n
            print(f"z{z}: {n} tiles")
        wsen = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    meta = {"source": str(args.ortho).replace("\\", "/"), "bounds_wsen": [round(v, 7) for v in wsen],
            "min_zoom": args.min_zoom, "max_zoom": args.max_zoom, "tiles": written,
            "url": f"/tiles/{args.project}/ortho/{{z}}/{{x}}/{{y}}.png"}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
