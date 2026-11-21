"""The map that grows while the drone flies (F1): each photo is placed on the ground about a second after it arrives.

Method (Test 7c in docs/validation.md, made fast enough to keep pace):
- every photo gets its own flat placement on the ground: shift, turn and size (4 numbers);
- photos are matched to the two photos before them and to up to three earlier photos from neighbouring flight
  lines (found by GPS distance); each matched point says "these two photos put this point in the same place";
- each photo's GPS says "the point under the drone is here"; the camera may look ahead of the drone, and how far
  is estimated from the data once enough photos have arrived (the USGS camera looks about 38 m ahead);
- ALL placements are re-solved together after every photo. Test 7e re-solved with an iterative solver and fell
  behind (23.9 s at 298 photos). Here every matched point adds to one small square table (the "normal equations",
  4 numbers per photo), so a full re-solve is a single direct solve of that table: milliseconds at 300 photos.

The result is rough: about 10 to 20 m on the USGS block (Test 7c). It is for seeing, never for measuring.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy.linalg import cho_factor, cho_solve

NP = 4  # parameters per photo: x = a*px - b*py + tx ; y = b*px + a*py + ty


@dataclass
class LiveConfig:
    s0: float  # rough metres per reduced pixel; only keeps the numbers well scaled (GPS fixes the real size)
    reduce: int = 4  # read photos at 1/reduce size (2, 4 or 8)
    n_features: int = 2500
    min_inliers: int = 25
    max_points_per_pair: int = 60
    cross_m: float = 70.0  # look for earlier photos from other flight lines within this distance (metres)
    w_gps: float = 1.0
    lookahead_after: int = 40  # estimate where the drone sits under the photo once this many photos are placed
    thumb_width: int = 640


@dataclass
class Photo:
    idx: int
    gps: np.ndarray  # (E, N) metres, relative to the run's origin
    t_arrival: float
    w: int = 0
    h: int = 0
    kp: np.ndarray | None = None
    des: np.ndarray | None = None
    thumb: np.ndarray | None = None
    linked: bool = False
    timings: dict = field(default_factory=dict)


class LiveMap:
    """Add photos one at a time, in the order they arrive; read placements at any moment."""

    def __init__(self, cfg: LiveConfig, origin_xy: tuple[float, float]):
        self.cfg = cfg
        self.origin = np.asarray(origin_xy, float)
        self.photos: list[Photo] = []
        self.AtA = np.zeros((0, 0))  # matched-point part of the normal equations
        self.x = np.zeros(0)
        self.e = np.zeros(2)  # point under the drone, in photo coordinates (metres-ish, y up); 0 = photo centre
        self.e_estimated = False
        self.pairs: list[tuple[int, int, int, int]] = []  # (i, j, good matches, inliers)
        self.rng = np.random.default_rng(0)
        self.sift = cv2.SIFT_create(cfg.n_features)
        self.flann = cv2.FlannBasedMatcher(dict(algorithm=1, trees=4), dict(checks=32))

    # ---------- geometry ----------
    def _P(self, ph: Photo, px: np.ndarray) -> np.ndarray:
        """reduced pixel (x, y) -> centred, y up, scaled by s0"""
        px = np.atleast_2d(px)
        return np.c_[(px[:, 0] - ph.w / 2) * self.cfg.s0, -(px[:, 1] - ph.h / 2) * self.cfg.s0]

    def _LT(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        a, b, tx, ty = self.x[NP * i:NP * i + NP]
        return np.array([[a, -b], [b, a]]), np.array([tx, ty])

    @staticmethod
    def _rows(p: np.ndarray) -> np.ndarray:
        """the two equation rows (x, y) of T(p) for a point p, over [a, b, tx, ty]: shape (2m, 4)"""
        m = len(p)
        R = np.zeros((2 * m, 4))
        R[0::2] = np.c_[p[:, 0], -p[:, 1], np.ones(m), np.zeros(m)]
        R[1::2] = np.c_[p[:, 1], p[:, 0], np.zeros(m), np.ones(m)]
        return R

    def _grow(self, n: int) -> None:
        k = NP * n
        if self.AtA.shape[0] < k:
            A = np.zeros((k, k))
            A[:self.AtA.shape[0], :self.AtA.shape[0]] = self.AtA
            self.AtA = A
            x = np.zeros(k)
            x[:len(self.x)] = self.x
            self.x = x

    def _add_pair(self, i: int, j: int, pi: np.ndarray, pj: np.ndarray) -> None:
        """T_i(pi) - T_j(pj) = 0 for every matched point: add R^T R to the table"""
        Ri, Rj = self._rows(pi), -self._rows(pj)
        si, sj = slice(NP * i, NP * i + NP), slice(NP * j, NP * j + NP)
        self.AtA[si, si] += Ri.T @ Ri
        self.AtA[sj, sj] += Rj.T @ Rj
        self.AtA[si, sj] += Ri.T @ Rj
        self.AtA[sj, si] += Rj.T @ Ri

    def solve(self) -> float:
        """re-solve every placement at once; returns seconds taken"""
        t0 = time.perf_counter()
        n = len(self.photos)
        A = self.AtA[:NP * n, :NP * n].copy()
        b = np.zeros(NP * n)
        Rg = self._rows(self.e[None, :]) * self.cfg.w_gps  # GPS: T_i(e) = G_i
        Gtg = Rg.T @ Rg
        for i, ph in enumerate(self.photos):
            s = slice(NP * i, NP * i + NP)
            A[s, s] += Gtg
            b[s] += Rg.T @ (ph.gps * self.cfg.w_gps)
        A[np.diag_indices_from(A)] += 1e-6  # keeps photos with no match yet solvable (they stay unplaced)
        try:
            self.x[:NP * n] = cho_solve(cho_factor(A), b)
        except np.linalg.LinAlgError:
            self.x[:NP * n] = np.linalg.lstsq(A, b, rcond=None)[0]
        return time.perf_counter() - t0

    def _estimate_lookahead(self) -> None:
        placed = [i for i in self.placed()]
        if len(placed) < 10:
            return
        es = []
        for i in placed:
            L, t = self._LT(i)
            es.append(np.linalg.solve(L, self.photos[i].gps - t))
        self.e = np.median(np.array(es), axis=0)
        self.e_estimated = True

    # ---------- photos ----------
    @staticmethod
    def prepare(img_bgr_reduced: np.ndarray, cfg: LiveConfig, sift) -> dict:
        """the part of a photo's work that needs no other photo (features, thumbnail): can run in another thread,
        with its own `sift`, while the previous photo is being matched and solved"""
        t0 = time.perf_counter()
        h, w = img_bgr_reduced.shape[:2]
        k, d = sift.detectAndCompute(cv2.cvtColor(img_bgr_reduced, cv2.COLOR_BGR2GRAY), None)
        tw = min(cfg.thumb_width, w)
        thumb = cv2.resize(img_bgr_reduced, (tw, int(h * tw / w)), interpolation=cv2.INTER_AREA)
        return {"w": w, "h": h, "kp": np.float32([q.pt for q in k]) if k else np.zeros((0, 2), np.float32),
                "des": d, "thumb": thumb, "features_s": time.perf_counter() - t0}

    def add_photo(self, img_bgr_reduced: np.ndarray, gps_xy: tuple[float, float], t_arrival: float) -> dict:
        """process one photo that has just arrived (already read at 1/reduce size); returns timings"""
        return self.add_prepared(self.prepare(img_bgr_reduced, self.cfg, self.sift), gps_xy, t_arrival)

    def add_prepared(self, prep: dict, gps_xy: tuple[float, float], t_arrival: float) -> dict:
        """match a prepared photo to earlier photos and re-solve every placement; returns timings"""
        cfg = self.cfg
        i = len(self.photos)
        ph = Photo(idx=i, gps=np.asarray(gps_xy, float) - self.origin, t_arrival=t_arrival,
                   w=prep["w"], h=prep["h"], kp=prep["kp"], des=prep["des"], thumb=prep["thumb"])
        self.photos.append(ph)
        self._grow(i + 1)
        t_feat = prep["features_s"]

        t0 = time.perf_counter()
        cand = [j for j in (i - 1, i - 2) if j >= 0]
        if i > 6:
            G = np.array([p.gps for p in self.photos[:i - 5]])
            dist = np.linalg.norm(G - ph.gps, axis=1)
            cand += [int(j) for j in np.argsort(dist)[:3] if dist[j] < cfg.cross_m]
        for j in cand:
            self._match(i, j)
        t_match = time.perf_counter() - t0

        if not self.e_estimated and len(self.placed()) >= cfg.lookahead_after:
            self.solve()
            self._estimate_lookahead()
        t_solve = self.solve()
        ph.timings = {"features_s": t_feat, "matching_s": t_match, "solve_s": t_solve}
        return ph.timings

    def _match(self, i: int, j: int) -> None:
        cfg, pi, pj = self.cfg, self.photos[i], self.photos[j]
        if pi.des is None or pj.des is None or len(pi.des) < 2 or len(pj.des) < 2:
            self.pairs.append((i, j, 0, 0))
            return
        good = [m for pr in self.flann.knnMatch(pi.des, pj.des, k=2) if len(pr) == 2 for m, nn in [pr]
                if m.distance < 0.75 * nn.distance]
        if len(good) < cfg.min_inliers:
            self.pairs.append((i, j, len(good), 0))
            return
        a = pi.kp[[m.queryIdx for m in good]]
        b = pj.kp[[m.trainIdx for m in good]]
        _, inl = cv2.findHomography(a, b, cv2.RANSAC, 6)
        ninl = int(inl.sum()) if inl is not None else 0
        self.pairs.append((i, j, len(good), ninl))
        if ninl < cfg.min_inliers:
            return
        idx = np.flatnonzero(inl.ravel())
        if len(idx) > cfg.max_points_per_pair:
            idx = self.rng.choice(idx, cfg.max_points_per_pair, replace=False)
        self._add_pair(i, j, self._P(pi, a[idx]), self._P(pj, b[idx]))
        pi.linked = pj.linked = True

    def finish(self) -> float:
        """after the last photo: re-estimate where the drone sits under the photo and re-solve once more"""
        t0 = time.perf_counter()
        self.solve()
        self._estimate_lookahead()
        self.solve()
        return time.perf_counter() - t0

    # ---------- results ----------
    def placed(self) -> list[int]:
        out = []
        for i, ph in enumerate(self.photos):
            if not ph.linked:
                continue
            L, _ = self._LT(i)
            if abs(np.linalg.det(L)) > 1e-4:
                out.append(i)
        return out

    def _correction(self, placed: list[int]) -> tuple[complex, complex]:
        """one overall shift/turn/size putting the solved drone positions on the GPS track (Test 7c's scale fix)"""
        if len(placed) < 3:
            return 1 + 0j, 0j
        anch = np.array([self._LT(i)[0] @ self.e + self._LT(i)[1] for i in placed])
        ca = anch[:, 0] + 1j * anch[:, 1]
        G = np.array([self.photos[i].gps for i in placed])
        cg = G[:, 0] + 1j * G[:, 1]
        alpha = np.sum((cg - cg.mean()) * np.conj(ca - ca.mean())) / np.sum(np.abs(ca - ca.mean()) ** 2)
        return alpha, cg.mean() - alpha * ca.mean()

    def footprints(self) -> dict:
        """corners (top-left, top-right, bottom-right, bottom-left) of every placed photo, in run coordinates
        plus origin (projected metres), and how far the solved drone positions sit from GPS"""
        placed = self.placed()
        alpha, beta = self._correction(placed)
        out, resid = [], []
        for i in placed:
            ph = self.photos[i]
            L, t = self._LT(i)
            c = self._P(ph, np.array([[0, 0], [ph.w, 0], [ph.w, ph.h], [0, ph.h]], float))
            g = (L @ c.T).T + t
            gc = alpha * (g[:, 0] + 1j * g[:, 1]) + beta
            out.append({"idx": i, "corners_xy": [[float(z.real + self.origin[0]), float(z.imag + self.origin[1])] for z in gc]})
            d = L @ self.e + t
            dz = alpha * complex(d[0], d[1]) + beta
            resid.append(abs(dz - complex(*ph.gps)))
        return {"photos": out, "scale_fix": float(abs(alpha)) if placed else None,
                "drone_vs_gps_median_m": float(np.median(resid)) if resid else None,
                "lookahead_estimated": self.e_estimated}

    def ground(self, i: int, px: np.ndarray) -> np.ndarray:
        """reduced-pixel points in photo i -> projected metres (with the overall correction), for evaluation"""
        alpha, beta = self._correction(self.placed())
        L, t = self._LT(i)
        g = (L @ self._P(self.photos[i], px).T).T + t
        z = alpha * (g[:, 0] + 1j * g[:, 1]) + beta
        return np.c_[z.real + self.origin[0], z.imag + self.origin[1]]
