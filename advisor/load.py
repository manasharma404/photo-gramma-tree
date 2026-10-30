"""Load road segments and places for a project into Neo4j (T4).

Usage:
    python -m advisor.load --project <p>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from neo4j import Driver

from advisor import MODES
from advisor.assess import assess_collection, load_vehicle_config
from advisor.graph import Topology, build_topology
from advisor.neo4j_client import open_driver, project_paths


def load_topology_to_neo4j(topology: Topology, project: str, driver: Driver) -> dict[str, int]:
    """Idempotently replace all Junction, Place, and ROAD_SEGMENT entities for `project`."""
    driver.execute_query(
        "MATCH (n {project: $project}) DETACH DELETE n",
        project=project,
    )

    junc_rows = [
        {"junction_id": j.junction_id, "lon": j.lon, "lat": j.lat}
        for j in sorted(topology.junctions.values(), key=lambda x: x.junction_id)
    ]
    if junc_rows:
        driver.execute_query(
            """
            UNWIND $rows AS row
            CREATE (:Junction {
              project: $project,
              junction_id: row.junction_id,
              lon: row.lon,
              lat: row.lat
            })
            """,
            project=project,
            rows=junc_rows,
        )

    seg_rows: list[dict[str, Any]] = []
    for seg in sorted(topology.segments.values(), key=lambda x: x.segment_id):
        row: dict[str, Any] = {
            "segment_id": seg.segment_id,
            "u": seg.u,
            "v": seg.v,
            "length_m": float(seg.length_m),
            "debris_volume_m3": seg.debris_volume_m3,
            "source": seg.source,
            "needs_verification": seg.needs_verification,
        }
        for m in MODES:
            row[f"status_{m}"] = seg.status_by_mode[m]
        seg_rows.append(row)

    if seg_rows:
        # Undirected roads are represented as symmetric directed relationships for GDS Dijkstra.
        driver.execute_query(
            """
            UNWIND $rows AS row
            MATCH (u:Junction {project: $project, junction_id: row.u})
            MATCH (v:Junction {project: $project, junction_id: row.v})
            CREATE (u)-[:ROAD_SEGMENT {
              project: $project,
              segment_id: row.segment_id,
              length_m: row.length_m,
              debris_volume_m3: row.debris_volume_m3,
              source: row.source,
              needs_verification: row.needs_verification,
              status_fire_truck: row.status_fire_truck,
              status_ambulance: row.status_ambulance,
              status_jeep: row.status_jeep,
              status_foot: row.status_foot
            }]->(v)
            CREATE (v)-[:ROAD_SEGMENT {
              project: $project,
              segment_id: row.segment_id,
              length_m: row.length_m,
              debris_volume_m3: row.debris_volume_m3,
              source: row.source,
              needs_verification: row.needs_verification,
              status_fire_truck: row.status_fire_truck,
              status_ambulance: row.status_ambulance,
              status_jeep: row.status_jeep,
              status_foot: row.status_foot
            }]->(u)
            """,
            project=project,
            rows=seg_rows,
        )

    place_rows = [
        {
            "place_id": p.place_id,
            "name": p.name,
            "kind": p.kind,
            "population": p.population,
            "population_source": p.population_source,
            "nearest_segment_id": p.nearest_segment_id,
            "lon": p.lon,
            "lat": p.lat,
            "junction_id": p.junction_id,
        }
        for p in topology.places
    ]
    if place_rows:
        driver.execute_query(
            """
            UNWIND $rows AS row
            CREATE (p:Place {
              project: $project,
              place_id: row.place_id,
              name: row.name,
              kind: row.kind,
              population: row.population,
              population_source: row.population_source,
              nearest_segment_id: row.nearest_segment_id,
              lon: row.lon,
              lat: row.lat,
              junction_id: row.junction_id
            })
            WITH p, row
            OPTIONAL MATCH (j:Junction {project: $project, junction_id: row.junction_id})
            FOREACH (_ IN CASE WHEN j IS NOT NULL THEN [1] ELSE [] END |
              CREATE (p)-[:AT_JUNCTION {project: $project}]->(j)
            )
            """,
            project=project,
            rows=place_rows,
        )

    return {
        "junctions": len(junc_rows),
        "segments": len(seg_rows),
        "places": len(place_rows),
    }


def load_project(
    project: str,
    data_root: Path | None = None,
    base_place_id: str | None = None,
    field_reports: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Load a project's segments + places from disk into Neo4j."""
    paths = project_paths(project, data_root=data_root)
    seg_fc = json.loads(paths["segments"].read_text(encoding="utf-8"))
    places_fc = json.loads(paths["places"].read_text(encoding="utf-8"))
    ml_data = (
        json.loads(paths["ml_scores"].read_text(encoding="utf-8"))
        if paths["ml_scores"].exists()
        else None
    )
    cfg = load_vehicle_config()
    state = assess_collection(seg_fc, config=cfg, ml_scores=ml_data, field_reports=field_reports)
    topo = build_topology(seg_fc, places_fc, state, base_place_id=base_place_id)

    driver = open_driver()
    if driver is None:
        raise RuntimeError(
            "Neo4j with GDS is not reachable. Start neo4j/docker-compose.yml and configure .env."
        )
    try:
        return load_topology_to_neo4j(topo, project=project, driver=driver)
    finally:
        driver.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="Project name under data/projects/<p> (or 'mock')")
    ap.add_argument("--base", default=None, help="Optional base place_id")
    args = ap.parse_args()

    counts = load_project(args.project, base_place_id=args.base)
    print(f"loaded project '{args.project}' into Neo4j: {counts}")


if __name__ == "__main__":
    main()
