"""Data for the motion scenes: our real South Fork surface model and the real camera positions.

Run from the repo root:  uv run python docs/demo/motion/prep_data.py
Writes docs/demo/motion/data/terrain.json. Nothing here is invented: heights come from the full-tier
surface model (trees included), camera positions from the photos' own GPS tags.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[3]
DSM = ROOT / "data/projects/southfork_f01_4/odm_dem/dsm.tif"
IMAGES = ROOT / "data/projects/southfork_f01_4/images"
OUT = Path(__file__).resolve().parent / "data" / "terrain.json"
N = 72  # blocks along the longer side

with rasterio.open(DSM) as r:
    scale = N / max(r.width, r.height)
    w, h = round(r.width * scale), round(r.height * scale)
    a = r.read(1, out_shape=(h, w), resampling=rasterio.enums.Resampling.average, masked=True)
    bounds, cell_m = r.bounds, (r.bounds.right - r.bounds.left) / w
    epsg = r.crs.to_epsg()

mask = ~np.ma.getmaskarray(a)
z = np.where(mask, a.filled(0), 0).astype(float)
zmin, zmax = float(z[mask].min()), float(z[mask].max())

exif = json.loads(subprocess.run(
    ["exiftool", "-n", "-json", "-FileName", "-GPSLatitude", "-GPSLongitude", "-GPSAltitude", str(IMAGES)],
    capture_output=True, text=True, check=True).stdout)
exif.sort(key=lambda e: e["FileName"])
t = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
track = []
for e in exif:
    x, y = t.transform(e["GPSLongitude"], e["GPSLatitude"])
    track.append([round((x - bounds.left) / cell_m, 2), round((bounds.top - y) / cell_m, 2), round(e["GPSAltitude"], 1)])

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({
    "source": "USGS South Fork F01-4, our full-tier surface model (trees included); camera positions from photo GPS",
    "w": w, "h": h, "cell_m": round(cell_m, 3), "zmin": round(zmin, 2), "zmax": round(zmax, 2),
    "z": [[round(float(v), 1) if m else None for v, m in zip(zr, mr)] for zr, mr in zip(z, mask)],
    "track": track,
}), encoding="utf-8")
print(OUT, w, h, "cell", round(cell_m, 2), "m", "relief", round(zmax - zmin, 1), "m", "photos", len(track),
      "track alt", min(p[2] for p in track), max(p[2] for p in track))
