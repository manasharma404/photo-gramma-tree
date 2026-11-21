"""Check a growing-map run against a measured orthophoto (the Test 7c measure).

For each placed photo: match it to the measured orthophoto near where the growing map put it, and compare the
growing map's ground position of the matched points with the orthophoto's (median per photo).

    uv run python scripts/eval_live_map.py data/live_runs/<run_id> \
        data/projects/southfork_f01_4_middle/odm_orthophoto/odm_orthophoto.tif
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
READ = {2: cv2.IMREAD_REDUCED_GRAYSCALE_2, 4: cv2.IMREAD_REDUCED_GRAYSCALE_4, 8: cv2.IMREAD_REDUCED_GRAYSCALE_8}
RR = 0.125  # metres per pixel the orthophoto is read at


def main() -> None:
    run, ortho = Path(sys.argv[1]), Path(sys.argv[2])
    res = json.loads((run / "result.json").read_text(encoding="utf-8"))
    sset = json.loads((ROOT / "data" / "live_sets" / f"{res['set']}.json").read_text(encoding="utf-8"))
    red = sset["reduce"]
    ref = rasterio.open(ortho)
    rh, rw = int(ref.height * ref.res[1] / RR), int(ref.width * ref.res[0] / RR)
    rgb = ref.read([1, 2, 3], out_shape=(3, rh, rw))
    alpha = ref.read(ref.count, out_shape=(rh, rw)) if ref.count >= 4 else np.full((rh, rw), 255, np.uint8)
    sift = cv2.SIFT_create(30000)
    rk, rd = sift.detectAndCompute(cv2.cvtColor(np.transpose(rgb, (1, 2, 0)), cv2.COLOR_RGB2GRAY), (alpha > 0).astype(np.uint8) * 255)
    rp = np.float32([q.pt for q in rk])
    to_xy = lambda p: np.c_[ref.bounds.left + p[:, 0] * RR, ref.bounds.top - p[:, 1] * RR]  # noqa: E731
    flann = cv2.FlannBasedMatcher(dict(algorithm=1, trees=4), dict(checks=32))
    fsift = cv2.SIFT_create(2500)
    per_photo = []
    for fp in res["footprints"]:
        img = cv2.imread(str(ROOT / sset["photos"][fp["idx"]]["file"]), READ[red])
        h, w = img.shape[:2]
        C = np.array(fp["corners_xy"])
        M = cv2.getAffineTransform(np.float32([[0, 0], [w, 0], [w, h]]), np.float32(C[:3]))
        ground = lambda px: (M[:, :2] @ np.asarray(px, float).T).T + M[:, 2]  # noqa: E731
        c = ground([[w / 2, h / 2]])[0]
        cpx = np.array([(c[0] - ref.bounds.left) / RR, (ref.bounds.top - c[1]) / RR])
        near = np.flatnonzero(np.hypot(rp[:, 0] - cpx[0], rp[:, 1] - cpx[1]) < 200 / RR)
        if len(near) < 100:
            continue
        k, d = fsift.detectAndCompute(img, None)
        if d is None:
            continue
        kp = np.float32([q.pt for q in k])
        good = [m for pr in flann.knnMatch(d, rd[near], k=2) if len(pr) == 2 for m, nn in [pr] if m.distance < 0.7 * nn.distance]
        if len(good) < 20:
            continue
        a, b = kp[[m.queryIdx for m in good]], rp[near][[m.trainIdx for m in good]]
        H, inl = cv2.findHomography(a, b, cv2.RANSAC, 4)
        if H is None or inl.sum() < 20:
            continue
        a, b = a[inl.ravel() > 0], b[inl.ravel() > 0]
        per_photo.append(float(np.median(np.linalg.norm(ground(a) - to_xy(b), axis=1))))
    out = {"run": run.name, "reference": str(ortho).replace("\\", "/"), "photos_compared": len(per_photo),
           "photos_placed": len(res["footprints"]),
           "typical_point_per_photo_m": {"median": round(float(np.median(per_photo)), 2),
                                         "p90": round(float(np.percentile(per_photo, 90)), 2),
                                         "max": round(float(np.max(per_photo)), 2)}}
    (run / "eval_vs_measured.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
