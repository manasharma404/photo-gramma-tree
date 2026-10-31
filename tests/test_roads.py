"""roads.segments on synthetic height models with known answers."""
import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import LineString

from roads import segments

PX = 0.1  # 10 cm, like our DSM
SIZE = 400  # 40 m x 40 m


def raster(arr):
    mem = MemoryFile()
    with mem.open(driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype="float32",
                  crs="EPSG:32611", transform=from_origin(0, SIZE * PX, PX, PX), nodata=-9999) as ds:
        ds.write(arr.astype("float32"), 1)
    return mem.open()


def ground():
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    return 1000 + 0.02 * x * PX  # gentle 2% slope along x


def road():
    # 30 m road along x at y = 20 m (row 200), 5 m wide
    return LineString([(5, 20), (35, 20)])


def test_debris_half_width():
    z = ground()
    # debris: 1 m high, covers y 20..22.5 m (left half of the 5 m road), x 15..20 m
    z[175:200, 150:200] += 1.0
    m = segments.measure_segment(road(), 5.0, raster(z), raster(ground()))
    assert m["coverage_fraction"] == pytest.approx(1.0)
    assert m["min_clear_width_m"] == pytest.approx(2.5, abs=0.15)
    assert m["max_obstruction_m"] == pytest.approx(1.0, abs=0.05)
    assert m["obstructed_length_m"] == pytest.approx(5.0, abs=1.5)
    assert m["debris_volume_m3"] == pytest.approx(12.5, rel=0.25)


def test_clear_road():
    m = segments.measure_segment(road(), 5.0, raster(ground()), raster(ground()))
    assert m["max_obstruction_m"] == 0.0
    assert m["min_clear_width_m"] == pytest.approx(5.0, abs=0.15)
    assert m["debris_volume_m3"] == 0.0


def test_canopy_is_not_visible_not_blocked():
    z = ground()
    z[150:250, 100:200] += 12.0  # a tree crown over 10 m of road: DSM high, DTM is ground
    m = segments.measure_segment(road(), 5.0, raster(z), raster(ground()))
    assert m["coverage_fraction"] == pytest.approx(2 / 3, abs=0.05)
    assert m["max_obstruction_m"] == 0.0


def test_hillside_path_is_not_debris():
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    z = 1000 + 0.02 * x * PX + 0.20 * (SIZE - y) * PX  # 20% sideways slope across the road
    m = segments.measure_segment(road(), 5.0, raster(z), raster(z))
    assert m["max_obstruction_m"] == 0.0
    assert m["min_clear_width_m"] == pytest.approx(5.0, abs=0.15)


def test_green_vegetation_is_not_visible_not_blocked():
    z = ground()
    z[175:225, 150:250] += 1.5  # a 1.5 m bush (below the 3 m canopy rule) ...
    rgb = np.zeros((3, SIZE, SIZE), np.uint8)
    rgb[:] = np.array([180, 170, 150])[:, None, None]  # bare soil
    rgb[:, 175:225, 150:250] = np.array([60, 140, 50])[:, None, None]  # ... that is green in the orthophoto
    mem = MemoryFile()
    with mem.open(driver="GTiff", width=SIZE, height=SIZE, count=3, dtype="uint8", crs="EPSG:32611",
                  transform=from_origin(0, SIZE * PX, PX, PX)) as ds:
        ds.write(rgb)
    m = segments.measure_segment(road(), 5.0, raster(z), raster(ground()), mem.open())
    assert m["max_obstruction_m"] == 0.0
    assert m["coverage_fraction"] < 0.9


def test_no_data_gives_nulls():
    m = segments.measure_segment(road(), 5.0, raster(np.full((SIZE, SIZE), -9999.0)))
    assert m["coverage_fraction"] == 0.0
    assert m["min_clear_width_m"] is None and m["debris_volume_m3"] is None


def test_split_line():
    parts = segments.split_line(LineString([(0, 0), (120, 0)]), 50)
    assert len(parts) == 3 and all(p.length == pytest.approx(40) for p in parts)
