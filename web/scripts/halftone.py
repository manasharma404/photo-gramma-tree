"""Halftone art for the About and Neo 2 pages, made from OUR OWN images (no stock, no AI imagery).

    uv run python web/scripts/halftone.py

Each source (orthophoto, video frame, 3D view) becomes navy-blue-lime dots: dot size and colour follow
brightness, like the lead's mockup. Output: web/public/art/<name>.webp.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "screenshots"
OUT = ROOT / "web" / "public" / "art"

NAVY = (11, 23, 48)
RAMP = [  # brightness -> dot colour; lime only for the brightest tenth, like the mockup
    (0.00, (20, 38, 92)),
    (0.45, (36, 70, 160)),
    (0.75, (78, 122, 208)),
    (0.88, (172, 208, 72)),
    (1.00, (222, 238, 150)),
]

# name: (source, crop box as fractions (l, t, r, b), output width, cell px, contrast gamma)
JOBS = {
    "sf_ortho_wide": ("halftone_src/sf_ortho.png", (0.08, 0.22, 0.92, 0.72), 1400, 9, 0.8),
    "sf_debris": ("halftone_src/sf_ortho.png", (0.30, 0.30, 0.62, 0.62), 800, 8, 0.8),
    "sf_ortho_round": ("halftone_src/sf_ortho.png", (0.18, 0.18, 0.82, 0.82), 700, 8, 0.8),
    "terrain_relief": ("halftone_src/sf_hillshade.png", (0.05, 0.05, 0.95, 0.95), 900, 8, 1.0),
    "neo2_frame": ("halftone_src/neo2_frame60.jpg", (0.0, 0.0, 1.0, 1.0), 1400, 9, 1.8),
    "neo2_frame_round": ("halftone_src/neo2_frame120.jpg", (0.15, 0.0, 0.75, 1.0), 700, 8, 1.6),
    "neo2_map": ("neo2/ortho_preview.png", (0.0, 0.0, 1.0, 1.0), 900, 8, 0.9),
}


def ramp(v):
    for (a, ca), (b, cb) in zip(RAMP, RAMP[1:]):
        if v <= b:
            t = (v - a) / (b - a)
            return tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return RAMP[-1][1]


def halftone(src, crop, width, cell, gamma, seed=7):
    im = Image.open(SRC / src).convert("RGB")
    w, h = im.size
    im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    height = int(width * im.height / im.width)
    ss = 3  # supersample for smooth dots
    g = np.asarray(im.convert("L").resize((width // cell + 1, height // cell + 1), Image.LANCZOS), dtype=float) / 255
    lo, hi = np.percentile(g, 2), np.percentile(g, 98)
    g = np.clip((g - lo) / max(hi - lo, 1e-6), 0, 1) ** gamma
    canvas = Image.new("RGB", (width * ss, height * ss), NAVY)
    d = ImageDraw.Draw(canvas)
    rng = np.random.default_rng(seed)
    for j in range(g.shape[0]):
        for i in range(g.shape[1]):
            v = g[j, i]
            r = cell * ss * 0.62 * (0.12 + 0.88 * v) ** 0.5
            x = (i + 0.5 + rng.uniform(-0.18, 0.18)) * cell * ss
            y = (j + 0.5 + rng.uniform(-0.18, 0.18)) * cell * ss
            d.ellipse((x - r, y - r, x + r, y + r), fill=ramp(min(1, max(0, v + rng.uniform(-0.05, 0.05)))))
    return canvas.resize((width, height), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1, 40, 2))


def hillshade(dsm_path, out_path, step=6, az=315, alt=45):
    """Shaded relief from our South Fork DSM (sun from the north-west), as the terrain picture."""
    import rasterio

    with rasterio.open(dsm_path) as s:
        z = s.read(1, out_shape=(s.height // step, s.width // step)).astype(float)
        res = s.res[0] * step
        nodata = s.nodata
    mask = z == nodata
    z[mask] = np.nanmedian(z[~mask])
    dy, dx = np.gradient(z, res)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    a, e = np.radians(az), np.radians(alt)
    hs = np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect)
    hs = (np.clip(hs, 0, 1) * 255).astype(np.uint8)
    hs[mask] = 0
    Image.fromarray(hs).save(out_path)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    hillshade(ROOT / "data/projects/southfork_f01_4/odm_dem/dsm.tif", SRC / "halftone_src/sf_hillshade.png")
    for name, job in JOBS.items():
        img = halftone(*job)
        img.save(OUT / f"{name}.webp", quality=82)
        print(name, img.size)
