"""Check drone videos before mapping and write video_report.json.

    python -m pipeline.video_check data/raw/neo2

Per clip: ffprobe facts, exiftool's view of embedded GPS, the GPS track decoded
from the DJI telemetry stream (also saved as <clip>_track.csv), and brightness
and sharpness on evenly spaced frames.
"""
import argparse
import csv
import json
import shutil
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pyproj import Geod

from pipeline import dji_telemetry, frame_quality

ROOT = Path(__file__).resolve().parent.parent
EXIFTOOL_FALLBACK = Path.home() / "AppData/Local/Programs/ExifTool/ExifTool.exe"


def ffprobe_facts(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,bit_rate:format_tags=creation_time,encoder,comment:"
         "stream=index,codec_type,codec_name,width,height,r_frame_rate:stream_tags=handler_name",
         "-of", "json", str(video)],
        capture_output=True, check=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    tags = info["format"].get("tags", {})
    return {
        "codec": v["codec_name"],
        "width": v["width"],
        "height": v["height"],
        "fps": round(num / den, 3),
        "duration_s": round(float(info["format"]["duration"]), 3),
        "bitrate_mbps": round(int(info["format"]["bit_rate"]) / 1e6, 2),
        "creation_time_utc": tags.get("creation_time"),
        "encoder": tags.get("encoder"),
        "comment": tags.get("comment"),
        "data_streams": [s.get("tags", {}).get("handler_name") for s in info["streams"] if s["codec_type"] == "data"],
    }


def exiftool_view(video):
    exe = shutil.which("exiftool") or (str(EXIFTOOL_FALLBACK) if EXIFTOOL_FALLBACK.exists() else None)
    if exe is None:
        return {"available": False}
    version = subprocess.run([exe, "-ver"], capture_output=True, text=True).stdout.strip()
    out = subprocess.run([exe, "-ee", "-j", "-GPSLatitude", "-Protocol", "-Warning", str(video)],
                         capture_output=True, text=True).stdout
    tags = json.loads(out)[0] if out.strip() else {}
    return {
        "available": True,
        "version": version,
        "gps_found": "GPSLatitude" in tags,
        "protocol": tags.get("Protocol"),
        "warning": tags.get("Warning"),
    }


def track_summary(track, csv_path):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(track[0].keys()))
        w.writeheader()
        w.writerows(track)
    gps = [r for r in track if r["lat"] is not None and r["lon"] is not None]
    if not gps:
        return {"frames": len(track), "frames_with_gps": 0}
    geod = Geod(ellps="WGS84")
    lats, lons = [r["lat"] for r in gps], [r["lon"] for r in gps]
    path_m = geod.line_length(lons, lats)
    ew_m = geod.inv(min(lons), statistics.mean(lats), max(lons), statistics.mean(lats))[2]
    ns_m = geod.inv(statistics.mean(lons), min(lats), statistics.mean(lons), max(lats))[2]
    alts = [r["alt_raw_mm"] / 1000 for r in gps if r["alt_raw_mm"] is not None]
    isos = [r["iso"] for r in track if r["iso"] is not None]
    return {
        "frames": len(track),
        "frames_with_gps": len(gps),
        "start": {"lat": gps[0]["lat"], "lon": gps[0]["lon"]},
        "bbox": {"lat_min": min(lats), "lat_max": max(lats), "lon_min": min(lons), "lon_max": max(lons)},
        "extent_m": {"east_west": round(ew_m, 1), "north_south": round(ns_m, 1)},
        "path_length_m": round(path_m, 1),
        "altitude_m": {"min": min(alts), "max": max(alts),
                       "note": "decoded field 3.4.4.2 / 1000; reference (MSL, ellipsoid or barometric) unknown"} if alts else None,
        "iso": {"min": min(isos), "max": max(isos), "note": "field meaning inferred"} if isos else None,
        "track_csv": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
        "field_map": {path: {"name": n, "meaning": m, "confidence": c}
                      for path, (n, m, c) in dji_telemetry.FIELDS.items()},
    }


def frame_stats(video, facts, n_frames, thresholds):
    frames = []
    for k in range(n_frames):
        t = (k + 0.5) * facts["duration_s"] / n_frames
        m = frame_quality.measure(frame_quality.video_frame_gray(video, t, facts["width"], facts["height"]))
        frames.append({"t_s": round(t, 2), "mean_luma": round(m["mean_luma"], 1),
                       "laplacian_var": round(m["laplacian_var"], 1)})

    def summary(key):
        vals = [f[key] for f in frames]
        return {"min": min(vals), "median": round(statistics.median(vals), 1), "max": max(vals)}

    return {
        "method": "standard_check (mean luminance; variance of Laplacian on full-resolution grayscale)",
        "n_frames": n_frames,
        "mean_luma": summary("mean_luma"),
        "laplacian_var": summary("laplacian_var"),
        "frames_flagged_dark": sum(f["mean_luma"] < thresholds["dark_mean_luma_below"] for f in frames),
        "frames_flagged_blurry": sum(f["laplacian_var"] < thresholds["blurry_laplacian_var_below"] for f in frames),
        "thresholds": {**thresholds, "status": "PLACEHOLDER (config/quality.yaml)"},
        "frames": frames,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--frames", type=int, default=20)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    thresholds = yaml.safe_load((ROOT / "config/quality.yaml").read_text())
    folder = args.folder.resolve()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "clips": []}
    for video in sorted(folder.glob("*.mp4")):
        print(f"checking {video.name}")
        facts = ffprobe_facts(video)
        clip = {"file": video.name, "size_bytes": video.stat().st_size, "ffprobe": facts,
                "exiftool": exiftool_view(video)}
        try:
            clip["telemetry_gps"] = track_summary(dji_telemetry.read_track(video),
                                                  folder / f"{video.stem}_track.csv")
        except (subprocess.CalledProcessError, StopIteration, ValueError) as e:
            clip["telemetry_gps"] = {"error": str(e)}
        clip["frame_quality"] = frame_stats(video, facts, args.frames, thresholds)
        report["clips"].append(clip)
    out = args.out or folder / "video_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
