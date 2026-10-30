"""Unit tests for the ODM runner's parsing helpers (no Docker needed)."""
import pytest

from pipeline import run_odm


@pytest.mark.parametrize("text, gb", [
    ("3.2GiB / 11.68GiB", 3.2),
    ("512MiB / 11.68GiB", 0.5),
    ("1.5GB / 12GB", 1.5e9 / 1024 ** 3),
])
def test_parse_mem_gb(text, gb):
    assert run_odm.parse_mem_gb(text) == pytest.approx(gb)


def test_parse_mem_gb_empty():
    assert run_odm.parse_mem_gb("--") is None


def test_stage_of():
    assert run_odm.stage_of("2026-10-31 03:00:00,000 INFO: Running opensfm stage") == "opensfm"
    assert run_odm.stage_of("[INFO]    Running odm_orthophoto stage") == "odm_orthophoto"
    assert run_odm.stage_of("[INFO]    Finished opensfm stage") is None


def test_tiers_never_use_gcp():
    for opts in run_odm.TIERS.values():
        assert not any(o.startswith("--gcp") for o in opts)
