"""Ridge-line art for the home page, drawn from OUR South Fork height model (not clip-art).

    uv run python web/scripts/ridge_lines.py

Takes two straight cross-sections through data/projects/southfork_f01_4/odm_dem/dsm.tif and writes them as
SVG paths to web/public/art/ridge_<name>.svg. Heights are relative (absolute heights are off by ~43 m, see
accuracy.json), so the label states relief only. Prints the relief so the page can quote it.
"""
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
DSM = ROOT / "data/projects/southfork_f01_4/odm_dem/dsm.tif"
OUT = ROOT / "web/public/art"
W, H = 1600, 180


def profile(z, axis, frac):
    line = z[int(z.shape[0] * frac), :] if axis == "row" else z[:, int(z.shape[1] * frac)]
    ok = np.isfinite(line)
    line = line[ok]
    # rolling median removes spikes where the surface model has gaps or smeared edges
    win = np.lib.stride_tricks.sliding_window_view(np.pad(line, 7, mode="edge"), 15)
    line = np.median(win, axis=1)
    k = max(1, len(line) // 400)
    line = np.convolve(line, np.ones(k) / k, mode="valid")[::k]  # smooth, ~400 points
    return line


def svg(line, name):
    lo, hi = float(line.min()), float(line.max())
    xs = np.linspace(0, W, len(line))
    ys = H - 12 - (line - lo) / max(hi - lo, 1e-6) * (H - 30)
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    fill = d + f" L{W},{H} L0,{H} Z"
    (OUT / f"ridge_{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">'
        f'<path d="{fill}" fill="#0F1E3D" fill-opacity="0.06"/>'
        f'<path d="{d}" fill="none" stroke="#0F1E3D" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>',
        encoding="utf-8")
    return hi - lo


with rasterio.open(DSM) as s:
    z = s.read(1, out_shape=(s.height // 8, s.width // 8)).astype(float)
    z[z == s.nodata] = np.nan
OUT.mkdir(parents=True, exist_ok=True)
for name, axis, frac in [("we", "row", 0.5), ("ns", "col", 0.45)]:
    print(name, f"relief {svg(profile(z, axis, frac), name):.0f} m")
