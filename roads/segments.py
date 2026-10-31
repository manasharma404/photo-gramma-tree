"""Measure road segments on the height model -> segments.geojson and places.geojson (contracts).

    python -m roads.segments --osm data/prefetch/osm_southfork.gpkg --dsm <dsm.tif> [--dtm <dtm.tif>] \
        [--accuracy <accuracy.json>] --out <dir>

Method (brief section 9), per segment of <= 50 m:
1. Stations every 1 m along the centreline; a cross-section across the corridor every 0.1 m.
2. Road surface per station = a low percentile of the cross-section; a smooth profile
   (degree <= 2) is fitted along the segment, stations far above it are set aside and
   the profile refitted.
3. Cells higher than `obstruction_min_m` above the profile are obstructions. Per station
   the clear width is the longest run of unobstructed, visible cells.
4. Cells where DSM - DTM > `canopy_min_m` are tree canopy: the ground is not visible there,
   so they count against coverage instead of as obstructions.
This module only measures. Status per vehicle comes from the teammate's assessment engine
(/advisor/state). Limitation: debris covering a whole segment end to end lifts the fitted
surface itself and is under-measured.
"""
import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import jsonschema
import numpy as np
import rasterio
import yaml
from shapely.geometry import LineString, MultiLineString, mapping
from shapely.ops import substring, transform as shp_transform
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config/roads.yaml").read_text(encoding="utf-8"))


def split_line(line, max_len):
    n = max(1, int(np.ceil(line.length / max_len)))
    step = line.length / n
    return [substring(line, i * step, (i + 1) * step) for i in range(n)]


def corridor_width(row):
    w = row.get("width")
    try:
        return float(str(w).replace("m", "").strip()), "osm_tag"
    except (TypeError, ValueError):
        table = CONFIG["default_width_by_class_m"]
        return float(table.get(row.get("highway"), table["other"])), "default_by_class(PLACEHOLDER)"


def sample(ds, xs, ys):
    """Sample a raster at points; NaN where outside or nodata."""
    rows, cols = rasterio.transform.rowcol(ds.transform, xs, ys)
    rows, cols = np.asarray(rows), np.asarray(cols)
    out = np.full(rows.shape, np.nan)
    ok = (rows >= 0) & (rows < ds.height) & (cols >= 0) & (cols < ds.width)
    if ok.any():
        r0, r1, c0, c1 = rows[ok].min(), rows[ok].max() + 1, cols[ok].min(), cols[ok].max() + 1
        win = ds.read(1, window=((r0, r1), (c0, c1)), masked=True)
        vals = win[rows[ok] - r0, cols[ok] - c0]
        out[ok] = np.where(np.ma.getmaskarray(vals), np.nan, np.ma.getdata(vals))
    return out


def fit_surface(dist, z, obstruction_min):
    """Robust smooth profile along the segment; returns fitted surface at each station."""
    ok = np.isfinite(z)
    if ok.sum() < 3:
        return np.full_like(z, np.nanmedian(z) if ok.any() else np.nan)
    keep = ok.copy()
    deg = 2 if ok.sum() >= 8 else 1
    for _ in range(3):
        coef = np.polyfit(dist[keep], z[keep], deg)
        fit = np.polyval(coef, dist)
        new_keep = ok & (z - fit <= obstruction_min)
        if new_keep.sum() < deg + 2 or (new_keep == keep).all():
            break
        keep = new_keep
    return np.polyval(coef, dist)


def longest_run(mask):
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def cross_slopes(zv, offs, obstruction_min):
    """Sideways slope of the ground: fitted per station to the low cells, then one median value for
    the whole segment (<= 50 m), so debris covering part of the width at a few stations can't tilt it."""
    b = np.full(zv.shape[0], np.nan)
    for i, row in enumerate(zv):
        keep = np.isfinite(row)
        if keep.sum() < 5:
            continue
        for _ in range(3):
            coef = np.polyfit(offs[keep], row[keep], 1)
            new = np.isfinite(row) & (row - np.polyval(coef, offs) <= obstruction_min / 2)
            if new.sum() < 5 or (new == keep).all():
                break
            keep = new
        b[i] = coef[0]
    fitted = np.isfinite(b)
    return np.full(zv.shape[0], float(np.median(b[fitted])) if fitted.any() else 0.0)


def vegetation_mask(ortho, X, Y, exg_min):
    """Green cells by the excess-green colour index (2g - r - b on chromatic coordinates).

    A plain colour rule, not a model: green = vegetation, which we can't see through,
    so it counts against coverage instead of as an obstruction.
    """
    rows, cols = rasterio.transform.rowcol(ortho.transform, X.ravel(), Y.ravel())
    rows, cols = np.asarray(rows), np.asarray(cols)
    ok = (rows >= 0) & (rows < ortho.height) & (cols >= 0) & (cols < ortho.width)
    veg = np.zeros(rows.shape, bool)
    if ok.any():
        r0, r1, c0, c1 = rows[ok].min(), rows[ok].max() + 1, cols[ok].min(), cols[ok].max() + 1
        rgb = ortho.read([1, 2, 3], window=((r0, r1), (c0, c1))).astype(float)
        R, G, B = (rgb[k, rows[ok] - r0, cols[ok] - c0] for k in range(3))
        s = R + G + B
        s[s == 0] = 1
        veg[ok] = (2 * G - R - B) / s > exg_min
    return veg.reshape(X.shape)


def measure_segment(line, width, dsm, dtm=None, ortho=None, cfg=CONFIG):
    step, across = cfg["station_step_m"], cfg["across_step_m"]
    n_st = max(2, int(line.length // step) + 1)
    dist = np.linspace(0, line.length, n_st)
    offs = np.arange(-width / 2 + across / 2, width / 2, across)
    pts = [line.interpolate(d) for d in dist]
    ahead = [line.interpolate(min(d + 0.5, line.length)) for d in dist]
    behind = [line.interpolate(max(d - 0.5, 0)) for d in dist]
    tx = np.array([a.x - b.x for a, b in zip(ahead, behind)])
    ty = np.array([a.y - b.y for a, b in zip(ahead, behind)])
    norm = np.hypot(tx, ty)
    norm[norm == 0] = 1
    nx, ny = -ty / norm, tx / norm
    X = np.array([p.x for p in pts])[:, None] + nx[:, None] * offs[None, :]
    Y = np.array([p.y for p in pts])[:, None] + ny[:, None] * offs[None, :]

    z = sample(dsm, X.ravel(), Y.ravel()).reshape(X.shape)
    visible = np.isfinite(z)
    if dtm is not None:
        g = sample(dtm, X.ravel(), Y.ravel()).reshape(X.shape)
        canopy = np.isfinite(g) & ((z - g) > cfg["canopy_min_m"])
        visible &= ~canopy
    if ortho is not None:
        visible &= ~vegetation_mask(ortho, X, Y, cfg["vegetation_exg_min"])
    zv = np.where(visible, z, np.nan)
    # remove each station's cross-slope (hillside paths tilt sideways), so the uphill edge isn't "debris"
    zv = zv - cross_slopes(zv, offs, cfg["obstruction_min_m"])[:, None] * offs[None, :]
    coverage = float(visible.mean())
    result = {"coverage_fraction": round(coverage, 3)}
    if coverage == 0 or np.isfinite(zv).sum() < 3:
        result.update({"max_obstruction_m": None, "obstructed_length_m": None, "min_clear_width_m": None,
                       "debris_volume_m3": None})
        return result

    with warnings.catch_warnings():  # stations fully under canopy are all-NaN: expected
        warnings.simplefilter("ignore", RuntimeWarning)
        station_low = np.nanpercentile(zv, cfg["surface_percentile"], axis=1)
    surface = fit_surface(dist, station_low, cfg["obstruction_min_m"])
    height = zv - surface[:, None]
    obstructed = height > cfg["obstruction_min_m"]
    clear = visible & ~obstructed
    clear_w = np.array([longest_run(row) for row in clear]) * across
    measured_station = visible.mean(axis=1) >= 0.5
    obs_h = np.where(obstructed, height, 0.0)
    result.update({
        "max_obstruction_m": round(float(np.nanmax(obs_h)), 2) if obstructed.any() else 0.0,
        "obstructed_length_m": round(float((obstructed.any(axis=1)).sum() * step), 1),
        "min_clear_width_m": round(float(clear_w[measured_station].min()), 2) if measured_station.any() else None,
        "debris_volume_m3": round(float(np.nansum(obs_h) * step * across), 2),
        "_obstructed_area_m2": float(obstructed.sum() * step * across),
    })
    return result


def explode(geom):
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return [geom] if isinstance(geom, LineString) else []


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--osm", type=Path, required=True)
    ap.add_argument("--dsm", type=Path, required=True)
    ap.add_argument("--dtm", type=Path, default=None)
    ap.add_argument("--ortho", type=Path, default=None, help="orthophoto, to set aside vegetation by colour")
    ap.add_argument("--accuracy", type=Path, default=None, help="accuracy.json, for tolerances")
    ap.add_argument("--landing-zones", type=Path, default=None, help="measurement.json of type landing_zones")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rmse_v = None
    if args.accuracy and args.accuracy.exists():
        acc = json.loads(args.accuracy.read_text(encoding="utf-8"))
        # debris heights are relative to the fitted road surface, so a constant absolute offset cancels:
        # prefer the relative vertical spread (accuracy/vertical.py) over the absolute RMSE_V
        rmse_v = (acc.get("vertical_relative") or {}).get("std_m", acc["vertical"]["rmse_v_m"])

    dsm = rasterio.open(args.dsm)
    dtm = rasterio.open(args.dtm) if args.dtm else None
    ortho = rasterio.open(args.ortho) if args.ortho else None
    roads = gpd.read_file(args.osm, layer="roads").to_crs(dsm.crs)
    to_wgs = Transformer.from_crs(dsm.crs, 4326, always_xy=True).transform

    features, n = [], 0
    for _, row in roads.iterrows():
        width, width_src = corridor_width(row)
        osm_id = row.get("id") if "id" in row else row.get("osmid")
        for part in explode(row.geometry):
            for seg in split_line(part, CONFIG["segment_max_m"]):
                n += 1
                m = measure_segment(seg, width, dsm, dtm, ortho)
                area = m.pop("_obstructed_area_m2", None)
                props = {
                    "mock": False,
                    "segment_id": f"seg_{n:04d}",
                    "osm_way_id": int(str(osm_id).split("/")[-1]) if osm_id is not None and str(osm_id) != "nan" else None,
                    "highway": str(row.get("highway")),
                    "length_m": round(seg.length, 1),
                    "corridor_width_m": width,
                    "corridor_width_source": width_src,
                    **m,
                    "debris_volume_tolerance_m3": round(rmse_v * area, 1) if (rmse_v and area) else None,
                    "ml": {"p_blocked": None, "model": None},
                    "measured": m["coverage_fraction"] > 0,
                }
                features.append({"type": "Feature", "geometry": mapping(shp_transform(to_wgs, seg)),
                                 "properties": props})

    segments = {"type": "FeatureCollection", "mock": False,
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": {"dsm": str(args.dsm).replace("\\", "/"), "dtm": str(args.dtm).replace("\\", "/") if args.dtm else None,
                           "osm": "© OpenStreetMap contributors (ODbL)", "config": "config/roads.yaml"},
                "features": features}
    segments = json.loads(json.dumps(segments))  # shapely gives tuples; the contract wants plain JSON arrays
    schema = json.loads((ROOT / "contracts/segments.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(segments, schema)
    (args.out / "segments.geojson").write_text(json.dumps(segments), encoding="utf-8")

    places = places_geojson(args.osm, args.landing_zones, segments)
    (args.out / "places.geojson").write_text(json.dumps(places), encoding="utf-8")

    covered = [f["properties"] for f in features if f["properties"]["measured"]]
    print(f"{len(features)} segments ({len(covered)} with data), {len(places['features'])} places -> {args.out}")
    for p in covered:
        print(f"  {p['segment_id']} {p['highway']:<12} cov {p['coverage_fraction']:.2f}  clear {p['min_clear_width_m']} m"
              f"  max obstr {p['max_obstruction_m']} m  obstructed {p['obstructed_length_m']} m  vol {p['debris_volume_m3']} m3")


def places_geojson(osm_path, landing_zones_path, segments):
    from shapely.geometry import shape
    places = gpd.read_file(osm_path, layer="places").to_crs(4326)
    seg_geoms = [(f["properties"]["segment_id"], shape(f["geometry"])) for f in segments["features"]]
    to_m = Transformer.from_crs(4326, 32611, always_xy=True).transform
    seg_m = [(sid, shp_transform(to_m, g)) for sid, g in seg_geoms]

    def nearest(pt):
        pm = shp_transform(to_m, pt)
        return min(seg_m, key=lambda s: s[1].distance(pm))[0] if seg_m else None

    feats = []
    for i, row in places.iterrows():
        kind = "settlement" if row.get("place") else "other_facility"
        if row.get("tourism") == "camp_site":
            kind = "shelter"
        feats.append({"type": "Feature", "geometry": mapping(row.geometry),
                      "properties": {"mock": False, "place_id": f"osm_place_{i}", "name": row.get("name") if isinstance(row.get("name"), str) else None,
                                     "kind": kind, "source": "osm", "population": None,
                                     "population_source": "PLACEHOLDER", "nearest_segment_id": nearest(row.geometry)}})
    if landing_zones_path and landing_zones_path.exists():
        lz = json.loads(landing_zones_path.read_text(encoding="utf-8"))
        for j, c in enumerate(lz["result"].get("candidates", [])):
            pt = shape(c["polygon"]).centroid
            feats.append({"type": "Feature", "geometry": mapping(pt),
                          "properties": {"mock": False, "place_id": f"lz_{j + 1}", "name": f"Landing zone candidate {j + 1}",
                                         "kind": "landing_zone", "source": "landing_zones", "population": None,
                                         "population_source": "not applicable", "nearest_segment_id": nearest(pt)}})
    out = json.loads(json.dumps({"type": "FeatureCollection", "mock": False, "features": feats}))
    schema = json.loads((ROOT / "contracts/places.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(out, schema)
    return out


if __name__ == "__main__":
    main()
