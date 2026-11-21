"""Bake the home page's callout anchors (web/src/assets/story_anchors.json) from our own files.

- Checkpoints: the RTK checkpoints of the run the page quotes (its accuracy.json): where each one truly is,
  and how far our map put it (horizontal error from dx, dy). No ground control was used to make that map.
- Roads: OpenStreetMap road lines (our roads/segments.geojson), clipped to the dots' extent.

Positions are metres east / north of the dots file's centre (EPSG:32611), the same frame the page draws in.
Run after scripts/bake_slide_dots.py:  python scripts/bake_story_anchors.py
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, box, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
DOTS = ROOT / "web/src/assets/slide_dots.bin"
OUT = ROOT / "web/src/assets/story_anchors.json"


def main() -> None:
    raw = DOTS.read_bytes()
    hl = struct.unpack("<I", raw[:4])[0]
    head = json.loads(raw[4 : 4 + hl])
    n = head["n"]
    o = 4 + hl
    xs = struct.unpack(f"<{n}h", raw[o : o + 2 * n])
    ys = struct.unpack(f"<{n}h", raw[o + 2 * n : o + 4 * n])
    ex, ey = max(abs(v) for v in xs) / 10, max(abs(v) for v in ys) / 10  # half extents, metres
    cx, cy = head["centre_utm"]
    to_utm = Transformer.from_crs("EPSG:4326", head["crs"], always_xy=True).transform

    def local(lon: float, lat: float) -> tuple[float, float]:
        e, nn = to_utm(lon, lat)
        return round(e - cx, 1), round(nn - cy, 1)

    acc_path = ROOT / head["numbers"]["map"]["source"].split(",")[0].replace("\\", "/").rsplit("/", 1)[0] / "accuracy.json"
    acc = json.loads(acc_path.read_text(encoding="utf-8"))
    cps = []
    for p in acc.get("per_point", []):
        if p.get("lon") is None or p.get("dx_m") is None:
            continue
        e, nn = local(p["lon"], p["lat"])
        cps.append({"id": p["id"], "e": e, "n": nn, "error_h_m": round(math.hypot(p["dx_m"], p["dy_m"]), 2),
                    "found_by": p.get("found_by")})

    seg_path = ROOT / "data/projects/southfork_f01_4/roads/segments.geojson"
    segs = json.loads(seg_path.read_text(encoding="utf-8"))
    clip = box(-ex, -ey, ex, ey)
    roads = []
    for f in segs["features"]:
        g = transform(lambda lon, lat, z=None: local(lon, lat), shape(f["geometry"]))
        g = g.intersection(clip)
        if g.is_empty:
            continue
        parts = [g] if isinstance(g, LineString) else list(getattr(g, "geoms", []))
        for part in parts:
            if isinstance(part, LineString) and part.length > 3:
                roads.append({"id": f["properties"]["segment_id"], "highway": f["properties"].get("highway"),
                              "xy": [[round(a, 1), round(b, 1)] for a, b in part.simplify(1.0).coords]})

    out = {
        # the measured numbers the home page quotes, copied from the dots file's header (which names their sources)
        "numbers": {"map": head["numbers"]["map"], "photos": head.get("photos"), "heights": head.get("heights")},
        "frame": "metres east / north of centre_utm in the dots file",
        "checkpoints": {"source": str(acc_path.relative_to(ROOT)).replace("\\", "/"), "run_id": acc.get("run_id"),
                        "used_gcps": acc.get("used_gcps"), "method": acc.get("checkpoint_method"), "points": cps},
        "roads": {"source": "data/projects/southfork_f01_4/roads/segments.geojson (OpenStreetMap, ODbL)",
                  "n_lines": len(roads), "lines": roads},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"checkpoints {len(cps)}, road lines {len(roads)} -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")
    for c in cps:
        print(f"  {c['id']}: e {c['e']} n {c['n']} error {c['error_h_m']} m")


if __name__ == "__main__":
    main()
