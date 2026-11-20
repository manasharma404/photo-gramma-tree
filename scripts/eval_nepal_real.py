import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json
import time
from advisor.assess import assess_collection
from advisor.report import compute_access_report
from advisor.priorities import compute_priorities

nepal_dir = ROOT / "data" / "projects" / "nepal"
seg_fc = json.loads((nepal_dir / "roads" / "segments.geojson").read_text(encoding="utf-8"))
places_fc = json.loads((nepal_dir / "places.geojson").read_text(encoding="utf-8"))

print(f"Assessing real Nepal network: {len(seg_fc['features']):,} segments, {len(places_fc['features']):,} places...")
t0 = time.time()
state = assess_collection(seg_fc)
print(f"State assessed in {time.time()-t0:.2f}s")

print("Computing access report (Clear First)...")
t0 = time.time()
rep = compute_access_report(
    segments_geojson=seg_fc,
    places_geojson=places_fc,
    advisor_state=state,
    project="nepal",
    backend="networkx",
)
print(f"Access report computed in {time.time()-t0:.2f}s")

print("\n--- TOP REOPEN PLAN (CLEAR FIRST) ---")
reopen_plan = rep.get("reopen_plan", [])
print(f"Total reopen plan items: {len(reopen_plan)}")
for item in reopen_plan[:5]:
    seg_id = item.get("segment_id")
    # Lookup segment details
    feat = next((f for f in seg_fc["features"] if f["properties"]["segment_id"] == seg_id), None)
    osm_id = feat["properties"].get("osm_way_id") if feat else None
    highway = feat["properties"].get("highway") if feat else None
    print(f"Rank {item['rank']}: Segment {seg_id} (OSM way {osm_id}, {highway}, mode: {item.get('mode')})")
    print(f"   Reconnects people: {item.get('reconnects_people')}")
    print(f"   Reconnects places: {item.get('reconnects_places')}")
    print(f"   Reasons: {item.get('reasons')}")

print("\n--- TOP PRIORITIES (FLY NEXT) ---")
t0 = time.time()
prio = compute_priorities(places_fc, state, rep)
print(f"Priorities computed in {time.time()-t0:.2f}s")
for idx, item in enumerate(prio.get("priority_list", [])[:5], start=1):
    print(f"Priority {idx}: Place {item.get('place_id')} ({item.get('name')}, {item.get('kind')})")
    print(f"   Population: {item.get('population')}, Severity score: {item.get('priority_score')}")
    print(f"   Access status: fire_truck={item.get('status_by_mode', {}).get('fire_truck')}, ambulance={item.get('status_by_mode', {}).get('ambulance')}")
