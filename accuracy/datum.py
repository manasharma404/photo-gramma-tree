"""Put USGS RTK checkpoints into the same frame as our map before comparing.

The USGS metadata (SEKI_SouthFork_DebrisFlow_GNSS_metadata.xml) states the RTK latitude/longitude are
NAD83(2011) (EPSG:6319) and ellipsoid heights are on GRS80. Our map is placed by the cameras' GPS, which
reports WGS84; current WGS84 realisations agree with ITRF2020 to a few centimetres. Near South Fork in 2024
the two frames differ by about 1.5 m horizontally and 0.6 m vertically, so comparing them directly would
blame the datum difference on the map.

This converts the *reference* into the map's frame. It never moves the map: checkpoints still only
measure error.
"""
from pyproj import Transformer

SOURCE_CRS = "EPSG:6319"  # NAD83(2011) geographic 3D, as stated in the USGS metadata
TARGET_CRS = "EPSG:9989"  # ITRF2020 geographic 3D (= WGS84 G2296 to a few cm)
SURVEY_EPOCH = 2024.33  # survey and flights on 30 Apr 2024; plate motion over days is negligible
NOTE = ("RTK checkpoints converted from NAD83(2011) (stated in the USGS metadata) to ITRF2020/WGS84 at epoch "
        f"{SURVEY_EPOCH} before comparison (about 1.5 m west and 0.6 m down at South Fork). The reference was "
        "converted; the map was not corrected.")

_T = Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)


def rtk_to_wgs84(row):
    """(lon, lat, ellipsoid height) of a USGS RTK CSV row, in the map's GPS frame."""
    lon, lat, h, _ = _T.transform(float(row["longitude"]), float(row["latitude"]),
                                  float(row["ellipsoid_ht_m"]), SURVEY_EPOCH)
    return lon, lat, h
