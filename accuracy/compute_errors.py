"""Positional error at confirmed checkpoints -> accuracy.json (contract).

    python -m accuracy.compute_errors --confirmed <confirmed.json> --rtk <rtk.csv> \
        --run-id <run_id> --out <accuracy.json> [--dsm <dsm.tif>]

confirmed.json lists checkpoints a person has confirmed in the orthophoto:
{"map_epsg": 32611, "note": "...", "points": [{"id": "SF10", "x": ..., "y": ..., "found_by": "manual"}]}

Errors are map minus surveyed, in metres in the map CRS. dz needs a DSM and uses
the RTK ellipsoid height, since ODM's output heights are relative to the WGS84
ellipsoid (from image EXIF). Checkpoints are never used to correct the map.
"""
import argparse
import csv
import json
import math
from pathlib import Path

import jsonschema
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
STANDARD_NOTE = ("ASPRS Positional Accuracy Standards Ed. 2 (2023) ask for at least 30 checkpoints for full "
                 "compliance; this assessment uses n_checkpoints.")


def rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirmed", type=Path, required=True)
    ap.add_argument("--rtk", type=Path, required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dsm", type=Path, default=None)
    ap.add_argument("--datum-note", default=None)
    args = ap.parse_args()

    conf = json.loads(args.confirmed.read_text(encoding="utf-8"))
    with open(args.rtk, encoding="utf-8-sig") as f:
        rtk = {r["pid"]: r for r in csv.DictReader(f)}
    to_map = Transformer.from_crs(4326, conf["map_epsg"], always_xy=True)

    dsm = None
    if args.dsm:
        import rasterio
        dsm = rasterio.open(args.dsm)

    per_point, dxs, dys, dzs, horiz, precisions = [], [], [], [], [], []
    for p in conf["points"]:
        r = rtk[p["id"]]
        sx, sy = to_map.transform(float(r["longitude"]), float(r["latitude"]))
        dx, dy = p["x"] - sx, p["y"] - sy
        dz = None
        if dsm is not None:
            z = next(dsm.sample([(p["x"], p["y"])]))[0]
            if dsm.nodata is None or z != dsm.nodata:
                dz = round(float(z) - float(r["ellipsoid_ht_m"]), 3)
                dzs.append(dz)
        dxs.append(dx)
        dys.append(dy)
        horiz.append(math.hypot(dx, dy))
        if r.get("horiz_precision_m"):
            precisions.append(float(r["horiz_precision_m"]))
        per_point.append({"id": p["id"], "dx_m": round(dx, 3), "dy_m": round(dy, 3), "dz_m": dz,
                          "found_by": p["found_by"]})

    rx, ry = rms(dxs), rms(dys)
    acc = {
        "mock": False,
        "run_id": args.run_id,
        "used_gcps": False,
        "n_checkpoints": len(per_point),
        "checkpoint_method": "rtk",
        "checkpoint_stated_accuracy_m": max(precisions) if precisions else None,
        "datum_note": args.datum_note or conf.get("note"),
        "horizontal": {"rmse_x_m": round(rx, 3), "rmse_y_m": round(ry, 3),
                       "rmse_h_m": round(math.hypot(rx, ry), 3), "max_error_m": round(max(horiz), 3)},
        "vertical": {"rmse_v_m": round(rms(dzs), 3) if dzs else None,
                     "max_error_m": round(max(abs(z) for z in dzs), 3) if dzs else None},
        "relative": [],
        "per_point": per_point,
        "standard_note": STANDARD_NOTE,
    }
    schema = json.loads((ROOT / "contracts/accuracy.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(acc, schema)
    args.out.write_text(json.dumps(acc, indent=2), encoding="utf-8")
    print(json.dumps({k: acc[k] for k in ("n_checkpoints", "horizontal", "vertical")}, indent=2))


if __name__ == "__main__":
    main()
