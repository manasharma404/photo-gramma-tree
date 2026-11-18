"""Cut a small test set from our own South Fork map, for the debris model (teammate brief, T2).

Run from the repo root:  uv run python scripts/make_eval_crops.py
Writes data/eval/southfork_crops/ (not in git): 50 PNG crops, a blank labels.csv, a labelling page
label.html, a key file that says where each crop came from, and a contact sheet.

Why three groups and not 50 road crops: inside our map, the only roads are 16 footpath pieces from
OpenStreetMap (about 800 m), and none of them crosses the debris channel. Road crops alone would be
almost all "clear", which tests false alarms but not whether the model finds debris. So:
  A  "path":   one crop at the middle of each of the 16 path pieces inside the map (14 fit: two sit
               at the map's edge, where a full crop would run off it)
  B  "bare":   random spots on pale bare ground (little green, among the brightest 15% of the map):
               debris, trails and rock all look like this, so it gives hard cases both ways. (A first try,
               "brighter than the median", mostly caught grey dead shrubs: about 6 of 50 crops showed debris,
               too few to measure whether the model finds it. Tightened on 18 Nov before any labelling.)
  C  "random": random spots anywhere on the map
The groups are a sampling rule, not labels. People label every crop; the model is scored per group
and over all. Crop ids are shuffled and the page does not show the group, so labelling is blind.

These crops are a test set: they must never be used for training.
"""
import csv
import json
import random
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.windows import Window
import shapely
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
ORTHO = ROOT / "data/projects/southfork_f01_4/odm_orthophoto/odm_orthophoto.tif"
SEGS = ROOT / "data/projects/southfork_f01_4/roads/segments.geojson"
OUT = ROOT / "data/eval/southfork_crops"
SIZE = 512            # crop side in pixels (25.6 m at 5 cm per pixel); resize to the model's training scale later
LOW = 1.0             # metres per pixel of the low-resolution copy used to pick spots
MIN_GAP_M = 30.0      # no two crop centres closer than this, so crops do not overlap
N_BARE, N_RANDOM = 18, 18   # with 14 path crops: 50 in all
SEED = 20261118       # fixed, so the same crops come out every time

rng = random.Random(SEED)
src = rasterio.open(ORTHO)
gsd = src.res[0]
half_m = SIZE * gsd / 2

# ---- a 1 m copy of the map, to find valid and bare ground ----
f = gsd / LOW
lw, lh = int(src.width * f), int(src.height * f)
low = src.read([1, 2, 3, 4], out_shape=(4, lh, lw), resampling=Resampling.average).astype(float)
rgb, alpha = low[:3], low[3]
s = rgb.sum(0) + 1e-6
r, g, b = rgb[0] / s, rgb[1] / s, rgb[2] / s
exg = 2 * g - r - b                      # excess green: high on vegetation, low on soil and rock
bright = rgb.mean(0)
lt = src.transform * src.transform.scale(src.width / lw, src.height / lh)

def full_crop_valid(col, row):
    """The whole crop footprint lies inside the map (no black edge)."""
    k = int(np.ceil(half_m / LOW))
    if row - k < 0 or col - k < 0 or row + k >= lh or col + k >= lw:
        return False
    return (alpha[row - k:row + k, col - k:col + k] > 250).mean() > 0.98

valid = np.zeros((lh, lw), bool)
for row in range(0, lh, 2):
    for col in range(0, lw, 2):
        valid[row, col] = full_crop_valid(col, row)
bare_thr = np.percentile(exg[alpha > 250], 15)      # the least green 15% of the map
bright_thr = np.percentile(bright[alpha > 250], 85)  # the brightest 15% of the map
bare = valid & (exg < bare_thr) & (bright > bright_thr)

chosen = []  # (x, y, group, segment_id)

def far_enough(x, y):
    return all((x - cx) ** 2 + (y - cy) ** 2 >= MIN_GAP_M ** 2 for cx, cy, *_ in chosen)

# ---- A: the middle of each path piece inside the map ----
to_utm = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
for feat in json.loads(SEGS.read_text())["features"]:
    p = feat["properties"]
    if not p.get("measured"):
        continue
    line = shapely.transform(LineString(feat["geometry"]["coordinates"]), lambda c: np.column_stack(to_utm.transform(c[:, 0], c[:, 1])))
    mid = line.interpolate(0.5, normalized=True)
    row, col = rasterio.transform.rowcol(lt, mid.x, mid.y)
    if full_crop_valid(col, row):
        chosen.append((mid.x, mid.y, "path", p["segment_id"]))
    else:
        print("skipped (crop would leave the map):", p["segment_id"])

# ---- B and C: random spots, kept apart from every other crop ----
def draw(mask, n, group):
    rows, cols = np.nonzero(mask)
    order = list(range(len(rows)))
    rng.shuffle(order)
    got = 0
    for i in order:
        x, y = rasterio.transform.xy(lt, rows[i], cols[i])
        if far_enough(x, y):
            chosen.append((x, y, group, ""))
            got += 1
            if got == n:
                return
    print(f"only {got} of {n} {group} spots fit")

draw(bare, N_BARE, "bare")
draw(valid, N_RANDOM, "random")

# ---- cut the crops at full resolution; shuffle the ids so the group cannot be guessed ----
OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.glob("c*.png"):
    old.unlink()
rng.shuffle(chosen)
to_ll = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform
key_rows, thumbs = [], []
for n, (x, y, group, seg) in enumerate(chosen, 1):
    cid = f"c{n:02d}"
    row, col = src.index(x, y)
    win = Window(col - SIZE // 2, row - SIZE // 2, SIZE, SIZE)
    arr = src.read([1, 2, 3], window=win)
    img = Image.fromarray(np.moveaxis(arr, 0, -1))
    img.save(OUT / f"{cid}.png")
    thumbs.append((cid, img.resize((256, 256))))
    lon, lat = to_ll(x, y)
    key_rows.append({"crop_id": cid, "group": group, "segment_id": seg,
                     "centre_x": round(x, 2), "centre_y": round(y, 2), "crs": str(src.crs),
                     "lon": round(lon, 7), "lat": round(lat, 7), "gsd_m": round(gsd, 4), "size_px": SIZE})

with open(OUT / "crops_key.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(key_rows[0])); w.writeheader(); w.writerows(key_rows)
with open(OUT / "labels.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["crop_id", "label", "notes"])
    for k in key_rows:
        w.writerow([k["crop_id"], "", ""])

# ---- contact sheet (ids only, no groups) ----
cols_n = 10
sheet = Image.new("RGB", (cols_n * 262 + 6, ((len(thumbs) + cols_n - 1) // cols_n) * 284 + 6), "white")
d = ImageDraw.Draw(sheet)
for i, (cid, th) in enumerate(thumbs):
    x0, y0 = 6 + (i % cols_n) * 262, 6 + (i // cols_n) * 284
    sheet.paste(th, (x0, y0 + 22)); d.text((x0, y0 + 4), cid, fill="black")
sheet.save(OUT / "contact_sheet.jpg", quality=90)

# ---- an overview: where the crops are (for the lead, after labelling; it shows the groups) ----
ov_s = 1600 / src.width
ov = src.read([1, 2, 3], out_shape=(3, int(src.height * ov_s), 1600), resampling=Resampling.average)
ov = Image.fromarray(np.moveaxis(ov, 0, -1)).convert("RGB"); d = ImageDraw.Draw(ov)
colours = {"path": (181, 211, 52), "bare": (255, 170, 60), "random": (120, 170, 255)}
for k in key_rows:
    row, col = src.index(k["centre_x"], k["centre_y"])
    h = SIZE / 2 * ov_s
    cx, cy = col * ov_s, row * ov_s
    d.rectangle([cx - h, cy - h, cx + h, cy + h], outline=colours[k["group"]], width=3)
    d.text((cx - h + 3, cy - h + 2), k["crop_id"], fill=(255, 255, 255))
ov.save(OUT / "where_crops_are_SHOWS_GROUPS.jpg", quality=88)

# ---- the labelling page ----
(OUT / "label.html").write_text((ROOT / "scripts/eval_label_page.html").read_text(encoding="utf-8")
                                .replace("__IDS__", json.dumps([k["crop_id"] for k in key_rows])), encoding="utf-8")

# ---- a zip to send to the other labeller: crops, page and blank sheet only (nothing that shows the groups) ----
import zipfile
with zipfile.ZipFile(OUT.parent / "southfork_crops_for_labelling.zip", "w", zipfile.ZIP_STORED) as z:
    for p in sorted(OUT.glob("c*.png")) + [OUT / "label.html", OUT / "labels.csv", OUT / "contact_sheet.jpg"]:
        z.write(p, f"southfork_crops/{p.name}")

counts = {gname: sum(k["group"] == gname for k in key_rows) for gname in colours}
print(f"{len(key_rows)} crops in {OUT}  {counts}  crop {SIZE} px = {SIZE * gsd:.1f} m at {gsd * 100:.1f} cm/px; "
      f"bare = excess green < {bare_thr:.3f} and brightness > {bright_thr:.0f}; {int(bare.sum())} candidate spots")
