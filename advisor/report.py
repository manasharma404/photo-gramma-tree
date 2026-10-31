"""Compute multi-vehicle reachability and T5 reopen plan via Neo4j GDS or NetworkX fallback.

Usage:
    python -m advisor.report --project <p> --out access_report.json
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from neo4j import Driver

from advisor.assess import assess_collection, load_vehicle_config
from advisor.graph import (
    Topology,
    assemble_access_report,
    build_topology,
    compute_access_report_networkx,
)
from advisor.load import load_topology_to_neo4j
from advisor.neo4j_client import open_driver, project_paths


def _neo4j_gds_reachable_junctions(
    driver: Driver,
    project: str,
    base_junction_id: str | None,
    mode: str,
    allowed_statuses: set[str],
    extra_open_segment_id: str | None = None,
) -> set[str]:
    if not base_junction_id:
        return set()
    graph_name = f"vortex_{project}_{mode}_{uuid.uuid4().hex[:8]}"
    status_prop = f"status_{mode}"
    extra_seg = extra_open_segment_id or "__NONE__"
    statuses_list = sorted(allowed_statuses)

    try:
        proj_res = driver.execute_query(
            """
            MATCH (source:Junction {project: $project})
            OPTIONAL MATCH (source)-[r:ROAD_SEGMENT {project: $project}]->(target:Junction {project: $project})
            WHERE r.segment_id = $extra_seg OR r[$status_prop] IN $allowed_statuses
            WITH gds.graph.project(
              $graph_name,
              source,
              target,
              {
                relationshipProperties: {
                  weight: CASE
                    WHEN r IS NULL THEN null
                    WHEN r.segment_id = $extra_seg OR r[$status_prop] IN ['open', 'unknown'] THEN r.length_m
                    ELSE r.length_m * 2.0
                  END
                }
              }
            ) AS g
            RETURN g.nodeCount AS nodeCount
            """,
            project=project,
            extra_seg=extra_seg,
            status_prop=status_prop,
            allowed_statuses=statuses_list,
            graph_name=graph_name,
        )
        if not proj_res.records or proj_res.records[0]["nodeCount"] == 0:
            return set()

        dijkstra_res = driver.execute_query(
            """
            MATCH (src:Junction {project: $project, junction_id: $base_junc})
            CALL gds.allShortestPaths.dijkstra.stream($graph_name, {
              sourceNode: src,
              relationshipWeightProperty: 'weight'
            })
            YIELD targetNode
            RETURN gds.util.asNode(targetNode).junction_id AS junction_id
            """,
            project=project,
            base_junc=base_junction_id,
            graph_name=graph_name,
        )
        return {str(rec["junction_id"]) for rec in dijkstra_res.records}
    finally:
        driver.execute_query(
            "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
            graph_name=graph_name,
        )


def compute_access_report_neo4j(
    topology: Topology,
    project: str,
    driver: Driver,
    sync_first: bool = True,
) -> dict[str, Any]:
    """Compute access_report.json using Neo4j Graph Data Science (neo4j-gds)."""
    if sync_first:
        load_topology_to_neo4j(topology, project=project, driver=driver)

    return assemble_access_report(
        topology=topology,
        reachability_fn=lambda mode, statuses, extra_seg: _neo4j_gds_reachable_junctions(
            driver=driver,
            project=project,
            base_junction_id=topology.base_junction_id,
            mode=mode,
            allowed_statuses=statuses,
            extra_open_segment_id=extra_seg,
        ),
        computed_with="neo4j-gds",
    )


def compute_access_report(
    segments_geojson: dict[str, Any],
    places_geojson: dict[str, Any],
    advisor_state: dict[str, Any] | None = None,
    project: str = "default",
    base_place_id: str | None = None,
    backend: str = "auto",
    field_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute access_report.json using Neo4j GDS if reachable, else NetworkX fallback."""
    state = advisor_state or assess_collection(segments_geojson, field_reports=field_reports)
    topo = build_topology(segments_geojson, places_geojson, state, base_place_id=base_place_id)

    if backend in ("auto", "neo4j"):
        driver = open_driver()
        if driver is not None:
            try:
                return compute_access_report_neo4j(topo, project=project, driver=driver, sync_first=True)
            finally:
                driver.close()
        if backend == "neo4j":
            raise RuntimeError("Requested --backend neo4j, but Neo4j GDS is unreachable.")

    return compute_access_report_networkx(topo)


def generate_project_report(
    project: str,
    out_path: Path | None = None,
    base_place_id: str | None = None,
    backend: str = "auto",
    data_root: Path | None = None,
    field_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Load project inputs, compute access_report, optionally write to disk, and return it."""
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
    report = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project=project,
        base_place_id=base_place_id,
        backend=backend,
    )
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="Project name under data/projects/<p> (or 'mock')")
    ap.add_argument("--out", type=Path, required=True, help="Output access_report.json path")
    ap.add_argument("--base", default=None, help="Optional base place_id")
    ap.add_argument("--backend", choices=("auto", "neo4j", "networkx"), default="auto")
    args = ap.parse_args()

    rep = generate_project_report(
        project=args.project,
        out_path=args.out,
        base_place_id=args.base,
        backend=args.backend,
    )
    print(
        f"wrote {args.out} via {rep['computed_with']} "
        f"({len(rep['places'])} places, {len(rep['reopen_plan'])} reopen candidates)"
    )


if __name__ == "__main__":
    main()
