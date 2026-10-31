"""Unit tests for accuracy helpers (no orthophoto needed)."""
import numpy as np
import pytest

from accuracy import compute_errors, find_targets


def test_rms():
    assert compute_errors.rms([3.0, 4.0]) == pytest.approx(np.sqrt(12.5))
    assert compute_errors.rms([]) is None


def test_datum_moves_rtk_about_1_5_m_west_and_0_6_m_down():
    from pyproj import Geod
    from accuracy.datum import rtk_to_wgs84
    row = {"longitude": "-118.76384247", "latitude": "36.35005250", "ellipsoid_ht_m": "1092.296"}  # USGS base SFKW
    lon, lat, h = rtk_to_wgs84(row)
    az, _, dist = Geod(ellps="GRS80").inv(-118.76384247, 36.35005250, lon, lat)
    assert dist == pytest.approx(1.52, abs=0.05)
    assert az % 360 == pytest.approx(279, abs=5)
    assert h - 1092.296 == pytest.approx(-0.63, abs=0.05)


def _scene(px_m=0.05, size=400):
    """Yellowish sand with one white target (with bluish triangles) and one white rock."""
    rgb = np.zeros((size, size, 3), np.uint8)
    rgb[:] = (200, 180, 140)
    t = slice(100, 112)  # 0.6 m target
    rgb[t, t] = (245, 245, 250)
    rgb[100:106, 100:106] = (90, 100, 140)  # bluish triangle stand-in
    rgb[300:312, 300:312] = (250, 245, 225)  # white-yellow rock
    return rgb, np.ones((size, size), bool), px_m


def test_detector_prefers_white_blue_target_over_rock():
    rgb, valid, px_m = _scene()
    cands = find_targets.candidates_in(rgb, valid, px_m)
    assert cands, "target not found"
    row, col, _, _ = cands[0]
    assert 98 <= row <= 114 and 98 <= col <= 114
    assert all(not (290 <= r <= 320 and 290 <= c <= 320) for r, c, _, _ in cands)
