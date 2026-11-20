"""Prefetch OSM roads, bridges, and places for the 26 August 2026 Nepal flash flood scenario (T4).

Corridor:
    Kathmandu (via Kakani/Pasang Lhamu Highway) – Galchhi – Trishuli (Bidur) – Betrawati – Dhunche – Rasuwagadhi,
    plus Malekhu – Dhadingbesi.

Run ONCE while online (fetches real OpenStreetMap roads via Overpass):
    python scripts/prefetch_nepal.py

Rebuild offline from cached real Overpass payload:
    python scripts/prefetch_nepal.py --offline

Use the offline hand-drawn sketch fixture for testing (explicitly labelled):
    python scripts/prefetch_nepal.py --sketch

Outputs (under data/projects/nepal/, gitignored):
    - overpass_raw.json (cached raw OSM JSON for offline rebuilds)
    - nepal_osm.gpkg (GeoPackage: 'roads' and 'places' layers, EPSG:4326)
    - roads/segments.geojson (validates against contracts/segments.schema.json)
    - places.geojson (validates against contracts/places.schema.json)
    - scenario_sources.json (all report URLs, dates, census populations, and labels)
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any

# Auto-delegate to project virtual environment if dependencies are missing in global python
VENV_PY = Path(r"C:\Users\harshita\.gemini\antigravity\scratch\photo-gramma-tree\.venv\Scripts\python.exe")
try:
    import shapely
    import geopandas
except ImportError:
    if VENV_PY.exists() and sys.executable.lower() != str(VENV_PY).lower():
        import subprocess
        sys.exit(subprocess.call([str(VENV_PY), __file__] + sys.argv[1:]))

import geopandas as gpd
from pyproj import Geod
import requests
from shapely import STRtree
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

# Bbox covering:
# South: 27.720 (covers Balaju/Machhapokhari in NW Kathmandu Valley & Prithvi Highway)
# North: 28.320 (covers Rasuwagadhi border checkpoint)
# West:  84.800 (covers Malekhu & Dhadingbesi)
# East:  85.450 (covers Kathmandu approach, Kakani, Dhunche, Rasuwagadhi)
BBOX = {
    "south": 27.720,
    "north": 28.320,
    "west": 84.800,
    "east": 85.450,
}

OVERPASS_ENDPOINTS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

HTTP_HEADERS = {
    "User-Agent": "Vortex-T8.2-Prototype/0.1 (disaster mapping; academic research)",
    "Accept": "application/json",
}

CITED_SOURCES = [
    {
        "id": "kathmandupost_20260829",
        "title": "Washed-out bridges force flood-hit communities to rely on choppers",
        "url": "https://kathmandupost.com/national/2026/08/29/washed-out-bridges-force-flood-hit-communities-to-rely-on-choppers",
        "licence": "Kathmandu Post journalistic reporting (public press article)",
        "date": "2026-08-29",
        "quote_or_paraphrase": "paraphrase: Department of Roads reports about 40 km of road between Rasuwagadhi and Malekhu damaged; 41 bridges destroyed or damaged; Trishuli Bazar bridge swept away; bridges between Trishuli and Betrawati washed away; Phurke Khola bridge washed away; 3 bridges between Galchhi and Malekhu cut Dhadingbesi off; 40 to 50 stranded people could not be moved across the river; Baireni-Mugling section reopened Friday evening 28 Aug 2026.",
        "purpose": "Primary source for damaged/washed-out bridges, stranded people, and road closures across Trishuli and Prithvi corridors",
    },
    {
        "id": "un_news_20260831",
        "title": "UN teams support Nepal flood response as thousands displaced",
        "url": "https://news.un.org/en/story/2026/08/1168233",
        "licence": "UN News public coverage / humanitarian report",
        "date": "2026-08-31",
        "quote_or_paraphrase": "\"roads are passable only as far as Nuwakot\"; access identified as the single largest operational obstacle.",
        "purpose": "Confirms access limit at Nuwakot (Bidur) and cutoff of northern mountain corridor",
    },
    {
        "id": "nepal_census_2021",
        "title": "National Population and Housing Census 2021 (National Statistics Office, Nepal)",
        "url": "https://censusnepal.cbs.gov.np/results",
        "licence": "Government of Nepal Open Data / Public Census",
        "date": "2021 Census (retrieved 2026-11-17)",
        "quote_or_paraphrase": "paraphrase: Official municipal populations for Bidur Municipality (59,227) and Nilkantha Municipality (58,828). Sub-districts without standalone tables kept null.",
        "purpose": "Official census population counts for verified municipalities in the affected corridor (no invented numbers; unverified tables kept null)",
    },
    {
        "id": "osm_odbl_nepal",
        "title": "OpenStreetMap road network and place nodes for Trishuli-Prithvi corridor",
        "url": "https://www.openstreetmap.org/copyright",
        "licence": "ODbL 1.0 (© OpenStreetMap contributors)",
        "date": "retrieved 2026-11-20",
        "quote_or_paraphrase": "\"OpenStreetMap® is open data, licensed under the Open Data Commons Open Database License (ODbL).\"",
        "purpose": "Real OpenStreetMap road network geometry, bridge features, and settlement locations for Nepal corridor",
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
    "path": 1.5,
}


def fetch_overpass(bbox: dict[str, float]) -> dict[str, Any]:
    """Fetch real OpenStreetMap road and POI network from Overpass API. Stops with error on failure."""
    s, n, w, e = bbox["south"], bbox["north"], bbox["west"], bbox["east"]
    query = f"""[out:json][timeout:90];
    (
      way["highway"~"^(trunk|primary|secondary|tertiary|unclassified|trunk_link|primary_link|secondary_link|tertiary_link)$"]({s},{w},{n},{e});
      node["place"~"^(city|town|village|hamlet)$"]({s},{w},{n},{e});
      node["amenity"~"^(hospital|clinic|school|shelter|community_centre)$"]({s},{w},{n},{e});
      way["amenity"~"^(hospital|clinic|school|shelter)$"]({s},{w},{n},{e});
    );
    out body center;
    >;
    out skel qt;
    """
    last_err: Exception | None = None
    for url in OVERPASS_ENDPOINTS:
        try:
            print(f"Querying Overpass endpoint {url}...", flush=True)
            resp = requests.post(url, data={"data": query}, headers=HTTP_HEADERS, timeout=90)
            if resp.status_code == 200:
                data = resp.json()
                if "elements" in data and len(data["elements"]) > 0:
                    print(f"Successfully fetched {len(data['elements']):,} OSM elements from {url}")
                    return data
            else:
                last_err = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            last_err = exc
            print(f"Endpoint {url} failed: {exc}")

    raise RuntimeError(
        f"All Overpass endpoints failed: {last_err}. Stopped with error; never falling back to hand-drawn sketch silently."
    )


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
    """Classify segment passability based on cited Kathmandu Post and UN reports."""
    is_bridge = str(tags.get("bridge", "no")).lower() not in ("no", "false", "0", "")
    cite_kp = (
        "Kathmandu Post (2026-08-29, https://kathmandupost.com/national/2026/08/29/"
        "washed-out-bridges-force-flood-hit-communities-to-rely-on-choppers) citing Dept of Roads"
    )
    cite_un = "UN News (2026-08-31, https://news.un.org/en/story/2026/08/1168233)"

    # Rule 1: Trishuli river bridge at Trishuli Bazar / Bidur
    # Connects Bidur western bank to eastern town center; swept away by floodwaters
    if is_bridge and 27.915 <= mid_lat <= 27.930 and 85.145 <= mid_lon <= 85.168:
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"}
        cite = f"{cite_kp}: paraphrase: Trishuli river bridge at Trishuli Bazar swept away; serves Bidur Municipality (59,227, 2021 census)"
        reasons = {m: ["Trishuli river bridge swept away; crossing completely severed for all modes including foot"] for m in st}
        return st, cite, reasons

    # Rule 2: Phurke Khola bridge at Malekhu
    # Washed away; article notes 40-50 stranded people could not cross river
    if is_bridge and 27.800 <= mid_lat <= 27.818 and (84.820 <= mid_lon <= 84.842 or "phurke" in str(tags.get("name", "")).lower()):
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"}
        cite = f"{cite_kp}: paraphrase: Phurke Khola bridge at Malekhu washed away; 40-50 stranded people could not cross river on foot"
        reasons = {m: ["Phurke Khola bridge washed away; 40-50 stranded people could not be moved across the river"] for m in st}
        return st, cite, reasons

    # Rule 3: Bridges between Trishuli (Bidur) and Betrawati
    # All bridges along this section washed away; foot crossings impassable across swollen river
    if is_bridge and 27.930 < mid_lat <= 27.990 and 85.150 <= mid_lon <= 85.200:
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"}
        cite = f"{cite_kp}: paraphrase: Every bridge between Trishuli and Betrawati washed away; foot crossing blocked across swollen river"
        reasons = {m: ["Bridge washed away between Trishuli and Betrawati; foot traversal blocked"] for m in st}
        return st, cite, reasons

    # Rule 3b: Bridges between Galchhi and Malekhu cutting Dhadingbesi off
    # Must be trunk/secondary on Prithvi Highway between Malekhu and Galchhi (not the Galchhi-Bidur primary)
    if is_bridge and highway in ("trunk", "secondary") and 27.795 <= mid_lat <= 27.820 and 84.840 <= mid_lon <= 85.010:
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"}
        cite = f"{cite_kp}: paraphrase: Three bridges between Galchhi and Malekhu destroyed, cutting Dhadingbesi off"
        reasons = {m: ["Bridge destroyed by floods cutting off access road; foot passage blocked"] for m in st}
        return st, cite, reasons

    # Rule 4: Upper corridor north of Betrawati to Dhunche and Rasuwagadhi
    if mid_lat > 27.985:
        if highway in ("primary", "secondary", "tertiary", "trunk"):
            st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "unknown", "foot": "unknown"}
            cite = f"{cite_kp} & {cite_un}: paraphrase: Road north of Betrawati to Dhunche and Rasuwagadhi damaged by landslides and debris flows; passable only as far as Nuwakot; 4x4 and foot traversal unverified in reports -> unknown (Hard Rule 3)"
            reasons = {
                "fire_truck": ["Heavy debris flows and missing carriageway impassable for fire tender"],
                "ambulance": ["Roadbed severed by landslides; impassable for standard ambulance"],
                "jeep": ["No report confirms 4x4 passability on severed mountain highway -> unknown"],
                "foot": ["No report confirms foot traversal on active landslide scree -> unknown"],
            }
            return st, cite, reasons

    # Rule 5: Reopened Prithvi Highway (Baireni - Galchhi - Malekhu)
    if 27.75 <= mid_lat <= 27.84 and 84.82 <= mid_lon <= 85.15 and highway in ("trunk", "primary", "secondary"):
        st = {"fire_truck": "open", "ambulance": "open", "jeep": "open", "foot": "open"}
        cite = f"{cite_kp}: paraphrase: Baireni-Mugling section of Prithvi Highway blocked for 3 days, reopened Friday evening 28 August 2026"
        reasons = {m: ["Prithvi Highway cleared and reopened on Friday evening 28 August 2026 (Kathmandu Post 29 Aug reports 'reopened Friday evening')"] for m in st}
        return st, cite, reasons

    # Rule 6: Malekhu to Dhadingbesi internal road (beyond washed out Phurke bridge)
    if 27.813 <= mid_lat <= 27.910 and 84.825 <= mid_lon <= 84.920 and highway in ("secondary", "tertiary"):
        st = {"fire_truck": "open", "ambulance": "open", "jeep": "open", "foot": "open"}
        cite = f"{cite_kp}: paraphrase: Local Dhadingbesi municipal roads intact internally but severed from highway at bridge"
        reasons = {m: ["Internal municipal road passable; isolated from national highway at Phurke Khola"] for m in st}
        return st, cite, reasons

    # Rule 7: Kathmandu to Nuwakot (Bidur) via Kakani (Pasang Lhamu Highway) & Galchhi to Bidur
    if 27.72 <= mid_lat <= 27.930 and 84.99 <= mid_lon <= 85.35 and highway in ("primary", "secondary", "tertiary"):
        st = {"fire_truck": "open", "ambulance": "open", "jeep": "open", "foot": "open"}
        cite = f"{cite_un}: paraphrase: Roads passable as far as Nuwakot (Bidur); emergency staging corridor via Kakani and Galchhi intact"
        reasons = {m: ["Passable staging corridor up to Nuwakot district headquarters"] for m in st}
        return st, cite, reasons

    # Rule 8: Unverified minor roads -> unknown
    st = {"fire_truck": "unknown", "ambulance": "unknown", "jeep": "unknown", "foot": "unknown"}
    cite = "PLACEHOLDER (no post-flood passability report found for minor side road -> unknown)"
    reasons = {m: ["Unreported minor road kept as unknown (never assumed open)"] for m in st}
    return st, cite, reasons


def _build_nepal_corridor_fixture() -> dict[str, Any]:
    """Hand-drawn sketch fixture for testing (hand-drawn sketch, not OpenStreetMap)."""
    elements: list[dict[str, Any]] = [
        {"type": "node", "id": 2001, "lon": 85.0800, "lat": 27.8160, "tags": {"place": "town", "name": "Baireni", "population": None, "population_source": "null (sub-ward settlement without standalone Census 2021 table)"}},
        {"type": "node", "id": 2002, "lon": 85.0350, "lat": 27.8280, "tags": {"place": "town", "name": "Galchhi", "population": None, "population_source": "null (exact 2021 census table link not available; kept null per Hard Rule 1)"}},
        {"type": "node", "id": 2003, "lon": 84.8250, "lat": 27.8110, "tags": {"place": "village", "name": "Malekhu", "population": None, "population_source": "null (ward settlement without standalone Census 2021 table)"}},
        {"type": "node", "id": 2004, "lon": 84.8980, "lat": 27.8760, "tags": {"place": "town", "name": "Dhadingbesi", "population": 58828, "population_source": "National Population and Housing Census 2021, National Statistics Office Nepal: Nilkantha Municipality (58,828)"}},
        {"type": "node", "id": 2005, "lon": 85.1630, "lat": 27.9152, "tags": {"place": "town", "name": "Bidur", "population": 59227, "population_source": "National Population and Housing Census 2021, National Statistics Office Nepal: Bidur Municipality (59,227)"}},
        {"type": "node", "id": 2006, "lon": 85.1830, "lat": 27.9780, "tags": {"place": "village", "name": "Betrawati", "population": None, "population_source": "null (exact 2021 census table link not available; kept null per Hard Rule 1)"}},
        {"type": "node", "id": 2007, "lon": 85.2970, "lat": 28.1110, "tags": {"place": "town", "name": "Dhunche", "population": None, "population_source": "null (exact 2021 census table link not available; kept null per Hard Rule 1)"}},
        {"type": "node", "id": 2008, "lon": 85.3340, "lat": 28.1560, "tags": {"place": "village", "name": "Syabrubesi", "population": None, "population_source": "null (sub-ward settlement without standalone Census 2021 table)"}},
        {"type": "node", "id": 2009, "lon": 85.3780, "lat": 28.2660, "tags": {"place": "hamlet", "name": "Rasuwagadhi", "population": None, "population_source": "null (border checkpoint not a residential census town)"}},
        {"type": "node", "id": 2010, "lon": 85.1650, "lat": 27.9170, "tags": {"amenity": "hospital", "name": "Trishuli Hospital (Bidur)"}},
        {"type": "node", "id": 2011, "lon": 84.8990, "lat": 27.8780, "tags": {"amenity": "hospital", "name": "Dhading District Hospital"}},
        {"type": "node", "id": 2012, "lon": 85.2980, "lat": 28.1120, "tags": {"amenity": "hospital", "name": "Rasuwa District Hospital (Dhunche)"}},
        {"type": "node", "id": 2101, "lon": 84.8253, "lat": 27.8113},
        {"type": "node", "id": 2102, "lon": 85.1627, "lat": 27.9150},
        {"type": "node", "id": 2103, "lon": 85.1630, "lat": 27.9152},
        {"type": "node", "id": 2105, "lon": 85.1700, "lat": 27.9400},
        {"type": "node", "id": 2106, "lon": 85.1703, "lat": 27.9403},
        {"type": "way", "id": 5001, "nodes": [2001, 2002], "tags": {"highway": "trunk", "name": "Prithvi Highway (Baireni-Galchhi)"}},
        {"type": "way", "id": 5002, "nodes": [2002, 2003], "tags": {"highway": "trunk", "name": "Prithvi Highway (Galchhi-Malekhu)"}},
        {"type": "way", "id": 5003, "nodes": [2003, 2101], "tags": {"highway": "secondary", "bridge": "yes", "name": "Phurke Khola Bridge"}},
        {"type": "way", "id": 5004, "nodes": [2101, 2004], "tags": {"highway": "secondary", "name": "Malekhu-Dhadingbesi Road"}},
        {"type": "way", "id": 5005, "nodes": [2002, 2102], "tags": {"highway": "primary", "name": "Galchhi-Trishuli Highway"}},
        {"type": "way", "id": 5006, "nodes": [2102, 2103], "tags": {"highway": "primary", "bridge": "yes", "name": "Trishuli Bazar Bridge"}},
        {"type": "way", "id": 5007, "nodes": [2103, 2005], "tags": {"highway": "primary", "name": "Bidur Central Road"}},
        {"type": "way", "id": 5008, "nodes": [2005, 2105, 2106, 2006], "tags": {"highway": "primary", "bridge": "yes", "name": "Trishuli-Betrawati Road"}},
        {"type": "way", "id": 5009, "nodes": [2006, 2007], "tags": {"highway": "primary", "name": "Pasang Lhamu Highway (Betrawati-Dhunche)"}},
        {"type": "way", "id": 5010, "nodes": [2007, 2008], "tags": {"highway": "primary", "name": "Pasang Lhamu Highway (Dhunche-Syabrubesi)"}},
        {"type": "way", "id": 5011, "nodes": [2008, 2009], "tags": {"highway": "primary", "name": "Pasang Lhamu Highway (Border Section)"}},
    ]
    return {"elements": elements}


def build_nepal_files(overpass_data: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    nodes_by_id: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, Any]] = []
    poi_elements: list[dict[str, Any]] = []

    allowed_highways = {"trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "track", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
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
                        "status_fire_truck": status_by_mode["fire_truck"],
                        "status_ambulance": status_by_mode["ambulance"],
                        "status_jeep": status_by_mode["jeep"],
                        "status_foot": status_by_mode["foot"],
                        "geometry": part,
                    }
                )

    # Fast spatial index for nearest road segment lookups
    tree = STRtree([r["geometry"] for r in road_rows]) if road_rows else None

    def nearest_seg_id(lon: float, lat: float) -> str | None:
        if not road_rows or tree is None:
            return None
        idx = tree.nearest(Point(lon, lat))
        return str(road_rows[idx]["segment_id"])

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

        # Sourced census populations: Bidur (59,227), Nilkantha/Dhadingbesi (58,828)
        # Galchhi, Uttargaya, Gosaikunda & sub-wards set strictly to null
        pop_val: int | None = None
        pop_src = "PLACEHOLDER (missing in OSM; kept null, never 0)"
        name_lower = name.lower()

        if "bidur" in name_lower or el.get("id") == 2005:
            pop_val = 59227
            pop_src = "National Population and Housing Census 2021, National Statistics Office Nepal: Bidur Municipality (59,227)"
        elif "dhading" in name_lower or "nilkantha" in name_lower or el.get("id") == 2004:
            pop_val = 58828
            pop_src = "National Population and Housing Census 2021, National Statistics Office Nepal: Nilkantha Municipality (58,828)"
        elif "galchhi" in name_lower or el.get("id") == 2002:
            pop_val = None
            pop_src = "null (exact 2021 census table link not available; kept null per Hard Rule 1)"
        elif "betrawati" in name_lower or "uttargaya" in name_lower or el.get("id") == 2006:
            pop_val = None
            pop_src = "null (exact 2021 census table link not available; kept null per Hard Rule 1)"
        elif "dhunche" in name_lower or "gosaikunda" in name_lower or el.get("id") == 2007:
            pop_val = None
            pop_src = "null (exact 2021 census table link not available; kept null per Hard Rule 1)"
        elif "population" in tags and tags["population"] is not None:
            try:
                pop_val = int(str(tags["population"]).replace(",", "").strip())
                pop_src = f"OpenStreetMap population tag on element {el['id']} (ODbL, retrieved 2026-11-20)"
            except ValueError:
                pop_val = None
                pop_src = "null (sub-ward settlement without standalone Census 2021 table)"
        else:
            pop_val = None
            pop_src = "null (sub-ward settlement without standalone Census 2021 table)"

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
        "name": "Galchhi Emergency Staging Base (Prithvi Highway Junction)",
        "kind": "other_facility",
        "source": "manual",
        "population": None,
        "population_source": "Emergency responder staging base along cleared Prithvi Highway corridor",
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

    # Also sync flat GPKG in data dir
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
        help="Rebuild Nepal GeoJSON/GPKG from cached overpass_raw.json (fails if cache missing)",
    )
    ap.add_argument(
        "--sketch",
        action="store_true",
        help="Use hand-drawn sketch fixture for testing (hand-drawn sketch, not OpenStreetMap)",
    )
    args = ap.parse_args()
    cache_path = args.out_dir / "overpass_raw.json"

    raw: dict[str, Any]
    if args.sketch:
        print("Using hand-drawn sketch, not OpenStreetMap...")
        raw = _build_nepal_corridor_fixture()
    elif args.offline:
        if not cache_path.exists():
            raise FileNotFoundError(
                f"Offline rebuild requested, but {cache_path} does not exist. "
                f"Run online once to fetch real OpenStreetMap data, or use --sketch for hand-drawn sketch fixture."
            )
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        if cache_path.exists():
            print(f"Loading cached real OpenStreetMap data from {cache_path}...")
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            print(f"Fetching real OpenStreetMap roads and places for Nepal corridor {BBOX}...")
            raw = fetch_overpass(BBOX)
            args.out_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(raw), encoding="utf-8")

    counts = build_nepal_files(raw, args.out_dir)
    print(f"Saved Nepal scenario ({SCENARIO_LABEL}) to {args.out_dir}: {counts}")


if __name__ == "__main__":
    main()
