"""End-to-end tests for E1-E6 GIS, KMZ, COG, A3 PDF, and manifest exports."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import cv2
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_bounds

from export import LAYER_NAMES
from export.all import export_project_all
from export.cog import validate_cog
from export.pdf_map import PDF_ROAD_STYLES, format_accuracy_line

ROOT = Path(__file__).resolve().parent.parent


def _write_synthetic_utm11_geotiffs(tmp_dir: Path) -> tuple[Path, Path]:
    """Create small synthetic EPSG:32611 orthophoto (RGB uint8) and DSM (float32) GeoTIFFs."""
    ortho_path = tmp_dir / "synth_ortho_32611.tif"
    dsm_path = tmp_dir / "synth_dsm_32611.tif"
    width, height = 320, 320
    # Valid UTM Zone 11N bounds (Sequoia / South Fork region, metres)
    transform = from_bounds(335000.0, 4025000.0, 335320.0, 4025320.0, width, height)

    yy, xx = np.mgrid[0:height, 0:width]
    rgb = np.stack(
        [
            ((xx * 2 + yy) % 256).astype(np.uint8),
            ((xx + yy * 2) % 256).astype(np.uint8),
            (120 + (xx % 80)).astype(np.uint8),
        ],
        axis=0,
    )
    with rasterio.open(
        ortho_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=3,
        dtype="uint8",
        crs="EPSG:32611",
        transform=transform,
    ) as dst:
        dst.write(rgb)

    dsm = (1150.0 + 0.08 * xx + 0.05 * yy).astype(np.float32)
    with rasterio.open(
        dsm_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:32611",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(dsm, 1)

    return ortho_path, dsm_path


def _assert_single_page_a3_landscape_pdf(pdf_path: Path) -> None:
    assert pdf_path.is_file() and pdf_path.stat().st_size > 1000
    raw = pdf_path.read_bytes()
    assert raw.startswith(b"%PDF-")
    # Matplotlib PDF writer writes exactly one /Type /Pages dictionary with /Count <N>
    counts = [int(m.group(1)) for m in re.finditer(rb"/Count\s+(\d+)", raw)]
    assert counts and max(counts) == 1, f"Expected 1-page PDF, got /Count values {counts}"
    mbox = re.search(
        rb"/MediaBox\s*\[\s*0(?:\.0+)?\s+0(?:\.0+)?\s+([0-9.]+)\s+([0-9.]+)\s*\]",
        raw,
    )
    assert mbox is not None, "PDF missing /MediaBox"
    w_pt, h_pt = float(mbox.group(1)), float(mbox.group(2))
    # A3 landscape = 420 mm x 297 mm = 1190.55 pt x 841.89 pt
    assert abs(w_pt - 1190.55) < 2.5 and abs(h_pt - 841.89) < 2.5, (w_pt, h_pt)


def test_export_cli_on_contract_examples_and_synthetic_epsg32611_geotiffs(tmp_path: Path) -> None:
    ortho_tif, dsm_tif = _write_synthetic_utm11_geotiffs(tmp_path)
    out_dir = tmp_path / "exports_mock"

    cmd = [
        sys.executable,
        "-m",
        "export.all",
        "--project",
        "mock",
        "--out",
        str(out_dir),
        "--orthophoto",
        str(ortho_tif),
        "--dsm",
        str(dsm_tif),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"CLI failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"

    # E6: Manifest check
    manifest_path = out_dir / "export_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["project"] == "mock"
    assert manifest["accuracy_line"] == "Positional accuracy: accuracy not measured yet"
    for entry in manifest["files"]:
        for req_key in ("file", "format", "crs", "layer_counts", "source_files", "generated_at"):
            assert req_key in entry, f"Missing {req_key} in manifest entry {entry}"
        assert (out_dir / entry["file"]).is_file()

    # E1: Re-open every GeoJSON file with geopandas.read_file
    # Note: place_MOCK_A is selected as base_place_id (reachable at base junction),
    # while lz_MOCK_1 goes into landing_zones, so cutoff_places is 0 on mock.
    expected_counts = {
        "roads_status": 2,
        "cutoff_places": 0,
        "landing_zones": 1,
        "checkpoints": 1,
        "measurements": 1,
    }
    for lname in LAYER_NAMES:
        gj_path = out_dir / f"{lname}.geojson"
        assert gj_path.is_file()
        gdf = gpd.read_file(gj_path)
        assert len(gdf) == expected_counts[lname]
        if len(gdf) > 0 and gdf.geometry.notna().any():
            assert gdf.crs is not None and gdf.crs.to_epsg() == 4326

    roads_gdf = gpd.read_file(out_dir / "roads_status.geojson")
    assert set(roads_gdf["status_ambulance"]) == {"unknown"}
    assert "reasons_ambulance" in roads_gdf.columns

    # E2: Re-open every layer in vortex.gpkg with geopandas.read_file
    gpkg_path = out_dir / "vortex.gpkg"
    assert gpkg_path.is_file()
    for lname in LAYER_NAMES:
        gdf_pkg = gpd.read_file(gpkg_path, layer=lname)
        assert len(gdf_pkg) == expected_counts[lname]
        assert gdf_pkg.crs is not None and gdf_pkg.crs.to_epsg() == 4326

    # E3: Unzip and parse vortex.kmz, verify shape+colour styles, zero external URLs, GroundOverlay
    kmz_path = out_dir / "vortex.kmz"
    assert kmz_path.is_file()
    with zipfile.ZipFile(kmz_path, "r") as zf:
        names = set(zf.namelist())
        assert "doc.kml" in names
        assert "overlay.png" in names
        expected_icons = {
            "icons/open_circle.png",
            "icons/partial_triangle.png",
            "icons/blocked_cross.png",
            "icons/unknown_diamond.png",
        }
        assert expected_icons.issubset(names)

        # Verify the 4 status icons are distinct geometric shapes
        decoded_shapes = []
        for ic_name in sorted(expected_icons):
            arr = cv2.imdecode(np.frombuffer(zf.read(ic_name), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            assert arr is not None and arr.shape == (48, 48, 4)
            decoded_shapes.append(arr[:, :, 3] > 0)
        for i in range(len(decoded_shapes)):
            for j in range(i + 1, len(decoded_shapes)):
                assert not np.array_equal(decoded_shapes[i], decoded_shapes[j]), "Icons must differ by shape"

        overlay_arr = cv2.imdecode(
            np.frombuffer(zf.read("overlay.png"), dtype=np.uint8), cv2.IMREAD_UNCHANGED
        )
        assert overlay_arr is not None and overlay_arr.ndim == 3 and overlay_arr.shape[2] == 4

        kml_text = zf.read("doc.kml").decode("utf-8")
        # Zero external icon/CDN URLs (only XML namespace http://www.opengis.net/kml/2.2 allowed)
        urls = re.findall(r"https?://[^\s\"'<>]+", kml_text)
        assert set(urls) <= {"http://www.opengis.net/kml/2.2"}, f"External URLs found in KML: {urls}"

        root = ET.fromstring(kml_text)
        ns = {"k": "http://www.opengis.net/kml/2.2"}
        styles = {el.attrib["id"]: el for el in root.findall(".//k:Style", ns) if "id" in el.attrib}
        road_colors = set()
        road_icons = set()
        for st_key in ("road_open", "road_partial", "road_blocked", "road_unknown"):
            assert st_key in styles
            col = styles[st_key].findtext("k:LineStyle/k:color", namespaces=ns)
            ic_href = styles[st_key].findtext("k:IconStyle/k:Icon/k:href", namespaces=ns)
            assert col and ic_href
            road_colors.add(col)
            road_icons.add(ic_href)
        assert len(road_colors) == 4, "All 4 road statuses must have distinct KML colours"
        assert len(road_icons) == 4, "All 4 road statuses must have distinct KML icon shapes"

        go = root.find(".//k:GroundOverlay", ns)
        assert go is not None
        assert go.findtext("k:Icon/k:href", namespaces=ns) == "overlay.png"
        north = float(go.findtext("k:LatLonBox/k:north", namespaces=ns))
        south = float(go.findtext("k:LatLonBox/k:south", namespaces=ns))
        east = float(go.findtext("k:LatLonBox/k:east", namespaces=ns))
        west = float(go.findtext("k:LatLonBox/k:west", namespaces=ns))
        assert north > south and east > west

    # E4: COG validity check on both orthophoto_cog.tif and dsm_cog.tif
    ortho_cog_res = validate_cog(out_dir / "orthophoto_cog.tif", strict=True)
    assert ortho_cog_res["valid"] is True
    assert ortho_cog_res["crs"] == "EPSG:32611"
    assert len(ortho_cog_res["overviews"]) >= 1

    dsm_cog_res = validate_cog(out_dir / "dsm_cog.tif", strict=True)
    assert dsm_cog_res["valid"] is True
    assert dsm_cog_res["crs"] == "EPSG:32611"
    assert len(dsm_cog_res["overviews"]) >= 1

    # E5: 1-page A3 landscape PDF check
    _assert_single_page_a3_landscape_pdf(out_dir / "map_a3.pdf")


def test_export_numeric_accuracy_reprojected_checkpoints_and_bw_patterns(tmp_path: Path) -> None:
    proj_dir = tmp_path / "synth_proj"
    proj_dir.mkdir(parents=True)
    ortho_tif, _ = _write_synthetic_utm11_geotiffs(proj_dir)

    segments_fc = {
        "type": "FeatureCollection",
        "mock": False,
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-118.8180, 36.3570], [-118.8170, 36.3570]]},
                "properties": {
                    "segment_id": "s_open",
                    "highway": "secondary",
                    "length_m": 90.0,
                    "corridor_width_m": 6.5,
                    "coverage_fraction": 0.95,
                    "max_obstruction_m": 0.05,
                    "min_clear_width_m": 5.5,
                    "measured": True,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-118.8170, 36.3570], [-118.8160, 36.3575]]},
                "properties": {
                    "segment_id": "s_partial",
                    "highway": "tertiary",
                    "length_m": 95.0,
                    "corridor_width_m": 4.0,
                    "coverage_fraction": 0.90,
                    "max_obstruction_m": 0.28,
                    "min_clear_width_m": 2.35,
                    "measured": True,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-118.8160, 36.3575], [-118.8150, 36.3580]]},
                "properties": {
                    "segment_id": "s_blocked",
                    "highway": "residential",
                    "length_m": 110.0,
                    "corridor_width_m": 4.0,
                    "coverage_fraction": 0.92,
                    "max_obstruction_m": 1.8,
                    "min_clear_width_m": 0.4,
                    "measured": True,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-118.8150, 36.3580], [-118.8142, 36.3584]]},
                "properties": {
                    "segment_id": "s_unknown",
                    "highway": "track",
                    "length_m": 85.0,
                    "corridor_width_m": None,
                    "coverage_fraction": 0.10,
                    "max_obstruction_m": None,
                    "min_clear_width_m": None,
                    "measured": False,
                },
            },
        ],
    }
    places_fc = {
        "type": "FeatureCollection",
        "mock": False,
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-118.8180, 36.3570]},
                "properties": {
                    "place_id": "p_base",
                    "name": "Staging Base",
                    "kind": "other_facility",
                    "source": "manual",
                    "population": None,
                    "population_source": "staging_base",
                    "nearest_segment_id": "s_open",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-118.8150, 36.3580]},
                "properties": {
                    "place_id": "p_hamlet",
                    "name": "Canyon Hamlet",
                    "kind": "settlement",
                    "source": "osm",
                    "population": 120,
                    "population_source": "WorldPop 2020 (CC BY 4.0)",
                    "nearest_segment_id": "s_blocked",
                },
            },
        ],
    }
    accuracy_doc = {
        "mock": False,
        "run_id": "southfork_quick_01",
        "used_gcps": False,
        "n_checkpoints": 2,
        "checkpoint_method": "rtk",
        "horizontal": {"rmse_x_m": 1.0, "rmse_y_m": 1.05, "rmse_h_m": 1.45, "max_error_m": 1.8},
        "vertical": {"rmse_v_m": 2.1, "max_error_m": 2.5},
        "per_point": [
            {"id": "SF01", "dx_m": 0.9, "dy_m": -1.1, "dz_m": 1.8, "found_by": "manual_click"},
            {"id": "SF02", "dx_m": -1.1, "dy_m": 1.0, "dz_m": -2.3, "found_by": "manual_click"},
        ],
    }
    confirmed_doc = {
        "map_epsg": 32611,
        "points": [
            {"id": "SF01", "x": 335100.0, "y": 4025120.0},
            {"id": "SF02", "x": 335220.0, "y": 4025240.0},
        ],
    }
    lz_meas = {
        "mock": False,
        "type": "landing_zones",
        "run_id": "southfork_quick_01",
        "input_geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-118.8175, 36.3571],
                    [-118.8172, 36.3571],
                    [-118.8172, 36.3574],
                    [-118.8175, 36.3574],
                    [-118.8175, 36.3571],
                ]
            ],
        },
        "result": {"candidates_count": 1, "diameter_m": 25.0},
        "tolerance": {"value": 0.5, "unit": "deg", "method": "slope bound"},
        "rule_source": "config/landing_zone.yaml",
        "placeholders_used": [],
        "measured": True,
    }

    (proj_dir / "segments.geojson").write_text(json.dumps(segments_fc), encoding="utf-8")
    (proj_dir / "places.geojson").write_text(json.dumps(places_fc), encoding="utf-8")
    (proj_dir / "accuracy.json").write_text(json.dumps(accuracy_doc), encoding="utf-8")
    (proj_dir / "confirmed.json").write_text(json.dumps(confirmed_doc), encoding="utf-8")
    (proj_dir / "measurement_lz.json").write_text(json.dumps(lz_meas), encoding="utf-8")

    out_dir = tmp_path / "exports_numeric"
    manifest = export_project_all(
        project="synth_proj",
        out_dir=out_dir,
        project_dir_override=proj_dir,
        orthophoto_override=ortho_tif,
    )

    assert manifest["accuracy_line"] == "Positional accuracy: ±1.45 m at 2 checkpoints (RMSE_H, RTK)"
    assert format_accuracy_line(None) == "Positional accuracy: accuracy not measured yet"

    chk_gdf = gpd.read_file(out_dir / "checkpoints.geojson")
    assert len(chk_gdf) == 2
    assert chk_gdf.geometry.notna().all()
    assert chk_gdf.crs.to_epsg() == 4326
    assert (chk_gdf.geometry.x < -118.0).all() and (chk_gdf.geometry.y > 35.0).all()

    lz_gdf = gpd.read_file(out_dir / "landing_zones.geojson")
    assert len(lz_gdf) == 1

    cutoff_gdf = gpd.read_file(out_dir / "cutoff_places.geojson")
    assert len(cutoff_gdf) == 1
    assert cutoff_gdf.iloc[0]["place_id"] == "p_hamlet"

    # Verify B&W print distinguishability: 4 distinct line dash patterns AND 4 distinct marker shapes
    linestyles = {str(v["linestyle"]) for v in PDF_ROAD_STYLES.values()}
    markers = {str(v["marker"]) for v in PDF_ROAD_STYLES.values()}
    assert len(linestyles) == 4
    assert len(markers) == 4

    _assert_single_page_a3_landscape_pdf(out_dir / "map_a3.pdf")


def test_f2_pdf_map_and_kmz_on_real_southfork_sample(tmp_path: Path) -> None:
    """F2: Test PDF map and KMZ on real South Fork sample data."""
    sf_dir = ROOT / "samples" / "southfork_f01_4"
    if not sf_dir.is_dir() or not (sf_dir / "segments.geojson").is_file():
        return

    out_dir = tmp_path / "sf_exports"
    manifest = export_project_all(
        project="southfork_f01_4",
        out_dir=out_dir,
        project_dir_override=sf_dir,
        orthophoto_override=sf_dir / "orthophoto_small.tif",
        accuracy_override=sf_dir / "accuracy.json",
        captured="30 Apr 2024",
        basis="USGS public data (30 Apr 2024), not our footage",
    )

    # 1. Manifest and accuracy
    assert manifest["project"] == "southfork_f01_4"
    assert "±6.09 m at 3 checkpoints" in manifest["accuracy_line"]
    assert manifest["layer_counts"]["roads_status"] == 498
    assert manifest["layer_counts"]["checkpoints"] == 3

    # 2. PDF map check
    pdf_path = out_dir / "map_a3.pdf"
    _assert_single_page_a3_landscape_pdf(pdf_path)

    # 3. KMZ check: name, description, layer summary split
    kmz_path = out_dir / "vortex.kmz"
    assert kmz_path.is_file()
    with zipfile.ZipFile(kmz_path, "r") as zf:
        kml_text = zf.read("doc.kml").decode("utf-8")
        assert "<name>Project Typhon: road access map: southfork_f01_4</name>" in kml_text
        assert "USGS public data (30 Apr 2024), not our footage" in kml_text
        assert "Capture date: 30 Apr 2024" in kml_text
        assert "Processed:" in kml_text
        assert "unknown inside mapped area: 16" in kml_text
        assert "outside mapped area: 482" in kml_text

    # 4. Default flags check: without captured and basis, defaults must be honest
    out_default = tmp_path / "sf_default"
    export_project_all(
        project="southfork_f01_4",
        out_dir=out_default,
        project_dir_override=sf_dir,
        orthophoto_override=sf_dir / "orthophoto_small.tif",
        accuracy_override=sf_dir / "accuracy.json",
    )
    with zipfile.ZipFile(out_default / "vortex.kmz", "r") as zf:
        kml_def = zf.read("doc.kml").decode("utf-8")
        assert "Data basis: not stated" in kml_def
        assert "Capture date: capture date: not recorded" in kml_def
