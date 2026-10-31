"""Prefetch WorldPop 2020 UN-adjusted population GeoTIFF for Wayanad (C1 / T16).

Run ONCE while online (downloads India 30-arc-second ~17 MB GeoTIFF, crops Wayanad bbox):
    uv run python scripts/prefetch_worldpop_wayanad.py

Re-apply offline from cached Wayanad GeoTIFF:
    uv run python scripts/prefetch_worldpop_wayanad.py --offline

Method (X = 750 m geodesic radius):
    - Dataset: WorldPop Global Project Population Data: Global 1 km Population Grids (2000-2020),
      UN-adjusted 2020 India (ind_ppp_2020_1km_Aggregated_UNadj.tif, 30 arc-seconds ~909x921 m
      at 11.5 deg N; people per pixel, WGS84).
      URL: https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/IND/ind_ppp_2020_1km_Aggregated_UNadj.tif
      Fallback URL: https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/IND/ind_ppp_2020_1km_Aggregated.tif
      DOI: https://doi.org/10.5258/SOTON/WP00671  |  Licence: CC BY 4.0.
    - Why X = 750 m: At 11.5 deg N, each 30-arc-second WorldPop pixel measures ~909 m x 921 m
      (centre-to-corner half-diagonal = 647 m). Choosing X = 750 m (> 647 m) guarantees every
      inhabited settlement point captures its containing grid cell (1-3 cells across ~1.77 km2
      valley settlement footprint), while 2 * 750 m = 1.5 km stays well below the ~2.2-2.6 km
      spacing between Chooralmala, Attamala, and Mundakkai so major settlements do not overlap.
    - Honesty rule: Non-settlement facilities (school, hospital, shelter, staging base) keep
      population=null. Settlements with no positive WorldPop cells within X m stay null (never 0).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tempfile
from typing import Any

import geopandas as gpd
import numpy as np
from pyproj import Geod
import rasterio
from rasterio.windows import Window, from_bounds
import requests
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
GEOD = Geod(ellps="WGS84")

WORLDPOP_CANDIDATES = [
    (
        "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/IND/"
        "ind_ppp_2020_1km_Aggregated_UNadj.tif",
        "https://doi.org/10.5258/SOTON/WP00671",
        "WorldPop 2020 UN-adjusted 1km India (ind_ppp_2020_1km_Aggregated_UNadj.tif)",
    ),
    (
        "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/IND/"
        "ind_ppp_2020_1km_Aggregated.tif",
        "https://doi.org/10.5258/SOTON/WP00670",
        "WorldPop 2020 1km India (ind_ppp_2020_1km_Aggregated.tif)",
    ),
]
WORLDPOP_LICENCE = "CC BY 4.0 (WorldPop, University of Southampton)"
CACHED_FILENAME = "worldpop_wayanad_2020.tif"

# ~3 km buffer around scripts/prefetch_wayanad.py BBOX so 750 m settlement circles stay well inside
WORLDPOP_BBOX = {
    "west": 76.105,
    "south": 11.445,
    "east": 76.205,
    "north": 11.545,
}
DEFAULT_RADIUS_M = 750.0

HTTP_HEADERS = {
    "User-Agent": "Vortex-T8.2-Prototype/0.1 (hackFront India 2026 offline landslide advisor; academic research)",
}


def download_worldpop_window(
    out_tif: Path,
    bbox: dict[str, float] = WORLDPOP_BBOX,
) -> dict[str, str]:
    """Download WorldPop India 2020 1km GeoTIFF (~17 MB) via HTTPS stream and crop Wayanad window."""
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None

    for url, doi, label in WORLDPOP_CANDIDATES:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                raw_tif = Path(tmpdir) / "worldpop_ind_2020.tif"
                with requests.get(url, headers=HTTP_HEADERS, stream=True, timeout=120) as resp:
                    resp.raise_for_status()
                    with open(raw_tif, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=262144):
                            if chunk:
                                fh.write(chunk)

                with rasterio.open(raw_tif) as src:
                    raw_win = from_bounds(
                        bbox["west"],
                        bbox["south"],
                        bbox["east"],
                        bbox["north"],
                        transform=src.transform,
                    )
                    col_off = max(0, int(math.floor(raw_win.col_off)))
                    row_off = max(0, int(math.floor(raw_win.row_off)))
                    width = min(src.width - col_off, max(4, int(math.ceil(raw_win.width)) + 2))
                    height = min(src.height - row_off, max(4, int(math.ceil(raw_win.height)) + 2))
                    win = Window(col_off=col_off, row_off=row_off, width=width, height=height)

                    data = src.read(1, window=win)
                    win_transform = src.window_transform(win)
                    profile = src.profile.copy()
                    profile.update(
                        driver="GTiff",
                        height=height,
                        width=width,
                        count=1,
                        transform=win_transform,
                        compress="deflate",
                        tiled=False,
                    )
                    retrieved_date = datetime.now(timezone.utc).date().isoformat()
                    with rasterio.open(out_tif, "w", **profile) as dst:
                        dst.write(data, 1)
                        dst.update_tags(
                            source_url=url,
                            doi=doi,
                            dataset_label=label,
                            licence=WORLDPOP_LICENCE,
                            retrieved_at=retrieved_date,
                        )
                return {
                    "url": url,
                    "doi": doi,
                    "label": label,
                    "retrieved_at": retrieved_date,
                }
        except Exception as exc:
            last_err = exc

    raise RuntimeError(f"Failed to download WorldPop India 2020 GeoTIFF: {last_err}") from last_err


def sum_worldpop_within_radius(
    tif_path: Path,
    lon: float,
    lat: float,
    radius_m: float = DEFAULT_RADIUS_M,
) -> tuple[int | None, int, dict[str, str]]:
    """Sum valid (>0) WorldPop grid cells whose centres lie within radius_m of (lon, lat)."""
    with rasterio.open(tif_path) as src:
        arr = src.read(1)
        nodata = src.nodata
        tags = src.tags()
        rows, cols = np.indices(arr.shape)
        xs, ys = rasterio.transform.xy(src.transform, rows, cols, offset="center")
        lons = np.asarray(xs, dtype=np.float64).ravel()
        lats = np.asarray(ys, dtype=np.float64).ravel()
        vals = np.asarray(arr, dtype=np.float64).ravel()

        valid = np.isfinite(vals)
        if nodata is not None:
            valid &= ~np.isclose(vals, float(nodata))
        valid &= vals >= 0.0

        meta = {
            "url": tags.get("source_url", WORLDPOP_CANDIDATES[0][0]),
            "doi": tags.get("doi", WORLDPOP_CANDIDATES[0][1]),
            "label": tags.get("dataset_label", WORLDPOP_CANDIDATES[0][2]),
            "retrieved_at": tags.get("retrieved_at", "2026-10-31"),
        }

        if not np.any(valid):
            return None, 0, meta

        v_lons = lons[valid]
        v_lats = lats[valid]
        v_vals = vals[valid]

        _, _, dists_m = GEOD.inv(
            np.full_like(v_lons, float(lon)),
            np.full_like(v_lats, float(lat)),
            v_lons,
            v_lats,
        )
        in_circle = (dists_m <= float(radius_m)) & (v_vals > 0.0)
        n_cells = int(np.count_nonzero(in_circle))
        if n_cells == 0:
            return None, 0, meta

        total = int(round(float(np.sum(v_vals[in_circle]))))
        if total <= 0:
            return None, 0, meta
        return total, n_cells, meta


def attach_worldpop_to_places_fc(
    places_fc: dict[str, Any],
    tif_path: Path,
    radius_m: float = DEFAULT_RADIUS_M,
) -> dict[str, Any]:
    """Attach WorldPop population & checkable population_source to settlement features in-place."""
    filled = 0
    unmatched = 0
    last_meta: dict[str, str] = {}
    for feat in places_fc.get("features", []):
        props = feat.get("properties") or {}
        if props.get("kind") != "settlement":
            continue
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        pop_val, n_cells, meta = sum_worldpop_within_radius(tif_path, lon, lat, radius_m=radius_m)
        last_meta = meta
        if pop_val is not None:
            props["population"] = pop_val
            props["population_source"] = (
                f"{meta['label']} ({WORLDPOP_LICENCE}, {meta['url']}, DOI {meta['doi']}, "
                f"retrieved {meta['retrieved_at']}): sum of {n_cells} grid cell(s) within "
                f"{int(round(radius_m))} m geodesic radius of OSM settlement point"
            )
            filled += 1
        else:
            props["population"] = None
            props["population_source"] = (
                f"PLACEHOLDER (0 positive WorldPop cells within {int(round(radius_m))} m of "
                f"{meta['url']}; kept null, never assumed 0)"
            )
            unmatched += 1
    return {
        "settlements_filled": filled,
        "settlements_null": unmatched,
        "radius_m": radius_m,
        "dataset": last_meta,
    }


def update_wayanad_project_population(
    project_dir: Path,
    tif_path: Path,
    radius_m: float = DEFAULT_RADIUS_M,
) -> dict[str, Any]:
    places_path = project_dir / "places.geojson"
    if not places_path.is_file():
        raise FileNotFoundError(f"Wayanad places.geojson not found at {places_path}")

    places_fc = json.loads(places_path.read_text(encoding="utf-8"))
    summary = attach_worldpop_to_places_fc(places_fc, tif_path, radius_m=radius_m)
    places_path.write_text(json.dumps(places_fc, indent=2), encoding="utf-8")

    # Keep wayanad_osm.gpkg 'places' layer synchronized if present
    gpkg_path = project_dir / "wayanad_osm.gpkg"
    if gpkg_path.is_file():
        rows = []
        for feat in places_fc.get("features", []):
            lon, lat = feat["geometry"]["coordinates"][:2]
            rows.append({**feat["properties"], "geometry": Point(float(lon), float(lat))})
        if rows:
            gpd.GeoDataFrame(rows, crs="EPSG:4326").to_file(
                gpkg_path, layer="places", driver="GPKG", mode="a"
            )

    sources_path = project_dir / "scenario_sources.json"
    if sources_path.is_file():
        sdoc = json.loads(sources_path.read_text(encoding="utf-8"))
        ds = summary.get("dataset") or {}
        existing_ids = {s.get("id") for s in sdoc.get("sources", [])}
        if "worldpop_2020_ind" not in existing_ids and ds:
            sdoc.setdefault("sources", []).append(
                {
                    "id": "worldpop_2020_ind",
                    "title": ds.get("label", "WorldPop 2020 India"),
                    "url": ds.get("url", WORLDPOP_CANDIDATES[0][0]),
                    "licence": WORLDPOP_LICENCE,
                    "date": f"2020 dataset (retrieved {ds.get('retrieved_at', '2026-10-31')})",
                    "quote_or_paraphrase": (
                        f"Estimated 2020 people per 30-arc-second (~910m) pixel; summed across cell "
                        f"centres within {int(round(radius_m))} m geodesic radius per settlement."
                    ),
                    "purpose": "Settlement population exposure for Wayanad reopen plan and priorities (C1/T16)",
                }
            )
        sdoc["population_attachment"] = summary
        sources_path.write_text(json.dumps(sdoc, indent=2), encoding="utf-8")

    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--project-dir",
        type=Path,
        default=ROOT / "data" / "projects" / "wayanad",
        help="Path to Wayanad project directory",
    )
    ap.add_argument(
        "--radius-m",
        type=float,
        default=DEFAULT_RADIUS_M,
        help="Geodesic buffer radius in metres around each settlement point (default: 750 m)",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Use cached worldpop_wayanad_2020.tif without network access",
    )
    args = ap.parse_args()

    tif_path = args.project_dir / CACHED_FILENAME
    if args.offline:
        if not tif_path.is_file():
            raise FileNotFoundError(f"--offline requested, but cached WorldPop raster not found: {tif_path}")
    else:
        print(f"Downloading WorldPop 2020 India GeoTIFF & cropping {WORLDPOP_BBOX} -> {tif_path} ...")
        download_worldpop_window(tif_path, bbox=WORLDPOP_BBOX)

    summary = update_wayanad_project_population(args.project_dir, tif_path, radius_m=args.radius_m)
    print(f"Updated {args.project_dir / 'places.geojson'} with WorldPop 2020 population: {summary}")


if __name__ == "__main__":
    main()
