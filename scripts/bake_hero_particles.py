"""Bake the home page's particle hero (web/src/assets/hero_particles.bin) from the lead's hero image.

The picture is web/public/hero.webp (the lead's Project Typhon illustration). It is artwork, not our map:
the page uses it as decoration only and never labels it as data.

Each particle is one sample of the picture on a regular grid (below the baked-in wordmark, because the
page sets its own headline as real text). It stores two positions:
  - detail: where it sits in the picture, drawn in the picture's colour (the halftone look of the original);
  - wire:   a point on a draped grid, a wireframe drawn over the picture. Grid lines are lifted by a smoothed
            "relief" from the picture's darkness, so it reads as terrain. This relief is a styling choice,
            not a height measurement.

File layout (little endian): uint32 header length, header JSON, then n x int16 dx, dy, wx, wy (pixels x 4),
then n x uint8 r, g, b, a, w (w = weight in the wireframe: 0 for the grey mist, 1 in the valley).  Run:  python scripts/bake_hero_particles.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web/public/hero.webp"
OUT = ROOT / "web/src/assets/hero_particles.bin"
TEXTURE = ROOT / "web/src/assets/hero_texture.webp"

TOP = 262          # first row below the wordmark in the picture
STEP = 3           # sampling grid, picture pixels
GRID = 15          # wireframe line spacing, picture pixels
LIFT = 70          # how far the darkest relief lifts a grid line, picture pixels
PAPER = np.array([242, 242, 236], float)  # the picture's paper colour


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    W, H = im.size
    a = np.asarray(im).astype(float)
    diff = np.sqrt(((a - PAPER) ** 2).sum(axis=2))
    alpha = np.clip((diff - 12) / 70, 0, 1)
    lum = a @ np.array([0.299, 0.587, 0.114]) / 255

    # "valley" = the coloured, dark part of the picture (forest, debris, river), not the grey mist around it
    sat = a.max(axis=2) - a.min(axis=2)
    valley = np.maximum(np.clip((sat - 14) / 22, 0, 1) * alpha, np.clip((0.48 - lum) / 0.22, 0, 1))
    blur = lambda m, r: np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(float) / 255
    valley_s = blur(valley, 5)
    relief = blur(valley * (0.4 + 0.6 * (1 - lum)), 18)
    relief /= max(relief.max(), 1e-6)

    ys, xs = np.mgrid[TOP:H:STEP, 0:W:STEP]
    xs, ys = xs.ravel(), ys.ravel()
    al = alpha[ys, xs]
    keep = al > 0.10
    xs, ys, al = xs[keep], ys[keep], al[keep]
    rgb = a[ys, xs].astype(np.uint8)
    ww = np.clip(valley_s[ys, xs] / 0.6, 0, 1)  # how strongly each particle shows in the wireframe

    # wire target: snap to the nearer grid line (horizontal or vertical), then lift by the relief
    gx = np.round(xs / GRID) * GRID
    gy = np.round(ys / GRID) * GRID
    to_h = np.abs(ys - gy) <= np.abs(xs - gx)
    wx = np.where(to_h, xs, gx).astype(float)
    wy = np.where(to_h, gy, ys).astype(float)
    wxi = np.clip(wx, 0, W - 1).astype(int)
    wyi = np.clip(wy, 0, H - 1).astype(int)
    wy = wy - LIFT * relief[wyi, wxi]

    n = len(xs)
    head = {"n": n, "w": W, "h": H, "top": TOP, "step": STEP, "grid": GRID, "lift": LIFT, "scale": 4,
            "source": "web/public/hero.webp (the lead's illustration; artwork, not data)"}
    hb = json.dumps(head).encode()
    q = lambda v: np.round(v * 4).astype("<i2").tobytes()
    body = q(xs) + q(ys) + q(wx) + q(wy) + rgb[:, 0].tobytes() + rgb[:, 1].tobytes() + rgb[:, 2].tobytes() \
        + np.round(al * 255).astype(np.uint8).tobytes() + np.round(ww * 255).astype(np.uint8).tobytes()
    OUT.write_bytes(struct.pack("<I", len(hb)) + hb + body)
    print(f"{n} particles -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")

    # the same picture below the wordmark, smaller: the footer's big name and the no-WebGL fallback use it
    tex = im.crop((0, TOP, W, H)).resize((1200, round(1200 * (H - TOP) / W)), Image.LANCZOS)
    tex.save(TEXTURE, "WEBP", quality=74, method=6)
    print(f"texture -> {TEXTURE.relative_to(ROOT)} ({TEXTURE.stat().st_size // 1024} KB)")

    if len(sys.argv) > 2 and sys.argv[1] == "--preview":  # previews of both states, for checking by eye
        out_dir = Path(sys.argv[2])
        for name, px, py, col in (("detail", xs, ys, rgb), ("wire", wx, wy, None)):
            canvas = np.full((H - TOP + 60, W, 3), 242, np.uint8)
            yy = np.clip((py - TOP + 50).astype(int), 0, canvas.shape[0] - 1)
            xx = np.clip(px.astype(int), 0, W - 1)
            if col is None:
                k = ww > 0.25
                canvas[yy[k], xx[k]] = (40, 52, 40)
            else:
                for dy in range(STEP):
                    for dx in range(STEP):
                        canvas[np.clip(yy + dy, 0, canvas.shape[0] - 1), np.clip(xx + dx, 0, W - 1)] = col
            Image.fromarray(canvas).save(out_dir / f"hero_{name}.png")


if __name__ == "__main__":
    main()
