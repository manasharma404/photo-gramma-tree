"""Project input discovery for Vortex export pipeline (E1-E6)."""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from advisor.assess import assess_collection, load_vehicle_config
from advisor.neo4j_client import project_paths
from advisor.report import compute_access_report
from advisor.store import list_field_reports

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ExportInputs:
    project: str
    project_dir: Path
    segments_fc: dict[str, Any]
    places_fc: dict[str, Any]
    advisor_state: dict[str, Any]
    access_report: dict[str, Any]
    accuracy: dict[str, Any] | None
    confirmed: dict[str, Any] | None
    rtk_rows: dict[str, dict[str, str]]
    measurements: list[tuple[str, dict[str, Any]]]
    run_doc: dict[str, Any] | None
    orthophoto_path: Path | None
    dsm_path: Path | None
    source_files: list[str] = field(default_factory=list)


def _data_root(data_root: Path | None = None) -> Path:
    if data_root is not None:
        return data_root
    env_root = os.environ.get("VORTEX_DATA_ROOT", "").strip()
    return Path(env_root) if env_root else ROOT


def _rel_or_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _first_existing(candidates: list[Path]) -> Path | None:
    for p in candidates:
        if p.is_file():
            return p
    return None


def _resolve_product_path(raw_path: str | None, search_roots: list[Path]) -> Path | None:
    if not raw_path:
        return None
    p = Path(raw_path)
    if p.is_file():
        return p
    for base in search_roots:
        cand = base / raw_path
        if cand.is_file():
            return cand
    return None


def load_export_inputs(
    project: str,
    *,
    data_root: Path | None = None,
    project_dir_override: Path | None = None,
    orthophoto_override: Path | None = None,
    dsm_override: Path | None = None,
    accuracy_override: Path | None = None,
    measurements_dir_override: Path | None = None,
) -> ExportInputs:
    """Resolve and load all contract inputs for a project ('mock' or data/projects/<project>)."""
    root = _data_root(data_root)
    source_files: list[str] = []

    if project_dir_override is not None:
        proj_dir = project_dir_override
        seg_path = _first_existing(
            [
                proj_dir / "roads" / "segments.geojson",
                proj_dir / "segments.geojson",
                proj_dir / "segments.example.geojson",
            ]
        )
        places_path = _first_existing(
            [
                proj_dir / "places.geojson",
                proj_dir / "roads" / "places.geojson",
                proj_dir / "places.example.geojson",
            ]
        )
        ml_path = _first_existing(
            [
                proj_dir / "ml_scores.json",
                proj_dir / "ml_scores.example.json",
            ]
        )
    else:
        resolved = project_paths(project, data_root=root)
        proj_dir = resolved["project_dir"]
        seg_path = resolved["segments"] if resolved["segments"].is_file() else None
        places_path = resolved["places"] if resolved["places"].is_file() else None
        ml_path = resolved["ml_scores"] if resolved["ml_scores"].is_file() else None

    if seg_path is None or not seg_path.is_file():
        raise FileNotFoundError(f"segments.geojson not found for project '{project}' in {proj_dir}")

    segments_fc = json.loads(seg_path.read_text(encoding="utf-8"))
    source_files.append(_rel_or_str(seg_path, root))

    if places_path is not None and places_path.is_file():
        places_fc = json.loads(places_path.read_text(encoding="utf-8"))
        source_files.append(_rel_or_str(places_path, root))
    else:
        places_fc = {
            "type": "FeatureCollection",
            "mock": bool(segments_fc.get("mock", False)),
            "features": [],
        }

    ml_scores: dict[str, Any] | None = None
    if ml_path is not None and ml_path.is_file():
        ml_scores = json.loads(ml_path.read_text(encoding="utf-8"))
        source_files.append(_rel_or_str(ml_path, root))

    field_reports = list_field_reports(project)
    cfg = load_vehicle_config()
    advisor_state = assess_collection(
        segments_fc,
        config=cfg,
        ml_scores=ml_scores,
        field_reports=field_reports,
    )

    acc_rep_path = _first_existing(
        [
            proj_dir / "access_report.json",
            proj_dir / "access_report.example.json" if project == "mock" else proj_dir / "access_report.json",
        ]
    )
    if acc_rep_path is not None and not field_reports and project != "mock":
        access_report = json.loads(acc_rep_path.read_text(encoding="utf-8"))
        source_files.append(_rel_or_str(acc_rep_path, root))
    else:
        access_report = compute_access_report(
            segments_geojson=segments_fc,
            places_geojson=places_fc,
            advisor_state=advisor_state,
            project=project,
            backend="networkx",
        )

    # Run metadata (survey timestamps & raster product paths)
    run_candidates = [proj_dir / "run.json"]
    if project == "mock" or (proj_dir / "run.example.json").is_file():
        run_candidates.append(proj_dir / "run.example.json")
    runs_root = root / "data" / "runs"
    if runs_root.is_dir():
        for rdir in sorted(runs_root.iterdir(), reverse=True):
            rj = rdir / "run.json"
            if rj.is_file():
                try:
                    rdoc = json.loads(rj.read_text(encoding="utf-8"))
                    if rdoc.get("project") == project:
                        run_candidates.insert(0, rj)
                        break
                except Exception:
                    continue

    run_path = _first_existing(run_candidates)
    run_doc: dict[str, Any] | None = None
    if run_path is not None:
        run_doc = json.loads(run_path.read_text(encoding="utf-8"))
        source_files.append(_rel_or_str(run_path, root))

    # Accuracy & checkpoint coordinate files
    acc_candidates: list[Path] = []
    if accuracy_override is not None:
        acc_candidates.append(accuracy_override)
    acc_candidates.extend(
        [
            proj_dir / "accuracy.json",
            proj_dir / "accuracy" / "accuracy.json",
        ]
    )
    if run_path is not None:
        acc_candidates.append(run_path.parent / "accuracy.json")
    if project == "mock" or (proj_dir / "accuracy.example.json").is_file():
        acc_candidates.append(proj_dir / "accuracy.example.json")

    acc_path = _first_existing(acc_candidates)
    accuracy_doc: dict[str, Any] | None = None
    confirmed_doc: dict[str, Any] | None = None
    rtk_rows: dict[str, dict[str, str]] = {}

    if acc_path is not None:
        accuracy_doc = json.loads(acc_path.read_text(encoding="utf-8"))
        source_files.append(_rel_or_str(acc_path, root))
        cp_search_dirs = [acc_path.parent, proj_dir]
        if run_path is not None:
            cp_search_dirs.append(run_path.parent)
        conf_path = _first_existing([d / "confirmed.json" for d in cp_search_dirs])
        if conf_path is not None:
            confirmed_doc = json.loads(conf_path.read_text(encoding="utf-8"))
            source_files.append(_rel_or_str(conf_path, root))
        for d in cp_search_dirs:
            if not d.is_dir():
                continue
            csv_files = sorted(d.glob("*rtk*.csv")) + sorted(d.glob("*RTK*.csv"))
            for cf in csv_files:
                if cf.is_file():
                    with open(cf, encoding="utf-8-sig") as fh:
                        reader = csv.DictReader(fh)
                        for row in reader:
                            pid = row.get("pid") or row.get("id")
                            if pid:
                                rtk_rows[str(pid)] = row
                    source_files.append(_rel_or_str(cf, root))
                    break
            if rtk_rows:
                break

    # Measurement JSON files
    meas_files: list[Path] = []
    if measurements_dir_override is not None and measurements_dir_override.is_dir():
        meas_files.extend(sorted(measurements_dir_override.glob("*.json")))
    else:
        for cand_dir in (proj_dir / "measurements", proj_dir):
            if cand_dir.is_dir():
                for jf in sorted(cand_dir.glob("*measurement*.json")):
                    if jf.is_file() and jf not in meas_files:
                        meas_files.append(jf)
        if not meas_files and (proj_dir / "measurements").is_dir():
            for jf in sorted((proj_dir / "measurements").glob("*.json")):
                if jf.is_file() and jf not in meas_files:
                    meas_files.append(jf)

    measurements: list[tuple[str, dict[str, Any]]] = []
    for idx, mf in enumerate(meas_files, start=1):
        try:
            mdoc = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(mdoc, dict) and "input_geometry" in mdoc and "type" in mdoc:
            measurements.append((f"{mf.stem}_{idx:02d}", mdoc))
            source_files.append(_rel_or_str(mf, root))

    # Orthophoto and DSM GeoTIFF discovery
    search_roots = [proj_dir, root]
    if run_path is not None:
        search_roots.insert(0, run_path.parent)

    ortho_path = orthophoto_override if (orthophoto_override and orthophoto_override.is_file()) else None
    if ortho_path is None and run_doc and isinstance(run_doc.get("products"), dict):
        ortho_path = _resolve_product_path(run_doc["products"].get("orthophoto"), search_roots)
    if ortho_path is None:
        ortho_path = _first_existing(
            [
                proj_dir / "orthophoto.tif",
                proj_dir / "ortho.tif",
                proj_dir / "odm_orthophoto" / "odm_orthophoto.tif",
            ]
        )
    if ortho_path is not None:
        source_files.append(_rel_or_str(ortho_path, root))

    dsm_path = dsm_override if (dsm_override and dsm_override.is_file()) else None
    if dsm_path is None and run_doc and isinstance(run_doc.get("products"), dict):
        dsm_path = _resolve_product_path(run_doc["products"].get("dsm"), search_roots)
    if dsm_path is None:
        dsm_path = _first_existing(
            [
                proj_dir / "dsm.tif",
                proj_dir / "odm_dem" / "dsm.tif",
            ]
        )
    if dsm_path is not None:
        source_files.append(_rel_or_str(dsm_path, root))

    # Deduplicate source_files preserving order
    dedup_sources = list(dict.fromkeys(source_files))

    return ExportInputs(
        project=project,
        project_dir=proj_dir,
        segments_fc=segments_fc,
        places_fc=places_fc,
        advisor_state=advisor_state,
        access_report=access_report,
        accuracy=accuracy_doc,
        confirmed=confirmed_doc,
        rtk_rows=rtk_rows,
        measurements=measurements,
        run_doc=run_doc,
        orthophoto_path=ortho_path,
        dsm_path=dsm_path,
        source_files=dedup_sources,
    )
