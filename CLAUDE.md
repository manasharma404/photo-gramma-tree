# CLAUDE.md: T8.2 "The First Map After The Landslide" (hackFront India 2026)

Save this file as `CLAUDE.md` in the repo root. It's the starting brief for Claude Code. The single source of truth for owners, timeline, bugs and decisions is `PLAN.md`, which you create in step 3 of section 16.

---

## Update 2, 30 Oct 2026, 11 pm IST: overrides everything below where they differ

**Laptop (confirmed):** Intel Core i5-13420H (8 cores, 12 threads), **16 GB RAM**, NVIDIA RTX 4050 laptop GPU (6 GB), about 119 GB free disk. Ignore the 8 GB settings in Update 1 and use these:
- **WSL memory:** in `.wslconfig`, set `memory=12GB`, `swap=16GB`, `processors=10`. Ask me before changing it.
- **Subsets:** start around 150 images. Grow toward 300 only after measuring peak memory.
- **Quick tier:** `--fast-orthophoto --skip-3dmodel --feature-quality high --max-concurrency 4 --orthophoto-resolution 5`
- **Full tier:** `--dsm --dtm --skip-3dmodel --pc-quality medium --feature-quality high --dem-resolution 10 --orthophoto-resolution 5 --max-concurrency 4 --cog`. If peak memory gets near the WSL limit, drop to `--pc-quality low --max-concurrency 2`.
- **Disk:**
  - download 2–3 of the USGS zips (about 4–6 GB) first, and delete each zip after extracting
  - ODM's working folders can be several times the input size, so keep at least 30 GB free
  - check free space before each run

**New split:**
- **The lead (you work with her): mapping and 3D.** `pipeline/`, `accuracy/`, `measure/`, `roads/` (road status from the height model), `export/`, `web/` (map + 3D view), `api/` (the main app).
- **Teammate: the route advisor.** `advisor/` holds the Neo4j graph, routing per vehicle type, field dead-end reports and the phone page. `ml/` is optional. The separate `access/` folder is dropped; it lives inside `advisor/`.
- **Integration:**
  - mount her FastAPI `APIRouter` at `/advisor` (`app.include_router(...)`) and serve her phone page at `/field`
  - `web/` colours roads from `GET /advisor/state`
  - give her `segments.geojson`, `places.geojson`, and landing zones as facilities, for the South Fork area
  - her Wayanad scenario doesn't depend on us
- **Phone GPS:** browsers only share GPS on https or localhost. Her page defaults to "tap where you are", and we don't need https for the demo.

**The Neo 2 videos:**
- **Saving:** two files received as WhatsApp **documents** (379 MB and 1.2 GB). Documents aren't recompressed, so save them from WhatsApp Desktop straight into `data/raw/neo2/` (gitignored). Don't re-save them through any app that re-encodes.
- **Check each file** and write `data/raw/neo2/video_report.json`:
  - `ffprobe`: resolution, frame rate, duration, bitrate, creation time
  - `exiftool -ee -G3`: any GPS track stored inside the MP4 (some DJI drones do this)
  - brightness: mean luminance of about 20 sampled frames. The file names suggest 20 Aug at about 10:40 pm, so check for night footage
  - sharpness: variance of the Laplacian on the same frames
- **Then run the video tier.**
  - **No GPS:** the result has no real position or scale; label it.
  - **Too dark or blurry to map:** keep the clip as "what responders have today" and report the failure with numbers.
- **Tomorrow morning:** the drone owner can connect the Neo 2 by USB-C and copy the original `DJI_*.MP4` files plus any `.SRT` files. If those exist, rerun with GPS.

---

## Update 1, 30 Oct 2026, 10:40 pm IST: data plan (still valid; memory settings replaced by Update 2)

**What changed**
- **Rain cancelled the survey flights.** About 25 hours remain before the deadline.
- **Drone:** a DJI Neo 2 (151 g nano drone; 12 MP 1/2-inch sensor; rolling shutter). It can't fly automated grids, and its videos only carry GPS if Video Subtitles (.SRT) was turned on, unless GPS is embedded in the MP4; check with `exiftool -ee`.
- **Laptop:** 8 GB RAM (assumed to be system RAM; confirm in step 1) and an NVIDIA RTX 4050 laptop GPU. **Memory is the bottleneck.**

**New data plan**
1. **Primary validation dataset:** USGS, "Aerial imagery and structure-from-motion derived data products from a UAS survey of the debris flow at South Fork Campground, Sequoia National Park, CA". Flown 30 Apr 2024; DOI 10.5066/P144KDGN; public domain, credit USGS.
   - **Raw images:** nadir JPGs, 3264 × 4928, Ricoh GR II (global shutter), about 110 m above ground, about 2.9 cm per pixel. Geotagged from the drone's onboard single-frequency GPS: USGS estimates about 3 m horizontal and 10 m vertical, the same class as a consumer drone. Seven zips, about 10.8 GB in total. ScienceBase item `67353631d34e6fbce7b5d58f`; list the files with `https://www.sciencebase.gov/catalog/item/67353631d34e6fbce7b5d58f?format=json`.
   - **Reference points:** 23 RTK-surveyed ground control tarps plus backpack RTK topography, in `SEKI_SouthFork_DebrisFlow_2024_RTK_GNSS.csv` (172 KB, ScienceBase item `6735365ad34e6fbce7b5d592`).
   - **USGS reference products:** 3 cm orthomosaic, DSM, and a point cloud with stated RMSE of 0.040 m horizontal and 0.085 m vertical (made with their ground control).
   - **How we use it:** run our pipeline **without** their ground control (GPS only, as the brief requires). Then measure our error at every RTK tarp inside our subset; these are our "known reference points". Compare our heights with the RTK topography points and the USGS DSM.
   - **Datum check first:** read the CSV's horizontal and vertical datum. USGS often uses NAD83(2011) with NAVD88 heights, while our output is WGS 84 with GPS heights. Convert before computing errors, or the datum difference will pollute the numbers. For heights, also report **relative** values (pile height above surrounding ground), where a constant offset cancels.
2. **Our own footage:** the Neo 2 videos already recorded, through the video tier. Without GPS, the reconstruction has no real-world position or scale. Label it, and scale it only from an object we measured.
3. **Before/after change:** USGS Medina River (2019 vs 2022) if time allows; otherwise skip and say so.
4. **Indian scenario:** for the access graph (teammate), OSM roads of an Indian landslide area with road states taken from cited reports, labelled "scenario reconstructed from reports, not drone-measured".
5. **README disclosure (draft):** "Our planned survey flights on 29–30 Oct were cancelled by rain. Accuracy and measurement validation in this prototype use the USGS South Fork Campground debris-flow survey (public domain), processed without its ground control, plus our own DJI Neo 2 video for the consumer-drone video path. We will fly our own survey with checkpoints before the 21 Nov round."

**Memory-safe processing (8 GB RAM; superseded by Update 2, since the laptop has 16 GB)**
- **WSL memory:** in `%UserProfile%\.wslconfig`, set `memory=6GB`, `swap=16GB` and `processors=<cores minus 2>`. Close browsers during runs. **Ask me before changing it.**
- **GPU check:**
  ```
  docker run --rm --gpus all --entrypoint nvidia-smi opendronemap/odm:gpu
  ```
  Expect a table naming the RTX 4050. If it fails, use the CPU image `opendronemap/odm`.
- **GPU run** (CUDA feature extraction, per the ODM README):
  ```
  docker run --rm --gpus all --name odm_<run_id> -v C:/Users/<you>/t82/data/projects:/datasets opendronemap/odm:gpu --project-path /datasets <project> <flags>
  ```
- **Subsets:** start with about 80–120 images, chosen by EXIF GPS to cover the debris flow and as many RTK tarps as possible. Grow only after measuring peak memory.
- **Quick tier:** `--fast-orthophoto --skip-3dmodel --feature-quality medium --max-concurrency 2 --orthophoto-resolution 5`
- **Full tier:** `--dsm --dtm --skip-3dmodel --pc-quality low --feature-quality medium --dem-resolution 10 --orthophoto-resolution 5 --max-concurrency 2 --cog`
- **Neo 2 video tier:** `--video-limit 300 --fast-orthophoto --skip-3dmodel --feature-quality medium --max-concurrency 2`
- **3D view:** render a terrain mesh from DSM + orthophoto in three.js instead of ODM's textured model. It uses less memory and shares the measurements' coordinates.
- **If a run dies from lack of memory,** halve the subset. Try `--split` only after a test.

**Revised first session (replaces section 16)**
1. `data/machine.json`; confirm whether 8 GB is system RAM.
2. Docker and GPU check (above). Pull `opendronemap/odm:gpu` and `opendronemap/odm`.
3. Skeleton, `PLAN.md` and contracts, if not done yet.
4. Download the RTK CSV and the **smallest** image zip.
   - read the EXIF GPS of every image
   - plot the image centres against the tarp positions
   - pick the subset and save it as `data/public/usgs_southfork/subset.txt`
   - record the licence in `data/LICENSES.md`
5. Quick tier on the subset → `run.json` (time, peak memory, area, GSD).
6. **Accuracy:**
   - find the tarps in our orthophoto (template matching on the cross pattern, else a manual click)
   - convert datums
   - compute the errors → `accuracy.json`, with N stated
7. **Full tier → DSM:**
   - compare heights with the RTK topography points (absolute after datum conversion, and relative)
   - write the results → `docs/validation.md`
8. Neo 2 video tier. Record whether GPS exists, and what that means for scale and position.
9. Measure endpoints on the South Fork DSM: debris volume over a deposit, landing zones, and a span across a channel if one exists.

**Revised timeline (IST)**
| When | Target |
|---|---|
| 30 Oct, to about 2 am | Downloads, subset, quick tier, first accuracy numbers |
| 31 Oct, morning | Full tier, validation table, Neo 2 video run |
| 31 Oct, 4 pm | Teammate's `ml_scores.json` and `access_report.json` integrated |
| 31 Oct, 7 pm | Exports tested; offline test with Wi-Fi off and a phone on the hotspot |
| 31 Oct, 9:30 pm | Code freeze, then rehearsal; submit by 11 pm |

---

## 0. How to work with me (read first)

**Who I am:** `[lead name]`, team lead. I'm a trained designer with 3D/CAD skills, building my backend skills. I drive the backend and the 3D measurement engine with you.
- Explain technical things in plain language and define jargon the first time.
- **For anything bigger than a small change, give me a plan in 3–6 bullets first.**
- **Commands:** one command per code block, with what to expect after it. I'm on **Windows** (PowerShell), with Docker Desktop on WSL2. Check before assuming.
- **Push back** when I'm wrong, with reasons, and offer the grounded alternative.
- **Never cut something the brief requires** without asking me. If it's hard, say how hard and propose the cheapest honest way.

**Hard rules**
1. **Never invent a number.** Every figure in the UI, README or pitch comes from a file a run produced, or is labelled `ESTIMATE` or `PLACEHOLDER`. Mock data carries `"mock": true` and obviously fake values.
2. **Measured vs estimated:** every output field that is a measurement says so, with its method and tolerance.
3. **Offline at runtime:** the pipeline and API make **no internet calls**. Downloads happen only in `scripts/prefetch_*.py`, run while online.
4. **Original work:** the rules require work built during the league. Don't copy code from our earlier projects (NETRA, MineGuard). Open-source libraries are fine with attribution.
5. **AI disclosure:** log AI-assisted work in `docs/AI_DISCLOSURE.md`. The rules require disclosure at submission.
6. **Data licences:** record every external dataset in `data/LICENSES.md` (source, licence, date, what we use it for). Public data is labelled as public in the UI and never presented as our footage.
7. **Git:**
   - small commits
   - never commit `data/` contents (raw images and outputs are big)
   - never force-push
   - show the diff and ask before pushing
8. **Contracts:** never change a JSON contract in `contracts/` without updating its example and logging the decision in `PLAN.md`.
9. **If something is impossible, or will take more than 2 hours beyond plan,** stop and tell me, with options. Don't improvise around it.
10. **Time limit:**
    - prototype submission closes **31 Oct 2026, 11:59 pm IST**
    - code freeze **31 Oct, 9:30 pm IST**
    - if we're behind, ship what works and list what's left

---

## 1. The problem statement (verbatim)

> **PS T8.2 The First Map After The Landslide**
> Build type: Measurement and data
> Responders need a current map in three hours. The satellite pass is on Thursday.
>
> **The situation:** A landslide closes a valley. A flood rearranges a district. The response team needs to know which roads exist, where the damage is, and where people are cut off. The available satellite pass is days away and may be under cloud. Somebody has a consumer drone. What they do not have is a way to turn an hour of flying into a usable map on a laptop, in the field, with no internet and unreliable power.
>
> **The problem:** Build a rapid mapping workflow that turns consumer drone footage into a georeferenced current map and a change report, entirely offline, on a laptop, in hours.
>
> **Why the current answers fail:** Photogrammetry software is cloud based, slow, or both, and the field has neither bandwidth nor patience. Accurate georeferencing normally expects ground control points that nobody is placing during a disaster. Satellite tasking is too slow for the first day and cloud cover often removes the option entirely. Video of the damage is not a map, and responders cannot plan from footage.
>
> **What we expect you to build:** A capture protocol simple enough for a stressed pilot to follow correctly the first time. Stitching and georeferencing without ground control points, with the resulting positional error stated honestly. Comparison against the last known state from open imagery, producing what changed and where access is blocked. Complete offline operation on a laptop, with a stated processing time for a stated area. Output in formats the responding agencies already use, because a proprietary map is a map nobody opens.
>
> **Data and stack:** Open photogrammetry tooling, open base imagery, and footage you capture yourself over any terrain, flying only where permitted. Geometry and image processing. Note that this problem statement is deliberately distinct from PS T8.1, which watches slowly from orbit; this one is fast, low, and offline.
>
> **The layer beneath:** Accuracy without ground control. Positional error accumulates across a stitched survey and, in a disaster response, being confidently wrong about where a blocked road is has consequences. Bounding and reporting that error honestly, rather than producing a beautiful map with unknown accuracy, is the professional difference and it is what we will look for.
>
> **What the judges will reward:** Positional error measured against known reference points. Processing time for a stated area on a normal laptop. Output a response agency could actually open and use.
>
> **Where this goes after hackFront:** Disaster management authorities, infrastructure owners, insurers and mining operations all need current maps quickly. This starts as a service delivered by a small team with a drone and becomes a product once the workflow is reliable, which is a sensible order for a hardware adjacent business.

**Prototype rubric** (from the event page):
1. Problem statement and track alignment
2. Innovation and solution effectiveness
3. Technical implementation and code quality
4. Functionality and prototype validation
5. Critical thinking and practical implementation

**Important:** "Without ground control points" means the main pipeline must **not** use GCPs. Our ground targets are **checkpoints only**, used to measure error and never to correct the map.

---

## 2. Our approach in one screen

**Story:** "Measure before you mobilise." In the first hours, the big decisions are measurements nobody has taken yet:
- the span of a washed-out crossing, and the bridge panels it needs
- working space at each bank
- debris height and volume on each road
- where a helicopter can land
- who is cut off, and which clearance reconnects the most people

Our tool takes those measurements from one drone flight, on a laptop, offline.

**Grounding (for context; the pitch is not your job):** at Wayanad in 2024, Army engineers built a 190-ft Bailey bridge from 19 ten-foot panels in 31 hours. In Dharali in 2025, the air lifeline and the helipad question dominated.

**What we show, in order:**
1. Router unplugged; our own flight loaded; timer running.
2. The map arrives: processing time and area shown.
3. Roads coloured by status per vehicle type; cut-off places in red; an "act now" list.
4. Reopen plan: the clearance that reconnects the most people (Neo4j).
5. 3D measuring view: span and panel estimate, working space, landing zones, debris depth and volume.
6. Exports open in QGIS and Google Earth, plus a printable PDF and a local-language situation report.
7. A spec sheet: positional accuracy at N checkpoints, minutes per hectare on this laptop.

**Tone:** we state accuracy as a **spec** ("±X m at N checkpoints"), not as an apology.

---

## 3. Scope

| Priority | Item | By |
|---|---|---|
| Must | OpenDroneMap (ODM) pipeline: quick and full tiers, timing, peak memory, area | 31 Oct |
| Must | Accuracy report from our checkpoints, plus relative distances from tape | 31 Oct |
| Must | Road segment status per vehicle type, from height model geometry (+ML score if ready) | 31 Oct |
| Must | Measurement API: span, debris height/volume, landing zones, working space | 31 Oct |
| Must | Validation table: tool vs tape for at least one span, one pile and one staged block | 31 Oct |
| Must | Exports: Cloud-Optimized GeoTIFF, KMZ, GeoPackage, GeoJSON, printable PDF | 31 Oct |
| Must | Runs with Wi-Fi off; map opens on a phone over the local network | 31 Oct |
| Must | Before/after change between our F1 and F5 flights (staged), plus OSM roads as last known state | 31 Oct |
| Should | Video-to-map path (MP4 + SRT through ODM) | 31 Oct |
| Should | Access report from Neo4j (owned by teammate; we supply inputs) | 31 Oct |
| Could | Debris-depth search-sector map, glTF/3D Tiles export, Sentinel-2 before layer | 31 Oct |
| Later | Gaussian-splat flythrough (OpenSplat), GPS-vs-imagery cross-check, offline voice, CAD bridge drop-in polish, 3D-printed terrain | 21 Nov finale |

---

## 4. Architecture

```
 our flights / public data
        │  (images or MP4+SRT, ground-truth CSVs)
        ▼
 pipeline/  ── ODM in Docker (quick tier → full tier) ──► products: orthophoto, DSM, DTM, point cloud, GLB
        │          timing + peak memory + area                     │
        ▼                                                          ▼
 accuracy/ (checkpoints → RMSE)                   measure/ (span, volume, landing zones, working space)
        │                                                          │
        ▼                                                          ▼
 roads/ (OSM segments + height-model geometry + ML scores) ──► roads/segments.geojson
        │                                                          │
        ├──────────────► access/ (teammate: Neo4j graph → access_report.json)
        ▼
 export/ (COG, KMZ, GPKG, GeoJSON, PDF, tiles)      api/ (FastAPI, serves everything + web/ build, offline)
                                                    web/ (MapLibre 2D, three.js 3D, act-now cards)
```

- **Coordinate systems:** all maths runs in the site's UTM zone. Delhi NCR is UTM 43N, EPSG:32643; check for the actual site. Exports go in EPSG:4326 where formats need it (GeoJSON, KMZ).
- **Storage:** plain files under `data/` plus a small JSON run registry. No database is needed except Neo4j for the access graph.

---

## 5. Repo layout and ownership

```
CLAUDE.md                this file
PLAN.md                  owners, timeline, bug table, decisions (single source of truth)
README.md                how to run, measured vs estimated, licences, AI disclosure link
contracts/               JSON Schemas + example files (mock: true)
config/
  vehicles.yaml          passability thresholds per vehicle (PLACEHOLDERS until sourced)
  helicopters.yaml       dimensions per helicopter type (PLACEHOLDERS until sourced)
  bridging.yaml          panel rule (PLACEHOLDER until sourced)
pipeline/                ingest, ODM runner, video handling, benchmark capture        (lead)
accuracy/                checkpoint matching, ArUco detection, RMSE, relative distances (lead)
measure/                 surfaces, span, volume, landing zones, working space          (lead)
roads/                   OSM segments, geometry status, fusion with ML scores        (lead)
export/                  COG, KMZ, GPKG, GeoJSON, PDF, tiles                          (lead)
api/                     FastAPI app                                                  (lead)
web/                     frontend (MapLibre + three.js)                               (lead)
ml/                      road-status model + predict CLI                              (teammate)
access/                  Neo4j loader, queries, reopen ranking                        (teammate)
scripts/                 prefetch_*.py (online only), run helpers, QR code
docs/                    AI_DISCLOSURE.md, demo_runbook.md, validation.md
data/                    gitignored: raw/, public/, projects/, runs/, prefetch/, machine.json, LICENSES.md (tracked)
tests/
```

Only `data/LICENSES.md` inside `data/` is tracked by git.

---

## 6. Data contracts

Create a JSON Schema plus an example file for each in `contracts/`. **Examples use nulls or `"mock": true`, never realistic-looking invented numbers.**

**`run.json`** (one per processing run)
```json
{
  "mock": true,
  "run_id": "2026-10-29_siteA_F1_quick",
  "project": "siteA",
  "inputs": {"kind": "images|video", "count": null, "source_folder": "data/raw/2026-10-29_siteA/F1_grid_before"},
  "tier": "quick|full",
  "odm_image": "opendronemap/odm:<pinned tag>",
  "odm_options": ["--fast-orthophoto", "--skip-3dmodel"],
  "machine_file": "data/machine.json",
  "status": "queued|running|done|failed",
  "started_at": null, "ended_at": null,
  "stages": [{"name": "<as printed by ODM>", "started_at": null, "seconds": null}],
  "total_seconds": null,
  "peak_memory_gb": null,
  "area_ha": null,
  "gsd_cm": null,
  "products": {"orthophoto": null, "dsm": null, "dtm": null, "point_cloud": null, "glb": null, "kmz": null}
}
```

**`accuracy.json`**
```json
{
  "mock": true,
  "run_id": null,
  "used_gcps": false,
  "n_checkpoints": null,
  "checkpoint_method": "rtk|dgps|phone",
  "checkpoint_stated_accuracy_m": null,
  "horizontal": {"rmse_x_m": null, "rmse_y_m": null, "rmse_h_m": null, "max_error_m": null},
  "vertical": {"rmse_v_m": null, "max_error_m": null},
  "relative": [{"from": "T1", "to": "T2", "taped_m": null, "map_m": null, "diff_m": null}],
  "per_point": [{"id": "T1", "dx_m": null, "dy_m": null, "dz_m": null, "found_by": "aruco|manual"}],
  "standard_note": "ASPRS Positional Accuracy Standards Ed. 2 (2023) ask for at least 30 checkpoints for full compliance; this assessment uses n_checkpoints."
}
```

**`segments.geojson`** (LineString features; properties below)
```json
{
  "mock": true,
  "segment_id": "seg_0001",
  "osm_way_id": null,
  "highway": "track",
  "length_m": null,
  "corridor_width_m": null,
  "corridor_width_source": "osm_tag|default_by_class(PLACEHOLDER)",
  "coverage_fraction": null,
  "max_obstruction_m": null,
  "obstructed_length_m": null,
  "min_clear_width_m": null,
  "debris_volume_m3": null,
  "debris_volume_tolerance_m3": null,
  "status_by_mode": {"truck": "open|partial|blocked|unknown", "jeep": "...", "foot": "..."},
  "ml": {"p_blocked": null, "model": null},
  "decision": "geometry|ml|agree|disagree_review",
  "measured": true
}
```

**`measurement.json`** (returned by every measure endpoint)
```json
{
  "mock": true,
  "type": "span|volume|landing_zones|working_space",
  "run_id": null,
  "input_geometry": {"type": "LineString|Polygon|Point", "coordinates": []},
  "result": {},
  "tolerance": {"value": null, "unit": "m|m3", "method": "how the tolerance was derived"},
  "rule_source": null,
  "placeholders_used": [],
  "measured": true
}
```
The `result` field by type:
- **span:** `{span_m, bank_a_height_m, bank_b_height_m, bed_elevation_m, profile_png, panel_estimate: {count, rule: "config/bridging.yaml"}}`
- **volume:** `{volume_m3, area_m2, max_height_m, reference_surface: "self-referenced corridor fit|polygon-rim fit"}`
- **landing_zones:** `{helicopter, candidates: [{polygon, fato_side_m, max_slope_deg, max_obstacle_in_safety_area_m, approach_dirs_checked, approach_beyond_map}]}`
- **working_space:** `{rectangle_polygon, width_m, length_m, max_slope_deg, requirement_m (PLACEHOLDER)}`

**`ml_scores.json`** (teammate → us): `[{"segment_id", "p_blocked", "p_partial", "p_clear", "model", "version"}]`

**`access_report.json`** (teammate → us):
```json
{
  "mock": true,
  "modes": ["truck", "jeep", "foot"],
  "places": [{"place_id": null, "name": null, "population": null, "population_source": "PLACEHOLDER",
              "reachable": {"truck": null, "jeep": null, "foot": null}, "facility": null}],
  "reopen_plan": [{"rank": 1, "segment_id": null, "reconnects_people": null, "reconnects_places": null, "debris_volume_m3": null}],
  "computed_with": "neo4j-gds|networkx-fallback"
}
```

**`spec.json`**: `{accuracy (from accuracy.json), timing: {area_ha, total_minutes, minutes_per_ha, tier}, laptop (from machine.json), validation: [{what, tool_value, taped_value, diff, unit}], data_sources, generated_at}`

---

## 7. Pipeline (ODM)

**Tiers**
| Tier | Purpose | ODM options (starting point; tune after the first run) |
|---|---|---|
| quick | First 2D map, fast | `--fast-orthophoto --skip-3dmodel --orthophoto-resolution <≈GSD>` |
| full | Height models for measuring, plus 3D | `--dsm --dtm --orthophoto-resolution <≈GSD> --dem-resolution <2×GSD> --pc-quality medium --feature-quality high --cog --orthophoto-kmz --build-overviews --gltf` |
| video | Video + SRT input | Put `name.mp4` and `name.srt` (same name) in `images/`; `--video-limit 500 --video-resolution 4000` are the defaults; tune |

**Options to try:**
- `--sfm-algorithm planar` for flat straight-down flights (faster)
- `--rolling-shutter` if the camera has a rolling shutter and the photos were taken in motion
- `--max-concurrency` to fit memory (about 1 GB per thread at 2 MP, per ODM docs)

**Never use `--gcp` in the main pipeline** (see section 1).

**Run** (Windows; the dataset folder contains `<project>/images/`):
```
docker run -ti --rm --name odm_<run_id> -v C:/Users/<you>/t82/data/projects:/datasets opendronemap/odm --project-path /datasets <project> --fast-orthophoto --skip-3dmodel
```
Expect ODM to print each processing stage. In `pipeline/run_odm.py`, drop `-ti`, so stdout can be piped and timestamped. Outputs land in `data/projects/<project>/`. The orthophoto is at `odm_orthophoto/odm_orthophoto.tif`. With `--dsm`/`--dtm`, the height models are at `odm_dem/dsm.tif` and `odm_dem/dtm.tif`. The point cloud is at `odm_georeferencing/odm_georeferenced_model.laz`. Native Windows ODM (installer on the releases page) is a fallback if Docker misbehaves.

**Benchmark capture** (`pipeline/benchmark.py`):
- **Stage times:** timestamp every stdout line as it arrives. Stage boundaries are the lines where ODM announces a stage; confirm the exact text on the first run and set the regex. Write the stage times to `run.json`.
- **Peak memory:** sample `docker stats --no-stream --format "{{.MemUsage}}" odm_<run_id>` every 2 s and keep the maximum.
- **Area:** count valid (non-nodata) orthophoto pixels × pixel area, in hectares.
- **GSD:** from the orthophoto's pixel size.
- **Machine:** write `data/machine.json` once (CPU model, cores, RAM, GPU, OS, disk free). It feeds the spec sheet.

---

## 8. Accuracy (`accuracy/`)

- **Inputs:**
  - `ground_truth/checkpoints.csv`: `id,lat,lon,alt_m,method,stated_accuracy_m,notes`
  - `ground_truth/distances.csv`: `from_id,to_id,distance_m,method`
- **Finding targets in the orthophoto:**
  - **First choice:** ArUco markers (DICT_4X4_100) detected with OpenCV (`cv2.aruco.ArucoDetector`). Read the orthophoto in windows around each checkpoint's expected position.
  - **Fallback:** manual click in the web UI, saved to `checkpoints_found.json`.
  - Find-GCP (GPL-2.0) is the reference tool for these markers.
- **Error and RMSE:**
  - per point: `dx, dy` in UTM metres; `dz` = DSM height minus surveyed altitude, only when the survey method gives usable heights (RTK/DGPS)
  - `RMSE_x`, `RMSE_y`
  - `RMSE_H = sqrt(RMSE_x² + RMSE_y²)`
  - `RMSE_V`
- **Relative accuracy:** taped distance vs map distance for each pair.
- **Reporting:**
  - always state N, the checkpoint method and that method's accuracy
  - phone GPS checkpoints are metre-level, so label them as such
  - ASPRS Ed. 2 counts checkpoint uncertainty in the product accuracy and asks for ≥30 checkpoints for full compliance

---

## 9. Measurement engine (`measure/`)

Shared ideas:
- **Height above surroundings:** the obstacle height model is DSM − reference surface. Prefer a **self-referenced** surface fitted from undisturbed ground around the feature, over ODM's DTM, because the DTM filter can treat large piles as ground. Test both against the staged block of known volume.
- **Tolerances:**
  - horizontal values: derived from `RMSE_H` (conservative: `±sqrt(2)·RMSE_H` for a distance between two picked points)
  - heights: `±RMSE_V`
  - volumes: conservative bound `±RMSE_V × footprint area`
  - label each "conservative bound"
- **Placeholders:** every threshold lives in `config/*.yaml`, marked `PLACEHOLDER` until sourced; the response lists the placeholders used.

**Road status** (`roads/`):
1. OSM `highway=*` ways clipped to the map footprint, then split into segments of ≤ 50 m.
2. Corridor: buffer by half the road width (from the OSM `width` tag, else a per-class default `[PLACEHOLDER]`).
3. Stations every 1 m along the centreline:
   - per cross-section, a low percentile of DSM gives the road-surface estimate
   - fit a smooth profile along the segment, flag residuals above `obstruction_min_m` `[PLACEHOLDER]`, then refit without them
4. Per segment:
   - max obstruction height
   - obstructed length
   - minimum clear width
   - debris volume
   - coverage fraction (share of the corridor with data)
5. Status per mode from `config/vehicles.yaml` (clear width and height limits per vehicle `[PLACEHOLDER]`). Use `unknown` when coverage is low or a value sits within its tolerance of a threshold.
6. Fusion with teammate's `ml_scores.json`:
   - agree → keep
   - disagree → `disagree_review`
   - never let the model silently flip a geometric "blocked" to "open"

**Span** (`POST /measure/span`, input LineString across the gap):
- sample DSM along the line every 0.1 m
- bank tops = outermost points where the profile drops by ≥ `bank_drop_min_m` `[PLACEHOLDER]`
- report span, bank heights and bed elevation
- panel estimate per `config/bridging.yaml`: `[PLACEHOLDER: confirm against Army bridging tables]`. Context only: Wayanad used 19 × 10-ft panels for 190 ft
- save a profile PNG

**Volume** (`POST /measure/volume`, input Polygon or a segment id):
- reference surface fitted to the polygon's rim (a plane or low-order surface)
- volume = Σ max(0, DSM − ref) × pixel area
- report max height and area
- validate against the staged block (known L × W × H)

**Landing zones** (`POST /measure/landing-zones`, input helicopter type from `config/helicopters.yaml`):
Rules from the Goa Directorate of Civil Aviation's helicopter operations document:
- touchdown area ≥ 2B × 2B (B = wheel or skid base)
- final approach and take-off area ≥ 1.5A × 1.5A (A = overall length), without obstructions
- safety area ≥ 10 m wide with no obstacle taller than 1 m
- approach climb surface 8% for ≥ 245 m

Method:
- slope from the DTM; obstacles from DSM − DTM
- slide square candidates; keep those within the slope limit `[PLACEHOLDER]` that have a clear safety ring
- check the 8% surface in 8 directions inside the mapped area
- set `approach_beyond_map: true` when 245 m runs past our data, and say so in the UI

**Working space** (`POST /measure/working-space`, input point plus required size `[PLACEHOLDER]`):
- build a mask: slope within limit and obstacle under limit
- distance transform → largest inscribed rectangle near the point
- report its size against the requirement

**Debris depth and search sectors** (Could): grid cells ranked by obstacle height over debris areas, overlaid with Google Open Buildings footprints. Label it "for planning search sectors; verify on the ground".

---

## 10. Access graph interface (owned by teammate)

We provide:
- `data/projects/<p>/roads/segments.geojson` (contract above)
- `data/projects/<p>/places.geojson`: OSM `place=*` nodes plus facilities (hospital, helipad candidates from `landing_zones`), with `population` left to the teammate

The teammate's `access/` module provides:
- `python -m access.load --project <p>`, which loads Neo4j
- `python -m access.report --project <p> --out access_report.json`

A NetworkX fallback must produce the same JSON for tests.

**Neo4j via Docker Compose.** Compose is safer on Windows, where PowerShell can mangle the quotes in the plugin list. Save as `neo4j/docker-compose.yml`:
```yaml
services:
  neo4j:
    image: neo4j:latest          # pin the tag after the first pull
    container_name: t82-neo4j
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/<password>
      NEO4J_PLUGINS: '["graph-data-science"]'
    volumes:
      - ./data:/data
      - ./plugins:/plugins
```
Start it from the `neo4j/` folder:
```
docker compose up -d
```
Expect the browser at http://localhost:7474. In the browser, `RETURN gds.version();` should print a version.
- **Start it once while online,** so the Graph Data Science plugin downloads into the mounted `plugins` folder. Later starts must work offline; test this.
- **Pin the image tag** you pulled and write it in `PLAN.md`.

---

## 11. Exports and offline serving

**Exports** (`export/`), each tested by opening it in its target app:
- **COG:** ODM `--cog`, or `gdal_translate -of COG`
- **KMZ** for Google Earth: ODM `--orthophoto-kmz`, plus our vector layers as KML
- **GeoPackage** for QGIS/ArcGIS, with layers `roads_status`, `blockages`, `measurements`, `landing_zones`, `checkpoints`, `cutoff_places`
- **GeoJSON** (EPSG:4326)
- **Printable PDF map:** orthophoto, overlays, coordinate grid, scale bar, north arrow, legend, flight time, accuracy line
- **Web tiles:** raster MBTiles → PMTiles, or ODM `--tiles`
- **Situation report:** Markdown/HTML. Translation is owned by the teammate (Sarvam Translate)

**Serving** (`api/`):
- FastAPI on `0.0.0.0:8000` serves the API, the built `web/` and the tiles
- no CDN links at runtime: bundle everything
- **Demo network:** a phone hotspot with mobile data off, or a pocket router. The laptop and the judges' phones join it, and `scripts/qr.py` prints a QR code for `http://<laptop-ip>:8000`
- `GET /health` reports internet reachable yes/no, so we can show "offline" truthfully

**Frontend** (`web/`): Vite + MapLibre GL JS (2D) + three.js (3D GLB from ODM `--gltf`).
- **Measurement maths happens in the backend.** The frontend sends geometry and draws results.
- **"Act now" cards:** title, place, numbers, status chip.
- **Road states** by shape and pattern, not only colour: passable, partial/foot-only, blocked (solid with ✕), unknown (grey hatch).
- **Build against `contracts/` mock files first,** so switching to live data is one setting.

---

## 12. Benchmarks and the spec sheet

`GET /spec` assembles `spec.json` from:
- `accuracy.json`
- the latest `run.json` for each tier
- `machine.json`
- `docs/validation.md` (tool vs tape)

The UI's spec card shows only those values. A missing value shows "not measured yet", never a guess.

---

## 13. Environment setup (Windows) and the prefetch list

**Do first:**
1. `docker version` should print client and server versions. If not, start Docker Desktop.
2. **Memory for Docker:** in `%UserProfile%\.wslconfig` set:
   ```
   [wsl2]
   memory=<about 75% of RAM>GB
   processors=<cores>
   ```
   then restart WSL. Ask me before changing it.
3. **Python 3.11+ virtual environment.** Core packages: `fastapi uvicorn[standard] pydantic rasterio numpy scipy shapely geopandas pyproj osmnx networkx neo4j opencv-contrib-python simplekml matplotlib psutil pyyaml laspy qrcode`. Install all while online, then freeze `requirements.lock`.

**Prefetch while online** (`scripts/prefetch_*.py`). The demo must not need any of these at runtime:
| What | Source | Note |
|---|---|---|
| Docker images | `opendronemap/odm` (+`:gpu` if there's an NVIDIA GPU), `neo4j` | Pin the tags |
| OSM roads and places for the site area | osmnx via Overpass (small bounding box) → GeoPackage; fallback: Geofabrik India "Northern Zone" `.osm.pbf` | ODbL; record it in LICENSES |
| Elevation | Copernicus DEM GLO-30, public S3 bucket `copernicus-dem-30m` (eu-central-1, `--no-sign-request`) | 30 m surface model, vertical error under 4 m at 90%; use for context and large slides only |
| Buildings | Google Open Buildings v3 tiles for the area | CC BY 4.0 |
| Satellite "before" view | Sentinel-2 L2A from Earth Search STAC `https://earth-search.aws.element84.com/v1`; check whether the collection id is `sentinel-2-l2a` or `sentinel-2-c1-l2a` | 10 m; a before layer for the slider |
| Public test data | See section 14 | Record licences |
| Model weights | Teammate's road model; Sarvam Translate (GPL-3.0) if used | Large; download early |

---

## 14. Test data plan

| Data | Use | Licence |
|---|---|---|
| **Our flights F1–F6 (29 Oct)** and ground truth | Everything we claim; demo footage | Ours |
| ODM sample dataset `mygla` (29 images, "good starter") or `aukerman` (77) | Pipeline smoke test today, before our footage arrives | Not stated on ODM's list; internal use only |
| ODM `zoo` (524 images) | Timing curve: minutes vs hectares | Same as above |
| USGS South Fork debris flow point cloud (30 Apr 2024; stated RMSE 4.0 cm horizontal, 8.5 cm vertical) | Check volume/height code against survey-grade data | Public domain |
| USGS Medina River UAS imagery + GCP info, 2019 and 2022 | Two-date change detection; checkpoint workflow | US government work |
| USGS Mud Creek landslide video (2017, 1 min) | Video-to-map without GPS (expect it to be hard; record what happens) | Public domain |
| CRASAR road-damage dataset and models | Teammate's ML (models are MIT on their model cards; check the dataset licence) | Check |

---

## 15. Milestones (IST) and definition of done

| When | Milestone |
|---|---|
| 29 Oct, morning | Environment ready; machine.json; skeleton + PLAN.md + contracts with mocks; ODM quick tier on `mygla` with run.json |
| 29 Oct, evening | Our flights ingested; quick tier on F1; full tier started overnight |
| 30 Oct | Accuracy report; road status v1; span/volume/landing/working-space v1; exports v1; validation table started; teammate's inputs delivered |
| 31 Oct, by 6 pm | Integration with access_report + ml_scores; offline test with Wi-Fi off and a phone on the hotspot; README + AI disclosure + licences |
| 31 Oct, 9:30 pm | Code freeze; two full demo rehearsals; submit by 11 pm |

**Definition of done for the prototype:**
1. One command runs quick + full tiers on our F1 photos offline and writes `run.json` with stage times, peak memory, area and GSD.
2. `accuracy.json` comes from our checkpoints, with N and method stated, plus relative distances.
3. `segments.geojson` with status per vehicle type for every road segment in the footprint.
4. All four measure endpoints work. `docs/validation.md` compares tool vs tape for at least one span, one pile and the staged block.
5. The F1 vs F5 staged change is detected, with a table of hits and misses.
6. Exports open in QGIS and Google Earth (tested), and the PDF prints.
7. The whole demo runs with Wi-Fi off, and a phone opens the map over the local network.
8. The README states what's real, what's simulated (staged change, public datasets) and what's estimated, plus licences and AI disclosure.

---

## 16. Your first session: do these in order

Each step ends with something we can check. Stop and report after each one.

1. **Machine check:** write `data/machine.json` (CPU, cores, RAM, GPU, OS, free disk). Show it to me.
2. **Docker check:**
   - run `docker version` and pull `opendronemap/odm`
   - report the image tag and size
   - if there's an NVIDIA GPU, also pull `opendronemap/odm:gpu`
3. **Skeleton:**
   - create the layout in section 5
   - create `PLAN.md` with owners, timeline, a bug table, a decisions log and a placeholders list
   - create `.gitignore` (excluding `data/` except `data/LICENSES.md`), `docs/AI_DISCLOSURE.md` and `data/LICENSES.md`
   - show the tree
4. **Contracts:**
   - write the JSON Schemas and mock examples from section 6
   - add a tiny test that validates every example against its schema
   - run it
5. **Smoke test:**
   - download the ODM sample `mygla`, or another small set if the link fails, and record its licence status
   - run the quick tier through `pipeline/run_odm.py`, with benchmark capture
   - show `run.json` and confirm the orthophoto opens (print its size and coordinate system with rasterio)
6. **Full tier** on the same set. Confirm `dsm.tif` and `dtm.tif` exist; print pixel size and value range.
7. **Measure stubs:**
   - implement `measure/span.py` on the smoke-test DSM with a hand-drawn line, saving the profile PNG
   - wire `POST /measure/span` in FastAPI
   - check it returns `measurement.json`
8. **Report** what works, the times you measured, and what's next. Ask me for the site's location once the flight is done, so we can run the prefetch scripts.

---

## 17. Placeholders and open questions

**Placeholders:**
- `[lead name]`
- `<you>` (Windows user folder)
- pinned image tags
- vehicle passability thresholds
- helicopter dimensions and slope limit
- bridging panel rule
- working-space requirement
- road width defaults by class
- `obstruction_min_m`, `bank_drop_min_m`
- population source (teammate)

**Open questions:**
- **Laptop specs:** RAM and GPU decide the tiers.
- **Neo4j track:** has our registration been switched from the General track?
- **Prototype form:** what exactly does the submission form ask for?
- **RTK:** does the drone partner have it?

---

## 18. Sources

- [OpenDroneMap README (Docker, Windows, video + SRT)](https://raw.githubusercontent.com/OpenDroneMap/ODM/master/README.md)
- [OpenDroneMap: options and flags](https://docs.opendronemap.org/arguments/)
- [OpenDroneMap: outputs](https://docs.opendronemap.org/outputs/)
- [OpenDroneMap: flying tips](https://docs.opendronemap.org/_sources/flying.rst.txt)
- [OpenDroneMap: sample datasets](https://oauth.opendronemap.org/odm/datasets/)
- [Neo4j: GDS on Docker](https://neo4j.com/docs/graph-data-science/current/installation/installation-docker/)
- [Find-GCP (ArUco markers)](https://github.com/zsiki/Find-GCP)
- [ASPRS Positional Accuracy Standards, Ed. 2 (LIDAR Magazine, 2023)](https://lidarmag.com/2023/10/06/the-asprs-positional-accuracy-standards-edition-2/)
- [Goa Directorate of Civil Aviation: helicopter operations](https://dca.goa.gov.in/wp-content/uploads/2020/07/Helicopter-operations.pdf)
- [Copernicus DEM: accuracy and licence](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)
- [Copernicus DEM on AWS](https://registry.opendata.aws/copernicus-dem/)
- [Earth Search STAC (Element 84)](https://github.com/Element84/earth-search)
- [Geofabrik India extracts](https://download.geofabrik.de/asia/india.html)
- [Google Open Buildings V3 (CC BY 4.0)](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings_v3_polygons)
- [USGS South Fork debris flow point cloud](https://cmgds.marine.usgs.gov/catalog/pcmsc/DataReleases/ScienceBase/DR_P144KDGN/SEKI_SouthFork_DebrisFlow_2024-04-30_pointcloud_metadata.html)
- [USGS Medina River UAS imagery](https://catalog.data.gov/dataset/uas-imagery-and-related-products-collected-for-structure-from-motion-work-obtained-by-usin)
- [USGS Mud Creek landslide video](https://www.usgs.gov/media/videos/uas-video-july-19-2017-mud-creek-landslide-big-sur)
- [CRASAR road damage benchmark (arXiv 2025)](https://arxiv.org/pdf/2512.12128)
- [CRASAR model card (MIT licence)](https://huggingface.co/CRASAR/CRASAR-U-DROIDs-RDA_AAAI26_Full_Pretrained_ScaleMAE_UPerNet/blob/main/README.md)
- [Sarvam Translate on AIKosh (GPL-3.0)](https://aikosh.indiaai.gov.in/home/models/details/sarvamtranslate.html)
- [Onmanorama: Wayanad Bailey bridge, 2024](https://onmanorama.com/news/kerala/2024/08/01/wayanad-landslide-army-constructs-bailey-bridge-in-chooralmala.html)
- [hackFront India 2026 event page](https://whereuelevate.com/drills/hackfrontindia-2026)
