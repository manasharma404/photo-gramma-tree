"""Turn a DJI Neo 2 clip into geotagged photos for ODM.

    python -m pipeline.video_frames --video data/raw/neo2/<clip>.mp4 --project neo2_<name> [--spacing-m 2] [--max 300]

1. Read the per-frame GPS track from the clip's telemetry (pipeline/dji_telemetry.py).
2. Walk the track and open a new window every `spacing_m` metres of movement (or 1 s when hovering);
   in each window keep the sharpest frame (standard check: variance of the Laplacian).
3. Extract those frames at full resolution, and write GPS latitude/longitude/altitude into their EXIF.
4. Write image_quality.json (contract; method "standard_check") listing every candidate and why it was
   kept or dropped, and images.txt for pipeline/run_odm.py.

Altitude: the telemetry's altitude reference is unknown (see video_report.json), so heights from this
run are relative only. Never uses ground control.
"""
import argparse
import csv
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import yaml
from pyproj import Geod

from pipeline import dji_telemetry, frame_quality

ROOT = Path(__file__).resolve().parent.parent
EXIFTOOL_FALLBACK = Path.home() / "AppData/Local/Programs/ExifTool/ExifTool.exe"
GEOD = Geod(ellps="WGS84")


def windows(track, fps, spacing_m, hover_s=1.0):
    """Group frame indices into windows of >= spacing_m movement, or hover_s seconds when not moving."""
    out, cur, start_i = [], [], 0
    dist = 0.0
    for i in range(len(track)):
        if i > 0 and track[i]["lat"] is not None and track[i - 1]["lat"] is not None:
            dist += GEOD.inv(track[i - 1]["lon"], track[i - 1]["lat"], track[i]["lon"], track[i]["lat"])[2]
        cur.append(i)
        if dist >= spacing_m - 1e-3 or (i - start_i) >= hover_s * fps:  # 1 mm slack for float sums
            out.append(cur)
            cur, dist, start_i = [], 0.0, i + 1
    if cur:
        out.append(cur)
    return out


def frame_at(video, index, fps, width, height):
    return frame_quality.video_frame_gray(video, index / fps, width, height)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--spacing-m", type=float, default=2.0)
    ap.add_argument("--probe-per-window", type=int, default=4, help="frames scored per window (speed vs choice)")
    ap.add_argument("--max", type=int, default=300, help="brief: --video-limit 300")
    args = ap.parse_args()

    from pipeline.video_check import ffprobe_facts
    facts = ffprobe_facts(args.video)
    fps, W, H = facts["fps"], facts["width"], facts["height"]
    thresholds = yaml.safe_load((ROOT / "config/quality.yaml").read_text())
    track = dji_telemetry.read_track(args.video)
    wins = windows(track, fps, args.spacing_m)
    if len(wins) > args.max:  # thin evenly to the limit
        wins = [wins[int(i)] for i in np.linspace(0, len(wins) - 1, args.max)]

    out_dir = ROOT / "data" / "projects" / args.project / "frames"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    items, kept, exif_rows = [], [], []
    for w in wins:
        probes = [w[int(k)] for k in np.linspace(0, len(w) - 1, min(args.probe_per_window, len(w)))]
        scored = []
        for i in probes:
            if track[i]["lat"] is None:
                items.append({"image": f"video:{i}", "score": None, "usable": False, "reasons": ["other"]})
                continue
            try:
                m = frame_quality.measure(frame_at(args.video, i, fps, W, H))
            except ValueError:  # e.g. the last frames of a clip: seeking that close to the end decodes nothing
                items.append({"image": f"video:{i}", "score": None, "usable": False, "reasons": ["other"]})
                continue
            reasons = []
            if m["mean_luma"] < thresholds["dark_mean_luma_below"]:
                reasons.append("dark")
            if m["laplacian_var"] < thresholds["blurry_laplacian_var_below"]:
                reasons.append("blur")
            scored.append((m["laplacian_var"], i, m, reasons))
        if not scored:
            continue
        scored.sort(reverse=True)
        best = scored[0]
        for lv, i, m, reasons in scored:
            chosen = i == best[1] and "dark" not in reasons
            # "other" = fine on its own, but a sharper frame was kept for this stretch of the flight
            items.append({"image": f"video:{i}", "score": None, "usable": chosen,
                          "reasons": reasons if chosen or reasons else ["other"]})
        if "dark" in best[3]:
            continue
        i = best[1]
        name = f"{args.video.stem[:24]}_f{i:05d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{i / fps:.3f}", "-i", str(args.video), "-map", "0:0",
                        "-frames:v", "1", "-q:v", "2", str(out_dir / name)], check=True)
        t = track[i]
        exif_rows.append({"SourceFile": str(out_dir / name), "GPSLatitude": t["lat"], "GPSLatitudeRef": "N" if t["lat"] >= 0 else "S",
                          "GPSLongitude": abs(t["lon"]), "GPSLongitudeRef": "E" if t["lon"] >= 0 else "W",
                          "GPSAltitude": (t["alt_raw_mm"] or 0) / 1000, "GPSAltitudeRef": 0,
                          "Make": "DJI", "Model": "FC9470"})
        kept.append(name)

    csv_path = out_dir.parent / "exif_import.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(exif_rows[0].keys()))
        wr.writeheader()
        wr.writerows(exif_rows)
    exe = shutil.which("exiftool") or str(EXIFTOOL_FALLBACK)
    subprocess.run([exe, "-q", "-overwrite_original", f"-csv={csv_path}", str(out_dir)], check=True)

    rel = lambda p: str(Path(p).resolve().relative_to(ROOT)).replace("\\", "/")  # resolve: --video may be relative
    (out_dir.parent / "images.txt").write_text("\n".join(rel(out_dir / k) for k in kept) + "\n", encoding="utf-8")
    iq = {"mock": False, "method": "standard_check", "model": None, "version": None, "source": rel(args.video),
          "items": items}
    import jsonschema
    jsonschema.validate(iq, json.loads((ROOT / "contracts/image_quality.schema.json").read_text(encoding="utf-8")))
    (out_dir.parent / "image_quality.json").write_text(json.dumps(iq, indent=2), encoding="utf-8")
    print(json.dumps({"windows": len(wins), "frames_scored": len(items), "frames_kept": len(kept),
                      "spacing_m": args.spacing_m, "out": rel(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
