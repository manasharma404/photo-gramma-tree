"""Build the map's DEMO scenario: a real road network (OpenStreetMap) with SIMULATED damage and people on it.

Why: our own drone data has no landslide with broken roads, so the map cannot show what Typhon decides. This
scenario lays simulated trouble on real roads so the full loop can be shown, and every part of it says so.

    uv run python scripts/build_demo_scenario.py --base wayanad          # the default base (OSM roads + places)
    uv run python scripts/build_demo_scenario.py --base southfork_f01_4  # stand-in when Wayanad is not on this laptop

Writes data/projects/demo/ (roads/segments.geojson, places.geojson, roads/places.geojson, demo.json).
What is simulated (and labelled so in every file and on screen):
  - four kinds of blockage, each letting different vehicles through: debris across the road (nobody), a road
    narrowed by debris (jeep and on foot), a damaged bridge (on foot only), water over the road (fire truck only);
  - one patch where the photos were blurred, so its roads are "not seen" (unknown) and a re-fly is offered;
  - people trapped, in different numbers and places (counts are made up for the demo, never real figures).
The roads themselves and named places are real OpenStreetMap data (ODbL). Nothing here is drone-measured.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import networkx as nx
from shapely.geometry import Point, mapping, shape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from advisor import MODES  # noqa: E402
from advisor.graph import build_topology  # noqa: E402

LABEL = "SIMULATED demo scenario on real OpenStreetMap roads: blockages, blurred patch and people are made up"
KINDS = {  # status per vehicle, and what to say
    "debris": {"title": "Debris across the road", "status": {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"},
               "why": "simulated: a landslide covers the road edge to edge; nothing passes until it is cleared"},
    "narrowed": {"title": "Road narrowed by debris", "status": {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "partial", "foot": "open"},
                 "why": "simulated: debris leaves about 2.4 m clear; a jeep squeezes through, trucks and ambulances do not"},
    "bridge": {"title": "Damaged bridge", "status": {"fire_truck": "blocked", "ambulance": "blocked", "jeep": "blocked", "foot": "partial"},
               "why": "simulated: the deck is cracked; people can cross on foot, one at a time; no vehicles"},
    "flood": {"title": "Water over the road", "status": {"fire_truck": "partial", "ambulance": "blocked", "jeep": "blocked", "foot": "blocked"},
              "why": "simulated: about 0.5 m of fast water; only a high-clearance fire truck gets through, slowly"},
}
ORDER = ["debris", "narrowed", "bridge", "flood"]


def local_m(lon0, lat0):
    k = 111_320.0
    return (lambda lon, lat: ((lon - lon0) * k * math.cos(math.radians(lat0)), (lat - lat0) * k))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="wayanad")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rnd = random.Random(args.seed)
    base_dir = ROOT / "data" / "projects" / args.base
    seg_path = base_dir / "roads" / "segments.geojson"
    place_path = next((p for p in (base_dir / "places.geojson", base_dir / "roads" / "places.geojson") if p.exists()), None)
    if not seg_path.exists() or place_path is None:
        raise SystemExit(f"no roads/places for {args.base} in {base_dir} (run its prefetch script first)")
    segs = json.loads(seg_path.read_text(encoding="utf-8"))
    places = json.loads(place_path.read_text(encoding="utf-8"))
    for f in places["features"]:
        f["properties"].pop("population", None)
    feats = segs["features"]
    all_open = {"segments": [{"segment_id": f["properties"]["segment_id"], "status_by_mode": {m: "open" for m in MODES},
                             "reasons_by_mode": {m: [] for m in MODES}, "source": "scenario", "needs_verification": False} for f in feats]}
    topo = build_topology(segs, places, all_open)
    if not topo.base_junction_id:
        raise SystemExit("no base place on the network")
    G = nx.Graph()
    for s in topo.segments.values():
        G.add_edge(s.u, s.v, sid=s.segment_id)
    comp = nx.node_connected_component(G, topo.base_junction_id)
    H = G.subgraph(comp).copy()
    J = topo.junctions
    lon0, lat0 = J[topo.base_junction_id].lon, J[topo.base_junction_id].lat
    to_m = local_m(lon0, lat0)
    xy = {j: to_m(J[j].lon, J[j].lat) for j in H.nodes}
    ext = max(1.0, max(math.dist(xy[a], xy[topo.base_junction_id]) for a in H.nodes))

    # candidate cut points: bridges whose far side is a decent chunk of the network
    cands = []
    for u, v in nx.bridges(H):
        H.remove_edge(u, v)
        side_u = nx.node_connected_component(H, u)
        H.add_edge(u, v, **G.edges[u, v])
        far = side_u if topo.base_junction_id not in side_u else set(H.nodes) - side_u
        n = len(far)
        if 2 <= n <= 0.45 * H.number_of_nodes():
            mid = ((xy[u][0] + xy[v][0]) / 2, (xy[u][1] + xy[v][1]) / 2)
            cands.append({"edge": (u, v), "sid": G.edges[u, v]["sid"], "far": far, "mid": mid, "n": n})
    cands.sort(key=lambda c: -min(c["n"], 60) + rnd.random() * 6)
    chosen = []
    for min_n, spread, nested in ((4, 0.18, False), (3, 0.1, False), (2, 0.05, False), (2, 0.1, True), (2, 0.0, True)):
        chosen = []  # relax until five fit: disjoint far sides spread over the map; last resort, nested ones
        for c in cands:
            clash = (lambda d: c["far"] == d["far"]) if nested else (lambda d: bool(c["far"] & d["far"]))
            if c["n"] < min_n or any(clash(d) or math.dist(c["mid"], d["mid"]) < spread * ext for d in chosen):
                continue
            chosen.append(c)
            if len(chosen) == 5:
                break
        if len(chosen) == 5:
            break
    print(f"network: {H.number_of_nodes()} junctions in the base's part, {len(cands)} candidate cut points")
    if len(chosen) < 5:
        raise SystemExit(f"only {len(chosen)} usable cut points on this network; try another base")

    by_sid = {f["properties"]["segment_id"]: f for f in feats}
    blockages, people, blur = [], [], []
    # default: what each vehicle can use on an undamaged road, by road class (a simulated rule, stated on screen;
    # vehicle sizes from config/vehicles.yaml): unpaved tracks are too narrow for a fire truck and rough for an
    # ambulance; narrow village roads are slow for a fire truck. Then the designed trouble on top.
    class_rule = {
        "track": ({"fire_truck": "blocked", "ambulance": "partial", "jeep": "open", "foot": "open"},
                  {"fire_truck": "simulated rule: a narrow unpaved track; a fire truck does not fit",
                   "ambulance": "simulated rule: a rough unpaved track; passable slowly, with care"}),
        "unclassified": ({"fire_truck": "partial", "ambulance": "open", "jeep": "open", "foot": "open"},
                         {"fire_truck": "simulated rule: a narrow village road; slow for a fire truck"}),
    }
    for f in feats:
        p = f["properties"]
        st, why = class_rule.get(p.get("highway"), ({m: "open" for m in MODES}, {}))
        p.update({"source": "scenario", "status_by_mode": dict(st), "scenario_label": LABEL,
                  "scenario_reasons_by_mode": {m: [why.get(m, "simulated: no damage reported on this road")] for m in MODES},
                  "measured": False, "mock": True})
    # On a network that is one long chain the cut points are nested (each far side holds the next). Then order
    # them from the base outwards and put people between them: each vehicle gets as far as its roads allow.
    nested = any(a["far"] & b["far"] for i, a in enumerate(chosen) for b in chosen[i + 1:])
    if nested:
        chosen.sort(key=lambda c: -c["n"])
    order = ["narrowed", "bridge", "flood", "debris"] if nested else ORDER
    for kind, c in zip(order, chosen[:4]):
        f = by_sid[c["sid"]]
        k = KINDS[kind]
        f["properties"].update({"status_by_mode": dict(k["status"]), "demo_kind": kind,
                                "scenario_reasons_by_mode": {m: [k["why"]] for m in MODES}})
        if kind == "debris":
            f["properties"]["debris_volume_m3"] = 340.0
        if kind == "narrowed":
            f["properties"]["min_clear_width_m"] = 2.4
            f["properties"]["debris_volume_m3"] = 85.0
        g = shape(f["geometry"])
        pt = g.interpolate(0.5, normalized=True)
        blockages.append({"segment_id": c["sid"], "kind": kind, "title": k["title"], "why": k["why"],
                          "passes": [m for m, s in k["status"].items() if s in ("open", "partial")], "lonlat": [pt.x, pt.y]})
    # the blurred patch: a circle around the fifth cut point; its roads become "not seen"
    c5 = chosen[4]
    u, v = c5["edge"]
    clon, clat = (J[u].lon + J[v].lon) / 2, (J[u].lat + J[v].lat) / 2
    r_m = max(120.0, min(260.0, 0.12 * ext))
    ring = [[clon + (r_m * math.cos(a)) / (111_320 * math.cos(math.radians(clat))), clat + (r_m * math.sin(a)) / 111_320]
            for a in [i * 2 * math.pi / 36 for i in range(37)]]
    zone = shape({"type": "Polygon", "coordinates": [ring]})
    hidden = []
    for f in feats:
        if f["properties"].get("demo_kind"):
            continue
        if shape(f["geometry"]).intersects(zone):
            f["properties"].update({"status_by_mode": {m: "unknown" for m in MODES}, "demo_kind": "blur",
                                    "scenario_reasons_by_mode": {m: ["simulated: the photos of this patch are blurred; road not seen"] for m in MODES}})
            hidden.append(f["properties"]["segment_id"])
    blur.append({"id": "blur-1", "polygon": {"type": "Polygon", "coordinates": [ring]}, "radius_m": round(r_m),
                 "segments": hidden, "why": "simulated: motion blur on the photos of this patch, so its roads were not seen"})

    # people: at real places on each cut-off side, else small stranded groups at road ends there
    names = iter(["Stranded group", "Families on a roof", "Tea-estate workers", "School shelter", "Stranded bus", "Homestay guests"])
    pid = 0
    def add_group(junction, count, name):
        nonlocal pid
        pid += 1
        props = {"place_id": f"demo_people_{pid}", "name": name, "kind": "settlement", "population": count,
                 "population_source": "SIMULATED (demo)", "mock": True}
        places["features"].append({"type": "Feature", "geometry": mapping(Point(J[junction].lon, J[junction].lat)), "properties": props})
        people.append({"place_id": props["place_id"], "name": name, "count": count, "lonlat": [J[junction].lon, J[junction].lat]})
    place_by_j = {}
    for pn in topo.places:
        if pn.junction_id and pn.place_id != topo.base_place_id:
            place_by_j.setdefault(pn.junction_id, []).append(pn)
    regions = ([chosen[i]["far"] - chosen[i + 1]["far"] for i in range(4)] + [chosen[4]["far"]]) if nested else [c["far"] for c in chosen]
    for c, region in zip(chosen, regions):
        if not region:
            continue
        leaves = sorted([j for j in region if H.degree(j) == 1], key=lambda j: -math.dist(xy[j], c["mid"]))
        if not leaves:  # a stretch of the chain with no road ends: use its point farthest from the blockage
            leaves = sorted(region, key=lambda j: -math.dist(xy[j], c["mid"]))[:1]
        # never put made-up counts on a real named village: simulated groups sit on unnamed road points
        for j in leaves[: (1 if nested else 2)]:
            add_group(j, rnd.choice([5, 8, 11, 15, 23, 31]), next(names, "Stranded group"))
    # two groups on the near side, still reachable, for contrast
    near = [j for j in H.nodes if all(j not in c["far"] for c in chosen) and H.degree(j) == 1 and j != topo.base_junction_id]
    near.sort(key=lambda j: -math.dist(xy[j], xy[topo.base_junction_id]))
    for j in near[:2]:
        add_group(j, rnd.choice([9, 14, 20]), next(names, "Stranded group"))

    # real settlements stay out of the demo (no simulated people on real communities; and a village with no
    # population would make the graph report "unknown" people); real facilities and the base stay in
    places["features"] = [f for f in places["features"] if f["properties"].get("mock") or f["properties"].get("kind") != "settlement"
                          or f["properties"].get("place_id") == topo.base_place_id]
    out = ROOT / "data" / "projects" / "demo"
    (out / "roads").mkdir(parents=True, exist_ok=True)
    segs.update({"mock": True, "scenario_label": LABEL})
    places.update({"mock": True, "scenario_label": LABEL})
    (out / "roads" / "segments.geojson").write_text(json.dumps(segs), encoding="utf-8")
    for p in (out / "places.geojson", out / "roads" / "places.geojson"):
        p.write_text(json.dumps(places), encoding="utf-8")
    lons = [J[j].lon for j in H.nodes]; lats = [J[j].lat for j in H.nodes]
    demo = {"mock": True, "label": LABEL, "base": args.base, "base_place_id": topo.base_place_id,
            "bounds_wsen": [min(lons), min(lats), max(lons), max(lats)],
            "blockages": blockages, "blur_zones": blur, "people": people,
            "people_total": sum(p["count"] for p in people),
            "sources": ["Roads and named places: OpenStreetMap contributors (ODbL), from the " + args.base + " data on this laptop",
                        "Everything else on this map is simulated for the demo"]}
    (out / "demo.json").write_text(json.dumps(demo, indent=1), encoding="utf-8")
    print(f"demo scenario on {args.base}: {len(feats)} roads, {len(blockages)} blockages, {len(hidden)} roads in the blurred patch, "
          f"{len(people)} groups of people ({demo['people_total']} simulated) -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
