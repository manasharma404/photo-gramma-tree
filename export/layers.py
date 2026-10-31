"""Vector layer builders for GeoJSON (E1) and GeoPackage vortex.gpkg (E2) in EPSG:4326."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point, shape

from advisor import MODES
from export import LAYER_NAMES
from export.inputs import ExportInputs

LAYER_GPKG_GEOMETRY_TYPE: dict[str, str] = {
    "roads_status": "LineString",
    "cutoff_places": "Point",
    "landing_zones": "Unknown",
    "checkpoints": "Point",
    "measurements": "Unknown",
}


def _empty_gdf(columns: list[str]) -> gpd.GeoDataFrame:
    data = {col: [] for col in columns}
    return gpd.GeoDataFrame(data, geometry=gpd.GeoSeries([], crs="EPSG:4326"), crs="EPSG:4326")


def _summary_road_status(status_by_mode: dict[str, str]) -> str:
    """Representative road status for single-symbol styling (ambulance primary, preserving unknown)."""
    amb = status_by_mode.get("ambulance")
    if amb in ("open", "partial", "blocked", "unknown"):
        return amb
    vals = [status_by_mode.get(m, "unknown") for m in MODES]
    if "blocked" in vals:
        return "blocked"
    if "partial" in vals:
        return "partial"
    if "unknown" in vals:
        return "unknown"
    return "open"


def build_roads_status_gdf(inp: ExportInputs) -> gpd.GeoDataFrame:
    cols = [
        "segment_id",
        "highway",
        "length_m",
        "corridor_width_m",
        "measured",
        "state_source",
        "needs_verification",
        "display_status",
        "status_fire_truck",
        "status_ambulance",
        "status_jeep",
        "status_foot",
        "reasons_fire_truck",
        "reasons_ambulance",
        "reasons_jeep",
        "reasons_foot",
    ]
    state_by_id = {str(s["segment_id"]): s for s in inp.advisor_state.get("segments", [])}
    rows: list[dict[str, Any]] = []
    geoms: list[Any] = []

    for feat in inp.segments_fc.get("features", []):
        props = feat.get("properties") or {}
        sid = str(props["segment_id"])
        st = state_by_id.get(sid, {})
        st_modes = st.get("status_by_mode") or {}
        rs_modes = st.get("reasons_by_mode") or {}
        geom = shape(feat["geometry"]) if feat.get("geometry") else None

        rows.append(
            {
                "segment_id": sid,
                "highway": props.get("highway"),
                "length_m": props.get("length_m"),
                "corridor_width_m": props.get("corridor_width_m"),
                "measured": bool(props.get("measured", False)),
                "state_source": st.get("source", props.get("source", "geometry")),
                "needs_verification": bool(st.get("needs_verification", True)),
                "display_status": _summary_road_status(st_modes),
                "status_fire_truck": st_modes.get("fire_truck", "unknown"),
                "status_ambulance": st_modes.get("ambulance", "unknown"),
                "status_jeep": st_modes.get("jeep", "unknown"),
                "status_foot": st_modes.get("foot", "unknown"),
                "reasons_fire_truck": "; ".join(rs_modes.get("fire_truck", [])),
                "reasons_ambulance": "; ".join(rs_modes.get("ambulance", [])),
                "reasons_jeep": "; ".join(rs_modes.get("jeep", [])),
                "reasons_foot": "; ".join(rs_modes.get("foot", [])),
            }
        )
        geoms.append(geom)

    if not rows:
        return _empty_gdf(cols)
    return gpd.GeoDataFrame(rows, geometry=gpd.GeoSeries(geoms, crs="EPSG:4326"), crs="EPSG:4326")


def build_cutoff_places_gdf(inp: ExportInputs) -> gpd.GeoDataFrame:
    cols = [
        "place_id",
        "name",
        "kind",
        "population",
        "population_source",
        "nearest_segment_id",
        "reachable_fire_truck",
        "reachable_ambulance",
        "reachable_jeep",
        "reachable_foot",
        "cutoff_modes",
        "unknown_modes",
    ]
    acc_by_id = {str(p["place_id"]): p for p in inp.access_report.get("places", [])}
    rows: list[dict[str, Any]] = []
    geoms: list[Any] = []

    for feat in inp.places_fc.get("features", []):
        props = feat.get("properties") or {}
        if props.get("kind") == "landing_zone":
            continue
        pid = str(props["place_id"])
        acc = acc_by_id.get(pid, {})
        reach = acc.get("reachable") or {m: None for m in MODES}

        cutoff_modes = [m for m in MODES if reach.get(m) is False]
        unknown_modes = [m for m in MODES if reach.get(m) is None]
        # Hard Rule 2: unknown (None) is never open; include places cut off OR unknown for any vehicle mode.
        if not cutoff_modes and not unknown_modes:
            continue

        def _fmt_reach(val: bool | None) -> str:
            if val is True:
                return "reachable"
            if val is False:
                return "cutoff"
            return "unknown"

        geom = shape(feat["geometry"]) if feat.get("geometry") else None
        rows.append(
            {
                "place_id": pid,
                "name": props.get("name") or pid,
                "kind": props.get("kind", "settlement"),
                "population": props.get("population"),
                "population_source": props.get("population_source"),
                "nearest_segment_id": props.get("nearest_segment_id"),
                "reachable_fire_truck": _fmt_reach(reach.get("fire_truck")),
                "reachable_ambulance": _fmt_reach(reach.get("ambulance")),
                "reachable_jeep": _fmt_reach(reach.get("jeep")),
                "reachable_foot": _fmt_reach(reach.get("foot")),
                "cutoff_modes": ",".join(cutoff_modes),
                "unknown_modes": ",".join(unknown_modes),
            }
        )
        geoms.append(geom)

    if not rows:
        return _empty_gdf(cols)
    return gpd.GeoDataFrame(rows, geometry=gpd.GeoSeries(geoms, crs="EPSG:4326"), crs="EPSG:4326")


def build_landing_zones_gdf(inp: ExportInputs) -> gpd.GeoDataFrame:
    cols = ["lz_id", "name", "source", "nearest_segment_id", "measured", "details_json"]
    rows: list[dict[str, Any]] = []
    geoms: list[Any] = []

    for feat in inp.places_fc.get("features", []):
        props = feat.get("properties") or {}
        if props.get("kind") != "landing_zone":
            continue
        geom = shape(feat["geometry"]) if feat.get("geometry") else None
        rows.append(
            {
                "lz_id": str(props["place_id"]),
                "name": props.get("name") or str(props["place_id"]),
                "source": props.get("source", "landing_zones"),
                "nearest_segment_id": props.get("nearest_segment_id"),
                "measured": not bool(props.get("mock", False)),
                "details_json": json.dumps(
                    {"population_source": props.get("population_source")}, ensure_ascii=False
                ),
            }
        )
        geoms.append(geom)

    for meas_id, mdoc in inp.measurements:
        if mdoc.get("type") != "landing_zones":
            continue
        geom = shape(mdoc["input_geometry"]) if mdoc.get("input_geometry") else None
        rows.append(
            {
                "lz_id": meas_id,
                "name": f"Measured landing zone ({meas_id})",
                "source": "measurement.json",
                "nearest_segment_id": None,
                "measured": bool(mdoc.get("measured", False)),
                "details_json": json.dumps(mdoc.get("result") or {}, ensure_ascii=False),
            }
        )
        geoms.append(geom)

    if not rows:
        return _empty_gdf(cols)
    return gpd.GeoDataFrame(rows, geometry=gpd.GeoSeries(geoms, crs="EPSG:4326"), crs="EPSG:4326")


def build_checkpoints_gdf(inp: ExportInputs) -> gpd.GeoDataFrame:
    cols = [
        "checkpoint_id",
        "run_id",
        "checkpoint_method",
        "found_by",
        "dx_m",
        "dy_m",
        "dz_m",
        "rmse_h_m",
        "rmse_v_m",
        "coordinate_source",
    ]
    acc = inp.accuracy
    if not acc:
        return _empty_gdf(cols)

    confirmed_by_id: dict[str, tuple[float, float]] = {}
    conf_transformer: Transformer | None = None
    if inp.confirmed and isinstance(inp.confirmed.get("points"), list):
        map_epsg = inp.confirmed.get("map_epsg")
        if map_epsg:
            conf_transformer = Transformer.from_crs(int(map_epsg), 4326, always_xy=True)
        for pt in inp.confirmed["points"]:
            if "id" in pt and pt.get("x") is not None and pt.get("y") is not None:
                confirmed_by_id[str(pt["id"])] = (float(pt["x"]), float(pt["y"]))

    horiz = acc.get("horizontal") or {}
    vert = acc.get("vertical") or {}
    rmse_h = horiz.get("rmse_h_m")
    rmse_v = vert.get("rmse_v_m")

    rows: list[dict[str, Any]] = []
    geoms: list[Any] = []
    for pt in acc.get("per_point", []):
        cid = str(pt["id"])
        geom: Point | None = None
        coord_src = "missing_coordinates"

        if pt.get("lon") is not None and pt.get("lat") is not None:
            geom = Point(float(pt["lon"]), float(pt["lat"]))
            coord_src = "accuracy.json"
        elif cid in inp.rtk_rows:
            r = inp.rtk_rows[cid]
            lon_s = r.get("longitude") or r.get("lon")
            lat_s = r.get("latitude") or r.get("lat")
            if lon_s is not None and lat_s is not None:
                geom = Point(float(lon_s), float(lat_s))
                coord_src = "rtk.csv"
        elif cid in confirmed_by_id and conf_transformer is not None:
            mx, my = confirmed_by_id[cid]
            lon, lat = conf_transformer.transform(mx, my)
            geom = Point(float(lon), float(lat))
            coord_src = f"confirmed.json (EPSG:{inp.confirmed['map_epsg']}->4326)"

        rows.append(
            {
                "checkpoint_id": cid,
                "run_id": acc.get("run_id"),
                "checkpoint_method": acc.get("checkpoint_method"),
                "found_by": pt.get("found_by"),
                "dx_m": pt.get("dx_m"),
                "dy_m": pt.get("dy_m"),
                "dz_m": pt.get("dz_m"),
                "rmse_h_m": rmse_h,
                "rmse_v_m": rmse_v,
                "coordinate_source": coord_src,
            }
        )
        geoms.append(geom)

    if not rows:
        return _empty_gdf(cols)
    return gpd.GeoDataFrame(rows, geometry=gpd.GeoSeries(geoms, crs="EPSG:4326"), crs="EPSG:4326")


def build_measurements_gdf(inp: ExportInputs) -> gpd.GeoDataFrame:
    cols = [
        "measurement_id",
        "type",
        "run_id",
        "measured",
        "mock",
        "tolerance_value",
        "tolerance_unit",
        "tolerance_method",
        "rule_source",
        "placeholders_used",
        "result_json",
    ]
    rows: list[dict[str, Any]] = []
    geoms: list[Any] = []

    for meas_id, mdoc in inp.measurements:
        geom = shape(mdoc["input_geometry"]) if mdoc.get("input_geometry") else None
        tol = mdoc.get("tolerance") or {}
        rows.append(
            {
                "measurement_id": meas_id,
                "type": mdoc.get("type"),
                "run_id": mdoc.get("run_id"),
                "measured": bool(mdoc.get("measured", False)),
                "mock": bool(mdoc.get("mock", False)),
                "tolerance_value": tol.get("value"),
                "tolerance_unit": tol.get("unit"),
                "tolerance_method": tol.get("method"),
                "rule_source": mdoc.get("rule_source"),
                "placeholders_used": json.dumps(mdoc.get("placeholders_used") or []),
                "result_json": json.dumps(mdoc.get("result") or {}, ensure_ascii=False),
            }
        )
        geoms.append(geom)

    if not rows:
        return _empty_gdf(cols)
    return gpd.GeoDataFrame(rows, geometry=gpd.GeoSeries(geoms, crs="EPSG:4326"), crs="EPSG:4326")


def build_all_layers(inp: ExportInputs) -> dict[str, gpd.GeoDataFrame]:
    return {
        "roads_status": build_roads_status_gdf(inp),
        "cutoff_places": build_cutoff_places_gdf(inp),
        "landing_zones": build_landing_zones_gdf(inp),
        "checkpoints": build_checkpoints_gdf(inp),
        "measurements": build_measurements_gdf(inp),
    }


def write_geojson_layers(layers: dict[str, gpd.GeoDataFrame], out_dir: Path) -> dict[str, Path]:
    """Write one EPSG:4326 GeoJSON file per layer (E1)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name in LAYER_NAMES:
        gdf = layers[name].to_crs("EPSG:4326") if layers[name].crs != "EPSG:4326" else layers[name]
        out_path = out_dir / f"{name}.geojson"
        if len(gdf) == 0:
            # Explicit empty RFC 7946 FeatureCollection with CRS metadata
            empty_fc = {
                "type": "FeatureCollection",
                "name": name,
                "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
                "features": [],
            }
            out_path.write_text(json.dumps(empty_fc, indent=2), encoding="utf-8")
        else:
            gdf.to_file(out_path, driver="GeoJSON")
        written[name] = out_path
    return written


def write_geopackage(layers: dict[str, gpd.GeoDataFrame], gpkg_path: Path) -> Path:
    """Write all five EPSG:4326 layers into a single GeoPackage vortex.gpkg (E2)."""
    gpkg_path.parent.mkdir(parents=True, exist_ok=True)
    if gpkg_path.exists():
        gpkg_path.unlink()
    for idx, name in enumerate(LAYER_NAMES):
        gdf = layers[name].to_crs("EPSG:4326") if layers[name].crs != "EPSG:4326" else layers[name]
        geom_type = LAYER_GPKG_GEOMETRY_TYPE[name]
        gdf.to_file(
            gpkg_path,
            layer=name,
            driver="GPKG",
            geometry_type=geom_type,
            mode="w" if idx == 0 else "a",
        )
    return gpkg_path
