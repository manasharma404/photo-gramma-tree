"""Download OpenStreetMap roads and places around the USGS South Fork site (run while ONLINE).

    python scripts/prefetch_osm_southfork.py

Writes data/prefetch/osm_southfork.gpkg with layers `roads` (highway=*) and
`places` (place=*, amenity / tourism points useful as destinations).
OSM data is ODbL: credit "© OpenStreetMap contributors" wherever it is shown.
The pipeline and API never call the internet; they read this file.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import osmnx as ox

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "prefetch" / "osm_southfork.gpkg"
# west, south, east, north: the mapped area plus ~1 km, so the road network reaches beyond the map
BBOX = (-118.785, 36.335, -118.745, 36.360)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    roads = ox.features_from_bbox(BBOX, tags={"highway": True})
    roads = roads[roads.geometry.geom_type.isin(["LineString", "MultiLineString"])].reset_index()
    places = ox.features_from_bbox(BBOX, tags={"place": True, "amenity": True, "tourism": ["camp_site", "picnic_site"]})
    places = places.reset_index()
    places["geometry"] = places.geometry.representative_point()

    keep_r = [c for c in ("osmid", "id", "highway", "name", "width", "surface", "tracktype", "access", "geometry")
              if c in roads.columns]
    keep_p = [c for c in ("osmid", "id", "place", "amenity", "tourism", "name", "geometry") if c in places.columns]
    roads[keep_r].to_file(OUT, layer="roads", driver="GPKG")
    places[keep_p].to_file(OUT, layer="places", driver="GPKG")
    meta = {"source": "OpenStreetMap via Overpass (osmnx)", "licence": "ODbL 1.0, © OpenStreetMap contributors",
            "bbox_wsen": BBOX, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "roads": len(roads), "places": len(places)}
    OUT.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print(roads[[c for c in ("highway", "name") if c in roads.columns]].value_counts().head(20))
    print(places[[c for c in ("place", "amenity", "tourism", "name") if c in places.columns]].head(20))


if __name__ == "__main__":
    main()
