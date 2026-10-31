"""Printable A3 landscape PDF map with B&W-readable road patterns and honest accuracy line (E5)."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
import numpy as np
from pyproj import Geod
from shapely.geometry import LineString, MultiLineString, Point, Polygon

from export.inputs import ExportInputs
from export.kmz import warp_orthophoto_to_wgs84_png

# Exact ISO A3 landscape dimensions: 420 mm x 297 mm
A3_WIDTH_IN = 420.0 / 25.4
A3_HEIGHT_IN = 297.0 / 25.4
GEOD = Geod(ellps="WGS84")

# Distinct in BOTH colour AND black-and-white line pattern + midpoint symbol!
PDF_ROAD_STYLES: dict[str, dict[str, Any]] = {
    "open": {
        "color": "#1b7837",
        "linestyle": "-",
        "linewidth": 2.3,
        "marker": "o",
        "markersize": 4.2,
        "markerfacecolor": "#1b7837",
        "label": "Open (solid line, filled dot)",
    },
    "partial": {
        "color": "#d95f02",
        "linestyle": (0, (6, 3)),
        "linewidth": 2.2,
        "marker": "^",
        "markersize": 5.8,
        "markerfacecolor": "white",
        "label": "Partial / crawl (dashed, hollow triangle)",
    },
    "blocked": {
        "color": "#b2182b",
        "linestyle": (0, (5, 2, 1.2, 2)),
        "linewidth": 3.0,
        "marker": "X",
        "markersize": 6.8,
        "markerfacecolor": "#b2182b",
        "label": "Blocked (thick dash-dot, X cross)",
    },
    "unknown": {
        "color": "#525252",
        "linestyle": (0, (1.2, 2.2)),
        "linewidth": 1.9,
        "marker": "D",
        "markersize": 5.0,
        "markerfacecolor": "white",
        "label": "Unknown — never assumed open (dotted, hollow diamond)",
    },
}


def format_accuracy_line(accuracy_doc: dict[str, Any] | None) -> str:
    """Format positional accuracy strictly from accuracy.json; never guess when missing."""
    if not accuracy_doc:
        return "Positional accuracy: accuracy not measured yet"
    n_cp = accuracy_doc.get("n_checkpoints")
    horiz = accuracy_doc.get("horizontal") or {}
    rmse_h = horiz.get("rmse_h_m")
    if rmse_h is None or n_cp is None or int(n_cp) <= 0:
        return "Positional accuracy: accuracy not measured yet"
    method = str(accuracy_doc.get("checkpoint_method") or "checkpoints").upper()
    return f"Positional accuracy: ±{float(rmse_h):.2f} m at {int(n_cp)} checkpoints (RMSE_H, {method})"


def _nice_scale_length_m(span_m: float) -> float:
    target = max(10.0, span_m * 0.22)
    exp = 10.0 ** math.floor(math.log10(target))
    for mult in (1.0, 2.0, 2.5, 5.0, 10.0):
        cand = mult * exp
        if cand >= target * 0.75:
            return cand
    return 10.0 * exp


def _draw_scale_bar(ax: plt.Axes, xmin: float, xmax: float, ymin: float, ymax: float) -> None:
    mid_lat = 0.5 * (ymin + ymax)
    _, _, width_m = GEOD.inv(xmin, mid_lat, xmax, mid_lat)
    if not math.isfinite(width_m) or width_m <= 1.0:
        return

    bar_m = _nice_scale_length_m(width_m)
    deg_per_m = (xmax - xmin) / width_m
    bar_deg = bar_m * deg_per_m

    x0 = xmin + 0.04 * (xmax - xmin)
    y0 = ymin + 0.045 * (ymax - ymin)
    bar_h = 0.013 * (ymax - ymin)

    # Backdrop box for legibility over orthophoto in both colour and B&W print
    pad_x = 0.015 * (xmax - xmin)
    pad_y = 0.018 * (ymax - ymin)
    ax.add_patch(
        Rectangle(
            (x0 - pad_x, y0 - pad_y),
            bar_deg + 2 * pad_x,
            bar_h + 3.2 * pad_y,
            facecolor="white",
            edgecolor="black",
            linewidth=0.8,
            alpha=0.88,
            zorder=18,
        )
    )
    # Two alternating B&W blocks (0 -> bar_m/2 -> bar_m)
    half_deg = 0.5 * bar_deg
    ax.add_patch(
        Rectangle((x0, y0), half_deg, bar_h, facecolor="black", edgecolor="black", linewidth=0.9, zorder=19)
    )
    ax.add_patch(
        Rectangle(
            (x0 + half_deg, y0), half_deg, bar_h, facecolor="white", edgecolor="black", linewidth=0.9, zorder=19
        )
    )
    label_txt = f"{bar_m / 1000:.1f} km" if bar_m >= 1000 else f"{int(round(bar_m))} m"
    half_txt = f"{bar_m / 2000:.2f} km" if bar_m >= 1000 else f"{int(round(bar_m / 2))}"
    ax.text(x0, y0 + bar_h + 0.005 * (ymax - ymin), "0", fontsize=8, ha="center", va="bottom", zorder=20)
    ax.text(
        x0 + half_deg,
        y0 + bar_h + 0.005 * (ymax - ymin),
        half_txt,
        fontsize=8,
        ha="center",
        va="bottom",
        zorder=20,
    )
    ax.text(
        x0 + bar_deg,
        y0 + bar_h + 0.005 * (ymax - ymin),
        label_txt,
        fontsize=8,
        fontweight="bold",
        ha="center",
        va="bottom",
        zorder=20,
    )


def _draw_north_arrow(ax: plt.Axes) -> None:
    # Axes-fraction north arrow in top-right corner
    ax.annotate(
        "N",
        xy=(0.955, 0.945),
        xytext=(0.955, 0.855),
        xycoords="axes fraction",
        textcoords="axes fraction",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "black", "alpha": 0.9},
        arrowprops={"arrowstyle": "-|>,head_width=0.45,head_length=0.7", "lw": 2.0, "color": "black"},
        zorder=22,
    )


def write_pdf_map(
    inp: ExportInputs,
    layers: dict[str, gpd.GeoDataFrame],
    pdf_path: Path,
) -> dict[str, Any]:
    """Render a 1-page A3 landscape printable map PDF (E5)."""
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    accuracy_line = format_accuracy_line(inp.accuracy)

    # Determine timestamps honestly
    processed_time = "not recorded"
    if inp.run_doc:
        processed_time = str(inp.run_doc.get("ended_at") or inp.run_doc.get("started_at") or "not recorded")
    if processed_time == "not recorded" and inp.advisor_state.get("updated_at"):
        processed_time = f"{inp.advisor_state['updated_at']} (analysis)"

    captured_time = str(inp.captured) if inp.captured else "capture date: not recorded"
    data_basis = str(inp.basis) if inp.basis else "not stated"
    survey_time = processed_time

    fig = plt.figure(figsize=(A3_WIDTH_IN, A3_HEIGHT_IN), dpi=150)
    ax = fig.add_axes([0.06, 0.12, 0.65, 0.79])
    panel_ax = fig.add_axes([0.73, 0.12, 0.25, 0.79])
    panel_ax.axis("off")

    # 1. Determine map extent: strictly fit to orthophoto bounds (fallback: measured: true segments, then all)
    obbox: dict[str, float] | None = None
    if inp.orthophoto_path is not None and inp.orthophoto_path.is_file():
        png_bytes, obbox = warp_orthophoto_to_wgs84_png(inp.orthophoto_path, max_dim=1400)
        arr = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if arr is not None:
            rgba = cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA)
            ax.imshow(
                rgba,
                extent=(obbox["west"], obbox["east"], obbox["south"], obbox["north"]),
                origin="upper",
                zorder=1,
            )

    roads_gdf = layers["roads_status"]
    has_measured = "measured" in roads_gdf.columns

    if obbox is not None:
        xmin, ymin, xmax, ymax = obbox["west"], obbox["south"], obbox["east"], obbox["north"]
    elif has_measured and (roads_gdf["measured"] == True).any():
        measured_gdf = roads_gdf[roads_gdf["measured"] == True]
        valid = measured_gdf[measured_gdf.geometry.notna() & (~measured_gdf.geometry.is_empty)]
        tb = valid.total_bounds
        xmin, ymin, xmax, ymax = float(tb[0]), float(tb[1]), float(tb[2]), float(tb[3])
    else:
        bounds_candidates: list[tuple[float, float, float, float]] = []
        for gdf in layers.values():
            valid = gdf[gdf.geometry.notna() & (~gdf.geometry.is_empty)]
            if len(valid) > 0:
                tb = valid.total_bounds
                if all(np.isfinite(tb)):
                    bounds_candidates.append((float(tb[0]), float(tb[1]), float(tb[2]), float(tb[3])))
        if bounds_candidates:
            xmin = min(b[0] for b in bounds_candidates)
            ymin = min(b[1] for b in bounds_candidates)
            xmax = max(b[2] for b in bounds_candidates)
            ymax = max(b[3] for b in bounds_candidates)
        else:
            xmin, ymin, xmax, ymax = 0.0, 0.0, 0.01, 0.01

    dx = max(xmax - xmin, 1e-4)
    dy = max(ymax - ymin, 1e-4)
    xmin, xmax = xmin - 0.05 * dx, xmax + 0.05 * dx
    ymin, ymax = ymin - 0.05 * dy, ymax + 0.05 * dy

    # Thin sparse midpoint markers when hundreds of segments are present so print stays clean
    marker_stride = max(1, len(roads_gdf) // 90)

    for idx, (_, row) in enumerate(roads_gdf.iterrows()):
        geom = row.geometry
        if geom is None or not hasattr(geom, "is_empty") or geom.is_empty:
            continue
        st = str(row.get("display_status", "unknown"))
        spec = PDF_ROAD_STYLES.get(st, PDF_ROAD_STYLES["unknown"])
        parts = [geom] if isinstance(geom, LineString) else (list(geom.geoms) if isinstance(geom, MultiLineString) else [])
        for part in parts:
            xs, ys = part.xy
            # White casing underneath for crisp contrast over dark orthophoto pixels & B&W toner
            ax.plot(xs, ys, color="white", linewidth=spec["linewidth"] + 1.4, zorder=4, alpha=0.85)
            ax.plot(
                xs,
                ys,
                color=spec["color"],
                linestyle=spec["linestyle"],
                linewidth=spec["linewidth"],
                zorder=5,
            )
            if idx % marker_stride == 0 or st == "blocked":
                mid = part.interpolate(0.5, normalized=True)
                ax.plot(
                    mid.x,
                    mid.y,
                    marker=spec["marker"],
                    markersize=spec["markersize"],
                    markerfacecolor=spec["markerfacecolor"],
                    markeredgecolor="black",
                    markeredgewidth=0.9,
                    linestyle="None",
                    zorder=7,
                )

    # Plot cutoff places
    cp_gdf = layers["cutoff_places"]
    for _, row in cp_gdf.iterrows():
        geom = row.geometry
        if isinstance(geom, Point) and not geom.is_empty:
            ax.plot(
                geom.x,
                geom.y,
                marker="s",
                markersize=8.0,
                markerfacecolor="#fdae61",
                markeredgecolor="black",
                markeredgewidth=1.2,
                linestyle="None",
                zorder=10,
            )
            ax.annotate(
                str(row.get("name") or row.get("place_id")),
                (geom.x, geom.y),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=7.5,
                fontweight="bold",
                bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": "black", "lw": 0.5, "alpha": 0.85},
                zorder=11,
            )

    # Plot landing zones
    lz_gdf = layers["landing_zones"]
    for _, row in lz_gdf.iterrows():
        geom = row.geometry
        if geom is None or not hasattr(geom, "is_empty") or geom.is_empty:
            continue
        pt = geom if isinstance(geom, Point) else geom.representative_point()
        if isinstance(geom, Polygon):
            xs, ys = geom.exterior.xy
            ax.plot(xs, ys, color="black", linestyle="--", linewidth=1.6, zorder=9)
        ax.plot(
            pt.x,
            pt.y,
            marker="*",
            markersize=12.0,
            markerfacecolor="white",
            markeredgecolor="black",
            markeredgewidth=1.3,
            linestyle="None",
            zorder=12,
        )

    # Plot checkpoints
    chk_gdf = layers["checkpoints"]
    for _, row in chk_gdf.iterrows():
        geom = row.geometry
        if isinstance(geom, Point) and not geom.is_empty:
            ax.plot(
                geom.x,
                geom.y,
                marker="P",
                markersize=8.5,
                markerfacecolor="white",
                markeredgecolor="black",
                markeredgewidth=1.2,
                linestyle="None",
                zorder=13,
            )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    mean_lat_rad = math.radians(max(-80.0, min(80.0, 0.5 * (ymin + ymax))))
    ax.set_aspect(1.0 / max(0.2, math.cos(mean_lat_rad)), adjustable="box")

    # Coordinate grid (WGS84 degrees)
    ax.grid(True, which="major", linestyle=":", linewidth=0.7, color="#333333", alpha=0.75, zorder=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.4f}°E"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.4f}°N"))
    ax.tick_params(axis="both", labelsize=8, top=True, labeltop=True, right=True, labelright=False)
    ax.set_xlabel("Longitude (WGS84 / EPSG:4326)", fontsize=9)
    ax.set_ylabel("Latitude (WGS84 / EPSG:4326)", fontsize=9)

    _draw_scale_bar(ax, xmin, xmax, ymin, ymax)
    _draw_north_arrow(ax)

    # Header banner
    fig.suptitle(
        f"Project Typhon: road access map: {inp.project}",
        x=0.5,
        y=0.965,
        fontsize=14,
        fontweight="bold",
    )

    # Right-hand legend & metadata block (high-contrast B&W friendly)
    legend_handles = [
        Line2D(
            [0],
            [0],
            color=spec["color"],
            linestyle=spec["linestyle"],
            linewidth=spec["linewidth"],
            marker=spec["marker"],
            markersize=spec["markersize"],
            markerfacecolor=spec["markerfacecolor"],
            markeredgecolor="black",
            label=spec["label"],
        )
        for spec in PDF_ROAD_STYLES.values()
    ]
    legend_handles.extend(
        [
            Line2D(
                [0],
                [0],
                linestyle="None",
                marker="s",
                markersize=8,
                markerfacecolor="#fdae61",
                markeredgecolor="black",
                label="Cut-off / unverified place",
            ),
            Line2D(
                [0],
                [0],
                linestyle="None",
                marker="*",
                markersize=11,
                markerfacecolor="white",
                markeredgecolor="black",
                label="Landing zone candidate",
            ),
            Line2D(
                [0],
                [0],
                linestyle="None",
                marker="P",
                markersize=8.5,
                markerfacecolor="white",
                markeredgecolor="black",
                label="Survey checkpoint",
            ),
        ]
    )

    leg = panel_ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.0, 1.0),
        frameon=True,
        edgecolor="black",
        facecolor="white",
        fontsize=8.2,
        title="LEGEND (Ambulance Primary Symbol;\nB&W Line Pattern + Marker Shape)",
        title_fontsize=8.8,
    )
    leg.get_title().set_fontweight("bold")

    status_counts = roads_gdf["display_status"].value_counts().to_dict() if len(roads_gdf) else {}
    inside_gdf = roads_gdf[roads_gdf["measured"] == True] if has_measured else roads_gdf
    outside_gdf = roads_gdf[roads_gdf["measured"] == False] if has_measured else roads_gdf.iloc[0:0]
    inside_counts = inside_gdf["display_status"].value_counts().to_dict() if len(inside_gdf) else {}

    meta_lines = [
        "SURVEY & ASSESSMENT METADATA",
        "-" * 34,
        f"Project: {inp.project}",
        f"Data basis: {data_basis}",
        f"Processed: {processed_time}",
        f"Capture date: {captured_time}",
        f"CRS: WGS 84 (EPSG:4326)",
        "",
        "ACCURACY STATEMENT (from accuracy.json)",
        f"  {accuracy_line}",
        "",
        "LAYER SUMMARY",
        f"  Road segments: {len(roads_gdf)}",
    ]
    if len(outside_gdf) > 0:
        meta_lines.extend([
            f"    Inside mapped area: {len(inside_gdf)}",
            f"      unknown inside mapped area: {inside_counts.get('unknown', 0)}",
            f"    outside mapped area: {len(outside_gdf)}",
        ])
    else:
        meta_lines.extend([
            f"    open={status_counts.get('open', 0)}, partial={status_counts.get('partial', 0)},",
            f"    blocked={status_counts.get('blocked', 0)}, unknown={status_counts.get('unknown', 0)}",
        ])
    meta_lines.extend([
        f"  Cut-off/unverified places: {len(cp_gdf)}",
        f"  Landing zones: {len(lz_gdf)}",
        f"  Checkpoints: {len(chk_gdf)}",
        f"  Measurements: {len(layers['measurements'])}",
        "",
        "OPERATIONAL NOTE",
        "  Decision-support map only (not dispatch).",
        "  'unknown' is never treated as 'open'.",
    ])
    panel_ax.text(
        0.02,
        0.54,
        "\n".join(meta_lines),
        transform=panel_ax.transAxes,
        va="top",
        ha="left",
        fontsize=8.3,
        family="monospace",
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "edgecolor": "black", "linewidth": 1.0},
    )

    fig.text(
        0.06,
        0.035,
        f"{accuracy_line}  |  Processed: {processed_time}  |  Capture: {captured_time}  |  Basis: {data_basis}",
        fontsize=8.5,
        fontweight="bold",
    )

    fig.savefig(pdf_path, format="pdf")
    plt.close(fig)

    return {
        "pdf_path": pdf_path,
        "accuracy_line": accuracy_line,
        "survey_time": survey_time,
        "page_size_mm": [420, 297],
    }
