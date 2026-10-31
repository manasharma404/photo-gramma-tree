"""Road-place topology builder, NetworkX reachability solver, and T5 reopen planner."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import networkx as nx
from pyproj import Geod

from advisor import MODES

GEOD = Geod(ellps="WGS84")
MODE_PRIORITY_ORDER = {"ambulance": 0, "fire_truck": 1, "jeep": 2, "foot": 3}


@dataclass
class Junction:
    junction_id: str
    lon: float
    lat: float


@dataclass
class SegmentEdge:
    segment_id: str
    u: str
    v: str
    length_m: float
    debris_volume_m3: float | None
    status_by_mode: dict[str, str]
    reasons_by_mode: dict[str, list[str]]
    source: str
    needs_verification: bool


@dataclass
class PlaceNode:
    place_id: str
    name: str | None
    kind: str
    population: int | None
    population_source: str
    nearest_segment_id: str | None
    lon: float
    lat: float
    junction_id: str | None

    @property
    def facility(self) -> str | None:
        return None if self.kind == "settlement" else self.kind


@dataclass
class Topology:
    mock: bool
    junctions: dict[str, Junction]
    segments: dict[str, SegmentEdge]
    places: list[PlaceNode]
    base_place_id: str | None = None
    base_junction_id: str | None = None
    extra_meta: dict[str, Any] = field(default_factory=dict)


def _dist_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    if lon1 == lon2 and lat1 == lat2:
        return 0.0
    _, _, d = GEOD.inv(lon1, lat1, lon2, lat2)
    return float(abs(d))


def _line_length_m(coords: list[list[float]]) -> float:
    if len(coords) < 2:
        return 1.0
    lons = [float(c[0]) for c in coords]
    lats = [float(c[1]) for c in coords]
    d = float(abs(GEOD.line_length(lons, lats)))
    return max(d, 0.5)


def select_base_place_and_junction(
    places: list[PlaceNode],
    junctions: dict[str, Junction],
    segments: dict[str, SegmentEdge],
    base_place_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Deterministically choose the staging base place and junction."""
    if base_place_id:
        for p in places:
            if p.place_id == base_place_id and p.junction_id:
                return p.place_id, p.junction_id
        if base_place_id in junctions:
            return None, base_place_id

    keywords = ("base", "staging", "entry", "gateway", "control")
    for p in places:
        text = f"{p.place_id} {p.name or ''}".lower()
        if any(k in text for k in keywords) and p.junction_id:
            return p.place_id, p.junction_id

    for p in places:
        if p.kind in ("hospital", "shelter", "other_facility") and p.junction_id:
            return p.place_id, p.junction_id

    for p in places:
        if p.junction_id:
            return p.place_id, p.junction_id

    if junctions:
        # Fallback when places.geojson is empty: highest-degree junction, alphabetical tie-break.
        deg: dict[str, int] = {jid: 0 for jid in junctions}
        for seg in segments.values():
            deg[seg.u] += 1
            deg[seg.v] += 1
        best_j = sorted(junctions.keys(), key=lambda j: (-deg[j], j))[0]
        return None, best_j

    return None, None


def build_topology(
    segments_geojson: dict[str, Any],
    places_geojson: dict[str, Any],
    advisor_state: dict[str, Any],
    base_place_id: str | None = None,
    snap_m: float = 3.0,
) -> Topology:
    """Construct a deterministic Junction-Segment-Place topology in WGS84 geodesic space."""
    state_by_seg = {str(s["segment_id"]): s for s in advisor_state.get("segments", [])}
    is_mock = bool(
        segments_geojson.get("mock")
        or places_geojson.get("mock")
        or advisor_state.get("mock")
    )

    junctions: dict[str, Junction] = {}
    junction_list: list[Junction] = []
    grid_index: dict[tuple[int, int], list[Junction]] = {}
    # ~11 m grid cell size in degrees (~0.0001 deg), safe for snap_m <= 10 m
    cell_deg = max(snap_m / 50000.0, 0.0001)

    def _cell_key(lon: float, lat: float) -> tuple[int, int]:
        return (int(lon // cell_deg), int(lat // cell_deg))

    def snap_or_create(lon: float, lat: float) -> str:
        gx, gy = _cell_key(lon, lat)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid_index.get((gx + dx, gy + dy), ()):
                    if _dist_m(lon, lat, j.lon, j.lat) <= snap_m:
                        return j.junction_id
        jid = f"junc_{len(junction_list) + 1:04d}"
        j_obj = Junction(junction_id=jid, lon=lon, lat=lat)
        junctions[jid] = j_obj
        junction_list.append(j_obj)
        grid_index.setdefault((gx, gy), []).append(j_obj)
        return jid

    raw_features = sorted(
        segments_geojson.get("features", []),
        key=lambda f: str(f.get("properties", {}).get("segment_id", "")),
    )

    segments: dict[str, SegmentEdge] = {}
    for feat in raw_features:
        props = feat.get("properties", {})
        if props.get("mock") is True:
            is_mock = True
        sid = str(props["segment_id"])
        coords = feat["geometry"]["coordinates"]
        u = snap_or_create(float(coords[0][0]), float(coords[0][1]))
        v = snap_or_create(float(coords[-1][0]), float(coords[-1][1]))
        raw_len = props.get("length_m")
        length_m = float(raw_len) if raw_len is not None and float(raw_len) > 0 else _line_length_m(coords)
        raw_vol = props.get("debris_volume_m3")
        debris_vol = float(raw_vol) if raw_vol is not None else None

        st_entry = state_by_seg.get(sid)
        if st_entry is not None:
            status_by_mode = dict(st_entry["status_by_mode"])
            reasons_by_mode = {m: list(st_entry["reasons_by_mode"][m]) for m in MODES}
            source = str(st_entry["source"])
            needs_ver = bool(st_entry["needs_verification"])
        else:
            status_by_mode = {m: "unknown" for m in MODES}
            reasons_by_mode = {m: ["missing assessment -> unknown"] for m in MODES}
            source = "geometry"
            needs_ver = True

        segments[sid] = SegmentEdge(
            segment_id=sid,
            u=u,
            v=v,
            length_m=length_m,
            debris_volume_m3=debris_vol,
            status_by_mode=status_by_mode,
            reasons_by_mode=reasons_by_mode,
            source=source,
            needs_verification=needs_ver,
        )

    places: list[PlaceNode] = []
    for feat in places_geojson.get("features", []):
        props = feat.get("properties", {})
        if props.get("mock") is True:
            is_mock = True
        coords = feat["geometry"]["coordinates"]
        plon, plat = float(coords[0]), float(coords[1])
        nsid = props.get("nearest_segment_id")
        attached_junc: str | None = None
        if nsid and str(nsid) in segments:
            seg = segments[str(nsid)]
            ju, jv = junctions[seg.u], junctions[seg.v]
            du = _dist_m(plon, plat, ju.lon, ju.lat)
            dv = _dist_m(plon, plat, jv.lon, jv.lat)
            attached_junc = seg.u if du <= dv else seg.v
        elif junction_list:
            attached_junc = min(
                junction_list,
                key=lambda j: (_dist_m(plon, plat, j.lon, j.lat), j.junction_id),
            ).junction_id

        pop_raw = props.get("population")
        population = int(pop_raw) if pop_raw is not None else None
        places.append(
            PlaceNode(
                place_id=str(props["place_id"]),
                name=props.get("name"),
                kind=str(props.get("kind", "settlement")),
                population=population,
                population_source=str(props.get("population_source", "PLACEHOLDER")),
                nearest_segment_id=str(nsid) if nsid is not None else None,
                lon=plon,
                lat=plat,
                junction_id=attached_junc,
            )
        )

    bp_id, bj_id = select_base_place_and_junction(places, junctions, segments, base_place_id)
    return Topology(
        mock=is_mock,
        junctions=junctions,
        segments=segments,
        places=places,
        base_place_id=bp_id,
        base_junction_id=bj_id,
    )


def edge_cost_for_status(length_m: float, status: str) -> float | None:
    """Traversal cost in effective metres (partial crawl = 2x length; blocked/unknown = impassable)."""
    if status == "open":
        return max(length_m, 0.5)
    if status == "partial":
        return max(length_m * 2.0, 1.0)
    return None


def _networkx_reachable_junctions(
    topology: Topology,
    mode: str,
    allowed_statuses: set[str],
    extra_open_segment_id: str | None = None,
) -> set[str]:
    if not topology.base_junction_id or topology.base_junction_id not in topology.junctions:
        return set()
    g = nx.Graph()
    for jid in topology.junctions:
        g.add_node(jid)
    for seg in topology.segments.values():
        st = "open" if seg.segment_id == extra_open_segment_id else seg.status_by_mode[mode]
        if st in allowed_statuses:
            weight = seg.length_m if st in ("open", "unknown") else seg.length_m * 2.0
            if g.has_edge(seg.u, seg.v):
                if weight < g[seg.u][seg.v]["weight"]:
                    g[seg.u][seg.v]["weight"] = weight
            else:
                g.add_edge(seg.u, seg.v, weight=weight)
    lengths = nx.single_source_dijkstra_path_length(g, topology.base_junction_id, weight="weight")
    return set(lengths.keys())


def count_alternative_routes(topology: Topology, target_junc: str | None, mode: str) -> int:
    """Count edge-disjoint passable routes from base to target_junc (Menger unit-capacity max flow)."""
    base_junc = topology.base_junction_id
    if not base_junc or not target_junc or base_junc not in topology.junctions or target_junc not in topology.junctions:
        return 0
    if base_junc == target_junc:
        return 1
    dg = nx.DiGraph()
    for jid in topology.junctions:
        dg.add_node(jid)
    for seg in topology.segments.values():
        if seg.status_by_mode[mode] in ("open", "partial") and seg.u != seg.v:
            # Add unit capacity in both directions, accumulating parallel segments.
            for a, b in ((seg.u, seg.v), (seg.v, seg.u)):
                if dg.has_edge(a, b):
                    dg[a][b]["capacity"] += 1
                else:
                    dg.add_edge(a, b, capacity=1)
    flow_val, _ = nx.maximum_flow(dg, base_junc, target_junc, capacity="capacity")
    return int(flow_val)


def assemble_access_report(
    topology: Topology,
    reachability_fn: Callable[[str, set[str], str | None], set[str]],
    computed_with: str,
) -> dict[str, Any]:
    """Build a schema-compliant access_report.json using the supplied reachability backend."""
    passable_by_mode: dict[str, set[str]] = {}
    optimistic_by_mode: dict[str, set[str]] = {}
    for mode in MODES:
        passable_by_mode[mode] = reachability_fn(mode, {"open", "partial"}, None)
        optimistic_by_mode[mode] = reachability_fn(mode, {"open", "partial", "unknown"}, None)

    places_out: list[dict[str, Any]] = []
    isolated_by_mode: dict[str, list[str]] = {m: [] for m in MODES}

    for p in topology.places:
        reach_map: dict[str, bool | None] = {}
        alt_map: dict[str, int] = {}
        for mode in MODES:
            if p.junction_id is None or topology.base_junction_id is None:
                reach_map[mode] = None
                alt_map[mode] = 0
            elif p.junction_id in passable_by_mode[mode]:
                reach_map[mode] = True
                alt_map[mode] = count_alternative_routes(topology, p.junction_id, mode)
            elif p.junction_id in optimistic_by_mode[mode]:
                # Only reachable through unknown segments -> unknown (null), never open or blocked.
                reach_map[mode] = None
                alt_map[mode] = 0
            else:
                reach_map[mode] = False
                alt_map[mode] = 0
                isolated_by_mode[mode].append(p.place_id)

        places_out.append(
            {
                "place_id": p.place_id,
                "name": p.name,
                "population": p.population,
                "population_source": p.population_source,
                "reachable": reach_map,
                "facility": p.facility,
                "alternative_routes": alt_map,
            }
        )

    # T5 Reopen plan: rank blocked segments by people and places reconnected per vehicle if cleared.
    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for mode in MODES:
        reached_before = passable_by_mode[mode]
        for seg in sorted(topology.segments.values(), key=lambda s: s.segment_id):
            if seg.status_by_mode[mode] != "blocked":
                continue
            # Frontier filter: clearing a single blocked edge (u, v) can newly reach
            # isolated junctions iff exactly one endpoint is already reachable from base.
            if (seg.u in reached_before) == (seg.v in reached_before):
                continue
            reached_after = reachability_fn(mode, {"open", "partial"}, seg.segment_id)
            newly_reached_places = [
                p
                for p in topology.places
                if p.junction_id is not None
                and p.junction_id not in reached_before
                and p.junction_id in reached_after
            ]
            if not newly_reached_places:
                continue

            reconnects_places = len(newly_reached_places)
            known_pops = [p.population for p in newly_reached_places if p.population is not None]
            unknown_settlements = [
                p for p in newly_reached_places if p.kind == "settlement" and p.population is None
            ]

            # Hard Rule 2: Missing population is unknown (null), never 0.
            if known_pops and not unknown_settlements:
                reconnects_people: int | None = int(sum(known_pops))
            else:
                reconnects_people = None

            place_labels = ", ".join(p.name or p.place_id for p in newly_reached_places)
            reasons = [
                f"Clearing {seg.segment_id} reconnects {reconnects_places} place(s) ({place_labels}) for {mode}"
            ]
            if reconnects_people is not None:
                reasons.append(f"Reconnected known population: {reconnects_people}")
            elif known_pops and unknown_settlements:
                reasons.append(
                    f"Known population reconnected >= {sum(known_pops)}, plus "
                    f"{len(unknown_settlements)} settlement(s) with unknown population (reported as null)"
                )
            else:
                reasons.append("Population of reconnected place(s) is unknown (null, never assumed 0)")

            if seg.debris_volume_m3 is not None:
                reasons.append(f"Estimated debris volume to clear: {seg.debris_volume_m3:.1f} m3")

            sort_key = (
                -(reconnects_people if reconnects_people is not None else -1),
                -reconnects_places,
                MODE_PRIORITY_ORDER[mode],
                seg.debris_volume_m3 if seg.debris_volume_m3 is not None else float("inf"),
                seg.segment_id,
            )
            candidates.append(
                (
                    sort_key,
                    {
                        "segment_id": seg.segment_id,
                        "mode": mode,
                        "reconnects_people": reconnects_people,
                        "reconnects_places": reconnects_places,
                        "debris_volume_m3": seg.debris_volume_m3,
                        "reasons": reasons,
                    },
                )
            )

    candidates.sort(key=lambda item: item[0])
    reopen_plan: list[dict[str, Any]] = []
    for idx, (_, entry) in enumerate(candidates, start=1):
        reopen_plan.append({"rank": idx, **entry})

    return {
        "mock": topology.mock,
        "modes": list(MODES),
        "base_place_id": topology.base_place_id,
        "isolated_places_by_mode": isolated_by_mode,
        "places": places_out,
        "reopen_plan": reopen_plan,
        "computed_with": computed_with,
    }


def compute_access_report_networkx(topology: Topology) -> dict[str, Any]:
    """Compute access_report.json using pure NetworkX fallback."""
    return assemble_access_report(
        topology=topology,
        reachability_fn=lambda mode, statuses, extra_seg: _networkx_reachable_junctions(
            topology, mode, statuses, extra_seg
        ),
        computed_with="networkx-fallback",
    )
