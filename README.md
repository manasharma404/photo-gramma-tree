# Project Typhon

*We build immediate 2D and 3D maps for post-landslide relief efforts.*

hackFront IIITD, team Vortex (repo: photo-gramma-tree). hackFront India 2026, **PS T8.2 "The First Map After The Landslide"**: turn consumer drone footage into a georeferenced map, measurements and road status per vehicle, **offline on a laptop**, and state the positional error honestly.

**Status (round 1, 31 Oct 2026):** working prototype; results below come from runs on this laptop. Plan, owners and decisions: [PLAN.md](PLAN.md). Validation write-up: [docs/validation.md](docs/validation.md).

**Try it:** [manasharma404.github.io/photo-gramma-tree](https://manasharma404.github.io/photo-gramma-tree/) is a read-only copy of the app (South Fork block): map, 3D view, panels, the guided tour, About and Drone data. Measuring and field reports run on the Typhon laptop (`uv run python -m api.main`).

**Watch it:** [docs/demo/typhon_demo.mp4](docs/demo/typhon_demo.mp4) (1 min 41 s): the real laptop app, recorded headlessly by `web/scripts/demo_video.mjs`: home, the guided tour, vehicles, measuring a span across the debris channel (59.40 ± 8.62 m), accuracy, 3D view, the field page. Captions describe what is on screen; frames are captured about 1.5 per second, so scrolling looks stepped.

## What it does
```
drone photos or video (+GPS) ──► ODM (Docker, GPU) ──► orthophoto, height models (DSM/DTM)
                                     │  stage times, peak memory, area      │
                                     ▼                                      ▼
            accuracy/ (checkpoints, never used as ground control)   measure/ (span, debris volume,
                                                                     landing zones, working space)
                                     ▼                                      ▼
            roads/ (OSM ways + height model → clear width, obstruction, debris per segment)
                                     ▼
            advisor/ (status per vehicle with reasons, who is cut off, reopen plan, priorities)
                                     ▼
            api/ + web/ (offline map, 3D view, panels; phones join over the laptop hotspot)
```

## What's real, what's public, what's estimated
| Item | Source | Label in the app |
|---|---|---|
| Survey images and checkpoints | **USGS South Fork Campground debris-flow survey** (30 Apr 2024), public domain, processed **without its ground control** | "USGS public data, not our footage" |
| Our own footage | DJI Neo 2 video (20 Aug 2026), GPS decoded from the clip's telemetry | "Our footage" |
| Wayanad scenario | OSM roads, road states from cited 2024 reports | "Scenario reconstructed from reports, not drone-measured" |
| Thresholds (vehicle clearances, slopes, helicopter sizes, panel rule, priority weights) | config files | every one marked `PLACEHOLDER` until sourced |
| Measurements | computed from our height models | each with its tolerance, or "not measured yet" |

Our planned survey flights on 29–30 Oct were cancelled by rain. We will fly our own survey with checkpoints before the 21 Nov round.

## Results so far (from `data/runs/`, this laptop: i5-13420H, 16 GB, RTX 4050)
| Run | Images | Time | Peak memory | Area | Notes |
|---|---|---|---|---|---|
| USGS F01-5 strip, quick tier | 109 | 50.4 min | 6.97 GiB | 10.12 ha | ~5.0 min/ha |
| USGS F01-5 strip, full tier | 109 | 66.6 min (incremental) | 7.01 GiB | 9.07 ha | DSM/DTM at 0.10 m |
| USGS F01-4 block (5 parallel lines), quick tier | 248 | 145.6 min | 8.61 GiB | 12.94 ha | ~11.2 min/ha; GPU feature extraction |
| USGS F01-4 block, full tier (height models) | 248 | 171.4 min (incremental) | 11.0 GiB | 13.19 ha | DSM/DTM at 0.10 m |
| Our DJI Neo 2 video (220 frames), quick tier | 220 | 67.7 min | 8.24 GiB | 4.32 ha extent | 7 pieces joined by GPS; open ground clean, buildings smeared, so usable area is smaller (not measured); no checkpoints |

**Accuracy without ground control (USGS RTK checkpoints):**
| Flight geometry | Checkpoints | Horizontal RMSE | Max |
|---|---|---|---|
| One straight line (F01-5) | 2 | 34.2 m | 34.4 m |
| Block of 5 parallel lines (F01-4) | 3 | **6.1 m** | 7.6 m |

The USGS checkpoints are NAD83(2011) (stated in their metadata); we convert them to the map's WGS84 frame first (`accuracy/datum.py`, 1.5 m at this site). That converts the reference, never the map.

One straight line lets the model roll about the line (errors 34.7–34.8 m across it, 3–5 m along it). **Capture rule we derived: never map from one straight line; fly at least two parallel lines.** **Vertical (block):** absolute heights are off by +43 m (consumer-GPS camera altitudes), but heights **relative to nearby ground are good to ±1.1 m** (326 surveyed ground points). Volumes and heights are relative, so their tolerances use the ±1.1 m figure. N is small (ASPRS asks for ≥ 30), so treat these as prototype measurements.

## Run it (Windows)
Needs Docker Desktop (WSL2), `uv`, Node 22, ffmpeg, exiftool.
```
uv sync
uv run pytest
cd web && npm install && npm run build && cd ..
```
**1. Images in.** Either a photo survey, or a drone video turned into geotagged stills:
```
uv run python -m pipeline.subset --images <photo folder> --rtk <checkpoints.csv> --out-dir <dir>
uv run python -m pipeline.video_frames --video <clip.mp4> --project <name>
```
**2. Map.** Quick tier first (orthophoto), full tier later (adds DSM/DTM). Each run is logged in `data/runs/<run_id>/` with time and peak memory. Ground control is refused on purpose: checkpoints only measure error.
```
uv run python -m pipeline.run_odm --project <name> --tier quick --images-list <list.txt> --extra --feature-type sift
uv run python -m pipeline.run_odm --project <name> --tier full  --images-list <list.txt> --extra --feature-type sift
```
**3. Accuracy** (only where surveyed checkpoints exist). `find_targets` saves crops; a person confirms the IDs in `confirmed.json` before errors are computed.
```
uv run python -m accuracy.find_targets --ortho <odm_orthophoto.tif> --rtk <checkpoints.csv> --out data/runs/<run_id>/targets
uv run python -m accuracy.compute_errors --confirmed data/runs/<run_id>/targets/confirmed.json --rtk <checkpoints.csv> --run-id <run_id> --out data/runs/<run_id>/accuracy.json --dsm <dsm.tif>
uv run python -m accuracy.vertical --dtm <dtm.tif> --rtk <checkpoints.csv> --accuracy data/runs/<run_id>/accuracy.json
```
**4. Roads, tiles, 3D, serve.** OSM roads are fetched once beforehand (`scripts/prefetch_osm_southfork.py`); nothing touches the internet after that.
```
uv run python -m roads.segments --osm data/prefetch/osm_southfork.gpkg --dsm <dsm.tif> --dtm <dtm.tif> --ortho <odm_orthophoto.tif> --accuracy data/runs/<run_id>/accuracy.json --out data/projects/<name>/roads
uv run python -m pipeline.tiles --ortho <odm_orthophoto.tif> --project <name>
uv run python -m pipeline.terrain --dsm <dsm.tif> --ortho <odm_orthophoto.tif> --project <name>
uv run python -m pipeline.activate --run <quick_run_id> --full <full_run_id> --accuracy data/runs/<run_id>/accuracy.json
uv run python -m api.main
```
Then open `http://localhost:8000` (laptop) or `http://<laptop-ip>:8000` (phone on the hotspot). Field reports: `/field`. Advisor setup (Neo4j, Wayanad): [docs/runbook_advisor.md](docs/runbook_advisor.md).

## Repo map
| Folder | What |
|---|---|
| `pipeline/` | ODM runner with benchmarks, subset picker, Neo 2 telemetry/frames, tiles, 3D terrain |
| `accuracy/` | target finder, checkpoint errors → `accuracy.json`, spec endpoint |
| `measure/` | span, debris volume, landing zones, working space (+ API) |
| `roads/` | road segment measurements from the height model |
| `advisor/`, `api/`, `quality/`, `ml/`, `export/` | teammate: decisions, offline server and field page, quality checks, exports |
| `web/` | map, panels, 3D view |
| `contracts/` | JSON Schemas shared by both halves, with mock examples |

## Licences and AI disclosure
- Data: [data/LICENSES.md](data/LICENSES.md) (USGS public domain; OpenStreetMap ODbL)
- AI-assisted work: [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md)
