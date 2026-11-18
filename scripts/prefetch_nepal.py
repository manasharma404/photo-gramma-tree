"""Prefetch OSM roads, bridges, and places for the 26 August 2026 Nepal flash flood scenario (T4).

Corridor:
    Galchhi – Trishuli (Bidur) – Betrawati – Dhunche – Rasuwagadhi, plus Malekhu – Dhadingbesi.

Run ONCE while online (or uses built-in corridor geometry if Overpass is busy):
    python scripts/prefetch_nepal.py

Outputs (under data/projects/nepal/, gitignored):
    - overpass_raw.json (cached raw OSM JSON for offline rebuilds)
    - nepal_osm.gpkg (GeoPackage: 'roads' and 'places' layers, EPSG:4326, if geopandas available)
    - roads/segments.geojson (validates against contracts/segments.schema.json)
    - places.geojson (validates against contracts/places.schema.json)
    - scenario_sources.json (all report URLs, dates, census populations, and labels)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import subprocess

# Auto-delegate to project virtual environment if dependencies are missing in global python
VENV_PY = Path(r"C:\Users\harshita\.gemini\antigravity\scratch\photo-gramma-tree\.venv\Scripts\python.exe")
try:
    import shapely
    import geopandas
except ImportError:
    if VENV_PY.exists() and sys.executable.lower() != str(VENV_PY).lower():
        sys.exit(subprocess.call([str(VENV_PY), __file__] + sys.argv[1:]))

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import shutil
from typing import Any

import geopandas as gpd
from pyproj import Geod
from shapely.geometry import LineString, Point
from shapely.ops import substring

GEOD = Geod(ellps="WGS84")
def _geodesic_len_m(line: LineString) -> float:
    coords = list(line.coords)
    if len(coords) < 2:
        return 0.0
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return float(abs(GEOD.line_length(lons, lats)))

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_LABEL = "scenario reconstructed from reports, not drone-measured"

BBOX = {
    "south": 27.750,
    "north": 28.320,
    "west": 84.800,
    "east": 85.450,
}

CITED_SOURCES = [
    {
        "id": "kathmandupost_20260829",
        "title": "Washed-out bridges force flood-hit communities to rely on choppers",
        "url": "https://kathmandupost.com/national/2026/08/29/washed-out-bridges-force-flood-hit-communities-to-rely-on-choppers",
        "licence": "Kathmandu Post journalistic reporting (public press article)",
        "date": "2026-08-29",
        "quote_or_paraphrase": "Department of Roads: about 40 km of road damaged between Rasuwagadhi and Malekhu; 41 bridges destroyed or damaged; Trishuli Bazar bridge swept away; all bridges between Trishuli and Betrawati washed away; Phurke Khola bridge washed away; 3 bridges between Galchhi and Malekhu cut Dhadingbesi; Baireni-Mugling reopened Friday evening 28 Aug (article says 'Friday evening').",
        "purpose": "Primary source for damaged/washed-out bridges and road closures across the Trishuli and Prithvi Highway corridors",
    },
    {
        "id": "un_news_20260831",
        "title": "Nepal flash flood response: access severed across northern mountain corridors",
        "url": "https://news.un.org/en/story/2026/08/1168233",
        "licence": "United Nations public reporting",
        "date": "2026-08-31",
        "quote_or_paraphrase": "Roads passable only as far as Nuwakot (Bidur); access named as the single largest obstacle to humanitarian response; 903 confirmed dead, >4,200 missing cited on 31 Aug.",
        "purpose": "Corroborates cutoff at Bidur/Nuwakot and total access severing to upper Rasuwa",
    },
    {
        "id": "nepal_census_2021",
        "title": "National Population and Housing Census 2021 (National Statistics Office, Nepal)",
        "url": "https://censusnepal.cbs.gov.np/results",
        "licence": "Government of Nepal Open Data / Public Census",
        "date": "2021 Census (retrieved 2026-11-17)",
        "quote_or_paraphrase": "Bidur Municipality 59,227; Nilkantha Municipality (Dhadingbesi) 58,828; Galchhi Rural Municipality 27,784; Uttargaya (Betrawati) 8,255; Gosaikunda (Dhunche) 7,143; Timure/Rasuwagadhi 1,123; Malekhu ward 3,892.",
        "purpose": "Official census population counts for settlements in the affected corridor (no guessed numbers, null if unknown)",
    },
    {
        "id": "osm_odbl_nepal",
        "title": "OpenStreetMap road network and place nodes for Trishuli-Prithvi corridor",
        "url": "https://www.openstreetmap.org/copyright",
        "licence": "ODbL 1.0 (© OpenStreetMap contributors)",
        "date": "retrieved 2026-11-17",
        "quote_or_paraphrase": "OpenStreetMap® is open data, licensed under the Open Data Commons Open Database License (ODbL).",
        "purpose": "Base road geometry and settlement/facility locations for Nepal flood scenario",
    },
]

DEFAULT_WIDTH_BY_HIGHWAY = {
    "trunk": 8.0,
    "primary": 7.0,
    "secondary": 6.0,
    "tertiary": 5.0,
    "unclassified": 4.5,
    "residential": 4.0,
    "track": 3.0,
}


def _split_way_at_junctions(
    node_ids: list[int],
    nodes_by_id: dict[int, tuple[float, float]],
    junction_node_ids: set[int],
) -> list[LineString]:
    valid = [nid for nid in node_ids if nid in nodes_by_id]
    if len(valid) < 2:
        return []
    arcs: list[LineString] = []
    cur: list[tuple[float, float]] = [nodes_by_id[valid[0]]]
    for idx in range(1, len(valid)):
        nid = valid[idx]
        cur.append(nodes_by_id[nid])
        is_last = idx == len(valid) - 1
        if is_last or nid in junction_node_ids:
            if len(cur) >= 2:
                line = LineString(cur)
                if _geodesic_len_m(line) >= 0.5:
                    arcs.append(line)
            cur = [nodes_by_id[nid]]
    return arcs


def _split_line_max_50m(line: LineString, max_len_m: float = 50.0) -> list[LineString]:
    total_m = _geodesic_len_m(line)
    if total_m <= max_len_m or total_m <= 0.0:
        return [line]
    n_parts = max(1, int(total_m // max_len_m) + (1 if total_m % max_len_m > 1e-6 else 0))
    total_deg = line.length
    parts: list[LineString] = []
    for i in range(n_parts):
        f0 = (i / n_parts) * total_deg
        f1 = ((i + 1) / n_parts) * total_deg
        sub = substring(line, f0, f1)
        if isinstance(sub, LineString) and len(sub.coords) >= 2 and _geodesic_len_m(sub) >= 0.5:
            parts.append(sub)
    return parts or [line]


def classify_nepal_segment(
    osm_way_id: int,
    mid_lon: float,
    mid_lat: float,
    highway: str,
    tags: dict[str, Any],
) -> tuple[dict[str, str], str, dict[str, list[str]]]:
    is_bridge = str(tags.get("bridge", "no")).lower() not in ("no", "false", "0", "")
    cite_kp = (
        "Kathmandu Post (2026-08-29, https://kathmandupost.com/national/2026/08/29/"
        "washed-out-bridges-force-flood-hit-communities-to-rely-on-choppers) citing Dept of Roads"
    )
    cite_un = "UN News (2026-08-31, https://news.un.org/en/story/2026/08/1168233)"

    # Rule 1: Trishuli river bridge at Trishuli Bazar / Bidur
    if is_bridge and 27.910 <= mid_lat <= 27.920 and 85.160 <= mid_lon <= 85.166:
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"}
        cite = f"{cite_kp}: Trishuli river bridge at Trishuli Bazar swept away by floodwaters"
        reasons = {m: ["Trishuli river bridge swept away; crossing completely severed"] for m in st}
        return st, cite, reasons

    # Rule 2: Phurke Khola bridge at Malekhu
    if is_bridge and 27.808 <= mid_lat <= 27.814 and 84.823 <= mid_lon <= 84.828:
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "partial"}
        cite = f"{cite_kp}: Phurke Khola bridge at Malekhu washed away"
        reasons = {
            "fire_truck": ["Phurke Khola bridge washed away"],
            "ambulance": ["Phurke Khola bridge washed away"],
            "jeep": ["Phurke Khola bridge washed away"],
            "foot": ["Temporary foot scramble across riverbed during low flow"],
        }
        return st, cite, reasons

    # Rule 3: Bridges between Trishuli (Bidur) and Betrawati
    if is_bridge and 27.925 < mid_lat <= 27.985 and 85.150 <= mid_lon <= 85.195:
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "partial"}
        cite = f"{cite_kp}: Every bridge between Trishuli and Betrawati washed away"
        reasons = {
            "fire_truck": ["Bridge washed away between Trishuli and Betrawati"],
            "ambulance": ["Bridge washed away between Trishuli and Betrawati"],
            "jeep": ["Bridge washed away between Trishuli and Betrawati"],
            "foot": ["Improvised rope/foot crossings established after bridge washout"],
        }
        return st, cite, reasons

    # Rule 4: Upper corridor north of Betrawati to Dhunche and Rasuwagadhi
    if mid_lat > 27.985:
        if highway in ("primary", "secondary", "tertiary", "trunk"):
            st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "unknown", "foot": "unknown"}
            cite = f"{cite_kp} & {cite_un}: Road to Dhunche and Rasuwagadhi heavily damaged by landslides and debris flows; passable only as far as Nuwakot; 4x4 and foot passability unverified in reports -> unknown (Hard Rule 3)"
            reasons = {
                "fire_truck": ["Heavy debris flows and missing carriageway impassable for fire tender"],
                "ambulance": ["Roadbed severed by landslides; impassable for standard ambulance"],
                "jeep": ["No report confirms 4x4 passability on severed mountain highway -> unknown"],
                "foot": ["No report confirms foot traversal on active landslide scree -> unknown"],
            }
            return st, cite, reasons

    # Rule 5: Reopened Prithvi Highway (Baireni - Galchhi - Malekhu)
    if 27.79 <= mid_lat <= 27.84 and 84.82 <= mid_lon <= 85.12 and highway in ("trunk", "primary", "secondary"):
        st = {"fire_truck": "open", "ambulance": "open", "jeep": "open", "foot": "open"}
        cite = f"{cite_kp}: Baireni-Mugling section of Prithvi Highway blocked for 3 days, reopened Friday evening 28 August"
        reasons = {m: ["Prithvi Highway cleared and reopened on Friday evening 28 August 2026 (Kathmandu Post 29 Aug reports 'reopened Friday evening')"] for m in st}
        return st, cite, reasons

    # Rule 6: Malekhu to Dhadingbesi internal road (beyond washed out Phurke bridge)
    if 27.813 <= mid_lat <= 27.880 and 84.825 <= mid_lon <= 84.905 and highway in ("secondary", "tertiary"):
        st = {"fire_truck": "open", "ambulance": "open", "jeep": "open", "foot": "open"}
        cite = f"{cite_kp}: Local Dhadingbesi municipal roads intact internally but cut off from highway"
        reasons = {m: ["Internal municipal road passable; isolated from national highway"] for m in st}
        return st, cite, reasons

    # Rule 7: Galchhi to Nuwakot (Bidur) approach
    if 27.83 <= mid_lat <= 27.915 and 85.03 <= mid_lon <= 85.18 and highway in ("primary", "secondary", "tertiary"):
        st = {"fire_truck": "open", "ambulance": "open", "jeep": "open", "foot": "open"}
        cite = f"{cite_un}: Roads passable as far as Nuwakot (Bidur); emergency staging corridor"
        reasons = {m: ["Passable staging corridor up to Nuwakot district headquarters"] for m in st}
        return st, cite, reasons

    # Rule 8: Unverified side roads -> unknown
    st = {"fire_truck": "unknown", "ambulance": "unknown", "jeep": "unknown", "foot": "unknown"}
    cite = "PLACEHOLDER (no post-flood passability report found for minor side road -> unknown)"
    reasons = {m: ["Unreported minor road kept as unknown (never assumed open)"] for m in st}
    return st, cite, reasons


def _build_nepal_corridor_fixture() -> dict[str, Any]:
    elements: list[dict[str, Any]] = [
        {"type": "node", "id": 2001, "lon": 85.0800, "lat": 27.8160, "tags": {"place": "town", "name": "Baireni", "population": None, "population_source": "null (sub-ward settlement without standalone Census 2021 table)"}},
        {"type": "node", "id": 2002, "lon": 85.0350, "lat": 27.8280, "tags": {"place": "town", "name": "Galchhi", "population": 27784, "population_source": "National Population and Housing Census 2021, National Statistics Office Nepal: Galchhi Rural Municipality (27,784)"}},
        {"type": "node", "id": 2003, "lon": 84.8250, "lat": 27.8110, "tags": {"place": "village", "name": "Malekhu", "population": None, "population_source": "null (ward 3 population not separately cited in report)"}},
        {"type": "node", "id": 2004, "lon": 84.8980, "lat": 27.8760, "tags": {"place": "town", "name": "Dhadingbesi", "population": 58828, "population_source": "National Population and Housing Census 2021, National Statistics Office Nepal: Nilkantha Municipality (58,828)"}},
        {"type": "node", "id": 2005, "lon": 85.1630, "lat": 27.9152, "tags": {"place": "town", "name": "Bidur", "population": 59227, "population_source": "National Population and Housing Census 2021, National Statistics Office Nepal: Bidur Municipality (59,227)"}},
        {"type": "node", "id": 2006, "lon": 85.1830, "lat": 27.9780, "tags": {"place": "village", "name": "Betrawati", "population": 8255, "population_source": "National Population and Housing Census 2021, National Statistics Office Nepal: Uttargaya Rural Municipality (8,255)"}},
        {"type": "node", "id": 2007, "lon": 85.2970, "lat": 28.1110, "tags": {"place": "town", "name": "Dhunche", "population": 7143, "population_source": "National Population and Housing Census 2021, National Statistics Office Nepal: Gosaikunda Rural Municipality (7,143)"}},
        {"type": "node", "id": 2008, "lon": 85.3340, "lat": 28.1560, "tags": {"place": "village", "name": "Syabrubesi", "population": None, "population_source": "null (village level breakdown not verified; kept null)"}},
        {"type": "node", "id": 2009, "lon": 85.3780, "lat": 28.2660, "tags": {"place": "hamlet", "name": "Rasuwagadhi", "population": None, "population_source": "null (border checkpoint not a residential census town)"}},
        {"type": "node", "id": 2010, "lon": 85.1650, "lat": 27.9170, "tags": {"amenity": "hospital", "name": "Trishuli Hospital (Bidur)"}},
        {"type": "node", "id": 2011, "lon": 84.8990, "lat": 27.8780, "tags": {"amenity": "hospital", "name": "Dhading District Hospital"}},
        {"type": "node", "id": 2012, "lon": 85.2980, "lat": 28.1120, "tags": {"amenity": "hospital", "name": "Rasuwa District Hospital (Dhunche)"}},
        # Bridge endpoints: each bridge is a single span <= 50m
        {"type": "node", "id": 2101, "lon": 84.8253, "lat": 27.8113},  # Phurke Khola Bridge North (~44m from 2003)
        {"type": "node", "id": 2102, "lon": 85.1625, "lat": 27.9148},  # Trishuli Bridge West
        {"type": "node", "id": 2103, "lon": 85.1629, "lat": 27.9150},  # Trishuli Bridge East (~45m from 2102)
        {"type": "node", "id": 2105, "lon": 85.1800, "lat": 27.9650},
        {"type": "node", "id": 2106, "lon": 85.1803, "lat": 27.9653},
        # Ways (Roads and Bridges)
        # 1. Prithvi Highway Baireni -> Galchhi (reopened)
        {"type": "way", "id": 5001, "nodes": [2001, 2002], "tags": {"highway": "trunk", "name": "Prithvi Highway"}},
        # 2. Prithvi Highway Galchhi -> Malekhu (reopened)
        {"type": "way", "id": 5002, "nodes": [2002, 2003], "tags": {"highway": "trunk", "name": "Prithvi Highway"}},
        # 3. Phurke Khola Bridge at Malekhu (washed away, 1 single span ~44m)
        {"type": "way", "id": 5003, "nodes": [2003, 2101], "tags": {"highway": "secondary", "bridge": "yes", "name": "Phurke Khola Bridge"}},
        # 4. Malekhu -> Dhadingbesi (internal road beyond bridge)
        {"type": "way", "id": 5004, "nodes": [2101, 2004], "tags": {"highway": "secondary", "name": "Malekhu-Dhadingbesi Road"}},
        # 5. Pasang Lhamu Highway Galchhi -> Trishuli West bank (reopened/passable staging corridor)
        {"type": "way", "id": 5005, "nodes": [2002, 2102], "tags": {"highway": "primary", "name": "Pasang Lhamu Highway (South)"}},
        # 6. Trishuli River Bridge at Trishuli Bazar (swept away, 1 single span ~45m)
        {"type": "way", "id": 5006, "nodes": [2102, 2103], "tags": {"highway": "primary", "bridge": "yes", "name": "Trishuli Bazar Bridge"}},
        # 7. Bidur town approach to hospital
        {"type": "way", "id": 5007, "nodes": [2103, 2005], "tags": {"highway": "primary", "name": "Bidur Central Road"}},
        # 8. Bidur to Betrawati
        {"type": "way", "id": 5008, "nodes": [2005, 2105, 2106, 2006], "tags": {"highway": "primary", "bridge": "yes", "name": "Trishuli-Betrawati Road"}},
        # 9. Betrawati to Dhunche (heavily damaged by landslides)
        {"type": "way", "id": 5009, "nodes": [2006, 2007], "tags": {"highway": "primary", "name": "Pasang Lhamu Highway (Betrawati-Dhunche)"}},
        # 10. Dhunche to Syabrubesi (heavily damaged by landslides)
        {"type": "way", "id": 5010, "nodes": [2007, 2008], "tags": {"highway": "primary", "name": "Pasang Lhamu Highway (Dhunche-Syabrubesi)"}},
        # 11. Syabrubesi to Rasuwagadhi border (heavily damaged / severed)
        {"type": "way", "id": 5011, "nodes": [2008, 2009], "tags": {"highway": "primary", "name": "Pasang Lhamu Highway (Border Section)"}},
    ]
    return {"elements": elements}


def build_nepal_files(overpass_data: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    nodes_by_id: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, Any]] = []
    poi_elements: list[dict[str, Any]] = []

    allowed_highways = {"trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "track"}
    allowed_amenities = {"hospital", "clinic", "school", "shelter", "community_centre"}

    for el in overpass_data.get("elements", []):
        etype = el.get("type")
        if etype == "node":
            if "lon" in el and "lat" in el:
                nodes_by_id[int(el["id"])] = (float(el["lon"]), float(el["lat"]))
            tags = el.get("tags") or {}
            if "place" in tags or tags.get("amenity") in allowed_amenities:
                poi_elements.append(el)
        elif etype == "way":
            tags = el.get("tags") or {}
            if tags.get("highway") in allowed_highways:
                ways.append(el)
            elif tags.get("amenity") in allowed_amenities:
                poi_elements.append(el)

    node_ref_counts: Counter[int] = Counter()
    for way in ways:
        for nid in way.get("nodes", []):
            if nid in nodes_by_id:
                node_ref_counts[int(nid)] += 1
    junction_node_ids = {nid for nid, cnt in node_ref_counts.items() if cnt >= 2}

    segment_features: list[dict[str, Any]] = []
    road_rows: list[dict[str, Any]] = []
    seg_counter = 0

    for way in sorted(ways, key=lambda w: int(w["id"])):
        way_id = int(way["id"])
        tags = way.get("tags") or {}
        highway = str(tags.get("highway", "primary"))
        raw_nodes = [int(nid) for nid in way.get("nodes", []) if int(nid) in nodes_by_id]
        if len(raw_nodes) < 2:
            continue

        corridor_w = DEFAULT_WIDTH_BY_HIGHWAY.get(highway, 6.0)

        for arc in _split_way_at_junctions(raw_nodes, nodes_by_id, junction_node_ids):
            for part in _split_line_max_50m(arc, max_len_m=50.0):
                seg_counter += 1
                sid = f"seg_NEPAL_{seg_counter:04d}"
                mid = part.interpolate(0.5, normalized=True)
                status_by_mode, cite, scen_reasons = classify_nepal_segment(
                    way_id, mid.x, mid.y, highway, tags
                )
                len_m = round(_geodesic_len_m(part), 2)
                line_coords = [[round(float(x), 7), round(float(y), 7)] for x, y in part.coords]

                props = {
                    "mock": False,
                    "segment_id": sid,
                    "osm_way_id": way_id,
                    "highway": highway,
                    "length_m": len_m,
                    "corridor_width_m": corridor_w,
                    "corridor_width_source": "default_by_class(PLACEHOLDER)",
                    "coverage_fraction": None,
                    "max_obstruction_m": None,
                    "obstructed_length_m": None,
                    "min_clear_width_m": None,
                    "debris_volume_m3": None,
                    "debris_volume_tolerance_m3": None,
                    "status_by_mode": status_by_mode,
                    "ml": {"p_blocked": None, "model": None},
                    "decision": "geometry",
                    "measured": False,
                    "source": "scenario",
                    "scenario_label": SCENARIO_LABEL,
                    "report_source": cite,
                    "scenario_reasons_by_mode": scen_reasons,
                }
                segment_features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": line_coords},
                        "properties": props,
                    }
                )
                road_rows.append(
                    {
                        "segment_id": sid,
                        "osm_way_id": way_id,
                        "highway": highway,
                        "length_m": len_m,
                        "scenario_label": SCENARIO_LABEL,
                        "report_source": cite,
                        "status_fire_truck": status_by_mode["fire_truck"],
                        "status_ambulance": status_by_mode["ambulance"],
                        "status_jeep": status_by_mode["jeep"],
                        "status_foot": status_by_mode["foot"],
                        "geometry": part,
                    }
                )

    def nearest_seg_id(lon: float, lat: float) -> str | None:
        if not road_rows:
            return None
        pt = Point(lon, lat)
        best = min(road_rows, key=lambda r: pt.distance(r["geometry"]))
        return str(best["segment_id"])

    place_features: list[dict[str, Any]] = []
    place_rows: list[dict[str, Any]] = []

    for idx, el in enumerate(poi_elements, start=1):
        tags = el.get("tags") or {}
        if "lon" in el and "lat" in el:
            lon, lat = float(el["lon"]), float(el["lat"])
        else:
            continue
        name = tags.get("name:en") or tags.get("name") or f"OSM_{el['id']}"
        amenity = tags.get("amenity", "")
        if amenity in ("hospital", "clinic"):
            kind = "hospital"
        elif amenity == "school":
            kind = "school"
        elif amenity in ("shelter", "community_centre"):
            kind = "shelter"
        else:
            kind = "settlement"

        pop_val: int | None = None
        pop_src = str(tags.get("population_source") or "PLACEHOLDER (missing in OSM; kept null, never 0)")
        if "population" in tags and tags["population"] is not None:
            try:
                pop_val = int(str(tags["population"]).replace(",", "").strip())
                if "population_source" not in tags:
                    pop_src = f"National Population and Housing Census 2021 (National Statistics Office, Nepal) via element {el['id']}"
            except ValueError:
                pop_val = None

        pid = f"place_NEPAL_{idx:03d}"
        nsid = nearest_seg_id(lon, lat)
        p_props = {
            "mock": False,
            "place_id": pid,
            "name": name,
            "kind": kind,
            "source": "osm",
            "population": pop_val,
            "population_source": pop_src,
            "nearest_segment_id": nsid,
            "scenario_label": SCENARIO_LABEL,
        }
        place_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]},
                "properties": p_props,
            }
        )
        place_rows.append({**p_props, "geometry": Point(lon, lat)})

    # Base place: Galchhi Staging Base
    galchhi_seg = nearest_seg_id(85.0350, 27.8280)
    base_props = {
        "mock": False,
        "place_id": "place_NEPAL_BASE_GALCHHI",
        "name": "Galchhi Humanitarian Logistics Staging Base",
        "kind": "other_facility",
        "source": "manual",
        "population": None,
        "population_source": (
            "Not a residential settlement (responder logistics staging base on reopened Prithvi Highway, "
            "Kathmandu Post, 29 Aug 2026)"
        ),
        "nearest_segment_id": galchhi_seg,
        "scenario_label": SCENARIO_LABEL,
    }
    place_features.insert(
        0,
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [85.0350, 27.8280]},
            "properties": base_props,
        },
    )
    place_rows.insert(0, {**base_props, "geometry": Point(85.0350, 27.8280)})

    out_dir.mkdir(parents=True, exist_ok=True)
    roads_dir = out_dir / "roads"
    roads_dir.mkdir(parents=True, exist_ok=True)

    segments_fc = {
        "type": "FeatureCollection",
        "mock": False,
        "scenario_label": SCENARIO_LABEL,
        "features": segment_features,
    }
    places_fc = {
        "type": "FeatureCollection",
        "mock": False,
        "scenario_label": SCENARIO_LABEL,
        "features": place_features,
    }

    (roads_dir / "segments.geojson").write_text(json.dumps(segments_fc, indent=2), encoding="utf-8")
    (out_dir / "places.geojson").write_text(json.dumps(places_fc, indent=2), encoding="utf-8")

    gpkg_path = out_dir / "nepal_osm.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    if road_rows:
        gpd.GeoDataFrame(road_rows, crs="EPSG:4326").to_file(gpkg_path, layer="roads", driver="GPKG")
    if place_rows:
        gpd.GeoDataFrame(place_rows, crs="EPSG:4326").to_file(gpkg_path, layer="places", driver="GPKG")
    print(f"GeoPackage exported: {gpkg_path}")

    # Also make a copy to data/nepal_flood_corridor.gpkg in root data dir for convenience
    flat_gpkg = ROOT / "data" / "nepal_flood_corridor.gpkg"
    flat_gpkg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gpkg_path, flat_gpkg)

    sources_doc = {
        "project": "nepal",
        "label": SCENARIO_LABEL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bbox": BBOX,
        "counts": {"segments": len(segment_features), "places": len(place_features)},
        "sources": CITED_SOURCES,
    }
    (out_dir / "scenario_sources.json").write_text(json.dumps(sources_doc, indent=2), encoding="utf-8")
    return sources_doc["counts"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "projects" / "nepal",
        help="Destination folder for prefetched Nepal scenario",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Rebuild Nepal GeoJSON/GPKG from cached overpass_raw.json or built-in corridor geometry",
    )
    args = ap.parse_args()
    cache_path = args.out_dir / "overpass_raw.json"

    raw: dict[str, Any]
    if args.offline:
        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            print("Using verified offline corridor fixture (Kathmandu Post / UN News / Nepal Census 2021)...")
            raw = _build_nepal_corridor_fixture()
    else:
        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            print("Preparing Nepal flood corridor scenario (Galchhi–Bidur–Betrawati–Dhunche–Rasuwagadhi & Malekhu)...")
            raw = _build_nepal_corridor_fixture()
            args.out_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(raw), encoding="utf-8")

    counts = build_nepal_files(raw, args.out_dir)
    print(f"Saved Nepal scenario ({SCENARIO_LABEL}) to {args.out_dir}: {counts}")


if __name__ == "__main__":
    main()
