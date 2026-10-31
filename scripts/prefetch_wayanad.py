"""Prefetch OSM roads and places for the 30 July 2024 Wayanad (Chooralmala-Mundakkai) scenario (T6).

Run ONCE while online:
    uv run python scripts/prefetch_wayanad.py

Rebuild offline from cached Overpass payload:
    uv run python scripts/prefetch_wayanad.py --offline

Outputs (under data/projects/wayanad/, gitignored):
    - overpass_raw.json (cached raw OSM JSON for offline rebuilds)
    - wayanad_osm.gpkg (GeoPackage: 'roads' and 'places' layers, EPSG:4326)
    - roads/segments.geojson (validates against contracts/segments.schema.json)
    - places.geojson (validates against contracts/places.schema.json)
    - scenario_sources.json (all report URLs, dates, ODbL attribution, and label)

IMPORTANT: Every segment and metadata file is explicitly labelled:
    "scenario reconstructed from reports, not drone-measured"
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import requests
from pyproj import Geod
from shapely.geometry import LineString, Point
from shapely.ops import substring

ROOT = Path(__file__).resolve().parent.parent
GEOD = Geod(ellps="WGS84")
SCENARIO_LABEL = "scenario reconstructed from reports, not drone-measured"

# Tight bounding box around Punchirimattom -> Mundakkai -> Chooralmala -> Attamala (Meppadi Panchayat, Wayanad).
BBOX = {
    "south": 11.472,
    "north": 11.512,
    "west": 76.135,
    "east": 76.172,
}

# Exact OSM way ID of the Chooralmala river bridge connecting Chooralmala (primary 30778557)
# to the Mundakkai/Attamala southern bank (tertiary 380928381 / 380928408).
CHOORALMALA_BRIDGE_WAY_ID = 380928388

OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

HTTP_HEADERS = {
    "User-Agent": "Vortex-T8.2-Prototype/0.1 (hackFront India 2026 offline landslide advisor; academic research)",
    "Accept": "application/json",
}

CITED_SOURCES = [
    {
        "id": "osm_odbl",
        "title": "OpenStreetMap road network and place nodes (Chooralmala-Mundakkai-Attamala bbox)",
        "url": "https://www.openstreetmap.org/copyright",
        "licence": "ODbL 1.0 (© OpenStreetMap contributors)",
        "date": "retrieved 2026-10-31",
        "quote_or_paraphrase": "OpenStreetMap® is open data, licensed under the Open Data Commons Open Database License (ODbL).",
        "purpose": "Base road geometry and settlement/facility locations for Wayanad scenario",
    },
    {
        "id": "pib_mod_2039494",
        "title": "PIB Ministry of Defence (Release ID 2039494): Indian Army Intensifies Rescue Operations in Wayanad Landslide Affected Areas",
        "url": "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039494",
        "licence": "Government of India public press release (GODL-India)",
        "date": "2024-07-31 (retrieved 2026-10-31)",
        "quote_or_paraphrase": "\"construction of a bridge on the Meppadi-Chooralmala Road will commence\" (Actions Planned for the Day)",
        "purpose": "Confirms road-moved JCB/TATRA/Bailey bridge staging along Meppadi-Chooralmala Road and severed stream crossing requiring airlifted earth-moving equipment",
    },
    {
        "id": "pib_mod_2039871",
        "title": "PIB Ministry of Defence (Release ID 2039871): Indian Army Intensifies Rescue Operation in Areas Affected by Landslide in Wayanad",
        "url": "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039871",
        "licence": "Government of India public press release (GODL-India)",
        "date": "2024-07-31 (retrieved 2026-10-31)",
        "quote_or_paraphrase": "\"operations along six kilometre stretch of landslide affected areas\"; foot bridge completed overnight 30-31 July",
        "purpose": "Documents 6 km landslide-affected stretch, cut-off southern areas prior to 150-ft Bailey bridge, and ambulance deployment from Kalpetta",
    },
    {
        "id": "pib_mod_2041094",
        "title": "PIB Ministry of Defence (Release ID 2041094): Indian Navy Continues with Rescue and Relief Operations at Wayanad",
        "url": "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2041094",
        "licence": "Government of India public press release (GODL-India)",
        "date": "2024-08-03 (retrieved 2026-10-31)",
        "quote_or_paraphrase": "\"connecting the regions of Chooralmala and Mundakkai which were isolated by the landslides\" (para 2)",
        "purpose": "Confirms Chooralmala and Mundakkai were isolated across the river until the Bailey bridge enabled movement of machinery and ambulances, while upper disaster zones remained inaccessible by road (para 3)",
    },
    {
        "id": "sphere_india_sitrep5_2024",
        "title": "Sphere India Situation Report: Wayanad Landslide (26 August 2024, 14:00 PM IST)",
        "url": "https://www.sphereindia.org.in/sites/default/files/2024-08/SI_Sitrep-5__Wayanad_Landslide_26-08-2024.pdf",
        "licence": "Humanitarian situation report (Sphere India public PDF)",
        "date": "2024-08-26 (retrieved 2026-10-31)",
        "quote_or_paraphrase": "30 July 2024 02:17 hrs landslide buried ~700 houses in Mundakkai, Chooralmala, Vellarimala Village (p. 1)",
        "purpose": "Confirms buried residential zones and infrastructure damage in Mundakkai, Chooralmala, and Vellarimala Village (Meppadi Panchayat)",
    },
]

DEFAULT_WIDTH_BY_HIGHWAY = {
    "primary": 7.0,
    "secondary": 6.5,
    "tertiary": 5.5,
    "unclassified": 4.5,
    "residential": 4.0,
    "service": 3.5,
    "track": 3.0,
    "path": 1.5,
    "footway": 1.5,
}


def fetch_overpass(bbox: dict[str, float]) -> dict[str, Any]:
    s, w, n, e = bbox["south"], bbox["west"], bbox["north"], bbox["east"]
    query = f"""
    [out:json][timeout:60];
    (
      way["highway"~"^(primary|secondary|tertiary|unclassified|residential|track)$"]({s},{w},{n},{e});
      node["place"]({s},{w},{n},{e});
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
            resp = requests.post(url, data={"data": query}, headers=HTTP_HEADERS, timeout=45)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_err = exc

    # Official OpenStreetMap v0.6 bbox JSON fallback (bbox area is 0.0015 sq deg << 0.25 limit).
    osm_url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={w},{s},{e},{n}"
    try:
        resp = requests.get(osm_url, headers=HTTP_HEADERS, timeout=45)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise RuntimeError(f"All Overpass and OSM map endpoints failed: {last_err}; {exc}") from exc


def _geodesic_len_m(line: LineString) -> float:
    coords = list(line.coords)
    if len(coords) < 2:
        return 0.0
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return float(abs(GEOD.line_length(lons, lats)))


def _split_way_at_junctions(
    node_ids: list[int],
    nodes_by_id: dict[int, tuple[float, float]],
    junction_node_ids: set[int],
) -> list[LineString]:
    """Split an OSM way at every shared intersection node so graph topology stays connected."""
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
    """Split a junction-to-junction LineString into chunks <= max_len_m."""
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


def classify_wayanad_segment(
    osm_way_id: int,
    mid_lon: float,
    mid_lat: float,
    highway: str,
    tags: dict[str, Any],
) -> tuple[dict[str, str], str, dict[str, list[str]]]:
    """Assign road passability from cited 30 July 2024 Wayanad disaster reports."""
    is_bridge = str(tags.get("bridge", "no")).lower() not in ("no", "false", "0", "")

    # 1. Collapsed Chooralmala river bridge connecting Chooralmala to Mundakkai/Vellarmala/Attamala.
    if osm_way_id == CHOORALMALA_BRIDGE_WAY_ID or (is_bridge and 11.4970 <= mid_lat <= 11.5005):
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"}
        cite = (
            "PIB Ministry of Defence Release ID 2041094 (2024-08-03, para 2, "
            "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2041094) & Release ID 2039494 "
            "(2024-07-31, Actions Planned, https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039494): "
            "Chooralmala-Mundakkai river crossing severed by 30 July 2024 landslides prior to Bailey bridge"
        )
        reasons = {
            m: ["Chooralmala river bridge severed by landslide debris flow prior to Bailey bridge"]
            for m in st
        }
        return st, cite, reasons

    # 2. Upper Punchirimattom landslide crown & boulder run-out zone (south of Mundakkai town, lat < 11.4855).
    if mid_lat < 11.4855 and mid_lon <= 76.1605:
        if highway in ("primary", "secondary", "tertiary", "unclassified", "residential"):
            st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "partial"}
            cite = (
                "PIB Ministry of Defence Release ID 2041094 (2024-08-03, para 3, "
                "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2041094: upper disaster area "
                "'inaccessible by road', rescue teams airlifted/on foot) & Sphere India SitRep-5 (2024-08-26, "
                "p. 1, https://www.sphereindia.org.in/sites/default/files/2024-08/SI_Sitrep-5__Wayanad_Landslide_26-08-2024.pdf)"
            )
            reasons = {
                "fire_truck": ["Upper Punchirimattom-Mundakkai road inaccessible to vehicles due to landslide debris"],
                "ambulance": ["Upper Punchirimattom-Mundakkai road inaccessible to vehicles due to landslide debris"],
                "jeep": ["Upper Punchirimattom-Mundakkai road inaccessible to vehicles due to landslide debris"],
                "foot": ["Foot rescue columns traversed upper landslide zone on foot"],
            }
            return st, cite, reasons

    # 3. Southern bank Mundakkai - Vellarmala - Attamala road network (11.4855 <= lat < 11.4995, south of river).
    # Cut off from northern base by collapsed Chooralmala bridge (way 380928388); once bridged,
    # 4x4 jeeps, crawl-speed ambulances, and foot teams could traverse into Mundakkai/Attamala.
    if 11.4855 <= mid_lat < 11.4995 and highway in ("secondary", "tertiary", "unclassified", "residential"):
        # Check if on northern Chooralmala town bank (west of bridge, connected to primary 30778557)
        if osm_way_id == 30778557 or (mid_lat >= 11.49915 and mid_lon < 76.1600):
            pass  # Handled by northern Chooralmala staging rule below
        else:
            st = {"fire_truck": "blocked", "ambulance": "partial", "jeep": "partial", "foot": "open"}
            cite = (
                "PIB Ministry of Defence Release ID 2041094 (2024-08-03, para 2, "
                "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2041094: Bailey bridge enabled "
                "ambulances into isolated Mundakkai) & Sphere India SitRep-5 (2024-08-26, p. 1, "
                "https://www.sphereindia.org.in/sites/default/files/2024-08/SI_Sitrep-5__Wayanad_Landslide_26-08-2024.pdf); "
                "PLACEHOLDER (fire_truck=blocked on debris-damaged hill roads pending drone width measurement)"
            )
            reasons = {
                "fire_truck": ["PLACEHOLDER: debris-damaged southern hill carriageway assumed blocked for 16t fire tender"],
                "ambulance": ["Crawl-speed ambulance evacuation feasible once Chooralmala bridge is open"],
                "jeep": ["4x4 light vehicle passage feasible once Chooralmala bridge is open"],
                "foot": ["Passable on foot on southern bank"],
            }
            return st, cite, reasons

    # 4. Northern approach from Meppadi into Chooralmala staging town & northern colonies.
    if (osm_way_id == 30778557 or mid_lat >= 11.4990) and highway in (
        "primary",
        "secondary",
        "tertiary",
        "unclassified",
        "residential",
    ):
        st = {"fire_truck": "open", "ambulance": "open", "jeep": "open", "foot": "open"}
        cite = (
            "PIB Ministry of Defence Release ID 2039494 (2024-07-31, Status of Additional Columns, "
            "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039494) & Release ID 2039871 "
            "(2024-07-31, para 4, https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039871): "
            "Meppadi-Chooralmala northern road carried TATRA, Bailey bridge sets, 3 JCBs, and ambulances"
        )
        reasons = {m: ["Meppadi-Chooralmala northern staging corridor open in PIB Defence reports"] for m in st}
        return st, cite, reasons

    # 5. Minor tea-estate tracks inside the 6 km landslide valley -> blocked for wheeled vehicles, unknown for foot.
    if highway == "track" and mid_lat < 11.5005 and 76.145 <= mid_lon <= 76.163:
        st = {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "unknown"}
        cite = (
            "PLACEHOLDER (minor OSM highway=track inside 6 km landslide valley reported in PIB Release ID "
            "2039871, 2024-07-31, https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039871: "
            "unpaved estate footpath/track treated as blocked for wheeled vehicles, unknown for foot)"
        )
        reasons = {
            "fire_truck": ["Unpaved estate track in landslide valley impassable for heavy fire tender"],
            "ambulance": ["Unpaved estate track in landslide valley impassable for ambulance"],
            "jeep": ["Unverified hill track inside landslide zone blocked for wheeled access"],
            "foot": ["No post-landslide verification for minor estate track -> unknown (never assumed open)"],
        }
        return st, cite, reasons

    # 6. Any other unverified minor track/path with no specific report mention -> unknown (Hard Rule 2).
    st = {"fire_truck": "unknown", "ambulance": "unknown", "jeep": "unknown", "foot": "unknown"}
    cite = "PLACEHOLDER (no post-landslide passability report found for minor side track -> unknown)"
    reasons = {m: ["Unreported minor track kept as unknown (never assumed open)"] for m in st}
    return st, cite, reasons


def build_wayanad_files(overpass_data: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    nodes_by_id: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, Any]] = []
    poi_elements: list[dict[str, Any]] = []

    allowed_highways = {"primary", "secondary", "tertiary", "unclassified", "residential", "track"}
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
                if "center" in el:
                    poi_elements.append(el)
                else:
                    w_coords = [nodes_by_id[nid] for nid in el.get("nodes", []) if nid in nodes_by_id]
                    if w_coords:
                        cx = sum(c[0] for c in w_coords) / len(w_coords)
                        cy = sum(c[1] for c in w_coords) / len(w_coords)
                        poi_elements.append({**el, "center": {"lon": cx, "lat": cy}})

    # Identify all shared OSM junction nodes (nodes referenced >= 2 times across road ways).
    node_ref_counts: Counter[int] = Counter()
    for way in ways:
        for nid in way.get("nodes", []):
            if nid in nodes_by_id:
                node_ref_counts[int(nid)] += 1
    junction_node_ids = {nid for nid, cnt in node_ref_counts.items() if cnt >= 2}

    segment_features: list[dict[str, Any]] = []
    road_gpkg_rows: list[dict[str, Any]] = []
    seg_counter = 0

    for way in sorted(ways, key=lambda w: int(w["id"])):
        way_id = int(way["id"])
        tags = way.get("tags") or {}
        highway = str(tags.get("highway", "unclassified"))
        raw_nodes = [int(nid) for nid in way.get("nodes", []) if int(nid) in nodes_by_id]
        if len(raw_nodes) < 2:
            continue

        raw_w = tags.get("width")
        corridor_w: float | None = None
        w_source = "default_by_class(PLACEHOLDER)"
        if raw_w is not None:
            try:
                corridor_w = float(str(raw_w).split()[0].replace("m", ""))
                w_source = "osm_tag"
            except ValueError:
                corridor_w = None
        if corridor_w is None:
            corridor_w = DEFAULT_WIDTH_BY_HIGHWAY.get(highway, 4.0)

        for arc in _split_way_at_junctions(raw_nodes, nodes_by_id, junction_node_ids):
            for part in _split_line_max_50m(arc, max_len_m=50.0):
                seg_counter += 1
                sid = f"seg_WAY_{seg_counter:04d}"
                mid = part.interpolate(0.5, normalized=True)
                status_by_mode, cite, scen_reasons = classify_wayanad_segment(
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
                    "corridor_width_source": w_source,
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
                road_gpkg_rows.append(
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

    # Identify main connected component of paved/classified roads so places & staging base attach cleanly.
    comp_graph = nx.Graph()
    for r in road_gpkg_rows:
        c0 = (round(r["geometry"].coords[0][0], 6), round(r["geometry"].coords[0][1], 6))
        c1 = (round(r["geometry"].coords[-1][0], 6), round(r["geometry"].coords[-1][1], 6))
        comp_graph.add_edge(c0, c1, segment_id=r["segment_id"])

    main_vertices: set[tuple[float, float]] = set()
    if comp_graph.number_of_nodes() > 0:
        main_vertices = set(max(nx.connected_components(comp_graph), key=len))

    # Prefer snapping places onto non-track roads in the main connected component when within ~300 m.
    main_non_track_rows = [
        r
        for r in road_gpkg_rows
        if r["highway"] != "track"
        and (
            (round(r["geometry"].coords[0][0], 6), round(r["geometry"].coords[0][1], 6)) in main_vertices
        )
    ]
    candidate_road_rows = main_non_track_rows or road_gpkg_rows

    def nearest_seg_id(lon: float, lat: float) -> str | None:
        if not candidate_road_rows:
            return None
        pt = Point(lon, lat)
        best = min(candidate_road_rows, key=lambda r: pt.distance(r["geometry"]))
        return str(best["segment_id"])

    place_features: list[dict[str, Any]] = []
    place_gpkg_rows: list[dict[str, Any]] = []

    for idx, el in enumerate(poi_elements, start=1):
        tags = el.get("tags") or {}
        if "lon" in el and "lat" in el:
            lon, lat = float(el["lon"]), float(el["lat"])
        elif "center" in el:
            lon, lat = float(el["center"]["lon"]), float(el["center"]["lat"])
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
        pop_src = "PLACEHOLDER (missing in OSM; kept null, never 0)"
        if "population" in tags:
            try:
                pop_val = int(str(tags["population"]).replace(",", "").strip())
                pop_src = f"OpenStreetMap population tag on element {el['id']} (ODbL, retrieved 2026-10-31)"
            except ValueError:
                pop_val = None

        pid = f"place_WAY_{idx:03d}"
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
        place_gpkg_rows.append({**p_props, "geometry": Point(lon, lat)})

    # Ensure the northern Chooralmala staging base point (on the open Meppadi primary/tertiary approach
    # of the main connected road component) is present so routing starts from the real responder entry side.
    northern_open = [
        r
        for r in candidate_road_rows
        if r["status_ambulance"] == "open"
        and r["highway"] in ("primary", "secondary", "tertiary")
    ]
    if not northern_open:
        northern_open = [r for r in road_gpkg_rows if r["status_ambulance"] == "open"]
    if northern_open:
        top_seg = max(northern_open, key=lambda r: max(c[1] for c in r["geometry"].coords))
        coords_top = list(top_seg["geometry"].coords)
        bx, by = max((coords_top[0], coords_top[-1]), key=lambda c: c[1])
        base_props = {
            "mock": False,
            "place_id": "place_WAY_BASE_MEPPADI_APPROACH",
            "name": "Chooralmala North Staging Point (Meppadi Road)",
            "kind": "other_facility",
            "source": "manual",
            "population": None,
            "population_source": (
                "Not a residential settlement (responder staging point along Meppadi-Chooralmala Road, "
                "PIB Release ID 2039494, 2024-07-31, https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039494)"
            ),
            "nearest_segment_id": top_seg["segment_id"],
            "scenario_label": SCENARIO_LABEL,
        }
        place_features.insert(
            0,
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(float(bx), 7), round(float(by), 7)]},
                "properties": base_props,
            },
        )
        place_gpkg_rows.insert(0, {**base_props, "geometry": Point(float(bx), float(by))})

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

    # If WorldPop 2020 cache is present on disk, attach settlement populations offline (C1/T16).
    worldpop_tif = out_dir / "worldpop_wayanad_2020.tif"
    if worldpop_tif.is_file():
        from scripts.prefetch_worldpop_wayanad import attach_worldpop_to_places_fc

        attach_worldpop_to_places_fc(places_fc, worldpop_tif)
        place_gpkg_rows = []
        for feat in places_fc["features"]:
            px, py = feat["geometry"]["coordinates"][:2]
            place_gpkg_rows.append({**feat["properties"], "geometry": Point(float(px), float(py))})

    (roads_dir / "segments.geojson").write_text(json.dumps(segments_fc, indent=2), encoding="utf-8")
    (out_dir / "places.geojson").write_text(json.dumps(places_fc, indent=2), encoding="utf-8")

    gpkg_path = out_dir / "wayanad_osm.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    if road_gpkg_rows:
        gpd.GeoDataFrame(road_gpkg_rows, crs="EPSG:4326").to_file(gpkg_path, layer="roads", driver="GPKG")
    if place_gpkg_rows:
        gpd.GeoDataFrame(place_gpkg_rows, crs="EPSG:4326").to_file(gpkg_path, layer="places", driver="GPKG")

    sources_doc = {
        "project": "wayanad",
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
        default=ROOT / "data" / "projects" / "wayanad",
        help="Destination folder for prefetched Wayanad scenario",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Rebuild Wayanad GeoJSON/GPKG from cached overpass_raw.json without network",
    )
    args = ap.parse_args()
    cache_path = args.out_dir / "overpass_raw.json"

    if args.offline:
        if not cache_path.exists():
            raise FileNotFoundError(f"Offline rebuild requested, but {cache_path} does not exist.")
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        print(f"Fetching OSM roads and places for Chooralmala/Mundakkai bbox {BBOX}...")
        raw = fetch_overpass(BBOX)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(raw), encoding="utf-8")

    counts = build_wayanad_files(raw, args.out_dir)
    print(f"Saved Wayanad scenario ({SCENARIO_LABEL}) to {args.out_dir}: {counts}")


if __name__ == "__main__":
    main()
