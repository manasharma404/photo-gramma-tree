"""Relative vertical accuracy: height model vs surveyed ground points after removing the constant offset.

    python -m accuracy.vertical --dtm <dtm.tif> --rtk <rtk.csv> --accuracy <accuracy.json>

Consumer GPS puts the whole model at the wrong absolute height (a near-constant offset), but
measurements like debris volume, pile height and span use heights *relative to nearby ground*,
where that offset cancels. This adds to accuracy.json:

  "vertical_relative": {"std_m": spread after removing the mean offset, "offset_m": that offset, "n": points, ...}

The ground points are sampled at their surveyed position plus the map's measured mean horizontal
shift (from accuracy.json per_point), so the horizontal error doesn't inflate the vertical one.
measure/ uses std_m for height and volume tolerances; the absolute RMSE_V stays in "vertical".
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dtm", type=Path, required=True)
    ap.add_argument("--rtk", type=Path, required=True)
    ap.add_argument("--accuracy", type=Path, required=True)
    args = ap.parse_args()
    acc = json.loads(args.accuracy.read_text(encoding="utf-8"))
    pts = acc["per_point"]
    shift = (float(np.mean([p["dx_m"] for p in pts])), float(np.mean([p["dy_m"] for p in pts])))

    with rasterio.open(args.dtm) as ds, open(args.rtk, encoding="utf-8-sig") as f:
        to_map = Transformer.from_crs(4326, ds.crs, always_xy=True)
        rows = [r for r in csv.DictReader(f) if r["code"] == "TOPO"]
        xy = np.array([to_map.transform(float(r["longitude"]), float(r["latitude"])) for r in rows]) + np.array(shift)
        ell = np.array([float(r["ellipsoid_ht_m"]) for r in rows])
        z = np.array([v[0] for v in ds.sample(xy)], float)
        ok = np.isfinite(z) & (z != ds.nodata) & (z > 0)
    dz = z[ok] - ell[ok]
    acc["vertical_relative"] = {
        "std_m": round(float(dz.std()), 2),
        "offset_m": round(float(dz.mean()), 2),
        "n": int(ok.sum()),
        "reference": "USGS RTK ground (TOPO) points, ellipsoid heights",
        "surface": str(args.dtm).replace("\\", "/"),
        "horizontal_shift_applied_m": [round(shift[0], 2), round(shift[1], 2)],
        "method": "DTM minus surveyed ground height; std after removing the mean offset (absolute heights are off by offset_m; "
                  "heights relative to nearby ground are good to about std_m)",
    }
    args.accuracy.write_text(json.dumps(acc, indent=2), encoding="utf-8")
    print(json.dumps(acc["vertical_relative"], indent=2))


if __name__ == "__main__":
    main()
