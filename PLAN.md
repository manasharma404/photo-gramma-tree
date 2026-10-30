# PLAN.md: Vortex (hackFront T8.2 "The First Map After The Landslide")

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
| Telemetry | Both files carry a DJI `dvtm_NEO2.proto` data stream ("CAM meta"); **may** hold GPS, not decoded yet | first bytes of stream 1 |
| Stabilisation | `EIS:RS` (electronic stabilisation, rolling shutter) | MP4 comment tag |
| Content | Night, floodlit grass football ground, players moving, mostly oblique view, buildings behind | 5 sampled frames, viewed |

**What the footage means:** it is lit well enough to see, but plain grass, moving people, an angled camera and stabilisation warping (EIS) all work against mapping. Expect a weak or failed reconstruction. That's fine: the brief says to keep it as "what responders have today" and report the failure with numbers. **South Fork (USGS) carries our accuracy and measurement claims.**

## Owners
| Area | Folders | Owner |
|---|---|---|
| Mapping and 3D | `pipeline/ accuracy/ measure/ roads/ export/ web/ api/` | Lead + Claude |
| Route advisor | `advisor/` (Neo4j, routing per vehicle, dead-end reports, phone page) | Teammate |
| ML | `ml/` (image-quality model; road-status model optional) | Teammate |
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
| 10 | Measure: volume over a deposit, landing zones, span (if a channel exists), working space; `roads/segments.geojson` + `places.geojson` for South Fork → hand to teammate | Endpoints return `measurement.json` | 16:00 |
| 11 | API + web: FastAPI, MapLibre 2D, three.js terrain from DSM + orthophoto, road colours from `GET /advisor/state`, spec card; mount teammate's router at `/advisor` and page at `/field` | Runs offline, screenshot | 18:00 |
| 12 | Exports: COG, KMZ, GPKG, GeoJSON, PDF; each opened in its target app | Opened in QGIS / Google Earth | 19:00 |
| 13 | Offline test (Wi-Fi off, phone on hotspot); README disclosure; runbook | Phone opens the map | 20:30 |
| — | **Code freeze 21:30**, two rehearsals, submit by 23:00 | | |

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

## Bug table
| # | Bug | Owner | Status |
|---|---|---|---|
| — | none yet | | |

## Placeholders (until sourced)
Pinned image tags (ODM, Neo4j) · vehicle passability thresholds · helicopter dimensions and slope limit · bridging panel rule · working-space requirement · road width defaults by class · `obstruction_min_m`, `bank_drop_min_m` · population source (teammate).
