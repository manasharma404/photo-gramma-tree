"""The growing-map engine on a synthetic flight where the true position of every photo is known."""
import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from pipeline.live_map import LiveConfig, LiveMap  # noqa: E402

RES = 0.1  # metres per ground pixel


def _ground(seed=0, w=1700, h=1000):
    rng = np.random.default_rng(seed)
    g = rng.normal(128, 40, (h, w)).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 2.0)
    for _ in range(900):  # blobs and boxes give the matcher something distinctive
        x, y, r = int(rng.integers(0, w)), int(rng.integers(0, h)), int(rng.integers(3, 14))
        c = int(rng.integers(0, 255))
        if rng.random() < 0.5:
            cv2.circle(g, (x, y), r, c, -1)
        else:
            cv2.rectangle(g, (x, y), (x + r, y + int(r * 1.6)), c, -1)
    g = np.clip(g, 0, 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def _flight(ground, rng, gps_noise_m=2.0):
    """three parallel lines, back and forth; returns frames, noisy GPS (metres) and true centres (metres)"""
    fw, fh = 320, 240
    frames, gps, truth = [], [], []
    for line, (yc, heading) in enumerate([(300, 0.0), (420, 180.0), (540, 0.0)]):
        xs = list(range(200, 1500, 80))
        if heading == 180.0:
            xs = xs[::-1]
        for xc in xs:
            M = cv2.getRotationMatrix2D((float(xc), float(yc)), heading, 1.0)
            M[:, 2] += [fw / 2 - xc, fh / 2 - yc]
            frames.append(cv2.warpAffine(ground, M, (fw, fh)))
            t = np.array([xc * RES, -yc * RES])
            truth.append(t)
            gps.append(t + rng.normal(0, gps_noise_m, 2))
    return frames, np.array(gps), np.array(truth)


def test_places_every_photo_near_its_true_position_and_solves_fast():
    rng = np.random.default_rng(1)
    ground = _ground()
    frames, gps, truth = _flight(ground, rng)
    lm = LiveMap(LiveConfig(s0=RES, reduce=1, cross_m=20.0, lookahead_after=10_000), tuple(gps.mean(axis=0)))
    solve_s = []
    for i, f in enumerate(frames):
        solve_s.append(lm.add_photo(f, tuple(gps[i]), float(i))["solve_s"])
    lm.finish()
    fp = lm.footprints()
    assert len(fp["photos"]) == len(frames)
    centres = np.array([np.mean(p["corners_xy"], axis=0) for p in fp["photos"]])
    err = np.linalg.norm(centres - truth[[p["idx"] for p in fp["photos"]]], axis=1)
    # GPS alone is 2 m noisy per photo; solving all photos together must do better than that
    assert np.median(err) < 1.5, np.median(err)
    assert max(solve_s) < 0.5  # a full re-solve per photo, in well under a second


def test_frame_sizes_come_out_right():
    rng = np.random.default_rng(2)
    frames, gps, _ = _flight(_ground(seed=3), rng)
    lm = LiveMap(LiveConfig(s0=RES, reduce=1, cross_m=20.0, lookahead_after=10_000), tuple(gps.mean(axis=0)))
    for i, f in enumerate(frames):
        lm.add_photo(f, tuple(gps[i]), float(i))
    lm.finish()
    widths = [np.linalg.norm(np.subtract(p["corners_xy"][1], p["corners_xy"][0])) for p in lm.footprints()["photos"]]
    assert np.median(widths) == pytest.approx(320 * RES, rel=0.05)  # 32 m wide on the ground


def test_a_photo_that_matches_nothing_is_not_placed():
    rng = np.random.default_rng(4)
    frames, gps, _ = _flight(_ground(seed=5), rng)
    frames[5] = np.full_like(frames[5], 127)  # blank: lens cap, cloud
    lm = LiveMap(LiveConfig(s0=RES, reduce=1, cross_m=20.0, lookahead_after=10_000), tuple(gps.mean(axis=0)))
    for i, f in enumerate(frames):
        lm.add_photo(f, tuple(gps[i]), float(i))
    placed = {p["idx"] for p in lm.footprints()["photos"]}
    assert 5 not in placed
    assert len(placed) == len(frames) - 1
