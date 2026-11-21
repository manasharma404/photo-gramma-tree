"""The growing map over HTTP: start a replay of a small synthetic photo set and watch every photo get placed."""
import json
import time

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
from fastapi.testclient import TestClient  # noqa: E402
from pyproj import Transformer  # noqa: E402

from api.main import create_app  # noqa: E402
from pipeline import live_run  # noqa: E402
from tests.test_live_map import RES, _flight, _ground  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    rng = np.random.default_rng(7)
    frames, gps, _ = _flight(_ground(seed=8), rng)
    to_ll = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)
    photos = []
    for i, f in enumerate(frames):
        p = tmp_path / f"f{i:04d}.jpg"
        cv2.imwrite(str(p), f)
        lon, lat = to_ll.transform(500000 + gps[i][0], 3150000 + gps[i][1])
        photos.append({"file": str(p), "t": float(i), "lon": lon, "lat": lat})
    sets = tmp_path / "sets"
    sets.mkdir()
    (sets / "synthetic.json").write_text(json.dumps({"name": "synthetic", "epsg": 32643, "s0": RES, "reduce": 2,
                                                     "cross_m": 20.0, "source": "synthetic", "photos": photos}))
    monkeypatch.setattr(live_run, "SETS", sets)
    monkeypatch.setattr(live_run, "RUNS", tmp_path / "runs")
    monkeypatch.setitem(live_run.READ_FLAG, 2, cv2.IMREAD_COLOR)  # synthetic frames are already small
    return TestClient(create_app()), len(frames)


def test_replay_places_photos_and_serves_them(client):
    c, n = client
    assert c.get("/health").json()["mounted_routers"]["live"] is True
    assert [s["name"] for s in c.get("/live/sets").json()] == ["synthetic"]
    st = c.post("/live/start", json={"set": "synthetic", "speed": 0}).json()
    run_id = st["run_id"]
    for _ in range(600):
        st = c.get("/live/status").json()
        if st["state"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["state"] == "done", st
    assert st["placed"] == n and st["behind"] == 0
    assert "not for measuring" in st["label"]
    fp = c.get("/live/footprints").json()
    assert fp["run_id"] == run_id and len(fp["photos"]) == n
    lon, lat = fp["photos"][0]["corners"][0]
    assert 70 < lon < 80 and 25 < lat < 32  # UTM 43N, back in degrees
    r = c.get(f"/live/thumb/{run_id}/0.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert c.get(f"/live/thumb/{run_id}/9999.jpg").status_code == 404
    assert c.get("/live/thumb/other_run/0.jpg").status_code == 404


def test_unknown_set_and_bad_names_are_refused(client):
    c, _ = client
    assert c.post("/live/start", json={"set": "nope", "speed": 1}).status_code == 404
    assert c.post("/live/start", json={"set": "../etc", "speed": 1}).status_code == 422
    assert c.post("/live/start", json={"set": "synthetic", "speed": -1}).status_code == 422
