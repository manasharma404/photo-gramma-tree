"""Run OpenDroneMap in Docker with benchmark capture, and write run.json.

    python -m pipeline.run_odm --project southfork_f01_5 --tier quick \
        --images-list data/public/usgs_southfork/subset.txt

Images are hard-linked into data/projects/<project>/images (no extra disk).
Every ODM output line is timestamped into data/runs/<run_id>/odm.log; stage
times come from ODM's "Running <stage> stage" lines. Peak memory is sampled
from `docker stats` every 2 s. Area and GSD are read from the orthophoto.
Never uses --gcp: the brief requires georeferencing without ground control.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "data" / "projects"
RUNS = ROOT / "data" / "runs"
ODM_IMAGE = "opendronemap/odm:gpu@sha256:c6ecdec7764094732248517c51d6430fbc9dad61b586daafded04745026d9ed8"

# Update 2 settings (16 GB laptop, WSL memory=12GB)
TIERS = {
    "quick": ["--fast-orthophoto", "--skip-3dmodel", "--feature-quality", "high", "--max-concurrency", "4",
              "--orthophoto-resolution", "5"],
    "full": ["--dsm", "--dtm", "--skip-3dmodel", "--pc-quality", "medium", "--feature-quality", "high",
             "--dem-resolution", "10", "--orthophoto-resolution", "5", "--max-concurrency", "4", "--cog"],
}

STAGE_RE = re.compile(r"Running (\w+) stage")
MEM_RE = re.compile(r"([\d.]+)\s*([KMGT]i?B)", re.I)
UNITS = {"b": 1 / 1024 ** 3, "kib": 1 / 1024 ** 2, "kb": 1e3 / 1024 ** 3, "mib": 1 / 1024, "mb": 1e6 / 1024 ** 3,
         "gib": 1.0, "gb": 1e9 / 1024 ** 3, "tib": 1024.0, "tb": 1e12 / 1024 ** 3}


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_mem_gb(mem_usage):
    """'3.2GiB / 11.68GiB' -> 3.2 (GiB, as docker reports)."""
    m = MEM_RE.search(mem_usage)
    if not m:
        return None
    return float(m.group(1)) * UNITS[m.group(2).lower()]


def stage_of(line):
    m = STAGE_RE.search(line)
    return m.group(1) if m else None


def link_images(paths, dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for p in paths:
        src = (ROOT / p).resolve()
        os.link(src, dest / src.name)
    return len(paths)


class MemorySampler(threading.Thread):
    def __init__(self, container, interval=2.0):
        super().__init__(daemon=True)
        self.container, self.interval = container, interval
        self.peak_gb, self.samples = None, 0
        self._halt = threading.Event()  # not "_stop": that name is a Thread internal

    def run(self):
        while not self._halt.is_set():
            out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", self.container],
                                 capture_output=True, text=True).stdout.strip()
            gb = parse_mem_gb(out) if out else None
            if gb is not None:
                self.samples += 1
                self.peak_gb = gb if self.peak_gb is None else max(self.peak_gb, gb)
            self._halt.wait(self.interval)

    def stop(self):
        self._halt.set()


def orthophoto_stats(path):
    """Area of valid pixels (ha) and pixel size (cm), read at reduced resolution to save memory."""
    import rasterio
    with rasterio.open(path) as ds:
        step = max(1, max(ds.width, ds.height) // 4000)
        mask = ds.dataset_mask(out_shape=(ds.height // step, ds.width // step))
        px_area = abs(ds.transform.a * ds.transform.e) * step * step
        return {
            "area_ha": round(float((mask > 0).sum()) * px_area / 1e4, 3),
            "gsd_cm": round(abs(ds.transform.a) * 100, 2),
            "crs": str(ds.crs),
            "size_px": [ds.width, ds.height],
        }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--tier", choices=sorted(TIERS), required=True)
    ap.add_argument("--images-list", type=Path, required=True, help="text file, one image path per line")
    ap.add_argument("--extra", nargs=argparse.REMAINDER, default=[], help="extra ODM options (after --extra)")
    args = ap.parse_args()
    if any(o.startswith("--gcp") for o in args.extra):
        raise SystemExit("--gcp is not allowed: checkpoints are for measuring error only")

    paths = [l.strip() for l in args.images_list.read_text(encoding="utf-8").splitlines() if l.strip()]
    run_id = f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_{args.project}_{args.tier}"
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True)
    container = f"odm_{run_id}".replace(":", "")
    options = TIERS[args.tier] + args.extra

    run = {
        "mock": False, "run_id": run_id, "project": args.project,
        "inputs": {"kind": "images", "count": None, "source_folder": str(args.images_list).replace("\\", "/"),
                   "quality_filter": None},
        "tier": args.tier, "odm_image": ODM_IMAGE, "odm_options": options,
        "machine_file": "data/machine.json", "status": "running",
        "started_at": None, "ended_at": None, "stages": [], "total_seconds": None,
        "peak_memory_gb": None, "area_ha": None, "gsd_cm": None,
        "products": {"orthophoto": None, "dsm": None, "dtm": None, "point_cloud": None, "glb": None, "kmz": None},
    }
    project_dir = PROJECTS / args.project
    run["inputs"]["count"] = link_images(paths, project_dir / "images")
    free_gb = shutil.disk_usage(ROOT).free / 1024 ** 3
    print(f"{run_id}: {run['inputs']['count']} images, {free_gb:.1f} GB free")

    cmd = ["docker", "run", "--rm", "--gpus", "all", "--name", container,
           "-v", f"{PROJECTS.as_posix()}:/datasets", ODM_IMAGE,
           "--project-path", "/datasets", args.project] + options
    (run_dir / "command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")

    sampler = MemorySampler(container)
    t0 = time.monotonic()
    run["started_at"] = now()
    current = None
    with open(run_dir / "odm.log", "w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
        sampler.start()
        for line in proc.stdout:
            t = time.monotonic() - t0
            log.write(f"[{t:9.1f}s] {line}")
            log.flush()
            name = stage_of(line)
            if name:
                if current:
                    current["seconds"] = round(t - current["_t"], 1)
                current = {"name": name, "started_at": now(), "seconds": None, "_t": t}
                run["stages"].append(current)
                print(f"  [{t / 60:6.1f} min] stage {name}")
        code = proc.wait()
    sampler.stop()
    total = time.monotonic() - t0
    if current:
        current["seconds"] = round(total - current["_t"], 1)
    for s in run["stages"]:
        s.pop("_t", None)

    run["ended_at"] = now()
    run["total_seconds"] = round(total, 1)
    run["peak_memory_gb"] = round(sampler.peak_gb, 2) if sampler.peak_gb is not None else None
    run["status"] = "done" if code == 0 else "failed"

    candidates = {
        "orthophoto": "odm_orthophoto/odm_orthophoto.tif", "dsm": "odm_dem/dsm.tif", "dtm": "odm_dem/dtm.tif",
        "point_cloud": "odm_georeferencing/odm_georeferenced_model.laz", "glb": "odm_texturing/odm_textured_model_geo.glb",
        "kmz": "odm_orthophoto/odm_orthophoto.kmz",
    }
    for key, rel in candidates.items():
        if (project_dir / rel).exists():
            run["products"][key] = str((project_dir / rel).relative_to(ROOT)).replace("\\", "/")
    if run["products"]["orthophoto"]:
        stats = orthophoto_stats(ROOT / run["products"]["orthophoto"])
        run["area_ha"], run["gsd_cm"] = stats["area_ha"], stats["gsd_cm"]
        (run_dir / "orthophoto_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    schema = json.loads((ROOT / "contracts/run.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(run, schema)
    (run_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(f"{run['status']} in {total / 60:.1f} min, peak {run['peak_memory_gb']} GiB "
          f"({sampler.samples} samples), area {run['area_ha']} ha, GSD {run['gsd_cm']} cm -> {run_dir / 'run.json'}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
