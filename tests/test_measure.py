"""measure.core on synthetic terrain with known answers."""
import jsonschema
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from measure import core

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "contracts/measurement.schema.json").read_text(encoding="utf-8"))
X0, Y0, PX = 342000.0, 4023800.0, 0.1  # near South Fork, UTM 11N
TO_WGS = Transformer.from_crs(32611, 4326, always_xy=True).transform


def write(path, arr):
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
                       dtype="float32", crs="EPSG:32611", transform=from_origin(X0, Y0, PX, PX), nodata=-9999) as ds:
        ds.write(arr.astype("float32"), 1)
    return path


def ll(x, y):
    return list(TO_WGS(X0 + x, Y0 - y))


def grid(n):
    y, x = np.mgrid[0:n, 0:n] * PX
    return x, y


def test_volume_block(tmp_path):
    x, y = grid(300)  # 30 m
    ground = 1000 + 0.03 * x + 0.01 * y  # tilted plane: the rim fit must follow it
    dsm = ground.copy()
    dsm[(x >= 10) & (x < 12) & (y >= 10) & (y < 13)] += 1.5  # 2 x 3 x 1.5 m = 9 m3
    s = core.Surfaces(write(tmp_path / "dsm.tif", dsm))
    poly = {"type": "Polygon", "coordinates": [[ll(8, 8), ll(14, 8), ll(14, 15), ll(8, 15), ll(8, 8)]]}
    m = core.volume(s, poly)
    jsonschema.validate(m, SCHEMA)
    assert m["result"]["volume_m3"] == pytest.approx(9.0, rel=0.05)
    assert m["result"]["max_height_m"] == pytest.approx(1.5, abs=0.05)
    assert m["tolerance"]["value"] is None  # no accuracy.json -> no guessed tolerance


def test_span_channel(tmp_path):
    x, y = grid(400)  # 40 m
    dsm = np.full(x.shape, 1003.0)
    channel = (x >= 14) & (x < 26)  # 12 m wide, 3 m deep, flat bed
    dsm[channel] = 1000.0
    s = core.Surfaces(write(tmp_path / "dsm.tif", dsm))
    m = core.span(s, {"type": "LineString", "coordinates": [ll(5, 20), ll(35, 20)]})
    jsonschema.validate(m, SCHEMA)
    assert m["result"]["span_m"] == pytest.approx(12.0, abs=0.3)
    assert m["result"]["bed_elevation_m"] == pytest.approx(1000.0)
    assert m["result"]["panel_estimate"]["count"] == 6  # ceil((12 + 2*3) / 3.048)
    assert (ROOT / m["result"]["profile_png"]).exists()


def test_span_flat_has_no_span(tmp_path):
    x, _ = grid(200)
    s = core.Surfaces(write(tmp_path / "dsm.tif", 1000 + 0.001 * x))
    m = core.span(s, {"type": "LineString", "coordinates": [ll(2, 10), ll(18, 10)]})
    assert m["result"]["span_m"] is None and m["result"]["note"]


def test_working_space(tmp_path):
    x, y = grid(800)  # 80 m
    ground = np.full(x.shape, 1000.0)
    dsm = ground.copy()
    dsm[(x > 50)] += 5.0  # trees east of x = 50 m
    s = core.Surfaces(write(tmp_path / "dsm.tif", dsm), write(tmp_path / "dtm.tif", ground))
    m = core.working_space(s, {"type": "Point", "coordinates": ll(25, 40)}, width_m=10, length_m=20)
    jsonschema.validate(m, SCHEMA)
    assert m["result"]["meets_requirement"] is True
    assert m["result"]["width_m"] >= 10 and m["result"]["length_m"] >= 20


def test_landing_zone_open_field(tmp_path):
    x, y = grid(1200)  # 120 m flat field
    ground = np.full(x.shape, 1000.0)
    s = core.Surfaces(write(tmp_path / "dsm.tif", ground), write(tmp_path / "dtm.tif", ground))
    m = core.landing_zones(s, "light_utility")
    jsonschema.validate(m, SCHEMA)
    cands = m["result"]["candidates"]
    assert cands, "an empty flat field must have a candidate"
    assert cands[0]["fato_side_m"] >= 1.5 * 16.0
    assert cands[0]["approach_beyond_map"] is True  # 245 m doesn't fit in a 120 m map


def test_landing_zone_rejects_obstacle_field(tmp_path):
    x, y = grid(600)
    ground = np.full(x.shape, 1000.0)
    dsm = ground.copy()
    dsm[::50, :] += 3.0  # a 3 m obstacle line every 5 m: nowhere is clear
    s = core.Surfaces(write(tmp_path / "dsm.tif", dsm), write(tmp_path / "dtm.tif", ground))
    assert core.landing_zones(s, "light_utility")["result"]["candidates"] == []
