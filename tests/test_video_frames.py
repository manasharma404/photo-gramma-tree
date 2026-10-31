"""Frame windowing for pipeline.video_frames (no video needed)."""
from pipeline.video_frames import GEOD, windows


def track_moving(n, step_m, lat0=28.0, lon0=77.0):
    pts, lon = [], lon0
    for _ in range(n):
        pts.append({"lat": lat0, "lon": lon})
        lon = GEOD.fwd(lon, lat0, 90, step_m)[0]
    return pts


def test_windows_by_distance():
    w = windows(track_moving(41, 0.5), fps=100, spacing_m=2.0)  # 20 m at 0.5 m/frame, fps high so time never triggers
    assert len(w) == 10
    assert len(w[0]) == 5  # the starting frame plus four 0.5 m steps
    assert all(len(x) == 4 for x in w[1:])


def test_windows_when_hovering_fall_back_to_time():
    w = windows(track_moving(60, 0.0), fps=10, spacing_m=2.0)  # 6 s hover at 10 fps
    assert len(w) == 6


def test_no_gps_frames_still_grouped():
    t = track_moving(10, 0.5) + [{"lat": None, "lon": None}] * 5
    assert sum(len(x) for x in windows(t, fps=10, spacing_m=2.0)) == 15
