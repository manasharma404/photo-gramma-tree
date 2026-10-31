"""Tile maths for pipeline.tiles (no raster needed)."""
import pytest

from pipeline import tiles


def test_tile_zero_is_the_world():
    b = tiles.tile_bounds(0, 0, 0)
    assert b == pytest.approx((-tiles.HALF, -tiles.HALF, tiles.HALF, tiles.HALF))


def test_tiles_cover_bounds():
    b = tiles.tile_bounds(18, 1000, 2000)
    inner = (b[0] + 1, b[1] + 1, b[2] - 1, b[3] - 1)
    assert tiles.tiles_for(inner, 18) == [(1000, 2000)]
    assert len(tiles.tiles_for(inner, 19)) == 4
