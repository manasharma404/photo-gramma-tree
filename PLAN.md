# PLAN.md: Project Typhon, team Vortex (hackFront T8.2 "The First Map After The Landslide")

**Status: APPROVED by the lead, 31 Oct 00:30 IST.** Single source of truth for owners, timeline, bugs and decisions. Brief: `CLAUDE.md` (Update 2 overrides Update 1 overrides the rest).

## Facts checked on 31 Oct, 00:15 IST
| Item | Value | How checked |
|---|---|---|
| CPU | Intel Core i5-13420H | `Win32_Processor` |
| RAM | 15.7 GB visible to Windows (16 GB installed) | `Win32_ComputerSystem` |
| GPU | RTX 4050 Laptop, 6 GB, driver 592.82 | `nvidia-smi` |
| **Free disk** | 17 GB on C: (only drive) at first; **47.3 GB after the Docker cleanup (D1)**. The brief assumed ~119 GB | `Get-PSDrive` |
| Docker | Installed, **engine not running** | `docker version` |
| `.wslconfig` | Does not exist yet | `Test-Path` |
| ffmpeg/ffprobe | 9.0.2 installed | `Get-Command` |
| exiftool | **Not installed** | `Get-Command` |
| Neo 2 clip 0148 | 4K HEVC, 59.94 fps, 56.1 s, 56.6 Mb/s, 379 MB, created 20 Aug 17:39 UTC (23:09 IST) | `ffprobe` |
| Neo 2 clip 0149 | 4K HEVC, 59.94 fps, 177.1 s, 56.5 Mb/s, 1.25 GB, created 20 Aug 17:40 UTC (23:10 IST) | `ffprobe` |
| Telemetry | Both files carry a DJI `dvtm_NEO2.proto` data stream ("CAM meta"). **GPS in every frame** (decoded by `pipeline/dji_telemetry.py`; exiftool 13.59 cannot read it). See step 4 in the decisions log | `pipeline.video_check` |
| Stabilisation | `EIS:RS` (electronic stabilisation, rolling shutter) | MP4 comment tag |
| Content | Night, floodlit grass football ground, players moving, mostly oblique view, buildings behind | 5 sampled frames, viewed |

**What the footage means:** it is lit well enough to see, but plain grass, moving people, an angled camera and stabilisation warping (EIS) all work against mapping. Expect a weak or failed reconstruction. That's fine: the brief says to keep it as "what responders have today" and report the failure with numbers. **South Fork (USGS) carries our accuracy and measurement claims.**

## Owners
| Area | Folders | Owner |
|---|---|---|
| Map, measurements, everything on screen | `pipeline/ accuracy/ measure/ roads/`, all of `web/` (map, 3D, panels, styling) | Lead + Claude |
| Decisions, field delivery, exports | `advisor/ quality/ ml/ api/ neo4j/ export/`, `scripts/qr.py`, `config/vehicles.yaml`, `config/priority.yaml` | Teammate (see `TEAMMATE.md` v3, prompts `docs/teammate_prompt.md`, `docs/teammate_followup_1.md`) |
| Shared, frozen once approved | `contracts/`, this file | Lead decides |

## Work plan (lead + Claude), one feature at a time
| # | Step | Done when | Target (IST) |
|---|---|---|---|
| 1 | Machine check → `data/machine.json`; start Docker; GPU check; **pull one ODM image** (GPU first, CPU only if GPU fails, to save disk) | JSON shown; `nvidia-smi` runs inside the container; image tag pinned here | 01:00 |
| 2 | Skeleton: `git init` on `main`, `.gitignore`, `README`, `docs/AI_DISCLOSURE.md`, `data/LICENSES.md`; Python venv + `requirements.lock` | Tree shown | 01:30 |
| 3 | Contracts: schemas + mock examples (incl. the 3 new ones below) + a test that validates them | Test passes | 02:00 |
| 4 | Neo 2 check → `data/raw/neo2/video_report.json`: ffprobe, telemetry decode (GPS yes/no), brightness and sharpness on ~20 frames | Report shown | 02:30 |
| 5 | USGS South Fork: RTK CSV + **smallest** image zip; EXIF GPS of every image; plot centres vs tarps; `subset.txt` (~150 images); licence logged; datum read from CSV | Plot + subset shown | 04:00 |
| 6 | Quick tier on the subset → `run.json` (stage times, peak memory, area, GSD) | Orthophoto opens with rasterio | 06:00 |
| 7 | Accuracy: find tarps in orthophoto (template match, else manual click), datum conversion, errors → `accuracy.json` with N | Numbers from a run, N stated | 09:00 |
| 8 | Full tier → DSM/DTM; heights vs RTK topography (absolute + relative) → `docs/validation.md` | Table filled from runs | 12:00 |
| 9 | Neo 2 video tier (frame selection uses our sharpness check now, teammate's ML scores later); report result or failure with numbers | Result or failure written up | 13:00 |
| 10 | Measure: volume over a deposit, landing zones, span (if a channel exists), working space, as `measure.router`; `accuracy.router` for `/spec`. **`roads/`**: OSM ways clipped to the map, ≤ 50 m segments, DSM cross-sections → `segments.geojson` + `places.geojson` (incl. landing zones); write it during ODM waits, test on a synthetic DSM, hand to the teammate ~15:00 | Endpoints return `measurement.json`; both GeoJSONs validate | 15:00 |
| 11 | Web: MapLibre 2D map, three.js terrain from DSM + orthophoto, **data panels** (road status per vehicle from `GET /advisor/state`, priorities, measurements, accuracy, field reports), spec card; styling. Built against contract mocks first. **Her** `api/` app serves it and mounts our routers | Runs offline, screenshot | 18:00 |
| 12 | Exports: COG, KMZ, GPKG, GeoJSON, PDF; each opened in its target app | Opened in QGIS / Google Earth | 19:00 |
| 13 | README (what's real / public / estimated, how to run), offline check (Wi-Fi off, phone on hotspot) | README complete; phone opens the map | 20:30 |
| 14 | **Round 1 submission: a PPT + the GitHub link** (no live demo, no rehearsal). Slides use only numbers from runs; placeholders listed, not invented | PPT ready, repo link works from a fresh clone | 23:00 |
| — | **Code freeze 21:30**, submit by 23:00 | | |

**If we slip:** steps 9 and 12's PDF are the first to shrink; Medina River change detection is already skipped unless time appears (say so in the README).

## New contracts to freeze with the teammate (proposed)
1. **`image_quality.json`** (teammate's ML → `pipeline/`): see `contracts/image_quality.schema.json`: `{mock, method: "ml_model"|"standard_check", model, version, source, items: [{image: "<file or video:frame_index>", score: 0-1, usable, reasons: [...]}]}`. The pipeline uses it to drop frames before ODM. Until it arrives, `pipeline/` uses our own brightness + Laplacian sharpness check, labelled **"standard sharpness check"**, never "AI".
2. **Advisor router:** her module exposes `advisor.router` (a FastAPI `APIRouter`) and a static folder for the phone page. We mount it at `/advisor` and serve the page at `/field`.
3. **`GET /advisor/state`:** `{"mock": bool, "segments": [{"segment_id", "status_by_mode": {"truck","jeep","foot"}, "source": "geometry|field_report|scenario"}], "updated_at"}`. `web/` colours roads only from this.
4. Existing contracts from the brief stay as written: `segments.geojson`, `places.geojson`, `ml_scores.json`, `access_report.json`.

## Decisions needed from the lead
| # | Question | My recommendation |
|---|---|---|
| D1 | **Disk: 17 GB free, brief wants ≥30 GB free during ODM runs.** | Pull only the GPU ODM image; download one USGS zip at a time and delete it after extracting; move (not copy) the two videos into `data/raw/neo2/`; and if you can, free ~15 GB yourself (I won't delete anything of yours). |
| D2 | Install exiftool? | Yes (winget, ~10 MB). Needed for the GPS check the brief asks for; I'll also try decoding the DJI telemetry stream directly. |
| D3 | `.wslconfig`: `memory=12GB, swap=16GB, processors=10` per Update 2. Swap also lives on C:. | Use `swap=8GB` instead, because of D1. Needs a WSL restart. |
| D4 | Folder location: `Desktop\hackfront\vortex`, git on `main`, no GitHub remote yet. | Keep it there; add the remote when you give me the URL. |

## Decisions log
| When | Decision | By |
|---|---|---|
| 31 Oct 00:15 | Project folder `vortex` created at `Desktop\hackfront\vortex` with the Update 2 layout | Claude (default; lead to confirm) |
| 31 Oct 00:30 | PLAN.md and TEAMMATE.md approved; D2–D4 approved as recommended | Lead |
| 31 Oct 00:30 | D1 (disk): lead frees space by cleaning RAKSHAM's Docker data (project `farq`). Docker's disk file is 47.4 GB: 18.3 GB build cache, 9.4 GB images, 3.8 GB volumes, ~16 GB already-deleted space not yet returned to Windows. Plan: stop farq, turn off its auto-restart, prune build cache, trim and compact the disk file. Images and volumes (RAKSHAM's data) are kept | Lead runs it; Claude verifies sizes after |
| 31 Oct 00:50 | D1 result, measured: Docker disk file 47.4 → 15.7 GB; C: free 17 → 47.3 GB. RAKSHAM images and volumes kept; its containers no longer auto-start | Claude measured |
| 31 Oct 01:00 | Step 1 done. ODM pinned: `opendronemap/odm:gpu@sha256:c6ecdec7764094732248517c51d6430fbc9dad61b586daafded04745026d9ed8` (9.38 GB, built ~2 months ago). `nvidia-smi` inside it sees the RTX 4050 (6 GB). CPU image not pulled. Docker sees 12 GB RAM, 10 CPUs. C: free after the pull: 31.3 GB | Claude measured |
| 31 Oct 01:20 | Step 2: git on `main`; Python env via `uv` (Python 3.12.15, since uv could not install 3.11; brief says 3.11+); `uv.lock` + `requirements.lock`. Lead offered to move data to an external drive if disk-saving gets in the way | Claude |
| 31 Oct 01:25 | Step 3: 10 contracts in `contracts/` (schema + mock example each), `tests/test_contracts.py` 24/24 pass. **Changes from the brief's section 6:** `run.tier` adds `video`, optional `inputs.quality_filter`; `accuracy.used_gcps` is fixed to `false`, `found_by` adds `template` (USGS tarps), optional `datum_note`; `ml_scores.json` is wrapped as `{mock, scores: [...]}` so it can carry `mock`; `measurement.tolerance.unit` adds `m2`, `deg`; `image_quality.json` puts `method` (`ml_model` / `standard_check`), `model`, `version` at the top instead of per item; new `places.geojson` (adds `kind`, `source`, `nearest_segment_id`) and `advisor_state` schemas | Claude; lead to confirm |
| 31 Oct 02:00 | Lead: teammate prompt waits until she finalises her scope; focus on the lead's work | Lead |
| 31 Oct 02:00 | Step 5 blocked: ScienceBase (and its S3 / CMGDS mirrors) refuse scripts behind a Cloudflare bot check; the lead downloads the RTK CSV and smallest image zip by hand | Lead |
| 31 Oct 02:10 | **Work division (TEAMMATE.md v3):** her six docs are hers except R1 (accuracy validator, lead). Moved to her: `roads/` (segment measurements), `api/` app shell + offline serving + QR + hotspot, `web/src/panels/`, status per vehicle with reasons, quality checks. Lead keeps ODM pipeline, accuracy, `measure/` (span, volume, landing zones, working space), exports, map + 3D + all styling | Lead (rule), Claude (details) |
| 31 Oct 02:10 | **Contract changes:** modes are `fire_truck, ambulance, jeep, foot` (was truck/jeep/foot; N1 picked by Claude under the lead's "decide this") in `segments`, `advisor_state`, `access_report`; `segments.status_by_mode` and `decision` optional (status comes from `/advisor/state`); `advisor_state` adds `reasons_by_mode`, `needs_verification`; `access_report.reopen_plan` adds `mode`, `reasons`; new `priorities.json` (`decision_support: true` enforced); `image_quality.json` optional `coverage` block. 32 tests pass | Claude |
| 31 Oct 02:30 | Repo pushed to GitHub `manasharma404/photo-gramma-tree` (`main`), merged with GitHub's starter commit; fresh clone installs and passes 32 tests. At the lead's request, Claude co-author lines were removed from all commits and force-pushed (explicit go; teammate had not cloned) | Lead |
| 31 Oct 02:45 | **Step 5 (USGS) findings.** Lead downloaded `F01-5` (109 images) and `F02-2` (61) + RTK CSV. Image EXIF: WGS84 (G1150), ellipsoid heights; USGS states ~3 m horizontal, ~10 m vertical. **RTK CSV datum not stated** in the file; its metadata page is not on the CMGDS mirror (404). Likely NAD83(2011) + NAVD88 (orthometric − ellipsoid ≈ 28.3 m in the file) → must confirm before step 7; NAD83 vs WGS84 is ~1–1.5 m here. **The zips are flight-line fragments:** `F01-5` is one strip along the flow over targets SF08–SF13 (7 of 23 targets under any image, 6 seen by ≥3); `F02-2` is separate short passes. Subset = all 109 `F01-5` images (`subset.txt`, `subset.json`, `subset.png`). A single strip has no side overlap: expect weaker geometry; a neighbouring strip (likely `F01-4`) would make a proper block | Claude measured |
| 31 Oct 03:20 | **Step 6 done: first quick tier**, run `2026-10-31_0227_southfork_f01_5_quick`. 109/109 images reconstructed in 1 component (130,280 sparse points). **50.4 min total** (opensfm 34.1 min, texturing 11.2, orthophoto 2.4), **peak memory 6.97 GiB** (docker stats, 2 s samples), **orthophoto valid area 10.12 ha**, pixel size 5.0 cm (set by `--orthophoto-resolution 5`; capture GSD stated by USGS is 2.9 cm), EPSG:32611 → about 5.0 min/ha for this tier on this laptop. ODM's own report gives 15.3 m average "GPS error" (camera GPS vs reconstruction, internal, not our checkpoint accuracy). The orthophoto has two pieces with a gap between them (no images there); targets SF10, SF11, SF19–SF23 fall inside. **GPU was probably not used for features** (no GPU line in the log; ODM's default feature type is likely CPU-only) → test `--feature-type sift` next run. **Disk:** C: free 36.4 → 21.2 GB; project folder 5.2 GB, Docker's disk file grew 15.7 → 26.0 GB (space inside it is reused by later runs, but not returned to Windows) | Claude measured |
| 31 Oct 04:10 | **Step 7, first accuracy result (single-strip diagnostic).** Targets are ~0.5–0.8 m white squares with bluish "bowtie" triangles (some black/white checker); `accuracy/find_targets.py` finds them by white + bluish pixels; IDs assigned by consistent shift and confirmed visually (crops in `data/runs/2026-10-31_0227_.../targets/`; lead to re-confirm). Confident: SF10, SF11 → `accuracy.json` **N = 2, horizontal RMSE 35.0 m** (max 35.1). SF09, SF12, SF18/19 are visible but their IDs are ambiguous → excluded. **Cause, measured:** the 50 camera positions over this part form a line (150 m long, 4.2 m across-track spread), so the reconstruction can roll about the flight line; both shifts are 34.7–34.8 m across-track, 3–5 m along-track. Not a GPS-accuracy number: a capture-geometry failure. **Capture-protocol rule: never map from one straight line; fly ≥ 2 parallel lines.** Proper accuracy needs a neighbouring strip (likely `F01-4`, 1.89 GB). Datum (NAD83 vs WGS84, ~1–1.5 m) still unconfirmed, negligible at this error | Claude measured |
| 31 Oct 04:40 | **Step 8 (full tier, single strip):** run `2026-10-31_0337_southfork_f01_5_full`, done, 66.6 min **incremental** (reused matching), peak 7.01 GiB, 9.07 ha, DSM/DTM at 0.10 m (range ~1159–1359 m). DTM vs 823 RTK ground points: mean +58.6 m, std 7.6 m, tilt −8.4° across track. Focal length and flying height in the model are right; the images' GPS altitudes read ~146 m above ground vs ~110 m stated, so the vertical offset comes mostly from GPS altitude + roll tilt. Full write-up: `docs/validation.md` | Claude measured |
| 31 Oct 08:30 | **Block run (USGS F01-4, 5 parallel lines), quick tier:** run `2026-10-31_0546_southfork_f01_4_quick`, 248/248 images in 1 component, **145.6 min**, **peak 8.61 GiB**, **12.94 ha** → ~11.2 min/ha. GPU feature extraction confirmed (`ROOT_SIFT_GPU`, 149 s for 248 images vs ~5 s/image on CPU in the strip run); matching + reconstruction dominate (opensfm 110 min, incl. ~20 min undistorting through the Docker file mount). **Accuracy: N = 3 checkpoints (SF16, SF17, SF18), horizontal RMSE 6.42 m, max 7.88 m**, a consistent ~1 m W / 5–8 m N shift (part may be the unconfirmed NAD83/WGS84 datum, ~1–1.5 m). SF15, SF19, SF20 not identifiable at 5 cm. Full tier started (reusing matching). Lead freed 22 GB on C: | Claude measured |
| 31 Oct 08:20 | Lead's hero image (illustration, captioned as such) and logo SVGs added; logo recoloured for light UI by `web/scripts/make_logo.py` | Lead |
| 31 Oct 07:35 | **Product name: Project Typhon** (team name stays Vortex; repo name unchanged; internal code names like `VORTEX_*` unchanged). Brand kit v1.0 adopted for the UI; status colours chosen by Claude within the brand (open green solid, partial amber dashed, blocked red thick + ✕, unknown grey dotted, needs-verification ocean ring). Landing page kept: lead supplies one hero image; Claude overlays the rest. Mockup data is decorative only: the app shows only our measured values | Lead |
| 31 Oct 06:30 | **Round 1 deliverable = PPT + GitHub link**; no rehearsals (lead). Step 11 (UI) is design-led: the lead designs, Claude implements against `docs/ui_layout_brief.md`; visual decisions stay with the lead | Lead |
| 31 Oct 05:45 | **Teammate round 1 reviewed and merged into `main`** (branch `teammate` @ `be4ed92`, 9 commits, 03:44–04:28): all files inside her folders; rules labelled "never AI"; 59 `PLACEHOLDER`s; no runtime internet or CDN; 68 tests pass on `main` after merge (2 skipped). Not verified for real: Neo4j (sandbox), Wayanad prefetch, field page on a phone, ML gate; some sources are home-page only. Lead's question "was her work limited?": no; she finished all Must and Should items as code quickly; the gaps are verification. | Lead (merge rule), Claude (review) |
| 31 Oct 05:50 | **Exports move to the teammate** (`export/`), so the lead's side keeps pipeline, accuracy, measure, roads and web. `docs/teammate_followup_1.md` lists everything she can finish without us; follow-up 2 comes when our real outputs exist | Lead |
| 31 Oct 05:40 | `F01-4` (248 images) downloaded and extracted: a **block of 5 parallel flight lines** over targets SF15–SF20 (6 targets, all seen by ≥ 3 images). Quick tier started on it with `--feature-type sift` (GPU test); first attempt failed in 0.4 s because Docker Desktop had stopped while the laptop slept, relaunched | Claude |
| 31 Oct 02:20 | Rebalance: `roads/` (T9) and the data panels (T10) move back to the lead. Reason: T9 needs our DSM and `measure/` code and fits our ODM waits; panels keep all of `web/` with one owner who also does styling. Her 8 Must items can all start on mock data now | Lead |
| 31 Oct 02:00 | Step 4 done → `data/raw/neo2/video_report.json` (+ `<clip>_track.csv`). Videos moved from Downloads. **GPS:** 3363/3363 frames (clip 0148) and 10615/10615 (clip 0149); flight extent 29.5 × 37.1 m and 50.9 × 74.0 m; paths 87.6 m and 390.3 m. Altitude field reads 299.8–325.8 m, reference unknown (not used for anything yet). **Brightness:** median luma 98.7 / 101.2 of 255, 0 of 20 frames dark. **Sharpness:** Laplacian variance median 27.1 / 34.5; 18 of 20 frames per clip under the PLACEHOLDER blur threshold of 100. ISO (inferred field) reached 4250 / 6400, so night noise reduction likely softens detail. Threshold is uncalibrated, so this is a warning, not a verdict: the video tier run decides | Claude measured |
| 31 Oct 02:00 | Step 9 approach changed: since the GPS exists, extract frames ourselves, drop bad ones (standard check now, teammate's `image_quality.json` later), write GPS into each frame's EXIF, then run ODM on images. This replaces ODM's MP4+SRT path and gives the video map a real position and scale (consumer-GPS accuracy, to be stated) | Claude; lead to confirm |

## Bug table
| # | Bug | Owner | Status |
|---|---|---|---|
| — | none yet | | |

## Placeholders (until sourced)
Pinned image tags (ODM, Neo4j) · vehicle passability thresholds · helicopter dimensions and slope limit · bridging panel rule · working-space requirement · road width defaults by class · `obstruction_min_m`, `bank_drop_min_m` · population source (teammate).
