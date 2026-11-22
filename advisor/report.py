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
    compute_fly_next,
)
from advisor.load import load_topology_to_neo4j
from advisor.neo4j_client import open_driver, project_paths


def _neo4j_cypher_reachable_junctions(
    driver: Driver,
    project: str,
    base_junction_id: str | None,
    mode: str,
    allowed_statuses: set[str],
    extra_open_segment_id: str | None = None,
    excluded_segment_id: str | None = None,
) -> set[str]:
    """Plain-Cypher multi-vehicle reachability solver without GDS plugin (AuraDB Free ready)."""
    if not base_junction_id:
        return set()
    status_prop = f"status_{mode}"
    extra_seg = extra_open_segment_id or "__NONE__"
    excl_seg = excluded_segment_id or "__NONE__"
    statuses_list = sorted(allowed_statuses)

    query = """
    MATCH (src:Junction {project: $project, junction_id: $base_junc})
    MATCH (dst:Junction {project: $project})
    WHERE src <> dst
    MATCH p = shortestPath((src)-[:ROAD_SEGMENT*..50]->(dst))
    WHERE ALL(r IN relationships(p) WHERE r.segment_id <> $excl_seg AND (r.segment_id = $extra_seg OR r[$status_prop] IN $allowed_statuses))
    RETURN DISTINCT dst.junction_id AS junction_id
    """
    res = driver.execute_query(
        query,
        project=project,
        base_junc=base_junction_id,
        extra_seg=extra_seg,
        excl_seg=excl_seg,
        status_prop=status_prop,
        allowed_statuses=statuses_list,
    )
    reached = {str(rec["junction_id"]) for rec in res.records}
    reached.add(base_junction_id)
    return reached


def run_cypher_reach_query(
    driver: Driver,
    project: str,
    base_junction_id: str,
    mode: str = "ambulance",
) -> list[str]:
    """Plain Cypher Query 1: Vehicle reachability from staging base."""
    status_prop = f"status_{mode}"
    query = """
    MATCH (src:Junction {project: $project, junction_id: $base_junc})
    MATCH (dst:Junction {project: $project})
    WHERE src <> dst
    MATCH p = shortestPath((src)-[:ROAD_SEGMENT*..50]->(dst))
    WHERE ALL(r IN relationships(p) WHERE r[$status_prop] IN ['open', 'partial'])
    RETURN DISTINCT dst.junction_id AS junction_id
    ORDER BY junction_id
    """
    res = driver.execute_query(query, project=project, base_junc=base_junction_id, status_prop=status_prop)
    return [base_junction_id] + [str(r["junction_id"]) for r in res.records]


def run_cypher_clear_first_query(
    driver: Driver,
    project: str,
    mode: str = "ambulance",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Plain Cypher Query 2: Clear First (which single blockage reconnects the most people)."""
    status_prop = f"status_{mode}"
    query = """
    MATCH (target:Place {project: $project})
    WHERE target.population IS NOT NULL AND target.population > 0
    MATCH (b:Place {project: $project})
    WHERE b.kind IN ['hospital', 'shelter'] OR b.name CONTAINS 'Base' OR b.place_id CONTAINS 'BASE'
    MATCH p = (b)-[:AT_JUNCTION]->(:Junction)-[:ROAD_SEGMENT*1..10]-(dest:Junction)<-[:AT_JUNCTION]-(target)
    UNWIND relationships(p) AS rel
    WITH rel.segment_id AS seg_to_clear, target, p, rel
    WHERE rel[$status_prop] = 'blocked'
    WITH seg_to_clear, target, p
    WHERE single(r IN relationships(p) WHERE r[$status_prop] = 'blocked' AND r.segment_id = seg_to_clear)
      AND ALL(r IN relationships(p) WHERE r.segment_id = seg_to_clear OR r[$status_prop] IN ['open', 'partial'])
    RETURN seg_to_clear AS segment_id,
           count(DISTINCT target) AS reconnects_places,
           sum(target.population) AS reconnects_people,
           collect(DISTINCT coalesce(target.name, target.place_id)) AS reconnected_settlements
    ORDER BY reconnects_people DESC, reconnects_places DESC
    LIMIT $limit
    """
    try:
        res = driver.execute_query(query, project=project, status_prop=status_prop, limit=limit)
        return [
            {
                "segment_id": r["segment_id"],
                "reconnects_places": int(r["reconnects_places"]),
                "reconnects_people": int(r["reconnects_people"]),
                "reconnected_settlements": list(r["reconnected_settlements"]),
            }
            for r in res.records
        ]
    except Exception:
        return []


def run_cypher_fly_next_query(
    driver: Driver,
    project: str,
    base_place_id: str | None = None,
    mode: str = "ambulance",
    limit: int = 5,
    w: float = 0.50,
    ml_scores: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Plain Cypher Query 3: Fly Next (which unknown road settles route for most people + uncertainty)."""
    status_prop = f"status_{mode}"
    query = """
    MATCH (target:Place {project: $project})
    WHERE target.population IS NOT NULL AND target.population > 0
    MATCH (b:Place {project: $project})
    WHERE ($base_place_id IS NOT NULL AND b.place_id = $base_place_id)
       OR b.kind IN ['hospital', 'shelter'] OR b.name CONTAINS 'Base' OR b.place_id CONTAINS 'BASE'
    MATCH path = (b)-[:AT_JUNCTION]->(:Junction)-[:ROAD_SEGMENT*1..10]-(:Junction)<-[:AT_JUNCTION]-(target)
    WHERE ANY(r IN relationships(path) WHERE r[$status_prop] = 'unknown')
      AND NONE(r IN relationships(path) WHERE r[$status_prop] = 'blocked')
    UNWIND relationships(path) AS rel
    WITH rel.segment_id AS unknown_segment, target
    WHERE rel[$status_prop] = 'unknown'
    RETURN unknown_segment AS segment_id,
           count(DISTINCT target) AS impacted_settlements,
           sum(target.population) AS impacted_population
    ORDER BY impacted_population DESC
    LIMIT $limit
    """
    ml_by_id = {}
    if isinstance(ml_scores, dict):
        for item in ml_scores.get("scores", []):
            if "segment_id" in item:
                ml_by_id[str(item["segment_id"])] = item

    try:
        res = driver.execute_query(
            query,
            project=project,
            base_place_id=base_place_id,
            status_prop=status_prop,
            limit=limit * 2,
        )
        scored = []
        for r in res.records:
            sid = str(r["segment_id"])
            pop = int(r["impacted_population"])
            ml_item = ml_by_id.get(sid)
            p_blk = ml_item.get("p_blocked") if ml_item else None
            unc = round(1.0 - abs(2.0 * float(p_blk) - 1.0), 4) if p_blk is not None else 0.0
            score = round(float(pop) * (1.0 + float(w) * unc), 2)
            scored.append({
                "segment_id": sid,
                "score": score,
                "impacted_population": pop,
                "impacted_settlements": int(r["impacted_settlements"]),
                "uncertainty": unc,
                "p_blocked": float(p_blk) if p_blk is not None else None,
            })
        scored.sort(key=lambda x: (-x["score"], -x["impacted_population"], x["segment_id"]))
        for idx, item in enumerate(scored[:limit], start=1):
            item["rank"] = idx
        return scored[:limit]
    except Exception:
        return []


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
    use_cypher: bool = False,
    ml_scores: dict[str, Any] | None = None,
    w: float = 0.50,
) -> dict[str, Any]:
    """Compute access_report.json using Neo4j Graph Data Science or Plain-Cypher fallback (AuraDB ready)."""
    if sync_first:
        load_topology_to_neo4j(topology, project=project, driver=driver)

    def _reach(mode: str, statuses: set[str], extra_seg: str | None = None, excl_seg: str | None = None) -> set[str]:
        if not use_cypher and not excl_seg:
            try:
                # GDS Dijkstra
                return _neo4j_gds_reachable_junctions(
                    driver=driver,
                    project=project,
                    base_junction_id=topology.base_junction_id,
                    mode=mode,
                    allowed_statuses=statuses,
                    extra_open_segment_id=extra_seg,
                )
            except Exception:
                # GDS procedure unavailable or failed -> fallback to Plain Cypher
                pass
        return _neo4j_cypher_reachable_junctions(
            driver=driver,
            project=project,
            base_junction_id=topology.base_junction_id,
            mode=mode,
            allowed_statuses=statuses,
            extra_open_segment_id=extra_seg,
            excluded_segment_id=excl_seg,
        )

    rep = assemble_access_report(
        topology=topology,
        reachability_fn=lambda m, s, extra=None: _reach(m, s, extra_seg=extra),
        computed_with="neo4j-gds",
    )
    rep["fly_next"] = compute_fly_next(
        topology=topology,
        reachability_fn=_reach,
        ml_scores=ml_scores,
        w=w,
    )
    return rep


def compute_access_report(
    segments_geojson: dict[str, Any],
    places_geojson: dict[str, Any],
    advisor_state: dict[str, Any] | None = None,
    project: str = "default",
    base_place_id: str | None = None,
    backend: str = "auto",
    field_reports: list[dict[str, Any]] | None = None,
    ml_scores: dict[str, Any] | None = None,
    w: float = 0.50,
) -> dict[str, Any]:
    """Compute access_report.json using Neo4j (GDS or Cypher) if reachable, else NetworkX fallback."""
    state = advisor_state or assess_collection(segments_geojson, ml_scores=ml_scores, field_reports=field_reports)
    topo = build_topology(segments_geojson, places_geojson, state, base_place_id=base_place_id)

    if backend in ("auto", "neo4j", "cypher"):
        driver = open_driver()
        if driver is not None:
            try:
                use_cypher = (backend == "cypher")
                return compute_access_report_neo4j(
                    topo,
                    project=project,
                    driver=driver,
                    sync_first=True,
                    use_cypher=use_cypher,
                    ml_scores=ml_scores,
                    w=w,
                )
            finally:
                driver.close()
        if backend in ("neo4j", "cypher"):
            raise RuntimeError(f"Requested --backend {backend}, but Neo4j is unreachable.")

    return compute_access_report_networkx(topo, ml_scores=ml_scores, w=w)


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
        ml_scores=ml_data,
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
