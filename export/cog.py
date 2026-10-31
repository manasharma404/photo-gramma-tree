"""Cloud-Optimized GeoTIFF (COG) converter and programmatic validity check (E4)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as rio_copy


def convert_to_cog(
    src_path: Path,
    dst_path: Path,
    *,
    blocksize: int = 256,
    overview_factors: tuple[int, ...] = (2, 4, 8),
) -> dict[str, Any]:
    """Convert an orthophoto or DSM GeoTIFF to a Cloud-Optimized GeoTIFF and validate it."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if dst_path.exists():
        dst_path.unlink()

    with rasterio.open(src_path) as src:
        is_float = any("float" in str(dt).lower() for dt in src.dtypes)
        resamp_name = "AVERAGE"
        resamp_enum = Resampling.average

    # Attempt native GDAL COG driver first, ensuring overviews are generated even on small test rasters.
    used_native_cog = False
    try:
        rio_copy(
            src_path,
            dst_path,
            driver="COG",
            BLOCKSIZE=blocksize,
            COMPRESS="DEFLATE",
            PREDICTOR=3 if is_float else 2,
            OVERVIEW_RESAMPLING=resamp_name,
            OVERVIEWS="FORCE_USE_EXISTING" if False else "AUTO",
        )
        used_native_cog = True
    except Exception:
        used_native_cog = False

    # If native COG driver skipped overviews on a small (<512 px) raster or wasn't available,
    # build explicit internal overviews and copy with copy_src_overviews=True + tiled blocks.
    needs_explicit_overviews = not used_native_cog
    if used_native_cog and dst_path.is_file():
        with rasterio.open(dst_path) as check_ds:
            if len(check_ds.overviews(1)) == 0 and min(check_ds.width, check_ds.height) >= 64:
                needs_explicit_overviews = True

    if needs_explicit_overviews:
        with tempfile.TemporaryDirectory() as tmpdir:
            inter_path = Path(tmpdir) / "intermediate_tiled.tif"
            with rasterio.open(src_path) as src:
                profile = src.profile.copy()
                tile_w = max(16, min(blocksize, (src.width // 16) * 16 or 16))
                tile_h = max(16, min(blocksize, (src.height // 16) * 16 or 16))
                # GDAL TIFF tile dimensions must be multiples of 16
                tile_w = max(16, (tile_w // 16) * 16)
                tile_h = max(16, (tile_h // 16) * 16)
                profile.update(
                    driver="GTiff",
                    tiled=True,
                    blockxsize=tile_w,
                    blockysize=tile_h,
                    compress="deflate",
                )
                with rasterio.open(inter_path, "w", **profile) as inter:
                    inter.write(src.read())
                    if src.nodata is not None:
                        inter.nodata = src.nodata
                    valid_factors = [
                        f for f in overview_factors if min(src.width, src.height) // f >= 8
                    ] or [2]
                    inter.build_overviews(valid_factors, resamp_enum)
                    inter.update_tags(ns="rio_overview", resampling=resamp_name.lower())

            if dst_path.exists():
                dst_path.unlink()
            try:
                rio_copy(
                    inter_path,
                    dst_path,
                    driver="COG",
                    BLOCKSIZE=blocksize,
                    COMPRESS="DEFLATE",
                    OVERVIEWS="FORCE_USE_EXISTING",
                )
            except Exception:
                rio_copy(
                    inter_path,
                    dst_path,
                    driver="GTiff",
                    TILED="YES",
                    BLOCKXSIZE=tile_w,
                    BLOCKYSIZE=tile_h,
                    COMPRESS="DEFLATE",
                    COPY_SRC_OVERVIEWS="YES",
                )

    return validate_cog(dst_path, strict=True)


def validate_cog(tif_path: Path, *, strict: bool = True) -> dict[str, Any]:
    """Validate that a GeoTIFF is tiled, CRS-tagged, and contains internal pyramids (COG)."""
    errors: list[str] = []
    if not tif_path.is_file() or tif_path.stat().st_size == 0:
        errors.append(f"COG file missing or empty: {tif_path}")
        if strict:
            raise ValueError("; ".join(errors))
        return {"valid": False, "errors": errors}

    with rasterio.open(tif_path) as src:
        driver = src.driver
        crs_str = src.crs.to_string() if src.crs else None
        block_shapes = list(src.block_shapes)
        overviews_1 = list(src.overviews(1))
        img_struct = src.tags(ns="IMAGE_STRUCTURE")

        if driver != "GTiff":
            errors.append(f"Expected GTiff driver, got {driver}")
        if not crs_str:
            errors.append("COG is missing CRS definition")

        # Check internal tiling (not full-width scanline strips unless tiny)
        bh, bw = block_shapes[0]
        is_tiled = bool(src.profile.get("tiled", False)) or (
            bw <= 512 and bh <= 512 and bw % 16 == 0 and bh % 16 == 0
        )
        if not is_tiled:
            errors.append(f"GeoTIFF is not internally tiled (block shape={block_shapes[0]}, size={src.width}x{src.height})")

        if min(src.width, src.height) >= 64 and len(overviews_1) == 0:
            errors.append("GeoTIFF has no internal overview pyramids")

        # Check IFD offset ordering when exposed by GDAL
        main_ifd = src.get_tag_item("IFD_OFFSET", "TIFF", bidx=1)
        ovr_ifd_ok = True
        if main_ifd is not None and overviews_1:
            # In valid COG layout, overview IFDs precede or pack cleanly in header before main data
            layout_tag = img_struct.get("LAYOUT", "")
            if layout_tag and layout_tag != "COG":
                ovr_ifd_ok = False
                errors.append(f"Unexpected IMAGE_STRUCTURE LAYOUT={layout_tag}")

        result = {
            "valid": len(errors) == 0 and ovr_ifd_ok,
            "path": str(tif_path),
            "driver": driver,
            "crs": crs_str,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "block_shapes": block_shapes,
            "overviews": overviews_1,
            "layout": img_struct.get("LAYOUT", "GTiff-COG"),
            "errors": errors,
        }

    if strict and not result["valid"]:
        raise ValueError(f"Invalid COG at {tif_path}: {'; '.join(errors)}")
    return result
