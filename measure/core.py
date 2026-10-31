"""The four measurements: span, volume, landing zones, working space.

Every function takes geometry in WGS84 (GeoJSON order: lon, lat), reads the run's
DSM/DTM, and returns a measurement.json dict (contracts/measurement.schema.json).
Tolerances come from accuracy.json and are labelled as conservative bounds; when
accuracy is missing the tolerance is null, never a guess.
"""
import json
import math
from pathlib import Path

import numpy as np
import rasterio
import yaml
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import transform as shp_transform

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config/measure.yaml").read_text(encoding="utf-8"))
HELI = yaml.safe_load((ROOT / "config/helicopters.yaml").read_text(encoding="utf-8"))["helicopters"]
BRIDGE = yaml.safe_load((ROOT / "config/bridging.yaml").read_text(encoding="utf-8"))


class Surfaces:
    """The rasters and accuracy of one run."""

    def __init__(self, dsm, dtm=None, accuracy=None, run_id=None):
        self.dsm = rasterio.open(dsm)
        self.dtm = rasterio.open(dtm) if dtm else None
        self.acc = json.loads(Path(accuracy).read_text(encoding="utf-8")) if accuracy and Path(accuracy).exists() else None
        self.run_id = run_id
        self.to_map = Transformer.from_crs(4326, self.dsm.crs, always_xy=True).transform
        self.to_wgs = Transformer.from_crs(self.dsm.crs, 4326, always_xy=True).transform

    @property
    def rmse_h(self):
        return self.acc["horizontal"]["rmse_h_m"] if self.acc else None

    @property
    def rmse_v(self):
        return self.acc["vertical"]["rmse_v_m"] if self.acc else None

    def window(self, ds, bounds, res=None):
        """Read a window as a float array with NaN for nodata; optional resampling to `res` metres."""
        win = from_bounds(*bounds, ds.transform).round_offsets().round_lengths()
        if res:
            h = max(1, int(round((bounds[3] - bounds[1]) / res)))
            w = max(1, int(round((bounds[2] - bounds[0]) / res)))
            arr = ds.read(1, window=win, out_shape=(h, w), boundless=True, masked=True,
                          resampling=Resampling.average)
        else:
            arr = ds.read(1, window=win, boundless=True, masked=True)
        tf = rasterio.windows.transform(win, ds.transform)
        if res:
            tf = rasterio.Affine(res, 0, tf.c, 0, -res, tf.f)
        data = np.where(np.ma.getmaskarray(arr), np.nan, np.ma.getdata(arr)).astype(float)
        if ds.nodata is not None:
            data[data == ds.nodata] = np.nan
        return data, tf


def _result(kind, s, geom_wgs, result, tol, unit, method, rule_source, placeholders):
    out = {"mock": False, "type": kind, "run_id": s.run_id, "input_geometry": mapping(geom_wgs),
           "result": result, "tolerance": {"value": tol, "unit": unit, "method": method},
           "rule_source": rule_source, "placeholders_used": placeholders, "measured": True}
    return json.loads(json.dumps(out))  # shapely gives tuples; the contract (and the API) wants plain JSON


# ---------------------------------------------------------------- volume
def volume(s, polygon_wgs, rim_m=1.0):
    poly = shp_transform(s.to_map, shape(polygon_wgs))
    b = poly.buffer(rim_m + 1).bounds
    z, tf = s.window(s.dsm, b)
    inside = ~geometry_mask([mapping(poly)], z.shape, tf, invert=False)
    ring = poly.buffer(rim_m).difference(poly)
    rim = ~geometry_mask([mapping(ring)], z.shape, tf, invert=False)
    rows, cols = np.nonzero(rim & np.isfinite(z))
    if len(rows) < 10 or not (inside & np.isfinite(z)).any():
        raise ValueError("not enough height data on the polygon rim or inside it")
    xs, ys = rasterio.transform.xy(tf, rows, cols)
    A = np.c_[xs, ys, np.ones(len(xs))]
    coef, *_ = np.linalg.lstsq(A, z[rows, cols], rcond=None)
    r_in, c_in = np.nonzero(inside & np.isfinite(z))
    xi, yi = rasterio.transform.xy(tf, r_in, c_in)
    h = z[r_in, c_in] - (coef[0] * np.asarray(xi) + coef[1] * np.asarray(yi) + coef[2])
    px_area = abs(tf.a * tf.e)
    pos = np.clip(h, 0, None)
    area = float(inside.sum() * px_area)
    vol = float(pos.sum() * px_area)
    tol = round(s.rmse_v * area, 1) if s.rmse_v else None
    result = {"volume_m3": round(vol, 2), "area_m2": round(area, 1), "max_height_m": round(float(pos.max()), 2),
              "reference_surface": "polygon-rim fit (plane through DSM 0-1 m outside the polygon)",
              "valid_fraction": round(float(np.isfinite(z[inside]).mean()), 3)}
    return _result("volume", s, shape(polygon_wgs), result, tol, "m3",
                   "conservative bound: RMSE_V x footprint area (accuracy.json)" if tol else "accuracy not measured yet",
                   None, [])


# ---------------------------------------------------------------- span
def span(s, line_wgs):
    cfg = CFG["span"]
    line = shp_transform(s.to_map, shape(line_wgs))
    d = np.arange(0, line.length + 1e-9, cfg["sample_step_m"])
    pts = [line.interpolate(x) for x in d]
    z = np.array([v[0] for v in s.dsm.sample([(p.x, p.y) for p in pts])], float)
    if s.dsm.nodata is not None:
        z[z == s.dsm.nodata] = np.nan
    if np.isfinite(z).mean() < 0.8:
        raise ValueError("less than 80% of the line has height data")
    i_bed = int(np.nanargmin(z))
    tol = cfg["bank_top_tolerance_m"]
    # bank top = innermost point (closest to the bed) still within `tol` of that side's highest point,
    # i.e. the edge where the ground starts to drop, not the far end of a flat bank
    side_a, side_b = z[: i_bed + 1], z[i_bed:]
    i_a = int(np.nonzero(side_a >= np.nanmax(side_a) - tol)[0].max()) if i_bed > 0 else 0
    i_b = i_bed + int(np.nonzero(side_b >= np.nanmax(side_b) - tol)[0].min())
    bed = float(z[i_bed])
    ok = (z[i_a] - bed >= cfg["bank_drop_min_m"]) and (z[i_b] - bed >= cfg["bank_drop_min_m"]) and i_a < i_bed < i_b
    span_m = float(d[i_b] - d[i_a]) if ok else None
    panels = None
    if span_m:
        panels = math.ceil((span_m + 2 * BRIDGE["bank_seat_m"]) / BRIDGE["panel_length_m"])
    png = _profile_png(d, z, i_a, i_b, i_bed, span_m)
    result = {"span_m": round(span_m, 2) if span_m else None,
              "bank_a_height_m": round(float(z[i_a]), 2), "bank_b_height_m": round(float(z[i_b]), 2),
              "bed_elevation_m": round(bed, 2), "profile_png": png,
              "panel_estimate": {"count": panels, "rule": "config/bridging.yaml"},
              "note": None if ok else f"no bank pair standing >= {cfg['bank_drop_min_m']} m above the bed"}
    tol = round(math.sqrt(2) * s.rmse_h, 2) if (s.rmse_h and span_m) else None
    return _result("span", s, shape(line_wgs), result, tol, "m",
                   "conservative bound: sqrt(2) x RMSE_H for a distance between two picked points" if tol else "accuracy not measured yet",
                   "config/bridging.yaml", ["span.bank_drop_min_m", "bridging.bank_seat_m", "bridging.rule"])


def _profile_png(d, z, i_a, i_b, i_bed, span_m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = ROOT / "data" / "measurements"
    out.mkdir(parents=True, exist_ok=True)
    name = f"span_{abs(hash((float(d[-1]), float(np.nansum(z))))) % 10**8}.png"
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(d, z, lw=1)
    ax.plot([d[i_a], d[i_b]], [z[i_a], z[i_b]], "o--", label=f"span {span_m:.2f} m" if span_m else "no span")
    ax.plot(d[i_bed], z[i_bed], "v", label="bed")
    ax.set_xlabel("distance along line (m)")
    ax.set_ylabel("height (m, DSM)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / name, dpi=100)
    plt.close(fig)
    return str((out / name).relative_to(ROOT)).replace("\\", "/")


# ---------------------------------------------------------------- terrain helpers
def slope_deg(z, res):
    gy, gx = np.gradient(z, res)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def largest_rectangle(mask):
    """Largest all-True axis-aligned rectangle: (area, row0, col0, h, w)."""
    best = (0, 0, 0, 0, 0)
    heights = np.zeros(mask.shape[1], int)
    for r in range(mask.shape[0]):
        heights = np.where(mask[r], heights + 1, 0)
        stack = []
        for c in range(len(heights) + 1):
            h = heights[c] if c < len(heights) else 0
            start = c
            while stack and stack[-1][1] >= h:
                start, hh = stack.pop()
                area = hh * (c - start)
                if area > best[0]:
                    best = (area, r - hh + 1, start, hh, c - start)
            stack.append((start, h))
    return best


# ---------------------------------------------------------------- working space
def working_space(s, point_wgs, width_m=None, length_m=None):
    cfg = CFG["working_space"]
    width_m = width_m or cfg["required_width_m"]
    length_m = length_m or cfg["required_length_m"]
    p = shp_transform(s.to_map, shape(point_wgs))
    r = cfg["search_radius_m"]
    res = 0.5
    bounds = (p.x - r, p.y - r, p.x + r, p.y + r)
    ground, tf = s.window(s.dtm if s.dtm is not None else s.dsm, bounds, res)
    top, _ = s.window(s.dsm, bounds, res)
    ok = np.isfinite(ground) & np.isfinite(top)
    ok &= slope_deg(np.nan_to_num(ground, nan=np.nanmean(ground)), res) <= cfg["max_slope_deg"]
    ok &= (top - ground) <= cfg["max_obstacle_m"]
    area, r0, c0, h, w = largest_rectangle(ok)
    if area == 0:
        raise ValueError("no flat, clear area found near the point")
    x0, y0 = rasterio.transform.xy(tf, r0, c0, offset="ul")
    rect = box(x0, y0 - h * res, x0 + w * res, y0)
    rect_wgs = shp_transform(s.to_wgs, rect)
    a, b = sorted([w * res, h * res])
    meets = a >= min(width_m, length_m) and b >= max(width_m, length_m)
    sub = ok[r0:r0 + h, c0:c0 + w]
    result = {"rectangle_polygon": mapping(rect_wgs), "width_m": round(a, 1), "length_m": round(b, 1),
              "max_slope_deg": round(float(np.nanmax(slope_deg(np.nan_to_num(ground, nan=0), res)[r0:r0 + h, c0:c0 + w])), 1),
              "requirement_m": {"width": width_m, "length": length_m, "status": "PLACEHOLDER"},
              "meets_requirement": bool(meets and sub.all())}
    tol = round(math.sqrt(2) * s.rmse_h, 2) if s.rmse_h else None
    return _result("working_space", s, shape(point_wgs), result, tol, "m",
                   "conservative bound: sqrt(2) x RMSE_H on rectangle sides" if tol else "accuracy not measured yet",
                   "config/measure.yaml",
                   ["working_space.max_slope_deg", "working_space.max_obstacle_m",
                    "working_space.required_width_m", "working_space.required_length_m"])


# ---------------------------------------------------------------- landing zones
def landing_zones(s, helicopter, area_wgs=None):
    cfg = CFG["landing_zones"]
    heli = HELI[helicopter]
    A, B = heli["overall_length_A_m"], heli["undercarriage_base_B_m"]
    fato = max(1.5 * A, 2 * B)
    safety = cfg["safety_area_width_m"]
    res = cfg["grid_m"]
    if area_wgs:
        bounds = shp_transform(s.to_map, shape(area_wgs)).bounds
    else:
        bounds = tuple(s.dsm.bounds)
    ground, tf = s.window(s.dtm if s.dtm is not None else s.dsm, bounds, res)
    top, _ = s.window(s.dsm, bounds, res)
    obstacle = top - ground
    slope = slope_deg(np.nan_to_num(ground, nan=np.nanmean(ground)), res)
    n_f = int(math.ceil(fato / res))
    n_s = int(math.ceil(safety / res))
    valid = np.isfinite(ground) & np.isfinite(top)
    bad_fato = (~valid) | (slope > cfg["max_slope_deg"]) | (obstacle > cfg["max_obstacle_in_fato_m"])
    bad_safety = (~valid) | (obstacle > cfg["max_obstacle_in_safety_m"])
    # a FATO square at (r, c) top-left is OK when no bad cell inside; safety ring: no bad cell in the larger square
    integ_f = np.pad(bad_fato.astype(int).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    integ_s = np.pad(bad_safety.astype(int).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    H, W = ground.shape
    cands = []
    step = max(1, n_f // 4)
    for r in range(n_s, H - n_f - n_s, step):
        for c in range(n_s, W - n_f - n_s, step):
            if integ_f[r + n_f, c + n_f] - integ_f[r, c + n_f] - integ_f[r + n_f, c] + integ_f[r, c]:
                continue
            r0, c0, r1, c1 = r - n_s, c - n_s, r + n_f + n_s, c + n_f + n_s
            if integ_s[r1, c1] - integ_s[r0, c1] - integ_s[r1, c0] + integ_s[r0, c0]:
                continue
            cands.append((float(slope[r:r + n_f, c:c + n_f].max()), r, c))
    cands.sort()
    out, taken = [], []
    for sl, r, c in cands:
        if any(abs(r - rr) < n_f + n_s and abs(c - cc) < n_f + n_s for rr, cc in taken):
            continue
        taken.append((r, c))
        x0, y0 = rasterio.transform.xy(tf, r, c, offset="ul")
        sq = box(x0, y0 - n_f * res, x0 + n_f * res, y0)
        approach = _approach(ground, top, tf, res, r, c, n_f, cfg)
        out.append({"polygon": mapping(shp_transform(s.to_wgs, sq)), "fato_side_m": round(n_f * res, 1),
                    "max_slope_deg": round(sl, 1),
                    "max_obstacle_in_safety_area_m": round(float(np.nanmax(obstacle[r - n_s:r + n_f + n_s, c - n_s:c + n_f + n_s])), 2),
                    **approach})
        if len(out) >= cfg["max_candidates"]:
            break
    result = {"helicopter": helicopter, "helicopter_label": heli["label"], "fato_required_m": round(fato, 1),
              "candidates": out, "searched_area_m2": round(float(valid.sum() * res * res), 0)}
    geom = shape(area_wgs) if area_wgs else shp_transform(s.to_wgs, box(*bounds))
    tol = s.rmse_h
    return _result("landing_zones", s, geom, result, tol, "m",
                   "candidate position: RMSE_H (accuracy.json)" if tol else "accuracy not measured yet",
                   "Goa DCA helicopter operations document (brief section 9); config/helicopters.yaml",
                   ["helicopters.* dimensions", "landing_zones.max_slope_deg", "landing_zones.max_obstacle_in_fato_m"])


def _approach(ground, top, tf, res, r, c, n_f, cfg):
    """8% climb surface in 8 directions from the FATO edge, inside the mapped area."""
    H, W = top.shape
    z0 = np.nanmean(ground[r:r + n_f, c:c + n_f])
    cr, cc = r + n_f / 2, c + n_f / 2
    clear_dirs, checked, beyond = [], [], False
    for k in range(8):
        ang = math.radians(45 * k)
        dr, dc = -math.cos(ang), math.sin(ang)  # 0 = north
        ok, reached = True, 0.0
        dist = n_f * res / 2
        while dist <= n_f * res / 2 + cfg["approach_length_m"]:
            rr, c2 = int(cr + dr * dist / res), int(cc + dc * dist / res)
            if not (0 <= rr < H and 0 <= c2 < W) or not np.isfinite(top[rr, c2]):
                break
            if top[rr, c2] > z0 + cfg["approach_gradient"] * (dist - n_f * res / 2):
                ok = False
                break
            reached = dist - n_f * res / 2
            dist += res
        name = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][k]
        checked.append(name)
        if ok:
            clear_dirs.append(name)
            if reached < cfg["approach_length_m"]:
                beyond = True
    return {"approach_dirs_checked": checked, "approach_dirs_clear": clear_dirs, "approach_beyond_map": beyond}
