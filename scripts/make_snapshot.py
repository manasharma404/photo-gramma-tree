"""Save the running app's data as static files, for a read-only snapshot site.

    cd web && npm run build:snapshot && cd ..
    uv run python scripts/make_snapshot.py            # API must be running on :8000

Fills web/dist-snapshot/data/*.json from the live API (the same answers the app shows) and copies
the active project's map tiles and 3D terrain next to them. The result is a plain static folder:
the map, 3D view and panels work; measuring needs the live server and says so.
"""
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "web" / "dist-snapshot"
API = "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.loads(r.read())


def save(name, data):
    p = SITE / "data" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def main():
    if not (SITE / "app" / "index.html").exists():
        raise SystemExit("build the site first: cd web && npm run build:snapshot")
    active = get("/accuracy/active")
    project = active["project"]
    save("health", {"snapshot": True, "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "note": "read-only snapshot of the Project Typhon app; measuring needs the live server"})
    save("active", active)
    save("spec", get("/accuracy/spec"))
    save("helicopters", get("/measure/helicopters"))
    for layer in ("segments", "places", "checkpoints"):
        try:
            save(f"layers/{layer}", get(f"/accuracy/layers/{layer}"))
        except Exception as e:  # a layer can legitimately be missing; the app shows "not measured yet"
            print("skip layer", layer, e)
    for name in ("state", "priorities", "access", "reports"):
        save(f"advisor/{name}", get(f"/advisor/{name}?project={project}"))

    src = ROOT / "data" / "projects" / project / "tiles"
    dst = SITE / "tiles" / project
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    files = [p for p in SITE.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files) / 1e6
    print(f"snapshot of {project}: {len(files)} files, {size:.1f} MB in {SITE}")


if __name__ == "__main__":
    main()
