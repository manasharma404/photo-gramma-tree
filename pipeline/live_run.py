"""Replay a photo set into the growing map, at flight speed (as a live feed would deliver it) or as fast as possible.

    uv run python -m pipeline.live_run southfork_block            # as fast as possible: timing + picture
    uv run python -m pipeline.live_run rec28_campus --speed 1      # real time, one photo when its moment comes

Writes data/live_runs/<run_id>/: result.json (timings, placements), thumbs/<idx>.jpg, mosaic.jpg (check picture).
The API (live/routes.py) uses Replay in a background thread so the web map can show photos as they land.
"""
from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from pyproj import Transformer

from pipeline.live_map import LiveConfig, LiveMap

ROOT = Path(__file__).resolve().parent.parent
SETS = ROOT / "data" / "live_sets"
RUNS = ROOT / "data" / "live_runs"
READ_FLAG = {2: cv2.IMREAD_REDUCED_COLOR_2, 4: cv2.IMREAD_REDUCED_COLOR_4, 8: cv2.IMREAD_REDUCED_COLOR_8}


def list_sets() -> list[dict]:
    out = []
    for f in sorted(SETS.glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        out.append({"name": m["name"], "photos": len(m["photos"]), "seconds": m["photos"][-1]["t"], "gps": m["source"]})
    return out


class Replay:
    """One replay of one photo set. Thread-safe reads of its state for the API."""

    def __init__(self, set_name: str, speed: float = 1.0):
        path = SETS / f"{set_name}.json"
        if not path.is_file():
            raise FileNotFoundError(f"no photo set '{set_name}' (build it with python -m pipeline.live_sets)")
        self.set = json.loads(path.read_text(encoding="utf-8"))
        self.speed = speed
        self.run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S") + f"_live_{set_name}"
        self.dir = RUNS / self.run_id
        (self.dir / "thumbs").mkdir(parents=True, exist_ok=True)
        self.to_xy = Transformer.from_crs("EPSG:4326", f"EPSG:{self.set['epsg']}", always_xy=True)
        self.to_ll = Transformer.from_crs(f"EPSG:{self.set['epsg']}", "EPSG:4326", always_xy=True)
        xy = np.array([self.to_xy.transform(p["lon"], p["lat"]) for p in self.set["photos"]])
        self.xy = xy
        self.cfg = LiveConfig(s0=self.set["s0"], reduce=self.set["reduce"], cross_m=self.set["cross_m"])
        self.map = LiveMap(self.cfg, tuple(xy.mean(axis=0)))
        self.lock = threading.Lock()
        self.state = "ready"
        self.arrived = 0
        self.done_times: list[float] = []  # seconds each photo took from arrival to placed on the map
        self.placed_at: list[float] = []  # when each photo was placed (seconds since start)
        self.work_s: list[float] = []  # laptop time each photo needs (the slower of the two side-by-side workers)
        self.t_start = None
        self.error = None
        self._stop = threading.Event()
        self.thread = None

    # ---------- running ----------
    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, daemon=True, name=f"replay-{self.run_id}")
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _reader(self, q: queue.Queue) -> None:
        """photos arrive (at flight pace, or at once); each is read and prepared here, in parallel with matching"""
        sift = cv2.SIFT_create(self.cfg.n_features)
        try:
            for i, p in enumerate(self.set["photos"]):
                due = p["t"] / self.speed if self.speed > 0 else 0.0
                while self.speed > 0 and time.perf_counter() - self.t_start < due:
                    if self._stop.wait(0.02):
                        return
                if self._stop.is_set():
                    return
                # the photo arrived when the drone delivered it (its due time), even if this worker is late to it:
                # measuring from when the worker picked it up would hide a backlog
                t_arr = due if self.speed > 0 else time.perf_counter() - self.t_start
                self.arrived = i + 1  # no lock: the matching loop holds it for ~0.5 s and this must not wait
                t0 = time.perf_counter()
                img = cv2.imread(str(ROOT / p["file"]), READ_FLAG[self.cfg.reduce])
                prep = LiveMap.prepare(img, self.cfg, sift)
                prep["prepare_s"] = time.perf_counter() - t0  # read + features + thumbnail
                q.put((i, prep, t_arr))
        finally:
            q.put(None)

    def run(self) -> None:
        try:
            self.state = "running"
            self.t_start = time.perf_counter()
            q: queue.Queue = queue.Queue(maxsize=2)
            threading.Thread(target=self._reader, args=(q,), daemon=True).start()
            while (item := q.get()) is not None:
                i, prep, t_arr = item
                t0 = time.perf_counter()
                with self.lock:
                    self.map.add_prepared(prep, tuple(self.xy[i]), t_arr)
                    ph = self.map.photos[i]
                cv2.imwrite(str(self.dir / "thumbs" / f"{i}.jpg"), ph.thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
                self._refresh_cache()
                t_done = time.perf_counter() - self.t_start
                with self.lock:
                    # the two workers run side by side, so the laptop needs the longer of the two per photo
                    self.work_s.append(max(prep["prepare_s"], time.perf_counter() - t0))
                    self.placed_at.append(t_done)
                    self.done_times.append(t_done - t_arr)  # from arrival to placed on the map
            if self._stop.is_set():
                self.state = "stopped"
                return
            with self.lock:
                self.state = "finishing"
                self.finish_s = self.map.finish()
            self._refresh_cache()
            self.state = "done"
            self.save()
        except Exception as exc:  # reported on screen, never hidden
            self.error = repr(exc)
            self.state = "failed"
            raise

    # ---------- reading ----------
    def _refresh_cache(self) -> None:
        """after each re-solve: work out every photo's corners once, so the web map's polling costs nothing and
        never holds the lock the matching loop needs"""
        with self.lock:
            fp = self.map.footprints()
        xy = np.array([c for p in fp["photos"] for c in p["corners_xy"]]).reshape(-1, 2)
        lon, lat = self.to_ll.transform(xy[:, 0], xy[:, 1]) if len(xy) else ([], [])
        ll = np.round(np.c_[lon, lat], 7).reshape(-1, 4, 2).tolist() if len(xy) else []
        self._fp_cache = fp
        self._ll_cache = [{"idx": p["idx"], "corners": c} for p, c in zip(fp["photos"], ll)]

    def _due_count(self) -> int:
        """photos the drone has delivered by now (at flight pace), whether or not the laptop has got to them"""
        if self.t_start is None:
            return 0
        if self.speed <= 0:
            return self.arrived
        el = (time.perf_counter() - self.t_start) * self.speed
        return int(sum(1 for p in self.set["photos"] if p["t"] <= el))

    def status(self) -> dict:
        fp = getattr(self, "_fp_cache", None) or {"photos": [], "drone_vs_gps_median_m": None}
        due = self._due_count()
        with self.lock:
            n = len(self.placed_at)
            gaps = np.diff(self.placed_at) if n > 1 else np.array([])
            return {
                "run_id": self.run_id, "set": self.set["name"], "state": self.state, "error": self.error,
                "speed": self.speed, "photos_total": len(self.set["photos"]), "arrived": due,
                "processed": n, "placed": len(fp["photos"]),
                "behind": max(0, due - n) if self.state == "running" else 0,
                # how often a photo can be placed (must stay under 1 s for a one-photo-a-second flight)
                "seconds_per_photo_recent": round(float(np.median(gaps[-20:])), 2) if len(gaps) else None,
                "seconds_per_photo_all": round(float(self.placed_at[-1] / n), 2) if n and self.speed == 0 else
                (round(float(np.mean(gaps)), 2) if len(gaps) else None),
                # laptop time per photo; under the time between photos (1 s) means it keeps pace with room to spare
                "work_s_per_photo_recent": round(float(np.median(self.work_s[-20:])), 2) if self.work_s else None,
                "work_s_per_photo_max": round(float(np.max(self.work_s)), 2) if self.work_s else None,
                "arrival_to_placed_s_recent": round(float(np.median(self.done_times[-20:])), 2) if n else None,
                "arrival_to_placed_s_max": round(float(np.max(self.done_times)), 2) if n else None,
                "drone_vs_gps_median_m": None if fp["drone_vs_gps_median_m"] is None else round(fp["drone_vs_gps_median_m"], 2),
                "gps_source": self.set["source"],
                "label": "Rough map: about 10 to 20 m, for seeing, not for measuring",
            }

    def footprints_lonlat(self) -> list[dict]:
        return list(getattr(self, "_ll_cache", []))

    def save(self) -> None:
        st = self.status()
        with self.lock:
            fp = self.map.footprints()
            pl = np.array(self.map.pairs) if self.map.pairs else np.zeros((0, 4))
            tm = [p.timings for p in self.map.photos]
        used = pl[pl[:, 3] >= self.cfg.min_inliers] if len(pl) else pl
        res = {**st, "pairs_tried": int(len(pl)), "pairs_used": int(len(used)),
               "seconds_breakdown_mean": {k: round(float(np.mean([t[k] for t in tm])), 3) for k in ("features_s", "matching_s", "solve_s")},
               "solve_s_last": round(tm[-1]["solve_s"], 3) if tm else None,
               "finish_s": round(getattr(self, "finish_s", 0.0), 3), "scale_fix": fp["scale_fix"],
               "lookahead_estimated": fp["lookahead_estimated"], "footprints": fp["photos"]}
        (self.dir / "result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    def render(self, res_m: float) -> Path:
        """check picture: nearest-centre mosaic of the thumbnails (not part of the live loop)"""
        fp = self.map.footprints()["photos"]
        allc = np.array([c for p in fp for c in p["corners_xy"]])
        lo, hi = np.percentile(allc, 0.5, axis=0) - 10, np.percentile(allc, 99.5, axis=0) + 10
        W, H = int((hi[0] - lo[0]) / res_m), int((hi[1] - lo[1]) / res_m)
        mos = np.zeros((H, W, 3), np.uint8)
        best = np.full((H, W), np.inf, np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        for p in fp:
            th = self.map.photos[p["idx"]].thumb
            th_h, th_w = th.shape[:2]
            c = np.array(p["corners_xy"])
            dst = np.float32(np.c_[(c[:3, 0] - lo[0]) / res_m, (hi[1] - c[:3, 1]) / res_m])
            M = cv2.getAffineTransform(np.float32([[0, 0], [th_w, 0], [th_w, th_h]]), dst)
            warped = cv2.warpAffine(th, M, (W, H))
            cov = cv2.warpAffine(np.full((th_h, th_w), 255, np.uint8), M, (W, H)) > 0
            cc = c.mean(axis=0)
            d2 = (xx - (cc[0] - lo[0]) / res_m) ** 2 + (yy - (hi[1] - cc[1]) / res_m) ** 2
            take = cov & (d2 < best)
            mos[take] = warped[take]
            best[take] = d2[take]
        out = self.dir / "mosaic.jpg"
        cv2.imwrite(str(out), mos, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set")
    ap.add_argument("--speed", type=float, default=0.0, help="1 = real time; 0 = as fast as possible (timing)")
    ap.add_argument("--res", type=float, default=0.25, help="check-picture resolution, metres per pixel")
    a = ap.parse_args()
    r = Replay(a.set, speed=a.speed)
    r.run()
    r.render(a.res)
    res = json.loads((r.dir / "result.json").read_text(encoding="utf-8"))
    res.pop("footprints")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
