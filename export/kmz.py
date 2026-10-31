"""Google Earth KMZ exporter with shape+colour status styles and orthophoto GroundOverlay (E3)."""
from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

import cv2
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject
from shapely.geometry import LineString, MultiLineString, Point, Polygon

KML_NS = "http://www.opengis.net/kml/2.2"

# KML colours use aabbggrr hex order.
ROAD_STYLE_SPEC: dict[str, dict[str, Any]] = {
    "open": {
        "kml_color": "ff2ca02c",
        "bgra": (44, 160, 44, 255),
        "width": "4.0",
        "icon": "icons/open_circle.png",
        "shape": "circle",
        "scale": "0.75",
    },
    "partial": {
        "kml_color": "ff008cff",
        "bgra": (0, 140, 255, 255),
        "width": "3.5",
        "icon": "icons/partial_triangle.png",
        "shape": "triangle",
        "scale": "0.85",
    },
    "blocked": {
        "kml_color": "ff2827d6",
        "bgra": (40, 39, 214, 255),
        "width": "5.0",
        "icon": "icons/blocked_cross.png",
        "shape": "cross",
        "scale": "0.95",
    },
    "unknown": {
        "kml_color": "ff7f7f7f",
        "bgra": (127, 127, 127, 255),
        "width": "2.2",
        "icon": "icons/unknown_diamond.png",
        "shape": "diamond",
        "scale": "0.80",
    },
}


def _render_marker_png(shape_kind: str, bgra: tuple[int, int, int, int], size: int = 48) -> bytes:
    """Render an offline 48x48 RGBA PNG shape marker so KMZ needs zero external icon URLs."""
    img = np.zeros((size, size, 4), dtype=np.uint8)
    c = size // 2
    white = (255, 255, 255, 255)
    dark = (20, 20, 20, 255)

    if shape_kind == "circle":
        cv2.circle(img, (c, c), 15, white, -1, lineType=cv2.LINE_AA)
        cv2.circle(img, (c, c), 12, bgra, -1, lineType=cv2.LINE_AA)
        cv2.circle(img, (c, c), 15, dark, 2, lineType=cv2.LINE_AA)
    elif shape_kind == "triangle":
        pts = np.array([[c, 6], [size - 6, size - 8], [6, size - 8]], dtype=np.int32)
        cv2.fillPoly(img, [pts], bgra, lineType=cv2.LINE_AA)
        cv2.polylines(img, [pts], True, white, 4, lineType=cv2.LINE_AA)
        cv2.polylines(img, [pts], True, dark, 2, lineType=cv2.LINE_AA)
    elif shape_kind == "cross":
        cv2.line(img, (9, 9), (size - 9, size - 9), white, 10, lineType=cv2.LINE_AA)
        cv2.line(img, (size - 9, 9), (9, size - 9), white, 10, lineType=cv2.LINE_AA)
        cv2.line(img, (9, 9), (size - 9, size - 9), bgra, 6, lineType=cv2.LINE_AA)
        cv2.line(img, (size - 9, 9), (9, size - 9), bgra, 6, lineType=cv2.LINE_AA)
    elif shape_kind == "diamond":
        pts = np.array([[c, 5], [size - 5, c], [c, size - 5], [5, c]], dtype=np.int32)
        cv2.fillPoly(img, [pts], white, lineType=cv2.LINE_AA)
        cv2.polylines(img, [pts], True, bgra, 5, lineType=cv2.LINE_AA)
    elif shape_kind == "square":
        cv2.rectangle(img, (9, 9), (size - 9, size - 9), bgra, -1)
        cv2.rectangle(img, (9, 9), (size - 9, size - 9), white, 3)
    elif shape_kind == "helipad":
        cv2.circle(img, (c, c), 18, (255, 255, 255, 240), -1, lineType=cv2.LINE_AA)
        cv2.circle(img, (c, c), 18, bgra, 3, lineType=cv2.LINE_AA)
        cv2.line(img, (c - 7, c - 9), (c - 7, c + 9), bgra, 3)
        cv2.line(img, (c + 7, c - 9), (c + 7, c + 9), bgra, 3)
        cv2.line(img, (c - 7, c), (c + 7, c), bgra, 3)
    elif shape_kind == "plus":
        cv2.line(img, (c, 7), (c, size - 7), white, 7, lineType=cv2.LINE_AA)
        cv2.line(img, (7, c), (size - 7, c), white, 7, lineType=cv2.LINE_AA)
        cv2.line(img, (c, 7), (c, size - 7), bgra, 4, lineType=cv2.LINE_AA)
        cv2.line(img, (7, c), (size - 7, c), bgra, 4, lineType=cv2.LINE_AA)

    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError(f"Failed to encode KML icon PNG for {shape_kind}")
    return bytes(buf)


def warp_orthophoto_to_wgs84_png(
    ortho_path: Path,
    max_dim: int = 1024,
) -> tuple[bytes, dict[str, float]]:
    """Reproject an orthophoto GeoTIFF to EPSG:4326 and downsample to RGBA PNG + LatLonBox."""
    with rasterio.open(ortho_path) as src:
        dst_crs = "EPSG:4326"
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        if width is None or height is None or width <= 0 or height <= 0:
            raise ValueError(f"Invalid reprojected dimensions for {ortho_path}")

        scale = min(1.0, float(max_dim) / float(max(width, height)))
        if scale < 1.0:
            new_w = max(1, int(round(width * scale)))
            new_h = max(1, int(round(height * scale)))
            transform = transform * transform.scale(width / new_w, height / new_h)
            width, height = new_w, new_h

        nbands = src.count
        warped = np.zeros((min(4, max(3, nbands)), height, width), dtype=np.float32)
        valid_mask = np.ones((height, width), dtype=bool)

        bands_to_read = [1, 2, 3] if nbands >= 3 else [1, 1, 1]
        for idx, bidx in enumerate(bands_to_read):
            dst_arr = np.full((height, width), np.nan, dtype=np.float32)
            reproject(
                source=rasterio.band(src, bidx),
                destination=dst_arr,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src.nodata,
                dst_transform=transform,
                dst_crs=dst_crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
            valid_mask &= np.isfinite(dst_arr)
            warped[idx] = np.nan_to_num(dst_arr, nan=0.0)

        # Normalize to uint8 if source is float or >255 uint16
        rgb = warped[:3]
        if str(src.dtypes[0]) != "uint8":
            finite_vals = rgb[:, valid_mask]
            if finite_vals.size > 0:
                vmin = float(np.percentile(finite_vals, 2))
                vmax = float(np.percentile(finite_vals, 98))
                if vmax <= vmin:
                    vmax = vmin + 1.0
                rgb = np.clip((rgb - vmin) / (vmax - vmin) * 255.0, 0.0, 255.0)
        rgb_u8 = np.clip(rgb, 0.0, 255.0).astype(np.uint8)

        alpha = np.where(valid_mask, 235, 0).astype(np.uint8)
        if nbands >= 4:
            a_arr = np.zeros((height, width), dtype=np.float32)
            reproject(
                source=rasterio.band(src, 4),
                destination=a_arr,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest,
            )
            alpha = np.where(valid_mask & (a_arr > 0), 235, 0).astype(np.uint8)

        # OpenCV expects BGRA channel order
        bgra = np.dstack([rgb_u8[2], rgb_u8[1], rgb_u8[0], alpha])
        ok, buf = cv2.imencode(".png", bgra)
        if not ok:
            raise RuntimeError(f"Failed to encode downsampled orthophoto PNG from {ortho_path}")

        west = float(transform.c)
        north = float(transform.f)
        east = float(west + transform.a * width)
        south = float(north + transform.e * height)

        bbox = {
            "north": max(north, south),
            "south": min(north, south),
            "east": max(east, west),
            "west": min(east, west),
        }
        return bytes(buf), bbox


def _coords_str(coords: list[tuple[float, ...]]) -> str:
    return " ".join(f"{float(c[0]):.7f},{float(c[1]):.7f},0" for c in coords)


def _append_geometry_xml(parent: ET.Element, geom: Any, add_midpoint_marker: bool = False) -> bool:
    if geom is None or not hasattr(geom, "is_empty") or geom.is_empty:
        return False

    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if len(coords) < 2:
            return False
        if add_midpoint_marker:
            mg = ET.SubElement(parent, "MultiGeometry")
            ls = ET.SubElement(mg, "LineString")
            ET.SubElement(ls, "tessellate").text = "1"
            ET.SubElement(ls, "coordinates").text = _coords_str(coords)
            mid = geom.interpolate(0.5, normalized=True)
            pt = ET.SubElement(mg, "Point")
            ET.SubElement(pt, "coordinates").text = f"{mid.x:.7f},{mid.y:.7f},0"
        else:
            ls = ET.SubElement(parent, "LineString")
            ET.SubElement(ls, "tessellate").text = "1"
            ET.SubElement(ls, "coordinates").text = _coords_str(coords)
        return True

    if isinstance(geom, MultiLineString):
        mg = ET.SubElement(parent, "MultiGeometry")
        for part in geom.geoms:
            ls = ET.SubElement(mg, "LineString")
            ET.SubElement(ls, "tessellate").text = "1"
            ET.SubElement(ls, "coordinates").text = _coords_str(list(part.coords))
        if add_midpoint_marker and len(geom.geoms) > 0:
            mid = geom.geoms[0].interpolate(0.5, normalized=True)
            pt = ET.SubElement(mg, "Point")
            ET.SubElement(pt, "coordinates").text = f"{mid.x:.7f},{mid.y:.7f},0"
        return True

    if isinstance(geom, Point):
        if math.isnan(geom.x) or math.isnan(geom.y):
            return False
        pt = ET.SubElement(parent, "Point")
        ET.SubElement(pt, "coordinates").text = f"{geom.x:.7f},{geom.y:.7f},0"
        return True

    if isinstance(geom, Polygon):
        poly = ET.SubElement(parent, "Polygon")
        ob = ET.SubElement(poly, "outerBoundaryIs")
        lr = ET.SubElement(ob, "LinearRing")
        ET.SubElement(lr, "coordinates").text = _coords_str(list(geom.exterior.coords))
        return True

    return False


def _add_style(
    doc: ET.Element,
    style_id: str,
    *,
    line_color: str | None = None,
    line_width: str = "2.5",
    icon_href: str | None = None,
    icon_scale: str = "0.85",
    poly_color: str | None = None,
) -> None:
    st = ET.SubElement(doc, "Style", id=style_id)
    if icon_href:
        ist = ET.SubElement(st, "IconStyle")
        ET.SubElement(ist, "scale").text = icon_scale
        ic = ET.SubElement(ist, "Icon")
        ET.SubElement(ic, "href").text = icon_href
    if line_color:
        lst = ET.SubElement(st, "LineStyle")
        ET.SubElement(lst, "color").text = line_color
        ET.SubElement(lst, "width").text = line_width
    if poly_color:
        pst = ET.SubElement(st, "PolyStyle")
        ET.SubElement(pst, "color").text = poly_color


def _description_table(props: dict[str, Any]) -> str:
    rows = []
    for k, v in props.items():
        if k == "geometry":
            continue
        rows.append(
            f"<tr><td><b>{html.escape(str(k))}</b></td><td>{html.escape(str(v))}</td></tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def write_kmz(
    *,
    project: str,
    layers: dict[str, gpd.GeoDataFrame],
    kmz_path: Path,
    orthophoto_path: Path | None = None,
    data_basis: str | None = None,
    processed_time: str | None = None,
    captured_time: str | None = None,
) -> dict[str, Any]:
    """Write vortex.kmz with styled vector layers (shape + colour) and optional GroundOverlay."""
    kmz_path.parent.mkdir(parents=True, exist_ok=True)
    ET.register_namespace("", KML_NS)
    kml_root = ET.Element("kml", xmlns=KML_NS)
    doc = ET.SubElement(kml_root, "Document")
    ET.SubElement(doc, "name").text = f"Project Typhon: road access map: {project}"

    roads_gdf = layers.get("roads_status")
    has_measured = roads_gdf is not None and "measured" in roads_gdf.columns
    inside_gdf = roads_gdf[roads_gdf["measured"] == True] if has_measured else roads_gdf
    outside_gdf = roads_gdf[roads_gdf["measured"] == False] if has_measured else (roads_gdf.iloc[0:0] if roads_gdf is not None else None)
    inside_unknown = inside_gdf["display_status"].value_counts().get("unknown", 0) if (inside_gdf is not None and len(inside_gdf)) else 0

    desc_lines = [
        f"Project: {project}",
        f"Data basis: {data_basis or 'not stated'}",
        f"Processed: {processed_time or 'not recorded'}",
        f"Capture date: {captured_time or 'capture date: not recorded'}",
        f"Road segments: {len(roads_gdf) if roads_gdf is not None else 0}",
    ]
    if has_measured and outside_gdf is not None and len(outside_gdf) > 0:
        desc_lines.append(f"unknown inside mapped area: {inside_unknown}")
        desc_lines.append(f"outside mapped area: {len(outside_gdf)}")
    ET.SubElement(doc, "description").text = "\n".join(desc_lines)

    bundled_files: dict[str, bytes] = {}

    # 1. Road status styles (distinct by BOTH geometric marker shape AND line/marker colour)
    for status_name, spec in ROAD_STYLE_SPEC.items():
        bundled_files[spec["icon"]] = _render_marker_png(spec["shape"], spec["bgra"])
        _add_style(
            doc,
            f"road_{status_name}",
            line_color=spec["kml_color"],
            line_width=spec["width"],
            icon_href=spec["icon"],
            icon_scale=spec["scale"],
        )

    # 2. Point/polygon layer styles
    bundled_files["icons/place_square.png"] = _render_marker_png("square", (30, 30, 210, 255))
    bundled_files["icons/lz_helipad.png"] = _render_marker_png("helipad", (180, 90, 10, 255))
    bundled_files["icons/checkpoint_plus.png"] = _render_marker_png("plus", (180, 0, 180, 255))
    bundled_files["icons/measurement_ring.png"] = _render_marker_png("diamond", (200, 120, 0, 255))

    _add_style(doc, "cutoff_place_style", icon_href="icons/place_square.png", icon_scale="0.95")
    _add_style(
        doc,
        "landing_zone_style",
        line_color="ffffaa00",
        line_width="2.5",
        icon_href="icons/lz_helipad.png",
        icon_scale="1.0",
        poly_color="55ffaa00",
    )
    _add_style(doc, "checkpoint_style", icon_href="icons/checkpoint_plus.png", icon_scale="0.90")
    _add_style(
        doc,
        "measurement_style",
        line_color="ff00d4ff",
        line_width="3.0",
        icon_href="icons/measurement_ring.png",
        icon_scale="0.85",
        poly_color="4400d4ff",
    )

    # 3. Optional orthophoto GroundOverlay
    has_ground_overlay = False
    overlay_bbox: dict[str, float] | None = None
    if orthophoto_path is not None and orthophoto_path.is_file():
        png_bytes, overlay_bbox = warp_orthophoto_to_wgs84_png(orthophoto_path, max_dim=1024)
        bundled_files["overlay.png"] = png_bytes
        go = ET.SubElement(doc, "GroundOverlay")
        ET.SubElement(go, "name").text = f"{project} orthophoto (downsampled)"
        ic = ET.SubElement(go, "Icon")
        ET.SubElement(ic, "href").text = "overlay.png"
        llb = ET.SubElement(go, "LatLonBox")
        for edge in ("north", "south", "east", "west"):
            ET.SubElement(llb, edge).text = f"{overlay_bbox[edge]:.7f}"
        has_ground_overlay = True

    # 4. Vector Folders
    placemark_counts: dict[str, int] = {}

    # 4a. roads_status
    f_roads = ET.SubElement(doc, "Folder")
    ET.SubElement(f_roads, "name").text = "roads_status"
    cnt_roads = 0
    for _, row in layers["roads_status"].iterrows():
        geom = row.geometry
        if geom is None or not hasattr(geom, "is_empty") or geom.is_empty:
            continue
        st_name = str(row.get("display_status", "unknown"))
        if st_name not in ROAD_STYLE_SPEC:
            st_name = "unknown"
        pm = ET.SubElement(f_roads, "Placemark")
        ET.SubElement(pm, "name").text = f"{row['segment_id']} [{st_name.upper()}]"
        ET.SubElement(pm, "styleUrl").text = f"#road_{st_name}"
        ET.SubElement(pm, "description").text = _description_table(row.to_dict())
        if _append_geometry_xml(pm, geom, add_midpoint_marker=True):
            cnt_roads += 1
        else:
            f_roads.remove(pm)
    placemark_counts["roads_status"] = cnt_roads

    # 4b. Other layers
    other_specs = [
        ("cutoff_places", "name", "cutoff_place_style"),
        ("landing_zones", "name", "landing_zone_style"),
        ("checkpoints", "checkpoint_id", "checkpoint_style"),
        ("measurements", "measurement_id", "measurement_style"),
    ]
    for lname, title_col, style_id in other_specs:
        folder = ET.SubElement(doc, "Folder")
        ET.SubElement(folder, "name").text = lname
        cnt = 0
        for _, row in layers[lname].iterrows():
            geom = row.geometry
            if geom is None or not hasattr(geom, "is_empty") or geom.is_empty:
                continue
            pm = ET.SubElement(folder, "Placemark")
            ET.SubElement(pm, "name").text = str(row.get(title_col) or lname)
            ET.SubElement(pm, "styleUrl").text = f"#{style_id}"
            ET.SubElement(pm, "description").text = _description_table(row.to_dict())
            if _append_geometry_xml(pm, geom, add_midpoint_marker=False):
                cnt += 1
            else:
                folder.remove(pm)
        placemark_counts[lname] = cnt

    ET.indent(kml_root, space="  ")
    kml_bytes = ET.tostring(kml_root, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(kmz_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_bytes)
        for rel_name, content in sorted(bundled_files.items()):
            zf.writestr(rel_name, content)

    return {
        "kmz_path": kmz_path,
        "placemark_counts": placemark_counts,
        "has_ground_overlay": has_ground_overlay,
        "overlay_bbox": overlay_bbox,
    }
