"""Copy small real outputs into samples/<project>/ so teammates can test without our data folder.

    uv run python scripts/make_samples.py --project southfork_f01_4 --accuracy <accuracy.json> --ortho <orthophoto.tif>

Copies roads/segments.geojson and roads/places.geojson, the accuracy file, and a downsampled
orthophoto (max 2048 px, JPEG-compressed GeoTIFF). Sources: USGS South Fork survey (public domain),
OpenStreetMap (ODbL). Everything else in data/ stays out of git.
"""
import argparse
import json
import shutil
from pathlib import Path

import rasterio
from rasterio.enums import Resampling

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--accuracy", type=Path, required=True)
    ap.add_argument("--ortho", type=Path, required=True)
    ap.add_argument("--max-px", type=int, default=2048)
    args = ap.parse_args()
    src = ROOT / "data" / "projects" / args.project / "roads"
    out = ROOT / "samples" / args.project
    out.mkdir(parents=True, exist_ok=True)
    for name in ("segments.geojson", "places.geojson"):
        shutil.copy(src / name, out / name)
    shutil.copy(args.accuracy, out / "accuracy.json")

    with rasterio.open(args.ortho) as ds:
        scale = max(ds.width, ds.height) / args.max_px
        w, h = int(ds.width / scale), int(ds.height / scale)
        data = ds.read(out_shape=(ds.count, h, w), resampling=Resampling.average)
        profile = ds.profile.copy()
        profile.update(width=w, height=h, transform=ds.transform * ds.transform.scale(ds.width / w, ds.height / h),
                       compress="jpeg" if ds.count == 3 else "deflate", tiled=True, blockxsize=256, blockysize=256)
        profile.pop("photometric", None)
        with rasterio.open(out / "orthophoto_small.tif", "w", **profile) as dst:
            dst.write(data)

    seg = json.loads((out / "segments.geojson").read_text(encoding="utf-8"))
    acc = json.loads((out / "accuracy.json").read_text(encoding="utf-8"))
    (out / "README.md").write_text(
        f"# Sample: {args.project}\n\nReal outputs from Project Typhon's pipeline, small enough for git.\n\n"
        f"| File | What |\n|---|---|\n"
        f"| `segments.geojson` | {len(seg['features'])} road segments with measurements (contracts/segments.schema.json) |\n"
        f"| `places.geojson` | places and landing-zone candidates (contracts/places.schema.json) |\n"
        f"| `accuracy.json` | horizontal RMSE {acc['horizontal']['rmse_h_m']} m at {acc['n_checkpoints']} checkpoints |\n"
        f"| `orthophoto_small.tif` | orthophoto downsampled to {w}x{h} px |\n\n"
        "Sources: USGS South Fork Campground debris-flow survey, 30 Apr 2024 (public domain), processed by us without "
        "ground control; roads and places © OpenStreetMap contributors (ODbL).\n", encoding="utf-8")
    print("wrote", sorted(p.name for p in out.iterdir()), f"ortho {w}x{h}")


if __name__ == "__main__":
    main()
