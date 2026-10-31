"""Unified export CLI: python -m export.all --project <p> --out <dir> (E6)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from export.cog import convert_to_cog
from export.inputs import load_export_inputs
from export.kmz import write_kmz
from export.layers import build_all_layers, write_geojson_layers, write_geopackage
from export.pdf_map import write_pdf_map


def export_project_all(
    project: str,
    out_dir: Path,
    *,
    data_root: Path | None = None,
    project_dir_override: Path | None = None,
    orthophoto_override: Path | None = None,
    dsm_override: Path | None = None,
    accuracy_override: Path | None = None,
    measurements_dir_override: Path | None = None,
) -> dict[str, Any]:
    """Run E1-E5 exports for a project and write export_manifest.json (E6)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    inp = load_export_inputs(
        project=project,
        data_root=data_root,
        project_dir_override=project_dir_override,
        orthophoto_override=orthophoto_override,
        dsm_override=dsm_override,
        accuracy_override=accuracy_override,
        measurements_dir_override=measurements_dir_override,
    )

    layers = build_all_layers(inp)
    layer_counts = {name: int(len(gdf)) for name, gdf in layers.items()}

    entries: list[dict[str, Any]] = []

    # E1: GeoJSON files (EPSG:4326)
    geojson_paths = write_geojson_layers(layers, out_dir)
    for lname, gpath in geojson_paths.items():
        entries.append(
            {
                "file": gpath.name,
                "format": "GeoJSON",
                "crs": "EPSG:4326",
                "layer_counts": {lname: layer_counts[lname]},
                "source_files": inp.source_files,
                "generated_at": generated_at,
            }
        )

    # E2: GeoPackage vortex.gpkg
    gpkg_path = write_geopackage(layers, out_dir / "vortex.gpkg")
    entries.append(
        {
            "file": gpkg_path.name,
            "format": "GPKG",
            "crs": "EPSG:4326",
            "layer_counts": dict(layer_counts),
            "source_files": inp.source_files,
            "generated_at": generated_at,
        }
    )

    # E3: Google Earth KMZ
    kmz_info = write_kmz(
        project=project,
        layers=layers,
        kmz_path=out_dir / "vortex.kmz",
        orthophoto_path=inp.orthophoto_path,
    )
    entries.append(
        {
            "file": kmz_info["kmz_path"].name,
            "format": "KMZ",
            "crs": "EPSG:4326",
            "layer_counts": kmz_info["placemark_counts"],
            "has_ground_overlay": kmz_info["has_ground_overlay"],
            "source_files": inp.source_files,
            "generated_at": generated_at,
        }
    )

    # E4: Cloud-Optimized GeoTIFFs (orthophoto and/or DSM when present)
    if inp.orthophoto_path is not None and inp.orthophoto_path.is_file():
        ortho_cog = out_dir / "orthophoto_cog.tif"
        cog_meta = convert_to_cog(inp.orthophoto_path, ortho_cog)
        entries.append(
            {
                "file": ortho_cog.name,
                "format": "COG",
                "crs": cog_meta["crs"],
                "layer_counts": {"bands": int(cog_meta["count"])},
                "source_files": inp.source_files,
                "generated_at": generated_at,
            }
        )

    if inp.dsm_path is not None and inp.dsm_path.is_file():
        dsm_cog = out_dir / "dsm_cog.tif"
        dsm_meta = convert_to_cog(inp.dsm_path, dsm_cog)
        entries.append(
            {
                "file": dsm_cog.name,
                "format": "COG",
                "crs": dsm_meta["crs"],
                "layer_counts": {"bands": int(dsm_meta["count"])},
                "source_files": inp.source_files,
                "generated_at": generated_at,
            }
        )

    # E5: Printable A3 landscape PDF map
    pdf_info = write_pdf_map(inp, layers, out_dir / "map_a3.pdf")
    entries.append(
        {
            "file": pdf_info["pdf_path"].name,
            "format": "PDF",
            "crs": "EPSG:4326",
            "layer_counts": dict(layer_counts),
            "accuracy_line": pdf_info["accuracy_line"],
            "page_size_mm": pdf_info["page_size_mm"],
            "source_files": inp.source_files,
            "generated_at": generated_at,
        }
    )

    manifest = {
        "project": project,
        "generated_at": generated_at,
        "layer_counts": layer_counts,
        "source_files": inp.source_files,
        "accuracy_line": pdf_info["accuracy_line"],
        "files": entries,
    }
    manifest_path = out_dir / "export_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="Project slug (e.g. mock, wayanad, southfork)")
    ap.add_argument("--out", type=Path, required=True, help="Output directory for exported files")
    ap.add_argument("--project-dir", type=Path, default=None, help="Optional override directory for project inputs")
    ap.add_argument("--orthophoto", type=Path, default=None, help="Optional orthophoto GeoTIFF path")
    ap.add_argument("--dsm", type=Path, default=None, help="Optional DSM GeoTIFF path")
    ap.add_argument("--accuracy", type=Path, default=None, help="Optional accuracy.json path")
    args = ap.parse_args()

    manifest = export_project_all(
        project=args.project,
        out_dir=args.out,
        project_dir_override=args.project_dir,
        orthophoto_override=args.orthophoto,
        dsm_override=args.dsm,
        accuracy_override=args.accuracy,
    )
    print(
        f"Exported {len(manifest['files'])} artifacts for project '{args.project}' -> {args.out} "
        f"(layers={manifest['layer_counts']})"
    )


if __name__ == "__main__":
    main()
