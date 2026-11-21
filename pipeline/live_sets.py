"""Photo sets for the growing map: a list of photos in arrival order, each with its time and GPS.

    uv run python -m pipeline.live_sets usgs  --images data/projects/southfork_f01_4/images --name southfork_block
    uv run python -m pipeline.live_sets video --images data/projects/rec28_campus/images --log data/raw/rec28/flightlog_155239.csv \
        --offset 16.05 --start 40 --step 0.5 --name rec28_campus

Writes data/live_sets/<name>.json (gitignored):
  {"name", "epsg", "s0", "reduce", "cross_m", "source", "photos": [{"file", "t", "lon", "lat"}]}
- usgs: GPS and time from each photo's own EXIF (USGS South Fork block, public domain).
- video: frames named f<k>.jpg taken from a video at --start + (k-1) * --step seconds; GPS from the flight
  controller's log at (video time + --offset). The offset for REC_0028 (16.05 s) was found in Test 7e by matching
  the map's track to the GPS track.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "live_sets"


def utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def _dms(v, ref) -> float:
    d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
    return -d if ref in ("S", "W") else d


def from_usgs(images: Path) -> list[dict]:
    photos = []
    for f in sorted(images.glob("*.jp*g")):
        ex = Image.open(f)._getexif() or {}
        tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
        gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in (tags.get("GPSInfo") or {}).items()}
        if "GPSLatitude" not in gps:
            continue
        t = datetime.strptime(tags["DateTimeOriginal"], "%Y:%m:%d %H:%M:%S").timestamp()
        photos.append({"file": str(f.relative_to(ROOT)).replace("\\", "/"), "t": t,
                       "lon": _dms(gps["GPSLongitude"], gps["GPSLongitudeRef"]),
                       "lat": _dms(gps["GPSLatitude"], gps["GPSLatitudeRef"])})
    t0 = photos[0]["t"]
    for p in photos:
        p["t"] = round(p["t"] - t0, 3)
    return photos


def from_video(images: Path, log: Path, offset: float, start: float, step: float) -> list[dict]:
    import pandas as pd
    d = pd.read_csv(log, comment="#")
    lt = d.t_ms.to_numpy() / 1000.0
    lat, lon = d.lat_e7.to_numpy() / 1e7, d.lon_e7.to_numpy() / 1e7
    photos = []
    for f in sorted(images.glob("f*.jpg")):
        k = int(re.search(r"f(\d+)", f.stem).group(1))
        tv = start + (k - 1) * step
        tl = tv + offset
        if not (lt[0] <= tl <= lt[-1]):
            continue
        photos.append({"file": str(f.relative_to(ROOT)).replace("\\", "/"), "t": tv,
                       "lon": float(np.interp(tl, lt, lon)), "lat": float(np.interp(tl, lt, lat))})
    t0 = photos[0]["t"]
    for p in photos:
        p["t"] = round(p["t"] - t0, 3)
    return photos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["usgs", "video"])
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--s0", type=float, help="rough metres per reduced pixel (default: 0.12 usgs, 0.05 video)")
    ap.add_argument("--reduce", type=int, help="read photos at 1/reduce size (default: 4 usgs, 2 video)")
    ap.add_argument("--cross-m", type=float, help="neighbouring-line search radius, metres (default: 70 usgs, 30 video)")
    a = ap.parse_args()
    images = a.images if a.images.is_absolute() else ROOT / a.images
    if a.kind == "usgs":
        photos, s0, red, cross, src = from_usgs(images), 0.12, 4, 70.0, "photo EXIF GPS"
    else:
        log = a.log if a.log.is_absolute() else ROOT / a.log
        photos = from_video(images, log, a.offset, a.start, a.step)
        s0, red, cross, src = 0.05, 2, 30.0, f"flight log {log.name}, offset {a.offset} s"
    out = {"name": a.name, "epsg": utm_epsg(photos[0]["lon"], photos[0]["lat"]), "s0": a.s0 or s0,
           "reduce": a.reduce or red, "cross_m": a.cross_m or cross, "source": src, "photos": photos}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{a.name}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    span = photos[-1]["t"] - photos[0]["t"]
    print(f"{a.name}: {len(photos)} photos over {span:.0f} s, EPSG:{out['epsg']}, GPS from {src}")


if __name__ == "__main__":
    main()
